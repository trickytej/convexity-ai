import type { Driver, ModelLine, SourceClass } from "@/lib/api";

const LINE_NAMES: Record<ModelLine, string> = {
  revenue: "Revenue",
  gross_margin: "Gross margin",
  op_margin: "Op margin",
  eps: "EPS",
  multiple: "Multiple",
};

export function driverLabel(d: Driver): string {
  return d.year ? `Y${d.year} ${LINE_NAMES[d.line]}` : LINE_NAMES[d.line];
}

/** Every taggable model driver: Y1–Y3 for the P&L lines, plus the multiple. */
export const DRIVER_OPTIONS: Driver[] = [
  ...(["revenue", "gross_margin", "op_margin", "eps"] as ModelLine[]).flatMap((line) =>
    [1, 2, 3].map((year) => ({ line, year })),
  ),
  { line: "multiple", year: null },
];

export const SOURCE_LABEL: Record<SourceClass, string> = {
  print: "Print",
  chatter: "Chatter",
  inside: "Inside view",
};
