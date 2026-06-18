import { createClient } from "@/lib/supabase/server";
import SourceForm from "@/components/SourceForm";
import {
  addTopic,
  deleteSource,
  deleteTopic,
  signOut,
  toggleLocation,
  toggleStore,
  triggerGroceryScan,
  triggerScan,
} from "./actions";
import type {
  GroceryLocation,
  GroceryStore,
  ResearchSource,
  ResearchTopic,
  ScrapeError,
  ScrapeRun,
} from "@/lib/types";

// Admin dashboard. Protected by middleware (redirects to /login when signed out).
// All reads here use the authenticated session; RLS allows admin-only tables.
export const dynamic = "force-dynamic";

const statusColor: Record<string, string> = {
  queued: "bg-amber-100 text-amber-800",
  running: "bg-blue-100 text-blue-800",
  success: "bg-green-100 text-green-800",
  partial: "bg-yellow-100 text-yellow-800",
  failed: "bg-red-100 text-red-800",
};

export default async function AdminPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  const [
    { data: sources },
    { data: topics },
    { data: runs },
    { data: errors },
    { data: gStores },
    { data: gLocations },
    { count: dealCount },
  ] = await Promise.all([
    supabase.from("research_sources").select("*").order("name"),
    supabase.from("research_topics").select("*").order("name"),
    supabase.from("scrape_runs").select("*").order("created_at", { ascending: false }).limit(20),
    supabase.from("scrape_errors").select("*").order("occurred_at", { ascending: false }).limit(25),
    supabase.from("grocery_stores").select("*").order("display_name"),
    supabase.from("grocery_locations").select("*").order("name"),
    supabase.from("grocery_deals").select("id", { count: "exact", head: true }),
  ]);

  const sourceList = (sources as ResearchSource[]) ?? [];
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

      {/* ---- Grocery deals (primary) ---- */}
      <section className="card border-emerald-200">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-semibold">🛒 Grocery deals</h2>
          <span className="text-sm text-slate-500">{dealCount ?? 0} deals stored</span>
        </div>
        <p className="mb-3 text-sm text-slate-600">
          Refresh pulls the latest weekly flyers (Flipp) for your enabled stores &amp;
          ZIPs. Requires the local agent running <code>python -m agent.main schedule</code>.
        </p>
        <form action={triggerGroceryScan} className="mb-4">
          <button className="btn bg-emerald-700 hover:bg-emerald-600">Refresh grocery deals now</button>
        </form>

        <div className="grid gap-4 md:grid-cols-2">
          {/* Stores whitelist */}
          <div>
            <h3 className="mb-2 text-sm font-semibold text-slate-700">Stores ({storeList.filter(s => s.enabled).length}/{storeList.length} on)</h3>
            <div className="space-y-1">
              {storeList.map((s) => (
                <form key={s.id} action={toggleStore} className="flex items-center justify-between rounded border border-slate-200 px-2 py-1">
                  <input type="hidden" name="id" value={s.id} />
                  <input type="hidden" name="enabled" value={(!s.enabled).toString()} />
                  <span className="text-sm">{s.display_name}</span>
                  <button className={`text-xs ${s.enabled ? "text-emerald-700" : "text-slate-400"}`}>
                    {s.enabled ? "● enabled" : "○ disabled"}
                  </button>
                </form>
              ))}
            </div>
          </div>

          {/* Locations (ZIPs) */}
          <div>
            <h3 className="mb-2 text-sm font-semibold text-slate-700">Locations ({locationList.filter(l => l.enabled).length}/{locationList.length} on)</h3>
            <div className="grid grid-cols-2 gap-1">
              {locationList.map((l) => (
                <form key={l.id} action={toggleLocation} className="flex items-center justify-between rounded border border-slate-200 px-2 py-1">
                  <input type="hidden" name="id" value={l.id} />
                  <input type="hidden" name="enabled" value={(!l.enabled).toString()} />
                  <span className="text-xs">{l.name} ({l.postal_code})</span>
                  <button className={`text-xs ${l.enabled ? "text-emerald-700" : "text-slate-400"}`} title="toggle">
                    {l.enabled ? "●" : "○"}
                  </button>
                </form>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ---- Manual trigger (research) ---- */}
      <section className="card">
        <h2 className="mb-3 text-lg font-semibold">Run a research scan now</h2>
        <p className="mb-3 text-sm text-slate-600">
          Queues a job. Your local agent (running <code>python -m agent.main schedule</code>)
          picks it up within seconds. The website never scrapes directly.
        </p>
        <div className="flex flex-wrap items-end gap-3">
          <form action={triggerScan}>
            <button className="btn">Scan all enabled sources</button>
          </form>
          <form action={triggerScan} className="flex items-end gap-2">
            <div>
              <label className="label">…or one source</label>
              <select name="source_id" className="input">
                {sourceList.map((s) => (
                  <option key={s.id} value={s.id}>{s.name}</option>
                ))}
              </select>
            </div>
            <button className="btn-secondary">Scan selected</button>
          </form>
        </div>
      </section>

      {/* ---- Sources ---- */}
      <section>
        <h2 className="mb-3 text-lg font-semibold">Target websites ({sourceList.length})</h2>

        <details className="card mb-4">
          <summary className="cursor-pointer font-medium">+ Add a new source</summary>
          <div className="mt-4">
            <SourceForm />
          </div>
        </details>

        <div className="space-y-3">
          {sourceList.map((s) => (
            <details key={s.id} className="card">
              <summary className="flex cursor-pointer items-center justify-between">
                <span className="font-medium">
                  {s.name}{" "}
                  <span className="badge ml-2">{s.engine}</span>
                  {!s.enabled && <span className="badge ml-1 bg-red-100 text-red-700">disabled</span>}
                </span>
                <span className="text-xs text-slate-400">{s.base_url}</span>
              </summary>
              <div className="mt-4 space-y-4">
                <SourceForm source={s} />
                <form action={deleteSource}>
                  <input type="hidden" name="id" value={s.id} />
                  <button className="text-sm text-red-600 hover:underline">Delete this source</button>
                </form>
              </div>
            </details>
          ))}
          {sourceList.length === 0 && (
            <p className="text-sm text-slate-500">No sources yet — add one above.</p>
          )}
        </div>
      </section>

      {/* ---- Topics / keywords ---- */}
      <section>
        <h2 className="mb-3 text-lg font-semibold">Topics</h2>
        <form action={addTopic} className="card mb-3 flex flex-wrap items-end gap-2">
          <div className="flex-1">
            <label className="label">Topic name</label>
            <input name="name" required className="input" placeholder="e.g. Immunology" />
          </div>
          <div className="flex-1">
            <label className="label">Description (optional)</label>
            <input name="description" className="input" />
          </div>
          <button className="btn">Add topic</button>
        </form>
        <div className="flex flex-wrap gap-2">
          {((topics as ResearchTopic[]) ?? []).map((t) => (
            <form key={t.id} action={deleteTopic} className="badge flex items-center gap-2">
              <input type="hidden" name="id" value={t.id} />
              {t.name}
              <button className="text-red-500" title="Delete topic">×</button>
            </form>
          ))}
        </div>
      </section>

      {/* ---- Scraper logs ---- */}
      <section>
        <h2 className="mb-3 text-lg font-semibold">Recent scrape runs</h2>
        <div className="card overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-slate-500">
                <th className="py-1 pr-4">When</th>
                <th className="py-1 pr-4">Trigger</th>
                <th className="py-1 pr-4">Status</th>
                <th className="py-1 pr-4">Pages</th>
                <th className="py-1 pr-4">Found</th>
                <th className="py-1 pr-4">New</th>
                <th className="py-1 pr-4">Errors</th>
              </tr>
            </thead>
            <tbody>
              {((runs as ScrapeRun[]) ?? []).map((run) => (
                <tr key={run.id} className="border-t border-slate-100">
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

      {/* ---- Failed URLs ---- */}
      <section>
        <h2 className="mb-3 text-lg font-semibold">Failed URLs &amp; errors</h2>
        <div className="card overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-slate-500">
                <th className="py-1 pr-4">When</th>
                <th className="py-1 pr-4">Type</th>
                <th className="py-1 pr-4">URL</th>
                <th className="py-1 pr-4">Message</th>
              </tr>
            </thead>
            <tbody>
              {((errors as ScrapeError[]) ?? []).map((err) => (
                <tr key={err.id} className="border-t border-slate-100 align-top">
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
