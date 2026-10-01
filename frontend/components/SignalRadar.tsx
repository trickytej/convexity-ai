/** Radar sweep over the news flow: the arm rotates (6s period); blips flash
 * exactly when the sweep passes their bearing (delay = angle/360 * period).
 * Grey blips are noise and die fast; cyan blips are signal — they ping,
 * linger, and carry a label. Pure SVG + CSS, deterministic, reduced-motion safe. */

const PERIOD = 6; // seconds per revolution — keep in sync with globals.css

// (angle° clockwise from 12 o'clock, radius 0..1)
const NOISE: [number, number][] = [
  [28, 0.72], [55, 0.38], [97, 0.82], [131, 0.55], [168, 0.3],
  [205, 0.68], [241, 0.47], [262, 0.88], [311, 0.6], [338, 0.4],
];

const SIGNAL: { angle: number; r: number; label: string; dx?: number; dy?: number }[] = [
  { angle: 74, r: 0.62, label: "NVDA · capex", dx: 10, dy: 4 },
  { angle: 192, r: 0.5, label: "HBM supply", dx: -78, dy: 4 },
  { angle: 296, r: 0.74, label: "inference share", dx: 10, dy: 4 },
];

const C = 210; // center
const R = 190; // outer radius

function pos(angle: number, r: number): { x: number; y: number } {
  const rad = ((angle - 90) * Math.PI) / 180;
  return { x: C + R * r * Math.cos(rad), y: C + R * r * Math.sin(rad) };
}

function delay(angle: number): string {
  return `${((angle / 360) * PERIOD).toFixed(2)}s`;
}

export default function SignalRadar() {
  return (
    <div aria-hidden className="relative select-none">
      <svg viewBox="0 0 420 420" className="h-[320px] w-[320px] sm:h-[400px] sm:w-[400px]">
        <defs>
          <radialGradient id="radar-bg" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#00d4ff" stopOpacity="0.05" />
            <stop offset="75%" stopColor="#00d4ff" stopOpacity="0.015" />
            <stop offset="100%" stopColor="#00d4ff" stopOpacity="0" />
          </radialGradient>
        </defs>

        {/* dish */}
        <circle cx={C} cy={C} r={R} fill="url(#radar-bg)" />
        {[0.25, 0.5, 0.75, 1].map((f) => (
          <circle
            key={f}
            cx={C}
            cy={C}
            r={R * f}
            fill="none"
            stroke={f === 1 ? "#00d4ff" : "#ffffff"}
            strokeOpacity={f === 1 ? 0.22 : 0.06}
            strokeWidth="1"
          />
        ))}
        <line x1={C - R} y1={C} x2={C + R} y2={C} stroke="#ffffff" strokeOpacity="0.05" />
        <line x1={C} y1={C - R} x2={C} y2={C + R} stroke="#ffffff" strokeOpacity="0.05" />

        {/* sweep (rotating group; wedges trail the leading edge) */}
        <g className="radar-sweep" style={{ transformOrigin: `${C}px ${C}px` }}>
          <path
            d={`M${C},${C} L${C},${C - R} A${R},${R} 0 0 0 ${C - R * Math.sin((40 * Math.PI) / 180)},${C - R * Math.cos((40 * Math.PI) / 180)} Z`}
            fill="#00d4ff"
            opacity="0.06"
          />
          <path
            d={`M${C},${C} L${C},${C - R} A${R},${R} 0 0 0 ${C - R * Math.sin((16 * Math.PI) / 180)},${C - R * Math.cos((16 * Math.PI) / 180)} Z`}
            fill="#00d4ff"
            opacity="0.09"
          />
          <line x1={C} y1={C} x2={C} y2={C - R} stroke="#00d4ff" strokeOpacity="0.7" strokeWidth="1.5" />
        </g>

        {/* noise blips */}
        {NOISE.map(([angle, r], i) => {
          const p = pos(angle, r);
          return (
            <circle
              key={`n-${i}`}
              cx={p.x}
              cy={p.y}
              r="2.5"
              fill="#71717a"
              className="radar-blip"
              style={{ animationDelay: delay(angle) }}
            />
          );
        })}

        {/* signal blips + pings */}
        {SIGNAL.map((s, i) => {
          const p = pos(s.angle, s.r);
          return (
            <g key={`s-${i}`}>
              <circle
                cx={p.x}
                cy={p.y}
                r="10"
                fill="none"
                stroke="#00d4ff"
                strokeWidth="1"
                className="radar-ping"
                style={{ animationDelay: delay(s.angle), transformOrigin: `${p.x}px ${p.y}px` }}
              />
              <circle
                cx={p.x}
                cy={p.y}
                r="3.5"
                fill="#00d4ff"
                className="radar-signal"
                style={{ animationDelay: delay(s.angle) }}
              />
              <text
                x={p.x + (s.dx ?? 10)}
                y={p.y + (s.dy ?? 4)}
                fill="#00d4ff"
                fillOpacity="0.85"
                fontSize="10"
                className="radar-signal font-[family-name:var(--font-mono)]"
                style={{ animationDelay: delay(s.angle) }}
              >
                {s.label}
              </text>
            </g>
          );
        })}

        {/* center */}
        <circle cx={C} cy={C} r="3" fill="#00d4ff" />
      </svg>

      <p className="absolute -bottom-1 left-1/2 -translate-x-1/2 font-[family-name:var(--font-mono)] text-[9px] uppercase tracking-[0.2em] text-zinc-700">
        scanning the flow
      </p>
    </div>
  );
}
