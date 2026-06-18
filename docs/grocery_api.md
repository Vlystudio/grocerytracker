# Grocery price API — for your other website

Your other website can look up this week's grocery prices (collected by the
local agent) two ways. **Both read public data only** (the deals table is
public-read via RLS); no secret keys are exposed.

---

## Option A — the `/api/deals` endpoint (recommended, clean contract)

Lives in the dashboard app. Returns current-week, priced deals as JSON, with
open CORS (callable from a browser app on any domain).

```
GET /api/deals
```

| Param | Default | Meaning |
|---|---|---|
| `q` | — | product search (e.g. `milk`, `chicken breast`) |
| `store` | — | filter by store (e.g. `Hannaford`, `Aldi`) |
| `zip` | — | filter by ZIP (e.g. `04101`) |
| `sort` | `price_asc` | `price_asc` \| `price_desc` \| `newest` |
| `limit` | `50` | 1–200 |
| `include_expired` | `false` | set `true` to include past weeks |
| `include_unpriced` | `false` | set `true` to include items with no parsed price |

**Response**
```json
{
  "query": { "q": "milk", "store": null, "zip": null, "sort": "price_asc" },
  "count": 3,
  "deals": [
    { "store": "Shaw's", "product": "Planet Oat Oatmilk", "brand": "Planet Oat",
      "price": 2.49, "discount": null,
      "valid_from": "2026-06-14T04:00:00+00:00", "valid_to": "2026-06-21T03:59:59+00:00",
      "image": "http://f.wishabi.net/...", "zip": "04101" }
  ]
}
```

### Examples

"What's the cheapest milk this week?"
```
GET /api/deals?q=milk&limit=1
```

JavaScript (browser or Node):
```js
const base = "https://YOUR-DASHBOARD-HOST";      // e.g. http://localhost:3001 in dev
const res = await fetch(`${base}/api/deals?q=eggs&limit=5`);
const { deals } = await res.json();
deals.forEach(d => console.log(d.store, d.product, "$" + d.price));
```

Python:
```python
import requests
r = requests.get("https://YOUR-DASHBOARD-HOST/api/deals", params={"q": "coffee", "store": "Hannaford"})
for d in r.json()["deals"]:
    print(d["store"], d["product"], d["price"])
```

PHP (e.g. WordPress):
```php
$json = file_get_contents("https://YOUR-DASHBOARD-HOST/api/deals?q=" . urlencode("chicken"));
$deals = json_decode($json, true)["deals"];
```

> **Hosting:** in development the base URL is `http://localhost:3001`. For your
> *other* website (on a different machine/host) to reach it, deploy this
> dashboard app (e.g. Vercel free tier) and use that URL. If both run on the
> same PC, `http://localhost:3001` works as-is.

---

## Option B — query Supabase directly (zero deploy, works from anywhere now)

Supabase is already a public cloud endpoint, so your other site can hit its
auto-generated REST API with the **anon** (public) key. Good if you don't want
to deploy the dashboard.

```
GET https://iwtngnmsdotumalpsfmv.supabase.co/rest/v1/grocery_deals
    ?select=store,product_name,brand,price,valid_to,postal_code
    &product_name=ilike.*milk*
    &price=not.is.null
    &valid_to=gte.2026-06-18T00:00:00Z
    &order=price.asc
    &limit=5

Headers:
    apikey: <YOUR_SUPABASE_ANON_KEY>
```

Or with `@supabase/supabase-js` on the other site:
```js
import { createClient } from "@supabase/supabase-js";
const sb = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
const { data } = await sb
  .from("grocery_deals")
  .select("store, product_name, price, valid_to")
  .ilike("product_name", "%milk%")
  .not("price", "is", null)
  .gte("valid_to", new Date().toISOString())
  .order("price", { ascending: true })
  .limit(5);
```

Use the **anon** key only (never the service-role key) on a website.

---

## Keeping prices fresh
Deals reflect the latest collector run. Keep them current by running the agent's
scheduler (`python -m agent.main schedule`) for a daily refresh, or trigger
**"Refresh grocery deals now"** in `/admin`.
