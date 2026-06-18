-- =============================================================================
-- Example seed data — run AFTER schema.sql.
-- These are safe, public, scraping-friendly sources to demonstrate the system.
-- Edit/remove from the admin dashboard once the app is running.
-- =============================================================================

-- Topics ----------------------------------------------------------------------
insert into public.research_topics (name, slug, description) values
    ('Oncology',        'oncology',        'Cancer research and clinical trials'),
    ('Cardiology',      'cardiology',      'Heart and cardiovascular studies'),
    ('Neuroscience',    'neuroscience',    'Brain and nervous system research'),
    ('Public Health',   'public-health',   'Epidemiology and population health'),
    ('Machine Learning','machine-learning','ML/AI methods applied to science')
on conflict (slug) do nothing;

-- Sources ---------------------------------------------------------------------
-- PLOS ONE: open-access, static HTML, rich citation_* metadata, and a
-- permissive robots.txt (only /search, /metrics, /user are disallowed). Its
-- homepage statically links to recent article pages, so a depth-1 Scrapy crawl
-- finds real papers. This is the proven, working example.
insert into public.research_sources
    (name, base_url, allowed_domains, search_keywords, crawl_depth, rate_limit, max_pages, engine, enabled, notes)
values
    ('PLOS ONE (recent articles)',
     'https://journals.plos.org/plosone/',
     array['journals.plos.org'],
     array[]::text[],                -- empty = keep every article page found
     1, 2.0, 25, 'scrapy', true,
     'Open-access. robots.txt permits article pages. Add keywords to narrow topics.'),

    -- Example of a JavaScript-rendered source (disabled until you set a real URL).
    ('Example JS journal',
     'https://example.com/articles',
     array['example.com'],
     array['trial','cohort','randomized'],
     1, 3.0, 20, 'playwright', false,
     'Placeholder for a JavaScript-rendered site. Set a real URL, then enable.')
on conflict do nothing;
