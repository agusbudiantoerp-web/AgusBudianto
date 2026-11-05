import streamlit as st
from engine import analyze_equity, calculate_dcf, dcf_sensitivity, build_research_summary
from reports import make_excel_report, make_pdf_report

st.set_page_config(page_title="AI Equity Research", page_icon="📊", layout="wide")
st.title("AI Equity Research")
st.caption("Indonesian equities first · shared engine for web and Telegram · Yahoo Finance data")
st.warning("Research support only. Not investment advice. Verify data and assumptions independently.")
with st.sidebar:
    st.header("Research settings")
    symbol = st.text_input("Ticker saham", "ANTM", help="Untuk saham BEI cukup masukkan ANTM. Aplikasi menambahkan .JK.")
    period = st.selectbox("Periode harga", ["1y", "2y", "5y", "10y"], index=2)
    st.subheader("DCF assumptions")
    years = st.slider("Forecast years", 3, 10, 5)
    growth_pct = st.number_input("Annual FCF growth (%)", -50.0, 100.0, 5.0, 1.0)
    wacc_pct = st.number_input("WACC (%)", 1.0, 100.0, 12.0, 0.5)
    terminal_pct = st.number_input("Terminal growth (%)", -10.0, 20.0, 2.5, 0.5)
    run = st.button("Analyze stock", type="primary", use_container_width=True)
if run:
    try:
        with st.spinner("Mengambil data pasar dan menghitung indikator..."):
            result = analyze_equity(symbol, period)
            dcf = calculate_dcf(result, years, growth_pct/100, wacc_pct/100, terminal_pct/100)
        st.session_state["equity_result"], st.session_state["equity_dcf"] = result, dcf
    except Exception as exc:
        st.error(str(exc))
data, dcf = st.session_state.get("equity_result"), st.session_state.get("equity_dcf")
if data:
    st.subheader(f"{data['company']} · {data['ticker']}")
    c = st.columns(4)
    c[0].metric("Latest price", f"{data['price']:,.2f} {data['currency']}")
    c[1].metric("Daily change", f"{data['change_pct']:.2f}%" if data.get("change_pct") is not None else "N/A")
    c[2].metric("Period return", f"{data['period_return_pct']:.2f}%" if data.get("period_return_pct") is not None else "N/A")
    c[3].metric("Annualized volatility", f"{data['annualized_volatility_pct']:.2f}%" if data.get("annualized_volatility_pct") is not None else "N/A")
    st.caption(f"Harga terakhir: {data.get('latest_price_date','N/A')} · Laporan laba rugi: {data.get('latest_financial_period','N/A')} · Neraca: {data.get('latest_balance_period','N/A')} · Arus kas: {data.get('latest_cashflow_period','N/A')}")
    for warning in data.get("data_quality_warnings", []): st.warning(warning)
    st.info(data["data_quality_note"])
    tab1, tab2, tab3, tab4 = st.tabs(["Overview", "Fundamentals", "Technical", "Valuation"])
    with tab1:
        st.write(f"**Sector:** {data['sector']} · **Industry:** {data['industry']}")
        st.write(f"**Data source:** {data['data_source']} · **Generated:** {data['as_of']}")
        for item in build_research_summary(data): st.write("• " + item)
        st.line_chart(data["history"].set_index("Date")["Close"])
    with tab2:
        st.dataframe([{"Metric": k, "Value": v if v is not None else "N/A"} for k,v in data["ratios"].items()], use_container_width=True, hide_index=True)
    with tab3:
        metrics = {"SMA 20": data["sma20"], "SMA 50": data["sma50"], "SMA 200": data["sma200"], "RSI 14": data["rsi14"]}
        st.dataframe([{"Indicator": k, "Value": v if v is not None else "N/A"} for k,v in metrics.items()], use_container_width=True, hide_index=True)
        st.write("Trend:", data["trend"], "· RSI:", data["rsi_signal"])
    with tab4:
        if dcf and dcf.get("available"):
            st.metric("Illustrative DCF enterprise value", f"{dcf['enterprise_value']:,.2f} {data['currency']}")
            st.dataframe(dcf["forecast"], use_container_width=True, hide_index=True)
            st.caption(dcf["warning"])
            sensitivity = dcf_sensitivity(result, years=years, terminal_growth=terminal_pct/100)
            if sensitivity.get("available"):
                st.subheader("DCF sensitivity · enterprise value")
                st.caption(sensitivity["warning"])
                st.dataframe(sensitivity["matrix"], use_container_width=True, hide_index=True)
            else:
                st.info(sensitivity.get("reason", "Sensitivity not available."))
        else:
            st.info(dcf.get("reason", "Run analysis first.") if dcf else "Run analysis first.")
            if "bank" in (dcf.get("reason", "").lower() if dcf else ""):
                st.write("Untuk bank, evaluasi P/B, ROE, pertumbuhan laba, kualitas aset, NPL, CAR, dan dividend discount/residual income; jangan gunakan DCF FCF generik.")
    col1, col2 = st.columns(2)
    col1.download_button("Download Excel report", make_excel_report(data, dcf), file_name=f"{data['ticker'].replace('.', '_')}_research.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
    col2.download_button("Download PDF report", make_pdf_report(data, dcf), file_name=f"{data['ticker'].replace('.', '_')}_research.pdf", mime="application/pdf", use_container_width=True)
else:
    st.info("Masukkan ticker saham, atur asumsi, lalu klik Analyze stock.")
