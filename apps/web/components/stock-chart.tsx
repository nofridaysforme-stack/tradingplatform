"use client";

import { CandlestickSeries, createChart } from "lightweight-charts";
import { useEffect, useRef } from "react";

const css = (name: string) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

/** Six months of daily bars, in the handoff's candle style. */
export function StockChart({ ticker, bars }: { ticker: string; bars: { time: string; open: number; high: number; low: number; close: number }[] }) {
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = box.current;
    if (!el || bars.length === 0) return;
    const ink = css("--ink");
    const bg = css("--bg");
    const chart = createChart(el, {
      autoSize: true,
      layout: { background: { color: bg }, textColor: css("--mute"), fontFamily: "IBM Plex Sans Condensed, IBM Plex Sans, sans-serif", fontSize: 10 },
      grid: { vertLines: { visible: false }, horzLines: { visible: false } },
      rightPriceScale: { borderColor: css("--rule") },
      timeScale: { borderColor: css("--rule") },
      localization: { priceFormatter: (p: number) => p.toFixed(2) },
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
    });
    series.setData(bars);
    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [bars]);
  if (bars.length === 0) return <p className="m-0 text-sm text-ink-2">No daily bars are stored for {ticker} yet.</p>;
  return (
    <figure className="m-0">
      <div ref={box} className="h-[260px] w-full" />
      <figcaption className="mt-2 text-[13px] text-mute">Daily bars for the last {bars.length} sessions.</figcaption>
    </figure>
  );
}
