"""Data collectors for non-research sources (e.g. grocery deals).

Unlike the research scrapers (which crawl HTML), collectors pull from
structured public endpoints. The grocery collector uses the Flipp weekly-flyer
API, which returns clean JSON keyed by postal code.
"""
