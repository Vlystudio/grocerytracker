-- =============================================================================
-- Grocery deals tracker — schema (run AFTER the base schema.sql).
-- Source of data: Flipp weekly-flyer API (backflipp.wishabi.com), keyed by ZIP.
--
-- Reuses the existing scrape_runs / scrape_errors tables for run + error logging
-- (their source_id is nullable, so grocery runs simply leave it null).
-- =============================================================================

create extension if not exists "pgcrypto";
create extension if not exists "pg_trgm";

-- 1. grocery_locations — the ZIP codes you want flyers for ---------------------
create table if not exists public.grocery_locations (
    id          uuid primary key default gen_random_uuid(),
    name        text not null,                 -- e.g. "Portland, ME"
    postal_code text not null unique,           -- e.g. "04101"
    enabled     boolean not null default true,
    created_at  timestamptz not null default now()
);

-- 2. grocery_stores — your store whitelist (which merchants to keep) -----------
-- match_key is matched case-insensitively as a substring of Flipp's merchant
-- name, so "market basket" catches both "Market Basket" and "Demoulas Market
-- Basket", and "aldi" catches "ALDI".
create table if not exists public.grocery_stores (
    id           uuid primary key default gen_random_uuid(),
    display_name text not null,                 -- e.g. "Market Basket"
    match_key    text not null unique,           -- e.g. "market basket"
    enabled      boolean not null default true,
    created_at   timestamptz not null default now()
);

-- 3. grocery_deals — one row per flyer item (a product on sale) ----------------
create table if not exists public.grocery_deals (
    id             uuid primary key default gen_random_uuid(),
    flipp_item_id  bigint unique,               -- dedup key (unique per flyer item)
    store          text not null,               -- display_name of the matched store
    merchant_raw   text,                         -- exact merchant string from Flipp
    product_name   text not null,
    brand          text,
    price          numeric,                      -- parsed sale price (may be null)
    discount       text,                         -- e.g. "Save $1.00" when present
    valid_from     timestamptz,
    valid_to       timestamptz,
    image_url      text,                         -- product cutout image
    flyer_id       bigint,
    postal_code    text,                         -- ZIP where this deal was found
    retrieved_at   timestamptz not null default now(),
    created_at     timestamptz not null default now()
);

create index if not exists idx_deals_store    on public.grocery_deals (store);
create index if not exists idx_deals_validto  on public.grocery_deals (valid_to desc);
create index if not exists idx_deals_price    on public.grocery_deals (price);
create index if not exists idx_deals_zip      on public.grocery_deals (postal_code);
create index if not exists idx_deals_name_trgm
    on public.grocery_deals using gin (product_name gin_trgm_ops);
create index if not exists idx_deals_fts on public.grocery_deals
    using gin (to_tsvector('english', coalesce(product_name,'') || ' ' || coalesce(brand,'')));

-- =============================================================================
-- Row Level Security
-- =============================================================================
alter table public.grocery_locations enable row level security;
alter table public.grocery_stores    enable row level security;
alter table public.grocery_deals     enable row level security;

-- Deals: public read (the website needs them); writes are service-role only.
drop policy if exists deals_read on public.grocery_deals;
create policy deals_read on public.grocery_deals for select using (true);

-- Locations & stores: public read (for dashboard filters); admin manages them.
drop policy if exists loc_read  on public.grocery_locations;
drop policy if exists loc_admin on public.grocery_locations;
create policy loc_read  on public.grocery_locations for select using (true);
create policy loc_admin on public.grocery_locations for all to authenticated using (true) with check (true);

drop policy if exists store_read  on public.grocery_stores;
drop policy if exists store_admin on public.grocery_stores;
create policy store_read  on public.grocery_stores for select using (true);
create policy store_admin on public.grocery_stores for all to authenticated using (true) with check (true);

-- =============================================================================
-- Convenience view: distinct stores that actually have deals (for filters).
-- =============================================================================
create or replace view public.v_deal_stores as
    select store, count(*) as deal_count
    from public.grocery_deals
    where valid_to is null or valid_to >= now()
    group by store
    order by deal_count desc;

grant select on public.v_deal_stores to anon, authenticated;
