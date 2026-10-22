"""All accounts and payments below are synthetic isolated test fixtures."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date,timedelta
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from application_store import ApplicationStore,_due_date,SCHEMA


@pytest.fixture
def store(tmp_path):
    path = tmp_path/'pp1.sqlite3'
    with sqlite3.connect(path) as conn:
        conn.execute('CREATE TABLE historical_sentinel(value TEXT)')
        conn.execute("INSERT INTO historical_sentinel VALUES ('preserved')")
    return ApplicationStore(path)


@pytest.fixture
def owner(store):
    return store.create_user('Demo.Owner','correct-pass-123')['id']


def save(store,owner,principal=1200,rate=0,months=3):
    borrower = {'name':'Synthetic Demo','description':'A test business','mobile':'9000000000','id_number':'TEST0001','state':'MH'}
    result = {'loan_terms':{'principal':principal,'annual_rate':rate,'term_months':months},
              'applicant_copy':{'Decision':'Manual review required'},'entities':{'category':'Dairy','location':'Pune'},
              'sentiment':{'label':'Neutral'},'policy_snapshot':{'demo':True}}
    return store.save_application(owner,borrower,result)


def tracked(store,owner,**kwargs):
    app_id = save(store,owner,**kwargs)
    store.start_tracking(owner,app_id,'2026-01-31')
    return app_id


def test_additive_migration_auth_and_full_json(store,owner):
    store.migrate()
    assert store.authenticate_user('DEMO.OWNER','correct-pass-123')['id']==owner
    assert store.authenticate_user('demo.owner','bad') is None
    assert store.authenticate_user('missing','bad') is None
    with pytest.raises(ValueError,match='already registered'):
        store.create_user('demo.owner','another-pass-123')
    with pytest.raises(ValueError,match='10–200'):
        store.create_user('new.name','short')
    app_id = save(store,owner)
    app = store.get_application(owner,app_id)
    assert app['borrower_data']['id_number']=='TEST0001'
    assert app['result']['policy_snapshot']=={'demo':True}
    assert app['canonical']['currency']=='INR'
    assert app['canonical']['source_type']=='local_application'
    assert app['canonical']['repayment_status']=='Not tracked'
    assert app['canonical']['cluster_id'] is None
    with store.pool.connection() as conn:
        assert conn.execute('SELECT value FROM historical_sentinel').fetchone()[0]=='preserved'
        assert conn.execute('SELECT password_hash FROM users').fetchone()[0]!='correct-pass-123'
        assert conn.execute('PRAGMA journal_mode').fetchone()[0]=='wal'


def test_new_application_persists_sentiment_in_result_and_canonical_record(store,owner):
    app_id=save(store,owner)
    app=store.get_application(owner,app_id)
    with store.pool.connection() as conn:
        row=conn.execute('SELECT result_json,canonical_json FROM applications WHERE id=?',(app_id,)).fetchone()
    assert json.loads(row['result_json'])['sentiment']==app['result']['sentiment']
    assert json.loads(row['canonical_json'])['sentiment']=='neutral'
    assert store.list_applications(owner)['items'][0]['sentiment']=='neutral'


def test_old_application_sentiment_is_enriched_without_rewriting_saved_evidence(store,owner):
    app_id=save(store,owner)
    with store.transaction() as conn:
        row=conn.execute('SELECT result_json,borrower_json,canonical_json FROM applications WHERE id=?',(app_id,)).fetchone()
        old_result=json.loads(row['result_json'])
        old_result.pop('sentiment',None)
        borrower=json.loads(row['borrower_json'])
        borrower['description']='I need to borrow 10,000 rupees for my dairy business'
        canonical=json.loads(row['canonical_json'])
        canonical['sentiment']='unavailable'
        conn.execute('UPDATE applications SET result_json=?,borrower_json=?,canonical_json=? WHERE id=?',
                     (json.dumps(old_result),json.dumps(borrower),json.dumps(canonical),app_id))
    with store.pool.connection() as conn:
        before=tuple(conn.execute('SELECT result_json,canonical_json FROM applications WHERE id=?',(app_id,)).fetchone())
    app=store.get_application(owner,app_id)
    assert app['result']['sentiment']['label']=='neutral'
    assert app['canonical']['sentiment']=='neutral'
    assert store.list_applications(owner)['items'][0]['sentiment']=='neutral'
    assert {key:value for key,value in app['result'].items() if key!='sentiment'}==old_result
    with store.pool.connection() as conn:
        after=tuple(conn.execute('SELECT result_json,canonical_json FROM applications WHERE id=?',(app_id,)).fetchone())
    assert after==before


def test_owner_isolation_every_operation(store,owner):
    stranger = store.create_user('Other.User','other-pass-123')['id']
    app_id = tracked(store,owner)
    operations = [lambda:store.get_application(stranger,app_id),lambda:store.get_ledger(stranger,app_id),
        lambda:store.start_tracking(stranger,app_id,'2026-01-31'),
        lambda:store.record_payment(stranger,app_id,10,'2026-02-01','p1'),
        lambda:store.import_payments_csv(stranger,app_id,'amount,paid_on,reference\n10,2026-02-01,p1\n')]
    for operation in operations:
        with pytest.raises(LookupError,match='not found'):
            operation()
    assert store.list_applications(stranger)['total']==0
    assert store.list_applications(owner)['items'][0]['application_id']==app_id


def test_missing_principal_saved_as_draft_not_disbursed(store,owner):
    app_id = save(store,owner,principal=None)
    assert store.get_application(owner,app_id)['canonical']['loan_amount'] is None
    with pytest.raises(ValueError,match='no confirmed loan amount'):
        store.start_tracking(owner,app_id,'2026-01-31')


def test_confirmed_agreement_overrides_preserve_estimate_snapshot(store,owner):
    app_id = save(store,owner,principal=1200,rate=.12,months=3)
    before = store.get_application(owner,app_id)['result']
    ledger = store.start_tracking(owner,app_id,'2026-01-31',principal=2000,annual_rate=0,months=4)
    assert ledger['principal']==2000 and ledger['estimated_principal']==1200
    assert ledger['annual_rate']==0 and ledger['term_months']==4
    assert ledger['scheduled_total']==2000 and len(ledger['schedule'])==4
    assert ledger['agreement_terms']['source']=='user_entered_agreement'
    assert ledger['agreement_terms']['bank_verified'] is False
    after = store.get_application(owner,app_id)
    assert after['result']==before
    assert after['canonical']['loan_amount']==1200
    assert after['canonical']['agreement_terms']['principal']==2000
    assert store.start_tracking(owner,app_id,'2026-01-31')['principal']==2000
    with pytest.raises(ValueError,match='terms cannot be changed'):
        store.start_tracking(owner,app_id,'2026-01-31',principal=2500)
    assert store.list_applications(owner,purpose='small_business')['total']==1
    assert store.list_applications(owner,purpose="small_business' OR 1=1 --")['total']==0
    assert after['canonical']['category']=='small_business'
    assert after['canonical']['category_label']=='Dairy'


def test_agreement_overrides_validate_and_can_complete_missing_principal(store,owner):
    app_id = save(store,owner,principal=None)
    for kwargs in ({'principal':'nan'},{'principal':100,'annual_rate':2},{'principal':100,'months':0},{'principal':100,'months':True}):
        with pytest.raises(ValueError):
            store.start_tracking(owner,app_id,'2026-01-31',**kwargs)
    assert store.get_ledger(owner,app_id)['tracking_started'] is False
    assert store.start_tracking(owner,app_id,'2026-01-31',principal=1000)['principal']==1000
    assert store.start_tracking(owner,app_id,'2026-01-31')['principal']==1000


def test_month_end_dates_and_schedule_reconciliation(store,owner):
    assert _due_date(date(2024,1,31),1)==date(2024,2,29)
    assert _due_date(date(2024,1,31),2)==date(2024,3,31)
    assert _due_date(date(2026,1,30),2)==date(2026,3,30)
    app_id = tracked(store,owner,principal=50000,rate=.12,months=12)
    ledger = store.get_ledger(owner,app_id)
    assert ledger['schedule'][0]['due_date']=='2026-02-28'
    assert ledger['schedule'][1]['due_date']=='2026-03-31'
    assert sum(row['principal'] for row in ledger['schedule'])==pytest.approx(50000)
    assert sum(row['amount'] for row in ledger['schedule'])==pytest.approx(ledger['scheduled_total'])
    assert ledger['outstanding_principal']==50000
    assert ledger['outstanding']==pytest.approx(ledger['outstanding_principal']+ledger['outstanding_interest'])
    assert store.start_tracking(owner,app_id,'2026-01-31')['schedule']==ledger['schedule']
    with pytest.raises(ValueError,match='already started'):
        store.start_tracking(owner,app_id,'2026-02-01')


def test_due_late_partial_paid_and_asof_dates(store,owner):
    app_id = tracked(store,owner)
    assert store.get_ledger(owner,app_id,'2026-02-27')['status']=='Current'
    assert store.get_ledger(owner,app_id,'2026-02-28')['status']=='Due'
    assert store.get_ledger(owner,app_id,'2026-03-01')['status']=='Late'
    store.record_payment(owner,app_id,100,'2026-02-20','first')
    ledger = store.get_ledger(owner,app_id,'2026-03-01')
    assert ledger['schedule'][0]['status']=='Partially paid'
    assert ledger['schedule'][0]['is_late'] is True
    assert ledger['overdue_amount']==300
    assert ledger['outstanding']==1100
    assert store.get_ledger(owner,app_id,'2026-02-19')['total_paid']==0
    store.record_payment(owner,app_id,1100,'2026-04-30','settled')
    ledger = store.get_ledger(owner,app_id)
    assert ledger['status']=='Paid' and ledger['outstanding']==0
    assert all(row['status']=='Paid' for row in ledger['schedule'])
    assert store.get_application(owner,app_id)['canonical']['tracking_status']=='settled'
    with pytest.raises(ValueError,match='before.*disbursement'):
        store.get_ledger(owner,app_id,'2026-01-30')


def test_backdated_payments_reallocate_by_actual_date(store,owner):
    app_id = tracked(store,owner)
    store.record_payment(owner,app_id,400,'2026-05-01','later')
    store.record_payment(owner,app_id,400,'2026-02-20','earlier')
    ledger = store.get_ledger(owner,app_id,'2026-03-01')
    assert ledger['total_paid']==400
    assert ledger['schedule'][0]['status']=='Paid'
    assert ledger['schedule'][1]['paid']==0
    assert ledger['payments'][0]['reference']=='earlier'


def test_idempotence_conflict_overpayment_and_audit(store,owner):
    app_id = tracked(store,owner)
    first = store.record_payment(owner,app_id,'100.00','2026-02-20','ref-1')
    second = store.record_payment(owner,app_id,100,'2026-02-20','ref-1')
    assert not first['idempotent'] and second['idempotent']
    assert first['payment']['id']==second['payment']['id']
    with pytest.raises(ValueError,match='different payment'):
        store.record_payment(owner,app_id,200,'2026-02-20','ref-1')
    with pytest.raises(ValueError,match='exceeds'):
        store.record_payment(owner,app_id,1100.01,'2026-02-20','overpay')
    assert store.get_ledger(owner,app_id)['total_paid']==100
    with store.pool.connection() as conn:
        actions = [r[0] for r in conn.execute('SELECT action FROM application_audit WHERE application_id=?',(app_id,))]
        assert actions==['application_saved','manual_disbursement_recorded','payment_recorded']


def test_exact_small_final_residual_can_be_settled_and_retried(store,owner):
    app_id = tracked(store,owner,principal=1200.50)
    store.record_payment(owner,app_id,1200,'2026-02-20','main')
    assert store.get_ledger(owner,app_id)['outstanding']==.50
    assert store.get_ledger(owner,app_id)['minimum_payment']==.01
    with pytest.raises(ValueError,match='exact final'):
        store.record_payment(owner,app_id,.25,'2026-02-20','fraction')
    result = store.record_payment(owner,app_id,.50,'2026-02-20','final')
    assert result['ledger']['status']=='Paid'
    assert store.record_payment(owner,app_id,.50,'2026-02-20','final')['idempotent']


def test_v2_migration_preserves_existing_payment_ids_and_allocations(tmp_path):
    path = tmp_path/'legacy.sqlite3'
    with sqlite3.connect(path) as conn:
        conn.executescript(SCHEMA.replace('CHECK(amount_cents>0)','CHECK(amount_cents>=100)'))
        conn.execute("INSERT INTO users VALUES (1,'legacy','test-hash','2026-01-01')")
        conn.execute('''INSERT INTO applications(id,owner_id,borrower_json,result_json,canonical_json,
          principal_cents,annual_rate,term_months,created_at,tracking_start_date,tracking_recorded_at)
          VALUES (?,?,?,?,?,?,?,?,?,?,?)''',('legacy-app',1,'{}','{"entities":{"category":"Dairy"}}',
          '{"category":"Dairy"}',120000,0,3,'2026-01-01','2026-01-31','2026-01-31'))
        for i,day in enumerate(['2026-02-28','2026-03-31','2026-04-30'],1):
            conn.execute('INSERT INTO installments VALUES (?,?,?,?,?,?)',(i,'legacy-app',i,day,40000,0))
        conn.execute("INSERT INTO payments VALUES (5,'legacy-app',100,'2026-02-01','existing','2026-02-01',1)")
        conn.execute('INSERT INTO payment_allocations VALUES (5,1,100,0)')
        conn.commit()
    store = ApplicationStore(path)
    ledger = store.get_ledger(1,'legacy-app')
    assert ledger['total_paid']==1 and ledger['payments'][0]['id']==5
    assert store.get_application(1,'legacy-app')['canonical']['category']=='small_business'
    store.record_payment(1,'legacy-app',1198.50,'2026-02-20','remaining-main')
    assert store.record_payment(1,'legacy-app',.50,'2026-02-20','final')['ledger']['status']=='Paid'
    with store.pool.connection() as conn:
        assert conn.execute('PRAGMA foreign_key_check').fetchall()==[]
        assert conn.execute('SELECT MAX(version) FROM application_schema').fetchone()[0]==3


@pytest.mark.parametrize('amount',['nan','inf','-1','0','0.99','1.001',True,'1000000001'])
def test_invalid_money_rejected(store,owner,amount):
    app_id = tracked(store,owner)
    with pytest.raises(ValueError,match='amount'):
        store.record_payment(owner,app_id,amount,'2026-02-01','bad')
    assert store.get_ledger(owner,app_id)['payments']==[]


def test_dates_and_tracking_required(store,owner):
    app_id = save(store,owner)
    future = (date.today()+timedelta(days=1)).isoformat()
    with pytest.raises(ValueError,match='future'):
        store.start_tracking(owner,app_id,future)
    with pytest.raises(ValueError,match='before entering'):
        store.record_payment(owner,app_id,100,'2026-02-01','p1')
    store.start_tracking(owner,app_id,'2026-01-31')
    for paid,match in [('2026-01-01','before.*disbursement'),(future,'future'),('2026-02-30','valid')]:
        with pytest.raises(ValueError,match=match):
            store.record_payment(owner,app_id,100,paid,'bad')


def test_csv_atomic_validation_idempotence_and_overpayment(store,owner):
    app_id = tracked(store,owner)
    text = 'amount,paid_on,reference\n100,2026-02-20,p1\n200,2026-03-20,p2\n'
    result = store.import_payments_csv(owner,app_id,text)
    assert result['imported']==2 and result['ledger']['total_paid']==300
    assert store.import_payments_csv(owner,app_id,text)['duplicates']==2
    for invalid in ['amount,paid_on,reference\n100,2026-02-20,p3\nNaN,2026-03-20,p4',
                    'amount,paid_on,reference\n100,2026-02-20,p3\n1200,2026-03-20,p4',
                    'amount,paid_on,reference\n100,2026-02-20,p3\n500,2026-03-20,p2']:
        with pytest.raises(ValueError):
            store.import_payments_csv(owner,app_id,invalid)
        assert store.get_ledger(owner,app_id)['total_paid']==300
        assert len(store.get_ledger(owner,app_id)['payments'])==2


def test_concurrent_writers_idempotent_and_reader_snapshot(store,owner):
    app_id = tracked(store,owner,principal=12000)
    def record(i):
        return store.record_payment(owner,app_id,100,'2026-02-20',f'ref-{i%8}')
    with ThreadPoolExecutor(max_workers=8) as executor:
        records = list(executor.map(record,range(32)))
    assert sum(not row['idempotent'] for row in records)==8
    ledger = store.get_ledger(owner,app_id)
    assert ledger['total_paid']==800
    assert sum(p['amount'] for p in ledger['payments'])==ledger['total_paid']
    assert store.pool._created<=4
    with store.pool.connection() as conn:
        assert conn.execute('PRAGMA foreign_key_check').fetchall()==[]
        assert conn.execute('PRAGMA integrity_check').fetchone()[0]=='ok'


def test_research_rebuild_preserves_accounts_and_payments(store,owner,tmp_path):
    spec = importlib.util.spec_from_file_location('prepare_data_storage_test',ROOT/'scripts'/'prepare_data.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    app_id = tracked(store,owner)
    store.record_payment(owner,app_id,100,'2026-02-20','p1')
    with store.pool.connection() as conn:
        module.schema(conn)
        conn.execute("INSERT INTO locations VALUES ('Original location')")
        conn.commit()
    staged = tmp_path/'staged.sqlite3'
    with sqlite3.connect(staged) as conn:
        module.schema(conn)
        conn.execute("INSERT INTO locations VALUES ('New location')")
        conn.commit()
    backup = module.install_research_database(staged,store.path)
    assert Path(backup).is_file()
    assert store.authenticate_user('demo.owner','correct-pass-123')['id']==owner
    assert store.get_ledger(owner,app_id)['total_paid']==100
    with store.pool.connection() as conn:
        assert conn.execute('SELECT name FROM locations').fetchone()[0]=='New location'
    with sqlite3.connect(backup) as conn:
        assert conn.execute('SELECT name FROM locations').fetchone()[0]=='Original location'
        assert conn.execute('SELECT COUNT(*) FROM payments').fetchone()[0]==1
