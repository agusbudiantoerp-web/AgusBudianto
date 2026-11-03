// Menjalankan backend Python (server.py) di browser memakai Pyodide. Semua gratis, tanpa server.
importScripts("https://cdn.jsdelivr.net/pyodide/v0.26.4/full/pyodide.js", "qt-data.js");
let py = null;
const LOG = [];
const say = (m) => postMessage({ type: "status", msg: m });
const pyfile = async (f) => {
  for (const p of ["py/" + f, f]) {
    try { const r = await fetch(new URL(p, self.location.href), { cache: "no-cache" }); if (r.ok) return await r.text(); } catch (e) {}
  }
  throw new Error("Berkas Python tidak ditemukan: " + f + " (dicari di py/" + f + " dan " + f + ")");
};

const ready = (async () => {
  say("Memuat mesin Python (pertama kali ±10–20 detik)…");
  py = await loadPyodide({ stdout: (s) => LOG.push(s), stderr: (s) => LOG.push(s) });
  py.FS.mkdirTree("/py"); py.FS.mkdirTree("/data");
  for (const f of ["server.py", "orderflow.py", "zapi.py", "universe.py", "qt_bridge.py"]) py.FS.writeFile("/py/" + f, await pyfile(f));
  py.runPython("import sys; sys.path.insert(0,'/py')");
  const lq = py.runPython("import universe; ','.join(['IHSG']+universe.LQ45)").split(",");
  const report = await QTData.loadAll({
    fetch: (u, o) => fetch(u, o), href: self.location.href, known: lq, expected: lq.map((n) => n + ".JK.csv"),
    write: (n, t) => py.FS.writeFile("/data/" + n, t), say,
  });
  say("Menyiapkan terminal…");
  py.runPython("import qt_bridge");
  const info = JSON.parse(py.runPython("qt_bridge.info()"));
  info.report = report; info.log = LOG.slice(-10);
  postMessage({ type: "ready", info });
})().catch((e) => { postMessage({ type: "fatal", msg: String(e && e.message || e).slice(0, 1500) }); throw e; });

onmessage = async (e) => {
  const { id, path, query } = e.data;
  try {
    await ready;
    const res = py.runPython(`qt_bridge.handle(${JSON.stringify(path)}, ${JSON.stringify(query)})`).toJs();
    postMessage({ type: "res", id, status: res[0], body: res[1] });
  } catch (err) {
    postMessage({ type: "res", id, status: 500, body: JSON.stringify({ error: String(err && err.message || err) }) });
  }
};
