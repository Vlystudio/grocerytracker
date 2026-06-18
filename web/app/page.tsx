import { createClient } from "@/lib/supabase/server";
import FilterBar from "@/components/FilterBar";
import RecordCard from "@/components/RecordCard";
import type { ResearchRecord, ResearchTopic } from "@/lib/types";

// The public browse/search page. Reads directly from Supabase via the anon key
// (RLS allows public SELECT on research_records). Filters come from the URL.
export const dynamic = "force-dynamic";

const PAGE_SIZE = 50;

export default async function HomePage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const sp = await searchParams;
  const supabase = await createClient();

  // ---- Build the filtered record query ----
  let query = supabase
    .from("research_records")
    .select("*")
    .order("publication_date", { ascending: false, nullsFirst: false })
    .order("retrieved_at", { ascending: false })
    .limit(PAGE_SIZE);

  if (sp.q) {
    // Match the term in title, abstract or summary.
    const term = sp.q.replace(/[%,]/g, " ");
    query = query.or(
      `title.ilike.%${term}%,abstract.ilike.%${term}%,summary.ilike.%${term}%`
    );
  }
  if (sp.website) query = query.eq("source_website", sp.website);
  if (sp.topic) query = query.eq("topic_id", sp.topic);
  if (sp.study_type) query = query.eq("study_type", sp.study_type);
  if (sp.from) query = query.gte("publication_date", sp.from);
  if (sp.to) query = query.lte("publication_date", sp.to);

  // Run the record query + the dropdown lookups in parallel.
  const [{ data: records }, { data: topics }, { data: websites }, { data: types }] =
    await Promise.all([
      query,
      supabase.from("research_topics").select("*").order("name"),
      supabase.from("v_record_websites").select("source_website"),
      supabase
        .from("research_records")
        .select("study_type")
        .not("study_type", "is", null),
    ]);

  // Distinct, sorted study types for the dropdown.
  const studyTypes = Array.from(
    new Set((types ?? []).map((t: { study_type: string }) => t.study_type))
  ).sort();

  return (
    <div>
      <h1 className="mb-4 text-2xl font-bold">Research records</h1>

      <FilterBar
        topics={(topics as ResearchTopic[]) ?? []}
        websites={(websites ?? []).map((w: { source_website: string }) => w.source_website)}
        studyTypes={studyTypes}
        current={sp as Record<string, string>}
      />

      <p className="mb-3 text-sm text-slate-500">
        {records?.length ?? 0} result{records?.length === 1 ? "" : "s"}
        {records?.length === PAGE_SIZE ? " (showing first 50)" : ""}
      </p>

      <div className="grid gap-4">
        {(records as ResearchRecord[] | null)?.map((r) => (
          <RecordCard key={r.id} record={r} />
        ))}
        {(!records || records.length === 0) && (
          <p className="text-slate-500">
            No records match your filters yet. Run the local agent to populate data.
          </p>
        )}
      </div>
    </div>
  );
}
