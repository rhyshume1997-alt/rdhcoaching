# S5 — Supply and demand zones (his own definition), plus range/Monday-range mechanics and the 50% invalidation rule
Source: transcripts/S5.md  |  Runtime covered: 00:00:02 to 01:43:55

## 1. Scope
The first ~28 minutes are Q&A carry-over: inverse head-and-shoulders validity, trend-line touch counting, swing failure patterns (SFPs), the "Monday range," and how to trade inside a range (range lows / mid-range / range highs, touch counting, partial TPs). The main lesson is his personal definition of supply and demand zones, which he explicitly contrasts with the textbook definition: price must impulse first, then consolidate horizontally, then break out with a "sufficient gap in price action" sized to the timeframe. He then specifies how to ladder entries/DCAs into the zone, where stops and TPs go, and the hard invalidation rule that a zone dies once price fills 50% of it.

## 2. Definitions

**Demand zone (textbook)** — price comes down, consolidates, then goes up; that consolidation area is the demand zone; price coming back into it usually bounces. `[00:32:06]`

**Demand zone (HIS definition — deliberately different)** — price must first go UP, then consolidate horizontally (a range / bull flag / symmetrical triangle), then break out with a sufficient gap in price action. The consolidation is the zone. `[00:34:22]` `[00:34:55]` — he flags this as "my own method... different than what you will see in the books" `[00:28:02]`.

**Supply zone (textbook)** — price goes up, consolidates up there, comes back down; that consolidation is the supply zone. `[01:13:26]`

**Supply zone (HIS definition)** — "basically what a demand zone is but inverted": price comes DOWN into a horizontal consolidation, then breaks down with a sufficient gap in price action. `[01:14:00]`

**Sufficient gap in price action** — the move away from the consolidation zone; it must be "wide enough in correlation with a timeframe." Higher timeframes require a bigger move away, otherwise the zone will not be a strong bounce point. `[00:35:30]` `[00:36:05]`

**Order block (bullish)** — the last RED candle before a directional change in price (i.e. before an impulse up). `[00:32:40]` `[01:08:52]`

**Order block (bearish)** — the last GREEN candle before a directional change in price. `[00:33:12]` `[01:11:37]`

**Order blocks vs zones** — order blocks are "a form of supply and demand zone"; an order block is usually found inside a demand zone, and he says he plays order blocks and supply/demand zones differently. `[00:33:12]` `[00:34:22]` `[00:54:43]`

**Half candle** — a candle whose body opens (or closes) inside the zone but closes (or opens) outside it. Two half candles count as one full candle. `[00:47:48]` `[00:49:30]`

**SR point** — a level that was resistance, was broken and flipped to support (or vice versa); the flip level. Used as the FIRST/lightest entry of a zone ladder. `[00:37:11]` `[00:58:40]`

**Swing failure pattern (SFP)** — a candle wicks through a swing high (or low), takes the liquidity, and closes back inside the prior range. `[00:09:24]` `[00:10:00]` — NOTE ASR/misspeak: at `[00:10:00]` he calls liquidity taken above a swing high "sellside liquidity"; conventionally that is buyside liquidity. Treat the direction (above the high) as authoritative, not the label.

**Monday range** — Monday's daily high and Monday's daily low, marked as a box, then traded on a lower timeframe. `[00:13:22]` `[00:13:57]`

**Mid-range** — the midpoint level of a range; a tradeable level in its own right, weakening with each touch. `[00:16:46]` `[00:21:13]`

**Technical TP** — the measured/final target of a chart pattern (e.g. bull flag pole projection). He uses the phrase to say he does NOT trade to those targets. `[00:07:47]`

**50% fill / 50% line** — the midpoint of a supply or demand zone. Once price trades through it, the bids/liquidity that made the zone are considered consumed. `[00:38:52]` `[00:44:26]`

## 3. Hard rules

**S5-R1** — A trend line is valid only once it has three touches; three touches makes it valid regardless of cleanliness.
params: touches >= 3
`[00:06:41]` `[00:07:14]`

**S5-R2** — Do not take the same trade at a support or resistance level after its third touch; levels weaken with each touch. Wait for the flip (breakout + retest) instead.
params: max touches traded = 3
`[00:24:35]` `[00:26:16]`
CONTRADICTION FLAG: see S5-C3 — the demand-zone replay rule (S5-R25) permits repeated trades of the same zone well past three touches (he counts seven bounces on the BTC demand zone at `[00:46:40]`).

**S5-R3** — Do not enter on a breakout candle. Require breakout candle close beyond the level, then a retest candle that closes back on the correct side ("breakout, retest and hold"); enter as soon as the candle AFTER the successful retest opens.
params: 1 breakout close + 1 retest close
`[00:05:34]` `[00:26:16]` `[00:26:50]`

**S5-R4** — SFP short: if a candle wicks above a swing high and closes back below it, open a short with the stop above the wick and TPs at levels of support.
params: stop = above sweep wick
`[00:10:00]`

**S5-R5** — SFP long: if a candle wicks below a swing low and closes back above it, long with the stop below the wick.
params: stop = below sweep wick
`[00:11:06]`

**S5-R6** — If the SFP entry is missed on the close, place a limit order at the previous swing high (short) / swing low (long) with the same stop above/below the wick; this gives tighter risk.
params: limit = prior swing point; same stop
`[00:10:00]` `[00:11:06]`

**S5-R7** — Do not market-enter an SFP if the reversal candle already closed far from the swept level ("already had a huge move"); use the limit at the swing point instead.
params: none stated (see S5-A3)
`[00:10:32]`

**S5-R8** — Mark Monday's daily high and Monday's daily low as the Monday range; the crypto daily candle opens at 5:00 pm (his exchange/local time).
params: daily open 17:00
`[00:13:22]` `[00:13:57]`

**S5-R9** — Trade the Monday range only on a lower timeframe — the 1 hour or the 30 minute.
params: 1h, 30m
`[00:14:30]` `[00:15:38]`

**S5-R10** — Inside a range: long only at range lows, short only at range highs. Never short at range lows.
params: n/a
`[00:20:36]` `[00:21:13]`

**S5-R11** — Shorts at mid-range are permitted ONLY when price is currently at mid-range, targeting range lows.
params: n/a
`[00:21:13]` `[00:21:47]`

**S5-R12** — When shorting mid-range on a low timeframe, take the stop-loss level from a HIGHER timeframe, placed above the wicks with leeway; a stop placed only a fraction away (his example: $0.60) gives no room for error.
params: example stop distance rejected = $0.60
`[00:22:21]`

**S5-R13** — Do not take a long at mid-range if there is no support level between entry and the range low to anchor the stop; in that case the risk-to-reward is not there and the trade is skipped.
params: n/a
`[00:23:27]` `[00:24:00]`

**S5-R14** — Take no trade while price is consolidating at mid-range (it can resolve either way); wait for the higher risk-to-reward levels (range low / range high).
params: n/a
`[00:25:08]`

**S5-R15** — A valid HIS-definition demand zone requires, in order: (1) an up-impulse into the zone, (2) horizontal consolidation, (3) a breakout, (4) a sufficient gap in price action away from the zone. The consolidation must be horizontal — a downward-drifting consolidation does not qualify.
params: 4 ordered conditions
`[00:34:22]` `[00:47:14]` `[01:29:19]`

**S5-R16** — Sufficient-gap thresholds by timeframe (move away from the breakout point):
params: 15m/1h: 3–5% acceptable, 8% on 1h = "perfect", 5% on 1h fine; 30m: 4% sufficient, "around 3 to 5%"; daily: at least 8–12%, a 3–4% move on the daily is NOT strong; 2-day: 13% is good
`[00:35:30]` `[00:36:05]` `[00:36:38]` `[00:54:07]` `[00:55:17]` `[01:17:59]`

**S5-R17** — A zone must contain at least two FULL candle bodies. Two half candles count as one full candle. One-and-a-half candles is not valid. Only candle bodies count, not wicks.
params: min full bodies = 2
`[00:47:48]` `[00:48:22]` `[00:54:43]`

**S5-R18** — The longer the consolidation (measured in candles/candle bodies), the stronger the zone.
params: monotonic in candle count
`[00:47:14]` `[00:47:48]`

**S5-R19** — Exclude a giant wick from the zone box; a candle that wicks above the zone and closes back below does not count toward the zone. Small wicks close to the candle bodies may be included.
params: n/a (see S5-A7)
`[01:05:00]` `[01:17:59]` `[01:30:30]`

**S5-R20** — Entry ladder for a demand zone: first and LIGHTEST entry at the SR point (top of the zone); optional intermediate DCA(s) found by dropping to a lower timeframe; final and HEAVIEST DCA at support (bottom of the zone). "Heavier bids always at the top [supply] or at the bottom if you're longing."
params: entry weight ordering light -> heavy, top -> bottom for longs
`[00:37:11]` `[00:37:46]` `[00:52:27]` `[01:34:03]`

**S5-R21** — Entry ladder for a supply zone: SR point entry is the least size, final/heaviest DCA at the TOP of the box ("I always go for the top"); average fills mid-zone.
params: heaviest at top of box
`[01:14:32]` `[01:15:06]` `[01:31:45]`

**S5-R22** — Number of DCAs is set by zone width: a small/tight zone gets one DCA, a wider zone gets two.
params: examples — zone $1.50 from stop = 1 DCA; zone ~$9 wide = 1 DCA; zone ~$2 = 1 DCA + tight stop
`[00:37:11]` `[00:49:30]` `[01:14:32]` `[01:24:41]`

**S5-R23** — Place entry prices at wicks, at the "points of most touch," not at bodies — but bodies are acceptable where a consolidation cluster exists.
params: n/a
`[01:05:00]` `[01:05:33]`

**S5-R24** — Stop for a demand-zone long goes below the support line / below the wick at the bottom of the zone; for a supply-zone short, above the wick at the top. If that stop is wide, reduce position size rather than tightening it.
params: n/a
`[00:37:46]` `[00:51:21]` `[01:19:10]` `[01:33:29]`

**S5-R25** — Do not place the stop above a separate, distinct resistance level — that level is its own trade; drop to a lower timeframe to find a stop just above the local wick instead.
params: n/a
`[01:31:08]`

**S5-R26** — Take partial profits: place multiple TPs (TP1/TP2/TP3) at levels of support (for shorts) or resistance / SR points (for longs). Do not use one entry and one TP.
params: TPs = 2–3
`[00:25:08]` `[00:25:40]` `[00:56:27]` `[01:32:19]`

**S5-R27** — Stop trailing on TP hits: when TP1 hits, move stop to break even; when TP2 hits, move stop to TP1.
params: TP1 -> BE; TP2 -> TP1
`[00:08:20]` `[00:25:40]` `[00:40:00]` `[01:20:48]`

**S5-R28** — 50% invalidation: the same setup may be re-taken repeatedly as long as price has not filled/breached the 50% line of the zone. Once 50% of the zone is filled, that setup is dead and must not be re-taken.
params: 50% of zone depth; "round it" to the nearest visually-50% level
`[00:38:52]` `[00:39:26]` `[00:40:34]` `[01:22:28]` `[01:36:24]`

**S5-R29** — After a 50% fill, a NEW, different setup may be built on the same chart — typically an untouched support further down with a much tighter stop and better R:R.
params: n/a
`[00:45:00]` `[01:21:54]` `[01:23:02]` `[01:37:03]`

**S5-R30** — Zone within a zone: when a small zone sits inside a larger one, take the larger play, because its consolidation is longer; the stop is the same either way.
params: n/a
`[01:00:22]` `[01:01:28]`

**S5-R31** — An order block whose move away was small, or that has already had 50% of it filled, is weak; expect at most a small bounce on the next touch.
params: example contrast — 6% move away (weak) vs 15% (strong)
`[01:09:59]` `[01:10:32]`

**S5-R32** — Risk cap: on a swing trade you should only lose 4–5% of your portfolio if the stop is hit.
params: max loss 4–5% of portfolio per swing trade
`[01:35:50]`

**S5-R33** — When shorting inside an uptrend, use lower position size and lower risk (bulls win in an uptrend).
params: reduced size (no number given)
`[00:42:50]`

**S5-R34** — Timeframe selection: swing trading uses the 8h, 12h and daily (4h also counts as swing); scalping uses the 2h and 30m; when given a choice, always take the higher timeframe.
params: swing = 8h/12h/1D (+4h); scalp = 2h/30m
`[01:41:45]` `[01:42:18]`

**S5-R35** — Support/resistance on lower timeframes is always weaker than on higher timeframes; higher-timeframe levels hold, lower-timeframe levels get burst through.
params: monotonic in timeframe
`[00:27:24]` `[00:57:00]`

**S5-R36** — On days with scheduled events (CPI, FOMC, conferences), trade only higher timeframes; do not use the 15m or 1h unless you are a strong scalper. Wait for the event to pass and a range to form before trading.
params: avoid 15m/1h on event days
`[00:18:57]` `[00:20:02]`

**S5-R37** — Do not trade weekends; wait for Monday's range to form. Weekend volume and volatility are low.
params: n/a
`[00:12:49]` `[00:16:11]`

**S5-R38** — After being stopped out, if an SFP then prints at the same level, re-enter the same trade with the stop above/below the new wick.
params: n/a
`[00:22:54]`

**S5-R39** — Bull-flag target: measure the pole from the FIRST green impulse (not a later shorter one) and copy-paste it from the breakout; but take profit at the nearest clear un-flipped resistance rather than at the full technical target.
params: pole = first impulse leg
`[00:07:14]` `[00:07:47]`

**S5-R40** — Inverse head and shoulders validity: the head must be below the left shoulder and the right shoulder must not exceed the left shoulder's level (the book example where the right shoulder goes higher then comes back down is invalid).
params: right shoulder high <= left shoulder high
`[00:01:08]` `[00:02:49]`

**S5-R41** — A trend-line ("sideways") inverse head and shoulders is valid only against a DOWNTREND trend line acting as resistance; against a former uptrend trend line it is invalid (it is just a reclaim).
params: downtrend trend lines only
`[00:03:21]` `[00:04:29]`
Softened immediately: he says he does not play trend-line H&S at all and prefers horizontal ones `[00:05:02]` `[00:05:34]`.

**S5-R42** — Expect more supply zones in bear markets/downtrends and more demand zones in bull markets/uptrends.
params: n/a
`[01:16:17]` `[01:16:51]`

**S5-R43** — If unsure whether a structure is an order block or a supply/demand zone, draw the support/resistance lines FIRST and classify from there.
params: n/a
`[00:58:06]` `[00:58:40]`

**S5-R44** — Higher highs / higher lows are read off candle BODIES (line-chart logic), not wicks.
params: bodies only
`[01:25:16]`

## 4. Parameters and thresholds

| parameter | value | applies to | timestamp |
|---|---|---|---|
| Trend line validity | 3 touches minimum | all trend lines | `[00:06:41]` |
| Max touches of an S/R level traded | 3 (no trade on 4th) | range / S-R trading | `[00:24:35]` `[00:26:16]` |
| Crypto daily candle open | 5:00 pm | Monday range definition | `[00:13:22]` |
| Monday range execution timeframes | 1h and 30m | Monday range scalps | `[00:14:30]` `[00:15:38]` |
| Rejected stop distance (too tight) | $0.60 | mid-range short example | `[00:22:21]` |
| Sufficient gap, 15m/1h | 3–5% | zone validation | `[00:36:38]` |
| Sufficient gap, 1h "perfect" | 8% | zone validation | `[00:35:30]` |
| Sufficient gap, 1h acceptable | 5% | zone validation | `[00:35:30]` |
| Sufficient gap, 30m | 4% (≈3–5%) | zone validation | `[00:54:07]` `[00:55:17]` |
| Sufficient gap, daily minimum | 8–12% | zone validation | `[00:36:38]` |
| Insufficient gap, daily | 3–4% | zone rejection | `[00:36:05]` |
| Sufficient gap, 2-day | 13% (good) | zone validation | `[01:17:59]` |
| Minimum candle bodies in zone | 2 full (2 halves = 1 full) | zone validation | `[00:47:48]` |
| Invalid candle count | 1 and a half | zone rejection | `[00:48:22]` |
| Backtested win rate | 77–82% | his supply/demand method | `[00:38:20]` `[01:15:40]` |
| Backtest years | 2018, 2019, 2020 | his supply/demand method | `[00:28:02]` |
| Zone invalidation level | 50% of zone depth (rounded) | zone replay rule | `[00:38:52]` `[01:22:28]` |
| Probability of breakdown after 50% fill | ~60% | zone replay rationale | `[00:44:26]` |
| Zone width -> 1 DCA | $1.50 / ~$2 / ~$9 examples | DCA count | `[00:49:30]` `[01:14:32]` `[01:24:41]` |
| Max portfolio loss per swing trade | 4–5% | risk sizing | `[01:35:50]` |
| Weak vs strong order block move | 6% vs 15% | order block strength | `[01:10:32]` |
| Swing timeframes | 8h, 12h, daily (4h also) | style selection | `[01:41:45]` `[01:42:18]` |
| Scalp timeframes | 2h, 30m (prefers 2h) | style selection | `[01:41:45]` |
| Post-weekend volume peak | 48–72h after weekend = Tue/Wed | volatility expectation | `[00:17:53]` |
| Example realised moves | 5%, 10%, 12–13%, 24%, 30%, 37% | backtest walkthroughs | `[00:08:20]` `[00:11:06]` `[00:27:24]` `[01:21:21]` `[01:24:41]` `[01:11:05]` |
| Win rate ceiling | not 100% ("nothing has a 100% success rate") | expectation setting | `[00:38:20]` |

## 5. Entry model

Identification (demand zone, long side):
1. Price makes an up-impulse. `[00:34:22]`
2. Price consolidates HORIZONTALLY (bull flag, symmetrical triangle, or plain range). Downward-sloping consolidation disqualifies. `[00:34:55]` `[00:47:14]`
3. The consolidation must contain at least two full candle bodies (two halves = one full). `[00:47:48]`
4. Price breaks out of the consolidation AND moves away by the timeframe-appropriate "sufficient gap" (S5-R16). Until that gap exists, the zone is "not a valid zone yet." `[00:35:30]` `[00:55:17]`
5. Only then are limit orders placed; then wait passively — "it could take minutes, hours, days." `[00:38:20]`

Order ladder (long):
- Entry 1 (lightest): at the SR point, i.e. the TOP of the zone / the flipped level. "We enter at SR points lightly." `[00:37:11]`
- DCA 1 (optional, only if the zone is wide): found by dropping to a lower timeframe and locating an intermediate level inside the zone, typically between the middle and the bottom. `[00:37:46]` `[00:52:27]`
- Final DCA (heaviest): at support, the BOTTOM of the zone. "This is going to be your heaviest bid." `[00:37:46]` `[01:34:03]`
- Zone width decides 1 vs 2 DCAs (S5-R22).
- Price levels are taken from wicks at the "points of most touch," with candle-body clusters acceptable. `[01:05:00]`

Short side (supply zone) is the mirror: SR point entry is the lightest, final/heaviest DCA at the TOP of the box, average fills mid-zone. `[01:14:32]` `[01:15:06]` `[01:31:45]`

Non-zone entries taught in the same session:
- Breakout–retest–hold: enter on the open of the candle after a retest candle closes back on the correct side. `[00:26:50]`
- SFP: market entry on the close of the sweep candle, or limit at the prior swing point if missed. `[00:10:00]` `[00:11:06]`
- Range: long range lows, short range highs, mid-range only per S5-R11/R13. `[00:20:36]`

## 6. Stops

- Demand-zone long: stop below the support line at the bottom of the zone, below the wick. `[00:37:46]` `[00:51:21]`
- Supply-zone short: stop above the wick at the top of the box. `[01:33:29]`
- SFP: stop above/below the sweep wick — this is what makes the risk tight. `[00:10:00]`
- Breakout–retest long: stop below the retested support. `[00:07:14]` `[00:26:50]`
- Low-timeframe trades take their stop level from a HIGHER timeframe, above/below the wicks with leeway. `[00:22:21]`
- Never place the stop above a separate resistance level — that level is its own trade. Go to a lower timeframe and place it just above the local wick. `[01:31:08]`
- A stop that is "too wide" is not tightened; it is compensated for with lower position size. "If it's within your risk tolerance, you can place your stop loss here, but you have to go in with lower position size." `[00:51:53]` `[01:19:10]`
- Absolute ceiling on width: the stop must not cost more than 4–5% of portfolio on a swing trade. `[01:35:50]`
- A trade is skipped entirely when there is no sensible structure to anchor the stop to (his mid-range long example: the only support is at the range low, so the R:R "is not there"). `[00:23:27]` `[00:24:00]`
- Giant wicks are excluded from the zone (and therefore from the stop anchor) unless within risk tolerance. `[01:05:00]`

## 7. Take profit and trade management

- Always take partials. Explicitly warns against "one stop and one TP" — that configuration would have been stopped out in his example. `[00:25:08]`
- 2 to 3 TPs, placed at structural levels: for longs, SR points / resistance / range highs; for shorts, levels of support and then the final support. `[00:56:27]` `[01:32:19]` `[01:26:25]`
- TP1 hit -> move stop to break even. `[00:08:20]` `[00:25:40]` `[00:39:26]`
- TP2 hit -> move stop to TP1. `[00:40:00]` `[01:20:48]`
- He accepts being trailed out: in one walkthrough TP2 hit, stop moved to TP1, price came back and stopped him at TP1 — described as correct behaviour, and the setup is then re-taken. `[00:40:00]` `[00:57:00]`
- Do not trade to the full technical/pattern target; take profit at the nearest clear resistance that has not yet been flipped. `[00:07:47]`
- Spot traders substitute: instead of stops, DCA down at support levels. `[00:08:20]`

## 8. Invalidation and re-entry

Re-entry (allowed):
- The same zone setup may be taken repeatedly as long as the 50% line has not been filled. "If you want, you can take the same trade over and over again. I personally will." `[00:39:26]` `[00:40:00]`
- After a stop-out, if an SFP prints at the same level, re-enter the same trade with the stop above the new wick. `[00:22:54]`
- A range may be played repeatedly between its lows and highs until broken (subject to the third-touch rule). `[00:16:11]` `[00:17:20]`

Invalidation (zone dies):
- Once price fills/breaches 50% of the zone, the setup is dead — "this zone is no longer valid... at that point the setup is going to look completely different." `[00:38:52]` `[00:39:26]`
- Rationale: 50% of the bids that formed the zone have been consumed; remaining liquidity sits lower; ~60% of the time price then closes below the SR point, flips it to resistance and plummets. `[00:41:10]` `[00:44:26]`
- After a 50% fill he switches to a completely different setup — usually an untouched support further down with a tight stop — or does not play the chart at all. `[00:45:00]` `[01:23:35]` `[01:37:03]`
- Level-based invalidation: no trade at the same S/R after its third touch; wait for the flip. `[00:24:35]` `[00:26:16]`
- Pattern invalidation: no entry without a breakout AND a successful retest with close. `[00:08:53]`

## 9. Timeframes

- Swing trading: 8h, 12h and daily are "the best"; 4h also counts as a swing timeframe for when he wants a swing but not a high-timeframe hold. `[01:41:45]` `[01:42:18]`
- Scalping: 2h and 30m; he prefers the 2h "100% of the time" over the 30m, and always chooses the higher of two offered timeframes. `[01:41:45]` `[01:42:50]`
- Monday range: execute on 1h or 30m. `[00:14:30]`
- Higher-timeframe confirmation logic:
  - Higher-timeframe S/R is stronger; lower-timeframe levels are weak and get burst through. `[00:27:24]` `[00:57:00]`
  - "The higher the time frame you are on, the stronger that bounce will be." `[00:38:20]`
  - Higher timeframes require a bigger sufficient gap to validate a zone (S5-R16). `[00:36:05]`
  - Stops for low-timeframe entries are taken from a higher timeframe. `[00:22:21]`
  - DCAs inside a zone are found by dropping to a LOWER timeframe. `[00:37:46]` `[01:19:10]` `[01:35:12]`
  - A structure can change class with timeframe: "a 30 minute order block is now a two-hour SR point" — counted as extra confluence. `[00:59:48]`
  - A messy daily zone can be re-drawn on the 2-day where it "looks clean." `[01:17:25]`
- On event days, move UP in timeframe (S5-R36). `[00:20:02]`

## 10. Confluence

Confluence types he names and counts:
- SR point (flipped level) — the base confluence; "use your lines first." `[00:54:43]` `[00:58:06]` `[01:38:21]`
- Supply/demand zone. `[00:54:43]`
- Order block inside the zone. `[00:54:43]` `[01:04:27]`
- Fibs / the golden pocket (deferred to a later session, but used as confluence here). `[01:04:27]` `[01:05:33]`
- Trend line with 3 touches, and breakout/retest of a downtrend line. `[01:04:27]` `[01:38:21]`
- Chart pattern (bull flag, double bottom, inverse H&S). `[00:59:13]` `[01:12:45]`
- Higher-low structure / uptrend intact. `[01:02:02]` `[01:38:56]`

Counts he actually states: 4 confluences on the SOL trade (breakout+retest of downtrend, demand zone, fibs, horizontal SR point) `[01:04:27]`; 3 confluences on the entry-level choice (wick point of most touch, golden pocket fib, downtrend retest) `[01:05:33]`; 3 in the homework framing (trend line, SR line, demand zone) `[01:43:55]`.

Weighting: none given. He states only "the more you can find, the better it's going to be" and confirms 3 is "a good one." `[01:43:55]` There is no stated minimum count required to take a trade.

## 11. Explicitly excluded

- Fair value gaps — "I don't trade fair value gaps... it's not in my trading skill." `[01:07:12]` `[01:08:20]`
- ICT — "total joke," mocks the naming (turtle soup, unicorn); mutes people who bring it up. `[01:07:45]` `[01:08:52]`
- Smart Money Concepts — rejects its claim to supply/demand and to liquidity grabs/SFPs, which he says predate SMC. `[01:07:45]` `[01:08:20]`
- Fundamental/news trading — "I don't really trade fundamental news." `[00:18:26]`
- Weekend trading — "personally I don't trade during the weekends." `[00:12:49]`
- Scalping (personally) — "I suck at scalping... trading chop and scalping on lower time frames is not my thing." `[00:20:02]`
- Trend-line (sideways) inverse head and shoulders — "I don't even try to play them. I prefer the horizontal ones." `[00:05:34]`
- Technical/pattern measured targets as the actual TP. `[00:07:47]`
- Single-entry/single-TP trade construction. `[00:25:08]`
- Trades at mid-range consolidation. `[00:25:08]`
- Claims of a 100% win rate. `[00:38:20]`
- The book's inverse H&S definition — flatly called wrong. `[00:00:36]` `[00:02:49]`

## 12. Ambiguities for the bot

**S5-A1** — "Sufficient gap" is measured from an unspecified anchor. He says "this move from here to here" and "the move away from this breakout point," but never states whether the % is measured from the top of the zone, the breakout candle's close, or the zone midpoint, nor to what (the swing high, the close of the impulse, or the current price). A coder must pick. `[00:35:30]` `[00:36:05]`

**S5-A2** — The sufficient-gap thresholds are stated inconsistently and only for 15m, 30m, 1h, daily and 2-day. Nothing is given for the 2h, 4h, 8h or 12h — which are exactly the timeframes he later names as his primary swing and scalp timeframes. Interpolation is guesswork. `[00:36:38]` `[01:41:45]`

**S5-A3** — "If the candle closed like let's say down here, you might not want to market short because it already had a huge move" — no threshold for "huge move." Needs a numeric cap (e.g. % of the range already travelled) to be codeable. `[00:10:32]`

**S5-A4** — Zone box boundaries are never defined algorithmically. He says exclude giant wicks, include small wicks "because they're very close to the candle bodies," and elsewhere uses candle bodies only. No rule for how close a wick has to be to be included. `[01:05:00]` `[01:30:30]`

**S5-A5** — "Horizontal consolidation" has no tolerance. He rejects a downward-drifting consolidation by eye `[00:47:14]` `[01:29:19]`, but gives no max slope, no max range-height, and no rule for how a symmetrical triangle (which he explicitly allows) can be "horizontal." `[00:34:55]`

**S5-A6** — Position sizing is unquantified. He specifies only ordering ("lightest at SR point, heaviest at support") and a 4–5% portfolio loss ceiling. No fraction per rung (e.g. 20/30/50), which means average entry, and therefore break-even and every TP-trailing decision, is undetermined. `[00:37:46]` `[01:34:03]` `[01:35:50]`

**S5-A7** — "Zone width decides 1 vs 2 DCAs" is given only as dollar examples ($1.50, ~$2, ~$9 -> one DCA) on specific instruments. There is no percentage or ATR-normalised cutoff, so the rule does not transfer across symbols or price scales. `[00:49:30]` `[01:14:32]`

**S5-A8** — Intermediate DCA placement is delegated to "go to a lower timeframe and find a DCA point" / "points of most touch," with no specification of which lower timeframe, or how a point-of-most-touch is computed. He himself says "for me, I don't know where to place DCA" in the drawn example. `[00:37:46]` `[01:19:10]` `[01:35:12]`

**S5-A9** — The 50% line is explicitly fuzzy: "is this 50% or is this not? Round it. This is about 50%. I would call that a 50% fill." No tolerance band is given, and the invalidation rule is a hard gate hanging off this fuzzy measurement. `[01:22:28]`

**S5-A10** — Unclear whether 50% is breached by a WICK or requires a candle CLOSE below the midpoint. His walkthroughs use "pierced through 50%" and "filled" interchangeably. `[01:23:02]` `[01:36:24]`

**S5-A11** — Unclear whether the 50% rule is measured against the zone as originally drawn or re-measured after each partial fill, and whether the "different setup" he switches to after a 50% fill has its own zone rules or is purely discretionary. `[00:45:00]` `[01:23:35]`

**S5-A12** — TP levels are "levels of support/resistance" chosen by eye. No rule states how many levels back to look, how to rank candidate levels, or how to space TP1/TP2/TP3. In one walkthrough TP3 is at "resistance," in another TP1 is "the SR point at this current price." `[00:56:27]` `[01:32:19]`

**S5-A13** — No stated minimum number of confluences to take a trade, and no weighting between them. "The more the better" is not codeable; a scoring function must be invented. `[01:43:55]`

**S5-A14** — He says he plays order blocks and supply/demand zones "differently" `[00:34:22]` but never states the different entry/stop/TP rules for a standalone order block. Order block treatment is deferred to the next session. `[00:32:06]`

**S5-A15** — "Points of most touch" for entry placement is never defined numerically (touch tolerance, lookback, minimum touches). `[01:05:00]`

**S5-A16** — Touch counting for the third-touch rule is undefined: is a touch a wick, a body close, or a bounce of some minimum size? He counts "one, two, three, four" visually including a "deviation." `[00:24:35]` `[00:46:40]`

**S5-A17** — The Monday range assumes a 5:00 pm daily open, which is his platform/timezone, not stated as UTC. Without the exchange and timezone, the Monday high/low is undefined. `[00:13:22]`

**S5-A18** — "Higher timeframe" for stop placement is relative and unspecified (from a 1h trade, is it the 4h? the daily?). `[00:22:21]`

**S5-A19** — The 77–82% win rate has no sample size, no instrument list, no definition of a "win" (TP1 hit? full TP?), and no statement of whether it counts DCA'd trades from average entry. Not usable as a validation target. `[00:38:20]` `[01:15:40]`

**S5-A20** — "Uptrend" and "downtrend" are used as regime filters (short with lower size in an uptrend; more supply zones in downtrends) but never defined mechanically beyond "higher highs and higher lows by candle bodies." No lookback or swing-detection parameters. `[00:42:50]` `[01:16:51]` `[01:25:16]`

**S5-A21** — The "BVOL zone" reference at `[00:17:53]` (weekend price entering a zone, 48–72 hours to Tue/Wed volume) is unintelligible in the transcript and refers back to material not in this session; do not implement from this session alone.

**S5-A22** — Zone-within-zone: "take the larger play" is stated, but nothing says how much larger, or what to do when the two zones have different sufficient-gap validity or different 50% lines. `[01:01:28]`

## 13. Contradictions

**S5-C1** — Range longs at mid-range. At `[00:21:13]` he says "you always long range lows and only at range lows." At `[00:24:00]` he says "although you can take longs at mid-range, you have to see your situation" — permitting mid-range longs when a support exists for the stop. The absolute rule is softened within three minutes.

**S5-C2** — 1h sufficient gap. At `[00:35:30]` an 8% move on the 1h is "perfect" and 5% is "fine"; at `[00:36:38]` "lower time frames, like on a 15 minute or the 1 hour, a 3 to 5% totally fine." A 4% 1h move is therefore both valid and below the first-stated bar. At `[00:55:17]` a move is judged "not great" and then accepted once it reaches ~4%.

**S5-C3** — Third-touch rule vs zone replay. S5-R2 forbids trading a level after its third touch `[00:24:35]` `[00:26:16]`, but S5-R28 permits replaying a zone indefinitely until the 50% line fills, and he approvingly counts seven bounces off the BTC demand zone `[00:46:40]`. He also says "play the range over and over again" `[00:17:20]`. A bot cannot enforce both; the touch rule appears to apply to bare S/R lines and the 50% rule to zones, but he never says so.

**S5-C4** — 50% rule presented as hard, described as probabilistic. It is stated as an absolute gate ("this zone is no longer valid") `[00:39:26]`, but the rationale is "it happens about 60% of the time" and "I'm not saying it's true" `[00:44:26]`, and he concedes "we could bounce multiple times after that first 50%" `[01:23:35]` and "not always... we can still bounce from it" `[00:46:07]`. Coded as hard invalidation it will skip trades he says can still work.

**S5-C5** — Final DCA location. "Your final DCA usually comes at support... this is going to be your heaviest bid" `[00:37:46]`, versus "you don't always have to have your DCA at the bottom here... you can DCA at any support level you want" `[00:51:53]`. The heaviest-rung anchor is therefore not fixed.

**S5-C6** — Stop width. "This is a wide stop, so manage your risks. If you choose there, you can choose here as well" `[01:19:10]` allows a discretionary tighter stop, contradicting the structural rule that the stop sits below the zone's support (S5-R24) and the rule against arbitrary tight stops `[00:22:21]`.

**S5-C7** — Wicks vs bodies. Zone construction is "only looking for candle bodies" `[00:47:48]` and order blocks are taken "by the candle bodies" `[01:09:27]`, yet entries go at wicks `[01:05:00]`, small wicks may be included in the box `[01:30:30]`, and "this makes sense to use the wicks" when the body is small `[01:09:59]`. Body-only is not actually the rule.

**S5-C8** — SFP liquidity label. Liquidity taken above a swing high is called "sellside liquidity" `[00:10:00]`, which inverts the conventional term. Almost certainly a misspeak; do not encode the label, encode the direction.

**S5-C9** — Order-block handling deferred. He says he plays order blocks differently from zones `[00:34:22]` yet in every walkthrough treats an order block inside a zone as just another confluence with the zone's own entry/stop/TP `[00:54:43]` `[01:04:27]`. Expect the next session (order blocks, promised for "Wednesday" `[00:32:06]`) to conflict with or supersede this.

**S5-C10** — Fibs / golden pocket are used as a decisive confluence for choosing the actual entry price `[01:05:33]` while being explicitly not yet taught ("I will go over fibs a little bit later on") `[01:04:27]`. Any fib logic must come from a later session; this session's confluence count depends on rules it does not contain.

**S5-C11** — Trade-frequency stance. "When we are consolidating here at mid-range, I personally am not going to take any trade" and "I'd rather take the higher risk-to-reward trades" `[00:25:08]` sits against the Monday-range section, where he describes scalpers taking trades at mid-range breaks with "very very tight stops" as a legitimate play `[00:16:46]` `[00:17:20]`.
