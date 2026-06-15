"use client";

import { useState } from "react";
import type { GeneratedReport } from "@/lib/api";

function toMarkdown(r: GeneratedReport): string {
  const lines: string[] = [`# Weekly Report — ${r.week_key}`, ""];
  if (r.exec_summary) {
    lines.push(r.exec_summary, "");
  }
  for (const s of r.sections) {
    lines.push(`## ${s.sector} — ${s.headline}`);
    for (const b of s.bullets) {
      const shows = Array.from(new Set(b.sources.map((x) => x.show_slug)));
      lines.push(`- ${b.text}${shows.length ? ` _(${shows.join(", ")})_` : ""}`);
    }
    if (s.watch_items.length) {
      lines.push(`- **Watch:** ${s.watch_items.join("; ")}`);
    }
    lines.push("");
  }
  return lines.join("\n");
}

export function ReportActions({ report }: { report: GeneratedReport }) {
  const [copied, setCopied] = useState(false);

  async function copyMarkdown() {
    try {
      await navigator.clipboard.writeText(toMarkdown(report));
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // clipboard blocked; ignore
    }
  }

  const btn =
    "rounded-lg px-3 py-2 text-sm font-medium ring-1 ring-inset transition bg-white/[0.06] text-zinc-200 ring-white/10 hover:bg-white/10 hover:text-white";

  return (
    <div className="flex items-center gap-2 print:hidden">
      <button type="button" onClick={() => window.print()} className={btn}>
        Download PDF
      </button>
      <button type="button" onClick={copyMarkdown} className={btn}>
        {copied ? "Copied!" : "Copy as Markdown"}
      </button>
    </div>
  );
}
