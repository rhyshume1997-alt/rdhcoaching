# TBOT1 — Live multi-coin crypto chart walkthrough (BTC, ETH, ~18 alts) with entries, stops and TPs called in real time

Source: transcripts/TBOT1.md  |  Runtime covered: 00:00:01 to 01:10:03 (`[end]` block, ~01:11)

## 1. Scope
This is not a structured lesson — it is a live weekend market review in which he charts Bitcoin, ETH, Bitcoin dominance, USDT dominance and roughly eighteen alts back to back, calling entries, stops and take-profits out loud on each. Its value to the bot is that it shows the *applied* method: the fixed order in which he reads a chart (HTF trend line → key horizontal levels → liquidity → order blocks/zones → fibs → confluence check → drop to LTF → entry/stop/TP), and how he sizes and skips trades that technically qualify. It also exposes where he overrides his own textbook rules — most often on "the level gets weaker every touch", on stop width, and on "I don't short strength".

## 2. Definitions

**Play the trend until broken** — while price is on/inside the trend line, trade in the trend's direction; only a break of that line changes it. `[00:01:14]`

**Consolidation on support in a downtrend** — the longer price sits on a support level inside a downtrend, the more likely it resolves *down*, not up. `[00:01:14]`

**Level decay / "weaker every touch"** — every additional touch of a support, trend line or fib zone makes it more likely to fail; he states the golden pocket is good for one or two plays and unreliable from the third. `[00:04:55]` `[00:22:24]` `[00:25:17]` `[00:26:30]`

**Liquidity (areas to sweep)** — clusters of stops at internal lows/highs and at prior swing extremes; he names them as targets price will go and take. `[00:01:14]` `[00:52:38]`

**Golden pocket** — the fib retracement zone he expects a bounce from; used as the primary entry level. `[00:03:31]` `[00:23:30]` `[00:31:30]` `[00:34:06]`

**0.786 fib** — the deeper retracement level, used as the DCA / second entry, and as "the deeper wick" he prefers. `[00:03:31]` `[00:04:11]` `[00:21:52]` `[00:22:57]` `[00:26:30]`

**Order block (OB)** — a prior consolidation/origin block he expects price to react from; the actual price object he attaches an entry to when a fib lines up with it. `[00:02:57]` `[00:03:31]` `[00:16:02]` `[00:23:30]` `[00:26:30]`

**Supply zone** — created when a big move down is followed by a consolidation drifting up; that consolidation becomes the supply that sends price back down. `[00:14:53]` `[00:26:30]` `[00:39:15]`

**Demand zone** — the area that has repeatedly held price up; the only place he will buy a dying coin. `[00:22:24]` `[01:00:44]`

**SR point (support/resistance flip point)** — a level that has acted as both; counted as an independent confluence alongside fibs and OBs. `[00:12:41]` `[00:20:42]` `[00:25:17]` `[00:27:04]` `[00:54:33]` `[01:01:48]`

**SFP (swing failure pattern)** — price takes out a prior high/low and fails to hold beyond it; sweep-lows-and-reclaim is a long trigger, sweep-highs-and-fail is a short trigger with stops above the wick. `[00:06:38]` `[00:08:20]` `[00:20:42]` `[01:05:47]`

**Capitulation wick** — an extreme flush wick; his claim is it *always* gets recovered eventually — "a matter of when, not if" — and he explicitly refuses to place stops or take entries off it. `[00:08:56]` `[00:22:57]` `[00:48:12]` `[00:55:25]`

**Bearish engulfing candle** — a candle that fails to reclaim and engulfs the prior one; he treats it as a repeatable downside signal ("move back up, engulfing candle, downside" as a cycle). `[00:14:53]` `[00:19:34]` `[00:33:19]`

**Break of structure (BOS)** — a higher high made above the last lower high (or the mirror for downside); the trigger that permits buying the *next* higher low. `[00:31:30]` `[00:48:46]`

**Distribution** — a sharp move up followed by consolidation, especially in a downtrend; read as sellers distributing, not accumulation. `[00:51:25]`

**Beta coin** — a coin whose fate is dictated by its major (LDO is "an ETH beta"); it cannot be played on its own chart, only when the major is performing, but it pays a larger ROI when it does. `[00:24:38]` `[00:27:41]`

**Conditional trigger** — a pre-defined price condition that arms a trade he is not taking now (e.g. ETH 1,800–2,500 buy zone); he posts these rather than trading at market. `[00:10:03]` `[00:52:38]`

**Expansion after accumulation** — the longer the consolidation/accumulation, the more explosive and violent the eventual expansion. `[00:04:55]` `[00:45:42]` `[00:46:19]`

**"Too wide"** — a zone or stop distance large enough that a normal-leverage position would risk too much; the trade is not cancelled, it is *downgraded* to spot or low leverage. `[00:15:27]` `[00:16:02]` `[00:27:04]` `[00:42:53]`

## 3. Hard rules

**TBOT1-R1** — While price holds the trend line, trade in the direction of the trend; a break of the trend line is what changes the bias.
`params:` trend line drawn off swing pivots; "many variations" acknowledged.
`[00:01:14]`

**TBOT1-R2** — In a downtrend, treat prolonged consolidation on support as a downside resolution, not a base.
`params:` none numeric.
`[00:01:14]`

**TBOT1-R3** — Decay every level with each touch: a golden pocket / support may be played once or twice, and is considered unreliable from the third touch onward.
`params:` touch count 1–2 = tradeable, 3+ = weak.
`[00:04:55]` `[00:22:24]` `[00:26:30]`
*Softened / contradicted:* he takes the scalp anyway on ENA at what he counts as a repeat touch `[00:16:44]` and on HYPE while saying "getting weaker and weaker every single time we touch it. But, a scalp opportunity" `[00:22:24]`. See TBOT1-C1.

**TBOT1-R4** — A setup requires stacked confluence at one price: fib level + order block + SR point (+ trend-line touch where available).
`params:` he names 3–4 aligned objects as "your confluence".
`[00:20:42]` `[00:21:52]` `[00:23:30]` `[00:26:30]`

**TBOT1-R5** — First entry goes at the golden pocket; the DCA/second entry goes at the 0.786 fib.
`params:` golden pocket = entry 1; 0.786 = entry 2 (DCA).
`[00:03:31]` `[00:04:11]` `[00:22:57]` `[00:26:30]`

**TBOT1-R6** — Stop goes below the structural low/wick that defines the zone — but never below or off a capitulation wick; use the ordinary wick instead.
`params:` BTC example stop "below 92K" with entry ~93.5K.
`[00:04:11]` `[00:22:57]` `[00:55:25]`

**TBOT1-R7** — If the stop distance / zone width is too wide for leverage, do not cancel the trade — take it on spot or with low leverage.
`params:` "plays on spot because it's too wide, unless you go with like low leverage".
`[00:15:27]` `[00:16:02]` `[00:27:04]`

**TBOT1-R8** — Do not turn bullish on a downtrending asset until the named resistance is reclaimed AND flipped to support; only then long toward the highs.
`params:` ETH trigger = 3,000 reclaim → target 4,000–4,200. DOGE = flip level then long. POPCAT = "you need to get above this level to long".
`[00:07:09]` `[00:07:47]` `[00:08:20]` `[00:31:30]` `[00:34:40]`

**TBOT1-R9** — SFP long: sweep the prior lows and reclaim them → long. SFP short: wait for the prior highs to be taken out and failed → short with stop above the wick.
`params:` ETH SFP long ~2,450 sweep-and-reclaim.
`[00:06:38]` `[00:08:20]` `[00:20:42]` `[01:05:47]`

**TBOT1-R10** — A bearish engulfing candle (failure to trade back above the prior candle's body by the daily close) signals a downside move.
`params:` daily close used as the confirmation; also read on 4h/12h.
`[00:14:53]` `[00:19:34]` `[00:33:19]`

**TBOT1-R11** — Trade RSI divergence: price making higher highs with RSI making lower highs = short; price making lower lows with RSI making higher lows = long.
`params:` FARTCOIN bullish div paid a 53% move; SOL weekly bearish div (first since Nov 2021 cycle top) = "topped for the cycle".
`[00:35:49]` `[00:41:38]` `[01:06:59]`

**TBOT1-R12** — Do not short strength.
`params:` none.
`[00:24:03]`
*Contradicted in practice:* "any impulse up, I'd be looking to short" `[01:00:44]`, and he gives short levels into strength on BNB `[00:54:01]` and ONDO `[00:52:04]`. See TBOT1-C2.

**TBOT1-R13** — Cap risk on a large swing position at 5–6% of portfolio.
`params:` 5–6% of portfolio (stated for the SOL cycle-top swing short).
`[00:38:08]`

**TBOT1-R14** — Ladder into a swing short across a range rather than entering at one price; the fill average sits mid-ladder, and the position is cut if the invalidation level is flipped to support.
`params:` SOL ladder start ~from the rejection area up to ~260; cut if 270 flips to support.
`[00:38:08]`

**TBOT1-R15** — Post-downtrend buy trigger: require a break above the last lower high, then buy the first higher low, with stop below the previous higher low (or below the lower low if it made one first).
`params:` enter small on the first leg, add at the next higher low; SUI target ~3.50.
`[00:48:46]` `[00:49:20]` `[00:49:57]`

**TBOT1-R16** — Breakdown entry sizing: enter the initial breakdown with a *small* position and add on the retest, because a wick-down-and-reclaim of the trend line invalidates the breakdown.
`params:` "smaller position sizing" first, add on retest; OM 1h breakdown.
`[01:07:34]` `[01:08:07]`

**TBOT1-R17** — Every trade gets three take-profits: TP1 at the nearest structure (range lows / first OB), TP2 and TP3 at successive resistances or range highs.
`params:` TP1/TP2/TP3 stated on LINK, ENA, RENDER and OM.
`[00:13:44]` `[00:17:20]` `[01:04:24]` `[01:08:44]` `[01:09:17]`

**TBOT1-R18** — Spot-bag invalidation on a weak alt is a *daily close* below the stated level, not a wick.
`params:` POPCAT spot buy at 20 cents, invalidated on daily close below 15 cents.
`[00:32:04]` `[00:48:46]` (SUI: "although we had the wick, the candle closed above the support")

**TBOT1-R19** — Stay risk-off on alts while BTC dominance and USDT dominance are still trending up; only take alt longs after USDT dominance rejects at its next level.
`params:` USDT.D next level ≈ 5% (transcribed once as "5 cents"); BTC.D needs the deviation + trend-line rejection.
`[00:44:33]` `[00:45:09]` `[00:45:42]` `[00:46:51]`

**TBOT1-R20** — If a coin's USDT pair, its BTC pair, and Bitcoin itself are all at resistance at the same time, do not long it — expect an outsized drop when BTC turns down.
`params:` SOL precedent cited at 14% / 35% / 27% down moves; applied as a warning on BNB.
`[00:57:03]` `[00:58:14]` `[00:58:46]`

**TBOT1-R21** — Do not trade a beta coin on its own chart; gate it on its major's performance.
`params:` LDO gated on ETH; LDO moved 8% vs ETH 5% on the same day (higher ROI when the gate opens).
`[00:24:38]` `[00:27:41]`

**TBOT1-R22** — Treat a capitulation wick as eventually recovered ("when, not if"), so bid the wick area rather than chasing the breakdown.
`params:` no time bound given.
`[00:08:56]` `[00:47:40]` `[00:48:12]`

**TBOT1-R23** — Expect the breakout out of a tight range/long consolidation to be violent, and expect it to trap the crowd first (squeeze the consensus side, reject, then resume the trend).
`params:` BTC range ≈ 2K wide; violent move expected "Tuesday or Wednesday".
`[00:00:01]` `[00:04:55]` `[00:05:26]` `[00:45:42]` `[00:46:19]`

**TBOT1-R24** — Discount weekend signals: low volume means charts are unclear and setups are not worth touching.
`params:` weekend; "no volume"; "I don't see anything worth touching, it's just not clear".
`[00:09:30]` `[00:24:03]` `[00:28:14]`

**TBOT1-R25** — Do not take a trade at current market price; wait for price to arrive at a pre-marked level, and publish it as a conditional instead.
`params:` "I wouldn't take anything at a current market price trade right now".
`[00:10:03]` `[00:52:38]`

**TBOT1-R26** — Stack two conditional entries at different depths: if the shallower scalp stops out, the deeper order is the one that triggers, and that one is played until broken.
`params:` POPCAT — scalp at the retest level, deeper order at 20 cents.
`[00:30:54]`

**TBOT1-R27** — On a range, take three separate plays off the same chart: long the range low, short the range high / SR retest, and a breakout continuation play.
`params:` "three separate plays" (LINK), "three separate shorts" (HYPE), "three opportunities".
`[00:12:41]` `[00:13:44]` `[00:24:03]` `[00:24:38]`

**TBOT1-R28** — A short setup at a level is cancelled if the trend line above is reclaimed; a long setup below is cancelled if support is lost on a close.
`params:` BNB — "small short only because if we reclaim this trend line... we can go higher" (3-day trend line).
`[00:54:01]` `[00:54:33]`

**TBOT1-R29** — A short thesis that is not filled decays with time: the longer price consolidates into the trend line without triggering, the weaker the short becomes, and it must be re-assessed rather than left resting.
`params:` ETH short "gets weaker" the longer consolidation runs; reassessed at the weekly update.
`[00:06:04]` `[00:06:38]` `[00:08:20]`

**TBOT1-R30** — Bid an established demand zone on a dying/illiquid coin only for a quick, small-target move, using the zone edge as an "easy invalidation", and sell into the flipped SR resistance.
`params:` BEAM — target 10–15% move; "not even a one hour trade"; short again on rejection at 1.14 cents.
`[01:00:44]` `[01:01:16]` `[01:01:48]`

## 4. Parameters and thresholds

| parameter | value | applies to | timestamp |
|---|---|---|---|
| BTC consolidation range width | ~2K (USD) | BTC range read | `[00:00:01]` |
| Expected breakout timing | Tuesday or Wednesday | BTC weekly plan | `[00:00:33]` |
| BTC liquidity target (downside) | 85,000 | BTC swing target | `[00:01:14]` |
| BTC bullish trigger level | ~106,000 ("above this level we will see new highs") | BTC bias flip | `[00:01:47]` |
| BTC preferred long entry (OB / golden pocket) | 93,500 ("70 or 93.5" — ASR; the OB is 93.5K) | BTC long | `[00:03:31]` |
| BTC DCA level | 0.786 fib | BTC long DCA | `[00:04:11]` |
| BTC stop | below 92,000 | BTC long | `[00:04:11]` |
| BTC trade duration estimate | "about a three-hour trade" | BTC long | `[00:04:11]` |
| BTC short zone | 100,000; refined 101,000–102,000 | BTC short | `[00:04:11]` `[00:04:55]` |
| ETH safer short zone | 2,720–2,800 | ETH short | `[00:06:38]` |
| ETH bull trigger | 3,000 reclaim + flip to support | ETH bias | `[00:07:09]` `[00:08:20]` |
| ETH upside target if 3K reclaims | 4,000–4,200 (cycle highs) | ETH long | `[00:07:47]` |
| ETH SFP long level | ~2,450 sweep + reclaim | ETH long | `[00:08:20]` |
| ETH "buy cheap" zone | 1,800–2,500 | ETH spot/conditional | `[00:09:30]` |
| ETH vs LDO daily move comparison | ETH 5% / LDO 8% | beta-coin ROI | `[00:27:41]` |
| LINK scalp entry | ~18.19 | LINK scalp | `[00:13:44]` |
| ENA short trigger | ~62 (cents) | ENA short | `[00:16:44]` |
| ENA touch count at range high | "one, two, three touches" | level decay | `[00:16:44]` |
| ENA no-support-until level | ~40 cents | ENA risk note | `[00:17:20]` |
| UNI/next-coin support | 22.72 | key level | `[00:18:25]` |
| HYPE demand/buy zone | 18–19 (USD) | HYPE long | `[00:22:24]` |
| HYPE entry | ~21.28 at the 0.786 fib | HYPE long | `[00:22:57]` |
| Golden-pocket reuse limit | 1–2 plays, weak from the 3rd | all charts | `[00:26:30]` |
| LDO fib alignment TF | 0.786 aligning with 3-day OB | LDO long | `[00:26:30]` |
| POPCAT short level | 50 cents | POPCAT short | `[00:29:10]` |
| POPCAT buy level | 20 cents | POPCAT spot/scalp | `[00:29:43]` `[00:32:04]` |
| POPCAT spot invalidation | daily close below 15 cents | POPCAT spot | `[00:32:04]` |
| POPCAT reversal-pattern TF | 4-hour or 12-hour close | POPCAT long trigger | `[00:29:43]` |
| DOGE short level | 30 cents | DOGE short | `[00:32:44]` |
| DOGE upside trend-line/golden-pocket level | 23.68 (cents) | DOGE resistance | `[00:34:06]` |
| SOL first bearish weekly div since | cycle top, November 2021 | SOL cycle-top thesis | `[00:35:49]` |
| SOL major support | 180 (buy area 183 down to 175) | SOL long | `[00:37:00]` `[00:38:40]` |
| SOL long stop | below 166 | SOL swing long | `[00:38:40]` |
| SOL short ladder top | ~260 | SOL swing short | `[00:38:08]` |
| SOL short cut level | 270 flipped to support | SOL swing short | `[00:38:08]` |
| SOL risk budget | 5–6% of portfolio | SOL swing short | `[00:38:08]` |
| SOL short targets | 120, "maybe even sub 100" | SOL swing short | `[00:38:40]` |
| FARTCOIN divergence payout | 53% move | RSI div example | `[00:42:19]` |
| FARTCOIN support to hold | 41 cents | FARTCOIN | `[00:42:53]` |
| FARTCOIN leverage stop | below 37 cents | FARTCOIN long | `[00:43:25]` |
| USDT.D next resistance | ~5% (spoken once as "5 cents") | alt risk-on trigger | `[00:45:42]` `[00:46:51]` |
| SUI target | ~3.50 (also the short level if reached) | SUI | `[00:49:57]` |
| ONDO short level | 158 (USD as spoken) | ONDO short | `[00:52:04]` |
| BNB trend-line timeframe | 3-day | BNB short invalidation | `[00:54:01]` |
| SOL analogue drawdowns when all pairs at resistance | 14%, 35%, 27% | correlation risk | `[00:58:46]` |
| BEAM quick-move target | 10–15% | BEAM long | `[01:01:16]` |
| BEAM short-on-rejection level | 1.14 cents | BEAM short | `[01:01:48]` |
| BEAM trade duration | "not even a one hour trade" | BEAM scalp | `[01:01:48]` |
| RENDER long stop | below ~4.20 | RENDER inverse H&S long | `[01:03:51]` |
| OM support established | 5.45 ("454"/"5:45" ASR) | OM levels | `[01:05:47]` `[01:08:44]` |
| OM short stop (tightened) | 6.20 | OM short | `[01:08:07]` |
| OM breakdown entry TF | 1-hour close; "rejects in 47 minutes" | OM short | `[01:08:07]` |
| OM scalp long entry | ~5.24, stop 5.09 | OM long | `[01:09:17]` |
| Higher timeframes used | weekly, 3-day, daily, 12h, 4h | structure/bias | `[00:02:21]` `[00:26:30]` `[00:29:43]` `[00:44:33]` |
| Lower timeframes used | 4h → 1h ("lower time frame") | entry refinement | `[00:02:21]` `[01:08:07]` |

## 5. Entry model

The setup is identified top-down and the entry is then placed at the *single price where the most objects overlap*. His stated confluence stack is: fib retracement level (golden pocket, or 0.786) + order block / supply-demand zone + SR point + a trend-line touch — "you have your confluence from your swing lows to the most recent high falls perfectly in line with all those fibs. You have your order block and you also have your SR point. So that's the scalp that you take" `[00:20:42]`. Fibs are drawn swing-low→swing-high for shorts/retracement-downs and swing-high→swing-low for longs `[00:01:47]` `[00:02:57]` `[00:31:30]`.

Ordering of entries:
1. **First entry** at the golden pocket / the OB that the golden pocket lands on `[00:03:31]` `[00:23:30]`.
2. **Final DCA** at the 0.786 fib — always deeper than entry 1, and this is his "preferred wick" `[00:03:31]` `[00:04:11]` `[00:22:57]`.
3. For swing shorts he replaces the two-entry model with a **ladder**: start shorting at the first rejection level and ladder up to the ceiling (SOL: ladder to ~260), so average fill sits mid-range `[00:38:08]`.
4. For **breakdown/momentum** entries the ordering inverts: small position on the break, add on the retest `[01:07:34]`.
5. For **post-downtrend reversal** entries: nothing until a break of structure above the last lower high, then buy the first higher low small, and add at the next higher low `[00:48:46]` `[00:49:57]`.
6. Where two depths both look plausible he stacks them: shallower scalp order plus a deeper order, accepting that the first may stop into the second `[00:30:54]`.

He does not enter at market. Setups that are not at price are published as conditional triggers and left to fill `[00:10:03]` `[00:52:38]`.

## 6. Stops

- Stops go **below the wick / below the support that defines the zone** for longs, and **above the wick / above resistance** for shorts `[00:12:41]` `[00:20:42]` `[00:24:38]` `[01:03:02]`.
- **Explicit exception:** never anchor the stop to a capitulation wick — "stops below this wick, not the capitulation wick" `[00:22:57]`; and he refuses to draw the entry from the "cap wick" either `[00:55:25]`.
- Where structure gives no alternative, he accepts the only available level and calls the trade "very risky / very tight" rather than skipping it — ENA: "you have no other stop-loss placement below here... very tight scalp" `[00:17:20]`.
- **Too wide** is defined by position sizing, not by trade rejection: a wide zone means spot or low leverage, not a pass — "plays on spot because it's too wide, unless you go with like low leverage" `[00:15:27]`, "this is a very wide zone, so low leverage" `[00:27:04]`, ENA/other OB "I definitely would try to short, but it's just too wide" → he breaks down to a lower timeframe to tighten it instead `[00:16:02]`, and on FARTCOIN "just a wide OB... let's tighten that up" `[00:42:53]`.
- On OM he keeps a wide stop but pulls it in to a named number: "it's a wide stop loss, but bring it down to maybe 620" `[01:08:07]`. On SOL he does the opposite and *wants* a wider stop for the cycle-top swing `[00:38:08]`.
- Spot positions use a level-close invalidation rather than a price stop: daily close below 15 cents `[00:32:04]`; and "easy invalidation. That's your support" `[01:00:44]`.

## 7. Take profit and trade management

- **Three TPs is the default.** LINK: "final TPs come around here" `[00:13:44]`; ENA: "TP1, TP2 and TP3" `[00:17:20]`; RENDER: "technical targets. TP1 here, TP2, TP3" `[01:04:24]`; OM: "TP1 will be range lows... so like somewhere there, there and then there" `[01:08:44]` `[01:09:17]`.
- TP placement is structural, not R-multiple based: TP1 = nearest range low/high or the first OB, TP2/TP3 = successive SR levels or the swing high `[00:04:11]` (BTC "targeting this high here"), `[01:08:44]`.
- Scalps target the opposite side of the mini-range `[00:16:44]` `[00:40:01]` `[01:09:17]`; swings target the prior cycle structure `[00:07:47]` `[00:38:40]`.
- Position management he does state: cut the whole swing short if the invalidation level flips to support `[00:38:08]`; add to a reversal long only at the next confirmed higher low `[00:49:57]`; add to a breakdown short only on the retest `[01:07:34]`.
- **No stop-loss trailing rule is given anywhere in this session** — there is no "move stop to breakeven on TP1" statement.

## 8. Invalidation and re-entry

- A zone dies by **repetition**: one or two plays off a golden pocket / support are fine, from the third it is expected to fail `[00:26:30]`; the same decay is applied to trend lines and to horizontal support ("getting weaker and weaker every time we touch it") `[00:04:55]` `[00:22:24]` `[00:25:17]`.
- A trend line also dies by **time**: "the longer it takes, the longer the trend line comes down" `[00:08:20]`, and a resting short thesis decays and must be re-assessed rather than left standing `[00:06:38]`.
- Structural invalidation for a bearish thesis: reclaim of the trend line / flip of the key level to support `[00:38:08]` `[00:54:01]` `[01:07:34]`. For a bullish thesis on a spot bag: a daily *close* below the level, wicks below it do not count `[00:32:04]` `[00:48:46]`.
- **Re-entry after a stop-out is explicitly allowed and pre-planned:** "If we get stopped on this one, your other one will trigger and play here until broken" `[00:30:54]`. Same on ETH: "If that one stops out, then we're waiting for these highs to be taken out with the swing failure pattern and then back down" `[00:06:38]` — i.e. the re-entry is a *different* trigger type at a different level, not a repeat of the same order.
- Break of structure resets the whole read: once a higher high is made above the last lower high, downtrend rules stop applying and the higher-low buy model turns on `[00:31:30]` `[00:48:46]`.

## 9. Timeframes

- **Bias / thesis:** weekly and 3-day for the cycle picture (SOL weekly bearish div `[00:35:49]`; BTC dominance "let's start from the weekly and trickle down" `[00:43:59]`; LDO 3-day OB `[00:26:30]`; BNB 3-day trend line `[00:54:01]`).
- **Primary structure:** daily — bearish engulfing candles, support/resistance, "now the daily closes like this" `[00:14:53]`, "here is your next big area on the daily" `[00:17:52]`.
- **Swing / setup:** 4-hour — where he first checks divergences ("do we have any divergences forming? Not on the 4 hour") `[00:02:21]`, and 12h/4h for reversal-pattern closes `[00:29:43]`.
- **Entry refinement:** he repeatedly says "break this down on a lower time frame" before placing anything — BTC `[00:02:21]` `[00:02:57]`, UNI `[00:18:25]`, ENA `[00:16:02]`, LDO `[00:26:30]`, SOL `[00:39:15]`, OM `[01:06:27]`. Explicit LTF entry timeframe named once: the 1-hour breakdown on OM `[01:08:07]`.
- HTF confirmation logic is directional gating, not signal confirmation: HTF trend decides whether he takes the long or the short at the LTF level ("still in a downtrend... we're going to treat it as a downtrend") `[00:04:55]` `[00:18:58]` `[00:39:15]`.
- A too-wide LTF zone is fixed by going lower still: "let me break that down even lower" `[00:16:02]`.

## 10. Confluence

He wants a **stack at one price**, and names the ingredients explicitly on UNI: swing-low→recent-high fib set + order block + SR point, all landing together — "that's the scalp that you take" `[00:20:42]`. On HYPE: "786 fib falls perfectly in line with another trend line touch... this has been your demand zone" and then "we have again order blocks at the same level. Everything points to that area to long" `[00:21:52]` `[00:23:30]`. On LDO: "786 perfectly aligns with this OB down here in the 3-day" `[00:26:30]`. On POPCAT: double bottom + Adam-and-Eve breakout + retest + golden pocket `[00:30:54]` `[00:31:30]`.

Countable confluence types he uses: fib golden pocket, fib 0.786, order block, supply/demand zone, SR point, trend-line touch, range boundary, RSI divergence, candle pattern (engulfing / doji / reversal), chart pattern (flag, wedge, double bottom/top, inverse H&S, triple bottom), liquidity sweep / SFP, and the cross-market gate (BTC, BTC.D, USDT.D, BTC pair).

He does **not** state a minimum count and does **not** state weights. The observed practice is 3–4 aligned objects for a called setup, and "everything points to that area" as the qualitative bar `[00:23:30]`. He does treat cross-market context as a *veto* rather than a weight — all-pairs-at-resistance overrides an otherwise good-looking long `[00:57:03]` `[00:58:46]`.

## 11. Explicitly excluded

- **Memecoins / the meme sector** — "memes have completely died off... I don't think that we see an insurgence in them" `[00:29:10]`; "I think memes are dead" `[00:43:25]`; DOGE "completely killed off" and news-immune `[00:32:44]`. Yet he still calls levels on POPCAT, DOGE and FARTCOIN.
- **Individual coin refusal** — POPCAT: "I wouldn't touch this" `[00:32:04]`; low-volume weekend LDO LTF: "I don't see anything worth touching. Like it's just not clear. There's like no volume" `[00:28:14]`.
- **Shorting strength** — "you know me, I don't like to short strength" `[00:24:03]`.
- **Trading at market** — "I wouldn't take anything at a current market price trade right now" `[00:52:38]`.
- **Alt longs / hold positions while dominance is strong** — "I wouldn't look into getting into hold positions unless you are wanting to add to your spot bags" `[00:46:51]`; "I value shorts more than longs right now" `[00:45:09]`.
- **DCA on this particular BTC trade** — "I'm not going to DCA on this one" even while teaching where the DCA would go `[00:04:11]`.
- **Off-CEX data sources** — asked about all-time lows: "I don't know on dexscreener. I'm not going to go on there" `[00:29:43]`.
- **Shorting an already beaten-down coin** — "shorts risky because this already is a very very beat down coin" `[00:29:43]`.
- **Gaming and AI sectors** — treated as dead narratives, buy-the-demand-zone-only `[01:00:44]` `[01:01:16]`.

## 12. Ambiguities for the bot

**TBOT1-A1** — "Golden pocket" is never numerically defined in this session. Standard is 0.618–0.65, but he never says it; the coder must fix the band. `[00:03:31]`

**TBOT1-A2** — Fib anchor selection is unspecified: he draws "from highs down to lows", "from these lows", "from your swing lows to the most recent high" on different charts. No rule for which swing pair to pick, or on which timeframe. `[00:01:47]` `[00:02:57]` `[00:20:42]` `[00:31:30]`

**TBOT1-A3** — Order block definition is never given mechanically (last opposing candle? consolidation body? wick-to-body?). He points at them visually. `[00:02:57]` `[00:16:02]`

**TBOT1-A4** — "SR point" vs "supply/demand zone" vs "order block" overlap; whether three overlapping objects at one price count as three confluences or one is not stated. `[00:20:42]` `[00:23:30]`

**TBOT1-A5** — No minimum confluence count and no weighting scheme is given. `[00:20:42]`

**TBOT1-A6** — Level-decay touch counting is undefined: what constitutes a "touch" (wick, close, time in zone), and whether the counter resets after a break or after time. He also miscounts aloud on ENA ("one, two, three touches. It's about to be the second touch here"). `[00:16:44]` `[00:26:30]`

**TBOT1-A7** — Position size is only specified once (5–6% of portfolio, SOL swing short). Nothing for scalps, nothing for the "small" breakdown entry, no leverage numbers, no definition of "low leverage". `[00:38:08]` `[00:15:27]` `[01:07:34]`

**TBOT1-A8** — "Too wide" has no threshold — no % of price, no ATR multiple, no max-R. The spot/low-leverage downgrade therefore has no trigger condition. `[00:15:27]` `[00:27:04]`

**TBOT1-A9** — TP allocation is never given: three TPs, but no fraction of position at each. `[00:13:44]` `[00:17:20]` `[01:09:17]`

**TBOT1-A10** — No stop-management rule at all: nothing about moving to breakeven at TP1 or trailing. The bot must decide. (whole session)

**TBOT1-A11** — No R:R minimum is stated. He says "the best R:R you can get" on LINK but gives no number or floor. `[00:11:33]`

**TBOT1-A12** — DCA sizing is undefined: entry-1 vs entry-2 weighting at golden pocket vs 0.786, and whether the stop is sized to the average or to entry 1. `[00:04:11]` `[00:22:57]`

**TBOT1-A13** — Ladder mechanics for swing shorts are undefined: number of rungs, spacing, size per rung. Only the top of the ladder (~260) and the cut level (270) are given. `[00:38:08]`

**TBOT1-A14** — "Below the wick" has no buffer specified. BTC entry 93.5K / stop below 92K implies ~1.5%, but he never generalises it. `[00:04:11]` `[00:22:57]`

**TBOT1-A15** — "Capitulation wick" has no size/volume threshold distinguishing it from an ordinary wick, yet the stop rule depends on that distinction. `[00:08:56]` `[00:22:57]`

**TBOT1-A16** — Trade-duration labels ("about a three-hour trade" `[00:04:11]`, "not even a one hour trade" `[01:01:48]`) are unexplained — expected holding time, or the timeframe to manage on? Not resolvable from context.

**TBOT1-A17** — The "scalp vs swing" classification has no stated criterion; the same chart yields both without a rule for which to take. `[00:12:06]` `[00:13:44]` `[00:27:04]`

**TBOT1-A18** — RSI settings, timeframe and "too oversold" threshold are unspecified — "RSI is just too oversold" is given as a reason not to expect continuation, with no level. `[00:09:30]`

**TBOT1-A19** — The dominance gate is soft: USDT.D "next level comes around 5%" (ASR renders it "5 cents" later), and "strong rejection" is undefined. BTC.D needs a "deviation, come back down, reject trend line" with no measurable definition. `[00:44:33]` `[00:45:42]` `[00:46:51]`

**TBOT1-A20** — The beta-coin gate ("only if ETH does well") has no metric — no correlation window, no threshold move. `[00:24:38]` `[00:27:41]`

**TBOT1-A21** — The all-pairs-at-resistance veto needs "at resistance" to be machine-defined across three charts simultaneously (coin/USDT, coin/BTC, BTC/USDT). `[00:57:03]`

**TBOT1-A22** — The weekend/low-volume filter has no volume threshold and no stated hours; he applies it inconsistently (skips LDO LTF but calls scalps on other coins in the same session). `[00:09:30]` `[00:24:03]` `[00:28:14]`

**TBOT1-A23** — News is used as a discretionary override ("I just don't know what the news will be this week", Trump/tariffs) with no encodable rule. `[00:02:21]` `[00:08:56]`

**TBOT1-A24** — Chart patterns are named but never defined (bear flag, bull flag, falling/rising wedge, Adam & Eve, inverse H&S, triple bottom, U-shape). He even disputes his own bear-flag call by feel: "way too long of a consolidation. It's more of a channel". `[00:21:20]` `[00:30:54]` `[01:01:16]`

**TBOT1-A25** — Several stated prices are unit-ambiguous through ASR: "70 or 93.5" (BTC OB), "454"/"5:45" for OM support, "11.4 cents / 1.14 cents" for BEAM, "$158" for ONDO. A coder must not hard-code these without checking the chart. `[00:03:31]` `[01:01:48]` `[01:05:47]` `[01:08:44]`

## 13. Contradictions

**TBOT1-C1** — *Level decay vs taking the trade anyway.* He states a level is unreliable from the third touch `[00:26:30]` and that supports get "weaker and weaker every single time we touch it" `[00:22:24]`, but then takes the scalp at exactly those levels: ENA after counting touches `[00:16:44]`, HYPE in the same breath as the warning `[00:22:24]`, LDO "every time we've come here, we've seen the bounce, but it's getting weaker" followed by an entry plan `[00:25:17]`. The operative rule in practice appears to be "decay reduces size/conviction", not "decay disqualifies".

**TBOT1-C2** — *"I don't like to short strength" vs shorting impulses.* Stated at `[00:24:03]`, but he then says "any impulse up, any impulse up, I'd be looking to short" on BEAM `[01:00:44]`, calls a short on BNB specifically because it has been "overperforming most coins" `[00:53:14]` `[00:54:01]`, and short-plans every bounce into resistance across the session `[00:04:11]` `[00:12:41]` `[00:52:04]`. The reconcilable version: he shorts strength *into a marked resistance in a downtrend*, not strength in open space — but he never says this.

**TBOT1-C3** — *Stop width.* "Too wide → spot / low leverage only" `[00:15:27]` `[00:27:04]`, and an OB he "definitely would short, but it's just too wide" `[00:16:02]`. Yet on SOL he says "I would want a wider stop" for the cycle-top short `[00:38:08]`, and on OM he takes the trade with an admittedly wide stop after arbitrarily tightening it to 620 `[01:08:07]`. Wide stops are disqualifying for scalps and acceptable for swings — implied, never stated.

**TBOT1-C4** — *Wick handling.* "Stops below this wick, not the capitulation wick" `[00:22:57]` and "I'm not going to take it from that cap wick" `[00:55:25]`, but he also says a capitulation wick "always gets recovered" and plans to bid it — "I'd be waiting to play these wicks" `[00:08:56]` `[00:47:40]` `[00:51:25]`. So the capitulation wick is simultaneously an invalid stop anchor and a valid entry target.

**TBOT1-C5** — *Sector exclusion vs coverage.* "Memes are dead", "I wouldn't touch this" `[00:29:10]` `[00:32:04]` `[00:43:25]`, yet POPCAT, DOGE and FARTCOIN all get full entry/stop/TP plans in the same breath. Same for gaming/AI on BEAM `[01:00:44]`.

**TBOT1-C6** — *DCA taught but declined.* He specifies the DCA level and then opts out on the same trade — "if you want to DCA, I'm not going to DCA on this one, but if you were to DCA, it'd be around the 786 fib" `[00:04:11]`. Similarly on SOL: "ladder all the way to like 260ish. I wouldn't have a DCA there" `[00:38:08]`. The bot cannot tell when a DCA leg is armed and when it is not.

**TBOT1-C7** — *Downtrend continuation vs capitulation recovery.* R2/R23 say downtrend consolidation on support resolves down `[00:01:14]`, while R22 says capitulation wicks always get recovered `[00:08:56]`. On a coin that has just capitulated and is now consolidating on support (SUI `[00:47:40]`), the two rules point opposite ways; he resolves it by feel ("structurally speaking, this wants to go to make a new lower low" `[00:49:57]`).

**TBOT1-C8** — *Weekend filter.* "There's no volume, it's the weekend" is used to refuse LDO `[00:28:14]` and to caution generally `[00:09:30]`, but he still issues live scalps on other coins in the same session, and on HYPE explicitly says "if you want to long and you're okay with the weekend volume, then this is the area to play the scalp" `[00:24:03]` — turning the filter into a user preference rather than a rule.

**TBOT1-C9** — *Bear flag on HYPE.* He rejects the bear-flag read — "I want to say no because it's way too long of a consolidation. It's more of a channel" `[00:21:20]` — then a minute later says "it isn't on a bear flag here" while trading the pattern's implied breakdown `[00:23:30]`. Pattern classification is not stable within the session.

**TBOT1-C10** — *Predicted for other sessions:* the BTC long plan at `[00:03:31]`–`[00:04:11]` is a counter-trend long inside a downtrend he insists on treating as a downtrend `[00:04:55]`. If other sessions teach "only trade with the HTF trend", this session contradicts it: he trades the counter-trend leg to the range high and then re-shorts.

## 14. Observed decision procedure

The order he actually follows, reconstructed from the repeated pass over ~20 charts (BTC `[00:00:01]`–`[00:05:26]`, ETH `[00:05:26]`–`[00:10:03]`, HYPE `[00:21:20]`–`[00:24:38]`, SOL `[00:35:15]`–`[00:40:48]`, SUI `[00:47:40]`–`[00:49:57]`, OM `[01:05:13]`–`[01:10:03]`):

1. **Open the highest relevant timeframe and clear the chart.** "Let's get a clean chart" `[00:00:01]`; "let's start from the weekly and trickle down" `[00:43:59]`.
2. **Name the trend in one word.** "Downtrend here" `[00:02:21]`, "trend is down, right" `[00:18:58]`, "still in a downtrend" `[00:39:15]`. Everything after this is filtered by that word.
3. **Draw the trend line / channel and ask whether it is intact, and how tired it is.** How many touches, how long the consolidation on it, whether it has already been broken and retested `[00:00:33]` `[00:01:14]` `[00:08:20]` `[00:18:25]` `[00:22:24]`.
4. **Mark the crucial horizontal levels** — the one that must hold, and the one that must be reclaimed to change the bias. "A very crucial level to get above... 106ish" `[00:01:47]`; "very very important level to hold here" `[00:14:20]`; "I'm not bullish until this 3K level is reclaimed" `[00:07:09]`.
5. **Mark the liquidity** — internal highs/lows and swing extremes price will go and sweep. "We have two areas of liquidity that we can sweep" `[00:01:14]`; "hopefully we sweep them, come back, and then we reject" `[00:06:04]`; `[00:52:38]`.
6. **Mark order blocks and supply/demand zones**, including how they formed. "This order block here either holds" `[00:02:57]`; "whenever we get a huge move down and then we start consolidating up it creates the supply zone" `[00:14:53]`; `[00:39:15]`.
7. **Draw the fibs and check where the golden pocket and 0.786 land.** "If we were to draw fibs from these lows..." `[00:02:57]`; "draw your fibs. Okay. 786 fib falls perfectly in line with another trend line touch" `[00:21:52]`; `[00:25:59]`.
8. **Check whether those objects overlap at one price — the confluence test.** "You have your confluence... falls perfectly in line with all those fibs. You have your order block and you also have your SR point" `[00:20:42]`; "everything points to that area to long" `[00:23:30]`.
9. **Read the candles and the pattern.** Bearish engulfing / doji / capitulation wick / reversal close, plus flag, wedge, double bottom, inverse H&S. "Now the daily closes like this... then we have a bearish engulfing candle" `[00:14:53]`; `[00:29:43]` `[00:30:54]` `[01:05:47]`.
10. **Check RSI divergence** (and only then oversold/overbought). "Do we have any divergences forming? Not on the 4 hour" `[00:02:21]`; "you had price making lower lows while RSI was making higher lows" `[00:41:38]`; "you have a bearish div. This probably goes down" `[01:06:59]`.
11. **Drop to the lower timeframe to refine.** Said on nearly every chart: "we have to break this down on a lower time frame" `[00:02:21]` `[00:16:02]` `[00:18:25]` `[00:26:30]` `[00:39:15]` `[01:06:27]`.
12. **Read LTF market structure for the trigger** — lower highs/lower lows still intact, or a break of structure and a higher low forming. "Theoretically, we just made another lower high. So we should go and make another lower low" `[00:18:58]`; "higher high has been made. This was your last higher low... we have a break of structure" `[00:31:30]`; `[00:48:46]`.
13. **Pick the play type from what's left**: range trade / scalp / swing / conditional. Frequently he lists all of them off one chart — "so three separate plays" `[00:13:44]`, "three separate shorts" `[00:24:38]`.
14. **Place entry, then stop, then TPs, in that order.** "Entry around 21.28... 786 fib, stops below this wick, not the capitulation wick. And then... we target these highs" `[00:22:57]`; "scalp long 524ish. Stop loss 509 target back to range highs and TP at level of resistance" `[01:09:17]`.
15. **Measure the stop width and let it set the vehicle**: normal leverage, low leverage, or spot only. "Stops below support area, plays on spot because it's too wide unless you go with like low leverage" `[00:15:27]`; "this is a very wide zone, so low leverage" `[00:27:04]`.
16. **Apply the external gates last, as a veto** — BTC's own position, BTC dominance and USDT dominance, the coin's BTC pair, beta relationships, news, and weekend volume. "If Bitcoin breaks down this week, this will break down" `[00:52:38]`; "when the BTC pairing's at resistance, the USDT pairing's at resistance, also a trend line. If Bitcoin goes down, this chart nukes hard" `[00:57:03]`; "you can't really play it until ETH does well" `[00:27:41]`; "I'd be pretty risk off on alts until we see a strong rejection around 5[%]" `[00:46:51]`.
17. **If it does not pass, do nothing and post a conditional instead** — never enter at market. "This is your conditional trigger" `[00:10:03]`; "I wouldn't take anything at a current market price trade right now" `[00:52:38]`; "so I'm going to post this in chats" `[00:05:26]` `[00:11:33]` `[00:28:14]` `[00:57:35]`.
