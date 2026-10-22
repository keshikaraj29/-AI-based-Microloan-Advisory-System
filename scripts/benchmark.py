"""Reproducible in-process timings; includes full Flask request dispatch.

This does not claim browser/network latency or an LLM speed-up. The original
project had no chat endpoint. Reports machine-specific measurements.
"""
import json
import math
from pathlib import Path
import platform
import os
import sqlite3
import statistics
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import app as application


def measure(call, n=40, expected=200):
    started = time.perf_counter()
    first = call()
    cold = (time.perf_counter() - started)*1000
    assert first.status_code == expected, first.status_code
    values = []
    for _ in range(n):
        started = time.perf_counter()
        response = call()
        values.append((time.perf_counter() - started)*1000)
        assert response.status_code == expected, response.status_code
    ordered = sorted(values)
    return {'first_ms':round(cold,3),'p50_ms':round(statistics.median(values),3),
            'p95_ms':round(ordered[max(0, math.ceil(n*.95)-1)],3),
            'max_ms':round(max(values),3),'requests':n,'http_status':expected}


def main():
    app = application.app
    app.config['TESTING'] = True
    with tempfile.TemporaryDirectory(prefix='pp1-benchmark-') as directory:
        # Never add benchmark accounts or submissions to the delivered database.
        from data_store import get_store
        database=Path(directory)/'benchmark.sqlite3'
        with sqlite3.connect(get_store().path) as src, sqlite3.connect(database) as dst:
            src.backup(dst)
        os.environ['PP1_DATABASE']=str(database)
        get_store.cache_clear()
        client = app.test_client()
        client.get('/apply')
        with client.session_transaction() as session:
            csrf = session['csrf']
        results = {
            'summary': measure(lambda:client.get('/api/research/summary')),
            'borrowers_page': measure(lambda:client.get('/api/research/borrowers?page_size=20')),
            'chat_dataset': measure(lambda:client.post('/api/chat',json={'message':'What dataset is used?'},headers={'X-CSRF-Token':csrf})),
            'chat_clusters': measure(lambda:client.post('/api/chat',json={'message':'Explain borrower clusters'},headers={'X-CSRF-Token':csrf})),
        }
        client.post('/register',data={'csrf_token':csrf,'username':'benchmark.synthetic','password':'temporary-testing-only-123'})
        client.get('/apply')
        with client.session_transaction() as session: csrf=session['csrf']
        form = {'csrf_token':csrf,'name':'Benchmark Demo','dob':'1990-01-01','gender':'Other',
                'mobile':'9000000000','address':'Demonstration address','id_type':'PAN','id_number':'DEMO00000X',
                'monthly_income':'25000','years_business':'5','bank_account':'Yes','credit_card':'No',
                'existing_loan':'No','language':'English','description':'I need a loan of INR 50000 for wheat farming on 2 acres in Pune district.'}
        results['application_submit'] = measure(lambda:client.post('/submit',data=form),n=10,expected=302)
        record = {'runtime':sys.version.split()[0],'platform':platform.platform(),'measured_at':time.strftime('%Y-%m-%dT%H:%M:%S%z'),
                  'method':'Flask test client; one first call then sequential warm requests. Excludes process import, browser rendering, HTTP transport, OCR and on-demand PDF.',
                  'baseline':'No chat API existed in Phase 1. No before/after chat speed-up percentage is claimed.',
                  'results':results}
        (ROOT/'docs'/'performance_results.json').write_text(json.dumps(record,indent=2)+'\n')
        print(json.dumps(record,indent=2))


if __name__=='__main__':
    main()
