# Design

| File | Contents | Status |
|---|---|---|
| `handoff/` | Claude Design handoff for building the portal: `README.md` (rules and component notes), `tokens.css` (colors, type, spacing for light and dark), `IndicatorRing.tsx` (ring geometry), and the reference boards in `reference/` | Followed by the portal build (Phase 5) |
| `trading-desk-design-round-one.pdf` | Round one from Claude Design (October 2026): indicator ring, dashboard, signal detail, levels, notifications, sign-in, rule approval, history, rules | Waiting for the owners' review (Phase 3 gate) |

Round two (per page 10 of round one): stocks, stock detail and holdings; levels on desktop; health and economic events; brokers, instruments, users, and the install guide.

## Round one against the specs

The design follows the brief (spec 13): the ring keeps the document order of the eight indicators with dashed violet for provisional rules, long and short are blue and amber with an arrow and the word, and prices use tabular figures. The specs decide behavior and content (CLAUDE.md). Differences to resolve in round two:

| Page | Design shows | Specs say |
|---|---|---|
| 6 | Fibonacci Pivot ladder labelled R1 to R4 and S1 to S4, "Range 94 pips, Fib 0.618" | Spec 07: Pivot (prior close) with Break, Confirmation, Take Profit, and Reset above and below, at the closest Fibonacci number to the range and the next three (for example 55, 89, 144, 233 pips) |
| 5, 9 | A spread gate ("Spread within limit", "Spread gate") | No spread gate in spec 06; spreads are applied per broker for display (spec 10) |
| 9 | Fib Pivot rules "Range lookback", "Fibonacci number", "Entry touch tolerance" | Spec 07 rules: unit, levels, entry, confirmation, stop, target, reset, one per side, window, expiry, confluence |
| 9 | Trendlines and channels parameters "Lookback 48 bars", "Maximum slope 0.8 pips per bar" | Seeded parameters: minimum touches, touch tolerance, parallel tolerance, maximum line age |
| 5 | 3/8 window 08:00 to 11:00 | Primary 00:00 to 10:30, alternative 05:00 to 14:00 New York |
| 4, 6, 8 | EUR/GBP, GBP/JPY | Launch pairs are the seven USD majors (owners can add more) |

Sample figures in the mock-ups (prices, rule version numbers, results) are placeholders; the portal shows live data.

## How the portal follows the handoff

The portal uses the handoff tokens, type, and ring geometry as given (`apps/web/app/globals.css`, `apps/web/components/ring.tsx`). Where the handoff and the specs differ, the portal keeps the handoff's look and the specs' content:

- Levels: the Fibonacci Pivot ladder uses the handoff's layout, with spec 07's labels (Break, Confirmation, Take Profit, Reset) in place of R1 to R4 and S1 to S4.
- No spread gate is shown; spreads appear per broker (spec 10).
- Rule pages show the seeded rules and parameters, not the sample ones in the boards.
- Provisional badge text uses `--prov-ink` (#5B44B8) in the light theme: the handoff's `--prov` measures 4.42:1 on `--bg-selected`, below AA. This follows the handoff's own `--short` / `--short-ink` split.
- Settings › Rules adds a strategy switch and pair choice at the top of each strategy group (the `strategy_configs` decision of 2026-10-01).
