import type { GroceryDeal } from "@/lib/types";

// A single grocery deal: product image, name, price, store, validity.
export default function DealCard({ deal }: { deal: GroceryDeal }) {
  const validTo = deal.valid_to ? new Date(deal.valid_to) : null;
  const expired = validTo ? validTo < new Date() : false;

  return (
    <article className="card flex flex-col">
      <div className="mb-2 flex h-32 items-center justify-center overflow-hidden rounded bg-slate-50">
        {deal.image_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={deal.image_url}
            alt={deal.product_name}
            className="max-h-32 object-contain"
            loading="lazy"
          />
        ) : (
          <span className="text-xs text-slate-400">no image</span>
        )}
      </div>

      <div className="flex items-center justify-between">
        <span className="badge">{deal.store}</span>
        {deal.price != null ? (
          <span className="text-lg font-bold text-emerald-700">
            ${deal.price.toFixed(2)}
          </span>
        ) : (
          <span className="text-xs text-slate-400">see flyer</span>
        )}
      </div>

      <h3 className="mt-1 line-clamp-2 text-sm font-medium text-slate-900">
        {deal.product_name}
      </h3>
      {deal.brand && <p className="text-xs text-slate-500">{deal.brand}</p>}
      {deal.discount && (
        <p className="mt-1 text-xs font-medium text-rose-600">{deal.discount}</p>
      )}

      <p className={`mt-auto pt-2 text-xs ${expired ? "text-rose-500" : "text-slate-400"}`}>
        {validTo
          ? `${expired ? "Ended" : "Valid until"} ${validTo.toLocaleDateString()}`
          : ""}
      </p>
    </article>
  );
}
