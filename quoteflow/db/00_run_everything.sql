-- ============================================================
-- QuoteFlow COMPLETE DATABASE SETUP - single-paste version
-- ============================================================
-- Combines migrations 01-05 so the whole setup is ONE copy-paste
-- in the Supabase SQL editor (works fine from a phone browser):
--   https://supabase.com/dashboard/project/qtgqliczvyyrkibvxfqv/sql/new
-- Idempotent: safe to run more than once.
-- ACCESS IS INVITE-ONLY after this runs: only rhyshume1997@gmail.com
-- can create the first organisation (and adopts the seeded JNR data).
-- Everyone else needs an invite from inside the app (Team panel).
-- ============================================================

-- ==================== 01_align_schema.sql ====================

-- QuoteFlow Phase 0 - migration 1 of 3
-- Aligns the JNREng Supabase project (qtgqliczvyyrkibvxfqv) tables with the
-- columns the app in quoteflow/index.html reads and writes.
-- Idempotent: safe to re-run. Apply via Supabase SQL editor or CLI.

create or replace function public.set_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end $$;

-- ============ RFQS ============
alter table public.rfqs add column if not exists customer text;
alter table public.rfqs add column if not exists email text;
alter table public.rfqs add column if not exists phone text;
alter table public.rfqs add column if not exists description text;
alter table public.rfqs add column if not exists quantity integer;
alter table public.rfqs add column if not exists material text;
alter table public.rfqs add column if not exists estimated_value numeric(12,2);
alter table public.rfqs add column if not exists status text default 'new';
alter table public.rfqs add column if not exists notes text;
alter table public.rfqs add column if not exists created_at timestamptz default now();
alter table public.rfqs add column if not exists updated_at timestamptz default now();
alter table public.rfqs alter column status set default 'new';
alter table public.rfqs alter column created_at set default now();
alter table public.rfqs alter column updated_at set default now();
drop trigger if exists rfqs_updated_at on public.rfqs;
create trigger rfqs_updated_at before update on public.rfqs
  for each row execute function public.set_updated_at();

-- ============ QUOTES ============
alter table public.quotes add column if not exists quote_ref text;
alter table public.quotes add column if not exists customer text;
alter table public.quotes add column if not exists description text;
alter table public.quotes add column if not exists quantity integer;
alter table public.quotes add column if not exists unit_price numeric(12,2);
alter table public.quotes add column if not exists total numeric(12,2);
alter table public.quotes add column if not exists status text default 'sent';
alter table public.quotes add column if not exists sent_date date default current_date;
alter table public.quotes add column if not exists followups_sent integer default 0;
alter table public.quotes add column if not exists next_followup_date date;
alter table public.quotes add column if not exists replied boolean default false;
alter table public.quotes add column if not exists paid_detected boolean default false;
alter table public.quotes add column if not exists created_at timestamptz default now();
alter table public.quotes add column if not exists updated_at timestamptz default now();
alter table public.quotes alter column created_at set default now();
alter table public.quotes alter column updated_at set default now();
create unique index if not exists quotes_quote_ref_uniq on public.quotes (quote_ref);
drop trigger if exists quotes_updated_at on public.quotes;
create trigger quotes_updated_at before update on public.quotes
  for each row execute function public.set_updated_at();

-- ============ INVOICES ============
alter table public.invoices add column if not exists invoice_ref text;
alter table public.invoices add column if not exists customer text;
alter table public.invoices add column if not exists description text;
alter table public.invoices add column if not exists quantity integer;
alter table public.invoices add column if not exists unit_price numeric(12,2);
alter table public.invoices add column if not exists total numeric(12,2) default 0;
alter table public.invoices add column if not exists status text default 'outstanding';
alter table public.invoices add column if not exists sent_date date default current_date;
alter table public.invoices add column if not exists due_date date;
alter table public.invoices add column if not exists paid_at timestamptz;
alter table public.invoices add column if not exists late_payer_flag text;
alter table public.invoices add column if not exists created_at timestamptz default now();
alter table public.invoices add column if not exists updated_at timestamptz default now();
alter table public.invoices alter column created_at set default now();
alter table public.invoices alter column updated_at set default now();
create unique index if not exists invoices_invoice_ref_uniq on public.invoices (invoice_ref);
drop trigger if exists invoices_updated_at on public.invoices;
create trigger invoices_updated_at before update on public.invoices
  for each row execute function public.set_updated_at();

-- ============ STOCK ============
alter table public.stock add column if not exists sku text;
alter table public.stock add column if not exists name text;
alter table public.stock add column if not exists current_stock numeric(12,2) default 0;
alter table public.stock add column if not exists reorder_level numeric(12,2) default 0;
alter table public.stock add column if not exists reorder_qty numeric(12,2);
alter table public.stock add column if not exists unit_cost numeric(12,2);
alter table public.stock add column if not exists supplier text;
alter table public.stock add column if not exists lead_time text;
alter table public.stock add column if not exists auto_purchase boolean default false;
alter table public.stock add column if not exists order_note text;
alter table public.stock add column if not exists updated_at timestamptz default now();
alter table public.stock alter column updated_at set default now();
create unique index if not exists stock_sku_uniq on public.stock (sku);
drop trigger if exists stock_updated_at on public.stock;
create trigger stock_updated_at before update on public.stock
  for each row execute function public.set_updated_at();


-- ==================== 02_rls_policies.sql ====================

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


-- ==================== 03_seed_demo_data.sql ====================

-- QuoteFlow Phase 0 - migration 3 of 3
-- Seed data matching the built-in demo content, with dates relative to now()
-- so aging buckets and follow-up stages always look current.
-- Idempotent: RFQs seed only into an empty table; the rest upsert on their
-- unique refs and do nothing on conflict.

insert into public.rfqs (customer, email, description, quantity, material, estimated_value, status, notes, created_at)
select v.customer, v.email, v.description, v.quantity, v.material, v.estimated_value, v.status, v.notes, v.created_at
from (values
  ('Aerospace Components Ltd', 'procurement@aerospacecomponents.co.uk',
   'CNC machined titanium brackets x50 - Grade 5 Ti-6Al-4V', 50, 'Titanium Grade 5',
   8400.00, 'new', 'Full technical drawings (Rev 3) and material specification provided.', now() - interval '1 day'),
  ('Defence Manufacturing Co', 'procurement@defencemanufacturing.co.uk',
   'Precision milled components x200 - Material grade needs confirming', 200, 'Stainless Steel 304',
   12850.00, 'clarification', 'Stainless steel grade not specified. Cannot quote accurately without it.', now() - interval '3 days'),
  ('Precision Engineering Group', 'orders@precisioneng.co.uk',
   'Stainless steel shafts x30 - 316 grade, drawings attached', 30, 'Stainless Steel 316',
   6200.00, 'ready', 'All information provided. Similar job completed last month.', now() - interval '5 days')
) as v(customer, email, description, quantity, material, estimated_value, status, notes, created_at)
where not exists (select 1 from public.rfqs);

insert into public.quotes (quote_ref, customer, description, quantity, total, sent_date, followups_sent, next_followup_date, replied, paid_detected, status)
values
  ('JNR-Q-001', 'Aerospace Components Ltd', 'CNC machined titanium brackets x50', 50, 8400.00,
   current_date - 3, 0, current_date + 1, false, false, 'sent'),
  ('JNR-Q-002', 'Defence Manufacturing Co', 'Precision milled components x200', 200, 12850.00,
   current_date - 7, 2, current_date + 7, false, false, 'sent'),
  ('JNR-Q-003', 'Precision Engineering Group', 'Stainless steel shafts x30', 30, 6200.00,
   current_date - 10, 2, current_date + 4, false, false, 'sent'),
  ('JNR-Q-004', 'Industrial Systems Ltd', 'Aluminium plate components x75', 75, 15600.00,
   current_date - 2, 0, null, false, true, 'accepted'),
  ('JNR-Q-005', 'Marine Engineering Co', 'Bronze marine fittings x40', 40, 9400.00,
   current_date - 1, 0, null, true, false, 'sent')
on conflict (quote_ref) do nothing;

insert into public.invoices (invoice_ref, customer, description, total, status, sent_date, due_date, paid_at, late_payer_flag)
values
  ('INV-2026-084', 'Construction Services Ltd', 'Steel beam fabrication', 6000.00,
   'outstanding', current_date - 105, current_date - 75, null, 'CHRONIC LATE PAYER'),
  ('INV-2026-091', 'Marine Engineering Co', 'Bronze marine fittings', 4827.00,
   'outstanding', current_date - 77, current_date - 47, null, null),
  ('INV-2026-088', 'Tech Manufacturing Ltd', 'Aluminium plate components', 8000.00,
   'outstanding', current_date - 68, current_date - 38, null, null),
  ('INV-2026-095', 'Industrial Systems Ltd', 'Stainless steel shafts', 8800.00,
   'outstanding', current_date - 42, current_date - 12, null, null),
  ('INV-2026-097', 'Defence Manufacturing Co', 'Precision milled components', 6800.00,
   'outstanding', current_date - 35, current_date - 5, null, null),
  ('INV-2026-099', 'Aerospace Components Ltd', 'Titanium brackets x50', 10080.00,
   'outstanding', current_date - 22, current_date + 8, null, null),
  ('INV-2026-100', 'Precision Engineering Group', 'Machined housings x24', 8340.00,
   'outstanding', current_date - 12, current_date + 18, null, null),
  ('INV-2026-093', 'Precision Engineering Group', 'Stainless steel shafts x30', 6200.00,
   'paid', current_date - 40, current_date - 10, now() - interval '6 days', null)
on conflict (invoice_ref) do nothing;

insert into public.stock (sku, name, current_stock, reorder_level, reorder_qty, unit_cost, supplier, lead_time, auto_purchase, order_note)
values
  ('AL-6082-BAR-50', 'Aluminium 6082 Bar', 12, 25, 50, 42.00, 'MetalSupplies Ltd', '3-5 days', true, 'Auto-ordered today'),
  ('SS-304-PLT-2MM', 'Stainless Steel 304', 28, 30, 40, 32.50, 'Steel Supplies Co', '7-10 days', true, 'Pending trigger'),
  ('MS-PLT-10MM', 'Mild Steel Plate', 85, 40, 100, 18.20, 'Industrial Metals', '2-3 days', false, null),
  ('TI-G5-BAR-50', 'Titanium Grade 5', 45, 20, 30, 124.00, 'Aerospace Materials', '14-21 days', false, null),
  ('BR-C360-BAR', 'Brass C360', 8, 15, 25, 18.40, 'Copper & Brass Ltd', '5-7 days', true, 'Auto-ordered yesterday')
on conflict (sku) do nothing;


-- ==================== 04_phase1_auth_tenancy.sql ====================

-- QuoteFlow Phase 1 - authentication, organisations, tenant isolation,
-- outbox, jobs, machines, purchasing, settings.
-- Run AFTER 01-03. Idempotent: safe to re-run.

-- ============================================================
-- 1. ORGANISATIONS & MEMBERSHIP
-- ============================================================
create table if not exists public.orgs (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  created_at timestamptz not null default now()
);

create table if not exists public.org_members (
  org_id uuid not null references public.orgs(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  role text not null default 'owner' check (role in ('owner','office','shop_floor')),
  created_at timestamptz not null default now(),
  primary key (org_id, user_id)
);

-- Membership lookup used by every policy. SECURITY DEFINER so policies can
-- read org_members without recursive RLS issues.
create or replace function public.my_org_ids()
returns setof uuid
language sql security definer set search_path = public stable as $$
  select org_id from public.org_members where user_id = auth.uid();
$$;

-- ============================================================
-- 2. NEW BUSINESS TABLES
-- ============================================================
create table if not exists public.email_outbox (
  id bigint generated always as identity primary key,
  org_id uuid,
  kind text not null check (kind in ('quote_send','clarification','gentle_reminder','firm_chase','final_notice')),
  to_email text,
  subject text not null,
  body text,
  related_ref text,
  customer text,
  amount numeric(12,2),
  days_overdue integer,
  status text not null default 'pending_approval' check (status in ('pending_approval','queued','approved','skipped','sent')),
  approved_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
drop trigger if exists email_outbox_updated_at on public.email_outbox;
create trigger email_outbox_updated_at before update on public.email_outbox
  for each row execute function public.set_updated_at();

create table if not exists public.machines (
  id bigint generated always as identity primary key,
  org_id uuid,
  name text not null,
  type text,
  hours_run numeric(12,1) default 0,
  last_maintenance date,
  next_due date,
  created_at timestamptz not null default now()
);

create table if not exists public.machine_logs (
  id bigint generated always as identity primary key,
  org_id uuid,
  machine_id bigint references public.machines(id) on delete cascade,
  note text not null,
  log_date date not null default current_date,
  created_at timestamptz not null default now()
);

create table if not exists public.stock_movements (
  id bigint generated always as identity primary key,
  org_id uuid,
  sku text not null,
  name text,
  delta numeric(12,2) not null,
  direction text not null check (direction in ('in','out')),
  note text,
  created_at timestamptz not null default now()
);

create table if not exists public.org_settings (
  org_id uuid primary key,
  settings jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);
drop trigger if exists org_settings_updated_at on public.org_settings;
create trigger org_settings_updated_at before update on public.org_settings
  for each row execute function public.set_updated_at();

-- Align pre-existing jobs & purchase_orders tables with app columns
alter table public.jobs add column if not exists job_ref text;
alter table public.jobs add column if not exists customer text;
alter table public.jobs add column if not exists description text;
alter table public.jobs add column if not exists stage text default 'material';
alter table public.jobs add column if not exists status text default 'on_track';
alter table public.jobs add column if not exists due_date date;
alter table public.jobs add column if not exists value numeric(12,2);
alter table public.jobs add column if not exists created_at timestamptz default now();
create unique index if not exists jobs_job_ref_uniq on public.jobs (job_ref);

alter table public.purchase_orders add column if not exists po_ref text;
alter table public.purchase_orders add column if not exists supplier text;
alter table public.purchase_orders add column if not exists sku text;
alter table public.purchase_orders add column if not exists material_name text;
alter table public.purchase_orders add column if not exists quantity numeric(12,2);
alter table public.purchase_orders add column if not exists unit_cost numeric(12,2);
alter table public.purchase_orders add column if not exists total numeric(12,2);
alter table public.purchase_orders add column if not exists status text default 'ordered';
alter table public.purchase_orders add column if not exists created_at timestamptz default now();

-- org_id on every business table
alter table public.rfqs add column if not exists org_id uuid;
alter table public.quotes add column if not exists org_id uuid;
alter table public.invoices add column if not exists org_id uuid;
alter table public.stock add column if not exists org_id uuid;
alter table public.jobs add column if not exists org_id uuid;
alter table public.purchase_orders add column if not exists org_id uuid;

-- ============================================================
-- 3. ORG STAMPING - new rows inherit the writer's org
-- ============================================================
create or replace function public.stamp_org_id()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  if new.org_id is null then
    select org_id into new.org_id from public.org_members
    where user_id = auth.uid() limit 1;
  end if;
  return new;
end $$;

do $$
declare t text;
begin
  foreach t in array array['rfqs','quotes','invoices','stock','jobs','purchase_orders','email_outbox','machines','machine_logs','stock_movements']
  loop
    execute format('drop trigger if exists stamp_org_%I on public.%I', t, t);
    execute format('create trigger stamp_org_%I before insert on public.%I for each row execute function public.stamp_org_id()', t, t);
  end loop;
end $$;

-- ============================================================
-- 4. ORG BOOTSTRAP
-- Called after login. Returns the caller's org, creating one (and claiming
-- any legacy rows with no org, if this is the first org) when needed.
-- ============================================================
create or replace function public.ensure_org(org_name text)
returns table (org_id uuid, org_display_name text)
language plpgsql security definer set search_path = public as $$
declare
  v_org uuid;
  v_name text;
  v_first boolean;
begin
  if auth.uid() is null then
    raise exception 'not authenticated';
  end if;

  select m.org_id, o.name into v_org, v_name
  from public.org_members m join public.orgs o on o.id = m.org_id
  where m.user_id = auth.uid() limit 1;

  if v_org is null then
    select not exists (select 1 from public.orgs) into v_first;
    v_name := coalesce(nullif(trim(org_name), ''), 'My Company');
    insert into public.orgs (name) values (v_name) returning id into v_org;
    insert into public.org_members (org_id, user_id, role) values (v_org, auth.uid(), 'owner');

    if v_first then
      -- First organisation adopts the pre-org rows (JNR's seeded data)
      update public.rfqs set org_id = v_org where public.rfqs.org_id is null;
      update public.quotes set org_id = v_org where public.quotes.org_id is null;
      update public.invoices set org_id = v_org where public.invoices.org_id is null;
      update public.stock set org_id = v_org where public.stock.org_id is null;
      update public.jobs set org_id = v_org where public.jobs.org_id is null;
      update public.purchase_orders set org_id = v_org where public.purchase_orders.org_id is null;
      update public.email_outbox set org_id = v_org where public.email_outbox.org_id is null;
      update public.machines set org_id = v_org where public.machines.org_id is null;
      update public.machine_logs set org_id = v_org where public.machine_logs.org_id is null;
      update public.stock_movements set org_id = v_org where public.stock_movements.org_id is null;
    end if;
  end if;

  return query select v_org, v_name;
end $$;

grant execute on function public.ensure_org(text) to authenticated;
revoke execute on function public.ensure_org(text) from anon;

-- ============================================================
-- 5. TENANT-SCOPED RLS - replaces the Phase 0 demo-open policies
-- ============================================================
do $$
declare t text;
begin
  foreach t in array array['rfqs','quotes','invoices','stock','jobs','purchase_orders','email_outbox','machines','machine_logs','stock_movements','orgs','org_members','org_settings']
  loop
    execute format('alter table public.%I enable row level security', t);
  end loop;

  -- drop the demo-open policies from Phase 0
  foreach t in array array['rfqs','quotes','invoices','stock']
  loop
    execute format('drop policy if exists "demo read %s" on public.%I', t, t);
    execute format('drop policy if exists "demo insert %s" on public.%I', t, t);
    execute format('drop policy if exists "demo update %s" on public.%I', t, t);
  end loop;

  -- org-scoped read/insert/update on business tables (no delete anywhere)
  foreach t in array array['rfqs','quotes','invoices','stock','jobs','purchase_orders','email_outbox','machines','machine_logs','stock_movements']
  loop
    execute format('drop policy if exists "org read %s" on public.%I', t, t);
    execute format('drop policy if exists "org insert %s" on public.%I', t, t);
    execute format('drop policy if exists "org update %s" on public.%I', t, t);
    execute format('create policy "org read %s" on public.%I for select to authenticated using (org_id in (select public.my_org_ids()))', t, t);
    execute format('create policy "org insert %s" on public.%I for insert to authenticated with check (org_id in (select public.my_org_ids()))', t, t);
    execute format('create policy "org update %s" on public.%I for update to authenticated using (org_id in (select public.my_org_ids()))', t, t);
  end loop;
end $$;

drop policy if exists "read own orgs" on public.orgs;
create policy "read own orgs" on public.orgs for select to authenticated
  using (id in (select public.my_org_ids()));

drop policy if exists "read own membership" on public.org_members;
create policy "read own membership" on public.org_members for select to authenticated
  using (user_id = auth.uid());

drop policy if exists "org read settings" on public.org_settings;
drop policy if exists "org insert settings" on public.org_settings;
drop policy if exists "org update settings" on public.org_settings;
create policy "org read settings" on public.org_settings for select to authenticated
  using (org_id in (select public.my_org_ids()));
create policy "org insert settings" on public.org_settings for insert to authenticated
  with check (org_id in (select public.my_org_ids()));
create policy "org update settings" on public.org_settings for update to authenticated
  using (org_id in (select public.my_org_ids()));

-- ============================================================
-- 6. SEED - jobs, machines, outbox drafts (org_id null until first
--    organisation claims them via ensure_org)
-- ============================================================
insert into public.jobs (job_ref, customer, description, stage, status, due_date, value)
values
  ('JNR-J-218', 'Aerospace Components', 'Titanium brackets x50', 'machining', 'on_track', current_date + 5, 8400.00),
  ('JNR-J-219', 'Defence Manufacturing', 'Milled components x200', 'setup', 'on_track', current_date + 9, 12850.00),
  ('JNR-J-220', 'Precision Engineering', 'Stainless shafts x30', 'inspection', 'at_risk', current_date + 3, 6200.00),
  ('JNR-J-221', 'Industrial Systems', 'Aluminium plates x75', 'material', 'on_track', current_date + 13, 15600.00),
  ('JNR-J-222', 'Marine Engineering Co', 'Brass fittings x120', 'machining', 'overdue', current_date - 2, 9400.00)
on conflict (job_ref) do nothing;

insert into public.machines (name, type, hours_run, last_maintenance, next_due)
select v.name, v.type, v.hours_run, v.last_maintenance, v.next_due
from (values
  ('Haas VF-2', 'CNC Mill', 2847, current_date - 70, current_date - 10),
  ('Mazak Quick Turn', 'CNC Lathe', 1923, current_date - 24, current_date + 3),
  ('DMG Mori NLX 2500', 'CNC Lathe', 1204, current_date - 7, current_date + 54),
  ('Doosan DNM 4500', 'CNC Mill', 945, current_date - 21, current_date + 40),
  ('Bridgeport Series 1', 'Manual Mill', 3124, current_date - 60, current_date + 1),
  ('Colchester Mascot 1600', 'Manual Lathe', 4681, current_date - 115, current_date - 55)
) as v(name, type, hours_run, last_maintenance, next_due)
where not exists (select 1 from public.machines);

insert into public.email_outbox (kind, to_email, subject, body, related_ref, customer, amount, days_overdue, status)
select v.kind, v.to_email, v.subject, v.body, v.related_ref, v.customer, v.amount, v.days_overdue, 'pending_approval'
from (values
  ('final_notice', 'accounts@constructionservices.co.uk',
   'Final Notice - Invoice INV-2026-084 - £6,000 Overdue',
   E'Dear Sir/Madam,\n\nThis is a final notice regarding outstanding invoice INV-2026-084 for £6,000.00, now 75 days overdue.\n\nDespite previous reminders we have not received payment or correspondence regarding this invoice. Unless payment is received within 7 days we will have no option but to pass this matter to our debt recovery partners.\n\nRegards,\nJNR Engineering Limited',
   'INV-2026-084', 'Construction Services Ltd', 6000.00, 75),
  ('firm_chase', 'accounts@marineengineering.co.uk',
   'Overdue Invoice - INV-2026-091 - £4,827 - 47 Days Outstanding',
   E'Hello,\n\nI''m following up on invoice INV-2026-091 for £4,827.00 which is now 47 days overdue.\n\nCould you let me know when we can expect payment? If there''s an issue with the invoice, please get in touch.\n\nRegards,\nJNR Engineering Limited',
   'INV-2026-091', 'Marine Engineering Co', 4827.00, 47),
  ('gentle_reminder', 'accounts@defencemanufacturing.co.uk',
   'Friendly Reminder - Invoice INV-2026-097',
   E'Hi Team,\n\nJust a quick reminder that invoice INV-2026-097 for £6,800.00 was due recently.\n\nIf you''ve already arranged payment please ignore this. Otherwise could you let me know roughly when we can expect it?\n\nThanks,\nJNR Engineering Limited',
   'INV-2026-097', 'Defence Manufacturing Co', 6800.00, 5)
) as v(kind, to_email, subject, body, related_ref, customer, amount, days_overdue)
where not exists (select 1 from public.email_outbox);


-- ==================== 05_invite_only_access.sql ====================

-- QuoteFlow Phase 1.1 - INVITE-ONLY ACCESS
-- Signing up no longer grants anything: a user must be on the allowlist
-- (app_access) to enter a workspace. Owners invite teammates by email.
-- Run AFTER 04. Idempotent: safe to re-run.

create table if not exists public.app_access (
  email text primary key,
  org_id uuid references public.orgs(id) on delete cascade,  -- null = may create a NEW organisation
  role text not null default 'office' check (role in ('owner','office','shop_floor')),
  invited_by uuid,
  created_at timestamptz not null default now()
);
alter table public.app_access enable row level security;

-- Owners manage the invites of their own organisation
drop policy if exists "owners read invites" on public.app_access;
drop policy if exists "owners create invites" on public.app_access;
drop policy if exists "owners revoke invites" on public.app_access;
create policy "owners read invites" on public.app_access for select to authenticated
  using (org_id in (select org_id from public.org_members where user_id = auth.uid() and role = 'owner'));
create policy "owners create invites" on public.app_access for insert to authenticated
  with check (org_id in (select org_id from public.org_members where user_id = auth.uid() and role = 'owner'));
create policy "owners revoke invites" on public.app_access for delete to authenticated
  using (org_id in (select org_id from public.org_members where user_id = auth.uid() and role = 'owner'));

-- Team visibility: members can see who is in their organisation
drop policy if exists "read org membership" on public.org_members;
create policy "read org membership" on public.org_members for select to authenticated
  using (org_id in (select public.my_org_ids()));

-- Bootstrap operator: may create the first organisation (and adopt the
-- seeded data). Uses the repository owner's account email.
insert into public.app_access (email, org_id, role)
values ('rhyshume1997@gmail.com', null, 'owner')
on conflict (email) do nothing;

-- ensure_org, invite-only edition
create or replace function public.ensure_org(org_name text)
returns table (org_id uuid, org_display_name text)
language plpgsql security definer set search_path = public as $$
declare
  v_org uuid;
  v_name text;
  v_first boolean;
  v_email text;
  v_access public.app_access%rowtype;
begin
  if auth.uid() is null then
    raise exception 'not authenticated';
  end if;

  -- Existing membership always wins
  select m.org_id, o.name into v_org, v_name
  from public.org_members m join public.orgs o on o.id = m.org_id
  where m.user_id = auth.uid() limit 1;
  if v_org is not null then
    return query select v_org, v_name;
    return;
  end if;

  -- No membership: the allowlist decides
  select lower(u.email) into v_email from auth.users u where u.id = auth.uid();
  select * into v_access from public.app_access a where lower(a.email) = v_email;
  if not found then
    raise exception 'ACCESS_DENIED: this workspace is invite-only';
  end if;

  if v_access.org_id is not null then
    -- Invited into an existing organisation: join it with the invited role
    insert into public.org_members (org_id, user_id, role)
    values (v_access.org_id, auth.uid(), v_access.role)
    on conflict do nothing;
    select o.name into v_name from public.orgs o where o.id = v_access.org_id;
    return query select v_access.org_id, v_name;
    return;
  end if;

  -- Entitled to create a brand-new organisation
  select not exists (select 1 from public.orgs) into v_first;
  v_name := coalesce(nullif(trim(org_name), ''), 'My Company');
  insert into public.orgs (name) values (v_name) returning id into v_org;
  insert into public.org_members (org_id, user_id, role) values (v_org, auth.uid(), 'owner');
  -- Tie the allowlist entry to the created org so it cannot be reused
  update public.app_access set org_id = v_org where lower(email) = v_email;

  if v_first then
    -- First organisation adopts the pre-org rows (JNR's seeded data)
    update public.rfqs set org_id = v_org where public.rfqs.org_id is null;
    update public.quotes set org_id = v_org where public.quotes.org_id is null;
    update public.invoices set org_id = v_org where public.invoices.org_id is null;
    update public.stock set org_id = v_org where public.stock.org_id is null;
    update public.jobs set org_id = v_org where public.jobs.org_id is null;
    update public.purchase_orders set org_id = v_org where public.purchase_orders.org_id is null;
    update public.email_outbox set org_id = v_org where public.email_outbox.org_id is null;
    update public.machines set org_id = v_org where public.machines.org_id is null;
    update public.machine_logs set org_id = v_org where public.machine_logs.org_id is null;
    update public.stock_movements set org_id = v_org where public.stock_movements.org_id is null;
  end if;

  return query select v_org, v_name;
end $$;

grant execute on function public.ensure_org(text) to authenticated;
revoke execute on function public.ensure_org(text) from anon;
