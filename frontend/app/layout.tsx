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
      <body className="min-h-screen bg-white text-zinc-900 antialiased">
        <header className="sticky top-0 z-10 print:hidden" style={{ backgroundColor: "rgb(45, 45, 90)" }}>
          <div className="mx-auto flex h-14 max-w-5xl items-center justify-between px-4">
            <Link href="/" className="text-2xl font-semibold tracking-tight text-white">
              TMTB<span className="text-white/60">:</span> Podcast Insights
            </Link>
            <nav className="flex gap-6 text-sm" style={{ color: "rgba(255,255,255,0.7)" }}>
              <Link href="/" className="transition-colors hover:text-white">
                Podcasts
              </Link>
              <Link href="/episodes" className="transition-colors hover:text-white">
                Insights
              </Link>
              <Link href="/newsletter" className="transition-colors hover:text-white">
                Newsletter
              </Link>
            </nav>
          </div>
        </header>
        <main className="mx-auto max-w-5xl px-4 py-8">{children}</main>
      </body>
    </html>
  );
}
