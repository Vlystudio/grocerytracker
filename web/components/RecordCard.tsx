import Link from "next/link";
import type { ResearchRecord } from "@/lib/types";

// A compact summary card for the search/browse list.
export default function RecordCard({ record }: { record: ResearchRecord }) {
  return (
    <Link href={`/records/${record.id}`} className="block">
      <article className="card transition hover:shadow-md">
        <div className="mb-1 flex flex-wrap items-center gap-2 text-xs text-slate-500">
          <span className="badge">{record.source_website}</span>
          {record.study_type && <span className="badge">{record.study_type}</span>}
          {record.publication_date && <span>{record.publication_date}</span>}
        </div>

        <h2 className="text-base font-semibold text-slate-900">{record.title}</h2>

        {record.authors.length > 0 && (
          <p className="mt-1 text-sm text-slate-600">
            {record.authors.slice(0, 4).join(", ")}
            {record.authors.length > 4 ? " et al." : ""}
          </p>
        )}

        {(record.summary || record.abstract) && (
          <p className="mt-2 line-clamp-3 text-sm text-slate-700">
            {record.summary || record.abstract}
          </p>
        )}
      </article>
    </Link>
  );
}
