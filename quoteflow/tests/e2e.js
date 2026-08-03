// QuoteFlow end-to-end suite. The Supabase client is stubbed with an
// in-memory database so every UI action and its persistence can be
// asserted without touching the real project.
// Run: NODE_PATH=<global node_modules> node e2e.js
const { chromium } = require('playwright');

const daysAgo = n => new Date(Date.now() - n * 86400000).toISOString().slice(0, 10);

const seed = {
  rfqs: [
    { id: 1, customer: 'Aerospace Components Ltd', email: 'proc@aero.co.uk', description: 'CNC machined titanium brackets x50', quantity: 50, material: 'Titanium Grade 5', estimated_value: 8400, status: 'new', created_at: new Date(Date.now() - 1 * 864e5).toISOString() },
    { id: 2, customer: 'Defence Manufacturing Co <img src=x onerror=window.__xss=1>', description: 'Precision milled components x200', estimated_value: 12850, status: 'clarification', created_at: new Date(Date.now() - 3 * 864e5).toISOString() },
    { id: 3, customer: 'Precision Engineering Group', description: 'Stainless steel shafts x30', estimated_value: 6200, status: 'ready', created_at: new Date(Date.now() - 5 * 864e5).toISOString() }
  ],
  quotes: [
    { id: 1, quote_ref: 'JNR-Q-001', customer: 'Aerospace Components Ltd', total: 8400, quantity: 50, unit_price: 168, sent_date: daysAgo(3), followups_sent: 0, next_followup_date: daysAgo(-1), replied: false, paid_detected: false, status: 'sent' },
    { id: 2, quote_ref: 'JNR-Q-002', customer: 'Defence Manufacturing Co', total: 12850, sent_date: daysAgo(7), followups_sent: 2, replied: false, paid_detected: false, status: 'sent' },
    { id: 3, quote_ref: 'JNR-Q-004', customer: 'Industrial Systems Ltd', total: 15600, sent_date: daysAgo(2), followups_sent: 0, replied: false, paid_detected: true, status: 'accepted' }
  ],
  invoices: [
    { id: 1, invoice_ref: 'INV-2026-084', customer: 'Construction Services Ltd', description: 'Steel beam fabrication', total: 6000, status: 'outstanding', sent_date: daysAgo(105), due_date: daysAgo(75), late_payer_flag: 'CHRONIC LATE PAYER' },
    { id: 2, invoice_ref: 'INV-2026-095', customer: 'Industrial Systems Ltd', description: 'Stainless steel shafts', total: 8800, status: 'outstanding', sent_date: daysAgo(42), due_date: daysAgo(12) },
    { id: 3, invoice_ref: 'INV-2026-099', customer: 'Aerospace Components Ltd', description: 'Titanium brackets', total: 10080, status: 'outstanding', sent_date: daysAgo(22), due_date: daysAgo(-8) },
    { id: 4, invoice_ref: 'INV-2026-093', customer: 'Precision Engineering Group', description: 'Stainless steel shafts', total: 6200, status: 'paid', sent_date: daysAgo(40), paid_at: new Date(Date.now() - 4 * 864e5).toISOString(), due_date: daysAgo(8) }
  ],
  stock: [
    { id: 1, sku: 'AL-6082-BAR-50', name: 'Aluminium 6082 Bar', current_stock: 12, reorder_level: 25, reorder_qty: 50, unit_cost: 42, supplier: 'MetalSupplies Ltd', lead_time: '3-5 days', auto_purchase: true, order_note: 'Auto-ordered today' },
    { id: 2, sku: 'MS-PLT-10MM', name: 'Mild Steel Plate', current_stock: 85, reorder_level: 40, reorder_qty: 100, unit_cost: 18.2, supplier: 'Industrial Metals', lead_time: '2-3 days', auto_purchase: false }
  ],
  jobs: [
    { id: 1, job_ref: 'JNR-J-218', customer: 'Aerospace Components', description: 'Titanium brackets x50', stage: 'machining', status: 'on_track', due_date: daysAgo(-5), value: 8400 },
    { id: 2, job_ref: 'JNR-J-219', customer: 'Defence Manufacturing', description: 'Milled components x200', stage: 'setup', status: 'on_track', due_date: daysAgo(-9), value: 12850 },
    { id: 3, job_ref: 'JNR-J-222', customer: 'Marine Engineering Co', description: 'Brass fittings x120', stage: 'machining', status: 'overdue', due_date: daysAgo(2), value: 9400 }
  ],
  machines: [
    { id: 1, name: 'Haas VF-2', type: 'CNC Mill', hours_run: 2847, last_maintenance: daysAgo(70), next_due: daysAgo(10) },
    { id: 2, name: 'DMG Mori NLX 2500', type: 'CNC Lathe', hours_run: 1204, last_maintenance: daysAgo(7), next_due: daysAgo(-54) }
  ],
  machine_logs: [],
  email_outbox: [
    { id: 1, kind: 'final_notice', customer: 'Construction Services Ltd', to_email: 'accounts@constructionservices.co.uk', amount: 6000, days_overdue: 75, related_ref: 'INV-2026-084', subject: 'Final Notice - INV-2026-084', body: 'Dear Sir/Madam, final notice...', status: 'pending_approval', created_at: new Date().toISOString() },
    { id: 2, kind: 'gentle_reminder', customer: 'Defence Manufacturing Co', to_email: 'accounts@defence.co.uk', amount: 6800, days_overdue: 5, related_ref: 'INV-2026-097', subject: 'Friendly Reminder - INV-2026-097', body: 'Hi Team, quick reminder...', status: 'pending_approval', created_at: new Date().toISOString() }
  ],
  stock_movements: [],
  org_settings: [],
  purchase_orders: [],
  app_access: [ { email: 'rhys@jnr.co.uk', org_id: null, role: 'owner', created_at: new Date(Date.now() - 30 * 864e5).toISOString() } ]
};

const stubJs = `
window.__mockData = ${JSON.stringify(seed)};
window.supabase = {
  createClient: function () {
    const authCallbacks = [];
    function currentSession() {
      try { return JSON.parse(localStorage.getItem('stub-session')); } catch (e) { return null; }
    }
    function fire(event, session) {
      setTimeout(() => authCallbacks.forEach(cb => cb(event, session)), 0);
    }
    const auth = {
      async getSession() { return { data: { session: currentSession() } }; },
      async signInWithPassword({ email, password }) {
        if (password === 'wrongpass') return { data: {}, error: { message: 'Invalid login credentials' } };
        const session = { user: { id: 'user-1', email } };
        localStorage.setItem('stub-session', JSON.stringify(session));
        fire('SIGNED_IN', session);
        return { data: { session }, error: null };
      },
      async signUp({ email }) {
        const session = { user: { id: 'user-1', email } };
        localStorage.setItem('stub-session', JSON.stringify(session));
        fire('SIGNED_IN', session);
        return { data: { session }, error: null };
      },
      async signOut() {
        localStorage.removeItem('stub-session');
        fire('SIGNED_OUT', null);
        return { error: null };
      },
      onAuthStateChange(cb) { authCallbacks.push(cb); return { data: { subscription: { unsubscribe() {} } } }; }
    };
    function builder(table) {
      const st = { table, op: 'select', filters: [], values: null, wantSingle: false, sort: null };
      const api = {
        select() { return api; },
        order(col, opts) { st.sort = { col, asc: !opts || opts.ascending !== false }; return api; },
        eq(col, val) { st.filters.push([col, val]); return api; },
        single() { st.wantSingle = true; return api; },
        insert(rows) { st.op = 'insert'; st.values = Array.isArray(rows) ? rows : [rows]; return api; },
        update(vals) { st.op = 'update'; st.values = vals; return api; },
        upsert(rows) { st.op = 'upsert'; st.values = Array.isArray(rows) ? rows : [rows]; return api; },
        delete() { st.op = 'delete'; return api; },
        then(resolve) {
          const all = window.__mockData[st.table] = window.__mockData[st.table] || [];
          let result;
          if (st.op === 'insert') {
            st.values.forEach(r => { r.id = (all.length ? Math.max(...all.map(x => +x.id || 0)) : 0) + 1; if (!r.created_at) r.created_at = new Date().toISOString(); all.push(r); });
            result = { data: st.values, error: null };
          } else if (st.op === 'upsert') {
            st.values.forEach(r => {
              const i = all.findIndex(x => x.org_id === r.org_id);
              if (i >= 0) Object.assign(all[i], r); else all.push(r);
            });
            result = { data: st.values, error: null };
          } else if (st.op === 'delete') {
            const keep = all.filter(r => !st.filters.every(([c, v]) => String(r[c]) === String(v)));
            const removed = all.length - keep.length;
            window.__mockData[st.table] = keep;
            result = { data: [], error: null, count: removed };
          } else if (st.op === 'update') {
            const matched = all.filter(r => st.filters.every(([c, v]) => String(r[c]) === String(v)));
            matched.forEach(r => Object.assign(r, st.values));
            result = { data: matched, error: null };
          } else {
            let rows = all.filter(r => st.filters.every(([c, v]) => String(r[c]) === String(v)));
            if (st.sort) rows = rows.slice().sort((a, b) => (String(a[st.sort.col]) > String(b[st.sort.col]) ? 1 : -1) * (st.sort.asc ? 1 : -1));
            result = st.wantSingle ? { data: rows[0] || null, error: rows[0] ? null : { message: 'not found' } } : { data: rows, error: null };
          }
          resolve(result);
        }
      };
      return api;
    }
    return {
      from: builder,
      auth: auth,
      rpc: async function (name, args) {
        if (name === 'ensure_org') {
          const sess = currentSession();
          const email = sess && sess.user.email.toLowerCase();
          const entry = (window.__mockData.app_access || []).find(a => a.email.toLowerCase() === email);
          if (!entry) return { data: null, error: { message: 'ACCESS_DENIED: this workspace is invite-only' } };
          if (!entry.org_id) entry.org_id = 'org-1';
          return { data: [{ org_id: entry.org_id, org_display_name: (args && args.org_name) || 'JNR Engineering Ltd' }], error: null };
        }
        return { data: null, error: { message: 'unknown rpc ' + name } };
      }
    };
  }
};
`;

let failures = 0;
function check(name, cond, extra) {
  if (cond) console.log('PASS  ' + name);
  else { failures++; console.log('FAIL  ' + name + (extra ? '  -> ' + extra : '')); }
}

(async () => {
  const browser = await chromium.launch({ executablePath: process.env.PW_CHROME || '/opt/pw-browsers/chromium-1194/chrome-linux/chrome' });
  const context = await browser.newContext();
  const page = await context.newPage();
  const pageErrors = [];
  page.on('pageerror', e => pageErrors.push(String(e)));

  await page.route('**/cdn.jsdelivr.net/**', r => r.fulfill({ contentType: 'application/javascript', body: stubJs }));
  await page.route('**/cdn.tailwindcss.com/**', r => r.fulfill({ contentType: 'application/javascript', body: 'window.tailwind={config:{}};' }));
  await page.route('**/fonts.googleapis.com/**', r => r.fulfill({ contentType: 'text/css', body: '' }));
  await page.route('**/fonts.gstatic.com/**', r => r.fulfill({ contentType: 'font/woff2', body: '' }));

  const APP = process.env.APP_URL || 'file://' + require('path').resolve(__dirname, '..', 'index.html');

  // ---------- AUTH GATE ----------
  await page.goto(APP);
  await page.waitForTimeout(600);
  check('auth overlay blocks the app on load', await page.locator('#authOverlay:not(.hidden)').isVisible());
  check('no data loaded before login (RFQ stat still static)', await page.textContent('#rfqStatNew') === '12');

  // wrong password -> error, still locked
  await page.fill('#authEmail', 'rhys@jnr.co.uk');
  await page.fill('#authPassword', 'wrongpass');
  await page.click('#authSubmitBtn');
  await page.waitForTimeout(400);
  check('wrong password shows error', await page.locator('#authError').isVisible());
  check('still locked after failed login', await page.locator('#authOverlay:not(.hidden)').isVisible());

  // uninvited user: valid credentials, but not on the allowlist
  await page.fill('#authEmail', 'stranger@random.com');
  await page.fill('#authPassword', 'correct-horse-battery');
  await page.click('#authSubmitBtn');
  await page.waitForTimeout(900);
  check('uninvited user rejected with invite-only message', (await page.textContent('#authError')).includes('invite-only'));
  check('uninvited user stays locked out', await page.locator('#authOverlay:not(.hidden)').isVisible());

  // correct login (invited bootstrap user)
  await page.fill('#authEmail', 'rhys@jnr.co.uk');
  await page.fill('#authPassword', 'correct-horse-battery');
  await page.click('#authSubmitBtn');
  await page.waitForTimeout(1200);
  check('login hides the overlay', await page.locator('#authOverlay.hidden').count() === 1);
  check('user email shown in sidebar', (await page.textContent('#userEmail')).includes('rhys@jnr.co.uk'));
  check('org name shown in sidebar', (await page.textContent('#userOrg')).includes('JNR Engineering'));

  // ---------- DATA RENDERED AFTER LOGIN ----------
  check('RFQ stats live', await page.textContent('#rfqStatNew') === '1');
  check('XSS payload did not execute', (await page.evaluate(() => window.__xss)) === undefined);
  check('invoice aging live', (await page.textContent('#totalOwed')).trim() === '£24,880');
  check('dashboard win rate computed (100%)', (await page.textContent('#kpiWinRate')).trim() === '100%');
  check('dashboard outstanding = aging total', (await page.textContent('#kpiOutstanding')).trim() === '£24,880');
  check('avg days to pay computed', (await page.textContent('#kpiAvgDaysToPay')).trim() !== '28');

  // Jobs
  check('job KPIs live', await page.textContent('#jobStatMachining') === '2');
  const jobsHtml = await page.locator('#jobTableBody').innerHTML();
  check('jobs rendered from DB', jobsHtml.includes('JNR-J-218'));
  check('overdue job derived', jobsHtml.includes('Behind Schedule'));

  // Machines
  const machinesHtml = await page.locator('#machineTableBody').innerHTML();
  check('machines rendered from DB', machinesHtml.includes('Haas VF-2'));
  check('machine overdue derived', machinesHtml.includes('Maintenance Overdue'));
  check('machine stats live', await page.textContent('#machineStatWarnings') === '1');

  // Approval queue from outbox
  const apprHtml = await page.locator('#approvalList').innerHTML();
  check('approval queue rendered from outbox', apprHtml.includes('FINAL NOTICE') && apprHtml.includes('GENTLE REMINDER'));

  // Late payers computed
  const lateHtml = await page.locator('#latePayerList').innerHTML();
  check('late payer patterns computed', lateHtml.includes('Construction Services Ltd'));

  // ---------- BUTTON: advance job stage ----------
  await page.click('.nav-item[data-page="job"]');
  await page.locator('#jobTableBody tr:has-text("JNR-J-218") button').click();
  await page.waitForTimeout(500);
  check('advance job persists to DB', await page.evaluate(() =>
    window.__mockData.jobs.some(j => j.job_ref === 'JNR-J-218' && j.stage === 'inspection')));

  // ---------- BUTTON: quote engine ----------
  await page.click('.nav-item[data-page="rfq"]');
  await page.waitForTimeout(300);
  await page.locator('#rfq .rfq-row button:has-text("Generate Quote")').first().click();
  await page.waitForTimeout(600);
  check('Generate Quote navigates to quote page', await page.locator('#quote.page.active').count() === 1);
  check('quote form prefilled from RFQ', (await page.inputValue('#quoteCustomer')) === 'Precision Engineering Group');

  await page.fill('#quoteMatCost', '1000');
  await page.fill('#quoteMachineHrs', '10');
  await page.fill('#quoteSetupHrs', '2');
  await page.click('button:has-text("Generate Quote"):not(.rfq-row button)');
  await page.waitForTimeout(700);
  // cost = 1000*1.08 + 10*65 + 2*45 = 1080 + 650 + 90 = 1820; price = 1820/0.65 = 2800
  check('quote maths correct (£2800.00)', (await page.textContent('#quoteResValue')).trim() === '£2800.00', await page.textContent('#quoteResValue'));
  check('quote ref assigned (JNR-Q-005)', (await page.textContent('#quoteResRef')).trim() === 'JNR-Q-005', await page.textContent('#quoteResRef'));
  check('quote saved to DB', await page.evaluate(() =>
    window.__mockData.quotes.some(q => q.quote_ref === 'JNR-Q-005' && q.total === 2800)));
  check('RFQ marked quoted', await page.evaluate(() =>
    window.__mockData.rfqs.find(r => r.id === 3).status === 'quoted'));

  // Send to customer -> outbox
  await page.click('button:has-text("Send to Customer")');
  await page.waitForTimeout(300);
  await page.fill('#sendQuoteEmail', 'buyer@precisioneng.co.uk');
  await page.click('#viewDetailModal button:has-text("Add to Outbox")');
  await page.waitForTimeout(500);
  check('quote email queued in outbox', await page.evaluate(() =>
    window.__mockData.email_outbox.some(o => o.kind === 'quote_send' && o.related_ref === 'JNR-Q-005' && o.status === 'queued')));
  check('quote status now sent', await page.evaluate(() =>
    window.__mockData.quotes.find(q => q.quote_ref === 'JNR-Q-005').status === 'sent'));

  // ---------- BUTTON: approval queue ----------
  await page.click('.nav-item[data-page="approval"]');
  await page.waitForTimeout(300);
  await page.locator('[data-approval-id="2"] button:has-text("Approve & Send")').click();
  await page.waitForTimeout(700);
  check('approve persists to outbox', await page.evaluate(() =>
    window.__mockData.email_outbox.find(o => o.id === 2).status === 'approved'));
  page.once('dialog', d => d.accept());
  await page.locator('[data-approval-id="1"] button:has-text("Skip")').click();
  await page.waitForTimeout(600);
  check('skip persists to outbox', await page.evaluate(() =>
    window.__mockData.email_outbox.find(o => o.id === 1).status === 'skipped'));

  // ---------- BUTTON: chase all overdue ----------
  await page.click('.nav-item[data-page="invoice"]');
  await page.waitForTimeout(300);
  await page.click('button:has-text("Chase All Overdue")');
  await page.waitForTimeout(900);
  check('chase-all drafts reminders for overdue invoices', await page.evaluate(() =>
    window.__mockData.email_outbox.some(o => o.related_ref === 'INV-2026-084' && o.status === 'pending_approval') &&
    window.__mockData.email_outbox.some(o => o.related_ref === 'INV-2026-095' && o.status === 'pending_approval')));
  check('chase-all navigates to approval queue', await page.locator('#approval.page.active').count() === 1);

  // ---------- BUTTON: invoice detail + draft reminder ----------
  await page.click('.nav-item[data-page="invoice"]');
  await page.waitForTimeout(300);
  await page.locator('#invoiceList button:has-text("View")').first().click();
  await page.waitForTimeout(400);
  check('invoice detail modal from DB', (await page.textContent('#viewDetailTitle')).includes('INV-2026-084'));
  await page.click('#viewDetailModal .modal-close');

  // ---------- BUTTON: barcode stock movement ----------
  await page.click('.nav-item[data-page="stock"]');
  await page.waitForTimeout(300);
  await page.click('button:has-text("Scan Barcode")');
  await page.waitForTimeout(300);
  await page.click('#scanModeOut');
  await page.fill('#barcodeSku', 'al-6082-bar-50');
  await page.fill('#barcodeQty', '5');
  await page.click('button:has-text("Apply")');
  await page.waitForTimeout(600);
  check('barcode OUT updates stock 12->7', await page.evaluate(() =>
    window.__mockData.stock.find(s => s.sku === 'AL-6082-BAR-50').current_stock === 7));
  check('stock movement recorded', await page.evaluate(() =>
    window.__mockData.stock_movements.some(m => m.sku === 'AL-6082-BAR-50' && m.direction === 'out' && +m.delta === 5)));
  await page.click('#barcodeModal .modal-close');

  // ---------- BUTTON: supplier config + purchase order ----------
  await page.locator('#stockTableBody button:has-text("Configure")').first().click();
  await page.waitForTimeout(300);
  await page.fill('#cfgReorderLevel', '30');
  await page.click('#viewDetailModal button:has-text("Save Configuration")');
  await page.waitForTimeout(500);
  check('supplier config persists', await page.evaluate(() =>
    window.__mockData.stock.find(s => s.sku === 'AL-6082-BAR-50').reorder_level == 30));

  await page.locator('#stockTableBody button:has-text("Configure")').first().click();
  await page.waitForTimeout(300);
  await page.click('#viewDetailModal button:has-text("Order Now")');
  await page.waitForTimeout(500);
  check('purchase order created', await page.evaluate(() =>
    window.__mockData.purchase_orders.some(p => p.sku === 'AL-6082-BAR-50' && p.po_ref && p.po_ref.includes('-PO-'))));

  // ---------- BUTTON: auto-purchase rules ----------
  await page.waitForTimeout(4200); // let toasts clear the top-right corner
  await page.click('button:has-text("Auto-Purchase Rules")');
  await page.waitForTimeout(300);
  await page.locator('#autoPurchaseRules button').nth(1).click();
  await page.click('#autoPurchaseModal button:has-text("Save Settings")');
  await page.waitForTimeout(500);
  check('auto-purchase toggle persists', await page.evaluate(() =>
    window.__mockData.stock.find(s => s.sku === 'MS-PLT-10MM').auto_purchase === true));
  check('org settings saved', await page.evaluate(() =>
    window.__mockData.org_settings.length === 1));

  // ---------- BUTTON: machine service ----------
  await page.click('.nav-item[data-page="machine"]');
  await page.waitForTimeout(300);
  await page.locator('#machineTableBody button:has-text("Schedule Service")').first().click();
  await page.waitForTimeout(300);
  await page.fill('#serviceNote', 'Full service');
  await page.click('#viewDetailModal button:has-text("Book Service")');
  await page.waitForTimeout(600);
  check('service booking persists (log written)', await page.evaluate(() =>
    window.__mockData.machine_logs.length === 1));
  check('machine next_due pushed out', await page.evaluate(() => {
    const m = window.__mockData.machines.find(m => m.name === 'Haas VF-2');
    return new Date(m.next_due) > new Date();
  }));

  // ---------- clarify -> outbox ----------
  await page.click('.nav-item[data-page="rfq"]');
  await page.waitForTimeout(300);
  await page.locator('button:has-text("Clarify")').first().click();
  await page.waitForTimeout(300);
  await page.click('#clarifyModal button:has-text("Send Clarification")');
  await page.waitForTimeout(500);
  check('clarification queued in outbox', await page.evaluate(() =>
    window.__mockData.email_outbox.some(o => o.kind === 'clarification' && o.status === 'queued')));

  // ---------- BUTTON: team access (invite-only management) ----------
  await page.click('button:has-text("Team")');
  await page.waitForTimeout(400);
  await page.fill('#inviteEmail', 'bob@jnr.co.uk');
  await page.click('#viewDetailModal button:has-text("Grant Access")');
  await page.waitForTimeout(500);
  check('invite persisted to allowlist', await page.evaluate(() =>
    window.__mockData.app_access.some(a => a.email === 'bob@jnr.co.uk' && a.org_id === 'org-1' && a.role === 'office')));
  page.once('dialog', d => d.accept());
  await page.locator('#teamList div:has-text("bob@jnr.co.uk") button:has-text("Revoke")').click();
  await page.waitForTimeout(500);
  check('revoke removes from allowlist', await page.evaluate(() =>
    !window.__mockData.app_access.some(a => a.email === 'bob@jnr.co.uk')));
  await page.click('#viewDetailModal .modal-close');

  // ---------- session persistence + deep link ----------
  await page.goto(APP + '#stock');
  await page.waitForTimeout(1000);
  check('session survives reload (no overlay)', await page.locator('#authOverlay.hidden').count() === 1);
  check('deep link works while authed', await page.locator('#stock.page.active').count() === 1);

  // ---------- sign out ----------
  await page.click('#signOutBtn');
  await page.waitForTimeout(600);
  check('sign out locks the app again', await page.locator('#authOverlay:not(.hidden)').isVisible());
  check('session cleared on sign out', (await page.evaluate(() => localStorage.getItem('stub-session'))) === null);

  // ---------- DISCOVERY FORM ACCESS GATE ----------
  const DISC = 'file://' + require('path').resolve(__dirname, '..', 'jnr', 'jnr-discovery', 'index.html');
  await page.goto(DISC);
  await page.waitForTimeout(400);
  check('discovery gate blocks by default', await page.locator('#accessGate').isVisible());
  await page.fill('#accessCode', 'wrong-code');
  await page.click('#accessGate button');
  await page.waitForTimeout(400);
  check('wrong code rejected', await page.locator('#accessError').isVisible());
  check('gate still up after wrong code', await page.locator('#accessGate').isVisible());
  await page.fill('#accessCode', 'JNR-2026');
  await page.click('#accessGate button');
  await page.waitForTimeout(500);
  check('correct code opens the form', await page.locator('#accessGate').isHidden());
  await page.goto(DISC);
  await page.waitForTimeout(400);
  check('unlock persists across reload', await page.locator('#accessGate').isHidden());

  check('no JS errors across entire run', pageErrors.length === 0, pageErrors.slice(0, 3).join(' | '));

  await browser.close();
  console.log(failures === 0 ? '\nALL CHECKS PASSED' : `\n${failures} CHECK(S) FAILED`);
  process.exit(failures === 0 ? 0 : 1);
})();
