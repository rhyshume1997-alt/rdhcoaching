# S6 — Order blocks in depth, plus Fibonacci retracements/extensions and where they rank in confluence

Source: transcripts/S6.md  |  Runtime covered: 00:00:01 to 02:04:25

> ASR note: this transcript is auto-captioned. Corrections applied throughout: "FIPS"/"fips"/"pip" → fibs/fib; "ECA" → DCA; "or black" → order block; "3.82"/"382" → 0.382; "618/66/786/886" → 0.618/0.66/0.786/0.886; "bare flag" → bear flag; "Ono"/"Onondo" → ONDO; "sole meme coins" → Solana meme coins; "rugps" → rug pulls; "DEN" → degen; "Python" → PYTH; "9633"/"96 33" → $0.9633; "south low" → range low; "SR point" is his own term (a broken support/resistance level that has flipped role) and is kept verbatim.

## 1. Scope

This session does two things. First, it defines the order block precisely (a single candle — the last opposite-colour candle before a directional change) and separates it from his personal, non-textbook definitions of supply and demand zones, then works through ~15 live/replay examples of entry, DCA laddering, position sizing to a fixed portfolio-loss budget, stop placement, TP placement, invalidation by 50% fill, and re-entry after a stop-out. Second, it covers Fibonacci: which levels he considers back-tested and tradeable (the golden pocket 0.618–0.66 and the 0.786), how bullish vs bearish fibs are drawn, when trend-based fib extensions are used (price discovery only), and where fibs sit in his confluence hierarchy — explicitly below support/resistance and supply/demand. The session also states his full chart-preparation order of operations, which is the most directly codeable thing in it.

## 2. Definitions

- **Bearish order block (OB)** — the last green candle before a directional change in price (i.e. before price turns down). `[00:29:51]`
- **Bullish order block (OB)** — the last red candle before a directional change in price (i.e. before price turns up). `[00:30:27]` `[00:32:04]`
- **Order block, cardinality** — an order block is ONE candle only. Never two. It may sit inside a larger consolidation/zone, but the order block itself is a single candle. `[00:58:23]` `[01:00:05]`
- **Supply zone (textbook)** — price goes up, consolidates horizontally, then goes down (a reversal zone). Bearish order blocks are supply zones by the textbook definition. `[00:30:59]` `[00:58:57]`
- **Supply zone (HIS definition — deliberately different)** — price comes DOWN, consolidates horizontally, then continues DOWN, with a sufficient gap in price away from the consolidation. A continuation zone, not a reversal zone. `[00:32:04]` `[00:35:39]` `[01:34:52]`
- **Demand zone (textbook)** — price comes down, consolidates, then goes up (a reversal zone). `[00:32:38]` `[00:36:48]`
- **Demand zone (HIS definition — deliberately different)** — price goes UP, consolidates horizontally, then continues UP, creating a sufficient gap in price from the breakout point. "Price is not coming down, it's going up." `[00:33:13]`
- **SR point** — a level that broke and flipped role: price closed through it, and it is retested from the other side. A resistance that price closed below becomes a confirmed resistance; a resistance broken and reclaimed becomes support. `[00:04:36]` `[00:14:20]` `[00:42:25]`
- **Untested SR** — an SR point that has flipped role but has not yet been retested. Expected to give the cleanest reaction. `[00:16:41]` `[00:17:51]`
- **50% fill** — price trading through half of the zone's depth. His marker for the zone being consumed / liquidity grabbed. `[00:02:50]` `[00:48:43]`
- **Golden pocket** — the band between the 0.618 and the 0.66 fib. He uses 0.66, not the commonly cited 0.65, on his old mentor's instruction and his own back-testing. `[01:26:22]` `[01:40:01]`
- **Bullish fibs** — a fib retracement drawn from a swing LOW up to a swing HIGH; the levels are potential BOUNCE points, used to plan longs. `[01:20:33]` `[01:21:41]` `[01:22:15]`
- **Bearish fibs** — a fib retracement drawn from a swing HIGH down to a swing LOW; the levels are potential REJECTION points, used to plan shorts. `[01:23:28]`
- **Trend-based fib extension** — used only when a coin is in price discovery, to project take-profit levels where no historical resistance exists. `[01:17:45]` `[01:45:16]`
- **Price discovery** — coin trading above all prior all-time highs, so no true resistance exists; extension levels are "just possible rejection points". `[01:46:22]`
- **Beta coin** — a coin whose price is driven by a major regardless of its own technicals. ETH betas named: OP, LDO, ENS. SOL betas named: JTO, JUP, PYTH. `[00:25:18]` `[00:25:51]`
- **Quasimodo** — requires a higher-high / higher-low structure that then breaks; cannot exist in a pure downtrend of lower highs and lower lows. `[00:20:03]`
- **Downtrend** — lower lows and lower highs; remains a downtrend "until proven otherwise" (until that structure breaks). `[00:04:36]`
- **Break of structure** — price trading above the last lower high (his 15m ONDO example), then making a higher low. `[00:05:12]` (fuller treatment deferred to the next session)

## 3. Hard rules

**S6-R1 — Bearish order block identification.** Mark the last green candle before a directional change down as a bearish order block.
`params:` exactly 1 candle; colour = green (close > open); direction change = down
`[00:29:51]` `[01:00:05]`

**S6-R2 — Bullish order block identification.** Mark the last red candle before a directional change up as a bullish order block.
`params:` exactly 1 candle; colour = red (close < open); direction change = up
`[00:30:27]` `[00:32:04]`

**S6-R3 — An order block is never more than one candle.** Asked directly whether an OB requires two candles minimum, he says no: "order blocks don't have two candles… technically you only have one candle, and that is your order block."
`params:` candle_count = 1
`[00:58:23]` `[01:00:05]`

**S6-R4 — HIS supply zone is a continuation pattern.** Zone qualifies when price moves down, consolidates horizontally, then continues down away from the consolidation.
`params:` direction_in = down; direction_out = down; requires horizontal consolidation + gap in price
`[00:32:04]` `[00:35:39]`

**S6-R5 — HIS demand zone is a continuation pattern.** Zone qualifies when price moves up, consolidates horizontally, then continues up, creating a sufficient gap from the breakout point.
`params:` direction_in = up; direction_out = up; requires horizontal consolidation + gap from breakout
`[00:33:13]`

**S6-R6 — Zone strength scales with consolidation candle count.** "More candles, the stronger the zone will be."
`params:` strength ∝ candle count in consolidation
`[00:33:13]` `[00:24:13]`

**S6-R7 — Zone strength scales with timeframe.** "Higher the time frame, the stronger the zone will be" / "the lower the time frame, the weaker it's going to be."
`params:` strength ∝ timeframe; 15m SR gave only ~1% bounce
`[00:33:48]` `[00:24:46]` `[00:56:03]`

**S6-R8 — Zone strength scales with the size of the move away from the zone.** "Stronger the move away, stronger it's going to be."
`params:` a 2% move away = weak, scalp-only; 5% move called "a lot"; 26–27% move away used to justify a swing short
`[00:04:03]` `[00:08:04]` `[00:45:16]`

**S6-R9 — Zone/OB boundary: include the wick if it is small, use the candle body if the wick is large.** "The wick is very small… you can include the top wick. But the bottom I'm going to use the candle body."
`params:` no numeric wick threshold given; example of a rejected wick = $0.60 on LINK
`[00:53:12]` `[00:53:46]` `[00:54:22]` `[00:02:15]`

**S6-R10 — A zone is dead once it has been ~50% filled.** "That's why I don't play setups after that 50% fill." Corollary: a zone that has NOT reached 50% fill may be traded again — and repeatedly. In the LINK example the same supply zone was tradeable three separate times because the first two touches did not reach 50%.
`params:` fill_threshold = 50% of zone depth; max re-takes observed = 3
`[00:02:50]` `[00:48:43]` `[00:52:38]` `[00:46:22]`

**S6-R11 — Maximum loss per trade is 4–5% of portfolio if the stop is hit; 5% is the hard cap.** Sizing is solved backwards from this: pick quantities such that (stop − average entry) × total size ≤ 5% of portfolio.
`params:` 4–5% of portfolio, 5% max; on a $1,000 portfolio = $40–$55, "$55 max"
`[00:10:53]` `[00:11:27]` `[00:41:15]` `[00:41:51]` `[00:44:04]`

**S6-R12 — Position size is solved by iteration against R11.** Worked ONDO short: 15 + 25 coins → stop loss = $114 = 11.4% → rejected; 8 + 15 = 23 coins → $65.50 = 6.5% → still rejected; 7 + 12 = 19 coins → $54 ≈ 5.4% → accepted.
`params:` avg entry 38.38, stop 41.23, per-coin loss 2.85; accepted config 7 + 12 coins
`[00:09:41]` `[00:10:20]` `[00:10:53]` `[00:11:27]`

**S6-R13 — Ladder DCAs with increasing size so the average sits nearer the final DCA.** LINK short: 35 / 55 / 100 units at 17.28 / 17.858 / 18.181 → average 17.921, explicitly noted as "closer to the last DCA point." Earlier ONDO example also had the heavier bids higher: "because we have our heavier bids up here, the average would be closer to the heavier bids."
`params:` example ratio 35 : 55 : 100; average lands near final DCA
`[00:39:23]` `[00:40:05]` `[00:13:47]`

**S6-R14 — Entry goes at the SR / resistance level; the DCA goes at the next level; the final DCA goes at the top (short) or bottom (long) of the zone.** "My entry is always going to be an SR point or a resistance point." "Entry at SR, probably DCA here at the top, give yourself some room for error."
`params:` short example — entry 17.28 (OB/SR), DCA 17.858 (prior support now resistance), final DCA 18.181 (top of zone)
`[00:05:12]` `[00:38:49]` `[01:57:29]`

**S6-R15 — The 0.786 fib is the standard DCA level.** "The 786 fib is usually my DCA point."
`params:` 0.786
`[01:57:29]` `[01:29:56]` `[01:35:26]`

**S6-R16 — DCA count is 1 by default, occasionally 2, and 0 when the zone/range is tight.** "One entry and one DCA." "This is in a range where you do not have a DCA." "I would only have one DCA here, not two."
`params:` DCA count ∈ {0, 1, 2}
`[00:09:08]` `[00:23:05]` `[01:11:20]`

**S6-R17 — Stop goes beyond the far side of the zone: above the zone/wick for shorts, below the support/zone for longs.**
`params:` example stops — 18.456 (above LINK supply zone), "stops above the wick", "stops below support"
`[00:36:14]` `[00:38:49]` `[00:41:51]` `[00:54:56]`

**S6-R18 — Do not place the stop above/below an oversized wick; use the candle body instead.** "I'm not going to place it above the wick. That is a 60 cent wick. So I'm going to place it here."
`params:` rejected wick size = $0.60 (LINK, ~$17–18 price, i.e. ~3.4% of price)
`[00:36:14]`

**S6-R19 — A stop that lands inside another support/demand area is a bad stop.** On ETH 1H: "if I place it here below this wick, it's basically in another support area / demand zone… so stop-loss placement is very, very hard." His fix was to tighten the stop and move the DCA rather than widen it.
`params:` no numeric threshold
`[01:11:53]` `[01:12:28]`

**S6-R20 — Take profits are placed at support/resistance (SR) levels, not at fixed R multiples.** TP1 and TP2 are the next two S/R levels in the trade's direction.
`params:` 2 TPs shown in every worked example
`[00:14:20]` `[00:17:16]` `[00:45:49]`

**S6-R21 — When TP2 is hit, move the stop loss to TP1 or to break-even.** "There's your TP2. At that point, you move your stop loss to TP1 or break even."
`params:` trigger = TP2 hit; new stop = TP1 price or entry average
`[00:45:49]`

**S6-R22 — Exit at break-even if the trade does not react immediately after entry / if the level that justified the trade is lost.** "If I'm still in this trade and we're not getting a nice immediate reaction, I'm getting out break even."
`params:` no time or price threshold given
`[01:13:03]` `[01:13:38]`

**S6-R23 — Exit a short if the level you shorted flips into support.** "If we flip this into support and we are consolidating here… maybe you get out of the trade, because if it's flipping into support, it's going to look like a giant deviation and back into the range."
`[01:15:24]`

**S6-R24 — Re-entry after a stop-out is permitted if price closes back above the support (long) that was lost.** In the LINK long: stopped out on a wick, then "we closed above here… so if we closed above support you could have re-entered with same [setup]." Setup declared still valid because support held and a double bottom formed.
`params:` requires a candle CLOSE back above the level; original stop then re-placed below the new wick
`[00:43:29]` `[00:44:04]`

**S6-R25 — The same zone may be re-taken as long as R10 (50% fill) has not triggered.** "Is this valid if we get it again? Yes, it's still valid."
`[00:49:49]` `[00:52:38]`

**S6-R26 — Reduce position size to ~1/3 of normal (max loss ~1.5% instead of 4–5%) when price action is unclear or support looks weak.** "If I take the trade, I probably go in with maybe one third of normal size… I'm only going to lose max like 1.5%. If you're never sure of the price action, lower your position size."
`params:` size multiplier = 1/3; loss budget 1.5%
`[00:52:00]`

**S6-R27 — On a wick-heavy chart, enter light (20–30% of the position) at the area of interest and place heavier bids at the deeper support.**
`params:` 20–30% first tranche
`[01:55:08]`

**S6-R28 — Chart preparation / confluence order of operations.** (1) Clear the chart completely. (2) Start on a higher timeframe. (3) Plot support and resistance — this includes SR points and trend lines ("trend lines are just diagonal support and resistances"). (4) Plot supply and demand zones. (5) Indicators — BTC dominance if trading alts, USDT dominance if trading majors only, DXY. (6) Fibs. (7) Patterns.
`params:` fixed sequence; "support and resistance is first. Always."
`[01:03:00]` `[01:03:33]` `[01:04:09]` `[01:08:09]` `[01:56:54]`

**S6-R29 — Never take a trade on an order block alone; an OB requires confluence.** "I don't take trades based off OBs alone. I need confluence." He passes on a 15m OB explicitly because "there's no confluence here. Just the order block."
`[00:45:16]` `[00:55:31]` `[01:00:44]`

**S6-R30 — Never trade fibs alone.** "You don't want to necessarily just rely on fibs alone… it's not enough." Fibs must tie to an S/R level, a zone, or an OB.
`[01:58:15]` `[01:58:49]`

**S6-R31 — When two candidate zones compete, take the one with more confluences.** He picks the ONDO zone that also has resistance + supply zone + golden pocket over one with fewer. He picks the more-consolidated demand zone over the order block inside it. He picks a $20–30-wide ETH supply zone over a $10-wide one.
`params:` examples of 3 and 4 stacked confluences; no stated minimum count
`[00:18:25]` `[01:07:32]` `[01:14:12]` `[01:00:44]`

**S6-R32 — Only two fib levels are treated as tradeable: the golden pocket (0.618–0.66) and the 0.786.** "There's only two of them that I've back tested that I found to be very accurate… the golden pocket… and the 786 fib. These two have the highest reversal points."
`params:` 0.618, 0.66, 0.786
`[01:26:22]` `[01:31:02]` `[01:40:37]`

**S6-R33 — Recommended fib setting list is five levels; he personally uses the middle three.** Listed descending: 0.886, 0.786, 0.66, 0.618, 0.236. "If you want to have five fib settings, just those. I use the three middle ones."
`params:` full set {0.236, 0.618, 0.66, 0.786, 0.886}; his set {0.618, 0.66, 0.786}
`[01:41:14]` `[01:41:52]`

**S6-R34 — Bullish fibs are drawn swing low → swing high and used to find bounces (longs).**
`[01:20:33]` `[01:21:06]` `[01:22:15]` `[01:42:57]`

**S6-R35 — Bearish fibs are drawn swing high → swing low and used to find rejections (shorts).**
`[01:23:28]` `[01:42:57]` `[01:49:49]`

**S6-R36 — Trend-based fib extensions are used only when a coin is in price discovery, and are drawn swing low → swing high (the all-time high) → dragged down to the newly created swing low.** The resulting levels become TP1…TP5.
`params:` 3 clicks: swing low, swing high/ATH, new swing low; use ALL fib levels here, not just GP/0.786
`[01:17:45]` `[01:45:16]` `[01:45:48]` `[01:47:29]` `[01:48:40]`

**S6-R37 — Never short a coin in price discovery.** "When a coin goes into price discovery, please don't short it. Even if you find fibs, please don't short it, because there's no true resistance."
`[01:46:22]`

**S6-R38 — When fibs disagree with drawn S/R, S/R wins.** "Everything is noise when there are support and resistance lines already drawn." "Did I really need fibs to tell me that when I have my support and resistance lines? No."
`[01:18:56]` `[02:03:52]` `[01:39:27]`

**S6-R39 — An untested SR point is the strongest rejection candidate; a second touch of a confirmed level is still valid but weaker.** "You have an untested SR point which should give you a nice rejection… an untested SR is going to give you a nice rejection." The second resistance touch is called "still valid."
`[00:16:41]` `[00:17:16]` `[00:17:51]`

**S6-R40 — Multiple touches of the same support weaken it.** "We've touched this demand zone so many times, this support line so many times. This is a weak weak support area. We've had multiple touches."
`params:` no touch-count threshold
`[00:50:56]` `[01:55:46]`

**S6-R41 — Gate an altcoin trade on its BTC pairing.** Check the ALT/BTC chart to judge relative strength; if the BTC pairing looks strong, do not expect the deep pullback you are bidding for.
`[00:27:36]` `[00:28:10]` `[00:28:43]`

**S6-R42 — Beta coins override their own technicals.** ETH betas (OP, LDO, ENS) and SOL betas (JTO, JUP, PYTH) follow the major: "it doesn't matter how good the technical setup was. If ETH plummeted, this coin would plummet as well."
`params:` observed same-day: SOL +6%, JTO +15% vs ETH −6%, OP −8%, LDO −8%
`[00:25:18]` `[00:25:51]` `[00:26:27]` `[00:27:04]`

**S6-R43 — Trade the perp chart when trading perps.** He calls using a spot chart for a perp setup "my first mistake" because the wicks differ, which changes fills and stops.
`[00:12:33]` `[00:16:01]`

**S6-R44 — Newly listed coins: spot only, not leverage.** "If you're looking to buy a coin that's newly listed, please start out with spot first. Leverage is going to be very, very hard."
`[01:50:23]`

**S6-R45 — Illiquid / thin-orderbook coins: spot only, not leverage.** Applied to ENS-style wick-heavy charts and to low-cap memecoins: "don't trade them on leverage. They're very illiquid. They could easily destroy you. Trade them on spot."
`params:` example wicks — 10% on a 5m candle, 15% on a 4H candle
`[00:24:13]` `[02:01:05]` `[02:01:38]`

**S6-R46 — If no qualifying zone exists, do not force one; skip the coin.** "If you can't find any, don't try to force it… because they've all been played out." "For me, I just move on. Tough coin right now. Focus on coins that have volatility and strength."
`[00:03:23]` `[00:51:28]` `[01:56:18]`

**S6-R47 — Chart inversion check.** Right-click the y-axis → invert scale, to reveal patterns and zones hidden in the normal orientation. Used as a routine step.
`[01:06:26]` `[01:06:59]` `[01:52:09]`

**S6-R48 — Reject an order block or zone that is too small in absolute price terms.** "This one way too tiny. I would not play that at all. It's literally like $100." On ETH 1H he rejects a ~$10-wide supply zone in favour of a ~$20–30-wide one. On ENS he calls a $0.30 OB "a weak order block."
`params:` rejected: ~$100 wide OB, ~$10 wide ETH supply zone, $0.30 ENS OB; accepted: $20–30 ETH supply zone
`[00:58:57]` `[01:14:12]` `[00:23:39]`

**S6-R49 — Downtrend persists until structure breaks.** Lower lows and lower highs = downtrend "until proven otherwise"; a downtrend produces more supply zones than demand zones, so bias short.
`[00:03:23]` `[00:04:36]`

**S6-R50 — Quasimodo requires an uptrend structure first.** No higher high / higher low sequence → no quasimodo, regardless of what else the chart shows.
`[00:20:03]` `[00:20:36]`

## 4. Parameters and thresholds

| parameter | value | applies to | timestamp |
|---|---|---|---|
| Order block candle count | exactly 1 | OB definition | `[00:58:23]` `[01:00:05]` |
| Zone invalidation fill | 50% of zone depth | all zones and OBs | `[00:02:50]` `[00:48:43]` `[00:52:38]` |
| Max re-takes of one zone (observed) | 3 | LINK supply zone example | `[00:52:38]` |
| Max portfolio loss per trade | 4–5%, 5% hard cap | position sizing | `[00:11:27]` `[00:41:15]` |
| Max loss in $ on $1,000 portfolio | $40–$55, "$55 max" | position sizing | `[00:41:51]` `[00:44:04]` |
| Rejected sizing #1 (ONDO) | 15 + 25 coins → $114 loss = 11.4% | position sizing | `[00:10:53]` |
| Rejected sizing #2 (ONDO) | 8 + 15 coins → $65.50 = 6.5% | position sizing | `[00:11:27]` |
| Accepted sizing (ONDO) | 7 + 12 coins → $54 ≈ 5.4% | position sizing | `[00:11:27]` |
| ONDO worked example prices | entry 35.551 / DCA 40.11 / avg 38.38 / stop 41.23; per-coin loss 2.85 | short example | `[00:09:41]` `[00:10:20]` |
| ONDO alt example | entry 35.647, DCA 39.786, stop ~$5.70 wide ("pretty wide") | short example | `[00:08:04]` `[00:12:33]` |
| LINK ladder prices | 17.28 / 17.858 / 18.181 | 3-leg short entry | `[00:38:49]` |
| LINK ladder sizes | 35 / 55 / 100 units | DCA weighting | `[00:39:23]` |
| LINK average entry | 17.921 (closer to final DCA) | DCA weighting | `[00:40:05]` |
| LINK $ per $1 move | $190 | P&L math | `[00:40:40]` |
| LINK stop | 18.456; 0.535 × 190 = $101 = 10% of $1,000 — "too high" (left unfixed) | position sizing | `[00:40:40]` `[00:41:15]` |
| LINK long re-entry loss | $0.96 per coin | stop-out example | `[00:43:29]` `[00:44:04]` |
| LINK long realised (entry only) | 90 coins; $2.36 move = ~$70 | P&L math | `[00:47:31]` |
| LINK long realised (entry + DCA) | avg 17.63, 90.74 coins, $66.60 | P&L math | `[00:48:10]` |
| Reduced size when unsure | 1/3 of normal → max loss ~1.5% | position sizing | `[00:52:00]` |
| Light first tranche on wicky charts | 20–30% of position | position sizing | `[01:55:08]` |
| ONDO 15m stop width | ~3% ("very tight stop") | stop sizing | `[00:05:12]` `[00:04:03]` |
| Rejected wick for stop placement | $0.60 on LINK (~3.4% of price) | stop placement | `[00:36:14]` |
| Weak move-away | 2% | zone strength | `[00:04:03]` |
| Strong move-away examples | 5% (called "a lot"), 7%, 9%, 10–11%, 26–27%, 50% (spot hold) | zone strength / targets | `[00:45:16]` `[00:13:47]` `[00:50:23]` `[00:49:49]` `[00:08:04]` `[00:57:49]` |
| ENS no-DCA move | 5.2% | scalp example | `[00:23:39]` |
| ENS OB width (weak) | $0.30 / "20 cents" risk | zone size floor | `[00:23:39]` |
| Rejected OB size | ~$100 wide "way too tiny" | zone size floor | `[00:58:57]` |
| ETH 1H supply zone comparison | reject $10 wide, take $20–30 wide | zone selection | `[01:14:12]` |
| 15m SR bounce magnitude | ~1% | timeframe strength | `[00:56:03]` |
| 1H scalp magnitudes | 0.5%–1% | timeframe strength | `[01:12:28]` `[01:28:12]` |
| Leverage multiplier example | 7% move = 70% of margin at 10x, 140% at 20x | leverage math | `[00:13:47]` |
| Plays available from one 15m range | 7 | range trading | `[00:54:56]` |
| Golden pocket | 0.618 to 0.66 (he uses 0.66; notes others use 0.65) | fibs | `[01:26:22]` `[01:40:01]` |
| Primary reversal fib | 0.786 ("my favourite fib", usual DCA point) | fibs | `[01:26:22]` `[01:57:29]` `[01:58:15]` |
| Recommended 5-level fib set | 0.236, 0.618, 0.66, 0.786, 0.886 | fib settings | `[01:41:14]` `[01:41:52]` |
| Levels he actually uses | the middle three: 0.618, 0.66, 0.786 | fib settings | `[01:41:52]` |
| 0.886 status | "a really cool one", "a lot of people live and die by it" — but he has NOT back-tested it | fib settings | `[01:38:17]` |
| Fib levels he calls made-up noise | 0.113, 0.114, 0.13, 0.15, 2.14 (and 2.36 he likes but doesn't use) | fib settings | `[01:37:07]` `[01:37:42]` `[01:41:52]` |
| Pure retracement levels "technically" | 0, 0.5, 1 (range low / mid / high) | fibs | `[01:38:17]` |
| ONDO 2H fib target | 0.786 at $0.906 | fib example | `[01:53:26]` |
| ETH golden pocket example | 3488–3493 | fib example | `[01:33:05]` |
| Price-discovery extension TPs | TP1–TP5 from all extension levels; rejections shown at GP, 0.786, 1.0, 1.23 | price discovery | `[01:45:48]` `[01:47:29]` |
| Only indicator he uses | 200 EMA, daily only, and only sometimes | indicators | `[01:09:27]` |
| Same-day beta divergence | SOL +6%, JTO +15%, BTC −3.25%, ETH −6%, OP −8%, LDO −8% | beta coins | `[00:25:51]` `[00:26:27]` `[00:27:04]` |
| Memecoin wick sizes | 10% on a 5m candle, 15% on a 4H candle | liquidity filter | `[02:01:05]` `[02:02:44]` |
| His primary trading timeframe | 4H, plus spot | timeframes | `[00:57:15]` |
| Scalp timeframes | under 4H (2H, 1H, 15m, 5m, 3m) | timeframes | `[01:52:43]` `[00:57:15]` `[01:50:23]` |
| Swing timeframes referenced | 3-day, daily, 12H, 8H, 4H | timeframes | `[00:02:15]` `[00:02:50]` `[00:41:15]` `[01:54:34]` |
| TP count per trade | 2 (TP1, TP2) in every worked example | trade management | `[00:17:16]` `[00:45:49]` |

## 5. Entry model

**Setup identification (in the order he runs it, per S6-R28):**
1. Clear chart, start on a high timeframe.
2. Draw support/resistance, including SR points (broken-and-flipped levels) and trend lines.
3. Draw supply/demand zones — both his continuation definition and the textbook reversal definition are traded.
4. Locate the order block: the single last-green candle before a down-move (bearish) or last-red candle before an up-move (bullish). The OB frequently sits *inside* a larger zone; that stacking is itself a confluence.
5. Check indicators (BTC.D for alts, USDT.D for majors, DXY).
6. Draw fibs — bullish (swing low → swing high) if looking for longs, bearish (swing high → swing low) if looking for shorts — and check whether the golden pocket or 0.786 lands on an already-drawn level.
7. Check patterns.
8. Reject the setup if the zone is ≥50% filled (S6-R10), too small in absolute terms (S6-R48), or backed only by an OB or only by fibs (S6-R29, S6-R30).

**Order placement (short, the fully worked LINK example at `[00:38:49]`–`[00:40:05]`):**
- **Entry (first fill, smallest size):** at the SR / resistance level, or at the order block. Price 17.28, size 35. "My entry is always going to be an SR point or a resistance point." `[01:57:29]`
- **DCA 1 (middle size):** at the next level up — in this case a prior support that was lost and never reclaimed, therefore still resistance. Price 17.858, size 55.
- **DCA 2 / final DCA (largest size):** at the top of the supply zone. Price 18.181, size 100.
- **Resulting average:** 17.921 — deliberately weighted toward the final DCA so that the position's break-even sits near the top of the zone.

**Long variant (`[00:41:51]`, `[01:27:00]`):** entry at the bullish order block / the level that flipped to support; DCA at the next support down or at the 0.786 fib; stop below. In the fib-confluence long he states the sequence explicitly: "I'm going to start my entries at the OB, which we have now flipped to support. I'm going to have my DCA down here. I'm going to have my stop loss here. And I'm going to target the range high."

**Sizing:** quantities are not chosen first — they are solved so that (stop − average entry) × total size ≤ 4–5% of portfolio (S6-R11/R12). He iterates candidate quantity pairs until the loss figure lands in budget.

**DCA count:** default 1 DCA; 2 DCAs allowed when the zone is deep; 0 DCAs when the range/zone is tight and there is nowhere to put one (`[00:23:05]`, `[01:11:20]`).

**Fib overlay on entries:** the 0.786 is the standard DCA level; the golden pocket may hold either the entry or a DCA depending on where it lands relative to the SR level. In the ETH short at `[01:29:56]` the stack is: entry at the supply zone, DCA at the golden pocket / an order block, final DCA at the 0.786, stop above the supply zone.

## 6. Stops

- **Placement:** beyond the far edge of the zone — above the supply zone / OB for shorts, below the support / demand zone for longs (`[00:36:14]`, `[00:38:49]`, `[00:41:51]`, `[00:54:56]`).
- **Wick handling:** do not place the stop beyond an oversized wick. On LINK he refuses to place a stop above a $0.60 wick and places it at the candle body instead (`[00:36:14]`). Same logic as the zone-boundary rule (S6-R9): small wick → include it; large wick → use the body.
- **What makes a stop bad:**
  - It lands inside another support/demand area — "stop-loss placement is very, very hard… it's basically in another support area / demand zone" (`[01:11:53]`). His remedy is to move the DCA and tighten the stop, not to widen it.
  - It is too wide relative to the position: a $5.70 stop off a $35.55 entry (≈16%) is called "a pretty wide stop" (`[00:08:04]`).
  - It forces a position size that breaches the 4–5% loss budget — this is the operative constraint, not stop width in isolation (`[00:11:27]`).
  - Wicky, illiquid charts make stops unusable at all: "these can easily go above your invalidation points with a quick wick" (`[02:01:38]`), "this wick makes it very hard to place stop losses" (`[01:54:34]`).
- **Tight stops are acceptable:** the ONDO 15m scalp uses "a very very tight stop" of ~3% (`[00:04:03]`, `[00:05:12]`).
- **Spot exception:** on spot he runs no stop loss at all — "This is why I do spot. You have no stop loss. The wicks don't matter" (`[00:43:29]`). Spot exit is manual and discretionary: he does not close until support turns into resistance, then closes manually (`[00:57:49]`).

## 7. Take profit and trade management

- **TP placement:** at support/resistance levels in the direction of the trade — never at fixed R multiples. Two TPs in every worked example, labelled TP1 and TP2 (`[00:17:16]`, `[00:45:49]`, `[01:00:05]`).
- **TP identification in practice:** the first opposing S/R level is TP1, the next is TP2 (`[00:17:16]`); for a long that has broken out, the flipped SR level on the retest is a TP (`[00:14:20]`).
- **Stop trailing:** on TP2 being hit, move the stop to TP1 or to break-even (`[00:45:49]`). This is the only trailing rule stated.
- **Break-even exit:** if the trade does not react promptly, or if the level that justified the trade is lost/undone by a single large candle, exit at break-even and stand aside (`[01:13:03]`, `[01:13:38]`).
- **Flip exit for shorts:** if the shorted level flips into support and price consolidates above it, get out — that is a deviation back into the range and price is likely to run to mid-range and range highs (`[01:15:24]`).
- **Partial-target reality:** he repeatedly banks the move even when it is small in spot terms because leverage multiplies it — a 7% move at 10x is 70% of margin (`[00:13:47]`); a 7% move on a daily is "a lot if you're swing trading" and worth a TP at support (`[00:15:27]`).
- **Position may stay in-zone:** if the DCA fills and price never exits the zone, the trade can still work — "if your DCA fills and you stay within the zone, you still might get a nice decent move out" (`[00:14:54]`).
- **Low-timeframe management:** 5m/15m/1H order block plays "you literally have to be in front of your charts to watch" — they are not set-and-forget (`[00:57:15]`).
- **Price-discovery TP ladder:** trend-based fib extension levels become TP1 through TP5; all levels are used, not just the golden pocket and 0.786, "because you need multiple points of rejection." They are explicitly probabilistic — "doesn't mean they're all going to hit. They're just a way of predicting numbers" (`[01:45:16]`, `[01:45:48]`, `[01:48:05]`).

## 8. Invalidation and re-entry

**Zone death:**
- A zone dies once it has been ~50% filled — "That's why I don't play setups after that 50% fill." At 50% fill, liquidity has been grabbed and price moves away (`[00:48:43]`).
- Corollary: a zone that has been touched but never 50% filled remains live and may be traded again. He demonstrates the same LINK supply zone being tradeable three separate times: touch 1 — 50% not filled; touch 2 — 50% not filled; touch 3 — 50% filled, zone now dead (`[00:52:38]`).
- Explicit re-validation check: "Is this valid if we get it again? Yes, it's still valid" (`[00:49:49]`). And on a 3-day demand zone: "We did not get a 50% fill. So this can be played again" (`[00:02:50]`).
- Repeated touches without a fill still degrade the level: "We've touched this support line so many times. This is a weak weak support area" (`[00:50:56]`). This sits in tension with the 50%-fill rule — see S6-A21.

**Setup death (non-fill reasons):**
- Structure: a support that closes below and flips to resistance kills the long thesis; the level becomes a short SR (`[00:04:36]`, `[00:59:31]`).
- Zone size: an OB or zone too small in absolute terms is never taken (`[00:58:57]`, `[01:14:12]`).
- Absence of confluence: an OB standing alone is not traded (`[00:45:16]`, `[00:55:31]`).

**Re-entry after a stop-out:**
- Permitted when price closes back above the lost support. LINK long: stopped out on a wick below support, then "we closed above here… so if we closed above support you could have re-entered with the same [setup]." The setup was declared still clean because support held, a double bottom formed, and the textbook demand zone was intact (`[00:43:29]`, `[00:44:04]`).
- The re-entered stop is placed below the new wick.
- Spot avoids the problem entirely — no stop, so no stop-out, so no re-entry decision (`[00:43:29]`, `[00:57:49]`).

## 9. Timeframes

- **His own style:** 4-hour, plus spot trading. "This is why I trade on a 4 hour and I have confirmations and spot trading" (`[00:57:15]`).
- **Analysis direction:** always start on a higher timeframe and work down (`[01:03:33]`). Higher timeframe zones are stronger; lower timeframe zones are weaker (`[00:33:48]`, `[00:24:46]`, `[00:56:03]`).
- **Swing timeframes referenced:** 3-day, daily, 12H, 8H, 4H. A daily-timeframe setup is explicitly labelled a swing trade and carries the 4–5% loss budget (`[00:41:15]`).
- **Scalp timeframes:** "anything under 4 hours" — 2H, 1H, 15m, 5m, 3m (`[01:52:43]`). Expected magnitudes shrink accordingly: 15m SR ≈ 1% bounce (`[00:56:03]`), 1H moves 0.5–1% (`[01:12:28]`, `[01:28:12]`).
- **Low-timeframe caveat:** low-timeframe OB plays require live screen presence and cannot expect large moves (`[00:57:15]`).
- **Drilling down for confirmation:** he drops to a lower timeframe to check whether a level actually rejected / to time an entry inside a higher-timeframe zone (`[00:23:05]`, `[00:56:38]`, `[01:05:52]`), and to find demand zones when none remain on higher timeframes (`[00:01:39]`, `[00:03:23]`).
- **Drilling up:** when no swing low exists on the current timeframe for drawing fibs, go to a higher timeframe to find one (`[01:53:59]`, `[01:54:34]`).
- **New / low-data coins:** may require 3m, 5m or 10m charts simply because there is not enough history (`[01:50:23]`).
- **Higher-timeframe / cross-market confirmation logic:**
  - BTC dominance when trading alts; USDT dominance when trading majors only; DXY (`[01:04:09]`).
  - The coin's BTC pairing as a strength filter — if ALT/BTC is strong, a deep USD pullback will not come (`[00:27:36]`, `[00:28:43]`).
  - The parent major for beta coins — ETH for OP/LDO/ENS, SOL for JTO/JUP/PYTH; the parent's move overrides the coin's own technicals (`[00:25:18]`, `[00:25:51]`).

## 10. Confluence

**What counts as a confluence (each named as such in this session):**
- Support / resistance level `[01:04:43]`
- SR point (broken-and-flipped level), with untested SR ranked strongest `[00:16:41]` `[00:18:57]`
- Supply zone or demand zone — his definition or textbook `[00:18:25]` `[01:35:26]`
- Order block sitting inside a zone `[00:44:43]` `[01:35:26]`
- Golden pocket (0.618–0.66) `[00:18:25]` `[01:35:26]`
- 0.786 fib `[01:33:41]` `[01:35:26]`
- Range low / range high `[00:56:03]` `[01:14:47]`
- Trend line (treated as diagonal S/R) `[01:05:19]` `[01:08:09]`
- Double bottom / double top `[00:44:04]` `[01:32:28]`
- Chart patterns — falling wedge, cup and handle, bear flag, inverse head and shoulders `[00:06:57]` `[01:06:59]` `[01:55:08]` `[02:04:25]`
- Multiple support levels stacked at the same price `[00:56:38]`

**How many he wants:** never numerically specified. He requires "confluence" and refuses OB-only and fib-only trades, but states no minimum count. Worked examples show 3 confluences (resistance + supply zone + potential SR, `[00:18:57]`) and 4 (resistance + supply zone + OB inside the supply zone + golden pocket, "we have four confluences there", `[01:35:26]`).

**Weighting — he does weight, hierarchically:**
- S/R (including SR points and trend lines) is drawn first and outranks everything: "support and resistance is first. Always" `[01:03:33]`; "everything is noise when there are support and resistance lines already drawn" `[01:18:56]`.
- Supply/demand zones second `[01:03:33]`.
- Fibs are rated above patterns: "I would use fibs over patterns 100% of the time" `[01:56:54]`, and he also says "I prefer fibs first, patterns [after]" `[01:08:09]` — but elsewhere calls fibs "the last one to draw to get confluence" `[01:56:54]`. See S6-C2.
- Zone consolidation outranks the OB inside it: "what am I going to use? More consolidation demand zone over the order block" `[01:07:32]`.
- Between two valid candidates, take the one with the extra confluence: "I have more confluence in taking this zone than taking this zone. However, both are still valid" `[00:18:25]`; "I probably wouldn't trade this order block. Although it's an order block, I would rather trade this resistance. There's more confluence" `[01:00:44]`.
- No confluence at all → skip: "there's no confluence here. Just the order block" `[00:55:31]`.

## 11. Explicitly excluded

- **Volume profile** — "I don't take a look at volume profile" `[01:09:27]`.
- **Indicators generally** — "I have no indicators on my chart whatsoever." "Everything I do starts with lines and boxes" `[01:09:27]`.
- **EMAs** — only sometimes, only on the daily, and only the 200 EMA `[01:09:27]`.
- **Divergences** — "sometimes if I want to look for divergences I'll look, but I typically do not" `[01:09:27]`.
- **Fib channels** — "Some people use it. I do not use it" `[01:17:09]`.
- **Fib spirals, Fibonacci circles/arcs, Jupiter/moon-distance overlays** — "complete nonsense", "the most useless tool", "no one in the world uses this… it's just engagement farming. If anyone shows this, unfollow them" `[01:15:59]` `[01:16:33]`.
- **Non-standard fib levels** — 0.113, 0.114, 0.13, 0.15, 2.14 dismissed as made-up numbers `[01:37:07]` `[01:37:42]`. He also likes but does not use 2.36 `[01:41:52]`.
- **Multiple stacked fib drawings on one chart** — the student example with ~90 fibs open is criticised directly `[01:36:00]` `[01:37:07]`.
- **Fibs as a primary/standalone signal** — "fibs should not be used as your holy grail" `[02:04:25]`; "fibs should not be your first resort" `[01:53:59]`.
- **Order blocks as a standalone signal** — `[00:45:16]`.
- **Shorting a coin in price discovery** — `[01:46:22]`.
- **Leverage on newly listed coins** — `[01:50:23]`.
- **Leverage on illiquid / thin-orderbook coins** — ENS-type charts and low-cap memecoins; "trade them on spot" `[00:24:13]` `[02:01:05]`.
- **Low-cap / brand-new memecoins entirely** — "TA typically doesn't work in general on those… most of them turn out to be rug pulls. I typically stay away from these coins. This is why I trade high cap coins only" `[01:59:23]` `[02:01:38]`. He carves out Bonk and Pepe as high-cap enough to work `[01:59:58]`.
- **SMC-style zone laddering** — he describes the SMC approach (5–6 orders laddered across a demand-zone box) and contrasts it with his own: "for me I'm picking out my entries at a specific line and DCAing at another support area. I have one and two. They have like maybe five or six orders" `[01:01:51]` `[01:02:25]`.
- **Forcing trades when nothing qualifies** — "sometimes it's okay to not take a trade" `[00:51:28]` `[00:03:23]`.
- **Taking every valid setup** — "it doesn't mean that you have to take every single trade. Maybe it's not time for longs" `[00:50:56]`.

## 12. Ambiguities for the bot

**S6-A1 — "Directional change in price" has no definition.** The entire OB rule depends on it (S6-R1/R2) but he never says how large a move, over how many candles, qualifies as a directional change. A coder must pick a swing-detection method (fractal, ZigZag %, N-bar pivot) that he never specifies. `[00:29:51]`

**S6-A2 — "Sufficient gap in price" is undefined.** Required for both his supply and demand zone definitions (S6-R4/R5). No percentage, no ATR multiple. `[00:31:31]` `[00:33:13]`

**S6-A3 — The 50% fill measurement is unspecified.** 50% of what: the zone's high-to-low including wicks, or body-to-body? Measured by any wick touching the midpoint, or by a candle CLOSE beyond it? Given his separate wick-vs-body rule, this matters and he never resolves it. `[00:48:43]` `[00:52:38]`

**S6-A4 — Wick-vs-body inclusion has no numeric threshold.** "The wick is very small" vs "this is a very very wide wick" — the only datapoint is a rejected $0.60 wick on a ~$17 coin (≈3.4%). Whether the criterion is absolute, % of price, % of candle range, or relative to ATR is not stated. `[00:53:12]` `[00:53:46]` `[00:36:14]`

**S6-A5 — Minimum zone/OB size is given in raw dollars, not normalised.** "$100 is way too tiny", "$10 vs $20–30" on ETH, "$0.30 is a weak order block" on ENS. These are unusable as a rule across coins at different prices without a normalisation he never provides (% of price? ATR? % of the expected move?). `[00:58:57]` `[01:14:12]` `[00:23:39]`

**S6-A6 — "Stronger the move away" has no threshold.** 2% is called weak/scalp-only; 5% is "a lot". But these are on different coins and timeframes, so no single cut-off can be derived. `[00:04:03]` `[00:45:16]`

**S6-A7 — "More candles = stronger zone" has no minimum.** No candle count is ever given for a valid consolidation, nor a scoring function mapping candle count to strength. `[00:33:13]`

**S6-A8 — DCA size allocation is not a rule.** The 35/55/100 split is explicitly disclaimed: "these are just random numbers. I haven't calculated based on how much I would lose." The only hard constraint is that total loss ≤5%; the ratio between tranches is left open beyond "heavier on the later DCA". `[00:39:23]` `[00:40:05]`

**S6-A9 — When to use 0, 1 or 2 DCAs is judgment.** "This is in a range where you do not have a DCA" and "I would only have one DCA here, not two" are asserted without a criterion (zone depth? number of intervening S/R levels? stop distance?). `[00:23:05]` `[01:11:20]`

**S6-A10 — TP1/TP2 selection is not deterministic.** "Take profits at levels of support/resistance" — but charts have many. Which S/R levels qualify, how far they may be, and whether an unreached level can be skipped are never specified. `[00:17:16]` `[00:45:49]`

**S6-A11 — Position fraction closed at each TP is never stated.** He shows TP1 and TP2 but never says what percentage of the position is sold at each. The trailing rule (stop → TP1 or break-even on TP2) implies size remains, but how much is unknown. `[00:45:49]`

**S6-A12 — There is no maximum stop width.** He calls ~16% "pretty wide" but takes the trade; he calls ~3% "very tight" and also takes it. The real constraint is the 5% portfolio-loss budget, which any stop width can satisfy with a small enough size — so "too wide" is never actually operative as a filter. `[00:08:04]` `[00:04:03]` `[00:11:27]`

**S6-A13 — "Stop lands inside another support area" is diagnosed but not acted on.** He says placement is "very, very hard" and then places one anyway. Skip the trade, tighten the stop, or move the DCA? He does the last two in one example and gives no rule. `[01:11:53]` `[01:12:28]`

**S6-A14 — No minimum confluence count.** "I need confluence" (S6-R29) with examples at 3 and 4, but no N. A bot must choose. `[00:45:16]` `[00:18:57]` `[01:35:26]`

**S6-A15 — Confluences are ranked but not weighted numerically.** He states an ordering (S/R > zones > fibs/patterns) and makes pairwise comparisons, but gives no scores, so "more confluence" cannot be computed when the two candidates have different *kinds* of confluence. `[01:03:33]` `[01:07:32]` `[00:18:25]`

**S6-A16 — Swing high/low selection for fibs is explicitly non-deterministic.** "You can take it from many swing low points. It doesn't matter which one. You will have different supports that come out." He also says to "drag it out and even it up with the highs" when the draw looks wrong. This makes fib levels unreproducible without a swing-detection rule he does not give. `[01:21:06]` `[01:24:41]`

**S6-A17 — Break-even exit trigger is subjective.** "Not getting a nice immediate reaction" — no bar count, no time limit, no adverse-excursion threshold. `[01:13:38]`

**S6-A18 — Re-entry trigger timeframe is unspecified.** "If we closed above support you could have re-entered" — closed on which timeframe? The chart in play, or the timeframe the zone was drawn on? `[00:43:29]`

**S6-A19 — Size-reduction trigger is pure discretion.** "If you're never sure of the price action, lower your position size" — 1/3 size and 1.5% loss budget are concrete, but the trigger condition is not codeable as stated. Same for the 20–30% light entry. `[00:52:00]` `[01:55:08]`

**S6-A20 — BTC-pairing strength is qualitative.** "If the BTC pairing looks really good, you're not going to get that deep pullback." No metric — no relative-strength window, no threshold, no lookback. `[00:28:43]`

**S6-A21 — "Multiple touches weakens support" has no touch count, and conflicts operationally with the 50%-fill rule.** The 50%-fill rule says an unfilled zone stays valid; the multiple-touch rule says repeated touches make it weak. A bot needs a touch counter and a decay function, neither of which he gives. `[00:50:56]` `[00:52:38]`

**S6-A22 — 0.886 fib is in the recommended settings list but explicitly un-back-tested by him.** "That one's a really cool one as well. I just haven't back tested it." Include as a level or not? `[01:38:17]` `[01:41:14]`

**S6-A23 — Golden pocket upper bound is 0.66 or 0.65 depending on source.** He uses 0.66 and recommends it, but acknowledges the 0.65 convention. The band width differs by 0.01 — material for a limit order. `[01:40:01]`

**S6-A24 — The trend-based extension level set is not enumerated in the session.** "I just chose all of them, which again is the ones that it's going to be shared in the notes." Only 1.0 and 1.23 are named on-screen. The actual TP1–TP5 set lives in an external notes file the bot does not have. `[01:46:22]` `[01:47:29]`

**S6-A25 — Spot vs leverage decision is qualitative.** "I probably play this on spot because of the difference from the top to the bottom of the zone" — a zone-depth threshold is implied but never given. `[00:02:50]`

**S6-A26 — Both his zone definitions and both textbook definitions are traded, with no selection rule.** He carefully distinguishes his continuation zones from textbook reversal zones, then trades both throughout the session without saying when to prefer one. `[00:32:38]` `[00:36:48]` `[01:34:52]`

**S6-A27 — "Consolidates horizontally" has no tolerance.** How much slope is still horizontal? How tight must the range be? Undefined for both zone definitions. `[00:33:13]` `[00:35:39]`

**S6-A28 — The indicator step of the workflow (step 5) is a placeholder.** "The different types of indicators that I talk about, my favourite one" — never named in this session; BTC.D / USDT.D / DXY are named but with no read rules or thresholds. Deferred to a later session. `[01:03:33]` `[01:04:09]`

**S6-A29 — Break of structure and quasimodo are defined only by example and explicitly deferred.** "When I go over break structures on Monday, it'll make more sense." Not codeable from this session alone. `[00:05:12]` `[00:20:03]`

## 13. Contradictions

**S6-C1 — His supply zone definition is stated backwards once.** At `[00:31:31]` he says "This is my definition of a supply zone. Price goes up, consolidates, then goes down." At `[00:32:04]`, `[00:35:39]` and `[00:58:57]` the same up-consolidate-down pattern is called the TEXTBOOK definition, and his own is down-consolidate-down. The weight of evidence (three statements plus every worked example) supports down-consolidate-down as his definition; treat `[00:31:31]` as a misspeak or ASR corruption, but a coder reading only that passage would build the wrong detector.

**S6-C2 — Where fibs sit in the confluence order.** At `[01:08:09]` he places fibs before patterns in the drawing sequence ("I prefer fibs first, patterns [after]"). At `[01:56:54]` he says "fibs should be the last one to draw to get confluence" — and in the same breath, "I would use fibs over patterns 100% of the time." Last-to-draw and ranked-above-patterns cannot both order the sequence. A bot must decide whether patterns are step 6 or step 7.

**S6-C3 — Untested SR vs confirmed resistance as the stronger level.** At `[00:05:12]` he says a level is stronger "because we've already confirmed resistance" (price broke down and closed below it). At `[00:17:51]` he says the strongest candidate is "an untested SR point… an untested SR is going to give you a nice rejection." These are two different senses of tested/untested (confirmed as a level vs untouched since the flip), but as written they give opposite strength rankings for a level that has been retested once.

**S6-C4 — The 5% loss budget is stated as a hard rule and then abandoned in the very next worked example.** He says "just make sure you don't lose more than 5%" and "$55 max" at `[00:41:15]`–`[00:41:51]`, having just computed the LINK setup at $101 = 10% of a $1,000 portfolio — and then declines to fix it: "for the sake of this example, I'm not going to figure that out right now." The rest of the LINK walkthrough uses the oversized position. The ONDO example at `[00:11:27]` DOES enforce the budget by iterating sizes.

**S6-C5 — Golden pocket upper bound: 0.66 (his) vs 0.65 (commonly cited).** He acknowledges both, uses 0.66, and recommends highlighting 0.66 — but also says "you can do both of them." `[01:26:22]` `[01:40:01]`

**S6-C6 — "There's no right way to draw fibs" immediately reversed.** At `[01:49:12]`: "There's no wrong way of drawing fibs. There's no right way of drawing fibs." Four seconds later at `[01:49:49]`: "Um, but you want to — actually, there's a right way of drawing fibs. Sorry. Swing high to swing low."

**S6-C7 — Fibs are "complete nonsense" and also a core part of his process.** He opens the fib section calling Fibonacci "complete nonsense" and "the most useless tool" `[01:15:59]`, then spends 45 minutes on it and states that the 0.786 is his standard DCA level `[01:57:29]` and "my favourite fib" `[01:58:15]`. The dismissal is aimed at spirals/arcs/channels and exotic levels, but the rhetoric is broad enough to mislead.

**S6-C8 — Zone re-tradeability: 50%-fill rule vs multiple-touch weakening.** `[00:52:38]` says the same zone can be taken three times because 50% never filled. `[00:50:56]` says a support with many touches is "weak weak" and may not be worth taking. The two rules produce opposite verdicts on a repeatedly-touched, never-filled level.

**S6-C9 — Order blocks alone are not traded, but he walks through OB-only trades.** S6-R29 is explicit `[00:45:16]`. Yet at `[00:54:22]`–`[00:55:31]` he walks a 15m OB trade through entry, stop and TP1, and only afterwards says "but there's no confluence here, just the order block." At `[00:38:16]` he says "I don't take trades based off OBs alone" while the LINK short he is building is anchored on an OB inside a supply zone (which does satisfy the rule). The teaching examples blur the rule.

**S6-C10 — Suspected cross-session conflict: spot has no stop loss.** `[00:43:29]` and `[00:57:49]` establish that his spot trades run without stops and are closed manually only when support flips to resistance. Every position-sizing rule in this session (S6-R11, R12) assumes a stop price exists. A bot cannot apply the 4–5% loss budget to a spot trade with no stop; this will need reconciling with whatever risk framework the other sessions define.

**S6-C11 — Suspected cross-session conflict: timeframe of record.** He states 4H as his trading timeframe `[00:57:15]`, but the worked position-sizing example is explicitly a daily swing `[00:41:15]`, the fib walkthroughs are on 1H, and he answers scalp questions on 2H/15m/5m. Session-level rules (loss budget, DCA count, TP count) may be timeframe-dependent in ways not stated here.
