#!/usr/bin/env python3
"""Pembuat snapshot untuk IDX Terminal versi website (dijalankan GitHub Actions atau manual).
Memakai fungsi pengambil data yang sama dengan idx_server.py (Yahoo Finance + Google News), lalu menulis berkas JSON statis:
  snapshot.json            harga seluruh emiten + indeks (+ daftar broker)
  news.json                berita pasar gabungan
  detail/<KODE>.json       grafik 1 tahun & intraday, fundamental, berita per emiten      (mode full)
  news/<KODE>.json         berita per emiten                                              (mode full)
Pemakaian:  python idx_snapshot.py --out hasil --mode snapshot|full
Jika data gagal diambil (mis. diblokir sumber), berkas lama TIDAK ditimpa dan skrip keluar dengan kode 1."""
import argparse, datetime, json, os, sys, time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import idx_server as S


def retry(fn, *a, tries=3, wait=1.5):
    r = None
    for i in range(tries):
        r = fn(*a)
        if not (isinstance(r, dict) and "error" in r and len(r) == 1):
            return r
        time.sleep(wait * (i + 1))
    return r


def write_json(path, obj):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)


def build_snapshot():
    syms = [S.INDEX] + [k + ".JK" for k in S.EMITEN]
    with ThreadPoolExecutor(8) as ex:
        res = list(ex.map(lambda s: retry(S.fetch, s), syms))
    index = res[0] if "error" not in res[0] else None
    stocks = {}
    for k, d in zip(S.EMITEN, res[1:]):
        if "error" not in d:
            stocks[k] = {**d, "name": S.EMITEN[k][0], "sector": S.EMITEN[k][1], "group": S.EMITEN[k][2]}
    return index, stocks, [r.get("error") for r in res if "error" in r][:3]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="hasil"); ap.add_argument("--mode", choices=["snapshot", "full"], default="snapshot")
    ap.add_argument("--max-minutes", type=float, default=20)
    a = ap.parse_args()
    t0 = time.time()
    index, stocks, errs = build_snapshot()
    need = max(20, int(.3 * len(S.EMITEN)))
    if not index or len(stocks) < need:
        print(f"GAGAL: hanya {len(stocks)} emiten terambil (minimal {need}), indeks={'ok' if index else 'gagal'}. Contoh galat: {errs}", file=sys.stderr)
        return 1
    now = int(time.time())
    write_json(os.path.join(a.out, "snapshot.json"), {
        "index": index, "stocks": stocks, "indices": S.INDICES, "brokers": S.BROKERS,
        "server_time": now, "generated": datetime.datetime.utcfromtimestamp(now).isoformat() + "Z"})
    print(f"snapshot: {len(stocks)}/{len(S.EMITEN)} emiten")
    nw = S.news_all()
    if nw.get("items"):
        write_json(os.path.join(a.out, "news.json"), nw); print(f"berita pasar: {len(nw['items'])} item")
    nd = nn = 0
    if a.mode == "full":
        def one(k):
            if time.time() - t0 > a.max_minutes * 60:
                return 0, 0
            d = S.detail(k)
            okd = any(isinstance(d.get(p), dict) and "error" not in d[p] for p in ("daily", "intra"))
            if okd:
                write_json(os.path.join(a.out, "detail", k + ".json"), d)
            n = S.news_emiten(k)
            okn = bool(n.get("items"))
            if okn:
                write_json(os.path.join(a.out, "news", k + ".json"), n)
            return int(okd), int(okn)
        with ThreadPoolExecutor(3) as ex:
            for x, y in ex.map(one, list(S.EMITEN)):
                nd += x; nn += y
        print(f"detail: {nd}, berita emiten: {nn}")
    write_json(os.path.join(a.out, "meta.json"), {"mode": a.mode, "generated": now, "stocks": len(stocks), "detail": nd, "news": nn})
    return 0


if __name__ == "__main__":
    sys.exit(main())
