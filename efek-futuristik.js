/*!
 * efek-futuristik.js  v2
 * Latar: galaksi (nebula, planet, bintang) + peta serangan siber + hujan biner.
 * Semua data serangan hanya SIMULASI visual (IP memakai blok contoh RFC 5737).
 * Cara pakai: tambahkan SATU baris sebelum </body> di index.html:
 *   <script src="efek-futuristik.js" defer></script>
 * Hapus baris itu untuk menghilangkan efek.
 */
(function () {
  'use strict';
  if (window.__fxLoaded) return;
  window.__fxLoaded = true;

  var TAU = Math.PI * 2;
  var reduce = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
  var MODES = ['gabungan', 'galaksi', 'serangan', 'biner', 'mati'];
  var LABEL = { gabungan: 'Galaksi + Serangan + Biner', galaksi: 'Galaksi & Planet', serangan: 'Serangan Siber', biner: 'Hujan Biner', mati: 'Efek mati' };
  var FLAGS = { // g=bintang+nebula, p=planet, c=serangan, r=biner
    gabungan: { g: 1, p: 1, c: 1, r: 1 }, galaksi: { g: 1, p: 1 }, serangan: { g: 1, c: 1 },
    biner: { r: 1 }, mati: {}
  };
  var mode = 'gabungan';
  try { var sv = localStorage.getItem('fx-mode'); if (MODES.indexOf(sv) > -1) mode = sv; } catch (e) {}

  function lum(rgb) {
    var a = (rgb.match(/[\d.]+/g) || [0, 0, 0]).map(Number);
    return (0.2126 * a[0] + 0.7152 * a[1] + 0.0722 * a[2]) / 255;
  }
  var darkTheme = lum(getComputedStyle(document.body).color) > 0.5;
  var TOP = 2147483000;

  /* ---------- CSS ---------- */
  var css = [
    '#fx-galaxy,#fx-cyber,#fx-rain{position:fixed;inset:0;width:100%;height:100%;pointer-events:none}',
    '#fx-galaxy{z-index:' + (darkTheme ? '-3' : TOP - 3) + '}',
    '#fx-cyber{z-index:' + (darkTheme ? '-2' : TOP - 2) + ';opacity:' + (darkTheme ? '1' : '.22') + '}',
    '#fx-rain{z-index:' + (darkTheme ? '-1' : TOP - 1) + ';opacity:' + (darkTheme ? '.4' : '.12') + '}',
    '#fx-galaxy{opacity:' + (darkTheme ? '1' : '0') + '}',
    '#fx-glow{position:fixed;left:0;top:0;width:520px;height:520px;margin:-260px 0 0 -260px;border-radius:50%;pointer-events:none;z-index:-1;' +
      'background:radial-gradient(circle,rgba(0,255,200,.10),rgba(120,80,255,.06) 40%,transparent 70%)}',
    '#fx-bar{position:fixed;left:0;top:0;height:3px;width:0;z-index:' + (TOP + 1) + ';pointer-events:none;' +
      'background:linear-gradient(90deg,#00ffc8,#7a5cff,#ff3df0);box-shadow:0 0 12px #00ffc8}',
    '#fx-btn{position:fixed;left:14px;bottom:14px;z-index:' + (TOP + 2) + ';font:600 12px/1 ui-monospace,Consolas,monospace;' +
      'color:#00ffc8;background:rgba(3,8,18,.85);border:1px solid rgba(0,255,200,.5);border-radius:999px;padding:9px 13px;cursor:pointer;' +
      'box-shadow:0 0 14px rgba(0,255,200,.25);letter-spacing:.04em}',
    '#fx-btn:hover{box-shadow:0 0 22px rgba(0,255,200,.55)}',
    '#fx-btn:focus-visible{outline:3px solid #ffd84d;outline-offset:2px}',
    '#fx-log{position:fixed;right:14px;bottom:14px;width:min(380px,44vw);z-index:' + (TOP + 1) + ';pointer-events:none;' +
      'font:11px/1.45 ui-monospace,Consolas,monospace;color:#9dffe3;background:rgba(2,7,16,.72);border:1px solid rgba(0,255,200,.35);' +
      'border-radius:6px;padding:8px 10px;box-shadow:0 0 18px rgba(0,255,200,.18);backdrop-filter:blur(3px)}',
    '#fx-log b{display:flex;justify-content:space-between;color:#00ffc8;letter-spacing:.08em;margin-bottom:5px;font-size:10.5px}',
    '#fx-log div{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}',
    '#fx-log .a{color:#ff6b86}#fx-log .k{color:#4dffa6}#fx-log .m{color:#6fd6ff}#fx-log .w{color:#ffd84d}',
    '@media(max-width:760px){#fx-log{display:none!important}}',
    '.fx-reveal{opacity:0;transform:translateY(26px);transition:opacity .8s ease,transform .8s ease}',
    '.fx-in{opacity:1;transform:none}',
    '@media print{#fx-galaxy,#fx-cyber,#fx-rain,#fx-glow,#fx-bar,#fx-btn,#fx-log{display:none!important}.fx-reveal{opacity:1!important;transform:none!important}}'
  ];
  if (darkTheme) {
    css.push(
      'html{background:#02040c!important}',
      'body{background:transparent!important}',
      'body>header,body>main,body>section,body>footer,main,section,.hero,#top{background-color:transparent!important;background-image:none!important}',
      'h1,h2{text-shadow:0 0 18px rgba(0,255,200,.32),0 0 42px rgba(122,92,255,.25)}',
      'a:hover,button:hover{filter:drop-shadow(0 0 6px rgba(0,255,200,.55))}'
    );
  }
  var st = document.createElement('style'); st.textContent = css.join('\n'); document.head.appendChild(st);

  /* ---------- elemen ---------- */
  function mk(tag, id) { var e = document.createElement(tag); e.id = id; return e; }
  var cg = mk('canvas', 'fx-galaxy'), cc = mk('canvas', 'fx-cyber'), cr = mk('canvas', 'fx-rain'),
      glow = mk('div', 'fx-glow'), bar = mk('div', 'fx-bar'), btn = mk('button', 'fx-btn'), log = mk('div', 'fx-log');
  [cg, cc, cr].forEach(function (c) { c.setAttribute('aria-hidden', 'true'); });
  log.setAttribute('aria-hidden', 'true'); btn.type = 'button';
  document.body.insertBefore(cr, document.body.firstChild);
  document.body.insertBefore(cc, document.body.firstChild);
  document.body.insertBefore(cg, document.body.firstChild);
  [glow, bar, log, btn].forEach(function (e) { document.body.appendChild(e); });
  var gx = cg.getContext('2d'), cx2 = cc.getContext('2d'), rx = cr.getContext('2d');

  var W = 0, H = 0, DPR = Math.min(window.devicePixelRatio || 1, 1.5);
  var stars = [], drops = [], nodes = [], links = [], attacks = [], ripples = [], shoot = null;
  var mx = 0, my = 0, tx = 0, ty = 0, FS = 16;

  var CITIES = ['JKT', 'SIN', 'TYO', 'SEL', 'PEK', 'BOM', 'DXB', 'MOW', 'FRA', 'LON', 'NYC', 'SFO', 'SAO', 'SYD', 'JNB'];

  function resize() {
    W = innerWidth; H = innerHeight;
    [cg, cc, cr].forEach(function (c) { c.width = W * DPR; c.height = H * DPR; });
    gx.setTransform(DPR, 0, 0, DPR, 0, 0); cx2.setTransform(DPR, 0, 0, DPR, 0, 0); rx.setTransform(DPR, 0, 0, DPR, 0, 0);
    var n = Math.round(W * H / 4800); stars = [];
    for (var i = 0; i < n; i++) {
      var z = Math.random() < .6 ? 0 : Math.random() < .7 ? 1 : 2;
      stars.push({ x: Math.random() * W, y: Math.random() * H, z: z, r: .4 + z * .45 + Math.random() * .5,
        p: Math.random() * TAU, s: .6 + Math.random() * 1.6, h: [200, 170, 280, 330][Math.floor(Math.random() * 4)] });
    }
    var cols = Math.ceil(W / FS); drops = [];
    for (var c = 0; c < cols; c++) drops.push(Math.random() * -60);
    // simpul jaringan: grid berjitter
    nodes = []; var gc = W < 760 ? 3 : 5, gr = W < 760 ? 4 : 3, k = 0;
    for (var r = 0; r < gr; r++) for (var q = 0; q < gc; q++) {
      nodes.push({ x: (q + .5 + (Math.random() - .5) * .6) / gc * W, y: (r + .5 + (Math.random() - .5) * .6) / gr * H,
        name: CITIES[k % CITIES.length], p: Math.random() * TAU, home: k === 0 }); k++;
    }
    links = [];
    nodes.forEach(function (a, i) {
      var d = nodes.map(function (b, j) { return { j: j, d: Math.hypot(a.x - b.x, a.y - b.y) }; })
        .filter(function (o) { return o.j !== i; }).sort(function (u, v) { return u.d - v.d; }).slice(0, 2);
      d.forEach(function (o) { if (o.j > i || links.every(function (l) { return !(l[0] === o.j && l[1] === i); })) links.push([i, o.j]); });
    });
    attacks = []; ripples = [];
  }

  /* ---------- planet ---------- */
  function sphere(c, cx, cy, r, h, t, bands) {
    var g = c.createRadialGradient(cx, cy, r * .9, cx, cy, r * 1.55);
    g.addColorStop(0, 'hsla(' + h + ',90%,60%,.38)'); g.addColorStop(1, 'hsla(' + h + ',90%,60%,0)');
    c.fillStyle = g; c.beginPath(); c.arc(cx, cy, r * 1.55, 0, TAU); c.fill();
    c.save(); c.beginPath(); c.arc(cx, cy, r, 0, TAU); c.clip();
    var b = c.createRadialGradient(cx - r * .4, cy - r * .4, r * .1, cx, cy, r);
    b.addColorStop(0, 'hsl(' + h + ',75%,70%)'); b.addColorStop(.55, 'hsl(' + h + ',65%,38%)'); b.addColorStop(1, 'hsl(' + (h + 25) + ',55%,12%)');
    c.fillStyle = b; c.fillRect(cx - r, cy - r, 2 * r, 2 * r);
    if (bands) for (var i = 0; i < 9; i++) {
      var yy = cy - r + (i + .5) * (2 * r / 9) + Math.sin(t * .0003 + i) * r * .02;
      c.fillStyle = 'hsla(' + (h + (i % 2 ? 18 : -18)) + ',60%,' + (i % 2 ? 72 : 28) + '%,.17)'; c.fillRect(cx - r, yy, 2 * r, r * .1);
    }
    var s = c.createRadialGradient(cx - r * .3, cy - r * .3, r * .55, cx - r * .3, cy - r * .3, r * 1.5);
    s.addColorStop(0, 'rgba(0,0,10,0)'); s.addColorStop(1, 'rgba(0,0,10,.85)');
    c.fillStyle = s; c.fillRect(cx - r, cy - r, 2 * r, 2 * r);
    c.restore();
  }
  function ringPart(c, cx, cy, r, h, front) {
    var rot = -.38;
    [[2.0, .55, .34, 2.2], [2.35, .62, .22, 1.4], [1.72, .47, .28, 1.2]].forEach(function (o) {
      c.strokeStyle = 'hsla(' + (h + 20) + ',60%,75%,' + o[2] + ')'; c.lineWidth = o[3] * (r / 40);
      c.beginPath(); c.ellipse(cx, cy, r * o[0], r * o[1], rot, front ? 0 : Math.PI, front ? Math.PI : TAU); c.stroke();
    });
  }
  function drawPlanets(t) {
    var u = Math.min(W, H);
    // planet bercincin (besar, ungu)
    var a = { x: W * .83 + mx * 10, y: H * .24 + my * 8 + Math.sin(t * .00008) * 6, r: u * .1 };
    ringPart(gx, a.x, a.y, a.r, 268, false); sphere(gx, a.x, a.y, a.r, 268, t, true); ringPart(gx, a.x, a.y, a.r, 268, true);
    // planet biru (mirip bumi)
    var b = { x: W * .11 + mx * 14, y: H * .74 + my * 10 + Math.sin(t * .00007 + 1) * 6, r: u * .07 };
    sphere(gx, b.x, b.y, b.r, 205, t, false);
    var ang = t * .0004, mxm = b.x + Math.cos(ang) * b.r * 2.4, mym = b.y + Math.sin(ang) * b.r * .8, mr = b.r * .2;
    if (Math.sin(ang) >= 0) sphere(gx, mxm, mym, mr, 40, t, false); // bulan di depan
    else { /* di belakang planet: tak digambar */ }
    // planet merah kecil
    sphere(gx, W * .56 + mx * 6, H * .1 + my * 5, u * .035, 8, t, true);
    // planet cyan kecil
    sphere(gx, W * .34 + mx * 18, H * .9 + my * 12, u * .028, 170, t, false);
  }

  /* ---------- galaksi ---------- */
  var blobs = [
    { x: .2, y: .25, r: .55, h: 265, a: .24, sp: .00006 }, { x: .78, y: .35, r: .5, h: 190, a: .17, sp: .00008 },
    { x: .5, y: .85, r: .6, h: 320, a: .16, sp: .00005 }, { x: .9, y: .8, r: .4, h: 215, a: .13, sp: .00007 }
  ];
  function drawGalaxy(t, withPlanets) {
    gx.clearRect(0, 0, W, H);
    var bg = gx.createLinearGradient(0, 0, 0, H);
    bg.addColorStop(0, '#02030b'); bg.addColorStop(.6, '#050716'); bg.addColorStop(1, '#0a0620');
    gx.fillStyle = bg; gx.fillRect(0, 0, W, H);
    for (var i = 0; i < blobs.length; i++) {
      var b = blobs[i], ang = t * b.sp * TAU + i * 2, cx = (b.x + Math.cos(ang) * .06) * W, cy = (b.y + Math.sin(ang * 1.3) * .06) * H,
          rad = b.r * Math.max(W, H) * .6, g = gx.createRadialGradient(cx, cy, 0, cx, cy, rad);
      g.addColorStop(0, 'hsla(' + b.h + ',90%,55%,' + b.a + ')'); g.addColorStop(.5, 'hsla(' + (b.h + 30) + ',80%,40%,' + b.a * .35 + ')');
      g.addColorStop(1, 'hsla(' + b.h + ',80%,30%,0)');
      gx.fillStyle = g; gx.fillRect(0, 0, W, H);
    }
    mx += (tx - mx) * .04; my += (ty - my) * .04;
    var sy = window.scrollY || 0;
    for (var k = 0; k < stars.length; k++) {
      var s = stars[k], f = (s.z + 1) * .5, x = s.x + mx * f * 14, y = ((s.y - sy * .03 * f) % H + H) % H + my * f * 10,
          tw = .55 + .45 * Math.sin(t * .002 * s.s + s.p);
      gx.globalAlpha = tw * (.5 + s.z * .22); gx.fillStyle = 'hsl(' + s.h + ',90%,' + (80 + s.z * 6) + '%)';
      gx.beginPath(); gx.arc(x, y, s.r, 0, TAU); gx.fill();
      if (s.z === 2 && tw > .9) { gx.globalAlpha = .35; gx.fillRect(x - 5, y - .3, 10, .6); gx.fillRect(x - .3, y - 5, .6, 10); }
    }
    gx.globalAlpha = 1;
    if (withPlanets) drawPlanets(t);
    if (!shoot && Math.random() < .004) shoot = { x: Math.random() * W * .8, y: Math.random() * H * .4, l: 0, v: 9 + Math.random() * 6 };
    if (shoot) {
      var gr = gx.createLinearGradient(shoot.x, shoot.y, shoot.x - 90, shoot.y - 45);
      gr.addColorStop(0, 'rgba(255,255,255,.95)'); gr.addColorStop(1, 'rgba(0,255,200,0)');
      gx.strokeStyle = gr; gx.lineWidth = 1.6; gx.beginPath(); gx.moveTo(shoot.x, shoot.y); gx.lineTo(shoot.x - 90, shoot.y - 45); gx.stroke();
      shoot.x += shoot.v; shoot.y += shoot.v * .5; shoot.l++;
      if (shoot.l > 70 || shoot.x > W + 100 || shoot.y > H + 100) shoot = null;
    }
  }

  /* ---------- serangan siber (simulasi) ---------- */
  var TYPES = ['SYN flood', 'SQL injection', 'SSH brute-force', 'Port scan', 'XSS probe', 'UDP flood', 'Credential stuffing', 'DNS amplification'];
  var BLOCKS = ['203.0.113.', '198.51.100.', '192.0.2.']; // blok IP contoh (RFC 5737), bukan IP nyata
  var blocked = 12000 + Math.floor(Math.random() * 7000), nextSpawn = 0, logLines = [];
  var head = document.createElement('b'), hl = document.createElement('span'), hr = document.createElement('span');
  hl.textContent = '▌CYBER DEFENSE // SIMULASI'; head.appendChild(hl); head.appendChild(hr); log.appendChild(head);
  function pad(n) { return (n < 10 ? '0' : '') + n; }
  function pushLog(src, dst, type, status) {
    var d = new Date(), row = document.createElement('div'),
        cls = status === 'BLOCKED' ? 'k' : status === 'MITIGATED' ? 'm' : 'w',
        ip = BLOCKS[Math.floor(Math.random() * 3)] + (1 + Math.floor(Math.random() * 254));
    row.innerHTML = ''; // aman: hanya textContent di bawah
    var s1 = document.createElement('span'); s1.className = 'a'; s1.textContent = pad(d.getHours()) + ':' + pad(d.getMinutes()) + ':' + pad(d.getSeconds()) + ' ' + type + ' ';
    var s2 = document.createElement('span'); s2.textContent = ip + ' ' + src + '→' + dst + ' ';
    var s3 = document.createElement('span'); s3.className = cls; s3.textContent = status;
    row.appendChild(s1); row.appendChild(s2); row.appendChild(s3);
    log.appendChild(row); logLines.push(row);
    while (logLines.length > 7) log.removeChild(logLines.shift());
  }
  function spawnAttack() {
    if (nodes.length < 2 || attacks.length > 11) return;
    var i = Math.floor(Math.random() * nodes.length), j = Math.random() < .4 ? 0 : Math.floor(Math.random() * nodes.length);
    if (i === j) j = (j + 1) % nodes.length;
    var A = nodes[i], B = nodes[j], mxp = (A.x + B.x) / 2, myp = (A.y + B.y) / 2 - Math.hypot(A.x - B.x, A.y - B.y) * (.18 + Math.random() * .18);
    var rr = Math.random(), status = rr < .72 ? 'BLOCKED' : rr < .88 ? 'MITIGATED' : 'ALERT';
    attacks.push({ a: A, b: B, cx: mxp, cy: myp, t: 0, sp: .00035 + Math.random() * .0004, type: TYPES[Math.floor(Math.random() * TYPES.length)],
      status: status, col: B.home ? '255,77,109' : (Math.random() < .3 ? '255,184,0' : '255,60,90') });
  }
  function bez(a, t) { var u = 1 - t; return [u * u * a.a.x + 2 * u * t * a.cx + t * t * a.b.x, u * u * a.a.y + 2 * u * t * a.cy + t * t * a.b.y]; }
  var lastC = 0;
  function drawCyber(t) {
    var dt = Math.min(60, t - lastC); lastC = t;
    cx2.clearRect(0, 0, W, H);
    // jaringan dasar
    cx2.lineWidth = 1; cx2.strokeStyle = 'rgba(0,255,200,.09)';
    links.forEach(function (l) { cx2.beginPath(); cx2.moveTo(nodes[l[0]].x, nodes[l[0]].y); cx2.lineTo(nodes[l[1]].x, nodes[l[1]].y); cx2.stroke(); });
    // simpul
    cx2.font = '600 10px ui-monospace,Consolas,monospace';
    nodes.forEach(function (n) {
      var pu = .5 + .5 * Math.sin(t * .003 + n.p), r = n.home ? 5 : 3;
      cx2.fillStyle = n.home ? 'rgba(0,255,200,.95)' : 'rgba(110,255,220,.75)';
      cx2.beginPath(); cx2.arc(n.x, n.y, r, 0, TAU); cx2.fill();
      cx2.strokeStyle = 'rgba(0,255,200,' + (.15 + pu * .3) + ')'; cx2.beginPath(); cx2.arc(n.x, n.y, r + 4 + pu * 5, 0, TAU); cx2.stroke();
      cx2.fillStyle = 'rgba(150,255,230,.7)'; cx2.fillText(n.name + (n.home ? ' ★' : ''), n.x + 9, n.y - 7);
    });
    // spawn
    nextSpawn -= dt;
    if (nextSpawn <= 0) { spawnAttack(); nextSpawn = 350 + Math.random() * 750; }
    // serangan
    for (var i = attacks.length - 1; i >= 0; i--) {
      var at = attacks[i]; at.t += at.sp * dt;
      var steps = 18, t0 = Math.max(0, at.t - .28);
      cx2.strokeStyle = 'rgba(' + at.col + ',.10)'; cx2.lineWidth = 1; // jalur penuh samar
      cx2.beginPath(); cx2.moveTo(at.a.x, at.a.y); cx2.quadraticCurveTo(at.cx, at.cy, at.b.x, at.b.y); cx2.stroke();
      for (var s = 0; s < steps; s++) { // ekor
        var p1 = bez(at, t0 + (Math.min(at.t, 1) - t0) * s / steps), p2 = bez(at, t0 + (Math.min(at.t, 1) - t0) * (s + 1) / steps);
        cx2.strokeStyle = 'rgba(' + at.col + ',' + (s / steps * .9) + ')'; cx2.lineWidth = 1 + s / steps * 1.6;
        cx2.beginPath(); cx2.moveTo(p1[0], p1[1]); cx2.lineTo(p2[0], p2[1]); cx2.stroke();
      }
      if (at.t < 1) {
        var h = bez(at, at.t), g = cx2.createRadialGradient(h[0], h[1], 0, h[0], h[1], 9);
        g.addColorStop(0, 'rgba(255,255,255,.95)'); g.addColorStop(.4, 'rgba(' + at.col + ',.7)'); g.addColorStop(1, 'rgba(' + at.col + ',0)');
        cx2.fillStyle = g; cx2.beginPath(); cx2.arc(h[0], h[1], 9, 0, TAU); cx2.fill();
      } else {
        ripples.push({ x: at.b.x, y: at.b.y, r: 4, l: 1, col: at.status === 'ALERT' ? '255,184,0' : '77,255,166' });
        blocked += at.status === 'ALERT' ? 0 : 1; hr.textContent = 'DIBLOKIR: ' + blocked.toLocaleString('en-US');
        pushLog(at.a.name, at.b.name, at.type, at.status); attacks.splice(i, 1);
      }
    }
    // gelombang tumbukan / perisai
    for (var k = ripples.length - 1; k >= 0; k--) {
      var rp = ripples[k]; rp.r += dt * .05; rp.l -= dt * .0016;
      if (rp.l <= 0) { ripples.splice(k, 1); continue; }
      cx2.strokeStyle = 'rgba(' + rp.col + ',' + rp.l * .8 + ')'; cx2.lineWidth = 1.6;
      cx2.beginPath(); cx2.arc(rp.x, rp.y, rp.r, 0, TAU); cx2.stroke();
    }
  }

  /* ---------- hujan biner ---------- */
  var lastRain = 0;
  function drawRain(t) {
    if (t - lastRain < 45) return; lastRain = t;
    rx.globalCompositeOperation = 'destination-out'; rx.fillStyle = 'rgba(0,0,0,.13)'; rx.fillRect(0, 0, W, H);
    rx.globalCompositeOperation = 'source-over'; rx.font = '700 ' + FS + 'px ui-monospace,Consolas,monospace';
    for (var i = 0; i < drops.length; i++) {
      var x = i * FS, y = drops[i] * FS;
      if (drops[i] > 0) {
        rx.fillStyle = 'rgba(210,255,240,.95)'; rx.fillText(Math.random() < .5 ? '0' : '1', x, y);
        rx.fillStyle = darkTheme ? 'rgba(0,255,140,.85)' : 'rgba(0,110,60,.9)'; rx.fillText(Math.random() < .5 ? '0' : '1', x, y - FS);
      }
      if (y > H && Math.random() > .975) drops[i] = Math.random() * -20;
      drops[i] += .55 + (i % 7) * .07;
    }
  }

  /* ---------- kontrol ---------- */
  function apply() {
    var f = FLAGS[mode];
    cg.style.display = f.g ? '' : 'none'; cc.style.display = f.c ? '' : 'none'; cr.style.display = f.r ? '' : 'none';
    log.style.display = f.c ? '' : 'none'; glow.style.display = mode === 'mati' ? 'none' : '';
    if (!f.g) gx.clearRect(0, 0, W, H); if (!f.c) cx2.clearRect(0, 0, W, H); if (!f.r) rx.clearRect(0, 0, W, H);
    btn.textContent = '◉ ' + LABEL[mode]; btn.setAttribute('aria-label', 'Ganti efek latar. Sekarang: ' + LABEL[mode]);
    hr.textContent = 'DIBLOKIR: ' + blocked.toLocaleString('en-US');
  }
  function frame(t) {
    var f = FLAGS[mode];
    if (f.g) drawGalaxy(t, f.p);
    if (f.c) drawCyber(t);
    if (f.r) drawRain(t);
    requestAnimationFrame(frame);
  }
  function renderStatic() {
    var f = FLAGS[mode]; if (f.g) drawGalaxy(1000, f.p);
    if (f.c) { for (var i = 0; i < 6; i++) spawnAttack(); attacks.forEach(function (a) { a.t = .3 + Math.random() * .5; }); drawCyber(1000); }
    if (f.r) for (var j = 0; j < 40; j++) { lastRain = 0; drawRain(j * 60); }
  }
  btn.onclick = function () {
    mode = MODES[(MODES.indexOf(mode) + 1) % MODES.length];
    try { localStorage.setItem('fx-mode', mode); } catch (e) {}
    apply(); if (reduce) renderStatic();
  };
  addEventListener('resize', function () { resize(); apply(); if (reduce) renderStatic(); });
  addEventListener('mousemove', function (e) {
    tx = (e.clientX / W - .5) * 2; ty = (e.clientY / H - .5) * 2; glow.style.transform = 'translate(' + e.clientX + 'px,' + e.clientY + 'px)';
  }, { passive: true });
  addEventListener('scroll', function () {
    var h = document.documentElement.scrollHeight - innerHeight; bar.style.width = (h > 0 ? scrollY / h * 100 : 0) + '%';
  }, { passive: true });

  function reveal() {
    if (reduce || !('IntersectionObserver' in window)) return;
    var secs = document.querySelectorAll('section');
    var io = new IntersectionObserver(function (es) {
      es.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add('fx-in'); io.unobserve(e.target); } });
    }, { threshold: .08 });
    secs.forEach(function (s, i) { if (i > 0) { s.classList.add('fx-reveal'); io.observe(s); } });
    setTimeout(function () { document.querySelectorAll('.fx-reveal').forEach(function (s) { s.classList.add('fx-in'); }); }, 4500);
  }

  resize(); apply(); reveal();
  if (reduce) renderStatic(); else requestAnimationFrame(frame);
})();
