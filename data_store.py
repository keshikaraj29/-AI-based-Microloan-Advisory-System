"""Indexed, read-only SQLite access for request handlers.

Build the database once with ``python scripts/prepare_data.py``. Connections
are bounded, exclusively checked out, safe across Flask worker threads, and
never held by a request after it returns. No spreadsheet parsing occurs here.
"""
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from queue import LifoQueue, Empty
import os
import sqlite3
import statistics
import threading

BASE_DIR = Path(__file__).resolve().parent


class SQLitePool:
    def __init__(self, path, size=4, timeout=5, read_only=True):
        self.path = Path(path).resolve()
        self.size = max(1, min(int(size), 16))
        self.timeout = timeout
        self.read_only = read_only
        self._queue = LifoQueue(maxsize=self.size)
        self._pid = os.getpid()
        self._lock = threading.Lock()
        self._created = 0
        self._identity = None
        self._generation = 0

    def _refresh_generation(self):
        """Close old idle handles when the offline importer replaces the file."""
        stat = self.path.stat()
        identity = (os.getpid(), stat.st_dev, stat.st_ino)
        if identity != self._identity:
            while True:
                try:
                    self._queue.get_nowait().close()
                except Empty:
                    break
            self._queue = LifoQueue(maxsize=self.size)
            self._created = 0
            self._pid = os.getpid()
            self._identity = identity
            self._generation += 1

    @contextmanager
    def connection(self):
        # A preloaded WSGI application may fork before its first request.
        with self._lock:
            self._refresh_generation()
            generation = self._generation
            queue = self._queue
            try:
                conn = self._queue.get_nowait()
            except Empty:
                conn = None
                if self._created < self.size:
                    conn = sqlite3.connect(self.path.as_uri() + ('?mode=ro' if self.read_only else '?mode=rw'), uri=True,
                                           check_same_thread=False, timeout=self.timeout)
                    conn.row_factory = sqlite3.Row
                    conn.execute('PRAGMA query_only = ' + ('ON' if self.read_only else 'OFF'))
                    conn.execute('PRAGMA foreign_keys = ON')
                    conn.execute(f'PRAGMA busy_timeout = {int(self.timeout * 1000)}')
                    self._created += 1
        if conn is None:
            try:
                conn = queue.get(timeout=self.timeout)
            except Empty as exc:
                raise TimeoutError('Database is busy. Please retry shortly.') from exc
        try:
            yield conn
        finally:
            if conn.in_transaction:
                conn.rollback()
            with self._lock:
                if generation == self._generation:
                    self._queue.put(conn)
                else:
                    conn.close()


class DataStore:
    def __init__(self, path=None, pool_size=4):
        self.path = Path(path or os.environ.get('PP1_DATABASE', BASE_DIR / 'data' / 'pp1.sqlite3'))
        self.pool = SQLitePool(self.path, pool_size)

    def table_counts(self):
        with self.pool.connection() as conn:
            return {t: conn.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
                    for t in ('loans', 'market_prices', 'farm_records', 'dairy_records')}

    def market_locations(self):
        return list(self._market_locations(self._version()))

    def _version(self):
        stat = self.path.stat()
        return stat.st_dev, stat.st_ino, stat.st_mtime_ns

    @lru_cache(maxsize=1)
    def _market_locations(self, version):
        with self.pool.connection() as conn:
            rows = conn.execute('SELECT name FROM locations ORDER BY name').fetchall()
        return tuple(r[0] for r in rows)

    @lru_cache(maxsize=256)
    def _market_price(self, location, commodity, months, version):
        # Each branch uses its own composite lookup index. UNION removes a
        # record matching both its district and market name.
        clauses, values = [], []
        for field in ('district_key', 'market_key', 'state_key'):
            clause = f'SELECT id FROM market_prices WHERE {field}=? AND commodity_key=?'
            values.extend((location, commodity))
            if months:
                clause += ' AND month IN (' + ','.join('?' for _ in months) + ')'
                values.extend(months)
            clauses.append(clause)
        sql = ('SELECT modal_price, price_date FROM market_prices WHERE id IN ('
               + ' UNION '.join(clauses) + ')')
        with self.pool.connection() as conn:
            rows = conn.execute(sql, values).fetchall()
        if not rows:
            return None
        prices = [r[0] for r in rows]
        return {'median_price': round(statistics.median(prices), 2),
                'mean_price': round(statistics.mean(prices), 2),
                'observations': len(prices), 'price_unit': 'INR per quintal',
                'latest_date': max(r[1] for r in rows),
                'source': 'Supplied AGMARKNET historical workbook (2024–2025)'}

    def market_price(self, location, commodity, months=None):
        month_tuple = tuple(sorted(set(int(x) for x in (months or ()))))
        if any(x < 1 or x > 12 for x in month_tuple):
            raise ValueError('Months must be between 1 and 12.')
        result = self._market_price(str(location or '').strip().casefold(),
                                    str(commodity or '').strip().casefold(), month_tuple, self._version())
        return dict(result) if result else None


@lru_cache(maxsize=1)
def get_store():
    """Return the process-local store (PP1_DATABASE overrides its path)."""
    return DataStore(pool_size=int(os.environ.get('PP1_DB_POOL_SIZE', '4')))
