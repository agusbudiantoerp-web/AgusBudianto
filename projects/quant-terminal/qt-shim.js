// Mengalihkan semua panggilan fetch('/api/...') milik terminal ke backend Python di Web Worker (Pyodide).
(function () {
  if (!location.pathname.endsWith("/") && !/\.html?$/.test(location.pathname)) { location.replace(location.pathname + "/" + location.search + location.hash); return; }
  const realFetch = window.fetch.bind(window);
  const ov = document.createElement("div");
  ov.style.cssText = "position:fixed;inset:0;z-index:99999;background:#070d1a;color:#d6e0f5;display:flex;align-items:center;justify-content:center;font:14px 'Segoe UI',system-ui,sans-serif;text-align:center;padding:24px";
  ov.innerHTML = '<div><div style="font-size:18px;margin-bottom:8px">Quant Terminal</div><div id="qt-ov-msg" style="color:#7384a8;white-space:pre-wrap;max-width:880px;text-align:left;font-size:13px">Memuat…</div></div>';
  document.addEventListener("DOMContentLoaded", () => document.body.appendChild(ov));
  const setMsg = (m, err) => { const el = document.getElementById("qt-ov-msg"); if (el) { el.textContent = m; if (err) el.style.color = "#ff4d5e"; } };

  const worker = new Worker("qt-worker.js");
  const pending = new Map(); let seq = 0, up = false;
  worker.onmessage = (e) => {
    const d = e.data;
    if (d.type === "status") setMsg(d.msg);
    else if (d.type === "ready") {
      up = true; ov.remove();
      if (d.info.src !== "CSV") console.warn("Folder data/ kosong: terminal memakai data SIMULASI.");
    } else if (d.type === "fatal") setMsg("Gagal memuat mesin Python:\n" + d.msg + "\n\nJalankan halaman diagnosa.html di folder yang sama untuk melihat tahap yang gagal.", true);
    else if (d.type === "res") { const p = pending.get(d.id); if (p) { pending.delete(d.id); p(d); } }
  };
  worker.onerror = (e) => setMsg("Galat worker: " + (e.message || "tidak diketahui"), true);

  const json = (o, s) => new Response(JSON.stringify(o), { status: s || 200, headers: { "Content-Type": "application/json" } });
  const EXPS = "qt_exps_v1";

  async function exps(method, o) {
    if (method === "POST") {
      try { const a = JSON.parse(o.body); localStorage.setItem(EXPS, JSON.stringify(a)); return json({ ok: true, n: a.length }); }
      catch (e) { return json({ ok: false, n: 0 }, 200); }
    }
    try { const s = localStorage.getItem(EXPS); if (s) return json(JSON.parse(s)); } catch (e) {}
    try { const r = await realFetch("experiments.json"); if (r.ok) return json(await r.json()); } catch (e) {}
    return json([]);
  }

  window.fetch = function (u, o) {
    o = o || {};
    const url = typeof u === "string" ? u : (u && u.url) || "";
    const m = url.match(/^(?:https?:\/\/[^/]+)?(\/api\/[^?]*)(?:\?(.*))?$/);
    if (!m) return realFetch(u, o);
    const path = m[1], query = m[2] || "", method = (o.method || "GET").toUpperCase();
    if (path === "/api/exps") return exps(method, o);
    if (path === "/api/orderflow/stream")
      return Promise.resolve(new Response('data: {"error":"Mode live tidak tersedia pada versi website. Gunakan tombol Segarkan.","final":true}\n\n', { headers: { "Content-Type": "text/event-stream" } }));
    return new Promise((resolve, reject) => {
      const id = ++seq;
      pending.set(id, (d) => resolve(new Response(d.body, { status: d.status, headers: { "Content-Type": "application/json" } })));
      if (o.signal) o.signal.addEventListener("abort", () => { pending.delete(id); reject(new DOMException("Aborted", "AbortError")); });
      worker.postMessage({ id, path, query });
    });
  };
})();
