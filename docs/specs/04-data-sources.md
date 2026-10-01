# Data Sources

All providers sit behind a `DataProvider` protocol so a source can be replaced without touching strategies.

```python
class ForexDataProvider(Protocol):
    def candles(self, instrument: str, granularity: str,
                start: datetime | None, end: datetime | None,
                count: int | None) -> list[Candle]: ...

class StockDataProvider(Protocol):
    def grouped_daily(self, session_date: date) -> list[DailyBar]: ...
    def ticker_history(self, ticker: str, start: date, end: date) -> list[DailyBar]: ...
    def splits_on(self, session_date: date) -> list[Split]: ...
    def active_common_stocks(self) -> list[TickerRef]: ...
```

## Forex: OANDA v20 REST API

| Item | Value |
|---|---|
| Hosts | Practice `https://api-fxpractice.oanda.com`, live `https://api-fxtrade.oanda.com` |
| Auth | `Authorization: Bearer <OANDA_API_TOKEN>` |
| Candles endpoint | `GET /v3/instruments/{instrument}/candles` |
| Granularities used | `M15` (signals), `D` (daily levels), `W`, `M` (weekly and monthly pivots) |
| Price component | `price=M` (mid). Broker spreads are applied later per broker profile. |
| Daily alignment | `dailyAlignment=17&alignmentTimezone=America/New_York` so the daily candle matches the New York 17:00 roll |
| Weekly alignment | `weeklyAlignment=Sunday` with the same timezone |
| Max per request | 5000 candles; page by `from`/`to` for history |
| Rate limits | Stay under 100 requests per second per token; the worker needs far fewer |
| Completed bars | Use only candles with `"complete": true` |
| Instrument names | OANDA format `EUR_USD`; store display format `EUR/USD` separately |

### Candle model

```python
class Candle(BaseModel):
    instrument: str        # "EUR_USD"
    granularity: str       # "M15"
    ts: datetime           # bar open time, UTC
    o: Decimal
    h: Decimal
    l: Decimal
    c: Decimal
    volume: int            # tick volume
    complete: bool
```

### Backfill

On first start, and whenever an instrument is added:
- M15: 120 trading days
- D: 400 days
- W: 104 weeks
- M: 36 months

The backtester requests deeper history directly (see `12-backtesting.md`).

### Gaps and weekends

Forex trades from Sunday 17:00 to Friday 17:00 New York time. The worker skips scheduled runs outside that window and on configured market holidays (Christmas Day and New Year's Day closures; keep a `market_holidays` table admins can edit).

## Instruments and pips

| Instrument | OANDA name | Pip size | Display decimals |
|---|---|---|---|
| EUR/USD | EUR_USD | 0.0001 | 5 |
| GBP/USD | GBP_USD | 0.0001 | 5 |
| USD/JPY | USD_JPY | 0.01 | 3 |
| USD/CHF | USD_CHF | 0.0001 | 5 |
| USD/CAD | USD_CAD | 0.0001 | 5 |
| AUD/USD | AUD_USD | 0.0001 | 5 |
| NZD/USD | NZD_USD | 0.0001 | 5 |

Rule: any pair quoted in JPY uses 0.01. When admins add an instrument, the form pre-fills pip size from this rule and lets them override it.

```python
def to_pips(price_distance: Decimal, pip_size: Decimal) -> Decimal:
    return price_distance / pip_size

def from_pips(pips: Decimal, pip_size: Decimal) -> Decimal:
    return pips * pip_size
```

## Stocks: Massive (formerly Polygon.io)

| Item | Value |
|---|---|
| Host | `https://api.massive.com` (the legacy host `https://api.polygon.io` serves the same API) |
| Auth | `apiKey` query parameter or `Authorization: Bearer` header |
| Plan | Free Basic: 5 calls per minute, end-of-day data, 2 years of history. Upgrade only if timing or limits become a problem. |
| Full-market daily bars | `GET /v2/aggs/grouped/locale/us/market/stocks/{YYYY-MM-DD}?adjusted=true` |
| Single-ticker history | `GET /v2/aggs/ticker/{ticker}/range/1/day/{from}/{to}?adjusted=true` |
| Ticker reference | `GET /v3/reference/tickers?market=stocks&type=CS&active=true&limit=1000` (paginate with `next_url`) |
| Splits | `GET /v3/reference/splits?execution_date={YYYY-MM-DD}` |

### Rate limiting

The Massive client enforces 5 calls per rolling 60 seconds with a token bucket. All Massive calls go through one shared limiter.

### Initial backfill

Fetch grouped daily bars for the last 300 trading sessions (enough for 252-session highs and lows plus the 50-session close). At 5 calls per minute this takes about an hour, once. Run it as a one-time job with progress logged to `job_runs`.

### Splits

Stored bars are adjusted as of the day they were fetched. When a split executes, older stored bars for that ticker become inconsistent. Each evening, after loading the grouped bars, call the splits endpoint for that date and refetch full history for each affected ticker with the single-ticker endpoint, replacing its stored rows.

### Universe

Active common stocks (`type=CS`) on NYSE, Nasdaq, and NYSE American. Refresh the reference list weekly. OTC tickers are excluded. Liquidity filters are strategy parameters (see `08-strategy-stock-screener.md`).

## Econ events (first release: manual)

Admins enter events in the portal: datetime (New York), currency, title, impact (high, medium, low). An `EconCalendarProvider` protocol exists so an automated source can be added later without changing strategy code. Choosing that source is an open item.

## Data staleness rules

| Check | Threshold | Action |
|---|---|---|
| No new completed M15 bar for an enabled pair while market open | 30 minutes | Health warning, alert Jana and admins |
| Daily levels missing for today after 17:20 New York | 20 minutes | Health warning and retry |
| Stock grouped bars missing by 23:00 New York on a session day | | Health warning; screener skips that day |
| OANDA or Massive returns 401 or 403 | Immediate | Health error, alert, stop calls to that provider until next hour |
