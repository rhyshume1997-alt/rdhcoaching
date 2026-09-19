# S3 — Macro "indicator" charts (BVOL volatility, BTC.D, USDT.D, DXY, CME gap) and how they gate risk-on/risk-off

Source: transcripts/S3.md  |  Runtime covered: 00:00:00 to 02:06:49

## 1. Scope

This session teaches four non-price "context" charts the instructor uses to decide when to be risk-on or risk-off, and in what size: the BitMEX 24h Bitcoin volatility index (BVOL/BVOL24H), Bitcoin dominance (BTC.D), USDT dominance (USDT.D), and the dollar index (DXY), plus a fifth chart he dismisses (the CME Bitcoin futures gap). It is explicitly a context/filter lesson, not a setup lesson: the only entry mechanics stated are recaps ("enter at SR points and DCA lower", stop above the rejection wick, wait for a close above the level). It also contains a market-structure exit rule, a counter-trend position-sizing rule, and an all-time-high breakout rule, all delivered as asides.

Note: there is a genuine instructor break at 01:08:54–01:18:08 (no content lost).

## 2. Definitions

- **BVOL / "BVOL 24H" (he says "Bivvol")** — a BitMEX chart that measures the *volatility* of Bitcoin, not its price; it is not a TradingView indicator and you do no TA on it. `[00:08:22]` `[00:08:55]` `[00:32:41]`
- **The BVOL zone / box** — the horizontal band on BVOL where volatility has historically bottomed out and bounced from; currently 0.81 to 1.4. Candles entering it mean volatility has died. `[00:09:28]` `[00:26:00]`
- **Tight consolidation / no volatility** — price ranging in roughly a $800 range for three days at current prices (or a 2–3% range), which is what drives BVOL into the zone. `[00:12:21]` `[00:29:56]`
- **Bitcoin dominance (BTC.D)** — Bitcoin's share of total crypto market cap; it says nothing about Bitcoin's price, only about money leaving alts. Rising = bearish alts, falling = bullish alts. Deliberately traded **inverse**: buy at resistance, sell at support. `[00:41:34]` `[00:43:18]` `[00:43:51]` `[01:07:47]`
- **USDT dominance (USDT.D)** — stablecoin share of market cap; inversely correlated to the *whole* crypto market (not just alts). Up = profit-taking into stables, more shorts than longs, liquidations, sidelined capital, FUD. `[01:02:33]` `[01:04:13]`
- **DXY** — the dollar index. A bullish dollar is bearish for crypto *and* equities; a bearish dollar is bullish for both. He flags that this correlation has been broken for ~7 months and he cannot explain it. `[01:21:31]` `[01:24:18]` `[01:27:02]`
- **Risk on / risk off** — his framing for whether to be in alts at all and how big, decided from these charts rather than from the price chart. `[00:41:34]` `[01:29:52]`
- **CME gap** — the price gap between Friday's CME futures close and Monday's open, caused by crypto trading through the weekend while the Chicago Mercantile Exchange is shut. `[01:30:40]` `[01:31:14]`
- **Meme chart** — his label for a chart people quote but that adds no information over levels you already have plotted (CME gap; also fear & greed). `[01:35:22]` `[01:38:40]`
- **SR point** — a level that was support, was lost, and became resistance (or vice versa). His stated primary entry location. `[00:01:06]` `[01:54:12]`
- **Deviation** — a close below a level that is *not* followed by a retest and rejection from below; it does not count as a flip. `[00:02:15]`
- **Bearish/bullish engulfing candle** — a candle whose **body** is longer than the body of the preceding opposite-colour candle. `[01:42:41]`
- **Market structure break** — closing below the last higher low, then putting in a lower high (or the mirror image to the upside). `[00:05:34]` `[02:03:19]` `[02:06:14]`
- **Price discovery** — a coin trading above its all-time high with no overhead levels; only long these, never short. `[01:48:20]`
- **Alt/BTC pairing** — the altcoin's chart denominated in BTC; used to rank which alts will outperform when the market is stable. `[00:50:44]` `[00:51:56]`
- **Alt season** — the condition where BTC.D falls while Bitcoin's price rises, so alts pump far harder than Bitcoin. `[00:48:29]`
- **Funding rate** — periodic payment between longs and shorts; deeply negative funding means shorts pay longs to hold. `[01:53:04]` `[01:53:38]`
- **Range low / mid-range** — the bottom and middle of an established range; mid-range is treated as the "boss level" that decides direction. `[00:02:15]` `[00:06:41]`

## 3. Hard rules

**S3-R1** — When a daily BVOL candle enters the zone, expect a large-volatility move in Bitcoin within the following 48–72 hours.
`params:` chart = BVOL24H; timeframe = daily only; zone = 0.81 to 1.4; window = 48–72h (also stated as "2 to 3 days").
`[00:11:12]` `[00:26:00]`

**S3-R2** — Do no technical analysis on BVOL: no trend lines, no structure, no direction. The only operation is the zone-touch test.
`params:` TA allowed on BTC.D and USDT.D; TA **not** allowed on BVOL.
`[00:08:22]` `[01:05:22]`
*(Softened/contradicted: he does maintain a horizontal box on it and relocates it based on where bounces cluster — see S3-R7 and S3-C1.)*

**S3-R3** — Do not derive direction from a BVOL zone touch; the resulting move can be up or down.
`params:` none — direction signal = null.
`[00:14:04]` `[00:28:16]` `[00:32:41]`

**S3-R4** — Read BVOL on Thursday, Friday, Saturday, Sunday; that is when the zone is normally reached.
`params:` days = Thu–Sun; Mon/Tue/Wed/Thu are the "nice days to trade".
`[00:37:05]` `[00:38:11]`
*(Softened at `[00:37:39]`: touches can also occur mid-week around Fed/Powell events, which are "usually on Wednesdays".)*

**S3-R5** — When BVOL is in the zone, leverage traders reduce size or stand aside and wait for the move to complete before trading the resulting range; spot buyers may still buy dips.
`params:` leverage = reduced size / sit out; spot = unchanged.
`[00:17:30]` `[00:28:50]`

**S3-R6** — If the expected move has *not* arrived by the end of the 2–3 day window, treat the situation as more dangerous, not less.
`params:` window elapsed with no move ⇒ raise caution.
`[00:38:11]`

**S3-R7** — Relocate the BVOL box upward when price stops reaching it and instead bounces repeatedly from a higher area; relocate down when candles print consistently below it.
`params:` historical boxes named: 0.19–0.81 (old), 0.81–1.4 (current), 1.8–2.2 (a prior cycle box). Trigger = "multiple bounces" from the new area.
`[00:09:28]` `[00:31:36]` `[00:34:52]`

**S3-R8** — On BTC.D, buy alts at resistance and sell/trim alts at support (inverse of normal TA).
`params:` chart = CRYPTOCAP:BTC.D; plot on 4h or higher (4h, daily, 3-day, weekly).
`[00:43:18]` `[00:59:40]` `[02:01:02]`

**S3-R9** — On USDT.D, buy at resistance and sell at support (USDT.D is inverse the whole crypto market).
`params:` ticker = USDT.D; TA is fully valid on this chart.
`[01:05:22]` `[01:06:00]`

**S3-R10** — Treat a bearish DXY as bullish crypto and equities, and a bullish DXY as bearish for both.
`params:` DXY source = TVC feed.
`[01:21:31]` `[02:02:08]`
*(He immediately notes this has failed since ~December and he does not know why — `[01:22:05]` `[01:24:18]`.)*

**S3-R11** — Rank the context charts in this fixed order of importance: USDT.D (1), DXY (2), BTC.D (3), BVOL (4).
`params:` 1=USDT.D, 2=DXY, 3=BTC.D, 4=BVOL.
`[01:20:56]`

**S3-R12** — Check USDT.D and DXY every single day; check BTC.D only when an alert fires as price approaches a plotted resistance or trend line.
`params:` alerts set on horizontal lines and trend lines.
`[01:28:45]` `[01:29:17]`

**S3-R13** — Enter positions at SR points and DCA lower; if the lower DCA never fills, average up at the next SR point instead.
`params:` example: SOL entry filled 25%, average 150.6, target average after averaging up ≈152.
`[01:54:12]` `[01:54:49]`

**S3-R14** — Never average up into a supply zone or into open air — only at an SR point.
`params:` "no reason to buy or average up here… you're buying into a supply zone, unnecessary points".
`[01:54:49]` `[01:55:22]`

**S3-R15** — For a short at an SR rejection, place the stop above the rejection wick; do not DCA a short whose whole move is only 1–2%.
`params:` stop = above wick high; skip DCA when total expected move ≤ ~2%.
`[01:41:02]` `[01:41:34]`

**S3-R16** — Require a candle **close** above the trigger level before firing entries, not just a touch.
`params:` example: needed a close above 61K on Bitcoin before sending plays.
`[01:41:34]`

**S3-R17** — A level only flips (support→resistance) after a close through it **plus** a retest and rejection; a close through it alone is a deviation and the level stays valid.
`params:` deviation = close beyond, no retest/reject.
`[00:02:15]` `[00:03:20]`

**S3-R18** — Each additional touch of a support level weakens it; expect it to break after repeated touches.
`params:` he counts "one, two, three, four, five, six touches" before the break.
`[00:02:15]`

**S3-R19** — A trend line requires three touch points to be valid; two touches is not a trend line.
`params:` min touches = 3.
`[00:56:23]`
*(Immediately softened: "you can by all means change your trend lines to fit your narrative" — `[00:56:55]`.)*

**S3-R20** — Uptrend remains intact until the last higher low is lost; losing it is the invalidation.
`params:` invalidation = close below last higher low. Stated for BTC.D at `[00:57:29]`, and for the Bitcoin recap at `[00:06:07]` `[00:07:15]` (range low 61K down to 59.5K).
`[00:07:15]` `[00:57:29]`

**S3-R21** — Exit a macro position only after a two-step confirmation: close below the last higher low, then a subsequent lower high forms. Do not exit on the break alone.
`params:` timeframe = daily/macro; both conditions required.
`[02:03:19]` `[02:05:40]` `[02:06:14]`

**S3-R22** — Re-entry after that exit: wait for price to reclaim the broken level, then buy the reclaim.
`params:` "reclaim it, and then I would have bought right there".
`[02:06:14]`

**S3-R23** — After a break of structure to the upside, expect only shallow pullbacks and buy them until the invalidation level is lost.
`params:` buy shallow pullbacks; stop = loss of the flagged level.
`[00:07:15]`

**S3-R24** — Risk per trade by style: scalp loses 2–3% of portfolio if stopped; swing loses 4–5%.
`params:` scalp 2–3%; swing 4–5%.
`[00:04:25]`

**S3-R25** — When trading *against* the prevailing trend, cut position size and cut risk-per-trade to ~1%.
`params:` example portfolio $1,000; normal position 20% of portfolio; counter-trend position $100; risk 1% instead of 2–3%.
`[00:03:53]` `[00:04:25]` `[00:04:58]`
*(Internally inconsistent — see S3-C9.)*

**S3-R26** — Reject setups whose risk-to-reward is about 1:1.
`params:` R:R ≈ 1:1 → no trade. Preferred alternative in his example: stop below support, ~6% upside vs ~2% for the chase.
`[00:19:42]` `[00:20:17]`

**S3-R27** — When a coin closes above its all-time high, treat the close as the breakout candle (a wick above that closes back below does not count); expect a retest of that level and continuation higher.
`params:` requires close above ATH; retest expected "always".
`[01:47:10]` `[01:48:20]`

**S3-R28** — In price discovery (above ATH), only take longs — never short.
`params:` direction filter = long-only.
`[01:48:20]` `[01:48:55]`

**S3-R29** — When the market is stable, select alts by the trend/market structure of their ALT/BTC pairing; a bullish BTC pair means the alt holds up on Bitcoin retraces and outperforms on Bitcoin pumps.
`params:` universe = 4–5 regularly traded coins; ETH/BTC excluded as "usually always down".
`[00:51:56]` `[01:44:23]` `[01:45:29]`

**S3-R30** — A breakout on an alt/BTC pair is confirmed only on a daily close above the retested level.
`params:` timeframe = daily close.
`[01:44:56]`

**S3-R31** — Consolidation under resistance is bullish (expect the breakout, then the flip to support, then continuation).
`params:` none.
`[00:51:20]`

**S3-R32** — Bank profit when the coin's own chart is at resistance/SR/supply **and** USDT.D or BTC.D is at support; at minimum move stops to break-even or into profit.
`params:` trim size unspecified; stop → break-even or better.
`[01:00:12]` `[01:07:12]` `[01:18:08]`

**S3-R33** — Take profit on leverage positions at those levels always; on spot you may skip taking profit if the intended TP is close and structure has broken to the upside.
`params:` spot skip allowed when a 2–3% retrace still leaves structure intact.
`[01:19:14]`

**S3-R34** — Deeply negative funding favours holding longs (shorts pay you), but extreme negative funding eventually resolves against price.
`params:` "max negative funding… negative 3 at one point".
`[01:53:04]` `[01:53:38]` `[01:54:12]`

**S3-R35** — Do not trade CME gaps as a signal; gaps do not have to fill (though usually do, over weeks to months). Use the price levels you already plotted.
`params:` example gap 39.5K–40.3K filled ~1.5 months later; an unfilled gap remains at ~3K.
`[01:31:48]` `[01:32:56]` `[01:33:30]` `[01:35:22]`

**S3-R36** — Plot levels in advance and let price come to you; do not chase or knife-catch during a high-volatility window.
`params:` none.
`[00:15:46]` `[00:16:20]` `[00:19:09]`

## 4. Parameters and thresholds

| parameter | value | applies to | timestamp |
|---|---|---|---|
| scalp max loss | 2–3% of portfolio | risk per trade | `[00:04:25]` |
| swing max loss | 4–5% of portfolio | risk per trade | `[00:04:25]` |
| normal position size | 20% of portfolio | position sizing | `[00:03:53]` |
| counter-trend position size | $100 on a $1,000 portfolio (vs $200 normal) | counter-trend sizing | `[00:04:25]` |
| counter-trend risk | ~1% of portfolio | counter-trend sizing | `[00:04:58]` |
| rejected risk-to-reward | 1:1 | trade filter | `[00:20:17]` |
| patience example outcomes | 2% chase vs 6% waited entry | trade filter | `[00:19:42]` |
| BVOL current zone | 0.81 to 1.4 (also said "1.41") | BVOL | `[00:09:28]` `[00:26:00]` |
| BVOL previous zone | 0.19 to 0.81 | BVOL history | `[00:09:28]` |
| BVOL older zone | 1.8 to 2.2 | BVOL history | `[00:34:52]` |
| BVOL move window | 48–72 hours | BVOL | `[00:11:12]` |
| BVOL move window (restated) | 2–3 days | BVOL | `[00:26:00]` |
| BVOL move window (restated) | 48–96 hours / 2–4 days | BVOL | `[00:16:20]` |
| BVOL timeframe | daily only | BVOL | `[00:08:22]` |
| BVOL active days | Thursday–Sunday | BVOL | `[00:37:05]` |
| "tight range" definition | ~$800 over 3 days (at ~$60K BTC) | consolidation | `[00:12:21]` |
| "tight range" (2020) | ~$500 | consolidation | `[00:22:36]` |
| "tight range" (2017 summer) | ~$50 | seasonality | `[01:56:34]` |
| "tight range" (last cycle summer) | ~$800 | seasonality | `[01:56:34]` |
| dead-market range | 2–3% for half a month to a month | consolidation | `[00:27:08]` |
| realised move after zone touch (22 Jun) | 10% down and 10% up in 48–96h | BVOL backtest | `[00:13:28]` `[00:16:20]` |
| realised move after zone touch (29 Jun) | 16% down | BVOL backtest | `[00:17:30]` |
| realised move after zone touch (Trump weekend) | 7% up in one day | BVOL backtest | `[00:18:37]` |
| realised move (Apr 2020) | 18% up then 20% down | BVOL backtest | `[00:23:44]` |
| realised move (Dec 22–Jan 23) | 24% (17K→21–22K) in 4 days | BVOL backtest | `[00:27:08]` |
| support touch count before break | 6 | support strength | `[00:02:15]` |
| trend line validity | 3 touch points minimum | trend lines | `[00:56:23]` |
| BTC.D critical level | 56% (must not flip to support) | BTC.D | `[00:59:07]` |
| BTC dominance current | >55% of market cap | BTC.D | `[01:08:54]` |
| consequence if 56% flips to support | ~40% haircut across the market | BTC.D | `[00:59:07]` |
| consequence if BTC.D last higher low lost | ~50% single-day moves on alts | BTC.D | `[00:57:29]` |
| BTC.D plotting timeframes | 4h, daily, 3-day, weekly (4h or higher) | BTC.D | `[02:01:02]` |
| alt-season example (Oct 23) | LINK +61%, SOL +47%, BTC +15% | BTC.D at resistance | `[00:48:29]` |
| BTC move at BTC.D resistance | 14% up | BTC.D | `[00:47:56]` |
| BTC move at BTC.D support | 8% | BTC.D | `[00:45:32]` |
| rising-BTC.D alt behaviour | strong alts ~11%, weak alts ~3% | alt selection | `[01:43:49]` |
| entry trigger level (example) | daily close above 61K | entry trigger | `[01:41:34]` |
| BTC invalidation band (example) | 61K down to 59.5K range low | market structure | `[00:06:07]` |
| SOL position fill | 25% filled, avg 150.6 → ~152 after averaging up | DCA | `[01:54:49]` |
| alt/BTC watchlist size | 4–5 coins | alt selection | `[00:51:56]` |
| extreme funding | around -3 (max negative) | funding | `[01:53:38]` |
| meme-coin move examples | POPCAT +16%, FLOKI +16–17%, DOGE +13% | ATH breakouts | `[01:46:34]` `[01:49:28]` |
| expected FLOKI upside | ~50% | discretionary call | `[01:50:00]` |
| CME gap example | 39.5K–40.3K, filled ~1.5 months later | CME | `[01:33:30]` |
| CME gap (current) | 61K down to 59K | CME | `[01:31:48]` |
| unfilled CME gap | ~3K | CME | `[01:35:22]` |
| CME premium | $200–$300 on BTC; ~$15 on ETH | CME | `[01:38:07]` `[01:39:50]` |
| DXY level watched | ~104.7 (potential lower high) | DXY | `[02:02:08]` |
| cycle remaining | 8–12 months max | macro view | `[01:59:21]` |

## 5. Entry model

Setup identification in this session is level-first, context-second:

1. **Plot levels in advance**, over the weekend, on the price chart: range high / mid-range / range low, support, resistance, and SR points (former support now resistance, or vice versa). `[00:01:42]` `[00:16:20]` `[01:39:50]`
2. **Check the four context charts in priority order** — USDT.D, DXY, BTC.D, BVOL — to decide risk-on/risk-off and size, not entry price. `[01:20:56]` `[01:39:50]`
3. **First entry goes at the SR point.** This is stated as an absolute: "I always enter my positions at SR points and DCA lower." `[01:54:12]`
4. **DCAs are placed lower, at the next levels** — in the CME worked example the sequence is entry at the SR point, then a further DCA at the support line beneath it. `[01:34:10]`
5. **If price never trades down to the DCA**, average up at the next SR point rather than chasing — accepting the higher blended average (150.6 → ~152 on his SOL example, 25% filled). Averaging up is only permitted at an SR point, never into a supply zone. `[01:54:49]` `[01:55:22]`
6. **Trigger confirmation:** he waited for a daily *close* above 61K before firing out plays; a reclaim without the close was not enough. `[01:41:34]`
7. **For shorts**, the mirror: enter on the rejection of an SR point from below, stop above the rejection wick, and skip DCA when the whole expected move is only 1–2%. `[01:41:02]`
8. **Alt selection** when the market is stable: screen the ALT/BTC pairings of 4–5 regular coins and take the ones in uptrend / breaking out; confirm with a daily close above the retested breakout level. `[00:51:56]` `[01:44:23]` `[01:44:56]`
9. **ATH breakouts** are a separate long-only entry: close above ATH → wait for the retest of that level → long the retest. `[01:47:10]`

## 6. Stops

- Short at an SR rejection: stop goes **above the wick** of the rejection candle, because a reclaim of that wick means "we're going much higher". `[01:41:02]`
- Long from support: stop goes **below support**, and he contrasts this favourably with a chase entry whose stop placement produces 1:1. `[00:20:17]`
- What makes a stop unacceptable is expressed as R:R rather than distance: a stop that yields ~1:1 risk-to-reward is "not great" and the trade is skipped in favour of waiting for the level. `[00:20:17]`
- Loss caps by style bound the stop indirectly: a scalp must be sized so a stop-out costs 2–3% of portfolio, a swing 4–5%, and a counter-trend trade ~1%. `[00:04:25]` `[00:04:58]`
- No explicit "stop too wide" distance, ATR multiple, or percentage is given anywhere in this session.

## 7. Take profit and trade management

- **Trigger to trim:** when your coin is at resistance / an SR point / a supply zone **and** USDT.D or BTC.D has arrived at *its* support. That confluence is what makes him take profit, not the coin's chart alone. `[01:00:12]` `[01:07:12]` `[01:07:47]` `[01:18:08]`
- **Also trim** when BTC.D reaches support after you bought alts at BTC.D resistance ("sell alts or at least trim your bags"). `[00:43:18]`
- **Stop management:** on those same signals, "start scaling or at least taking profits, moving your stop losses up in profit or break even" so the remainder is risk-free. `[01:00:12]`
- **Leverage vs spot:** leverage positions "definitely want to take profit"; spot can skip a TP if the intended target is close by and structure has broken to the upside, tolerating a 2–3% retrace. `[01:18:08]` `[01:19:14]`
- **Macro exit** (whole-bag): see S3-R21 — close below the last higher low, then a confirmed lower high. He explicitly accepts missing the final leg up in exchange for avoiding the move down. `[02:05:40]` `[02:06:14]`
- **Number of TPs:** not specified in this session. He references "your actual take profit is maybe up here" and "final TP" without giving a count or a laddering scheme. `[00:19:42]` `[01:19:14]`

## 8. Invalidation and re-entry

- **A level is not lost on a close alone.** A close through a level with no retest-and-rejection is a deviation; the level is reclaimed and remains tradeable. `[00:02:15]` `[00:03:20]`
- **A support dies by attrition**: each touch weakens it; after roughly six touches he expects it to give way and the next level down to be in play. `[00:02:15]`
- **Uptrend invalidation** = loss of the last higher low. Until then, a pullback that puts in another higher low keeps the trend intact. `[00:06:07]` `[00:57:29]` `[02:03:19]`
- **Macro invalidation** requires two events: close below the last higher low, then a lower high. Only then exit. `[02:05:40]`
- **Re-entry after invalidation:** wait for the broken level to be reclaimed, then buy the reclaim. `[02:06:14]`
- **A missed move is not chased** — the levels "will eventually come back down", possibly a week later; re-arm the same plan at the same level rather than entering at market. `[00:19:09]`
- **After a BVOL volatility event**, the old level set may be void; he had to wait for a new level to be established (the reclaim of the range) before re-entering, having missed his 53K bid by a small margin. `[00:40:27]` `[00:41:02]`
- **ATH breakouts can fail**: a failed ATH breakout that breaks back down turns the ATH into resistance; the "always retests and runs" rule applies to the *next* valid breakout, not the failed one. `[01:48:20]`

## 9. Timeframes

| chart | timeframe |
|---|---|
| BVOL | daily **only**; Thursday–Sunday `[00:08:22]` `[00:37:05]` |
| BTC.D | 4h or higher — 4h, daily, 3-day, weekly `[02:01:02]`; he draws on 3-day for clarity `[00:56:23]` `[00:58:02]` |
| USDT.D | daily and 3-day both used; note it "does not close during the weekends" `[01:19:46]` `[01:42:08]` `[01:43:14]` |
| DXY | daily `[01:25:23]` |
| Macro exit / structure | daily as the "macro time frame" `[02:02:41]` |
| Alt/BTC breakout confirmation | daily close `[01:44:56]` |
| Entry refinement | drops to lower timeframes only to see the SR wick and place the stop `[01:41:02]` |

Higher-timeframe confirmation logic: a level can be support on the daily but a bearish 3-day candle over the same area overrides the daily read ("this may pump on the daily… but on the 3-day chart this is still a very bearish candle… so we're most likely going to dump further"). `[01:19:46]`

## 10. Confluence

- He states outright that BTC.D is **confluence only**, not a standalone system: "I only use this chart as confluence, but there are a lot of people that just trade based off this chart… I don't recommend it." `[00:59:40]`
- The charts are meant to be read together, never in isolation: "These charts tie into one another. You don't want to just be looking at this chart and making decisions based off this chart. You also want to take a look at Bitcoin. You want to take a look at whatever coin you're in." `[01:07:12]`
- A worked long example stacks: reclaim of range low + daily close above 61K + bearish DXY + bearish engulfing on USDT.D at support + BTC.D read + strong SOL/BTC pairing. That is five to six items before he "fired out a whole bunch of plays". `[01:41:34]` `[01:42:08]` `[01:43:14]` `[01:44:23]`
- A worked bid example stacks: demand zone + SR attempt + fibs likely lining up = "more confluence for this to come back down into this area and then go back higher". `[00:20:17]` `[00:20:51]`
- A worked take-profit example stacks: resistance + SR point + supply zone + USDT.D at support. `[01:18:08]`
- He gives **no count and no weighting**. The only ordering he supplies is the importance ranking of the four context charts (USDT.D > DXY > BTC.D > BVOL). `[01:20:56]`

## 11. Explicitly excluded

- **No TA on BVOL** — no analysis whatsoever, only the zone test. `[00:08:22]` `[01:05:22]`
- **CME gap trading** — "a meme chart"; gaps "absolutely do not" have to be filled; he does not trade them because the levels are ones he has already plotted. `[01:31:48]` `[01:35:22]` `[01:38:40]`
- **Fear and greed index** — "completely useless… it's just all psychological". `[01:38:40]`
- **USDC dominance** — not used; not enough people use USDC, and Coinbase is "basically the only one that uses this garbage". `[01:51:12]`
- **Combined USDT+USDC dominance** — "I don't use this either. I only use USDT." `[01:51:54]`
- **ETH/BTC pairing** — not looked at, "because it's usually like always down". `[00:51:56]`
- **Stocks / options / futures volume analysis** — "I don't trade stocks. Crypto is the only market that I'm in", and he does not know how CME futures volume works. `[01:36:59]`
- **Shorting coins in price discovery** — "you just buy and buy and don't short". `[01:48:20]`
- **Chasing / blind knife-catching without preset levels** — explicitly discouraged, gives poor R:R. `[00:15:46]` `[00:20:17]`
- **Trading against the trend at full size** — permitted only at reduced size. `[00:03:53]`
- **Drawing resistance far above current price action** — "I'm not going to look back on the weekly and draw resistance up here… we haven't got above this current price action, so there's no need." `[00:58:34]`

## 12. Ambiguities for the bot

**S3-A1** — "The candle comes into that zone" is undefined. Does a BVOL zone touch require the *low* to enter 0.81–1.4, the *close* to be inside it, or any wick overlap? He also says "it's okay to deviate under the box" `[00:12:53]` without bounding how far below still counts. A coder must pick low-enters-band vs close-inside-band, and must decide whether a candle *below* the band is still a signal. `[00:08:55]` `[00:12:53]` `[00:26:00]`

**S3-A2** — The BVOL move window is stated three different ways in the same session (48–72h, "2 to 3 days", 48–96h / "2 to 4 days"), and one worked example fired "literally the next day". The bot needs a single window; nothing in the transcript picks one. `[00:11:12]` `[00:16:20]` `[00:18:03]` `[00:26:00]`

**S3-A3** — "Big move" / "extremely volatile" has no magnitude threshold. Realised examples span 7% to 24%, over 1 to 4 days. There is no stated bar for calling the signal correct or failed, so backtest scoring is undefined. `[00:13:28]` `[00:17:30]` `[00:18:37]` `[00:27:08]`

**S3-A4** — The BVOL box relocation rule is purely discretionary: "that's where most of the bounces have been from", "when you see multiple bounces from this point, you move it". No count of bounces, no lookback window, no tolerance. He also says he will announce changes manually in his server, which implies it is *not* meant to be automated. `[00:31:36]` `[00:33:15]` `[00:34:52]` `[00:35:29]`

**S3-A5** — What to actually *do* on a BVOL signal is not a rule. He says he "sits patient"; leverage traders can "play that volatility"; spot can buy dips; also "trade with lower size". These are four different actions. No entry, stop, or size number attaches to the signal. `[00:14:37]` `[00:17:30]` `[00:28:50]`

**S3-A6** — "Buy at resistance on BTC.D" does not say *what* to buy, *how much*, or with what stop. The signal is a market-regime flag with no position spec attached. Same for "sell at support". `[00:43:18]` `[00:59:40]`

**S3-A7** — Support and resistance levels on BTC.D/USDT.D/DXY are hand-drawn. There is no algorithm for identifying them, no minimum touch count (except the 3-touch rule for trend *lines*), and no price tolerance band for "at support". `[00:44:25]` `[00:56:23]` `[00:58:02]`

**S3-A8** — "SR point" tolerance is undefined for entries. In the CME example he says "we didn't necessarily hit the SR point, but we came back down and bounced from support" `[01:34:10]` — so entries fill near, not at, the level. The bot needs a band (ticks? %? ATR?) that is never stated.

**S3-A9** — DCA structure is unspecified: how many DCAs, how they are spaced, and what fraction of the position each carries. The only datapoint is "I only got 25% fill" on SOL `[01:54:49]`, which implies a laddered scheme he never describes. `[01:34:10]` `[01:54:12]`

**S3-A10** — "If I can't DCA lower, then I average up" has no trigger condition. After how long, or after what price event, does the bot conclude the DCA will not fill and average up instead? `[01:54:12]` `[01:54:49]`

**S3-A11** — Counter-trend detection is undefined. "Trading against the market" / "against the uptrend" is judged by eye from market structure; the bot needs a mechanical trend definition (which timeframe, which structure points). `[00:03:53]` `[00:04:58]`

**S3-A12** — Position sizing units are mixed. "20% of your portfolio" is notional exposure; "you lose 2 to 3%" is risk. Whether leverage is applied, and how the two reconcile, is never stated. `[00:03:53]` `[00:04:25]`

**S3-A13** — "Take some profit", "trim your bags", "scale out" — no fraction is ever given. `[00:43:18]` `[01:00:12]` `[01:07:12]`

**S3-A14** — "Move your stop losses up in profit or break even" — the bot must decide which, and if "up in profit", to what level. `[01:00:12]`

**S3-A15** — "When the market is stable" (the precondition for using ALT/BTC pairings) is undefined; possibly it means the BVOL zone/low-volatility state, but he does not link them. `[00:51:56]`

**S3-A16** — The alt universe is "maybe four or five coins that I regularly trade" — only SOL, LINK, INJ, and ETH (excluded) are named in passing, plus meme coins later. There is no defined watchlist. `[00:51:56]`

**S3-A17** — Market structure (higher high / higher low / lower high / lower low) is central to R20, R21, R23 and R29 but he explicitly defers the definition: "when I go over this later on in the course it'll make sense". Swing-point detection parameters are entirely absent from this session. `[00:05:34]` `[02:02:41]`

**S3-A18** — The ATH-retest rule says price "always retests that level and then continues to go higher", but gives no time window, no maximum retrace depth, and no rule for when to abandon a retest that fails (he acknowledges failures exist at `[01:48:20]`). `[01:47:10]`

**S3-A19** — The bearish engulfing on USDT.D was used as a *long* signal for crypto and he says "as soon as we went below, that's when I started firing out longs" — but "below" what is not stated, and this is the only engulfing application given. It is not generalised into a rule. `[01:43:14]`

**S3-A20** — Funding is introduced and deferred ("I can actually talk about next session"). The only number is "-3" as an extreme. No entry, exit, or size rule attaches to it. `[01:53:04]` `[01:53:38]`

**S3-A21** — DXY's stated relationship has been failing for seven months by his own account, and he cannot explain it. The bot must decide whether to use rule S3-R10 at all, or to gate it on a rolling correlation check he never mentions. `[01:22:05]` `[01:24:18]` `[01:27:02]`

**S3-A22** — Confluence is never counted or weighted. Two of his worked examples stack 3 items, one stacks 6. There is no stated minimum to take a trade. `[00:20:51]` `[01:07:12]` `[01:41:34]`

**S3-A23** — The meme-coin rotation logic ("memes usually follow one another… let's focus on cat and dogs") is explicitly associative pattern-matching and is not codeable as stated. `[01:46:02]` `[01:48:55]`

**S3-A24** — Seasonality and the Q4/cycle-top forecast (`[01:55:55]`–`[01:59:21]`) are narrative opinion with no mechanical trigger. The "8 to 12 months max" cycle estimate is a personal view, not a rule.

**S3-A25** — The "support gets weaker with each touch" rule has no threshold. Six touches is an observation from one chart, not a stated cutoff for refusing the trade. `[00:02:15]`

**S3-A26** — CME gaps "usually do fill" but "absolutely do not" have to. There is no probability or window attached, and he tells you not to trade them — so the bot should probably ignore the chart entirely, but he never says that outright. `[01:31:48]` `[01:32:56]`

## 13. Contradictions

**S3-C1** — "You do not do any TA on this chart. There's no analysis on this chart" `[00:08:22]`, yet he draws horizontal support boxes on BVOL, identifies bounce clusters, and relocates the box based on them `[00:31:36]` `[00:33:15]` `[00:34:52]`. Reconciliation: he probably means no trend/structure/direction analysis, only a static horizontal band — but the bot must be told that explicitly.

**S3-C2** — BVOL window stated as 48–72 hours `[00:11:12]`, as 2–3 days `[00:26:00]`, and as 48–96 hours / 2–4 days `[00:16:20]`; then a live example fires the next day `[00:18:03]`, and he separately says the absence of a move within the window is itself a warning `[00:38:11]`. The window is effectively unfalsifiable as stated.

**S3-C3** — "Only look at this chart on Thursday, Friday, Saturday, Sunday" `[00:37:05]` vs "it's not just based on the weekends" — mid-week Fed/Powell days also produce touches `[00:37:39]` `[00:38:11]`.

**S3-C4** — "Buy at resistance, you sell at support" on BTC.D/USDT.D `[00:43:18]` `[01:05:22]` directly inverts the support/resistance logic taught for price charts throughout the rest of the session. He flags this himself — "I know this goes against what we've been learning, but this chart is inverse alts" `[00:43:51]` — so the bot must scope the inversion strictly to BTC.D and USDT.D and never to price charts.

**S3-C5** — "I only use this chart as confluence… there are a lot of people that just trade based off this chart. I don't recommend it" `[00:59:40]`, yet the session's main takeaway from BTC.D is stated as a direct actionable buy/sell rule `[00:43:18]` `[00:59:40]`.

**S3-C6** — CME gaps: "people think that gaps have to be filled. They absolutely do not" `[01:31:48]`, then "it doesn't mean that gaps don't have to be filled… but usually they do fill" `[01:32:56]`. The ASR double negative makes his position genuinely ambiguous; the safe reading (consistent with him calling it a meme chart) is that filling is common but not required and not tradeable.

**S3-C7** — "You definitely want to take profit" at resistance/supply `[01:18:08]` vs "maybe you don't take profit on spot" when the target is near and structure is intact `[01:19:14]`. Resolved by instrument type (leverage always, spot conditional), but the spot condition is soft.

**S3-C8** — DXY is ranked the **second most important** chart `[01:20:56]` and he says to check it every day `[01:28:45]`, while simultaneously stating the correlation has been inverted/broken for ~7 months and that neither he nor the economists he asked can explain it `[01:24:18]` `[01:27:02]`. A bot cannot both weight it highly and treat it as unreliable.

**S3-C9** — Counter-trend sizing is internally inconsistent: he halves the position ($200 → $100) but says "your stop loss is still going to be the same in terms of how much you would lose" `[00:04:58]`, then immediately says you should risk 1% instead of 2–3%. Halving size halves risk; it cannot both stay the same and drop to 1%.

**S3-C10** — Trend lines require three touch points `[00:56:23]`, followed thirty seconds later by "you can by all means change your trend lines to fit your narrative, because that's what a trend line is" `[00:56:55]`. The second statement destroys the mechanical value of the first.

**S3-C11** — Support "gets weaker and weaker" with more touches `[00:02:15]`, but he also repeatedly bids the *same* SR/support levels and treats repeated bounces from a BVOL box level as evidence the level is *valid* `[00:32:10]` `[00:34:19]`. Whether repeated touches strengthen or weaken a level is treated both ways.

**S3-C12 (cross-session risk)** — "I always enter my positions at SR points and DCA lower" `[01:54:12]` is stated as absolute, but this same session also has him entering on a *breakout close* above 61K `[01:41:34]` and on an ATH retest `[01:47:10]`. Expect other sessions to add further entry types; do not code "SR point only" as an exclusive gate.

**S3-C13 (cross-session risk)** — Risk figures (scalp 2–3%, swing 4–5%, counter-trend 1%, position 20%) are recapped here as if established in an earlier session `[00:04:25]`. These must be reconciled against whatever the earlier and later sessions state before being hard-coded.
