"""Lightweight validated settings for the academic demonstration policy."""
import math
import os


def load_policy():
    """Policy settings are configurable by the operator, never inferred from data."""
    try:
        rate = float(os.environ.get('PP1_DEMO_ANNUAL_RATE', '.12'))
        months = int(os.environ.get('PP1_DEMO_TERM_MONTHS', '12'))
        min_months = int(os.environ.get('PP1_DEMO_MIN_TERM_MONTHS', '1'))
        max_months = int(os.environ.get('PP1_DEMO_MAX_TERM_MONTHS', '360'))
        ratio = float(os.environ.get('PP1_DEMO_MAX_DEBT_RATIO', '.40'))
    except (ValueError,TypeError,OverflowError) as exc:
        raise RuntimeError('Demonstration policy configuration is invalid.') from exc
    if not math.isfinite(rate) or not 0 <= rate <= 1 or not 1 <= min_months <= months <= max_months <= 360 or not math.isfinite(ratio) or not 0 < ratio <= 1:
        raise RuntimeError('Invalid demonstration policy: rate must be 0–1, months 1–360, and debt ratio greater than 0 and at most 1.')
    return {'id': 'configurable-demo-v1', 'annual_rate': rate, 'term_months': months,
            'default_term_months': months, 'min_term_months': min_months, 'max_term_months': max_months,
            'max_total_debt_ratio': ratio, 'currency': 'INR',
            'source': 'Operator-configured academic demonstration policy; no lender policy supplied',
            'description': f'Illustrative {rate*100:g}% annual nominal interest, {months} monthly installments, and total monthly debt installments at most {ratio*100:g}% of declared monthly income.',
            'limitations': 'Excludes fees, insurance, penalties and unreported expenses. A lender must verify income, obligations, product rules and documents. No approval or risk probability is produced.'}
