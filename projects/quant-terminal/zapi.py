"""Klien Zapi (https://zapi.ink) untuk Quant Terminal. Hanya stdlib.

KUNCI API: isi file zapi_key.txt (satu baris) di folder aplikasi, ATAU set variabel lingkungan ZAPI_KEY.
Kunci tidak pernah dikirim ke browser dan tidak pernah dicatat di log.

KUOTA: paket gratis Zapi = 600 request/bulan (100/menit). Modul ini mencatat tiap panggilan jaringan ke zapi_usage.json
(PERKIRAAN lokal; hitungan resmi ada di dashboard Zapi) dan berhenti saat anggaran lokal (ZAPI_BUDGET, default 500) habis.
Respons di-cache di memori (TTL per endpoint) sehingga pemanggilan berulang tidak memakai kuota.

Endpoint yang dipakai (semua GET https://api.zapi.ink/v1/<kategori:sumber>/<endpoint>, header x-api-key):
  finance:idx/stock-history      riwayat harian satu saham (1 request/saham)       -> data/<KODE>.JK.csv
  finance:idx/stock-summary      ringkasan SEMUA saham pada satu tanggal (1 request/hari bursa) -> pembaruan harian
  finance:pluang/orderbook       antrean bid/ask satu saham                          -> panel Order flow
  finance:pluang/running-trades  cetakan transaksi (sisi agresor BUY/SELL)           -> panel Order flow
  finance:pluang/broker-summary  10 broker net beli/jual teratas                     -> panel Order flow (opsional)
  finance:pluang/brokers         klasifikasi broker LOCAL/FOREIGN versi Pluang       -> pengelompokan broker"""
import json, os, socket, threading, time, urllib.error, urllib.parse, urllib.request
from datetime import date, datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
USAGE_FILE = os.environ.get("ZAPI_USAGE_FILE") or os.path.join(HERE, "zapi_usage.json")
LOCK = threading.Lock()
CACHE = {}
WIB = timezone(timedelta(hours=7))


class ZapiError(Exception):
    pass


def base():
    return os.environ.get("ZAPI_BASE", "https://api.zapi.ink").rstrip("/")


def api_key():
    k = os.environ.get("ZAPI_KEY", "").strip()
    if not k:
        fp = os.path.join(HERE, "zapi_key.txt")
        if os.path.isfile(fp):
            with open(fp, encoding="utf-8-sig") as f:
                lines = [x.strip() for x in f.read().splitlines() if x.strip() and not x.strip().startswith("#")]
            k = lines[0] if lines else ""
    return k or None


def budget():
    try:
        return max(1, int(os.environ.get("ZAPI_BUDGET", "500")))
    except ValueError:
        return 500


def usage():
    m = time.strftime("%Y-%m")
    try:
        with open(USAGE_FILE, encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError):
        d = {}
    return d if d.get("month") == m else {"month": m, "count": 0}


def _bump():
    with LOCK:
        d = usage(); d["count"] = int(d.get("count", 0)) + 1
        tmp = USAGE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f)
        os.replace(tmp, USAGE_FILE)
        return d["count"]


def remaining():
    return max(0, budget() - int(usage().get("count", 0)))


def _err_msg(e):
    try:
        d = json.loads(e.read().decode("utf-8", "replace"))
        return str(d.get("message") or d.get("content") or "")[:200]
    except Exception:
        return ""


def call(path, params=None, ttl=0, timeout=25):
    """GET /v1/<path>. Mengembalikan isi `data` dari amplop {project, data, timestamp}. Hanya panggilan jaringan yang memakai kuota."""
    key = api_key()
    if not key:
        raise ZapiError("API key Zapi belum diisi: taruh di file zapi_key.txt atau variabel lingkungan ZAPI_KEY.")
    q = {k: v for k, v in (params or {}).items() if v not in (None, "")}
    url = f"{base()}/v1/{path}" + ("?" + urllib.parse.urlencode(sorted(q.items())) if q else "")
    with LOCK:
        hit = CACHE.get(url)
    if hit and hit[0] > time.time():
        return hit[1]
    if remaining() <= 0:
        raise ZapiError(f"Anggaran request lokal bulan ini habis ({usage()['count']}/{budget()}). Naikkan ZAPI_BUDGET bila paket Anda lebih besar, atau tunggu bulan depan.")
    _bump()
    req = urllib.request.Request(url, headers={"x-api-key": key, "Accept": "application/json", "User-Agent": "QuantTerminal/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read()
    except urllib.error.HTTPError as e:
        m = _err_msg(e)
        if e.code == 401:
            raise ZapiError("API key ditolak (401): periksa isi zapi_key.txt / ZAPI_KEY.")
        if e.code == 429:
            raise ZapiError("Limit atau kuota Zapi tercapai (429). Tunggu sebentar, atau cek penggunaan di dashboard Zapi.")
        if e.code == 404:
            raise ZapiError(f"Tidak ditemukan (404){': ' + m if m else ''}")
        raise ZapiError(f"HTTP {e.code}{': ' + m if m else ''}")
    except urllib.error.URLError as e:
        raise ZapiError(f"Tidak bisa menghubungi Zapi: {e.reason}")
    except (socket.timeout, TimeoutError):
        raise ZapiError("Zapi tidak merespons tepat waktu (timeout).")
    try:
        d = json.loads(body)
    except ValueError:
        raise ZapiError("Respons Zapi bukan JSON yang valid.")
    data = d["data"] if isinstance(d, dict) and "project" in d and "data" in d else d
    if ttl > 0:
        with LOCK:
            if len(CACHE) > 400:
                CACHE.clear()
            CACHE[url] = (time.time() + ttl, data)
    return data


# --- pembungkus endpoint -------------------------------------------------------------------------------------------
def brokers_groups():
    """{'asing': [...], 'lokal': [...]} dari klasifikasi Pluang (LOCAL/FOREIGN). Cache 24 jam. Bukan klasifikasi institusi vs ritel."""
    d = call("finance:pluang/brokers", ttl=86400)
    g = {"asing": [], "lokal": []}
    for it in (d.get("items") or []) if isinstance(d, dict) else []:
        c = str(it.get("code", "")).upper()
        if c:
            g["asing" if str(it.get("type", "")).upper() == "FOREIGN" else "lokal"].append(c)
    return g


def orderbook(code):
    return call("finance:pluang/orderbook", {"code": code}, ttl=15)


def running_trades(code, cursor=None):
    return call("finance:pluang/running-trades", {"code": code, "cursor": cursor}, ttl=15)


def broker_summary(code):
    return call("finance:pluang/broker-summary", {"code": code, "net": "true"}, ttl=300)


def stock_history(code, frm):
    return call("finance:idx/stock-history", {"code": code, "from": frm}, ttl=60, timeout=60)


def stock_summary(day):
    return call("finance:idx/stock-summary", {"date": day, "length": 1500}, ttl=60, timeout=60)


# --- sinkronisasi data harian ke CSV -------------------------------------------------------------------------------
SYNC = dict(running=False, mode=None, total=0, done=0, current="", errors=[], skipped=[], written=0, started=0, finished=0, ok=False, message="")


def _csv_last_date(fp):
    try:
        with open(fp, encoding="utf-8") as f:
            lines = [x for x in f.read().splitlines() if x.strip()]
        return lines[-1].split(",")[0] if len(lines) > 1 else None
    except OSError:
        return None


def _fresh(fp):
    return os.path.isfile(fp) and time.time() - os.path.getmtime(fp) < 20 * 3600 and (_csv_last_date(fp) or "") != ""


def wib_today():
    """Tanggal terakhir yang datanya sudah final (pasar tutup 16:00 WIB; dipakai batas 17:00)."""
    now = datetime.now(WIB)
    return now.date() if now.hour >= 17 else now.date() - timedelta(days=1)


def plan(mode, symbols, data_dir):
    """Perkiraan jumlah request untuk sinkronisasi. Kembalikan (jumlah, daftar tugas)."""
    if mode == "backfill":
        todo = [s for s in symbols if not _fresh(os.path.join(data_dir, f"{s}.JK.csv"))]
        return len(todo), todo
    files = [f[:-7] for f in os.listdir(data_dir) if f.endswith(".JK.csv")] if os.path.isdir(data_dir) else []
    lasts = [x for x in (_csv_last_date(os.path.join(data_dir, f"{s}.JK.csv")) for s in files) if x]
    if not lasts:
        return 0, []
    last = date.fromisoformat(min(lasts)); end = wib_today()
    days = [last + timedelta(days=i) for i in range(1, (end - last).days + 1)]
    days = [d for d in days if d.weekday() < 5][-31:]
    return len(days), [d.isoformat() for d in days]


def _run(mode, symbols, data_dir, years, on_done):
    S = SYNC
    try:
        os.makedirs(data_dir, exist_ok=True)
        n, todo = plan(mode, symbols, data_dir)
        S.update(total=n, done=0, skipped=[s for s in symbols if s not in todo] if mode == "backfill" else [])
        if mode == "backfill":
            frm = (date.today() - timedelta(days=int(365 * years))).isoformat()
            for i, s in enumerate(todo):
                S.update(current=s, done=i)
                try:
                    d = stock_history(s, frm)
                except ZapiError as e:
                    S["errors"].append(f"{s}: {e}")
                    if "429" in str(e) or "anggaran" in str(e).lower() or "ditolak" in str(e):
                        break
                    continue
                rows = sorted({(it["date"][:10], float(it["close"]), float(it.get("volume") or 0)) for it in (d.get("items") or [])
                               if it.get("date") and it.get("close")})
                if len(rows) < 100:
                    S["errors"].append(f"{s}: riwayat terlalu pendek ({len(rows)} bar)"); continue
                fp = os.path.join(data_dir, f"{s}.JK.csv")
                with open(fp + ".tmp", "w", encoding="utf-8") as f:
                    f.write("Date,Close,Volume\n")
                    f.writelines(f"{a},{b},{c}\n" for a, b, c in rows)
                os.replace(fp + ".tmp", fp); S["written"] += 1
        else:
            files = [f[:-7] for f in os.listdir(data_dir) if f.endswith(".JK.csv")]
            for i, day in enumerate(todo):
                S.update(current=day, done=i)
                try:
                    d = stock_summary(day)
                except ZapiError as e:
                    S["errors"].append(f"{day}: {e}")
                    if "429" in str(e) or "anggaran" in str(e).lower() or "ditolak" in str(e):
                        break
                    continue
                m = {str(r.get("StockCode", "")).upper(): r for r in ((d.get("data") if isinstance(d, dict) else None) or [])}
                if not m or not any(str(r.get("Date", ""))[:10] == day for r in m.values()):
                    S["skipped"].append(day); continue  # hari libur / belum ada data
                for s in files:
                    r = m.get(s)
                    fp = os.path.join(data_dir, f"{s}.JK.csv")
                    if r and r.get("Close") and str(r.get("Date", ""))[:10] == day and (_csv_last_date(fp) or "") < day:
                        with open(fp, "a", encoding="utf-8") as f:
                            f.write(f"{day},{float(r['Close'])},{float(r.get('Volume') or 0)}\n")
                        S["written"] += 1
        S["ok"] = S["written"] > 0
        S["message"] = f"selesai: {S['written']} berkas/baris diperbarui, {len(S['skipped'])} dilewati, {len(S['errors'])} galat"
        if S["written"] and on_done:
            on_done()
    except Exception as e:  # jaga agar thread tidak mati diam-diam
        S["errors"].append(f"galat tak terduga: {type(e).__name__}: {e}"); S["message"] = "gagal"
    finally:
        S.update(running=False, finished=time.time(), done=S["total"] if not S["errors"] else S["done"])


def start_sync(mode, symbols, data_dir, on_done=None, years=3):
    if mode not in ("backfill", "daily"):
        return "mode tidak dikenal"
    if not api_key():
        return "API key Zapi belum diisi (zapi_key.txt / ZAPI_KEY)."
    with LOCK:
        if SYNC["running"]:
            return "sinkronisasi lain sedang berjalan"
        n, _ = plan(mode, symbols, data_dir)
        if mode == "daily" and n == 0 and not os.path.isdir(data_dir):
            return "belum ada data di folder data/. Jalankan 'Unduh riwayat' dulu."
        if n > remaining():
            return f"butuh sekitar {n} request tetapi sisa anggaran lokal hanya {remaining()} (naikkan ZAPI_BUDGET bila paket Anda lebih besar)."
        SYNC.update(running=True, mode=mode, errors=[], skipped=[], written=0, started=time.time(), finished=0, ok=False, message="berjalan", total=n, done=0, current="")
    threading.Thread(target=_run, args=(mode, symbols, data_dir, years, on_done), daemon=True).start()
    return None
