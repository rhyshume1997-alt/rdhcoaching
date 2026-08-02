# QuoteFlow vs Statii — Dissection & Gap Analysis

**Goal:** evolve the JNR artefacts into an in-house replacement for Statii-class MRP/ERP
software — used by JNR Engineering at cost, then productised and scaled to other
small manufacturers.

**Date:** July 2026 · **Author:** analysis produced for Rhys Hume

---

## 1. What exists today (honest audit of the artefacts)

### 1.1 `quoteflow/index.html` — the live demo (5,033 lines)

A single-file SPA, branded for JNR Engineering, with 9 pages:
Dashboard, Email Automation, RFQ Control, Quote Generator, Job Board,
Invoicing, Approval Queue, Stock & Suppliers, Machine Maintenance.

**What's real:**
- Navigation, modals, toasts, multi-select filter system — all functional.
- A Supabase client wired to project `qtgqliczvyyrkibvxfqv` (JNREng).
- RFQs: create-form saves to DB, list renders from DB, detail view reads from DB.

**What's illusion:**
- ~95% of visible data is hardcoded HTML (KPIs, charts, invoices, jobs, stock,
  machines, approval queue, late-payer intelligence).
- `loadQuotesFromDB` / `loadInvoicesFromDB` / `loadStockFromDB` fetch data but
  **nothing renders it** — results are logged and discarded.
- Action buttons ("Send to Customer", "Reorder", "Schedule Service"…) are mapped
  to toast notifications only, via a button-text lookup table.
- **The Supabase project was paused and contained ZERO tables.** Every DB call the
  demo has ever made failed or returned nothing. (Project has now been restored;
  schema still needs creating.)

**Code defects found:**
- Duplicate declarations of `submitNewRfq` and `filterInvoices` (later definition
  silently wins; dead code).
- Unescaped DB values injected via `innerHTML` in `renderRfqs`/`viewRfqFromDB` (XSS
  as soon as real customer data flows).
- No auth of any kind; no RLS design behind the publishable key.
- Zero mobile support — fixed 260px sidebar, no media queries at all.
- `history`/URL routing stubbed out (back button does nothing).

### 1.2 `quoteflow/QuoteFlow-V3-Branded.html`
Superseded snapshot of the same app (V3, before filter chips). Keep as archive or delete.

### 1.3 `quoteflow/jnr/jnr-discovery/index.html`
The 20-question discovery form. Genuinely functional (Formspree → email), well-written
questions. This is the **requirements-capture instrument** — its answers should drive
build priority. Gaps: no draft autosave (20 questions lost on a refresh), checkbox
answers submit as raw codes, sensitive answers (late payers, bad suppliers) transit a
third party (Formspree) rather than your own DB.

**Verdict:** what exists is a first-class *sales demo* — roughly 15% of a Statii
replacement by function, but the hardest-to-fake part (a coherent, opinionated UI that
a machine-shop owner instantly understands) is already built. The gap is not more
screens; it's a **data model, auth, and real CRUD behind the screens that exist**.

---

## 2. The target: what Statii actually is

Statii (Statii Ltd, UK) is ERP/MRP for small subcontract manufacturers & engineering
job shops. Its documented scope: contact management, costing & estimating, sales
orders & document management, purchasing, inventory control, production planning &
scheduling, **shop floor data capture (SFDC)**, live profit reporting, automated
document creation & traceability, dispatch, and invoicing.

Its core value is one unbroken chain:

```
Enquiry → Estimate/Quote → Sales Order → Works Order (routing/operations)
→ Purchasing & Goods-In → Shop Floor Clocking → Dispatch/Delivery Note
→ Invoice → Quoted-vs-Actual Costing
```

**Pricing (public sources, 2026):** entry ~£99/month; plans reported around
$130/month (1 user) to $260/month (Professional, unlimited users) plus ~$6/user/month
for shop-floor data capture. Simple 30-day rolling contract.

**Cost comparison for in-house:** Supabase free tier (or £25/mo Pro) + free static
hosting runs QuoteFlow for **£0–£25/month total** vs £1,200–£3,000+/year for Statii.
The "at cost" pitch is real — and the margin space for reselling to other companies
is the difference.

**Legal note:** replicating a *feature set / workflow category* is lawful and normal —
functionality isn't copyright. Do **not** copy Statii's screens, icons, text, manuals
or code. QuoteFlow's existing UI is already visually its own — keep it that way.

---

## 3. Module-by-module gap map

| # | Statii module | QuoteFlow today | Gap | Effort |
|---|---------------|-----------------|-----|--------|
| 1 | Contacts / customer & supplier database | Hardcoded names only | Full CRUD, one `customers` + `suppliers` table, late-payer flags | S |
| 2 | Enquiries / RFQ log | UI done; partial DB round-trip | Finish: statuses, attachments (drawings!), link → quote | S |
| 3 | Costing & estimating | Static mock page | **The heart of Statii.** Cost model: material cost + machine-hour rates + labour + setup + margin; price-break quantities | M |
| 4 | Quote generation & documents | Static mock | Quote records, numbering (JNR-Q-xxx), PDF generation, email send, accept/reject tracking | M |
| 5 | Sales orders / works orders | Job Board is display-only | Works order entity with routing (operations, workcentres, est. times), job card printing | M/L |
| 6 | Production planning / scheduling | Static "bottleneck map" picture | Capacity view per machine/workcentre from works-order operations | L |
| 7 | Shop floor data capture | Barcode modal is a mock | Tablet clock-on/clock-off per operation → actual times. Statii charges extra for this; it's the moat for "quoted vs actual" | L |
| 8 | Purchasing & goods-in | Stock page static; "auto-purchase" fictional | PO records, supplier link, goods-in booking that updates stock | M |
| 9 | Inventory control | Static table; `stock` DB functions unused | Real stock table (SKU, levels, reorder points), movements ledger | M |
| 10 | Dispatch / delivery notes | **Absent entirely** (only Statii module with no screen) | Delivery note entity + PDF; required for engineering customers | S/M |
| 11 | Invoicing | Static; VAT is a hardcoded ×1.2 | Invoice records from jobs, aging buckets computed, mark-paid, Xero/Sage/QuickBooks export (CSV first) | M |
| 12 | Live profit reporting / KPIs | Static SVG charts | Compute from real tables; quoted-vs-actual per job is the killer report | M |
| 13 | Document management / traceability | Fake attachment chips | Supabase Storage for drawings/PDFs per RFQ/job; audit trail | M |
| — | **Quote & invoice chasing automation** (Approval Queue, Email Automation pages) | Mocked, but *designed* | **Statii doesn't do this.** This is QuoteFlow's differentiator — keep and build it (Resend/SendGrid + scheduled edge functions) | M |

Effort: S = days, M = 1–2 weeks, L = multiple weeks (single competent builder + AI assistance).

---

## 4. Architecture to get there (and to scale to other companies)

Keep the stack boring and cheap:

- **Database/auth/storage/functions: Supabase** (already chosen). Postgres schema with
  RLS from day one. Design every table with an `org_id` column now — multi-tenancy
  later becomes a policy change, not a rewrite: `org_id` FK → `orgs`, RLS
  `org_id = auth.jwt() ->> 'org_id'`. JNR is simply tenant #1.
- **Auth:** Supabase Auth, email+password, magic links for shop-floor tablets.
  The current publishable-key-no-auth setup is fine for a demo, unacceptable the day
  real customer data enters.
- **Frontend:** short term, keep enhancing the single-file SPA (it demos well and
  ships instantly). The moment Phase 2 starts, split into a Vite/Next.js app —
  a 500KB hand-edited HTML file will not survive works orders + scheduling.
- **Email automation:** Supabase Edge Functions on cron + Resend. This powers the
  Approval Queue for real.
- **PDF:** client-side (pdfmake) first; server-side later.
- **Hosting:** current static hosting (repo already has `vercel.json`) — £0.

Core schema (Phase 1): `orgs`, `users`, `customers`, `suppliers`, `rfqs`,
`rfq_attachments`, `quotes`, `quote_lines`, `jobs` (works orders), `job_operations`,
`invoices`, `invoice_lines`, `stock_items`, `stock_movements`, `purchase_orders`,
`email_queue`.

---

## 5. Build order (each phase independently usable by JNR)

**Phase 0 — hygiene (days): ✅ code DONE (July 2026).** Duplicate/XSS/dead-code
defects fixed; quotes, invoices (incl. computed aging) and stock now render from
the database with demo fallback; mark-paid and create-invoice persist; mobile
responsive; hash routing. Verified with a 51-check headless-browser suite.
Database side: JNREng project restored from pause; the schema/RLS/seed SQL is
versioned in `quoteflow/db/01..03_*.sql` — run the three files in order in the
Supabase SQL editor (one-time) to finish. *Result: the demo is real.*

**Phase 1 — quote-to-invoice loop (1–2 wks):** auth + customers + RFQ pipeline with
drawing uploads + quote builder with cost model + PDF + invoice records with real
aging. *Result: JNR can stop using spreadsheets for quoting & chasing. Already
competitive with ~40% of Statii at £0/month.*

**Phase 2 — works orders & purchasing (2–4 wks):** jobs with routing/operations,
job cards, POs, goods-in, stock movements, delivery notes. *Result: covers the
Statii core loop.*

**Phase 3 — shop floor & scheduling (3–6 wks):** tablet clock-on/off, capacity view,
quoted-vs-actual costing report. *Result: full Statii parity + the email-automation
differentiator Statii lacks.*

**Phase 4 — productise (ongoing):** multi-tenant onboarding, org settings/branding,
Stripe billing, marketing site. Discovery form becomes the standard onboarding
questionnaire for every new customer.

Use JNR's discovery-form answers to reorder Phases 1–3 by their actual pain.

---

## 6. Risks & flags

1. **This repo is the wrong home long-term.** A rival-to-Statii product living inside
   `rdhcoaching` (a fitness-coaching site repo) with client-named URLs will bite —
   split `quoteflow` into its own private repo before Phase 1 ends.
2. **Sensitive client data** (late payers, bad suppliers) currently flows through
   Formspree; move discovery submissions into your own Supabase once auth exists.
3. **RLS before real data.** The publishable key is in public HTML (normal), so
   table policies are the only security boundary. No real data until policies exist.
4. **Don't stack features on the 500KB HTML file past Phase 0** — it's already at the
   edge of maintainability (the duplicate-function bugs are the symptom).
5. **Statii's support/implementation service is part of what customers pay for** —
   when scaling to other companies, the discovery-form-driven onboarding is your
   equivalent; budget human time for it.
