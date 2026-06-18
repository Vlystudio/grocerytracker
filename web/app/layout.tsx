import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Research Dashboard",
  description: "Searchable scientific research aggregated by a local agent.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <header className="border-b border-slate-200 bg-white">
          <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
            <Link href="/deals" className="text-lg font-semibold">
              🛒 Grocery Deals
            </Link>
            <nav className="flex gap-4 text-sm">
              <Link href="/deals" className="hover:underline">
                Deals
              </Link>
              <Link href="/" className="hover:underline">
                Research
              </Link>
              <Link href="/admin" className="hover:underline">
                Admin
              </Link>
            </nav>
          </div>
        </header>
        <main className="mx-auto max-w-6xl px-4 py-6">{children}</main>
        <footer className="mx-auto max-w-6xl px-4 py-8 text-xs text-slate-400">
          Data scraped locally · Website reads from Supabase only.
        </footer>
      </body>
    </html>
  );
}
