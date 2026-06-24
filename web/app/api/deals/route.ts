// Public read API for grocery deals — designed for YOUR OTHER WEBSITE to call.
//
//   GET /api/deals?q=milk                  -> this week's milk deals (cheapest first)
//   GET /api/deals?q=eggs&store=Hannaford  -> filter by store
//   GET /api/deals?q=coffee&limit=1        -> just the single cheapest match
//   GET /api/deals?store=Aldi&zip=04101    -> a store's deals in a ZIP
//
// Returns current-week, priced deals by default. CORS is open because the data
// is already public (Supabase RLS allows anon SELECT on grocery_deals).
import { createClient } from "@supabase/supabase-js";
import { NextRequest, NextResponse } from "next/server";
import { resolveLocation } from "@/lib/maine";
import { storesNearZip } from "@/lib/stores-near";

export const dynamic = "force-dynamic";

// Stateless anon client — read-only, public data. No service-role key here.
// Created per-request (lazy) so a missing env var can't crash the build.
function getClient() {
  return createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  );
}

const CORS: Record<string, string> = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

// Preflight support for browser callers on other domains.
export async function OPTIONS() {
  return new NextResponse(null, { status: 204, headers: CORS });
}

export async function GET(req: NextRequest) {
  const sp = req.nextUrl.searchParams;
  const q = sp.get("q")?.trim() || null;
  const store = sp.get("store")?.trim() || null;
  const category = sp.get("category")?.trim() || null;
  const zip = sp.get("zip")?.trim() || null;
  const near = sp.get("near")?.trim() || null; // ZIP or Maine town -> nearby stores
  const sort = sp.get("sort") ?? "price_asc";
  const includeExpired = sp.get("include_expired") === "true";
  const includeUnpriced = sp.get("include_unpriced") === "true";
  const includeNongrocery = sp.get("include_nongrocery") === "true";
  const limit = Math.min(Math.max(Number(sp.get("limit")) || 50, 1), 200);

  const supabase = getClient();
  let query = supabase
    .from("grocery_deals")
    .select(
      "store, product_name, brand, price, discount, category, unit, valid_from, valid_to, image_url, postal_code"
    )
    .limit(limit);

  // Default: grocery-only, valid this week, with a price.
  if (!includeNongrocery) query = query.eq("is_grocery", true);
  if (!includeExpired) query = query.gte("valid_to", new Date().toISOString());
  if (!includeUnpriced) query = query.not("price", "is", null);

  // "near" = a Maine ZIP or town -> limit to stores that serve that area.
  let nearStores: string[] | null = null;
  if (near) {
    const loc = resolveLocation(near);
    if (loc) {
      const s = await storesNearZip(loc.zip);
      if (s.length) {
        nearStores = s;
        query = query.in("store", s);
      }
    }
  }

  if (q) query = query.ilike("product_name", `%${q.replace(/[%,]/g, " ")}%`);
  if (store) query = query.ilike("store", `%${store}%`);
  if (category) query = query.eq("category", category);
  if (zip) query = query.eq("postal_code", zip);

  if (sort === "price_desc")
    query = query.order("price", { ascending: false, nullsFirst: false });
  else if (sort === "newest")
    query = query.order("retrieved_at", { ascending: false });
  else query = query.order("price", { ascending: true, nullsFirst: false });

  const { data, error } = await query;
  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500, headers: CORS });
  }

  const deals = (data ?? []).map((d) => ({
    store: d.store,
    product: d.product_name,
    brand: d.brand,
    price: d.price,
    unit: d.unit,
    category: d.category,
    discount: d.discount,
    valid_from: d.valid_from,
    valid_to: d.valid_to,
    image: d.image_url,
    zip: d.postal_code,
  }));

  return NextResponse.json(
    {
      query: { q, store, category, near, zip, sort },
      stores_near: nearStores,
      count: deals.length,
      deals,
    },
    { headers: CORS }
  );
}
