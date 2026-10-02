// The 3/8 indicator ring and the Fib Pivot ladder mark, ported from
// docs/design/handoff/IndicatorRing.tsx. Geometry matches the design files; never reorder.

export type SegState = "fired" | "provisional" | "off";
export type Direction = "long" | "short";

/** Fixed order, clockwise from 12 o'clock, with the rule key each segment shows. */
export const INDICATORS = [
  { key: "three_eight.candlestick", name: "Candlestick", short: "Candle" },
  { key: "three_eight.hl_failure", name: "New high/low failure", short: "Failure" },
  { key: "three_eight.pivot_touch", name: "Pivots", short: "Pivots" },
  { key: "three_eight.flag_pennant_triangle", name: "Flags, pennants, triangles", short: "Patterns" },
  { key: "three_eight.trendline_channel", name: "Trendlines and channels", short: "Lines" },
  { key: "three_eight.pdh", name: "Previous day high", short: "PDH" },
  { key: "three_eight.pdl", name: "Previous day low", short: "PDL" },
  { key: "three_eight.fibonacci", name: "Fibonacci", short: "Fib" },
] as const;

export interface IndicatorFact {
  key: string;
  fired: boolean;
  provisional: boolean;
}

/** Segment states in ring order. A fired provisional indicator shows the dashed state;
 *  an indicator that did not fire is an outline, provisional or not. */
export function ringStates(indicators: IndicatorFact[]): SegState[] {
  const byKey = new Map(indicators.map((i) => [i.key, i]));
  return INDICATORS.map(({ key }) => {
    const ind = byKey.get(key);
    if (!ind?.fired) return "off";
    return ind.provisional ? "provisional" : "fired";
  });
}

interface RingProps {
  states: SegState[];
  direction: Direction;
  size: number;
  variant?: "segments" | "hairline";
  showCount?: boolean;
  iconOutline?: string;
  label?: string;
}

const pt = (a: number, rad: number) =>
  `${(50 + rad * Math.cos(a)).toFixed(2)} ${(50 + rad * Math.sin(a)).toFixed(2)}`;

export function IndicatorRing({
  states,
  direction,
  size,
  variant = "segments",
  showCount = true,
  iconOutline,
  label,
}: RingProps) {
  const thin = variant === "hairline";
  const R = 47;
  const r = thin ? 39 : 30;
  const gap = thin ? 3 : 4.5;
  const large = size >= 80;
  const col = direction === "long" ? "var(--long)" : "var(--short)";
  const n = states.filter((s) => s !== "off").length;
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 100 100"
      role="img"
      aria-label={label ?? `${n} of 8 indicators fired`}
      className="block flex-none"
    >
      {states.map((s, i) => {
        const a0 = ((-90 + i * 45 + gap / 2) * Math.PI) / 180;
        const a1 = ((-90 + (i + 1) * 45 - gap / 2) * Math.PI) / 180;
        const d = `M${pt(a0, R)}A${R} ${R} 0 0 1 ${pt(a1, R)}L${pt(a1, r)}A${r} ${r} 0 0 0 ${pt(a0, r)}Z`;
        const fired = s === "fired";
        const prov = s === "provisional";
        return (
          <path
            key={i}
            d={d}
            fill={fired || prov ? col : "none"}
            fillOpacity={prov ? 0.28 : 1}
            stroke={fired ? col : prov ? "var(--prov)" : (iconOutline ?? "var(--rule)")}
            strokeWidth={large ? 1.5 : 1}
            strokeDasharray={prov ? (large ? "4 3" : "2 1.5") : undefined}
            vectorEffect="non-scaling-stroke"
            strokeLinejoin="round"
          />
        );
      })}
      {showCount &&
        (large ? (
          <>
            <text x="50" y="55" textAnchor="middle" fontSize={thin ? 30 : 24} fontWeight={600} fill="var(--ink)">
              {n}
            </text>
            <text x="50" y={thin ? 70 : 67} textAnchor="middle" fontSize={thin ? 11 : 10} fill="var(--mute)">
              of 8
            </text>
          </>
        ) : (
          <text x="50" y="63" textAnchor="middle" fontSize={34} fontWeight={600} fill="var(--ink)">
            {n}
          </text>
        ))}
    </svg>
  );
}

/** App icon motif: alternating fired segments, long colour, no count. */
export const ICON_STATES: SegState[] = ["fired", "off", "fired", "off", "fired", "off", "fired", "off"];

export function RingMark({ size = 24 }: { size?: number }) {
  return <IndicatorRing states={ICON_STATES} direction="long" size={size} showCount={false} label="Trading desk" />;
}

/** Fib Pivot list marker (40x40): the price position on the ladder. `step` counts levels
 *  from the pivot: 1 = Break, 2 = Confirmation; negative below the pivot. */
export function LadderMark({ direction, step = 1 }: { direction: Direction; step?: number }) {
  const ys = [6, 13, 20, 27, 34];
  const cy = 20 - Math.max(-2, Math.min(2, step)) * 7;
  const where = step === 0 ? "at the pivot" : `${Math.abs(step)} level${Math.abs(step) > 1 ? "s" : ""} ${step > 0 ? "above" : "below"} the pivot`;
  return (
    <svg width={40} height={40} viewBox="0 0 40 40" role="img" aria-label={`Fib Pivot, price ${where}`} className="block flex-none">
      {ys.map((y, i) => (
        <line
          key={y}
          x1={8}
          x2={32}
          y1={y}
          y2={y}
          stroke={i === 2 ? "var(--ink)" : "var(--rule)"}
          strokeWidth={i === 2 ? 1.5 : 1}
        />
      ))}
      <circle cx={20} cy={cy} r={4} fill={direction === "long" ? "var(--long)" : "var(--short)"} />
    </svg>
  );
}
