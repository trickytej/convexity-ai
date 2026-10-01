/** Animated product metaphor: the news deluge streams left→right; most of it
 * is noise that passes through, but signal stops at the thesis rail and gets
 * flagged to the Brief. Pure CSS animation (keyframes in globals.css),
 * deterministic markup, honors prefers-reduced-motion. */

const LANES = [14, 32, 50, 68, 86];

// (lane%, base left%, delay s, duration s) — deterministic spread, no RNG.
const NOISE: [number, number, number, number][] = [
  [14, 8, 0.0, 9.5], [14, 55, 3.1, 8.0], [32, 22, 1.2, 10.5], [32, 70, 4.6, 9.0],
  [50, 12, 2.3, 8.5], [50, 48, 5.8, 10.0], [68, 30, 0.7, 9.8], [68, 64, 3.9, 8.2],
  [86, 18, 1.8, 10.2], [86, 52, 5.1, 8.8], [32, 40, 7.2, 9.3], [68, 8, 6.4, 10.8],
];

// Cyan "hits": stop at the rail, pulse, hand off.
const HITS: [number, number, number][] = [
  [32, 0.5, 11], [50, 4.5, 11], [68, 8.5, 11],
];

const CHIPS = [
  { delay: 2.2, tone: "supports", text: "NVDA · capex accelerating" },
  { delay: 6.2, tone: "contradicts", text: "inference commoditizing" },
  { delay: 10.2, tone: "supports", text: "supply still tight" },
];

export default function SignalFlow() {
  return (
    <div aria-hidden className="relative h-64 w-full select-none overflow-hidden">
      {/* lanes */}
      {LANES.map((top) => (
        <div
          key={top}
          className="absolute left-0 right-0 h-px bg-white/[0.05]"
          style={{ top: `${top}%` }}
        />
      ))}

      {/* noise dots */}
      {NOISE.map(([lane, left, delay, dur], i) => (
        <span
          key={`n-${i}`}
          className="sf-noise absolute h-1.5 w-1.5 rounded-full bg-zinc-600"
          style={{
            top: `calc(${lane}% - 3px)`,
            left: `${left}%`,
            animationDelay: `${delay}s`,
            animationDuration: `${dur}s`,
          }}
        />
      ))}

      {/* signal dots */}
      {HITS.map(([lane, delay, dur], i) => (
        <span
          key={`h-${i}`}
          className="sf-hit absolute h-2 w-2 rounded-full bg-[#00d4ff] shadow-[0_0_10px_#00d4ff88]"
          style={{
            top: `calc(${lane}% - 4px)`,
            left: `${18 + i * 9}%`,
            animationDelay: `${delay}s`,
            animationDuration: `${dur}s`,
          }}
        />
      ))}

      {/* thesis rail */}
      <div
        className="absolute w-px bg-gradient-to-b from-transparent via-[#00d4ff]/50 to-transparent"
        style={{ left: "64%", top: "4%", bottom: "4%" }}
      />
      <p
        className="absolute font-[family-name:var(--font-mono)] text-[9px] uppercase tracking-[0.2em] text-[#00d4ff]/60"
        style={{ left: "64%", top: "-2%", transform: "translateX(-50%)" }}
      >
        your theses
      </p>

      {/* flagged chips */}
      <div className="absolute flex flex-col gap-2" style={{ left: "69%", top: "22%" }}>
        {CHIPS.map((c) => (
          <span
            key={c.text}
            className="sf-chip inline-flex w-max items-center gap-1.5 rounded-full border border-[#00d4ff]/25 bg-[#0d1a2e]/90 px-2.5 py-1 text-[10px] font-medium text-zinc-300"
            style={{ animationDelay: `${c.delay}s` }}
          >
            <span
              className={`inline-block h-1.5 w-1.5 rounded-full ${
                c.tone === "supports" ? "bg-emerald-400" : "bg-rose-400"
              }`}
            />
            {c.text}
          </span>
        ))}
      </div>

      {/* captions */}
      <p className="absolute bottom-0 left-0 font-[family-name:var(--font-mono)] text-[9px] uppercase tracking-[0.2em] text-zinc-700">
        news flow
      </p>
      <p className="absolute bottom-0 right-0 font-[family-name:var(--font-mono)] text-[9px] uppercase tracking-[0.2em] text-zinc-700">
        flagged to the brief
      </p>
    </div>
  );
}
