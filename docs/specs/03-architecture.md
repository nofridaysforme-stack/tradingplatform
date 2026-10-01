# Architecture

## Components

```
                +------------------+        +-------------------+
 OANDA v20 ---> |                  |        |                   |
 (forex bars)   |  scanner worker  | -----> |     Postgres      | <---- web portal (Next.js)
 Massive  ----> |  (Python)        |        |                   |       owners' browsers
 (stock bars)   |                  |        +-------------------+       and installed app
                |  rules engine    |
                |  strategies      | ---> web push, email, Telegram ---> owners' devices
                |  notifications   |
                |  backtest        |
                +------------------+
```

| Component | Responsibility | Runs on |
|---|---|---|
| scanner | Fetch bars, compute levels, evaluate strategies, write signals, track outcomes, send notifications, write heartbeat | Railway service, always on |
| web | Sign-in, dashboards, settings, rule management, push subscription, health view | Railway service |
| postgres | All persistent state | Railway Postgres |

The web app never calls OANDA or Massive. It reads what the worker writes.

## Why a persistent worker

The forex strategy runs every 15 minutes, 24 hours a day, five days a week, and must act within seconds of each bar close. A long-running Python process with an in-process scheduler is simpler and more reliable than serverless functions on a timer, and TA-Lib's native library installs cleanly in a container.

## Repository layout

```
/apps/web
  /app
    /(auth)/sign-in
    /(portal)/dashboard
    /(portal)/signals/[id]
    /(portal)/levels
    /(portal)/stocks
    /(portal)/stocks/[ticker]
    /(portal)/holdings
    /(portal)/history
    /(portal)/econ
    /(portal)/settings/{instruments,brokers,notifications,rules,users}
    /(portal)/health
    /api/{auth,health,push,telegram}
  /components
  /lib/{db,auth,format,pips}
  /public/{manifest.webmanifest,sw.js,icons}

/services/scanner
  /scanner
    main.py                 entry point: scheduler setup
    config.py               env settings (pydantic-settings)
    db.py                   connection pool, repositories
    time.py                 market calendar, session windows, NY day roll
    instruments.py          pip math
    /data
      base.py               DataProvider protocol
      oanda.py              forex candles
      massive.py            stock bars, tickers, splits
    /levels
      floor_pivots.py
      fib_pivot.py
      prev_day.py
    /indicators             pure functions, one file per indicator
      swings.py  trend.py  fibonacci.py  candles.py  hl_failure.py
      trendlines.py  patterns.py  ranging.py  thrust.py
    /rules
      registry.py           loads rule_definitions and strategy_configs
      versions.py
    /strategies
      three_eight.py
      fib_pivot.py
      stock_screener.py
    /signals
      lifecycle.py          dedupe, outcome tracking, expiry
      broker_adjust.py
    /notify
      dispatcher.py  webpush.py  email.py  telegram.py  templates.py
    /jobs
      forex_bar_close.py  forex_day_roll.py  stock_eod.py  outcomes.py  heartbeat.py
    /backtest
      run.py  engine.py  costs.py  metrics.py  report.py
  /tests
    /fixtures
  pyproject.toml
  Dockerfile

/db/migrations              dbmate SQL files
/docs/specs                 this spec set
```

## Data flow: forex bar close

1. Scheduler fires at hh:00:05, hh:15:05, hh:30:05, hh:45:05 UTC while the forex market is open.
2. For each enabled instrument, fetch the latest M15 candles from OANDA; upsert only those with `complete=true`.
3. If a new completed bar exists, run outcome tracking for open signals on that instrument, then run the 3/8 Formula and the Fibonacci Pivot trigger checks.
4. New signals are written in one transaction with their indicators and events.
5. The dispatcher sends notifications according to each owner's preferences and logs delivery.
6. If no new completed bar arrives, retry at +20s and +40s, then log a stale-data warning.

## Data flow: forex day roll (17:00 New York)

1. Fetch the completed daily candle (aligned to 17:00 New York).
2. Compute daily floor pivots, previous day high and low, and the Fibonacci Pivot ladder. On the first day of a week or month, recompute weekly or monthly pivots.
3. Store in `levels`.

## Data flow: stock end of day

1. At 18:30 New York on weekdays, request the grouped daily bars for the session date. Retry every 15 minutes until 23:00 if not yet available.
2. Upsert into `stock_daily_bars`. Check the splits endpoint for that date and refetch history for split tickers.
3. Run the stock screener over the universe. Store results in `stock_screen_results`.
4. Create alerts for newly qualified, trend-confirmed stocks and for holdings that reached their sales target.

## Environments

| Environment | OANDA host | Purpose |
|---|---|---|
| local | practice | Development |
| staging | practice | Integration and the 10-day stability run |
| production | the owners' live account host, or practice if they prefer | Paper run and live use |

Signals do not depend on which OANDA environment is used for data; both serve prices. Use the account the owners hold.

## Real-time updates in the portal

The portal polls `GET` endpoints every 30 seconds with TanStack Query while a tab is visible. Push notifications carry urgency; the portal does not need sockets.
