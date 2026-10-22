"""Auditable INR presentation with a pinned, sourced exchange-rate snapshot."""
from copy import deepcopy
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from functools import lru_cache
import json
import math
import os
from pathlib import Path

BASE = Path(__file__).resolve().parent


@lru_cache(maxsize=4)
def _read(path, mtime):
    data = json.loads(Path(path).read_text())
    rate = float(data['usd_to_inr'])
    if isinstance(data['usd_to_inr'],bool) or not math.isfinite(rate) or rate <= 0:
        raise ValueError('Conversion rate must be positive and finite.')
    if data.get('source_currency')!='USD' or data.get('display_currency')!='INR':
        raise ValueError('The configured conversion must use source USD and display INR.')
    return data


def get_fx():
    path = Path(os.environ.get('PP1_FX_CONFIG', BASE/'config'/'fx.json'))
    try:
        return deepcopy(_read(str(path), path.stat().st_mtime_ns))
    except (OSError,ValueError,KeyError,TypeError) as exc:
        raise RuntimeError('The INR reference-rate configuration is missing or invalid. Check config/fx.json.') from exc


def convert_source_amount(value,rate=None):
    if value is None:
        return None
    try:
        number = Decimal(str(value))
        if not number.is_finite():
            return None
        rate = get_fx()['usd_to_inr'] if rate is None else rate
        return float((number * Decimal(str(rate))).quantize(Decimal('.01'), rounding=ROUND_HALF_UP))
    except (InvalidOperation,TypeError,ValueError,OverflowError):
        return None


def format_inr(value):
    if value is None or value == '':
        return 'Not provided'
    try:
        val = Decimal(str(value))
        if not val.is_finite():
            return 'Not provided'
        val = val.quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
    except (TypeError, ValueError,InvalidOperation):
        return 'Not provided'
    sign = '-' if val < 0 else ''
    whole, fraction = f'{abs(val):.2f}'.split('.')
    if len(whole) > 3:
        prefix, suffix = whole[:-3], whole[-3:]
        groups = []
        while prefix:
            groups.insert(0, prefix[-2:])
            prefix = prefix[:-2]
        whole = ','.join(groups + [suffix])
    return f'{sign}₹{whole}.{fraction}'


def research_summary_inr(summary):
    result = deepcopy(summary)
    if result.get('dataset',{}).get('currency')=='INR' and result.get('fx'):
        return result
    result['fx'] = get_fx()
    rate = result['fx']['usd_to_inr']
    original = result['dataset'].get('currency','USD')
    if original not in ('USD','INR'):
        raise RuntimeError('No INR conversion is configured for the research source currency.')
    convert = (lambda value:convert_source_amount(value,rate)) if original=='USD' else (lambda value:value)
    result['dataset']['source_currency'] = original
    result['dataset']['currency'] = 'INR'
    result['dataset']['display_note'] = result['fx']['scope']
    for source in result['dataset'].get('sources', []):
        if source.get('currency') == 'USD':
            source['source_currency'] = 'USD'
            source['currency'] = 'INR (converted reference values)'
    for group_name in ('clusters', 'loan_structures'):
        for row in result.get(group_name, []):
            for field in ('mean_loan_amount', 'mean_annual_income'):
                if field in row:
                    row[field] = convert(row[field])
    methods = result.get('methods', {})
    for field in ('loan_amount', 'annual_income'):
        if field in methods.get('imputation_medians', {}):
            methods['imputation_medians'][field] = convert(methods['imputation_medians'][field])
        if field in methods.get('clip_bounds_1_99_percentile', {}):
            methods['clip_bounds_1_99_percentile'][field] = [convert(x) for x in methods['clip_bounds_1_99_percentile'][field]]
    methods['monetary_display_currency'] = 'INR'
    methods['monetary_units_note'] = 'Monetary method summaries are converted for display. Models were fitted in the original source monetary units; use the source research artifact for exact reproduction.'
    return result


def research_page_inr(page):
    result = deepcopy(page)
    if result.get('display_currency')=='INR' and result.get('fx'):
        return result
    result['fx'] = get_fx()
    rate = result['fx']['usd_to_inr']
    for row in result.get('items', []):
        if row.get('currency') == 'USD':
            row['loan_amount'] = convert_source_amount(row.get('loan_amount'),rate)
            row['source_currency'] = 'USD'
            row['currency'] = 'INR'
        elif row.get('currency') not in (None,'INR'):
            row['source_currency'] = row['currency']
            row['loan_amount'] = None
            row['currency'] = 'INR'
            row['conversion_status'] = 'rate_missing'
        row.setdefault('source_type','research')
    result['display_currency'] = 'INR'
    return result


def household_summary_inr(summary):
    result = deepcopy(summary)
    if result.get('display_currency')=='INR' and result.get('fx'):
        return result
    result['fx'] = get_fx()
    rate = result['fx']['usd_to_inr']
    result['display_currency'] = 'INR'
    for group in result.get('currency_groups', []):
        original = group.get('currency')
        group['source_currency'] = original
        group['currency'] = 'INR'
        group['income_unit'] = 'INR per month'
        if original == 'INR':
            group['conversion_status'] = 'native'
            continue
        for metric in ('household_income', 'per_capita_household_income', 'business_income'):
            for key in ('mean_baseline','mean_followup','mean_change','median_change'):
                if key in group.get(metric, {}):
                    group[metric][key] = convert_source_amount(group[metric][key],rate) if original == 'USD' else None
        group['conversion_status'] = 'converted' if original == 'USD' else 'rate_missing'
        group['conversion_note'] = ('Amounts converted using the disclosed reference snapshot; source-currency cohorts stay separate.' if original == 'USD' else 'No reference rate is configured for this source currency; monetary results are withheld until one is provided.')
    return result
