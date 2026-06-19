-- =============================================================================
-- Grocery seed: your Maine locations + store whitelist.
-- Run AFTER grocery_schema.sql. Safe to re-run (ON CONFLICT DO NOTHING).
-- =============================================================================

-- Locations (ZIP codes) -------------------------------------------------------
insert into public.grocery_locations (name, postal_code) values
    ('Portland, ME',        '04101'),
    ('Falmouth, ME',        '04105'),
    ('South Portland, ME',  '04106'),
    ('Sanford, ME',         '04073'),
    ('Scarborough, ME',     '04074'),
    ('Saco, ME',            '04072'),
    ('Lewiston, ME',        '04240'),
    ('Augusta, ME',         '04330'),
    ('Auburn, ME',          '04210'),
    ('Gardiner, ME',        '04345')
on conflict (postal_code) do nothing;

-- Store whitelist (match_key is a lowercase substring of Flipp's merchant) -----
insert into public.grocery_stores (display_name, match_key) values
    ('Hannaford',      'hannaford'),
    ('Shaw''s',        'shaw'),
    ('Walmart',        'walmart'),
    ('Costco',         'costco'),
    ('Market Basket',  'market basket'),
    ('Aldi',           'aldi'),
    -- Whole Foods is NOT on Flipp; it's collected from its own API by the
    -- wholefoods.py collector. The unusual match_key never matches a Flipp
    -- merchant, so toggling this row only controls the Whole Foods collector.
    ('Whole Foods',    'wholefoods-api')
on conflict (match_key) do nothing;
-- NOTE: Trader Joe's is intentionally omitted — it isn't on Flipp and its own
-- site is Akamai-protected against scraping.
