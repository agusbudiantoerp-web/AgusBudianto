// IDX Terminal versi website: mengganti server lokal dengan berkas JSON statis (dibuat GitHub Actions) + impor CSV di browser.
(function () {
  const real = window.fetch.bind(window);
  const gh = location.hostname.match(/^([^.]+)\.github\.io$/), parts = location.pathname.split("/").filter(Boolean);
  const BASE = window.IDX_DATA_BASE || (gh && parts.length ? `https://raw.githubusercontent.com/${gh[1]}/${parts[0]}/idx-data/` : "idx-data/");
  const json = (o, s) => new Response(JSON.stringify(o), { status: s || 200, headers: { "Content-Type": "application/json" } });
  const getJSON = async (p) => { try { const r = await real(BASE + p, { cache: "no-cache" }); return r.ok ? await r.json() : null; } catch (e) { return null; } };

  // ---------- banner ----------
  let bar = null;
  function note(html, bad) {
    const mk = () => {
      if (!bar) { bar = document.createElement("div"); bar.style.cssText = "position:fixed;left:10px;bottom:10px;z-index:9999;max-width:min(620px,calc(100vw - 20px));padding:9px 30px 9px 12px;border-radius:8px;font:12px/1.5 'Segoe UI',system-ui,sans-serif;box-shadow:0 4px 16px #0008"; document.body.appendChild(bar); }
      bar.style.background = bad ? "#2b1216" : "#101a2b"; bar.style.border = "1px solid " + (bad ? "#8a2a36" : "#27406b"); bar.style.color = bad ? "#ffd0d6" : "#cfe0ff";
      bar.innerHTML = html + '<button aria-label="Tutup" style="position:absolute;top:3px;right:6px;background:none;border:0;color:inherit;font-size:14px;cursor:pointer">✕</button>';
      bar.querySelector("button").onclick = () => { bar.remove(); bar = null; };
    };
    document.body ? mk() : document.addEventListener("DOMContentLoaded", mk);
  }
  const ago = (s) => { const m = Math.round((Date.now() / 1000 - s) / 60); return m < 1 ? "baru saja" : m < 90 ? m + " menit lalu" : m < 2880 ? Math.round(m / 60) + " jam lalu" : Math.round(m / 1440) + " hari lalu"; };

  // ---------- snapshot ----------
  let snapP = null, snapT = 0, noted = false, BROKERS = {};
  const getSnap = () => { if (!snapP || Date.now() - snapT > 50000) { snapT = Date.now(); snapP = snapshot(); } return snapP; };
  async function snapshot() {
    const d = await getJSON("snapshot.json");
    if (!d || !d.stocks) {
      if (!noted) note("<b>Snapshot data belum tersedia.</b><br>Jalankan workflow <b>idx-data</b> di tab Actions repo GitHub Anda (Run workflow), lalu muat ulang halaman.<br>Sumber dicari di: " + BASE, true);
      noted = true;
      return json({ error: "snapshot belum tersedia" }, 503);
    }
    BROKERS = d.brokers || {};
    const old = Date.now() / 1000 - d.server_time > 3 * 86400;
    if (!noted) note("Data <b>snapshot</b> (bukan real-time): diperbarui " + ago(d.server_time) + (old ? " — <b>sudah lama</b>, cek workflow Actions." : ".") +
         "<br>Sumber: Yahoo Finance &amp; Google News, dapat tertunda. Bukan saran investasi.", old);
    noted = true;
    return json(d);
  }

  // ---------- impor CSV (port dari idx_server.py) ----------
  const ALIAS = {
    holders: { kode: ["kode", "ticker", "kode_saham", "emiten"], pemegang: ["pemegang", "nama", "holder", "name", "pemegang_saham"], jenis: ["jenis", "tipe", "type", "kategori"],
      persen: ["persen", "%", "persentase", "pct", "percent"], lembar: ["lembar", "jumlah_saham", "shares", "jumlah", "lembar_saham"], tanggal: ["tanggal", "date", "periode"] },
    broker: { kode: ["kode", "ticker", "kode_saham", "emiten"], tanggal: ["tanggal", "date"], broker: ["broker", "kode_broker", "code", "brokers"],
      buy_lot: ["buy_lot", "blot", "lot_beli", "buylot"], buy_val: ["buy_val", "bval", "nilai_beli", "buyval", "buy_value"],
      sell_lot: ["sell_lot", "slot", "lot_jual", "selllot"], sell_val: ["sell_val", "sval", "nilai_jual", "sellval", "sell_value"] } };
  const NUMF = { holders: ["persen", "lembar"], broker: ["buy_lot", "buy_val", "sell_lot", "sell_val"] };
  const FIELDS = { holders: ["kode", "tanggal", "pemegang", "jenis", "persen", "lembar"], broker: ["kode", "tanggal", "broker", "buy_lot", "buy_val", "sell_lot", "sell_val"] };
  const KEYS = { holders: ["kode", "tanggal", "pemegang"], broker: ["kode", "tanggal", "broker"] };

  function num(x) {
    x = String(x == null ? "" : x).replace(/[^\d,.\-]/g, "").trim();
    if (!x || "-.,".includes(x)) return 0;
    if (x.includes(",") && x.includes(".")) x = x.lastIndexOf(".") > x.lastIndexOf(",") ? x.replace(/,/g, "") : x.replace(/\./g, "").replace(",", ".");
    else if (/^-?\d{1,3}(,\d{3})+$/.test(x)) x = x.replace(/,/g, "");
    else if (/^-?\d{1,3}(\.\d{3})+$/.test(x)) x = x.replace(/\./g, "");
    else x = x.replace(",", ".");
    const v = Number(x); return Number.isFinite(v) && /\d/.test(x) ? v : 0;
  }
  function iso(d) {
    d = (d || "").trim(); const m = d.match(/^(\d{1,2})[/-](\d{1,2})[/-](\d{4})$/);
    return m ? `${m[3]}-${String(+m[2]).padStart(2, "0")}-${String(+m[1]).padStart(2, "0")}` : (d || new Date().toISOString().slice(0, 10));
  }
  function readCSV(text, dl) {
    const rows = []; let row = [], f = "", q = false;
    for (let i = 0; i < text.length; i++) {
      const c = text[i];
      if (q) { if (c === '"') { if (text[i + 1] === '"') { f += '"'; i++; } else q = false; } else f += c; }
      else if (c === '"') q = true;
      else if (c === dl) { row.push(f); f = ""; }
      else if (c === "\n" || c === "\r") { if (c === "\r" && text[i + 1] === "\n") i++; row.push(f); rows.push(row); row = []; f = ""; }
      else f += c;
    }
    if (f !== "" || row.length) { row.push(f); rows.push(row); }
    return rows;
  }
  function parseCSV(text, kind) {
    text = text.trim(); const first = text.split(/\r?\n/)[0] || "";
    let dl = ";", best = -1; for (const c of [";", ",", "\t"]) { const n = first.split(c).length - 1; if (n > best) { best = n; dl = c; } }
    const all = readCSV(text, dl); const hdr = (all[0] || []).map((h) => h.trim().toLowerCase().replace(/ /g, "_"));
    const idx = {}; for (const f in ALIAS[kind]) for (const a of ALIAS[kind][f]) if (hdr.includes(a)) { idx[f] = hdr.indexOf(a); break; }
    const need = kind === "holders" ? ["kode", "pemegang", "persen"] : ["kode", "broker"], miss = need.filter((n) => !(n in idx));
    if (miss.length) throw new Error("kolom wajib tidak ditemukan: " + miss.join(", ") + " (kolom terbaca: " + hdr.join(", ") + ")");
    const out = [];
    for (const r of all.slice(1)) {
      if (!r.some((v) => v !== "")) continue;
      const g = (f) => (f in idx && idx[f] < r.length ? r[idx[f]].trim() : "");
      const row = {}; for (const f of FIELDS[kind]) row[f] = g(f);
      row.kode = row.kode.toUpperCase().replace(".JK", ""); row.tanggal = iso(row.tanggal);
      for (const f of NUMF[kind]) row[f] = num(row[f]);
      if (kind === "broker") row.broker = row.broker.toUpperCase(); else row.jenis = row.jenis.toLowerCase();
      if (row.kode) out.push(row);
    }
    return out;
  }
  const LS = (k) => "idx_" + k + "_v1";
  const loadLocal = (k) => { try { return JSON.parse(localStorage.getItem(LS(k)) || "[]"); } catch (e) { return []; } };
  const SEED = {};
  async function seed(kind) {
    if (SEED[kind]) return SEED[kind];
    SEED[kind] = (async () => { try { const r = await real(kind + ".csv", { cache: "no-cache" }); return r.ok ? parseCSV(await r.text(), kind) : []; } catch (e) { return []; } })();
    return SEED[kind];
  }
  async function rowsFor(kind, k) {
    const m = new Map();
    for (const r of [...(await seed(kind)), ...loadLocal(kind)]) m.set(KEYS[kind].map((f) => String(r[f])).join("|"), r);
    return [...m.values()].filter((r) => r.kode === k);
  }
  function upload(kind, text) {
    try {
      if (!FIELDS[kind]) throw new Error("jenis impor tidak dikenal");
      if (text.length > 5e6) throw new Error("file terlalu besar (maks 5 MB)");
      const rows = parseCSV(text, kind); if (!rows.length) throw new Error("tidak ada baris data");
      const m = new Map(loadLocal(kind).map((r) => [KEYS[kind].map((f) => String(r[f])).join("|"), r]));
      for (const r of rows) m.set(KEYS[kind].map((f) => String(r[f])).join("|"), r);
      try { localStorage.setItem(LS(kind), JSON.stringify([...m.values()])); } catch (e) { throw new Error("penyimpanan browser penuh atau dinonaktifkan"); }
      return { ok: true, added: rows.length, codes: [...new Set(rows.map((r) => r.kode))].sort() };
    } catch (e) { return { ok: false, error: String(e.message || e) }; }
  }

  // ---------- pengalihan fetch ----------
  window.fetch = async function (u, o) {
    o = o || {};
    const url = typeof u === "string" ? u : (u && u.url) || "";
    const m = url.match(/^(?:https?:\/\/[^/]+)?(\/api\/[^?]*)(?:\?(.*))?$/);
    if (!m) return real(u, o);
    const path = m[1], q = new URLSearchParams(m[2] || ""), k = (q.get("s") || q.get("k") || "").toUpperCase();
    if (path === "/api/snapshot") return getSnap().then((r) => r.clone());
    if (path === "/api/detail") {
      const d = await getJSON("detail/" + k + ".json");
      const msg = "detail belum tersedia di snapshot (dibuat berkala oleh workflow, mode full)";
      return json(d || { daily: { error: msg }, intra: { error: msg }, summary: { error: msg }, news: [] });
    }
    if (path === "/api/news") return json((await getJSON(k ? "news/" + k + ".json" : "news.json")) || { items: [], status: {} });
    if (path === "/api/holders") return json({ rows: await rowsFor("holders", k) });
    if (path === "/api/broker") { await getSnap(); return json({ rows: await rowsFor("broker", k), brokers: BROKERS }); }
    if (path === "/api/upload") return json(upload(q.get("type") || "", String(o.body || "")));
    return json({ error: "tidak ditemukan" }, 404);
  };
})();
