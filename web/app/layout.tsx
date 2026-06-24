import type { Metadata } from "next";
import Link from "next/link";
import NavBar from "@/components/NavBar";
import "./globals.css";

export const metadata: Metadata = {
  title: "Grocery Deals — Maine",
  description: "This week's grocery flyer deals across Maine stores, in one place.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <header className="sticky top-0 z-30 border-b border-slate-800 bg-slate-950/80 backdrop-blur">
          <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
            <Link href="/" className="flex items-center gap-2 font-semibold">
              <span className="grid h-8 w-8 place-items-center rounded-lg bg-emerald-500/15 text-lg ring-1 ring-emerald-500/30">
                🛒
              </span>
              <span className="text-base">
                Grocery&nbsp;Deals
                <span className="ml-1.5 hidden text-xs font-normal text-slate-500 sm:inline">
                  Maine
                </span>
              </span>
            </Link>
            <NavBar />
          </div>
        </header>

        <main className="mx-auto max-w-6xl px-4 py-6">{children}</main>

        <footer className="mx-auto max-w-6xl px-4 py-10 text-xs text-slate-600">
          Weekly flyer deals, refreshed automatically · prices from store circulars.
        </footer>
      </body>
    </html>
  );
}
