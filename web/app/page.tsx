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
  return `${Math.round(hrs / 24)} day${hrs >= 48 ? "s" : ""} ago`;
}

// Build a "/" URL from the current params plus overrides (undefined clears).
function qs(
  base: Record<string, string | undefined>,
  override: Record<string, string | undefined>
): string {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries({ ...base, ...override })) {
    if (v) p.set(k, v);
  }
  const s = p.toString();
  return s ? `/?${s}` : "/";
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

  const cats = (categories ?? []) as { category: string; deal_count: number }[];
  const storeList = (stores ?? []) as { store: string; deal_count: number }[];
  const totalDeals = cats.reduce((n, c) => n + c.deal_count, 0);

  return (
    <div className="space-y-6">
      {/* Heading + freshness */}
      <div>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Grocery deals</h1>
          <span className="inline-flex items-center gap-1.5 rounded-full border border-slate-800 bg-slate-900 px-2.5 py-1 text-xs text-slate-400">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
            Updated {timeAgo(lastRefresh?.last_refresh ?? null)}
          </span>
        </div>
        <p className="mt-1 text-sm text-slate-400">
          {totalDeals.toLocaleString()} deals on sale across {storeList.length} stores — refreshed automatically.
        </p>
      </div>

      {/* Category quick-filters */}
      <div className="-mx-1 flex flex-nowrap gap-2 overflow-x-auto pb-1 sm:flex-wrap">
        <a href={qs(sp, { category: undefined })} className={`chip ${!sp.category ? "chip-active" : ""}`}>
          All
        </a>
        {cats.map((c) => (
          <a
            key={c.category}
            href={qs(sp, { category: c.category })}
            className={`chip whitespace-nowrap ${sp.category === c.category ? "chip-active" : ""}`}
          >
            {c.category}
            <span className="ml-1.5 text-xs text-slate-500">{c.deal_count}</span>
          </a>
        ))}
      </div>

      {/* Toolbar */}
      <form method="get" className="card grid gap-3 sm:grid-cols-12">
        {/* keep the active category chip when submitting the toolbar */}
        <input type="hidden" name="category" value={sp.category ?? ""} />
        <div className="sm:col-span-5">
          <label className="label" htmlFor="q">Search</label>
          <input id="q" name="q" defaultValue={sp.q ?? ""} placeholder="milk, chicken, coffee…" className="input" />
        </div>
        <div className="sm:col-span-3">
          <label className="label" htmlFor="store">Store</label>
          <select id="store" name="store" defaultValue={sp.store ?? ""} className="input">
            <option value="">All stores</option>
            {storeList.map((s) => (
              <option key={s.store} value={s.store}>{s.store} ({s.deal_count})</option>
            ))}
          </select>
        </div>
        <div className="sm:col-span-2">
          <label className="label" htmlFor="sort">Sort</label>
          <select id="sort" name="sort" defaultValue={sort} className="input">
            <option value="price_asc">Price ↑</option>
            <option value="price_desc">Price ↓</option>
            <option value="newest">Newest</option>
          </select>
        </div>
        <div className="sm:col-span-2">
          <label className="label" htmlFor="show">Show</label>
          <select id="show" name="show" defaultValue={sp.show ?? "current"} className="input">
            <option value="current">Current</option>
            <option value="all">Incl. expired</option>
          </select>
        </div>
        <div className="flex items-end gap-2 sm:col-span-12">
          <button type="submit" className="btn">Apply filters</button>
          <a href="/" className="btn-secondary">Reset</a>
        </div>
      </form>

      {/* Results */}
      <div className="flex items-center justify-between">
        <p className="text-sm text-slate-400">
          {deals?.length ?? 0} result{deals?.length === 1 ? "" : "s"}
          {deals?.length === PAGE_SIZE ? " (first 120)" : ""}
          {sp.category ? ` in ${sp.category}` : ""}
        </p>
      </div>

      {deals && deals.length > 0 ? (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
          {(deals as GroceryDeal[]).map((d) => (
            <DealCard key={d.id} deal={d} />
          ))}
        </div>
      ) : (
        <div className="card grid place-items-center py-16 text-center text-slate-400">
          <p className="text-lg">No deals match your filters.</p>
          <a href="/" className="btn-secondary mt-4">Clear filters</a>
        </div>
      )}
    </div>
  );
}
