import "./globals.css";
import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "research-digest",
  description: "Weekly sector-research digest from podcasts",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-zinc-50 text-zinc-900 antialiased">
        <header className="sticky top-0 z-10 border-b border-zinc-200 bg-white/80 backdrop-blur print:hidden">
          <div className="mx-auto flex h-14 max-w-5xl items-center justify-between px-4">
            <Link href="/" className="font-semibold tracking-tight">
              research<span className="text-indigo-600">·</span>digest
            </Link>
            <nav className="flex gap-5 text-sm text-zinc-600">
              <Link href="/" className="hover:text-zinc-900">
                Home
              </Link>
              <Link href="/report" className="hover:text-zinc-900">
                Weekly report
              </Link>
              <Link href="/insights" className="hover:text-zinc-900">
                Weekly insights
              </Link>
              <Link href="/episodes" className="hover:text-zinc-900">
                Episodes
              </Link>
              <Link href="/newsletter" className="hover:text-zinc-900">
                Newsletter
              </Link>
            </nav>
          </div>
        </header>
        <main className="mx-auto max-w-5xl px-4 py-8">{children}</main>
        <footer className="mx-auto max-w-5xl px-4 py-10 text-xs text-zinc-400 print:hidden">
          research-digest · Layer 1–2: transcripts + triage
        </footer>
      </body>
    </html>
  );
}
