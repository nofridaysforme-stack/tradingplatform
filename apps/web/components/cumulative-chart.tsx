"use client";

import { useEffect, useRef, useState } from "react";
import { nyDateTime, pips } from "@/lib/format";

const H = 140;
const PAD = { top: 10, right: 12, bottom: 18, left: 44 };

/** Cumulative pips (handoff: 1.5px ink polyline, rule zero line, no fill) with a crosshair
 *  and tooltip. The table below the chart is its data view. */
export function CumulativeChart({ points }: { points: { at: string; pips: number }[] }) {
  const box = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(720);
  const [hover, setHover] = useState<number | null>(null);
  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => e && setWidth(Math.max(240, e.contentRect.width)));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  if (points.length < 2) {
    return <p className="m-0 text-sm text-ink-2">The chart appears once two signals have closed for this filter.</p>;
  }
  const values = points.map((p) => p.pips);
  const lo = Math.min(0, ...values);
  const hi = Math.max(0, ...values);
  const span = hi - lo || 1;
  const x = (i: number) => PAD.left + (i / (points.length - 1)) * (width - PAD.left - PAD.right);
  const y = (v: number) => PAD.top + ((hi - v) / span) * (H - PAD.top - PAD.bottom);
  const line = points.map((p, i) => `${x(i).toFixed(1)},${y(p.pips).toFixed(1)}`).join(" ");
  const last = points[points.length - 1]!;
  const h = hover === null ? null : points[hover];

  const onMove = (clientX: number) => {
    const rect = box.current?.getBoundingClientRect();
    if (!rect) return;
    const rel = (clientX - rect.left - PAD.left) / (width - PAD.left - PAD.right);
    setHover(Math.max(0, Math.min(points.length - 1, Math.round(rel * (points.length - 1)))));
  };

  return (
    <figure className="m-0">
      <div
        ref={box}
        className="relative overflow-hidden"
        onPointerMove={(e) => onMove(e.clientX)}
        onPointerLeave={() => setHover(null)}
        tabIndex={0}
        role="group"
        aria-label={`Cumulative pips over ${points.length} closed signals, ending at ${pips(last.pips)}. Use the left and right arrow keys to read each point.`}
        onKeyDown={(e) => {
          if (e.key === "ArrowRight") setHover((v) => Math.min(points.length - 1, (v ?? -1) + 1));
          if (e.key === "ArrowLeft") setHover((v) => Math.max(0, (v ?? points.length) - 1));
          if (e.key === "Escape") setHover(null);
        }}
        onBlur={() => setHover(null)}
      >
        <svg width={width} height={H} className="block" aria-hidden="true">
          <line x1={PAD.left} x2={width - PAD.right} y1={y(0)} y2={y(0)} stroke="var(--rule)" strokeWidth={1} />
          <text x={PAD.left - 6} y={y(0) + 3} textAnchor="end" fontSize={10} fill="var(--mute)">
            0
          </text>
          {hi > 0 && (
            <text x={PAD.left - 6} y={y(hi) + 3} textAnchor="end" fontSize={10} fill="var(--mute)">
              {pips(hi)}
            </text>
          )}
          {lo < 0 && (
            <text x={PAD.left - 6} y={y(lo) + 3} textAnchor="end" fontSize={10} fill="var(--mute)">
              {pips(lo)}
            </text>
          )}
          <polyline points={line} fill="none" stroke="var(--ink)" strokeWidth={1.5} strokeLinejoin="round" />
          {h && hover !== null && (
            <>
              <line x1={x(hover)} x2={x(hover)} y1={PAD.top} y2={H - PAD.bottom} stroke="var(--faint)" strokeWidth={1} />
              <circle cx={x(hover)} cy={y(h.pips)} r={4} fill="var(--ink)" stroke="var(--bg)" strokeWidth={2} />
            </>
          )}
        </svg>
        {h && hover !== null && (
          <div
            role="status"
            className="pointer-events-none absolute top-0 rounded-badge border border-ink bg-bg px-2 py-1 text-xs text-ink"
            style={{ left: Math.min(x(hover) + 8, width - 150) }}
          >
            <div className="font-semibold">{pips(h.pips)} pips</div>
            <div className="text-mute">
              Signal {hover + 1} · {h.at.length > 10 ? `${nyDateTime(new Date(h.at))} NY` : h.at}
            </div>
          </div>
        )}
      </div>
    </figure>
  );
}
