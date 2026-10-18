import ResearchTabs from "@/components/ResearchTabs";

// Research hub: your own research first, then the shared corpus (podcasts, newsletters).
export default function ResearchLayout({ children }: { children: React.ReactNode }) {
  return (
    <div>
      <ResearchTabs />
      {children}
    </div>
  );
}
