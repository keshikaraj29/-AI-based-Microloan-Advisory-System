"""Category-scoped research views, kept distinct from owned applications."""
from copy import deepcopy
from collections import Counter
from functools import lru_cache
import json
import math
from currency_tools import research_summary_inr, research_page_inr
from data_store import get_store
from research_analytics import get_research_summary, query_loans


def summary_for_category(purpose=None):
    summary = deepcopy(get_research_summary())
    if not purpose:
        return research_summary_inr(summary)
    if purpose not in summary.get('filters', {}).get('purposes', []):
        raise ValueError('Choose a category present in the supplied data.')
    with get_store().pool.connection() as conn:
        rows = [dict(r) for r in conn.execute("SELECT loan_amount,term_months,interest_rate,annual_income,dti,loan_status,cluster_id,sentiment_label,sentiment_score,topic_id,state,LENGTH(TRIM(COALESCE(description,''))) AS description_length FROM loans WHERE purpose=?",(purpose,))]
    if any(r['cluster_id'] is None for r in rows):
        raise RuntimeError('Research model assignments are being prepared. Retry after preparation completes.')
    resolved_statuses = {'Fully Paid','Charged Off','Does not meet the credit policy. Status:Fully Paid','Does not meet the credit policy. Status:Charged Off'}
    def resolved(rs):
        return [r for r in rs if r['loan_status'] in resolved_statuses]
    def paid_rate(rs):
        chosen = resolved(rs)
        return sum(r['loan_status'].endswith('Fully Paid') for r in chosen)/len(chosen) if chosen else None
    def mean(rs, name):
        vals = [r[name] for r in rs if r[name] is not None]
        return sum(vals)/len(vals) if vals else None
    def groups(field):
        return [(v,[r for r in rows if r[field] == v]) for v in sorted({r[field] for r in rows}, key=str)]
    summary['scope'] = {'purpose':purpose,'label':purpose.replace('_',' ').title(),'model_scope':'Global corpus model; cohort outcomes are recalculated for this category.'}
    summary['dataset']['full_sample_records'] = summary['dataset']['records']
    summary['dataset']['records'] = len(rows)
    summary['dataset']['narratives'] = sum(r['sentiment_label'] != 'unavailable' for r in rows)
    summary['dataset']['nonempty_descriptions'] = sum(r['description_length']>0 for r in rows)
    summary['dataset']['source_count_scope'] = 'Full supplied archive; source_records and source_narratives are not category-filtered.'
    summary['dataset']['table_count_scope'] = 'Physical source tables before filtering. The records field is the selected category count.'
    summary['metrics']['repayment_rate'] = paid_rate(rows)
    summary['metrics']['resolved_count'] = len(resolved(rows))
    summary['metrics']['unresolved_count'] = len(rows)-len(resolved(rows))
    # Model validation pertains to the global fitted model, not a re-fit on the filter.
    summary['metrics']['model_scope'] = 'Global fitted model; not re-estimated for this category'
    summary['clusters'] = [dict(id=v,label=f'Segment {v+1}',count=len(rs),resolved_count=len(resolved(rs)),repayment_rate=paid_rate(rs),mean_loan_amount=mean(rs,'loan_amount'),mean_annual_income=mean(rs,'annual_income'),mean_interest_rate=mean(rs,'interest_rate'),mean_dti=mean(rs,'dti'),mean_term_months=mean(rs,'term_months'),income_change_pct=None) for v,rs in groups('cluster_id')]
    summary['metrics']['cohort_cluster_count'] = len(summary['clusters'])
    summary['loan_structures'] = [dict(term_months=v,count=len(rs),resolved_count=len(resolved(rs)),repayment_rate=paid_rate(rs),mean_interest_rate=mean(rs,'interest_rate'),mean_loan_amount=mean(rs,'loan_amount')) for v,rs in groups('term_months')]
    summary['sentiment'] = [dict(label=v,count=len(rs),resolved_count=len(resolved(rs)),repayment_rate=paid_rate(rs)) for v,rs in groups('sentiment_label') if v != 'unavailable']
    summary['regions'] = [dict(state=v,count=len(rs),resolved_count=len(resolved(rs)),repayment_rate=paid_rate(rs)) for v,rs in groups('state')]
    topics_by_id = {t['id']:t for t in summary['topics']}
    summary['topics'] = [dict(topics_by_id[v],count=len(rs),resolved_count=len(resolved(rs)),repayment_rate=paid_rate(rs)) for v,rs in groups('topic_id') if v in topics_by_id]
    correlations=[]
    for feature in ('loan_amount','annual_income','interest_rate','dti','term_months','sentiment_score'):
        pairs=[(r[feature],float(r['loan_status'].endswith('Fully Paid'))) for r in resolved(rows) if r[feature] is not None]
        corr=None
        if len(pairs)>2:
            xs,ys=zip(*pairs); mx=sum(xs)/len(xs); my=sum(ys)/len(ys)
            denominator=math.sqrt(sum((x-mx)**2 for x in xs)*sum((y-my)**2 for y in ys))
            if denominator: corr=sum((x-mx)*(y-my) for x,y in pairs)/denominator
        correlations.append(dict(feature=feature,outcome='fully_paid_among_resolved',correlation=corr,n=len(pairs)))
    summary['correlations']=correlations
    summary['status_counts'] = dict(Counter(r['loan_status'] for r in rows))
    summary['purpose_comparisons'] = [{'purpose':purpose,'count':len(rows),'resolved_count':len(resolved(rows)),'repayment_rate':paid_rate(rows)}]
    summary['methods']['cohort_definition'] = f'Exact purpose={purpose} within the original uniform sample; no resampling or model refitting.'
    summary['methods']['cluster_selection'] += ' These validation scores and preprocessing parameters describe the global model, not a model refitted to the selected category.'
    summary['insights']=[f"Showing {len(rows):,} {purpose.replace('_',' ')} records within the prepared sample. Category outcomes are recomputed from those records.", 'These historical consumer-loan records provide category context. They do not predict this applicant’s business income or establish a bank offer.']
    return research_summary_inr(summary)


def research_page(**kwargs):
    return research_page_inr(query_loans(**kwargs))


CONTEXT_COLUMNS = {
 'market': [('id','Record','number'),('district','District','text'),('market','Market','text'),
            ('commodity','Commodity','text'),('state','State','text'),('modal_price','Modal price (INR/quintal)','money'),('price_date','Price date','text')],
 'dairy': [('id','Record','number'),('location','Location','text'),('product','Product','text'),('date','Transaction date','text'),
           ('quantity','Quantity (litres/kg)','number'),('unit_price','Price per unit (INR)','money'),
           ('quantity_sold','Quantity sold (litres/kg)','number'),('sold_unit_price','Sale price per unit (INR)','money'),
           ('revenue','Approximate revenue (INR)','money'),('storage','Storage condition','text')],
 'farm': [('id','Record','number'),('location','Location','text'),('crop','Crop','text'),('season','Season','text'),
          ('year','Year','number'),('area','Area (source units)','number'),('yield','Yield (source units)','number'),
          ('rainfall','Rainfall (source units)','number'),('temperature','Temperature (source units)','number'),
          ('soil_type','Soil type','text'),('irrigation','Irrigation','text')]
}


@lru_cache(maxsize=24)
def _context_values(database_path,version,table,column):
    # Only two small CSV context tables reach here. Resolve stored spelling
    # once, then use equality against the existing composite B-tree indexes.
    with get_store().pool.connection() as conn:
        values = [r[0] for r in conn.execute(f'SELECT DISTINCT {column} FROM {table}') if r[0] is not None]
    mapping = {}
    for value in values:
        mapping.setdefault(str(value).strip().casefold(),[]).append(value)
    return mapping


def _finite_number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError,TypeError):
        return None


def context_records(source='dairy',page=1,per_page=20,product=None,location=None):
    """Bounded, typed public business-context records from the supplied files.

    Product/location filters are exact, case-insensitive matches. No broader
    regional fallback is applied here; callers must label such a query clearly.
    The farm source's unverified price and unit assumptions are not exported.
    """
    if source not in CONTEXT_COLUMNS:
        raise ValueError('Choose dairy, farm or market as the context source.')
    try:
        page,size = int(page),int(per_page)
        if not 1<=page<=10000 or not 1<=size<=100:
            raise ValueError
    except (TypeError,ValueError,OverflowError) as exc:
        raise ValueError('Use a page from 1 to 10000 and per_page from 1 to 100.') from exc
    product = str(product or '').strip().casefold()
    location = str(location or '').strip().casefold()
    if len(product)>150 or len(location)>150:
        raise ValueError('Product and location filters must each have at most 150 characters.')
    store = get_store()
    params,clauses = [],[]
    if source=='market':
        table = 'market_prices'
        if location:
            alternatives = []
            for key in ('district_key','market_key','state_key'):
                alternatives.append(f'SELECT id FROM market_prices WHERE {key}=?' + (' AND commodity_key=?' if product else ''))
                params.append(location)
                if product:
                    params.append(product)
            clauses.append('id IN ('+' UNION '.join(alternatives)+')')
        elif product:
            clauses.append('commodity_key=?')
            params.append(product)
        select = 'id,district,market,commodity,state,modal_price,price_date'
    else:
        table = 'dairy_records' if source=='dairy' else 'farm_records'
        product_column = 'product' if source=='dairy' else 'crop'
        for column,requested in ((product_column,product),('location',location)):
            if requested:
                values = _context_values(str(store.path.resolve()),store._version(),table,column).get(requested,[])
                if not values:
                    clauses.append('0')
                else:
                    clauses.append(column+' IN ('+','.join('?' for _ in values)+')')
                    params.extend(values)
        select = '*'
    where = (' WHERE '+' AND '.join(clauses)) if clauses else ''
    with store.pool.connection() as conn:
        conn.execute('BEGIN')
        try:
            total = conn.execute('SELECT COUNT(*) FROM '+table+where,params).fetchone()[0]
            rows = conn.execute('SELECT '+select+' FROM '+table+where+' ORDER BY id LIMIT ? OFFSET ?',
                                params+[size,(page-1)*size]).fetchall()
        finally:
            conn.rollback()
    items = []
    for row in rows:
        if source=='market':
            item = dict(row)
        else:
            raw = json.loads(row['row_json'])
            if source=='dairy':
                item = {'id':row['id'],'location':row['location'],'product':row['product'],
                    'date':raw.get('Date'),'quantity':_finite_number(raw.get('Quantity (liters/kg)')),
                    'unit_price':_finite_number(raw.get('Price per Unit')),
                    'quantity_sold':_finite_number(raw.get('Quantity Sold (liters/kg)')),
                    'sold_unit_price':_finite_number(raw.get('Price per Unit (sold)')),
                    'revenue':_finite_number(raw.get('Approx. Total Revenue(INR)')),'storage':raw.get('Storage Condition')}
            else:
                item = {'id':row['id'],'location':row['location'],'crop':row['crop'],'season':row['season'],
                    'year':_finite_number(raw.get('Year')),'area':_finite_number(raw.get('Area')),
                    'yield':_finite_number(raw.get('yeilds')),'rainfall':_finite_number(raw.get('Rainfall')),
                    'temperature':_finite_number(raw.get('Temperature')),'soil_type':raw.get('Soil type'),'irrigation':raw.get('Irrigation')}
        items.append(item)
    note = {'market':'Observed wholesale modal prices in INR per quintal from the supplied historical workbook.',
            'dairy':'Source amounts are INR per product unit; quantities retain the source litres/kg convention. Records are transactions, not borrower outcomes.',
            'farm':'Source agricultural units have not been independently verified. The price column is omitted; no invented unit conversion is applied.'}[source]
    return {'source':source,'source_type':'business_context','currency':'INR','items':items,
        'columns':[{'key':key,'label':label,'kind':kind} for key,label,kind in CONTEXT_COLUMNS[source]],
        'page':page,'page_size':size,'per_page':size,'total':total,'count':total,'pages':math.ceil(total/size),
        'filters':{'product':product or None,'location':location or None,'matching':'Exact, case-insensitive; no automatic regional fallback'},'note':note}
