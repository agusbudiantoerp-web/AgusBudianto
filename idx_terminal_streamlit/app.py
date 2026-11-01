# IDX Terminal Streamlit — public cloud prototype
# Data from Yahoo Finance; delayed/availability may vary. Not investment advice.

import math
from datetime import date
import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf
import plotly.graph_objects as go

def npf_irr(cashflows):
    # Newton iteration with a bounded fallback scan.
    try:
        x=0.1
        for _ in range(100):
            f=sum(cf/(1+x)**i for i,cf in enumerate(cashflows))
            df=sum(-i*cf/(1+x)**(i+1) for i,cf in enumerate(cashflows) if i)
            if abs(df)<1e-12:break
            nx=x-f/df
            if nx<=-0.999 or not np.isfinite(nx):break
            if abs(nx-x)<1e-8:return nx
            x=nx
    except Exception: pass
    grid=np.linspace(-0.9,5,2000)
    vals=[sum(cf/(1+x)**i for i,cf in enumerate(cashflows)) for x in grid]
    for i in range(len(vals)-1):
        if vals[i]==0 or vals[i]*vals[i+1]<0:
            lo,hi=grid[i],grid[i+1]
            for _ in range(80):
                mid=(lo+hi)/2
                fm=sum(cf/(1+mid)**j for j,cf in enumerate(cashflows))
                fl=sum(cf/(1+lo)**j for j,cf in enumerate(cashflows))
                if fl*fm<=0:hi=mid
                else:lo=mid
            return (lo+hi)/2
    return None


st.set_page_config(page_title="IDX Terminal | Ulil Absyor", page_icon="📈", layout="wide")

EMITEN = {
{'BBCA': ('Bank Central Asia', 'Keuangan', 'Djarum'), 'BBRI': ('Bank Rakyat Indonesia', 'Keuangan', 'BUMN'), 'BMRI': ('Bank Mandiri', 'Keuangan', 'BUMN'), 'BBNI': ('Bank Negara Indonesia', 'Keuangan', 'BUMN'), 'BRIS': ('Bank Syariah Indonesia', 'Keuangan', 'BUMN'), 'ARTO': ('Bank Jago', 'Keuangan', 'Gojek/Tokped'), 'TLKM': ('Telkom Indonesia', 'Infrastruktur', 'BUMN'), 'ISAT': ('Indosat', 'Infrastruktur', 'Ooredoo'), 'EXCL': ('XL Axiata', 'Infrastruktur', 'Axiata'), 'JSMR': ('Jasa Marga', 'Infrastruktur', 'BUMN'), 'TOWR': ('Sarana Menara', 'Infrastruktur', 'Djarum'), 'MTEL': ('Dayamitra Telekom', 'Infrastruktur', 'BUMN'), 'ASII': ('Astra International', 'Industri', 'Jardine/Astra'), 'UNTR': ('United Tractors', 'Energi', 'Jardine/Astra'), 'AUTO': ('Astra Otoparts', 'Konsumer Siklikal', 'Jardine/Astra'), 'ADRO': ('Adaro Andalan', 'Energi', 'Adaro/Alamtri'), 'ADMR': ('Adaro Minerals', 'Energi', 'Adaro/Alamtri'), 'AMMN': ('Amman Mineral', 'Barang Baku', 'Salim/Medco'), 'MEDC': ('Medco Energi', 'Energi', 'Medco'), 'PTBA': ('Bukit Asam', 'Energi', 'BUMN'), 'ITMG': ('Indo Tambangraya', 'Energi', 'Banpu'), 'BUMI': ('Bumi Resources', 'Energi', 'Bakrie'), 'PGAS': ('Perusahaan Gas Negara', 'Energi', 'BUMN'), 'INCO': ('Vale Indonesia', 'Barang Baku', 'MIND ID'), 'ANTM': ('Aneka Tambang', 'Barang Baku', 'MIND ID'), 'MDKA': ('Merdeka Copper Gold', 'Barang Baku', 'Merdeka'), 'MBMA': ('Merdeka Battery', 'Barang Baku', 'Merdeka'), 'TINS': ('Timah', 'Barang Baku', 'MIND ID'), 'BRPT': ('Barito Pacific', 'Barang Baku', 'Prajogo Pangestu'), 'TPIA': ('Chandra Asri', 'Barang Baku', 'Prajogo Pangestu'), 'BREN': ('Barito Renewables', 'Energi', 'Prajogo Pangestu'), 'CUAN': ('Petrindo Jaya Kreasi', 'Energi', 'Prajogo Pangestu'), 'SMGR': ('Semen Indonesia', 'Barang Baku', 'BUMN'), 'INTP': ('Indocement', 'Barang Baku', 'Heidelberg'), 'ICBP': ('Indofood CBP', 'Konsumer Primer', 'Salim'), 'INDF': ('Indofood Sukses Makmur', 'Konsumer Primer', 'Salim'), 'UNVR': ('Unilever Indonesia', 'Konsumer Primer', 'Unilever'), 'KLBF': ('Kalbe Farma', 'Kesehatan', 'Kalbe'), 'CPIN': ('Charoen Pokphand', 'Konsumer Primer', 'CP'), 'MYOR': ('Mayora Indah', 'Konsumer Primer', 'Mayora'), 'GOTO': ('GoTo Gojek Tokopedia', 'Teknologi', 'Gojek/Tokped'), 'EMTK': ('Elang Mahkota Teknologi', 'Teknologi', 'Salim/Sinar Mas'), 'BSDE': ('Bumi Serpong Damai', 'Properti', 'Sinar Mas'), 'SMRA': ('Summarecon', 'Properti', 'Summarecon'), 'CTRA': ('Ciputra Development', 'Properti', 'Ciputra'), 'PWON': ('Pakuwon Jati', 'Properti', 'Pakuwon'), 'ACES': ('Aspirasi Hidup (ACE)', 'Konsumer Siklikal', 'Kawan Lama'), 'MAPI': ('Mitra Adiperkasa', 'Konsumer Siklikal', 'MAP'), 'AKRA': ('AKR Corporindo', 'Energi', 'Lainnya'), 'AMRT': ('Sumber Alfaria Trijaya', 'Konsumer Primer', 'Salim'), 'INKP': ('Indah Kiat Pulp', 'Barang Baku', 'Sinar Mas'), 'PGEO': ('Pertamina Geothermal', 'Energi', 'BUMN'), 'AALI': ('Astra Agro Lestari', 'Konsumer Primer', 'Jardine/Astra'), 'ADHI': ('Adhi Karya', 'Infrastruktur', 'BUMN'), 'ASRI': ('Alam Sutera', 'Properti', 'Lainnya'), 'BBTN': ('Bank Tabungan Negara', 'Keuangan', 'BUMN'), 'BDMN': ('Bank Danamon', 'Keuangan', 'Lainnya'), 'BJBR': ('BPD Jabar Banten', 'Keuangan', 'Daerah'), 'BJTM': ('BPD Jatim', 'Keuangan', 'Daerah'), 'BNGA': ('Bank CIMB Niaga', 'Keuangan', 'Lainnya'), 'BNLI': ('Bank Permata', 'Keuangan', 'Lainnya'), 'BTPS': ('BTPN Syariah', 'Keuangan', 'Lainnya'), 'BUKA': ('Bukalapak', 'Teknologi', 'Lainnya'), 'BYAN': ('Bayan Resources', 'Energi', 'Lainnya'), 'CMRY': ('Cisarua Mountain Dairy', 'Konsumer Primer', 'Lainnya'), 'DEWA': ('Darma Henwa', 'Energi', 'Lainnya'), 'DOID': ('Delta Dunia Makmur', 'Energi', 'Lainnya'), 'DSSA': ('Dian Swastatika Sentosa', 'Energi', 'Sinar Mas'), 'ELSA': ('Elnusa', 'Energi', 'BUMN'), 'ERAA': ('Erajaya Swasembada', 'Konsumer Siklikal', 'Lainnya'), 'ESSA': ('Surya Esa Perkasa', 'Barang Baku', 'Lainnya'), 'FILM': ('MD Pictures', 'Konsumer Siklikal', 'Lainnya'), 'HEAL': ('Medikaloka Hermina', 'Kesehatan', 'Lainnya'), 'HRUM': ('Harum Energy', 'Energi', 'Lainnya'), 'HMSP': ('HM Sampoerna', 'Konsumer Primer', 'Sampoerna/PMI'), 'INDY': ('Indika Energy', 'Energi', 'Lainnya'), 'JPFA': ('Japfa Comfeed', 'Konsumer Primer', 'Lainnya'), 'LPKR': ('Lippo Karawaci', 'Properti', 'Lippo'), 'LSIP': ('PP London Sumatra', 'Konsumer Primer', 'Jardine/Astra'), 'MAPA': ('MAP Aktif Adiperkasa', 'Konsumer Siklikal', 'MAP'), 'MIKA': ('Mitra Keluarga', 'Kesehatan', 'Lainnya'), 'MNCN': ('Media Nusantara Citra', 'Konsumer Siklikal', 'MNC'), 'NCKL': ('Trimegah Bangun Persada', 'Barang Baku', 'Lainnya'), 'PANI': ('Pantai Indah Kapuk Dua', 'Properti', 'Agung Sedayu'), 'PNBN': ('Bank Pan Indonesia', 'Keuangan', 'Lainnya'), 'PTPP': ('PP Persero', 'Infrastruktur', 'BUMN'), 'SCMA': ('Surya Citra Media', 'Konsumer Siklikal', 'Emtek'), 'SIDO': ('Sido Muncul', 'Kesehatan', 'Lainnya'), 'SILO': ('Siloam Hospitals', 'Kesehatan', 'Lippo'), 'SRTG': ('Saratoga Investama', 'Keuangan', 'Lainnya'), 'SSIA': ('Surya Semesta Internusa', 'Properti', 'Lainnya'), 'TBIG': ('Tower Bersama', 'Infrastruktur', 'Lainnya'), 'TKIM': ('Tjiwi Kimia', 'Barang Baku', 'Sinar Mas'), 'WIKA': ('Wijaya Karya', 'Infrastruktur', 'BUMN'), 'BRMS': ('Bumi Resources Minerals', 'Barang Baku', 'Bakrie'), 'ENRG': ('Energi Mega Persada', 'Energi', 'Bakrie'), 'GGRM': ('Gudang Garam', 'Konsumer Primer', 'Lainnya'), 'CBDK': ('Bangun Kosambi Sukses', 'Properti', 'Agung Sedayu'), 'TCPI': ('Transcoal Pacific', 'Energi', 'Lainnya'), 'PNLF': ('Panin Financial', 'Keuangan', 'Lainnya'), 'MLPT': ('Multipolar Technology', 'Teknologi', 'Lippo'), 'BELI': ('Global Digital Niaga', 'Teknologi', 'Lainnya'), 'BMTR': ('Global Mediacom', 'Konsumer Siklikal', 'MNC'), 'AMAR': ('Bank Amar', 'Keuangan', 'Lainnya'), 'BBHI': ('Allo Bank', 'Keuangan', 'Lainnya'), 'SMDR': ('Samudera Indonesia', 'Industri', 'Lainnya'), 'TAPG': ('Triputra Agro Persada', 'Konsumer Primer', 'Lainnya'), 'AVIA': ('Avia Avian', 'Barang Baku', 'Lainnya'), 'ROTI': ('Nippon Indosari', 'Konsumer Primer', 'Lainnya'), 'TBLA': ('Tunas Baru Lampung', 'Konsumer Primer', 'Lainnya'), 'BIRD': ('Blue Bird', 'Industri', 'Lainnya'), 'ASSA': ('Adi Sarana Armada', 'Industri', 'Lainnya'), 'GJTL': ('Gajah Tunggal', 'Konsumer Siklikal', 'Lainnya'), 'ISSP': ('Steel Pipe Industry', 'Barang Baku', 'Lainnya'), 'KRAS': ('Krakatau Steel', 'Barang Baku', 'BUMN'), 'IMAS': ('Indomobil Sukses Internasional', 'Konsumer Siklikal', 'Indomobil')}
}

TICKERS = {k: k + ".JK" for k in EMITEN}
SECTORS = sorted({v[1] for v in EMITEN.values()})

@st.cache_data(ttl=300, show_spinner=False)
def load_market_data(period="1y"):
    symbols = ["^JKSE"] + list(TICKERS.values())
    # Batch downloads are more efficient than one request per ticker.
    frames = []
    for start in range(0, len(symbols), 15):
        batch = symbols[start:start+15]
        try:
            raw = yf.download(batch, period=period, interval="1d",
                             auto_adjust=True, group_by="ticker",
                             progress=False, threads=True)
            if raw is not None and not raw.empty:
                frames.append(raw)
        except Exception:
            pass
    return frames

def extract_series(frames, ticker, field="Close"):
    vals=[]
    for df in frames:
        if isinstance(df.columns, pd.MultiIndex):
            if (ticker, field) in df.columns:
                vals.append(df[(ticker, field)].dropna())
            elif (field, ticker) in df.columns:
                vals.append(df[(field, ticker)].dropna())
        elif field in df.columns and ticker in TICKERS.values():
            vals.append(df[field].dropna())
    if not vals:
        return pd.Series(dtype=float)
    out=pd.concat(vals).sort_index()
    return out[~out.index.duplicated(keep="last")].dropna()

def market_table(frames):
    rows=[]
    for code,(name,sector,group) in EMITEN.items():
        ticker=TICKERS[code]
        close=extract_series(frames,ticker,"Close")
        vol=extract_series(frames,ticker,"Volume")
        if len(close)<2: continue
        last=float(close.iloc[-1]); prev=float(close.iloc[-2])
        change=(last/prev-1)*100 if prev else np.nan
        ret3=(last/close.iloc[-min(63,len(close))]-1)*100 if len(close)>2 else np.nan
        avgvol=float(vol.tail(20).mean()) if len(vol) else np.nan
        vr=float(vol.iloc[-1]/avgvol) if avgvol else np.nan
        high=float(close.tail(252).max()) if len(close) else np.nan
        rows.append({"Kode":code,"Nama":name,"Sektor":sector,"Grup":group,
                     "Harga":last,"% Harian":change,"Return 3B (%)":ret3,
                     "Volume":float(vol.iloc[-1]) if len(vol) else np.nan,
                     "Vol / Avg20":vr,"Jarak High 52W (%)":(last/high-1)*100 if high else np.nan})
    return pd.DataFrame(rows)

def metric_card(label,value,delta=None):
    st.metric(label,value,delta)

def fmt_rp(x):
    try:return f"Rp {x:,.0f}".replace(",",".")
    except:return "—"

st.title("🇮🇩 IDX Terminal")
st.caption("Market intelligence & financial engineering laboratory · Prototype publik")
st.warning("Data bersumber dari Yahoo Finance (bukan data resmi IDX). Data dapat terlambat, tidak lengkap, atau gagal dimuat. Bukan rekomendasi investasi.", icon="⚠️")

with st.sidebar:
    st.header("Pengaturan")
    period=st.selectbox("Riwayat data",["1y","6mo","3mo"],index=0)
    st.caption("Cache data 5 menit untuk mengurangi permintaan ke sumber data.")

with st.spinner("Mengambil data pasar dari Yahoo Finance… (pertama kali dapat memerlukan beberapa menit)"):
    frames=load_market_data(period)
    ihsg=extract_series(frames,"^JKSE","Close")
    df=market_table(frames)

if df.empty:
    st.error("Data belum berhasil dimuat. Coba Refresh atau tunggu beberapa saat.")
    st.stop()

tabs=st.tabs(["📊 Pasar & Screener","🔎 Detail Emiten","🧠 AI Quant Lab","📑 Equity Research","⛏️ Mining Finance","🏗️ Project Control","📚 GitHub Projects"])

with tabs[0]:
    c1,c2,c3,c4=st.columns(4)
    if len(ihsg)>=2:
        pct=(ihsg.iloc[-1]/ihsg.iloc[-2]-1)*100
        c1.metric("IHSG",f"{ihsg.iloc[-1]:,.2f}",f"{pct:+.2f}%")
    else:c1.metric("IHSG","N/A")
    c2.metric("Emiten terdata",f"{len(df)}")
    c3.metric("Naik",f"{(df['% Harian']>0).sum()}")
    c4.metric("Turun",f"{(df['% Harian']<0).sum()}")
    st.subheader("Screener Saham")
    f1,f2,f3=st.columns([2,1,1])
    query=f1.text_input("Cari kode / nama",placeholder="BBCA, BBRI, Adaro…")
    sector=f2.selectbox("Sektor",["Semua"]+SECTORS)
    signal=f3.selectbox("Filter",["Semua","Naik","Turun","Volume ≥ 2x"])
    view=df.copy()
    if query:
        view=view[view["Kode"].str.contains(query.upper(),case=False)|view["Nama"].str.contains(query,case=False,na=False)]
    if sector!="Semua":view=view[view["Sektor"]==sector]
    if signal=="Naik":view=view[view["% Harian"]>0]
    elif signal=="Turun":view=view[view["% Harian"]<0]
    elif signal=="Volume ≥ 2x":view=view[view["Vol / Avg20"]>=2]
    sortby=st.selectbox("Urutkan",["% Harian","Return 3B (%)","Vol / Avg20","Jarak High 52W (%)"])
    view=view.sort_values(sortby,ascending=False,na_position="last")
    st.dataframe(view,hide_index=True,use_container_width=True,
                 column_config={"Harga":st.column_config.NumberColumn(format="Rp %.0f"),
                               "% Harian":st.column_config.NumberColumn(format="%.2f%%"),
                               "Return 3B (%)":st.column_config.NumberColumn(format="%.2f%%"),
                               "Vol / Avg20":st.column_config.NumberColumn(format="%.2fx"),
                               "Jarak High 52W (%)":st.column_config.NumberColumn(format="%.2f%%")})
    st.download_button("⬇️ Download screener CSV",view.to_csv(index=False).encode("utf-8-sig"),
                      "idx_screener.csv","text/csv")

with tabs[1]:
    codes=sorted(df["Kode"].tolist())
    selected=st.selectbox("Pilih emiten",codes,index=codes.index("BBCA") if "BBCA" in codes else 0)
    row=df[df["Kode"]==selected].iloc[0]
    a,b,c=st.columns(3)
    a.metric("Harga",fmt_rp(row["Harga"]),f'{row["% Harian"]:+.2f}%')
    b.metric("Return 3 bulan",f'{row["Return 3B (%)"]:+.2f}%')
    c.metric("Volume / Avg20",f'{row["Vol / Avg20"]:.2f}x' if pd.notna(row["Vol / Avg20"]) else "N/A")
    close=extract_series(frames,TICKERS[selected],"Close")
    if not close.empty:
        fig=go.Figure()
        fig.add_trace(go.Scatter(x=close.index,y=close.values,mode="lines",name="Adjusted Close"))
        fig.update_layout(title=f"{selected} — Price history",height=420,xaxis_title="",yaxis_title="IDR",template="plotly_dark")
        st.plotly_chart(fig,use_container_width=True)
    st.subheader("Snapshot indikator teknikal")
    if len(close)>=50:
        sma20=close.rolling(20).mean().iloc[-1]
        sma50=close.rolling(50).mean().iloc[-1]
        delta=close.diff()
        gain=delta.clip(lower=0).rolling(14).mean().iloc[-1]
        loss=(-delta.clip(upper=0)).rolling(14).mean().iloc[-1]
        rsi=100 if loss==0 else 100-100/(1+gain/loss)
        x,y,z=st.columns(3)
        x.metric("SMA 20",fmt_rp(sma20), "Di atas" if row["Harga"]>sma20 else "Di bawah")
        y.metric("SMA 50",fmt_rp(sma50), "Di atas" if row["Harga"]>sma50 else "Di bawah")
        z.metric("RSI 14",f"{rsi:.1f}", "Overbought" if rsi>=70 else ("Oversold" if rsi<=30 else "Neutral"))
    st.info("Fundamental, foreign flow, broker summary, dan ownership membutuhkan sumber data terpisah/unggahan. Tidak ditampilkan sebagai data real-time otomatis pada prototype ini.")

with tabs[2]:
    st.subheader("AI Quant Lab")
    st.markdown("Laboratorium demonstrasi screening faktor, return historis, dan optimasi portofolio.")
    st.caption("Versi awal: menggunakan return historis, bukan prediksi AI atau sinyal trading.")
    selected_codes=st.multiselect("Pilih saham untuk portfolio",sorted(df["Kode"].tolist()),default=[x for x in ["BBCA","BMRI","BBRI","TLKM","ASII"] if x in df["Kode"].tolist()])
    if len(selected_codes)>=2:
        retlist=[]
        for code in selected_codes:
            s=extract_series(frames,TICKERS[code],"Close").pct_change().dropna()
            s.name=code;retlist.append(s)
        returns=pd.concat(retlist,axis=1).dropna()
        ann_ret=returns.mean()*252
        cov=returns.cov()*252
        n=len(selected_codes)
        weights=np.repeat(1/n,n)
        p_ret=float(weights@ann_ret.values)
        p_vol=float(np.sqrt(weights@cov.values@weights))
        st.write("**Equal-weight portfolio (baseline)**")
        k1,k2,k3=st.columns(3)
        k1.metric("Estimasi return tahunan",f"{p_ret*100:.2f}%")
        k2.metric("Volatilitas tahunan",f"{p_vol*100:.2f}%")
        k3.metric("Sharpe (rf=0)",f"{p_ret/p_vol:.2f}" if p_vol else "N/A")
        st.dataframe(pd.DataFrame({"Kode":selected_codes,"Bobot baseline":weights}),hide_index=True)
        st.line_chart((1+returns).cumprod(),height=320)
        st.download_button("Download return harian CSV",returns.to_csv().encode(),"portfolio_returns.csv","text/csv")
    else: st.info("Pilih minimal dua saham.")
    st.warning("Optimasi bobot, Monte Carlo, backtesting dan machine learning akan menjadi pengembangan berikutnya. Hasil historis bukan jaminan return masa depan.")

with tabs[3]:
    st.subheader("IDX Equity Research AI")
    code=st.selectbox("Emiten untuk ringkasan riset",sorted(df["Kode"].tolist()),key=lambda x: (x!="BBCA",x))
    r=df[df["Kode"]==code].iloc[0]
    close=extract_series(frames,TICKERS[code],"Close")
    st.markdown(f"### {r['Nama']} ({code})")
    st.write(f"Sektor: **{r['Sektor']}**")
    st.write(f"Harga terakhir: **{fmt_rp(r['Harga'])}** | Return harian **{r['% Harian']:+.2f}%** | Return 3 bulan **{r['Return 3B (%)']:+.2f}%**")
    if len(close)>=50:
        s20=close.rolling(20).mean().iloc[-1]; s50=close.rolling(50).mean().iloc[-1]
        mom="Bullish" if r["Harga"]>s20>s50 else ("Bearish" if r["Harga"]<s20<s50 else "Mixed / sideways")
        st.write(f"**Trend teknikal sederhana:** {mom}")
    report=f"""# Ringkasan IDX Equity Research — {code}
Tanggal: {date.today().isoformat()}

- Emiten: {r['Nama']}
- Sektor: {r['Sektor']}
- Harga terakhir: {r['Harga']:.2f}
- Return harian: {r['% Harian']:.2f}%
- Return 3 bulan: {r['Return 3B (%)']:.2f}%
- Volume / rata-rata 20 hari: {r['Vol / Avg20']:.2f}x
- Jarak dari high 52 minggu: {r['Jarak High 52W (%)']:.2f}%

Catatan: ringkasan kuantitatif berbasis data historis. Bukan rekomendasi investasi.
Fundamental, laporan keuangan, foreign flow, broker summary, dan katalis belum diverifikasi.
"""
    st.download_button("📥 Unduh ringkasan riset (.md)",report, f"research_{code}.md","text/markdown")
    st.info("Versi lanjutan: laporan PDF/Excel, financial statement analysis, foreign flow, broker, AI narrative, dan audit sumber.")

with tabs[4]:
    st.subheader("Mining Financial Engineering")
    st.caption("Kalkulator proyek sederhana — input asumsi Anda sendiri.")
    col1,col2=st.columns(2)
    capex=col1.number_input("Initial CAPEX (Rp)",min_value=0.0,value=100_000_000_000.0,step=1_000_000_000.0)
    years=col2.number_input("Durasi proyek (tahun)",min_value=1,max_value=30,value=5)
    rate=col1.number_input("Discount rate (%)",min_value=0.0,max_value=100.0,value=12.0)/100
    annual_cf=col2.number_input("Net annual cash flow (Rp)",value=35_000_000_000.0,step=1_000_000_000.0)
    cfs=[-capex]+[annual_cf]*int(years)
    npv=sum(cf/((1+rate)**i) for i,cf in enumerate(cfs))
    irr=npf_irr(cfs)
    m,n=st.columns(2)
    m.metric("NPV",fmt_rp(npv))
    n.metric("IRR",f"{irr*100:.2f}%" if irr is not None else "Tidak konvergen")
    st.subheader("Sensitivitas cash flow")
    mults=np.arange(0.6,1.41,0.1)
    sens=pd.DataFrame({"Cash flow multiplier":mults,
        "NPV":[sum((cf*mult if i else cf)/((1+rate)**i) for i,cf in enumerate(cfs)) for mult in mults]})
    st.line_chart(sens.set_index("Cash flow multiplier"))
    st.dataframe(sens,use_container_width=True,hide_index=True)
    st.caption("Belum termasuk pajak, working capital, terminal value, eskalasi biaya, royalty, dan jadwal produksi.")

with tabs[5]:
    st.subheader("AI Project Control")
    st.caption("Earned Value Management (EVM) — input proyek")
    p1,p2,p3=st.columns(3)
    pv=p1.number_input("Planned Value (PV)",min_value=0.0,value=1_000_000_000.0)
    ev=p2.number_input("Earned Value (EV)",min_value=0.0,value=900_000_000.0)
    ac=p3.number_input("Actual Cost (AC)",min_value=0.0,value=1_050_000_000.0)
    spi=ev/pv if pv else np.nan
    cpi=ev/ac if ac else np.nan
    eac=ac/cpi if cpi and not np.isnan(cpi) else np.nan
    vac=pv-eac if not np.isnan(eac) else np.nan
    q1,q2,q3,q4=st.columns(4)
    q1.metric("SPI",f"{spi:.3f}" if not np.isnan(spi) else "N/A")
    q2.metric("CPI",f"{cpi:.3f}" if not np.isnan(cpi) else "N/A")
    q3.metric("EAC",fmt_rp(eac) if not np.isnan(eac) else "N/A")
    q4.metric("VAC (BAC−EAC)",fmt_rp(vac) if not np.isnan(vac) else "N/A")
    st.write("Interpretasi dasar: SPI < 1 berarti progres tertinggal dari rencana; CPI < 1 berarti biaya aktual melebihi nilai pekerjaan yang diperoleh.")
    bac=st.number_input("Budget at Completion (BAC)",min_value=0.0,value=2_000_000_000.0)
    st.write(f"Forecast EAC berbasis CPI: **{fmt_rp(bac/cpi) if cpi else 'N/A'}**")
    st.info("Pengembangan berikutnya: schedule integration, critical path, resource loading, Monte Carlo, risk register, dan Primavera.")

with tabs[6]:
    st.subheader("GitHub Projects")
    st.markdown("Repository sumber dan dokumentasi untuk demonstrasi tools.")
    st.markdown("- [IDX Terminal Repository](https://github.com/agusbudiantoerp-web/ulilabsyor)")
    st.markdown("- [Financial Engineering AI Lab](https://github.com/agusbudiantoerp-web)")
    st.caption("Tambahkan link repository spesifik setiap modul setelah source code dipisahkan dan didokumentasikan.")

