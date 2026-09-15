/* Arshmeister frame measurement harness.
 * Paste into devtools console on a youtube.com/watch page.
 * Read-only. Forces 1080p playback quality, changes nothing on the channel.
 *
 * Typical session:
 *   await seekTo(821);      // seek and pause on the target frame
 *   fillViewport();         // blow the player up to fill the window
 *   snap();                 // capture the paused frame to a canvas
 *   col(1375, 400, 700);    // column scan: finds horizontal lines and band edges
 *   rowCoverage(608, 120, 1000);  // is this row a drawn level or just candles
 *   gate(469, 592.5, 147, 4483.7, 11690.3, 0.056);  // validate before trusting anything
 *   magnify(0.68, 0.46, 6); // zoom a label to read its digits
 *
 * 2026-09-06: gate() patched. See docs/measurement/09-CORRECTIONS-2026-09-06.md C9.
 */

const player = () => document.querySelector('#movie_player');
const vid    = () => document.querySelector('video');

/* Seek to T, play through the frame so it repaints, then pause.
   Seeking while paused often leaves a stale frame from the previous seek. */
async function seekTo(T) {
  const p = player(), v = vid();
  try { p.setPlaybackQualityRange('hd1080','hd1080'); p.setPlaybackQuality('hd1080'); } catch (e) {}
  v.muted = true; v.playbackRate = 1;
  p.seekTo(Math.max(0, T - 3), true); p.playVideo();
  const t0 = Date.now();
  while (v.currentTime < T && Date.now() - t0 < 25000) await new Promise(r => setTimeout(r, 200));
  p.pauseVideo();
  try { p.setPlaybackQualityRange('hd1080','hd1080'); p.setPlaybackQuality('hd1080'); } catch (e) {}
  await new Promise(r => setTimeout(r, 1500));
  const out = { ct: Math.round(v.currentTime), w: v.videoWidth, h: v.videoHeight, q: p.getPlaybackQuality() };
  if (out.w !== 1920) console.warn('NOT 1080p, do not trust this frame:', out);
  return out;
}

/* Hide YouTube chrome and make the video fill the window. */
function fillViewport() {
  ['#masthead-container','#secondary','#below'].forEach(s => {
    const e = document.querySelector(s); if (e) e.style.display = 'none';
  });
  const v = vid();
  v.style.cssText = 'position:fixed!important;left:0!important;top:0!important;' +
    'width:' + innerWidth + 'px!important;height:' + innerHeight + 'px!important;' +
    'object-fit:contain!important;z-index:99999!important;background:#000!important';
  return v.getBoundingClientRect();
}

/* Magnify a point on the video. cx, cy are fractions of the VIDEO frame, 0 to 1.
   Display only: snap() reads the raw video element, so measurements stay in native
   1920x1080 coordinates no matter what this does. That is deliberate. It is what
   structurally prevents the project's number one error class, reading geometry in
   one view and a price in another.
   Resets any existing transform first, otherwise it reads a transformed rect
   and lands in the wrong place. */
function magnify(cx, cy, s) {
  const v = vid();
  v.style.setProperty('transform', 'none', 'important');
  void v.offsetWidth;
  const r  = v.getBoundingClientRect();
  const sc = Math.min(r.width / v.videoWidth, r.height / v.videoHeight);
  const dw = v.videoWidth * sc, dh = v.videoHeight * sc;
  const px = (r.width - dw) / 2 + cx * dw, py = (r.height - dh) / 2 + cy * dh;
  v.style.setProperty('transform-origin', '0 0', 'important');
  v.style.setProperty('transform',
    'translate(' + (innerWidth / 2 - px * s) + 'px,' + (innerHeight / 2 - py * s) + 'px) scale(' + s + ')',
    'important');
}

/* Capture the paused frame. Always re-snap after seeking. */
let G = null;
function snap() {
  const v = vid();
  const c = document.createElement('canvas');
  c.width = v.videoWidth; c.height = v.videoHeight;
  G = c.getContext('2d'); G.drawImage(v, 0, 0);
  return v.videoWidth + 'x' + v.videoHeight;
}

/* Column scan. Returns rows where the colour changes by more than `th`.
   Pick an x inside the object but clear of any label box.
   NOTE: each pixel is compared to the last REPORTED pixel, not the previous one.
   That is useful hysteresis on noise, but on a gradient it can drift a detected
   edge by a pixel. The stop-overshoot question turns on a 15 px signal. */
function col(x, y0, y1, th = 16) {
  const d = G.getImageData(x, y0, 1, y1 - y0).data, out = [];
  let pr = -1, pg = -1, pb = -1;
  for (let i = 0; i < y1 - y0; i++) {
    const r = d[i*4], g = d[i*4+1], b = d[i*4+2];
    if (Math.abs(r-pr) > th || Math.abs(g-pg) > th || Math.abs(b-pb) > th) {
      out.push((y0 + i) + ':' + r + ',' + g + ',' + b); pr = r; pg = g; pb = b;
    }
  }
  return out;
}

/* Row coverage. Distinguishes a drawn level from candles.
   Full-width solid line ~100% of scanned width, dashed ~55%, candles ~5%.
   CAVEAT: anything not near-white counts as coverage, so a row crossing a
   semi-transparent zone box fill reads high from the fill alone and looks like a
   drawn level. Zone boxes are what is being measured. Also inverts entirely on a
   dark chart theme. Sanity-check the avg colour it returns. */
function rowCoverage(y, x0, x1) {
  const d = G.getImageData(x0, y, x1 - x0, 1).data;
  let n = 0, sr = 0, sg = 0, sb = 0;
  for (let i = 0; i < x1 - x0; i++) {
    const r = d[i*4], g = d[i*4+1], b = d[i*4+2];
    if (!(r > 245 && g > 245 && b > 245)) { n++; sr += r; sg += g; sb += b; }
  }
  return { y, px: n, pct: +(100 * n / (x1 - x0)).toFixed(1),
           avg: n ? [Math.round(sr/n), Math.round(sg/n), Math.round(sb/n)] : null };
}

/* THE VALIDATION GATE. Run this before trusting any measurement on a frame.
 *
 * stopDist and targetDist MUST be the position tool's PRINTED LABEL values.
 * If you pass distances you derived from pixels through a single scale, then
 * `printed` IS the pixel ratio and the error is exactly zero, so the gate
 * returns PASS unconditionally and tells you nothing.
 *
 * The ratio test alone is SCALE-INVARIANT, so it cannot see a misread stop leg:
 * the error cancels in the comparison but still corrupts scalePerPx. That is how
 * the BNB 1D frame carried a 6.3% price-scale error through four passes
 * (12.6 read for a true 13.4). Pass `qty` and the risk check catches it: on this
 * trader's charts qty x stopDist is a constant 250.00 on every frame measured,
 * 2022-11 to 2025-06. See 09-CORRECTIONS-2026-09-06.md C5 and C9.
 */
function gate(entryRow, stopRow, targetRow, stopDist, targetDist, qty, expectedRisk = 250) {
  const measured = Math.abs(entryRow - targetRow) / Math.abs(stopRow - entryRow);
  const printed  = targetDist / stopDist;
  const err      = Math.abs(measured - printed) / printed;
  const scale    = stopDist / Math.abs(stopRow - entryRow);
  const risk     = (qty == null) ? null : qty * stopDist;
  const riskErr  = (risk == null) ? null : Math.abs(risk - expectedRisk) / expectedRisk;

  let verdict;
  if (err >= 0.02)              verdict = 'FAIL, treat frame as unreadable';
  else if (riskErr === null)    verdict = 'PASS (ratio only - pass qty to check the scale)';
  else if (riskErr >= 0.02)     verdict = 'FAIL, stop leg misread - the scale is wrong';
  else                          verdict = 'PASS';

  return { measured: +measured.toFixed(3), printed: +printed.toFixed(3),
           errPct: +(100 * err).toFixed(2), scalePerPx: scale,
           risk: risk === null ? null : +risk.toFixed(2),
           riskErrPct: riskErr === null ? null : +(100 * riskErr).toFixed(2),
           verdict };
}

/* Convert a row to a price once the frame has passed the gate. */
function priceAt(row, entryRow, entryPrice, scalePerPx) {
  return entryPrice + (entryRow - row) * scalePerPx;
}
