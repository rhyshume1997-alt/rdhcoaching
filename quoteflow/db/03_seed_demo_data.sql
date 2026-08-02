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
