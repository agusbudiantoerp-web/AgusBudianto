"""IDX Terminal - server lokal. Jalankan: python server.py  ->  http://localhost:8000
Hanya butuh Python 3.8+ (tanpa pip install). Data: Yahoo Finance (.JK), di-refresh tiap 5 detik."""
import json, time, threading, urllib.request, urllib.parse, http.cookiejar
from concurrent.futures import ThreadPoolExecutor
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

# kode: (nama, sektor, grup konglomerasi)
EMITEN = {
 "BBCA":("Bank Central Asia","Keuangan","Djarum"),"BBRI":("Bank Rakyat Indonesia","Keuangan","BUMN"),
 "BMRI":("Bank Mandiri","Keuangan","BUMN"),"BBNI":("Bank Negara Indonesia","Keuangan","BUMN"),
 "BRIS":("Bank Syariah Indonesia","Keuangan","BUMN"),"ARTO":("Bank Jago","Keuangan","Gojek/Tokped"),
 "TLKM":("Telkom Indonesia","Infrastruktur","BUMN"),"ISAT":("Indosat","Infrastruktur","Ooredoo"),
 "EXCL":("XL Axiata","Infrastruktur","Axiata"),"JSMR":("Jasa Marga","Infrastruktur","BUMN"),
 "TOWR":("Sarana Menara","Infrastruktur","Djarum"),"MTEL":("Dayamitra Telekom","Infrastruktur","BUMN"),
 "ASII":("Astra International","Industri","Jardine/Astra"),"UNTR":("United Tractors","Energi","Jardine/Astra"),
 "AUTO":("Astra Otoparts","Konsumer Siklikal","Jardine/Astra"),
 "ADRO":("Adaro Andalan","Energi","Adaro/Alamtri"),"ADMR":("Adaro Minerals","Energi","Adaro/Alamtri"),
 "AMMN":("Amman Mineral","Barang Baku","Salim/Medco"),"MEDC":("Medco Energi","Energi","Medco"),
 "PTBA":("Bukit Asam","Energi","BUMN"),"ITMG":("Indo Tambangraya","Energi","Banpu"),
 "BUMI":("Bumi Resources","Energi","Bakrie"),"PGAS":("Perusahaan Gas Negara","Energi","BUMN"),
 "INCO":("Vale Indonesia","Barang Baku","MIND ID"),"ANTM":("Aneka Tambang","Barang Baku","MIND ID"),
 "MDKA":("Merdeka Copper Gold","Barang Baku","Merdeka"),"MBMA":("Merdeka Battery","Barang Baku","Merdeka"),
 "TINS":("Timah","Barang Baku","MIND ID"),"BRPT":("Barito Pacific","Barang Baku","Prajogo Pangestu"),
 "TPIA":("Chandra Asri","Barang Baku","Prajogo Pangestu"),"BREN":("Barito Renewables","Energi","Prajogo Pangestu"),
 "CUAN":("Petrindo Jaya Kreasi","Energi","Prajogo Pangestu"),
 "SMGR":("Semen Indonesia","Barang Baku","BUMN"),"INTP":("Indocement","Barang Baku","Heidelberg"),
 "ICBP":("Indofood CBP","Konsumer Primer","Salim"),"INDF":("Indofood Sukses Makmur","Konsumer Primer","Salim"),
 "UNVR":("Unilever Indonesia","Konsumer Primer","Unilever"),"KLBF":("Kalbe Farma","Kesehatan","Kalbe"),
 "CPIN":("Charoen Pokphand","Konsumer Primer","CP"),"MYOR":("Mayora Indah","Konsumer Primer","Mayora"),
 "GOTO":("GoTo Gojek Tokopedia","Teknologi","Gojek/Tokped"),"EMTK":("Elang Mahkota Teknologi","Teknologi","Salim/Sinar Mas"),
 "BSDE":("Bumi Serpong Damai","Properti","Sinar Mas"),"SMRA":("Summarecon","Properti","Summarecon"),
 "CTRA":("Ciputra Development","Properti","Ciputra"),"PWON":("Pakuwon Jati","Properti","Pakuwon"),
 "ACES":("Aspirasi Hidup (ACE)","Konsumer Siklikal","Kawan Lama"),"MAPI":("Mitra Adiperkasa","Konsumer Siklikal","MAP"),
}

TAMBAHAN = """AKRA|AKR Corporindo|Energi;AMRT|Sumber Alfaria Trijaya|Konsumer Primer|Salim;INKP|Indah Kiat Pulp|Barang Baku|Sinar Mas;PGEO|Pertamina Geothermal|Energi|BUMN;
AALI|Astra Agro Lestari|Konsumer Primer|Jardine/Astra;ADHI|Adhi Karya|Infrastruktur|BUMN;ASRI|Alam Sutera|Properti;BBTN|Bank Tabungan Negara|Keuangan|BUMN;BDMN|Bank Danamon|Keuangan;
BJBR|BPD Jabar Banten|Keuangan|Daerah;BJTM|BPD Jatim|Keuangan|Daerah;BNGA|Bank CIMB Niaga|Keuangan;BNLI|Bank Permata|Keuangan;BTPS|BTPN Syariah|Keuangan;BUKA|Bukalapak|Teknologi;
BYAN|Bayan Resources|Energi;CMRY|Cisarua Mountain Dairy|Konsumer Primer;DEWA|Darma Henwa|Energi;DOID|Delta Dunia Makmur|Energi;DSSA|Dian Swastatika Sentosa|Energi|Sinar Mas;
ELSA|Elnusa|Energi|BUMN;ERAA|Erajaya Swasembada|Konsumer Siklikal;ESSA|Surya Esa Perkasa|Barang Baku;FILM|MD Pictures|Konsumer Siklikal;HEAL|Medikaloka Hermina|Kesehatan;
HRUM|Harum Energy|Energi;HMSP|HM Sampoerna|Konsumer Primer|Sampoerna/PMI;INDY|Indika Energy|Energi;JPFA|Japfa Comfeed|Konsumer Primer;LPKR|Lippo Karawaci|Properti|Lippo;
LSIP|PP London Sumatra|Konsumer Primer|Jardine/Astra;MAPA|MAP Aktif Adiperkasa|Konsumer Siklikal|MAP;MIKA|Mitra Keluarga|Kesehatan;MNCN|Media Nusantara Citra|Konsumer Siklikal|MNC;
NCKL|Trimegah Bangun Persada|Barang Baku;PANI|Pantai Indah Kapuk Dua|Properti|Agung Sedayu;PNBN|Bank Pan Indonesia|Keuangan;PTPP|PP Persero|Infrastruktur|BUMN;
SCMA|Surya Citra Media|Konsumer Siklikal|Emtek;SIDO|Sido Muncul|Kesehatan;SILO|Siloam Hospitals|Kesehatan|Lippo;SRTG|Saratoga Investama|Keuangan;SSIA|Surya Semesta Internusa|Properti;
TBIG|Tower Bersama|Infrastruktur;TKIM|Tjiwi Kimia|Barang Baku|Sinar Mas;WIKA|Wijaya Karya|Infrastruktur|BUMN;BRMS|Bumi Resources Minerals|Barang Baku|Bakrie;ENRG|Energi Mega Persada|Energi|Bakrie;
GGRM|Gudang Garam|Konsumer Primer;CBDK|Bangun Kosambi Sukses|Properti|Agung Sedayu;TCPI|Transcoal Pacific|Energi;PNLF|Panin Financial|Keuangan;MLPT|Multipolar Technology|Teknologi|Lippo;
BELI|Global Digital Niaga|Teknologi;BMTR|Global Mediacom|Konsumer Siklikal|MNC;AMAR|Bank Amar|Keuangan;BBHI|Allo Bank|Keuangan;SMDR|Samudera Indonesia|Industri;TAPG|Triputra Agro Persada|Konsumer Primer;
AVIA|Avia Avian|Barang Baku;ROTI|Nippon Indosari|Konsumer Primer;TBLA|Tunas Baru Lampung|Konsumer Primer;BIRD|Blue Bird|Industri;ASSA|Adi Sarana Armada|Industri;GJTL|Gajah Tunggal|Konsumer Siklikal;
ISSP|Steel Pipe Industry|Barang Baku;KRAS|Krakatau Steel|Barang Baku|BUMN;IMAS|Indomobil Sukses Internasional|Konsumer Siklikal|Indomobil"""
for x in TAMBAHAN.replace("\n","").split(";"):
    p = x.strip().split("|")
    if len(p) >= 3 and p[0] not in EMITEN: EMITEN[p[0]] = (p[1], p[2], p[3] if len(p) > 3 else "Lainnya")

# Keanggotaan indeks: PERKIRAAN. Edit/timpa dengan file indeks.json (lihat README) setelah cek rilis resmi IDX / Kompas.
IDX30 = "ADRO AKRA AMMN AMRT ANTM ARTO ASII BBCA BBNI BBRI BMRI BRIS BRPT CPIN EXCL GOTO ICBP INCO INDF INKP ISAT KLBF MDKA MEDC PGAS PTBA SMGR TLKM UNTR UNVR".split()
JII = "ADRO AKRA AMMN ANTM BRIS BRPT CPIN CTRA EXCL ICBP INCO INDF INKP INTP ISAT ITMG KLBF MAPI MBMA MDKA MEDC MTEL MYOR PGAS PTBA SMGR TLKM TPIA UNTR UNVR".split()
NOT_K100 = set("BMTR FILM DEWA ENRG AVIA ISSP KRAS GJTL IMAS MLPT BELI AMAR BBHI PNLF TCPI ROTI TBLA BIRD ASSA SMDR AUTO".split())
KOMPAS100 = [k for k in EMITEN if k not in NOT_K100]
INDICES = {"IDX30": IDX30, "JII": JII, "KOMPAS100": KOMPAS100}
import os
try: INDICES.update(json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "indeks.json"))))
except Exception: pass

INDEX = "^JKSE"
STATE = {"index": None, "stocks": {}, "ts": 0}

def fetch(sym):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d&range=3mo"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        r = json.load(urllib.request.urlopen(req, timeout=8))["chart"]["result"][0]
        m = r["meta"]; q = r["indicators"]["quote"][0]
        cl = [c for c in q["close"] if c]; vs = [v for v in q["volume"] if v][:-1][-20:]
        avgv = sum(vs) / len(vs) if vs else 0
        px = m["regularMarketPrice"]; prev = m.get("chartPreviousClose") or (cl[-2] if len(cl) > 1 else px)
        vol = m.get("regularMarketVolume", 0)
        return {"price": px, "prev": prev, "chg": px - prev, "pct": (px / prev - 1) * 100 if prev else 0, "vol": vol,
                "avgv": avgv, "vr": vol / avgv if avgv else 0, "hi52": m.get("fiftyTwoWeekHigh"), "lo52": m.get("fiftyTwoWeekLow"),
                "r3m": (px / cl[0] - 1) * 100 if cl else 0, "t": m.get("regularMarketTime"), "spark": cl[-30:]}
    except Exception as e:
        return {"error": str(e)}

def refresher():  # latar belakang: seluruh emiten diperbarui terus-menerus
    syms = [INDEX] + [k + ".JK" for k in EMITEN]
    while True:
        with ThreadPoolExecutor(20) as ex: res = list(ex.map(fetch, syms))
        if "error" not in res[0]: STATE["index"] = res[0]
        for k, d in zip(EMITEN, res[1:]):
            if "error" not in d: STATE["stocks"][k] = {**d, "name": EMITEN[k][0], "sector": EMITEN[k][1], "group": EMITEN[k][2]}
        STATE["ts"] = time.time(); time.sleep(2)

def snapshot():
    for _ in range(40):
        if STATE["index"] and STATE["stocks"]: break
        time.sleep(0.5)
    return {"index": STATE["index"] or {"price": 0, "chg": 0, "pct": 0, "r3m": 0}, "stocks": STATE["stocks"], "indices": INDICES, "server_time": int(time.time())}

CJ = http.cookiejar.CookieJar()
OP = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CJ)); OP.addheaders = [("User-Agent", "Mozilla/5.0")]
CRUMB = {"v": None, "t": 0}; DCACHE = {}
def crumb():
    if CRUMB["v"] and time.time() - CRUMB["t"] < 3600: return CRUMB["v"]
    try: OP.open("https://fc.yahoo.com", timeout=8)
    except Exception: pass
    CRUMB["v"] = OP.open("https://query2.finance.yahoo.com/v1/test/getcrumb", timeout=8).read().decode(); CRUMB["t"] = time.time()
    return CRUMB["v"]
def jget(u): return json.load(OP.open(u, timeout=10))
def safe(f, *a):
    try: return f(*a)
    except Exception as e: return {"error": str(e)}
def chart(sym, rng, itv):
    r = jget(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval={itv}&range={rng}")["chart"]["result"][0]
    q = r["indicators"]["quote"][0]
    return {"t": r.get("timestamp", []), "o": q["open"], "h": q["high"], "l": q["low"], "c": q["close"], "v": q["volume"], "prev": r["meta"].get("chartPreviousClose")}
def summary(sym):
    mods = "assetProfile,summaryDetail,defaultKeyStatistics,financialData,majorHoldersBreakdown,institutionOwnership,fundOwnership"
    try:
        return jget(f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{sym}?modules={mods}&crumb={urllib.parse.quote(crumb())}")["quoteSummary"]["result"][0]
    except Exception as e:
        CRUMB["v"] = None; return {"error": str(e)}
def news(sym):
    n = jget(f"https://query1.finance.yahoo.com/v1/finance/search?q={sym}&newsCount=8&quotesCount=0").get("news", [])
    return [{"title": x.get("title"), "pub": x.get("publisher"), "link": x.get("link"), "t": x.get("providerPublishTime")} for x in n]
def detail(k):
    c = DCACHE.get(k)
    if c and time.time() - c[0] < 10: return c[1]
    sym = k + ".JK"
    with ThreadPoolExecutor(5) as ex:
        fs = {"daily": ex.submit(safe, chart, sym, "1y", "1d"), "intra": ex.submit(safe, chart, sym, "1d", "5m"),
              "summary": ex.submit(safe, summary, sym), "news": ex.submit(safe, news, sym)}
        d = {n: f.result() for n, f in fs.items()}
    DCACHE[k] = (time.time(), d); return d

import re, html, email.utils, xml.etree.ElementTree as ET
def gn(q, reg):
    hl, gl, ce = ("id", "ID", "ID:id") if reg == "ID" else ("en-US", "US", "US:en")
    return f"https://news.google.com/rss/search?q={urllib.parse.quote(q)}&hl={hl}&gl={gl}&ceid={ce}"
SUMBER = [  # (nama, wilayah, [url dicoba berurutan; yang pertama berisi berita dipakai])
 ("Bisnis.com", "ID", ["https://www.bisnis.com/rss", gn("site:bisnis.com when:2d", "ID")]),
 ("The Investor", "ID", [gn("site:investor.id when:2d", "ID")]),
 ("CNBC Indonesia", "ID", ["https://www.cnbcindonesia.com/market/rss", gn("site:cnbcindonesia.com when:2d", "ID")]),
 ("CNN Indonesia", "ID", ["https://www.cnnindonesia.com/ekonomi/rss", gn("site:cnnindonesia.com ekonomi when:2d", "ID")]),
 ("Kontan", "ID", [gn("site:kontan.co.id when:2d", "ID")]),
 ("CNBC", "INT", ["https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664", gn("site:cnbc.com when:1d", "INT")]),
 ("CNN", "INT", ["http://rss.cnn.com/rss/money_news_international.rss", gn("site:cnn.com business when:1d", "INT")]),
 ("Bloomberg", "INT", ["https://feeds.bloomberg.com/markets/news.rss", gn("site:bloomberg.com when:1d", "INT")]),
 ("Reuters", "INT", [gn("site:reuters.com markets when:1d", "INT")]),
]
def rss(url):
    data = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=8).read()
    out = []
    for it in ET.fromstring(data).iter("item"):
        try: t = int(email.utils.parsedate_to_datetime(it.findtext("pubDate")).timestamp())
        except Exception: t = 0
        s = it.find("source")
        out.append({"title": html.unescape(re.sub("<[^>]+>", "", (it.findtext("title") or "").strip())), "link": (it.findtext("link") or "").strip(), "t": t, "src": s.text if s is not None else None})
    return [x for x in out if x["title"] and x["link"]]
def one_source(sp):
    nama, reg, urls = sp
    for u in urls:
        try:
            r = rss(u)[:25]
            if r:
                for x in r: x["src"] = nama; x["reg"] = reg
                return nama, r, "rss" if "google" not in u else "google"
        except Exception: pass
    return nama, [], "gagal"
NC = {"t": 0, "d": None}; NK = {}
def news_all():
    if NC["d"] and time.time() - NC["t"] < 120: return NC["d"]
    with ThreadPoolExecutor(9) as ex: res = list(ex.map(one_source, SUMBER))
    items = sorted([x for _, r, _ in res for x in r], key=lambda x: -x["t"])
    NC.update(t=time.time(), d={"items": items, "status": {n: {"n": len(r), "via": v} for n, r, v in res}}); return NC["d"]
def news_emiten(k):
    c = NK.get(k)
    if c and time.time() - c[0] < 120: return c[1]
    nama = EMITEN[k][0]
    try: r = rss(gn(f'"{nama}" OR "{k}" saham when:14d', "ID"))[:20]
    except Exception: r = []
    for x in r: x["reg"] = "ID"; x["src"] = x["src"] or "Google News"
    r.sort(key=lambda x: -x["t"]); NK[k] = (time.time(), {"items": r}); return NK[k][1]

# ---------- Data impor: pemegang saham & broker summary (CSV) ----------
import csv, io, datetime
DDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
BROKERS = {  # kode: (nama, A=asing / L=lokal). Periksa & ubah sesuai daftar anggota bursa terbaru.
 "YP":("Mirae Asset","L"),"PD":("Indo Premier","L"),"CC":("Mandiri Sekuritas","L"),"NI":("BNI Sekuritas","L"),"OD":("BRI Danareksa","L"),
 "SQ":("BCA Sekuritas","L"),"LG":("Trimegah","L"),"KI":("Ciptadana","L"),"HP":("Henan Putihrai","L"),"EP":("MNC Sekuritas","L"),
 "XL":("Stockbit Sekuritas","L"),"XC":("Ajaib Sekuritas","L"),"DH":("Sinarmas Sekuritas","L"),"IF":("Samuel Sekuritas","L"),"PP":("Aldiracita","L"),
 "AZ":("Sucor Sekuritas","L"),"MG":("Semesta Indovest","L"),"GR":("Panin Sekuritas","L"),"CP":("KB Valbury","L"),"DX":("Bahana Sekuritas","L"),
 "SS":("Supra Sekuritas","L"),"IN":("Investindo Nusantara","L"),"CD":("Mega Capital","L"),"LS":("Reliance Sekuritas","L"),"AO":("Erdikha Elit","L"),
 "AI":("UOB Kay Hian","A"),"KZ":("CLSA Indonesia","A"),"ZP":("Maybank Sekuritas","A"),"YU":("CGS International","A"),"BK":("J.P. Morgan","A"),
 "AK":("UBS","A"),"RX":("Macquarie","A"),"MS":("Morgan Stanley","A"),"GW":("HSBC","A"),"DR":("RHB Sekuritas","A"),"TP":("OCBC Sekuritas","A"),
 "FS":("Yuanta","A"),"BQ":("Korea Investment & Sekuritas","A")}
ALIAS = {
 "holders": {"kode":["kode","ticker","kode_saham","emiten"],"pemegang":["pemegang","nama","holder","name","pemegang_saham"],"jenis":["jenis","tipe","type","kategori"],
             "persen":["persen","%","persentase","pct","percent"],"lembar":["lembar","jumlah_saham","shares","jumlah","lembar_saham"],"tanggal":["tanggal","date","periode"]},
 "broker": {"kode":["kode","ticker","kode_saham","emiten"],"tanggal":["tanggal","date"],"broker":["broker","kode_broker","code","brokers"],
            "buy_lot":["buy_lot","blot","lot_beli","buylot"],"buy_val":["buy_val","bval","nilai_beli","buyval","buy_value"],
            "sell_lot":["sell_lot","slot","lot_jual","selllot"],"sell_val":["sell_val","sval","nilai_jual","sellval","sell_value"]}}
NUMF = {"holders": ["persen", "lembar"], "broker": ["buy_lot", "buy_val", "sell_lot", "sell_val"]}
FIELDS = {"holders": ["kode","tanggal","pemegang","jenis","persen","lembar"], "broker": ["kode","tanggal","broker","buy_lot","buy_val","sell_lot","sell_val"]}
KEYS = {"holders": ("kode","tanggal","pemegang"), "broker": ("kode","tanggal","broker")}
def num(x):
    x = re.sub(r"[^\d,.\-]", "", str(x or "")).strip()
    if not x or x in "-.,": return 0.0
    if "," in x and "." in x:
        x = x.replace(",", "") if x.rfind(".") > x.rfind(",") else x.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"-?\d{1,3}(,\d{3})+", x): x = x.replace(",", "")
    elif re.fullmatch(r"-?\d{1,3}(\.\d{3})+", x): x = x.replace(".", "")
    else: x = x.replace(",", ".")
    try: return float(x)
    except ValueError: return 0.0
def iso(d):
    d = (d or "").strip(); m = re.fullmatch(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", d)
    return f"{m[3]}-{int(m[2]):02d}-{int(m[1]):02d}" if m else (d or datetime.date.today().isoformat())
def parse_csv(text, kind):
    text = text.strip(); first = text.splitlines()[0] if text else ""
    dl = max(";,\t", key=first.count)
    rd = csv.reader(io.StringIO(text), delimiter=dl); hdr = [h.strip().lower().replace(" ", "_") for h in next(rd)]
    idx = {}
    for f, al in ALIAS[kind].items():
        for a in al:
            if a in hdr: idx[f] = hdr.index(a); break
    need = ["kode", "pemegang", "persen"] if kind == "holders" else ["kode", "broker"]
    miss = [n for n in need if n not in idx]
    if miss: raise ValueError("kolom wajib tidak ditemukan: " + ", ".join(miss) + " (kolom terbaca: " + ", ".join(hdr) + ")")
    out = []
    for r in rd:
        if not any(r): continue
        g = lambda f: r[idx[f]].strip() if f in idx and idx[f] < len(r) else ""
        row = {f: g(f) for f in FIELDS[kind]}; row["kode"] = row["kode"].upper().replace(".JK", ""); row["tanggal"] = iso(row["tanggal"])
        for f in NUMF[kind]: row[f] = num(row[f])
        if kind == "broker": row["broker"] = row["broker"].upper()
        else: row["jenis"] = row["jenis"].lower()
        if row["kode"]: out.append(row)
    return out
def load(kind):
    try: return list(csv.DictReader(open(os.path.join(DDIR, kind + ".csv"), encoding="utf-8")))
    except Exception: return []
def save_merge(kind, new):
    os.makedirs(DDIR, exist_ok=True); kf = KEYS[kind]
    cur = {tuple(r[k] for k in kf): r for r in load(kind)}
    for r in new: cur[tuple(str(r[k]) for k in kf)] = r
    with open(os.path.join(DDIR, kind + ".csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, FIELDS[kind]); w.writeheader(); w.writerows(cur.values())
def rows_for(kind, k):
    out = []
    for r in load(kind):
        if r["kode"] == k:
            for f in NUMF[kind]: r[f] = float(r[f] or 0)
            out.append(r)
    return out

class H(SimpleHTTPRequestHandler):
    def js(self, o):
        b = json.dumps(o).encode(); self.send_response(200); self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        u = urllib.parse.urlparse(self.path); q = urllib.parse.parse_qs(u.query); k = q.get("s", q.get("k", [""]))[0].upper()
        if u.path == "/api/snapshot": self.js(snapshot())
        elif u.path == "/api/detail": self.js(detail(k) if k in EMITEN else {"error": "kode tidak dikenal"})
        elif u.path == "/api/news": self.js(news_emiten(k) if k in EMITEN else news_all())
        elif u.path == "/api/holders": self.js({"rows": rows_for("holders", k)})
        elif u.path == "/api/broker": self.js({"rows": rows_for("broker", k), "brokers": BROKERS})
        else: super().do_GET()
    def do_POST(self):
        u = urllib.parse.urlparse(self.path); kind = urllib.parse.parse_qs(u.query).get("type", [""])[0]
        try:
            if u.path != "/api/upload" or kind not in FIELDS: raise ValueError("jenis impor tidak dikenal")
            n = int(self.headers.get("Content-Length", 0))
            if n > 5_000_000: raise ValueError("file terlalu besar (maks 5 MB)")
            rows = parse_csv(self.rfile.read(n).decode("utf-8-sig", errors="replace"), kind)
            if not rows: raise ValueError("tidak ada baris data")
            save_merge(kind, rows); self.js({"ok": True, "added": len(rows), "codes": sorted({r["kode"] for r in rows})})
        except Exception as e: self.js({"ok": False, "error": str(e)})
    def log_message(self, *a): pass

if __name__ == "__main__":
    import os, sys, webbrowser
    os.chdir(os.path.dirname(os.path.abspath(__file__)))  # agar index.html selalu ketemu
    for port in (8000, 8001, 8080, 5000):
        try:
            srv = ThreadingHTTPServer(("127.0.0.1", port), H); break
        except OSError:
            print(f"Port {port} sedang dipakai, mencoba port lain...", flush=True)
    else:
        sys.exit("Semua port sibuk. Tutup program lain lalu coba lagi.")
    threading.Thread(target=refresher, daemon=True).start()
    url = f"http://localhost:{port}"
    print("=" * 50, flush=True)
    print(f"IDX Terminal BERJALAN. Buka: {url}", flush=True)
    print("Tekan Ctrl+C untuk berhenti.", flush=True)
    print("=" * 50, flush=True)
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try: srv.serve_forever()
    except KeyboardInterrupt: print("Dihentikan.")
