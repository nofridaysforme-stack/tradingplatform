# Screens and Design Brief (for Claude Design)

## The product in one paragraph

A private trading desk for a few business owners. It watches currency pairs and US stocks around the clock using the owners' own written trading systems, and tells them, with reasons, when a trade setup appears. The owners check it on their phones the moment an alert arrives and on a laptop when reviewing history and adjusting rules. It is a working tool, not a marketing site. Nobody outside the owners will ever see it.

## Audience and primary job

- Audience: experienced owners who know trading vocabulary (pips, pivots, Fibonacci) and trust their own system.
- Primary job: within five seconds of opening an alert, the owner knows direction, instrument, entry, stop, target, and why the system thinks so.
- Secondary jobs: review how past signals turned out; tune rules; manage brokers, pairs, and notifications.

## Design direction

### Concept: the system on paper, made live

The owners' systems began as typewritten course pages worked with a desk calculator. The interface borrows that lineage without nostalgia: exact figures, ruled structure, nothing decorative, and one signature element that is unique to their method.

### The memorable element: the 3/8 indicator ring

Every 3/8 signal shows an eight-segment ring, one segment per indicator in the document's order (Candlestick, New high/low failure, Pivots, Flags/pennants/triangles, Trendlines/channels, Previous day high, Previous day low, Fibonacci). Fired segments fill in the signal's direction color; unfired segments stay as outlines; provisional segments use a dashed outline. The count sits in the center ("3 of 8"). The ring appears large on the signal page, small in lists, and as the app icon motif. Spend the design's boldness here; keep everything else quiet.

### Proposed tokens (Claude Design may refine; keep the intent)

| Token | Value | Use |
|---|---|---|
| Graphite | #23282E | Primary text (light theme), app background (dark theme) |
| Ledger | #F6F7F5 | Background (light theme), primary text (dark theme) |
| Rule grey | #C9CED3 | Dividers, outlines, unfired ring segments |
| Long cobalt | #2563C9 | Long direction |
| Short amber | #C27A00 | Short direction |
| Provisional violet | #6E56CF | Provisional badges and dashed outlines |

Long and short use blue and amber rather than green and red so they stay distinguishable for color-blind owners. Direction always appears as color plus an arrow icon plus the word.

Type: one family with true tabular figures for every price, such as IBM Plex Sans, with its condensed width for dense tables. Prices align on the decimal. Sentence case throughout. No all-caps labels.

Both light and dark themes, following the device setting with a manual switch in Settings.

### Avoid

- Identical rounded cards with soft shadows for every block
- Green/red-only direction cues
- Decorative gradients, tickers scrolling across the top, stock-photo charts
- Monospace for small data labels
- Labels above every block that repeat the obvious

## Screens

Mobile-first for Dashboard, Signal detail, Levels, and Settings > Notifications. Desktop layouts for History, Stocks, and Settings > Rules.

### 1. Sign in
Email field and "Email me a sign-in link". Confirmation state: "Check your email for a sign-in link." Error for addresses not on the allowlist: "This email isn't approved. Ask an admin to add it."

### 2. Dashboard
- Top strip: forex market status (open or closed, current session, inside or outside the 3/8 trading window, New York time), active broker name with a switch control.
- Live signals: open and confirmed signals, newest first. Each row: direction marker, instrument, strategy, small indicator ring (3/8) or ladder marker (Fib Pivot), entry, stop, target, reward-to-risk, time since signal, provisional badge if any, confluence marker if both systems agree.
- Today's daily goal: pips from closed 3/8 signals today versus the 60 to 75 pip target.
- Stock digest preview: count of newly confirmed stocks from last session, link to Stocks.
- Health dot: green, amber, red with a link to Health.
- Empty state: "No open signals. The scanner checks every 15 minutes while the market is open."

### 3. Signal detail
- Header: direction, instrument, strategy, state, time.
- Trade plan block: entry, stop, target, alternative target if present, risk and reward in pips, reward-to-risk. Two columns: reference prices and the active broker's adjusted prices. "Open in Broker A" button.
- Why: the large indicator ring, then a list of all eight indicators with fired or not, level references and values, provisional badges with a one-line explanation ("Provisional: this definition is waiting for owner approval."). Gates passed with values. The template-built explanation sentence.
- Chart: 15-minute candles for the session with entry, stop, target, and the pivot and Fib levels drawn as labeled horizontal lines; the triggering bar marked.
- Timeline: created, confirmed, reset reached, closed, with prices and times.
- Outcome when closed: result in pips, reference and broker-net.
- Admin only: "Mark invalid" with reason, "Add note".

### 4. Levels
Per pair (pair switcher at top): daily, weekly, monthly floor pivots; PDH and PDL; the Fibonacci Pivot ladder with the range, chosen Fibonacci number, and all eight levels around the pivot; current price position on the ladder. Mobile: one pair at a time. Desktop: a grid of all pairs.

### 5. Stocks
- Table of the last session's results: ticker, status (qualified, trend established, trend confirmed), close, 52-week high and low, APR, five-line values (5, 10, 20, 50 day ACC and APR), consistency flag. Filters by status; sortable columns; search.
- Session picker for past sessions.

### 6. Stock detail
Daily chart (6 months), the five-line bar drawn as a compact visual of the 5, 10, 20, 50 day closes against today, qualification checks with values, history of status changes, "Add to holdings".

### 7. Holdings
Per owner: ticker, purchase price, date, expected profit, sales target, total earnings, daily target, weekly target, last close, progress bar toward target, sessions elapsed of 20. Add, edit, close a holding.

### 8. History
Filterable table of all signals: date, strategy, instrument, direction, outcome, result pips, reward-to-risk, rule versions, provisional flag. Summary metrics above the table for the current filter: trades, win rate, net pips, expectancy, profit factor. A small cumulative pips chart. Export CSV.

### 9. Econ events (admin edit, owners view)
Upcoming and recent events: time (New York), currency, title, impact. "Add event" form.

### 10. Settings
- Profile: name, timezone, theme.
- Brokers: list of profiles; active broker selection per owner; admin edit form with name, platform link template, and a spread per instrument table.
- Instruments (admin): list with enabled toggle, pip size, sort order; "Add pair" form with pip size pre-filled.
- Notifications: channels (Turn on notifications, Connect Telegram, email shown as always on), strategies, instruments, quiet hours, include updates, "Send test notification".
- Rules (admin): grouped by strategy. Each rule shows name, status badge, enabled toggle, plain-language description, source reference, parameters with units and allowed ranges, per-pair overrides, version history with diffs, and a performance panel (signals using this rule and their outcomes). Actions: "Save new version", "Approve rule". Confirmation dialog states that the scanner will use the change from the next bar.
- Users (admin): allowlist, roles, deactivate.

### 11. Health
Worker heartbeat age, last completed bar per pair, last day roll, last stock scan, provider status, recent job runs with failures expanded, notification delivery stats for the last 24 hours.

### 12. Install guide (modal)
Shown on iPhone Safari when not installed: three steps to add to Home Screen, then "Turn on notifications" once installed.

## Component inventory

Direction marker; indicator ring (large, small, icon); provisional badge; confluence marker; state chip; price cell with tabular alignment and pip distance; trade plan block with reference and broker columns; level ladder; five-line bar visual; health dot; filter bar; data table with sticky header; parameter editor rows (number with unit, toggle, enum select); version diff view; empty states; toasts that echo action names ("Version saved", "Rule approved", "Test notification sent").

## States to design

Loading (skeleton rows), empty, error with a next step, market closed, stale data warning banner ("Prices for GBP/USD haven't updated for 30 minutes. Alerts for this pair are paused until data resumes."), no broker selected, notifications blocked by the browser, iOS not installed.

## Accessibility floor

WCAG AA contrast in both themes, visible keyboard focus, touch targets at least 44 px, reduced-motion respected, no information carried by color alone, prices readable by screen readers with direction spoken ("Long, entry 1.0843").
