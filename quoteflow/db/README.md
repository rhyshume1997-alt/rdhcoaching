# QuoteFlow database setup (JNREng Supabase project)

Project: `qtgqliczvyyrkibvxfqv` (JNREng) — the URL/key baked into
`quoteflow/index.html`.

Run these once, in order, in the Supabase Dashboard → SQL Editor
(https://supabase.com/dashboard/project/qtgqliczvyyrkibvxfqv/sql):

1. `01_align_schema.sql` — adds every column the app reads/writes to the
   existing `rfqs`, `quotes`, `invoices`, `stock` tables, plus updated_at
   triggers and unique refs. Idempotent.
2. `02_rls_policies.sql` — demo-open read/insert/update policies for the anon
   key (no delete). **Replace with authenticated + org policies before real
   customer data goes in.**
3. `03_seed_demo_data.sql` — demo rows with dates relative to today, so aging
   buckets and follow-up stages always look current. Idempotent.

Until 2 and 3 are applied the deployed app still works — every page falls back
to its built-in demo content — but saving RFQs/invoices will show an error
toast because row-level security has no policies yet.

Note: free-tier Supabase projects auto-pause after ~1 week of inactivity.
If the demo suddenly shows only fallback content, restore the project from the
Supabase dashboard.
