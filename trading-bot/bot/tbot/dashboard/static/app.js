/* tbot dashboard — vanilla JS, no build step.
 *
 * Three rules this file follows:
 *   1. Nothing is drawn as "live" unless the server says the feed is live and the data is not
 *      stale.  Every degraded state gets a banner in words, never a silently stale number.
 *   2. Every number that came out of the engine carries its rule IDs; they are one click away
 *      on every ticket and every rejection group.
 *   3. The forming bar is drawn in the chart but is never part of an analysis.  The server
 *      guarantees that; the chart labels it so the distinction is visible.
 */
'use strict';

const S = {
  settings: null,
  status: null,
  symbol: null,
  timeframe: null,
  analysis: null,      // the full /api/analysis envelope for the selected pair
  setups: [],
  rejections: null,
  overrides: {},       // pending edits in the Settings panel
  tab: 'setups',
  chart: null,
  candles: null,
  priceLines: [],
  formingBar: null,
};

const $ = (id) => document.getElementById(id);
const fmtNum = (v, d) => (v === null || v === undefined || Number.isNaN(v))
  ? '—' : Number(v).toLocaleString(undefined, { maximumFractionDigits: d ?? 6 });
const fmtPct = (v, d = 2) => (v === null || v === undefined) ? '—'
  : (v > 0 ? '+' : '') + Number(v).toFixed(d) + '%';
const fmtTime = (t) => t ? new Date(t * 1000).toISOString().replace('T', ' ').slice(0, 16) + 'Z' : '—';
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

async function api(path, opts) {
  const r = await fetch(path, opts);
  let body = null;
  try { body = await r.json(); } catch (e) { body = null; }
  if (!r.ok) {
    const detail = body && body.detail;
    const err = new Error(typeof detail === 'string' ? detail
      : (detail && detail.message) || `HTTP ${r.status}`);
    err.detail = detail;
    throw err;
  }
  return body;
}

/* ================================================================= banners */

function setBanner(kind, text) {
  let el = $('banner-bar');
  if (!el) {
    el = document.createElement('div');
    el.id = 'banner-bar';
    $('topbar').insertAdjacentElement('afterend', el);
    el.style.gridArea = 'top';
  }
  if (!text) { el.innerHTML = ''; el.style.display = 'none'; return; }
  el.style.display = 'block';
  el.innerHTML = `<div class="notice ${kind}">${esc(text)}</div>`;
}

function connectionWording(st) {
  if (!st) return { cls: 'bad', text: 'no server status', banner: null };
  const c = st.connection || {};
  const stale = (st.pairs || []).some((p) => p.data_stale);
  switch (c.status) {
    case 'live':
      if (stale) return { cls: 'warn', text: 'live · bars behind',
        banner: ['warn', 'Connected, but the newest bar is older than this timeframe should allow. Treat prices as not current.'] };
      return { cls: 'live', text: `live · ${esc(c.source)}`, banner: null };
    case 'replay':
      return { cls: 'replay', text: 'replay (offline)',
        banner: ['info', 'Offline replay data — deterministic synthetic candles, not a live market. Switch the source in Settings to go live.'] };
    case 'connecting':
      return { cls: 'warn', text: 'connecting…',
        banner: ['warn', 'Connecting to the exchange. Nothing on screen is live yet.'] };
    case 'reconnecting': {
      const inS = c.next_retry_at ? Math.max(0, Math.round(c.next_retry_at - (st.server_time || Date.now() / 1000))) : null;
      return { cls: 'bad', text: `reconnecting (${c.attempts})`,
        banner: ['bad', `Disconnected from ${c.source}. ${c.last_error || c.detail || ''} Retrying${inS !== null ? ` in ~${inS}s` : ''} (attempt ${c.attempts}). Prices below are the last ones received, not live.`] };
    }
    case 'rate_limited':
      return { cls: 'bad', text: 'rate limited',
        banner: ['bad', `${c.source} is rate-limiting us${c.retry_after ? `; backing off for ${Math.round(c.retry_after)}s` : ''}. No new candles until it clears — nothing below is live.`] };
    case 'error':
      return { cls: 'bad', text: 'feed error',
        banner: ['bad', `Feed error: ${c.last_error || c.detail}. Nothing below is live.`] };
    case 'stopped':
      return { cls: 'bad', text: 'feed stopped', banner: ['bad', 'The market feed is stopped.'] };
    default:
      return { cls: 'warn', text: c.status || 'idle',
        banner: ['warn', 'Waiting for the first candles.'] };
  }
}

function renderStatus(st) {
  S.status = st;
  const w = connectionWording(st);
  $('conn-dot').className = 'dot ' + w.cls;
  $('conn-text').textContent = w.text;
  setBanner(w.banner ? w.banner[0] : '', w.banner ? w.banner[1] : '');

  const c = (st && st.connection) || {};
  const cache = (st && st.cache) || {};
  $('feed-detail').innerHTML = [
    ['source', c.source], ['state', c.status],
    ['last message', c.seconds_since_message === null || c.seconds_since_message === undefined
      ? 'never' : `${Math.round(c.seconds_since_message)}s ago`],
    ['messages', c.messages], ['reconnects', c.attempts],
    ['pipeline passes', cache.computed], ['cache hits', cache.cache_hits],
    ['coalesced', cache.coalesced], ['throttled', cache.throttled],
    ['pass errors', cache.errors],
  ].map(([k, v]) => `<div style="display:flex;justify-content:space-between;gap:8px">
      <span>${esc(k)}</span><span style="font-family:var(--mono);color:var(--fg)">${esc(v ?? '—')}</span></div>`).join('');
}

/* ================================================================= chart */

function makeChart() {
  if (!window.LightweightCharts) {
    $('chart-empty').style.display = 'grid';
    $('chart-empty').innerHTML =
      `<div><h3>Chart library did not load</h3>
       <p>The page could not reach the CDN that serves TradingView Lightweight Charts.<br>
       Every panel below still works — only the chart drawing is affected.</p></div>`;
    return null;
  }
  const chart = LightweightCharts.createChart($('chart'), {
    layout: { background: { color: '#0b0f16' }, textColor: '#93a3bd', fontSize: 11 },
    grid: { vertLines: { color: '#141d2e' }, horzLines: { color: '#141d2e' } },
    rightPriceScale: { borderColor: '#22304a', scaleMargins: { top: 0.12, bottom: 0.12 } },
    timeScale: { borderColor: '#22304a', timeVisible: true, secondsVisible: false, rightOffset: 6 },
    crosshair: { mode: 0 },
    autoSize: true,
  });
  // v4 and v5 name the series factory differently; support both.
  const opts = {
    upColor: '#26a69a', downColor: '#ef5350', borderVisible: false,
    wickUpColor: '#26a69a', wickDownColor: '#ef5350',
  };
  const candles = chart.addCandlestickSeries
    ? chart.addCandlestickSeries(opts)
    : chart.addSeries(LightweightCharts.CandlestickSeries, opts);

  chart.timeScale().subscribeVisibleTimeRangeChange(drawOverlay);
  chart.timeScale().subscribeVisibleLogicalRangeChange(drawOverlay);
  new ResizeObserver(() => { sizeOverlay(); drawOverlay(); }).observe($('chartwrap'));
  S.chart = chart; S.candles = candles;
  sizeOverlay();
  return chart;
}

function sizeOverlay() {
  const cv = $('overlay');
  const r = $('chartwrap').getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  cv.width = Math.max(1, Math.round(r.width * dpr));
  cv.height = Math.max(1, Math.round(r.height * dpr));
  cv.style.width = r.width + 'px';
  cv.style.height = r.height + 'px';
}

function clearPriceLines() {
  if (!S.candles) return;
  S.priceLines.forEach((l) => { try { S.candles.removePriceLine(l); } catch (e) {} });
  S.priceLines = [];
}

function addPriceLine(price, color, title, style) {
  if (!S.candles || price === null || price === undefined) return;
  try {
    S.priceLines.push(S.candles.createPriceLine({
      price: Number(price), color, lineWidth: 1,
      lineStyle: style === undefined ? 2 : style,
      axisLabelVisible: true, title,
    }));
  } catch (e) { /* a price outside the scale is not worth breaking the page over */ }
}

function setChartData() {
  if (!S.candles || !S.analysis) return;
  const rows = (S.analysis.candles || []).slice();
  if (!rows.length) return;
  S.candles.setData(rows.map((c) => ({
    time: c.time, open: c.open, high: c.high, low: c.low, close: c.close,
  })));
  applyForming(S.analysis.forming);
  drawLevelLines();
  drawOverlay();
}

function applyForming(bar) {
  S.formingBar = bar || null;
  if (!S.candles || !bar) return;
  // Drawn, never analysed: the server builds the engine's Series from closed bars only.
  try {
    S.candles.update({ time: bar.time, open: bar.open, high: bar.high, low: bar.low, close: bar.close });
  } catch (e) {}
  $('chart-price').textContent = `last ${fmtNum(bar.close, 6)} · forming bar (not analysed)`;
}

function drawLevelLines() {
  clearPriceLines();
  const a = S.analysis && S.analysis.analysis;
  if (!a) return;
  const ov = a.overlays || {};

  (ov.levels || []).forEach((l) => {
    if (l.sloped) return;
    const flip = l.flip_state && l.flip_state !== 'none';
    addPriceLine(l.price, flip ? '#c084fc' : '#7dd3fc',
      `${l.level_kind}${l.touch_count ? ` ×${l.touch_count}` : ''}`, 2);
  });
  (ov.range_levels || []).forEach((l) => addPriceLine(l.price, '#64748b', 'range', 3));
  (ov.fibs || []).forEach((f) => {
    if (f.in_golden_pocket) addPriceLine(f.price, '#fbbf24', `fib ${f.ratio}`, 3);
  });
  if (a.bias_level) addPriceLine(a.bias_level.price, '#f472b6', 'bias invalidation', 1);

  // the selected plan's ladder, stop and targets
  const plan = selectedPlan();
  if (plan) {
    plan.entries.forEach((e) => addPriceLine(e.price, '#e2e8f0',
      `${e.kind} ${e.size_pct}%`, e.kind === 'dca' ? 2 : 0));
    addPriceLine(plan.stop_price, '#ef4444',
      plan.stop_is_synthetic ? 'stop (synthetic)' : 'stop', 0);
    plan.take_profits.forEach((t) => addPriceLine(t.price, '#22c55e', `TP${t.index} ${t.size_pct}%`, 0));
  }
}

function selectedPlan() {
  const a = S.analysis && S.analysis.analysis;
  if (!a || !a.plans || !a.plans.length) return null;
  const wanted = S.selectedPlanId;
  return a.plans.find((p) => p.id === wanted) || a.plans[0];
}

function drawOverlay() {
  const cv = $('overlay');
  const ctx = cv.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  const W = cv.width / dpr, H = cv.height / dpr;
  ctx.clearRect(0, 0, W, H);

  const a = S.analysis && S.analysis.analysis;
  if (!a || !S.chart || !S.candles) return;
  const ts = S.chart.timeScale();
  const vr = ts.getVisibleRange();
  if (!vr) return;

  const xAt = (t) => {
    if (t === null || t === undefined) return null;
    const c = ts.timeToCoordinate(t);
    if (c !== null) return c;
    return t < vr.from ? 0 : W;
  };
  const yAt = (p) => {
    const c = S.candles.priceToCoordinate(Number(p));
    return c === null ? null : c;
  };

  const box = (x1, x2, yTop, yBot, fill, stroke, dashed) => {
    if (yTop === null || yBot === null) return;
    const left = Math.max(0, Math.min(x1, x2));
    const right = Math.min(W, Math.max(x1, x2));
    if (right <= left) return;
    const top = Math.min(yTop, yBot), h = Math.max(1, Math.abs(yBot - yTop));
    ctx.fillStyle = fill;
    ctx.fillRect(left, top, right - left, h);
    ctx.save();
    ctx.strokeStyle = stroke;
    ctx.lineWidth = 1;
    if (dashed) ctx.setLineDash([4, 3]);
    ctx.strokeRect(left + 0.5, top + 0.5, right - left - 1, h - 1);
    ctx.restore();
  };

  const ov = a.overlays || {};

  // --- supply/demand zones: supply red, demand grey (the source colour convention)
  (ov.zones || []).forEach((z) => {
    const dead = z.is_dead;
    const supply = z.side === 'supply';
    const base = supply ? '239,68,68' : '148,163,184';
    const alpha = dead ? 0.05 : (z.zone_class === 'continuation' ? 0.17 : 0.11);
    const x1 = xAt(z.start_time);
    box(x1 === null ? 0 : x1, W, yAt(z.top), yAt(z.bottom),
      `rgba(${base},${alpha})`, `rgba(${base},${dead ? 0.28 : 0.62})`, dead);
    const y = yAt(supply ? z.top : z.bottom);
    if (y !== null) {
      ctx.fillStyle = `rgba(${base},${dead ? 0.45 : 0.95})`;
      ctx.font = '10px ui-monospace, monospace';
      const label = `${z.side} ${z.zone_class}${z.fill_pct ? ` · ${Math.round(z.fill_pct)}% filled` : ''}${dead ? ' · dead' : ''}`;
      ctx.fillText(label, Math.max(4, (x1 === null ? 0 : x1) + 4), y + (supply ? -3 : 11));
    }
  });

  // --- order blocks: cyan
  (ov.order_blocks || []).forEach((o) => {
    const dead = o.is_dead;
    const x1 = xAt(o.start_time);
    box(x1 === null ? 0 : x1, W, yAt(o.top), yAt(o.bottom),
      `rgba(34,211,238,${dead ? 0.04 : 0.13})`, `rgba(34,211,238,${dead ? 0.25 : 0.68})`, dead);
  });

  // --- trend lines (sloped levels)
  ctx.save();
  ctx.lineWidth = 1.4;
  ctx.setLineDash([6, 4]);
  ctx.strokeStyle = '#fbbf24';
  (ov.trendlines || []).concat((ov.levels || []).filter((l) => l.sloped)).forEach((l) => {
    if (!l.from || !l.to) return;
    const x1 = xAt(l.from.time), x2 = xAt(l.to.time);
    const y1 = yAt(l.from.price), y2 = yAt(l.to.price);
    if (x1 === null || x2 === null || y1 === null || y2 === null) return;
    ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke();
  });
  ctx.restore();

  // --- ranges
  ctx.save();
  ctx.setLineDash([2, 4]);
  ctx.strokeStyle = 'rgba(148,163,184,.5)';
  (ov.ranges || []).filter((r) => !r.dead).forEach((r) => {
    [r.high, r.low].forEach((p) => {
      const y = yAt(p);
      if (y === null) return;
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke();
    });
  });
  ctx.restore();

  // --- forming-bar marker: the boundary the engine will not cross
  if (S.formingBar) {
    const x = xAt(S.formingBar.time);
    if (x !== null) {
      ctx.save();
      ctx.strokeStyle = 'rgba(148,163,184,.45)';
      ctx.setLineDash([3, 3]);
      ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke();
      ctx.fillStyle = 'rgba(148,163,184,.85)';
      ctx.font = '10px ui-monospace, monospace';
      ctx.fillText('forming — not analysed', Math.min(W - 130, x + 4), 14);
      ctx.restore();
    }
  }
}

/* ================================================================= watchlist */

function trendTag(t) {
  if (!t) return '';
  const cls = t === 'up' ? 'up' : t === 'down' ? 'down' : '';
  return `<span class="tag ${cls}">${esc(t)}</span>`;
}

function renderWatchlist(rows) {
  $('wl-count').textContent = `${rows.length}`;
  if (!rows.length) { $('wl-rows').innerHTML = '<div class="empty">no pairs configured</div>'; return; }
  $('wl-rows').innerHTML = rows.map((r) => {
    const active = r.symbol === S.symbol && r.timeframe === S.timeframe;
    const nz = r.nearest_zone;
    const zoneBit = nz
      ? `<span class="tag ${nz.side}">${esc(nz.side)} ${fmtNum(nz.edge, 6)}</span>
         <span class="tag">${fmtPct(r.distance_pct)}</span>`
      : '<span class="tag">no live zone</span>';
    const setupBit = r.live_setups
      ? `<span class="tag live">${r.live_setups} setup${r.live_setups > 1 ? 's' : ''}</span>` : '';
    const staleBit = r.data_stale ? '<span class="tag stale">stale</span>' : '';
    const statusBit = (r.status !== 'ready')
      ? `<span class="tag">${esc(r.status)}</span>` : '';
    return `<div class="wl-row ${active ? 'active' : ''}" data-sym="${esc(r.symbol)}" data-tf="${esc(r.timeframe)}">
      <div class="wl-head">
        <span class="wl-sym">${esc(r.symbol)}</span>
        <span class="wl-tf">${esc(r.timeframe)}</span>
        <span class="wl-price">${fmtNum(r.last_price, 6)}</span>
      </div>
      <div class="wl-meta">
        ${trendTag(r.trend)}${r.regime ? `<span class="tag">${esc(r.regime)}</span>` : ''}
        ${zoneBit}${setupBit}${staleBit}${statusBit}
      </div>
      ${r.error ? `<div class="sub" style="color:#fca5a5">${esc(r.error)}</div>` : ''}
    </div>`;
  }).join('');
  $('wl-rows').querySelectorAll('.wl-row').forEach((el) => {
    el.onclick = () => selectPair(el.dataset.sym, el.dataset.tf);
  });
}

/* ================================================================= setups */

function ruleChips(ids, limit) {
  const list = (ids || []).slice(0, limit || 40);
  if (!list.length) return '<span class="sub">no rule ids recorded</span>';
  return `<div class="rules">${list.map((r) =>
    `<span class="rule ${/^(CF|S\d)/.test(r) ? 'hi' : ''}">${esc(r)}</span>`).join('')}</div>`;
}

function ticketHtml(p) {
  const dir = p.direction;
  const rr = p.rr_to_tp1;
  const conv = p.conviction || (p.setup && p.setup.conviction);
  const stale = p.stale ? '<span class="tag stale">recomputing</span>' : '';
  const legs = p.entries.map((e) => `<tr>
      <td>${e.index}</td><td>${esc(e.kind)}</td>
      <td class="num">${fmtNum(e.price, 6)}</td>
      <td class="num">${e.size_pct}%</td>
      <td class="sub" title="the level this leg leans on">${esc(e.level_id)}</td>
    </tr>`).join('');
  const tps = p.take_profits.map((t) => `<tr>
      <td>TP${t.index}</td><td class="num">${fmtNum(t.price, 6)}</td>
      <td class="num">${t.size_pct}%</td>
      <td class="sub">${esc(t.level_id || 'structural')}</td>
    </tr>`).join('');
  const classes = (p.confluence_classes || []).map((c) => `<span class="rule">${esc(c)}</span>`).join('');

  return `<article class="ticket" data-plan="${esc(p.id)}">
    <header class="ticket-head ${dir}">
      <span class="dir ${dir}">${dir.toUpperCase()}</span>
      <strong>${esc(p.symbol)}</strong>
      <span class="tag">${esc(p.timeframe || S.timeframe)}</span>
      <span class="tag">${esc(p.trade_class)} / ${esc(p.vehicle)}${p.leverage && p.leverage !== 1 ? ` ${p.leverage}x` : ''}</span>
      <span class="tag ${conv === 'high' ? 'live' : ''}">${esc(conv || 'normal')} conviction</span>
      ${stale}
    </header>
    <div class="ticket-body">
      <dl class="kv">
        <dt title="R:R measured from the planned average entry to TP1 (CF-42)">R:R to TP1</dt>
        <dd>${fmtNum(rr, 2)}</dd>
        <dt title="§6 confluence score and the classes behind it (CF-31, P14)">confluence</dt>
        <dd>${fmtNum(p.confluence_score, 2)} <span class="sub">${classes}</span></dd>
        <dt>planned avg entry</dt><dd>${fmtNum(p.planned_average_entry, 6)}</dd>
        <dt>position size</dt>
        <dd>${fmtNum(p.qty_total, 6)} <span class="sub">≈ $${fmtNum(p.notional_usd, 2)} · risk ${fmtNum(p.risk_budget_pct, 2)}%</span></dd>
        <dt>expected move</dt><dd>${fmtPct(p.expected_move_pct)}</dd>
        ${p.distance_to_entry_pct !== undefined && p.distance_to_entry_pct !== null
          ? `<dt>distance to entry</dt><dd>${fmtPct(p.distance_to_entry_pct)}</dd>` : ''}
      </dl>

      <div>
        <table class="legs">
          <thead><tr><th>#</th><th>leg</th><th class="num">price</th><th class="num">size</th><th>on level</th></tr></thead>
          <tbody>${legs}</tbody>
        </table>
      </div>

      <div>
        <table class="legs">
          <thead><tr><th colspan="4">stop &amp; targets</th></tr></thead>
          <tbody>
            <tr><td>STOP</td><td class="num" style="color:#fca5a5">${fmtNum(p.stop_price, 6)}</td>
                <td class="num">100%</td>
                <td class="sub">${p.stop_is_synthetic ? 'synthetic — spot exit is close-below-then-flip (CF-05)' : 'structural (CF-14)'}</td></tr>
            ${tps}
          </tbody>
        </table>
        ${p.spot_exit_rule ? `<div class="sub">spot exit rule: ${esc(p.spot_exit_rule)}</div>` : ''}
      </div>

      <details class="why">
        <summary>Why this trade — rule IDs behind every number</summary>
        <div style="display:grid;gap:8px;margin-top:7px">
          <div><div class="sub">plan ${esc(p.id)}</div>${ruleChips(p.source_ids)}</div>
          ${p.setup ? `<div><div class="sub">setup ${esc(p.setup.id)} · entry family ${esc(p.setup.entry_family)} · structure ${esc(p.setup.structure_tf)}</div>${ruleChips(p.setup.source_ids)}</div>` : ''}
          ${p.setup && p.setup.object_ids && p.setup.object_ids.length
            ? `<div><div class="sub">confluence objects</div>${ruleChips(p.setup.object_ids)}</div>` : ''}
          <div class="sub">invalidation level: ${esc(p.invalidation_level_id)}${
            p.bias_invalidation_price ? ` · bias invalidation ${fmtNum(p.bias_invalidation_price, 6)}` : ''}</div>
        </div>
      </details>
    </div>
  </article>`;
}

function renderSetups() {
  const list = S.setups || [];
  $('badge-setups').textContent = list.length;
  const el = $('panel-setups');
  if (!list.length) {
    el.innerHTML = `<div class="empty">No qualified trade plans right now.<br>
      <span class="sub">Every candidate that got close is in <b>Rejected</b>, with the gate that stopped it.</span></div>`;
    return;
  }
  el.innerHTML = list.map(ticketHtml).join('');
  el.querySelectorAll('.ticket').forEach((node) => {
    node.onclick = () => {
      S.selectedPlanId = node.dataset.plan;
      drawLevelLines();
      drawOverlay();
    };
  });
}

/* ================================================================= rejected */

function renderRejected(data) {
  const groups = (data && data.groups) || [];
  const total = (data && data.total) || 0;
  $('badge-rejected').textContent = total;
  const el = $('panel-rejected');
  if (!groups.length) {
    el.innerHTML = `<div class="empty">Nothing was rejected on the last closed bar.<br>
      <span class="sub">This panel fills up when candidates form and a gate stops them.</span></div>`;
    return;
  }
  const head = `<p class="sub" style="margin:0 0 10px">
    <b>${total}</b> near-miss${total === 1 ? '' : 'es'} on the last closed bar, grouped by the gate
    that stopped them. The gate with the biggest share is the one deciding what you trade.</p>`;

  el.innerHTML = head + groups.map((g, i) => {
    const reasons = (g.reasons || []).map((r) => `
      <div class="reason">
        <div class="reason-head">
          <span class="reason-name">${esc(r.reason)}</span>
          <span class="reason-n">${r.count}×</span>
        </div>
        <div class="reason-text">${esc(r.text)}</div>
        ${r.examples && r.examples.length ? `<div class="examples">${
          r.examples.map((x) => `<div class="example">${esc(x.symbol || '')} ${esc(x.direction || '')} · ${esc(x.setup_id || '')}${
            x.detail ? `<br>${esc(x.detail)}` : ''}</div>`).join('')}</div>` : ''}
        ${ruleChips(r.source_ids, 16)}
      </div>`).join('');

    const keys = (g.config_keys || []).map((k) =>
      `<span class="keychip" data-key="${esc(k)}" title="jump to this key in Settings">${esc(k)}</span>`).join('');

    return `<details class="gate" ${i === 0 ? 'open' : ''}>
      <summary>
        <span class="gate-id">${esc(g.gate)}</span>
        <span class="gate-title">${esc(g.title)}</span>
        <span class="gate-count">${g.count} · ${g.share_pct}%</span>
      </summary>
      <div class="bar"><i style="width:${Math.max(2, g.share_pct)}%"></i></div>
      <div class="gate-body">
        <div class="gate-what">${esc(g.what)}</div>
        ${reasons}
        ${keys ? `<div><div class="sub">keys that move this gate</div><div class="keychips">${keys}</div></div>` : ''}
        <div class="gate-loosen"><b>If you loosen it:</b> ${esc(g.loosening)}</div>
      </div>
    </details>`;
  }).join('');

  el.querySelectorAll('.keychip').forEach((chip) => {
    chip.onclick = () => {
      switchTab('settings');
      $('cfg-search').value = chip.dataset.key;
      searchConfig();
    };
  });
}

/* ================================================================= settings */

function renderSettings(data) {
  const s = data.settings;
  S.settings = s;
  S.overrides = Object.assign({}, s.overrides);

  $('set-pairs').value = s.pairs.join('\n');
  $('set-history').value = s.history_bars;
  $('set-source').innerHTML = s.available_sources
    .map((x) => `<option ${x === s.source ? 'selected' : ''}>${esc(x)}</option>`).join('');
  $('set-tfs').innerHTML = s.available_timeframes.map((tf) =>
    `<span class="chip ${s.timeframes.includes(tf) ? 'on' : ''}" data-tf="${esc(tf)}">${esc(tf)}</span>`).join('');
  $('set-tfs').querySelectorAll('.chip').forEach((c) => {
    c.onclick = () => c.classList.toggle('on');
  });

  $('tunables').innerHTML = data.tunables.map((grp) => `
    <div class="group-title">${esc(grp.group)}</div>
    ${grp.keys.map(cfgRowHtml).join('')}`).join('');
  bindCfgRows($('tunables'));

  // top-bar selectors
  $('sel-pair').innerHTML = s.pairs.map((p) =>
    `<option ${p === S.symbol ? 'selected' : ''}>${esc(p)}</option>`).join('');
  $('sel-tf').innerHTML = s.timeframes.map((t) =>
    `<option ${t === S.timeframe ? 'selected' : ''}>${esc(t)}</option>`).join('');
}

function cfgRowHtml(k) {
  let input;
  if (k.members && k.members.length) {
    input = `<select data-key="${esc(k.key)}">${k.members.map((m) =>
      `<option ${String(m) === String(k.value) ? 'selected' : ''}>${esc(m)}</option>`).join('')}</select>`;
  } else if (k.type === 'bool') {
    input = `<select data-key="${esc(k.key)}">
      <option value="true" ${k.value === true ? 'selected' : ''}>true</option>
      <option value="false" ${k.value === false ? 'selected' : ''}>false</option></select>`;
  } else if (k.type === 'int' || k.type === 'float') {
    input = `<input type="number" data-key="${esc(k.key)}" value="${esc(k.value)}"
      step="${k.type === 'int' ? 1 : 'any'}"
      ${k.minimum !== null && k.minimum !== undefined ? `min="${k.minimum}"` : ''}
      ${k.maximum !== null && k.maximum !== undefined ? `max="${k.maximum}"` : ''}>`;
  } else {
    input = `<input type="text" data-key="${esc(k.key)}" value="${esc(
      typeof k.value === 'object' ? JSON.stringify(k.value) : k.value)}">`;
  }
  const bounds = [k.minimum !== null && k.minimum !== undefined ? `min ${k.minimum}` : '',
                  k.maximum !== null && k.maximum !== undefined ? `max ${k.maximum}` : '']
                 .filter(Boolean).join(' · ');
  return `<div class="cfg" id="cfg-${esc(k.key)}">
    <div class="cfg-head">
      <span class="cfg-key ${k.overridden ? 'changed' : ''}" title="${esc(k.note || '')}">${esc(k.key)}</span>
      ${input}
    </div>
    <div class="cfg-meta">default ${esc(typeof k.default === 'object' ? JSON.stringify(k.default) : k.default)}${
      bounds ? ` · ${esc(bounds)}` : ''} · §${esc(k.group)} · ${esc(k.source_id)}</div>
  </div>`;
}

function bindCfgRows(root) {
  root.querySelectorAll('[data-key]').forEach((inp) => {
    inp.onchange = () => {
      const key = inp.dataset.key;
      let v = inp.value;
      if (inp.tagName === 'SELECT' && (v === 'true' || v === 'false')) v = (v === 'true');
      else if (inp.type === 'number') v = Number(v);
      else { try { v = JSON.parse(v); } catch (e) { /* keep the string */ } }
      S.overrides[key] = v;
      inp.closest('.cfg').querySelector('.cfg-key').classList.add('changed');
    };
  });
}

async function searchConfig() {
  const q = $('cfg-search').value.trim();
  if (!q) { $('cfg-results').innerHTML = ''; return; }
  const data = await api(`/api/config?grep=${encodeURIComponent(q)}&limit=40`);
  $('cfg-results').innerHTML = data.keys.length
    ? data.keys.map(cfgRowHtml).join('')
    : `<div class="sub" style="padding:8px 0">nothing matches “${esc(q)}” in ${data.total} keys</div>`;
  bindCfgRows($('cfg-results'));
}

async function saveSettings() {
  const msg = $('settings-msg');
  msg.className = ''; msg.textContent = 'applying…';
  const pairs = $('set-pairs').value.split(/\s|,/).map((x) => x.trim()).filter(Boolean);
  const tfs = [...$('set-tfs').querySelectorAll('.chip.on')].map((c) => c.dataset.tf);
  try {
    const data = await api('/api/settings', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        pairs, timeframes: tfs, source: $('set-source').value,
        history_bars: Number($('set-history').value), overrides: S.overrides,
      }),
    });
    renderSettings(data);
    msg.className = 'ok';
    msg.textContent = data.feed_restarted
      ? 'Applied. The feed reconnected and every watched pair is recomputing.'
      : 'Applied. Every watched pair is recomputing on its last closed bar.';
    if (!S.settings.pairs.includes(S.symbol)) S.symbol = S.settings.pairs[0];
    if (!S.settings.timeframes.includes(S.timeframe)) S.timeframe = S.settings.timeframes[0];
    setTimeout(refreshAll, 900);
  } catch (e) {
    msg.className = 'bad';
    const d = e.detail;
    msg.textContent = (d && d.problems)
      ? `${d.message}\n\n${d.problems.join('\n')}`
      : `Rejected — nothing changed.\n${e.message}`;
  }
}

/* ================================================================= data flow */

function switchTab(tab) {
  S.tab = tab;
  document.querySelectorAll('#tabs button').forEach((b) =>
    b.classList.toggle('active', b.dataset.tab === tab));
  document.querySelectorAll('.panel').forEach((p) =>
    p.classList.toggle('active', p.id === 'panel-' + tab));
  if (tab === 'rejected') loadRejections();
}

async function selectPair(symbol, tf) {
  S.symbol = symbol; S.timeframe = tf; S.selectedPlanId = null;
  $('sel-pair').value = symbol; $('sel-tf').value = tf;
  await loadAnalysis();
  await loadWatchlist();
  if (S.tab === 'rejected') loadRejections();
}

async function loadAnalysis(force) {
  if (!S.symbol || !S.timeframe) return;
  $('chart-title').textContent = `${S.symbol} ${S.timeframe}`;
  let env;
  try {
    env = await api(`/api/analysis?symbol=${encodeURIComponent(S.symbol)}&timeframe=${encodeURIComponent(S.timeframe)}${force ? '&refresh=true' : ''}`);
  } catch (e) {
    $('chart-empty').style.display = 'grid';
    $('chart-empty').innerHTML = `<div><h3>Could not load ${esc(S.symbol)} ${esc(S.timeframe)}</h3><p>${esc(e.message)}</p></div>`;
    return;
  }
  S.analysis = env;
  const a = env.analysis;
  $('chart-empty').style.display = (env.ok || (env.candles || []).length) ? 'none' : 'grid';
  if (!env.ok) {
    $('chart-empty').innerHTML = `<div><h3>No analysis yet</h3><p>${esc(env.error || 'waiting for closed bars')}</p></div>`;
  }
  setChartData();

  if (a) {
    $('bar-time').textContent = fmtTime(a.meta.bar_time);
    const regime = a.regime ? ` · regime ${a.regime.state}${a.regime.risk_on ? '' : ' (risk-off)'}` : '';
    $('chart-trend').textContent = `trend ${a.trend} · structure ${a.structure_trend}${regime}`;
    if (!S.formingBar) $('chart-price').textContent = `last close ${fmtNum(a.meta.last_close, 6)}`;
    S.setups = (a.plans || []).map((p) => Object.assign({}, p, {
      timeframe: S.timeframe, stale: env.stale,
    }));
    renderSetups();
    if (S.tab === 'rejected') renderRejected({ groups: env.rejection_groups || [], total: (a.rejections || []).length });
    else $('badge-rejected').textContent = (a.rejections || []).length;
  } else {
    S.setups = []; renderSetups();
  }
  if (env.stale) {
    setBanner('warn', `Showing the analysis of an earlier bar for ${S.symbol} ${S.timeframe} — a fresh pass is running.`);
  }
}

async function loadWatchlist() {
  try {
    const data = await api('/api/watchlist');
    renderWatchlist(data.rows);
    renderStatus(data.status);
  } catch (e) { /* the status banner already covers a dead server */ }
}

async function loadRejections() {
  try {
    const data = await api(`/api/rejections?symbol=${encodeURIComponent(S.symbol || '')}&timeframe=${encodeURIComponent(S.timeframe || '')}`);
    S.rejections = data;
    renderRejected(data);
  } catch (e) { /* keep whatever is on screen */ }
}

async function refreshAll() {
  await loadWatchlist();
  await loadAnalysis();
  if (S.tab === 'rejected') await loadRejections();
}

/* ================================================================= websocket */

function connectWs() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  const ws = new WebSocket(`${proto}://${location.host}/ws`);
  let alive = null;
  ws.onopen = () => {
    alive = setInterval(() => { try { ws.send(JSON.stringify({ type: 'ping' })); } catch (e) {} }, 20000);
  };
  ws.onmessage = (ev) => {
    let msg; try { msg = JSON.parse(ev.data); } catch (e) { return; }
    if (msg.type === 'status') renderStatus(msg.status);
    else if (msg.type === 'tick') {
      if (msg.symbol === S.symbol && msg.timeframe === S.timeframe) {
        applyForming(msg.forming);
        drawOverlay();
      }
    } else if (msg.type === 'analysis') {
      if (msg.symbol === S.symbol && msg.timeframe === S.timeframe) loadAnalysis();
      loadWatchlist();
    } else if (msg.type === 'settings') {
      api('/api/settings').then(renderSettings).catch(() => {});
    }
  };
  ws.onclose = () => {
    if (alive) clearInterval(alive);
    // the page's own connection to the server, not the exchange one
    setTimeout(connectWs, 2500);
  };
  ws.onerror = () => { try { ws.close(); } catch (e) {} };
}

/* ================================================================= boot */

async function boot() {
  makeChart();
  document.querySelectorAll('#tabs button').forEach((b) => {
    b.onclick = () => switchTab(b.dataset.tab);
  });
  $('btn-refresh').onclick = () => loadAnalysis(true);
  $('btn-save').onclick = saveSettings;
  $('btn-reset').onclick = () => { S.overrides = {}; saveSettings(); };
  $('sel-pair').onchange = () => selectPair($('sel-pair').value, S.timeframe);
  $('sel-tf').onchange = () => selectPair(S.symbol, $('sel-tf').value);
  let t = null;
  $('cfg-search').oninput = () => { clearTimeout(t); t = setTimeout(searchConfig, 250); };

  const data = await api('/api/settings');
  S.symbol = data.settings.pairs[0];
  S.timeframe = data.settings.timeframes[0];
  renderSettings(data);
  await refreshAll();
  connectWs();
  setInterval(loadWatchlist, 15000);
}

boot().catch((e) => setBanner('bad', `Dashboard failed to start: ${e.message}`));
