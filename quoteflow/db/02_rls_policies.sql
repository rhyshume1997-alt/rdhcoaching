-- QuoteFlow Phase 0 - migration 2 of 3
-- Demo-open RLS policies. The app ships the publishable (anon) key with no
-- auth layer yet, so anon needs read/insert/update for the demo to function.
-- Deliberately NO delete policy anywhere.
--
-- !! SECURITY WARNING !!
-- 04_phase1_auth_tenancy.sql REPLACES these policies with org-scoped,
-- authenticated-only ones. NEVER re-run this file on its own after 04 has
-- been applied - doing so would reopen anonymous read/write access.
-- Always run via 00_run_everything.sql, which applies 04 last.

alter table public.rfqs enable row level security;
alter table public.quotes enable row level security;
alter table public.invoices enable row level security;
alter table public.stock enable row level security;

drop policy if exists "demo read rfqs" on public.rfqs;
drop policy if exists "demo insert rfqs" on public.rfqs;
drop policy if exists "demo update rfqs" on public.rfqs;
create policy "demo read rfqs" on public.rfqs for select using (true);
create policy "demo insert rfqs" on public.rfqs for insert with check (true);
create policy "demo update rfqs" on public.rfqs for update using (true);

drop policy if exists "demo read quotes" on public.quotes;
drop policy if exists "demo insert quotes" on public.quotes;
drop policy if exists "demo update quotes" on public.quotes;
create policy "demo read quotes" on public.quotes for select using (true);
create policy "demo insert quotes" on public.quotes for insert with check (true);
create policy "demo update quotes" on public.quotes for update using (true);

drop policy if exists "demo read invoices" on public.invoices;
drop policy if exists "demo insert invoices" on public.invoices;
drop policy if exists "demo update invoices" on public.invoices;
create policy "demo read invoices" on public.invoices for select using (true);
create policy "demo insert invoices" on public.invoices for insert with check (true);
create policy "demo update invoices" on public.invoices for update using (true);

drop policy if exists "demo read stock" on public.stock;
drop policy if exists "demo insert stock" on public.stock;
drop policy if exists "demo update stock" on public.stock;
create policy "demo read stock" on public.stock for select using (true);
create policy "demo insert stock" on public.stock for insert with check (true);
create policy "demo update stock" on public.stock for update using (true);
