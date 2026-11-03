"""Jembatan: menjalankan fungsi API server.py langsung di browser (Pyodide), tanpa server HTTP."""
import os, sys, json, types
os.environ["QT_DATA_DIR"] = os.environ.get("QT_DATA_DIR", "/data")
for _m in ("webbrowser",):
    try:
        __import__(_m)
    except Exception:
        sys.modules[_m] = types.ModuleType(_m)
try:
    import http.server  # noqa
except Exception:  # pragma: no cover
    hs = types.ModuleType("http.server")
    hs.BaseHTTPRequestHandler = object; hs.ThreadingHTTPServer = object
    sys.modules["http.server"] = hs
from urllib.parse import parse_qs
import server as S

API = {"/api/data": S.payload, "/api/universe": S.universe, "/api/walkforward": S.walkforward, "/api/portfolio": S.portfolio,
       "/api/pwf": S.pwf, "/api/montecarlo": S.montecarlo, "/api/stress": S.stress, "/api/mwf": S.mwf, "/api/compare": S.compare,
       "/api/orderflow": S.orderflow_api}
OFF = "Fitur ini dinonaktifkan pada versi website (tidak ada server)."


def handle(path, query=""):
    """Mengembalikan (status, json_str)."""
    try:
        if path == "/api/zapi/status":
            return 200, json.dumps({"key": False, "sync": {"running": False, "errors": [], "skipped": 0}, "src": S.SRC, "used": 0, "budget": 0})
        if path in ("/api/zapi/test", "/api/zapi/sync"):
            return 200, json.dumps({"error": OFF})
        if path == "/api/orderflow/stream":
            return 200, json.dumps({"error": "Mode live (streaming) tidak tersedia pada versi website. Gunakan tombol Segarkan.", "final": True})
        if path not in API:
            return 404, json.dumps({"error": "tidak ditemukan"})
        qd = parse_qs(query)
        if path == "/api/orderflow" and qd.get("src", [""])[0] == "zapi":
            return 200, json.dumps({"error": OFF})
        try:
            tf = int(float(qd.get("tf", ["0"])[0] or 0))
        except ValueError:
            tf = 0
        S.CTX.tf = 0 if tf < 10 else min(tf, 500)
        return 200, json.dumps(API[path](qd))
    except Exception as e:
        return 500, json.dumps({"error": f"{type(e).__name__}: {e}"})


def info():
    idx = S.GROUPS.get("IDX", []); glob = S.GROUPS.get("Global", [])
    return json.dumps({"src": S.SRC, "n": len(S.DATES), "dropped": list(S.DROPPED), "idx": len(idx), "glob": len(glob),
                       "d0": str(S.DATES[0]), "d1": str(S.DATES[-1]), "sample": (idx + glob)[:6]})
