-- =============================================================================
-- Research Scraping Agent — Supabase / Postgres schema
-- -----------------------------------------------------------------------------
-- Run this in the Supabase SQL Editor (or `supabase db push`) on a fresh
-- project. It is idempotent-ish: it creates tables, indexes, triggers, and
-- Row Level Security (RLS) policies.
--
-- Security model
--   * The LOCAL Python agent connects with the SERVICE ROLE key. The service
--     role bypasses RLS, so it can read configs and write records freely.
--   * The Next.js website connects with the ANON key only.
--       - Anonymous visitors can READ public research data.
--       - Logged-in (authenticated) admins can manage sources/topics and
--         queue manual scans.
--   * The service-role key is NEVER shipped to the browser.
-- =============================================================================

-- Extensions ------------------------------------------------------------------
create extension if not exists "pgcrypto";   -- gen_random_uuid()
create extension if not exists "pg_trgm";     -- trigram fuzzy title matching

-- =============================================================================
-- 1. research_topics  — canonical list of research categories used for filters
-- =============================================================================
create table if not exists public.research_topics (
    id          uuid primary key default gen_random_uuid(),
    name        text not null unique,
    slug        text not null unique,
    description text,
    created_at  timestamptz not null default now()
);

-- =============================================================================
-- 2. research_sources — the per-site whitelist + crawl configuration
-- =============================================================================
create table if not exists public.research_sources (
    id              uuid primary key default gen_random_uuid(),
    name            text not null unique,          -- human label, e.g. "PubMed" (unique; used for upsert)
    base_url        text not null,                 -- where the crawl starts
    allowed_domains text[] not null default '{}',  -- domains the crawler may visit
    search_keywords text[] not null default '{}',  -- only keep pages matching these
    crawl_depth     int  not null default 1,       -- link-following depth
    rate_limit      numeric not null default 1.0,  -- seconds to wait between requests
    max_pages       int  not null default 50,      -- safety cap per run
    engine          text not null default 'scrapy' -- 'scrapy' (static) | 'playwright' (JS)
                    check (engine in ('scrapy', 'playwright')),
    enabled         boolean not null default true, -- agent only scans enabled sources
    notes           text,
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now()
);

create index if not exists idx_sources_enabled on public.research_sources (enabled);

-- =============================================================================
-- 3. research_records — one row per extracted scientific paper / study
-- =============================================================================
create table if not exists public.research_records (
    id               uuid primary key default gen_random_uuid(),
    source_id        uuid references public.research_sources (id) on delete set null,
    topic_id         uuid references public.research_topics (id) on delete set null,

    -- Core bibliographic fields
    title            text not null,
    title_normalized text,                 -- lowercased/stripped, for fuzzy dedup
    url              text not null,         -- canonical page URL (dedup key)
    doi              text,                  -- e.g. 10.1000/xyz (dedup key when present)
    authors          text[] not null default '{}',
    publication_date date,

    -- Content fields (a mix of parsed + AI-extracted)
    abstract         text,
    summary          text,                  -- AI-generated plain-language summary
    study_type       text,                  -- e.g. "RCT", "meta-analysis"
    sample_size      int,
    key_findings     text[] not null default '{}',
    pdf_links        text[] not null default '{}',

    -- Provenance (requirement: every record carries source + retrieval time)
    source_website   text not null,         -- denormalized host for easy filtering
    retrieved_at     timestamptz not null default now(),

    -- Bookkeeping
    raw_text         text,                  -- cleaned page text the AI worked from
    extraction_engine text,                 -- 'ollama' | 'openai' | 'anthropic' | 'parser'
    created_at       timestamptz not null default now(),

    constraint research_records_url_key unique (url)
);

-- DOI is unique only when present (papers without a DOI are still allowed).
create unique index if not exists uq_records_doi
    on public.research_records (doi) where doi is not null;

create index if not exists idx_records_source     on public.research_records (source_id);
create index if not exists idx_records_topic       on public.research_records (topic_id);
create index if not exists idx_records_pubdate     on public.research_records (publication_date desc);
create index if not exists idx_records_website     on public.research_records (source_website);
create index if not exists idx_records_retrieved   on public.research_records (retrieved_at desc);

-- Trigram index powers fast fuzzy title matching in SQL (used by dedup).
create index if not exists idx_records_title_trgm
    on public.research_records using gin (title_normalized gin_trgm_ops);

-- Full-text search vector for the dashboard search box.
create index if not exists idx_records_fts on public.research_records
    using gin (to_tsvector('english',
        coalesce(title,'') || ' ' || coalesce(abstract,'') || ' ' || coalesce(summary,'')));

-- =============================================================================
-- 4. extracted_tables — tables pulled out of a record's page
-- =============================================================================
create table if not exists public.extracted_tables (
    id          uuid primary key default gen_random_uuid(),
    record_id   uuid not null references public.research_records (id) on delete cascade,
    table_index int not null default 0,    -- position of the table on the page
    caption     text,
    -- Stored as JSON: { "headers": [...], "rows": [[...], ...] }
    data        jsonb not null default '{}'::jsonb,
    created_at  timestamptz not null default now()
);

create index if not exists idx_tables_record on public.extracted_tables (record_id);

-- =============================================================================
-- 5. scrape_runs — one row per crawl execution (also the manual-trigger queue)
-- =============================================================================
create table if not exists public.scrape_runs (
    id            uuid primary key default gen_random_uuid(),
    source_id     uuid references public.research_sources (id) on delete set null,
    trigger       text not null default 'manual'   -- 'manual' | 'scheduled'
                  check (trigger in ('manual', 'scheduled')),
    status        text not null default 'queued'   -- lifecycle below
                  check (status in ('queued', 'running', 'success', 'partial', 'failed')),
    started_at    timestamptz,
    finished_at   timestamptz,
    pages_crawled int not null default 0,
    records_found int not null default 0,
    records_new   int not null default 0,
    errors_count  int not null default 0,
    notes         text,
    created_at    timestamptz not null default now()
);
-- Flow: admin (or scheduler) inserts status='queued' → local agent picks it up,
-- sets 'running', then 'success'/'partial'/'failed' when finished.

create index if not exists idx_runs_status on public.scrape_runs (status);
create index if not exists idx_runs_created on public.scrape_runs (created_at desc);

-- =============================================================================
-- 6. scrape_errors — failed pages / exceptions for debugging
-- =============================================================================
create table if not exists public.scrape_errors (
    id          uuid primary key default gen_random_uuid(),
    run_id      uuid references public.scrape_runs (id) on delete cascade,
    source_id   uuid references public.research_sources (id) on delete set null,
    url         text,
    error_type  text,                       -- 'http', 'parse', 'ai', 'timeout', ...
    message     text,
    traceback   text,
    resolved    boolean not null default false,
    occurred_at timestamptz not null default now()
);

create index if not exists idx_errors_run      on public.scrape_errors (run_id);
create index if not exists idx_errors_resolved on public.scrape_errors (resolved);

-- =============================================================================
-- updated_at trigger for research_sources
-- =============================================================================
create or replace function public.set_updated_at()
returns trigger language plpgsql as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists trg_sources_updated_at on public.research_sources;
create trigger trg_sources_updated_at
    before update on public.research_sources
    for each row execute function public.set_updated_at();

-- =============================================================================
-- Row Level Security
-- =============================================================================
alter table public.research_topics  enable row level security;
alter table public.research_sources enable row level security;
alter table public.research_records enable row level security;
alter table public.extracted_tables enable row level security;
alter table public.scrape_runs      enable row level security;
alter table public.scrape_errors    enable row level security;

-- NOTE: the service role (local agent) bypasses every policy below, so we only
-- need to grant the narrow access the website requires.

-- ---- research_topics: public read, admin write -----------------------------
drop policy if exists topics_read   on public.research_topics;
drop policy if exists topics_write  on public.research_topics;
create policy topics_read  on public.research_topics
    for select using (true);
create policy topics_write on public.research_topics
    for all to authenticated using (true) with check (true);

-- ---- research_records: public read only (agent writes via service role) -----
drop policy if exists records_read on public.research_records;
create policy records_read on public.research_records
    for select using (true);

-- ---- extracted_tables: public read only ------------------------------------
drop policy if exists tables_read on public.extracted_tables;
create policy tables_read on public.extracted_tables
    for select using (true);

-- ---- research_sources: admin-only (configs may contain sensitive targets) ---
drop policy if exists sources_admin on public.research_sources;
create policy sources_admin on public.research_sources
    for all to authenticated using (true) with check (true);

-- ---- scrape_runs: admins read all + may queue a manual run ------------------
drop policy if exists runs_read   on public.scrape_runs;
drop policy if exists runs_insert on public.scrape_runs;
create policy runs_read on public.scrape_runs
    for select to authenticated using (true);
-- Admins may only INSERT manual, queued runs (agent updates them via service role).
create policy runs_insert on public.scrape_runs
    for insert to authenticated
    with check (trigger = 'manual' and status = 'queued');

-- ---- scrape_errors: admin read only ----------------------------------------
drop policy if exists errors_read on public.scrape_errors;
create policy errors_read on public.scrape_errors
    for select to authenticated using (true);

-- =============================================================================
-- Convenience view: distinct websites for the dashboard "filter by website".
-- Readable by anon because it only exposes data already in public records.
-- =============================================================================
create or replace view public.v_record_websites as
    select source_website, count(*) as record_count
    from public.research_records
    group by source_website
    order by record_count desc;

grant select on public.v_record_websites to anon, authenticated;
