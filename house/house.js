/* ============================================================================
   Home Studio — a private 3D walkthrough + planner for one house.
   Plan view (2D canvas) is where you build. 3D and Walk are for looking around.
   Everything lives in this browser; export a .house.json to back it up.
   ========================================================================== */

/* ---------------------------------------------------------------- helpers */
var $  = function (sel, root) { return (root || document).querySelector(sel); };
var $$ = function (sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); };

function uid(prefix) {
  return (prefix || 'x') + '_' + Math.random().toString(36).slice(2, 9);
}
function clamp(v, lo, hi) { return v < lo ? lo : v > hi ? hi : v; }
function round(v, dp) { var f = Math.pow(10, dp == null ? 3 : dp); return Math.round(v * f) / f; }
function deg2rad(d) { return d * Math.PI / 180; }
function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
    return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
  });
}
function debounce(fn, ms) {
  var t; return function () { var a = arguments, self = this; clearTimeout(t); t = setTimeout(function () { fn.apply(self, a); }, ms); };
}
function toast(msg, kind) {
  var el = $('#toast');
  el.textContent = msg;
  el.style.borderColor = kind === 'bad' ? '#4a2233' : kind === 'good' ? '#1f4a33' : '';
  el.classList.add('show');
  clearTimeout(toast._t);
  toast._t = setTimeout(function () { el.classList.remove('show'); }, 2600);
}

/* Lengths are always stored in metres. These convert for display / input. */
function fmtLen(m) {
  if (S.proj && S.proj.units === 'ft') {
    var totalIn = m * 39.3700787;
    var ft = Math.floor(totalIn / 12);
    var inch = Math.round((totalIn - ft * 12) * 10) / 10;
    if (inch >= 12) { ft += 1; inch -= 12; }
    return ft + "'" + (inch ? ' ' + inch + '"' : '');
  }
  if (m < 1) return Math.round(m * 100) + ' cm';
  return (Math.round(m * 100) / 100).toFixed(2).replace(/\.?0+$/, '') + ' m';
}
function fmtArea(sqm) {
  if (S.proj && S.proj.units === 'ft') return Math.round(sqm * 10.7639) + ' sq ft';
  return (Math.round(sqm * 10) / 10) + ' m²';
}
/* Accepts 2.4 / 240cm / 2400mm / 8ft / 7'6" / 95in — returns metres. */
function parseLen(str, fallback) {
  if (str == null) return fallback;
  var s = String(str).trim().toLowerCase().replace(/,/g, '.');
  if (!s) return fallback;
  var m;
  if ((m = s.match(/^(-?[\d.]+)\s*mm$/))) return parseFloat(m[1]) / 1000;
  if ((m = s.match(/^(-?[\d.]+)\s*cm$/))) return parseFloat(m[1]) / 100;
  if ((m = s.match(/^(-?[\d.]+)\s*m$/)))  return parseFloat(m[1]);
  if ((m = s.match(/^(-?[\d.]+)\s*(?:in|")$/))) return parseFloat(m[1]) * 0.0254;
  if ((m = s.match(/^(-?[\d.]+)\s*(?:ft|')$/))) return parseFloat(m[1]) * 0.3048;
  if ((m = s.match(/^(-?[\d.]+)\s*(?:ft|')\s*(-?[\d.]+)\s*(?:in|")?$/))) {
    return parseFloat(m[1]) * 0.3048 + parseFloat(m[2]) * 0.0254;
  }
  var n = parseFloat(s);
  if (isNaN(n)) return fallback;
  return S.proj && S.proj.units === 'ft' ? n * 0.3048 : n;
}
function money(v) {
  if (v == null || v === '' || isNaN(v)) return '';
  var cur = (S.proj && S.proj.currency) || '£';
  return cur + (Math.round(v * 100) / 100).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 2 });
}

/* Shrinks any image (File, blob URL or data URI) so the project stays small. */
function shrinkImage(src, maxPx, quality) {
  return new Promise(function (resolve, reject) {
    var img = new Image();
    img.crossOrigin = 'anonymous';
    img.onload = function () {
      var scale = Math.min(1, maxPx / Math.max(img.width, img.height));
      var w = Math.max(1, Math.round(img.width * scale));
      var h = Math.max(1, Math.round(img.height * scale));
      var c = document.createElement('canvas');
      c.width = w; c.height = h;
      var ctx = c.getContext('2d');
      ctx.drawImage(img, 0, 0, w, h);
      try { resolve(c.toDataURL('image/jpeg', quality || 0.8)); }
      catch (e) { reject(e); }
    };
    img.onerror = function () { reject(new Error('Could not read that image')); };
    img.src = src;
  });
}
function fileToDataURL(file) {
  return new Promise(function (resolve, reject) {
    var r = new FileReader();
    r.onload = function () { resolve(r.result); };
    r.onerror = function () { reject(new Error('Could not read that file')); };
    r.readAsDataURL(file);
  });
}

/* ------------------------------------------------------------------ state */
var S = {
  proj: null,
  view: 'plan',
  tool: 'select',
  level: 0,
  sel: null,            // { type:'room'|'item'|'opening', id }
  hover: null,
  pendingPlace: null,   // item id waiting to be dropped on the plan
  cam: { x: 0, y: 0, ppm: 55 },   // plan view transform (pixels per metre)
  grid: 0.25,
  snap: true,
  history: [],
  future: [],
  needs3D: false
};

var DEFAULT_SHAPES = [
  { id: 'box',      label: 'Box / cabinet', w: 0.8, d: 0.5, h: 0.9 },
  { id: 'sofa',     label: 'Sofa',          w: 2.0, d: 0.9, h: 0.85 },
  { id: 'chair',    label: 'Chair',         w: 0.5, d: 0.55, h: 0.9 },
  { id: 'table',    label: 'Table / desk',  w: 1.4, d: 0.8, h: 0.75 },
  { id: 'bed',      label: 'Bed',           w: 1.5, d: 2.0, h: 0.55 },
  { id: 'wardrobe', label: 'Wardrobe',      w: 1.2, d: 0.6, h: 2.0 },
  { id: 'shelf',    label: 'Shelving',      w: 0.9, d: 0.35, h: 1.8 },
  { id: 'rug',      label: 'Rug',           w: 2.0, d: 1.4, h: 0.02 },
  { id: 'tv',       label: 'TV / screen',   w: 1.2, d: 0.08, h: 0.7 },
  { id: 'art',      label: 'Art / mirror',  w: 0.6, d: 0.04, h: 0.8 },
  { id: 'lamp',     label: 'Lamp',          w: 0.4, d: 0.4, h: 1.5 },
  { id: 'plant',    label: 'Plant',         w: 0.5, d: 0.5, h: 1.1 },
  { id: 'appliance',label: 'Appliance',     w: 0.6, d: 0.6, h: 0.85 }
];
function shapeDef(id) {
  for (var i = 0; i < DEFAULT_SHAPES.length; i++) if (DEFAULT_SHAPES[i].id === id) return DEFAULT_SHAPES[i];
  return DEFAULT_SHAPES[0];
}

function newProject(name) {
  return {
    v: 1,
    name: name || 'Our house',
    units: 'm',
    currency: '£',
    opts: { wallH: 2.4, wallT: 0.1, shadows: true, ceilings: false, clip: true, light: 100 },
    levels: [newLevel('Ground floor', 0)],
    items: [],
    photos: []
  };
}
function newLevel(name, base) {
  return {
    id: uid('lv'), name: name, base: base || 0, height: 2.4,
    rooms: [], openings: [],
    plan: { src: '', opacity: 0.55, ppm: 40, ox: 0, oy: 0, locked: true }
  };
}
function level() { return S.proj.levels[clamp(S.level, 0, S.proj.levels.length - 1)]; }
function findRoom(id) { var l = level(); for (var i = 0; i < l.rooms.length; i++) if (l.rooms[i].id === id) return l.rooms[i]; return null; }
function findOpening(id) { var l = level(); for (var i = 0; i < l.openings.length; i++) if (l.openings[i].id === id) return l.openings[i]; return null; }
function findItem(id) { for (var i = 0; i < S.proj.items.length; i++) if (S.proj.items[i].id === id) return S.proj.items[i]; return null; }
function findPhoto(id) { for (var i = 0; i < S.proj.photos.length; i++) if (S.proj.photos[i].id === id) return S.proj.photos[i]; return null; }
function levelItems(lv) { var id = (lv || level()).id; return S.proj.items.filter(function (it) { return it.level === id && it.placed; }); }

/* ---------------------------------------------------------- undo / redo */
function snapshot() {
  try {
    S.history.push(JSON.stringify(S.proj));
    if (S.history.length > 40) S.history.shift();
    S.future.length = 0;
    updateUndoButtons();
  } catch (e) { /* nothing worth breaking the app for */ }
}
function undo() {
  if (!S.history.length) return;
  S.future.push(JSON.stringify(S.proj));
  S.proj = JSON.parse(S.history.pop());
  afterRestore();
}
function redo() {
  if (!S.future.length) return;
  S.history.push(JSON.stringify(S.proj));
  S.proj = JSON.parse(S.future.pop());
  afterRestore();
}
function afterRestore() {
  S.level = clamp(S.level, 0, S.proj.levels.length - 1);
  S.sel = null;
  updateUndoButtons();
  syncSettingsInputs();
  renderAll();
  save();
}
function updateUndoButtons() {
  $('#btnUndo').disabled = !S.history.length;
  $('#btnRedo').disabled = !S.future.length;
}

/* -------------------------------------------------------------- storage */
var DB_NAME = 'homeStudio', DB_STORE = 'proj';
function openDB() {
  return new Promise(function (resolve, reject) {
    if (!window.indexedDB) return reject(new Error('no idb'));
    var req = indexedDB.open(DB_NAME, 1);
    req.onupgradeneeded = function () { req.result.createObjectStore(DB_STORE); };
    req.onsuccess = function () { resolve(req.result); };
    req.onerror = function () { reject(req.error); };
  });
}
function dbPut(key, val) {
  return openDB().then(function (db) {
    return new Promise(function (resolve, reject) {
      var tx = db.transaction(DB_STORE, 'readwrite');
      tx.objectStore(DB_STORE).put(val, key);
      tx.oncomplete = function () { resolve(); };
      tx.onerror = function () { reject(tx.error); };
    });
  });
}
function dbGet(key) {
  return openDB().then(function (db) {
    return new Promise(function (resolve, reject) {
      var tx = db.transaction(DB_STORE, 'readonly');
      var r = tx.objectStore(DB_STORE).get(key);
      r.onsuccess = function () { resolve(r.result); };
      r.onerror = function () { reject(r.error); };
    });
  });
}
var save = debounce(function () {
  var payload = JSON.stringify(S.proj);
  dbPut('current', payload).then(function () {
    setSaveState('Saved');
  })['catch'](function () {
    try { localStorage.setItem('homeStudio.proj', payload); setSaveState('Saved'); }
    catch (e) { setSaveState('Too big to save — export a backup', true); }
  });
}, 700);
function setSaveState(msg, bad) {
  var el = $('#saveState');
  el.textContent = msg;
  el.style.color = bad ? 'var(--bad)' : 'var(--muted)';
}
function load() {
  return dbGet('current').then(function (v) {
    if (v) return v;
    return localStorage.getItem('homeStudio.proj');
  })['catch'](function () {
    try { return localStorage.getItem('homeStudio.proj'); } catch (e) { return null; }
  });
}
function touch() { setSaveState('Saving…'); save(); }

/* ------------------------------------------------------------- geometry */
/* Walls are generated from room rectangles, then cut by doors and windows. */
function wallSegments(lv) {
  lv = lv || level();
  var t = S.proj.opts.wallT, groups = {};
  function push(axis, coord, from, to) {
    if (to - from <= 0.001) return;
    var key = axis + '|' + coord.toFixed(3);
    (groups[key] = groups[key] || { axis: axis, coord: coord, runs: [] }).runs.push([from, to]);
  }
  lv.rooms.forEach(function (r) {
    push('h', r.y,       r.x - t / 2, r.x + r.w + t / 2);
    push('h', r.y + r.d, r.x - t / 2, r.x + r.w + t / 2);
    push('v', r.x,       r.y - t / 2, r.y + r.d + t / 2);
    push('v', r.x + r.w, r.y - t / 2, r.y + r.d + t / 2);
  });
  var segs = [];
  Object.keys(groups).forEach(function (k) {
    var g = groups[k];
    g.runs.sort(function (a, b) { return a[0] - b[0]; });
    var cur = null;
    g.runs.forEach(function (r) {
      if (cur && r[0] <= cur.to + 0.001) { cur.to = Math.max(cur.to, r[1]); return; }
      cur = { axis: g.axis, coord: g.coord, from: r[0], to: r[1] };
      segs.push(cur);
    });
  });
  return segs;
}

/* Splits one wall segment into the solid pieces left over around its openings. */
function wallPieces(seg, lv) {
  lv = lv || level();
  var H = lv.height || S.proj.opts.wallH;
  var holes = lv.openings.filter(function (o) {
    return o.axis === seg.axis && Math.abs(o.coord - seg.coord) < 0.06 &&
           o.to > seg.from + 0.001 && o.from < seg.to - 0.001;
  }).map(function (o) {
    return { from: Math.max(o.from, seg.from), to: Math.min(o.to, seg.to), sill: o.sill, top: Math.min(o.top, H) };
  }).sort(function (a, b) { return a.from - b.from; });

  var pieces = [], cursor = seg.from;
  holes.forEach(function (h) {
    if (h.from > cursor + 0.001) pieces.push({ from: cursor, to: h.from, y0: 0, y1: H });
    if (h.sill > 0.001)          pieces.push({ from: h.from, to: h.to, y0: 0, y1: h.sill });
    if (h.top < H - 0.001)       pieces.push({ from: h.from, to: h.to, y0: h.top, y1: H });
    cursor = Math.max(cursor, h.to);
  });
  if (cursor < seg.to - 0.001) pieces.push({ from: cursor, to: seg.to, y0: 0, y1: H });
  return pieces.map(function (p) { return { axis: seg.axis, coord: seg.coord, from: p.from, to: p.to, y0: p.y0, y1: p.y1 }; });
}

function allWallPieces(lv) {
  lv = lv || level();
  var out = [];
  wallSegments(lv).forEach(function (seg) { out = out.concat(wallPieces(seg, lv)); });
  return out;
}

/* Rectangles a walking person actually bumps into (window sills, walls, not lintels). */
function collisionRects(lv) {
  var t = S.proj.opts.wallT;
  return allWallPieces(lv).filter(function (p) { return p.y0 < 1.55 && p.y1 > 0.2; }).map(function (p) {
    return p.axis === 'h'
      ? { x0: p.from, x1: p.to, y0: p.coord - t / 2, y1: p.coord + t / 2 }
      : { x0: p.coord - t / 2, x1: p.coord + t / 2, y0: p.from, y1: p.to };
  });
}

function roomAt(x, y, lv) {
  lv = lv || level();
  for (var i = lv.rooms.length - 1; i >= 0; i--) {
    var r = lv.rooms[i];
    if (x >= r.x && x <= r.x + r.w && y >= r.y && y <= r.y + r.d) return r;
  }
  return null;
}
function roomArea(r) { return r.w * r.d; }

/* Item footprint corners in plan space, honouring rotation. */
function itemCorners(it) {
  var c = Math.cos(deg2rad(it.rot || 0)), s = Math.sin(deg2rad(it.rot || 0));
  var hw = it.w / 2, hd = it.d / 2;
  return [[-hw, -hd], [hw, -hd], [hw, hd], [-hw, hd]].map(function (p) {
    return { x: it.x + p[0] * c - p[1] * s, y: it.y + p[0] * s + p[1] * c };
  });
}
function pointInItem(x, y, it) {
  var c = Math.cos(-deg2rad(it.rot || 0)), s = Math.sin(-deg2rad(it.rot || 0));
  var dx = x - it.x, dy = y - it.y;
  var lx = dx * c - dy * s, ly = dx * s + dy * c;
  return Math.abs(lx) <= it.w / 2 && Math.abs(ly) <= it.d / 2;
}
/* Distance from a point to a wall segment, plus how far along it that lands. */
function segHit(x, y, seg) {
  if (seg.axis === 'h') {
    var t = clamp(x, seg.from, seg.to);
    return { dist: Math.hypot(x - t, y - seg.coord), along: t };
  }
  var u = clamp(y, seg.from, seg.to);
  return { dist: Math.hypot(x - seg.coord, y - u), along: u };
}
function bounds(lv) {
  lv = lv || level();
  var b = null;
  function add(x0, y0, x1, y1) {
    if (!b) b = { x0: x0, y0: y0, x1: x1, y1: y1 };
    else { b.x0 = Math.min(b.x0, x0); b.y0 = Math.min(b.y0, y0); b.x1 = Math.max(b.x1, x1); b.y1 = Math.max(b.y1, y1); }
  }
  lv.rooms.forEach(function (r) { add(r.x, r.y, r.x + r.w, r.y + r.d); });
  levelItems(lv).forEach(function (it) {
    itemCorners(it).forEach(function (c) { add(c.x, c.y, c.x, c.y); });
  });
  if (lv.plan && lv.plan.src && lv.plan.imgW) {
    add(lv.plan.ox, lv.plan.oy, lv.plan.ox + lv.plan.imgW / lv.plan.ppm, lv.plan.oy + lv.plan.imgH / lv.plan.ppm);
  }
  return b || { x0: 0, y0: 0, x1: 8, y1: 6 };
}

/* ========================================================================
   PLAN VIEW — the 2D canvas you build on
   ====================================================================== */
var planCanvas = $('#planCanvas'), pctx = planCanvas.getContext('2d');
var imgCache = {};
function cachedImage(src, onload) {
  if (!src) return null;
  if (imgCache[src]) return imgCache[src].complete ? imgCache[src] : null;
  var img = new Image();
  img.onload = function () { if (onload) onload(); };
  img.src = src;
  imgCache[src] = img;
  return null;
}

function w2s(x, y) { return { x: x * S.cam.ppm + S.cam.x, y: y * S.cam.ppm + S.cam.y }; }
function s2w(x, y) { return { x: (x - S.cam.x) / S.cam.ppm, y: (y - S.cam.y) / S.cam.ppm }; }
function snapVal(v) { return S.snap && S.grid > 0 ? Math.round(v / S.grid) * S.grid : round(v, 3); }

function fitToPlan() {
  var b = bounds(), pad = 1.2;
  var cw = planCanvas.clientWidth, ch = planCanvas.clientHeight;
  var w = (b.x1 - b.x0) + pad * 2, h = (b.y1 - b.y0) + pad * 2;
  S.cam.ppm = clamp(Math.min(cw / w, ch / h), 6, 400);
  S.cam.x = cw / 2 - ((b.x0 + b.x1) / 2) * S.cam.ppm;
  S.cam.y = ch / 2 - ((b.y0 + b.y1) / 2) * S.cam.ppm;
  drawPlan();
}

function resizePlanCanvas() {
  var dpr = Math.min(window.devicePixelRatio || 1, 2);
  planCanvas.width = Math.max(1, Math.floor(planCanvas.clientWidth * dpr));
  planCanvas.height = Math.max(1, Math.floor(planCanvas.clientHeight * dpr));
  pctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  drawPlan();
}

function drawPlan() {
  if (S.view !== 'plan') return;
  var cw = planCanvas.clientWidth, ch = planCanvas.clientHeight, lv = level();
  pctx.save();
  pctx.clearRect(0, 0, cw, ch);
  pctx.fillStyle = '#08081a';
  pctx.fillRect(0, 0, cw, ch);

  /* grid */
  if (S.grid > 0) {
    var step = S.grid * S.cam.ppm;
    while (step < 9) step *= 2;
    var majorEvery = Math.max(1, Math.round(1 / S.grid));
    var startX = S.cam.x % step, startY = S.cam.y % step;
    pctx.lineWidth = 1;
    for (var gx = startX, i = 0; gx < cw; gx += step, i++) {
      var wx = Math.round((gx - S.cam.x) / S.cam.ppm / S.grid);
      pctx.strokeStyle = (wx % majorEvery === 0) ? '#1a1a3d' : '#111128';
      pctx.beginPath(); pctx.moveTo(Math.round(gx) + 0.5, 0); pctx.lineTo(Math.round(gx) + 0.5, ch); pctx.stroke();
    }
    for (var gy = startY; gy < ch; gy += step) {
      var wy = Math.round((gy - S.cam.y) / S.cam.ppm / S.grid);
      pctx.strokeStyle = (wy % majorEvery === 0) ? '#1a1a3d' : '#111128';
      pctx.beginPath(); pctx.moveTo(0, Math.round(gy) + 0.5); pctx.lineTo(cw, Math.round(gy) + 0.5); pctx.stroke();
    }
  }

  /* floor plan underlay */
  if (lv.plan && lv.plan.src) {
    var img = cachedImage(lv.plan.src, drawPlan);
    if (img) {
      lv.plan.imgW = img.width; lv.plan.imgH = img.height;
      var p0 = w2s(lv.plan.ox, lv.plan.oy);
      var pw = img.width / lv.plan.ppm * S.cam.ppm, ph = img.height / lv.plan.ppm * S.cam.ppm;
      pctx.globalAlpha = lv.plan.opacity;
      pctx.drawImage(img, p0.x, p0.y, pw, ph);
      pctx.globalAlpha = 1;
      if (!lv.plan.locked) {
        pctx.strokeStyle = 'rgba(196,107,228,.8)'; pctx.setLineDash([6, 4]); pctx.lineWidth = 1.5;
        pctx.strokeRect(p0.x, p0.y, pw, ph); pctx.setLineDash([]);
      }
    }
  }

  /* rooms */
  lv.rooms.forEach(function (r) {
    var a = w2s(r.x, r.y), b = w2s(r.x + r.w, r.y + r.d);
    pctx.fillStyle = r.floor || '#1b2340';
    pctx.globalAlpha = 0.9;
    pctx.fillRect(a.x, a.y, b.x - a.x, b.y - a.y);
    pctx.globalAlpha = 1;
    var isSel = S.sel && S.sel.type === 'room' && S.sel.id === r.id;
    pctx.strokeStyle = isSel ? '#5271FF' : '#3b3b74';
    pctx.lineWidth = isSel ? 2 : 1;
    pctx.strokeRect(a.x, a.y, b.x - a.x, b.y - a.y);
  });

  /* walls */
  var t = S.proj.opts.wallT;
  allWallPieces(lv).forEach(function (p) {
    var full = p.y1 - p.y0 > (lv.height || 2.4) - 0.05;
    var a, b;
    if (p.axis === 'h') { a = w2s(p.from, p.coord - t / 2); b = w2s(p.to, p.coord + t / 2); }
    else { a = w2s(p.coord - t / 2, p.from); b = w2s(p.coord + t / 2, p.to); }
    pctx.fillStyle = full ? '#d7d7ee' : '#7c7ca8';
    pctx.fillRect(a.x, a.y, Math.max(1, b.x - a.x), Math.max(1, b.y - a.y));
  });

  /* openings */
  lv.openings.forEach(function (o) {
    var isSel = S.sel && S.sel.type === 'opening' && S.sel.id === o.id;
    var col = o.type === 'window' ? '#6ec8ff' : o.type === 'arch' ? '#9a9ac4' : '#ffd27a';
    pctx.strokeStyle = isSel ? '#fff' : col;
    pctx.lineWidth = isSel ? 4 : 3;
    pctx.beginPath();
    if (o.axis === 'h') {
      var y = w2s(0, o.coord).y;
      pctx.moveTo(w2s(o.from, 0).x, y); pctx.lineTo(w2s(o.to, 0).x, y);
    } else {
      var x = w2s(o.coord, 0).x;
      pctx.moveTo(x, w2s(0, o.from).y); pctx.lineTo(x, w2s(0, o.to).y);
    }
    pctx.stroke();
    if (o.type === 'door') {  /* swing arc, purely to read the plan */
      var r = (o.to - o.from) * S.cam.ppm;
      var pv = o.axis === 'h' ? w2s(o.from, o.coord) : w2s(o.coord, o.from);
      pctx.strokeStyle = 'rgba(255,210,122,.4)'; pctx.lineWidth = 1;
      pctx.beginPath();
      if (o.axis === 'h') pctx.arc(pv.x, pv.y, r, 0, Math.PI / 2);
      else pctx.arc(pv.x, pv.y, r, -Math.PI / 2, 0);
      pctx.stroke();
    }
  });

  /* items */
  S.proj.items.forEach(function (it) {
    if (it.level !== lv.id || !it.placed) return;
    var isSel = S.sel && S.sel.type === 'item' && S.sel.id === it.id;
    var c = w2s(it.x, it.y);
    pctx.save();
    pctx.translate(c.x, c.y);
    pctx.rotate(deg2rad(it.rot || 0));
    var w = it.w * S.cam.ppm, d = it.d * S.cam.ppm;
    var im = it.img ? cachedImage(it.img, drawPlan) : null;
    pctx.fillStyle = it.color || '#8a7fd6';
    pctx.globalAlpha = it.status === 'idea' ? 0.55 : 0.85;
    pctx.fillRect(-w / 2, -d / 2, w, d);
    pctx.globalAlpha = 1;
    if (im && w > 22 && d > 22) {
      pctx.globalAlpha = 0.9;
      var s = Math.min(w / im.width, d / im.height);
      pctx.drawImage(im, -im.width * s / 2, -im.height * s / 2, im.width * s, im.height * s);
      pctx.globalAlpha = 1;
    }
    pctx.strokeStyle = isSel ? '#fff' : 'rgba(255,255,255,.35)';
    pctx.lineWidth = isSel ? 2 : 1;
    pctx.strokeRect(-w / 2, -d / 2, w, d);
    /* a nick on the front edge so orientation is obvious */
    pctx.strokeStyle = 'rgba(255,255,255,.6)';
    pctx.beginPath(); pctx.moveTo(-Math.min(w, 12) / 2, d / 2 - 3); pctx.lineTo(Math.min(w, 12) / 2, d / 2 - 3); pctx.stroke();
    pctx.restore();
    if (S.cam.ppm > 26) {
      var top = Math.min.apply(null, itemCorners(it).map(function (p) { return w2s(p.x, p.y).y; }));
      pctx.fillStyle = '#dcdcf5';
      pctx.font = '11px ui-sans-serif,system-ui,sans-serif';
      pctx.textAlign = 'center';
      pctx.fillText(it.name, c.x, top - 4);
    }
  });

  /* room names last, so furniture never sits on top of them */
  lv.rooms.forEach(function (r) {
    var a = w2s(r.x, r.y), b = w2s(r.x + r.w, r.y + r.d);
    if (b.x - a.x < 54 || b.y - a.y < 34) return;
    pctx.textAlign = 'left';
    pctx.fillStyle = 'rgba(8,8,26,.66)';
    var text = r.name, sub = fmtLen(r.w) + ' × ' + fmtLen(r.d) + ' · ' + fmtArea(roomArea(r));
    pctx.font = '600 12px ui-sans-serif,system-ui,sans-serif';
    var tw = Math.max(pctx.measureText(text).width, 0);
    pctx.font = '11px ui-sans-serif,system-ui,sans-serif';
    tw = Math.max(tw, pctx.measureText(sub).width) + 12;
    pctx.fillRect(a.x + 5, a.y + 5, Math.min(tw, b.x - a.x - 10), 32);
    pctx.fillStyle = '#dcdcf5';
    pctx.font = '600 12px ui-sans-serif,system-ui,sans-serif';
    pctx.fillText(text, a.x + 11, a.y + 20);
    pctx.fillStyle = '#9a9ac4';
    pctx.font = '11px ui-sans-serif,system-ui,sans-serif';
    pctx.fillText(sub, a.x + 11, a.y + 33);
    pctx.textAlign = 'center';
  });

  /* handles for the current selection */
  if (S.sel && S.sel.type === 'room') {
    var r2 = findRoom(S.sel.id);
    if (r2) roomHandles(r2).forEach(function (h) { drawHandle(h.sx, h.sy); });
  }
  if (S.sel && S.sel.type === 'item') {
    var it2 = findItem(S.sel.id);
    if (it2 && it2.placed && it2.level === lv.id) itemHandles(it2).forEach(function (h) { drawHandle(h.sx, h.sy, h.k === 'rot'); });
  }
  if (S.sel && S.sel.type === 'opening') {
    var o2 = findOpening(S.sel.id);
    if (o2) openingHandles(o2).forEach(function (h) { drawHandle(h.sx, h.sy); });
  }

  /* live drag overlays */
  if (drag && drag.mode === 'newRoom') {
    var a3 = w2s(Math.min(drag.x0, drag.x1), Math.min(drag.y0, drag.y1));
    var b3 = w2s(Math.max(drag.x0, drag.x1), Math.max(drag.y0, drag.y1));
    pctx.strokeStyle = '#5271FF'; pctx.setLineDash([5, 4]); pctx.lineWidth = 2;
    pctx.strokeRect(a3.x, a3.y, b3.x - a3.x, b3.y - a3.y); pctx.setLineDash([]);
    label((a3.x + b3.x) / 2, a3.y - 8, fmtLen(Math.abs(drag.x1 - drag.x0)) + ' × ' + fmtLen(Math.abs(drag.y1 - drag.y0)));
  }
  if (drag && (drag.mode === 'measure' || drag.mode === 'calibrate')) {
    var m0 = w2s(drag.x0, drag.y0), m1 = w2s(drag.x1, drag.y1);
    pctx.strokeStyle = drag.mode === 'calibrate' ? '#C46BE4' : '#4ade80';
    pctx.lineWidth = 2; pctx.setLineDash([6, 4]);
    pctx.beginPath(); pctx.moveTo(m0.x, m0.y); pctx.lineTo(m1.x, m1.y); pctx.stroke(); pctx.setLineDash([]);
    var dist = Math.hypot(drag.x1 - drag.x0, drag.y1 - drag.y0);
    label((m0.x + m1.x) / 2, (m0.y + m1.y) / 2 - 10,
      drag.mode === 'calibrate' ? 'Drag a known length' : fmtLen(dist));
  }
  pctx.restore();

  function label(x, y, text) {
    pctx.font = '600 12px ui-sans-serif,system-ui,sans-serif';
    pctx.textAlign = 'center';
    var w = pctx.measureText(text).width + 12;
    pctx.fillStyle = 'rgba(11,11,24,.92)';
    pctx.fillRect(x - w / 2, y - 15, w, 20);
    pctx.strokeStyle = '#26264f'; pctx.lineWidth = 1;
    pctx.strokeRect(x - w / 2, y - 15, w, 20);
    pctx.fillStyle = '#ececfa';
    pctx.fillText(text, x, y);
  }
}
function drawHandle(x, y, round_) {
  pctx.fillStyle = '#fff';
  pctx.strokeStyle = '#5271FF';
  pctx.lineWidth = 2;
  pctx.beginPath();
  if (round_) pctx.arc(x, y, 5, 0, Math.PI * 2);
  else pctx.rect(x - 4, y - 4, 8, 8);
  pctx.fill(); pctx.stroke();
}
function roomHandles(r) {
  var pts = [
    { k: 'nw', x: r.x, y: r.y }, { k: 'n', x: r.x + r.w / 2, y: r.y }, { k: 'ne', x: r.x + r.w, y: r.y },
    { k: 'e', x: r.x + r.w, y: r.y + r.d / 2 }, { k: 'se', x: r.x + r.w, y: r.y + r.d },
    { k: 's', x: r.x + r.w / 2, y: r.y + r.d }, { k: 'sw', x: r.x, y: r.y + r.d }, { k: 'w', x: r.x, y: r.y + r.d / 2 }
  ];
  return pts.map(function (p) { var s = w2s(p.x, p.y); p.sx = s.x; p.sy = s.y; return p; });
}
function itemHandles(it) {
  var c = Math.cos(deg2rad(it.rot || 0)), s = Math.sin(deg2rad(it.rot || 0));
  function loc(lx, ly) {
    var p = w2s(it.x + lx * c - ly * s, it.y + lx * s + ly * c);
    return { sx: p.x, sy: p.y };
  }
  var hw = it.w / 2, hd = it.d / 2;
  var list = [
    Object.assign({ k: 'nw' }, loc(-hw, -hd)), Object.assign({ k: 'ne' }, loc(hw, -hd)),
    Object.assign({ k: 'se' }, loc(hw, hd)),   Object.assign({ k: 'sw' }, loc(-hw, hd)),
    Object.assign({ k: 'rot' }, loc(0, -hd - 26 / S.cam.ppm))
  ];
  return list;
}
function openingHandles(o) {
  var a = o.axis === 'h' ? w2s(o.from, o.coord) : w2s(o.coord, o.from);
  var b = o.axis === 'h' ? w2s(o.to, o.coord) : w2s(o.coord, o.to);
  return [{ k: 'a', sx: a.x, sy: a.y }, { k: 'b', sx: b.x, sy: b.y }];
}

/* ---------------------------------------------------- plan interaction */
var drag = null, spaceDown = false, lastMouse = { x: 0, y: 0 };

function hitTest(wx, wy, px, py) {
  var lv = level(), i;
  /* selection handles win, so you can always grab them */
  if (S.sel) {
    var hs = S.sel.type === 'room' ? (findRoom(S.sel.id) ? roomHandles(findRoom(S.sel.id)) : [])
           : S.sel.type === 'item' ? (findItem(S.sel.id) && findItem(S.sel.id).placed ? itemHandles(findItem(S.sel.id)) : [])
           : S.sel.type === 'opening' ? (findOpening(S.sel.id) ? openingHandles(findOpening(S.sel.id)) : []) : [];
    for (i = 0; i < hs.length; i++) {
      if (Math.hypot(hs[i].sx - px, hs[i].sy - py) < 9) return { type: 'handle', k: hs[i].k };
    }
  }
  for (i = S.proj.items.length - 1; i >= 0; i--) {
    var it = S.proj.items[i];
    if (it.level === lv.id && it.placed && pointInItem(wx, wy, it)) return { type: 'item', id: it.id };
  }
  for (i = lv.openings.length - 1; i >= 0; i--) {
    var o = lv.openings[i];
    var d = o.axis === 'h'
      ? Math.hypot(clamp(wx, o.from, o.to) - wx, o.coord - wy)
      : Math.hypot(o.coord - wx, clamp(wy, o.from, o.to) - wy);
    if (d < 10 / S.cam.ppm) return { type: 'opening', id: o.id };
  }
  var r = roomAt(wx, wy, lv);
  if (r) return { type: 'room', id: r.id };
  if (lv.plan && lv.plan.src && !lv.plan.locked && lv.plan.imgW) {
    var x1 = lv.plan.ox + lv.plan.imgW / lv.plan.ppm, y1 = lv.plan.oy + lv.plan.imgH / lv.plan.ppm;
    if (wx >= lv.plan.ox && wx <= x1 && wy >= lv.plan.oy && wy <= y1) return { type: 'plan' };
  }
  return null;
}

/* Nearest wall to a point — used when dropping doors and windows. */
function nearestWall(wx, wy, maxDist) {
  var best = null;
  wallSegments().forEach(function (seg) {
    var h = segHit(wx, wy, seg);
    if (h.dist < (maxDist == null ? 0.6 : maxDist) && (!best || h.dist < best.dist)) {
      best = { seg: seg, dist: h.dist, along: h.along };
    }
  });
  return best;
}

function planPointerDown(e) {
  planCanvas.setPointerCapture(e.pointerId);
  var rect = planCanvas.getBoundingClientRect();
  var px = e.clientX - rect.left, py = e.clientY - rect.top;
  var w = s2w(px, py);
  var panning = e.button === 1 || e.button === 2 || spaceDown;

  if (panning) { drag = { mode: 'pan', px: px, py: py, ox: S.cam.x, oy: S.cam.y }; return; }

  if (S.tool === 'measure') { drag = { mode: 'measure', x0: w.x, y0: w.y, x1: w.x, y1: w.y }; return; }
  if (S.tool === 'calibrate') { drag = { mode: 'calibrate', x0: w.x, y0: w.y, x1: w.x, y1: w.y }; return; }

  if (S.tool === 'room') {
    snapshot();
    drag = { mode: 'newRoom', x0: snapVal(w.x), y0: snapVal(w.y), x1: snapVal(w.x), y1: snapVal(w.y) };
    return;
  }
  if (S.tool === 'door' || S.tool === 'window') {
    var near = nearestWall(w.x, w.y);
    if (!near) { toast('Click on a wall to put a ' + S.tool + ' in it'); return; }
    snapshot();
    var isWin = S.tool === 'window';
    var width = isWin ? 1.2 : 0.9;
    var half = width / 2;
    var a = clamp(near.along - half, near.seg.from, near.seg.to - width);
    var op = {
      id: uid('op'), type: isWin ? 'window' : 'door', axis: near.seg.axis, coord: near.seg.coord,
      from: round(a, 3), to: round(a + width, 3),
      sill: isWin ? 0.9 : 0, top: isWin ? 2.1 : 2.05
    };
    level().openings.push(op);
    select({ type: 'opening', id: op.id });
    setTool('select');
    changed();
    return;
  }
  if (S.tool === 'item') {
    if (S.pendingPlace) {
      var pend = findItem(S.pendingPlace);
      if (pend) {
        snapshot();
        pend.level = level().id;
        pend.x = snapVal(w.x); pend.y = snapVal(w.y);
        pend.placed = true;
        select({ type: 'item', id: pend.id });
        S.pendingPlace = null;
        setTool('select');
        changed();
        return;
      }
      S.pendingPlace = null;
    }
    openItemModal(null, { x: snapVal(w.x), y: snapVal(w.y) });
    setTool('select');
    return;
  }

  /* select tool */
  var hit = hitTest(w.x, w.y, px, py);
  if (!hit) {
    drag = { mode: 'pan', px: px, py: py, ox: S.cam.x, oy: S.cam.y, maybeDeselect: true };
    return;
  }
  if (hit.type === 'handle') {
    snapshot();
    if (S.sel.type === 'room') {
      var r = findRoom(S.sel.id);
      drag = { mode: 'resizeRoom', k: hit.k, id: r.id, orig: { x: r.x, y: r.y, w: r.w, d: r.d } };
    } else if (S.sel.type === 'item') {
      var it = findItem(S.sel.id);
      drag = hit.k === 'rot'
        ? { mode: 'rotateItem', id: it.id, startAngle: Math.atan2(w.y - it.y, w.x - it.x), origRot: it.rot || 0 }
        : { mode: 'resizeItem', k: hit.k, id: it.id, orig: { w: it.w, d: it.d, x: it.x, y: it.y } };
    } else if (S.sel.type === 'opening') {
      drag = { mode: 'resizeOpening', k: hit.k, id: S.sel.id };
    }
    return;
  }
  if (hit.type === 'item') {
    select({ type: 'item', id: hit.id });
    snapshot();
    var i2 = findItem(hit.id);
    drag = { mode: 'moveItem', id: hit.id, dx: i2.x - w.x, dy: i2.y - w.y };
    return;
  }
  if (hit.type === 'opening') {
    select({ type: 'opening', id: hit.id });
    snapshot();
    var o2 = findOpening(hit.id);
    drag = { mode: 'moveOpening', id: hit.id, grab: (o2.axis === 'h' ? w.x : w.y) - o2.from };
    return;
  }
  if (hit.type === 'room') {
    select({ type: 'room', id: hit.id });
    snapshot();
    var r2 = findRoom(hit.id);
    drag = { mode: 'moveRoom', id: hit.id, dx: r2.x - w.x, dy: r2.y - w.y };
    return;
  }
  if (hit.type === 'plan') {
    snapshot();
    var lp = level().plan;
    drag = { mode: 'movePlan', dx: lp.ox - w.x, dy: lp.oy - w.y };
  }
}

function planPointerMove(e) {
  var rect = planCanvas.getBoundingClientRect();
  var px = e.clientX - rect.left, py = e.clientY - rect.top;
  var w = s2w(px, py);
  lastMouse = { x: px, y: py };
  if (!drag) { updateStatus(w); return; }
  drag.moved = true;

  if (drag.mode === 'pan') {
    S.cam.x = drag.ox + (px - drag.px);
    S.cam.y = drag.oy + (py - drag.py);
  } else if (drag.mode === 'newRoom') {
    drag.x1 = snapVal(w.x); drag.y1 = snapVal(w.y);
  } else if (drag.mode === 'measure' || drag.mode === 'calibrate') {
    drag.x1 = S.snap && drag.mode === 'measure' ? snapVal(w.x) : w.x;
    drag.y1 = S.snap && drag.mode === 'measure' ? snapVal(w.y) : w.y;
  } else if (drag.mode === 'moveRoom') {
    var r = findRoom(drag.id);
    if (r) {
      var nx = snapVal(w.x + drag.dx), ny = snapVal(w.y + drag.dy);
      var sn = snapRoomEdges(r, nx, ny);
      r.x = sn.x; r.y = sn.y;
    }
  } else if (drag.mode === 'resizeRoom') {
    resizeRoom(findRoom(drag.id), drag, w);
  } else if (drag.mode === 'moveItem') {
    var it = findItem(drag.id);
    if (it) { it.x = snapVal(w.x + drag.dx); it.y = snapVal(w.y + drag.dy); }
  } else if (drag.mode === 'resizeItem') {
    resizeItem(findItem(drag.id), drag, w);
  } else if (drag.mode === 'rotateItem') {
    var it2 = findItem(drag.id);
    if (it2) {
      var ang = Math.atan2(w.y - it2.y, w.x - it2.x);
      var deg = drag.origRot + (ang - drag.startAngle) * 180 / Math.PI;
      it2.rot = round(S.snap ? Math.round(deg / 15) * 15 : deg, 1);
    }
  } else if (drag.mode === 'moveOpening') {
    moveOpening(findOpening(drag.id), w, drag.grab);
  } else if (drag.mode === 'resizeOpening') {
    var o = findOpening(drag.id);
    if (o) {
      var v = snapVal(o.axis === 'h' ? w.x : w.y);
      if (drag.k === 'a') o.from = Math.min(v, o.to - 0.3); else o.to = Math.max(v, o.from + 0.3);
    }
  } else if (drag.mode === 'movePlan') {
    var lp = level().plan;
    lp.ox = round(w.x + drag.dx, 3); lp.oy = round(w.y + drag.dy, 3);
  }
  drawPlan();
  updateStatus(w);
}

function planPointerUp(e) {
  if (!drag) return;
  var d = drag; drag = null;
  if (d.mode === 'newRoom') {
    var w = Math.abs(d.x1 - d.x0), h = Math.abs(d.y1 - d.y0);
    if (w < 0.4 || h < 0.4) { S.history.pop(); updateUndoButtons(); drawPlan(); return; }
    var r = {
      id: uid('rm'), name: 'Room ' + (level().rooms.length + 1),
      x: round(Math.min(d.x0, d.x1), 3), y: round(Math.min(d.y0, d.y1), 3),
      w: round(w, 3), d: round(h, 3), floor: '#1e2748'
    };
    level().rooms.push(r);
    select({ type: 'room', id: r.id });
    setTool('select');
    changed();
    return;
  }
  if (d.mode === 'calibrate') {
    var dist = Math.hypot(d.x1 - d.x0, d.y1 - d.y0);
    if (dist < 0.05) { drawPlan(); return; }
    askCalibration(d, dist);
    return;
  }
  if (d.mode === 'measure') { drawPlan(); return; }
  if (d.mode === 'pan' && d.maybeDeselect && !d.moved) { select(null); }
  if (['moveRoom', 'resizeRoom', 'moveItem', 'resizeItem', 'rotateItem', 'moveOpening', 'resizeOpening', 'movePlan'].indexOf(d.mode) >= 0) {
    if (d.moved) changed(); else { S.history.pop(); updateUndoButtons(); }
  }
  drawPlan();
}

/* Rooms snap to each other's edges so walls line up without fiddling. */
function snapRoomEdges(room, nx, ny) {
  if (!S.snap) return { x: nx, y: ny };
  var tol = 0.16, lv = level();
  var xs = [], ys = [];
  lv.rooms.forEach(function (o) {
    if (o.id === room.id) return;
    xs.push(o.x, o.x + o.w); ys.push(o.y, o.y + o.d);
  });
  var cands = [nx, nx + room.w];
  xs.forEach(function (v) {
    cands.forEach(function (c, i) {
      if (Math.abs(c - v) < tol) nx = i === 0 ? v : v - room.w;
    });
  });
  var candsY = [ny, ny + room.d];
  ys.forEach(function (v) {
    candsY.forEach(function (c, i) {
      if (Math.abs(c - v) < tol) ny = i === 0 ? v : v - room.d;
    });
  });
  return { x: round(nx, 3), y: round(ny, 3) };
}
function resizeRoom(r, d, w) {
  if (!r) return;
  var o = d.orig, minS = 0.5;
  var x0 = o.x, y0 = o.y, x1 = o.x + o.w, y1 = o.y + o.d;
  var k = d.k;
  if (k.indexOf('w') >= 0) x0 = Math.min(snapVal(w.x), x1 - minS);
  if (k.indexOf('e') >= 0) x1 = Math.max(snapVal(w.x), x0 + minS);
  if (k.indexOf('n') >= 0) y0 = Math.min(snapVal(w.y), y1 - minS);
  if (k.indexOf('s') >= 0) y1 = Math.max(snapVal(w.y), y0 + minS);
  r.x = round(x0, 3); r.y = round(y0, 3); r.w = round(x1 - x0, 3); r.d = round(y1 - y0, 3);
}
function resizeItem(it, d, w) {
  if (!it) return;
  var c = Math.cos(-deg2rad(it.rot || 0)), s = Math.sin(-deg2rad(it.rot || 0));
  var dx = w.x - d.orig.x, dy = w.y - d.orig.y;
  var lx = Math.abs(dx * c - dy * s) * 2, ly = Math.abs(dx * s + dy * c) * 2;
  it.w = round(Math.max(0.1, S.snap ? Math.round(lx / 0.05) * 0.05 : lx), 3);
  it.d = round(Math.max(0.1, S.snap ? Math.round(ly / 0.05) * 0.05 : ly), 3);
}
function moveOpening(o, w, grab) {
  if (!o) return;
  var width = o.to - o.from;
  var segs = wallSegments().filter(function (s) { return s.axis === o.axis && Math.abs(s.coord - o.coord) < 0.06; });
  var lo = -Infinity, hi = Infinity;
  if (segs.length) {
    lo = Math.min.apply(null, segs.map(function (s) { return s.from; }));
    hi = Math.max.apply(null, segs.map(function (s) { return s.to; }));
  }
  var start = snapVal((o.axis === 'h' ? w.x : w.y) - grab);
  start = clamp(start, lo, hi - width);
  o.from = round(start, 3); o.to = round(start + width, 3);
}

function updateStatus(w) {
  var bits = [];
  if (w) bits.push('x ' + fmtLen(w.x) + '  y ' + fmtLen(w.y));
  var lv = level();
  var area = lv.rooms.reduce(function (a, r) { return a + roomArea(r); }, 0);
  bits.push(lv.rooms.length + ' room' + (lv.rooms.length === 1 ? '' : 's'));
  if (area) bits.push(fmtArea(area));
  if (S.pendingPlace) {
    var p = findItem(S.pendingPlace);
    if (p) bits.push('Click to place “' + p.name + '”');
  }
  $('#statusbar').textContent = bits.join('   ·   ');
}

planCanvas.addEventListener('pointerdown', planPointerDown);
planCanvas.addEventListener('pointermove', planPointerMove);
planCanvas.addEventListener('pointerup', planPointerUp);
planCanvas.addEventListener('pointercancel', planPointerUp);
planCanvas.addEventListener('contextmenu', function (e) { e.preventDefault(); });
planCanvas.addEventListener('wheel', function (e) {
  e.preventDefault();
  var rect = planCanvas.getBoundingClientRect();
  var px = e.clientX - rect.left, py = e.clientY - rect.top;
  var before = s2w(px, py);
  var factor = Math.pow(0.999, e.deltaY);
  S.cam.ppm = clamp(S.cam.ppm * factor, 5, 500);
  S.cam.x = px - before.x * S.cam.ppm;
  S.cam.y = py - before.y * S.cam.ppm;
  drawPlan();
}, { passive: false });

/* ========================================================================
   3D — dollhouse orbit + first-person walkthrough (three.js)
   ====================================================================== */
var G = { ready: false, renderer: null, scene: null, camera: null, root: null, raf: 0,
          orbit: { target: new THREE.Vector3(), dist: 14, az: -0.9, pol: 0.95 },
          walk: { x: 2, z: 2, yaw: 0, pitch: 0, eye: 1.65, vel: { x: 0, z: 0 }, locked: false },
          keys: {}, mode: 'doll', clock: null, lookItem: null, texCache: {} };

function init3D() {
  if (G.ready) return true;
  if (!window.THREE) { toast('3D library could not load — check your connection', 'bad'); return false; }
  var canvas = $('#glCanvas');
  G.renderer = new THREE.WebGLRenderer({ canvas: canvas, antialias: true });
  G.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  G.renderer.shadowMap.enabled = true;
  G.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  G.scene = new THREE.Scene();
  G.scene.background = new THREE.Color(0x0a0a1c);
  G.scene.fog = new THREE.Fog(0x0a0a1c, 40, 120);
  G.camera = new THREE.PerspectiveCamera(62, 1, 0.05, 400);
  G.root = new THREE.Group();
  G.scene.add(G.root);

  var hemi = new THREE.HemisphereLight(0xdfe8ff, 0x3c3c58, 0.45);
  G.scene.add(hemi);
  var amb = new THREE.AmbientLight(0xe6ebff, 0.22);
  G.scene.add(amb);
  G.amb = amb;
  /* a soft lamp that follows you around indoors, so rooms are not pitch dark */
  var torch = new THREE.PointLight(0xfff2dd, 0.38, 8, 2);
  torch.visible = false;
  G.scene.add(torch);
  G.torch = torch;
  var sun = new THREE.DirectionalLight(0xfff4e0, 0.6);
  sun.position.set(12, 22, 8);
  sun.castShadow = true;
  sun.shadow.mapSize.width = sun.shadow.mapSize.height = 2048;
  var sc = sun.shadow.camera;
  sc.left = -25; sc.right = 25; sc.top = 25; sc.bottom = -25; sc.near = 1; sc.far = 90;
  G.scene.add(sun);
  G.sun = sun; G.hemi = hemi;

  var ground = new THREE.Mesh(
    new THREE.PlaneGeometry(300, 300),
    new THREE.MeshLambertMaterial({ color: 0x141430 })
  );
  ground.rotation.x = -Math.PI / 2;
  ground.position.y = -0.06;
  ground.receiveShadow = true;
  G.scene.add(ground);

  G.clock = new THREE.Clock();
  G.ready = true;
  bindOrbit(canvas);
  bindWalk(canvas);
  resize3D();
  return true;
}

function resize3D() {
  if (!G.ready) return;
  var el = $('#glCanvas');
  var w = el.clientWidth || 1, h = el.clientHeight || 1;
  G.renderer.setSize(w, h, false);
  G.camera.aspect = w / h;
  G.camera.updateProjectionMatrix();
}

function tex(src) {
  if (!src) return null;
  if (G.texCache[src]) return G.texCache[src];
  var t = new THREE.TextureLoader().load(src, function () { });
  t.anisotropy = 4;
  G.texCache[src] = t;
  return t;
}
function lam(color, opts) {
  return new THREE.MeshLambertMaterial(Object.assign({ color: new THREE.Color(color) }, opts || {}));
}
function boxMesh(w, h, d, mat, x, y, z) {
  var m = new THREE.Mesh(new THREE.BoxGeometry(Math.max(w, 0.001), Math.max(h, 0.001), Math.max(d, 0.001)), mat);
  m.position.set(x, y, z);
  m.castShadow = true; m.receiveShadow = true;
  return m;
}

/* Rebuilds the whole level. Cheap enough for a house; called on every edit. */
function build3D() {
  if (!G.ready) return;
  while (G.root.children.length) {
    var c = G.root.children.pop();
    c.traverse(function (o) {
      if (o.geometry) o.geometry.dispose();
      if (o.material) {
        (Array.isArray(o.material) ? o.material : [o.material]).forEach(function (m) { m.dispose(); });
      }
    });
  }
  var lv = level(), base = lv.base || 0, H = lv.height || S.proj.opts.wallH, t = S.proj.opts.wallT;
  var shadows = !!S.proj.opts.shadows;
  G.renderer.shadowMap.enabled = shadows;
  G.sun.castShadow = shadows;
  var lightMul = (S.proj.opts.light == null ? 100 : S.proj.opts.light) / 100;
  G.sun.intensity = 0.6 * lightMul;
  G.hemi.intensity = 0.45 * lightMul;
  G.amb.intensity = 0.22 * lightMul;

  /* floors + ceilings */
  lv.rooms.forEach(function (r) {
    var floor = boxMesh(r.w + t, 0.08, r.d + t, lam(r.floor || '#28304f'),
      r.x + r.w / 2, base - 0.04, r.y + r.d / 2);
    floor.castShadow = false;
    G.root.add(floor);
    if (S.proj.opts.ceilings || G.mode === 'walk') {
      var ceilMat = lam('#e2e2f0');
      var ceil = boxMesh(r.w + t, 0.06, r.d + t, ceilMat, r.x + r.w / 2, base + H + 0.03, r.y + r.d / 2);
      ceil.castShadow = false;
      G.root.add(ceil);
    }
  });

  /* walls */
  var wallMat = lam('#d9d9e8');
  allWallPieces(lv).forEach(function (p) {
    var len = p.to - p.from, hh = p.y1 - p.y0;
    var mid = (p.from + p.to) / 2, y = base + (p.y0 + p.y1) / 2;
    G.root.add(p.axis === 'h'
      ? boxMesh(len, hh, t, wallMat, mid, y, p.coord)
      : boxMesh(t, hh, len, wallMat, p.coord, y, mid));
  });

  /* window glass + door frames */
  var glass = new THREE.MeshLambertMaterial({ color: 0x9fd8ff, transparent: true, opacity: 0.28 });
  var frameMat = lam('#cfcfe4');
  lv.openings.forEach(function (o) {
    var len = o.to - o.from, hh = Math.max(0.05, o.top - o.sill), mid = (o.from + o.to) / 2;
    var y = base + o.sill + hh / 2;
    if (o.type === 'window') {
      var g = o.axis === 'h' ? boxMesh(len, hh, 0.02, glass, mid, y, o.coord) : boxMesh(0.02, hh, len, glass, o.coord, y, mid);
      g.castShadow = false;
      G.root.add(g);
    }
    /* thin reveal so openings read as openings from a distance */
    var fw = 0.04;
    if (o.axis === 'h') {
      G.root.add(boxMesh(len, fw, t * 1.02, frameMat, mid, base + o.top, o.coord));
      if (o.sill > 0.05) G.root.add(boxMesh(len, fw, t * 1.3, frameMat, mid, base + o.sill, o.coord));
    } else {
      G.root.add(boxMesh(t * 1.02, fw, len, frameMat, o.coord, base + o.top, mid));
      if (o.sill > 0.05) G.root.add(boxMesh(t * 1.3, fw, len, frameMat, o.coord, base + o.sill, mid));
    }
  });

  /* items */
  S.proj.items.forEach(function (it) {
    if (it.level !== lv.id || !it.placed) return;
    var grp = buildItem(it);
    grp.position.set(it.x, base + (it.mount || 0), it.y);
    grp.rotation.y = -deg2rad(it.rot || 0);
    grp.userData.itemId = it.id;
    G.root.add(grp);
  });

  G.collide = collisionRects(lv);
  highlightSelection();
}

/* Each item is a little kit of boxes sized to its real dimensions. */
function buildItem(it) {
  var g = new THREE.Group();
  var col = it.color || '#8a7fd6';
  var body = lam(col);
  var dark = lam(new THREE.Color(col).multiplyScalar(0.65).getStyle());
  var img = it.img ? tex(it.img) : null;
  var w = it.w, d = it.d, h = it.h;

  function faceMats(frontTex) {
    var side = lam(col);
    var front = frontTex ? new THREE.MeshLambertMaterial({ map: frontTex, color: 0xffffff }) : lam(col);
    return [side, side, lam(new THREE.Color(col).multiplyScalar(1.08).getStyle()), side, front, side];
  }

  switch (it.shape) {
    case 'sofa': {
      var seatH = h * 0.45, armW = Math.min(0.18, w * 0.12);
      g.add(boxMesh(w, seatH, d, body, 0, seatH / 2, 0));
      g.add(boxMesh(w, h - seatH, d * 0.28, dark, 0, seatH + (h - seatH) / 2, -d / 2 + d * 0.14));
      g.add(boxMesh(armW, h * 0.72, d, dark, -w / 2 + armW / 2, h * 0.36, 0));
      g.add(boxMesh(armW, h * 0.72, d, dark, w / 2 - armW / 2, h * 0.36, 0));
      break;
    }
    case 'chair': {
      var sh = h * 0.5, legT = 0.05;
      g.add(boxMesh(w, 0.07, d, body, 0, sh, 0));
      g.add(boxMesh(w, h - sh, 0.06, dark, 0, sh + (h - sh) / 2, -d / 2 + 0.05));
      [[-1, -1], [1, -1], [-1, 1], [1, 1]].forEach(function (s) {
        g.add(boxMesh(legT, sh, legT, dark, s[0] * (w / 2 - legT), sh / 2, s[1] * (d / 2 - legT)));
      });
      break;
    }
    case 'table': {
      var legT2 = 0.06;
      g.add(boxMesh(w, 0.06, d, body, 0, h - 0.03, 0));
      [[-1, -1], [1, -1], [-1, 1], [1, 1]].forEach(function (s) {
        g.add(boxMesh(legT2, h - 0.06, legT2, dark, s[0] * (w / 2 - legT2), (h - 0.06) / 2, s[1] * (d / 2 - legT2)));
      });
      break;
    }
    case 'bed': {
      var baseH = h * 0.45;
      g.add(boxMesh(w, baseH, d, dark, 0, baseH / 2, 0));
      g.add(boxMesh(w * 0.98, h - baseH, d * 0.94, lam('#e8e8f5'), 0, baseH + (h - baseH) / 2, d * 0.02));
      g.add(boxMesh(w * 0.42, 0.12, d * 0.16, lam('#ffffff'), -w * 0.24, h + 0.05, -d / 2 + d * 0.12));
      g.add(boxMesh(w * 0.42, 0.12, d * 0.16, lam('#ffffff'), w * 0.24, h + 0.05, -d / 2 + d * 0.12));
      g.add(boxMesh(w, h * 1.1, 0.07, body, 0, h * 0.55, -d / 2 - 0.03));
      break;
    }
    case 'wardrobe':
    case 'shelf': {
      g.add(boxMesh(w, h, d, new THREE.MeshLambertMaterial({ color: new THREE.Color(col) }), 0, h / 2, 0));
      var shelves = Math.max(2, Math.round(h / 0.4));
      for (var i = 1; i < shelves; i++) {
        g.add(boxMesh(w * 0.98, 0.02, 0.01, dark, 0, h * i / shelves, d / 2 + 0.005));
      }
      if (img) g.add(imagePanel(w * 0.9, h * 0.9, img, 0, h / 2, d / 2 + 0.01));
      break;
    }
    case 'rug': {
      var rug = boxMesh(w, 0.02, d, img ? new THREE.MeshLambertMaterial({ map: img, color: 0xffffff }) : body, 0, 0.01, 0);
      rug.castShadow = false;
      g.add(rug);
      break;
    }
    case 'tv': {
      g.add(boxMesh(w, h, Math.max(d, 0.05), lam('#15151f'), 0, h / 2, 0));
      g.add(imagePanel(w * 0.96, h * 0.92, img || null, 0, h / 2, Math.max(d, 0.05) / 2 + 0.005, '#0a0a12'));
      break;
    }
    case 'art': {
      g.add(boxMesh(w, h, Math.max(d, 0.03), lam('#2b2b3f'), 0, h / 2, 0));
      g.add(imagePanel(w * 0.9, h * 0.9, img || null, 0, h / 2, Math.max(d, 0.03) / 2 + 0.004, '#e6e6f2'));
      break;
    }
    case 'lamp': {
      var poleH = h * 0.72, shadeH = h - poleH;
      var lampBase = new THREE.Mesh(new THREE.CylinderGeometry(w * 0.35, w * 0.4, 0.04, 16), dark);
      lampBase.position.set(0, 0.02, 0);
      g.add(lampBase);
      var pole = new THREE.Mesh(new THREE.CylinderGeometry(0.02, 0.02, poleH, 8), dark);
      pole.position.set(0, poleH / 2, 0); g.add(pole);
      var shade = new THREE.Mesh(new THREE.CylinderGeometry(w * 0.42, w * 0.5, shadeH, 18),
        new THREE.MeshLambertMaterial({ color: 0xfff0cf, emissive: 0x554320 }));
      shade.position.set(0, poleH + shadeH / 2, 0);
      g.add(shade);
      break;
    }
    case 'plant': {
      var potH = h * 0.28;
      var pot = new THREE.Mesh(new THREE.CylinderGeometry(w * 0.3, w * 0.22, potH, 16), lam('#a86b4c'));
      pot.position.set(0, potH / 2, 0); g.add(pot);
      var leaf = new THREE.Mesh(new THREE.SphereGeometry(Math.min(w, d) * 0.5, 12, 10), lam('#3f8b52'));
      leaf.position.set(0, potH + (h - potH) * 0.55, 0);
      leaf.scale.set(1, (h - potH) / (Math.min(w, d)) * 0.9, 1);
      leaf.castShadow = true;
      g.add(leaf);
      break;
    }
    case 'appliance': {
      g.add(boxMesh(w, h, d, lam('#cfd4dd'), 0, h / 2, 0));
      g.add(boxMesh(w * 0.9, h * 0.55, 0.02, lam('#1b1b26'), 0, h * 0.62, d / 2 + 0.012));
      break;
    }
    default: {
      var mesh = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), faceMats(img));
      mesh.position.set(0, h / 2, 0);
      mesh.castShadow = true; mesh.receiveShadow = true;
      g.add(mesh);
    }
  }
  g.traverse(function (o) { if (o.isMesh) { o.castShadow = o.castShadow !== false; o.receiveShadow = true; } });
  return g;
}
function imagePanel(w, h, texture, x, y, z, fallback) {
  var mat = texture
    ? new THREE.MeshLambertMaterial({ map: texture, color: 0xffffff })
    : lam(fallback || '#5a5a7a');
  var m = new THREE.Mesh(new THREE.PlaneGeometry(w, h), mat);
  m.position.set(x, y, z);
  return m;
}

function highlightSelection() {
  if (!G.ready) return;
  G.root.children.forEach(function (c) {
    var on = S.sel && S.sel.type === 'item' && c.userData.itemId === S.sel.id;
    c.traverse(function (o) {
      if (o.isMesh && o.material && o.material.emissive) {
        if (o.material.userData.baseEmissive == null) o.material.userData.baseEmissive = o.material.emissive.getHex();
        o.material.emissive.setHex(on ? 0x2a3580 : o.material.userData.baseEmissive);
      }
    });
  });
}

/* ------------------------------------------------------------ cameras */
function bindOrbit(canvas) {
  var down = null;
  canvas.addEventListener('pointerdown', function (e) {
    if (G.mode !== 'doll') return;
    canvas.setPointerCapture(e.pointerId);
    down = { x: e.clientX, y: e.clientY, btn: e.button, az: G.orbit.az, pol: G.orbit.pol,
             tx: G.orbit.target.x, tz: G.orbit.target.z, moved: false };
  });
  canvas.addEventListener('pointermove', function (e) {
    if (G.mode !== 'doll') return;
    if (!down) { hoverPick(e); return; }
    var dx = e.clientX - down.x, dy = e.clientY - down.y;
    if (Math.abs(dx) + Math.abs(dy) > 3) down.moved = true;
    if (down.btn === 0 && !e.shiftKey) {
      G.orbit.az = down.az - dx * 0.006;
      G.orbit.pol = clamp(down.pol - dy * 0.006, 0.08, Math.PI / 2 - 0.02);
    } else {
      var s = G.orbit.dist * 0.0016;
      var ca = Math.cos(G.orbit.az), sa = Math.sin(G.orbit.az);
      G.orbit.target.x = down.tx - (dx * ca - dy * sa) * s;
      G.orbit.target.z = down.tz - (dx * sa + dy * ca) * s;
    }
  });
  canvas.addEventListener('pointerup', function (e) {
    if (G.mode !== 'doll') return;
    if (down && !down.moved && e.button === 0) pickAt(e);
    down = null;
  });
  canvas.addEventListener('contextmenu', function (e) { e.preventDefault(); });
  canvas.addEventListener('wheel', function (e) {
    if (G.mode !== 'doll') return;
    e.preventDefault();
    G.orbit.dist = clamp(G.orbit.dist * Math.pow(1.0012, e.deltaY), 1.5, 90);
  }, { passive: false });
}

function bindWalk(canvas) {
  canvas.addEventListener('click', function () {
    if (G.mode !== 'walk') return;
    if (!G.walk.locked && canvas.requestPointerLock) canvas.requestPointerLock();
  });
  document.addEventListener('pointerlockchange', function () {
    G.walk.locked = document.pointerLockElement === canvas;
    $('#walkHint').classList.toggle('hidden', G.walk.locked || G.mode !== 'walk');
    $('#crosshair').classList.toggle('hidden', !G.walk.locked);
  });
  document.addEventListener('mousemove', function (e) {
    if (!G.walk.locked) return;
    G.walk.yaw -= e.movementX * 0.0022;
    G.walk.pitch = clamp(G.walk.pitch - e.movementY * 0.0022, -1.4, 1.4);
  });
}

document.addEventListener('keydown', function (e) {
  var typing = /INPUT|TEXTAREA|SELECT/.test((e.target && e.target.tagName) || '');
  G.keys[e.code] = true;
  if (e.code === 'Space' && !typing && S.view === 'plan') { spaceDown = true; e.preventDefault(); }
  if (typing) return;
  var meta = e.ctrlKey || e.metaKey;
  if (meta && e.key.toLowerCase() === 'z') { e.preventDefault(); e.shiftKey ? redo() : undo(); return; }
  if (meta && e.key.toLowerCase() === 'y') { e.preventDefault(); redo(); return; }
  if (G.mode === 'walk' && G.walk.locked && e.code === 'KeyE') { openLookedAt(); return; }
  if (S.view !== 'plan') return;
  var map = { KeyV: 'select', KeyR: 'room', KeyD: 'door', KeyW: 'window', KeyI: 'item', KeyM: 'measure' };
  if (map[e.code]) { setTool(map[e.code]); return; }
  if (e.code === 'KeyF') { fitToPlan(); return; }
  if ((e.code === 'Delete' || e.code === 'Backspace') && S.sel) { e.preventDefault(); deleteSelection(); }
  if (e.code === 'Escape') select(null);
  /* nudge with the arrow keys */
  if (S.sel && /^Arrow/.test(e.code)) {
    var step = e.shiftKey ? (S.grid || 0.1) * 4 : (S.grid || 0.05);
    var dx = e.code === 'ArrowLeft' ? -step : e.code === 'ArrowRight' ? step : 0;
    var dy = e.code === 'ArrowUp' ? -step : e.code === 'ArrowDown' ? step : 0;
    if (dx || dy) {
      e.preventDefault();
      snapshot();
      if (S.sel.type === 'item') { var it = findItem(S.sel.id); if (it) { it.x = round(it.x + dx, 3); it.y = round(it.y + dy, 3); } }
      else if (S.sel.type === 'room') { var r = findRoom(S.sel.id); if (r) { r.x = round(r.x + dx, 3); r.y = round(r.y + dy, 3); } }
      else if (S.sel.type === 'opening') {
        var o = findOpening(S.sel.id); var dv = o && o.axis === 'h' ? dx : dy;
        if (o && dv) { o.from = round(o.from + dv, 3); o.to = round(o.to + dv, 3); }
      }
      changed();
    }
  }
});
document.addEventListener('keyup', function (e) {
  G.keys[e.code] = false;
  if (e.code === 'Space') spaceDown = false;
});

/* --------------------------------------------------------- render loop */
var ray = window.THREE ? new THREE.Raycaster() : null;
function loop() {
  G.raf = requestAnimationFrame(loop);
  if (!G.ready || S.view === 'plan') return;
  var dt = Math.min(G.clock.getDelta(), 0.1);

  if (G.mode === 'walk') {
    stepWalk(dt);
    G.camera.position.set(G.walk.x, (level().base || 0) + G.walk.eye, G.walk.z);
    G.camera.rotation.set(0, 0, 0, 'YXZ');
    G.camera.rotation.order = 'YXZ';
    G.camera.rotation.y = G.walk.yaw;
    G.camera.rotation.x = G.walk.pitch;
    G.torch.visible = true;
    G.torch.position.set(G.walk.x, (level().base || 0) + G.walk.eye + 0.25, G.walk.z);
    updateLookedAt();
  } else {
    G.torch.visible = false;
    var o = G.orbit;
    var y = (level().base || 0) + o.dist * Math.sin(o.pol);
    G.camera.position.set(
      o.target.x + o.dist * Math.cos(o.pol) * Math.cos(o.az),
      y,
      o.target.z + o.dist * Math.cos(o.pol) * Math.sin(o.az)
    );
    G.camera.lookAt(o.target.x, (level().base || 0) + 1, o.target.z);
  }
  G.renderer.render(G.scene, G.camera);
}

function stepWalk(dt) {
  var w = G.walk, speed = (G.keys.ShiftLeft || G.keys.ShiftRight) ? 3.4 : 1.6;
  var fx = 0, fz = 0;
  if (G.keys.KeyW || G.keys.ArrowUp) fz -= 1;
  if (G.keys.KeyS || G.keys.ArrowDown) fz += 1;
  if (G.keys.KeyA || G.keys.ArrowLeft) fx -= 1;
  if (G.keys.KeyD || G.keys.ArrowRight) fx += 1;
  var len = Math.hypot(fx, fz);
  var vx = 0, vz = 0;
  if (len) {
    fx /= len; fz /= len;
    var sinY = Math.sin(w.yaw), cosY = Math.cos(w.yaw);
    vx = (fx * cosY + fz * sinY) * speed;
    vz = (-fx * sinY + fz * cosY) * speed;
  }
  /* smooth start/stop so it doesn't feel like a spreadsheet */
  w.vel.x += (vx - w.vel.x) * Math.min(1, dt * 12);
  w.vel.z += (vz - w.vel.z) * Math.min(1, dt * 12);

  var nx = w.x + w.vel.x * dt, nz = w.z + w.vel.z * dt;
  if (S.proj.opts.clip) {
    var rects = G.collide || [];
    if (!blocked(nx, w.z, rects)) w.x = nx; else w.vel.x = 0;
    if (!blocked(w.x, nz, rects)) w.z = nz; else w.vel.z = 0;
  } else { w.x = nx; w.z = nz; }

  var targetEye = G.keys.KeyQ ? 1.05 : 1.65;
  w.eye += (targetEye - w.eye) * Math.min(1, dt * 8);
}
function blocked(x, z, rects) {
  var r = 0.26;
  for (var i = 0; i < rects.length; i++) {
    var b = rects[i];
    if (x > b.x0 - r && x < b.x1 + r && z > b.y0 - r && z < b.y1 + r) return true;
  }
  return false;
}

/* ------------------------------------------------------- 3D picking */
function screenRay(e) {
  var el = $('#glCanvas'), rect = el.getBoundingClientRect();
  var v = new THREE.Vector2(
    ((e.clientX - rect.left) / rect.width) * 2 - 1,
    -((e.clientY - rect.top) / rect.height) * 2 + 1
  );
  ray.setFromCamera(v, G.camera);
  return ray.intersectObjects(G.root.children, true);
}
function itemIdOf(obj) {
  while (obj) { if (obj.userData && obj.userData.itemId) return obj.userData.itemId; obj = obj.parent; }
  return null;
}
function pickAt(e) {
  if (!ray) return;
  var hits = screenRay(e);
  for (var i = 0; i < hits.length; i++) {
    var id = itemIdOf(hits[i].object);
    if (id) { select({ type: 'item', id: id }); return; }
  }
  select(null);
}
function hoverPick(e) {
  if (!ray) return;
  var hits = screenRay(e), id = null;
  for (var i = 0; i < hits.length && !id; i++) id = itemIdOf(hits[i].object);
  var tip = $('#hoverTip');
  if (!id) { tip.classList.add('hidden'); return; }
  var it = findItem(id);
  if (!it) { tip.classList.add('hidden'); return; }
  var rect = $('#stage').getBoundingClientRect();
  tip.innerHTML = '<div class="t">' + esc(it.name) + '</div><div class="s">' +
    esc(fmtLen(it.w) + ' × ' + fmtLen(it.d) + ' × ' + fmtLen(it.h)) +
    (it.price ? ' · ' + esc(money(it.price)) : '') + '</div>';
  tip.style.left = (e.clientX - rect.left + 14) + 'px';
  tip.style.top = (e.clientY - rect.top + 14) + 'px';
  tip.classList.remove('hidden');
}
function updateLookedAt() {
  if (!ray) return;
  ray.setFromCamera(new THREE.Vector2(0, 0), G.camera);
  var hits = ray.intersectObjects(G.root.children, true), id = null;
  for (var i = 0; i < hits.length; i++) {
    /* whatever is nearest wins — you cannot read a price tag through a wall */
    var m = hits[i].object.material;
    if (m && m.transparent) continue;
    if (hits[i].distance <= 4) id = itemIdOf(hits[i].object);
    break;
  }
  G.lookItem = id;
  var tip = $('#hoverTip');
  if (id && G.walk.locked) {
    var it = findItem(id);
    tip.innerHTML = '<div class="t">' + esc(it.name) + '</div><div class="s">' +
      (it.price ? esc(money(it.price)) + ' · ' : '') + (it.url ? 'press E for the link' : 'no link saved') + '</div>';
    tip.style.left = '50%'; tip.style.top = 'calc(50% + 26px)';
    tip.classList.remove('hidden');
  } else if (G.mode === 'walk') {
    tip.classList.add('hidden');
  }
  /* which room am I standing in? */
  var lbl = $('#roomLabel');
  var r = roomAt(G.walk.x, G.walk.z);
  if (r && G.walk.locked) { lbl.textContent = r.name; lbl.classList.remove('hidden'); }
  else lbl.classList.add('hidden');
  showRoomPhoto(r && G.walk.locked ? r.id : null);
}
function openLookedAt() {
  var it = G.lookItem && findItem(G.lookItem);
  if (!it) return;
  if (it.url) window.open(it.url, '_blank', 'noopener');
  else toast('No shop link saved for ' + it.name);
}

/* ========================================================================
   UI
   ====================================================================== */
function changed(skip3D) {
  touch();
  if (S.view === 'plan') { S.needs3D = true; drawPlan(); }
  else if (!skip3D) { build3D(); G.collide = collisionRects(); }
  renderSidebar();
  renderInspector();
  updateStatus();
}
function select(sel) {
  S.sel = sel;
  renderSidebar();
  renderInspector();
  drawPlan();
  highlightSelection();
}
function setTool(t) {
  S.tool = t;
  if (t !== 'item') S.pendingPlace = null;
  $$('#toolbar button[data-tool]').forEach(function (b) { b.classList.toggle('on', b.dataset.tool === t); });
  planCanvas.style.cursor = t === 'select' ? 'default' : 'crosshair';
  updateStatus();
}
function setView(v) {
  S.view = v;
  $$('#viewSwitch button').forEach(function (b) { b.classList.toggle('on', b.dataset.view === v); });
  var is3D = v !== 'plan';
  $('#planWrap').classList.toggle('hidden', is3D);
  $('#viewWrap').classList.toggle('hidden', !is3D);
  $('#toolbar').classList.toggle('hidden', is3D);
  $('#planBar').classList.toggle('hidden', is3D);
  $('#viewBar').classList.toggle('hidden', !is3D);
  $('#walkHint').classList.toggle('hidden', v !== 'walk');
  $('#crosshair').classList.add('hidden');
  $('#hoverTip').classList.add('hidden');
  $('#roomLabel').classList.add('hidden');
  if (is3D) {
    if (!init3D()) { setView('plan'); return; }
    var wasMode = G.mode;
    G.mode = v === 'walk' ? 'walk' : 'doll';
    resize3D();
    if (S.needs3D || !G.root.children.length || wasMode !== G.mode) { build3D(); S.needs3D = false; }
    G.collide = collisionRects();
    if (v === 'doll') {
      if (document.pointerLockElement) document.exitPointerLock();
      var b = bounds();
      G.orbit.target.set((b.x0 + b.x1) / 2, 0, (b.y0 + b.y1) / 2);
      G.orbit.dist = clamp(Math.max(b.x1 - b.x0, b.y1 - b.y0) * 1.5, 4, 60);
    } else {
      ensureWalkStart();
    }
  } else {
    if (document.pointerLockElement) document.exitPointerLock();
    resizePlanCanvas();
  }
  updateStatus();
}
function ensureWalkStart() {
  var lv = level();
  if (!lv.rooms.length) return;
  var inside = roomAt(G.walk.x, G.walk.z, lv);
  if (!inside) {
    var r = lv.rooms[0];
    G.walk.x = r.x + r.w / 2;
    G.walk.z = r.y + r.d / 2;
  }
}

/* ------------------------------------------------------------- sidebar */
function renderSidebar() {
  var lv = level();

  /* levels */
  $('#levelList').innerHTML = S.proj.levels.map(function (l, i) {
    var n = l.rooms.length;
    return '<div class="card' + (i === S.level ? ' sel' : '') + '" data-level="' + i + '">' +
      '<div class="thumb">' + (i === S.level ? '📍' : '▫️') + '</div>' +
      '<div class="body"><div class="title">' + esc(l.name) + '</div>' +
      '<div class="sub">' + n + ' room' + (n === 1 ? '' : 's') + ' · ' + fmtLen(l.height) + ' high</div></div>' +
      '<div class="end">✎</div></div>';
  }).join('');

  /* rooms */
  $('#roomList').innerHTML = lv.rooms.length ? lv.rooms.map(function (r) {
    var sel = S.sel && S.sel.type === 'room' && S.sel.id === r.id;
    return '<div class="card' + (sel ? ' sel' : '') + '" data-room="' + r.id + '">' +
      '<div class="thumb" style="background:' + esc(r.floor || '#1e2748') + '"></div>' +
      '<div class="body"><div class="title">' + esc(r.name) + '</div>' +
      '<div class="sub">' + fmtLen(r.w) + ' × ' + fmtLen(r.d) + '</div></div>' +
      '<div class="end">' + fmtArea(roomArea(r)) + '</div></div>';
  }).join('') : '<div class="empty">No rooms yet. Pick the ▭ tool and drag one out, or load the sample house from Setup.</div>';

  /* openings */
  $('#openingList').innerHTML = lv.openings.length ? lv.openings.map(function (o) {
    var sel = S.sel && S.sel.type === 'opening' && S.sel.id === o.id;
    var icon = o.type === 'window' ? '🪟' : o.type === 'arch' ? '⌒' : '🚪';
    return '<div class="card' + (sel ? ' sel' : '') + '" data-opening="' + o.id + '">' +
      '<div class="thumb">' + icon + '</div>' +
      '<div class="body"><div class="title">' + esc(o.type[0].toUpperCase() + o.type.slice(1)) + '</div>' +
      '<div class="sub">' + fmtLen(o.to - o.from) + ' wide</div></div></div>';
  }).join('') : '<div class="empty">No doors or windows yet.</div>';

  /* items */
  var filter = $('#itemFilter').value;
  var items = S.proj.items.filter(function (it) {
    if (filter === 'level') return it.level === lv.id;
    if (filter === 'unplaced') return !it.placed;
    return true;
  });
  $('#itemList').innerHTML = items.length ? items.map(function (it) {
    var sel = S.sel && S.sel.type === 'item' && S.sel.id === it.id;
    var thumb = it.img ? ' style="background-image:url(' + esc(it.img) + ')"' : '';
    var where = it.placed ? (roomAt(it.x, it.y, levelOf(it)) || {}).name || 'placed' : 'not placed';
    return '<div class="card' + (sel ? ' sel' : '') + '" data-item="' + it.id + '">' +
      '<div class="thumb"' + thumb + '>' + (it.img ? '' : '🪑') + '</div>' +
      '<div class="body"><div class="title">' + esc(it.name) + '</div>' +
      '<div class="sub"><span class="pill ' + it.status + '">' + it.status + '</span> ' + esc(where) + '</div></div>' +
      '<div class="end">' + esc(money(it.price)) + '</div></div>';
  }).join('') : '<div class="empty">Nothing added yet. Hit “From a shop link” and paste a product URL.</div>';

  /* photos */
  $('#photoList').innerHTML = S.proj.photos.length ? S.proj.photos.map(function (p) {
    var room = p.room ? findRoomAnywhere(p.room) : null;
    return '<div class="card" data-photo="' + p.id + '">' +
      '<div class="thumb" style="background-image:url(' + esc(p.src) + ')"></div>' +
      '<div class="body"><div class="title">' + esc(p.name) + '</div>' +
      '<div class="sub">' + esc(room ? room.name : 'not attached to a room') + '</div></div>' +
      '<div class="end">✎</div></div>';
  }).join('') : '<div class="empty">No photos yet.</div>';

  /* budget */
  var totals = { idea: 0, ordered: 0, owned: 0 }, counts = { idea: 0, ordered: 0, owned: 0 };
  S.proj.items.forEach(function (it) {
    var st = totals[it.status] != null ? it.status : 'idea';
    totals[st] += Number(it.price) || 0;
    counts[st]++;
  });
  var grand = totals.idea + totals.ordered + totals.owned;
  $('#budget').innerHTML =
    '<div class="card" style="cursor:default"><div class="body"><div class="title">' + esc(money(grand) || '—') + '</div>' +
    '<div class="sub">everything on the list</div></div></div>' +
    ['idea', 'ordered', 'owned'].map(function (k) {
      return '<div class="row" style="justify-content:space-between;padding:3px 2px;font-size:12.5px">' +
        '<span class="pill ' + k + '">' + k + ' (' + counts[k] + ')</span>' +
        '<span style="color:var(--muted)">' + esc(money(totals[k]) || '—') + '</span></div>';
    }).join('');

  /* level bar on the stage */
  $('#levelbar').innerHTML = S.proj.levels.map(function (l, i) {
    return '<button data-lvbtn="' + i + '" class="' + (i === S.level ? 'on' : '') + '">' + esc(l.name) + '</button>';
  }).join('');

  /* plan underlay info */
  var info = lv.plan && lv.plan.src
    ? 'Underlay scale: 1 m ≈ ' + Math.round(lv.plan.ppm) + ' px. Unlock it below to nudge it into place.'
    : 'No underlay on this level yet.';
  $('#planScaleInfo').textContent = info;
  $('#planOpacity').value = Math.round((lv.plan ? lv.plan.opacity : 0.55) * 100);
  $('#planLock').checked = !lv.plan || lv.plan.locked !== false;
}
function levelOf(it) {
  for (var i = 0; i < S.proj.levels.length; i++) if (S.proj.levels[i].id === it.level) return S.proj.levels[i];
  return level();
}
function findRoomAnywhere(id) {
  for (var i = 0; i < S.proj.levels.length; i++) {
    var rs = S.proj.levels[i].rooms;
    for (var j = 0; j < rs.length; j++) if (rs[j].id === id) return rs[j];
  }
  return null;
}
function renderAll() {
  syncSettingsInputs();
  renderSidebar();
  renderInspector();
  if (S.view === 'plan') drawPlan(); else { build3D(); G.collide = collisionRects(); }
  updateStatus();
  $('#projectName').value = S.proj.name;
}

/* ----------------------------------------------------------- inspector */
function renderInspector() {
  var body = $('#inspBody'), title = $('#inspTitle');
  if (!S.sel) {
    title.textContent = 'Nothing selected';
    body.innerHTML = '<p class="hint">Pick a room, a door or a piece of furniture to edit it here.</p>' +
      '<p class="hint">Shortcuts: <span class="kbd">V</span> select · <span class="kbd">R</span> room · ' +
      '<span class="kbd">D</span> door · <span class="kbd">W</span> window · <span class="kbd">M</span> measure · <span class="kbd">F</span> fit</p>';
    return;
  }
  if (S.sel.type === 'room') return inspectRoom();
  if (S.sel.type === 'item') return inspectItem();
  if (S.sel.type === 'opening') return inspectOpening();
  if (S.sel.type === 'level') return inspectLevel();
  if (S.sel.type === 'photo') return inspectPhoto();
}

var FLOOR_SWATCHES = ['#2b3352', '#3a3050', '#4a3a2c', '#2c4038', '#3d3d4d', '#5b4a3a', '#22283f', '#4b4b5e'];
var ITEM_SWATCHES = ['#8a7fd6', '#5271FF', '#C46BE4', '#4ade80', '#f0c24a', '#f4667a', '#cfd4dd', '#6b4f3a', '#2b2b3f'];

function inspectRoom() {
  var r = findRoom(S.sel.id);
  if (!r) { S.sel = null; return renderInspector(); }
  $('#inspTitle').textContent = 'Room · ' + r.name;
  $('#inspBody').innerHTML =
    '<label class="f"><span>Name</span><input type="text" id="f_name" value="' + esc(r.name) + '"></label>' +
    '<div class="grid2">' +
      '<label class="f"><span>Width</span><input type="text" id="f_w" value="' + fmtIn(r.w) + '"></label>' +
      '<label class="f"><span>Depth</span><input type="text" id="f_d" value="' + fmtIn(r.d) + '"></label>' +
    '</div>' +
    '<div class="grid2">' +
      '<label class="f"><span>X</span><input type="text" id="f_x" value="' + fmtIn(r.x) + '"></label>' +
      '<label class="f"><span>Y</span><input type="text" id="f_y" value="' + fmtIn(r.y) + '"></label>' +
    '</div>' +
    '<label class="f"><span>Floor colour</span><input type="color" id="f_floor" value="' + esc(r.floor || '#2b3352') + '"></label>' +
    '<div class="swatches" id="floorSwatches">' + FLOOR_SWATCHES.map(function (c) {
      return '<button data-c="' + c + '" style="background:' + c + '"></button>';
    }).join('') + '</div>' +
    '<p class="hint">' + fmtArea(roomArea(r)) + ' · ' + countItemsIn(r) + ' items in here</p>' +
    '<div class="row wrap" style="margin-top:10px">' +
      '<button class="btn sm" id="b_walkhere">Walk from here</button>' +
      '<button class="btn sm" id="b_dupe">Duplicate</button>' +
      '<button class="btn sm danger" id="b_del">Delete</button>' +
    '</div>';

  bindText('#f_name', function (v) { r.name = v || 'Room'; });
  bindLen('#f_w', function (v) { r.w = Math.max(0.3, v); });
  bindLen('#f_d', function (v) { r.d = Math.max(0.3, v); });
  bindLen('#f_x', function (v) { r.x = v; });
  bindLen('#f_y', function (v) { r.y = v; });
  bindVal('#f_floor', function (v) { r.floor = v; });
  $$('#floorSwatches button').forEach(function (b) {
    b.onclick = function () { snapshot(); r.floor = b.dataset.c; changed(); };
  });
  $('#b_walkhere').onclick = function () {
    G.walk.x = r.x + r.w / 2; G.walk.z = r.y + r.d / 2;
    setView('walk');
  };
  $('#b_dupe').onclick = function () {
    snapshot();
    var copy = JSON.parse(JSON.stringify(r));
    copy.id = uid('rm'); copy.x += r.w + 0.2; copy.name = r.name + ' copy';
    level().rooms.push(copy);
    select({ type: 'room', id: copy.id });
    changed();
  };
  $('#b_del').onclick = deleteSelection;
}
function countItemsIn(r) {
  return S.proj.items.filter(function (it) {
    return it.placed && it.level === level().id && it.x >= r.x && it.x <= r.x + r.w && it.y >= r.y && it.y <= r.y + r.d;
  }).length;
}

function inspectItem() {
  var it = findItem(S.sel.id);
  if (!it) { S.sel = null; return renderInspector(); }
  $('#inspTitle').textContent = it.name;
  $('#inspBody').innerHTML =
    (it.img ? '<img src="' + esc(it.img) + '" alt="" style="width:100%;max-height:150px;object-fit:contain;background:#fff;border-radius:10px;margin-bottom:10px">' : '') +
    '<label class="f"><span>Name</span><input type="text" id="f_name" value="' + esc(it.name) + '"></label>' +
    '<label class="f"><span>Shop link</span><input type="url" id="f_url" value="' + esc(it.url || '') + '" placeholder="https://…"></label>' +
    (it.url ? '<p class="hint"><a href="' + esc(it.url) + '" target="_blank" rel="noopener">Open the listing ↗</a></p>' : '') +
    '<div class="grid2">' +
      '<label class="f"><span>Price</span><input type="text" id="f_price" value="' + esc(it.price == null ? '' : it.price) + '"></label>' +
      '<label class="f"><span>Status</span><select id="f_status">' +
        ['idea', 'ordered', 'owned'].map(function (s) { return '<option' + (it.status === s ? ' selected' : '') + '>' + s + '</option>'; }).join('') +
      '</select></label>' +
    '</div>' +
    '<label class="f"><span>Kind</span><select id="f_shape">' +
      DEFAULT_SHAPES.map(function (s) { return '<option value="' + s.id + '"' + (it.shape === s.id ? ' selected' : '') + '>' + s.label + '</option>'; }).join('') +
    '</select></label>' +
    '<div class="grid3">' +
      '<label class="f"><span>Width</span><input type="text" id="f_w" value="' + fmtIn(it.w) + '"></label>' +
      '<label class="f"><span>Depth</span><input type="text" id="f_d" value="' + fmtIn(it.d) + '"></label>' +
      '<label class="f"><span>Height</span><input type="text" id="f_h" value="' + fmtIn(it.h) + '"></label>' +
    '</div>' +
    '<div class="grid2">' +
      '<label class="f"><span>Rotation °</span><input type="number" id="f_rot" value="' + (it.rot || 0) + '" step="5"></label>' +
      '<label class="f"><span>Off the floor</span><input type="text" id="f_mount" value="' + fmtIn(it.mount || 0) + '"></label>' +
    '</div>' +
    '<label class="f"><span>Colour</span><input type="color" id="f_color" value="' + esc(it.color || '#8a7fd6') + '"></label>' +
    '<div class="swatches" id="itemSwatches">' + ITEM_SWATCHES.map(function (c) {
      return '<button data-c="' + c + '" style="background:' + c + '"></button>';
    }).join('') + '</div>' +
    '<label class="f" style="margin-top:10px"><span>Level</span><select id="f_level">' +
      S.proj.levels.map(function (l) { return '<option value="' + l.id + '"' + (it.level === l.id ? ' selected' : '') + '>' + esc(l.name) + '</option>'; }).join('') +
    '</select></label>' +
    '<label class="f"><span>Notes</span><textarea id="f_notes">' + esc(it.notes || '') + '</textarea></label>' +
    '<div class="row wrap">' +
      (it.placed ? '<button class="btn sm" id="b_unplace">Take off the plan</button>' : '<button class="btn sm primary" id="b_place">Place on plan</button>') +
      '<button class="btn sm" id="b_photo">Photo</button>' +
      '<button class="btn sm" id="b_dupe">Duplicate</button>' +
      '<button class="btn sm danger" id="b_del">Delete</button>' +
    '</div>';

  bindText('#f_name', function (v) { it.name = v || 'Item'; });
  bindText('#f_url', function (v) { it.url = v.trim(); });
  bindText('#f_price', function (v) { var n = parseFloat(String(v).replace(/[^\d.]/g, '')); it.price = isNaN(n) ? null : n; });
  bindVal('#f_status', function (v) { it.status = v; });
  bindVal('#f_shape', function (v) {
    var was = it.shape; it.shape = v;
    if (was !== v) { var def = shapeDef(v); if (!it.sized) { it.w = def.w; it.d = def.d; it.h = def.h; } }
  });
  bindLen('#f_w', function (v) { it.w = Math.max(0.05, v); it.sized = true; });
  bindLen('#f_d', function (v) { it.d = Math.max(0.05, v); it.sized = true; });
  bindLen('#f_h', function (v) { it.h = Math.max(0.05, v); it.sized = true; });
  bindVal('#f_rot', function (v) { it.rot = Number(v) || 0; });
  bindLen('#f_mount', function (v) { it.mount = Math.max(0, v); });
  bindVal('#f_color', function (v) { it.color = v; });
  bindText('#f_notes', function (v) { it.notes = v; });
  bindVal('#f_level', function (v) { it.level = v; });
  $$('#itemSwatches button').forEach(function (b) {
    b.onclick = function () { snapshot(); it.color = b.dataset.c; changed(); };
  });
  if ($('#b_place')) $('#b_place').onclick = function () {
    S.pendingPlace = it.id; setTool('item'); setView('plan');
    toast('Click on the plan to drop “' + it.name + '”');
  };
  if ($('#b_unplace')) $('#b_unplace').onclick = function () { snapshot(); it.placed = false; changed(); };
  $('#b_photo').onclick = function () { pickImage(function (dataUrl) { snapshot(); it.img = dataUrl; changed(); }); };
  $('#b_dupe').onclick = function () {
    snapshot();
    var copy = JSON.parse(JSON.stringify(it));
    copy.id = uid('it'); copy.x = (copy.x || 0) + 0.4; copy.y = (copy.y || 0) + 0.4;
    S.proj.items.push(copy);
    select({ type: 'item', id: copy.id });
    changed();
  };
  $('#b_del').onclick = deleteSelection;
}

function inspectOpening() {
  var o = findOpening(S.sel.id);
  if (!o) { S.sel = null; return renderInspector(); }
  $('#inspTitle').textContent = o.type[0].toUpperCase() + o.type.slice(1);
  $('#inspBody').innerHTML =
    '<label class="f"><span>Type</span><select id="f_type">' +
      ['door', 'window', 'arch'].map(function (t) { return '<option value="' + t + '"' + (o.type === t ? ' selected' : '') + '>' + t + '</option>'; }).join('') +
    '</select></label>' +
    '<div class="grid2">' +
      '<label class="f"><span>Width</span><input type="text" id="f_wid" value="' + fmtIn(o.to - o.from) + '"></label>' +
      '<label class="f"><span>Head height</span><input type="text" id="f_top" value="' + fmtIn(o.top) + '"></label>' +
    '</div>' +
    '<label class="f"><span>Sill height (0 for a door)</span><input type="text" id="f_sill" value="' + fmtIn(o.sill) + '"></label>' +
    '<p class="hint">Drag it along the wall on the plan, or use the arrow keys.</p>' +
    '<div class="row wrap"><button class="btn sm danger" id="b_del">Delete</button></div>';
  bindVal('#f_type', function (v) {
    o.type = v;
    if (v === 'window' && o.sill < 0.05) { o.sill = 0.9; o.top = 2.1; }
    if (v !== 'window') { o.sill = 0; o.top = 2.05; }
  });
  bindLen('#f_wid', function (v) { o.to = o.from + Math.max(0.2, v); });
  bindLen('#f_top', function (v) { o.top = Math.max(o.sill + 0.2, v); });
  bindLen('#f_sill', function (v) { o.sill = clamp(v, 0, o.top - 0.2); });
  $('#b_del').onclick = deleteSelection;
}

function inspectLevel() {
  var lv = S.proj.levels[S.sel.index];
  if (!lv) { S.sel = null; return renderInspector(); }
  $('#inspTitle').textContent = 'Level · ' + lv.name;
  $('#inspBody').innerHTML =
    '<label class="f"><span>Name</span><input type="text" id="f_name" value="' + esc(lv.name) + '"></label>' +
    '<div class="grid2">' +
      '<label class="f"><span>Ceiling height</span><input type="text" id="f_h" value="' + fmtIn(lv.height) + '"></label>' +
      '<label class="f"><span>Floor level</span><input type="text" id="f_base" value="' + fmtIn(lv.base) + '"></label>' +
    '</div>' +
    '<p class="hint">Floor level is how high this storey sits above the ground floor.</p>' +
    (S.proj.levels.length > 1 ? '<button class="btn sm danger" id="b_del">Delete level</button>' : '');
  bindText('#f_name', function (v) { lv.name = v || 'Level'; });
  bindLen('#f_h', function (v) { lv.height = clamp(v, 1.6, 6); });
  bindLen('#f_base', function (v) { lv.base = v; });
  if ($('#b_del')) $('#b_del').onclick = function () {
    if (!confirm('Delete “' + lv.name + '” and everything on it?')) return;
    snapshot();
    var id = lv.id;
    S.proj.levels.splice(S.sel.index, 1);
    S.proj.items = S.proj.items.filter(function (it) { return it.level !== id; });
    S.level = clamp(S.level, 0, S.proj.levels.length - 1);
    select(null);
    changed();
  };
}

function inspectPhoto() {
  var p = findPhoto(S.sel.id);
  if (!p) { S.sel = null; return renderInspector(); }
  $('#inspTitle').textContent = 'Photo · ' + p.name;
  var roomOpts = '<option value="">— not attached —</option>' + S.proj.levels.map(function (l) {
    return l.rooms.map(function (r) {
      return '<option value="' + r.id + '"' + (p.room === r.id ? ' selected' : '') + '>' + esc(l.name + ' · ' + r.name) + '</option>';
    }).join('');
  }).join('');
  $('#inspBody').innerHTML =
    '<img src="' + esc(p.src) + '" alt="" style="width:100%;border-radius:10px;margin-bottom:10px">' +
    '<label class="f"><span>Name</span><input type="text" id="f_name" value="' + esc(p.name) + '"></label>' +
    '<label class="f"><span>Room</span><select id="f_room">' + roomOpts + '</select></label>' +
    '<label class="f"><span>Note</span><textarea id="f_note">' + esc(p.note || '') + '</textarea></label>' +
    '<div class="row wrap">' +
      '<button class="btn sm" id="b_toart">Hang it on a wall</button>' +
      '<button class="btn sm danger" id="b_del">Delete</button>' +
    '</div>' +
    '<p class="hint">“Hang it on a wall” turns the photo into a framed picture you can place in 3D.</p>';
  bindText('#f_name', function (v) { p.name = v || 'Photo'; });
  bindVal('#f_room', function (v) { p.room = v; });
  bindText('#f_note', function (v) { p.note = v; });
  $('#b_toart').onclick = function () {
    snapshot();
    var it = makeItem({ name: p.name, shape: 'art', img: p.src, w: 0.6, h: 0.8, d: 0.04, mount: 1.1, status: 'owned' });
    S.proj.items.push(it);
    S.pendingPlace = it.id;
    setTool('item'); setView('plan');
    select({ type: 'item', id: it.id });
    toast('Click on the plan to hang it');
    changed();
  };
  $('#b_del').onclick = function () {
    snapshot();
    S.proj.photos = S.proj.photos.filter(function (x) { return x.id !== p.id; });
    select(null);
    changed();
  };
}

/* form field plumbing: live preview on input, one undo step on commit */
function bindText(sel, apply) {
  var el = $(sel);
  if (!el) return;
  el.addEventListener('focus', function () { el._before = JSON.stringify(S.proj); });
  el.addEventListener('input', function () { apply(el.value); if (S.view === 'plan') drawPlan(); });
  el.addEventListener('change', function () { commitField(el); });
  el.addEventListener('blur', function () { commitField(el); });
}
function bindVal(sel, apply) {
  var el = $(sel);
  if (!el) return;
  el.addEventListener('focus', function () { el._before = JSON.stringify(S.proj); });
  el.addEventListener('input', function () { apply(el.value); if (S.view === 'plan') drawPlan(); });
  el.addEventListener('change', function () { apply(el.value); commitField(el); });
}
function bindLen(sel, apply) {
  var el = $(sel);
  if (!el) return;
  el.addEventListener('focus', function () { el._before = JSON.stringify(S.proj); });
  el.addEventListener('change', function () {
    var v = parseLen(el.value, null);
    if (v == null || isNaN(v)) { toast('Could not read “' + el.value + '”'); }
    else { apply(round(v, 3)); }
    commitField(el);
  });
}
function commitField(el) {
  if (!el._before) return;
  if (el._before !== JSON.stringify(S.proj)) {
    S.history.push(el._before);
    if (S.history.length > 40) S.history.shift();
    S.future.length = 0;
    updateUndoButtons();
    changed();
  }
  el._before = null;
}
function fmtIn(m) {
  if (m == null) return '';
  if (S.proj.units === 'ft') return fmtLen(m);
  return String(round(m, 3));
}

function deleteSelection() {
  if (!S.sel) return;
  snapshot();
  var lv = level();
  if (S.sel.type === 'room') lv.rooms = lv.rooms.filter(function (r) { return r.id !== S.sel.id; });
  if (S.sel.type === 'opening') lv.openings = lv.openings.filter(function (o) { return o.id !== S.sel.id; });
  if (S.sel.type === 'item') S.proj.items = S.proj.items.filter(function (i) { return i.id !== S.sel.id; });
  select(null);
  changed();
}

/* ---------------------------------------------------------------- modals */
function openModal(html) {
  var wrap = $('#modalWrap');
  wrap.innerHTML = '<div class="modal">' + html + '</div>';
  wrap.classList.remove('hidden');
  wrap.onclick = function (e) { if (e.target === wrap) closeModal(); };
  return wrap;
}
function closeModal() {
  var wrap = $('#modalWrap');
  wrap.classList.add('hidden');
  wrap.innerHTML = '';
}
document.addEventListener('keydown', function (e) {
  if (e.key === 'Escape' && !$('#modalWrap').classList.contains('hidden')) closeModal();
});

function makeItem(p) {
  var def = shapeDef(p.shape || 'box');
  return {
    id: uid('it'),
    name: p.name || 'New item',
    url: p.url || '',
    price: p.price == null ? null : p.price,
    status: p.status || 'idea',
    shape: p.shape || 'box',
    w: p.w || def.w, d: p.d || def.d, h: p.h || def.h,
    sized: !!p.sized,
    x: p.x || 0, y: p.y || 0, rot: p.rot || 0, mount: p.mount || 0,
    color: p.color || '#8a7fd6',
    img: p.img || '',
    notes: p.notes || '',
    level: p.level || level().id,
    placed: !!p.placed
  };
}

/* The add-from-a-link flow. Metadata comes back through /api/product-lookup
   because shops don't hand their pages to a browser on another origin. */
function openItemModal(existing, pos) {
  var draft = existing || makeItem({});
  openModal(
    '<div class="mhead"><h3>Add something to the house</h3>' +
      '<button class="btn sm ghost" id="m_close">✕</button></div>' +
    '<div class="mbody">' +
      '<label class="f"><span>Paste a product link (IKEA, DFS, Wayfair, Facebook Marketplace…)</span>' +
        '<input type="url" id="m_url" placeholder="https://www.ikea.com/gb/en/p/…"></label>' +
      '<div class="row"><button class="btn primary" id="m_fetch">Pull the details</button>' +
        '<button class="btn" id="m_upload">Use my own photo</button></div>' +
      '<div id="m_status" style="margin-top:10px"></div>' +
      '<div id="m_preview"></div>' +
      '<hr style="border:0;border-top:1px solid var(--line);margin:14px 0">' +
      '<label class="f"><span>Name</span><input type="text" id="m_name" value="' + esc(draft.name) + '"></label>' +
      '<div class="grid2">' +
        '<label class="f"><span>Price</span><input type="text" id="m_price" placeholder="0.00"></label>' +
        '<label class="f"><span>Status</span><select id="m_status_sel">' +
          '<option value="idea">idea</option><option value="ordered">ordered</option><option value="owned">owned</option>' +
        '</select></label>' +
      '</div>' +
      '<label class="f"><span>Kind</span><select id="m_shape">' +
        DEFAULT_SHAPES.map(function (s) { return '<option value="' + s.id + '">' + s.label + '</option>'; }).join('') +
      '</select></label>' +
      '<div class="grid3">' +
        '<label class="f"><span>Width</span><input type="text" id="m_w" value="' + fmtIn(draft.w) + '"></label>' +
        '<label class="f"><span>Depth</span><input type="text" id="m_d" value="' + fmtIn(draft.d) + '"></label>' +
        '<label class="f"><span>Height</span><input type="text" id="m_h" value="' + fmtIn(draft.h) + '"></label>' +
      '</div>' +
      '<p class="hint">Sizes are what make this useful — if the listing does not say, measure the gap you have and put that in.</p>' +
    '</div>' +
    '<div class="mfoot"><button class="btn" id="m_cancel">Cancel</button>' +
      '<button class="btn primary" id="m_add">Add to the house</button></div>'
  );

  var img = '';
  $('#m_close').onclick = $('#m_cancel').onclick = closeModal;
  $('#m_shape').value = draft.shape;
  $('#m_status_sel').value = draft.status;

  $('#m_shape').onchange = function () {
    var def = shapeDef($('#m_shape').value);
    $('#m_w').value = fmtIn(def.w); $('#m_d').value = fmtIn(def.d); $('#m_h').value = fmtIn(def.h);
  };
  $('#m_upload').onclick = function () {
    pickImage(function (dataUrl) {
      img = dataUrl;
      $('#m_preview').innerHTML = '<div class="preview"><img src="' + esc(dataUrl) + '" alt=""></div>';
    });
  };
  $('#m_fetch').onclick = function () {
    var url = $('#m_url').value.trim();
    if (!/^https?:\/\//i.test(url)) { setStatus('Paste the full https:// link to the product page', 'bad'); return; }
    setStatus('Fetching…');
    $('#m_fetch').disabled = true;
    fetch('/api/product-lookup', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: url })
    }).then(function (r) {
      return r.json().then(function (j) { return { ok: r.ok, body: j }; });
    }).then(function (res) {
      $('#m_fetch').disabled = false;
      if (!res.ok) { setStatus(res.body && res.body.error ? res.body.error : 'That site would not hand anything over — fill it in below instead.', 'bad'); return; }
      var p = res.body;
      if (p.title) $('#m_name').value = p.title.slice(0, 90);
      if (p.price != null) $('#m_price').value = p.price;
      if (p.image) {
        img = p.image;
        $('#m_preview').innerHTML = '<div class="preview"><img src="' + esc(p.image) + '" alt="">' +
          '<div class="hint">' + esc(p.siteName || '') + (p.currency ? ' · ' + esc(p.currency) : '') + '</div></div>';
      }
      if (p.dims) {
        if (p.dims.w) $('#m_w').value = fmtIn(p.dims.w);
        if (p.dims.d) $('#m_d').value = fmtIn(p.dims.d);
        if (p.dims.h) $('#m_h').value = fmtIn(p.dims.h);
        setStatus('Got it — including the size from the listing. Check it looks right.', 'good');
      } else {
        setStatus('Got the name, photo and price. No size on the page, so put one in below.', 'good');
      }
    })['catch'](function () {
      $('#m_fetch').disabled = false;
      setStatus('Could not reach the lookup service. Fill the details in by hand — it still works.', 'bad');
    });
  };
  $('#m_add').onclick = function () {
    var price = parseFloat(String($('#m_price').value).replace(/[^\d.]/g, ''));
    var it = makeItem({
      name: $('#m_name').value.trim() || 'New item',
      url: $('#m_url').value.trim(),
      price: isNaN(price) ? null : price,
      status: $('#m_status_sel').value,
      shape: $('#m_shape').value,
      w: parseLen($('#m_w').value, draft.w),
      d: parseLen($('#m_d').value, draft.d),
      h: parseLen($('#m_h').value, draft.h),
      sized: true,
      img: img
    });
    snapshot();
    if (pos) { it.x = pos.x; it.y = pos.y; it.placed = true; }
    S.proj.items.push(it);
    closeModal();
    select({ type: 'item', id: it.id });
    if (!pos) {
      S.pendingPlace = it.id;
      setTool('item');
      setView('plan');
      toast('Click on the plan to drop “' + it.name + '”');
    }
    changed();
  };
  function setStatus(msg, kind) {
    $('#m_status').innerHTML = '<div class="notice ' + (kind || '') + '">' + esc(msg) + '</div>';
  }
  setTimeout(function () { $('#m_url').focus(); }, 30);
}

function askCalibration(d, worldDist) {
  openModal(
    '<div class="mhead"><h3>Set the plan scale</h3></div>' +
    '<div class="mbody">' +
      '<p class="hint">How long is the line you just drew, in real life? A door is usually 0.9 m, a standard brick course 0.225 m.</p>' +
      '<label class="f"><span>Real length</span><input type="text" id="c_len" placeholder="' + (S.proj.units === 'ft' ? "10'" : '3.6') + '"></label>' +
    '</div>' +
    '<div class="mfoot"><button class="btn" id="c_cancel">Cancel</button>' +
      '<button class="btn primary" id="c_ok">Set scale</button></div>'
  );
  $('#c_cancel').onclick = function () { closeModal(); setTool('select'); drawPlan(); };
  $('#c_ok').onclick = function () {
    var real = parseLen($('#c_len').value, null);
    if (!real || real <= 0) { toast('Give me a length like 3.6 or 12ft', 'bad'); return; }
    snapshot();
    var lp = level().plan;
    var k = worldDist / real;                       // how much the underlay must shrink
    lp.ppm = lp.ppm * k;
    lp.ox = d.x0 - (d.x0 - lp.ox) / k;
    lp.oy = d.y0 - (d.y0 - lp.oy) / k;
    closeModal();
    setTool('select');
    changed();
    toast('Scale set — trace your rooms over the top', 'good');
  };
  setTimeout(function () { $('#c_len').focus(); }, 30);
}

/* --------------------------------------------------------- file helpers */
var imgPickMode = null, imgPickCb = null;
function pickImage(cb) { imgPickMode = 'single'; imgPickCb = cb; $('#imgPick').removeAttribute('multiple'); $('#imgPick').click(); }
function pickPhotos() { imgPickMode = 'photos'; imgPickCb = null; $('#imgPick').setAttribute('multiple', 'multiple'); $('#imgPick').click(); }
function pickPlanImage() { imgPickMode = 'plan'; imgPickCb = null; $('#imgPick').removeAttribute('multiple'); $('#imgPick').click(); }

$('#imgPick').addEventListener('change', function (e) {
  var files = Array.prototype.slice.call(e.target.files || []);
  e.target.value = '';
  if (!files.length) return;
  if (imgPickMode === 'single') {
    fileToDataURL(files[0]).then(function (u) { return shrinkImage(u, 640, 0.82); }).then(function (small) {
      if (imgPickCb) imgPickCb(small);
    })['catch'](function (err) { toast(err.message, 'bad'); });
    return;
  }
  if (imgPickMode === 'plan') {
    fileToDataURL(files[0]).then(function (u) { return shrinkImage(u, 2000, 0.85); }).then(function (small) {
      snapshot();
      var lv = level();
      lv.plan = lv.plan || {};
      lv.plan.src = small;
      lv.plan.opacity = lv.plan.opacity || 0.55;
      lv.plan.ppm = lv.plan.ppm || 40;
      lv.plan.ox = lv.plan.ox || 0;
      lv.plan.oy = lv.plan.oy || 0;
      lv.plan.locked = false;
      changed();
      setTimeout(fitToPlan, 120);
      toast('Now hit “Set scale” and drag along something you know the length of', 'good');
    })['catch'](function (err) { toast(err.message, 'bad'); });
    return;
  }
  /* photos */
  Promise.all(files.map(function (f) {
    return fileToDataURL(f).then(function (u) { return shrinkImage(u, 1100, 0.78); }).then(function (small) {
      return { id: uid('ph'), name: f.name.replace(/\.[^.]+$/, ''), src: small, room: '', note: '' };
    });
  })).then(function (photos) {
    snapshot();
    S.proj.photos = S.proj.photos.concat(photos);
    changed();
    toast(photos.length + ' photo' + (photos.length === 1 ? '' : 's') + ' added', 'good');
  })['catch'](function (err) { toast(err.message, 'bad'); });
});

function download(filename, text, type) {
  var blob = new Blob([text], { type: type || 'application/json' });
  var a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 500);
}
function exportProject() {
  var name = (S.proj.name || 'house').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
  download(name + '.house.json', JSON.stringify(S.proj, null, 1));
  toast('Backed up to your downloads', 'good');
}
function exportShoppingList() {
  var rows = [['Item', 'Status', 'Price', 'Width', 'Depth', 'Height', 'Level', 'Room', 'Link', 'Notes']];
  S.proj.items.forEach(function (it) {
    var lv = levelOf(it);
    var room = it.placed ? (roomAt(it.x, it.y, lv) || {}).name || '' : '';
    rows.push([it.name, it.status, it.price == null ? '' : it.price,
      round(it.w, 3), round(it.d, 3), round(it.h, 3), lv.name, room, it.url || '', (it.notes || '').replace(/\s+/g, ' ')]);
  });
  var csv = rows.map(function (r) {
    return r.map(function (c) { return '"' + String(c == null ? '' : c).replace(/"/g, '""') + '"'; }).join(',');
  }).join('\n');
  download('shopping-list.csv', csv, 'text/csv');
}
function importProject(file) {
  var read = file.text ? file.text() : new Promise(function (resolve, reject) {
    var r = new FileReader();
    r.onload = function () { resolve(r.result); };
    r.onerror = function () { reject(new Error('Could not read the file')); };
    r.readAsText(file);
  });
  read.then(function (text) {
    var data = JSON.parse(text);
    if (!data || !data.levels) throw new Error('That is not a Home Studio file');
    snapshot();
    S.proj = migrate(data);
    S.level = 0;
    select(null);
    renderAll();
    fitToPlan();
    save();
    toast('Loaded ' + (S.proj.name || 'the house'), 'good');
  })['catch'](function (err) { toast(err.message || 'Import failed', 'bad'); });
}
function migrate(p) {
  p.opts = Object.assign({ wallH: 2.4, wallT: 0.1, shadows: true, ceilings: false, clip: true, light: 100 }, p.opts || {});
  p.items = p.items || [];
  p.photos = p.photos || [];
  p.currency = p.currency || '£';
  p.units = p.units || 'm';
  (p.levels || []).forEach(function (l) {
    l.rooms = l.rooms || [];
    l.openings = l.openings || [];
    l.height = l.height || p.opts.wallH;
    l.base = l.base || 0;
    l.plan = Object.assign({ src: '', opacity: 0.55, ppm: 40, ox: 0, oy: 0, locked: true }, l.plan || {});
  });
  p.items.forEach(function (it) {
    it.status = it.status || 'idea';
    it.shape = it.shape || 'box';
    it.rot = it.rot || 0;
    it.mount = it.mount || 0;
  });
  return p;
}

/* ------------------------------------------------------------- sample */
function sampleHouse() {
  var p = newProject('Sample house');
  var lv = p.levels[0];
  lv.name = 'Ground floor';
  function room(name, x, y, w, d, floor) {
    return { id: uid('rm'), name: name, x: x, y: y, w: w, d: d, floor: floor };
  }
  lv.rooms = [
    room('Living room', 0,   0,   5.2, 4.2, '#2b3352'),
    room('Kitchen',     5.2, 0,   3.6, 4.2, '#2c4038'),
    room('Hall',        0,   4.2, 2.2, 3.4, '#3d3d4d'),
    room('Bedroom',     2.2, 4.2, 3.4, 3.4, '#3a3050'),
    room('Bathroom',    5.6, 4.2, 3.2, 3.4, '#22283f')
  ];
  function op(type, axis, coord, from, to, sill, top) {
    return { id: uid('op'), type: type, axis: axis, coord: coord, from: from, to: to, sill: sill, top: top };
  }
  lv.openings = [
    op('door',   'h', 4.2, 0.6, 1.5, 0,   2.05),   // hall into the living room
    op('door',   'v', 2.2, 4.6, 5.5, 0,   2.05),   // hall into the bedroom
    op('door',   'v', 5.6, 4.6, 5.5, 0,   2.05),   // bedroom into the bathroom
    op('arch',   'v', 5.2, 0.8, 2.4, 0,   2.2),    // living room through to the kitchen
    op('door',   'v', 0,   5.0, 5.9, 0,   2.05),   // front door
    op('window', 'h', 0,   1.4, 3.2, 0.9, 2.1),    // living room, front
    op('window', 'h', 0,   6.2, 7.8, 1.0, 2.1),    // kitchen, front
    op('window', 'h', 7.6, 2.6, 4.2, 0.9, 2.1),    // bedroom, back
    op('window', 'h', 7.6, 6.4, 7.4, 1.3, 2.1)     // bathroom, back
  ];
  p.items = [
    makeIt('Sofa',          'sofa',      2.2, 1.1, 0,   2.3, 0.95, 0.85, '#4a5a8a', lv.id),
    makeIt('Coffee table',  'table',     2.4, 2.3, 0,   1.1, 0.6,  0.42, '#6b4f3a', lv.id),
    makeIt('TV',            'tv',        2.4, 3.9, 180, 1.3, 0.08, 0.75, '#15151f', lv.id),
    makeIt('Rug',           'rug',       2.4, 2.2, 0,   2.6, 1.8,  0.02, '#3d4468', lv.id),
    makeIt('Bookshelf',     'shelf',     4.8, 2.0, 90,  0.9, 0.35, 1.8,  '#5b4a3a', lv.id),
    makeIt('Dining table',  'table',     7.0, 2.9, 0,   1.4, 0.85, 0.75, '#6b4f3a', lv.id),
    makeIt('Fridge',        'appliance', 8.4, 0.5, 0,   0.6, 0.65, 1.8,  '#cfd4dd', lv.id),
    makeIt('Bed',           'bed',       3.9, 6.3, 0,   1.5, 2.0,  0.55, '#4a4060', lv.id),
    makeIt('Wardrobe',      'wardrobe',  2.9, 4.6, 0,   1.2, 0.6,  2.0,  '#5b4a3a', lv.id),
    makeIt('Floor lamp',    'lamp',      0.6, 0.6, 0,   0.4, 0.4,  1.5,  '#d8cfae', lv.id),
    makeIt('Plant',         'plant',     4.8, 3.7, 0,   0.5, 0.5,  1.2,  '#3f8b52', lv.id)
  ];
  return p;
  function makeIt(name, shape, x, y, rot, w, d, h, color, levelId) {
    return { id: uid('it'), name: name, shape: shape, x: x, y: y, rot: rot, w: w, d: d, h: h,
             color: color, level: levelId, placed: true, status: 'owned', sized: true,
             price: null, url: '', img: '', notes: '', mount: 0 };
  }
}

/* ------------------------------------------------------ settings sync */
function syncSettingsInputs() {
  $('#unitSel').value = S.proj.units;
  $('#currencySel').value = S.proj.currency;
  $('#defWallH').value = fmtIn(S.proj.opts.wallH);
  $('#defWallT').value = fmtIn(S.proj.opts.wallT);
  $('#optShadows').checked = !!S.proj.opts.shadows;
  $('#optCeilings').checked = !!S.proj.opts.ceilings;
  $('#optClip').checked = !!S.proj.opts.clip;
  $('#optLight').value = S.proj.opts.light == null ? 100 : S.proj.opts.light;
  $('#projectName').value = S.proj.name;
}

/* ========================================================================
   WIRING
   ====================================================================== */
$$('#tabs button').forEach(function (b) {
  b.onclick = function () {
    $$('#tabs button').forEach(function (x) { x.classList.toggle('on', x === b); });
    $$('.pane').forEach(function (p) { p.classList.toggle('on', p.dataset.pane === b.dataset.tab); });
  };
});
$$('#toolbar button[data-tool]').forEach(function (b) {
  b.onclick = function () { if (S.view !== 'plan') setView('plan'); setTool(b.dataset.tool); };
});
$('#btnFit').onclick = fitToPlan;
$$('#viewSwitch button').forEach(function (b) { b.onclick = function () { setView(b.dataset.view); }; });

$('#levelList').onclick = function (e) {
  var card = e.target.closest('[data-level]');
  if (!card) return;
  var i = Number(card.dataset.level);
  if (i === S.level) { select({ type: 'level', index: i }); return; }
  S.level = i;
  select(null);
  if (S.view !== 'plan') { build3D(); G.collide = collisionRects(); ensureWalkStart(); }
  renderSidebar();
  drawPlan();
};
$('#levelbar').onclick = function (e) {
  var b = e.target.closest('[data-lvbtn]');
  if (!b) return;
  S.level = Number(b.dataset.lvbtn);
  select(null);
  if (S.view !== 'plan') { build3D(); G.collide = collisionRects(); ensureWalkStart(); }
  renderSidebar();
  drawPlan();
};
$('#btnAddLevel').onclick = function () {
  snapshot();
  var prev = S.proj.levels[S.proj.levels.length - 1];
  var lv = newLevel('Level ' + (S.proj.levels.length + 1), (prev.base || 0) + (prev.height || 2.4) + 0.25);
  lv.height = S.proj.opts.wallH;
  S.proj.levels.push(lv);
  S.level = S.proj.levels.length - 1;
  select({ type: 'level', index: S.level });
  changed();
};
$('#btnAddRoom').onclick = function () {
  snapshot();
  var c = s2w(planCanvas.clientWidth / 2, planCanvas.clientHeight / 2);
  var r = { id: uid('rm'), name: 'Room ' + (level().rooms.length + 1),
            x: snapVal(c.x - 2), y: snapVal(c.y - 1.75), w: 4, d: 3.5, floor: '#2b3352' };
  level().rooms.push(r);
  select({ type: 'room', id: r.id });
  changed();
};
$('#roomList').onclick = function (e) {
  var card = e.target.closest('[data-room]');
  if (card) select({ type: 'room', id: card.dataset.room });
};
$('#openingList').onclick = function (e) {
  var card = e.target.closest('[data-opening]');
  if (card) select({ type: 'opening', id: card.dataset.opening });
};
$('#itemList').onclick = function (e) {
  var card = e.target.closest('[data-item]');
  if (!card) return;
  var it = findItem(card.dataset.item);
  select({ type: 'item', id: card.dataset.item });
  if (it && it.placed && it.level !== level().id) {
    for (var i = 0; i < S.proj.levels.length; i++) {
      if (S.proj.levels[i].id === it.level) { S.level = i; renderSidebar(); drawPlan(); break; }
    }
  }
};
$('#photoList').onclick = function (e) {
  var card = e.target.closest('[data-photo]');
  if (card) select({ type: 'photo', id: card.dataset.photo });
};
$('#itemFilter').onchange = renderSidebar;

$('#btnAddItem').onclick = $('#btnAddItem2').onclick = function () { openItemModal(null, null); };
$('#btnAddBlank').onclick = function () {
  snapshot();
  var it = makeItem({ name: 'New item' });
  S.proj.items.push(it);
  S.pendingPlace = it.id;
  setTool('item');
  setView('plan');
  select({ type: 'item', id: it.id });
  toast('Click on the plan to place it');
  changed();
};
$('#btnShoppingList').onclick = exportShoppingList;
$('#btnAddPhoto').onclick = pickPhotos;
$('#btnPlanImage').onclick = pickPlanImage;
$('#btnCalibrate').onclick = function () {
  if (!level().plan.src) { toast('Upload a floor plan first'); return; }
  setView('plan');
  setTool('calibrate');
  toast('Drag along something you know the length of');
};
$('#btnPlanClear').onclick = function () {
  if (!level().plan.src) return;
  snapshot();
  level().plan.src = '';
  changed();
};
$('#planOpacity').oninput = function () {
  level().plan.opacity = Number(this.value) / 100;
  drawPlan();
};
$('#planOpacity').onchange = touch;
$('#planLock').onchange = function () { level().plan.locked = this.checked; touch(); drawPlan(); };

$('#gridSel').onchange = function () { S.grid = Number(this.value); drawPlan(); };
$('#snapChk').onchange = function () { S.snap = this.checked; };

$('#unitSel').onchange = function () { S.proj.units = this.value; renderAll(); touch(); };
$('#currencySel').onchange = function () { S.proj.currency = this.value; renderAll(); touch(); };
$('#defWallH').onchange = function () {
  var v = parseLen(this.value, S.proj.opts.wallH);
  snapshot();
  S.proj.opts.wallH = clamp(v, 1.6, 6);
  S.proj.levels.forEach(function (l) { l.height = S.proj.opts.wallH; });
  changed();
};
$('#defWallT').onchange = function () {
  var v = parseLen(this.value, S.proj.opts.wallT);
  snapshot();
  S.proj.opts.wallT = clamp(v, 0.02, 0.6);
  changed();
};
$('#optShadows').onchange = function () { S.proj.opts.shadows = this.checked; changed(); };
$('#optCeilings').onchange = function () { S.proj.opts.ceilings = this.checked; changed(); };
$('#optClip').onchange = function () { S.proj.opts.clip = this.checked; touch(); };
$('#optLight').oninput = function () {
  S.proj.opts.light = Number(this.value);
  if (G.ready) {
    var mul = S.proj.opts.light / 100;
    G.sun.intensity = 0.6 * mul;
    G.hemi.intensity = 0.45 * mul;
    G.amb.intensity = 0.22 * mul;
  }
};
$('#optLight').onchange = touch;

$('#btnExport').onclick = exportProject;
$('#btnImport').onclick = function () { $('#filePick').click(); };
$('#filePick').addEventListener('change', function (e) {
  var f = e.target.files && e.target.files[0];
  e.target.value = '';
  if (f) importProject(f);
});
$('#btnSample').onclick = function () {
  if (!confirm('Load the sample house? Your current plan is replaced (export first if you want to keep it).')) return;
  snapshot();
  S.proj = sampleHouse();
  S.level = 0;
  select(null);
  renderAll();
  fitToPlan();
  save();
};
$('#btnReset').onclick = function () {
  if (!confirm('Clear everything and start with an empty plan?')) return;
  snapshot();
  S.proj = newProject('Our house');
  S.level = 0;
  select(null);
  renderAll();
  fitToPlan();
  save();
};
$('#btnUndo').onclick = undo;
$('#btnRedo').onclick = redo;
$('#btnDeselect').onclick = function () { select(null); };
$('#projectName').oninput = function () { S.proj.name = this.value; touch(); };

$('#btnWalkFromHere').onclick = function () {
  G.walk.x = G.orbit.target.x;
  G.walk.z = G.orbit.target.z;
  ensureWalkStart();
  setView('walk');
};
$('#btnTopDown').onclick = function () {
  G.orbit.pol = Math.PI / 2 - 0.05;
  G.orbit.az = -Math.PI / 2;
  var b = bounds();
  G.orbit.target.set((b.x0 + b.x1) / 2, 0, (b.y0 + b.y1) / 2);
  G.orbit.dist = clamp(Math.max(b.x1 - b.x0, b.y1 - b.y0) * 1.1, 4, 70);
};

window.addEventListener('resize', function () {
  if (S.view === 'plan') resizePlanCanvas(); else resize3D();
});

/* fps read-out, handy when the shadows start costing something */
setInterval(function () {
  if (S.view === 'plan' || !G.ready) return;
  $('#fpsLbl').textContent = G.fps ? G.fps + ' fps' : '';
}, 800);
(function fpsCounter() {
  var frames = 0, last = performance.now();
  function tick() {
    frames++;
    var now = performance.now();
    if (now - last > 1000) { G.fps = Math.round(frames * 1000 / (now - last)); frames = 0; last = now; }
    requestAnimationFrame(tick);
  }
  tick();
})();

/* ---------------------------------------------------------------- boot */
load().then(function (raw) {
  var loaded = null;
  if (raw) { try { loaded = migrate(JSON.parse(raw)); } catch (e) { loaded = null; } }
  S.proj = loaded || sampleHouse();
  if (!loaded) setSaveState('Sample house loaded');
  else setSaveState('Saved');
  renderAll();
  setTool('select');
  resizePlanCanvas();
  fitToPlan();
  if (window.THREE) { requestAnimationFrame(loop); }
  else { toast('3D library did not load — the plan still works', 'bad'); }
})['catch'](function (err) {
  S.proj = sampleHouse();
  renderAll();
  resizePlanCanvas();
  fitToPlan();
  requestAnimationFrame(loop);
  console.warn(err);
});

/* The photo of how the room looks today, pinned in the corner as you walk it. */
var lastPeekRoom = null;
function showRoomPhoto(roomId) {
  if (roomId === lastPeekRoom) return;
  lastPeekRoom = roomId;
  var box = $('#photoPeek');
  var photo = roomId ? S.proj.photos.filter(function (p) { return p.room === roomId; })[0] : null;
  if (!photo) { box.classList.add('hidden'); box.innerHTML = ''; return; }
  box.innerHTML = '<img src="' + esc(photo.src) + '" alt=""><div class="cap">' + esc(photo.name) +
    (photo.note ? ' — ' + esc(photo.note) : '') + '</div>';
  box.classList.remove('hidden');
}
