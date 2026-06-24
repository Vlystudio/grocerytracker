import { createClient } from "@/lib/supabase/server";
import {
  signOut,
  toggleLocation,
  toggleStore,
  triggerGroceryScan,
} from "./actions";
import type {
  GroceryLocation,
  GroceryStore,
  ScrapeError,
  ScrapeRun,
} from "@/lib/types";

// Admin dashboard (grocery). Protected by middleware (redirects to /login when
// signed out). Reads use the authenticated session; RLS allows admin tables.
export const dynamic = "force-dynamic";

const statusColor: Record<string, string> = {
  queued: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  running: "bg-blue-500/15 text-blue-300 border-blue-500/30",
  success: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  partial: "bg-yellow-500/15 text-yellow-300 border-yellow-500/30",
  failed: "bg-rose-500/15 text-rose-300 border-rose-500/30",
};

export default async function AdminPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  const [
    { data: gStores },
    { data: gLocations },
    { count: dealCount },
    { data: runs },
    { data: errors },
  ] = await Promise.all([
    supabase.from("grocery_stores").select("*").order("display_name"),
    supabase.from("grocery_locations").select("*").order("name"),
    supabase.from("grocery_deals").select("id", { count: "exact", head: true }),
    supabase.from("scrape_runs").select("*").order("created_at", { ascending: false }).limit(20),
    supabase.from("scrape_errors").select("*").order("occurred_at", { ascending: false }).limit(25),
  ]);

  const storeList = (gStores as GroceryStore[]) ?? [];
  const locationList = (gLocations as GroceryLocation[]) ?? [];

  return (
    <div className="space-y-10">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Admin</h1>
        <div className="flex items-center gap-3 text-sm text-slate-500">
          <span>{user?.email}</span>
          <form action={signOut}>
            <button className="btn-secondary">Sign out</button>
          </form>
        </div>
      </div>

      {/* ---- Refresh deals ---- */}
      <section className="card">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-semibold">Refresh deals</h2>
          <span className="text-sm text-slate-500">{dealCount ?? 0} deals stored</span>
        </div>
        <p className="mb-3 text-sm text-slate-600">
          Pulls the latest weekly flyers (Flipp) for your enabled stores &amp; ZIPs.
          Requires the local agent running <code>python -m agent.main schedule</code>.
        </p>
        <form action={triggerGroceryScan}>
          <button className="btn bg-emerald-700 hover:bg-emerald-600">Refresh grocery deals now</button>
        </form>
      </section>

      {/* ---- Stores ---- */}
      <section>
        <h2 className="mb-3 text-lg font-semibold">
          Stores ({storeList.filter((s) => s.enabled).length}/{storeList.length} enabled)
        </h2>
        <p className="mb-3 text-sm text-slate-500">
          Toggle which stores are included in the next refresh.
        </p>
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {storeList.map((s) => (
            <form key={s.id} action={toggleStore} className="card flex items-center justify-between py-2">
              <input type="hidden" name="id" value={s.id} />
              <input type="hidden" name="enabled" value={(!s.enabled).toString()} />
              <span className="font-medium">{s.display_name}</span>
              <button className={`text-sm ${s.enabled ? "text-emerald-400" : "text-slate-400"}`}>
                {s.enabled ? "● enabled" : "○ disabled"}
              </button>
            </form>
          ))}
          {storeList.length === 0 && (
            <p className="text-sm text-slate-500">No stores configured.</p>
          )}
        </div>
      </section>

      {/* ---- Locations ---- */}
      <section>
        <h2 className="mb-3 text-lg font-semibold">
          Locations ({locationList.filter((l) => l.enabled).length}/{locationList.length} enabled)
        </h2>
        <p className="mb-3 text-sm text-slate-500">ZIP codes whose flyers are collected.</p>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
          {locationList.map((l) => (
            <form key={l.id} action={toggleLocation} className="card flex items-center justify-between py-2">
              <input type="hidden" name="id" value={l.id} />
              <input type="hidden" name="enabled" value={(!l.enabled).toString()} />
              <span className="text-sm">{l.name}<br /><span className="text-xs text-slate-400">{l.postal_code}</span></span>
              <button className={`text-sm ${l.enabled ? "text-emerald-400" : "text-slate-400"}`} title="toggle">
                {l.enabled ? "●" : "○"}
              </button>
            </form>
          ))}
        </div>
      </section>

      {/* ---- Run history ---- */}
      <section>
        <h2 className="mb-3 text-lg font-semibold">Recent refresh runs</h2>
        <div className="card overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-slate-500">
                <th className="py-1 pr-4">When</th>
                <th className="py-1 pr-4">Trigger</th>
                <th className="py-1 pr-4">Status</th>
                <th className="py-1 pr-4">Flyers</th>
                <th className="py-1 pr-4">Deals found</th>
                <th className="py-1 pr-4">New</th>
                <th className="py-1 pr-4">Errors</th>
              </tr>
            </thead>
            <tbody>
              {((runs as ScrapeRun[]) ?? []).map((run) => (
                <tr key={run.id} className="border-t border-slate-800">
                  <td className="py-1 pr-4">{new Date(run.created_at).toLocaleString()}</td>
                  <td className="py-1 pr-4">{run.trigger}</td>
                  <td className="py-1 pr-4">
                    <span className={`badge ${statusColor[run.status] ?? ""}`}>{run.status}</span>
                  </td>
                  <td className="py-1 pr-4">{run.pages_crawled}</td>
                  <td className="py-1 pr-4">{run.records_found}</td>
                  <td className="py-1 pr-4">{run.records_new}</td>
                  <td className="py-1 pr-4">{run.errors_count}</td>
                </tr>
              ))}
              {(!runs || runs.length === 0) && (
                <tr><td colSpan={7} className="py-2 text-slate-500">No runs yet.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* ---- Errors ---- */}
      <section>
        <h2 className="mb-3 text-lg font-semibold">Errors</h2>
        <div className="card overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-slate-500">
                <th className="py-1 pr-4">When</th>
                <th className="py-1 pr-4">Type</th>
                <th className="py-1 pr-4">Where</th>
                <th className="py-1 pr-4">Message</th>
              </tr>
            </thead>
            <tbody>
              {((errors as ScrapeError[]) ?? []).map((err) => (
                <tr key={err.id} className="border-t border-slate-800 align-top">
                  <td className="py-1 pr-4 whitespace-nowrap">{new Date(err.occurred_at).toLocaleString()}</td>
                  <td className="py-1 pr-4">{err.error_type}</td>
                  <td className="py-1 pr-4 max-w-xs truncate" title={err.url ?? ""}>{err.url}</td>
                  <td className="py-1 pr-4 max-w-md truncate" title={err.message ?? ""}>{err.message}</td>
                </tr>
              ))}
              {(!errors || errors.length === 0) && (
                <tr><td colSpan={4} className="py-2 text-slate-500">No errors logged. 🎉</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
