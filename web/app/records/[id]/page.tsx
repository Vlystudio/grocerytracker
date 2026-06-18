import Link from "next/link";
import { notFound } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import TableView from "@/components/TableView";
import type { ExtractedTable, ResearchRecord } from "@/lib/types";

export const dynamic = "force-dynamic";

// Full detail view for a single research record.
export default async function RecordPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const supabase = await createClient();

  const [{ data: record }, { data: tables }] = await Promise.all([
    supabase.from("research_records").select("*").eq("id", id).maybeSingle(),
    supabase
      .from("extracted_tables")
      .select("*")
      .eq("record_id", id)
      .order("table_index"),
  ]);

  if (!record) notFound();
  const r = record as ResearchRecord;

  return (
    <article className="space-y-6">
      <Link href="/" className="text-sm text-slate-500 hover:underline">
        ← Back to results
      </Link>

      <header>
        <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-slate-500">
          <span className="badge">{r.source_website}</span>
          {r.study_type && <span className="badge">{r.study_type}</span>}
          {r.sample_size != null && <span className="badge">n = {r.sample_size}</span>}
          {r.publication_date && <span>Published {r.publication_date}</span>}
        </div>
        <h1 className="text-2xl font-bold">{r.title}</h1>
        {r.authors.length > 0 && (
          <p className="mt-2 text-slate-600">{r.authors.join(", ")}</p>
        )}
      </header>

      {/* AI summary */}
      {r.summary && (
        <section className="card">
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
            AI summary
          </h2>
          <p className="text-slate-800">{r.summary}</p>
        </section>
      )}

      {/* Key findings */}
      {r.key_findings?.length > 0 && (
        <section className="card">
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
            Key findings
          </h2>
          <ul className="list-inside list-disc space-y-1 text-slate-800">
            {r.key_findings.map((f, i) => (
              <li key={i}>{f}</li>
            ))}
          </ul>
        </section>
      )}

      {/* Abstract */}
      {r.abstract && (
        <section className="card">
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
            Abstract
          </h2>
          <p className="whitespace-pre-line text-slate-800">{r.abstract}</p>
        </section>
      )}

      {/* Extracted tables */}
      {(tables as ExtractedTable[] | null)?.length ? (
        <section className="space-y-4">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
            Extracted tables
          </h2>
          {(tables as ExtractedTable[]).map((t) => (
            <TableView key={t.id} table={t} />
          ))}
        </section>
      ) : null}

      {/* Source links + provenance */}
      <section className="card text-sm">
        <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
          Source &amp; links
        </h2>
        <ul className="space-y-1">
          <li>
            <a href={r.url} target="_blank" rel="noreferrer" className="text-blue-600 hover:underline">
              Original page ↗
            </a>
          </li>
          {r.doi && (
            <li>
              DOI:{" "}
              <a
                href={`https://doi.org/${r.doi}`}
                target="_blank"
                rel="noreferrer"
                className="text-blue-600 hover:underline"
              >
                {r.doi} ↗
              </a>
            </li>
          )}
          {r.pdf_links?.map((p, i) => (
            <li key={i}>
              <a href={p} target="_blank" rel="noreferrer" className="text-blue-600 hover:underline">
                PDF {i + 1} ↗
              </a>
            </li>
          ))}
        </ul>
        <p className="mt-3 text-xs text-slate-400">
          Retrieved {new Date(r.retrieved_at).toLocaleString()} · extraction:{" "}
          {r.extraction_engine ?? "parser"}
        </p>
      </section>
    </article>
  );
}
