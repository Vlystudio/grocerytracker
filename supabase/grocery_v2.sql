-- =============================================================================
-- Grocery schema v2 — adds categorization, units, and a freshness view.
-- Run AFTER grocery_schema.sql. Idempotent (IF NOT EXISTS / OR REPLACE).
-- =============================================================================

-- New columns on grocery_deals -----------------------------------------------
alter table public.grocery_deals
    add column if not exists category   text,            -- produce, dairy, ...
    add column if not exists unit        text,            -- lb | each | bundle | null
    add column if not exists is_grocery  boolean not null default true;

create index if not exists idx_deals_category   on public.grocery_deals (category);
create index if not exists idx_deals_isgrocery  on public.grocery_deals (is_grocery);

-- Freshness: when was data last refreshed successfully? ------------------------
create or replace view public.v_last_refresh as
    select max(finished_at) as last_refresh
    from public.scrape_runs
    where status in ('success', 'partial');

grant select on public.v_last_refresh to anon, authenticated;

-- Distinct categories that currently have grocery deals (for the filter UI) ----
create or replace view public.v_deal_categories as
    select category, count(*) as deal_count
    from public.grocery_deals
    where category is not null
      and is_grocery = true
      and (valid_to is null or valid_to >= now())
    group by category
    order by deal_count desc;

grant select on public.v_deal_categories to anon, authenticated;
