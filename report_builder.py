"""Professional, paginated assessment PDF using only observed/declared figures."""
from __future__ import annotations

from datetime import datetime
from io import BytesIO
import math
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (BaseDocTemplate, Frame, KeepTogether, PageBreak,
                               PageTemplate, Paragraph, Spacer, Table, TableStyle)
from reportlab.graphics.shapes import Drawing, Line, Rect, String as _String
from reportlab.graphics.charts.doughnut import Doughnut

INK = colors.HexColor('#183E36')
MUTED = colors.HexColor('#536A64')
GREEN = colors.HexColor('#178069')
GOLD = colors.HexColor('#D6A95A')
PALE = colors.HexColor('#F0F5F1')
LINE = colors.HexColor('#D8E3DD')
RED = colors.HexColor('#A33D34')
WIDTH, HEIGHT = A4
CONTENT = WIDTH - 36*mm


def String(*args, **kwargs):
    kwargs.setdefault('fontName', 'Helvetica')
    return _String(*args, **kwargs)


def money(value):
    return 'Not provided' if value is None else f'INR {float(value):,.2f}'


def _text(value):
    text = str(value if value is not None else 'Not provided')
    text = text.replace('\u2011', '-').replace('\u2013', '-').replace('\u2014', '-')
    try:
        text.encode('cp1252')
    except UnicodeEncodeError:
        text = 'Original Unicode value is preserved in the application record / JSON.'
    return escape(text)


def _styles():
    base = getSampleStyleSheet()
    result = {
        'title': ParagraphStyle('ReportTitle', fontName='Helvetica-Bold', fontSize=25, leading=29, textColor=INK, spaceAfter=9),
        'h1': ParagraphStyle('SectionTitle', fontName='Helvetica-Bold', fontSize=16, leading=20, textColor=INK, spaceAfter=9),
        'h2': ParagraphStyle('SubTitle', fontName='Helvetica-Bold', fontSize=10.5, leading=14, textColor=INK, spaceBefore=8, spaceAfter=6),
        'body': ParagraphStyle('ReportBody', fontName='Helvetica', fontSize=9, leading=13, textColor=INK, spaceAfter=6),
        'small': ParagraphStyle('ReportSmall', fontName='Helvetica', fontSize=7.7, leading=10.7, textColor=MUTED, spaceAfter=5),
        'label': ParagraphStyle('ReportLabel', fontName='Helvetica-Bold', fontSize=7.7, leading=10.7, textColor=MUTED),
        'number': ParagraphStyle('ReportNumber', fontName='Helvetica-Bold', fontSize=17, leading=23, textColor=INK),
        'table': ParagraphStyle('ReportCell', fontName='Helvetica', fontSize=8, leading=11, textColor=INK),
        'tablehead': ParagraphStyle('ReportHead', fontName='Helvetica-Bold', fontSize=8, leading=11, textColor=colors.white),
    }
    return result


def _header_footer(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(INK)
    canvas.rect(0, HEIGHT-8*mm, WIDTH, 8*mm, fill=1, stroke=0)
    canvas.setFont('Helvetica-Bold', 9)
    canvas.drawString(18*mm, HEIGHT-17*mm, 'MICROLOAN ATLAS')
    canvas.setFillColor(MUTED)
    canvas.setFont('Helvetica', 7)
    canvas.drawRightString(WIDTH-18*mm, HEIGHT-17*mm, 'APPLICATION REVIEW | INR')
    canvas.setStrokeColor(LINE)
    canvas.line(18*mm, 18*mm, WIDTH-18*mm, 18*mm)
    canvas.setFont('Helvetica', 7)
    canvas.drawString(18*mm, 13*mm, 'Academic demonstration - human verification required')
    canvas.drawRightString(WIDTH-18*mm, 13*mm, f'Page {doc.page}')
    canvas.restoreState()


def _table(rows, widths, styles, header=True, row_split_range=None):
    formatted = [[Paragraph(_text(cell), styles['tablehead'] if header and idx == 0 else styles['table']) for cell in row] for idx, row in enumerate(rows)]
    table = Table(formatted, colWidths=widths, repeatRows=1 if header else 0, hAlign='LEFT', rowSplitRange=row_split_range)
    commands = [('VALIGN', (0,0),(-1,-1),'TOP'), ('LEFTPADDING',(0,0),(-1,-1),8),
                ('RIGHTPADDING',(0,0),(-1,-1),8), ('TOPPADDING',(0,0),(-1,-1),7),
                ('BOTTOMPADDING',(0,0),(-1,-1),7), ('LINEBELOW',(0,0),(-1,0),.6,LINE),
                ('ROWBACKGROUNDS',(0,1 if header else 0),(-1,-1),[colors.white,PALE])]
    if header:
        commands.append(('BACKGROUND',(0,0),(-1,0),INK))
    table.setStyle(TableStyle(commands))
    return table


def _metrics(items, styles):
    cells = []
    for label, value in items:
        cells.append([Paragraph(_text(label.upper()), styles['label']), Spacer(1,5), Paragraph(_text(value), styles['number'])])
    table = Table([cells], colWidths=[CONTENT/len(cells)]*len(cells))
    table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),PALE),('BOX',(0,0),(-1,-1),.5,LINE),
                              ('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),11),
                              ('TOPPADDING',(0,0),(-1,-1),10),('BOTTOMPADDING',(0,0),(-1,-1),10)]))
    return table


def _empty_chart(title, message, width=CONTENT, height=145):
    drawing = Drawing(width,height)
    drawing.add(Rect(0,0,width,height,fillColor=PALE,strokeColor=LINE))
    drawing.add(String(12,height-24,title,fontName='Helvetica-Bold',fontSize=10,fillColor=INK))
    drawing.add(String(12,height-53,message,fontSize=8,fillColor=MUTED))
    return drawing


def _repayment_donut(terms, width=235, height=172):
    if terms.get('principal') is None:
        return _empty_chart('Repayment composition','Requested principal is missing.',width,height)
    drawing = Drawing(width,height)
    drawing.add(String(0,height-10,'Scheduled repayment composition',fontName='Helvetica-Bold',fontSize=10,fillColor=INK))
    donut = Doughnut()
    donut.x, donut.y, donut.width, donut.height = 3, 39, 111, 111
    principal, interest = terms['principal'], terms['total_interest']
    donut.data = [principal, max(interest,0)]
    donut.slices[0].fillColor = GREEN
    donut.slices[1].fillColor = GOLD
    donut.slices.strokeColor = colors.white
    donut.labels = None
    donut.innerRadiusFraction = .7
    drawing.add(donut)
    drawing.add(String(123,117,'PRINCIPAL',fontName='Helvetica-Bold',fontSize=7,fillColor=MUTED))
    drawing.add(String(123,101,money(principal),fontName='Helvetica-Bold',fontSize=10,fillColor=INK))
    drawing.add(String(123,76,'INTEREST',fontName='Helvetica-Bold',fontSize=7,fillColor=GOLD))
    drawing.add(String(123,60,money(interest),fontName='Helvetica-Bold',fontSize=10,fillColor=INK))
    drawing.add(String(0,12,'No fees or insurance are included.',fontSize=7.5,fillColor=MUTED))
    return drawing


def _balance_chart(terms, width=235, height=172):
    schedule = terms.get('schedule') or []
    if not schedule:
        return _empty_chart('Scheduled balance','A principal is needed to build a schedule.',width,height)
    drawing = Drawing(width,height)
    drawing.add(String(0,height-10,'Scheduled outstanding principal',fontName='Helvetica-Bold',fontSize=10,fillColor=INK))
    x0,y0,w,h = 35,35,width-43,105
    principal = terms['principal']
    points = [principal]+[row['Balance'] for row in schedule]
    drawing.add(Line(x0,y0,x0+w,y0,strokeColor=LINE))
    drawing.add(Line(x0,y0,x0,y0+h,strokeColor=LINE))
    for fraction in (0,.5,1):
        drawing.add(Line(x0,y0+h*fraction,x0+w,y0+h*fraction,strokeColor=LINE,strokeWidth=.4))
        number = principal*fraction
        label = f'{number/1000:g}k' if number>=1000 else f'{number:g}'
        drawing.add(String(x0-6,y0+h*fraction-3,label,textAnchor='end',fontSize=7,fillColor=MUTED))
    for i in range(1,len(points)):
        drawing.add(Line(x0+w*(i-1)/(len(points)-1),y0+h*points[i-1]/principal,
                         x0+w*i/(len(points)-1),y0+h*points[i]/principal,strokeColor=GREEN,strokeWidth=2))
    drawing.add(String(x0,y0-13,'0',fontSize=7,fillColor=MUTED))
    drawing.add(String(x0+w,y0-13,str(len(schedule)),textAnchor='end',fontSize=7,fillColor=MUTED))
    drawing.add(String(x0+w/2,5,'Installment month | INR',textAnchor='middle',fontSize=7.5,fillColor=MUTED))
    return drawing


def _burden_chart(financials, terms, width=CONTENT, height=120):
    income, debt, emi = financials.get('monthly_income'), financials.get('existing_monthly_debt'), terms.get('emi')
    if income is None or debt is None or emi is None:
        return _empty_chart('Monthly income and installments','Income or installment information is missing.',width,height)
    drawing = Drawing(width,height)
    drawing.add(String(0,height-10,'Declared monthly income and debt installments',fontName='Helvetica-Bold',fontSize=10,fillColor=INK))
    maximum = max(income, debt+emi,1)
    rows = [('Declared income',income,GREEN),('Existing installments',debt,MUTED),('New installment',emi,GOLD)]
    for idx,(label,value,color) in enumerate(rows):
        y = height-40-idx*27
        drawing.add(String(0,y+3,label,fontSize=8,fillColor=MUTED))
        drawing.add(Rect(122,y,width-235,14,fillColor=PALE,strokeColor=None))
        drawing.add(Rect(122,y,(width-235)*value/maximum,14,fillColor=color,strokeColor=None))
        drawing.add(String(width,y+3,money(value),textAnchor='end',fontSize=8,fillColor=INK))
    return drawing


def create_assessment_pdf(result, path):
    """Write a report with natural pagination and no inferred business growth."""
    styles = _styles()
    p = lambda text, style='body': Paragraph(_text(text), styles[style])
    terms, financials = result['loan_terms'], result['financials']
    policy = result['policy_snapshot']
    applicant = result['applicant_copy']
    story = [p('Application assessment', 'title'),
             p(f"Prepared {datetime.now().strftime('%d %b %Y, %H:%M')} | {result['category']['label']}", 'small'),
             p(result['status_label'], 'h1')]
    if result.get('example_note'):
        story.append(p(result['example_note'], 'small'))
    name = str(applicant.get('Applicant Name') or 'Applicant')
    if not name.isascii():
        # Standard PDF fonts do not shape arbitrary scripts; avoid broken glyphs.
        name = 'Name preserved in the application record / JSON'
    story += [p(f'Applicant: {name}'), p('This report supports human review. It is not a lending approval, credit-risk probability or prediction of business growth.', 'small'),
              Spacer(1,7), _metrics([('Requested principal',money(terms['principal'])),('Monthly installment',money(terms['emi'])),('Repayment term',f"{terms['term_months']} months")],styles),Spacer(1,14)]
    if result.get('missing_information'):
        story += [p('Information required', 'h2')]
        story += [p(f'- {item}') for item in result['missing_information']]
    if result.get('concerns'):
        story += [p('Concerns to resolve', 'h2')]+[p(f'- {item}') for item in result['concerns']]
    if not result.get('missing_information') and not result.get('concerns'):
        story.append(p('The declared inputs meet the configured demonstration checks. A lender still needs to verify supporting records, living expenses and its own policy.'))
    story += [Spacer(1,9), Table([[_repayment_donut(terms,CONTENT/2-8),_balance_chart(terms,CONTENT/2-8)]],colWidths=[CONTENT/2]*2),
              Spacer(1,6), p(f"Total scheduled repayment: {money(terms['total_repayment'])}. Interest: {policy['annual_rate']*100:g}% annual nominal under the demonstration policy.",'small'),
              PageBreak(), p('Financial basis and policy','title'),p('Every calculation starts with an explicit declaration. Missing figures remain unavailable.'),
              _table([['Financial input or calculation','Amount / value'],
                      ['Declared monthly household income',money(financials['monthly_income'])],
                      ['Existing monthly debt installments',money(financials['existing_monthly_debt'])],
                      ['Monthly business revenue',money(financials['monthly_business_revenue'])],
                      ['Monthly business operating costs',money(financials['monthly_business_costs'])],
                      ['Annualized business revenue',money(financials['annual_revenue'])],
                      ['Annualized operating surplus',money(financials['annual_operating_surplus'])],
                      ['Annualized surplus less new-loan installments in the first year',money(financials['annual_cash_after_debt_service'])]],
                     [CONTENT*.60,CONTENT*.40],styles), Spacer(1,12), _burden_chart(financials,terms),
              p('Configured demonstration policy','h2'),p(policy['description']),p(policy['source'],'small'),p(policy['limitations'],'small'),
              p('Business figures are annualized only when both monthly revenue and operating costs were explicitly supplied. Annualization is multiplication by 12; it is not a forecast of growth.','small'),
              PageBreak(),p('Rule trace and source evidence','title'),p('The explanations below show exactly why the review status was produced.')]
    for trace in result.get('rule_trace',[]):
        block = [p(f"{trace['label']} | {trace['status'].replace('_',' ').upper()}",'h2'),p(trace['explanation'])]
        story.append(KeepTogether(block))
    story += [Spacer(1,8),p('Relevant dataset context','h1')]
    for context in result.get('dataset_context',[]):
        block=[p(context['source'],'h2'),p(f"{context.get('record_count',0):,} matched records | {context.get('match_scope','Scope not supplied')}",'small'),
               p(context.get('description',''))]
        if context.get('median_price') is not None:
            block.append(p(f"Historical source median: {money(context['median_price'])}. Unit: {context.get('price_unit')}. This value was not used to invent sales or profit.",'small'))
        if context.get('latest_date'):
            block.append(p(f"Latest matched source date: {context['latest_date']}",'small'))
        story.append(KeepTogether(block))
    story += [PageBreak(),p('Declared inputs and provenance','title'),
              p('User-entered values take precedence over narrative extraction. The original category remains in the application record. No inferred field is a verified fact.'),
              _table([['Field','Value','Origin']]+[[item['label'],money(item['value']) if item['field'] in {'loan_amount','monthly_income','existing_monthly_debt','monthly_business_revenue','monthly_business_costs'} else item['value'],item['source'].replace('_',' ')] for item in result['input_provenance']],
                     [CONTENT*.36,CONTENT*.34,CONTENT*.30],styles),Spacer(1,13),p('Interpretation limits','h1')]
    story += [p(f'- {item}') for item in result['limitations']]
    if not str(applicant.get('Applicant Name') or '').isascii():
        story.append(p('The original Unicode applicant name is preserved in the application record and JSON. This PDF uses a reference message to avoid unsupported standard-font glyphs.','small'))
    story += [PageBreak(),p('Scheduled installments','title'),p('This is a prospective amortization schedule. It is not a record of payments received. Final installment rounding reconciles principal to zero.')]
    if terms['schedule']:
        schedule_rows = [['Month','Payment (INR)','Principal (INR)','Interest (INR)','Balance (INR)']]
        for row in terms['schedule']:
            schedule_rows.append([str(row['Month'])]+[f"{row[field]:,.2f}" for field in ('EMI','Principal','Interest','Balance')])
        schedule_rows.append(['Total',f"{terms['total_repayment']:,.2f}",f"{terms['principal']:,.2f}",f"{terms['total_interest']:,.2f}",'0.00'])
        table = _table(schedule_rows,[CONTENT*.10,CONTENT*.23,CONTENT*.23,CONTENT*.21,CONTENT*.23],styles,
                       row_split_range=(3,-3) if len(schedule_rows)>6 else None)
        if len(terms['schedule'])>18:
            table.setStyle(TableStyle([('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]))
        table.setStyle(TableStyle([('LINEABOVE',(0,-1),(-1,-1),.8,INK)]))
        story.append(table)
    else:
        story.append(p('No schedule can be produced until a positive requested principal is supplied.'))
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc=BaseDocTemplate(str(path),pagesize=A4,title='Microloan Atlas - Application Assessment',author='Microloan Atlas',
                        leftMargin=18*mm,rightMargin=18*mm,topMargin=27*mm,bottomMargin=24*mm)
    frame=Frame(doc.leftMargin,doc.bottomMargin,doc.width,doc.height,id='body',leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0)
    doc.addPageTemplates(PageTemplate(id='assessment',frames=[frame],onPage=_header_footer))
    doc.build(story)
    return path
