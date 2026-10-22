"""Data correctness, deterministic ingestion and concurrent read regression tests."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
import csv
import gzip
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from data_store import DataStore, SQLitePool, get_store
from research_analytics import clean_narrative, get_research_summary, narrative_sentiment, query_loans

spec = importlib.util.spec_from_file_location('prepare_data', ROOT/'scripts'/'prepare_data.py')
prepare_data = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare_data)


def test_pool_bounds_readonly_and_exception_release(tmp_path):
    path = tmp_path/'sample.db'
    conn = sqlite3.connect(path)
    conn.execute('CREATE TABLE example(value INTEGER)')
    conn.execute('INSERT INTO example VALUES (42)')
    conn.commit()
    conn.close()
    pool = SQLitePool(path,size=2,timeout=.01)
    with ExitStack() as stack:
        stack.enter_context(pool.connection())
        stack.enter_context(pool.connection())
        with pytest.raises(TimeoutError):
            with pool.connection():
                pass
    with pytest.raises(sqlite3.OperationalError):
        with pool.connection() as conn:
            conn.execute('DELETE FROM example')
    def read(_):
        with pool.connection() as conn:
            return conn.execute('SELECT value FROM example').fetchone()[0]
    with ThreadPoolExecutor(max_workers=8) as executor:
        assert list(executor.map(read,range(80))) == [42]*80
    assert pool._created == 2


def test_pool_refreshes_after_atomic_database_rebuild(tmp_path):
    path = tmp_path/'sample.db'
    def create(path,value):
        conn = sqlite3.connect(path)
        conn.execute('CREATE TABLE example(value INTEGER)')
        conn.execute('INSERT INTO example VALUES (?)',(value,))
        conn.commit()
        conn.close()
    create(path,42)
    pool = SQLitePool(path,size=2)
    with pool.connection() as original:
        assert original.execute('SELECT value FROM example').fetchone()[0]==42
        replacement = tmp_path/'rebuilt.db'
        create(replacement,99)
        replacement.replace(path)
        with pool.connection() as refreshed:
            assert refreshed.execute('SELECT value FROM example').fetchone()[0]==99
    with pool.connection() as refreshed:
        assert refreshed.execute('SELECT value FROM example').fetchone()[0]==99
    assert pool._created==1


def test_reservoir_reproducible_and_preserves_source_rows(tmp_path):
    path = tmp_path/'loans.csv.gz'
    fields = ['loan_amnt','term','int_rate','annual_inc','dti','purpose','loan_status','desc']
    with gzip.open(path,'wt',newline='') as f:
        writer = csv.DictWriter(f,fieldnames=fields)
        writer.writeheader()
        for i in range(501):
            writer.writerow({'loan_amnt':100+i if i else '', 'term':'36 months',
                'int_rate':'10', 'annual_inc':'50000','dti':'20','purpose':'business',
                'loan_status':'Fully Paid','desc':f'Business expansion record {i}'})
    samples = []
    for _ in range(2):
        conn = sqlite3.connect(':memory:')
        prepare_data.schema(conn)
        stats = prepare_data.import_loans(conn,path,100)
        sample = conn.execute('SELECT source_row,loan_amount FROM loans ORDER BY id').fetchall()
        samples.append(sample)
        assert stats['valid_rows']==500 and stats['invalid_loan_amount_rows']==1
        assert len(sample)==100 and len({row[0] for row in sample})==100
        assert all(amount==99+row for row,amount in sample)
        conn.close()
    assert samples[0]==samples[1]


def test_only_one_importer_can_own_the_staging_files(tmp_path):
    with prepare_data.preparation_lock(tmp_path):
        with pytest.raises(RuntimeError,match='already running'):
            with prepare_data.preparation_lock(tmp_path):
                pass
    with prepare_data.preparation_lock(tmp_path):
        pass


def test_narrative_cleaning_and_negation():
    assert clean_narrative('Borrower added on 03/01/12 > <b>Growth</b> me@example.com')=='Growth'
    assert narrative_sentiment('stable profitable growth')[1]=='positive'
    assert narrative_sentiment('not stable')[1]=='negative'
    assert narrative_sentiment('not a hardship')[1]=='positive'
    assert narrative_sentiment('No lexical evidence here')[1]=='neutral'


def test_missing_or_malformed_summary_has_actionable_error(tmp_path, monkeypatch):
    path = tmp_path/'summary.json'
    monkeypatch.setenv('PP1_RESEARCH_SUMMARY',str(path))
    with pytest.raises(RuntimeError,match='prepare_data'):
        get_research_summary()
    path.write_text('{broken json')
    with pytest.raises(RuntimeError,match='prepare_data'):
        get_research_summary()


@pytest.mark.skipif(not (ROOT/'data'/'research_summary.json').exists(),reason='Prepare data first')
def test_real_data_outcomes_and_paginated_filters():
    summary = get_research_summary()
    assert summary['dataset']['records']==sum(row['count'] for row in summary['clusters'])
    assert summary['metrics']['resolved_count']+summary['metrics']['unresolved_count']==summary['dataset']['records']
    assert summary['metrics']['avg_income_change_pct'] is None
    assert summary['metrics']['silhouette_score']>0
    with get_store().pool.connection() as conn:
        paid = conn.execute("SELECT count(*) FROM loans WHERE loan_status IN ('Fully Paid','Does not meet the credit policy. Status:Fully Paid')").fetchone()[0]
        assert abs(paid/summary['metrics']['resolved_count']-summary['metrics']['repayment_rate'])<1e-6
        fields = summary['methods']['cluster_features']
        assert not {'loan_status','repaid','total_pymnt','sentiment_score'} & set(fields)
        assert conn.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    page1,page2 = query_loans(page=1,page_size=10),query_loans(page=2,page_size=10)
    assert len(page1['items'])==10
    assert not {r['borrower_id'] for r in page1['items']} & {r['borrower_id'] for r in page2['items']}
    assert query_loans(purpose="' OR 1=1 --")['total']==0
    assert query_loans(page_size=1000)['page_size']==100
    assert all('description' not in row for row in page1['items'])


@pytest.mark.skipif(not (ROOT/'data'/'pp1.sqlite3').exists(),reason='Prepare data first')
def test_market_lookup_matches_sql_and_uses_index():
    store = get_store()
    quote = store.market_price('Auraiya','Wheat')
    assert quote and quote['price_unit']=='INR per quintal'
    with store.pool.connection() as conn:
        rows = conn.execute("SELECT modal_price FROM market_prices WHERE district_key='auraiya' AND commodity_key='wheat'").fetchall()
        assert quote['observations']==len(rows)
        assert abs(quote['mean_price']-sum(row[0] for row in rows)/len(rows))<.01
        plans = conn.execute("EXPLAIN QUERY PLAN SELECT id FROM market_prices WHERE district_key=? AND commodity_key=?",('auraiya','wheat')).fetchall()
        assert any('INDEX' in row[3] for row in plans)
    assert store.market_price('No such market','Wheat') is None
    assert store.market_price('AURAIYA','WHEAT')==quote
    with pytest.raises(ValueError):
        store.market_price('Auraiya','Wheat',[13])
