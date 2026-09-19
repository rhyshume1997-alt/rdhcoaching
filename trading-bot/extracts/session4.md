# S4 — Range trading mechanics, then the chart-pattern library (flags, wedges, cup & handle, H&S, bearish quasimoto), plus leverage/position-count risk rules

Source: transcripts/S4.md  |  Runtime covered: 00:00:02 to 02:08:20

## 1. Scope
This session teaches how to define and trade a horizontal range (range low, range high, mid-range) as the highest-probability structure, including where to long, where to short, where to sit out, and how to trail stops on TP hits. It then walks through his pattern library — bull flag, bear flag, falling wedge, rising wedge, cup and handle, head and shoulders, inverse head and shoulders, and his own "bearish quasimoto" — each with a mechanical measured-move target and the insistence that entry only comes after breakout/breakdown **and** retest. It closes with hard portfolio-level risk rules: max 2 leverage positions, max 5-6 spot positions, 6-12% of portfolio per spot trade, limit orders only.

## 2. Definitions
- **Range low** — the first touch of support after a prior resistance/SR level is broken above and flipped to support; that flip is what establishes it. `[00:06:48]` `[00:21:18]` `[00:47:59]`
- **Range high** — the level of resistance confirmed by a *second* touch; a first rejection made in price discovery does not count as range high. `[00:21:53]` `[00:48:33]`
- **Points of most touch** — when two candidate lines compete, the range boundary is drawn at the price with the most touches, not necessarily at the flipped level. `[00:22:27]` `[01:02:13]`
- **Mid-range** — the middle band of the range; he explicitly says it is *not* the exact 50% midpoint, it is wherever it "aligns with support and resistance." Differs from the textbook 50% equilibrium. `[00:17:53]` `[00:24:12]`
- **Close above / flip** — the candle *body* must close above resistance (wicks are ignored); then a later candle must come back, retest, and close above the body; the following candle opening above completes the flip. `[00:34:34]` `[00:35:08]`
- **SR point** — a level that has been both support and resistance; after a break below support it is "pending retest" and becomes an SR point that can be shorted with a very tight stop. `[00:11:22]` `[00:28:45]`
- **Net short** — having only short positions with no spot or long positions to cover. `[00:39:06]`
- **Hedge (1:1)** — opening a leveraged short equal in size to the spot bag so up-moves and down-moves wash; the value is that closing the short in profit lets you buy more spot. `[00:09:41]` `[00:37:24]`
- **Flag pole / flag** — the impulse leg is the pole; the consolidation after it is the flag, which he says is "typically a range." `[00:52:15]` `[00:53:57]`
- **Bull flag vs falling wedge** — a bull flag is tight consolidation with **no change in market structure**; a falling wedge is steep and contains a break in structure (series of lower lows / lower highs). This is his working distinction, not the textbook shape definition. `[01:14:39]` `[01:26:58]`
- **Parallel channel** — if the two trend lines are parallel rather than converging diagonally, it is a channel (still bullish structure), not a falling wedge. `[01:18:03]`
- **Cup and handle** — two rejections from the neckline (resistance) forming a wide-based cup, followed by a handle that can itself be a mini-cup, a falling wedge, or a bull flag. `[01:29:27]` `[01:30:36]`
- **Head and shoulders** — neckline is support; head above both shoulders. His non-textbook insistence: the pattern is *not* tradeable at the right shoulder, only after breakdown + retest. "The number one pattern that I see people trade incorrectly." `[01:49:03]` `[01:49:39]`
- **Inverse head and shoulders** — head must be lower than both shoulders; shoulders need not be symmetrical; the right shoulder is not formed until the neckline has been touched. `[01:44:35]` `[01:46:15]`
- **Bearish quasimoto** — his own name for a deviation of head-and-shoulders that forms in an uptrend: after a final higher high, price closes below the prior higher low (making a lower low), rallies back to the previous higher high, makes a lower high and rejects. He states he is the only analyst who uses this name/pattern. `[01:55:04]` `[01:55:40]` `[01:57:54]`
- **Cross leverage** — margin mode he uses exclusively; gives a lower liquidation price than isolated, where isolated only risks what is put into the trade. `[01:59:38]` `[02:02:30]`

## 3. Hard rules

**S4-R1** — In an established range, go long/buy at the range low.
`params:` stop below support / below the wick; TP1 = mid-range, TP2 = range high. `[00:07:57]` `[00:08:00]` `[00:24:46]`

**S4-R2** — In an established range, go short (or sell spot) at the range high.
`params:` stop above resistance / above the wick; TP1 = mid-range, TP2 = range low. `[00:09:05]` `[00:10:14]` `[00:24:46]`

**S4-R3** — Mark range low only after a prior resistance/SR level is broken above and flipped to support (first support touch).
`params:` flip confirmation per S4-R5. `[00:21:18]` `[00:47:59]`

**S4-R4** — Mark range high only after a *second* touch of resistance; a first rejection in price discovery does not count. Where two candidate lines exist, choose the one with the most touches.
`params:` minimum 2 touches; tie-break = points of most touch. `[00:21:53]` `[00:22:27]` `[00:48:33]`

**S4-R5** — A level is "flipped" only when: (a) a candle body closes beyond it (wicks ignored), (b) a later candle retests and closes beyond it on the body, (c) the next candle opens beyond it.
`params:` 3-candle sequence; body-only, wicks ignored. `[00:34:34]` `[00:35:08]`

**S4-R6** — Mid-range longs are allowed only when price is at/consolidating under the range highs.
`params:` entry = mid-range limit; stop below support; final TP = range highs. `[00:13:01]` `[00:34:02]`

**S4-R7** — Mid-range shorts are allowed only when price is at/consolidating at the range lows.
`params:` entry = mid-range limit; final TP = range lows. `[00:11:54]` `[00:34:02]`

**S4-R8** — Take no trade at all while price is *at* or consolidating on/under mid-range.
`params:` zero position; applies to both directions. `[00:12:28]` `[00:26:32]` `[00:34:34]`

**S4-R9** — Never short at support. Short only once support is broken and flipped to resistance (an SR point).
`params:` stop must be "very tight" on the SR-point short. `[00:11:22]`

**S4-R10** — TP allocation by number of TPs.
`params:` 2 TPs = 50/50; 3 TPs = 40/30/30, front-loaded because TP1 is most likely to fill. `[00:18:27]`

**S4-R11** — Stop trailing on TP hits: TP1 hit → move stop to break even; TP2 hit → move stop to TP1.
`params:` deterministic, no discretion stated. `[00:10:14]` `[01:12:19]`

**S4-R12** — If stopped out at break even, the same setup may be re-entered with an adjusted stop (e.g. above the wick that stopped you out), keeping the same TP1/TP2.
`params:` stop relocated beyond the stop-out wick. `[00:10:48]`

**S4-R13** — Keep longing range lows and shorting range highs repeatedly until proven wrong; but as touch count rises either reduce position size or skip the trade.
`params:` he cites taking the trade at 5+ touches inside a confirmed range; expected loss rate ~2-3 in 10. `[00:32:46]` `[00:45:27]` `[00:46:00]`

**S4-R14** — Outside a solidified range (plain S/R, no clean range), do not take the trade after the third touch of the level.
`params:` touch count > 3 → no trade. `[00:44:23]` `[00:45:27]`

**S4-R15** — Discretionary early exit: if a short fills at resistance and price consolidates under resistance without moving down, close it (consolidation under resistance is bullish); if a long fills at support and price consolidates on support without bouncing, close it (consolidation on support is weakness).
`params:` "usually happens after the third or fourth touch"; duration threshold not given. `[00:16:15]` `[00:16:47]`

**S4-R16** — When the entry candle has a giant wick and stop placement is unclear, drop to a lower timeframe and place the stop below the intra-wick support.
`params:` example given on a daily wick, resolved on lower TF. `[00:41:36]` `[00:42:08]`

**S4-R17** — Bull flag measured target: copy the flag pole and anchor it at the base of the flag.
`params:` pole measured from the first green impulse — he uses the *most recent* qualifying impulse. `[00:52:48]` `[00:57:19]` `[01:00:56]`

**S4-R18** — Bear flag measured target: copy the pole measured from the first red impulse and anchor it at the top of the flag, projecting down.
`params:` mirror of S4-R17. `[01:05:49]` `[01:07:35]`

**S4-R19** — Preferred pattern entry is breakout/breakdown **plus retest plus close/hold**, then enter with stop just beyond the flipped level. Do not pre-place limit orders at the SR line before the flip, and do not trade the naked breakout (explicitly labelled the riskiest of the three options).
`params:` three ranked options — (1) naked breakout = riskiest, (2) breakout+retest = safest, (3) buy the bottom of the flag range = middle. `[00:53:57]` `[00:55:04]` `[01:48:29]` `[01:54:25]`

**S4-R20** — A trend line requires three touches to be valid.
`params:` 3 touches minimum. `[01:16:20]`

**S4-R21** — Falling wedge measured target: measure from the bottom trend line to the top trend line at the wedge's origin, then place that distance at the point of breakout.
`params:` anchor = breakout point, not wedge start. `[01:16:53]` `[01:17:28]`

**S4-R22** — Rising wedge measured target: measure top to bottom, place at the point of breakdown. Valid only if price arrived into the wedge from below (rising into it), not from above.
`params:` origin-direction filter is mandatory. `[01:21:44]` `[01:22:18]` `[01:24:34]`

**S4-R23** — Pattern classification filter: steep + break of market structure (lower lows / lower highs) = falling wedge; tight consolidation with no structure break = bull flag; parallel (non-converging) lines = channel, not a wedge.
`params:` "steep" and "tight" not quantified. `[01:14:39]` `[01:18:03]` `[01:26:58]` `[01:28:49]`

**S4-R24** — Cup and handle: the cup requires a wide base and two rejections from the neckline; the handle must not retrace below 40-50% of the cup depth. Target = cup base to neckline, projected up from the neckline. Entry = breakout + retest, stop below support.
`params:` handle floor 40-50% of cup; handle may be a mini-cup, a falling wedge, or a bull flag. `[01:29:27]` `[01:30:01]` `[01:31:45]` `[01:32:20]`

**S4-R25** — Inverse head and shoulders: head must be lower than both shoulders (no shoulder may be lower than the head); shoulders may differ in size; the right shoulder is not formed until the neckline is touched. Target = bottom of head to neckline, projected up from the neckline; entry on breakout + retest.
`params:` head < both shoulders is a hard geometric filter. `[01:44:35]` `[01:45:08]` `[01:45:42]` `[01:46:15]`

**S4-R26** — Head and shoulders: do NOT short at the right shoulder. Wait for breakdown of the neckline, retest, and rejection/close below, then short with a very tight stop. Target = head to neckline, projected down.
`params:` explicit prohibition on the right-shoulder short. `[01:49:39]` `[01:50:50]` `[01:53:51]`

**S4-R27** — Bearish quasimoto short trigger: in an uptrend making higher highs/higher lows, after the final higher high price closes below the prior higher low (making a lower low); then price rallies back to the previous higher high, makes a lower high there and rejects — that rejection is the entry trigger.
`params:` requires prior uptrend; rejection zone = previous higher high; he notes it should also coincide with resistance, not be traded alone. `[01:55:40]` `[01:56:48]` `[01:58:26]`

**S4-R28** — A bear flag is invalidated once price breaks out above the flag.
`params:` break above = pattern dead. `[01:25:40]`

**S4-R29** — The retest must occur on the same timeframe on which the pattern was drawn. Lower-TF retests may be used for a better entry price but do not confirm a higher-TF pattern.
`params:` pattern TF governs confirmation. `[01:38:13]` `[01:39:18]`

**S4-R30** — Maximum 2 leverage positions open at once, per exchange/per account (scalp account and swing account counted separately).
`params:` hard cap = 2. `[01:59:38]` `[02:00:48]` `[02:06:02]`

**S4-R31** — Maximum 5-6 spot positions open at once, each sized 6-12% of portfolio; close or TP existing plays before opening new ones.
`params:` 5-6 positions; 6-12% each; ~60-70% of portfolio deployed. `[02:06:34]` `[02:07:10]`

**S4-R32** — Never market into a position; always set limit orders. If a market entry is unavoidable, use a small size to leave room to add.
`params:` limit-only default. `[02:03:04]`

**S4-R33** — Do not add to an open leverage position in order to improve the liquidation price or reach break even faster; if you like a third setup, close one of the two open positions instead.
`params:` no averaging-down-to-save-liq. `[02:00:48]` `[02:02:30]`

**S4-R34** — Always place duplicate stop losses a tick or two apart, because exchange stops sometimes fail to trigger.
`params:` example 153.40 and 153.38 (≈0.013% apart); MEXC named as worst offender, BitGet/Bybit occasional. `[02:01:58]`

**S4-R35** — Hedging spot: open a leveraged short of the same coin quantity as the spot bag, at 2-3x leverage maximum.
`params:` 1:1 size, 2-3x leverage cap. `[00:09:41]` `[00:36:49]`

**S4-R36** — Never be net short in a bull market. In a bear market being net short is allowed.
`params:` regime-dependent directional constraint. `[00:38:33]` `[00:39:06]`

**S4-R37** — Timeframe assignment: swing/spot trades on 4H or higher; leverage and scalps on 1H or lower (anything under 4H is treated as a quick trade lasting minutes to hours).
`params:` 4H boundary. `[00:35:42]` `[01:40:58]`

**S4-R38** — Draw support/resistance first; patterns are only layered on top as confluence. Never take a trade on a pattern alone.
`params:` S/R is a gating precondition for every pattern trade. `[01:03:29]` `[01:04:03]` `[01:05:14]` `[01:48:29]`

**Softened / contradicted rules (both captured):**
- S4-R14 (no trade after 3rd touch) is explicitly overridden inside a confirmed range by S4-R13 — he takes the 5th and 6th touch of a range boundary. He states the difference himself: "range trading versus support is different." `[00:44:23]` `[00:45:27]`
- S4-R8 (no mid-range trades) is softened at `[00:34:02]`: the prohibition applies only when *price itself is at* mid-range; setting limits at mid-range from the extremes is allowed (S4-R6/R7). He also narrates having personally taken a mid-range long. `[00:27:39]`
- S4-R15: at `[00:16:15]` consolidation under resistance = bullish, close your short. At `[00:29:55]` he sees consolidation under resistance at mid-range and says "I don't care, I'm not taking any trade here" — the bullish read is disabled inside mid-range.

## 4. Parameters and thresholds

| parameter | value | applies to | timestamp |
|---|---|---|---|
| TP split, 2 targets | 50% / 50% | all trades | `[00:18:27]` |
| TP split, 3 targets | 40% / 30% / 30% | all trades | `[00:18:27]` |
| Stop trail on TP1 | move to break even | all trades | `[00:10:14]` `[01:12:19]` |
| Stop trail on TP2 | move to TP1 price | all trades | `[01:12:19]` |
| Range win rate (claimed) | 8 out of 10 | range boundary trades | `[00:15:42]` |
| Range win rate (claimed) | 7 out of 10 | mid-range limit trade | `[00:28:12]` |
| Range loss rate (claimed) | ~30% | range trades generally | `[00:44:23]` |
| Range record (claimed) | 10-for-14 or 11-for-15 | BTC range example | `[00:32:12]` |
| Range record (claimed) | 7-for-7 over ~2-3 weeks | AVAX range example | `[00:43:16]` `[00:43:49]` |
| Touches to confirm resistance / range high | 2 minimum | range construction | `[00:21:53]` |
| Touches to validate a trend line | 3 | trend lines | `[01:16:20]` |
| Touch count where a level weakens | 3rd-4th touch onward | non-range S/R; also cut-trade trigger | `[00:16:15]` `[00:44:23]` |
| No-trade touch threshold (no clean range) | after 3rd touch | plain S/R | `[00:44:23]` |
| Flip confirmation candles | 3 (close above, retest close above, next opens above) | all flips | `[00:35:08]` |
| Cup and handle: handle floor | 40-50% of cup depth | cup and handle | `[01:30:01]` `[01:31:12]` |
| Max leverage positions | 2 per account/exchange | leverage | `[02:00:48]` `[02:06:02]` |
| Max spot positions | 5-6 | spot short-term account | `[02:07:10]` |
| Spot position size | 6-12% of portfolio each | spot | `[02:07:10]` |
| Total spot deployment | ~60-70% of portfolio | spot | `[02:07:10]` |
| Hedge leverage cap | 2-3x | spot hedging | `[00:36:49]` |
| Hedge size | 1:1 vs spot quantity | spot hedging | `[00:09:41]` `[00:37:24]` |
| Duplicate stop spacing (example) | 153.40 and 153.38 (~0.013%) | leverage stops | `[02:01:58]` |
| Example loss tolerance | $300 loss on a $1,000 portfolio (30%) — used to show you cannot be liquidated at that size | cross leverage | `[02:01:22]` |
| Swing/spot timeframe | 4H and above | spot/swing | `[00:35:42]` |
| Leverage/scalp timeframe | 1H or less; under 4H generally | leverage | `[01:40:58]` |
| DCA split (calculator default) | 33% / 33% / 33% (entry + 2 DCAs), or entry + 1 DCA, or custom | position building | `[02:04:56]` |
| Historic trade cited | ETH short 3,900 → 1,600 | example only | `[01:13:32]` |
| Historic trade cited | WAVES short 60 → 8 | example only | `[01:13:32]` |

## 5. Entry model

**Range setups (primary model of this session):**
1. Build the range: find a resistance/SR level that price broke above and flipped to support → that first support touch is the **range low** `[00:21:18]`. Then wait for a **second** touch of resistance to establish the **range high**, drawn at the points of most touch `[00:21:53]` `[00:22:27]`. Mid-range is then drawn at the S/R level nearest the middle `[00:24:12]`.
2. Entries are **limit orders only**, placed at the level, never market `[02:03:04]`:
   - Long limit at range low `[00:07:57]`
   - Short limit at range high `[00:09:05]`
   - Long limit at mid-range **only** while price sits at/under range highs `[00:13:01]`
   - Short limit at mid-range **only** while price sits at range lows `[00:11:54]`
   - Short limit at an SR point (broken support pending retest) with a very tight stop `[00:11:22]` `[00:28:45]`
3. Range low is tradeable before the range high exists ("you're going to long support until broken") — the range high side of the playbook only unlocks after two touches confirm it `[00:23:37]` `[00:50:25]`.

**Pattern setups:**
- Ranked entry options, his words: (1) naked breakout — riskiest, explicitly discouraged; (2) breakout → retest → close/hold above the flipped level, then enter with stop below — his chosen method; (3) anticipate by buying the bottom of the flag's range like a range low `[00:53:57]` `[00:55:04]` `[00:56:10]`.
- He is explicit that you do **not** place a limit at the SR line waiting for the flip; you wait for the flip to complete, then enter `[00:55:38]`.
- Head and shoulders / inverse H&S / cup and handle / wedges all use the same breakout-or-breakdown + retest trigger `[01:32:20]` `[01:45:42]` `[01:49:39]` `[01:54:25]`.
- Quasimoto is the exception in mechanism: the trigger is the rejection from the previous higher high after the lower low, not a retest of a broken level `[01:58:26]`.

**Adding / DCA:**
- No explicit DCA ladder is given for range trades. The only structural statement is the student-built calculator he endorses: entry + 2 DCAs at 33/33/33, or entry + 1 DCA, or a custom split, with the sheet computing quantity and portfolio risk `[02:04:56]`.
- Discretionary scale-in: if you entered early on support and then a cup-and-handle or inverse H&S completes, you may add on the successful retest, accepting a higher average and **must** adjust the stop and re-check risk `[01:37:41]` `[01:47:23]`.
- Never add to a leverage position to fix the liquidation price `[02:00:48]`.

## 6. Stops

- Range long: stop "somewhere below support" or below the support wick `[00:08:00]` `[00:24:46]`.
- Range short: stop above resistance, or above the specific wick that swept it `[00:10:14]` `[00:10:48]` `[00:28:12]`.
- Mid-range long: stop below support (he shows it below the wick that formed the mid-range flip) `[00:13:01]` `[00:27:39]`.
- Pattern entries: stop below the flipped support (longs) or above the flipped resistance (shorts), placed after the retest — he frames this as the reason to wait: "now you have an easier invalidation" `[00:59:33]` `[01:32:20]`.
- SR-point shorts and post-breakdown H&S shorts must use a "very tight" stop `[00:11:22]` `[01:53:51]`.
- Giant-wick problem: if the daily candle's wick makes the stop unusably wide, drop to a lower timeframe and place the stop under the intra-wick support `[00:41:36]` `[00:42:08]`.
- Bear flag breakdown: "This should have the tightest stop" — stop above the nearest support-turned-resistance `[01:05:49]`.
- **What makes a stop too wide:** he never states a maximum stop distance or a maximum R risk. The only proxy is the position-sizing check — run the calculator, see the dollar loss if the stop hits, and confirm it cannot liquidate you (his example: $300 loss on a $1,000 account is survivable) `[02:00:13]` `[02:01:22]`. Wide-wick stops are addressed by moving timeframe, not by rejecting the trade.

## 7. Take profit and trade management

- Swing range default is **two** TPs: TP1 mid-range, TP2 the opposite range boundary `[00:08:32]` `[00:13:34]`.
- Repeatedly qualified: the "final TP" of any measured move is *theoretical*; you should actually take profit at intervening levels of resistance (longs) or support (shorts) `[00:08:32]` `[00:53:25]` `[01:12:19]` `[01:20:33]`.
- Splits: 50/50 for two TPs; 40/30/30 for three, with the largest tranche first because TP1 is most likely to fill `[00:18:27]`.
- Stop trailing: TP1 → break even; TP2 → TP1 `[00:10:14]` `[01:12:19]`.
- Measured-move targets per pattern: bull flag = pole from first (most recent) green impulse copied to flag base `[00:52:48]` `[01:00:56]`; bear flag = pole from first red impulse copied to flag top, downward `[01:05:49]`; falling wedge = bottom-to-top trend-line width at origin, placed at breakout point `[01:16:53]`; rising wedge = top-to-bottom, placed at breakdown point `[01:22:18]`; cup and handle = cup base to neckline, projected up from neckline `[01:31:45]`; inverse H&S = head bottom to neckline, projected up `[01:45:42]`; H&S = head to neckline, projected down `[01:50:50]`.
- Sanity clamp: he notes an H&S target that projected into negative pricing and says technical targets are not promises `[01:51:21]`.
- Discretionary trim/cut: if in profit approaching a neckline and price rejects, either move stop to break even or manually trim `[01:46:51]`. If a trade fills and stalls (consolidation against you), cut it — you will get more opportunities `[00:16:15]` `[00:32:46]`.
- Spot management: at range highs, sell everything bought at range lows; optionally hold and hedge instead `[00:09:05]` `[00:36:15]`.

## 8. Invalidation and re-entry

- **Re-entry is expected and repeated:** "you're going to keep shorting the highs until wrong. You're going to keep longing the lows until wrong" `[00:32:46]`. The same range setup is taken over and over — he cites 7 consecutive AVAX trades and 10-11 wins in 14-15 BTC attempts `[00:43:16]` `[00:32:12]`.
- After a break-even stop-out, the same play may be re-entered with the stop relocated beyond the wick that stopped you `[00:10:48]`.
- A range dies when the boundary is lost: he ties his broader market thesis to "until we lose that range low" `[00:03:57]` `[00:05:39]`, and notes range lows with many touches will "eventually give out" `[00:30:30]` `[00:32:12]`.
- Level strength decays with touches: 1-3 touches = strong; beyond that the level weakens and the trade should be smaller or skipped `[00:15:10]` `[00:32:46]`.
- Bear flag invalidation: break above the flag `[01:25:40]`.
- Inverse H&S is not yet formed (so not tradeable as such) until the neckline touch that creates the right shoulder `[01:46:15]`.
- H&S at the right shoulder is not an invalidation of the uptrend: if price retests the neckline and does not break down, "we're just going to go to the upside" `[01:53:51]`.
- Pattern flip failure: a lower-TF breakout/retest that closes back under on the pattern's own timeframe does not count `[01:39:18]`.

## 9. Timeframes

- He self-describes as a swing trader, predominantly spot, and trades **4H or higher** on essentially all trades; anything below 4H is a very quick trade lasting minutes to hours `[00:35:42]`.
- Higher timeframe → stronger S/R, resistance and support lines, and higher success rate; lower timeframe → weaker levels and weaker pattern reactions, though more patterns appear `[00:35:08]` `[01:40:58]` `[01:42:05]`.
- Patterns found on the daily are for spot; leverage wants smaller timeframes, 1H or less; scalping under 4H `[01:40:58]`.
- HTF confirmation logic: the retest confirming a pattern must occur on the timeframe the pattern was drawn on. You may use a lower TF for a better entry price, but a 4H breakout+retest that closes back under on the daily is not confirmed `[01:38:13]` `[01:39:18]` `[01:39:50]`.
- Chart hygiene: if a chart renders blurry when zoomed out, plot the points on a higher timeframe first, then drop down `[00:19:34]`. Use the lower TF when the higher-TF wick is too large to place a stop `[00:41:36]`. Mid-range is often cleaner on the 4H than the daily because there is more data `[00:24:12]`.
- Ranges themselves exist on any timeframe; strength scales with timeframe `[00:35:08]`.

## 10. Confluence

- **Order of operations is mandatory:** draw support and resistance lines first, then add supply/demand zones, then patterns on top `[01:04:40]` `[01:05:14]`.
- Patterns are confluence only — "you shouldn't just trade patterns alone" — and he cites personal failure trading patterns alone and analysts who lost their roles trading breakouts without retests `[01:04:03]` `[01:48:29]`.
- Worked example of stacking: strong support (3rd touch) + multi-touch downtrend resistance being broken + consolidation under resistance + a bull flag = "more confluences for a bullish continuation than we do for a bearish move down" `[01:04:03]` `[01:04:40]`.
- Cross-asset confluence from the opening review: USDT dominance rejecting resistance while BTC bounces from support/order block "lined up perfectly"; USDT dominance is inversely correlated to all of crypto, not just BTC `[00:01:10]` `[00:01:43]` `[00:02:17]`.
- The quasimoto is only taken when the previous-higher-high rejection level is *also* horizontal resistance and, ideally, trend-line resistance `[01:56:48]` `[02:07:46]`.
- Patterns can form on trend lines, and a pattern can nest inside a larger pattern (bull flag within a giant bull flag at a trend line) `[01:42:49]` `[01:43:30]` `[02:07:46]`.
- Cup and handle and inverse H&S are rated stronger than bull/bear flags, but rarer; flags are more common and more frequently traded `[01:39:50]` `[01:40:23]`.
- **He never states a required number of confluences** — only "more confluences for X than Y" as a directional comparison `[01:04:40]`.

## 11. Explicitly excluded

- Meme coins — "I don't trade meme coins really" `[00:16:47]` `[00:17:21]`.
- On-chain trading — never used Jupiter, does not own and never will own a MetaMask; only ever swapped via Phantom `[00:17:21]`.
- Trading from a PC — has never taken a trade on a PC; phone trader since 2019, PC used for charts only `[00:17:21]`.
- Any trade while price is at/consolidating on mid-range — "sit on your hands," "I don't trust either one of them," "I'm not taking anything" `[00:12:28]` `[00:16:47]` `[00:26:32]` `[00:31:40]` `[00:34:34]`.
- Longing range highs `[00:15:10]`.
- Shorting support before it breaks `[00:11:22]`.
- Trading a pattern in isolation without S/R `[01:04:03]` `[01:48:29]`.
- Naked breakout entries without a retest — "if I don't have confirmation, I'm not going to get into a trade" `[01:47:57]` `[01:48:29]`.
- Shorting the right shoulder of a head and shoulders before the neckline breaks `[01:49:39]`.
- Market orders for entry — "I never market into anything. I always set limits" `[02:03:04]`.
- Being net short in a bull market `[00:38:33]`.
- Calling a steep, structure-breaking consolidation a bull flag; calling a parallel channel a falling wedge; calling a non-clean, non-tight, sub-3-touch consolidation a bear flag `[01:08:11]` `[01:09:27]` `[01:18:03]`.
- Using a pattern at all when the consolidation is too small — "I wouldn't even use a pattern there. I would just place support and resistance" `[01:03:29]`.
- Isolated margin (he uses cross exclusively) `[01:59:38]`.

## 12. Ambiguities for the bot

**S4-A1** — **Mid-range is not algorithmically defined.** He explicitly rejects the exact midpoint and says it "will usually align with support and resistance," then eyeballs it on the 4H. A coder must choose: geometric 50%, or the highest-touch-count S/R level within some band around 50%, and how wide that band is. `[00:17:53]` `[00:24:12]`

**S4-A2** — **"Points of most touch" has no tolerance.** No price band, ATR multiple, or percentage is given for what counts as the same level being touched, nor whether wicks count as touches for this purpose (they are excluded for *closes* but he counts wick rejections visually). `[00:22:27]` `[00:49:06]`

**S4-A3** — **No distance threshold separating "at range lows/highs" from "at mid-range."** The entire R6/R7/R8 gating depends on where price "is," but no % of range width or ATR distance defines the three zones. `[00:13:01]` `[00:34:02]`

**S4-A4** — **"Consolidating for a long time" has no candle count.** The cut-the-trade rule (S4-R15) and the range-low-weakness read both hinge on this. He only offers "usually happens after the third or fourth touch." `[00:16:15]` `[00:32:46]`

**S4-A5** — **Stop buffer is unquantified.** "Somewhere below support," "below the wick," "somewhere here" — no tick/percentage/ATR offset is ever stated, and he says outright "I can't give you definite spot." `[00:07:57]` `[00:08:00]`

**S4-A6** — **No risk-per-trade or leverage-position sizing rule.** Spot gets 6-12% per position; leverage gets only a position *count* cap (2). No % risk, no leverage multiplier for directional trades (the 2-3x figure is for hedges only). `[00:36:49]` `[02:07:10]`

**S4-A7** — **DCA placement is undefined.** The calculator implies entry + 1 or 2 DCAs at 33/33/33 or a custom split, but he never says at what price levels DCAs sit relative to the first entry, nor whether range trades use DCAs at all. He also says he has never used that sheet. `[02:04:56]` `[02:05:29]`

**S4-A8** — **"Steep" vs "tight" (falling wedge vs bull flag) has no threshold.** He classifies by eye and invites students to tag him in chat to ask which it is. A coder needs a slope, an angle, a retracement depth, or a structure-break test. His only objective hook is "a bull flag has no change in market structure." `[01:14:39]` `[01:18:38]` `[01:26:58]`

**S4-A9** — **Cup handle floor is "40 to 50%" — which number?** Two different thresholds are stated interchangeably in the same breath, twice. `[01:30:01]` `[01:31:12]`

**S4-A10** — **"Wide base" for a cup is not measured.** No minimum cup width in candles or width:depth ratio. `[01:29:27]` `[01:34:09]`

**S4-A11** — **No required confluence count and no weighting.** He compares "more confluences for bullish than bearish" without defining the list, the count, or any weights, so the bot has no confluence scoring threshold. `[01:04:40]`

**S4-A12** — **Quasimoto stop placement is never stated,** and the "reject from the last higher high point" trigger has no tolerance band (exact price, or a zone?) and no confirmation candle requirement — unlike every other pattern here, which requires a retest close. `[01:55:40]` `[01:58:26]`

**S4-A13** — **Re-entry stop adjustment is "change the stop loss a little bit."** No rule for how far beyond the stop-out wick, nor a cap on how many re-entries per level. `[00:10:48]`

**S4-A14** — **"Take profits at levels of resistance/support" conflicts operationally with the fixed TP splits.** He says the measured-move final TP is theoretical and real TPs go at intervening levels, but never says how many such levels to use, how to select them, or how 50/50 and 40/30/30 map onto a variable number of levels. `[00:53:25]` `[01:12:19]` `[01:20:33]`

**S4-A15** — **Range detection scope is unspecified.** No lookback window, no minimum range height, no rule for when an old range is stale, and no rule for choosing between nested ranges on different timeframes. `[00:35:08]`

**S4-A16** — **"Until proven wrong" is not defined as an invalidation event.** Is the range dead after one stop-out, after a body close beyond the boundary, or after the flip sequence in S4-R5 completes in the opposite direction? He uses all three loosely. `[00:32:46]` `[00:46:00]`

**S4-A17** — **Bull/bear flag minimum size.** He rejects a flag as "way too small" without any metric — candle count, height, or duration. `[01:03:29]`

**S4-A18** — **Neckline geometry for H&S is never specified** — horizontal only, or a sloped line through the two troughs? All his examples are drawn by hand. `[01:49:03]` `[01:53:18]`

**S4-A19** — **Duplicate-stop spacing is one worked example (153.40 / 153.38), not a rule.** No percentage or tick generalization, and no guidance on how many duplicate stops. `[02:01:58]`

**S4-A20** — **Scalp account vs swing account are treated as separate 2-position buckets, but their capital split is never given,** nor how the 5-6 spot position cap interacts with the leverage caps in one portfolio. `[02:06:02]` `[02:07:10]`

**S4-A21** — **Bull/bear flag pole anchor is non-deterministic by his own admission** — "there's no wrong green impulse to take it from," which makes the measured target ambiguous by design. See S4-C6. `[01:00:56]` `[01:11:13]`

**S4-A22** — **"Very tight stop" (SR-point shorts, post-H&S-breakdown shorts) is never quantified.** `[00:11:22]` `[01:53:51]`

## 13. Contradictions

**S4-C1** — **Touch-count rule reverses itself.** More touches weaken a level and he would not take a trade after the third touch `[00:15:10]` `[00:44:23]`; but inside a confirmed range he takes the 5th, 6th and 7th touch anyway and calls that correct `[00:44:55]` `[00:45:27]`. He acknowledges the conflict and resolves it as "range trading versus support is different," then immediately reopens it with "But also, I can decide not to take this trade because of the multiple touches... So this is discretionary" `[00:46:00]`. A bot needs a deterministic branch here.

**S4-C2** — **Win rates are inconsistent across the session:** 8/10 `[00:15:42]`, 7/10 `[00:28:12]`, ~70% `[00:44:23]`, 10-for-14 or 11-for-15 (~73%) `[00:32:12]`, 7-for-7 `[00:43:16]`. None are backtested figures; they are recollections. Do not use any of them for sizing or expectancy.

**S4-C3** — **Consolidation-under-resistance reads both ways.** At `[00:16:15]` it "shows strength... price typically wants to break out," which is grounds to close a short. At `[00:29:55]` the same condition at mid-range is dismissed ("usually it's bullish, but during mid-range, I don't care") and price then dumps. A student also raises that a previous class called consolidation at support bearish; he half-confirms and half-softens it `[00:18:27]` `[00:19:00]`.

**S4-C4** — **Excluded instruments vs. his own book.** He says he does not trade meme coins and has never done on-chain trading `[00:16:47]` `[00:17:21]`, then at `[02:05:29]` says he bought Mumu, "it's mostly onchain," with the week's profits. Treat the exclusions as strategy-level filters that his personal discretionary book violates.

**S4-C5** — **Mid-range: no trades vs. mid-range trades.** "That's why I don't trade mid-range" `[00:26:32]`, "if we're consolidating on mid-range, I'm not taking anything" `[00:31:40]` — against explicit mid-range long and short setups `[00:11:54]` `[00:13:01]` and a mid-range long he says he personally called and filled for a 2% move `[00:27:39]`. He reconciles it at `[00:34:02]` (price *at* mid-range = no trade; limits *set* at mid-range from the extremes = fine), but the narration on charts keeps blurring the two.

**S4-C6** — **Flag pole anchoring.** "There's no wrong green impulse to take it from. However, I take it from the most recent one" `[01:00:56]`, and for bear flags "doesn't matter which red impulse you started from" while noting each yields a different final TP `[01:11:13]`. The measured target is therefore not a single value. Codify as "most recent impulse" and flag that this is the coder's choice, not his rule.

**S4-C7** — **Risk ranking of the three pattern entries is garbled.** He calls the naked breakout the riskiest `[00:54:31]`, then says the range-bottom entry "is the second less riskiest but uh riskiest but the less riskiest is going to be this breakout retest" `[00:56:10]`. Best reading: breakout+retest safest, range-bottom middle, naked breakout riskiest — but the transcript does not state it cleanly.

**S4-C8** — **Leverage position cap phrasing.** "I never have more than two positions open at once" `[01:59:38]` `[02:00:48]` vs. the clarification that it is two per exchange *and* two per account, with a scalp account and a swing account both running `[02:06:02]` — so the true global cap is 2 x (number of accounts), not 2.

**S4-C9** — **Likely cross-session conflict:** he defers order blocks / supply-and-demand zones to later sessions ("an order block which I will cover in the next two sessions") while already using them as confluence here `[00:01:10]` `[00:05:39]` `[00:28:45]`. Expect the order-block definition from a later session to change how the range-low and range-high entries are qualified. He also promises hedging will be covered "a little bit more later on the course" `[00:09:41]`.
