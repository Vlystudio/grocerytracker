// Server-only: given a Maine ZIP, return which of OUR tracked stores serve it.
//
// We do a single lightweight availability lookup against Flipp's flyer list for
// that ZIP (NOT scraping deals — the deal content still comes from Supabase),
// map the merchants to our store display names via grocery_stores.match_key,
// and cache the result in-memory to avoid repeat calls.
// (Only imported by server components / route handlers.)
import { createClient } from "@supabase/supabase-js";

const TTL_MS = 1000 * 60 * 60 * 6; // 6 hours
const cache = new Map<string, { stores: string[]; at: number }>();

type StoreKey = { display_name: string; match_key: string };

async function trackedStores(): Promise<StoreKey[]> {
  const sb = createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  );
  const { data } = await sb.from("grocery_stores").select("display_name, match_key");
  return (data ?? []) as StoreKey[];
}

/** Display names of tracked stores available near `zip`.
 *  Returns [] on a transient Flipp failure (caller should then show all stores).
 *  Only successful lookups are cached, so a one-off failure can't get stuck. */
export async function storesNearZip(zip: string): Promise<string[]> {
  const cached = cache.get(zip);
  if (cached && Date.now() - cached.at < TTL_MS) return cached.stores;

  let merchants: string[] | null = null;
  try {
    const res = await fetch(
      `https://backflipp.wishabi.com/flipp/flyers?postal_code=${encodeURIComponent(zip)}&locale=en-us`,
      { headers: { "User-Agent": "Mozilla/5.0" }, cache: "no-store", signal: AbortSignal.timeout(7000) }
    );
    if (res.ok) {
      const data = await res.json();
      merchants = (data.flyers ?? []).map((f: { merchant?: string }) =>
        (f.merchant ?? "").toLowerCase()
      );
    }
  } catch {
    merchants = null; // timeout / network / parse failure
  }

  // Couldn't reach Flipp — return empty WITHOUT caching so the next call retries.
  if (merchants === null) return [];

  const found = new Set<string>();
  const keys = await trackedStores();
  for (const m of merchants) {
    for (const k of keys) {
      if (k.match_key && k.match_key !== "wholefoods-api" && m.includes(k.match_key)) {
        found.add(k.display_name);
      }
    }
  }
  // Whole Foods isn't on Flipp; it has one Maine store (Portland). Include it
  // for the greater-Portland / southern-Maine ZIP range.
  if (/^04(0|1)\d{2}$/.test(zip)) found.add("Whole Foods");

  const stores = [...found].sort();
  cache.set(zip, { stores, at: Date.now() });
  return stores;
}
