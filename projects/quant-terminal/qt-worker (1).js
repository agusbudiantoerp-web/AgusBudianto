// Menjalankan backend Python (server.py) di browser memakai Pyodide. Semua gratis, tanpa server.
importScripts("https://cdn.jsdelivr.net/pyodide/v0.26.4/full/pyodide.js");
let py = null;
const say = (m) => postMessage({ type: "status", msg: m });
const txt = async (u) => { const r = await fetch(new URL(u, self.location.href)); if (!r.ok) throw new Error(u + " -> HTTP " + r.status); return r.text(); };

const ready = (async () => {
  say("Memuat mesin Python (pertama kali ±10–20 detik)…");
  py = await loadPyodide();
  py.FS.mkdirTree("/py"); py.FS.mkdirTree("/data");
  for (const f of ["server.py", "orderflow.py", "zapi.py", "universe.py", "qt_bridge.py"]) py.FS.writeFile("/py/" + f, await txt("py/" + f));
  py.runPython("import sys; sys.path.insert(0,'/py')");
  const names = py.runPython("import universe; ','.join(['IHSG']+universe.LQ45)").split(",").map((n) => n + ".JK.csv");
  // Folder data bisa berada di dalam folder terminal ("data/") ATAU di root repo ("../../data/"). Keduanya dicoba.
  const BASES = ["data/", "../../data/"];
  for (const b of BASES) { try { const m = JSON.parse(await txt(b + "manifest.json")); for (const n of m) if (!names.includes(n)) names.push(n); break; } catch (e) {} }
  say("Memuat data harga…");
  let ok = 0;
  await Promise.all(names.map(async (n) => {
    for (const b of BASES) {
      try { const r = await fetch(new URL(b + n, self.location.href)); if (r.ok) { py.FS.writeFile("/data/" + n, await r.text()); ok++; return; } } catch (e) {}
    }
  }));
  say("Menyiapkan terminal…");
  py.runPython("import qt_bridge");
  const info = JSON.parse(py.runPython("qt_bridge.info()"));
  info.files = ok;
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
