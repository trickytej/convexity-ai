import "./globals.css";
import type { Metadata } from "next";
import { auth } from "@/auth";
import { fontVars } from "@/lib/fonts";
import SiteHeader from "@/components/SiteHeader";
import WaveBackground from "@/components/WaveBackground";
import GuestPrompt from "@/components/GuestPrompt";

export const metadata: Metadata = {
  title: "ConvexityAI",
  description: "Track the questions that matter for the securities you follow",
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const session = await auth();
  const user = session?.user?.id
    ? {
        name: session.user.name,
        email: session.user.email,
        image: session.user.image,
        isAdmin: session.user.isAdmin,
      }
    : null;
  return (
    <html lang="en">
      <body
        className={`${fontVars} min-h-screen bg-[#0a0a0c] text-zinc-400 antialiased [color-scheme:dark] [font-family:var(--font-body)] print:bg-white print:text-zinc-900`}
      >
        <WaveBackground />
        <SiteHeader user={user} />
        {!user && <GuestPrompt />}
        <main className="relative z-10 mx-auto max-w-6xl px-6 pb-24 pt-10">{children}</main>
      </body>
    </html>
  );
}
