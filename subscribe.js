// POST /api/subscribe
// Adds or updates a subscriber in Mailchimp and applies allowlisted tags.
// Credentials come from server-side env vars only and are never returned or logged.

const ALLOWED_TAGS = [
  'Website Newsletter',
  'AI Audit',
  'Fat Loss',
  'Muscle Gain',
  'Online Coaching',
  'In-Person PT',
  'High Intent'
];

const MAX_BODY_BYTES = 4096;
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[a-zA-Z]{2,}$/;

function json(res, status, payload) {
  res.setHeader('Content-Type', 'application/json');
  res.setHeader('Cache-Control', 'no-store');
  return res.status(status).json(payload);
}

// Mailchimp needs the lowercased email hashed with MD5 as the subscriber id.
function subscriberHash(email) {
  const crypto = require('crypto');
  return crypto.createHash('md5').update(email.trim().toLowerCase()).digest('hex');
}

async function readBody(req) {
  // Vercel usually parses JSON for us. Fall back to manual read with a size cap.
  if (req.body && typeof req.body === 'object') return req.body;

  return await new Promise((resolve, reject) => {
    let size = 0;
    let raw = '';
    req.on('data', chunk => {
      size += chunk.length;
      if (size > MAX_BODY_BYTES) {
        reject(new Error('PAYLOAD_TOO_LARGE'));
        req.destroy();
        return;
      }
      raw += chunk;
    });
    req.on('end', () => {
      if (!raw) return resolve({});
      try { resolve(JSON.parse(raw)); }
      catch (e) { reject(new Error('BAD_JSON')); }
    });
    req.on('error', () => reject(new Error('READ_ERROR')));
  });
}

module.exports = async function handler(req, res) {
  // ---- method validation ----
  if (req.method !== 'POST') {
    res.setHeader('Allow', 'POST');
    return json(res, 405, { ok: false, error: 'Method not allowed.' });
  }

  // ---- config check (never reveal values) ----
  const API_KEY = process.env.MAILCHIMP_API_KEY;
  const AUDIENCE_ID = process.env.MAILCHIMP_AUDIENCE_ID;
  const SERVER_PREFIX = process.env.MAILCHIMP_SERVER_PREFIX;

  if (!API_KEY || !AUDIENCE_ID || !SERVER_PREFIX) {
    console.error('subscribe: missing Mailchimp configuration');
    return json(res, 500, { ok: false, error: 'Signup is temporarily unavailable.' });
  }

  // ---- body ----
  let body;
  try {
    body = await readBody(req);
  } catch (e) {
    const tooBig = e && e.message === 'PAYLOAD_TOO_LARGE';
    return json(res, tooBig ? 413 : 400, {
      ok: false,
      error: tooBig ? 'Request too large.' : 'Invalid request.'
    });
  }

  // ---- honeypot: silently accept so bots do not learn ----
  if (typeof body.company === 'string' && body.company.trim() !== '') {
    return json(res, 200, { ok: true });
  }

  // ---- email validation ----
  const email = typeof body.email === 'string' ? body.email.trim() : '';
  if (!email || email.length > 254 || !EMAIL_RE.test(email)) {
    return json(res, 400, { ok: false, error: 'Please enter a valid email address.' });
  }

  const firstName = typeof body.name === 'string' ? body.name.trim().slice(0, 80) : '';

  // ---- tags: allowlist only, never trust the browser ----
  const requested = Array.isArray(body.tags) ? body.tags : [];
  const tags = Array.from(new Set(
    ['Website Newsletter'].concat(requested.filter(t => ALLOWED_TAGS.includes(t)))
  ));

  const base = `https://${SERVER_PREFIX}.api.mailchimp.com/3.0`;
  const auth = 'Basic ' + Buffer.from('anystring:' + API_KEY).toString('base64');
  const hash = subscriberHash(email);

  try {
    // ---- PUT upserts: creates new, updates existing, no duplicate error ----
    function upsertBody(includeName) {
      const payload = {
        email_address: email,
        status_if_new: 'subscribed'    // applies to NEW contacts only
      };
      if (includeName && firstName) payload.merge_fields = { FNAME: firstName };
      return JSON.stringify(payload);
    }

    const memberUrl = `${base}/lists/${AUDIENCE_ID}/members/${hash}`;
    const putOpts = b => ({
      method: 'PUT',
      headers: { Authorization: auth, 'Content-Type': 'application/json' },
      body: b
    });

    let upsert = await fetch(memberUrl, putOpts(upsertBody(true)));

    // If the audience has no FNAME field (or other merge validation trouble),
    // retry with the email alone rather than losing the subscriber.
    if (!upsert.ok && upsert.status === 400 && firstName) {
      let d1 = '';
      try { const j = await upsert.clone().json(); d1 = (j.detail || '') + ' ' + (j.title || ''); } catch (e) {}
      if (/merge/i.test(d1)) {
        console.error('subscribe: merge_fields rejected, retrying without name');
        upsert = await fetch(memberUrl, putOpts(upsertBody(false)));
      }
    }

    if (!upsert.ok) {
      let detail = '';
      try { const d = await upsert.json(); detail = d.title || ''; } catch (e) {}

      // Previously unsubscribed / deleted contacts cannot be resubscribed by API.
      // Never claim success, and never imply an email is on its way.
      if (upsert.status === 400 && /compliance|forgotten/i.test(detail)) {
        return json(res, 409, {
          ok: false,
          error: 'That email was previously unsubscribed. Email rhumecoaching@gmail.com and I will add you back.'
        });
      }

      console.error('subscribe: mailchimp upsert failed', upsert.status, detail);
      return json(res, 502, { ok: false, error: 'Could not complete signup. Please try again.' });
    }

    // Existing contacts keep their current status: status_if_new only applies to new
    // records. If they are unsubscribed or cleaned, do not tag and do not claim success.
    let memberStatus = '';
    try { const m = await upsert.clone().json(); memberStatus = m.status || ''; } catch (e) {}

    if (memberStatus === 'unsubscribed' || memberStatus === 'cleaned') {
      return json(res, 409, {
        ok: false,
        error: 'That email was previously unsubscribed. Email rhumecoaching@gmail.com and I will add you back.'
      });
    }

    // ---- tags applied in a second call; failure here must not lose the subscriber ----
    try {
      const tagRes = await fetch(`${base}/lists/${AUDIENCE_ID}/members/${hash}/tags`, {
        method: 'POST',
        headers: { Authorization: auth, 'Content-Type': 'application/json' },
        body: JSON.stringify({ tags: tags.map(name => ({ name, status: 'active' })) })
      });
      if (!tagRes.ok) console.error('subscribe: tagging failed', tagRes.status);
    } catch (e) {
      console.error('subscribe: tagging threw');
    }

    return json(res, 200, { ok: true });

  } catch (e) {
    // Never surface upstream error text to the client.
    console.error('subscribe: unexpected failure');
    return json(res, 500, { ok: false, error: 'Something went wrong. Please try again.' });
  }
};
