"use client";

import {
  CandlestickSeries,
  createChart,
  createSeriesMarkers,
  HistogramSeries,
  LineSeries,
  LineStyle,
  type IChartApi,
  type ISeriesApi,
  type SeriesMarker,
  type SeriesType,
  type Time,
} from "lightweight-charts";
import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import type { ChartSeries } from "@/lib/db/schema";
import { EXIT_NAMES } from "@/lib/stock-names";

const css = (name: string) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

export interface ChartBar {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface ChartBuy {
  buySession: string;
  entry: number;
  state: string;
  exitSession: string | null;
  stopNow: number;
}

type Frame = "daily" | "weekly" | "monthly";
const FRAMES: [Frame, string][] = [
  ["daily", "Daily"],
  ["weekly", "Weekly"],
  ["monthly", "Monthly"],
];
/** The lines one bar length draws: the daily series, or its weekly or monthly view. */
type Lines = Pick<ChartSeries, "sessions" | "ma" | "volume_average" | "rsi" | "stoch_k" | "stoch_d" | "macd" | "macd_signal" | "macd_histogram">;

type PaneKey = "price" | "volume" | "macd" | "rsi" | "stoch";
// Pixel heights; RSI and Stochastics are behind the toggle (owners 2026-11-02).
const HEIGHTS: Record<PaneKey, number> = { price: 280, volume: 70, macd: 110, rsi: 90, stoch: 90 };
const TIME_AXIS = 28;

interface Legend {
  title: string;
  items: { name: string; value: string; color: string }[];
}

const WIDE = "(min-width: 1024px)";
const isWide = () => window.matchMedia(WIDE).matches;
function subscribeWide(onChange: () => void) {
  const q = window.matchMedia(WIDE);
  q.addEventListener("change", onChange);
  return () => q.removeEventListener("change", onChange);
}

const fmt = (v: number | null | undefined, digits = 2) => (v === null || v === undefined ? "" : v.toFixed(digits));
const last = (xs: (number | null)[] | null | undefined) => {
  if (!xs) return null;
  for (let i = xs.length - 1; i >= 0; i--) if (xs[i] !== null && xs[i] !== undefined) return xs[i]!;
  return null;
};
const volumeText = (v: number | null) =>
  v === null ? "" : v >= 1e6 ? `${(v / 1e6).toFixed(2)}M` : v >= 1e3 ? `${(v / 1e3).toFixed(0)}K` : String(Math.round(v));

/** The line for a series of values aligned with the chart's sessions; gaps are left out. */
function line(sessions: string[], values: (number | null)[] | null | undefined) {
  if (!values) return [];
  return sessions.flatMap((time, i) => (values[i] === null || values[i] === undefined ? [] : [{ time: time as Time, value: values[i]! }]));
}

/**
 * Daily candles with the scanner's indicators in stacked panes (spec 13): price with the
 * moving averages, the 52-week high and its 10% zone, and buy and sell markers; then volume,
 * MACD, and (with the toggle) RSI and Stochastics. Every line was computed by the scanner;
 * this only draws it (CLAUDE.md rule 1).
 */
export function StockChart({ ticker, bars, chart, buys = [] }: { ticker: string; bars: ChartBar[]; chart: ChartSeries | null; buys?: ChartBuy[] }) {
  const box = useRef<HTMLDivElement>(null);
  // Wide screens open with every pane; phones with price, volume, and MACD. The toggle wins.
  const wide = useSyncExternalStore(subscribeWide, isWide, () => false);
  const [choice, setChoice] = useState<boolean | null>(null);
  const all = choice ?? wide;
  // Weekly and monthly bars carry their own lines from the scanner, in weeks or months.
  const [frame, setFrame] = useState<Frame>("daily");
  const view = frame !== "daily" && chart?.[frame] ? chart[frame] : null;
  const daily = view === null;
  const shown: ChartBar[] = view ? view.bars : bars;
  const lines: Lines | null = view ?? chart;

  // A pane shows only when its line has values: monthly bars need years of history first.
  const has = { macd: last(lines?.macd) !== null, rsi: last(lines?.rsi) !== null, stoch: last(lines?.stoch_k) !== null };
  const panes: PaneKey[] = ["price", "volume", ...(has.macd ? (["macd"] as PaneKey[]) : [])];
  if (all && has.rsi) panes.push("rsi");
  if (all && has.stoch) panes.push("stoch");
  const height = panes.reduce((h, p) => h + HEIGHTS[p], 0) + TIME_AXIS;
  const legends = legendsFor(panes, shown, lines, chart);

  useEffect(() => {
    const el = box.current;
    if (!el || shown.length === 0) return;
    const color = { ink: css("--ink"), bg: css("--bg"), mute: css("--mute"), rule: css("--rule"), long: css("--long"), short: css("--short"), c1: css("--chart-1"), c2: css("--chart-2"), c3: css("--chart-3"), up: css("--chart-up"), down: css("--chart-down") };
    const c: IChartApi = createChart(el, {
      autoSize: true,
      layout: {
        background: { color: color.bg },
        textColor: color.mute,
        fontFamily: "IBM Plex Sans Condensed, IBM Plex Sans, sans-serif",
        fontSize: 10,
        panes: { separatorColor: color.rule, enableResize: false },
      },
      grid: { vertLines: { visible: false }, horzLines: { visible: false } },
      rightPriceScale: { borderColor: color.rule },
      // Room after the last bar for the high and low labels.
      timeScale: { borderColor: color.rule, rightOffset: 8 },
      handleScroll: false,
      handleScale: false,
    });
    const pane = (key: PaneKey) => panes.indexOf(key);

    // Price: candles, moving averages, the 52-week high and the zone, stops, and markers.
    const candles = c.addSeries(CandlestickSeries, {
      // Green up and red down (owners 2026-11-02); the words and arrows carry Buy and Sell.
      upColor: color.up,
      downColor: color.down,
      borderUpColor: color.up,
      borderDownColor: color.down,
      wickUpColor: color.up,
      wickDownColor: color.down,
      priceLineVisible: true,
      priceLineStyle: LineStyle.Dashed,
      priceLineColor: color.mute,
      lastValueVisible: true,
      priceFormat: { type: "price", precision: 2, minMove: 0.01 },
    });
    candles.setData(shown.map((b) => ({ time: b.time as Time, open: b.open, high: b.high, low: b.low, close: b.close })));
    const sessions = lines?.sessions ?? [];
    const maColors = [color.c1, color.c2, color.c3];
    Object.entries(lines?.ma ?? {})
      .sort(([a], [b]) => Number(a) - Number(b))
      .forEach(([, values], i) => {
        c.addSeries(LineSeries, { color: maColors[i % 3], lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false }).setData(line(sessions, values));
      });
    if (chart) {
      candles.createPriceLine({ price: chart.levels.high_52w, color: color.mute, lineStyle: LineStyle.Dotted, lineWidth: 1, title: "52-week high", axisLabelVisible: true });
      candles.createPriceLine({ price: chart.levels.zone_low, color: color.mute, lineStyle: LineStyle.Dotted, lineWidth: 1, title: "10% zone", axisLabelVisible: true });
    }
    for (const b of buys.filter((x) => x.state === "open")) {
      candles.createPriceLine({ price: b.stopNow, color: color.down, lineStyle: LineStyle.Dashed, lineWidth: 1, title: `Stop ${b.stopNow.toFixed(2)}`, axisLabelVisible: true });
    }
    createSeriesMarkers(candles, priceMarkers(shown, buys, color));

    // Volume, with its average.
    const vp = pane("volume");
    c.addSeries(HistogramSeries, { priceFormat: { type: "volume" }, priceLineVisible: false, lastValueVisible: false }, vp).setData(
      shown.map((b) => ({ time: b.time as Time, value: b.volume, color: b.close >= b.open ? color.up : color.down })),
    );
    if (lines?.volume_average) {
      const avg = c.addSeries(LineSeries, { color: color.c2, lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false, priceFormat: { type: "volume" } }, vp);
      avg.setData(line(sessions, lines.volume_average));
      if (daily && chart) voteDots(avg, chart, "stocks.ind_volume", color);
    }

    // MACD: the histogram, the MACD line, and its signal line.
    if (lines?.macd && pane("macd") >= 0) {
      const mp = pane("macd");
      c.addSeries(HistogramSeries, { priceLineVisible: false, lastValueVisible: false }, mp).setData(
        line(sessions, lines.macd_histogram).map((p) => ({ ...p, color: p.value >= 0 ? color.up : color.down })),
      );
      const m = c.addSeries(LineSeries, { color: color.c1, lineWidth: 1, priceLineVisible: false, lastValueVisible: false }, mp);
      m.setData(line(sessions, lines.macd));
      c.addSeries(LineSeries, { color: color.c2, lineWidth: 1, priceLineVisible: false, lastValueVisible: false }, mp).setData(line(sessions, lines.macd_signal));
      if (daily && chart) voteDots(m, chart, "stocks.ind_macd", color);
    }

    // RSI and Stochastics, with their buy and sell levels.
    if (chart && lines?.rsi && pane("rsi") >= 0) {
      const r = c.addSeries(LineSeries, { color: color.c1, lineWidth: 1, priceLineVisible: false, lastValueVisible: false }, pane("rsi"));
      r.setData(line(sessions, lines.rsi));
      for (const level of chart.levels.rsi) r.createPriceLine({ price: level, color: color.mute, lineStyle: LineStyle.Dashed, lineWidth: 1, axisLabelVisible: true, title: "" });
      if (daily && chart) voteDots(r, chart, "stocks.ind_rsi", color);
    }
    if (chart && lines?.stoch_k && pane("stoch") >= 0) {
      const k = c.addSeries(LineSeries, { color: color.c1, lineWidth: 1, priceLineVisible: false, lastValueVisible: false }, pane("stoch"));
      k.setData(line(sessions, lines.stoch_k));
      c.addSeries(LineSeries, { color: color.c2, lineWidth: 1, priceLineVisible: false, lastValueVisible: false }, pane("stoch")).setData(line(sessions, lines.stoch_d));
      for (const level of chart.levels.stoch) k.createPriceLine({ price: level, color: color.mute, lineStyle: LineStyle.Dashed, lineWidth: 1, axisLabelVisible: true, title: "" });
      if (daily && chart) voteDots(k, chart, "stocks.ind_stoch", color);
    }

    // Pane sizes are shares of the chart's height; the container is the sum of the heights.
    c.panes().forEach((p, i) => p.setStretchFactor(HEIGHTS[panes[i]!]));
    c.timeScale().fitContent();
    return () => c.remove();
    // panes is derived from chart and all; listing those keeps the effect stable.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [shown, lines, chart, buys, all, daily]);

  if (bars.length === 0) return <p className="m-0 text-sm text-ink-2">No daily bars are stored for {ticker} yet.</p>;
  let top = 0;
  return (
    <figure className="m-0">
      {chart?.weekly || chart?.monthly ? (
        <div role="group" aria-label="Bar length" className="mb-1 flex gap-1">
          {FRAMES.map(([key, label]) => (
            <button
              key={key}
              type="button"
              aria-pressed={frame === key}
              onClick={() => setFrame(key)}
              className={`inline-flex min-h-11 items-center rounded-[var(--radius-control)] px-3 text-sm ${frame === key ? "bg-selected font-semibold text-ink" : "text-link"}`}
            >
              {label}
            </button>
          ))}
        </div>
      ) : null}
      {has.rsi || has.stoch ? (
        <button
          type="button"
          aria-pressed={all}
          onClick={() => setChoice(!all)}
          className="mb-2 inline-flex min-h-11 items-center text-sm text-link"
        >
          {all ? "Hide RSI and Stochastics" : "Show RSI and Stochastics"}
        </button>
      ) : null}
      <div className="relative w-full" style={{ height }}>
        <div ref={box} className="absolute inset-0" />
        {panes.map((p) => {
          const at = top;
          top += HEIGHTS[p];
          const l = legends[p];
          return l ? (
            <div key={p} className="pointer-events-none absolute left-1 z-10 flex flex-wrap gap-x-2 text-[11px] leading-4" style={{ top: at + 2 }}>
              <span className="text-mute">{l.title}</span>
              {l.items.map((it) => (
                <span key={it.name} style={{ color: it.color }}>
                  {it.name} {it.value}
                </span>
              ))}
            </div>
          ) : null;
        })}
      </div>
      <figcaption className="mt-2 text-[13px] text-mute">
        {daily
          ? `Daily bars for the last ${shown.length} sessions.`
          : `${frame === "weekly" ? "Weekly" : "Monthly"} bars for the last ${shown.length} ${frame === "weekly" ? "weeks" : "months"}; the averages and indicators count ${frame === "weekly" ? "weeks" : "months"} instead of days. Buys and sells are decided on daily bars.`}
        {!lines
          ? " Indicator lines appear after this stock's next screen."
          : daily
            ? " Indicator lines and dots are the scanner's own values; a dot marks a session where that indicator voted."
            : ""}
      </figcaption>
    </figure>
  );
}

/** Pane titles with the last values, read by screen readers too. Colors follow the CSS
 *  tokens; every line also has its name. */
function legendsFor(panes: PaneKey[], bars: ChartBar[], lines: Lines | null, chart: ChartSeries | null): Partial<Record<PaneKey, Legend>> {
  const c = ["var(--chart-1)", "var(--chart-2)", "var(--chart-3)"];
  const out: Partial<Record<PaneKey, Legend>> = {};
  const lastBar = bars.at(-1);
  out.price = {
    title: "Price",
    items: [
      { name: "Close", value: fmt(lastBar?.close), color: "var(--ink)" },
      { name: "High", value: fmt(bars.length ? Math.max(...bars.map((b) => b.high)) : null), color: "var(--mute)" },
      { name: "Low", value: fmt(bars.length ? Math.min(...bars.map((b) => b.low)) : null), color: "var(--mute)" },
      ...Object.entries(lines?.ma ?? {})
        .sort(([a], [b]) => Number(a) - Number(b))
        .map(([n, v], i) => ({ name: `MA ${n}`, value: fmt(last(v)), color: c[i % 3]! })),
    ],
  };
  out.volume = {
    title: "Volume",
    items: [
      { name: "Latest", value: volumeText(lastBar?.volume ?? null), color: "var(--ink)" },
      ...(last(lines?.volume_average) !== null ? [{ name: "Average", value: volumeText(last(lines?.volume_average)), color: c[1]! }] : []),
    ],
  };
  if (chart && lines?.macd && panes.includes("macd")) {
    const [f, s, g] = chart.settings.macd;
    out.macd = {
      title: `MACD(${f},${s},${g})`,
      items: [
        { name: "MACD", value: fmt(last(lines.macd), 3), color: c[0]! },
        { name: "Signal", value: fmt(last(lines.macd_signal), 3), color: c[1]! },
        { name: "Histogram", value: fmt(last(lines.macd_histogram), 3), color: "var(--chart-3)" },
      ],
    };
  }
  if (chart && lines?.rsi && panes.includes("rsi")) {
    out.rsi = { title: `RSI(${chart.settings.rsi}) · ${chart.levels.rsi.join(" and ")}`, items: [{ name: "RSI", value: fmt(last(lines.rsi)), color: c[0]! }] };
  }
  if (chart && lines?.stoch_k && panes.includes("stoch")) {
    out.stoch = {
      title: `Stochastics(${chart.settings.stoch.join(",")}) · ${chart.levels.stoch.join(" and ")}`,
      items: [
        { name: "%K", value: fmt(last(lines.stoch_k)), color: c[0]! },
        { name: "%D", value: fmt(last(lines.stoch_d)), color: c[1]! },
      ],
    };
  }
  return out;
}

/** Buy and exit arrows with their words, and dots at the period's high and low. */
function priceMarkers(bars: ChartBar[], buys: ChartBuy[], color: { up: string; down: string; mute: string }): SeriesMarker<Time>[] {
  // The bar that holds a session: the day itself, or the week or month it ends (bars are
  // dated by their last session).
  const holder = (day: string) => {
    const i = bars.findIndex((b) => b.time >= day);
    return i >= 0 && (i > 0 || bars[0]!.time === day) ? bars[i]!.time : null;
  };
  const out: SeriesMarker<Time>[] = [];
  for (const b of buys) {
    const bought = holder(b.buySession);
    const exited = b.exitSession ? holder(b.exitSession) : null;
    if (bought) out.push({ time: bought as Time, position: "belowBar", shape: "arrowUp", color: color.up, text: "Buy" });
    if (exited) {
      out.push({ time: exited as Time, position: "aboveBar", shape: "arrowDown", color: color.down, text: EXIT_NAMES[b.state] ?? "Sell" });
    }
  }
  if (bars.length > 1) {
    const hi = bars.reduce((a, b) => (b.high > a.high ? b : a));
    const lo = bars.reduce((a, b) => (b.low < a.low ? b : a));
    // The values are in the price title; text here would be cut off at the chart's edges.
    out.push({ time: hi.time as Time, position: "aboveBar", shape: "circle", size: 0.5, color: color.mute });
    out.push({ time: lo.time as Time, position: "belowBar", shape: "circle", size: 0.5, color: color.mute });
  }
  return out.sort((a, b) => (String(a.time) < String(b.time) ? -1 : String(a.time) > String(b.time) ? 1 : 0));
}

/** A small dot on the sessions where an indicator voted to buy (below) or sell (above). */
function voteDots(series: ISeriesApi<SeriesType>, chart: ChartSeries, key: string, color: { up: string; down: string }) {
  const v = chart.votes[key];
  if (!v) return;
  const markers: SeriesMarker<Time>[] = [
    ...v.buy.map((t) => ({ time: t as Time, position: "belowBar" as const, shape: "circle" as const, size: 0.4, color: color.up })),
    ...v.sell.map((t) => ({ time: t as Time, position: "aboveBar" as const, shape: "circle" as const, size: 0.4, color: color.down })),
  ].sort((a, b) => (String(a.time) < String(b.time) ? -1 : 1));
  createSeriesMarkers(series, markers);
}
