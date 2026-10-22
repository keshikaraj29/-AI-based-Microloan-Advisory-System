"""Microloan Atlas: owned applications, explainable research and recorded payments."""
from collections import defaultdict, deque
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
from urllib.parse import urlencode, urlsplit
import io
import json
import math
import os
import re
import secrets
import sqlite3
import threading
import time

from flask import Flask, abort, flash, g, jsonify, redirect, render_template, request, send_file, session, url_for
from PIL import Image
from currency_tools import format_inr, get_fx

BASE = Path(__file__).resolve().parent
BASE_DIR = str(BASE)
REPORT_FOLDER = str(BASE/'reports')
TESSDATA_DIR = str(BASE/'tessdata')
os.environ.setdefault('MPLBACKEND', 'Agg')
os.environ.setdefault('MPLCONFIGDIR', str(BASE/'instance'/'matplotlib'))


def _secret():
    configured = os.environ.get('SECRET_KEY')
    if os.environ.get('PP1_ENV') == 'production' and (not configured or len(configured) < 32):
        raise RuntimeError('Production requires a SECRET_KEY of at least 32 characters.')
    if configured:
        return configured
    path = BASE/'instance'/'secret_key'
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open('x') as handle:
            os.chmod(path, 0o600)
            handle.write(secrets.token_hex(32))
    except FileExistsError:
        pass
    return path.read_text().strip()


app = Flask(__name__)
app.secret_key = _secret()
app.config.update(MAX_CONTENT_LENGTH=8*1024*1024, SESSION_COOKIE_HTTPONLY=True,
                  SESSION_COOKIE_SAMESITE='Lax', SESSION_COOKIE_SECURE=os.environ.get('PP1_ENV') == 'production',
                  PERMANENT_SESSION_LIFETIME=timedelta(hours=12), SEND_FILE_MAX_AGE_DEFAULT=86400)
PDF_LOCK = threading.Lock()
RATE_LOCK = threading.Lock()
RATE_BUCKETS = defaultdict(deque)


def csrf_token():
    if 'csrf' not in session:
        session['csrf'] = secrets.token_urlsafe(32)
    return session['csrf']


def asset_url(filename):
    path = Path(app.static_folder)/filename
    return url_for('static', filename=filename, v=path.stat().st_mtime_ns)


app.jinja_env.globals.update(csrf_token=csrf_token, asset_url=asset_url)
app.jinja_env.filters['inr'] = format_inr


@app.context_processor
def shared_context():
    try: fx=get_fx()
    except (RuntimeError,OSError,ValueError): fx=None
    return {'current_user': getattr(g, 'user', None), 'fx':fx}


def safe_next(value):
    try: parsed = urlsplit(value or '')
    except ValueError: return url_for('applications')
    return value if value and value.startswith('/') and not value.startswith('//') and not parsed.netloc and not parsed.scheme and '\\' not in value else url_for('applications')


def limited(key, limit, seconds):
    now = time.monotonic()
    with RATE_LOCK:
        if len(RATE_BUCKETS) > 10000:
            RATE_BUCKETS.clear()
        bucket = RATE_BUCKETS[key]
        while bucket and bucket[0] <= now-seconds:
            bucket.popleft()
        if len(bucket) >= limit:
            return True
        bucket.append(now)
    return False


@app.before_request
def protect_request():
    g.started = time.perf_counter()
    from application_store import get_user
    g.user = get_user(session['user_id']) if 'user_id' in session else None
    if 'user_id' in session and not g.user:
        session.clear()
    if request.method == 'POST':
        supplied = request.headers.get('X-CSRF-Token') or request.form.get('csrf_token', '')
        if not secrets.compare_digest(str(supplied), str(session.get('csrf', '__missing__'))):
            if request.path.startswith('/api/'):
                return jsonify(error='Session token expired. Refresh the page.'),400
            flash('Session token expired. Please submit again.')
            return redirect(url_for('login') if request.path in ('/login','/register') else url_for('apply'))
        if not app.testing and request.path in ('/login','/register','/api/chat'):
            auth = request.path != '/api/chat'
            if limited((request.remote_addr, 'auth' if auth else 'chat'), 30 if auth else 100, 900 if auth else 60):
                if request.path.startswith('/api/'):
                    return jsonify(error='Too many requests. Please retry shortly.'),429
                flash('Too many attempts. Please retry in a few minutes.')
                return render_template('auth.html',mode='login'),429


@app.after_request
def response_headers(response):
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['X-Frame-Options']='DENY'
    response.headers['Referrer-Policy']='same-origin'
    response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'self'; object-src 'none'"
    response.headers['Server-Timing']=f'app;dur={(time.perf_counter()-getattr(g,"started",time.perf_counter()))*1000:.2f}'
    if not request.path.startswith('/static/'):
        response.headers['Cache-Control']='no-store'
    return response


def login_required(function):
    @wraps(function)
    def wrapper(*args,**kwargs):
        if not g.user:
            if request.path.startswith('/api/'):
                return jsonify(error='Sign in to access your applications.'),401
            flash('Sign in to save and access your application securely.')
            return redirect(url_for('login',next=request.path))
        return function(*args,**kwargs)
    return wrapper


def owned_application(application_id):
    from application_store import get_application
    if not g.user:
        abort(401)
    try:
        return get_application(g.user['id'],application_id)
    except LookupError:
        abort(404)


@app.errorhandler(sqlite3.Error)
@app.errorhandler(TimeoutError)
@app.errorhandler(RuntimeError)
@app.errorhandler(FileNotFoundError)
def service_error(error):
    app.logger.error('Service unavailable: %s',type(error).__name__)
    if request.path.startswith('/api/'):
        return jsonify(error='The data service is unavailable. Please retry or check the setup guide.'),503
    return render_template('error.html', title='Data temporarily unavailable', message='Please retry shortly. If this continues, check the data preparation and server setup.'),503


@app.errorhandler(404)
@app.errorhandler(401)
def inaccessible(error):
    if request.path.startswith('/api/'):
        return jsonify(error='This record is unavailable for this account.'),error.code
    return render_template('error.html',title='Record unavailable',message='Sign in to the account that owns this record, or return to your applications.'),error.code


@app.errorhandler(413)
def too_large(error):
    if request.path.startswith('/api/'):
        return jsonify(error='Upload exceeds 8 MB.'),413
    flash('Upload exceeds 8 MB. Choose a smaller file.')
    return redirect(url_for('apply'))


@app.get('/')
def landing():
    return render_template('landing.html')


@app.get('/apply')
def apply():
    from research_analytics import get_research_summary
    draft=owned_application(request.args['from'])['borrower_data'] if request.args.get('from') else {}
    return render_template('index.html', purposes=get_research_summary().get('filters',{}).get('purposes',[]),draft=draft)


@app.route('/register',methods=['GET','POST'])
def register():
    from application_store import create_user
    if request.method == 'POST':
        try:
            user=create_user(request.form.get('username',''),request.form.get('password',''))
            session.clear();session.update(user_id=user['id'],username=user['username']);session.permanent=True
            return redirect(safe_next(request.form.get('next') or request.args.get('next')))
        except ValueError as exc:
            flash(str(exc))
    return render_template('auth.html',mode='register',next=safe_next(request.args.get('next')))


@app.route('/login',methods=['GET','POST'])
def login():
    from application_store import authenticate_user
    if request.method == 'POST':
        user=authenticate_user(request.form.get('username',''),request.form.get('password',''))
        if user:
            session.clear();session.update(user_id=user['id'],username=user['username']);session.permanent=True
            return redirect(safe_next(request.form.get('next') or request.args.get('next')))
        flash('Username or password is incorrect.')
    return render_template('auth.html',mode='login',next=safe_next(request.args.get('next')))


@app.post('/logout')
def logout():
    session.clear()
    return redirect(url_for('landing'))


def validate_mobile(value):
    return bool(re.fullmatch(r'\d{10}',str(value or '')))


def validate_income(value):
    try:
        return math.isfinite(float(value)) and 0<float(value)<=1e9
    except (TypeError,ValueError):
        return False


def calculate_age(dob):
    birth=datetime.strptime(dob,'%Y-%m-%d').date();today=datetime.today().date()
    return today.year-birth.year-((today.month,today.day)<(birth.month,birth.day))


def extract_description_from_image(file_storage):
    if not file_storage or not file_storage.filename:
        return ''
    if file_storage.filename.rsplit('.',1)[-1].lower() not in {'png','jpg','jpeg','webp','bmp','tif','tiff'}:
        raise ValueError('Upload a valid image file.')
    try:
        image=Image.open(file_storage.stream)
        if image.width*image.height>20_000_000:
            raise ValueError('Use an image below 20 megapixels.')
        image.load()
    except (OSError,Image.DecompressionBombError) as exc:
        raise ValueError('The uploaded file is not a readable image.') from exc
    try:
        import pytesseract
        if Path(TESSDATA_DIR).is_dir(): os.environ['TESSDATA_PREFIX']=TESSDATA_DIR
        languages=set(pytesseract.get_languages(config=''))
        text=pytesseract.image_to_string(image.convert('RGB'),lang='eng+hin' if {'eng','hin'}<=languages else 'eng',config='--psm 6',timeout=15)
    except Exception as exc:
        raise ValueError('OCR needs a working Tesseract installation. Type the description or follow the setup guide.') from exc
    return re.sub(r'\s+',' ',text).strip()


def run_web_loan_analysis(borrower_data):
    from assessment_engine import assess_application
    return assess_application(borrower_data)


def create_bank_pdf_report(result,path):
    from report_builder import create_assessment_pdf
    return create_assessment_pdf(result,path)


def weighted_sentiment_analysis(text):
    from research_analytics import narrative_sentiment
    score,label=narrative_sentiment(text)
    return {'score':score,'label':label.title()}


@app.post('/submit')
@login_required
def submit():
    from application_store import save_application
    try:
        data={k:request.form.get(k,'').strip() for k in ('name','dob','monthly_income','years_business','bank_account','existing_loan','language','description','loan_amount','term_months','monthly_business_revenue','monthly_business_costs','existing_monthly_debt','loan_purpose','business_category','location')}
        if not data['name'] or len(data['name'])>120: raise ValueError('Enter a name up to 120 characters.')
        if data['dob'] and not 18<=calculate_age(data['dob'])<=110: raise ValueError('Enter a valid adult date of birth.')
        typed=data['description'];ocr=extract_description_from_image(request.files.get('description_image'))
        data['description']='\n'.join(p for p in (typed,ocr) if p)
        if not data['description'] or len(data['description'])>6000: raise ValueError('Enter a business story between 1 and 6,000 characters.')
        result=run_web_loan_analysis(data)
        # No KYC numbers, phone, address, gender or date of birth are persisted.
        data.pop('dob',None)
        application_id=save_application(g.user['id'],data,result)
        return redirect(url_for('assessment',application_id=application_id))
    except (ValueError,KeyError) as exc:
        flash(str(exc) if isinstance(exc,ValueError) else 'Check the application fields.')
        from research_analytics import get_research_summary
        return render_template('index.html',draft=data,purposes=get_research_summary().get('filters',{}).get('purposes',[])),400


@app.get('/applications')
@login_required
def applications():
    from application_store import list_applications
    try: page=max(1,int(request.args.get('page',1)))
    except ValueError: page=1
    return render_template('applications.html',applications=list_applications(g.user['id'],page=page,page_size=20))


@app.get('/applications/<application_id>')
@login_required
def application_detail(application_id):
    return render_template('application_detail.html',application=owned_application(application_id))


@app.get('/applications/<application_id>/assessment')
@login_required
def assessment(application_id):
    record=owned_application(application_id)
    return render_template('result.html',result=record['result'],application=record,application_id=application_id,applicant_file=f'applicant_{application_id}.json',bank_file=f'bank_{application_id}.pdf')


@app.get('/applications/<application_id>/explanation')
@login_required
def explanation(application_id):
    record=owned_application(application_id)
    return render_template('explanation.html',application=record,result=record['result'],explanation=record['result'])


@app.post('/applications/<application_id>/start')
@login_required
def start_tracking(application_id):
    from application_store import start_tracking as start
    try:
        if request.form.get('confirm_recording') not in ('on','yes','1'): raise ValueError('Confirm that you are recording a disbursement that already occurred.')
        rate=request.form.get('annual_rate_percent','').strip()
        try: rate=float(rate)/100 if rate else None
        except ValueError: raise ValueError('Enter an annual interest rate as a percentage.')
        start(g.user['id'],application_id,request.form.get('start_date',''),
              principal=request.form.get('actual_principal') or None,annual_rate=rate,
              months=request.form.get('term_months') or None)
        flash('Repayment tracking started. This records your entry; no funds were transferred.')
    except LookupError: abort(404)
    except ValueError as exc: flash(str(exc))
    return redirect(url_for('application_detail',application_id=application_id))


@app.post('/applications/<application_id>/payments')
@login_required
def add_payment(application_id):
    from application_store import record_payment
    try:
        record_payment(g.user['id'],application_id,request.form.get('amount'),request.form.get('paid_on'),request.form.get('reference'))
        flash('Payment recorded and allocated to the repayment schedule.')
    except LookupError: abort(404)
    except ValueError as exc: flash(str(exc))
    return redirect(url_for('application_detail',application_id=application_id))


@app.post('/applications/<application_id>/payments/import')
@login_required
def import_payments(application_id):
    from application_store import import_payments_csv
    try:
        uploaded=request.files.get('payment_csv')
        if not uploaded or not uploaded.filename: raise ValueError('Choose a payment CSV file.')
        text=uploaded.read(1_000_001)
        if len(text)>1_000_000: raise ValueError('Payment CSV must be below 1 MB.')
        result=import_payments_csv(g.user['id'],application_id,text.decode('utf-8-sig'))
        flash(f"Imported {result['imported']} payments; {result['duplicates']} existing references skipped.")
    except LookupError: abort(404)
    except (ValueError,UnicodeError) as exc: flash(str(exc))
    return redirect(url_for('application_detail',application_id=application_id))


@app.get('/download/<filename>')
@login_required
def download_file(filename):
    match=re.fullmatch(r'(applicant|bank)_([0-9a-f-]{36})\.(json|pdf)',filename)
    if not match: abort(404)
    kind,identifier,extension=match.groups()
    if (kind,extension) not in {('applicant','json'),('bank','pdf')}: abort(404)
    record=owned_application(identifier)
    if kind=='applicant':
        payload=json.dumps(record['canonical'],ensure_ascii=False,allow_nan=False,indent=2).encode()
        return send_file(io.BytesIO(payload),mimetype='application/json',as_attachment=True,download_name=filename)
    # PDF remains generated on demand; the database is the authoritative JSON store.
    import tempfile
    with PDF_LOCK, tempfile.TemporaryDirectory(prefix='atlas-report-') as folder:
        path=Path(folder)/filename
        create_bank_pdf_report(record['result'],path)
        content=path.read_bytes()
    return send_file(io.BytesIO(content),mimetype='application/pdf',as_attachment=True,download_name=filename)


@app.get('/research')
def research():
    application_id=request.args.get('application_id')
    record=owned_application(application_id) if application_id else None
    purpose=record['result']['category']['purpose'] if record else request.args.get('purpose','')
    if purpose == 'unknown': purpose = ''
    return render_template('research.html',application=record,application_id=application_id,purpose=purpose)


@app.get('/api/health')
def health():
    from data_store import get_store
    return jsonify(status='ok',data=get_store().table_counts(),chat='local evidence and navigation',currency='INR')


@app.get('/api/research/summary')
def research_summary():
    from research_service import summary_for_category
    try: return jsonify(summary_for_category(request.args.get('purpose') or None))
    except ValueError as exc: return jsonify(error=str(exc)),400


@app.get('/api/research/borrowers')
def research_borrowers():
    from research_service import research_page
    from application_store import list_applications
    try:
        page=int(request.args.get('page',1));size=int(request.args.get('page_size',20))
        if not 1<=page<=10000 or not 1<=size<=100: raise ValueError('Choose a positive page and a page size from 1 to 100.')
        source=request.args.get('source','research')
        if source=='applications':
            if not g.user: return jsonify(error='Sign in to explore your applications.'),401
            return jsonify(list_applications(g.user['id'],page=page,page_size=size,purpose=request.args.get('purpose') or None))
        if source!='research': raise ValueError('Choose research or applications as the source.')
        return jsonify(research_page(page=page,per_page=size,purpose=request.args.get('purpose') or None,state=request.args.get('state') or None,cluster=request.args.get('cluster') or None))
    except (TypeError,ValueError) as exc: return jsonify(error=str(exc)),400


@app.get('/api/research/context')
@login_required
def research_context():
    identifier=request.args.get('application_id','');record=owned_application(identifier)
    result=record['result']
    return jsonify(application_context=result['dataset_context'],category=result['category'],explanation_url=url_for('explanation',application_id=identifier),application_id=identifier,result_status=result['status'])


@app.get('/api/research/business')
def business_records():
    from research_service import context_records
    try:
        return jsonify(context_records(source=request.args.get('source','dairy'),
            page=int(request.args.get('page',1)),per_page=int(request.args.get('page_size',20)),
            product=request.args.get('product') or None,location=request.args.get('location') or None))
    except (ValueError,TypeError) as exc:
        return jsonify(error=str(exc)),400


@app.get('/api/research/impact')
def household_impact():
    from impact_outcomes import analyze_outcomes
    from currency_tools import household_summary_inr
    return jsonify(household_summary_inr(analyze_outcomes()))


@app.post('/api/chat')
def chat():
    from atlas_service import answer
    payload=request.get_json(silent=True)
    if not isinstance(payload,dict) or not isinstance(payload.get('message'),str): return jsonify(error='Send a JSON object containing a message.'),400
    if payload.get('application_id') is not None and not isinstance(payload['application_id'],str): return jsonify(error='application_id must be a string.'),400
    message=payload['message'].strip()
    if not 1<=len(message)<=1000: return jsonify(error='Enter between 1 and 1,000 characters.'),400
    record=owned_application(payload['application_id']) if payload.get('application_id') else None
    result=answer(message,record)
    result['elapsed_ms']=round((time.perf_counter()-g.started)*1000,2)
    return jsonify(result)


if __name__=='__main__':
    app.run(host='127.0.0.1',port=int(os.environ.get('PORT','5000')),debug=False,threaded=True)
