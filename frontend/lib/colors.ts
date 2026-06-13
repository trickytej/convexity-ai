// Distinct, readable speaker colors. Applied via inline styles so Tailwind's
// JIT doesn't purge them.
const PALETTE = [
  "#4f46e5", // indigo
  "#059669", // emerald
  "#e11d48", // rose
  "#d97706", // amber
  "#0891b2", // cyan
  "#7c3aed", // violet
  "#ea580c", // orange
  "#0d9488", // teal
  "#be185d", // pink
  "#2563eb", // blue
];

export function speakerColor(name: string | null | undefined, speakers: string[]): string {
  if (!name) return "#71717a"; // zinc-500 for unknown
  const idx = speakers.indexOf(name);
  const i = idx >= 0 ? idx : speakers.length;
  return PALETTE[i % PALETTE.length];
}
