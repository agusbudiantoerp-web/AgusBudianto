import os, tempfile, hashlib
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
from pevc_engine.excel_io import load_inputs
from pevc_engine.engine import (quality_checks, dcf, dcf_sensitivity, comps_valuation, lbo, lbo_sensitivity,
    lbo_debt_schedule, vc_cap_table, monte_carlo_returns, audit_source)
from pevc_engine.reporting import make_docx, make_pdf, make_ic_memo

st.set_page_config(page_title='PE/VC Investment Analysis Engine',page_icon='📊',layout='wide')
st.title('PE/VC Investment Analysis Engine')
st.caption('Excel → validated inputs → Python models → audit trail → dashboard → investment committee memo')
st.warning('Workbook bawaan berisi data ilustratif. Semua hasil adalah decision support, bukan rekomendasi investasi atau pengganti due diligence.')
base_dir=os.path.dirname(__file__)
def_path=os.path.join(base_dir,'data','PEVC_Investment_Intelligence_Enhanced.xlsx')
up=st.file_uploader('Upload workbook Excel (.xlsx)',type=['xlsx'],help='Gunakan workbook dengan sheet Company_Financials. Setelah upload, nama file, fingerprint, kualitas data dan seluruh hasil model akan diperbarui.')
if up:
    file_bytes=up.getvalue(); source_name=up.name
    with tempfile.NamedTemporaryFile(suffix='.xlsx',delete=False) as f:
        f.write(file_bytes); path=f.name
    bundled_bytes=open(def_path,'rb').read() if os.path.exists(def_path) else b''
    if hashlib.sha256(file_bytes).hexdigest()==hashlib.sha256(bundled_bytes).hexdigest():
        st.info('File yang diunggah identik dengan workbook bawaan. Karena datanya sama, angka dashboard memang akan sama. Ubah nilai di Excel lalu unggah kembali untuk melihat hasil berubah.')
    else:
        st.success(f'Workbook baru terdeteksi: **{source_name}** — dashboard sedang menggunakan file ini.')
else:
    path=def_path; source_name=os.path.basename(def_path)
    file_bytes=open(def_path,'rb').read() if os.path.exists(def_path) else b''
    st.caption(f'Sumber aktif: workbook bawaan — {source_name}. Upload file lain untuk mengganti input.')
try:
    fin,a,comp=load_inputs(path)
except Exception as e:
    st.error(f'Gagal membaca workbook: {e}')
    st.info('Periksa nama sheet Company_Financials dan pastikan file bukan workbook rusak atau dilindungi password.')
    st.stop()
finally:
    if up and os.path.exists(path):
        try: os.unlink(path)
        except OSError: pass

source_key=hashlib.sha256(file_bytes).hexdigest()[:12]
st.subheader('Active Excel input')
st.write(f"**Source:** {source_name} · **Fingerprint:** `{source_key}` · **Financial rows loaded:** {len(fin)}")
if up:
    st.caption('Preview berikut berasal dari file yang baru diunggah. Jika angka yang Anda edit tidak terlihat di sini, periksa sheet/sel yang diedit dan simpan workbook di Excel sebelum upload ulang.')
    st.dataframe(fin, use_container_width=True, hide_index=True)

st.sidebar.header('Deal assumptions')
company=st.sidebar.text_input('Company / deal name','Illustrative Target Co.',key=f'company_{source_key}')
tax=st.sidebar.number_input('Tax rate',0.0,.95,float(a.get('tax_rate',.22)),.01,format='%.3f',key=f'tax_{source_key}')
wacc=st.sidebar.number_input('WACC',.001,.95,float(a.get('wacc',.12)),.005,format='%.3f',key=f'wacc_{source_key}')
growth=st.sidebar.number_input('Terminal growth',-.5,.9,float(a.get('terminal_growth',.03)),.005,format='%.3f',key=f'growth_{source_key}')
net_debt=st.sidebar.number_input('Net debt',value=float(a.get('net_debt',100)),step=10.,key=f'net_debt_{source_key}')
entry=st.sidebar.number_input('LBO entry EV / EBITDA',min_value=.1,value=float(a.get('entry_multiple',8)),step=.25,key=f'entry_{source_key}')
debt_mult=st.sidebar.number_input('Entry debt / EBITDA',min_value=0.,value=float(a.get('debt_multiple',4)),step=.25,key=f'debt_mult_{source_key}')
exit_mult=st.sidebar.number_input('LBO exit EV / EBITDA',min_value=.1,value=float(a.get('exit_multiple',8)),step=.25,key=f'exit_{source_key}')
years=st.sidebar.number_input('Holding period (years)',1,15,int(a.get('holding_period',5)),1,key=f'holding_{source_key}')
interest_rate=st.sidebar.number_input('Debt interest rate',0.0,1.0,float(a.get('interest_rate',.10)),.005,format='%.3f',key=f'interest_{source_key}')
notes=st.sidebar.text_area('Analyst notes / investment thesis','Replace sample data with verified information; document risks and diligence gaps.')
assumptions={'tax_rate':tax,'wacc':wacc,'terminal_growth':growth,'net_debt':net_debt,'entry_multiple':entry,'debt_multiple':debt_mult,'exit_multiple':exit_mult,'holding_period':years,'interest_rate':interest_rate}
quality=quality_checks(fin,assumptions)
try: dv=dcf(fin,wacc,growth,tax,net_debt); dcf_error=None
except Exception as e: dv=None; dcf_error=str(e)
last=fin.iloc[-1]; revenue=float(last['Revenue']); ebitda=revenue*float(last['EBITDA_Margin'])
compres=comps_valuation(comp,revenue,ebitda)
lbores=lbo(float(fin.iloc[0]['Revenue'])*float(fin.iloc[0]['EBITDA_Margin']),entry,debt_mult,ebitda,exit_mult,int(years))
try:
    debtres=lbo_debt_schedule(fin,entry,debt_mult,tax,interest_rate,
        cash_sweep_pct=st.sidebar.slider('Excess cash sweep',0,100,75,5)/100,
        max_leverage=st.sidebar.number_input('Max leverage covenant (x)',1.0,15.0,6.0,.5),
        min_interest_cover=st.sidebar.number_input('Minimum interest coverage (x)',0.0,10.0,1.5,.25),
        amortization_pct=st.sidebar.number_input('Annual mandatory amortization (% opening debt)',0.0,.5,.05,.01))
    debt_error=None
except Exception as e: debtres=None; debt_error=str(e)
source_audit=audit_source(source_name,file_bytes,fin,assumptions,comp)
fails=int((quality.Status=='FAIL').sum()) if len(quality) else 1
status='REVIEW REQUIRED' if fails else 'INITIAL CHECKS PASS'
summary={'status':status,'dcf_ev':dv['enterprise_value'] if dv else np.nan,'dcf_equity':dv['equity_value'] if dv else np.nan,'lbo_moic':lbores['moic'],'lbo_irr':lbores['irr'],'quality_failures':fails}

tabs=st.tabs(['Overview','Data Quality & Audit','DCF & Sensitivity','LBO Debt Schedule','VC Cap Table & Waterfall','Monte Carlo','Due Diligence','Investment Memo'])
with tabs[0]:
    st.subheader('Investment Snapshot'); c=st.columns(4)
    c[0].metric('DCF Enterprise Value',f"{dv['enterprise_value']:,.2f}" if dv else 'N/A')
    c[1].metric('DCF Equity Value',f"{dv['equity_value']:,.2f}" if dv else 'N/A')
    c[2].metric('LBO MOIC (multiple-only)',f"{lbores['moic']:.2f}x" if np.isfinite(lbores['moic']) else 'N/A')
    c[3].metric('LBO IRR (multiple-only)',f"{lbores['irr']:.1%}" if np.isfinite(lbores['irr']) else 'N/A')
    st.write('Model status:',status)
    if dcf_error: st.error(dcf_error)
    if dv:
        st.dataframe(dv['financials'],use_container_width=True,hide_index=True)
        st.plotly_chart(px.line(dv['financials'],x='Year',y=['Revenue','EBITDA','FCFF'],markers=True,title='Revenue, EBITDA and FCFF forecast'),use_container_width=True)
    st.subheader('Comparable valuation — illustrative until sources verified')
    c=st.columns(2); c[0].metric('Median EV / Revenue',f"{compres['median_ev_revenue']:.2f}x" if np.isfinite(compres['median_ev_revenue']) else 'N/A'); c[1].metric('Median EV / EBITDA',f"{compres['median_ev_ebitda']:.2f}x" if np.isfinite(compres['median_ev_ebitda']) else 'N/A')
    st.metric('Input fingerprint',source_audit['Data fingerprint'][:16]+'…')
with tabs[1]:
    st.subheader('Data validation'); st.dataframe(quality,use_container_width=True,hide_index=True)
    c=st.columns(3); c[0].metric('Failures',fails); c[1].metric('Warnings',int((quality.Status=='WARN').sum())); c[2].metric('Checks',len(quality))
    if fails: st.error('Perbaiki semua FAIL sebelum mengandalkan output valuasi.')
    else: st.success('Pemeriksaan struktur lolos; ini tidak membuktikan sumber data benar secara ekonomi.')
    st.subheader('Source audit trail')
    st.dataframe(pd.DataFrame([{'Field':k,'Value':v} for k,v in source_audit.items()]),use_container_width=True,hide_index=True)
    st.download_button('Download audit trail CSV',pd.DataFrame([source_audit]).to_csv(index=False).encode(), 'PEVC_Audit_Trail.csv','text/csv')
    st.caption('SHA-256 mengidentifikasi file sumber. Simpan salinan workbook asli dan catat perubahan asumsi untuk audit formal.')
with tabs[2]:
    if dv:
        c=st.columns(3); c[0].metric('Enterprise Value',f"{dv['enterprise_value']:,.2f}"); c[1].metric('Net Debt',f"{dv['net_debt']:,.2f}"); c[2].metric('Equity Value',f"{dv['equity_value']:,.2f}")
        sens=dcf_sensitivity(fin,wacc,growth,tax,net_debt); st.dataframe(sens.set_index('Terminal Growth').style.format('{:,.1f}'),use_container_width=True)
        st.plotly_chart(px.imshow(sens.set_index('Terminal Growth'),aspect='auto',color_continuous_scale='RdYlGn',origin='lower',title='DCF Equity Value Sensitivity'),use_container_width=True)
    else: st.error(dcf_error)
with tabs[3]:
    st.subheader('LBO debt schedule, cash sweep and covenant checks')
    if debt_error: st.error(debt_error)
    elif debtres:
        c=st.columns(3); c[0].metric('Entry EV',f"{debtres['entry_ev']:,.2f}"); c[1].metric('Initial Debt',f"{debtres['initial_debt']:,.2f}"); c[2].metric('Ending Debt',f"{debtres['ending_debt']:,.2f}")
        st.dataframe(debtres['schedule'],use_container_width=True,hide_index=True)
        breach=int(((debtres['schedule']['Leverage Covenant']=='BREACH')|(debtres['schedule']['Interest Coverage Covenant']=='BREACH')).sum())
        st.metric('Years with at least one covenant breach',breach)
        st.plotly_chart(px.line(debtres['schedule'],x='Year',y=['Opening Debt','Closing Debt'],markers=True,title='Debt paydown through cash sweep'),use_container_width=True)
        st.caption('Model ilustratif tahunan; belum mencakup revolver, PIK interest, cash minimum dinamis, tax loss carryforward, financing fees amortization atau covenant definitions dari dokumen pinjaman.')
    st.subheader('Entry / exit multiple sensitivity')
    grid=lbo_sensitivity(ebitda,debt_mult,int(years),entry,exit_mult); st.dataframe(grid.set_index('Exit Multiple').style.format('{:.2f}x'),use_container_width=True)
with tabs[4]:
    st.subheader('Multi-round VC cap table')
    default_rounds=pd.DataFrame([{'Round':'Seed','Investment':float(a.get('vc_investment',2)),'Pre-money':float(a.get('vc_pre_money',8))},{'Round':'Series A','Investment':float(a.get('vc_follow_on',3)),'Pre-money':float(a.get('vc_follow_on_pre_money',15))}])
    rounds=st.data_editor(default_rounds,num_rows='dynamic',use_container_width=True,key='vc_rounds')
    exit_equity=st.number_input('Exit equity value',min_value=0.,value=float(a.get('vc_exit_equity',100)),step=5.)
    liq=st.number_input('Liquidation preference multiple',min_value=0.,value=1.0,step=.25)
    participating=st.checkbox('Participating preferred (investors receive preference + pro-rata residual)',value=False)
    try:
        v=vc_cap_table(rounds,exit_equity,liq,participating)
        c=st.columns(4); c[0].metric('Total invested',f"{v['total_invested']:,.2f}"); c[1].metric('Founder ownership',f"{v['founder_ownership']:.2%}"); c[2].metric('Investor proceeds',f"{v['investor_proceeds']:,.2f}"); c[3].metric('Investor MOIC',f"{v['investor_moic']:.2f}x" if np.isfinite(v['investor_moic']) else 'N/A')
        st.dataframe(v['cap_table'],use_container_width=True,hide_index=True)
        st.write({'Liquidation preference':v['liquidation_preference'],'Common proceeds':v['common_proceeds']})
    except Exception as e: st.error(f'Cap table error: {e}')
    st.caption('Cap table menggunakan pendekatan priced-round sederhana. SAFE, convertible note, option pool, anti-dilution, seniority antar kelas dan legal waterfall kompleks belum dimodelkan.')
with tabs[5]:
    st.subheader('Probabilistic return distribution')
    c=st.columns(4); base_moic=c[0].number_input('Base / median MOIC',.1,20.,2.0,.1); vol=c[1].slider('Return dispersion (log sigma)',0.0,1.5,.6,.05); sims=c[2].selectbox('Simulations',[1000,5000,10000,25000,50000],index=2); seed=c[3].number_input('Random seed',0,999999,42,1)
    mc=monte_carlo_returns(base_moic,int(years),int(sims),vol,int(seed))
    st.dataframe(mc['summary'].round(3),use_container_width=True,hide_index=True)
    st.caption('MOIC statistics are multiples (x); IRR statistics are decimal returns (e.g. 0.15 = 15%); Probability Loss is a percentage.')
    st.plotly_chart(px.histogram(x=mc['moic'],nbins=60,title='Simulated MOIC distribution',labels={'x':'MOIC','y':'Simulation count'}),use_container_width=True)
    st.plotly_chart(px.histogram(x=mc['irr'],nbins=60,title='Simulated annualized IRR distribution',labels={'x':'Annualized IRR','y':'Simulation count'}),use_container_width=True)
    st.caption('Model menggunakan distribusi lognormal dengan median MOIC sebagai input. Ini asumsi distribusi, bukan estimasi empiris; kalibrasikan pada data historis/fund strategy sebelum keputusan.')
with tabs[6]:
    st.subheader('Due diligence tracker')
    if 'dd_findings' not in st.session_state:
        st.session_state.dd_findings=pd.DataFrame([
          {'Workstream':'Financial','Finding':'Quality of earnings not independently verified','Severity':'High','Status':'Open','Evidence / source':'Not provided','Impact / mitigation':'Reconcile audited statements, management accounts and cash flows'},
          {'Workstream':'Commercial','Finding':'Customer concentration and contract durability to validate','Severity':'Medium','Status':'Open','Evidence / source':'Not provided','Impact / mitigation':'Review top customer contracts and churn / renewal data'},
          {'Workstream':'Legal / Tax','Finding':'Legal, tax and regulatory diligence pending','Severity':'High','Status':'Open','Evidence / source':'Not provided','Impact / mitigation':'Obtain counsel review and quantify contingent liabilities'}])
    dd=st.data_editor(st.session_state.dd_findings,num_rows='dynamic',use_container_width=True,key='dd_editor',column_config={'Severity':st.column_config.SelectboxColumn(options=['Low','Medium','High','Critical']),'Status':st.column_config.SelectboxColumn(options=['Open','In progress','Resolved','Accepted risk'])})
    st.session_state.dd_findings=dd
    open_dd=dd[dd['Status'].astype(str).isin(['Open','In progress'])] if len(dd) and 'Status' in dd else pd.DataFrame()
    high_dd=dd[dd['Severity'].astype(str).isin(['High','Critical']) & ~dd['Status'].astype(str).eq('Resolved')] if len(dd) and 'Status' in dd and 'Severity' in dd else pd.DataFrame()
    c=st.columns(3); c[0].metric('Total findings',len(dd)); c[1].metric('Open / in progress',len(open_dd)); c[2].metric('High / critical not resolved',len(high_dd))
    if len(high_dd): st.error('Ada temuan High/Critical yang belum diselesaikan; komite investasi perlu mempertimbangkan mitigasi atau syarat transaksi.')
    st.download_button('Download due diligence register CSV',dd.to_csv(index=False).encode(),'PEVC_Due_Diligence_Register.csv','text/csv')
with tabs[7]:
    st.subheader('Investment Committee memo — generated from active model outputs')
    dd_current=st.session_state.get('dd_findings',pd.DataFrame())
    dd_open=dd_current[dd_current['Status'].astype(str).isin(['Open','In progress'])] if len(dd_current) and 'Status' in dd_current else pd.DataFrame()
    dd_red=dd_current[dd_current['Severity'].astype(str).isin(['High','Critical']) & ~dd_current['Status'].astype(str).eq('Resolved')] if len(dd_current) and 'Status' in dd_current and 'Severity' in dd_current else pd.DataFrame()
    dcf_ev_text=f"{dv['enterprise_value']:,.2f}" if dv else 'N/A'
    dcf_equity_text=f"{dv['equity_value']:,.2f}" if dv else 'N/A'
    ending_debt_text=f"{debtres['ending_debt']:,.2f}" if debtres else 'N/A'
    memo_text=f'''INVESTMENT COMMITTEE MEMO\n\nDeal: {company}\nSource workbook: {source_name}\nSource SHA-256: {source_audit['SHA-256']}\n\nRECOMMENDATION STATUS\n{status} — not an investment recommendation.\n\nVALUATION\nDCF enterprise value: {dcf_ev_text}\nDCF equity value: {dcf_equity_text}\nWACC: {wacc:.2%}; terminal growth: {growth:.2%}; net debt: {net_debt:,.2f}\nComparable median EV/Revenue: {compres['median_ev_revenue']:.2f}x; EV/EBITDA: {compres['median_ev_ebitda']:.2f}x\n\nLBO\nEntry multiple: {entry:.2f}x; debt multiple: {debt_mult:.2f}x; exit multiple: {exit_mult:.2f}x; holding: {years} years\nMultiple-only MOIC: {lbores['moic']:.2f}x; IRR: {lbores['irr']:.2%}\nDebt schedule ending debt: {ending_debt_text}\n\nDATA QUALITY & DILIGENCE\nValidation failures: {fails}; warnings: {int((quality.Status=='WARN').sum())}\nOpen DD findings: {len(dd_open)}; high/critical unresolved: {len(dd_red)}\n'''
    if len(dd_current):
        memo_text+='\nDUE DILIGENCE FINDINGS\n'+'\n'.join([f"- [{r.get('Severity','')}] {r.get('Workstream','')}: {r.get('Finding','')} — {r.get('Status','')}. Mitigation: {r.get('Impact / mitigation','')}" for _,r in dd_current.iterrows()])+'\n'
    memo_text+='\nKEY RISKS / OPEN ITEMS\n'+(notes or 'Analyst notes not provided.')+'\n\nMODEL LIMITATIONS\nThe output uses simplified DCF, LBO, VC waterfall and Monte Carlo assumptions. Verify source data, financing terms, legal rights, tax treatment and model outputs independently before IC approval.\n'
    st.text_area('Memo preview',memo_text,height=420)
    st.download_button('Download Investment Memo (.txt)',memo_text.encode(),'PEVC_Investment_Memo.txt','text/plain')
    ic_docx=make_ic_memo(company,source_audit,summary,dv or {},compres,lbores,debtres,mc['summary'] if 'mc' in locals() else None,quality,dd_current,assumptions,notes)
    st.download_button('Download formatted IC Memo (.docx)',ic_docx,'PEVC_Investment_Committee_Memo.docx','application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    args=(company,summary,dv or {},lbores,quality,assumptions,notes)
    st.download_button('Download valuation report (.docx)',make_docx(*args),'PEVC_Investment_Report.docx','application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    st.download_button('Download valuation report (.pdf)',make_pdf(*args),'PEVC_Investment_Report.pdf','application/pdf')
    st.info('Memo menggabungkan output model dan register due diligence yang sedang aktif. Dokumen memo teks mencakup lebih banyak modul daripada laporan valuasi DOCX/PDF saat ini.')
with st.expander('Input data preview'):
    st.write('Financials'); st.dataframe(fin,use_container_width=True)
    st.write('Comparable companies'); st.dataframe(comp,use_container_width=True)
