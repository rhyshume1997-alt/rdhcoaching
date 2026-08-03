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
