# Product Requirements

## Purpose

The owners trade with three written systems that were designed to be applied by hand with a calculator and a newspaper. The portal applies those systems continuously and consistently, tells the owners when a setup appears, shows exactly why, and keeps an honest record of how every suggestion turned out.

## Users

| Role | Who | Can do |
|---|---|---|
| Owner | Each business owner | View signals, levels, screener, history. Set personal notification preferences, active broker, tracked stock holdings. |
| Admin | One or more owners, plus Jana during the build | Everything an owner can do, plus manage instruments, broker profiles, rule definitions, econ events, and users |

Expected users: 2 to 5. No public access.

## Jobs the portal does

1. Watch the seven USD major pairs on 15-minute bars and alert when the 3/8 Formula finds a qualifying setup.
2. Compute the Fibonacci Pivot ladder for each pair every trading day and alert when price breaks, confirms, reaches take profit, or reaches reset.
3. Screen the whole US stock market after each close and alert when a stock newly qualifies and its trend is confirmed. Track owner-entered holdings against their sales targets.
4. Show each suggestion as a complete trade plan: direction, entry, stop, target, reward-to-risk, and the reasons.
5. Adjust entry and exit prices for the owner's active broker.
6. Track the outcome of every suggestion automatically.
7. Let admins change rule definitions without a developer, with version history.

## Functional requirements

### Signals
- F1. The worker evaluates each enabled forex instrument within 60 seconds of every 15-minute bar close while the forex market is open.
- F2. Each signal stores strategy, instrument, direction, entry, stop, target, reward-to-risk, fired indicators, provisional flags, rule version set, and the bar that triggered it.
- F3. Duplicate signals for the same setup are suppressed (see `10-signal-lifecycle.md`).
- F4. Every signal is evaluated on each later bar until it closes as target hit, stop hit, expired, or invalidated.

### Levels
- F5. Daily, weekly, and monthly floor pivots, previous day high and low, and the Fibonacci Pivot ladder are computed at each forex day roll (17:00 New York) and shown per pair.

### Stocks
- F6. After each US market close, the worker loads the full-market daily bars, computes the qualification rules and the five-line bar, and stores the results.
- F7. Owners can enter stock holdings (ticker, purchase price, date, expected profit). The portal computes sales target, total earnings, daily target, and weekly target, and alerts when the sales target is reached.

### Brokers
- F8. Admins create broker profiles with a name, platform link template, and typical spread per instrument.
- F9. Each owner chooses an active broker. Signal detail shows reference prices and broker-adjusted prices.

### Instruments
- F10. Admins add, pause, or remove instruments. Each instrument stores its pip size and per-instrument parameter overrides.

### Rules
- F11. Admins view every rule, its plain-language description, parameters, status (approved or provisional), and version history.
- F12. Admins edit parameters or approve a provisional rule. Each change creates a new version. Past signals keep the version that produced them.

### Notifications
- F13. Owners choose channels (web push, email, Telegram), which strategies and instruments alert them, and quiet hours.
- F14. Alerts deliver within 90 seconds of the triggering bar close.

### Econ events
- F15. Admins add upcoming economic releases (time, currency, title, impact). The 3/8 econ rules use these entries.

### History and performance
- F16. A history view lists every signal with outcome, filterable by strategy, instrument, direction, outcome, and rule version.
- F17. Summary metrics: count, win rate, average reward-to-risk achieved, net pips, by strategy and rule version.

### Health
- F18. A health view shows worker heartbeat, last completed bar per instrument, last stock scan, data source status, and recent job failures.
- F19. Jana and admins receive an alert if the worker heartbeat is older than 5 minutes or bars are stale for 30 minutes while the market is open.

## Non-goals

- Placing, modifying, or closing trades at any broker
- Storing broker login credentials
- Outside subscribers, public pages, sharing links, or published performance
- Native iOS or Android apps (the portal is an installable web app)
- Real-time tick charts; the portal works on completed bars
- Automated econ calendar feed in the first release (manual entry with an adapter slot for later)

## Acceptance criteria for launch

1. All three strategies pass their unit and fixture tests (see `17-testing-and-qa.md`).
2. Backtest reports exist for the 3/8 Formula and Fibonacci Pivot on all seven pairs, and the owners have reviewed them.
3. The worker has run on staging for 10 consecutive trading days with no missed bars and no unhandled errors.
4. A test signal reaches each owner on every channel they enabled within 90 seconds.
5. Every rule is visible in Settings with the correct status.
6. The paper run plan is agreed: 4 to 8 weeks of alerts with no money at risk.

## Success measures after launch

- Zero missed bar evaluations per week
- Median alert latency under 60 seconds
- Owners can explain any signal from its detail page without asking Jana
- After the paper run, a clear evidence base for approving or changing each provisional rule
