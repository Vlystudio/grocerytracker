# 🔬 Local AI Research Scraping Agent

A self-hosted system that scrapes scientific research from a whitelist of
websites, structures it with AI, stores it in Supabase, and serves it through a
Next.js dashboard.

```
┌────────────────────┐     writes (service-role)     ┌──────────────────┐     reads (anon key)     ┌────────────────────┐
│  Local Python      │  ───────────────────────────▶ │  Supabase         │ ◀─────────────────────── │  Next.js dashboard │
│  scraper / agent   │                               │  Postgres + Auth  │   queues manual scans    │  (browse + admin)  │
│  (your PC)         │  ◀─── polls run queue ─────── │  + RLS            │  ───────────────────────▶ │                    │
└────────────────────┘                               └──────────────────┘                          └────────────────────┘
```

**Key principle:** the scraper is the *only* thing that scrapes. The website
**only reads** from Supabase (and queues scan requests the agent picks up). The
service-role key never leaves your PC.

---

## 🛒 Grocery deals mode

This project also runs as a **grocery weekly-deals tracker** (built on the same
infrastructure). Instead of scraping each store's bot-protected site, it pulls
structured weekly-flyer data from the **Flipp** API by ZIP code — reliable and
sustainable.

- **You whitelist** which stores (`grocery_stores`) and ZIP codes
  (`grocery_locations`) to track.
- The collector pulls every flyer item (product, price, brand, image, validity)
  for your stores across your ZIPs, **de-duplicated by Flipp item id**.
- Deals are stored in `grocery_deals` and shown at **`/deals`** on the dashboard
  (search, filter by store, sort by price). Manage stores/ZIPs and trigger a
  refresh from **`/admin`**.

Commands (run from `scraper/` with the venv active):
```bash
python -m agent.main grocery-status   # show your ZIPs, stores, deal count
python -m agent.main grocery-run      # pull the latest weekly deals now
```
The `schedule` command refreshes deals **daily** and runs admin-queued
"Refresh grocery deals now" requests.

**Setup:** apply the grocery schema + seed once:
```bash
# from scraper/, venv active, with SUPABASE_DB_PASSWORD set
python scripts/init_db.py --file grocery_schema.sql --file grocery_seed.sql
```

**Store coverage:**
- **Flipp** (weekly flyers): Hannaford, Shaw's, Walmart, Costco, Market Basket, Aldi.
- **Whole Foods**: not on Flipp, but collected from its own public sales API by
  `agent/collectors/wholefoods.py` (store set via `WFM_STORE_ID`, default 10291 =
  Portland, ME). Toggle it like any store in `/admin`.
- **Trader Joe's is not included** — it isn't on Flipp and its own site is
  Akamai-protected against automation.

Both collectors run together via `run_grocery()` (one `grocery-run` / daily job),
writing into the same `grocery_deals` table.

The original **research-paper** pipeline below still works (it's just disabled
by default now); the two share the scheduler, dedup, logging, and dashboard.

---

## Project structure

```
research-agent/
├── README.md
├── .gitignore
├── docs/
│   └── example_record.json          # what one processed record looks like
├── supabase/
│   ├── schema.sql                   # tables, indexes, triggers, RLS policies
│   └── seed.sql                     # example topics + sources
├── scraper/                         # ── the local Python agent ──
│   ├── requirements.txt
│   ├── .env.example
│   ├── config/
│   │   └── sites.example.yaml       # example per-site config
│   └── agent/
│       ├── main.py                  # CLI: run / schedule / seed-sources / ...
│       ├── config.py                # env settings
│       ├── logging_conf.py          # console + rotating file logs
│       ├── models.py                # pydantic models + validation
│       ├── db.py                    # ALL Supabase access (service role)
│       ├── dedup.py                 # URL / DOI / fuzzy-title dedup
│       ├── pipeline.py              # crawl → parse → AI → dedup → store
│       ├── scheduler.py             # daily run + manual-run queue poller
│       ├── ai/
│       │   ├── extractor.py         # Ollama → OpenAI → Anthropic fallback
│       │   └── prompts.py
│       └── scrapers/
│           ├── parse.py             # BeautifulSoup/lxml field + table extraction
│           ├── scrapy_spider.py     # standalone Scrapy spider (static pages)
│           ├── static_scraper.py    # runs Scrapy in a subprocess
│           └── dynamic_scraper.py   # Playwright crawler (JS pages)
└── web/                             # ── the Next.js dashboard ──
    ├── package.json
    ├── .env.example
    ├── middleware.ts                # session refresh + /admin guard
    ├── lib/
    │   ├── types.ts
    │   └── supabase/{client,server}.ts
    ├── components/{RecordCard,FilterBar,TableView,SourceForm}.tsx
    └── app/
        ├── page.tsx                 # search + filters (public)
        ├── records/[id]/page.tsx    # detail page (public)
        ├── login/page.tsx           # admin sign-in
        └── admin/
            ├── page.tsx             # sources, topics, trigger, logs, errors
            └── actions.ts           # server actions (authenticated writes)
```

---

## Setup

### 1. Create the Supabase project & schema

1. Create a project at [supabase.com](https://supabase.com).
2. Open **SQL Editor** and run `supabase/schema.sql`, then (optionally)
   `supabase/seed.sql`.
3. Grab your keys from **Project Settings → API**:
   - `Project URL`
   - `anon` `public` key → used by the **website**
   - `service_role` key → used by the **local agent only** (keep secret!)
4. Create an admin login under **Authentication → Users → Add user**
   (email + password). You'll use this to sign into `/admin`.

### 2. Set up the local agent (Python)

> Requires Python 3.10+.

```bash
cd scraper
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
playwright install chromium          # only needed for Playwright sources

cp .env.example .env                 # then edit .env (Windows: copy)
```

Fill in `scraper/.env`:
- `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` (required)
- AI provider settings (see below — all optional)

**(Optional) Local AI with Ollama** — free, private, recommended:
```bash
# install from https://ollama.com, then:
ollama pull llama3.1
```
The agent auto-detects Ollama. If it's down and you've set `OPENAI_API_KEY`
or `ANTHROPIC_API_KEY`, it falls back to those. With no AI at all, it still
runs and stores parser-extracted fields.

Seed example sources into Supabase and verify:
```bash
python -m agent.main seed-sources -f config/sites.example.yaml
python -m agent.main list-sources
python -m agent.main test-ai        # shows which AI provider is active
```

### 3. Set up the website (Next.js)

> Requires Node.js 18.18+.

```bash
cd web
npm install
cp .env.example .env.local           # then edit (Windows: copy)
```

Fill in `web/.env.local` with **only** the public values:
- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`

```bash
npm run dev                          # http://localhost:3000
```

---

## Running it

### Manual one-off crawl
```bash
cd scraper
python -m agent.main run                       # all enabled sources
python -m agent.main run --source <SOURCE_ID>  # just one
```

### Daily automatic + admin-triggered scans
Run the scheduler as a long-lived process. It crawls daily at `DAILY_RUN_TIME`
and polls Supabase for scans you queue from the admin dashboard:
```bash
cd scraper
python -m agent.main schedule
```
- **Windows:** to run on a schedule even when not logged in, wrap
  `python -m agent.main run` in a `.bat` and add it to **Task Scheduler**, or
  just leave `schedule` running.
- **macOS/Linux:** use `cron`/`systemd`, or leave `schedule` running.

### Triggering a scan from the website
On `/admin`, click **Scan all enabled sources** (or pick one). This inserts a
`queued` row in `scrape_runs`; the running scheduler claims it within
`QUEUE_POLL_SECONDS`. The website itself never scrapes.

---

## How a record is built (data flow)

1. **Crawl** — Scrapy (static) or Playwright (JS) fetches pages within the
   source's `allowed_domains`, honoring `crawl_depth`, `rate_limit`,
   `max_pages`, retries, and robots.txt (Scrapy).
2. **Parse** — BeautifulSoup/lxml pulls high-confidence fields from
   `citation_*`/OpenGraph meta tags (title, DOI, authors, date, abstract, PDF
   links) and extracts tables; the page body is cleaned to plain text.
3. **AI extract** — the cleaned text → strict JSON (summary, study type, sample
   size, key findings). Validated with pydantic before use.
4. **Dedup** — skip if URL exists, DOI exists, or a fuzzy title match exceeds
   `FUZZY_TITLE_THRESHOLD`.
5. **Store** — insert into `research_records` (+ `extracted_tables`), always with
   `source_website` and `retrieved_at`. Errors go to `scrape_errors`, run stats
   to `scrape_runs`.

See `docs/example_record.json` for a concrete result.

---

## Per-site config fields

Managed in the admin UI (or `sites.example.yaml`):

| Field | Meaning |
|---|---|
| `base_url` | where the crawl starts |
| `allowed_domains` | domains the crawler may visit |
| `search_keywords` | only keep pages mentioning these |
| `crawl_depth` | link-following depth (0 = base page only) |
| `rate_limit` | seconds between requests |
| `max_pages` | hard cap per run |
| `engine` | `scrapy` (static) or `playwright` (JS) |
| `enabled` | agent only crawls enabled sources |

---

## Security model

- **Service-role key** lives only in `scraper/.env` (local). It bypasses RLS so
  the agent can write records — it must **never** reach the browser.
- **Website** uses the **anon key** only (`NEXT_PUBLIC_*`).
- **Row Level Security** (in `schema.sql`):
  - Public can **read** records, tables, topics.
  - Source configs, scrape logs, and errors are **authenticated-only**.
  - Admins can manage sources/topics and **queue manual runs** (insert is
    constrained to `trigger='manual', status='queued'`).
  - Record/table/error writes are service-role only.
- `/admin` is gated by middleware + a Supabase Auth session.

---

## Extending it

- **Add a source type:** add a new engine module under `scrapers/` and branch on
  `cfg.engine` in `pipeline._crawl_with_retry`.
- **Improve extraction:** tweak `ai/prompts.py` and the `AIExtraction` schema.
- **Classify topics automatically:** have the AI return a topic and map it to a
  `research_topics.id` before insert.
- **Pagination/full-text search on the site:** the schema already includes a
  `pg_trgm` and an FTS index you can switch the query to.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `Missing required environment variables` | Fill `scraper/.env` from `.env.example`. |
| Playwright errors about browsers | Run `playwright install chromium`. |
| Scrapy returns 0 pages | Site may block bots / require JS → switch `engine` to `playwright`, or check robots.txt. |
| AI fields empty | `python -m agent.main test-ai`; start Ollama or set an API key. |
| Admin redirects to /login forever | Create a user in Supabase Auth and confirm `.env.local` keys. |
| Website shows no data | Run a crawl; confirm RLS `records_read` policy exists. |
