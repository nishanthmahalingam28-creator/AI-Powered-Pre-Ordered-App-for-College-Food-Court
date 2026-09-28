-- Phase 1: Supabase/PostgreSQL foundation.
-- Target database for the React + TypeScript migration.
-- Legacy MySQL/Flask code is intentionally left untouched in this phase.

create extension if not exists pgcrypto;

create type public.app_role as enum ('customer','vendor','admin');
create type public.customer_type as enum ('student','faculty','guest');
create type public.shop_status as enum ('OPEN','CLOSED','TEMPORARILY_UNAVAILABLE');
create type public.order_status as enum ('pending','preparing','ready','completed','cancelled');
create type public.payment_status as enum ('pending','successful','failed','cancelled','refunded');

create table public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  legacy_id bigint unique,
  email text unique,
  role public.app_role not null default 'customer',
  is_active boolean not null default true,
  is_temporary boolean not null default false,
  account_expires_at timestamptz,
  status text not null default 'ACTIVE',
  full_name text,
  mobile text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.customer_profiles (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null unique references public.profiles(id) on delete cascade,
  customer_type public.customer_type not null default 'student',
  identifier text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.shops (
  id uuid primary key default gen_random_uuid(),
  legacy_id bigint unique,
  name text not null,
  slug text not null unique,
  owner_user_id uuid references public.profiles(id) on delete set null,
  description text,
  category text default 'Multi-Cuisine',
  image_url text,
  is_active boolean not null default true,
  operational_status public.shop_status not null default 'OPEN',
  created_by_admin boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.menu_items (
  id uuid primary key default gen_random_uuid(),
  legacy_id bigint unique,
  shop_id uuid not null references public.shops(id) on delete cascade,
  name text not null,
  description text,
  price numeric(10,2) not null check (price >= 0),
  category text not null default 'Main Course',
  meal_period text not null default 'lunch' check (meal_period in ('breakfast','lunch','dinner')),
  quantity integer not null default 0 check (quantity >= 0),
  is_available boolean not null default true,
  image_url text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.orders (
  id uuid primary key default gen_random_uuid(),
  legacy_id bigint unique,
  order_reference text not null unique,
  customer_id uuid not null references public.profiles(id) on delete restrict,
  shop_id uuid not null references public.shops(id) on delete restrict,
  total_amount numeric(10,2) not null check (total_amount >= 0),
  order_status public.order_status not null default 'pending',
  payment_status public.payment_status not null default 'pending',
  payment_method text not null default 'razorpay',
  pickup_otp_hash text,
  pickup_at timestamptz,
  payment_time timestamptz,
  preparing_time timestamptz,
  ready_time timestamptz,
  completed_time timestamptz,
  cancellation_time timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.order_items (
  id uuid primary key default gen_random_uuid(),
  order_id uuid not null references public.orders(id) on delete cascade,
  menu_item_id uuid references public.menu_items(id) on delete set null,
  item_name text not null,
  meal_period text not null default 'lunch' check (meal_period in ('breakfast','lunch','dinner')),
  unit_price numeric(10,2) not null check (unit_price >= 0),
  quantity integer not null default 1 check (quantity > 0),
  subtotal numeric(10,2) not null check (subtotal >= 0),
  created_at timestamptz not null default now()
);

create table public.payments (
  id uuid primary key default gen_random_uuid(),
  order_id uuid not null references public.orders(id) on delete cascade,
  customer_id uuid references public.profiles(id) on delete set null,
  provider text not null default 'razorpay',
  method text not null default 'razorpay',
  amount numeric(10,2) not null check (amount >= 0),
  currency text not null default 'INR',
  status public.payment_status not null default 'pending',
  transaction_ref text not null unique,
  gateway_order_id text,
  gateway_payment_id text,
  failure_reason text,
  paid_at timestamptz,
  refunded_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.notifications (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  order_id uuid references public.orders(id) on delete cascade,
  type text not null,
  title text not null,
  message text not null,
  is_read boolean not null default false,
  delivery_status text not null default 'delivered',
  delivered_at timestamptz,
  failure_reason text,
  read_at timestamptz,
  created_at timestamptz not null default now()
);

create table public.cart_items (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  menu_item_id uuid not null references public.menu_items(id) on delete cascade,
  quantity integer not null default 1 check (quantity > 0),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, menu_item_id)
);

create table public.expenses (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  order_id uuid unique references public.orders(id) on delete set null,
  amount numeric(10,2) not null check (amount >= 0),
  category text not null,
  description text not null,
  expense_date date not null default current_date,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.budgets (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  category text not null,
  amount_limit numeric(10,2) not null check (amount_limit >= 0),
  period text not null default 'monthly',
  start_date date,
  end_date date,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.audit_logs (
  id uuid primary key default gen_random_uuid(),
  actor_id uuid references public.profiles(id) on delete set null,
  action text not null,
  entity_type text not null,
  entity_id text,
  details jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table public.contact_messages (
  id uuid primary key default gen_random_uuid(),
  full_name text not null,
  email text not null,
  subject text not null,
  message text not null,
  status text not null default 'new' check (status in ('new','read','resolved')),
  read_at timestamptz,
  resolved_at timestamptz,
  created_at timestamptz not null default now()
);

create table public.vendor_daily_surveys (
  id uuid primary key default gen_random_uuid(),
  vendor_user_id uuid not null references public.profiles(id) on delete cascade,
  shop_id uuid not null references public.shops(id) on delete cascade,
  survey_date date not null,
  is_serving_today boolean not null default true,
  breakfast_start time not null default '06:00',
  breakfast_end time not null default '10:00',
  lunch_start time not null default '10:30',
  lunch_end time not null default '15:00',
  dinner_start time not null default '17:00',
  dinner_end time not null default '21:00',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (vendor_user_id,survey_date),
  unique (shop_id,survey_date)
);

create table public.vendor_daily_menu_items (
  id uuid primary key default gen_random_uuid(),
  survey_id uuid not null references public.vendor_daily_surveys(id) on delete cascade,
  shop_id uuid not null references public.shops(id) on delete cascade,
  menu_item_id uuid not null references public.menu_items(id) on delete cascade,
  meal_period text not null check (meal_period in ('breakfast','lunch','dinner')),
  item_name text not null,
  price numeric(10,2) not null check (price >= 0),
  quantity integer not null default 0 check (quantity >= 0),
  is_available boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (survey_id,menu_item_id,meal_period)
);

-- Food Survey replaces the legacy morning-survey model.
-- Exactly one response per student per meal per day.
create table public.food_survey_submissions (
  id uuid primary key default gen_random_uuid(),
  student_user_id uuid not null references public.profiles(id) on delete cascade,
  shop_id uuid not null references public.shops(id) on delete cascade,
  survey_date date not null default current_date,
  meal_period text not null check (meal_period in ('breakfast','lunch','dinner')),
  need_food boolean not null,
  submitted_at timestamptz not null default now(),
  unique (student_user_id,survey_date,meal_period)
);

create index idx_profiles_role on public.profiles(role);
create index idx_shops_owner_status on public.shops(owner_user_id,operational_status);
create index idx_menu_shop_available on public.menu_items(shop_id,is_available,quantity);
create index idx_menu_shop_meal on public.menu_items(shop_id,meal_period);
create index idx_orders_customer_status on public.orders(customer_id,order_status,created_at desc);
create index idx_orders_shop_status on public.orders(shop_id,order_status,created_at desc);
create index idx_orders_shop_payment on public.orders(shop_id,payment_status);
create index idx_order_items_order on public.order_items(order_id);
create index idx_payments_order on public.payments(order_id);
create index idx_notifications_user_unread on public.notifications(user_id,is_read,created_at desc);
create index idx_cart_user on public.cart_items(user_id);
create index idx_expenses_user_date on public.expenses(user_id,expense_date desc);
create index idx_budgets_user_period on public.budgets(user_id,period);
create index idx_vendor_surveys_shop_date on public.vendor_daily_surveys(shop_id,survey_date);
create index idx_vendor_daily_menu_shop_meal on public.vendor_daily_menu_items(shop_id,meal_period);
create index idx_food_survey_shop_date_meal on public.food_survey_submissions(shop_id,survey_date,meal_period);

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

do $$
declare
  t text;
begin
  foreach t in array array[
    'profiles','customer_profiles','shops','menu_items','orders','payments',
    'notifications','cart_items','expenses','budgets',
    'vendor_daily_surveys','vendor_daily_menu_items'
  ] loop
    execute format('create trigger %I before update on public.%I for each row execute function public.set_updated_at()',t||'_updated_at',t);
  end loop;
end $$;

create schema if not exists private;

create or replace function private.current_app_role()
returns public.app_role
language sql
stable
security definer
set search_path = ''
as $$
  select role from public.profiles where id = (select auth.uid());
$$;

create or replace function private.is_admin()
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select coalesce((select private.current_app_role()) = 'admin'::public.app_role,false);
$$;

create or replace function private.is_vendor_for_shop(target_shop uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1 from public.shops s
    where s.id = target_shop
      and s.owner_user_id = (select auth.uid())
      and (select private.current_app_role()) = 'vendor'::public.app_role
  );
$$;

alter table public.profiles enable row level security;
alter table public.customer_profiles enable row level security;
alter table public.shops enable row level security;
alter table public.menu_items enable row level security;
alter table public.orders enable row level security;
alter table public.order_items enable row level security;
alter table public.payments enable row level security;
alter table public.notifications enable row level security;
alter table public.cart_items enable row level security;
alter table public.expenses enable row level security;
alter table public.budgets enable row level security;
alter table public.audit_logs enable row level security;
alter table public.contact_messages enable row level security;
alter table public.vendor_daily_surveys enable row level security;
alter table public.vendor_daily_menu_items enable row level security;
alter table public.food_survey_submissions enable row level security;

revoke all on all tables in schema public from anon;
grant select,insert,update,delete on all tables in schema public to authenticated;

create policy profiles_self_or_admin_select on public.profiles
for select to authenticated using (id=(select auth.uid()) or (select private.is_admin()));
create policy profiles_self_or_admin_update on public.profiles
for update to authenticated
using (id=(select auth.uid()) or (select private.is_admin()))
with check (id=(select auth.uid()) or (select private.is_admin()));

create policy customer_profiles_self_or_admin on public.customer_profiles
for all to authenticated
using (user_id=(select auth.uid()) or (select private.is_admin()))
with check (user_id=(select auth.uid()) or (select private.is_admin()));

create policy shops_authenticated_read on public.shops
for select to authenticated using (true);
create policy shops_admin_write on public.shops
for all to authenticated
using ((select private.is_admin())) with check ((select private.is_admin()));
create policy shops_vendor_update_own on public.shops
for update to authenticated
using (owner_user_id=(select auth.uid()))
with check (owner_user_id=(select auth.uid()));

create policy menu_authenticated_read on public.menu_items
for select to authenticated using (true);
create policy menu_vendor_insert on public.menu_items
for insert to authenticated with check ((select private.is_vendor_for_shop(shop_id)));
create policy menu_vendor_update on public.menu_items
for update to authenticated
using ((select private.is_vendor_for_shop(shop_id)))
with check ((select private.is_vendor_for_shop(shop_id)));
create policy menu_vendor_delete on public.menu_items
for delete to authenticated using ((select private.is_vendor_for_shop(shop_id)));
create policy menu_admin_all on public.menu_items
for all to authenticated
using ((select private.is_admin())) with check ((select private.is_admin()));

create policy orders_customer_read on public.orders
for select to authenticated using (customer_id=(select auth.uid()));
create policy orders_vendor_read on public.orders
for select to authenticated using ((select private.is_vendor_for_shop(shop_id)));
create policy orders_admin_read_write on public.orders
for all to authenticated
using ((select private.is_admin())) with check ((select private.is_admin()));

create policy order_items_related_read on public.order_items
for select to authenticated using (
  exists (
    select 1 from public.orders o
    where o.id=order_id
      and (o.customer_id=(select auth.uid())
           or (select private.is_vendor_for_shop(o.shop_id))
           or (select private.is_admin()))
  )
);

create policy payments_related_read on public.payments
for select to authenticated using (
  customer_id=(select auth.uid())
  or exists (
    select 1 from public.orders o
    where o.id=order_id
      and ((select private.is_vendor_for_shop(o.shop_id)) or (select private.is_admin()))
  )
);
create policy payments_admin_write on public.payments
for all to authenticated
using ((select private.is_admin())) with check ((select private.is_admin()));

create policy notifications_self_or_admin on public.notifications
for all to authenticated
using (user_id=(select auth.uid()) or (select private.is_admin()))
with check (user_id=(select auth.uid()) or (select private.is_admin()));

create policy cart_self_or_admin on public.cart_items
for all to authenticated
using (user_id=(select auth.uid()) or (select private.is_admin()))
with check (user_id=(select auth.uid()) or (select private.is_admin()));

create policy expenses_self_or_admin on public.expenses
for all to authenticated
using (user_id=(select auth.uid()) or (select private.is_admin()))
with check (user_id=(select auth.uid()) or (select private.is_admin()));

create policy budgets_self_or_admin on public.budgets
for all to authenticated
using (user_id=(select auth.uid()) or (select private.is_admin()))
with check (user_id=(select auth.uid()) or (select private.is_admin()));

create policy contact_authenticated_insert on public.contact_messages
for insert to authenticated with check (true);
create policy contact_admin_manage on public.contact_messages
for all to authenticated
using ((select private.is_admin())) with check ((select private.is_admin()));

create policy vendor_surveys_authenticated_read on public.vendor_daily_surveys
for select to authenticated using (true);
create policy vendor_surveys_vendor_or_admin on public.vendor_daily_surveys
for all to authenticated
using (vendor_user_id=(select auth.uid()) or (select private.is_admin()))
with check (vendor_user_id=(select auth.uid()) or (select private.is_admin()));

create policy vendor_daily_menu_authenticated_read on public.vendor_daily_menu_items
for select to authenticated using (true);
create policy vendor_daily_menu_vendor_or_admin on public.vendor_daily_menu_items
for all to authenticated
using ((select private.is_vendor_for_shop(shop_id)) or (select private.is_admin()))
with check ((select private.is_vendor_for_shop(shop_id)) or (select private.is_admin()));

create policy food_survey_read on public.food_survey_submissions
for select to authenticated using (
  student_user_id=(select auth.uid())
  or (select private.is_vendor_for_shop(shop_id))
  or (select private.is_admin())
);
create policy food_survey_student_insert on public.food_survey_submissions
for insert to authenticated
with check (
  student_user_id=(select auth.uid())
  and (select private.current_app_role())='customer'::public.app_role
);
create policy food_survey_admin_write on public.food_survey_submissions
for all to authenticated
using ((select private.is_admin())) with check ((select private.is_admin()));

-- Direct browser writes to order/payment state are intentionally blocked by RLS:
-- there are no authenticated INSERT/UPDATE/DELETE policies for these tables.
-- Checkout, stock reservation, payment verification and pickup OTP completion
-- will be implemented atomically in later phases.

create policy audit_admin_read on public.audit_logs
for select to authenticated using ((select private.is_admin()));

comment on table public.food_survey_submissions is 'One student submission per meal period per day.';
comment on table public.expenses is 'Created after completed pickup in the order workflow.';
comment on table public.orders is 'Order lifecycle: pending -> preparing -> ready -> completed.';
