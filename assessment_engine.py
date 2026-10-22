"""Evidence-bounded application review using a transparent configurable demo policy.

All application amounts are INR. Neither historical US loan outcomes nor
protected/demographic attributes, card ownership, age or sentiment score an
applicant. No quantity, yield, revenue, cost or growth is filled by a default.
"""
from __future__ import annotations

from functools import lru_cache
import json
import math
import os
import re
import sqlite3
import statistics

import new
from narrative_sentiment import analyze_narrative

PURPOSES = {
    'car': 'Vehicle purchase', 'credit_card': 'Credit-card repayment',
    'debt_consolidation': 'Debt consolidation', 'educational': 'Education',
    'home_improvement': 'Home improvement', 'house': 'House purchase',
    'major_purchase': 'Major purchase', 'medical': 'Medical expenses',
    'moving': 'Moving and relocation', 'other': 'Other stated purpose',
    'renewable_energy': 'Renewable energy', 'small_business': 'Small business',
    'vacation': 'Travel and vacation', 'wedding': 'Wedding expenses',
}
PURPOSE_PATTERNS = (
    ('debt_consolidation', r'\b(?:consolidat\w*|combine\s+(?:my\s+)?debts?)\b'),
    ('credit_card', r'\bcredit[ -]?cards?\b'),
    ('educational', r'\b(?:education|educational|tuition|college|university|school fees|student fees)\b|शिक्षा|पढ़ाई'),
    ('medical', r'\b(?:medical|hospital|surgery|treatment|healthcare)\b|इलाज|अस्पताल'),
    ('renewable_energy', r'\b(?:solar|renewable|wind turbine|biogas)\b'),
    ('home_improvement', r'\b(?:renovat\w*|home improvement|house repair|home repair|remodel\w*)\b'),
    ('house', r'\b(?:buy|purchase)\s+(?:a\s+)?(?:house|home|flat|apartment)\b|\bhouse purchase\b'),
    ('car', r'\b(?:car|vehicle|motorcycle|scooter|auto rickshaw|truck|taxi)\b'),
    ('moving', r'\b(?:moving|relocat\w*|relocation)\b'),
    ('wedding', r'\b(?:wedding|marriage)\b|शादी'),
    ('vacation', r'\b(?:vacation|holiday|travel|tourism)\b'),
    ('major_purchase', r'\b(?:major purchase|appliance|furniture|refrigerator|laptop|computer)\b'),
    ('small_business', r'\b(?:business|shop|store|enterprise|workshop|startup|restaurant|tailor|sewing|salon|bakery|retail|trading)\b|व्यवसाय|दुकान'),
)
CITY_ALIASES = {'bengaluru': ('bengaluru', 'bangalore'), 'bangalore': ('bengaluru', 'bangalore'),
                'mumbai': ('mumbai', 'bombay'), 'chennai': ('chennai', 'madras')}
CITY_STATE = {'bengaluru': 'Karnataka', 'bangalore': 'Karnataka', 'mysuru': 'Karnataka',
              'mysore': 'Karnataka', 'mangalore': 'Karnataka', 'mangaluru': 'Karnataka',
              'pune': 'Maharashtra', 'mumbai': 'Maharashtra', 'chennai': 'Tamil Nadu',
              'hyderabad': 'Telangana', 'kochi': 'Kerala', 'jaipur': 'Rajasthan'}


def _value(data, *keys):
    for key in keys:
        value = data.get(key)
        if value is not None and str(value).strip() != '':
            return value
    return None


def _amount(value, label, *, positive=False):
    if value is None or str(value).strip() == '':
        return None
    try:
        if isinstance(value, bool):
            raise ValueError
        number = float(str(value).replace(',', '').strip())
    except (ValueError, TypeError) as exc:
        raise ValueError(f'{label} must be a number in INR.') from exc
    if not math.isfinite(number) or number < 0 or number > 1e9 or (positive and number <= 0):
        raise ValueError(f'{label} must be finite and {"greater than zero" if positive else "nonnegative"}, up to INR 1 billion.')
    return round(number, 2)


from policy_config import load_policy


def classify_purpose(data):
    description = str(data.get('description') or '')
    normalized = new.normalize_text(description)
    product, detected_sector = new.detect_product(normalized)
    raw = str(_value(data, 'loan_purpose', 'purpose', 'business_category') or '').strip()
    key = raw.casefold().replace('-', '_').replace(' ', '_')
    sector_raw = str(data.get('business_category') or data.get('sector') or '').casefold()
    if key in PURPOSES:
        purpose = key
        sector = 'farm' if purpose == 'small_business' and sector_raw in {'farm', 'farming', 'agriculture'} else 'dairy' if purpose == 'small_business' and sector_raw == 'dairy' else 'general'
    elif key in {'farm', 'farming', 'agriculture', 'agricultural'}:
        sector, purpose = 'farm', 'small_business'
    elif key in {'dairy', 'milk_business'}:
        sector, purpose = 'dairy', 'small_business'
    else:
        sector, purpose = 'general', key if key in PURPOSES else None
    source = 'user_entered' if raw else 'narrative_extracted'
    if raw and purpose is None:
        return {'raw': raw, 'purpose': 'unknown', 'sector': 'unknown', 'label': 'Purpose needs clarification',
                'source': 'user_entered_unrecognized', 'product': product}
    if purpose is None:
        if detected_sector:
            purpose, sector = 'small_business', detected_sector.casefold()
        elif re.search(r'\b(?:farm|farming|agricultur\w*|cultivat\w*)\b|खेती|कृषि', normalized, re.I):
            purpose, sector = 'small_business', 'farm'
        elif re.search(r'\bdairy\b|डेयरी', normalized, re.I):
            purpose, sector = 'small_business', 'dairy'
        else:
            for candidate, pattern in PURPOSE_PATTERNS:
                if re.search(pattern, normalized, re.I):
                    purpose = candidate
                    break
    elif purpose == 'small_business' and sector == 'general' and detected_sector:
        sector = detected_sector.casefold()
    if purpose == 'small_business' and sector == 'general':
        sector = 'small_business'
    purpose = purpose or 'unknown'
    label = {'farm': 'Farm business', 'dairy': 'Dairy business'}.get(sector, PURPOSES.get(purpose, 'Purpose needs clarification'))
    return {'raw': raw or description, 'purpose': purpose, 'sector': sector if purpose != 'unknown' else 'unknown',
            'label': label, 'source': source, 'product': product}


def _location(data):
    if _value(data, 'business_location', 'location') is not None:
        return str(_value(data, 'business_location', 'location')).strip(), 'user_entered'
    description = str(data.get('description') or '')
    for city in sorted(CITY_STATE, key=len, reverse=True):
        if re.search(r'\b' + re.escape(city) + r'\b', description, re.I):
            return city.title(), 'narrative_extracted'
    match = re.search(r'\bin\s+([A-Za-z ]{2,50}?)\s+(?:district|city)\b', description, re.I)
    return (match.group(1).strip().title(), 'narrative_extracted') if match else (None, 'missing')


def _finite_price(value):
    try:
        value = float(value)
        return value if math.isfinite(value) and value > 0 else None
    except (ValueError, TypeError):
        return None


def _context(category, location):
    """Fetch relevant observed context without generating an applicant forecast."""
    from data_store import get_store
    store = get_store()
    return _cached_context(str(store.path.resolve()), store._version(), category['purpose'],
                           category['sector'], str(category.get('product') or ''), str(location or ''))


@lru_cache(maxsize=256)
def _cached_context(database_path, version, purpose, sector, product, location):
    from data_store import get_store
    store = get_store()
    evidence = []
    if purpose == 'unknown':
        return evidence
    with store.pool.connection() as conn:
        n = conn.execute('SELECT COUNT(*) FROM loans WHERE purpose=?', (purpose,)).fetchone()[0]
        evidence.append({'source': 'Supplied historical LendingClub sample', 'scope': 'Historical US consumer lending',
            'match_scope': 'Loan-purpose category only; different population from this application', 'record_count': n,
            'description': f'{n:,} sampled records have purpose {purpose}. These records provide taxonomy/context only; their rates and outcomes do not set this applicant\'s terms or risk.',
            'price_unit': None, 'median_price': None, 'mean_price': None, 'latest_date': None, 'location': None, 'product': purpose})
        if sector not in {'farm', 'dairy'}:
            return evidence
        table, field = ('farm_records', 'crop') if sector == 'farm' else ('dairy_records', 'product')
        filters, values = [], []
        if product:
            filters.append(f'LOWER({field})=?')
            values.append(product.casefold())
        product_clause = (' WHERE ' + ' AND '.join(filters)) if filters else ''
        product_rows = conn.execute(f'SELECT location,row_json FROM {table}' + product_clause, values).fetchall()
        aliases = CITY_ALIASES.get(location.casefold(), (location.casefold(),)) if location else ()
        selected = [row for row in product_rows if row['location'].casefold() in aliases]
        match_scope = 'Exact supplied locality/product match' if selected else ''
        state = CITY_STATE.get(location.casefold())
        if not selected and state:
            selected = [row for row in product_rows if row['location'].casefold() == state.casefold()]
            if selected:
                match_scope = f'State-level fallback: {state}; no city-level match for {location}'
        if not selected:
            selected = product_rows
            match_scope = 'All supplied locations for this product/sector; no local match' if location else 'All supplied locations; applicant locality not provided'
        prices = []
        if sector == 'dairy' and product:
            for row in selected:
                price = _finite_price(json.loads(row['row_json']).get('Price per Unit (sold)'))
                if price is not None:
                    prices.append(price)
        evidence.append({'source': 'Supplied dairy_dataset.csv' if sector == 'dairy' else 'Supplied data_season.csv',
            'scope': 'Separate Indian business context; not borrower-linked loan outcomes',
            'match_scope': match_scope, 'record_count': len(selected), 'location': location, 'product': product or None,
            'description': 'Observed source context only. These prices/records do not supply business quantity, costs, profit or growth for the applicant.',
            'price_unit': 'INR per source unit (liters/kg); exact product unit not standardized' if prices else None,
            'median_price': round(statistics.median(prices), 2) if prices else None,
            'mean_price': round(statistics.mean(prices), 2) if prices else None, 'latest_date': None})
    if sector == 'farm' and product and location:
        match = None
        matched_location = location
        for candidate in CITY_ALIASES.get(location.casefold(), (location.casefold(),)):
            match = store.market_price(candidate, product)
            if match:
                matched_location = candidate
                break
        if match:
            evidence.append(dict(match, record_count=match['observations'], location=matched_location, product=product,
                scope='Historical market-price context', match_scope='Exact district/market/state key and commodity match',
                description='Historical supplied prices only; not current quotes. No yield, acreage, sales volume or operating cost is inferred.'))
        else:
            evidence.append({'source': 'Supplied AGMARKNET workbook', 'scope': 'Historical market-price context',
                'match_scope': 'No locality-and-commodity match', 'record_count': 0, 'location': location, 'product': product,
                'description': 'No matching local price is available. No national or invented price is inserted into the application.',
                'price_unit': 'INR per quintal', 'median_price': None, 'mean_price': None, 'latest_date': None})
    return evidence


def assess_application(borrower_data):
    data = dict(borrower_data)
    if str(data.get('currency', 'INR')).upper() != 'INR':
        raise ValueError('Application inputs must be supplied in INR.')
    policy = load_policy()
    requested_term = _value(data, 'term_months', 'requested_term_months', 'repayment_months')
    if requested_term is not None:
        if isinstance(requested_term, bool) or not re.fullmatch(r'\d+', str(requested_term).strip()):
            raise ValueError('Requested term must be a whole number of months.')
        months = int(requested_term)
        if not policy['min_term_months'] <= months <= policy['max_term_months']:
            raise ValueError(f'Requested term must be from {policy["min_term_months"]} to {policy["max_term_months"]} months under the configured demo policy.')
        policy['term_months'] = months
    policy['term_source'] = 'user_entered' if requested_term is not None else 'configured_policy_default'
    policy['description'] = (f'Illustrative {policy["annual_rate"]*100:g}% annual nominal interest, '
        f'{policy["term_months"]} monthly installments ({"requested term" if requested_term is not None else "configured default term"}), '
        f'and total monthly debt installments at most {policy["max_total_debt_ratio"]*100:g}% of declared monthly income. '
        f'Allowed term range: {policy["min_term_months"]}-{policy["max_term_months"]} months.')
    description = str(data.get('description') or '').strip()
    category = classify_purpose(data)
    location, location_source = _location(data)
    provenance = []
    raw_amount = _value(data, 'loan_amount', 'requested_amount')
    amount_source = 'user_entered' if raw_amount is not None else 'narrative_extracted'
    if raw_amount is None:
        normalized = new.normalize_text(description)
        if re.search(r'\b(?:USD|EUR|GBP|dollars?|euros?|pounds?)\b|[$€£]', description, re.I):
            raise ValueError('Enter the requested loan amount explicitly in INR; a foreign-currency narrative is not silently converted.')
        if re.search(r'(?:loan|amount|inr|rs\.?|₹|ऋण|लोन)\s*(?:of|is|around)?\s*[-−]\s*\d|[-−]\s*\d+(?:\.\d+)?\s*(?:rupees|रुपये)', normalized, re.I):
            raise ValueError('Requested loan amount must be positive.')
        if re.search(r'(?:loan|amount|inr|rs\.?|₹|ऋण|लोन)\s*(?:of|is|around)?\s*0(?:\.0+)?(?![\d.])|\b0(?:\.0+)?\s*(?:rupees|रुपये)\b', normalized, re.I):
            raise ValueError('Requested loan amount must be positive.')
        detected = new.detect_loan_amount(normalized)
        raw_amount = detected if detected else None
    principal = _amount(raw_amount, 'Requested loan amount', positive=True)
    fields = [('monthly_income', 'Declared monthly income'), ('existing_monthly_debt', 'Existing monthly debt installments'),
              ('monthly_business_revenue', 'Monthly business revenue'), ('monthly_business_costs', 'Monthly business operating costs')]
    financials = {name: _amount(data.get(name), label) for name, label in fields}
    debt_source = 'user_entered'
    if financials['existing_monthly_debt'] is None and str(data.get('existing_loan') or '').casefold() == 'no':
        financials['existing_monthly_debt'] = 0.0
        debt_source = 'user_declaration_no_existing_loan'
    provenance.append({'field': 'loan_amount', 'label': 'Requested principal', 'value': principal,
                       'source': amount_source if principal is not None else 'missing',
                       'detail': 'Explicit input takes precedence over text extraction. No default loan amount is used.'})
    provenance.append({'field': 'term_months', 'label': 'Repayment term (months)', 'value': policy['term_months'],
                       'source': policy['term_source'], 'detail': f'Configured permitted range {policy["min_term_months"]}-{policy["max_term_months"]} months; default {policy["default_term_months"]} months.'})
    for name, label in fields:
        value = financials[name]
        provenance.append({'field': name, 'label': label, 'value': value,
                           'source': (debt_source if name == 'existing_monthly_debt' else 'user_entered') if value is not None else 'missing',
                           'detail': 'Explicit declaration; not verified against documents. No dataset median is substituted.'})
    provenance.extend([{'field': 'purpose', 'label': 'Loan purpose', 'value': category['label'], 'source': category['source'], 'detail': 'Original category/text is retained for review.'},
                       {'field': 'location', 'label': 'Business locality', 'value': location, 'source': location_source, 'detail': 'Only identified locality is used; fallback scope appears with context.'}])
    schedule, emi, interest = [], None, None
    if principal is not None:
        frame, emi, interest = new.generate_repayment_schedule(principal, policy['annual_rate'], policy['term_months'])
        schedule = frame.to_dict(orient='records')
    total = round(sum(row['EMI'] for row in schedule), 2) if schedule else None
    terms = {'principal': principal, 'annual_rate': policy['annual_rate'], 'term_months': policy['term_months'],
             'months': policy['term_months'], 'emi': emi, 'total_interest': interest, 'total_repayment': total,
             'schedule': schedule, 'currency': 'INR', 'policy': policy}
    income, debt = financials['monthly_income'], financials['existing_monthly_debt']
    revenue, costs = financials['monthly_business_revenue'], financials['monthly_business_costs']
    paired = revenue is not None and costs is not None
    debt_total = round(debt + emi, 2) if debt is not None and emi is not None else None
    debt_ratio = debt_total / income if income is not None and income > 0 and debt_total is not None else None
    annual_debt_service = round(sum(row['EMI'] for row in schedule[:12]), 2) if schedule else None
    surplus = round((revenue - costs) * 12, 2) if paired else None
    financials.update(annual_revenue=round(revenue * 12, 2) if paired else None,
                      annual_operating_costs=round(costs * 12, 2) if paired else None,
                      annual_operating_surplus=surplus,
                      annual_cash_after_debt_service=round(surplus - annual_debt_service, 2) if surplus is not None and annual_debt_service is not None else None,
                      total_monthly_debt=debt_total, debt_to_income_ratio=debt_ratio,
                      monthly_income_after_debt=round(income - debt_total, 2) if income is not None and debt_total is not None else None)
    missing, traces, concerns = [], [], []
    def trace(id, label, status, observed, threshold, explanation):
        traces.append(dict(id=id, label=label, status=status, observed=observed, threshold=threshold, explanation=explanation))
    for id, label, value in [('amount', 'Requested principal', principal), ('income', 'Declared monthly income', income), ('obligations', 'Existing monthly debt installments', debt)]:
        if value is None:
            missing.append(f'Provide {label.lower()} in INR.')
        trace(id, label, 'missing' if value is None else 'pass', value, 'Explicit value required',
              'Missing information is not replaced by a default.' if value is None else 'Value supplied; documentary verification is still required.')
    if category['purpose'] == 'unknown':
        missing.append('Clarify the loan purpose or business sector.')
    trace('purpose', 'Purpose classification', 'missing' if category['purpose'] == 'unknown' else 'pass', category['label'], 'Recognized stated purpose',
          'Classification organizes relevant evidence and does not affect a risk score.')
    business = category['purpose'] == 'small_business'
    if business and not paired:
        missing.append('Provide both monthly business revenue and monthly operating costs to calculate business cashflow. Enter zero explicitly where appropriate.')
    trace('business_cashflow', 'Declared business cashflow', 'missing' if business and not paired else 'info',
          'Both figures supplied' if paired else 'Unavailable', 'No inferred yield, quantity, margin or growth',
          'Annual figures are 12 times the entered monthly amounts, not a growth forecast.' if paired else 'No business income or profit projection can be calculated from a business description or market price alone.')
    if income == 0 and debt_total is not None and debt_total > 0:
        concerns.append('Declared monthly income is zero while scheduled debt installments are positive.')
        ratio_status, ratio_explanation = 'concern', concerns[-1]
    elif debt_ratio is None:
        ratio_status, ratio_explanation = 'missing', 'Income, principal and existing obligations are needed to calculate this ratio.'
    elif debt_ratio > policy['max_total_debt_ratio']:
        concerns.append(f'Total monthly debt installments use {debt_ratio*100:.1f}% of declared income, above the demo policy limit of {policy["max_total_debt_ratio"]*100:g}%.')
        ratio_status, ratio_explanation = 'concern', concerns[-1]
    else:
        ratio_status, ratio_explanation = 'pass', f'Total monthly debt installments use {debt_ratio*100:.1f}% of declared income, within the configured demonstration limit. This is not a lender approval.'
    trace('debt_ratio', 'Total installment burden', ratio_status, debt_ratio, policy['max_total_debt_ratio'], ratio_explanation)
    if business and surplus is not None and annual_debt_service is not None:
        shortfall = surplus < annual_debt_service
        count = min(12, policy['term_months'])
        explanation = f'Annualized declared operating surplus does not cover the first {count} scheduled installments.' if shortfall else f'Annualized declared operating surplus covers the first {count} scheduled installments; verify business accounts and living costs.'
        trace('surplus_coverage', 'Business surplus versus scheduled payments', 'concern' if shortfall else 'pass', surplus, annual_debt_service, explanation)
        if shortfall:
            concerns.append(explanation)
    status = 'affordability_concern' if concerns else 'needs_information' if missing else 'ready_for_review'
    labels = {'ready_for_review': 'Ready for human review', 'needs_information': 'More information needed', 'affordability_concern': 'Affordability concern - review required'}
    try:
        context = _context(category, location)
    except (OSError, RuntimeError, sqlite3.Error, TimeoutError, ValueError):
        context = [{'source': 'Local prepared datasets', 'scope': 'Unavailable', 'match_scope': 'No lookup completed',
                    'record_count': 0, 'description': 'Dataset context is unavailable. No missing evidence has been replaced with an estimate.',
                    'price_unit': None, 'median_price': None, 'mean_price': None, 'latest_date': None, 'location': location, 'product': category.get('product')}]
    # Copy cached dictionaries so callers cannot change another request's context.
    context = json.loads(json.dumps(context))
    applicant = {'Applicant Name': str(data.get('name') or 'Applicant'), 'Decision': labels[status],
                 'Requested Loan': principal, 'Monthly EMI': emi, 'Total Interest': interest,
                 'Annual Interest Rate': f'{policy["annual_rate"]*100:g}% (demo policy)',
                 'Estimated Annual Revenue': financials['annual_revenue'], 'Operating Surplus': surplus,
                 'Operating Costs': financials['annual_operating_costs'], 'Annual Cash After Debt Service': financials['annual_cash_after_debt_service'],
                 'Projection Basis': 'Only explicitly entered monthly business revenue and operating costs are annualized. No growth forecast.',
                 'Loan Purpose': category['label'], 'Currency': 'INR'}
    reasons = [item['explanation'] for item in traces if item['id'] in {'debt_ratio', 'business_cashflow', 'surplus_coverage'}]
    result = {'status': status, 'status_label': labels[status], 'missing_information': missing,
        'concerns': concerns, 'rule_trace': traces, 'category': category, 'input_provenance': provenance,
        'dataset_context': context, 'loan_terms': terms, 'policy_snapshot': policy, 'financials': financials,
        'applicant_copy': applicant, 'bank_copy': dict(applicant, **{'Annual Interest Rate': policy['annual_rate']}),
        'business_description': description,
        'sentiment': analyze_narrative(description),
        'repayment_assessment': {'can_repay': None, 'within_demo_limit': ratio_status == 'pass', 'confidence_score': None,
            'emi_burden_percent': round(debt_ratio*100, 2) if debt_ratio is not None else None, 'reasons': reasons},
        'interest_assessment': {'base_rate': policy['annual_rate'], 'final_rate': policy['annual_rate'], 'increase': 0,
            'factors': [{'name': 'Configured demonstration policy', 'impact': 0, 'impact_display': 'Fixed', 'reason': policy['description']}]},
        'entities': {'loan_amount': principal, 'category': category['label'], 'product': category.get('product'), 'location': location, 'area': None, 'quantity': None, 'unit_price': None},
        'projection': {'revenue': financials['annual_revenue'], 'operating_cost': financials['annual_operating_costs'],
                       'operating_surplus': surplus, 'assumptions': [], 'basis': applicant['Projection Basis']},
        'chart_data': {'repayment': schedule, 'principal': principal, 'total_interest': interest,
                       'monthly_income': income, 'existing_monthly_debt': debt, 'emi': emi,
                       'remaining_monthly_income': financials['monthly_income_after_debt']},
        'limitations': ['No lending approval, repayment probability or poverty-impact estimate is produced.', policy['limitations'],
                       'Only explicitly supplied financial values are used. No business growth, yield, quantity or margin is inferred.',
                       'Historical dataset context is separate from this applicant and does not establish actual outcomes.'],
        'alternative_business': None}
    return result
