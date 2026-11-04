import pandas as pd
from openpyxl import load_workbook

def load_inputs(path):
    book=load_workbook(path,data_only=True,read_only=True)
    if 'Company_Financials' not in book.sheetnames: raise ValueError('Workbook harus memiliki sheet Company_Financials.')
    s=book['Company_Financials']
    # Support the supplied financial model layout: metric names in column A, years in row 3, values across columns.
    years=[s.cell(3,c).value for c in range(2,s.max_column+1)]
    metrics={}
    for r in range(4,s.max_row+1):
        name=s.cell(r,1).value
        if name:
            metrics[str(name).strip().lower()]=[s.cell(r,c).value for c in range(2,s.max_column+1)]
    def metric(*names, default=None):
        for n in names:
            if n.lower() in metrics: return metrics[n.lower()]
        return default
    revenue=metric('Revenue'); margin=metric('EBITDA Margin','EBITDA_Margin'); da=metric('D&A','DA'); capex=metric('Capex','Capital Expenditure'); nwc=metric('NWC','Net Working Capital')
    if not all(v is not None for v in [revenue,margin,da,capex,nwc]):
        # Also support normalized flat table format.
        df=pd.read_excel(path,sheet_name='Company_Financials')
        df.columns=[str(c).strip() for c in df.columns]
        required=['Year','Revenue','EBITDA_Margin','D&A','Capex','NWC']
        if not all(c in df.columns for c in required): raise ValueError('Format Company_Financials tidak dikenali. Gunakan workbook yang disertakan atau Input Template.')
        financials=df[required].copy()
    else:
        financials=pd.DataFrame({'Year':years,'Revenue':revenue,'EBITDA_Margin':margin,'D&A':da,'Capex':capex,'NWC':nwc}).dropna(subset=['Year'])
    a={}
    if 'Assumptions' in book.sheetnames:
        s=book['Assumptions']
        mapping={'tax_rate':4,'wacc':5,'terminal_growth':6,'net_debt':7,'entry_multiple':8,'debt_multiple':9,'interest_rate':10,'exit_multiple':11,'holding_period':12,'vc_investment':13,'vc_pre_money':14,'vc_follow_on':15,'vc_follow_on_pre_money':16,'vc_exit_equity':17}
        for k,r in mapping.items(): a[k]=s.cell(r,2).value
    if 'Assumptions_Input' in book.sheetnames:
        s=book['Assumptions_Input']
        for r in range(2,s.max_row+1):
            k=s.cell(r,1).value; v=s.cell(r,2).value
            if k: a[str(k).strip()]=v
    defaults={'tax_rate':.22,'wacc':.12,'terminal_growth':.03,'net_debt':100,'entry_multiple':8,'debt_multiple':4,'exit_multiple':8,'holding_period':5,'vc_investment':2,'vc_pre_money':8,'vc_exit_equity':100}
    for k,v in defaults.items():
        if a.get(k) is None: a[k]=v
    a={k:float(v) for k,v in a.items() if isinstance(v,(int,float))}
    comps=pd.DataFrame(columns=['Name','EV','Revenue','EBITDA'])
    if 'Comps_Input' in book.sheetnames:
        comps=pd.read_excel(path,sheet_name='Comps_Input')
    elif 'Comps_Valuation' in book.sheetnames:
        s=book['Comps_Valuation']
        rows=[]
        for r in range(5,s.max_row+1):
            name=s.cell(r,1).value; ev=s.cell(r,3).value; rev=s.cell(r,4).value; ebitda=s.cell(r,5).value
            if name and isinstance(ev,(int,float)): rows.append({'Name':name,'EV':ev,'Revenue':rev,'EBITDA':ebitda})
        comps=pd.DataFrame(rows,columns=['Name','EV','Revenue','EBITDA'])
    book.close()
    return financials,a,comps
