import type { ResearchSource } from "@/lib/types";
import { saveSource } from "@/app/admin/actions";

// Add/edit form for a crawl source. When `source` is provided it edits;
// otherwise it creates a new one. Pure server-action form (no client JS).
export default function SourceForm({ source }: { source?: ResearchSource }) {
  return (
    <form action={saveSource} className="grid gap-3 md:grid-cols-2">
      {source && <input type="hidden" name="id" value={source.id} />}

      <div className="md:col-span-2">
        <label className="label">Name</label>
        <input name="name" required defaultValue={source?.name} className="input" />
      </div>

      <div className="md:col-span-2">
        <label className="label">Base URL (crawl start)</label>
        <input name="base_url" required defaultValue={source?.base_url} className="input" />
      </div>

      <div>
        <label className="label">Allowed domains (comma-separated)</label>
        <input
          name="allowed_domains"
          defaultValue={source?.allowed_domains.join(", ")}
          placeholder="example.org, www.example.org"
          className="input"
        />
      </div>

      <div>
        <label className="label">Search keywords (comma-separated)</label>
        <input
          name="search_keywords"
          defaultValue={source?.search_keywords.join(", ")}
          placeholder="cancer, trial, cohort"
          className="input"
        />
      </div>

      <div>
        <label className="label">Engine</label>
        <select name="engine" defaultValue={source?.engine ?? "scrapy"} className="input">
          <option value="scrapy">Scrapy (static HTML)</option>
          <option value="playwright">Playwright (JavaScript)</option>
        </select>
      </div>

      <div className="grid grid-cols-3 gap-2">
        <div>
          <label className="label">Depth</label>
          <input type="number" name="crawl_depth" min={0} defaultValue={source?.crawl_depth ?? 1} className="input" />
        </div>
        <div>
          <label className="label">Rate (s)</label>
          <input type="number" step="0.5" name="rate_limit" defaultValue={source?.rate_limit ?? 2} className="input" />
        </div>
        <div>
          <label className="label">Max pages</label>
          <input type="number" name="max_pages" defaultValue={source?.max_pages ?? 50} className="input" />
        </div>
      </div>

      <div className="md:col-span-2">
        <label className="label">Notes</label>
        <input name="notes" defaultValue={source?.notes ?? ""} className="input" />
      </div>

      <label className="flex items-center gap-2 text-sm md:col-span-2">
        <input type="checkbox" name="enabled" defaultChecked={source?.enabled ?? true} />
        Enabled (the agent only crawls enabled sources)
      </label>

      <div className="md:col-span-2">
        <button type="submit" className="btn">
          {source ? "Save changes" : "Add source"}
        </button>
      </div>
    </form>
  );
}
