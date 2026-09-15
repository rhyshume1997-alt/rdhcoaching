# S2 — SR-flip confirmation mechanics, deviations, portfolio allocation, and the compounding "challenge account" risk framework
Source: transcripts/S2.md  |  Runtime covered: 00:00:01 to 02:04:06 (closing remarks in an untimestamped `[end]` block)

## 1. Scope
The first third of the session finishes the Session-1 homework on support / resistance / SR by defining exactly what confirms a level flip (a candle *close* through the level, then a retest that rejects) versus what is only a deviation (a close through the level followed by a reclaim with no retest). It then hard-pivots into trading psychology and money management: crypto market-cap rotation cycle, a fixed long-term portfolio allocation table, five separate account types, and a compounding "challenge account" with weekly/daily percentage goals plus per-trade and per-day loss caps. Entry/DCA/stop mechanics appear only as worked examples inside the SR discussion; take-profit placement is never taught in this session.

## 2. Definitions

- **Support** — a level price has bounced from repeatedly from above; "we have many touches from this level. So, it's confirmed." He colours it black on his charts. `[00:10:24]`
- **Resistance** — a level price has rejected from below; coloured red. `[00:08:05]`
- **SR** — his shorthand for a level that has been closed through but not yet retested: "an SR means pending retest." Coloured blue. It is an *intermediate, unconfirmed* state, not a synonym for "support/resistance" as textbooks use it. `[00:25:19]`
- **The flip sequence (support side)** — support must have a candle *close* below it → level turns blue (SR, pending retest) → price returns, retests and rejects → level is now confirmed resistance (red) → if price later closes back above it, it becomes SR again. `[00:02:51]` `[00:03:23]` `[00:03:57]`
- **The flip sequence (resistance side)** — resistance breaks with a close above → SR (blue, pending retest) → price comes back and the retest candle *closes above* → confirmed support (black). `[00:04:36]` `[00:06:15]`
- **Deviation** — a close through a level followed by a reclaim back through it **without** any retest-and-rejection in between; the level keeps its original identity. "A deviation is a breakout, but a fake out." `[00:03:23]` `[00:22:18]` `[00:25:56]` `[00:28:17]`
- **SR strength** — a function of how far price travelled away from the level after the break: "the greater the distance away in terms of percentages away from the resistance or the support... the stronger the SR will be." An 11% move = strong SR; a close right at the line = "a very weak SR." `[00:10:59]`
- **Swing failure pattern (SFP)** — described only in passing: price sweeps the liquidity above a prior high and then "the candle closed below the previous high, it's a swing failure." Explicitly deferred to a later session. `[00:15:33]` `[00:16:06]`
- **Trend line** — requires three points of touch before it may be drawn; may be drawn off candle bodies or off wicks. A trend line is itself a support (uptrend) or resistance (downtrend) and can also become an SR. `[00:32:54]` `[00:33:28]` `[00:34:33]`
- **Lost structure / break of structure** — the sequence higher-high / higher-low breaks: price closes below the last higher low, makes a lower low, then a lower high. "So this isn't a downtrend... I would have cut once I saw that formed." Full treatment deferred. `[01:05:47]` `[01:06:19]`
- **Large cap** — top 50 by market cap; "those are the coins that I specialize in trading." `[00:38:34]`
- **Mid cap** — 50th to 100th by market cap (per CoinGecko / CoinMarketCap). `[00:50:35]`
- **Small cap** — newer coins with good fundamentals, not meme coins. `[00:39:08]`
- **Micro cap** — meme coins / shitcoins; "these are the coins that only run for a small amount of time." `[00:40:19]`
- **Challenge / compounding account** — a separate accountability account with a fixed percentage goal per period; "once you hit the goal, you stop trading." `[01:18:42]` `[01:27:36]`
- **Chop** — never defined; used only as a personal weakness ("chop is weakness. I don't typically trade chop"). `[01:26:28]`

## 3. Hard rules

**S2-R1** — A support level only becomes SR (blue / pending retest) when a candle **closes** below it; a wick below does not flip it.
params: candle close < level; wick-only = no state change
`[00:02:51]`

**S2-R2** — An SR only becomes confirmed resistance after price returns to the level and rejects it; until that retest happens the level's state is "pending".
params: state machine: support → (close below) → SR → (retest + reject) → resistance
`[00:03:23]`

**S2-R3** — On the resistance side, an SR becomes confirmed support only when the retest candle **closes above** the level.
params: retest candle close > level
`[00:06:15]`

**S2-R4** — If price closes back through the level before any retest-and-rejection occurs, the event is a deviation and the level reverts to its original identity (support stays support, resistance stays resistance).
params: reclaim close before retest ⇒ revert state
`[00:03:23]` `[00:25:56]` `[00:28:59]`

**S2-R5** — A level may not transition SR → SR; it must pass through a confirmed resistance or support state first.
params: forbidden transition SR→SR
`[00:02:51]`

**S2-R6** — SR quality is scored by the percentage distance price travelled away from the level after the breaking close; only strong-move SRs are traded.
params: 11% move = "strong SR"; ~2% = "measly"; 1.5% cited as a weak pre-dump move; close right at the level = "very weak SR"
`[00:10:59]` `[00:05:08]` `[00:06:15]` `[00:18:23]`

**S2-R7** — On lower timeframes require an extra confirmation candle after the retest candle; on the 4-hour or daily you may act without it (he flags this as riskier).
params: LTF = retest candle + 1 confirmation candle; 4H/1D = retest candle only
`[00:26:30]`

**S2-R8** — The first entry, taken at the SR level, must be light; size is weighted toward the later DCAs — "our heavier bids are always at the bottom, or the top if you're shorting."
params: entry weight < DCA weight; heaviest fill at the far end of the ladder
`[00:13:17]` `[00:15:33]` `[00:29:32]`

**S2-R9** — Use a maximum of 2–3 DCAs; six DCAs is explicitly rejected.
params: DCA count ∈ {1,2,3}; max 3; 6 = forbidden
`[00:19:29]` `[00:21:45]` `[00:53:24]`
*(Softened/varied: at `[00:13:52]` he says on a daily chart "I don't see any reason to have more than one DCA here", and at `[00:14:25]` "You definitely can have more than one. You just have to go to a lower time frame to find your second DCA"; at `[00:53:24]` he restates it as "one or two DCAs, one or two or three". See S2-C2.)*

**S2-R10** — DCA orders attach to the next confirmed support level below (longs) or the next confirmed resistance level above (shorts), not to fixed price increments.
params: DCA price = next opposing S/R level
`[00:29:32]` `[01:00:07]`

**S2-R11** — When the daily chart offers only one DCA level, drop to a lower timeframe to locate the second DCA level.
params: daily → LTF for DCA2 (LTF unspecified)
`[00:14:25]`

**S2-R12** — Stops go beyond the wick of the swing that is expected to be liquidity-swept, not immediately beyond the level itself.
params: short stop = above the sweep wick high (his worked example: placed above the higher wick, was "almost got wicked"); placing it at the nearer level would have stopped him out
`[00:13:52]` `[00:14:25]` `[00:14:59]`

**S2-R13** — After being stopped out, do not re-enter immediately; wait for a swing failure pattern.
params: re-entry trigger = SFP (candle closes back below the swept previous high)
`[00:14:59]` `[00:15:33]`

**S2-R14** — A trend line requires three touches before it may be drawn and used; two touches is not a trend line. Touches may be candle bodies or wicks.
params: min touches = 3
`[00:32:54]` `[00:33:28]`

**S2-R15** — Support degrades with every retouch; a level with 1–2 touches and a large move away from it is tradeable again, a level on its 4th–6th touch is not.
params: touches 1–2 = playable; touches ≥ ~4 (he counts 4th, 5th, 6th) = "very weak support", do not long
`[00:30:37]` `[00:31:11]` `[00:32:19]`

**S2-R16** — Long-term portfolio allocation is fixed by market-cap bucket.
params: futures 10%; cash / dry powder 20%; large caps 30–40%; mid caps 10–20%; small caps 5%; micro caps & shitcoins 2–5%
`[00:47:44]` `[00:49:29]` `[00:50:35]` `[00:51:09]`

**S2-R17** — Keep at least 20% of the portfolio in cash at all times to bid dips; take profit into that reserve as price rises.
params: min cash 20%
`[00:47:44]` `[00:48:20]`

**S2-R18** — On a long-term position, withdraw the initial capital once the position does 3x (sometimes a partial withdrawal at 2x) so the remainder runs risk-free.
params: 3x = full initial out; 2x = partial (e.g. half of initial)
`[01:14:09]` `[01:14:43]`

**S2-R19** — Do not over-diversify the long-term book.
params: 4–5 large caps (up to 5–7), 3–4 mid caps; 50 coins = forbidden
`[01:12:59]` `[01:13:34]`

**S2-R20** — Per-trade loss caps by style: scalp plays may lose 2–3% of the portfolio; swing plays 4–5%. Exceed them and stop trading.
params: scalp max loss 2–3% of port; swing max loss 4–5% of port (mis-stated once as 5–6% then immediately corrected)
`[01:30:26]` `[01:30:58]` `[01:47:44]`

**S2-R21** — Two losing trades in one day ends trading for that day.
params: daily loss-count limit = 2
`[01:30:58]`

**S2-R22** — Once the challenge account hits its goal for the period, stop trading for the remainder of that period.
params: hit weekly goal on day 1 ⇒ no more trades that week
`[01:27:36]` `[01:28:09]` `[01:32:09]`

**S2-R23** — The challenge-account goal compounds: each period's starting balance is the previous period's ending balance, and the goal is that starting balance × goal %.
params: goal_n = balance_start_n × g; balance_start_{n+1} = balance_end_n. Worked: 1000 → goal 80 (8%); 1080 → goal 86.40; 1200 → residual goal ~59–60
`[01:20:55]` `[01:21:30]` `[01:22:04]`

**S2-R24** — Never increase risk-per-trade after a winning streak; de-risking downward is permitted.
params: 2% → 4% forbidden; 2% → 1% allowed; 2% → 3% explicitly forbidden
`[01:23:41]` `[01:24:14]` `[01:33:49]` `[01:37:44]`

**S2-R25** — Position-size percentage must be held constant in percentage terms as the account grows (1% of 1,000 and 1% of 5,000 are both "1%").
params: risk expressed as % of current equity, not fixed notional
`[01:33:49]`

**S2-R26** — If the account has grown and you are then losing consistently, cut the account in half and restart from the smaller balance; or bank a chunk to the bank/spot account and restart at the original size.
params: 5,000 → restart at 2,500; 200K → withdraw, restart at 10K
`[01:34:23]` `[01:35:33]`

**S2-R27** — Do not trade FOMC days; wait until the event is done, wait for a range to form, then trade that range.
params: block = FOMC day; resume = after event + range formation
`[01:29:18]`

**S2-R28** — Exit (or partially exit) a position when market structure breaks: a close below the last higher low, followed by a lower low and a lower high.
params: close < last higher low ⇒ cut
`[01:05:47]` `[01:06:19]` `[01:10:12]`

**S2-R29** — On spot he uses no stop-loss orders; he closes manually when the support level under his final DCA flips to resistance.
params: spot exit trigger = final-DCA support confirmed flipped to resistance
`[01:00:42]` `[01:01:18]`

**S2-R30** — Only enter at a support (for longs) / resistance (for shorts) level; never enter because price is moving in your direction.
params: entry price must equal a level, not a momentum condition
`[01:04:38]`

**S2-R31** — Once a support level is lost, stop adding to that position — do not keep DCAing a losing coin lower.
params: level lost ⇒ no further DCA; cut or re-enter lower at the next level
`[00:52:14]` `[00:53:24]` `[02:02:58]`

**S2-R32** — Account separation: five accounts — long-term (cold storage), short-term spot, leverage swing, leverage scalp, challenge/compounding. The swing account runs **one** play at a time; the scalp account may run multiple.
params: swing = 1 concurrent position; scalp = many; scalp funded with ~1,000 out of a ~15,000 leverage balance (≈6.7%)
`[01:11:20]` `[01:16:27]` `[01:17:34]`

**S2-R33** — Run the challenge account on a **weekly** cadence for spot; the daily cadence is only for leverage.
params: spot = weekly goal; leverage = daily or weekly
`[01:38:15]` `[01:46:00]`

**S2-R34** — On spot, do not put the full allocation into one trade; roughly 20% of the spot balance spread over one or two trades.
params: ~20% of port across 1–2 spot trades
`[01:38:15]`

**S2-R35** — Exclude coins with erratic high/low wicking on lower timeframes (low liquidity) from the tradeable universe.
params: filter = "wicks everywhere... that make no sense"; no numeric threshold given
`[01:26:28]`

## 4. Parameters and thresholds

| parameter | value | applies to | timestamp |
|---|---|---|---|
| Flip confirmation | candle **close** through level | S/R state machine | `[00:02:51]` |
| Confirmation candle after retest | required on LTF, optional on 4H/1D | flip confirmation | `[00:26:30]` |
| Strong SR move | 11% away from level | SR quality score | `[00:10:59]` |
| Weak SR moves | 1.5%, 2% ("measly"), or close at the line | SR quality score | `[00:05:08]` `[00:06:15]` `[00:10:59]` |
| Realised move on the worked short | 18% down | SR short example | `[00:15:33]` |
| Max DCAs | 2–3 (6 = forbidden; 1 on the daily) | entry ladder | `[00:13:52]` `[00:19:29]` `[00:21:45]` |
| Rejected DCA split example | 5 / 10 / 15 / 20 / 25 / 30% | why not to use 6 DCAs | `[00:21:11]` |
| Illustrative 2-leg split | 50 / 50 | DCA sizing | `[00:20:36]` `[01:00:07]` |
| Trend line minimum touches | 3 | trend line validity | `[00:32:54]` |
| Support touches before it is "weak" | 4th, 5th, 6th touch = do not long | level quality | `[00:31:11]` |
| Support touches that are still playable | 1–2 touches + large move away | level quality | `[00:31:11]` |
| Confluences on the Injective example | ~3 (order block + support + fibs) | confluence count | `[00:31:46]` |
| Large cap definition | top 50 market cap | universe | `[00:38:34]` |
| Mid cap definition | rank 50–100 | universe | `[00:50:35]` |
| Futures allocation | 10% of total portfolio | allocation | `[00:47:44]` |
| Cash / dry powder | 20% at all times | allocation | `[00:47:44]` |
| Large cap allocation | 30–40% | allocation | `[00:49:29]` |
| Mid cap allocation | 10–20% | allocation | `[00:50:35]` |
| Small cap allocation | 5% | allocation | `[00:51:09]` |
| Micro cap / shitcoin allocation | 2–5% | allocation | `[00:51:09]` |
| Long-term coin count | 4–5 large (up to 5–7), 3–4 mid | allocation | `[01:12:59]` `[01:13:34]` |
| Long-term entry ticket size | $5K–$10K per coin (his own) | allocation | `[01:13:34]` |
| Take initial capital out at | 3x (sometimes partial at 2x) | long-term management | `[01:14:09]` |
| Spot take-profit cadence (short-term acct) | after 10–15% moves | short-term spot | `[01:15:16]` |
| Cited own realised spot moves | ~12% then ~15% (SOL from 129) | short-term spot | `[00:48:20]` `[00:48:55]` |
| Scalp max loss | 2–3% of portfolio | risk cap | `[01:30:26]` |
| Swing max loss | 4–5% of portfolio (mis-said 5–6%, corrected) | risk cap | `[01:30:58]` `[01:47:44]` |
| Daily loss-count stop | 2 losses | risk cap | `[01:30:58]` |
| Original weekly goal | 20% (leverage, last bull run) | challenge account | `[01:19:47]` `[01:25:18]` |
| "More attainable" weekly goal | 8% | challenge account | `[01:20:55]` |
| Suggested spot weekly goal ($1,000 acct) | 5–10% | challenge account | `[01:39:55]` |
| Suggested leverage starting goal | 1–2% per day (1% if starting with $100) | challenge account | `[01:39:55]` |
| His current personal goal | 5% per day *or* 5% per week (stated ambiguously) | challenge account | `[01:38:49]` |
| Compounding demo | 2%/day on $100 → ~$137,000 in a year; 2%/day on $1,000 → ~$1M | motivation | `[01:31:32]` `[01:32:09]` |
| His live challenge result | $1,000 → ~$42–45K in 35 days, ~20 trades | motivation | `[01:32:41]` `[01:33:16]` |
| His leverage challenge run | started $20K, reached day 142 before restart; spot version started $50K | challenge account | `[01:38:49]` |
| Risk step forbidden | 2% → 3% or 4% | risk discipline | `[01:23:41]` `[01:37:44]` |
| Risk step allowed | 2% → 1% | risk discipline | `[01:37:44]` |
| Scalp account funding | ~$1,000 of a ~$15,000 leverage balance | account structure | `[01:17:34]` |
| Spot play position size example | 12% of portfolio ($120 of $1,000), willing to lose ~half of it (6% of port) | spot sizing | `[01:00:42]` `[01:01:18]` |
| Spot allocation per trade | ~20% of spot balance over 1–2 trades | spot sizing | `[01:38:15]` |
| Default leverage in his log | 10x | trade log | `[01:52:12]` |
| Trade-log worked example | BTC long 57,800 → TP 59,000 = +20.76% at 10x (2.0% unleveraged); SL 57,000 | trade log | `[01:52:12]` `[01:52:52]` |
| Win rate | manual input, not calculated; example 1 of 3 | trade log | `[01:56:53]` |
| His monthly trade counts | 25 (Jan), 26 (Feb), typically ~15 | trade log | `[01:58:36]` |
| Scalp holding period | few hours to a day at most | style | `[01:17:02]` |
| Swing holding period | days to weeks | style | `[01:17:02]` |
| Long-term holding period | > 1 year, until cycle end | style | `[01:11:54]` `[01:12:27]` |
| His screen time | ~2–3 hours per **week** | style | `[02:04:06]` |
| Micro-cap ticket size (his own) | $500–$2,000 ("1K in, made 6K") | universe | `[01:51:02]` |
| Drawdown-from-highs table used to argue allocation | BTC −25%, ETH −30%, SOL −33%, small cap −60%, micro cap ≈ −100% | allocation rationale | `[00:42:40]` `[00:43:15]` `[00:43:53]` `[00:44:29]` |

## 5. Entry model

Setup identification is a state machine on a horizontal level, run on closes:

1. Draw a level that has been confirmed by multiple touches (support = bounces from above; resistance = rejections from below). `[00:00:37]` `[00:10:24]`
2. Wait for a candle to **close** through it. The level becomes SR / "pending retest". `[00:02:51]`
3. Measure the % distance price travels away from the level after that close. A large move (11% cited) = strong SR and a tradeable setup; a close right at the level = weak, skip. `[00:10:59]` `[00:18:23]`
4. Wait for price to return to the SR level. On a rejection (short case) or a close back above (long case), the flip is confirmed. `[00:03:23]` `[00:06:15]`

Order placement, in order:

- **First entry** — at the SR level itself, on the retest. Deliberately **light**, because the retest may fail (a deviation) and you cannot know that in advance. "Entry at the SR is going to be light compared to your DCA." `[00:13:17]` `[00:29:32]`
- **DCA 1** — at the next confirmed opposing level (next resistance above for a short; next support below for a long). `[00:13:52]` `[00:29:32]` `[01:00:07]`
- **DCA 2 (final)** — at the level after that; if the daily chart does not show a second level, drop to a lower timeframe to find it. `[00:14:25]`
- **Weighting** — size increases down the ladder: "our heavier bids are always at the bottom, or the top if you're shorting." He rejects narrow 6-leg ladders (5/10/15/20/25/30) because the far legs never fill and the achieved average is no better than a 2-leg ladder that does fill. `[00:15:33]` `[00:20:01]` `[00:21:11]` `[00:21:45]`
- The whole reason entry is light is to leave room for error: "this is why we always always go light at entry to give ourselves room for error on the way up or down." `[00:16:06]`

Spot version of the same model: buy the first tranche at the flipped support, add at the next support down, average sits mid-ladder if using 50/50, heavier toward the bottom otherwise. `[01:00:07]`

## 6. Stops

- Stops go **beyond the wick of the swing likely to be swept**, not immediately beyond the entry level. In his daily short example he placed the stop above a higher wick specifically because "I knew that there was going to be a liquidity sweep"; the nearer placements he draws would both have been stopped out. `[00:13:52]` `[00:14:25]` `[00:14:59]`
- The stop that survived was still nearly wicked — "stop loss almost got wicked" — so the intended buffer is small, just above the sweep high. `[00:14:25]`
- What makes a stop too wide is expressed in **portfolio terms, not price terms**: the stop is too wide if being hit costs more than 2–3% of the portfolio on a scalp or 4–5% on a swing. He explicitly separates position size from risk: "you don't have to use four to 5% of your portfolio. You can use 20% of your portfolio in a leverage trade. But it's all about the position sizing and how much you lose if your stop loss to get hit." `[01:30:26]` `[01:47:44]` `[01:48:17]`
- On spot he runs **no** stop-loss orders and closes manually instead (see S2-R29). `[01:00:42]`
- Removing a stop-loss mid-trade is named as one of the cascade errors that destroys accounts. `[01:24:14]` `[01:24:46]`
- Counter-example from his own history: no stop-loss on a heavy BTC leverage position → −$800K unrealised. "So now I always use stop-losses." `[01:42:44]` `[01:49:23]`

## 7. Take profit and trade management

This session contains **no TP placement rules**. What is stated:

- He runs multiple TPs and leaves them resting: "I have TPS set... I only adjust TPS if I need to. Otherwise, everything is set." `[02:04:06]`
- His trade log has room for two TP columns and averages the percentage across them, but he never says where they go. `[01:52:12]` `[01:57:27]`
- Short-term spot account: take profit after 10–15% moves and rotate into the next setup. `[01:15:16]`
- Worked spot example: bid SOL at 129, took profit into a ~12% move, re-bid the same support at 129, took profit again into ~15%. Level-based, not target-multiple based. `[00:48:20]` `[00:48:55]`
- Long-term book: remove initial capital at 3x (partial at 2x) and let the rest run. `[01:14:09]`
- De-risking a spot position into strength is endorsed when price runs back toward break-even. `[01:02:26]` `[01:02:59]`
- **No stop-loss trailing rule on TP hits is given anywhere in this session.**

## 8. Invalidation and re-entry

- **Deviation invalidates the flip.** A close through the level followed by a reclaim with no retest returns the level to its prior identity. You cannot know it was a deviation until the reclaim close prints: "You don't know if something's a deviation until it reclaims back below." `[00:06:55]` `[00:28:59]` `[00:30:04]`
- **A trade taken at an unconfirmed SR is expected to sometimes lose to a deviation** — that is precisely why entry size is light and the stop is the backstop: "at that point your average becomes something like this and then you're just playing it to your stop loss." `[00:29:32]`
- **Zone death by touch count.** Each retouch of a support weakens it; by the 4th–6th touch he will not long it again. `[00:31:11]` `[00:32:19]`
- **Structure invalidation.** Close below the last higher low → lower low → lower high = downtrend confirmed, cut the position. `[01:05:47]` `[01:06:19]` `[01:10:12]`
- **Spot invalidation.** If the support beneath the final DCA is lost and flips to resistance, cut. `[01:00:42]` `[01:01:18]`
- **Re-entry after a stop-out** requires a swing failure pattern, not simply price returning to the level. `[00:14:59]`
- **Re-entry after cutting** is at the next lower support: cut the loss (example: −25%), re-buy the lower support, recover on the bounce (example: +35% / +77%). `[01:01:54]` `[01:09:40]`
- **He explicitly refuses to average down** into a coin whose support is lost: "Don't keep DCAing into something that's possibly dead." `[00:52:14]` `[00:53:24]`
- A weak level may still be re-traded if it has only 1–2 touches, price moved far away, and additional confluences (order block, fibs) sit on it. `[00:31:11]` `[00:31:46]`

## 9. Timeframes

- Timeframes used in worked examples: **daily** (primary for the SR examples and DCA layout) `[00:09:50]` `[00:13:52]`, **8-hour** (deviation example) `[00:28:17]`, **4-hour** `[00:06:15]`, **1-hour** (deviation example) `[00:24:07]`, **weekly** (micro-cap sizing example) `[00:56:11]`.
- **Higher-timeframe confirmation logic:** on the daily or 4-hour, a flip may be acted on without an extra confirmation candle after the retest; on lower timeframes he wants that extra candle. "Lower time frames I want to say yes, but if you have a higher time frame such as the daily or 4 hour you can go without it. It's going to be risky, but this is why we go in light with our DCAs." `[00:26:30]`
- **Timeframe drilling for DCAs:** when the daily only shows one DCA level, drop to a lower timeframe to place the second. `[00:14:25]`
- **Cycle exit** is defined on a higher timeframe: "it's when market structure is broken on a higher time frame." Which timeframe is not specified. `[01:12:27]`
- **Holding periods by account:** scalp = hours to a day `[01:17:02]`; swing = days to weeks `[01:17:02]`; long-term = a year or more `[01:11:54]`.
- Challenge-account cadence: weekly for spot, daily or weekly for leverage. `[01:38:15]` `[01:46:00]`

## 10. Confluence

- Named confluence types: **order blocks, supply zones, horizontal support/resistance, fibs, trend lines.** All except the horizontals are deferred to later sessions. `[00:18:57]` `[00:31:46]` `[00:32:19]`
- Purpose is level selection, not signal generation: "Which line is the one that I'm going to be using? Which line is stronger? Once we add more confluence on it... then you will know which line is going to be stronger based on the types of confluences that we use." `[00:18:57]`
- Only worked count in this session: on Injective he counts an order block + the support line + "probably some fibs" = "about three confluences to go from there." `[00:31:46]`
- He also counts a trend line coinciding with a horizontal as an additional confluence on that level. `[00:32:19]`
- **He never states a required minimum number of confluences, and never weights them.**

## 11. Explicitly excluded

- **Six (or narrowly-spaced many-leg) DCA ladders** — "I would not do more than two or three DCAs... I wouldn't go six." `[00:19:29]` `[00:21:45]`
- **Stop-loss orders on spot bags** — "Right now I don't have stop losses on my spot bags. I do manual closes." `[01:00:42]`
- **FOMC days** — no trading until the event is over and a range has formed. `[01:29:18]`
- **Chop** — "chop is weakness. I don't typically trade chop." `[01:26:28]`
- **Low-liquidity / erratically wicking coins** — "when you see wicks everywhere, high wicks, low wicks that make no sense, I would stay away from those coins. Those are coins that I personally do not trade." `[01:26:28]`
- **XRP** — "I suck at trading XRP... so I removed XRP." Reason: it does not move, only reacts to SEC news, trades in a very tight range. `[01:27:03]` `[01:44:56]`
- **Injective** — "this is on my no trade list personally." `[01:45:28]`
- **Heavy positions in micro / small caps** — capped at 2–5% and 5% respectively; "I see that a lot of people are overpositioned in micro cap or small cap coins." `[00:36:15]` `[00:51:09]`
- **Fundamental / narrative trading** — "I play technical charts... I prefer technical over fundamental. I'm not a fundamental guy." `[01:04:38]` `[01:08:35]`
- **Buying because price is going up** — "You only want to buy at support. You don't want to buy something because the coin's going up." `[01:04:38]`
- **Chasing a missed goal the following week** — "they're trying to chase their losses the next week. Don't do that." `[01:29:52]`
- **Increasing risk after a win streak** — "just never go from 2% if you're consistent to 3%." `[01:37:44]`
- **Adding margin to a losing trade to avoid taking the loss** — listed as the error cascade. `[01:24:46]` `[01:25:18]`
- **Day trading** — "I'm not a day trader. I'm a swing trader." `[end]` (immediately after `[02:04:06]`)
- **Coins he considers permanently topped** (as opinion, not a rule): DOT, LINK, Litecoin, Dogecoin to $1. `[00:45:34]` `[00:46:07]`

## 12. Ambiguities for the bot

**S2-A1** — "Reject" is never defined. The whole state machine hinges on "retest and reject", but no candle pattern, wick-to-body ratio, close condition, or minimum bounce % is given for the short/resistance side. Only the long side gets a mechanical version ("the retest candle has to close above"). A coder must invent the rejection test. `[00:03:23]` `[00:06:15]`

**S2-A2** — "Retest" has no tolerance band. How close price must come to the level to count as a retest (touch of the exact price, a % band, a wick vs a body) is never specified, and his levels are hand-drawn lines with visible thickness. `[00:03:23]`

**S2-A3** — Level construction is entirely manual. He never gives a programmatic way to derive the horizontal levels themselves — swing-detection lookback, wick vs body anchoring, how many bars, or how to merge nearby levels into one zone. Everything downstream depends on this.  `[00:00:37]` `[00:10:24]`

**S2-A4** — The SR-strength cutoff is undefined. 11% is "strong", ~2% is "measly", 1.5% is weak, a close at the line is "very weak" — but there is no threshold separating tradeable from skip, and no statement of whether the % is measured to the extreme or to a close. `[00:05:08]` `[00:10:59]`

**S2-A5** — Touch counts for level confirmation and level death are fuzzy. "Many touches" confirms a level; 1–2 touches is still playable; 4th/5th/6th touch is "very weak". No exact confirm-at-N or dead-at-N, and no rule for how a touch is counted (wick? body? one per swing?). `[00:10:24]` `[00:31:11]`

**S2-A6** — Entry vs DCA size split is never quantified. "Light" at entry and "heavier at the bottom" is the whole specification; 50/50 appears only as an illustrative simplification and the 5/10/15/20/25/30 ladder is presented as the thing *not* to do. `[00:15:33]` `[00:20:36]` `[00:21:11]`

**S2-A7** — "Go to a lower time frame to find your second DCA" — which lower timeframe, and which level on it, is unstated. `[00:14:25]`

**S2-A8** — Stop offset above the sweep wick is not quantified (no ticks, no %, no ATR). His own example was "almost got wicked", implying a very tight buffer. `[00:14:25]`

**S2-A9** — Which wick to place the stop above is discretionary and anticipatory: "I knew that there was going to be a liquidity sweep. Like personally, I knew." This is the single least codeable statement in the session — it requires predicting the sweep before it happens. `[00:14:59]`

**S2-A10** — SFP is the stated re-entry trigger but is defined in one clause and deferred ("I'll cover that a little bit later on in the course"). No lookback for "the previous high", no timeframe, no volume or wick condition. `[00:14:59]` `[00:16:06]`

**S2-A11** — **No take-profit rule exists in this session.** He has multiple TPs resting and takes profit "after 10–15% moves" on the short-term spot account, but never says how many TPs, at what levels, or with what size split — and gives no stop-trailing rule on TP hits at all. A coder has to source this from another session. `[01:15:16]` `[01:57:27]` `[02:04:06]`

**S2-A12** — "Break of structure" needs a swing-point algorithm he never provides (fractal lookback, minimum swing size, timeframe). He defers it twice. `[01:05:47]` `[01:10:12]`

**S2-A13** — Order blocks, supply zones and fibs are named as the confluences that decide which level is stronger, but all three are deferred; without them there is no level-ranking function. `[00:18:57]`

**S2-A14** — Confluence is never turned into a threshold. Three confluences appear in one example; no minimum is required and no weighting scheme is given, so "which line is stronger" stays subjective. `[00:31:46]`

**S2-A15** — "Deviation" has no time limit. An SR is "pending retest" indefinitely — "it could take, you know, many candles after that." There is no bar count after which a pending SR expires, which means a backtest can hold pending states forever. `[00:02:51]` `[00:03:23]`

**S2-A16** — The confirmation-candle rule is conditional on a soft boundary: extra candle on "lower time frames", optional on "the daily or 4 hour". Where the boundary sits (1H? 2H?) is not stated, and he hedges the rule itself ("yes and no, it depends on the situation"). `[00:26:30]`

**S2-A17** — Trend lines may be drawn "from candles" or "from wicks", which yields several valid lines from the same swings, with no selection rule. `[00:32:54]`

**S2-A18** — Position size and risk are conflated throughout. He gives 12% of portfolio into a spot play `[01:00:42]`, 20% of a spot balance across 1–2 trades `[01:38:15]`, 1–2% risk per trade `[01:23:08]` `[01:33:49]`, and 2–5% max loss caps `[01:30:26]` — these are three different quantities and the mapping between them is never written down.

**S2-A19** — "Chop" is a hard exclusion but is never defined. No range width, no ADX-equivalent, no bar count. `[01:26:28]`

**S2-A20** — "Wicks everywhere that make no sense" as a liquidity filter has no numeric form (no wick-to-body ratio, no volume floor, no spread test). `[01:26:28]`

**S2-A21** — The challenge-account goal is unresolved: 20% weekly originally, 8% as "attainable", 5–10% weekly for a $1,000 spot account, 1–2% daily for leverage, and his personal goal stated as "5% a day or 5% a week." A coder must pick one. `[01:19:47]` `[01:20:55]` `[01:38:49]` `[01:39:55]`

**S2-A22** — Whether the loss caps (2–3% scalp, 4–5% swing) apply to the challenge-account balance, the leverage-account balance, or total net worth is not stated; his examples slide between them. `[01:30:26]` `[01:47:44]`

**S2-A23** — The "two losses in a day → stop" rule does not define whether a loss is any negative close or only a stop-out, nor whether it resets at UTC midnight or on his own schedule (his sleep schedule is explicitly irregular). `[01:30:58]` `[02:04:06]`

**S2-A24** — Win rate is a manual field in his log; he never states an expected win rate or expectancy, so there is no benchmark to validate a backtest against. `[01:56:53]`

**S2-A25** — No signal timeframe is declared for the system as a whole. Examples jump between 1H, 4H, 8H, daily and weekly without saying which one the setup is scanned on. `[00:06:15]` `[00:24:07]` `[00:28:17]`

## 13. Contradictions

**S2-C1** — *Swing loss cap.* At `[01:30:58]` he says "Swing trades, you want to lose max 5 to 6% of your port or sorry, four to 5%" — a live self-correction. At `[01:47:44]` he restates it as "go in with four to 5% risk". Use 4–5%; the 5–6% figure is a slip, but both are on tape.

**S2-C2** — *DCA count.* "I don't see any reason to have more than one DCA here if you're using the daily chart" `[00:13:52]` → immediately "You definitely can have more than one" `[00:14:25]` → "I would not do more than two or three DCAs" `[00:19:29]` → "Three is okay, but depends on how wide your range is for DCA" `[00:22:18]` → "this is why when I mentioned DCAs is just to have one or two DCAs, one or two or three" `[00:53:24]`. The count is timeframe- and range-dependent but the dependency is never formalised.

**S2-C3** — *Confirmation candle.* Asked directly whether a third candle is needed after the retest, he answers "so yes and no it depends on the situation" `[00:26:30]`. The rule is stated and softened in the same breath, and he then acts without one on his own live BTC trade `[00:27:08]`.

**S2-C4** — *Stop-losses.* "Right now I don't have stop losses on my spot bags. I do manual closes" `[01:00:42]` vs "So now I always use stop-losses" `[01:49:23]` vs "again, have stop losses... you want to keep your losses small" for challenge swing plays `[01:47:44]`. Reconcilable as spot = manual close, leverage = hard stop — but he never says that explicitly, and a bot needs the distinction made for it.

**S2-C5** — *Cash reserve.* "I like to keep 20% available at all times" `[00:47:44]` vs "Right now that I have the dry capital, I definitely have more than 20% available" `[00:48:55]`. 20% is a floor in one place and an approximate target in the other.

**S2-C6** — *Cutting losers.* The trading rules say cut the moment the support level is lost and stop DCAing `[00:53:24]` `[01:00:42]`, but for the long-term book he says the opposite: "if it's a long-term hold, I wouldn't suggest cutting anything" `[02:02:58]`, and earlier "I wouldn't sell it completely... you can definitely derisk" `[00:58:22]`. The rules only apply to the trading accounts, which is stated once — "if you are an investor, this does not apply to you" `[00:53:58]` — and must be encoded as an account-scoped switch.

**S2-C7** — *Challenge goal.* Four different goal levels are given for what is presented as one mechanism (20% / 8% / 5–10% weekly / 1–2% daily), plus a personal goal stated as both daily and weekly in one sentence: "my goal is to hit 5% a day or 5% a week" `[01:38:49]`.

**S2-C8** — *Discretionary override of a mechanical rule.* The stop placement in the flagship worked example is justified by private foreknowledge — "I knew that there was going to be a liquidity sweep. Like personally, I knew" `[00:14:59]` — while the alternative placements he draws follow the stated rule and lose. The stated rule and the demonstrated behaviour disagree.

**S2-C9** — *Likely cross-session conflict:* position sizing and leverage were covered in Session 1 ("remember at the beginning of the first session, I went over position sizing and leverage" `[01:24:14]`); the percentages here (1%, 2%, 12%, 20%) should be checked against S1 before encoding. Likewise SFP, market structure, order blocks, supply zones, fibs, trend lines and deviations are all explicitly deferred to later sessions `[00:16:06]` `[00:32:19]` `[00:34:33]` `[01:05:47]` — expect their fuller definitions there to override the sketches given here.
