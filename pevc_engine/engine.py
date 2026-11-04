import numpy as np
import pandas as pd


def quality_checks(df, a):
    checks=[]
    def add(name, ok, severity, detail):
        checks.append({'Check':name,'Status':'PASS' if bool(ok) else ('WARN' if severity != 'High' else 'FAIL'),'Severity':severity,'Detail':str(detail)})
    required=['Year','Revenue','EBITDA_Margin','D&A','Capex','NWC']
    add('Required columns',all(c in df.columns for c in required),'High','Required: '+', '.join(required))
    if not all(c in df.columns for c in required): return pd.DataFrame(checks)
    add('Forecast has rows',len(df)>0,'High',f'{len(df)} forecast rows')
    add('Years numeric and unique',pd.to_numeric(df.Year,errors='coerce').notna().all() and df.Year.is_unique,'High','Years should be numeric and unique')
    for c in ['Revenue','EBITDA_Margin','D&A','Capex','NWC']:
        x=pd.to_numeric(df[c],errors='coerce')
        add(f'{c} numeric / complete',x.notna().all(),'High',f'{int(x.isna().sum())} missing or nonnumeric values')
    num=df[['Revenue','EBITDA_Margin','D&A','Capex','NWC']].apply(pd.to_numeric,errors='coerce')
    add('Revenue nonnegative',(num.Revenue>=0).all(),'High','Revenue must be >= 0')
    add('EBITDA margin plausible',num.EBITDA_Margin.between(-1,1).all(),'Medium','Margins must be decimals, e.g. 0.20 = 20%')
    add('D&A / Capex nonnegative',((num['D&A']>=0)&(num.Capex>=0)).all(),'Medium','Check negative D&A or Capex entries')
    add('WACC > terminal growth',float(a['wacc'])>float(a['terminal_growth']),'High',f"WACC={float(a['wacc']):.2%}; terminal growth={float(a['terminal_growth']):.2%}")
    add('Tax rate between 0 and 100%',0<=float(a['tax_rate'])<1,'High',f"Tax rate={float(a['tax_rate']):.2%}")
    add('Years ascending',pd.to_numeric(df.Year,errors='coerce').is_monotonic_increasing,'Medium','Forecast years should be ascending')
    add('Duplicate financial rows',not df.duplicated().any(),'Medium','Identical duplicate rows may indicate accidental imports')
    add('Missing financial values',not df[required].isna().any().any(),'High','No blanks permitted in required forecast fields')
    return pd.DataFrame(checks)


def calculate_fcff(df, tax_rate):
    x=df.copy()
    for c in ['Year','Revenue','EBITDA_Margin','D&A','Capex','NWC']: x[c]=pd.to_numeric(x[c],errors='raise')
    x['EBITDA']=x.Revenue*x.EBITDA_Margin
    x['EBIT']=x.EBITDA-x['D&A']
    x['Cash_Taxes']=np.maximum(x.EBIT,0)*tax_rate
    x['NOPAT']=x.EBIT-x.Cash_Taxes
    x['Change_NWC']=x.NWC.diff().fillna(0)
    x['FCFF']=x.NOPAT+x['D&A']-x.Capex-x.Change_NWC
    return x


def dcf(df,wacc,growth,tax,net_debt=0):
    if wacc<=growth: raise ValueError('WACC harus lebih besar daripada terminal growth.')
    x=calculate_fcff(df,tax); periods=np.arange(1,len(x)+1)
    x['Discount_Factor']=1/(1+wacc)**periods; x['PV_FCFF']=x.FCFF*x.Discount_Factor
    tv=float(x.FCFF.iloc[-1])*(1+growth)/(wacc-growth); pvtv=tv/(1+wacc)**len(x)
    ev=float(x.PV_FCFF.sum()+pvtv)
    return {'financials':x,'terminal_value':tv,'pv_terminal_value':pvtv,'enterprise_value':ev,'net_debt':float(net_debt),'equity_value':ev-float(net_debt)}


def dcf_sensitivity(df,wacc,growth,tax,net_debt=0):
    rows=[]
    for gshift in [-.01,-.005,0,.005,.01]:
        g=growth+gshift; row={'Terminal Growth':g}
        for wshift in [-.02,-.01,0,.01,.02]:
            w=wacc+wshift; row[f'WACC {w:.1%}']=dcf(df,w,g,tax,net_debt)['equity_value'] if w>g else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def comps_valuation(comps,target_revenue,target_ebitda):
    x=comps.copy()
    for c in ['EV','Revenue','EBITDA']:
        if c not in x.columns: x[c]=np.nan
        x[c]=pd.to_numeric(x[c],errors='coerce')
    x=x[(x.EV>0)&(x.Revenue>0)&(x.EBITDA>0)]
    if x.empty: return {'comps':x,'median_ev_revenue':np.nan,'median_ev_ebitda':np.nan,'implied_ev_revenue':np.nan,'implied_ev_ebitda':np.nan}
    x['EV/Revenue']=x.EV/x.Revenue; x['EV/EBITDA']=x.EV/x.EBITDA
    a=float(x['EV/Revenue'].median()); b=float(x['EV/EBITDA'].median())
    return {'comps':x,'median_ev_revenue':a,'median_ev_ebitda':b,'implied_ev_revenue':a*target_revenue,'implied_ev_ebitda':b*target_ebitda}


def lbo(entry_ebitda,entry_multiple,debt_multiple,exit_ebitda,exit_multiple,years,exit_net_debt=0,fees=0):
    if years<=0: raise ValueError('Holding period harus lebih dari nol.')
    entry_ev=entry_ebitda*entry_multiple; debt=entry_ebitda*debt_multiple
    equity=entry_ev-debt+fees; exit_ev=exit_ebitda*exit_multiple; exit_equity=exit_ev-exit_net_debt
    moic=exit_equity/equity if equity>0 else np.nan
    irr=moic**(1/years)-1 if moic>=0 and np.isfinite(moic) else np.nan
    return {'entry_ev':entry_ev,'initial_debt':debt,'initial_equity':equity,'exit_ev':exit_ev,'exit_equity':exit_equity,'moic':moic,'irr':irr}


def lbo_debt_schedule(financials, entry_multiple=8.0, debt_multiple=4.0, tax_rate=.22, interest_rate=.10,
                      minimum_cash=0.0, cash_sweep_pct=1.0, max_leverage=6.0, min_interest_cover=1.5,
                      amortization_pct=0.0, fees=0.0):
    """Illustrative annual debt schedule. Cash available is EBITDA less cash taxes, capex and change in NWC.
    Interest is based on average opening/closing debt; covenants are tested on opening debt and interest.
    """
    x=calculate_fcff(financials,tax_rate)
    if x.empty: raise ValueError('Financial forecast is empty.')
    entry_ebitda=float(x.iloc[0].EBITDA); entry_ev=entry_ebitda*entry_multiple
    opening_debt=max(0.0,entry_ebitda*debt_multiple); initial_equity=entry_ev-opening_debt+fees
    if initial_equity<=0: raise ValueError('Initial equity must be positive; reduce entry debt or fees.')
    rows=[]; debt=opening_debt
    for _,r in x.iterrows():
        ebitda=float(r.EBITDA); cash_tax=max(0.0,float(r.EBIT))*tax_rate
        mandatory=min(debt,max(0.0,opening_debt*amortization_pct))
        interest=debt*interest_rate
        cash_before_sweep=ebitda-cash_tax-float(r.Capex)-float(r.Change_NWC)-interest-mandatory-minimum_cash
        sweep=min(max(0.0,debt-mandatory),max(0.0,cash_before_sweep)*cash_sweep_pct)
        closing=max(0.0,debt-mandatory-sweep)
        avg_interest=((debt+closing)/2)*interest_rate
        # Recalculate sweep once using average-debt interest estimate.
        cash_before_sweep=ebitda-cash_tax-float(r.Capex)-float(r.Change_NWC)-avg_interest-mandatory-minimum_cash
        sweep=min(max(0.0,debt-mandatory),max(0.0,cash_before_sweep)*cash_sweep_pct)
        closing=max(0.0,debt-mandatory-sweep)
        leverage=debt/ebitda if ebitda>0 else np.inf
        coverage=ebitda/avg_interest if avg_interest>0 else np.inf
        rows.append({'Year':int(r.Year),'Revenue':float(r.Revenue),'EBITDA':ebitda,'Cash Taxes':cash_tax,'Capex':float(r.Capex),'Change NWC':float(r.Change_NWC),'Opening Debt':debt,'Interest Expense':avg_interest,'Mandatory Amortization':mandatory,'Cash Sweep':sweep,'Closing Debt':closing,'Leverage (x)':leverage,'Interest Coverage (x)':coverage,'Leverage Covenant': 'BREACH' if leverage>max_leverage else 'PASS','Interest Coverage Covenant':'BREACH' if coverage<min_interest_cover else 'PASS','Cash Available Before Sweep':cash_before_sweep})
        debt=closing; opening_debt=debt
    schedule=pd.DataFrame(rows)
    return {'schedule':schedule,'entry_ev':entry_ev,'initial_debt':opening_debt if len(schedule)==0 else max(0.0,entry_ebitda*debt_multiple),'initial_equity':initial_equity,'ending_debt':float(debt),'entry_ebitda':entry_ebitda}


def lbo_sensitivity(ebitda, debt_multiple, years, entry_center, exit_center):
    rows=[]; entries=np.arange(max(1,entry_center-2),entry_center+2.01,.5)
    for ex in np.arange(max(1,exit_center-2),exit_center+2.01,.5):
        r={'Exit Multiple':ex}
        for en in entries: r[f'Entry {en:.1f}x']=lbo(ebitda,en,debt_multiple,ebitda,ex,years)['moic']
        rows.append(r)
    return pd.DataFrame(rows)


def vc(investment,pre_money,exit_equity,dilution=0):
    if investment<0 or pre_money<0 or exit_equity<0 or not 0<=dilution<1: raise ValueError('Input VC tidak valid.')
    own=investment/(investment+pre_money) if investment+pre_money else 0
    exit_own=own*(1-dilution); proceeds=exit_own*exit_equity
    return {'ownership_initial':own,'ownership_exit':exit_own,'exit_proceeds':proceeds,'moic':proceeds/investment if investment else np.nan}


def vc_cap_table(rounds, exit_equity, liquidation_multiple=1.0, participating=False, common_preference_priority=True):
    """Simple priced-round cap table and single preferred class exit waterfall; not a legal-document simulator."""
    x=rounds.copy()
    required=['Round','Investment','Pre-money']
    if not all(c in x.columns for c in required): raise ValueError('Cap table needs Round, Investment, Pre-money columns.')
    x['Investment']=pd.to_numeric(x.Investment,errors='raise'); x['Pre-money']=pd.to_numeric(x['Pre-money'],errors='raise')
    if (x.Investment<0).any() or (x['Pre-money']<0).any(): raise ValueError('Investment and pre-money must be nonnegative.')
    founder=1.0; rows=[]; total_invested=0.0; latest_post=0.0
    for _,r in x.iterrows():
        invest=float(r.Investment); pre=float(r['Pre-money']); post=pre+invest
        new_ownership=invest/post if post>0 else 0.0
        founder*=pre/post if post>0 else 1.0
        # Existing investors diluted pro-rata; retain round-by-round ownership history.
        for old in rows: old['Ownership %']*=pre/post if post>0 else 1.0
        rows.append({'Shareholder':str(r.Round),'Investment':invest,'Pre-money':pre,'Post-money':post,'Ownership %':new_ownership})
        total_invested+=invest; latest_post=post
    rows.insert(0,{'Shareholder':'Founders / common','Investment':0.0,'Pre-money':np.nan,'Post-money':np.nan,'Ownership %':founder})
    cap=pd.DataFrame(rows)
    pref=total_invested*max(0.0,liquidation_multiple)
    preferred_ownership=float(cap.loc[cap.Shareholder!='Founders / common','Ownership %'].sum())
    if exit_equity<=0: pref_proceeds=0.0; common_proceeds=0.0; investor_proceeds=0.0
    elif participating:
        pref_proceeds=min(exit_equity,pref); residual=max(0.0,exit_equity-pref_proceeds)
        investor_proceeds=pref_proceeds+residual*preferred_ownership; common_proceeds=residual*(1-preferred_ownership)
    else:
        pref_proceeds=min(exit_equity,pref); residual=max(0.0,exit_equity-pref_proceeds)
        conversion=exit_equity*preferred_ownership
        if conversion>pref_proceeds:
            investor_proceeds=conversion; common_proceeds=exit_equity-conversion
        else:
            investor_proceeds=pref_proceeds; common_proceeds=residual
    return {'cap_table':cap,'total_invested':total_invested,'preferred_ownership':preferred_ownership,'founder_ownership':founder,'liquidation_preference':pref,'investor_proceeds':investor_proceeds,'common_proceeds':common_proceeds,'investor_moic':investor_proceeds/total_invested if total_invested>0 else np.nan}


def monte_carlo_returns(base_moic=2.0, years=5, n_sims=10000, moic_vol=.6, seed=42, downside_floor=0.0):
    """Lognormal MOIC distribution parameterized so median is base_moic."""
    if base_moic<=0 or years<=0 or n_sims<100 or moic_vol<0: raise ValueError('Monte Carlo assumptions invalid.')
    rng=np.random.default_rng(int(seed)); sigma=float(moic_vol)
    moic=rng.lognormal(mean=np.log(base_moic),sigma=sigma,size=int(n_sims))
    moic=np.maximum(moic,float(downside_floor)); irr=np.power(moic,1/years)-1
    q=np.quantile(moic,[.05,.25,.5,.75,.95]); qi=np.quantile(irr,[.05,.25,.5,.75,.95])
    return {'moic':moic,'irr':irr,'summary':pd.DataFrame([{'Metric':'MOIC','Mean':moic.mean(),'P5':q[0],'P25':q[1],'Median':q[2],'P75':q[3],'P95':q[4],'Probability Loss':np.mean(moic<1)}, {'Metric':'IRR','Mean':irr.mean(),'P5':qi[0],'P25':qi[1],'Median':qi[2],'P75':qi[3],'P95':qi[4],'Probability Loss':np.mean(irr<0)}])}


def audit_source(file_name, file_bytes, financials, assumptions, comps):
    import hashlib, datetime, json
    digest=hashlib.sha256(file_bytes).hexdigest()
    return {'Source file':file_name,'SHA-256':digest,'File size (bytes)':len(file_bytes),'Loaded at (UTC)':datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'),'Financial rows':len(financials),'Comparable rows':len(comps),'Assumption keys':', '.join(sorted(assumptions.keys())),'Data fingerprint':hashlib.sha256((financials.to_csv(index=False)+json.dumps(assumptions,sort_keys=True,default=str)+comps.to_csv(index=False)).encode()).hexdigest()}
