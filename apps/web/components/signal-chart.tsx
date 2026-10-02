"use client";

import {
  CandlestickSeries,
  createChart,
  createSeriesMarkers,
  LineStyle,
  type AutoscaleInfo,
  type IChartApi,
  type UTCTimestamp,
} from "lightweight-charts";
import { useEffect, useRef } from "react";
import { nyTime } from "@/lib/format";
import type { SignalDetail } from "@/lib/signals";

const css = (name: string) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

/** Handoff chart spec: hollow up bodies, solid down bodies, labeled level lines, and a
 *  direction-colour triangle under the trigger bar. TradingView Lightweight Charts keeps its
 *  attribution logo, as its license asks. */
export function SignalChart({ signal }: { signal: SignalDetail }) {
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = box.current;
    if (!el || signal.candles.length === 0) return;
    const ink = css("--ink");
    const bg = css("--bg");
    const faint = css("--faint");
    const chart: IChartApi = createChart(el, {
      autoSize: true,
      layout: { background: { color: bg }, textColor: css("--mute"), fontFamily: "IBM Plex Sans Condensed, IBM Plex Sans, sans-serif", fontSize: 10 },
      grid: { vertLines: { visible: false }, horzLines: { visible: false } },
      rightPriceScale: { borderColor: css("--rule") },
      timeScale: {
        borderColor: css("--rule"),
        timeVisible: true,
        tickMarkFormatter: (t: number) => nyTime(new Date(t * 1000)),
      },
      localization: {
        timeFormatter: (t: number) => `${nyTime(new Date(t * 1000))} NY`,
        priceFormatter: (p: number) => p.toFixed(signal.decimals),
      },
      handleScroll: false,
      handleScale: false,
    });
    const series = chart.addSeries(CandlestickSeries, {
      upColor: bg,
      downColor: ink,
      borderUpColor: ink,
      borderDownColor: ink,
      wickUpColor: ink,
      wickDownColor: ink,
      priceLineVisible: false,
      lastValueVisible: false,
      // Keep entry, stop, and target on screen even when price has not reached them.
      autoscaleInfoProvider: (original: () => AutoscaleInfo | null) => {
        const r = original();
        if (!r?.priceRange) return r;
        const plan = [signal.reference.entry, signal.reference.stop, signal.reference.target].map(Number);
        return {
          ...r,
          priceRange: {
            minValue: Math.min(r.priceRange.minValue, ...plan),
            maxValue: Math.max(r.priceRange.maxValue, ...plan),
          },
        };
      },
    });
    series.setData(signal.candles.map((c) => ({ ...c, time: c.time as UTCTimestamp })));
    const line = (price: number, title: string, color: string, style: LineStyle, width: 1 | 2 = 1) =>
      series.createPriceLine({ price, title, color, lineStyle: style, lineWidth: width, axisLabelVisible: false });
    for (const l of signal.levels) {
      line(l.price, l.label, faint, l.kind === "prev_day" ? LineStyle.Dotted : l.kind === "fib" ? LineStyle.LargeDashed : LineStyle.Dashed);
    }
    const p = signal.reference;
    line(Number(p.entry), "Entry", ink, LineStyle.Solid, 2);
    line(Number(p.stop), "Stop", ink, LineStyle.Dashed);
    line(Number(p.target), "Target", css("--long"), LineStyle.Solid, 2);
    const dir = signal.direction === "long" ? css("--long") : css("--short");
    createSeriesMarkers(series, [
      {
        time: (new Date(signal.bar_ts).getTime() / 1000) as UTCTimestamp,
        position: "belowBar",
        shape: "arrowUp",
        color: dir,
        size: 1,
      },
    ]);
    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [signal]);

  if (signal.candles.length === 0) {
    return <p className="m-0 text-sm text-ink-2">No 15-minute bars are stored for this signal yet.</p>;
  }
  return (
    <figure className="m-0">
      <div ref={box} className="h-[280px] w-full" />
      <figcaption className="mt-2 text-[13px] text-mute">
        15-minute bars in New York time with entry, stop, target, and levels. The triangle marks the bar that
        triggered the signal.
      </figcaption>
    </figure>
  );
}
