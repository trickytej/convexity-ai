import type { ReactNode } from "react";

const TONES = {
  zinc: "bg-white/[0.06] text-zinc-300 ring-white/10",
  green: "bg-emerald-500/10 text-emerald-300 ring-emerald-500/25",
  blue: "bg-sky-500/10 text-sky-300 ring-sky-500/25",
  amber: "bg-amber-500/10 text-amber-300 ring-amber-500/25",
  indigo: "bg-indigo-500/10 text-indigo-300 ring-indigo-500/25",
} as const;

export function Badge({
  children,
  tone = "zinc",
}: {
  children: ReactNode;
  tone?: keyof typeof TONES;
}) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${TONES[tone]}`}
    >
      {children}
    </span>
  );
}

export function SourceBadge({ source }: { source?: string | null }) {
  if (!source) return null;
  return source === "official" ? (
    <Badge tone="green">official transcript</Badge>
  ) : (
    <Badge tone="blue">AI transcript</Badge>
  );
}

export function TierBadge({ tier }: { tier: string }) {
  return <Badge tone={tier === "A" ? "green" : "zinc"}>Tier {tier}</Badge>;
}
