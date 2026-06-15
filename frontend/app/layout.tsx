import "./globals.css";
import type { Metadata } from "next";
import { fontVars } from "@/lib/fonts";
import SiteHeader from "@/components/SiteHeader";
import WaveBackground from "@/components/WaveBackground";

export const metadata: Metadata = {
  title: "research-digest",
  description: "Weekly sector-research digest from podcasts",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body
        className={`${fontVars} min-h-screen bg-[#0a0a0c] text-zinc-400 antialiased [color-scheme:dark] [font-family:var(--font-body)] print:bg-white print:text-zinc-900`}
      >
        <WaveBackground />
        <SiteHeader />
        <main className="relative z-10 mx-auto max-w-6xl px-6 pb-24 pt-10">{children}</main>
      </body>
    </html>
  );
}
