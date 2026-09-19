# S7 — Market structure breaks, swing failure patterns (SFP), double tops/bottoms; final conceptual class

Source: transcripts/S7.md  |  Runtime covered: 00:00:01 to 01:36:38

## 1. Scope
This is the last conceptual session. It teaches (a) how to define trend mechanically via higher highs/higher lows and lower highs/lower lows, and how a market structure break (MSB / BOS / CHoCH) is confirmed by a candle-body close through the last opposing swing point; (b) swing failure patterns — wick takes prior swing liquidity, body closes back inside — as an entry trigger and as a late-arriving confluence; (c) double bottom / double top as reversal and long-term-exit signals. It also carries forward the prior sessions' fib/order-block/SR entry machinery in Q&A form, and adds explicit position-size reduction rules for counter-trend trading.

## 2. Definitions

- **Uptrend** — price putting in higher lows and higher highs. `[00:22:53]`
- **Higher low** — a low that is higher than the previous low. **Higher high** — a high that is higher than the previous high. `[00:23:28]`
- **Lower high** — a high that is lower than the previous high. `[00:24:38]`
- **Market structure break (MSB)** — a candle **body** close beyond the last opposing swing point; bearish = close below the last higher low, bullish = close above the last lower high. He states MSB, "break of structure", and "change of character / CHoCH" all mean the same thing. `[00:19:28]` `[00:26:59]` `[00:34:30]`
- **Order block** — "last red candle before directional change." He uses this same phrase for both bullish and bearish order blocks. `[00:06:10]` `[00:39:36]`
- **Demand zone** — price goes up, consolidates, then goes up again; the "sufficient gap" consolidation creates the demand zone. `[00:10:04]`
- **Supply zone** — price comes down, consolidates within a range, then continues down; that range is the supply zone (can be very wide). `[00:46:12]`
- **SR point** — a level that was rejection/resistance, then broke out and flipped; on retest it is an SR point. Two touches is enough to call it. `[00:10:43]` `[00:05:04]`
- **Swing failure pattern (SFP)** — the wick takes out the previous swing high (grabs all its liquidity) but the candle **body closes below** that swing high point; "a swing failure just means that we failed to reclaim this level", followed by a swing in the other direction. Bullish SFP is the mirror: wick below the prior swing low, body closes above it. `[01:14:44]` `[01:15:17]` `[01:18:06]`
- **Double bottom** — a low, a neckline, then a second low **close to the same level** as the first (bodies, not wicks). Adam-and-Eve (one V, one cup) is his favourite name for it but shape does not matter. `[01:04:57]` `[01:09:01]`
- **Double top** — a top, then a rejection from the same point; "usually leads lower." `[01:07:22]`
- **Diagonal support / diagonal resistance** — his terms for the uptrend line under price and the downtrend line above it. `[00:49:00]`
- **Deviation** — a break out of a range that closes back inside it. `[01:30:16]` `[00:05:04]`

Deliberate departures from textbook:
- Structure is judged on **candle bodies only**, never wicks — he says explicitly that other analysts use wicks and he does not. `[01:11:53]`
- A double bottom made by a **long wick** does not count as a double bottom for him. `[01:10:48]` `[01:11:20]`
- He treats SFP as a *confluence that appears after* zones are marked, not a standalone system. `[01:32:31]` `[01:34:15]`

## 3. Hard rules

**S7-R1** — Draw bullish fib retracements anchored swing low → swing high and look for the bounce at the golden pocket or the 0.786.
params: fib levels used = golden pocket, 0.786. `[00:04:30]` `[00:05:36]` `[00:18:17]`

**S7-R2** — Bearish fibs / bearish order blocks / supply-zone plays use the identical logic mirrored; he states the rules are the same.
params: none. `[00:09:28]`

**S7-R3** — Do not enter an order block once roughly 70–80% or more of its liquidity has been taken.
params: 70–80% fill threshold. `[00:09:28]` `[00:07:47]`

**S7-R4** — Exception to R3: an order block whose liquidity has been taken is still playable if a strong higher-timeframe support sits on it with few touches (2nd or 3rd touch of that support).
params: touch count 2–3 = "great area to go long". `[00:08:22]`

**S7-R5** — An order block with ALL of its liquidity taken is invalid; if there is no other confluence, do not long it — play the support line underneath instead.
params: none. `[00:07:14]` `[00:08:54]` `[00:38:29]`

**S7-R6** — Skip order blocks formed by a very small candle ("smaller than a pinky nail"); play the support line instead.
params: none numeric. `[00:37:22]`

**S7-R7** — Include a zone's wick in the entry zone only if the resulting stop stays inside risk tolerance; a ~2% wick is fine to include, a 3–4% wick is not, and he rejects an 18% stop in favour of a 9% one.
params: ~2% wick include; 3–4% wick exclude; 18% stop rejected, 9% accepted. `[00:10:04]` `[00:11:18]` `[00:13:39]`

**S7-R8** — Size every trade so the maximum loss is 4–5% of portfolio; his worked default is 10% of portfolio deployed with leverage set to produce that 4–5% max loss on a swing play.
params: position 10% of portfolio; max loss 4–5%. `[00:20:00]` `[00:20:33]` `[00:25:54]`

**S7-R9** — When trading against the trend, halve everything: ~5% of portfolio instead of 10%, risking only 2–3% instead of 4–5%.
params: 5% position; 2–3% risk. `[00:20:00]` `[00:20:33]`

**S7-R10** — Counter-trend trades must be dropped to a lower timeframe and taken as scalps, with fast profit-taking.
params: scalp timeframes 5m/10m/15m. `[00:20:00]` `[00:25:12]` `[00:26:26]`

**S7-R11** — All structure (swing highs/lows, breaks, double bottoms) is evaluated on candle-body closes only; when in doubt switch the chart to line mode.
params: none. `[00:18:50]` `[00:28:05]` `[01:10:48]` `[01:11:53]`

**S7-R12** — Bearish MSB triggers when a candle body closes below the last higher low.
params: none. `[00:19:28]` `[00:39:02]` `[00:53:05]`

**S7-R13** — Bullish MSB triggers when a candle body closes above the last lower high.
params: none. `[00:26:59]` `[00:33:48]` `[00:41:17]`

**S7-R14** — Do not open a short before there is a candle body closure below the last higher low.
params: none. `[00:28:40]`

**S7-R15** — After a bullish MSB, wait for a retest of the broken lower high to hold as support before treating the trend as changed and going long.
params: none. `[00:27:31]` `[00:33:48]` `[00:47:19]`

**S7-R16** — After a bearish MSB, the short trigger is the retest of the broken higher low as resistance (or a rejection at a supply zone / bearish OB / heavy resistance at the new lower high), with stops above that resistance.
params: none. `[00:28:40]` `[00:40:44]` `[00:29:13]`

**S7-R17** — Cancel a pending bullish setup if the market has since put in lower highs / lost the trend. (SOFTENED later — see S7-C1.)
params: none. `[00:16:33]` `[00:17:06]`

**S7-R18** — Start entries at an SR point ("I always start my entries at SR points"), with the smallest size first, then DCA heavier below, so the average sits mid-zone.
params: first entry = lightest capital; DCA = heavier. `[00:06:41]` `[00:07:14]` `[00:22:18]` `[00:40:10]`

**S7-R19** — Prefer the entry price that stacks the most confluence (e.g. start of the order block where it overlaps the SR point) rather than mechanically the top of the SR.
params: none. `[00:06:41]` `[00:44:27]`

**S7-R20** — Higher timeframe takes precedence: define the zone on the higher timeframe even if a lower timeframe range looks cleaner, otherwise you miss the SR point and get left behind.
params: none. `[00:21:45]` `[00:22:18]`

**S7-R21** — Bearish SFP: wick takes out the prior swing high, candle body closes below it → short on that close, stop automatically above the wick high.
params: none. `[01:14:44]` `[01:15:17]` `[01:15:50]` `[01:19:52]`

**S7-R22** — Bullish SFP: wick takes out the prior swing low, candle body closes above it → long, stop below the wick low; entry on the next candle open.
params: none. `[01:18:06]` `[01:20:57]` `[01:24:22]`

**S7-R23** — If the wick takes the level but the candle does NOT close back beyond it, it is not an SFP — no trade.
params: none. `[01:22:39]`

**S7-R24** — Wait for the candle to actually close; entering mid-candle is invalid because the candle can still close back through the level and void the SFP.
params: none. `[01:20:57]`

**S7-R25** — The SFP candle cannot be adjacent to the swing-point candle it is raiding ("candles cannot be next to each other").
params: minimum gap not numerically specified. `[01:19:52]`

**S7-R26** — If the SFP wick is deep, do not take the trade at the SFP stop; either drop to a lower timeframe (e.g. 15m) to find a support/consolidation to place a tighter stop, or skip the trade entirely.
params: a 17% entry-to-stop distance is explicitly rejected. `[01:17:32]` `[01:18:06]` `[01:18:39]` `[01:23:14]`

**S7-R27** — If you miss the SFP close, do not chase mid-move; place a limit order back at the previous swing high/low point with the stop above/below the wick — tighter stop, better R:R.
params: none. `[01:16:25]` `[01:16:58]` `[01:21:31]` `[01:25:28]`

**S7-R28** — Two swing highs/lows that sit very close to each other produce weak SFPs; greater distance between them means more resting bids and a stronger SFP.
params: no distance threshold given. `[01:24:56]` `[01:25:28]`

**S7-R29** — Higher-timeframe SFPs give deeper retraces than lower-timeframe SFPs; size/expectation accordingly.
params: none. `[01:24:56]` `[01:26:03]`

**S7-R30** — Do not trade SFPs standalone; support/resistance and supply/demand must already be marked, and the SFP is added as confluence once it forms.
params: none. `[01:32:31]` `[01:33:41]` `[01:34:15]`

**S7-R31** — Do not take an SFP against the prevailing trend just because it printed (bullish uptrend + bearish SFP = skip); several worked examples are shown getting stopped out.
params: none. `[01:15:17]` `[01:26:36]` `[01:27:14]` `[01:29:41]`

**S7-R32** — Double bottom: second body-low close to the first, break the neckline, retest it, then long; measured target = the bottom-to-neckline distance projected above the neckline.
params: target = 1x (neckline − bottom). `[01:04:57]` `[01:05:30]` `[01:06:05]` `[01:08:29]`

**S7-R33** — Double bottom invalidation: close below the low / flip that support to resistance → cut.
params: none. `[01:05:30]`

**S7-R34** — A long wick down to the prior low does not qualify as the second bottom; bodies only.
params: none. `[01:10:48]` `[01:11:20]`

**S7-R35** — On a higher-timeframe double top, take some profit regardless of whether you think it will play out; HTF double tops and double bottoms are the strong ones.
params: HTF only; profit fraction unspecified. `[00:52:32]` `[00:53:05]`

**S7-R36** — Long-term exit rule: once HTF price closes below the last higher low, sell into the retest of that level as resistance / the next confirmed lower high. Accept being 20–30% off the actual top.
params: tolerance 20–30% off the top. `[00:51:15]` `[00:51:58]` `[00:54:48]` `[00:55:23]`

**S7-R37** — When the market is selling off, check the coin's BTC pair; if the BTC pairing looks bullish, that carries over to the USDT pairing.
params: none. `[01:07:55]` `[01:08:29]`

**S7-R38** — Do not leverage-trade coins whose charts show heavy wicks (illiquid/small-cap) or meme coins — spot only.
params: none. `[00:13:02]` `[01:26:36]`

**S7-R39** — Do not trade trend lines alone; a trendline break needs additional confluence. If you shorted a trendline retest and price closes back above the line, cut the short immediately for a minimum loss.
params: none. `[00:43:53]` `[00:44:27]`

**S7-R40** — Falling wedge: enter on breakout + retest of the wedge, with a tighter stop just below.
params: none. `[00:47:19]` `[00:47:54]`

## 4. Parameters and thresholds

| parameter | value | applies to | timestamp |
|---|---|---|---|
| Scalping timeframes | 5m / 10m / 15m | scalp style | `[00:00:01]` |
| Fib levels named | golden pocket, 0.786 | entries/DCA | `[00:04:30]` `[00:05:36]` |
| Order block liquidity-filled cutoff | ~70–80% | OB validity | `[00:09:28]` |
| Order block partial fill (still playable w/ confluence) | 50% | OB validity | `[00:37:57]` |
| Support touches making an OB playable despite filled liquidity | 2nd–3rd touch | HTF support | `[00:08:22]` |
| Wick size acceptable to include in a zone | ~2% | zone drawing | `[00:10:04]` |
| Wick size NOT acceptable to include | 3–4% | zone drawing | `[00:11:18]` |
| Example wick sizes | $200–$300; $27 = 6% (BNB) | zone drawing | `[00:10:43]` `[00:14:47]` |
| Stop width rejected vs accepted (illiquid example) | 18% rejected / 9% accepted | stop placement | `[00:13:39]` |
| Max loss per swing play | 4–5% of portfolio | risk | `[00:10:43]` `[00:20:00]` `[00:25:54]` |
| Default position size | 10% of portfolio | sizing | `[00:20:33]` `[00:25:54]` |
| Counter-trend position size | 5% of portfolio (half) | sizing | `[00:20:33]` |
| Counter-trend max loss | 2–3% of portfolio | risk | `[00:20:00]` `[00:26:26]` |
| Extra loss tolerated to widen entry into a wick | $6–$7 | zone drawing | `[00:11:18]` |
| Move size he will not short for | 1–2% | short filter | `[00:31:36]` |
| Possible adverse move after a valid bearish SFP | 0.5–1% before continuation up | SFP | `[01:15:50]` |
| SFP rejection hit rate | ~60% ("unless we're bullish") | SFP | `[01:16:25]` |
| SFP entry-to-stop distance rejected as too deep | 17% | SFP | `[01:23:14]` |
| SFP stop called too tight | $0.90 (SOL) | SFP | `[01:21:31]` |
| SFP standalone survivability claim | 3–4 stop-outs in 20 trades still net winning | SFP | `[01:33:41]` |
| Realised moves cited | 15% (TIA OB), 20% (ONDO double bottom), 7% (SOL double bottom), 5% (SFP re-entry), 27% (monthly SFP short) | examples | `[00:38:29]` `[00:48:26]` `[01:07:55]` `[01:26:03]` `[01:28:22]` |
| DCA spacing example | ~$1 apart (1h bearish OB) | DCA | `[01:31:58]` |
| ONDO macro bear invalidation | $0.70 on the daily | bias | `[00:47:54]` |
| SOL BTC-pair flip date cited | 25 July | BTC pairing | `[01:07:55]` |
| Named SR short level | 1.1158 | student chart | `[01:10:10]` |
| Bull-run start marker / progress | 25K BTC; ~50–60% through | macro bias | `[00:57:06]` |
| Normal bull-market pullback | 20–30% | macro bias | `[01:00:29]` `[01:02:08]` |
| Acceptable error selling the top | 20–30% | long-term exits | `[00:54:48]` |
| Alt performance benchmark | 4–5x from lows = alt season for that coin | macro bias | `[00:58:13]` |
| Wednesday live-session timeframes | 4h, 2h, 1h, 15m | next session | `[01:35:53]` |

## 5. Entry model

Setup identification, in his order of operations:

1. **Mark structure first** on candle bodies (line chart if unsure): last higher low, last lower high, current trend. `[00:18:50]` `[00:28:05]`
2. **Mark static levels**: support/resistance lines, SR points (flipped levels, 2 touches), supply/demand zones, order blocks. `[01:32:31]` `[01:34:15]`
3. **Overlay fibs**: bullish fib anchored swing low → swing high; look for golden pocket / 0.786 landing inside the zone. `[00:04:30]` `[00:07:14]` `[00:18:17]`
4. **Validity filters**: order block liquidity <70–80% taken (R3/R5), candle big enough (R6), wick inclusion inside risk tolerance (R7), trend not flipped against the direction (R17).
5. **SFP arrives last** as an extra confluence once price interacts with the marked zone — it is not a screener input. `[01:32:31]`

Entry placement and ordering:
- **First entry is at the SR point**, and it is the *smallest* clip: "this is why we go in very light with our least amount of capital, then DCA heavier." `[00:22:18]` `[00:40:10]`
- Where an order block overlaps the SR, he starts at the **top of the order block** (the most-confluence price) rather than strictly the top of the SR. `[00:06:41]`
- **DCA sits at the next confluence down** inside the zone — in the worked example, the support line / 0.786 fib. Average fill lands roughly mid-zone. `[00:06:41]` `[00:07:14]`
- Worked short example: entry at the SR point, DCA1 ~$1 above (filled), DCA2 higher (unfilled), then an SFP printed above and added confluence. `[01:31:23]` `[01:31:58]`
- **SFP entries** are the exception to the DCA ladder: single entry on the candle close (short) or the next candle open (long). `[01:19:52]` `[01:24:22]`
- **Missed SFP**: resting limit at the prior swing high/low, not a market chase. `[01:16:25]`
- **Post-MSB entries**: after a bullish MSB, long the retest of the broken lower high flipped to support; after a bearish MSB, short the retest of the broken higher low flipped to resistance. `[00:33:48]` `[00:40:44]` `[00:47:19]`

## 6. Stops

- Longs: stop **below** the zone / order block / support being played. `[00:06:41]` `[00:37:57]`
- Shorts: stop **above** the resistance, the wick, or the swing high. `[00:13:39]` `[00:29:13]`
- SFP: stop goes automatically **above the raiding wick** (bearish) or **below it** (bullish). `[01:15:50]` `[01:20:57]`
- Falling-wedge breakout retest: "probably a tighter stop somewhere below there." `[00:47:54]`

What makes a stop too wide:
- Any stop that would breach the 4–5% portfolio loss cap once position size is set. He states you flex position size to hold that cap: "you're going to be playing with your position size in advance that you lose no more than four to 5%." `[00:13:39]` `[00:14:13]`
- Including a 3–4% wick in the zone. `[00:11:18]`
- Concrete rejections: an 18% stop (chose a 9% variant instead) `[00:13:39]`; a 17% entry-to-stop SFP `[01:23:14]`.
- Too-wide SFP wicks: drop a timeframe to find a tighter structural stop, or abandon the trade. `[01:18:06]` `[01:18:39]`
- He also flags a stop can be **too tight** — a $0.90 SOL stop, "I wouldn't suggest going this tight… give yourself some more breather." `[01:21:31]`

## 7. Take profit and trade management

This session gives almost nothing mechanical on TP. What is stated:
- **Double bottom measured move**: target = bottom-to-neckline distance projected up from the neckline; "and higher." `[01:06:05]` `[01:08:29]`
- **Counter-trend**: "it is okay to play against the trend but you have to be very cautious and have to take profits fast." No level or fraction given. `[00:20:33]`
- **HTF double top**: take some profits regardless of whether the pattern resolves. Fraction unspecified. `[00:52:32]`
- **Long-term bag exit**: sell into the retest/next lower high after a HTF close below the last higher low. `[00:54:48]` `[00:55:23]`
- **Short management**: if a shorted trendline/level is reclaimed on a close, cut for a minimum loss. `[00:43:53]`
- One passing reference to "it's my final TP" while showing a memecoin chart, with no rule attached. `[01:03:15]`

**No stop-loss trailing rules, no TP1/TP2/TP3 ladder, and no move-stop-to-breakeven rule are stated anywhere in this session.**

## 8. Invalidation and re-entry

- **Order block dies** when its liquidity has been fully taken (~70–80%+), unless a strong HTF support with few touches overlays it. After a strong move away from a filled OB, "this order block is invalid because all the liquidity has been taken." `[00:07:14]` `[00:09:28]` `[00:38:29]`
- **Bullish setups die on trend flip**: pending longs are cancelled once price is consistently printing lower highs. `[00:16:33]` `[00:17:06]`
- **SFP dies** if the candle does not close back through the level `[01:22:39]`, or if you entered before the close and the candle then closes back beyond it `[01:20:57]`.
- **Double bottom dies** on a close below the low and its flip to resistance. `[01:05:30]`
- **Short dies** when price closes back above the level/trendline you shorted — cut immediately. `[00:43:53]`
- **Downtrend stays valid until** the last lower high is broken and flipped to support; only then may you long/swing long. `[00:41:17]` `[00:47:19]` `[00:33:48]`
- **Re-entry after a stop-out** is explicitly allowed: "if we had got stopped out on this play, we go up above the last lower high, we come back down, test it into support, and then continue the trend up." `[00:33:48]`
- **Missed-move re-entry** for SFPs: rest a limit at the prior swing high/low; note "it's not always a guarantee that price goes back up to reject from the level." `[01:16:25]`
- **Missed-move re-entry** generally: wait for the SR flip, "don't chase anything." `[01:21:31]` `[01:23:49]`

## 9. Timeframes

- **Scalping**: 5m / 10m / 15m. `[00:00:01]`
- **Wednesday live workflow (stated plan)**: start on higher timeframes — 4h → 2h → 1h → 15m. `[01:35:53]`
- **Swing/structure examples**: daily and 2-day are his structure charts; monthly used for the memecoin SFP examples. `[00:18:50]` `[00:39:36]` `[01:26:36]`
- **HTF precedence rule**: define the zone on the higher timeframe; a cleaner-looking LTF range will make you miss the SR point. `[00:21:45]` `[00:22:18]`
- **HTF/LTF trend can disagree by design**: a macro uptrend can contain a full LTF downtrend and vice versa; BTC can go to 40K and still be macro bullish. `[00:24:02]` `[00:49:33]` `[00:50:09]`
- **Timeframe of the break determines the trade type and the allocation**: "if they're talking about low time frame, it's most likely going to be a scalp. If they're talking about a high time frame, it's most likely going to be a swing trade. That's how you know how much you can allocate to a play." `[00:50:09]`
- **Counter-trend requires dropping a timeframe first** — those become scalps with automatically halved risk. `[00:25:54]` `[00:26:26]`
- **SFP strength scales with timeframe**: HTF SFPs give a deeper retrace, LTF SFPs are weaker but more frequent. `[01:24:56]` `[01:26:03]`
- **LTF rescue for a deep SFP wick**: e.g. from an 8h SFP, drop to the 15m to find a stop location. `[01:18:06]` `[01:18:39]` `[01:24:22]`

## 10. Confluence

Confluence types he names in this session: SR point (flipped level), support/resistance line, order block (bullish/bearish), supply zone, demand zone, fib golden pocket, 0.786 fib, double bottom / double top, SFP, trendline (diagonal support/resistance), falling wedge, market structure break.

- The governing instruction is "you want to find the most confluence" and to place the first entry where confluence stacks — in the worked example, the start of the order block *because* the SR sits there too. `[00:06:41]` `[00:44:27]`
- **No confluence = no trade**: with liquidity gone from the OB and nothing else present, "I wouldn't play the order block"; play only the support line if that line has been doing its job. `[00:08:54]` `[00:38:29]`
- Confluence can **rescue** an otherwise-dead zone: a filled order block is playable if a HTF support on its 2nd/3rd touch sits on it. `[00:08:22]`
- **Lower highs typically carry confluence** with a supply zone, a bearish order block, or heavy resistance — that combination is the short trigger. `[00:28:40]`
- **SFP is explicitly a second-order confluence**: "you can't be like, hey, I have an SFP, what other confluences can I get out of it" — zones must be pre-marked, the SFP arrives later. `[01:32:31]` `[01:34:15]`
- **He never states a minimum confluence count or any weighting scheme.** The closest to weighting is that HTF confluence outranks LTF `[00:21:45]`, and that trend alignment can veto an otherwise-valid confluence stack `[01:29:41]`.

## 11. Explicitly excluded

- **Shorting, in general**: "I haven't taken a short since last year… I've taken one short. For me, the risk-to-reward isn't there. I don't care about the 1% or 2% move down… I'd rather long and keep the uptrend than trying to play against the trend." `[00:31:36]` `[00:32:09]`
- **Shorting before a candle body closure** below structure. `[00:28:40]`
- **Illiquid / small-cap coins with heavy wicks**: "If I open up a chart and I see this, I do not trade it personally unless it's spot." `[00:13:02]`
- **Meme coins**: "meme coins do not have great TA in general… I don't even trade them unless it's going to be spot." `[01:26:36]`
- **Tiny order blocks** ("smaller than a pinky nail"). `[00:37:22]`
- **Order blocks whose liquidity is fully grabbed** (without overriding HTF support). `[00:07:14]` `[00:38:29]`
- **Trendlines traded alone**: "you shouldn't just trade off of trendlines alone." `[00:43:53]`
- **SFPs traded alone**: "I highly suggest you do not do that." `[01:34:15]`
- **Chasing a missed move / shorting mid-move with a stop above the wick**: "that is terrible risk-to-reward." `[01:16:58]` `[01:21:31]`
- **Wick-based structure breaks** (other analysts' method): "for me, it's always been candle bodies." `[01:11:53]`
- **Wick-based double bottoms**. `[01:10:48]`
- **Deep-wick SFPs** without a lower-timeframe stop location: "at this point just look for a separate play completely." `[01:18:06]`
- **DCAing into losing bags that aren't pumping while everything else is** — "it's better to cut the loss and look for something else." `[01:04:23]`
- Trendline breakout/breakdown mechanics were **on the syllabus but not delivered** this session (deferred to the live session). `[01:36:38]`

## 12. Ambiguities for the bot

**S7-A1** — Golden pocket is used repeatedly as an entry level but its numeric range is never stated in this session. The coder must supply 0.618–0.65 (or whatever prior sessions define) from outside S7. `[00:04:30]`

**S7-A2** — "70–80% of liquidity taken" has no measurement definition. Percentage of what — the OB candle's price range penetrated, the wick range, traded volume inside the zone, or time spent inside it? Also unclear whether the deepest wick or the deepest body counts as the penetration. `[00:09:28]`

**S7-A3** — The 70–80% figure conflicts with a separate remark that there is no 50% rule and with a later example where "50% of the order block filled" is still playable. The bot needs one threshold. `[00:07:47]` `[00:09:28]` `[00:37:57]`

**S7-A4** — "Strong support" / "not as many touches" as the override for a dead order block: he gives 2nd/3rd touch as good, but never states the touch count at which a support becomes too worn to use. He separately calls "multiple touches" risky without a number. `[00:08:22]` `[00:38:29]`

**S7-A5** — "Candle smaller than a pinky nail" is a screen-relative, zoom-dependent criterion. Needs replacing with e.g. a minimum candle range as a % of ATR or of the swing leg. `[00:37:22]`

**S7-A6** — Wick inclusion is framed as "risk tolerance", with 2% include / 3–4% exclude as loose examples, not a cutoff. The bot needs a single number and needs to know whether it's measured on the wick length as % of price or as % of the resulting stop distance. `[00:10:04]` `[00:11:18]`

**S7-A7** — Swing high / swing low detection is never defined algorithmically. No fractal width, no lookback, no minimum swing size. Every structure rule, every SFP, and every fib anchor depends on this. `[01:14:44]` `[00:23:28]`

**S7-A8** — Which timeframe defines "the trend" for the counter-trend size reduction? He moves between macro, 2-day, daily, 2h and "lower impulse" within one explanation and treats all of them as trends simultaneously. `[00:24:02]` `[00:45:00]` `[00:49:33]`

**S7-A9** — Which timeframe's candle close confirms an MSB? Examples use 2-day, daily, 2h and 1h interchangeably with no rule tying the MSB timeframe to the trade timeframe. `[00:18:50]` `[00:40:44]` `[01:24:22]`

**S7-A10** — "Deep wick" on an SFP has no threshold. 17% is rejected and $0.90 is called too tight, but no maximum stop distance is defined, and the lower-timeframe rescue ("go to the 15 minute and find consolidation") has no rule for what qualifies as a valid stop location. `[01:18:06]` `[01:21:31]` `[01:23:14]`

**S7-A11** — "Candles cannot be next to each other" for SFPs — the minimum number of candles between the swing point and the SFP candle is never given (1? 3? 5?). `[01:19:52]`

**S7-A12** — "Swing points too close to each other" makes an SFP weak — no distance threshold in price, %, or candle count. `[01:24:56]`

**S7-A13** — Double bottom tolerance: the second low must be "close to the same" level, "not a significant difference" — no % band. He rejects one visually and accepts another with no measurable line between them. `[01:09:01]` `[01:09:34]` `[01:10:48]`

**S7-A14** — Double bottom neckline is never precisely defined (the intervening high's body? its wick? the highest close between the two lows?), yet the measured target depends entirely on it. `[01:06:05]`

**S7-A15** — DCA ladder is unspecified: number of DCA levels, spacing, and the size fraction at each. Examples show entry + 1 DCA and entry + 2 DCAs, with only "very light first, DCA heavier" as guidance and one incidental "$1 apart" spacing. `[00:07:14]` `[00:22:18]` `[01:31:58]`

**S7-A16** — Take profit is essentially unspecified for everything except the double-bottom measured move. No TP count, no TP levels, no partial-close fractions, and no stop-trailing rule at all appears in this session. "Take profits fast" on counter-trend trades is uncodeable as stated. `[00:20:33]`

**S7-A17** — "Take some profits" on a HTF double top gives no fraction. Same for "sell your bags" on the long-term exit. `[00:52:32]` `[00:54:48]`

**S7-A18** — Position sizing: he states 10% of portfolio and a 4–5% max loss, but never gives the leverage/stop-distance formula that reconciles them for an arbitrary stop width. `[00:20:33]` `[00:25:54]`

**S7-A19** — "Cancel the setup" on a trend flip is ambiguous about whether it means cancel unfilled limit orders only, or also close a partially filled position. `[00:17:06]`

**S7-A20** — The MSB retest confirmation (R15/R16) has no timeout and no invalidation: how many candles to wait for the retest, and what happens if price runs away without retesting. `[00:27:31]`

**S7-A21** — The ~60% SFP rejection figure is asserted with no sample, timeframe, or asset scope, and is immediately qualified with "unless we're bullish". It is not usable as a parameter. `[01:16:25]`

**S7-A22** — "Trend not aligned" as an SFP veto (R31) is applied by eye across several examples with no stated timeframe or trend test, so the bot cannot reproduce which SFPs he'd skip. `[01:27:14]` `[01:29:41]`

**S7-A23** — The BTC-pairing rule (R37) has no trigger condition ("when the market's going down" is undefined) and no definition of "looks bullish" on the BTC pair. `[01:07:55]`

**S7-A24** — "Heavy wicks / illiquid coin" exclusion has no screen criterion (no volume floor, no market-cap floor, no wick-to-body ratio). `[00:13:02]` `[01:26:36]`

## 13. Contradictions

**S7-C1** — Counter-trend setups: at `[00:16:33]`–`[00:17:06]` he says a bullish setup should be **cancelled** once the trend has flipped to lower highs ("If I saw this and I had this setup, I would have canceled it"). At `[00:19:28]`–`[00:20:33]` he says "it is okay to take plays like this" and "it is okay to play against the trend" with halved size. The bot must choose between a hard veto and a size multiplier.

**S7-C2** — Order block liquidity threshold: "this one doesn't have a rule where 50% has to be taken" `[00:07:47]`, then "my rule for order blocks are like around 70 80%" `[00:09:28]`, then a later example where "this has 50% of the order block filled" and is still played `[00:37:57]`. Three different framings of the same filter.

**S7-C3** — Order block validity: "this order block is invalid because all the liquidity has been taken" `[00:07:14]`, immediately followed by "although the liquidity has been taken… that is a great area to go long" when HTF support overlays it `[00:08:22]`. Hard invalidation vs overridable invalidation.

**S7-C4** — He calls a **bearish** order block "the last red candle before directional change" `[00:39:36]`, using the identical phrase he used for the bullish/demand-side order block `[00:06:10]`. One of the two is a mis-statement (a bearish OB should be the last *green* candle before a move down). A coder cannot tell from S7 alone which he meant; other sessions must arbitrate.

**S7-C5** — SFP standalone: "you can get stopped out on like three or four of them and take like 20 trades, you will still have a winning percentage if you just trade SFPs" `[01:33:41]`, immediately followed by "But I highly suggest you do not do that" and the rule that SFPs are only a late confluence `[01:34:15]` `[01:32:31]`.

**S7-C6** — SFP entry timing: bearish SFPs are entered "as soon as that candle closed" `[01:19:52]` `[01:20:25]`, but the bullish SFP example says "You'd start a long on the next candle open" `[01:24:22]`. Probably the same instant in practice, but the bot needs one convention (close price vs next open).

**S7-C7** — Bodies vs wicks: structure, double bottoms and MSBs are strictly body-based `[01:11:53]` `[01:10:48]`, yet stops are placed relative to **wicks** `[01:15:50]` `[01:20:57]`, entry zones are drawn to include wicks `[00:10:04]`, and he notes the body close may not even give you the entry, so you use the wick level instead `[00:35:04]`. The body/wick rule is scope-dependent and is never stated as such.

**S7-C8** — Stop tightness: tight stops are praised as the reason SFPs have the best R:R `[01:16:25]` `[01:33:41]`, but a specific tight SFP stop is rejected as too tight with "give yourself some more breather" `[01:21:31]`. No rule separates "good tight" from "too tight".

**S7-C9** — He states he essentially never shorts and that short R:R isn't there `[00:31:36]`, yet the majority of this session's worked examples are short setups (TIA, ONDO, BNB, the monthly memecoin SFPs) presented as tradeable. Expect this to conflict with the live-trading session's actual trade selection.

**S7-C10** — Likely cross-session conflict: this session gives **no TP ladder and no stop-trailing rules**, while the template's section 7 anticipates them, implying earlier sessions specified them. Anything the bot inherits from S1–S6 on TP/trailing is untouched and unconfirmed here.
