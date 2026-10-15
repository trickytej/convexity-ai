/** Shared layout for the plain-text legal pages (privacy, terms). */
export default function LegalPage({
  eyebrow,
  title,
  updated,
  sections,
}: {
  eyebrow: string;
  title: string;
  updated: string;
  sections: { heading: string; body: string[] }[];
}) {
  return (
    <div className="max-w-3xl">
      <p className="flex items-center gap-3 text-[11px] font-medium uppercase tracking-[0.24em]">
        <span className="inline-block h-px w-8 bg-[#00d4ff]" />
        <span className="text-[#00d4ff]">{eyebrow}</span>
      </p>
      <h1 className="mt-4 text-4xl font-light tracking-tight text-zinc-50 [font-family:var(--font-display)]">{title}</h1>
      <p className="mt-3 text-[12px] text-zinc-600">Last updated {updated}</p>
      <div className="mt-10 space-y-8">
        {sections.map((s) => (
          <section key={s.heading}>
            <h2 className="text-[15px] font-medium text-zinc-200">{s.heading}</h2>
            {s.body.map((p, i) => (
              <p key={i} className="mt-2 text-[14px] leading-relaxed text-zinc-400">
                {p}
              </p>
            ))}
          </section>
        ))}
      </div>
    </div>
  );
}
