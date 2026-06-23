import { createClient } from "@/lib/supabase/server";
import DealCard from "@/components/DealCard";
import type { GroceryDeal } from "@/lib/types";

// Home page = the grocery-deals browser. Reads grocery_deals via the anon key
// (RLS allows public SELECT). Filters/sort come from the URL query string.
export const dynamic = "force-dynamic";

const PAGE_SIZE = 120;

function timeAgo(iso: string | null): string {
  if (!iso) return "never";
  const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs} hr ago`;
  return `${Math.round(hrs / 24)} day(s) ago`;
}

export default async function HomePage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const sp = await searchParams;
  const supabase = await createClient();

  const sort = sp.sort ?? "price_asc";
  const showAll = sp.show === "all";

  // Grocery-only by default (hides electronics/furniture/etc.).
  let query = supabase
    .from("grocery_deals")
    .select("*")
    .eq("is_grocery", true)
    .limit(PAGE_SIZE);

  if (!showAll) query = query.gte("valid_to", new Date().toISOString());
  if (sp.store) query = query.eq("store", sp.store);
  if (sp.category) query = query.eq("category", sp.category);
  if (sp.q) query = query.ilike("product_name", `%${sp.q.replace(/[%,]/g, " ")}%`);

  if (sort === "price_asc")
    query = query.order("price", { ascending: true, nullsFirst: false });
  else if (sort === "price_desc")
    query = query.order("price", { ascending: false, nullsFirst: false });
  else query = query.order("retrieved_at", { ascending: false });

  const [
    { data: deals },
    { data: stores },
    { data: categories },
    { data: lastRefresh },
  ] = await Promise.all([
    query,
    supabase.from("v_deal_stores").select("store, deal_count"),
    supabase.from("v_deal_categories").select("category, deal_count"),
    supabase.from("v_last_refresh").select("last_refresh").maybeSingle(),
  ]);

  return (
    <div>
      <div className="mb-1 flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="text-2xl font-bold">Grocery deals</h1>
        <span className="text-xs text-slate-400">
          Updated {timeAgo(lastRefresh?.last_refresh ?? null)}
        </span>
      </div>
      <p className="mb-4 text-sm text-slate-500">
        This week&apos;s flyer deals across your Maine stores, refreshed automatically.
      </p>

      {/* Filters (server-rendered GET form) */}
      <form method="get" className="card mb-6 grid gap-3 md:grid-cols-12">
        <div className="md:col-span-4">
          <label className="label" htmlFor="q">Search product</label>
          <input id="q" name="q" defaultValue={sp.q ?? ""} placeholder="milk, chicken, coffee…" className="input" />
        </div>
        <div className="md:col-span-2">
          <label className="label" htmlFor="category">Category</label>
          <select id="category" name="category" defaultValue={sp.category ?? ""} className="input">
            <option value="">All</option>
            {(categories ?? []).map((c: { category: string; deal_count: number }) => (
              <option key={c.category} value={c.category}>{c.category} ({c.deal_count})</option>
            ))}
          </select>
        </div>
        <div className="md:col-span-2">
          <label className="label" htmlFor="store">Store</label>
          <select id="store" name="store" defaultValue={sp.store ?? ""} className="input">
            <option value="">All stores</option>
            {(stores ?? []).map((s: { store: string; deal_count: number }) => (
              <option key={s.store} value={s.store}>{s.store} ({s.deal_count})</option>
            ))}
          </select>
        </div>
        <div className="md:col-span-2">
          <label className="label" htmlFor="sort">Sort</label>
          <select id="sort" name="sort" defaultValue={sort} className="input">
            <option value="price_asc">Price: low to high</option>
            <option value="price_desc">Price: high to low</option>
            <option value="newest">Newest</option>
          </select>
        </div>
        <div className="md:col-span-2">
          <label className="label" htmlFor="show">Show</label>
          <select id="show" name="show" defaultValue={sp.show ?? "current"} className="input">
            <option value="current">Current only</option>
            <option value="all">Include expired</option>
          </select>
        </div>
        <div className="flex items-end gap-2 md:col-span-12">
          <button type="submit" className="btn">Apply</button>
          <a href="/" className="btn-secondary">Reset</a>
        </div>
      </form>

      <p className="mb-3 text-sm text-slate-500">
        {deals?.length ?? 0} deal{deals?.length === 1 ? "" : "s"}
        {deals?.length === PAGE_SIZE ? " (showing first 120)" : ""}
      </p>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
        {(deals as GroceryDeal[] | null)?.map((d) => (
          <DealCard key={d.id} deal={d} />
        ))}
      </div>

      {(!deals || deals.length === 0) && (
        <p className="text-slate-500">No deals match your filters.</p>
      )}
    </div>
  );
}
