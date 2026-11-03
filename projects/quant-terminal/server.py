#!/usr/bin/env python3
"""Quant Terminal - backend lokal. Hanya butuh Python 3.8+ (tanpa pip install).
Jalankan:  python server.py   ->  buka http://localhost:8000
Data: jika folder data/ berisi CSV (kolom Date,Close) maka dipakai; jika tidak -> data SIMULASI.
Nama file: AAPL.csv (grup Global, USD) atau BBCA.JK.csv (grup IDX, Rupiah). Lihat fetch_data.py."""
import csv, glob, json, math, os, random, threading, webbrowser
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from universe import LQ45, AR_BANDS, SECTORS, STRESS_WINDOWS
import hmac, secrets
import orderflow, zapi

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("QT_DATA_DIR") or os.path.join(HERE, "data")
TOKEN = secrets.token_hex(16)  # token per proses; disisipkan ke index.html, wajib untuk endpoint yang memakai kuota Zapi
# simbol: (harga akhir, vol tahunan, beta ke faktor grup). Harga IDX = Rupiah, ILUSTRATIF (bukan kuotasi pasar).
GLOBAL = {"NQ": (20158, .24, .95), "ES": (5821, .16, .95), "SPY": (581, .16, .95), "QQQ": (492, .24, .93),
          "NVDA": (138, .55, .70), "AAPL": (229, .28, .65), "BTC": (67240, .55, .25), "GC": (2665, .14, .02), "CL": (71, .35, .20)}
IDX = {"IHSG": (7650, .14, .97), "BBCA": (9000, .24, .80), "BBRI": (4100, .30, .80), "BMRI": (4800, .28, .80),
       "BBNI": (4300, .30, .78), "TLKM": (2900, .26, .60), "ASII": (4800, .28, .70), "UNVR": (1900, .30, .45),
       "ICBP": (10500, .24, .45), "ADRO": (2500, .40, .50), "ANTM": (2400, .42, .55), "MDKA": (2200, .50, .55),
       "AMMN": (7500, .55, .45), "BREN": (7000, .70, .35), "GOTO": (70, .65, .50)}
N = 756


def sim_prices():
    rnd = random.Random(42)
    d, dates = date(2026, 10, 15), []
    while len(dates) < N:
        if d.weekday() < 5:
            dates.append(d)
        d -= timedelta(days=1)
    dates.reverse()
    ex = random.Random(7)  # anggota LQ45 lain: parameter acak (data simulasi, bukan kuotasi)
    idx = dict(IDX)
    for t in LQ45:
        idx.setdefault(t, (round(ex.uniform(600, 9000), -1), ex.uniform(.25, .5), ex.uniform(.45, .8)))
    px, vol, groups = {}, {}, {"Global": [], "IDX": []}
    for gname, assets in (("Global", GLOBAL), ("IDX", idx)):
        mkt, tr = [], 0.0
        for _ in range(N):  # faktor grup dengan tren yang berubah-ubah (regime)
            tr = .93 * tr + rnd.gauss(0, .00035)
            mkt.append(.0003 + tr + rnd.gauss(0, 1) * .008)
        for s, (last, vl, b) in assets.items():
            sd, p, v, base = vl / 252 ** .5, [1.0], [], math.exp(rnd.uniform(14.5, 18.5))
            for i in range(N):
                z = b * mkt[i] / .008 + math.sqrt(1 - b * b) * rnd.gauss(0, 1)
                p.append(p[-1] * (1 + z * sd + .0002))
                v.append(base * math.exp(.3 * rnd.gauss(0, 1)) * (1 + .8 * abs(z)))  # volume naik saat gerak besar
            px[s], vol[s] = [x / p[-1] * last for x in p[1:]], v
            groups[gname].append(s)
    return dates, px, vol, groups, "simulasi"


DROPPED = []  # saham yang disingkirkan saat memuat CSV karena riwayat jauh lebih pendek


def csv_prices():
    global DROPPED
    files = glob.glob(os.path.join(DATA_DIR, "*.csv"))
    if not files:
        return None
    series, vols, groups = {}, {}, {"Global": [], "IDX": []}
    for fp in files:
        name = os.path.basename(fp)[:-4].upper()
        sym, g = name.replace(".JK", ""), ("IDX" if name.endswith(".JK") else "Global")
        rows = [r for r in csv.DictReader(open(fp)) if r.get("Close") not in (None, "", "null")]
        series[sym] = {r["Date"][:10]: float(r["Close"]) for r in rows}
        if rows and rows[0].get("Volume"):
            vols[sym] = {r["Date"][:10]: float(r["Volume"] or 0) for r in rows}
        groups[g].append(sym)
    mx = max(len(v) for v in series.values())
    short = [k for k, v in series.items() if len(v) < .9 * mx]  # IPO baru / riwayat pendek mengecilkan irisan tanggal untuk semua saham
    for k in short:
        series.pop(k); vols.pop(k, None)
        for l in groups.values():
            if k in l:
                l.remove(k)
    DROPPED = sorted(short)
    if short:
        print("Saham dibuang karena riwayat jauh lebih pendek dari yang lain:", ", ".join(sorted(short)))
    if not series:
        return None
    common = sorted(set.intersection(*[set(v) for v in series.values()]))
    if len(common) < 300:
        print("PERINGATAN: irisan tanggal antar CSV < 300 bar, pakai data simulasi."); return None
    return ([date.fromisoformat(x) for x in common], {k: [v[x] for x in common] for k, v in series.items()},
            {k: [v[x] for x in common] for k, v in vols.items()}, groups, "CSV")


DATES, PRICES, VOL, GROUPS, SRC = csv_prices() or sim_prices()


def reload_data():
    """Muat ulang data setelah sinkronisasi Zapi menulis CSV baru."""
    global DATES, PRICES, VOL, GROUPS, SRC
    DATES, PRICES, VOL, GROUPS, SRC = csv_prices() or sim_prices()


def sma(x, n):
    out, acc = [None] * len(x), 0.0
    for i, v in enumerate(x):
        acc += v
        if i >= n:
            acc -= x[i - n]
        if i >= n - 1:
            out[i] = acc / n
    return out


def ema(x, n):
    a, out = 2 / (n + 1), [x[0]]
    for z in x[1:]:
        out.append(a * z + (1 - a) * out[-1])
    return out


NEEDV = ("brk", "obv")  # strategi yang butuh data Volume


def rsi_series(c, n):
    out, ag, al = [None] * len(c), 0.0, 0.0
    for i in range(1, len(c)):
        d = c[i] - c[i - 1]
        g, l = max(d, 0), max(-d, 0)
        if i <= n:
            ag, al = ag + g / n, al + l / n
        else:
            ag, al = (ag * (n - 1) + g) / n, (al * (n - 1) + l) / n
        if i >= n:
            out[i] = 100 if al == 0 else 100 - 100 / (1 + ag / al)
    return out


def _signals(strat, c, v, fast, slow, vm, lo):
    """Sinyal per bar: 1 long, 0 flat, -1 short, None = warm-up."""
    n, out = len(c), [None] * len(c)
    if strat == "sma":
        f, s = sma(c, fast), sma(c, slow)
        for i in range(n):
            if f[i] is not None and s[i] is not None:
                out[i] = 1 if f[i] > s[i] else (0 if lo else -1)
        return out
    if strat == "macd":  # fast/slow = periode EMA (sinyal = EMA 9 dari MACD). Long saat MACD > garis sinyal
        ml = [a - b for a, b in zip(ema(c, fast), ema(c, slow))]
        sl_ = ema(ml, 9)
        for i in range(slow + 8, n):
            eps = 1e-9 * abs(c[i])  # toleransi: MACD == garis sinyal dianggap netral, bukan sinyal
            out[i] = 1 if ml[i] > sl_[i] + eps else (-1 if (ml[i] < sl_[i] - eps and not lo) else 0)
        return out
    if strat == "obv":  # fast = SMA dari OBV, slow = SMA harga. Long bila arus volume (OBV) DAN harga sama-sama bullish
        obv = [0.0] * n
        for i in range(1, n):
            obv[i] = obv[i - 1] + (v[i] if c[i] > c[i - 1] else -v[i] if c[i] < c[i - 1] else 0)
        so, sc = sma(obv, fast), sma(c, slow)
        for i in range(n):
            if so[i] is None or sc[i] is None:
                continue
            out[i] = 1 if (obv[i] > so[i] and c[i] > sc[i]) else (-1 if (obv[i] < so[i] and c[i] < sc[i] and not lo) else 0)
        return out
    if strat == "rsi":  # fast = periode RSI, slow = level oversold; masuk saat RSI < slow, keluar saat RSI kembali >= 50
        r, st = rsi_series(c, fast), 0
        for i in range(n):
            if r[i] is None:
                continue
            if st == 0:
                st = 1 if r[i] < slow else (-1 if r[i] > 100 - slow and not lo else 0)
            elif (st == 1 and r[i] >= 50) or (st == -1 and r[i] <= 50):
                st = 0
            out[i] = st
        return out
    if strat == "bb":  # fast = periode, slow = k (std); masuk saat close menembus band bawah, keluar di garis tengah
        m, st = sma(c, fast), 0
        for i in range(fast - 1, n):
            w = c[i - fast + 1:i + 1]
            sd = (sum((x - m[i]) ** 2 for x in w) / fast) ** .5
            if st == 0:
                st = 1 if c[i] < m[i] - slow * sd else (-1 if c[i] > m[i] + slow * sd and not lo else 0)
            elif (st == 1 and c[i] >= m[i]) or (st == -1 and c[i] <= m[i]):
                st = 0
            out[i] = st
        return out
    va, st = sma(v, 20), 0  # breakout: close > high N hari DAN volume >= vm x rata2 20 hari; exit: close < low M hari
    for i in range(max(fast, slow, 21), n):
        hi, low = max(c[i - fast:i]), min(c[i - slow:i])
        if c[i] > hi and v[i] >= vm * va[i - 1]:
            st = 1
        elif c[i] < low and st >= 0:
            st = 0 if lo else -1
        elif st == -1 and c[i] > hi:
            st = 0
        out[i] = st
    return out


CTX = threading.local()  # konteks per-request: CTX.tf = periode SMA filter tren (0 = mati)


def signals(strat, c, v, fast, slow, vm, lo):
    """Sinyal strategi + (opsional) filter tren: long hanya bila close > SMA(tf), short hanya bila close < SMA(tf)."""
    out = _signals(strat, c, v, fast, slow, vm, lo)
    tf = getattr(CTX, "tf", 0)
    if tf:
        m = sma(c, tf)
        for i in range(len(c)):
            if m[i] is None:
                out[i] = None  # belum cukup data untuk SMA filter
            elif out[i] == 1 and not c[i] > m[i]:
                out[i] = 0
            elif out[i] == -1 and not c[i] < m[i]:
                out[i] = 0
    return out


def tick(p):  # fraksi harga IDX
    return 1 if p < 200 else 2 if p < 500 else 5 if p < 2000 else 10 if p < 5000 else 25


def t_up(p):
    t = tick(p); return math.ceil(p / t - 1e-9) * t


def t_dn(p):
    t = tick(p); return math.floor(p / t + 1e-9) * t


def backtest(c, sig, stop, cap, fee=0.0, lot=0, ticks=False, limits=False):
    """Akuntansi berbasis lembar: lot>0 -> bulatkan ke kelipatan lot; ticks -> fill dibulatkan ke tick (merugikan)."""
    up, dn = (t_up, t_dn) if ticks else (lambda p: p, lambda p: p)
    cash, sh, entry, e_i, e_eq, blocked, days_in = cap, 0.0, 0.0, 0, cap, 0, 0
    eq, trades = [cap], []

    def close(i):
        nonlocal cash, sh
        d = 1 if sh > 0 else -1
        px = dn(c[i]) if d > 0 else up(c[i])
        cash += sh * px - abs(sh) * px * fee
        trades.append(dict(i0=e_i, i1=i, dir=d, p0=entry, p1=px, pnl=cash - e_eq, pr=(cash - e_eq) / e_eq, qty=abs(sh),
                           r=d * (px / entry - 1) / (stop / 100) if stop else 0))
        sh = 0.0

    def hit(i, upd):  # close hari i terkunci ARA (upd=True) / ARB (upd=False)? -> order tidak bisa dieksekusi
        if not limits:
            return False
        pc = c[i - 1]
        lim = next(p for b, p in AR_BANDS if pc < b)
        r = c[i] / pc - 1
        return r >= .99 * lim if upd else r <= -.99 * lim

    dl = 0  # jumlah hari order tertunda karena ARA/ARB
    for i in range(1, len(c)):
        pos = (sh > 0) - (sh < 0)
        days_in += bool(pos)
        sg = sig[i]
        if blocked and sg != blocked:
            blocked = 0
        stopped = bool(pos and stop and pos * (c[i] / entry - 1) <= -stop / 100)
        if stopped or (sg is not None and sg != pos and (sg == 0 or sg != blocked)):  # blocked hanya menahan ENTRY, bukan exit
            if pos > 0 and hit(i, False):
                dl += 1  # tidak bisa jual saat ARB -> coba lagi besok
            else:
                if stopped:
                    blocked = pos  # tunggu sinyal berbalik sebelum masuk lagi searah
                if pos:
                    close(i)
                if sg and not stopped:
                    if sg > 0 and hit(i, True):
                        dl += 1  # tidak bisa beli saat ARA -> coba lagi besok
                    else:
                        px = up(c[i]) if sg > 0 else dn(c[i])
                        u = cash / (px * (1 + fee))
                        u = math.floor(u / lot) * lot if lot else u
                        if u > 0:
                            e_eq, entry, e_i = cash, px, i
                            cash += -u * px * (1 + fee) if sg > 0 else u * px * (1 - fee)
                            sh = u if sg > 0 else -u
        eq.append(cash + sh * c[i])
    if sh:
        close(len(c) - 1); eq[-1] = cash
    return eq, trades, days_in / len(c), dl


def stats(eq, trades):
    r = [eq[i] / eq[i - 1] - 1 for i in range(1, len(eq))]
    m = sum(r) / len(r)
    sd = (sum((x - m) ** 2 for x in r) / len(r)) ** .5 or 1e-9
    dn = (sum(min(x, 0) ** 2 for x in r) / len(r)) ** .5 or 1e-9
    peak, mdd = eq[0], 0
    for v in eq:
        peak = max(peak, v); mdd = max(mdd, (peak - v) / peak)
    w = [t["pnl"] for t in trades if t["pnl"] > 0]
    l = [-t["pnl"] for t in trades if t["pnl"] <= 0]
    cagr = (eq[-1] / eq[0]) ** (252 / len(eq)) - 1
    return dict(ret=eq[-1] / eq[0] - 1, cagr=cagr, sharpe=m / sd * 252 ** .5, sortino=m / dn * 252 ** .5, mdd=mdd,
                calmar=cagr / mdd if mdd else None, n=len(trades),
                pf=sum(w) / sum(l) if l and sum(l) > 0 else None,
                win=len(w) / len(trades) if trades else None,
                exp=sum(t["pnl"] for t in trades) / len(trades) if trades else None,
                rr=(sum(w) / len(w)) / (sum(l) / len(l)) if w and l else None)


def rsi14(c):
    g = [max(c[i] - c[i - 1], 0) for i in range(1, len(c))]
    l = [max(c[i - 1] - c[i], 0) for i in range(1, len(c))]
    ag, al = sum(g[:14]) / 14, sum(l[:14]) / 14
    for i in range(14, len(g)):
        ag, al = (ag * 13 + g[i]) / 14, (al * 13 + l[i]) / 14
    return 100 if al == 0 else 100 - 100 / (1 + ag / al)


def screen(grp):
    out = []
    for s in GROUPS[grp]:
        c, v = PRICES[s], VOL.get(s)
        if len(c) < 210:
            continue
        vr = v[-1] / (sum(v[-21:-1]) / 20) if v else None
        brk = c[-1] > max(c[-21:-1]) and (vr is None or vr >= 1.5)
        out.append(dict(s=s, lq=s in LQ45, last=c[-1], m1=c[-1] / c[-22] - 1, m3=c[-1] / c[-64] - 1, rsi=rsi14(c),
                        h52=c[-1] / max(c[-252:]) - 1, vr=vr, val=c[-1] * sum(v[-20:]) / 20 if v else None,
                        up=c[-1] > sum(c[-50:]) / 50 > sum(c[-200:]) / 200, brk=brk))
    return out


def payload(q):
    g = lambda k, d: type(d)(q.get(k, [d])[0])
    asset, fast, slow, stop, cap = g("asset", "NQ"), g("fast", 20), g("slow", 60), g("stop", 3.0), g("cap", 100000.0)
    strat, vm, lo, fee = g("strat", "sma"), g("vm", 1.5), g("mode", "ls") == "lo", g("fee", 0.0) / 100
    if asset not in PRICES:
        asset = next(iter(PRICES))
    grp = next(k for k, l in GROUPS.items() if asset in l)
    ok = valid_params(strat, fast, slow)
    if not ok:
        return {"error": "Parameter tidak valid. SMA/MACD: cepat < lambat | Breakout: exit M < N | RSI: periode 2-50, oversold 5-45 | Bollinger: periode >= 5, std > 0 | OBV: kedua periode >= 2."}
    if strat in NEEDV and asset not in VOL:
        return {"error": "Strategi ini (breakout/OBV) butuh kolom Volume pada CSV aset ini."}
    rules = g("rules", 1) == 1 and grp == "IDX" and asset != "IHSG"  # IHSG = indeks, tidak diperdagangkan langsung
    lot, ticks = (100 if rules else 0), rules
    if rules:
        lo = True  # short selling ritel tidak tersedia di IDX
    c, v = PRICES[asset], VOL.get(asset)
    sig = lambda cc, vv, a, b: signals(strat, cc, vv, a, b, vm, lo)
    eq, tr, expo, dl = backtest(c, sig(c, v, fast, slow), stop, cap, fee, lot, ticks, ticks)
    bh = [cap * x / c[0] for x in c]
    st, sb = stats(eq, tr), stats(bh, [])
    st["expo"], st["dl"] = expo, dl
    month, prev = {}, cap  # return bulanan strategi
    for i, d in enumerate(DATES):
        if i + 1 == len(DATES) or DATES[i + 1].month != d.month:
            month[f"{d.year}-{d.month}"] = (eq[i] / prev - 1) * 100; prev = eq[i]
    fs, ss, gl, okc = grid_for(strat)  # grid optimisasi
    grid = [[(stats(*backtest(c, sig(c, v, a, b), stop, cap, fee, lot, ticks, ticks)[:2])["sharpe"] if okc(a, b) else None)
             for b in ss] for a in fs]
    view = GROUPS[grp][:15] + ([asset] if asset not in GROUPS[grp][:15] else [])  # panel korelasi/monitor dibatasi 16 simbol
    rets = {k: [PRICES[k][i] / PRICES[k][i - 1] - 1 for i in range(1, len(c))] for k in view}

    def corr(a, b):
        ma, mb = sum(a) / len(a), sum(b) / len(b)
        return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b))
    mon = []
    for s in view:
        p = PRICES[s]
        last = signals(strat, p, VOL.get(s), fast, slow, vm, lo)[-1] if (strat not in NEEDV or s in VOL) else 0
        mon.append(dict(s=s, last=p[-1], chg=p[-1] - p[-2], pct=(p[-1] / p[-2] - 1) * 100, hi=max(p[-5:]), lo=min(p[-5:]),
                        sig="LONG" if last == 1 else ("SHORT" if last == -1 else "FLAT")))
    tl = [dict(d0=DATES[t["i0"]].isoformat(), date=DATES[t["i1"]].isoformat(), dir="Long" if t["dir"] > 0 else "Short",
               p0=t["p0"], p1=t["p1"], pnl=t["pnl"], r=t["r"], qty=t["qty"] / lot if lot else t["qty"]) for t in tr]
    return dict(asset=asset, groups=GROUPS, ccy="Rp" if grp == "IDX" else "$", src=SRC, rules=rules, gl=gl,
                dates=[d.isoformat() for d in DATES], eq=eq, bh=bh, stats=st, base=sb, month=month,
                rets=[(eq[i] / eq[i - 1] - 1) * 100 for i in range(1, len(eq))], fs=fs, ss=ss, grid=grid,
                syms=view, corr=[[corr(rets[a], rets[b]) for b in view] for a in view], monitor=mon, screen=screen(grp),
                trades=tl[-12:][::-1], all=tl)


def universe(q):
    g = lambda k, d: type(d)(q.get(k, [d])[0])
    asset, fast, slow, stop, cap = g("asset", "NQ"), g("fast", 20), g("slow", 60), g("stop", 3.0), g("cap", 100000.0)
    strat, vm, lo, fee = g("strat", "sma"), g("vm", 1.5), g("mode", "ls") == "lo", g("fee", 0.0) / 100
    if asset not in PRICES:
        asset = next(iter(PRICES))
    grp = next(k for k, l in GROUPS.items() if asset in l)
    ok = valid_params(strat, fast, slow)
    if not ok:
        return {"error": "Parameter tidak valid untuk strategi ini."}
    rules = g("rules", 1) == 1 and grp == "IDX"
    lot, only = (100 if rules else 0), g("lq", 0) == 1 and grp == "IDX"
    lo = lo or rules  # IDX: long-only
    rows, curves, bhs = [], [], []
    for s in GROUPS[grp]:
        if (rules and s == "IHSG") or (only and s not in LQ45) or (strat in NEEDV and s not in VOL):
            continue
        c, v = PRICES[s], VOL.get(s)
        eq, tr, expo, dl = backtest(c, signals(strat, c, v, fast, slow, vm, lo), stop, cap, fee, lot, rules, rules)
        bh = [cap * x / c[0] for x in c]
        st, sb = stats(eq, tr), stats(bh, [])
        rows.append(dict(s=s, lq=s in LQ45, ret=st["ret"], bh=sb["ret"], sharpe=st["sharpe"], mdd=st["mdd"], n=st["n"],
                         win=st["win"], pf=st["pf"], expo=expo, dl=dl))
        curves.append(eq); bhs.append(bh)
    if not rows:
        return {"error": "Tidak ada saham yang memenuhi syarat (strategi breakout/OBV butuh Volume)."}
    k, n = len(rows), len(DATES)
    port, bport = [sum(e[i] for e in curves) / k for i in range(n)], [sum(e[i] for e in bhs) / k for i in range(n)]
    sh = sorted(r["sharpe"] for r in rows)
    bench = [cap * x / PRICES["IHSG"][0] for x in PRICES["IHSG"]] if grp == "IDX" and "IHSG" in PRICES else None
    return dict(ccy="Rp" if grp == "IDX" else "$", src=SRC, n=k, prof=sum(r["ret"] > 0 for r in rows) / k, med=sh[k // 2],
                beat=sum(r["ret"] > r["bh"] for r in rows) / k, port=port, bport=bport, bench=bench, ps=stats(port, []),
                pb=stats(bport, []), rows=rows, dl=sum(r["dl"] for r in rows), trades=sum(r["n"] for r in rows), rules=rules)


STOPS = [3, 5, 8, 12, 0]  # kandidat stop-loss % (0 = tanpa stop) bila stop ikut dioptimasi


def grid_for(strat):
    if strat == "sma":
        return [5, 10, 15, 20, 30, 40], [30, 50, 80, 100, 150, 200], ["SMA cepat", "SMA lambat"], (lambda a, b: a < b)
    if strat == "brk":
        return [10, 20, 30, 40, 55, 80], [5, 10, 15, 20, 30, 50], ["Breakout N", "Exit M"], (lambda a, b: b < a)
    if strat == "rsi":
        return [5, 7, 10, 14, 21, 28], [15, 20, 25, 30, 35, 40], ["RSI periode", "Oversold"], (lambda a, b: True)
    if strat == "macd":
        return [5, 8, 10, 12, 15, 20], [20, 26, 30, 35, 40, 50], ["EMA cepat", "EMA lambat"], (lambda a, b: a < b)
    if strat == "obv":
        return [5, 10, 20, 30, 40, 60], [20, 30, 50, 100, 150, 200], ["OBV SMA", "Tren SMA"], (lambda a, b: True)
    return [10, 15, 20, 30, 40, 60], [1.0, 1.5, 2.0, 2.5, 3.0], ["Periode", "Std ×"], (lambda a, b: True)


def valid_params(strat, fast, slow):
    return {"sma": fast < slow, "brk": slow < fast, "rsi": 2 <= fast <= 50 and 5 <= slow <= 45, "bb": fast >= 5 and slow > 0,
            "macd": 2 <= fast < slow, "obv": fast >= 2 and slow >= 2}.get(strat, False)


def common(q):
    g = lambda k, d: type(d)(q.get(k, [d])[0])
    P = dict(g=g, asset=g("asset", "NQ"), fast=g("fast", 20), slow=g("slow", 60), stop=g("stop", 3.0), cap=g("cap", 100000.0),
             strat=g("strat", "sma"), vm=g("vm", 1.5), lo=g("mode", "ls") == "lo", fee=g("fee", 0.0) / 100)
    if P["asset"] not in PRICES:
        P["asset"] = next(iter(PRICES))
    P["grp"] = next(k for k, l in GROUPS.items() if P["asset"] in l)
    P["rules"] = g("rules", 1) == 1 and P["grp"] == "IDX" and P["asset"] != "IHSG"
    P["lot"] = 100 if P["rules"] else 0
    P["lo"] = P["lo"] or P["rules"]
    return P


def walkforward(q):
    """Rolling/anchored walk-forward: optimasi grid di jendela training, uji parameter terbaik di jendela test berikutnya."""
    P = common(q); g = P["g"]; asset, strat, cap = P["asset"], P["strat"], P["cap"]
    if strat in NEEDV and asset not in VOL:
        return {"error": "Strategi ini (breakout/OBV) butuh kolom Volume pada CSV aset ini."}
    train, test, anch, ostop = g("train", 252), g("test", 63), g("anch", 0) == 1, g("ostop", 0) == 1
    stops = STOPS if ostop else [P["stop"]]
    c, v = PRICES[asset], VOL.get(asset)
    n = len(c)
    if train < 60 or test < 10 or train + test > n - 1:
        return {"error": f"Jendela tidak valid: training >= 60, test >= 10, training + test <= {n - 1} bar."}
    fs, ss, gl, okc = grid_for(strat)
    base = [(a, b) for a in fs for b in ss if okc(a, b)]
    sg = {k: signals(strat, c, v, k[0], k[1], P["vm"], P["lo"]) for k in base}  # sinyal kausal: hanya memakai data sebelum bar t
    combos = [(a, b, st) for a, b in base for st in stops]
    bt = lambda i0, i1, k, cp: backtest(c[i0:i1], sg[k[:2]][i0:i1], k[2], cp, P["fee"], P["lot"], P["rules"], P["rules"])
    folds, oos, cur, trs, o0, vl, start = [], None, cap, [], None, [], train
    while start + test <= n:
        lo = 0 if anch else start - train
        best = None
        for k in combos:
            eq, tr, _, _ = bt(lo, start, k, cap)
            sh = stats(eq, tr)["sharpe"]
            if best is None or sh > best[0]:
                best = (sh, k)
        sh_is, k = best
        eq, tr, _, dl = bt(start - 1, start + test, k, cur)  # posisi dimulai flat di awal jendela test
        so = stats(eq, tr)
        if oos is None:
            oos, o0 = [eq[0]], start
        oos.extend(eq[1:]); cur = eq[-1]; trs.extend(tr); vl.append(len(oos) - 1)
        folds.append(dict(tr0=DATES[lo].isoformat(), tr1=DATES[start - 1].isoformat(), te0=DATES[start].isoformat(),
                          te1=DATES[start + test - 1].isoformat(), a=k[0], b=k[1], st=k[2], isS=sh_is, oosS=so["sharpe"],
                          oosR=eq[-1] / eq[0] - 1, n=len(tr), dl=dl))
        start += test
    if not folds:
        return {"error": "Data tidak cukup untuk satu fold pun."}
    bh = [cap * c[i] / c[o0 - 1] for i in range(o0 - 1, o0 - 1 + len(oos))]
    full = max(((stats(*bt(0, n, k, cap)[:2])["sharpe"], k) for k in combos))
    fr = stats(*bt(0, n, full[1], cap)[:2])
    sa, mis = stats(oos, trs), sum(f["isS"] for f in folds) / len(folds)
    return dict(ccy="Rp" if P["grp"] == "IDX" else "$", src=SRC, gl=gl, folds=folds, eq=oos, bh=bh, vl=vl[:-1],
                dates=[d.isoformat() for d in DATES[o0 - 1:o0 - 1 + len(oos)]], so=sa, sb=stats(bh, []), mean_is=mis,
                eff=sa["sharpe"] / mis if mis > .1 else None, pos=sum(f["oosR"] > 0 for f in folds) / len(folds),
                distinct=len({(f["a"], f["b"], f["st"]) for f in folds}), ostop=ostop,
                full=dict(sh=full[0], a=full[1][0], b=full[1][1], st=full[1][2], ret=fr["ret"]))


def ar_hit(c, i, upd):
    pc = c[i - 1]
    lim = next(p for b, p in AR_BANDS if pc < b)
    r = c[i] / pc - 1
    return r >= .99 * lim if upd else r <= -.99 * lim


def make_rank(kind, syms, px=None):
    PX = PRICES if px is None else px
    if kind == "mom":
        return lambda s, i: PX[s][i] / PX[s][i - 63] - 1 if i >= 63 else -9
    if kind == "rsi":
        R = {s: rsi_series(PX[s], 14) for s in syms}
        return lambda s, i: -(R[s][i] if R[s][i] is not None else 50)
    LV = {s: sma([a * b for a, b in zip(PX[s], VOL[s])], 20) for s in syms if s in VOL}
    return lambda s, i: (LV[s][i] or 0) if s in LV else 0


def run_port(syms, sig, K, rk, stop, cap, fee, rules, i0=0, i1=None, px=None, smax=0, sect=None):
    """Satu rekening, long-only: modal bersama, maks K posisi, ukuran posisi = ekuitas/K, prioritas masuk lewat skor rk.
    smax>0 + sect: maksimum posisi per sektor. px: kamus harga alternatif (skenario stres)."""
    PX = PRICES if px is None else px
    up, dn = (t_up, t_dn) if rules else ((lambda p: p), (lambda p: p))
    lot, n, cash, held, blocked, dl, buys = (100 if rules else 0), len(DATES), cap, {}, set(), 0, 0.0
    i1 = n if i1 is None else i1
    eq, npos, trades, contrib, sdays = [cap], [0], [], {}, {}

    def sell(s, i):
        nonlocal cash
        sh, entry, ei, cost = held.pop(s)
        pr = sh * dn(PX[s][i]) * (1 - fee)
        cash += pr
        trades.append(dict(s=s, pnl=pr - cost)); contrib[s] = contrib.get(s, 0) + pr - cost

    for i in range(i0 + 1, i1):
        for s in list(blocked):
            if sig[s][i] != 1:
                blocked.discard(s)
        for s in list(held):
            c, sg = PX[s], sig[s][i]
            stopped = bool(stop and c[i] / held[s][1] - 1 <= -stop / 100)
            if stopped or (sg is not None and sg != 1):
                if rules and ar_hit(c, i, False):
                    dl += 1; continue  # ARB: tidak bisa jual
                if stopped:
                    blocked.add(s)
                sell(s, i)
        slots = K - len(held)
        if slots > 0:
            cands = []
            for s in syms:
                if s not in held and s not in blocked and sig[s][i] == 1:
                    if rules and ar_hit(PX[s], i, True):
                        dl += 1  # ARA: tidak bisa beli
                    else:
                        cands.append(s)
            cands.sort(key=lambda s: -rk(s, i))
            cnt, chosen = {}, []
            if smax and sect:
                for s in held:
                    cnt[sect.get(s)] = cnt.get(sect.get(s), 0) + 1
            for s in cands:
                if len(chosen) >= slots:
                    break
                sc = sect.get(s) if (smax and sect) else None
                if sc is not None and cnt.get(sc, 0) >= smax:
                    continue  # sektor penuh
                chosen.append(s); cnt[sc] = cnt.get(sc, 0) + 1
            tgt = (cash + sum(h[0] * PX[s][i] for s, h in held.items())) / K
            for s in chosen:
                px_ = up(PX[s][i])
                u = min(tgt, cash) / (px_ * (1 + fee))
                u = math.floor(u / lot) * lot if lot else u
                if u > 0:
                    cost = u * px_ * (1 + fee); cash -= cost; buys += cost; held[s] = [u, px_, i, cost]
        eq.append(cash + sum(h[0] * PX[s][i] for s, h in held.items())); npos.append(len(held))
        if sect:
            for s in held:
                k_ = sect.get(s, "Lainnya"); sdays[k_] = sdays.get(k_, 0) + 1
    for s in list(held):
        sell(s, i1 - 1)
    eq[-1] = cash
    return eq, trades, npos, dl, contrib, buys, sdays


def sect_args(g, grp):
    return (g("smax", 0) if grp == "IDX" else 0), (SECTORS if grp == "IDX" else None)


def portfolio(q):
    P = common(q); g = P["g"]; grp, strat, cap = P["grp"], P["strat"], P["cap"]
    if not valid_params(strat, P["fast"], P["slow"]):
        return {"error": "Parameter tidak valid untuk strategi ini."}
    rules = g("rules", 1) == 1 and grp == "IDX"
    only = g("lq", 0) == 1 and grp == "IDX"
    syms = [s for s in GROUPS[grp] if not (rules and s == "IHSG") and not (only and s not in LQ45) and not (strat in NEEDV and s not in VOL)]
    if len(syms) < 2:
        return {"error": "Butuh minimal 2 saham (strategi breakout/OBV butuh Volume)."}
    sig = {s: signals(strat, PRICES[s], VOL.get(s), P["fast"], P["slow"], P["vm"], True) for s in syms}
    rk, K, n = make_rank(g("rank", "liq"), syms), max(1, g("k", 10)), len(DATES)
    args, (smax, SECT) = (syms, sig), sect_args(g, grp)
    eq, trades, npos, dl, contrib, buys, sdays = run_port(*args, K, rk, P["stop"], cap, P["fee"], rules, smax=smax, sect=SECT)
    sens = []
    for k in [3, 5, 8, 10, 15, 20, 30]:
        if k <= len(syms):
            e2, t2 = run_port(*args, k, rk, P["stop"], cap, P["fee"], rules, smax=smax, sect=SECT)[:2]
            z = stats(e2, t2); sens.append(dict(k=k, ret=z["ret"], sharpe=z["sharpe"], mdd=z["mdd"], n=len(t2)))
    bh = [cap * sum(PRICES[s][i] / PRICES[s][0] for s in syms) / len(syms) for i in range(n)]
    bench = [cap * x / PRICES["IHSG"][0] for x in PRICES["IHSG"]] if grp == "IDX" and "IHSG" in PRICES else None
    st, cnt = stats(eq, trades), {}
    for t in trades:
        cnt[t["s"]] = cnt.get(t["s"], 0) + 1
    st.update(avgpos=sum(npos) / n, maxpos=max(npos), util=sum(npos) / n / K, dl=dl, turn=buys / (sum(eq) / n) / (n / 252))
    cl = sorted(({"s": s, "pnl": p, "n": cnt[s]} for s, p in contrib.items()), key=lambda r: -r["pnl"])
    secs = []
    if SECT:
        pn, nt = {}, {}
        for t in trades:
            sc = SECT.get(t["s"], "Lainnya"); pn[sc] = pn.get(sc, 0) + t["pnl"]; nt[sc] = nt.get(sc, 0) + 1
        secs = sorted(({"sector": k, "avg": sdays.get(k, 0) / n, "pnl": pn.get(k, 0), "n": nt.get(k, 0)} for k in set(sdays) | set(pn)), key=lambda r: -r["avg"])
    return dict(ccy="Rp" if grp == "IDX" else "$", src=SRC, rules=rules, k=K, nsym=len(syms), dates=[d.isoformat() for d in DATES], smax=smax,
                eq=eq, bh=bh, bench=bench, npos=npos, st=st, sb=stats(bh, []), sens=sens, top=cl[:8], bot=cl[-5:][::-1] if len(cl) > 8 else [], sectors=secs)


def pwf(q):
    """Walk-forward portofolio: per fold optimasi (parameter strategi x jumlah posisi K) di training, uji di test berikutnya."""
    P = common(q); g = P["g"]; grp, strat, cap = P["grp"], P["strat"], P["cap"]
    rules = g("rules", 1) == 1 and grp == "IDX"
    only = g("lq", 0) == 1 and grp == "IDX"
    syms = [s for s in GROUPS[grp] if not (rules and s == "IHSG") and not (only and s not in LQ45) and not (strat in NEEDV and s not in VOL)]
    if len(syms) < 2:
        return {"error": "Butuh minimal 2 saham (strategi breakout/OBV butuh Volume)."}
    train, test, anch, n = g("train", 252), g("test", 63), g("anch", 0) == 1, len(DATES)
    if train < 60 or test < 10 or train + test > n - 1:
        return {"error": f"Jendela tidak valid: training >= 60, test >= 10, training + test <= {n - 1} bar."}
    fs, ss, gl, okc = grid_for(strat)
    ostop = g("ostop", 0) == 1
    stops = STOPS if ostop else [P["stop"]]
    base = [(a, b) for a in fs for b in ss if okc(a, b)]
    combos = [(a, b, st) for a, b in base for st in stops]
    Ks = [k for k in (5, 10, 20) if k <= len(syms)] or [len(syms)]
    sigs = {k: {s: signals(strat, PRICES[s], VOL.get(s), k[0], k[1], P["vm"], True) for s in syms} for k in base}
    rk, fee = make_rank(g("rank", "liq"), syms), P["fee"]
    smax, SECT = sect_args(g, grp)
    run = lambda k, K, cp, i0, i1: run_port(syms, sigs[k[:2]], K, rk, k[2], cp, fee, rules, i0, i1, smax=smax, sect=SECT)
    folds, oos, cur, trs, o0, vl, start = [], None, cap, [], None, [], train
    while start + test <= n:
        lo, best = (0 if anch else start - train), None
        for k in combos:
            for K in Ks:
                e, t = run(k, K, cap, lo, start)[:2]
                sh = stats(e, t)["sharpe"]
                if best is None or sh > best[0]:
                    best = (sh, k, K)
        sh_is, k, K = best
        e, t, _, dl = run(k, K, cur, start - 1, start + test)[:4]
        so = stats(e, t)
        if oos is None:
            oos, o0 = [e[0]], start
        oos.extend(e[1:]); cur = e[-1]; trs.extend(t); vl.append(len(oos) - 1)
        folds.append(dict(tr0=DATES[lo].isoformat(), tr1=DATES[start - 1].isoformat(), te0=DATES[start].isoformat(),
                          te1=DATES[start + test - 1].isoformat(), a=k[0], b=k[1], st=k[2], K=K, isS=sh_is, oosS=so["sharpe"],
                          oosR=e[-1] / e[0] - 1, n=len(t), dl=dl))
        start += test
    bh = [cap * sum(PRICES[s][i] / PRICES[s][o0 - 1] for s in syms) / len(syms) for i in range(o0 - 1, o0 - 1 + len(oos))]
    fb = max(((stats(*run(k, K, cap, 0, n)[:2])["sharpe"], k, K) for k in combos for K in Ks))
    sa, mis = stats(oos, trs), sum(f["isS"] for f in folds) / len(folds)
    return dict(ccy="Rp" if grp == "IDX" else "$", src=SRC, gl=gl, nsym=len(syms), folds=folds, eq=oos, bh=bh, vl=vl[:-1],
                dates=[d.isoformat() for d in DATES[o0 - 1:o0 - 1 + len(oos)]], so=sa, sb=stats(bh, []), mean_is=mis,
                eff=sa["sharpe"] / mis if mis > .1 else None, pos=sum(f["oosR"] > 0 for f in folds) / len(folds),
                distinct=len({(f["a"], f["b"], f["st"], f["K"]) for f in folds}), ostop=ostop,
                full=dict(sh=fb[0], a=fb[1][0], b=fb[1][1], st=fb[1][2], K=fb[2]))


def path_dd(r, add):
    """Path ekuitas level-trade: multiplikatif (compounding) atau aditif. Kembalikan (max drawdown, return akhir)."""
    x = peak = 1.0; mdd = 0.0
    for v in r:
        x = x + v if add else x * (1 + v)
        peak = max(peak, x)
        if peak > 0:
            mdd = max(mdd, (peak - x) / peak)
    return mdd, x - 1


def montecarlo(q):
    """Uji ketahanan: (1) acak urutan trade -> distribusi max DD; (2) bootstrap trade -> distribusi return;
    (3) buang 20% trade acak; (4) perturbasi parameter +-25% (fast/slow) dan +-30% (stop)."""
    P = common(q); g = P["g"]; strat, asset, grp, cap, fast, slow = P["strat"], P["asset"], P["grp"], P["cap"], P["fast"], P["slow"]
    if not valid_params(strat, fast, slow):
        return {"error": "Parameter tidak valid untuk strategi ini."}
    N, rnd, target = min(max(g("n", 2000), 200), 10000), random.Random(g("seed", 1)), g("target", "asset")
    if target == "asset":
        if strat in NEEDV and asset not in VOL:
            return {"error": "Strategi ini (breakout/OBV) butuh kolom Volume pada CSV aset ini."}
        c, v = PRICES[asset], VOL.get(asset)
        ev = lambda fa, sl, st: backtest(c, signals(strat, c, v, fa, sl, P["vm"], P["lo"]), st, cap, P["fee"], P["lot"], P["rules"], P["rules"])[:2]
        npar, add, bh = 120, False, c[-1] / c[0] - 1
        pr = lambda t: t["pr"]
    else:
        rules = g("rules", 1) == 1 and grp == "IDX"
        only = g("lq", 0) == 1 and grp == "IDX"
        syms = [s for s in GROUPS[grp] if not (rules and s == "IHSG") and not (only and s not in LQ45) and not (strat in NEEDV and s not in VOL)]
        if len(syms) < 2:
            return {"error": "Butuh minimal 2 saham."}
        rk, K = make_rank(g("rank", "liq"), syms), max(1, g("k", 10))
        smax, SECT = sect_args(g, grp)
        ev = lambda fa, sl, st: run_port(syms, {s: signals(strat, PRICES[s], VOL.get(s), fa, sl, P["vm"], True) for s in syms},
                                         K, rk, st, cap, P["fee"], rules, smax=smax, sect=SECT)[:2]
        npar, add = 50, True
        bh = sum(PRICES[s][-1] / PRICES[s][0] for s in syms) / len(syms) - 1
        pr = lambda t: t["pnl"] / cap
    be, bt = ev(fast, slow, P["stop"])
    rets = [pr(t) for t in bt]
    if len(rets) < 8:
        return {"error": f"Hanya {len(rets)} trade — terlalu sedikit untuk Monte Carlo (minimal 8). Coba parameter lain, data lebih panjang, atau portofolio."}
    n, dd, boot, drop = len(rets), [], [], []
    for _ in range(N):
        x = rets[:]; rnd.shuffle(x); dd.append(path_dd(x, add)[0])
        boot.append(path_dd([rnd.choice(rets) for _ in range(n)], add)[1])
        kept = [r for r in rets if rnd.random() > .2]
        drop.append(path_dd(kept, add)[1])
    psh, pret, tries = [], [], 0
    while len(psh) < npar and tries < npar * 4:
        tries += 1
        if strat == "bb":
            fa, sl = max(5, round(fast * rnd.uniform(.75, 1.25))), round(slow * rnd.uniform(.8, 1.2), 1)
        else:
            fa, sl = max(2, round(fast * rnd.uniform(.75, 1.25))), max(2, round(slow * rnd.uniform(.75, 1.25)))
        if not valid_params(strat, fa, sl):
            continue
        st = P["stop"] * rnd.uniform(.7, 1.3) if P["stop"] else 0
        z = stats(*ev(fa, sl, st)); psh.append(z["sharpe"]); pret.append(z["ret"])
    mdd0, ret0 = path_dd(rets, add)
    return dict(ccy="Rp" if grp == "IDX" else "$", src=SRC, target=target, N=N, dd=dd, boot=boot, drop=drop, psh=psh, pret=pret, bh=bh,
                base=dict(ret=ret0, mdd=mdd0, n=n, sharpe=stats(be, bt)["sharpe"], eqret=be[-1] / be[0] - 1, add=add))


def shocked(syms, t, steps, volx=0, vlen=30):
    """Harga skenario: loncatan level permanen (offset, persen) mulai bar t, dan/atau volatilitas x volx selama vlen bar."""
    out = {}
    for s in syms:
        p = PRICES[s]; q_ = p[:]
        if volx:
            for j in range(t, min(len(p), t + vlen)):
                q_[j] = q_[j - 1] * (1 + max(-.9, (p[j] / p[j - 1] - 1) * volx))
            for j in range(t + vlen, len(p)):
                q_[j] = q_[j - 1] * (p[j] / p[j - 1])
        for off, sh in steps:
            for j in range(t + off, len(q_)):
                q_[j] *= 1 + sh
        out[s] = q_
    return out


def stress(q):
    """Uji stres: (1) kinerja strategi pada jendela krisis historis; (2) guncangan sintetis di saat eksposur tertinggi."""
    P = common(q); g = P["g"]; strat, asset, grp, cap, fast, slow = P["strat"], P["asset"], P["grp"], P["cap"], P["fast"], P["slow"]
    if not valid_params(strat, fast, slow):
        return {"error": "Parameter tidak valid untuk strategi ini."}
    target, n = g("target", "asset"), len(DATES)
    if target == "asset":
        if strat in NEEDV and asset not in VOL:
            return {"error": "Strategi ini (breakout/OBV) butuh kolom Volume pada CSV aset ini."}
        v, K, syms, smax, SECT = VOL.get(asset), 1, [asset], 0, None

        def run(px):
            c = px[asset]
            e, t, _, dl = backtest(c, signals(strat, c, v, fast, slow, P["vm"], P["lo"]), P["stop"], cap, P["fee"], P["lot"], P["rules"], P["rules"])
            npos = [0] * n
            for t_ in t:
                for j in range(t_["i0"], t_["i1"]):
                    npos[j] = 1
            return e, t, npos, dl
        bh = [cap * PRICES[asset][i] / PRICES[asset][0] for i in range(n)]
    else:
        rules = g("rules", 1) == 1 and grp == "IDX"
        only = g("lq", 0) == 1 and grp == "IDX"
        syms = [s for s in GROUPS[grp] if not (rules and s == "IHSG") and not (only and s not in LQ45) and not (strat in NEEDV and s not in VOL)]
        if len(syms) < 2:
            return {"error": "Butuh minimal 2 saham."}
        K, smax_sect, rank = max(1, g("k", 10)), sect_args(g, grp), g("rank", "liq")
        smax, SECT = smax_sect

        def run(px):
            sg = {s: signals(strat, px[s], VOL.get(s), fast, slow, P["vm"], True) for s in syms}
            e, t, npos, dl = run_port(syms, sg, K, make_rank(rank, syms, px), P["stop"], cap, P["fee"], rules, px=px, smax=smax, sect=SECT)[:4]
            return e, t, npos, dl
        bh = [cap * sum(PRICES[s][i] / PRICES[s][0] for s in syms) / len(syms) for i in range(n)]
    px0 = {s: PRICES[s] for s in syms}
    eq, tr, npos, dl0 = run(px0)
    z0 = stats(eq, tr)
    wins = list(STRESS_WINDOWS)
    if g("sf", "") and g("st", ""):
        wins.append(("Kustom", g("sf", ""), g("st", "")))
    hist = []
    for name, d0, d1 in wins:
        idx = [i for i, d in enumerate(DATES) if d0 <= d.isoformat() <= d1]
        if len(idx) < 5:
            hist.append(dict(name=name, d0=d0, d1=d1, covered=False)); continue
        a_, b_ = idx[0], idx[-1]
        seg, pk, mdd = eq[a_:b_ + 1], eq[a_], 0.0
        for x in seg:
            pk = max(pk, x); mdd = max(mdd, (pk - x) / pk)
        hist.append(dict(name=name, d0=DATES[a_].isoformat(), d1=DATES[b_].isoformat(), covered=True, partial=DATES[0].isoformat() > d0 or DATES[-1].isoformat() < d1,
                         bars=len(idx), ret=seg[-1] / seg[0] - 1, mdd=mdd, worst=min(eq[i] / eq[i - 1] - 1 for i in range(max(a_, 1), b_ + 1)),
                         bh=bh[b_] / bh[a_] - 1, expo=sum(npos[a_:b_ + 1]) / (b_ - a_ + 1) / K))
    if target == "asset":  # waktu guncangan: saat eksposur tertinggi (tengah trade terpanjang / hari dengan posisi terbanyak)
        t0 = (lambda L: (L["i0"] + L["i1"]) // 2)(max(tr, key=lambda t: t["i1"] - t["i0"])) if tr else n // 2
    else:
        t0 = npos.index(max(npos))
    t0 = max(5, min(n - 40, t0))
    SC = [("Gap −10% semua aset", [(0, -.10)], 0), ("Gap −20% semua aset", [(0, -.20)], 0), ("Gap −30% semua aset", [(0, -.30)], 0),
          ("Crash bertahap −5%/hari × 5", [(i, -.05) for i in range(5)], 0), ("Volatilitas ×3 selama 30 hari", [], 3)]
    shocks = []
    for name, steps, vx in SC:
        e, t, _, dl = run(shocked(syms, t0, steps, vx))
        z = stats(e, t)
        shocks.append(dict(name=name, ret=z["ret"], delta=z["ret"] - z0["ret"], mdd=z["mdd"], worst=min(e[i] / e[i - 1] - 1 for i in range(1, n)), dl=dl,
                           eq=[round(x / cap * 100, 2) for x in e]))
    return dict(ccy="Rp" if grp == "IDX" else "$", src=SRC, target=target, t0=DATES[t0].isoformat(), hist=hist, shocks=shocks,
                base=dict(ret=z0["ret"], mdd=z0["mdd"], dl=dl0, worst=min(eq[i] / eq[i - 1] - 1 for i in range(1, n)), n=len(tr)),
                dates=[d.isoformat() for d in DATES], eq=[round(x / cap * 100, 2) for x in eq])


def mwf(q):
    """Walk-forward pada banyak saham sekaligus + ringkasan stabilitas parameter."""
    P = common(q); g = P["g"]; grp, strat = P["grp"], P["strat"]
    rules = g("rules", 1) == 1 and grp == "IDX"
    only = g("lq", 0) == 1 and grp == "IDX"
    syms = [s for s in GROUPS[grp] if not (rules and s == "IHSG") and not (only and s not in LQ45) and not (strat in NEEDV and s not in VOL)]
    if len(syms) < 2:
        return {"error": "Butuh minimal 2 saham."}
    fs, ss, gl, okc = grid_for(strat)
    rows, freq, sfreq, nf, chg = [], {}, {}, 0, []
    for s in syms:
        d = walkforward(dict(q, asset=[s]))
        if "error" in d:
            if rows == [] and s == syms[-1]:
                return d
            continue
        F = d["folds"]
        for f in F:
            k = (f["a"], f["b"]); freq[k] = freq.get(k, 0) + 1; sfreq[f["st"]] = sfreq.get(f["st"], 0) + 1
        nf += len(F)
        ch = sum((F[i]["a"], F[i]["b"], F[i]["st"]) != (F[i - 1]["a"], F[i - 1]["b"], F[i - 1]["st"]) for i in range(1, len(F))) / max(1, len(F) - 1)
        chg.append(ch)
        rows.append(dict(s=s, lq=s in LQ45, oosS=d["so"]["sharpe"], isS=d["mean_is"], eff=d["eff"], oosR=d["so"]["ret"], bhR=d["sb"]["ret"],
                         uniq=d["distinct"], chg=ch, folds=len(F)))
    if not rows:
        return {"error": "Tidak ada saham yang bisa diproses."}
    med = lambda a: sorted(a)[len(a) // 2] if a else None
    top = sorted(freq.items(), key=lambda kv: -kv[1])[:8]
    return dict(ccy="Rp" if grp == "IDX" else "$", src=SRC, gl=gl, n=len(rows), nf=nf, rows=rows, fs=fs, ss=ss,
                counts=[[freq.get((a, b), 0) for b in ss] for a in fs], stops=sorted(sfreq.items()), ostop=g("ostop", 0) == 1,
                top=[dict(a=k[0], b=k[1], n=c, share=c / nf) for k, c in top], medOOS=med([r["oosS"] for r in rows]),
                medIS=med([r["isS"] for r in rows]), pos=sum(r["oosS"] > 0 for r in rows) / len(rows),
                beat=sum(r["oosR"] > r["bhR"] for r in rows) / len(rows), medEff=med([r["eff"] for r in rows if r["eff"] is not None]),
                chg=sum(chg) / len(chg), modal=top[0][1] / nf)


DEF_PARAMS = {"sma": (20, 60), "brk": (20, 10), "rsi": (14, 30), "bb": (20, 2), "macd": (12, 26), "obv": (20, 50)}
STRAT_NAMES = {"sma": "SMA crossover", "brk": "Breakout + volume", "rsi": "RSI mean-reversion", "bb": "Bollinger mean-reversion",
               "macd": "MACD crossover", "obv": "Volume (OBV + tren)"}


def compare(q):
    """Jalankan keenam strategi (tanpa dan dengan filter tren SMA) pada satu saham, periode & biaya yang sama."""
    P = common(q); g = P["g"]; asset, cap = P["asset"], P["cap"]
    ftf, wfm = g("ftf", 200), g("wfm", 0) == 1
    ftf = 0 if ftf < 10 else min(ftf, 500)
    c, v, n = PRICES[asset], VOL.get(asset), len(DATES)
    variants = [(k, 0) for k in DEF_PARAMS] + ([(k, ftf) for k in DEF_PARAMS] if ftf else [])
    i0 = ftf if (ftf and not wfm) else 0  # semua baris dinilai dari titik awal yang sama (adil terhadap warm-up filter)
    saved, rows, dates, bhc = getattr(CTX, "tf", 0), [], None, None
    try:
        for k, tfv in variants:
            if k in NEEDV and v is None:
                continue
            CTX.tf = tfv
            if wfm:
                d = walkforward(dict(q, strat=[k], ostop=["0"]))
                if "error" in d:
                    continue
                st, eq, params = d["so"], d["eq"], "otomatis"
                if dates is None:
                    dates, bhc = d["dates"], d["bh"]
            else:
                a_, b_ = DEF_PARAMS[k]
                e, tr, expo, dl = backtest(c, signals(k, c, v, a_, b_, P["vm"], P["lo"]), P["stop"], cap, P["fee"], P["lot"], P["rules"], P["rules"])
                eq, tr = e[i0:], [t for t in tr if t["i1"] > i0]
                st, params = stats(eq, tr), f"{a_} / {b_}"
                st["expo"] = expo
                if dates is None:
                    dates, bhc = [d.isoformat() for d in DATES[i0:]], [cap * c[i] / c[i0] for i in range(i0, n)]
            rows.append(dict(key=k, name=STRAT_NAMES[k], tf=tfv, params=params, ret=st["ret"], cagr=st["cagr"], sharpe=st["sharpe"], sortino=st["sortino"],
                             mdd=st["mdd"], pf=st["pf"], win=st["win"], n=st["n"], expo=st.get("expo"), eq=[round(x / eq[0] * 100, 2) for x in eq]))
    finally:
        CTX.tf = saved
    if not rows:
        return {"error": "Tidak ada strategi yang bisa dijalankan pada aset ini."}
    sb = stats(bhc, [])
    for r in rows:  # kriteria dasar (patokan kasar, bukan jaminan)
        r["crit"] = [r["ret"] > sb["ret"], r["sharpe"] > .5, (r["pf"] or 0) > 1.3, r["n"] >= 30]
        r["score"] = sum(r["crit"])
    return dict(ccy="Rp" if P["grp"] == "IDX" else "$", src=SRC, asset=asset, wf=wfm, ftf=ftf, dates=dates, bh=[round(x / bhc[0] * 100, 2) for x in bhc],
                bs=dict(ret=sb["ret"], cagr=sb["cagr"], sharpe=sb["sharpe"], sortino=sb["sortino"], mdd=sb["mdd"]), rows=rows)


def orderflow_api(q):
    g = lambda k, d: type(d)(q.get(k, [d])[0])
    sym = g("sym", "BBCA").upper()
    if sym == "IHSG" or sym not in GROUPS.get("IDX", []):
        return {"error": "Order flow hanya untuk saham IDX (bukan indeks IHSG)."}
    try:
        src = "zapi" if g("src", "auto") == "zapi" else "auto"
        return orderflow.get(sym, PRICES[sym][-1], g("big", 300), g("small", 20), g("win", 300), g("levels", 10), src, g("brk", 0) == 1)
    except zapi.ZapiError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": f"Order flow gagal: {e}"}


def zapi_status():
    u = zapi.usage()
    k = zapi.api_key()
    S = dict(zapi.SYNC)
    S["errors"], S["skipped"] = list(S["errors"])[-6:], len(S["skipped"])
    n_b, _ = zapi.plan("backfill", LQ45, DATA_DIR)
    n_d, _ = zapi.plan("daily", LQ45, DATA_DIR)
    return dict(key=bool(k), hint=("…" + k[-4:]) if k and len(k) > 8 else "", base=zapi.base(), used=u.get("count", 0), budget=zapi.budget(),
                month=u.get("month"), sync=S, src=SRC, cost_backfill=n_b, cost_daily=n_d, dropped=list(DROPPED), n_files=len(glob.glob(os.path.join(DATA_DIR, "*.JK.csv"))))


def zapi_sync_start(body):
    extra = [x.strip().upper() for x in str(body.get("extra", "")).replace(";", ",").split(",")]
    extra = [x for x in extra if x.isalnum() and 2 <= len(x) <= 6]
    syms = list(dict.fromkeys(LQ45 + extra))
    err = zapi.start_sync(str(body.get("mode", "")), syms, DATA_DIR, on_done=reload_data)
    return {"error": err} if err else {"ok": True}


def zapi_test():
    try:
        g = zapi.brokers_groups()
        return {"ok": True, "foreign": len(g["asing"]), "local": len(g["lokal"]), "used": zapi.usage().get("count", 0), "budget": zapi.budget()}
    except zapi.ZapiError as e:
        return {"error": str(e)}


EXP_FILE = os.path.join(HERE, "experiments.json")


def read_exps():
    try:
        with open(EXP_FILE, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, list) else []
    except (OSError, ValueError):
        return []


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _send(self, body, ctype="application/json", code=200):
        self.send_response(code)
        self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(body)))
        self.end_headers(); self.wfile.write(body)

    def _token_ok(self):
        """Endpoint yang memakai kuota hanya melayani halaman kita sendiri: Host localhost + token yang disisipkan ke index.html."""
        local = ("localhost", "127.0.0.1")
        org = self.headers.get("Origin")
        return (self.headers.get("Host", "").split(":")[0] in local and (not org or urlparse(org).hostname in local)
                and hmac.compare_digest(self.headers.get("X-QT-Token", ""), TOKEN))

    def do_GET(self):
        u = urlparse(self.path)
        API = {"/api/data": payload, "/api/universe": universe, "/api/walkforward": walkforward, "/api/portfolio": portfolio,
               "/api/pwf": pwf, "/api/montecarlo": montecarlo, "/api/stress": stress, "/api/mwf": mwf, "/api/compare": compare, "/api/orderflow": orderflow_api}
        if u.path == "/api/zapi/status":
            self._send(json.dumps(zapi_status()).encode()); return
        if u.path in API:
            qd = parse_qs(u.query)
            if u.path == "/api/orderflow" and qd.get("src", [""])[0] == "zapi" and not self._token_ok():
                self.send_error(403, "token tidak valid"); return
            try:
                tf = int(float(qd.get("tf", ["0"])[0] or 0))
            except ValueError:
                tf = 0
            CTX.tf = 0 if tf < 10 else min(tf, 500)
            self._send(json.dumps(API[u.path](qd)).encode())
        elif u.path == "/api/exps":
            self._send(json.dumps(read_exps()).encode())
        elif u.path in ("/", "/index.html"):
            self._send(open(os.path.join(HERE, "index.html"), "rb").read().replace(b"__QT_TOKEN__", TOKEN.encode()), "text/html; charset=utf-8")
        else:
            self.send_error(404)

    def do_POST(self):  # eksperimen (file) dan aksi Zapi (memakai kuota; wajib token)
        u = urlparse(self.path)
        local = ("localhost", "127.0.0.1")
        org = self.headers.get("Origin")
        host_ok = self.headers.get("Host", "").split(":")[0] in local and (not org or urlparse(org).hostname in local)
        if u.path in ("/api/zapi/test", "/api/zapi/sync"):
            if not self._token_ok():
                self.send_error(403, "token tidak valid"); return
            ln = int(self.headers.get("Content-Length", "0") or 0)
            try:
                body = json.loads(self.rfile.read(min(ln, 10_000)) or b"{}")
            except ValueError:
                self.send_error(400); return
            self._send(json.dumps(zapi_test() if u.path.endswith("test") else zapi_sync_start(body)).encode()); return
        if u.path != "/api/exps" or not host_ok:
            self.send_error(403); return
        ln = int(self.headers.get("Content-Length", "0") or 0)
        if ln > 8_000_000:
            self.send_error(413); return
        try:
            data = json.loads(self.rfile.read(ln))
            assert isinstance(data, list) and len(data) <= 60
        except Exception:
            self.send_error(400); return
        tmp = EXP_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(tmp, EXP_FILE)
        self._send(json.dumps({"ok": True, "n": len(data)}).encode())


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    print(f"Quant Terminal berjalan di http://localhost:{port}  (Ctrl+C untuk berhenti)")
    threading.Timer(.8, lambda: webbrowser.open(f"http://localhost:{port}")).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
