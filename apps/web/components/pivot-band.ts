import type {
  IChartApiBase,
  IPrimitivePaneRenderer,
  IPrimitivePaneView,
  ISeriesApi,
  ISeriesPrimitive,
  SeriesAttachedParameter,
  SeriesType,
  Time,
} from "lightweight-charts";

type Target = Parameters<IPrimitivePaneRenderer["draw"]>[0];

export interface BandPoint {
  time: Time;
  /** The pivot MA. */
  a: number;
  /** Its signal line. */
  b: number;
}

/**
 * The fill between the pivot MA and its signal line, as in the client's script: green while
 * the pivot MA is at or above the signal line, red while it is below. Drawn under the candles.
 */
export class PivotBand implements ISeriesPrimitive<Time> {
  private chart: IChartApiBase<Time> | null = null;
  private series: ISeriesApi<SeriesType, Time> | null = null;

  constructor(
    private readonly points: BandPoint[],
    private readonly up: string,
    private readonly down: string,
  ) {}

  attached({ chart, series }: SeriesAttachedParameter<Time>): void {
    this.chart = chart;
    this.series = series;
  }

  detached(): void {
    this.chart = null;
    this.series = null;
  }

  paneViews(): readonly IPrimitivePaneView[] {
    return [{ zOrder: () => "bottom", renderer: () => ({ draw: (target: Target) => this.draw(target) }) }];
  }

  private draw(target: Target): void {
    const { chart, series } = this;
    if (!chart || !series) return;
    const ts = chart.timeScale();
    target.useBitmapCoordinateSpace(({ context: ctx, horizontalPixelRatio: hr, verticalPixelRatio: vr }) => {
      ctx.save();
      ctx.globalAlpha = 0.15;
      let prev: { x: number; ya: number; yb: number } | null = null;
      for (const p of this.points) {
        const x = ts.timeToCoordinate(p.time);
        const ya = series.priceToCoordinate(p.a);
        const yb = series.priceToCoordinate(p.b);
        if (x === null || ya === null || yb === null) {
          prev = null;
          continue;
        }
        const cur = { x: x * hr, ya: ya * vr, yb: yb * vr };
        if (prev) {
          ctx.fillStyle = p.a >= p.b ? this.up : this.down;
          ctx.beginPath();
          ctx.moveTo(prev.x, prev.ya);
          ctx.lineTo(cur.x, cur.ya);
          ctx.lineTo(cur.x, cur.yb);
          ctx.lineTo(prev.x, prev.yb);
          ctx.closePath();
          ctx.fill();
        }
        prev = cur;
      }
      ctx.restore();
    });
  }
}
