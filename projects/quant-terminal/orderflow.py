"""Order flow: order book + tape (time & sales) + broker summary untuk SATU saham IDX.

Sumber data:
  1) FILE  : orderflow/live/<SIMBOL>.json  (+ opsional <SIMBOL>_broker.csv) yang ditulis oleh skrip Anda sendiri dari
             sumber data berlisensi/resmi (lihat orderflow/README.txt). Dibaca ulang tiap permintaan.
  2) SIMULASI (cadangan, bila file tidak ada): data acak untuk mendemonstrasikan alat. BUKAN data pasar.

PENTING: order book bersifat anonim. Yang dihitung di sini adalah PROKSI berbasis ukuran order dan arah transaksi,
bukan identitas pelaku ("ritel"/"bandar"). Ukuran besar != pasti institusi; order besar di buku bisa dibatalkan (spoofing)."""
import csv, json, math, os, random, threading, time
from collections import deque
from datetime import datetime, timedelta, timezone
import zapi

HERE = os.path.dirname(os.path.abspath(__file__))
LIVE = os.path.join(HERE, "orderflow", "live")
GROUPS_FILE = os.path.join(HERE, "orderflow", "broker_groups.json")
LOCK = threading.Lock()
SIMS, FILES = {}, {}
ZLOCK = threading.Lock()
PHASES = [("netral", 0.0), ("akumulasi", 0.18), ("distribusi", -0.18)]
BRK = [("B%02d" % i, g) for i, g in enumerate(["asing"] * 3 + ["institusi"] * 3 + ["ritel"] * 6, 1)]  # kode SIMULASI, bukan broker nyata


def tick(p):  # fraksi harga IDX
    return 1 if p < 200 else 2 if p < 500 else 5 if p < 2000 else 10 if p < 5000 else 25


class Sim:
    def __init__(self, sym, last, t0=None):
        self.r = random.Random(sum(map(ord, sym)) * 7919)
        self.last, self.mid, self.t = float(last), float(last), (time.time() if t0 is None else t0)
        self.trades, self.phase, self.until = deque(maxlen=3000), PHASES[0], self.t + 60
        self.brk, self.by_g = {b: [0, 0] for b, _ in BRK}, {}
        for b, g in BRK:
            self.by_g.setdefault(g, []).append(b)

    def step(self, now):
        dt = min(now - self.t, 40.0)
        if dt <= 0:
            return
        t0, self.t = now - dt, now
        n = int(dt * 1.6 + self.r.random())
        for k in range(n):
            ts, r = t0 + dt * (k + 1) / n, self.r
            if ts > self.until:
                self.phase, self.until = r.choice(PHASES), ts + r.uniform(45, 120)
            bias, tk = self.phase[1], tick(self.mid)
            bid = math.floor(self.mid / tk) * tk
            ask = bid + tk * r.choice([1, 1, 2])
            side = 1 if r.random() < .5 + bias else -1
            big = r.random() < (.05 + (.12 if side * bias > 0 else .04 if bias else 0))  # lot besar lebih sering searah fase
            lots = int(r.lognormvariate(math.log(350), .5)) if big else max(1, int(r.lognormvariate(math.log(4), .9)))
            self.trades.append(dict(ts=ts, price=ask if side > 0 else bid, lots=lots, side="B" if side > 0 else "S"))
            self.mid += tk * side * (r.random() < (.25 if big else .10))
            self.mid = min(max(self.mid, self.last * .94), self.last * 1.06)
            ag = r.choice([b for g in (("asing", "institusi") if big else ("ritel",)) for b in self.by_g[g]])
            cp = r.choice([b for b, _ in BRK])
            buyer, seller = (ag, cp) if side > 0 else (cp, ag)
            self.brk[buyer][0] += lots; self.brk[seller][1] += lots

    def book(self, now, levels=10):
        r, bias = random.Random(int(now * 2) + len(self.trades)), self.phase[1]
        tk = tick(self.mid)
        bp = math.floor(self.mid / tk) * tk
        ap = bp + tk
        out = {}
        for nm, p0, sgn, f in (("bids", bp, -1, 1 + bias * 3), ("asks", ap, 1, 1 - bias * 2)):
            rows, p = [], p0
            wall = r.randrange(2, 8) if r.random() < .14 else -1
            for i in range(levels):
                lots = r.lognormvariate(math.log(120), .6) * (1 + .08 * i) * f * (r.uniform(6, 10) if i == wall else 1)
                rows.append([p, max(1, int(lots))])
                p += sgn * tick(p - (tick(p) if sgn < 0 else 0))
            out[nm] = rows
        return out


def _num(x):
    return float(x) if x not in (None, "") else None


def _sorted_book(d):
    bids = sorted(([float(p), int(l)] for p, l in d.get("bids", []) if float(p) > 0 and int(l) > 0), key=lambda r: -r[0])
    asks = sorted(([float(p), int(l)] for p, l in d.get("asks", []) if float(p) > 0 and int(l) > 0), key=lambda r: r[0])
    return {"bids": bids, "asks": asks}


def read_file(sym):
    """Kembalikan (book, trades, broker_rows, age, error) dari orderflow/live/<SYM>.json, atau None bila file tidak ada."""
    fp = os.path.join(LIVE, sym + ".json")
    if not os.path.isfile(fp):
        return None
    try:
        d = json.load(open(fp, encoding="utf-8"))
        book = _sorted_book(d)
        if not book["bids"] or not book["asks"]:
            raise ValueError("bids/asks kosong")
        st = FILES.setdefault(sym, deque(maxlen=3000))
        keys = {(t["ts"], t["price"], t["lots"]) for t in st}
        for t in sorted(d.get("trades", []), key=lambda t: t["ts"]):
            k = (float(t["ts"]), float(t["price"]), int(t["lots"]))
            if k in keys:
                continue
            side = t.get("side")
            if side not in ("B", "S"):  # klasifikasi quote rule, lalu tick rule
                pr = k[1]
                side = "B" if pr >= book["asks"][0][0] else "S" if pr <= book["bids"][0][0] else (
                    ("B" if pr > st[-1]["price"] else "S" if pr < st[-1]["price"] else st[-1]["side"]) if st else "?")
            st.append(dict(ts=k[0], price=k[1], lots=k[2], side=side)); keys.add(k)
        rows = {}
        bf = os.path.join(LIVE, sym + "_broker.csv")
        if os.path.isfile(bf):
            for r in csv.DictReader(open(bf, encoding="utf-8")):
                rows[r["broker"].strip().upper()] = [float(r["buy_lot"] or 0), float(r["sell_lot"] or 0)]
        return book, list(st), rows, time.time() - os.path.getmtime(fp), None
    except Exception as e:
        return None, [], {}, 0, f"File {sym}.json tidak valid: {e}"


def broker_summary(rows, groups):
    if not rows:
        return None
    m = {b.upper(): g for g, l in groups.items() for b in l}
    G = {}
    for b, (bl, sl) in rows.items():
        g = m.get(b, "lainnya"); x = G.setdefault(g, [0, 0]); x[0] += bl; x[1] += sl
    net = sorted(((b, bl - sl, m.get(b, "lainnya")) for b, (bl, sl) in rows.items()), key=lambda r: -r[1])
    pos = sum(n for _, n, _ in net if n > 0)
    return dict(groups=sorted(({"g": g, "buy": a, "sell": s, "net": a - s} for g, (a, s) in G.items()), key=lambda r: -r["net"]),
                buyers=[{"b": b, "net": n, "g": g} for b, n, g in net[:5] if n > 0],
                sellers=[{"b": b, "net": n, "g": g} for b, n, g in net[::-1][:5] if n < 0],
                conc=(sum(n for _, n, _ in net[:5] if n > 0) / pos) if pos else None, mapped=bool(m))


def analyze(book, trades, big, small, win, levels):
    bids, asks = book["bids"][:levels], book["asks"][:levels]
    bl, al = sum(l for _, l in bids), sum(l for _, l in asks)
    wb, wa = sum(l / (i + 1) for i, (_, l) in enumerate(bids)), sum(l / (i + 1) for i, (_, l) in enumerate(asks))
    imb, wimb = (bl - al) / (bl + al) if bl + al else 0.0, (wb - wa) / (wb + wa) if wb + wa else 0.0
    lv = sorted(l for _, l in bids + asks)
    med = lv[len(lv) // 2] if lv else 1
    walls = [dict(side="B", price=p, lots=l, x=l / med) for p, l in bids if l >= 3 * med] + [dict(side="A", price=p, lots=l, x=l / med) for p, l in asks if l >= 3 * med]
    now = trades[-1]["ts"] if trades else time.time()
    sel = [t for t in trades if t["ts"] >= now - win and t["side"] in ("B", "S")]
    S = {k: dict(buy=0, sell=0, n=0) for k in ("small", "mid", "big")}
    cv = dict(all=0, big=0, small=0)
    ca, cb, cs, tl = [], [], [], []
    for t in sel:
        k = "big" if t["lots"] >= big else "small" if t["lots"] <= small else "mid"
        sg = t["lots"] if t["side"] == "B" else -t["lots"]
        S[k]["buy" if sg > 0 else "sell"] += abs(sg); S[k]["n"] += 1
        cv["all"] += sg; cv["big"] += sg if k == "big" else 0; cv["small"] += sg if k == "small" else 0
        ca.append(cv["all"]); cb.append(cv["big"]); cs.append(cv["small"]); tl.append(time.strftime("%H:%M:%S", time.localtime(t["ts"])))
    st = max(1, math.ceil(len(sel) / 150))
    tb = sum(S[k]["buy"] for k in S); ts_ = sum(S[k]["sell"] for k in S)
    bt = S["big"]["buy"] + S["big"]["sell"]
    c1 = wimb
    c2 = (S["big"]["buy"] - S["big"]["sell"]) / bt if bt else 0.0
    c3 = (tb - ts_) / (tb + ts_) if tb + ts_ else 0.0
    score = (.25 * c1 + .45 * c2 + .30 * c3) if bt else (.4 * c1 + .6 * c3)
    nz = [c for c in (c1, c2 if bt else 0, c3) if abs(c) > .05]
    agree = bool(nz) and (all(c > 0 for c in nz) or all(c < 0 for c in nz))
    n = len(sel)
    conf = "rendah (sampel < 30 transaksi)" if n < 30 else ("sedang (komponen searah)" if agree and n >= 100 else "rendah (komponen tidak searah / sampel kecil)")
    bn = S["big"]["buy"] - S["big"]["sell"]; sn = S["small"]["buy"] - S["small"]["sell"]
    sgf = lambda x, tot: abs(x) / tot >= .10 if tot else False
    if sgf(bn, bt) and sgf(sn, S["small"]["buy"] + S["small"]["sell"]) and bn * sn < 0:
        pat = ("Lot besar net BELI sementara lot kecil net JUAL — pola yang sering ditafsirkan sebagai akumulasi" if bn > 0 else
               "Lot besar net JUAL sementara lot kecil net BELI — pola yang sering ditafsirkan sebagai distribusi") + " (hanya tafsiran, bukan bukti identitas pelaku)."
    elif sgf(bn, bt) and bn * sn > 0:
        pat = "Lot besar dan kecil bergerak searah (" + ("beli" if bn > 0 else "jual") + ")."
    else:
        pat = "Tidak ada pola jelas antara lot besar dan lot kecil."
    vw = sum(t["price"] * t["lots"] for t in sel) / sum(t["lots"] for t in sel) if sel else None
    mid = (bids[0][0] + asks[0][0]) / 2 if bids and asks else None
    return dict(book=dict(bids=bids, asks=asks), mid=mid, spread=(asks[0][0] - bids[0][0]) if bids and asks else None, imb=imb, wimb=wimb, walls=walls,
                stats=S, vwap=vw, n=n, unk=sum(1 for t in trades if t["ts"] >= now - win and t["side"] not in ("B", "S")), c=dict(book=c1, big=c2, all=c3),
                score=score, label="BELI" if score > .25 else "JUAL" if score < -.25 else "NETRAL", agree=agree, conf=conf, pattern=pat,
                cvd=dict(t=tl[::st], all=ca[::st], big=cb[::st], small=cs[::st]),
                tape=[dict(t=time.strftime("%H:%M:%S", time.localtime(x["ts"])), price=x["price"], lots=x["lots"], side=x["side"], big=x["lots"] >= big)
                      for x in trades[-30:][::-1]])


ZSTATE = {}
WIB = timezone(timedelta(hours=7))


def market_open_wib(now=None):
    """Perkiraan jam bursa IDX (WIB), tidak mencakup hari libur: Sen-Kam 09:00-12:00 & 13:30-16:00; Jum 09:00-11:30 & 14:00-16:00."""
    d = datetime.fromtimestamp(now or time.time(), WIB)
    m = d.hour * 60 + d.minute
    if d.weekday() >= 5:
        return False
    return (540 <= m < 690 or 840 <= m < 960) if d.weekday() == 4 else (540 <= m < 720 or 810 <= m < 960)


def _zapi_trades(sym, st, first):
    """Ambil running-trades (cetakan terbaru dulu), beri cap waktu, dedupe, simpan menaik. Kembalikan flag gap."""
    items, cur = [], None
    for _ in range(3 if first else 1):
        rt = zapi.running_trades(sym, cur)
        page = (rt.get("items") or []) if isinstance(rt, dict) else []
        items += page
        cur = rt.get("nextCursor") if isinstance(rt, dict) else None
        if not cur or not page:
            break
    now = time.time()
    day = datetime.fromtimestamp(now, WIB).date()
    out, prev, started = [], None, False
    for it in items:  # terbaru -> terlama; jam turun, bila naik berarti kemarin
        try:
            h, m, s_ = (int(x) for x in str(it["time"]).split(":"))
            lots, price, seq = int(it["lots"]), float(it["price"]), it.get("sequence", 0)
        except (KeyError, ValueError, TypeError):
            continue
        t = datetime(day.year, day.month, day.day, h, m, s_, tzinfo=WIB).timestamp()
        if not started:
            if t > now + 120:
                day -= timedelta(days=1); t -= 86400
            started = True
        elif t > prev + 1:
            day -= timedelta(days=1); t -= 86400
        prev = t
        act = str(it.get("action", "")).upper()
        out.append(dict(ts=t, price=price, lots=lots, side="B" if act == "BUY" else "S" if act == "SELL" else "?", seq=seq))
    keys = {(x["seq"], x["ts"], x["price"], x["lots"]) for x in st["dq"]}
    new = [x for x in out if (x["seq"], x["ts"], x["price"], x["lots"]) not in keys]
    gap = bool(st["dq"]) and len(new) == len(out) and len(out) >= 15  # tidak ada tumpang tindih dengan data sebelumnya
    for x in sorted(new, key=lambda x: (x["ts"], x["seq"] if isinstance(x["seq"], (int, float)) else 0)):
        st["dq"].append(x)
    return gap


def get_zapi(sym, levels, want_brk):
    """Order flow dari Zapi (Pluang): 2 request per pemanggilan baru (orderbook + running-trades), +1 bila broker summary diminta."""
    st = ZSTATE.setdefault(sym, dict(dq=deque(maxlen=3000), first=True))
    ob = zapi.orderbook(sym)
    pairs = lambda arr: [[float(r["price"]), int(r["lots"])] for r in (arr or []) if isinstance(r, dict) and r.get("price") and r.get("lots")]
    book = _sorted_book({"bids": pairs(ob.get("bids") if isinstance(ob, dict) else None), "asks": pairs(ob.get("asks") if isinstance(ob, dict) else None)})
    gap = _zapi_trades(sym, st, st["first"])
    st["first"] = False
    rows, groups = {}, {}
    if want_brk:
        bs = zapi.broker_summary(sym)
        for side, idx in (("buyers", 0), ("sellers", 1)):
            for r in (bs.get(side) or []) if isinstance(bs, dict) else []:
                b = str(r.get("broker", "")).upper()
                if b:
                    rows.setdefault(b, [0, 0])[idx] += float(r.get("lots") or 0)
        groups = zapi.brokers_groups()
    return book, list(st["dq"]), rows, groups, gap


def get(sym, last, big=300, small=20, win=300, levels=10, source="auto", want_brk=False):
    sym = "".join(ch for ch in sym.upper() if ch.isalnum())[:10]
    big, small, win, levels = max(2, int(big)), max(1, int(small)), max(30, int(win)), min(max(int(levels), 3), 10)
    small = min(small, big - 1)
    if source == "zapi":
        with ZLOCK:
            book, trades, rows, zg, gap = get_zapi(sym, levels, want_brk)
            groups = dict(zg)
            if os.path.isfile(GROUPS_FILE):
                try:
                    groups.update(json.load(open(GROUPS_FILE, encoding="utf-8")))  # pemetaan buatan Anda menimpa klasifikasi Pluang
                except Exception:
                    pass
            out = analyze(book, trades, big, small, win, levels)
        bsum = broker_summary(rows, groups)
        if bsum:
            bsum["partial"] = True  # sumber hanya memberi 10 broker net teratas per sisi
        last_t = trades[-1]["ts"] if trades else None
        out.update(src="ZAPI", age=0.0, sym=sym, brk=bsum, big=big, small=small, win=win, phase=None, gap=gap,
                   market_open=market_open_wib(), last_trade=time.strftime("%H:%M:%S", time.localtime(last_t)) if last_t else None,
                   quota=dict(used=zapi.usage().get("count", 0), budget=zapi.budget()))
        return out
    with LOCK:
        now, groups = time.time(), {}
        if os.path.isfile(GROUPS_FILE):
            try:
                groups = json.load(open(GROUPS_FILE, encoding="utf-8"))
            except Exception:
                groups = {}
        fr = read_file(sym)
        if fr is not None:
            book, trades, rows, age, err = fr
            if err:
                return {"error": err}
            src = "FILE"
        else:
            sim = SIMS.get(sym)
            if sim is None:  # isi riwayat 10 menit terakhir agar tape/CVD langsung terisi
                sim = SIMS.setdefault(sym, Sim(sym, last, t0=now - 600))
                for k in range(1, 21):
                    sim.step(now - 600 + 30 * k)
            sim.step(now)
            book, trades, rows, age, src = sim.book(now, levels), list(sim.trades), sim.brk, 0.0, "SIMULASI"
            groups = {g: [b for b, gg in BRK if gg == g] for g in ("asing", "institusi", "ritel")}
        out = analyze(book, trades, big, small, win, levels)
    out.update(src=src, age=age, sym=sym, brk=broker_summary(rows, groups), big=big, small=small, win=win,
               phase=(SIMS[sym].phase[0] if src == "SIMULASI" else None))
    return out
