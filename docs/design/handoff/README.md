# Handoff: Trading desk, design system and round-one screens

## Overview
A private trading desk for a small group of business owners. It watches FX pairs and US stocks against the owners' own written systems (the "3/8 system" and "Fib Pivot") and alerts them, with reasons, when a setup appears. Owners use it on mobile when an alert arrives and on desktop for history and rule tuning. Nobody outside the owners will see it, so it's a working tool, not a marketing site.

**Primary job:** within 5 seconds of opening an alert, the owner knows the direction, instrument, entry, stop, target and why the system flagged it.

The full product brief, covering all 12 screens, states and the accessibility floor, is in `reference/13-screens-and-design-brief.md`. Treat it as the functional spec. This README is the visual spec.

## About the design files
The files in `reference/` are **design references built in HTML**. They show the intended look and behaviour; they are not production code. Recreate them in the target codebase using its own framework and patterns. If no codebase exists yet, a good fit is React + TypeScript with CSS variables from `tokens.css`, served as a PWA, because the brief includes iOS add-to-Home-Screen and push notifications.

To view the references, open `reference/Trading Desk.dc.html` in a browser; it needs `support.js` and `doc-page.js` in the same folder. Each option on the board has an ID badge (1a–1j) for cross-referencing.

## Fidelity
**High fidelity.** Colours, type, spacing and copy are final for round one. Recreate the screens exactly, using `tokens.css` and `IndicatorRing.tsx`.

---

## 1. Design principles (do not violate)
1. **Ruled, not carded.** Separate blocks with 1px hairline rules and whitespace, like a worked course page. Don't use box shadows, rounded tiles or card grids.
2. **The ring carries the boldness.** The 3/8 indicator ring is the only expressive element. Everything else stays graphite and quiet.
3. **Blue and amber, never red and green.** Show direction with all three of: colour, an arrow (▲ / ▼) and the word ("Long" / "Short").
4. **Figures you can trust.** Set every number in tabular figures, right-aligned and aligned on the decimal.
5. **Sentence case everywhere.** No all-caps, no monospace labels, and no block labels that repeat the obvious.
6. **No decoration.** No gradients, scrolling tickers, stock photos or emoji.
7. **Toasts echo the action name:** "Version saved", "Rule approved", "Test notification sent".

## 2. Design tokens
All tokens are in **`tokens.css`**, as CSS variables with light and dark themes. The theme follows `prefers-color-scheme`, and `[data-theme]` on `<html>` overrides it (manual switch in Settings > Profile).

### Colour
| Token | Light | Dark | Use |
|---|---|---|---|
| `--bg` (Ledger) | #F6F7F5 | #23282E | App surface |
| `--bg-page` | #E9EBE8 | #1B1F24 | Desktop canvas behind content |
| `--bg-input` | #FFFFFF | #2F353C | Text inputs |
| `--bg-selected` | #E6E9EB | #2F353C | Selected list row |
| `--ink` (Graphite) | #23282E | #F6F7F5 | Primary text, primary buttons, active nav |
| `--ink-2` | #3A4148 | #C9CED3 | Body / secondary text |
| `--mute` | #5A626B | #A9B0B7 | Labels, meta, inactive tabs |
| `--faint` | #8C949C | #6B737B | Inactive numerals, chart reference lines (not for body text) |
| `--rule` | #C9CED3 | #4A525A | Block dividers, control borders, unfired ring segments |
| `--rule-soft` | #DDE1E4 | #3A4148 | Row dividers inside lists |
| `--rule-faint` | #E2E5E8 | #3A4148 | Toggle row dividers, progress track |
| `--long` | #2563C9 | #7FA6EE | Long: fills and text |
| `--short` | #C27A00 | #E0A341 | Short: **fills only** in light theme (3.0:1) |
| `--short-ink` | #975C00 | #E0A341 | Short: **text** (5.1:1 on Ledger) |
| `--prov` | #6E56CF | #A898F0 | Provisional, always as a dashed outline |
| `--error` | #8A2E2E | — | Field error border and message |
| `--health-ok` | #2E8B57 | #4FC08D | Health dot (amber and red use `--short` / `--error`) |
| `--warn-bg / -border / -ink` | #FBF1DF / #E6CFA3 / #5C3A00 | — | Stale-data banner |
| `--link / --link-hover` | #2563C9 / #1B4A99 | #7FA6EE / #A9C3F4 | Links |

### Typography
- **IBM Plex Sans** (400/500/600) everywhere, with `font-variant-numeric: tabular-nums` set globally.
- **IBM Plex Sans Condensed** for dense desktop tables (History, Stocks) and chart labels.

| Role | Size / weight | Notes |
|---|---|---|
| Signal page instrument | 28 / 600, letter-spacing −0.01em | e.g. "EUR/USD" |
| Screen title (mobile) | 22 / 600 | "Signals" |
| Dialog title | 18 / 600 | |
| List row instrument | 17 / 600 | |
| Prominent figure | 15–17 / 500–600 | Prices in rows, goal count |
| Body / control | 14–15 / 400–500 | Buttons 13–15 / 500–600 |
| Meta / labels | 13 / 400, `--mute` | |
| Small labels, badges | 12 / 400 | Column labels above prices, badges |
| Chart labels | 9.5 Condensed | |

Line-height is 1.45–1.5 for prose and 1.1 for titles. Use `text-wrap: pretty` on paragraphs.

### Spacing and shape
- Mobile horizontal padding is **20px**. List rows use padding `14px 20px`. Header blocks use `6px 20px 14px`.
- Gaps follow a 4/6/8/10/12/16/20/22/28 rhythm.
- Radii: **4px** controls, **3px** badges, **6px** dialogs. Nothing else is rounded. (The 28px corners on the mocks are the phone frame, not UI.)
- Borders are always 1px, except focused inputs and error inputs, which use 1.5px.
- **Shadows: none.** Dialogs use a 1px `--ink` border instead.
- Touch targets are at least 44px tall. Small inline buttons such as "Switch" are 32px tall and need 44px hit areas.

## 3. Components

### Indicator ring (signature) → `IndicatorRing.tsx`
- Eight annular segments in a 100×100 viewBox: outer radius 47, inner 30, 4.5° gap between segments. The hairline variant uses inner radius 39 and a 3° gap; it's an alternative to show the client, but `segments` is the default.
- Order is fixed and runs clockwise from 12 o'clock: Candlestick, New high/low failure, Pivots, Flags/pennants/triangles, Trendlines and channels, Previous day high, Previous day low, Fibonacci.
- Segment states:
  - **Fired:** filled and stroked in the direction colour.
  - **Not fired:** `--rule` outline only.
  - **Provisional:** direction-colour fill at 28% opacity, with a `--prov` dashed stroke (`4 3` large, `2 1.5` small).
- Centre label: at 80px and above, the count (24/600) plus "of 8" (10, `--mute`). Below 80px, the count only (34 units/600).
- Sizes: 120 on overview, 112 on Signal detail, 72 on the empty state (no label, all outlines), 40 in list rows, and 52 / 28 / 24 as the app icon and nav mark. The icon uses alternating fired segments, long colour, no label, on a Ledger or #2F353C tile with radius 18 at 76px.
- Accessibility: `aria-label="N of 8 indicators fired"`.

### Ladder mark (Fib Pivot list marker)
40×40. Five horizontal lines 24px wide, with the middle line in `--ink` at 1.5px and the others in `--rule`, plus a 4px-radius dot in the direction colour at the price position. It replaces the ring in rows for Fib Pivot signals.

### Direction marker
`▲ Long` / `▼ Short`, 14/600 in rows and 17/600 on the signal header. Use `--long` for long and `--short-ink` for short. Screen readers should hear "Long, entry 1.0843".

### Badges (12px, padding 1px 6px, radius 3px, no fill)
- **Provisional:** `--prov` text and a 1px **dashed** `--prov` border.
- **Confluence:** "◆ Both systems agree", `--ink` text and a 1px solid `--ink` border.
- **State chip** (Confirmed, Open…): `--ink` text and a 1px solid `--ink` border.

### Price cell / price row
Show the label (12, `--mute`) above the value (15, `--ink`), right-aligned. In list rows, a 4-column grid shows Entry (500) | Stop | Target | R:R.

### Trade plan block (Signal detail)
A grid of `1fr auto auto` with a 22px column gap and 15px text. Columns: label | Reference | Broker A (adjusted). The Entry row is 600 weight. Below the grid, show risk/reward in pips and R:R, then a full-width primary button: "Open in Broker A".

### Buttons
- **Primary:** `--ink` background, `--bg` text, no border, radius 4, height 44–48, 14–15/500–600.
- **Secondary:** transparent, 1px `--rule` border, `--ink` text, same sizes.
- **Inline small** ("Switch"): height 32, padding 0 12, 13/500.

### Inputs
Height 48, background `--bg-input`, 1px `--rule` border (1.5px `--ink` when focused), radius 4, padding 0 14, 16px text so iOS doesn't zoom. The label sits above at 14 `--ink-2` with an 8px gap.
- **Error:** 1.5px `--error` border, with the message below in 13 `--error`.
- **Parameter editor row (Rules):** name | value input with unit suffix | "Allowed 2 to 5" in `--mute`.

### Toggle
A track filled with `--ink` when on and `--rule` when off; the thumb moves right or left. Rows are separated by `--rule-faint` with a title (14) and an optional sub-line (13 `--mute`).

### Chips (pair switcher, instrument filter)
1px border, radius 4, height ≥ 32 with a 44px hit area.
- **Selected pair:** `--ink` fill, `--bg` text.
- **Unselected:** `--rule` border.
- **Instrument filter on:** "✓ EUR/USD" with an `--ink` border.

### Stale-data banner
Full width, `--warn-bg` background, 1px `--warn-border` bottom border, padding 12px 20px, 13px `--warn-ink`. Copy: "Prices for GBP/USD haven't updated for 30 minutes. Alerts for this pair are paused until data resumes."

### Health dot
An 8px circle followed by a "Health" link in `--mute`. Green `--health-ok`, amber `--short`, red `--error`.

### Daily goal bar
An 8px track in `--rule-faint` with a fill in `--ink` (percentage of the 75-pip maximum). A target bracket marks 60–75 pips (left 66.7%, width 16.7%) with 1px `--ink` borders extending 3px above and below. The label row reads "Today's goal" on the left and "**41** of 60–75 pips" on the right, with the source line "From 2 closed 3/8 signals" underneath.

### Navigation
- **Mobile:** a bottom bar of 5 tabs (Signals, Levels, Stocks, History, Settings), 64px tall plus the safe area, 12px labels. The active tab has an 18×2px `--ink` bar above an `--ink` 600 label; inactive tabs are `--mute`.
- **Desktop:** a 200px left nav with a 1px right `--rule` border, the ring mark plus "Trading desk" at the top, and items Signals, Levels, Stocks, Holdings, History, Econ events, Health, Settings. The active item has a 2px `--ink` left bar and is 600 weight.

### Dialog
Width 440, `--bg` background, 1px `--ink` border, radius 6, padding 26px 28px, no shadow. Title 18/600, body 14 `--ink-2`, buttons right-aligned (secondary, then primary).

### Tables (desktop)
Plex Condensed, a sticky header (12px `--mute`) and `--rule-soft` row dividers. Number columns are right-aligned. There are no zebra stripes or cell backgrounds.

### Charts
- **15-min candles:** 1px `--ink` wicks. Up bodies are hollow (`--bg` fill with an `--ink` stroke); down bodies are solid `--ink`. Level lines run full width with labels on the right in Condensed 9.5:
  - Entry: `--ink` solid 1.5
  - Stop: `--ink` dashed `4 2`
  - Target: `--long` solid 1.5
  - Pivots and S/R: `--faint` dashed `3 3`
  - PDH/PDL: dotted `1 3`
  - Fib: dashed `6 3`
  
  The trigger bar gets a small direction-colour triangle below it.
- **Cumulative pips (History):** a 1.5px `--ink` polyline with a `--rule` zero line. No fill.

## 4. Screens (round one)
Reference IDs refer to `reference/Trading Desk.dc.html`. Mobile frames are 390×844, with a 44px status bar.

- **1g Sign in:** the app mark plus "Trading desk". Email input, then a primary button: "Email me a sign-in link".
  - Confirmation: "Check your email for a sign-in link."
  - Error: "This email isn't approved. Ask an admin to add it."
- **1b / 1c Dashboard (mobile, light/dark):**
  - Header block: "Signals" with the Health dot on the right, then a status line ("Forex open · New York session · In 3/8 window until 11:00 · 09:42 NY"), then "Broker **Broker A**" with a Switch button.
  - Optional stale banner.
  - Signal rows, newest first. Each row has a direction marker, the instrument, "Strategy · State · Age", badges, the ring or ladder on the right, and a 4-column price grid.
  - Daily goal, then "**7** stocks newly confirmed after Tuesday's session" with a "Stocks" link. Bottom tabs.
  - Empty state: a 72px empty ring and "No open signals. The scanner checks every 15 minutes while the market is open."
- **1d Signal detail (mobile, one scroll):**
  1. "‹ Signals" back link.
  2. Header: direction and instrument at 28, then "3/8 system", a Confirmed chip and "Created 09:30 NY · 12 min ago".
  3. Trade plan block.
  4. Why: the 112px ring, then 8 indicator rows (number, name, status, detail, with the provisional note "Provisional: this definition is waiting for owner approval."), the gates passed with values, and the explanation sentence.
  5. Chart.
  6. Timeline: Created, Confirmed, Reset reached, Closed, with filled or hollow dots, prices and times.
  7. Admin only: "Mark invalid" and "Add note".
- **1e Levels (mobile):** a pair switcher row of chips. A floor pivots table (R3…S3 × Daily/Weekly/Monthly, with the P row in 600), then PDH/PDL, then the Fib Pivot ladder: R4…S4, with P drawn as an `--ink` line, the other levels as `--rule` lines, and a "now" price marker between levels.
- **1f Settings › Notifications (mobile):**
  - "Notifications blocked by the browser" warning with the next step.
  - Channels: "Turn on notifications", "Connect Telegram", and email shown as always on.
  - Strategy toggles, instrument chips and quiet hours.
  - "Send test notification" button.
- **1h History (desktop 1280):**
  - Left nav.
  - Filter bar: Dates, Strategy, Instrument, Direction, Outcome, Provisional.
  - Metrics row: Trades 64 · Win rate 58% · Net +412 pips · Expectancy +6.4 pips · Profit factor 1.82. Large numbers with small unit labels, separated by rules and not boxed.
  - Cumulative chart, then the condensed table. Export CSV.
- **1i Settings › Rules (desktop, admin):** a 3-column layout of nav | rule list grouped by strategy (name, version, provisional badge; selected row in `--bg-selected`) | editor. The editor shows the name, status badge, enabled toggle, description, source reference, parameter rows, per-pair overrides, version history with diffs, a performance panel, and the "Save new version" and "Approve rule" actions.
- **1j Approve-rule dialog:**
  - Title: "Approve Trendlines and channels v2?"
  - Body: "The provisional badge comes off this indicator. The scanner will use the change from the next bar, 09:45 NY."
  - Buttons: Cancel, Approve rule. Then the toast "Rule approved".

**Not designed yet (round two):** Stocks, Stock detail, Holdings, desktop Levels, Health, Econ events, Brokers/Instruments/Users, and the iOS install guide. Build them from the components above, following the brief.

## 5. States
| State | Treatment |
|---|---|
| Loading | Skeleton rows matching the signal row geometry, `--rule-faint` blocks, no shimmer under reduced motion |
| Empty | Empty ring (72px) plus one sentence of copy |
| Stale data | Warn banner below the header; alerts for that pair paused |
| Market closed | Status line reads "Forex closed" with the next open time; no window line |
| No broker | Broker slot reads "No broker selected" with "Choose" in place of Switch; the Broker column in the trade plan is hidden |
| Notifications blocked | Warn banner in Settings › Notifications with the browser steps |
| Error | Plain sentence plus a next step, `--error` only on the field or icon, never on whole blocks |

## 6. Accessibility floor
- WCAG AA in both themes. Amber text must use `--short-ink`.
- Visible `:focus-visible` outline (2px `--long`).
- Touch targets ≥ 44px. Respect `prefers-reduced-motion`.
- Never use colour alone: direction always comes with an arrow and the word, and provisional always uses a dash plus the word.
- Ring `aria-label`. Prices read as "Long, entry 1.0843".

## 7. Suggested build order
1. Wire up `tokens.css`, both fonts and the theme switching.
2. Primitives: Button, Input, Toggle, Chip, Badge, DirectionMarker, PriceCell, Rule (hairline divider).
3. `IndicatorRing` and `LadderMark`. Check them visually against reference 1a.
4. Dashboard → Signal detail → Levels → Notifications (mobile first).
5. History → Rules (desktop).
6. States and toasts across all screens.

## Files
- `tokens.css`: all design tokens (light/dark), base styles, focus and reduced motion.
- `IndicatorRing.tsx`: reference React implementation of the ring and ladder mark.
- `reference/Trading Desk.dc.html`: the round-one design board (IDs 1a–1j), the visual source of truth. Its logic class at the bottom holds the sample data and the chart geometry.
- `reference/Trading Desk Presentation.dc.html`: the 10-slide client deck explaining the rationale.
- `reference/13-screens-and-design-brief.md`: the functional spec for all screens.
- `reference/support.js`, `doc-page.js`, `deck-stage.js`: runtime needed to open the HTML references.
