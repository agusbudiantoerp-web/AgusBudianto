from io import BytesIO
from datetime import date
from docx import Document
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
import pandas as pd

def _f(x, digits=2):
    try: return 'N/A' if pd.isna(x) else f'{float(x):,.{digits}f}'
    except Exception: return str(x)

def make_docx(company, summary, dcf, lbo, quality, assumptions, notes=''):
    d=Document(); d.add_heading('PE/VC Investment Analysis Report',0)
    d.add_paragraph(f'Company / Deal: {company}'); d.add_paragraph(f'Generated: {date.today().isoformat()}')
    d.add_heading('1. Executive Summary',1)
    d.add_paragraph(f"Status: {summary['status']}. DCF enterprise value: {_f(dcf['enterprise_value'])}; equity value: {_f(dcf['equity_value'])}. LBO MOIC: {_f(lbo['moic'])}x; annualized IRR: {_f(lbo['irr']*100)}%.")
    d.add_paragraph('Outputs are based on entered assumptions and are not an investment recommendation. Validate data and model logic before use.')
    d.add_heading('2. DCF Valuation',1); d.add_paragraph(f"WACC: {_f(assumptions['wacc']*100)}%; terminal growth: {_f(assumptions['terminal_growth']*100)}%; net debt: {_f(dcf['net_debt'])}.")
    d.add_paragraph(f"Enterprise value: {_f(dcf['enterprise_value'])}; equity value: {_f(dcf['equity_value'])}; terminal value: {_f(dcf['terminal_value'])}.")
    d.add_heading('3. LBO Returns',1); d.add_paragraph(f"Entry EV: {_f(lbo['entry_ev'])}; initial equity: {_f(lbo['initial_equity'])}; exit EV: {_f(lbo['exit_ev'])}; MOIC: {_f(lbo['moic'])}x; IRR: {_f(lbo['irr']*100)}%.")
    d.add_heading('4. Data Quality Checks',1); t=d.add_table(rows=1,cols=4); t.style='Light Shading Accent 1'
    for i,h in enumerate(['Check','Status','Severity','Detail']): t.rows[0].cells[i].text=h
    for _,r in quality.iterrows():
        cells=t.add_row().cells
        for i,k in enumerate(['Check','Status','Severity','Detail']): cells[i].text=str(r.get(k,''))
    d.add_heading('5. Analyst Notes / Open Items',1); d.add_paragraph(notes or 'Complete due diligence and document unresolved assumptions.')
    d.add_heading('Disclaimer',1); d.add_paragraph('Decision-support draft only. It does not verify source data and must be independently reviewed.')
    b=BytesIO(); d.save(b); return b.getvalue()

def make_pdf(company, summary, dcf, lbo, quality, assumptions, notes=''):
    b=BytesIO(); doc=SimpleDocTemplate(b,pagesize=A4); st=getSampleStyleSheet()
    story=[Paragraph('PE/VC Investment Analysis Report',st['Title']),Spacer(1,10),Paragraph(f'Company / Deal: {company}',st['Normal']),Paragraph(f'Generated: {date.today().isoformat()}',st['Normal']),Spacer(1,12),Paragraph('Executive Summary',st['Heading2']),Paragraph(f"Status: {summary['status']}. DCF EV: {_f(dcf['enterprise_value'])}; equity value: {_f(dcf['equity_value'])}; LBO MOIC: {_f(lbo['moic'])}x; IRR: {_f(lbo['irr']*100)}%.",st['BodyText']),Spacer(1,10),Paragraph('Data Quality Checks',st['Heading2'])]
    data=[['Check','Status','Severity','Detail']]+[[str(r[k])[:150] for k in ['Check','Status','Severity','Detail']] for _,r in quality.iterrows()]
    t=Table(data,repeatRows=1,colWidths=[115,50,50,300]); t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#1F4E78')),('TEXTCOLOR',(0,0),(-1,0),colors.white),('GRID',(0,0),(-1,-1),.4,colors.grey),('FONTSIZE',(0,0),(-1,-1),7),('VALIGN',(0,0),(-1,-1),'TOP')]))
    story += [t,Spacer(1,12),Paragraph('Valuation and Returns',st['Heading2']),Paragraph(f"WACC: {_f(assumptions['wacc']*100)}%; terminal growth: {_f(assumptions['terminal_growth']*100)}%; net debt: {_f(dcf['net_debt'])}.",st['BodyText']),Paragraph(f"Entry EV: {_f(lbo['entry_ev'])}; exit EV: {_f(lbo['exit_ev'])}; MOIC: {_f(lbo['moic'])}x; IRR: {_f(lbo['irr']*100)}%.",st['BodyText']),Spacer(1,10),Paragraph('Analyst Notes / Open Items',st['Heading2']),Paragraph((notes or 'Complete due diligence and document unresolved assumptions.').replace('&','&amp;'),st['BodyText']),Spacer(1,10),Paragraph('Disclaimer: decision-support draft only; independently validate all data and calculations.',st['Italic'])]
    doc.build(story); return b.getvalue()


def make_ic_memo(company, source_audit, summary, dcf_result, comps_result, lbo_result, debt_result,
                 mc_summary, quality, diligence, assumptions, notes=''):
    """Generate a formatted IC memo from active model outputs and diligence findings."""
    d=Document()
    d.add_heading('Investment Committee Memorandum',0)
    d.add_paragraph(f'Deal: {company}')
    d.add_paragraph(f'Generated: {date.today().isoformat()} | Status: {summary.get("status","REVIEW REQUIRED")}')
    d.add_heading('1. Executive decision snapshot',1)
    d.add_paragraph('Preliminary decision-support document. A PASS in structural data checks is not proof of source accuracy or investment merit.')
    if dcf_result:
        d.add_paragraph(f"DCF enterprise value: {_f(dcf_result.get('enterprise_value'))}; equity value: {_f(dcf_result.get('equity_value'))}.")
    d.add_paragraph(f"LBO multiple-only return: {_f(lbo_result.get('moic'))}x MOIC and {_f(100*lbo_result.get('irr', float('nan')))}% annualized IRR.")
    if debt_result:
        d.add_paragraph(f"Debt schedule ending debt: {_f(debt_result.get('ending_debt'))}. Covenant breaches: {int(((debt_result['schedule']['Leverage Covenant']=='BREACH') | (debt_result['schedule']['Interest Coverage Covenant']=='BREACH')).sum())} year(s).")
    d.add_heading('2. Valuation and assumptions',1)
    d.add_paragraph(f"WACC {_f(100*assumptions.get('wacc',0))}%; terminal growth {_f(100*assumptions.get('terminal_growth',0))}%; tax rate {_f(100*assumptions.get('tax_rate',0))}%; net debt {_f(assumptions.get('net_debt',0))}.")
    d.add_paragraph(f"Comparable median EV/Revenue: {_f(comps_result.get('median_ev_revenue'))}x; EV/EBITDA: {_f(comps_result.get('median_ev_ebitda'))}x. Comparable inputs require independent source verification.")
    d.add_heading('3. LBO financing and covenant review',1)
    d.add_paragraph(f"Entry multiple {_f(assumptions.get('entry_multiple'))}x; debt/EBITDA {_f(assumptions.get('debt_multiple'))}x; exit multiple {_f(assumptions.get('exit_multiple'))}x; holding period {assumptions.get('holding_period')} years.")
    if debt_result:
        table=d.add_table(rows=1,cols=6); table.style='Light Shading Accent 1'
        for i,h in enumerate(['Year','Opening Debt','Cash Sweep','Closing Debt','Leverage','Covenants']): table.rows[0].cells[i].text=h
        for _,r in debt_result['schedule'].iterrows():
            cells=table.add_row().cells
            vals=[r['Year'],_f(r['Opening Debt']),_f(r['Cash Sweep']),_f(r['Closing Debt']),_f(r['Leverage (x)'])+'x',str(r['Leverage Covenant'])+' / '+str(r['Interest Coverage Covenant'])]
            for i,v in enumerate(vals): cells[i].text=str(v)
    d.add_heading('4. Probabilistic return analysis',1)
    if mc_summary is not None and len(mc_summary):
        table=d.add_table(rows=1,cols=7); table.style='Light Shading Accent 1'
        for i,h in enumerate(['Metric','Mean','P5','P25','Median','P75','P95']): table.rows[0].cells[i].text=h
        for _,r in mc_summary.iterrows():
            cells=table.add_row().cells
            for i,k in enumerate(['Metric','Mean','P5','P25','Median','P75','P95']): cells[i].text=str(r[k]) if k=='Metric' else _f(r[k])
    else: d.add_paragraph('Monte Carlo summary not available.')
    d.add_heading('5. Data quality and source audit',1)
    d.add_paragraph(f"Source workbook: {source_audit.get('Source file')}; SHA-256: {source_audit.get('SHA-256')}; loaded at {source_audit.get('Loaded at (UTC)')}.")
    table=d.add_table(rows=1,cols=3); table.style='Light Shading Accent 1'
    for i,h in enumerate(['Check','Status','Detail']): table.rows[0].cells[i].text=h
    for _,r in quality.iterrows():
        cells=table.add_row().cells
        for i,k in enumerate(['Check','Status','Detail']): cells[i].text=str(r.get(k,''))
    d.add_heading('6. Due diligence findings and red flags',1)
    if diligence is not None and len(diligence):
        table=d.add_table(rows=1,cols=5); table.style='Light Shading Accent 1'
        for i,h in enumerate(['Workstream','Finding','Severity','Status','Mitigation / impact']): table.rows[0].cells[i].text=h
        for _,r in diligence.iterrows():
            cells=table.add_row().cells
            vals=[r.get('Workstream',''),r.get('Finding',''),r.get('Severity',''),r.get('Status',''),r.get('Impact / mitigation','')]
            for i,v in enumerate(vals): cells[i].text=str(v)
    else: d.add_paragraph('No diligence findings recorded.')
    d.add_heading('7. Analyst thesis and open items',1); d.add_paragraph(notes or 'No analyst notes provided.')
    d.add_heading('Model limitations and disclaimer',1)
    d.add_paragraph('Simplified decision-support model only. DCF, debt schedule, VC waterfall and Monte Carlo assumptions are not a substitute for transaction documents, legal/tax advice, independent quality of earnings, or a reviewed financial model. Validate all data and outputs before investment committee approval.')
    b=BytesIO(); d.save(b); return b.getvalue()
