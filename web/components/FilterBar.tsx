import type { ResearchTopic } from "@/lib/types";

// Server-rendered filter form. Submitting does a GET to "/" with query params,
// which the page reads — no client-side JavaScript required.
export default function FilterBar({
  topics,
  websites,
  studyTypes,
  current,
}: {
  topics: ResearchTopic[];
  websites: string[];
  studyTypes: string[];
  current: Record<string, string>;
}) {
  return (
    <form method="get" className="card mb-6 grid gap-3 md:grid-cols-12">
      <div className="md:col-span-4">
        <label className="label" htmlFor="q">Search</label>
        <input
          id="q"
          name="q"
          defaultValue={current.q ?? ""}
          placeholder="title, abstract or summary…"
          className="input"
        />
      </div>

      <div className="md:col-span-2">
        <label className="label" htmlFor="website">Website</label>
        <select id="website" name="website" defaultValue={current.website ?? ""} className="input">
          <option value="">All</option>
          {websites.map((w) => (
            <option key={w} value={w}>{w}</option>
          ))}
        </select>
      </div>

      <div className="md:col-span-2">
        <label className="label" htmlFor="topic">Topic</label>
        <select id="topic" name="topic" defaultValue={current.topic ?? ""} className="input">
          <option value="">All</option>
          {topics.map((t) => (
            <option key={t.id} value={t.id}>{t.name}</option>
          ))}
        </select>
      </div>

      <div className="md:col-span-2">
        <label className="label" htmlFor="study_type">Study type</label>
        <select id="study_type" name="study_type" defaultValue={current.study_type ?? ""} className="input">
          <option value="">All</option>
          {studyTypes.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </div>

      <div className="md:col-span-1">
        <label className="label" htmlFor="from">From</label>
        <input id="from" type="date" name="from" defaultValue={current.from ?? ""} className="input" />
      </div>

      <div className="md:col-span-1">
        <label className="label" htmlFor="to">To</label>
        <input id="to" type="date" name="to" defaultValue={current.to ?? ""} className="input" />
      </div>

      <div className="flex items-end gap-2 md:col-span-12">
        <button type="submit" className="btn">Apply filters</button>
        <a href="/" className="btn-secondary">Reset</a>
      </div>
    </form>
  );
}
