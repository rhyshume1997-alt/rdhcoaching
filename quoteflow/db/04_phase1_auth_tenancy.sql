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
