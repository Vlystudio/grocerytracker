import type { GroceryDeal } from "@/lib/types";

// A single grocery deal card (dark theme). The image sits on a white tile so
// product cutouts (designed for white backgrounds) stay crisp and visible.
export default function DealCard({ deal }: { deal: GroceryDeal }) {
  const validTo = deal.valid_to ? new Date(deal.valid_to) : null;
  const expired = validTo ? validTo < new Date() : false;

  const unitSuffix =
    deal.unit === "lb" ? "/lb" : deal.unit === "each" ? " ea" : "";

  return (
    <article className="group flex flex-col overflow-hidden rounded-xl border border-slate-800 bg-slate-900/70 transition hover:-translate-y-0.5 hover:border-slate-700 hover:bg-slate-900 hover:shadow-xl hover:shadow-black/30">
      <div className="relative aspect-[4/3] bg-white">
        {deal.image_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={deal.image_url}
            alt={deal.product_name}
            loading="lazy"
            className="h-full w-full object-contain p-3"
          />
        ) : (
          <div className="grid h-full place-items-center text-xs text-slate-400">
            no image
          </div>
        )}
        <span className="absolute left-2 top-2 rounded-full bg-slate-950/80 px-2 py-0.5 text-xs font-medium text-slate-100 ring-1 ring-white/10 backdrop-blur-sm">
          {deal.store}
        </span>
      </div>

      <div className="flex flex-1 flex-col gap-1 p-3">
        <div className="flex items-baseline justify-between gap-2">
          {deal.price != null ? (
            <span className="text-xl font-bold tracking-tight text-emerald-400">
              ${deal.price.toFixed(2)}
              {unitSuffix && (
                <span className="ml-0.5 text-xs font-normal text-emerald-400/70">
                  {unitSuffix}
                </span>
              )}
            </span>
          ) : (
            <span className="text-sm font-semibold text-amber-400">See flyer</span>
          )}
          {deal.category && (
            <span className="shrink-0 text-[10px] uppercase tracking-wide text-slate-500">
              {deal.category}
            </span>
          )}
        </div>

        <h3 className="line-clamp-2 text-sm font-medium leading-snug text-slate-100">
          {deal.product_name}
        </h3>
        {deal.brand && <p className="text-xs text-slate-400">{deal.brand}</p>}
        {deal.discount && (
          <p className="text-xs font-medium text-amber-400/90">{deal.discount}</p>
        )}

        <p
          className={`mt-auto pt-2 text-[11px] ${
            expired ? "text-rose-400" : "text-slate-500"
          }`}
        >
          {validTo
            ? `${expired ? "Ended" : "Valid until"} ${validTo.toLocaleDateString()}`
            : ""}
        </p>
      </div>
    </article>
  );
}
