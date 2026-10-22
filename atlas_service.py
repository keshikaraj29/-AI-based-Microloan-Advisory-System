"""Local Atlas guidance with owned-application context and safe navigation actions."""
from urllib.parse import urlencode
import re
from currency_tools import format_inr, get_fx
from research_service import summary_for_category


def action(label,url):
    return {'label':label,'url':url}


def answer(message,application=None):
    text=message.casefold()
    result=application['result'] if application else None
    identifier=application['id'] if application else None
    purpose=(result.get('category') or {}).get('purpose') if result else None
    if purpose == 'unknown':
        purpose = None
    research='/research'+('?' + urlencode({'application_id':identifier,'purpose':purpose}) if identifier else '')
    links=[action('Start an application','/apply'),action('My applications','/applications'),action('Explore research',research)]
    if identifier:
        links=[action('Explain this assessment',f'/applications/{identifier}/explanation'),action('Track this loan',f'/applications/{identifier}'),action('Explore the same category',research)]
    source='Atlas application guide'
    if any(word in text for word in ('agmarknet','farm data','dairy data','business dataset','milk data','market prices')):
        return {'reply':'Open Business datasets to browse the supplied dairy, farm and market records. Select the source, then optionally filter by exact product/crop and locality. Prices are historical context, with their source units shown; they do not establish your future sales or profit. Your assessment explanation shows whether the match is at city or state level.','source':'Supplied business data catalog','actions':[action('Browse business datasets',research+'#business-data'),*links[:1]]}
    if re.search(r'\b(?:repayment|paid|default)\s+rate\b', text) and any(word in text for word in ('data','research','corpus','historical')):
        summary=summary_for_category(purpose)
        metrics=summary['metrics']; rate=metrics['repayment_rate']
        displayed=f"{rate*100:.2f}%" if rate is not None else 'not available'
        return {'reply':f"The historical fully-paid rate is {displayed} among {metrics['resolved_count']:,} resolved loans in this research cohort. Unresolved loans are excluded. This is an observed corpus statistic and does not predict whether a particular applicant will repay.",'source':'Observed research outcomes','actions':[action('Compare loan outcomes',research+'#outcomes')]}
    if any(word in text for word in ('cluster','segment','group')):
        summary=summary_for_category(purpose)
        m=summary['metrics']
        return {'reply':f"The prepared corpus has {m['cluster_count']} K-means groups. Its silhouette is {m['silhouette_score']:.3f}; Davies–Bouldin is {m['davies_bouldin_score']:.3f}. Groups use loan amount, annual income, interest rate, debt-to-income ratio and term. Repayment is compared after grouping. Your application’s category links to relevant records; it is not silently assigned a source-population credit score.",'source':'Prepared clustering methodology','actions':[action('Borrower groups',research+'#clusters'),*links[:1]]}
    if result and re.search(r'\b(?:sentiment|tone|wording)\b',text):
        sentiment=result.get('sentiment')
        if not sentiment:
            from narrative_sentiment import analyze_narrative
            sentiment=analyze_narrative(result.get('business_description',''))
        return {'reply':f"Your narrative is labeled {sentiment['label'].capitalize()}. {sentiment['explanation']} Sentiment describes wording and does not change the loan's interest rate or review outcome.",'source':sentiment['method'],'actions':[action('Read your narrative',f'/applications/{identifier}/assessment#application-narrative'),action('Explore narrative research',research+'#topics')]}
    if any(word in text for word in ('topic','nlp','narrative','sentiment')):
        return {'reply':'Corpus topics use TF-IDF text features and non-negative matrix factorization on eligible borrower narratives. Sentiment uses a disclosed word lexicon with negation handling. The application explanation separately shows words and phrases extracted from your story, the category they matched, and the data used. Sentiment does not set the interest rate or decide eligibility.','source':'NLP methodology','actions':[action('Narrative topics',research+'#topics'),*links[:1]]}
    if any(word in text for word in ('repayment','repaying','repayments','payment','overdue','tracking','csv')):
        reply='Open My applications, choose a saved record, and record the date of an actual disbursement to activate its schedule. Then log payments by amount, date and a unique reference, or import the payment CSV. The ledger allocates payments to installments and shows due, partial, overdue and paid entries. It reflects recorded payments; it does not read bank accounts or verify bank settlement automatically.'
        if application:
            ledger=application.get('ledger',{})
            reply+=f" This record’s status is {ledger.get('status','not started')}. Recorded outstanding: {format_inr(ledger.get('outstanding'))}; overdue: {format_inr(ledger.get('overdue_amount'))}."
        return {'reply':reply,'source':'Recorded repayment ledger','actions':links}
    if any(word in text for word in ('reject','approv','eligible','eligibility','accept','decision')):
        reply='The configurable demo policy checks the requested amount and term, missing information, monthly income, existing installment commitments and proposed EMI. It returns Ready for review, Needs information, or Affordability concern with a rule-by-rule explanation. A real lender must decide approval and its final terms; the application does not guarantee acceptance or issue a bank rejection.'
        if result:
            reply+=f" Your saved result: {result.get('status_label',result.get('status'))}. " + ' '.join(str(r.get('explanation','')) for r in result.get('rule_trace',[]) if r.get('status') != 'pass')
        return {'reply':reply,'source':'Configured demo lending policy','actions':links}
    if re.search(r'\b(?:interest|intrest|rates?|emi|installments?|instalments?)\b', text):
        if application and application.get('ledger',{}).get('tracking_started'):
            ledger=application['ledger'];estimate=result.get('loan_terms',{})
            reply=f"Your recorded agreement uses {ledger['annual_rate']*100:.2f}% annual interest over {ledger['term_months']} months on {format_inr(ledger['principal'])}. The original assessment estimated {estimate['annual_rate']*100:.2f}%. Agreement terms are entered by you and are not bank-verified; the payment tracker uses those recorded terms. Open the tracker for the dated installment schedule."
        elif result:
            terms=result.get('loan_terms',{})
            rate=terms.get('annual_rate')
            reply=f"This saved assessment estimates an annual interest rate of {rate*100:.2f}%" if rate is not None else 'A rate estimate is not available for this record yet.'
            reply+=f" and an EMI of {format_inr(terms.get('emi'))} over {terms.get('months','an unspecified number of')} months. The rate comes from the disclosed demo policy, not from an invented business forecast or a guaranteed bank offer. Open its explanation to inspect every input and rule."
        else:
            from policy_config import load_policy
            policy=load_policy()
            reply=f"The current configurable demo policy uses {policy['annual_rate']*100:.2f}% annual interest and a default term of {policy['term_months']} months when you do not specify a term. Enter your requested amount and term to calculate EMI and total repayment. Income and existing monthly debt are needed for the affordability check. This is a demonstration estimate requiring lender review. At zero interest EMI is principal divided by months; otherwise it uses reducing-balance amortization."
        return {'reply':reply,'source':'Repayment calculation and demo policy','actions':links}
    if any(word in text for word in ('growth','63000','63k','profit','revenue','income','generated','reason','why','explain result')):
        reply='The former milk-business illustration assumed a quantity, a unit price and operating costs. That could produce about ₹63,000 of annual surplus without knowing your business. This has been removed. The current assessment calculates annual revenue and operating surplus only from explicitly supplied monthly business sales and costs. A loan amount alone cannot establish either income or growth. Matched dataset prices are context and are never silently multiplied into a personal forecast.'
        if result:
            financials=result.get('financials',{})
            reply+=f" This record’s annual revenue: {format_inr(financials.get('annual_revenue'))}; annual operating surplus: {format_inr(financials.get('annual_operating_surplus'))}."
        return {'reply':reply,'source':'Assessment provenance','actions':links}
    if any(word in text for word in ('apply','application','hindi','ocr','fill','how to')):
        return {'reply':'Create an account or sign in, open Application, state the amount and term, describe the business or loan purpose, and enter monthly income and existing installment commitments. Business sales and costs are optional, but both are needed for a surplus calculation. For example, “I need a loan to open a milk business in Bengaluru of around 10000 rupees” identifies a dairy/small-business purpose and amount; it does not supply income forecasts. Your result, explanation, JSON and repayment tracker are saved under My applications.','source':source,'actions':links}
    if any(word in text for word in ('poverty','impact','sdg','causal','limitation')):
        return {'reply':'These data support loan-performance comparisons, category exploration and narrative analysis. They do not include linked household poverty measures and a comparison group, so they cannot prove poverty reduction. The household-outcome import accepts real baseline/follow-up observations and reports descriptive changes. Converted historical consumer-loan amounts remain source-population context, not Indian lending guarantees.','source':'Research limitations','actions':[action('Read methods and limitations',research+'#methods'),action('Household outcomes',research+'#household-impact')]}
    if any(word in text for word in ('rupee','currency','convert','exchange')):
        fx=get_fx()
        return {'reply':f"All displayed monetary figures are rupees. Foreign-source research loan amounts are converted with a fixed RBI reference snapshot of ₹{fx['usd_to_inr']:.4f} per source currency unit dated {fx['rate_date']}. It is a reproducible display conversion, not a live exchange quote. Application, dairy and Indian market values are already in rupees and are not converted twice.",'source':fx['source'],'actions':[action('View data provenance',research+'#methods')]}
    if any(word in text for word in ('data','dataset','source','explore','business','category','navigate','show','open','loan')):
        summary=summary_for_category(purpose)
        d=summary['dataset']
        return {'reply':f"Explore {d['records']:,} prepared records{' in your loan category' if purpose else ''}, with {d['narratives']:,} eligible narratives. Research covers every purpose in the supplied loan data, including small business, debt consolidation, education, medical, vehicle and home-related loans. Agriculture and dairy add separate business context. Choose a category in Research, or open Explore the same category from a saved assessment. All displayed amounts are rupees.",'source':'Prepared dataset catalog','actions':links}
    return {'reply':'I can guide you through applying, the proposed interest rate and EMI, missing inputs, review or affordability concerns, same-category research, the assessment explanation, and payment recording. Choose an action below, or ask a specific question.','source':source,'actions':links}
