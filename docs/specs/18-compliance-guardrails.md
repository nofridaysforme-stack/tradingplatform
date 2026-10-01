# Compliance Guardrails

This is research and project guidance, not legal advice. If the use described here changes, involve an attorney.

## The boundary: owners' own trading only

The portal is built for the business owners to use for their own trading. Under that use:

- **No commodity trading advisor registration is triggered.** A commodity trading advisor is someone who, for compensation, advises others about trading. The owners are not advising anyone.
- **No hypothetical-performance disclaimer obligation applies** to internal backtest reports, because those rules govern presenting results to others. Reports stay internal anyway.
- **OANDA's API license fits.** The license limits use of the OANDA system and rates to the licensee's own internal use and prohibits disclosing the rates to third parties. The OANDA account must be in the business's name (or an owner's), and only the owners may have portal access.
- **Massive's free plan fits** personal, non-redistributed use.

## What would break the boundary

Any of these reopens regulatory and licensing questions and requires a review before it happens:

1. Sharing alerts, screenshots of signals, or levels with anyone outside the owners
2. Charging anyone for access, or adding users who are not owners
3. Publishing backtest or live performance (website, social media, pitch decks)
4. Adding automated order placement for anyone other than the owners' own accounts
5. Offering the portal as a product

If the owners ever want any of these, the starting points are: CFTC Rule 4.14(a)(9) (an exemption for standardized, non-tailored advice that does not direct client accounts), CFTC Rule 4.41 (required cautionary statement for simulated or hypothetical performance, enforced even against unregistered advisors), the Investment Advisers Act publisher exclusion as interpreted in Lowe v. SEC (impersonal, bona fide publications of general and regular circulation) for stock content, and redistribution licenses from data vendors.

## Product guardrails built into the code

| Guardrail | Where |
|---|---|
| No public sign-up; allowlist only | `15-auth-and-security.md` |
| No public pages showing signals or performance; `noindex` on all pages | `15-auth-and-security.md` |
| No share links or export of signals outside CSV for signed-in users | `14-api-contracts.md` |
| No order placement or broker credentials | `01-CLAUDE.md` rule 7 |
| Data keys never sent to the browser | `15-auth-and-security.md` |

## In-portal notice

Shown once at first sign-in and available in Settings:

> This portal applies your own trading rules to market data and suggests possible trades. It does not place trades, and it does not guarantee results. Every trading decision is yours. Past or simulated results do not predict future results. Do not share alerts or access outside the owners.

The owner must select "I understand" to continue. The acknowledgment time is stored in `users.acknowledged_notice_at`.

## Build contract notes (for Jana and the client)

Include in the development agreement:

- Scope: the spec set by reference, with the provisional-rule approach described
- No guarantee of trading results; the client makes all trading decisions
- Accounts (OANDA, Massive, Railway, Resend, domain, Telegram bot) are opened in the client's name and paid by the client
- Code ownership transfers on final payment; Jana keeps the right to reuse non-client-specific components and general know-how, excluding the client's trading rules
- Limitation of liability capped at fees paid; no liability for trading losses, data provider outages, or missed alerts
- Confidentiality of the client's trading materials
- The personal-use boundary above, acknowledged by the client
- Support retainer terms: response times, included hours, what counts as a change request
