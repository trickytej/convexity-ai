export const dynamic = "force-dynamic";

export default function NewslettersPage() {
  return (
    <div>
      {/* masthead */}
      <p className="flex items-center gap-3 text-[11px] font-medium uppercase tracking-[0.24em]">
        <span className="inline-block h-px w-8 bg-[#00d4ff]" />
        <span className="text-[#00d4ff]">Sources</span>
      </p>

      <h1 className="mt-4 text-4xl font-light tracking-tight text-zinc-50 [font-family:var(--font-display)] sm:text-5xl">
        Newsletters
      </h1>

      <p className="mt-3 text-[15px] text-zinc-400">
        Import newsletters to extract and curate insights alongside your podcasts.
      </p>

      {/* empty state */}
      <div className="mt-12 rounded-xl border border-dashed border-white/[0.12] bg-[#0b0c10]/50 px-8 py-16 text-center">
        <p className="text-2xl font-light text-zinc-400 [font-family:var(--font-display)]">
          Newsletter ingestion coming soon
        </p>
        <p className="mx-auto mt-3 max-w-md text-sm leading-relaxed text-zinc-600">
          You'll be able to import newsletters by RSS feed, forwarded email, or pasted PDF —
          and run the same nugget extraction pipeline you use for podcasts.
        </p>
      </div>
    </div>
  );
}
