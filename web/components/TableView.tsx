import type { ExtractedTable } from "@/lib/types";

// Renders an extracted table (headers + rows) stored as JSON.
export default function TableView({ table }: { table: ExtractedTable }) {
  const headers = table.data?.headers ?? [];
  const rows = table.data?.rows ?? [];

  return (
    <figure className="card overflow-x-auto">
      {table.caption && (
        <figcaption className="mb-2 text-sm font-medium text-slate-700">
          {table.caption}
        </figcaption>
      )}
      <table className="w-full border-collapse text-sm">
        {headers.length > 0 && (
          <thead>
            <tr>
              {headers.map((h, i) => (
                <th
                  key={i}
                  className="border-b border-slate-300 bg-slate-50 px-2 py-1 text-left font-semibold"
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
        )}
        <tbody>
          {rows.map((row, ri) => (
            <tr key={ri} className="odd:bg-white even:bg-slate-50">
              {row.map((cell, ci) => (
                <td key={ci} className="border-b border-slate-100 px-2 py-1 align-top">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </figure>
  );
}
