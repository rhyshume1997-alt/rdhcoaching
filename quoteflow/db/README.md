# QuoteFlow database setup (JNREng Supabase project)

Project: `qtgqliczvyyrkibvxfqv` (JNREng) — the URL/key baked into
`quoteflow/index.html`.

Run these once, in order, in the Supabase Dashboard → SQL Editor
(https://supabase.com/dashboard/project/qtgqliczvyyrkibvxfqv/sql):

1. `01_align_schema.sql` — adds every column the app reads/writes to the
   existing `rfqs`, `quotes`, `invoices`, `stock` tables, plus updated_at
   triggers and unique refs. Idempotent.
2. `02_rls_policies.sql` — Phase 0 demo-open policies. Still run it (04
   replaces these policies cleanly), or skip straight to 04 if you never
   want an unauthenticated demo mode.
3. `03_seed_demo_data.sql` — demo rows with dates relative to today, so aging
   buckets and follow-up stages always look current. Idempotent.
4. `04_phase1_auth_tenancy.sql` — **Phase 1.** Organisations + membership,
   org-scoped RLS on every table (replaces the demo-open policies), org
   stamping triggers, the `ensure_org` bootstrap function, email outbox,
   jobs/machines/purchasing tables and their seeds. After this runs, the
   app REQUIRES login: anonymous visitors see nothing and can write nothing,
   and each company sees only its own rows.

## Auth setup (one-time, Supabase Dashboard → Authentication)

- Email provider is enabled by default; nothing to install.
- Recommended for the first login: Authentication → Sign In / Up →
  disable "Confirm email" so the first account works instantly, or keep it
  on and click the confirmation link Supabase emails you.
- The FIRST account to sign up creates the first organisation and
  automatically adopts all the seeded JNR data. Sign up with Rhys/JNR's
  email first, before sharing the URL with anyone.

Note: free-tier Supabase projects auto-pause after ~1 week of inactivity.
If the demo suddenly shows only fallback content, restore the project from the
Supabase dashboard.
