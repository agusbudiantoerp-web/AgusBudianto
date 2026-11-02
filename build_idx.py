#!/usr/bin/env python3
"""Membuat snapshot statis IDX Terminal (dijalankan GitHub Actions).
Memakai fungsi pengambil data dari idx_core.py, lalu menulis JSON ke idx/data/ untuk dibaca idx/index.html."""
import json, os, sys, time
from concurrent.futures import ThreadPoolExecutor
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import idx_core as C
OUT = os.path.join(ROOT, "idx", "data")
IMPORT = os.path.join(ROOT, "idx_import")

def w(rel, obj):
    p = os.path.join(OUT, rel); os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p + ".tmp", "w", encoding="utf-8") as f: json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(p + ".tmp", p)

def main():
    t0 = time.time(); kodes = list(C.EMITEN)
    with ThreadPoolExecutor(10) as ex: res = list(ex.map(C.fetch, [C.INDEX] + [k + ".JK" for k in kodes]))
    idx, stocks = res[0], {}
    for k, d in zip(kodes, res[1:]):
        if "error" not in d: stocks[k] = {**d, "name": C.EMITEN[k][0], "sector": C.EMITEN[k][1], "group": C.EMITEN[k][2]}
    print(f"harga: {len(stocks)}/{len(kodes)} emiten, indeks {'ok' if 'error' not in idx else idx['error']}")
    if "error" in idx or len(stocks) < max(10, len(kodes) // 4):
        sys.exit("Data harga gagal diambil (kemungkinan diblokir atau jaringan bermasalah). Snapshot tidak ditulis.")
    w("snapshot.json", {"index": idx, "stocks": stocks, "indices": C.INDICES, "server_time": int(time.time())})
    # detail per emiten (grafik, ringkasan, berita Yahoo)
    def det(k):
        d = C.detail(k)
        if all(isinstance(v, dict) and "error" in v for v in d.values()): return k, False
        w(f"d/{k}.json", d); return k, True
    with ThreadPoolExecutor(4) as ex: ok = [k for k, g in ex.map(det, list(stocks)) if g]
    print(f"detail: {len(ok)}/{len(stocks)}")
    # berita
    try: w("news.json", C.news_all())
    except Exception as e: print("berita umum gagal:", e); w("news.json", {"items": [], "status": {}})
    def nw(k):
        try: w(f"n/{k}.json", C.news_emiten(k))
        except Exception: w(f"n/{k}.json", {"items": []})
    with ThreadPoolExecutor(4) as ex: list(ex.map(nw, kodes))
    # data impor (opsional): idx_import/*.csv
    for kind, fn in (("holders", "pemegang_saham.csv"), ("broker", "broker_summary.csv")):
        rows = []
        fp = os.path.join(IMPORT, fn)
        if os.path.isfile(fp):
            try: rows = C.parse_csv(open(fp, encoding="utf-8-sig").read(), kind)
            except Exception as e: print(f"{fn} dilewati: {e}")
        cur = {tuple(r[x] for x in C.KEYS[kind]): r for r in rows}.values()
        for k in kodes:
            mine = [r for r in cur if r["kode"] == k]
            w(f"{'h' if kind == 'holders' else 'b'}/{k}.json", {"rows": mine} if kind == "holders" else {"rows": mine, "brokers": C.BROKERS})
    print(f"selesai dalam {time.time() - t0:.0f} dtk")

if __name__ == "__main__": main()
