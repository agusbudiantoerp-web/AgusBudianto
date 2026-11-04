/*!
 * efek-futuristik.js  -  latar galaksi dinamis + hujan biner (gaya The Matrix)
 * Cara pakai: tambahkan SATU baris sebelum </body> di index.html:
 *   <script src="efek-futuristik.js" defer></script>
 * Hapus baris itu untuk menghilangkan efek. File lain tidak perlu diubah.
 */
(function () {
  'use strict';
  if (window.__fxLoaded) return;
  window.__fxLoaded = true;

  var reduce = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
  var MODES = ['gabungan', 'galaksi', 'biner', 'mati'];
  var LABEL = { gabungan: 'Galaksi + Biner', galaksi: 'Galaksi', biner: 'Biner', mati: 'Efek mati' };
  var mode = 'gabungan';
  try { var m = localStorage.getItem('fx-mode'); if (MODES.indexOf(m) > -1) mode = m; } catch (e) {}

  /* ---------- deteksi tema halaman (gelap / terang) ---------- */
  function lum(rgb) {
    var a = (rgb.match(/[\d.]+/g) || [0, 0, 0]).map(Number);
    return (0.2126 * a[0] + 0.7152 * a[1] + 0.0722 * a[2]) / 255;
  }
  var cs = getComputedStyle(document.body);
  var darkTheme = lum(cs.color) > 0.5; // teks terang = tema gelap

  /* ---------- CSS ---------- */
  var css = [
    '#fx-galaxy,#fx-rain{position:fixed;inset:0;width:100%;height:100%;pointer-events:none}',
    '#fx-galaxy{z-index:-2}',
    '#fx-rain{z-index:' + (darkTheme ? '-1' : '2147483000') + ';opacity:' + (darkTheme ? '.55' : '.14') + '}',
    '#fx-glow{position:fixed;left:0;top:0;width:520px;height:520px;margin:-260px 0 0 -260px;border-radius:50%;pointer-events:none;z-index:-1;' +
      'background:radial-gradient(circle,rgba(0,255,200,.10),rgba(120,80,255,.06) 40%,transparent 70%);transition:opacity .4s}',
    '#fx-bar{position:fixed;left:0;top:0;height:3px;width:0;z-index:2147483001;pointer-events:none;' +
      'background:linear-gradient(90deg,#00ffc8,#7a5cff,#ff3df0);box-shadow:0 0 12px #00ffc8}',
    '#fx-btn{position:fixed;left:14px;bottom:14px;z-index:2147483002;font:600 12px/1 ui-monospace,Consolas,monospace;' +
      'color:#00ffc8;background:rgba(3,8,18,.82);border:1px solid rgba(0,255,200,.5);border-radius:999px;padding:9px 13px;cursor:pointer;' +
      'box-shadow:0 0 14px rgba(0,255,200,.25);letter-spacing:.04em}',
    '#fx-btn:hover{box-shadow:0 0 22px rgba(0,255,200,.55)}',
    '#fx-btn:focus-visible{outline:3px solid #ffd84d;outline-offset:2px}',
    '.fx-reveal{opacity:0;transform:translateY(26px);transition:opacity .8s ease,transform .8s ease}',
    '.fx-in{opacity:1;transform:none}',
    '@media print{#fx-galaxy,#fx-rain,#fx-glow,#fx-bar,#fx-btn{display:none!important}.fx-reveal{opacity:1!important;transform:none!important}}'
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
  var st = document.createElement('style');
  st.textContent = css.join('\n');
  document.head.appendChild(st);

  /* ---------- elemen ---------- */
  function mk(tag, id) { var e = document.createElement(tag); e.id = id; return e; }
  var cg = mk('canvas', 'fx-galaxy'), cr = mk('canvas', 'fx-rain'),
      glow = mk('div', 'fx-glow'), bar = mk('div', 'fx-bar'), btn = mk('button', 'fx-btn');
  cg.setAttribute('aria-hidden', 'true'); cr.setAttribute('aria-hidden', 'true');
  btn.type = 'button';
  document.body.insertBefore(cg, document.body.firstChild);
  document.body.insertBefore(cr, document.body.firstChild);
  document.body.appendChild(glow); document.body.appendChild(bar); document.body.appendChild(btn);
  var gx = cg.getContext('2d'), rx = cr.getContext('2d');

  var W = 0, H = 0, DPR = Math.min(window.devicePixelRatio || 1, 1.5);
  var stars = [], drops = [], shoot = null, mx = 0, my = 0, tx = 0, ty = 0;
  var FS = 16; // ukuran huruf biner

  function resize() {
    W = innerWidth; H = innerHeight;
    [cg, cr].forEach(function (c) { c.width = W * DPR; c.height = H * DPR; });
    gx.setTransform(DPR, 0, 0, DPR, 0, 0); rx.setTransform(DPR, 0, 0, DPR, 0, 0);
    var n = Math.round(W * H / 5200); // jumlah bintang menyesuaikan layar
    stars = [];
    for (var i = 0; i < n; i++) {
      var layer = Math.random() < .6 ? 0 : Math.random() < .7 ? 1 : 2;
      stars.push({ x: Math.random() * W, y: Math.random() * H, z: layer,
        r: .4 + layer * .45 + Math.random() * .5, p: Math.random() * 6.28, s: .6 + Math.random() * 1.6,
        h: [200, 170, 280, 330][Math.floor(Math.random() * 4)] });
    }
    var cols = Math.ceil(W / FS);
    drops = [];
    for (var c = 0; c < cols; c++) drops.push(Math.random() * -60);
  }

  /* ---------- galaksi ---------- */
  var blobs = [
    { x: .2, y: .25, r: .55, h: 265, a: .20, sp: .00006 },
    { x: .78, y: .35, r: .5, h: 190, a: .15, sp: .00008 },
    { x: .5, y: .85, r: .6, h: 320, a: .14, sp: .00005 }
  ];
  function drawGalaxy(t) {
    gx.clearRect(0, 0, W, H);
    var bg = gx.createLinearGradient(0, 0, 0, H);
    bg.addColorStop(0, '#02030b'); bg.addColorStop(.6, '#050716'); bg.addColorStop(1, '#0a0620');
    gx.fillStyle = bg; gx.fillRect(0, 0, W, H);
    // nebula bergerak pelan
    for (var i = 0; i < blobs.length; i++) {
      var b = blobs[i], ang = t * b.sp * 6.28 + i * 2,
          cx = (b.x + Math.cos(ang) * .06) * W, cy = (b.y + Math.sin(ang * 1.3) * .06) * H,
          rad = b.r * Math.max(W, H) * .6, g = gx.createRadialGradient(cx, cy, 0, cx, cy, rad);
      g.addColorStop(0, 'hsla(' + b.h + ',90%,55%,' + b.a + ')');
      g.addColorStop(.5, 'hsla(' + (b.h + 30) + ',80%,40%,' + b.a * .35 + ')');
      g.addColorStop(1, 'hsla(' + b.h + ',80%,30%,0)');
      gx.fillStyle = g; gx.fillRect(0, 0, W, H);
    }
    // bintang dengan paralaks & kerlip
    mx += (tx - mx) * .04; my += (ty - my) * .04;
    var sy = (window.scrollY || 0);
    for (var k = 0; k < stars.length; k++) {
      var s = stars[k], f = (s.z + 1) * .5;
      var x = s.x + mx * f * 14 - 0, y = ((s.y - sy * .03 * f) % H + H) % H + my * f * 10;
      var tw = .55 + .45 * Math.sin(t * .002 * s.s + s.p);
      gx.globalAlpha = tw * (.5 + s.z * .22);
      gx.fillStyle = 'hsl(' + s.h + ',90%,' + (80 + s.z * 6) + '%)';
      gx.beginPath(); gx.arc(x, y, s.r, 0, 6.283); gx.fill();
      if (s.z === 2 && tw > .9) { // kilau
        gx.globalAlpha = .35; gx.fillRect(x - 5, y - .3, 10, .6); gx.fillRect(x - .3, y - 5, .6, 10);
      }
    }
    gx.globalAlpha = 1;
    // bintang jatuh sesekali
    if (!shoot && Math.random() < .004) shoot = { x: Math.random() * W * .8, y: Math.random() * H * .4, l: 0, v: 9 + Math.random() * 6 };
    if (shoot) {
      var gr = gx.createLinearGradient(shoot.x, shoot.y, shoot.x - 90, shoot.y - 45);
      gr.addColorStop(0, 'rgba(255,255,255,.95)'); gr.addColorStop(1, 'rgba(0,255,200,0)');
      gx.strokeStyle = gr; gx.lineWidth = 1.6; gx.beginPath();
      gx.moveTo(shoot.x, shoot.y); gx.lineTo(shoot.x - 90, shoot.y - 45); gx.stroke();
      shoot.x += shoot.v; shoot.y += shoot.v * .5; shoot.l++;
      if (shoot.l > 70 || shoot.x > W + 100 || shoot.y > H + 100) shoot = null;
    }
  }

  /* ---------- hujan biner ---------- */
  var lastRain = 0;
  function drawRain(t) {
    if (t - lastRain < 45) return; // ~22 fps, ringan dan terasa "digital"
    lastRain = t;
    rx.globalCompositeOperation = 'destination-out';
    rx.fillStyle = 'rgba(0,0,0,.13)'; rx.fillRect(0, 0, W, H); // jejak memudar
    rx.globalCompositeOperation = 'source-over';
    rx.font = '700 ' + FS + 'px ui-monospace,Consolas,monospace';
    for (var i = 0; i < drops.length; i++) {
      var ch = Math.random() < .5 ? '0' : '1', x = i * FS, y = drops[i] * FS;
      if (drops[i] > 0) {
        rx.fillStyle = 'rgba(210,255,240,.95)'; rx.fillText(ch, x, y); // kepala terang
        rx.fillStyle = darkTheme ? 'rgba(0,255,140,.85)' : 'rgba(0,110,60,.9)';
        rx.fillText(Math.random() < .5 ? '0' : '1', x, y - FS);
      }
      if (y > H && Math.random() > .975) drops[i] = Math.random() * -20;
      drops[i] += .55 + (i % 7) * .07;
    }
  }

  /* ---------- loop ---------- */
  var raf = 0;
  function apply() {
    var g = mode === 'gabungan' || mode === 'galaksi', r = mode === 'gabungan' || mode === 'biner';
    cg.style.display = g ? '' : 'none'; cr.style.display = r ? '' : 'none';
    glow.style.display = mode === 'mati' ? 'none' : '';
    if (mode === 'mati') { gx.clearRect(0, 0, W, H); rx.clearRect(0, 0, W, H); }
    btn.textContent = '◉ ' + LABEL[mode];
    btn.setAttribute('aria-label', 'Ganti efek latar. Sekarang: ' + LABEL[mode]);
  }
  function frame(t) {
    if (mode !== 'mati') {
      if (mode !== 'biner') drawGalaxy(t);
      if (mode !== 'galaksi') drawRain(t);
    }
    raf = requestAnimationFrame(frame);
  }
  btn.onclick = function () {
    mode = MODES[(MODES.indexOf(mode) + 1) % MODES.length];
    try { localStorage.setItem('fx-mode', mode); } catch (e) {}
    apply(); if (reduce) renderStatic();
  };
  function renderStatic() { if (mode !== 'mati') { drawGalaxy(1000); for (var i = 0; i < 40; i++) { lastRain = 0; drawRain(i * 60); } } }

  addEventListener('resize', function () { resize(); apply(); if (reduce) renderStatic(); });
  addEventListener('mousemove', function (e) {
    tx = (e.clientX / W - .5) * 2; ty = (e.clientY / H - .5) * 2;
    glow.style.transform = 'translate(' + e.clientX + 'px,' + e.clientY + 'px)';
  }, { passive: true });
  addEventListener('scroll', function () {
    var h = document.documentElement.scrollHeight - innerHeight;
    bar.style.width = (h > 0 ? scrollY / h * 100 : 0) + '%';
  }, { passive: true });

  /* ---------- animasi muncul saat scroll (hanya section) ---------- */
  function reveal() {
    if (reduce || !('IntersectionObserver' in window)) return;
    var secs = document.querySelectorAll('main > section, body > section, section');
    var io = new IntersectionObserver(function (es) {
      es.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add('fx-in'); io.unobserve(e.target); } });
    }, { threshold: .08 });
    secs.forEach(function (s, i) { if (i > 0) { s.classList.add('fx-reveal'); io.observe(s); } });
    setTimeout(function () { document.querySelectorAll('.fx-reveal').forEach(function (s) { s.classList.add('fx-in'); }); }, 4500); // pengaman
  }

  resize(); apply(); reveal();
  if (reduce) renderStatic(); else raf = requestAnimationFrame(frame);
})();
