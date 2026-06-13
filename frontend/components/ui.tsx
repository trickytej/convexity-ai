import type { ReactNode } from "react";

const TONES = {
  zinc: "bg-zinc-100 text-zinc-700 ring-zinc-200",
  green: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  blue: "bg-blue-50 text-blue-700 ring-blue-200",
  amber: "bg-amber-50 text-amber-700 ring-amber-200",
  indigo: "bg-indigo-50 text-indigo-700 ring-indigo-200",
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
