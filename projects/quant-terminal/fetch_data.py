#!/usr/bin/env python3
"""Unduh data harian riil (butuh internet + `pip install yfinance`) ke folder data/.
Pemakaian:  python fetch_data.py                -> IHSG + seluruh daftar LQ45 (universe.py)
            python fetch_data.py GOTO PGAS ...  -> tambah kode saham IDX lain (tanpa .JK)
Lalu restart server.py: otomatis memakai CSV (grup IDX, Rupiah). Dikenali dari akhiran .JK.csv"""
import os, sys
from universe import LQ45
try:
    import yfinance as yf
except ImportError:
    sys.exit("Jalankan dulu: pip install yfinance")
T = {"IHSG": "^JKSE"}
for k in LQ45 + sys.argv[1:]:
    T[k.upper()] = k.upper() + ".JK"
os.makedirs("data", exist_ok=True)
for name, tk in T.items():
    df = yf.download(tk, period="4y", auto_adjust=True, progress=False)
    if df.empty:
        print("lewati", tk); continue
    close, vol = df["Close"].squeeze().dropna(), df["Volume"].squeeze()
    with open(f"data/{name}.JK.csv", "w") as f:
        f.write("Date,Close,Volume\n")
        for d, v in close.items():
            f.write(f"{d.date()},{float(v):.4f},{float(vol.get(d, 0))}\n")
    print("ok", name, len(close), "bar")
