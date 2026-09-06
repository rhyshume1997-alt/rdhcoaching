/* Tests for /api/product-lookup. No dependencies: node test/product-lookup.test.js
   DNS and fetch are stubbed, so nothing leaves the machine. */
const assert = require('assert');
const dns = require('dns').promises;

dns.lookup = async (host) => {
  if (host === 'internal.local') return [{ address: '10.0.0.7', family: 4 }];
  if (host === 'meta.evil') return [{ address: '169.254.169.254', family: 4 }];
  return [{ address: '93.184.216.34', family: 4 }];
};

const PAGE = `<html><head>
<meta property="og:site_name" content="Test Furniture Co">
<meta property="og:title" content="Fallback title">
<meta property="og:image" content="/img/sofa.jpg">
<script type="application/ld+json">
{"@type":"Product","name":"Hallberg 3-seater","brand":{"name":"Hallberg"},
 "description":"Deep seat, fabric.","offers":{"price":"899.99","priceCurrency":"GBP"}}
</script></head><body>
<table><tr><th>Width</th><td>212 cm</td></tr><tr><th>Depth</th><td>95 cm</td></tr><tr><th>Height</th><td>84 cm</td></tr></table>
</body></html>`;
const IMG = Buffer.from('89504e470d0a1a0a', 'hex');
let redirectFollowed = false;

global.fetch = async (url) => {
  if (url === 'https://shop.example/p/sofa') {
    redirectFollowed = true;
    return { status: 302, ok: false, headers: new Map([['location', 'https://shop.example/p/sofa-final']]), arrayBuffer: async () => Buffer.alloc(0) };
  }
  if (url === 'https://shop.example/p/sofa-final') {
    return { status: 200, ok: true, headers: new Map([['content-type', 'text/html']]), arrayBuffer: async () => Buffer.from(PAGE) };
  }
  if (url === 'https://shop.example/img/sofa.jpg') {
    return { status: 200, ok: true, headers: new Map([['content-type', 'image/png']]), arrayBuffer: async () => IMG };
  }
  throw new Error('nothing else should be fetched: ' + url);
};

const handler = require('../api/product-lookup.js');

function mockRes() {
  const r = { statusCode: 0, body: null };
  r.setHeader = () => {};
  r.status = (c) => { r.statusCode = c; return r; };
  r.json = (b) => { r.body = b; return r; };
  r.end = () => r;
  return r;
}
const post = (body, headers = {}) => {
  const res = mockRes();
  return handler({ method: 'POST', headers: Object.assign({ origin: 'https://www.rdhcoaching.com' }, headers), body }, res).then(() => res);
};

const tests = [];
const test = (name, fn) => tests.push([name, fn]);

test('parses dimensions in every shape shops write them', () => {
  assert.deepStrictEqual(handler.readDimensions('Sofa 220 x 90 x 85 cm'), { w: 2.2, d: 0.9, h: 0.85 });
  assert.deepStrictEqual(handler.readDimensions('Unit 2200 x 900 x 850 mm'), { w: 2.2, d: 0.9, h: 0.85 });
  assert.deepStrictEqual(handler.readDimensions('Width: 120 cm Depth: 45cm Height: 200 cm'), { w: 1.2, d: 0.45, h: 2 });
  assert.strictEqual(handler.readDimensions('A lovely sofa in grey'), null);
});

test('reads JSON-LD product data', () => {
  const r = handler.readJsonLd(PAGE);
  assert.strictEqual(r.title, 'Hallberg 3-seater');
  assert.strictEqual(r.price, 899.99);
  assert.strictEqual(r.currency, 'GBP');
});

test('follows redirects and returns the product', async () => {
  const res = await post({ url: 'https://shop.example/p/sofa' });
  assert.strictEqual(res.statusCode, 200);
  assert.ok(redirectFollowed);
  assert.strictEqual(res.body.title, 'Hallberg 3-seater');
  assert.strictEqual(res.body.price, 899.99);
  assert.strictEqual(res.body.siteName, 'Test Furniture Co');
  assert.ok(/^data:image\/png;base64,/.test(res.body.image));
  assert.deepStrictEqual(res.body.dims, { w: 2.12, d: 0.95, h: 0.84 });
});

test('will not fetch private or link-local addresses', async () => {
  for (const url of ['https://internal.local/admin', 'https://meta.evil/latest/meta-data/']) {
    const res = await post({ url });
    assert.strictEqual(res.statusCode, 502);
  }
  assert.ok(handler.isPrivateAddress('10.0.0.5', 4));
  assert.ok(handler.isPrivateAddress('169.254.169.254', 4));
  assert.ok(handler.isPrivateAddress('::ffff:127.0.0.1', 6));
  assert.ok(!handler.isPrivateAddress('93.184.216.34', 4));
});

test('rejects bad input, other origins and other methods', async () => {
  assert.strictEqual((await post({ url: 'file:///etc/passwd' })).statusCode, 400);
  assert.strictEqual((await post({})).statusCode, 400);
  assert.strictEqual((await post({ url: 'https://shop.example/p/sofa' }, { origin: 'https://evil.example' })).statusCode, 403);
  const res = mockRes();
  await handler({ method: 'GET', headers: {} }, res);
  assert.strictEqual(res.statusCode, 405);
});

(async () => {
  let failed = 0;
  for (const [name, fn] of tests) {
    try { await fn(); console.log('ok   ' + name); }
    catch (e) { failed++; console.log('FAIL ' + name + '\n     ' + e.message); }
  }
  console.log(failed ? failed + ' failing' : tests.length + ' passing');
  process.exit(failed ? 1 : 0);
})();
