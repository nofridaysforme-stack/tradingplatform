// Reference implementation of the 3/8 indicator ring, the product's signature element.
// The geometry matches the design files exactly. Port it to your framework as needed.
import React from 'react';

export type SegState = 'fired' | 'provisional' | 'off';
export type Direction = 'long' | 'short';

// Fixed order, clockwise from 12 o'clock. Never reorder.
export const INDICATORS = [
  { name: 'Candlestick', short: 'Candle' },
  { name: 'New high/low failure', short: 'Failure' },
  { name: 'Pivots', short: 'Pivots' },
  { name: 'Flags, pennants, triangles', short: 'Patterns' },
  { name: 'Trendlines and channels', short: 'Lines' },
  { name: 'Previous day high', short: 'PDH' },
  { name: 'Previous day low', short: 'PDL' },
  { name: 'Fibonacci', short: 'Fib' },
] as const;

interface Props {
  states: SegState[];          // length 8, in INDICATORS order
  direction: Direction;
  size: 120 | 112 | 72 | 52 | 40 | 28 | 24 | number; // 120/112 = signal page, 40 = list row, 52/28/24 = icon
  variant?: 'segments' | 'hairline';
  showCount?: boolean;         // false for icon and empty state
  iconOutline?: string;        // override unfired stroke (dark app icon uses #6B737B)
}

export function IndicatorRing({ states, direction, size, variant = 'segments', showCount = true, iconOutline }: Props) {
  const thin = variant === 'hairline';
  const R = 47, r = thin ? 39 : 30, gap = thin ? 3 : 4.5; // viewBox 0 0 100 100
  const large = size >= 80;
  const col = direction === 'long' ? 'var(--long)' : 'var(--short)';
  const pt = (a: number, rad: number) => `${(50 + rad * Math.cos(a)).toFixed(2)} ${(50 + rad * Math.sin(a)).toFixed(2)}`;
  const n = states.filter(s => s !== 'off').length;

  return (
    <svg width={size} height={size} viewBox="0 0 100 100" role="img"
      aria-label={`${n} of 8 indicators fired`} style={{ display: 'block', flex: 'none' }}>
      {states.map((s, i) => {
        const a0 = (-90 + i * 45 + gap / 2) * Math.PI / 180;
        const a1 = (-90 + (i + 1) * 45 - gap / 2) * Math.PI / 180;
        const d = `M${pt(a0, R)}A${R} ${R} 0 0 1 ${pt(a1, R)}L${pt(a1, r)}A${r} ${r} 0 0 0 ${pt(a0, r)}Z`;
        const fired = s === 'fired', prov = s === 'provisional';
        return (
          <path key={i} d={d}
            fill={fired || prov ? col : 'none'}
            fillOpacity={prov ? 0.28 : 1}
            stroke={fired ? col : prov ? 'var(--prov)' : (iconOutline ?? 'var(--rule)')}
            strokeWidth={large ? 1.5 : 1}
            strokeDasharray={prov ? (large ? '4 3' : '2 1.5') : undefined}
            vectorEffect="non-scaling-stroke" strokeLinejoin="round" />
        );
      })}
      {showCount && (large ? (
        <>
          <text x="50" y="55" textAnchor="middle" fontSize={thin ? 30 : 24} fontWeight={600} fill="var(--ink)">{n}</text>
          <text x="50" y={thin ? 70 : 67} textAnchor="middle" fontSize={thin ? 11 : 10} fill="var(--mute)">of 8</text>
        </>
      ) : (
        <text x="50" y="63" textAnchor="middle" fontSize={34} fontWeight={600} fill="var(--ink)">{n}</text>
      ))}
    </svg>
  );
}

// App icon motif: alternating fired segments, long colour, no count.
export const ICON_STATES: SegState[] = ['fired', 'off', 'fired', 'off', 'fired', 'off', 'fired', 'off'];

// Fib Pivot list marker (40×40), used in place of the ring for Fib Pivot signals.
export function LadderMark({ direction }: { direction: Direction }) {
  const ys = [6, 13, 20, 27, 34];
  return (
    <svg width={40} height={40} viewBox="0 0 40 40" role="img" aria-label="Fib Pivot, price at R1">
      {ys.map((y, i) => (
        <line key={i} x1={8} x2={32} y1={y} y2={y} stroke={i === 2 ? 'var(--ink)' : 'var(--rule)'} strokeWidth={i === 2 ? 1.5 : 1} />
      ))}
      <circle cx={20} cy={13} r={4} fill={direction === 'long' ? 'var(--long)' : 'var(--short)'} />
    </svg>
  );
}
