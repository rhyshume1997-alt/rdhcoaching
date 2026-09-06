// POST /api/product-lookup  { url }
// Reads a public product page server-side and hands back the bits the house
// planner needs: name, photo, price and any dimensions printed on the page.
// A browser cannot do this itself — shops do not send CORS headers.
//
// The page is fetched with no credentials, only over https, only to public
// addresses, and only the parsed fields come back. Nothing is stored.

const dns = require('dns').promises;

const MAX_HTML_BYTES = 1_500_000;
const MAX_IMAGE_BYTES = 900_000;
const FETCH_TIMEOUT_MS = 8000;
const MAX_REDIRECTS = 4;
const UA = 'Mozilla/5.0 (compatible; HomeStudio/1.0; +https://www.rdhcoaching.com)';

const ALLOWED_ORIGIN_HOSTS = [
  'www.rdhcoaching.com',
  'rdhcoaching.com',
  'localhost',
  '127.0.0.1'
];

// Very small per-instance throttle. Serverless instances are short-lived, so
// this is a speed bump rather than a wall.
const hits = new Map();
const RATE_LIMIT = 40;
const RATE_WINDOW_MS = 60_000;

function json(res, status, payload) {
  res.setHeader('Content-Type', 'application/json');
  res.setHeader('Cache-Control', 'no-store');
  return res.status(status).json(payload);
}

function rateLimited(ip) {
  const now = Date.now();
  const rec = hits.get(ip);
  if (!rec || now - rec.start > RATE_WINDOW_MS) {
    hits.set(ip, { start: now, n: 1 });
    if (hits.size > 500) hits.clear();
    return false;
  }
  rec.n += 1;
  return rec.n > RATE_LIMIT;
}

function originAllowed(req) {
  const origin = req.headers.origin;
  if (!origin) return true; // non-browser callers still face the rate limit
  try {
    const host = new URL(origin).hostname;
    return ALLOWED_ORIGIN_HOSTS.includes(host) || /\.vercel\.app$/.test(host);
  } catch (e) {
    return false;
  }
}

// Blocks loopback, private, link-local and other non-public destinations so
// this endpoint cannot be pointed at anything internal.
function isPrivateAddress(addr, family) {
  if (family === 6) {
    const a = addr.toLowerCase();
    if (a === '::1' || a === '::') return true;
    if (a.startsWith('fe80') || a.startsWith('fc') || a.startsWith('fd')) return true;
    const mapped = a.match(/^::ffff:(\d+\.\d+\.\d+\.\d+)$/);
    if (mapped) return isPrivateAddress(mapped[1], 4);
    return false;
  }
  const p = addr.split('.').map(Number);
  if (p.length !== 4 || p.some(n => Number.isNaN(n))) return true;
  if (p[0] === 10 || p[0] === 127 || p[0] === 0) return true;
  if (p[0] === 169 && p[1] === 254) return true;
  if (p[0] === 172 && p[1] >= 16 && p[1] <= 31) return true;
  if (p[0] === 192 && p[1] === 168) return true;
  if (p[0] === 100 && p[1] >= 64 && p[1] <= 127) return true;
  if (p[0] >= 224) return true;
  return false;
}

async function assertPublicHost(hostname) {
  let addrs;
  try {
    addrs = await dns.lookup(hostname, { all: true });
  } catch (e) {
    throw new Error('That address could not be found.');
  }
  if (!addrs.length) throw new Error('That address could not be found.');
  for (const a of addrs) {
    if (isPrivateAddress(a.address, a.family)) throw new Error('That address is not reachable from here.');
  }
}

// Follows redirects by hand so every hop is checked, not just the first.
async function safeFetch(startUrl, accept, maxBytes) {
  let url = startUrl;
  for (let hop = 0; hop <= MAX_REDIRECTS; hop++) {
    const parsed = new URL(url);
    if (parsed.protocol !== 'https:' && parsed.protocol !== 'http:') throw new Error('Only http(s) links work here.');
    await assertPublicHost(parsed.hostname);

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
    let res;
    try {
      res = await fetch(url, {
        redirect: 'manual',
        signal: controller.signal,
        headers: {
          'User-Agent': UA,
          Accept: accept,
          'Accept-Language': 'en-GB,en;q=0.9'
        }
      });
    } finally {
      clearTimeout(timer);
    }

    if (res.status >= 300 && res.status < 400) {
      const loc = res.headers.get('location');
      if (!loc) throw new Error('That page kept redirecting.');
      url = new URL(loc, url).toString();
      continue;
    }
    if (!res.ok) throw new Error('That page came back as ' + res.status + '.');

    const buf = Buffer.from(await res.arrayBuffer());
    if (buf.length > maxBytes) throw new Error('That page is too big to read.');
    return { buf, finalUrl: url, type: res.headers.get('content-type') || '' };
  }
  throw new Error('That page kept redirecting.');
}

function pickMeta(html, names) {
  for (const name of names) {
    const re = new RegExp(
      '<meta[^>]+(?:property|name|itemprop)\\s*=\\s*["\']' + name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') +
      '["\'][^>]*>', 'i'
    );
    const tag = html.match(re);
    if (!tag) continue;
    const content = tag[0].match(/content\s*=\s*["']([^"']*)["']/i);
    if (content && content[1].trim()) return content[1].trim();
  }
  return '';
}

function decodeEntities(s) {
  return String(s || '')
    .replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"').replace(/&#0?39;|&apos;/g, "'").replace(/&nbsp;/g, ' ')
    .replace(/&#(\d+);/g, (m, d) => String.fromCharCode(Number(d)));
}

// Product pages usually carry JSON-LD; it is the most reliable source.
function readJsonLd(html) {
  const out = { title: '', image: '', price: null, currency: '', brand: '', description: '' };
  const blocks = html.match(/<script[^>]+application\/ld\+json[^>]*>([\s\S]*?)<\/script>/gi) || [];
  for (const block of blocks) {
    const body = block.replace(/^[\s\S]*?>/, '').replace(/<\/script>$/i, '');
    let data;
    try { data = JSON.parse(body); } catch (e) { continue; }
    const queue = Array.isArray(data) ? data.slice() : [data];
    while (queue.length) {
      const node = queue.shift();
      if (!node || typeof node !== 'object') continue;
      if (Array.isArray(node['@graph'])) queue.push(...node['@graph']);
      const type = node['@type'];
      const isProduct = type === 'Product' || (Array.isArray(type) && type.includes('Product'));
      if (!isProduct) continue;
      if (!out.title && typeof node.name === 'string') out.title = node.name;
      if (!out.description && typeof node.description === 'string') out.description = node.description;
      if (!out.brand) {
        if (typeof node.brand === 'string') out.brand = node.brand;
        else if (node.brand && typeof node.brand.name === 'string') out.brand = node.brand.name;
      }
      if (!out.image) {
        const img = node.image;
        if (typeof img === 'string') out.image = img;
        else if (Array.isArray(img) && img.length) out.image = typeof img[0] === 'string' ? img[0] : (img[0] && img[0].url) || '';
        else if (img && typeof img.url === 'string') out.image = img.url;
      }
      const offers = Array.isArray(node.offers) ? node.offers[0] : node.offers;
      if (offers && out.price == null) {
        const raw = offers.price != null ? offers.price : (offers.lowPrice != null ? offers.lowPrice : null);
        const n = parseFloat(String(raw).replace(/[^\d.]/g, ''));
        if (!Number.isNaN(n)) out.price = n;
        if (typeof offers.priceCurrency === 'string') out.currency = offers.priceCurrency;
      }
    }
  }
  return out;
}

// "220 x 90 x 85 cm", "W 220cm D 90cm H 85cm", "Width: 2200 mm" — all common.
function readDimensions(text) {
  if (!text) return null;
  const t = decodeEntities(text).replace(/\s+/g, ' ');
  const unitToM = { mm: 0.001, cm: 0.01, m: 1, in: 0.0254, '"': 0.0254, ft: 0.3048, "'": 0.3048 };

  const triple = t.match(
    /(\d+(?:[.,]\d+)?)\s*(mm|cm|m|in|"|ft|')?\s*[x×]\s*(\d+(?:[.,]\d+)?)\s*(mm|cm|m|in|"|ft|')?\s*[x×]\s*(\d+(?:[.,]\d+)?)\s*(mm|cm|m|in|"|ft|')/i
  );
  if (triple) {
    const unit = (triple[6] || triple[4] || triple[2] || 'cm').toLowerCase();
    const k = unitToM[unit] || 0.01;
    const nums = [triple[1], triple[3], triple[5]].map(v => parseFloat(v.replace(',', '.')) * k);
    if (nums.every(n => n > 0.01 && n < 6)) return { w: round3(nums[0]), d: round3(nums[1]), h: round3(nums[2]) };
  }

  const labelled = {};
  const labelRe = /\b(width|depth|height|length|w|d|h|l)\b\s*[:=]?\s*(\d+(?:[.,]\d+)?)\s*(mm|cm|m|in|"|ft|')/gi;
  let m;
  while ((m = labelRe.exec(t))) {
    const key = m[1].toLowerCase()[0];
    const k = unitToM[m[3].toLowerCase()] || 0.01;
    const value = parseFloat(m[2].replace(',', '.')) * k;
    if (!(value > 0.01 && value < 6)) continue;
    if (key === 'w' && labelled.w == null) labelled.w = value;
    if ((key === 'd' || key === 'l') && labelled.d == null) labelled.d = value;
    if (key === 'h' && labelled.h == null) labelled.h = value;
  }
  if (labelled.w || labelled.d || labelled.h) {
    return {
      w: labelled.w ? round3(labelled.w) : null,
      d: labelled.d ? round3(labelled.d) : null,
      h: labelled.h ? round3(labelled.h) : null
    };
  }
  return null;
}
function round3(n) { return Math.round(n * 1000) / 1000; }

async function fetchImageAsDataUri(imageUrl, pageUrl) {
  let abs;
  try { abs = new URL(imageUrl, pageUrl).toString(); } catch (e) { return ''; }
  if (!/^https?:/i.test(abs)) return '';
  try {
    const { buf, type } = await safeFetch(abs, 'image/*', MAX_IMAGE_BYTES);
    if (!/^image\//i.test(type)) return '';
    if (/svg/i.test(type)) return ''; // svg can carry script; not worth it here
    return 'data:' + type.split(';')[0] + ';base64,' + buf.toString('base64');
  } catch (e) {
    return '';
  }
}

module.exports = async (req, res) => {
  if (req.method === 'OPTIONS') return res.status(204).end();
  if (req.method !== 'POST') return json(res, 405, { error: 'POST only.' });
  if (!originAllowed(req)) return json(res, 403, { error: 'Not allowed from there.' });

  const ip = String(req.headers['x-forwarded-for'] || '').split(',')[0].trim() || 'unknown';
  if (rateLimited(ip)) return json(res, 429, { error: 'Slow down a moment, then try again.' });

  let body = req.body;
  if (typeof body === 'string') { try { body = JSON.parse(body); } catch (e) { body = null; } }
  const target = body && typeof body.url === 'string' ? body.url.trim() : '';
  if (!/^https?:\/\/[^\s]+$/i.test(target) || target.length > 2048) {
    return json(res, 400, { error: 'Paste the full https:// link to the product page.' });
  }

  try {
    const { buf, finalUrl } = await safeFetch(target, 'text/html,application/xhtml+xml', MAX_HTML_BYTES);
    const html = buf.toString('utf8');

    const ld = readJsonLd(html);
    const title = decodeEntities(
      ld.title ||
      pickMeta(html, ['og:title', 'twitter:title']) ||
      (html.match(/<title[^>]*>([\s\S]*?)<\/title>/i) || [, ''])[1]
    ).trim().slice(0, 160);

    const description = decodeEntities(ld.description || pickMeta(html, ['og:description', 'description'])).slice(0, 600);

    let price = ld.price;
    if (price == null) {
      const metaPrice = pickMeta(html, ['product:price:amount', 'og:price:amount', 'twitter:data1', 'price']);
      const n = parseFloat(String(metaPrice).replace(/[^\d.]/g, ''));
      if (!Number.isNaN(n) && n > 0) price = n;
    }
    const currency = ld.currency || pickMeta(html, ['product:price:currency', 'og:price:currency']) || '';

    const imageUrl = ld.image || pickMeta(html, ['og:image', 'og:image:secure_url', 'twitter:image', 'twitter:image:src']);
    const image = imageUrl ? await fetchImageAsDataUri(imageUrl, finalUrl) : '';

    const dims = readDimensions([title, description, textOfSpecs(html)].join(' | '));

    return json(res, 200, {
      title: title || '',
      brand: ld.brand || '',
      siteName: decodeEntities(pickMeta(html, ['og:site_name'])) || new URL(finalUrl).hostname.replace(/^www\./, ''),
      price: price == null ? null : price,
      currency,
      image,
      description,
      dims,
      url: finalUrl
    });
  } catch (e) {
    const msg = e && e.message ? e.message : '';
    const safe = /reachable|found|redirect|too big|came back|http\(s\)/i.test(msg)
      ? msg
      : 'That site would not hand its page over. Fill the details in by hand.';
    return json(res, 502, { error: safe });
  }
};

// Spec tables are where furniture sizes usually hide.
function textOfSpecs(html) {
  const chunks = [];
  const tables = html.match(/<(table|dl|ul)[^>]*>[\s\S]{0,6000}?<\/\1>/gi) || [];
  for (const t of tables.slice(0, 12)) {
    const text = decodeEntities(t.replace(/<[^>]+>/g, ' ')).replace(/\s+/g, ' ');
    if (/\b(width|depth|height|length|dimension)/i.test(text)) chunks.push(text.slice(0, 1200));
  }
  return chunks.join(' | ').slice(0, 4000);
}

// Exposed for test/product-lookup.test.js; Vercel only uses
// the default handler above.
module.exports.readDimensions = readDimensions;
module.exports.readJsonLd = readJsonLd;
module.exports.pickMeta = pickMeta;
module.exports.isPrivateAddress = isPrivateAddress;
