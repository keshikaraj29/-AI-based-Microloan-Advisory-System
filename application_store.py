"""Private local accounts, applications and manually recorded loan payments.

Uses the same SQLite file as the supplied research data, with separate tables.
Application projections are never inserted as observed LendingClub records.
No function moves money, connects to a bank or autonomously approves a loan.
All operations require an owner id established by the Flask login session.

Amounts are stored as integer paise. Tracking records a fixed installment
schedule; early payments cover that agreed schedule, without an invented
interest rebate or principal-only prepayment rule. References are idempotency
keys scoped to one application. A CSV import commits entirely or not at all.
"""
from calendar import monthrange
from contextlib import contextmanager
import csv
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from functools import lru_cache
import io
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import uuid

from werkzeug.security import check_password_hash, generate_password_hash
from data_store import BASE_DIR, SQLitePool
from narrative_sentiment import enrich_assessment

CENT = Decimal('0.01')
MAX_CSV_ROWS = 2000
MAX_CSV_BYTES = 1024 * 1024

SCHEMA = '''
CREATE TABLE IF NOT EXISTS application_schema (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS users (
 id INTEGER PRIMARY KEY, username TEXT NOT NULL COLLATE NOCASE UNIQUE,
 password_hash TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS applications (
 id TEXT PRIMARY KEY, owner_id INTEGER NOT NULL REFERENCES users(id),
 borrower_json TEXT NOT NULL, result_json TEXT NOT NULL, canonical_json TEXT NOT NULL,
 principal_cents INTEGER CHECK(principal_cents IS NULL OR principal_cents>0), annual_rate REAL NOT NULL,
 term_months INTEGER NOT NULL CHECK(term_months BETWEEN 1 AND 600),
 created_at TEXT NOT NULL, tracking_start_date TEXT, tracking_recorded_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_applications_owner ON applications(owner_id,created_at,id);
CREATE TABLE IF NOT EXISTS installments (
 id INTEGER PRIMARY KEY, application_id TEXT NOT NULL REFERENCES applications(id),
 installment_number INTEGER NOT NULL, due_date TEXT NOT NULL,
 principal_cents INTEGER NOT NULL CHECK(principal_cents>=0),
 interest_cents INTEGER NOT NULL CHECK(interest_cents>=0),
 UNIQUE(application_id,installment_number)
);
CREATE INDEX IF NOT EXISTS idx_installments_due ON installments(application_id,due_date);
CREATE TABLE IF NOT EXISTS payments (
 id INTEGER PRIMARY KEY, application_id TEXT NOT NULL REFERENCES applications(id),
 amount_cents INTEGER NOT NULL CHECK(amount_cents>0), paid_on TEXT NOT NULL,
 reference TEXT NOT NULL, recorded_at TEXT NOT NULL, recorded_by INTEGER NOT NULL REFERENCES users(id),
 UNIQUE(application_id,reference)
);
CREATE INDEX IF NOT EXISTS idx_payments_application_date ON payments(application_id,paid_on,id);
CREATE TABLE IF NOT EXISTS payment_allocations (
 payment_id INTEGER NOT NULL REFERENCES payments(id),
 installment_id INTEGER NOT NULL REFERENCES installments(id),
 principal_cents INTEGER NOT NULL CHECK(principal_cents>=0),
 interest_cents INTEGER NOT NULL CHECK(interest_cents>=0),
 PRIMARY KEY(payment_id,installment_id)
);
CREATE INDEX IF NOT EXISTS idx_payment_allocations_installment ON payment_allocations(installment_id,payment_id);
CREATE TABLE IF NOT EXISTS application_audit (
 id INTEGER PRIMARY KEY, application_id TEXT REFERENCES applications(id),
 owner_id INTEGER NOT NULL REFERENCES users(id), action TEXT NOT NULL,
 recorded_at TEXT NOT NULL, detail_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_application_audit_owner ON application_audit(owner_id,application_id,id);
'''


def _now():
    return datetime.now(timezone.utc).isoformat()


def _json(value):
    try:
        result = json.dumps(value,ensure_ascii=False,allow_nan=False,separators=(',',':'))
    except (TypeError,ValueError) as exc:
        raise ValueError('Application data must contain finite JSON values.') from exc
    if len(result.encode('utf-8'))>2*1024*1024:
        raise ValueError('Application data exceeds the 2 MiB record limit.')
    return result


def _money(value, minimum=Decimal('1.00')):
    if isinstance(value,bool):
        raise ValueError('Enter a monetary amount of at least INR 1 with at most two decimal places.')
    try:
        number = Decimal(str(value))
        if not number.is_finite() or number < minimum or number > Decimal('1000000000'):
            raise ValueError
        if number != number.quantize(CENT):
            raise ValueError
        return int(number * 100)
    except (ValueError,InvalidOperation,TypeError) as exc:
        raise ValueError(f'Enter a finite amount of at least INR {minimum}, at most INR 1 billion, with at most two decimal places.') from exc


PURPOSE_LABELS = {'debt_consolidation':'Debt consolidation','credit_card':'Credit card refinancing',
    'home_improvement':'Home improvement','other':'Other stated purpose','major_purchase':'Major purchase',
    'small_business':'Small business','car':'Vehicle','medical':'Medical expenses','moving':'Moving and relocation',
    'vacation':'Vacation','house':'Housing','wedding':'Wedding','renewable_energy':'Renewable energy',
    'educational':'Education','unknown':'Purpose needs clarification'}


def _category(borrower,result):
    category = result.get('category',{})
    category = category if isinstance(category,dict) else {}
    entities = result.get('entities',{})
    supplied = str(category.get('purpose') or borrower.get('loan_purpose') or borrower.get('purpose') or '').strip().casefold().replace(' ','_')
    label = str(category.get('label') or entities.get('category') or '')
    sector = str(category.get('sector') or '').casefold()
    if supplied not in PURPOSE_LABELS:
        fallback = label.casefold()
        supplied = 'small_business' if any(word in fallback for word in ('farm','dairy','business')) else 'unknown'
    return {'category':supplied,'category_label':label or PURPOSE_LABELS[supplied],
            'sector':sector or ('farm' if 'farm' in label.casefold() else 'dairy' if 'dairy' in label.casefold() else 'general')}


def _migrate_payment_minimum(conn):
    """Relax the v1/v2 constraint without losing existing payments/allocations."""
    sql = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='payments'").fetchone()[0]
    if not re.search(r'amount_cents\s*>=\s*100',sql):
        return
    conn.execute('''CREATE TABLE payments_v3 (
      id INTEGER PRIMARY KEY, application_id TEXT NOT NULL REFERENCES applications(id),
      amount_cents INTEGER NOT NULL CHECK(amount_cents>0), paid_on TEXT NOT NULL,
      reference TEXT NOT NULL, recorded_at TEXT NOT NULL, recorded_by INTEGER NOT NULL REFERENCES users(id),
      UNIQUE(application_id,reference))''')
    conn.execute('INSERT INTO payments_v3 SELECT * FROM payments')
    conn.execute('''CREATE TABLE payment_allocations_v3 (
      payment_id INTEGER NOT NULL REFERENCES payments_v3(id),
      installment_id INTEGER NOT NULL REFERENCES installments(id),
      principal_cents INTEGER NOT NULL CHECK(principal_cents>=0),
      interest_cents INTEGER NOT NULL CHECK(interest_cents>=0),PRIMARY KEY(payment_id,installment_id))''')
    conn.execute('INSERT INTO payment_allocations_v3 SELECT * FROM payment_allocations')
    conn.execute('DROP TABLE payment_allocations')
    conn.execute('DROP TABLE payments')
    conn.execute('ALTER TABLE payments_v3 RENAME TO payments')
    conn.execute('ALTER TABLE payment_allocations_v3 RENAME TO payment_allocations')
    conn.execute('CREATE INDEX idx_payments_application_date ON payments(application_id,paid_on,id)')
    conn.execute('CREATE INDEX idx_payment_allocations_installment ON payment_allocations(installment_id,payment_id)')


def _date(value,field='date',allow_future=False):
    try:
        parsed = date.fromisoformat(str(value))
    except (TypeError,ValueError) as exc:
        raise ValueError(f'{field} must use a valid YYYY-MM-DD date.') from exc
    if parsed.isoformat()!=str(value) or parsed.year<1900:
        raise ValueError(f'{field} must use YYYY-MM-DD and be in 1900 or later.')
    if not allow_future and parsed>date.today():
        raise ValueError(f'{field} cannot be in the future for an observed event.')
    return parsed


def _due_date(start,offset):
    """Anchor every due date to the original day (Jan31→Feb28→Mar31)."""
    total = start.year*12+start.month-1+offset
    year,month = divmod(total,12)
    month += 1
    return date(year,month,min(start.day,monthrange(year,month)[1]))


def _schedule(principal_cents,annual_rate,months,start):
    principal = Decimal(principal_cents)/100
    rate = Decimal(str(annual_rate))/12
    emi = principal/months if rate==0 else principal*rate/(1-(1+rate)**(-months))
    regular = emi.quantize(CENT,rounding=ROUND_HALF_UP)
    balance = principal
    rows = []
    for number in range(1,months+1):
        interest = (balance*rate).quantize(CENT,rounding=ROUND_HALF_UP)
        paid_principal = balance if number==months else min(balance,max(regular-interest,Decimal('0')))
        balance -= paid_principal
        rows.append((number,_due_date(start,number).isoformat(),int(paid_principal*100),int(interest*100)))
    return rows


class ApplicationStore:
    def __init__(self,path=None,pool_size=4):
        self.path = Path(path or os.environ.get('PP1_DATABASE',BASE_DIR/'data'/'pp1.sqlite3')).resolve()
        if not self.path.is_file():
            raise FileNotFoundError('Prepare the research database before saving local applications.')
        self.pool = SQLitePool(self.path,size=pool_size,timeout=10,read_only=False)
        self.migrate()

    def migrate(self):
        """Add application tables; existing source tables/records are untouched."""
        with self.pool.connection() as conn:
            conn.execute('PRAGMA journal_mode=WAL')
            conn.executescript(SCHEMA)
            expected = {'id','username','password_hash','created_at'}
            actual = {row[1] for row in conn.execute('PRAGMA table_info(users)')}
            if not expected.issubset(actual):
                raise RuntimeError('Existing users table has an incompatible schema; no data was replaced.')
            conn.execute('BEGIN IMMEDIATE')
            columns = {row[1] for row in conn.execute('PRAGMA table_info(applications)')}
            additions = {'confirmed_principal_cents':'INTEGER','confirmed_annual_rate':'REAL',
                         'confirmed_term_months':'INTEGER','agreement_terms_source':'TEXT'}
            for name,kind in additions.items():
                if name not in columns:
                    conn.execute(f'ALTER TABLE applications ADD COLUMN {name} {kind}')
            _migrate_payment_minimum(conn)
            for row in conn.execute('SELECT id,borrower_json,result_json,canonical_json FROM applications').fetchall():
                canonical = json.loads(row['canonical_json'])
                if canonical.get('category') not in PURPOSE_LABELS or 'category_label' not in canonical:
                    canonical.update(_category(json.loads(row['borrower_json']),json.loads(row['result_json'])))
                    conn.execute('UPDATE applications SET canonical_json=? WHERE id=?',(_json(canonical),row['id']))
            conn.execute("CREATE INDEX IF NOT EXISTS idx_applications_owner_category ON applications(owner_id,json_extract(canonical_json,'$.category'),created_at)")
            conn.execute('INSERT OR IGNORE INTO application_schema VALUES (?,?)',(3,_now()))
            conn.commit()

    @contextmanager
    def transaction(self):
        with self.pool.connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            try:
                yield conn
                conn.commit()
            except BaseException:
                conn.rollback()
                raise

    @contextmanager
    def read_snapshot(self):
        """Use one WAL snapshot for schedule, allocations and payment totals."""
        with self.pool.connection() as conn:
            conn.execute('BEGIN')
            try:
                yield conn
            finally:
                conn.rollback()

    @staticmethod
    def _owned(conn,owner_id,application_id):
        row = conn.execute('SELECT * FROM applications WHERE id=? AND owner_id=?',
                           (str(application_id),int(owner_id))).fetchone()
        if row is None:
            raise LookupError('Application not found.')
        return row

    @staticmethod
    def _audit(conn,owner_id,application_id,action,detail):
        conn.execute('INSERT INTO application_audit(application_id,owner_id,action,recorded_at,detail_json) VALUES (?,?,?,?,?)',
                     (application_id,owner_id,action,_now(),_json(detail)))

    def create_user(self,username,password):
        username = str(username or '').strip().casefold()
        if not re.fullmatch(r'[a-z0-9_.@+\-]{3,100}',username):
            raise ValueError('Username must have 3–100 letters, numbers or . _ @ + - characters.')
        if not isinstance(password,str) or not 10<=len(password)<=200:
            raise ValueError('Use a password with 10–200 characters.')
        password_hash = generate_password_hash(password)
        now = _now()
        try:
            with self.transaction() as conn:
                cursor = conn.execute('INSERT INTO users(username,password_hash,created_at) VALUES (?,?,?)',
                                      (username,password_hash,now))
                user_id = cursor.lastrowid
                self._audit(conn,user_id,None,'account_created',{})
        except sqlite3.IntegrityError as exc:
            raise ValueError('That username is already registered.') from exc
        return {'id':user_id,'username':username,'created_at':now}

    def authenticate_user(self,username,password):
        if not isinstance(password,str) or len(password)>200:
            return None
        with self.pool.connection() as conn:
            row = conn.execute('SELECT * FROM users WHERE username=?',
                               (str(username or '').strip().casefold(),)).fetchone()
        if row is None or not check_password_hash(row['password_hash'],password):
            return None
        return {'id':row['id'],'username':row['username'],'created_at':row['created_at']}

    def get_user(self,owner_id):
        with self.pool.connection() as conn:
            row = conn.execute('SELECT id,username,created_at FROM users WHERE id=?',(int(owner_id),)).fetchone()
        return dict(row) if row else None

    def save_application(self,owner_id,borrower_data,result):
        if not isinstance(borrower_data,dict) or not isinstance(result,dict):
            raise ValueError('Supply borrower and assessment JSON objects.')
        result = enrich_assessment(result,borrower_data)
        applicant = result.get('applicant_copy',{})
        entities = result.get('entities',{})
        terms = result.get('loan_terms',{})
        principal_value = terms.get('principal',applicant.get('Requested Loan',entities.get('loan_amount')))
        principal = _money(principal_value) if principal_value is not None else None
        annual_rate = terms.get('annual_rate',result.get('bank_copy',{}).get('Annual Interest Rate'))
        if annual_rate is None:
            try:
                annual_rate = float(str(applicant.get('Annual Interest Rate','')).rstrip('%'))/100
            except (TypeError,ValueError) as exc:
                raise ValueError('A finite annual interest rate is required to save an application.') from exc
        try:
            annual_rate = float(annual_rate)
            months_raw = terms.get('term_months',result.get('repayment_months',12))
            months = int(months_raw)
            if not math.isfinite(annual_rate) or not 0<=annual_rate<=1 or isinstance(months_raw,bool) or months!=float(months_raw) or not 1<=months<=600:
                raise ValueError
        except (TypeError,ValueError,OverflowError) as exc:
            raise ValueError('Use annual_rate as a fraction from 0 to 1 and a whole term of 1–600 months.') from exc
        application_id,now = str(uuid.uuid4()),_now()
        canonical = {'borrower_id':application_id,'application_id':application_id,
          **_category(borrower_data,result),'state':borrower_data.get('state') or entities.get('state'),
          'location':entities.get('location'),'loan_amount':principal/100 if principal is not None else None,'term_months':months,
          'interest_rate':round(annual_rate*100,6),'repayment_status':'Not tracked',
          'sentiment':result.get('sentiment',{}).get('label','unavailable'),
          'cluster_id':None,'cluster_label':'Not assigned','issue_date':None,
          'currency':'INR','source_type':'local_application','tracking_status':'not_started',
          'created_at':now,'applicant_name':str(borrower_data.get('name','')),
          'assessment_decision':applicant.get('Decision','Assessment saved'),
          'income_change_pct':None}
        borrower_json,result_json,canonical_json = _json(borrower_data),_json(result),_json(canonical)
        with self.transaction() as conn:
            if not conn.execute('SELECT id FROM users WHERE id=?',(int(owner_id),)).fetchone():
                raise LookupError('Account not found.')
            conn.execute('''INSERT INTO applications(id,owner_id,borrower_json,result_json,canonical_json,
                principal_cents,annual_rate,term_months,created_at) VALUES (?,?,?,?,?,?,?,?,?)''',
                (application_id,int(owner_id),borrower_json,result_json,canonical_json,principal,annual_rate,months,now))
            self._audit(conn,int(owner_id),application_id,'application_saved',{'source_type':'local_application'})
        return application_id

    def start_tracking(self,owner_id,application_id,start_date,principal=None,annual_rate=None,months=None):
        start = _date(start_date,'Disbursement date')
        with self.transaction() as conn:
            application = self._owned(conn,owner_id,application_id)
            prior_principal = application['confirmed_principal_cents'] if application['tracking_start_date'] and application['confirmed_principal_cents'] is not None else application['principal_cents']
            principal_cents = _money(principal) if principal is not None else prior_principal
            if principal_cents is None:
                raise ValueError('This application has no confirmed loan amount. Enter the actual agreed principal before tracking disbursement.')
            try:
                prior_rate = application['confirmed_annual_rate'] if application['tracking_start_date'] and application['confirmed_annual_rate'] is not None else application['annual_rate']
                prior_months = application['confirmed_term_months'] if application['tracking_start_date'] and application['confirmed_term_months'] is not None else application['term_months']
                confirmed_rate = prior_rate if annual_rate is None else float(annual_rate)
                term_value = prior_months if months is None else months
                confirmed_months = int(term_value)
                if isinstance(annual_rate,bool) or not math.isfinite(confirmed_rate) or not 0<=confirmed_rate<=1 or isinstance(term_value,bool) or confirmed_months!=float(term_value) or not 1<=confirmed_months<=600:
                    raise ValueError
            except (ValueError,TypeError,OverflowError) as exc:
                raise ValueError('Confirm annual_rate as a fraction from 0 to 1 and a whole agreement term of 1–600 months.') from exc
            if application['tracking_start_date']:
                if application['tracking_start_date']!=start.isoformat():
                    raise ValueError('Tracking has already started. Its disbursement date cannot be silently changed.')
                existing_principal = application['confirmed_principal_cents'] if application['confirmed_principal_cents'] is not None else application['principal_cents']
                existing_rate = application['confirmed_annual_rate'] if application['confirmed_annual_rate'] is not None else application['annual_rate']
                existing_months = application['confirmed_term_months'] if application['confirmed_term_months'] is not None else application['term_months']
                if ((principal is not None and principal_cents!=existing_principal) or
                    (annual_rate is not None and confirmed_rate!=existing_rate) or
                    (months is not None and confirmed_months!=existing_months)):
                    raise ValueError('Tracking has already started. Confirmed agreement terms cannot be changed after the schedule is recorded.')
                return self._ledger(conn,application)
            source = 'user_entered_agreement' if any(value is not None for value in (principal,annual_rate,months)) else 'application_estimate_recorded_by_user'
            schedule = _schedule(principal_cents,confirmed_rate,confirmed_months,start)
            conn.executemany('INSERT INTO installments(application_id,installment_number,due_date,principal_cents,interest_cents) VALUES (?,?,?,?,?)',
                             [(application_id,*row) for row in schedule])
            conn.execute('''UPDATE applications SET tracking_start_date=?,tracking_recorded_at=?,
                         confirmed_principal_cents=?,confirmed_annual_rate=?,confirmed_term_months=?,agreement_terms_source=? WHERE id=?''',
                         (start.isoformat(),_now(),principal_cents,confirmed_rate,confirmed_months,source,application_id))
            self._audit(conn,int(owner_id),application_id,'manual_disbursement_recorded',
                        {'start_date':start.isoformat(),'money_moved':False,'bank_connection':False,
                         'principal':principal_cents/100,'annual_rate':confirmed_rate,'term_months':confirmed_months,
                         'terms_source':source,'bank_verified':False})
            application = self._owned(conn,owner_id,application_id)
            return self._ledger(conn,application)

    @staticmethod
    def _payment_values(amount,paid_on,reference):
        cents = _money(amount,minimum=Decimal('0.01'))
        paid = _date(paid_on,'Payment date').isoformat()
        if not isinstance(reference,str) or not reference.strip() or len(reference.strip())>120:
            raise ValueError('Use a unique payment reference with 1–120 characters.')
        return cents,paid,reference.strip()

    def _insert_payment(self,conn,application,owner_id,cents,paid,reference):
        application_id = application['id']
        if not application['tracking_start_date']:
            raise ValueError('Record actual disbursement before entering payments.')
        if paid<application['tracking_start_date']:
            raise ValueError('Payment date cannot be before the recorded disbursement date.')
        existing = conn.execute('SELECT * FROM payments WHERE application_id=? AND reference=?',
                                (application_id,reference)).fetchone()
        if existing:
            if existing['amount_cents']!=cents or existing['paid_on']!=paid:
                raise ValueError('This reference already identifies a different payment. Use its original amount and date, or a new reference.')
            return dict(existing),True
        scheduled = conn.execute('SELECT COALESCE(SUM(principal_cents+interest_cents),0) FROM installments WHERE application_id=?',(application_id,)).fetchone()[0]
        recorded = conn.execute('SELECT COALESCE(SUM(amount_cents),0) FROM payments WHERE application_id=?',(application_id,)).fetchone()[0]
        if cents<100 and cents!=scheduled-recorded:
            raise ValueError('Payment amount must be at least INR 1, except an exact final remaining balance of at least INR 0.01.')
        if cents>scheduled-recorded:
            raise ValueError(f'Payment exceeds the remaining scheduled balance of INR {(scheduled-recorded)/100:,.2f}. No automatic prepayment rebate is assumed.')
        now = _now()
        cursor = conn.execute('INSERT INTO payments(application_id,amount_cents,paid_on,reference,recorded_at,recorded_by) VALUES (?,?,?,?,?,?)',
                              (application_id,cents,paid,reference,now,int(owner_id)))
        self._audit(conn,int(owner_id),application_id,'payment_recorded',{'payment_id':cursor.lastrowid,'amount':cents/100,'paid_on':paid,'reference':reference})
        return {'id':cursor.lastrowid,'application_id':application_id,'amount_cents':cents,'paid_on':paid,
                'reference':reference,'recorded_at':now,'recorded_by':int(owner_id)},False

    @staticmethod
    def _allocate(conn,application_id):
        """Reallocate deterministically by payment date after backdated entries."""
        installments = [dict(row) for row in conn.execute('SELECT * FROM installments WHERE application_id=? ORDER BY installment_number',(application_id,))]
        payments = conn.execute('SELECT id,amount_cents FROM payments WHERE application_id=? ORDER BY paid_on,id',(application_id,)).fetchall()
        conn.execute('DELETE FROM payment_allocations WHERE installment_id IN (SELECT id FROM installments WHERE application_id=?)',(application_id,))
        index = 0
        for payment in payments:
            remaining = payment['amount_cents']
            while remaining and index<len(installments):
                installment = installments[index]
                interest = min(remaining,installment['interest_cents'])
                installment['interest_cents'] -= interest
                remaining -= interest
                principal = min(remaining,installment['principal_cents'])
                installment['principal_cents'] -= principal
                remaining -= principal
                if interest or principal:
                    conn.execute('INSERT INTO payment_allocations VALUES (?,?,?,?)',
                                 (payment['id'],installment['id'],principal,interest))
                if installment['principal_cents']+installment['interest_cents']==0:
                    index += 1
            if remaining:
                raise RuntimeError('Recorded payments exceed the schedule; transaction rolled back.')

    def record_payment(self,owner_id,application_id,amount,paid_on,reference):
        cents,paid,ref = self._payment_values(amount,paid_on,reference)
        with self.transaction() as conn:
            application = self._owned(conn,owner_id,application_id)
            payment,duplicate = self._insert_payment(conn,application,owner_id,cents,paid,ref)
            if not duplicate:
                self._allocate(conn,application_id)
            return {'payment':self._public_payment(payment),'ledger':self._ledger(conn,application),'idempotent':duplicate}

    def import_payments_csv(self,owner_id,application_id,csv_text):
        if isinstance(csv_text,bytes):
            try:
                csv_text = csv_text.decode('utf-8-sig')
            except UnicodeDecodeError as exc:
                raise ValueError('Payment CSV must use UTF-8 encoding.') from exc
        if not isinstance(csv_text,str) or len(csv_text.encode('utf-8'))>MAX_CSV_BYTES:
            raise ValueError('Payment CSV must be text of at most 1 MiB.')
        reader = csv.DictReader(io.StringIO(csv_text.lstrip('\ufeff'),newline=''))
        expected = ['amount','paid_on','reference']
        if reader.fieldnames is None or set(reader.fieldnames)!=set(expected) or len(reader.fieldnames)!=3:
            raise ValueError('CSV headers must be amount,paid_on,reference.')
        records = []
        try:
            for row in reader:
                if len(records)>=MAX_CSV_ROWS:
                    raise ValueError(f'CSV allows at most {MAX_CSV_ROWS} payment rows.')
                if None in row or any(v is None for v in row.values()):
                    raise ValueError(f'CSV row {reader.line_num} has the wrong number of columns.')
                try:
                    records.append(self._payment_values(row['amount'],row['paid_on'],row['reference']))
                except ValueError as exc:
                    raise ValueError(f'CSV row {reader.line_num}: {exc}') from exc
        except csv.Error as exc:
            raise ValueError('Unable to parse the payment CSV.') from exc
        if not records:
            raise ValueError('CSV contains no payments.')
        with self.transaction() as conn:
            application = self._owned(conn,owner_id,application_id)
            inserted,duplicates = 0,0
            for values in records:
                _,duplicate = self._insert_payment(conn,application,owner_id,*values)
                duplicates += int(duplicate)
                inserted += int(not duplicate)
            if inserted:
                self._allocate(conn,application_id)
            self._audit(conn,int(owner_id),application_id,'payment_csv_imported',{'imported':inserted,'duplicates':duplicates})
            return {'imported':inserted,'duplicates':duplicates,'ledger':self._ledger(conn,application)}

    @staticmethod
    def _public_payment(row):
        return {'id':row['id'],'amount':row['amount_cents']/100,'paid_on':row['paid_on'],
                'reference':row['reference'],'recorded_at':row['recorded_at']}

    def _ledger(self,conn,application,as_of=None):
        asof = _date(as_of,'As-of date',allow_future=True) if as_of is not None else date.today()
        application_id = application['id']
        tracked = bool(application['tracking_start_date'])
        if tracked and asof.isoformat()<application['tracking_start_date']:
            raise ValueError('As-of date cannot be before the recorded disbursement date.')
        rows = conn.execute('''SELECT i.*,COALESCE(SUM(CASE WHEN p.paid_on<=? THEN a.principal_cents ELSE 0 END),0) AS principal_paid,
          COALESCE(SUM(CASE WHEN p.paid_on<=? THEN a.interest_cents ELSE 0 END),0) AS interest_paid
          FROM installments i LEFT JOIN payment_allocations a ON a.installment_id=i.id LEFT JOIN payments p ON p.id=a.payment_id
          WHERE i.application_id=? GROUP BY i.id ORDER BY i.installment_number''',
          (asof.isoformat(),asof.isoformat(),application_id)).fetchall()
        payments = [self._public_payment(row) for row in conn.execute('SELECT * FROM payments WHERE application_id=? AND paid_on<=? ORDER BY paid_on,id',(application_id,asof.isoformat()))]
        schedule,scheduled,total_paid,remaining,overdue,due,principal_left,interest_left = [],0,0,0,0,0,0,0
        for row in rows:
            amount = row['principal_cents']+row['interest_cents']
            paid = row['principal_paid']+row['interest_paid']
            balance = amount-paid
            is_late = row['due_date']<asof.isoformat() and balance>0
            is_due = row['due_date']<=asof.isoformat() and balance>0
            status = 'Paid' if not balance else 'Partially paid' if paid else 'Late' if is_late else 'Due' if is_due else 'Scheduled'
            schedule.append({'number':row['installment_number'],'due_date':row['due_date'],
                'principal':row['principal_cents']/100,'interest':row['interest_cents']/100,
                'amount':amount/100,'paid':paid/100,'remaining':balance/100,'status':status,'is_late':is_late,
                'principal_paid':row['principal_paid']/100,'interest_paid':row['interest_paid']/100})
            scheduled += amount
            total_paid += paid
            remaining += balance
            overdue += balance if is_late else 0
            due += balance if is_due else 0
            principal_left += row['principal_cents']-row['principal_paid']
            interest_left += row['interest_cents']-row['interest_paid']
        status = 'Not tracked' if not tracked else 'Paid' if remaining==0 else 'Late' if overdue else 'Due' if due else 'Partially paid' if total_paid else 'Current'
        next_due = next((item for item in schedule if item['remaining']>0),None)
        principal = application['confirmed_principal_cents'] if tracked and application['confirmed_principal_cents'] is not None else application['principal_cents']
        annual_rate = application['confirmed_annual_rate'] if tracked and application['confirmed_annual_rate'] is not None else application['annual_rate']
        months = application['confirmed_term_months'] if tracked and application['confirmed_term_months'] is not None else application['term_months']
        agreement_terms = {'principal':principal/100,'annual_rate':annual_rate,'interest_rate':round(annual_rate*100,6),
            'term_months':months,'currency':'INR','source':application['agreement_terms_source'] or 'application_estimate_recorded_by_user',
            'bank_verified':False,'verification':'Recorded by the user; not verified against a bank or lender.'} if tracked else None
        return {'application_id':application_id,'currency':'INR','as_of':asof.isoformat(),
            'tracking_started':tracked,'start_date':application['tracking_start_date'],
            'tracking_recorded_at':application['tracking_recorded_at'],'status':status,
            'principal':principal/100 if principal is not None else None,'annual_rate':annual_rate,
            'interest_rate':round(annual_rate*100,6),'term_months':months,
            'agreement_terms':agreement_terms,
            'estimated_principal':application['principal_cents']/100 if application['principal_cents'] is not None else None,
            'scheduled_total':scheduled/100 if tracked else None,'total_paid':total_paid/100,
            'outstanding':remaining/100 if tracked else None,'outstanding_principal':principal_left/100 if tracked else None,
            'outstanding_interest':interest_left/100 if tracked else None,'amount_due':due/100,
            'overdue_amount':overdue/100,'next_due_date':next_due['due_date'] if next_due else None,
            'next_due_amount':next_due['remaining'] if next_due else None,'schedule':schedule,'payments':payments,
            'tracking_status':'not_started' if not tracked else 'settled' if remaining==0 else 'tracking',
            'minimum_payment':0.01 if 0<remaining<100 else 1.0,
            'method':'User-recorded disbursement and payments; fixed schedule, allocated oldest installment first, interest before principal. No bank connection, money movement or automatic interest rebate. Payments must be at least INR 1, except an exact final residual of at least INR 0.01.'}

    def get_ledger(self,owner_id,application_id,as_of=None):
        with self.read_snapshot() as conn:
            return self._ledger(conn,self._owned(conn,owner_id,application_id),as_of)

    def get_application(self,owner_id,application_id):
        with self.read_snapshot() as conn:
            application = self._owned(conn,owner_id,application_id)
            ledger = self._ledger(conn,application)
            canonical = json.loads(application['canonical_json'])
            borrower = json.loads(application['borrower_json'])
            result = enrich_assessment(json.loads(application['result_json']),borrower)
            canonical['sentiment'] = result['sentiment']['label']
            canonical.update(repayment_status=ledger['status'],tracking_status=ledger['tracking_status'],issue_date=ledger['start_date'],agreement_terms=ledger['agreement_terms'])
            return {'id':application['id'],'owner_id':application['owner_id'],'created_at':application['created_at'],
                    'canonical':canonical,'borrower_data':borrower,
                    'result':result,'tracking':ledger,'ledger':ledger,'agreement_terms':ledger['agreement_terms']}

    def list_applications(self,owner_id,page=1,page_size=20,per_page=None,purpose=None,category=None):
        page = max(1,int(page))
        page_size = max(1,min(100,int(per_page or page_size)))
        category_value = purpose or category
        clause = 'owner_id=?'
        params = [int(owner_id)]
        if category_value:
            clause += " AND json_extract(canonical_json,'$.category')=?"
            params.append(str(category_value))
        with self.read_snapshot() as conn:
            total = conn.execute('SELECT COUNT(*) FROM applications WHERE '+clause,params).fetchone()[0]
            rows = conn.execute('SELECT * FROM applications WHERE '+clause+' ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?',
                                params+[page_size,(page-1)*page_size]).fetchall()
            items = []
            for row in rows:
                canonical = json.loads(row['canonical_json'])
                result = enrich_assessment(json.loads(row['result_json']),json.loads(row['borrower_json']))
                canonical['sentiment'] = result['sentiment']['label']
                ledger = self._ledger(conn,row)
                canonical.update(repayment_status=ledger['status'],tracking_status=ledger['tracking_status'],issue_date=ledger['start_date'],
                                 outstanding=ledger['outstanding'],amount_due=ledger['amount_due'],agreement_terms=ledger['agreement_terms'])
                items.append(canonical)
        return {'items':items,'page':page,'page_size':page_size,'total':total,'pages':math.ceil(total/page_size)}


@lru_cache(maxsize=4)
def _store(path):
    return ApplicationStore(path)


def get_application_store():
    return _store(str(Path(os.environ.get('PP1_DATABASE',BASE_DIR/'data'/'pp1.sqlite3')).resolve()))


def create_user(username,password):
    return get_application_store().create_user(username,password)


def authenticate_user(username,password):
    return get_application_store().authenticate_user(username,password)


def get_user(owner_id):
    return get_application_store().get_user(owner_id)


def save_application(owner_id,borrower_data,result):
    return get_application_store().save_application(owner_id,borrower_data,result)


def get_application(owner_id,application_id):
    return get_application_store().get_application(owner_id,application_id)


def list_applications(owner_id,page=1,page_size=20,per_page=None,purpose=None,category=None):
    return get_application_store().list_applications(owner_id,page,page_size,per_page,purpose,category)


def start_tracking(owner_id,application_id,start_date,principal=None,annual_rate=None,months=None):
    return get_application_store().start_tracking(owner_id,application_id,start_date,principal,annual_rate,months)


def record_payment(owner_id,application_id,amount,paid_on,reference):
    return get_application_store().record_payment(owner_id,application_id,amount,paid_on,reference)


def import_payments_csv(owner_id,application_id,csv_text):
    return get_application_store().import_payments_csv(owner_id,application_id,csv_text)


def get_ledger(owner_id,application_id,as_of=None):
    return get_application_store().get_ledger(owner_id,application_id,as_of)
