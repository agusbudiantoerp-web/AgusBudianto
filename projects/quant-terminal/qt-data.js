// Pemuat data CSV yang tangguh: mencari di data/ (dalam folder terminal) dan ../../data/ (root repo),
// menerima nama berkas bervariasi (bbca.csv, BBCA.csv, BBCA.JK.csv), dan menemukan berkas lewat GitHub API bila perlu.
(function (root) {
  function normName(fn, known) {
    let b = String(fn).replace(/\.csv$/i, "").toUpperCase();
    if (!/\.JK$/.test(b) && known.has(b)) b += ".JK";
    return b + ".csv";
  }
  async function loadAll(o) {
    const f = o.fetch, href = o.href, say = o.say || function () {};
    const known = new Set(o.known);
    const u = new URL(href);
    const bases = { term: new URL("data/", href).href, root: new URL("../../data/", href).href };
    const names = new Set(o.expected);
    const rep = { bases, byBase: { term: 0, root: 0 }, api: {}, count: 0, written: [], missingCount: 0, missingSample: [] };
    // 1. manifest.json (opsional)
    for (const k of ["term", "root"]) {
      try { const r = await f(bases[k] + "manifest.json", { cache: "no-cache" }); if (r.ok) (await r.json()).forEach((n) => names.add(n)); } catch (e) {}
    }
    // 2. daftar berkas lewat GitHub API (hanya untuk github.io)
    const parts = u.pathname.split("/").filter(Boolean);
    if (u.hostname.endsWith(".github.io") && parts.length > 1) {
      const owner = u.hostname.split(".")[0], repo = parts[0], termDir = parts.slice(1, -1).join("/");
      const paths = { root: "data" }; if (termDir) paths.term = termDir + "/data";
      for (const k in paths) {
        try {
          const r = await f(`https://api.github.com/repos/${owner}/${repo}/contents/${paths[k]}`);
          if (!r.ok) { rep.api[k] = { n: 0, err: "HTTP " + r.status }; continue; }
          const a = await r.json();
          const csv = (Array.isArray(a) ? a : []).filter((x) => x.type === "file" && /\.csv$/i.test(x.name)).map((x) => x.name);
          csv.forEach((n) => names.add(n)); rep.api[k] = { n: csv.length, err: null };
        } catch (e) { rep.api[k] = { n: 0, err: String((e && e.message) || e) }; }
      }
    }
    // 3. unduh
    say("Memuat data harga…");
    const written = new Set();
    await Promise.all([...names].map(async (n) => {
      for (const k of ["term", "root"]) {
        try {
          const r = await f(bases[k] + n, { cache: "no-cache" });
          if (!r.ok) continue;
          const out = normName(n, known);
          const t = await r.text();
          if (!written.has(out)) { written.add(out); o.write(out, t); rep.byBase[k]++; }
          return;
        } catch (e) {}
      }
    }));
    rep.written = [...written].sort(); rep.count = written.size;
    const miss = o.expected.filter((n) => !written.has(normName(n, known)));
    rep.missingCount = miss.length; rep.missingSample = miss.slice(0, 8);
    return rep;
  }
  root.QTData = { normName, loadAll };
  if (typeof module !== "undefined") module.exports = root.QTData;
})(typeof self !== "undefined" ? self : globalThis);
