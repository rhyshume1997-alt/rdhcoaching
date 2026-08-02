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
