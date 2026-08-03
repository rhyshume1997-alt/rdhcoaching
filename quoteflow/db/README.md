# QuoteFlow database setup (JNREng Supabase project)

Project: `qtgqliczvyyrkibvxfqv` (JNREng) — the URL/key baked into
`quoteflow/index.html`.

**Fastest path (works from a phone): run `00_run_everything.sql`** — it is
all four migrations combined into one idempotent paste, and the whole
sequence has been tested end-to-end on a clean Postgres 16 including a
two-company isolation test (see repo history). One paste, done.

Or run the four files individually, in order, in the Supabase Dashboard →
SQL Editor (https://supabase.com/dashboard/project/qtgqliczvyyrkibvxfqv/sql):

1. `01_align_schema.sql` — adds every column the app reads/writes to the
   existing `rfqs`, `quotes`, `invoices`, `stock` tables, plus updated_at
   triggers and unique refs. Idempotent.
2. `02_rls_policies.sql` — Phase 0 demo-open policies. Still run it (04
   replaces these policies cleanly), or skip straight to 04 if you never
   want an unauthenticated demo mode.
3. `03_seed_demo_data.sql` — demo rows with dates relative to today, so aging
   buckets and follow-up stages always look current. Idempotent.
5. `05_invite_only_access.sql` — **Invite-only lockdown.** Signing up no
   longer grants access on its own; a user must be on the `app_access`
   allowlist. Only `rhyshume1997@gmail.com` may create the first
   organisation (and adopts the seed). Everyone else needs an invite,
   which owners send from the in-app **Team** panel. Verified with an
   attack test: uninvited signups are refused, non-owners cannot invite
   or revoke, and each invite is single-use (bound to its org once used).

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
- The workspace is INVITE-ONLY. `rhyshume1997@gmail.com` is the seeded
  bootstrap owner — sign up with that email first; it creates JNR's
  organisation and adopts all seeded data. Nobody else can get in until
  you invite their email from the in-app Team panel, so sharing the URL
  is now safe: strangers who open it and sign up are refused a workspace.
- To change the bootstrap email, edit the INSERT in
  `05_invite_only_access.sql` before running the setup.

Note: free-tier Supabase projects auto-pause after ~1 week of inactivity.
If the demo suddenly shows only fallback content, restore the project from the
Supabase dashboard.
