"""Local research scraping agent.

A self-contained crawler that reads a whitelist of sources from Supabase,
scrapes scientific pages (Scrapy for static, Playwright for JS), extracts
structured records (optionally with a local Ollama model or an API fallback),
de-duplicates them, and writes clean rows back to Supabase.
"""

__version__ = "1.0.0"

# Use the operating system's certificate store (Windows/macOS/Linux) for TLS
# verification instead of Python's bundled CA list. This makes the agent work on
# networks that inspect HTTPS (antivirus, VPNs, corporate proxies) whose root
# certificate is trusted by the OS but not by certifi. Safe + recommended.
try:
    import truststore as _truststore

    _truststore.inject_into_ssl()
except Exception:  # truststore optional — fall back to default verification
    pass
