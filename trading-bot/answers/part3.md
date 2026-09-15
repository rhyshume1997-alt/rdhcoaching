# Part 3 — Questions 11 to 15

Answered from the recordings only. Where he never said it, this file says so rather than
producing a number. Session references are `S<n> [hh:mm:ss]` against `transcripts/`.

---

## Q11 — Where does the entry go after a structure break?

**Question.** S7 says short the retest of the broken higher low; S8 says don't short the close,
wait for the next lower high; S3 says don't act until a lower high has formed. Same entry or three?
And how many candles do you wait for the retest?

### Verdict

**One entry, described three times at increasing strictness. Not three entries.**

Bearish case (mirror for bullish):

1. **Detect** — a candle **body** closes below the last higher low. This is the flag only; it is
   never the entry. Both S7 and S8 say so explicitly.
2. **Entry price** — the first swing high that prints after the break, **capped at the broken
   level**: `entry = min(broken_higher_low, first_post_break_swing_high)`.
   - When price rallies all the way back, that rally's peak *is* the next lower high and *is* the
     broken level retested as resistance — S7's and S8's descriptions coincide. This is the normal
     case and why the three sound different.
   - When price rolls over below the broken level, S8's "next lower high" still gives an entry and
     S7's retest never happens. S8 covers the case S7 doesn't.
   - S3's "don't act until a lower high has actually formed" is the same rule with pivot
     confirmation attached — it is a macro-**exit** rule (S3-R21, daily bags), not a third entry.
     CF-22 already separates exit from entry; that separation is correct.
3. **Trigger** — rejection at that level, with the confluence he names: supply zone, bearish order
   block, or heavy resistance. Stop above it.

**Wait time: he refuses to bound it.** There is no candle count anywhere in eight sessions. The
closest he comes is the analogous SR-flip retest, where he says the quiet part out loud:
"Next candle **or however many candles it takes**." His invalidation is condition-based, not
time-based: if price closes back **above** the broken higher low without ever giving the rejection,
the break was a *deviation* and the short is dead.

**Confidence:** `derived` for the unification (each leg is stated; the reconciliation is mine).
`absent` for the candle count.

### Evidence

- S7 `[00:26:59]` — "As soon as we close above, okay, candle bodies as soon as we close above, we
  have a market structure break… **You want to see a confirmation of a retest of the previous lower
  high to hold** and then we continue higher. Okay, because this can easily put in, you know, a
  double top and then continue to make another lower low."
- S7 `[00:28:40]` — "unless price comes down, closes below, **have to have a candle closure below
  before opening up a short**, see if it goes back up to reject from a lower high. **Usually lower
  highs have confluence with either a supply zone or a bearish order block or heavy resistance.** If
  you have that rejection, right, you would mark it short with your stops somewhere above resistance
  and look for technically the next lower low."
- S7 `[00:40:44]` — "on a macro wise, **once we retested this and turned this previous higher low
  into resistance, okay, that was your short trigger.**"
- S8 `[00:25:58]` — "if we lose it, okay, **don't short as soon as we close below. Look for that next
  lower high to possibly get an entry.**"
- S8 `[01:17:19]` — "we have the break of structure. So, **you're looking for the next lower high to
  short**, which was here."
- TBOT1 `[00:31:30]` — bullish mirror: "last higher low, right? We have a break of structure. So yes,
  we can come back down here, put another higher low and grind higher."
- On the timeout, S4 `[00:35:08]` — "**Next candle or however many candles it takes** has to come
  back down, retest that resistance and close above the candle body."
- On the invalidation, S2 `[00:25:56]` — "if we reclaim it without a retest, meaning if we close back
  above, then this is just a **deviation** of that level."

**Cuts against:** S7 `[00:41:17]` describes the bullish side as needing a full flip, not a rejection
— "until we have a breakout and **flip this into support**, that's when we have a trend change and we
can long." The bullish entry may therefore need the stricter 3-candle flip (S4-R5) where the bearish
one only needs a rejection. He never reconciles that asymmetry, and I am not confident enough to
encode it. Also S7-A20 stands: he was asked nothing about a timeout and volunteered nothing.

### What a sweep would settle

Only the timeout. `msb_retest_timeout_bars`, sweep `{10, 20, 40, 60, disabled}` on the structure
timeframe. Decider: expectancy per MSB signal, not hit rate — a long timeout raises fill count and
lowers average quality, so the knee in expectancy×count is the answer. Expect the metric to be flat,
because his real invalidation is the deviation close, which §11 does not currently have a key for.
**That missing key is the more important gap: there is no config entry for "MSB invalidated by close
back beyond the broken level."** It should exist and default to true.

### Config change

- `msb_entry_requires_retest` — **no change** (`true`). Now backed by four independent statements
  rather than inference.
- `msb_retest_timeout_bars` — **no change** (`20`). Remains **[OUR CHOICE]**; he explicitly declines
  to bound it.
- New key needed: `msb_deviation_invalidates` (bool, default `true`) — not currently in §11.

---

## Q12 — Mid-range as a band

**Question.** How wide is the no-trade zone either side of mid-range, and is mid-range the geometric
50% or the nearest S/R level to it?

### Verdict

**Part A — which level: STATED, and it is the S/R level, not the geometric 50%.** He was asked this
question directly and answered it. `mid_range_search_pct = 10.0` implements the right policy; the
listed alternative `0 (pure geometric 50%)` should be **struck from the allowed set** — it
contradicts him.

**Part B — band width: ABSENT, and the question may be the wrong shape.** He never gives a distance,
a percentage or an ATR multiple. What he actually gates on is a **state, not a distance**: the veto
fires when price is *consolidating* at, on or under mid-range. Six separate phrasings across S4, S5
and S8 all use "consolidating"; none uses a distance.

Recommended implementation, which is closer to his words than any band:

```
mid_range_no_trade = price within level_tolerance_atr of the mid_range LEVEL
                     OR a P13 consolidation window overlaps the mid_range level
```

Keep `mid_range_band_pct = 15.0` as the geometric fallback when no consolidation is detected, but it
stays **[OUR CHOICE]** and should be swept.

One thing that *is* stated and must not be lost: the veto is on price **being** at mid-range now. A
resting limit **at** mid-range, placed while price sits at a range extreme, is explicitly permitted.

**Confidence:** Part A `stated`. Part B `absent`.

### Evidence

- S4 `[00:17:53]` — asked outright: "Do we mark the mid-range at exactly the middle of the range or
  it should align with support and resistance? Uh, good question. **It will usually align with
  support and resistance.**"
- S4 `[00:24:12]` — "let's call this our mid-range at this point… **even though it's not exactly in
  the middle**."
- S3 `[00:02:15]` — "**your mid-range is actually a little bit higher.** It's around here."
- S8 `[01:38:23]` — "**Mid-range is this blue level here.**" A single level, named on a chart.
- S5 `[00:24:35]` — mid-range is touch-counted like any other level: "we've had three touches of this
  mid-range. So, it's making this weaker and weaker as we get closer and closer to it."
- On the state-not-distance point:
  - S4 `[00:12:28]` — "if we are **consolidating** under mid-range, okay, you do not want to take any
    trade. Whenever we are **consolidating** on or under mid-range… this is an area where you have to
    sit on your hands."
  - S4 `[00:16:47]` — "**consolidation** under resistance at mid-range and **consolidation** on
    support at mid-range. I don't trust either one of them. So, I don't take a trade whatsoever."
  - S4 `[00:34:34]` — "whenever price is just **consolidating** at mid-range, sit on your hands."
  - S8 `[01:37:43]` — "when we are at mid-range and we're just **chopping**, I just sit patience."
- On limits from the extremes, S4 `[00:34:02]` — "It's better to not play at mid-range… **Then that's
  only if price is at mid-range. If price is up here, then yes, you're going to set limits at
  mid-range.** Or if price is here, then yes, you could set shorts at mid-range."

**Cuts against:** S8 `[01:38:23]` is the one place he sounds like he has a band — "we are a little
bit below mid-range… but if we reclaim this level, we're trading at mid-range" — implying a little
below is *outside* the zone and reclaiming puts you *inside* it. That reads as a very tight band, not
15% of range height. And S8-C6 records five live scalp setups issued during that same mid-range chop,
so the veto is not one he honours in practice at scalp size.

### What a sweep would settle

`mid_range_band_pct`, sweep `{5, 10, 15, 20}` percent of range height each side. Decider: this is a
pure gate, so measure **expectancy of the trades it blocks**. If the blocked population has
expectancy at or above the unblocked one, the band is too wide. Widen until the blocked population's
expectancy drops below zero, then stop. Sweep jointly with `mid_range_search_pct {5, 10, 15}` since
moving the level moves the band.

### Config change

- `mid_range_search_pct` — **no change** (`10.0`). Remove `0 (pure geometric 50%)` from the allowed
  alternatives; he rejected it on tape.
- `mid_range_band_pct` — **no change** (`15.0`). Still **[OUR CHOICE]**; nothing in the recordings
  supports 15 over 5 or 20.
- `mid_range_limits_from_extremes_enabled` — **no change** (`true`). Upgrade its source note from
  inference to stated (S4 `[00:34:02]`).

---

## Q13 — Sufficient gap for 2H, 4H, 8H and 12H

**Question.** What is the minimum move away from a zone on the 4H and the 12H?

### Verdict

**ABSENT for all four. He gives no number for 2H, 4H, 8H or 12H anywhere in eight sessions.** I
searched every instance of "sufficient" (12 hits, all in S5/S6/S7), every `N% move/gap/away` string
paired with a timeframe name in a ±2-block window, and every timeframe name spelled both ways. The
four rows are guesses and must stay labelled as such.

**Which rows are his:**

| TF | current | his? | what he actually said |
|---|---|---|---|
| 15m | 3.0 | **his (lower bound)** | grouped with 1H as "3 to 5% totally fine" |
| 30m | 3.5 | **WRONG — should be 4.0** | "sufficient gap 30 minutes **4%**. That's sufficient enough." |
| 1H | 4.0 | **his (inside band)** | 3–5% fine; **5% fine**; **8% perfect**; 4% accepted live |
| 2H | 5.0 | **OURS — interpolated** | nothing |
| 4H | 6.0 | **OURS — interpolated** | nothing |
| 8H | 7.0 | **OURS — interpolated** | nothing |
| 12H | 7.5 | **OURS — interpolated** | nothing |
| 1D | 8.0 | **his (lower bound)** | "at least 8 to 12%"; 3–4% explicitly not strong |
| 2D | 13.0 | **his** | "there is a 13% move up which is good on a higher time frame" |
| 3D+ | 15.0 | **OURS — extrapolated** | nothing |

**Two findings beyond the missing rows:**

1. **The 30m row is a mislabelled guess.** SPEC §5.5 and CF-11 both cite S5-R16 for `30m = 3.5`, but
   S5-R16's own params say "30m: 4% sufficient" and the transcript says 4%. 3.5 came from smoothing
   the ladder. **Fix it to 4.0.** That also makes the ≤1H rows read the way he speaks: a flat 3–5%
   band with 4% as the operating point, not a rising staircase.

2. **His anchors are mutually inconsistent, so the missing rows cannot be derived — only guessed.**
   Fitting a power law `gap = a·T^b`:
   - 1H (4%) → 1D (8%) is a 24× timeframe step for a 2× gap step ⇒ `b ≈ 0.22`
   - 1D (8%) → 2D (13%) is a 2× step for a 1.63× gap step ⇒ `b ≈ 0.70`

   No single exponent fits both. Extrapolating the 1D→2D slope backwards puts the 12H at ~4.9%,
   *below* the 1H. The naive volatility scaling (`b = 0.5`) puts the 4H at 8% and the 12H at 13.9%,
   which blows past his own daily floor. **The interpolation is not recoverable from his numbers.**

   Bracketing with the two defensible fits (lower bounds 4→8, `b=0.218`; upper bounds 5→12,
   `b=0.275`) gives an honest envelope: 2H 4.7–6.1, 4H 5.4–7.3, 8H 6.3–8.9, 12H 6.8–9.8. The
   existing 5.0/6.0/7.0/7.5 sits inside all four — keep it, but keep the label.

3. **Practical consequence.** The percentage table is a guess exactly where he trades most: S5
   `[01:41:45]` names 8H, 12H and daily as his swing timeframes and the 2H as his scalp timeframe. On
   2H–12H the **ATR test should be the binding one** and the percentage the loose floor — the reverse
   of how CF-11 currently frames it. Leave `sufficient_gap_require_both_tests = true`, but expect the
   ATR test to do the work on those four rows and tune `sufficient_gap_atr_mult` accordingly.

**Confidence:** `stated` for 15m, 30m, 1H, 1D, 2D. `absent` for 2H, 4H, 8H, 12H, 3D+.

### Evidence

- S5 `[00:35:30]` — "**sufficient gap in price action means the move away from this consolidation
  zone**… this move from here to here has to be wide enough in correlation with a time frame. So for
  example, **on a 1 hour, right, this is an 8% move. That's perfect.**"
- S5 `[00:36:05]` — "you can actually have on a 1 hour be like a **5% move. That's fine.** Now a four
  or **3% move on the daily is not a strong move** from this breakout point. **Higher time frames need
  to have a higher move away from that zone.**"
- S5 `[00:36:38]` — "**Lower time frames, okay, like on a 15 minute or the 1 hour, a 3 to 5% totally
  fine. Higher time frames like the daily you need like at least 8 to 12%.**" ← the only two-tier
  statement in the corpus, and the whole 15m–1H group gets one band.
- S5 `[00:54:07]` — "Price goes up, consolidates, breakout, **sufficient gap 30 minutes 4%. That's
  sufficient enough.**"
- S5 `[00:55:17]` / `[00:55:51]` — "There's the breakout. **This is not a valid zone yet. This move is
  not great**… you're looking for anything like around 3 to 5%… **at this point, right, you have like
  a 4% move. You would go ahead and set your bids.**"
- S5 `[01:17:59]` — "This is a two-day chart… **there is a 13% move up which is good on a higher time
  frame.**"
- S5 `[01:41:45]` — "If you want to swing trade, the best time frames to do so are going to be **8
  hour and 12 hour and the daily**. If you want to scalp, it's going to be the **2 hour and the 30
  minute** for me personally."
- S5 `[01:42:18]` — "**4 hour is also great too, because that's a swing time frame**… 8 hour has been
  like a really hidden gem for me. I like the 12 hour."
- The corpus confirms the void directly — S5-A2: "**nothing at all is given for 2h, 4h, 8h or 12h** —
  precisely his primary trading timeframes." S6-A2 calls "sufficient gap" undefined outright.

**Cuts against / weakens the whole table:** the adjectival statements do not line up with the
percentages. S6 `[00:04:03]` calls a 2% move away "weak, scalp-only" on a low timeframe; S6
`[00:45:16]` calls "a 5% move… a lot" on a 4H chart — 5% is *below* the interpolated 4H row of 6.0,
so his own worked 4H example would fail the table. S6 `[00:08:04]` uses 26–27% to justify a swing
short. S5 `[01:10:32]` contrasts "6% right compared to 15" for order-block strength. These are not
thresholds and cannot be converted into any, but they suggest 6.0 on the 4H may be set too high.

### What a sweep would settle

`sufficient_gap_pct_by_tf`, four rows only. Sweep each independently within its bracket:

| key row | sweep |
|---|---|
| `2H` | 4.5, 5.0, 5.5, 6.0, 6.5 |
| `4H` | 5.0, 5.5, 6.0, 6.5, 7.0, 7.5, 8.0 |
| `8H` | 6.0, 6.5, 7.0, 7.5, 8.0, 8.5, 9.0 |
| `12H` | 6.5, 7.0, 7.5, 8.0, 9.0, 10.0 |

Decider: **expectancy per zone-sourced trade at the zone's first touch**, with a floor on signal
count so the optimiser cannot solve it by admitting three zones a year. Run each row on that
timeframe's own data — do not fit one exponent across all four, because his anchors prove no single
exponent exists. Sweep jointly with `sufficient_gap_atr_mult {1.5, 2.0, 2.5, 3.0}`, since the two
tests are ANDed and only the binding one moves the metric. If the ATR test is binding at every
percentage value in the sweep, report that and set the percentage rows to his brackets' lower bounds.

### Config change

- `sufficient_gap_pct_by_tf` — **change the 30m row from 3.5 to 4.0** (S5 `[00:54:07]`, stated).
  Re-source it to S5-R16 correctly.
- `sufficient_gap_pct_by_tf` rows `2H/4H/8H/12H/3D+` — **no change to the values** (5.0 / 6.0 / 7.0 /
  7.5 / 15.0), but they are **[OUR CHOICE]** and must not be presented as his. SPEC §5.5 already marks
  them; CF-11's "log-interpolation" justification should be softened — the interpolation is not
  derivable, because his 1H→1D and 1D→2D slopes disagree by a factor of three.
- `sufficient_gap_atr_mult` — **no change** (`2.0`), but promote it to the primary test for 2H–12H in
  the §5.5 prose, since the percentage row there is a guess.

---

## Q14 — Do the pattern, trend-line and scalp modules ship?

**Question.** He taught a pattern library (S4), a trend-line breakdown method (S8) and a scalping
session (S8), disowning each. Live strategies, or confluence only?

### Verdict — three different answers, because the three disavowals are three different kinds

| Module | Ship as live strategy? | Kind of disavowal |
|---|---|---|
| **Chart patterns** | **No standalone entries — but this is not a disavowal.** Ship confluence ON, and let measured-move targets set TPs. | *"Never alone"* — he trades them, layered on S/R |
| **Trend-line breakdown** | **No.** Off by default, backtest-selectable, and constrained when on. | *"I don't, but it works"* — the objection is operational |
| **Scalp** | **Yes, but floored at 30m.** What he disowns is 15m-and-below day trading, not the trade class. | *"Unreliable"* at the low end only; he names the 2H as his own scalp timeframe |

**1. Chart patterns — the premise is wrong.** He never says patterns don't work. He says
*pattern-only trading* didn't work **for him, once, historically**, and that the fix was ordering, not
removal. He then describes actively trading pattern breakout+retest as his own method. Keeping
`module_chart_patterns_enabled = false` for **standalone signal generation** is right; calling
patterns "disowned" is not. Two stated uses must remain live: pattern-as-confluence
(`disowned_modules_still_score_confluence = true`, already correct), and the measured-move target as
a TP level (S4's whole pattern library exists to produce those).

**2. Trend-line breakdown — genuinely "I don't, but it works".** He gives a mechanical reason that is
about *him at a screen*, not about the edge: the play has no hard stop and must be babysat. A bot does
not have that problem, which is the one case in the corpus where the bot could execute something
better than he can. That is not enough to flip the default — but if it is enabled for backtest, the
constraints he attaches are stated and must be enforced: **small size, one entry, no DCA, close on
reclaim (not on stop), re-enter on the next breakdown.**

Important split that CF-37 blurs: **trend lines themselves are not disowned.** S6-R28 puts them in
step 3 of chart prep ("trend lines are just diagonal support and resistances") and he counts one as a
confluence in live analysis. Only *trend-line-breakdown-as-an-entry-trigger* is off.

**3. Scalp — the strongest-sounding disavowal, and the one that means least.** He says "I don't
scalp" in S8 and "I suck at scalping" in S5, and in S5 also says the 2H is his favourite scalp chart
and that he scalps a few trades within a day on it. Both cannot be literal. The reconciliation is in
his own words: what he quit was **150-trades-a-day low-timeframe day trading**, on grounds of both
reliability *and* stress. His stated scalp timeframes are the 2H and the 30m. And the spec already
carries a scalp risk branch he specified himself — `max_loss_pct_scalp = 2.5`, `tp_count_scalp = 3`,
`dca_count_scalp_max = 1`, `scalp_excludes_btc` — which would be dead code under a hard veto.

So: **enable the scalp module, floored at 30m**, not 15m. His own S8 live session, run on 15m and 1H
charts, went **1 for 3** — his evidence, against the low end, from the same session as the
disavowal. The 5m/10m floor in S7-R10 is scoped to counter-trend demotion only and should not raise
the general floor.

**Confidence:** patterns `stated`. Trend-line `stated` (the disavowal) / `inferred` (the default).
Scalp `inferred` — this is the one place I am recommending a change against a prior verdict, and it
rests on reconciling two of his statements rather than on either alone.

### Evidence

**Patterns**
- S4 `[01:48:29]` — "Yes, I did breakouts a while back. **Yes, I traded patterns alone. I did not
  find any success in doing so. So that's why I have my support resistance lines first and then I add
  these confluence on top of it.**" ← never-alone, not never.
- S4 `[01:47:57]` — "then yes, you're waiting for the breakout retest and then you mark it long…
  **That's how I play it.** So I know retests can take a long time, but if I don't have confirmation,
  I'm not going to get into a trade."
- S4 `[01:49:39]` — head and shoulders: "**for a head and shoulders to be formed correctly or played
  correctly, breakdown, retest, then you can take the short.**" He is teaching how he plays it.
- S4-R38 — "Draw support/resistance first; patterns are only layered on top as confluence. Never take
  a trade on a pattern alone."
- S6 `[01:56:54]` — "I would use fibs over patterns 100% of the time" — a ranking, not an exclusion.

**Trend-line breakdown**
- S8 `[00:28:52]` — "You don't have a stop-loss. You have to watch this play as it develops, **which
  is why I don't like trading breakdowns and patterns in general, like breakouts**, because if the
  candle closes back above… you would close out your trade for a minimal loss."
- S8 `[00:30:37]` — "**Now, why am I sharing this with you if I don't trade it myself? Sometimes it
  works.** Like, you have to be at your computer or at your phone… and you have to monitor that whole
  entire move." ← the operational objection, stated as the reason.
- S8 `[00:31:44]` — "**you don't DCA on these type of plays. These are only one entry, one stop loss,
  multiple TPs.**"
- S8 `[00:35:55]` — "**if you are going to short breakdowns, go in with small position size** and you
  have to be okay with cutting your positions as soon as it's reclaimed."
- Against removing trend lines entirely: S6-R28 step 3 puts trend lines in the S/R stage; S5
  `[01:38:21]` counts one as the third confluence in a live setup; S5 `[01:43:55]` "Add your trend
  line for confluence."

**Scalp**
- S5 `[00:20:02]` — "**for me, I suck at scalping. I know my strengths and weaknesses. Trading chop
  and scalping on lower time frames is not my thing.**"
- S5 `[00:20:36]` — immediately after: "**And if you're good at scalping, then this is going to be
  heaven for you** when we have those volatility sessions." ← "works, just not for me."
- S8 `[01:34:48]` — "**this is why I don't scalp because lower time frames are highly unreliable
  compared to high time frames. You will have more losses than wins on low time frames unless it's
  easy mode.** But theoretically because you take so many trades in a day… when I was day trading, I
  was taking like 150 trades a day."
- S8 `[01:35:25]` — "**that required me spending so many hours watching charts, putting notifications
  on. It just wasn't worth it. The stress wasn't worth it.**" ← the reliability claim is bundled with
  an effort claim, and the effort claim does not transfer to a bot.
- S8 `[01:37:43]` — "I have a list of weaknesses, right? So trading chop is one of them. **Scalping is
  another.**"
- S2 `[01:26:28]` — "**for me, chop is weakness. I don't typically trade chop because I know what my
  weaknesses are.**" Framed identically to "I suck at trading XRP" at `[01:27:03]` — a personal-fit
  statement, not a claim about the method.
- **Against the disavowal**, S5 `[01:41:45]` — "**If you want to scalp, it's going to be the 2 hour
  and the 30 minute for me personally**… I prefer a 2 hour than a 30 minute 100% of the time."
- S5 `[01:42:50]` — "**if I'm looking to scalp, whether it be a few trades within the day or whatever,
  the two-hour chart for me is my favourite.**"
- S8 `[00:44:49]` — "**these are going to be scalps. So, anything on a 4 hour time frame or lower.**"
  He then runs five of them live.
- S8 `[01:40:42]` — "you can actually take TP2 a little bit higher, but **scalping, that's enough for
  scalp.**"

**Cuts against my scalp verdict, and it is not weak:** S8 `[01:57:24]` — "**One for three.** Soul got
stopped and Doge got stopped. Yeah, there's just no follow through in the markets." His own live
scalp session lost money, and he said "I don't scalp" during it. If the reviewer weights precedence
rule 4 literally, leaving `module_scalp_enabled = false` is defensible. My argument is only that
"I don't scalp" cannot be read as covering the 2H, because he names the 2H as his scalp timeframe and
his favourite chart — so a veto is too blunt, and the floor is the right control. Note also that the
scalps in S8 were executed with the *same* machinery (SR points, supply zones, order blocks, SFPs) on
a lower timeframe — the "scalp module" is not a distinct strategy, it is a timeframe class.

Also worth flagging while here: the RSI/divergence disavowal is the same shape and is already handled
correctly (`rsi_divergence_mode = "confluence_only"`), but S8-C3 stands — the only SOL long he
identified in S8 rested on a bullish divergence at `[01:25:35]` — in the same breath as "I don't like
using divergences cuz they could be very misleading" (`[01:24:49]`) and "**I also don't like using
RSI**" (`[01:25:35]`).

### What a sweep would settle

- `module_scalp_enabled` × `scalp_tf_floor {15m, 30m, 1H}` × `scalp_tf_ceiling {2H, 4H}` as a 2×3×2
  grid. Decider: **expectancy per scalp trade net of `fee_taker_bps` and `slippage_market_bps`** —
  fees are the whole argument on low timeframes and a gross-P&L metric will give the wrong answer.
  Secondary guard: max drawdown, since his stated objection is loss frequency.
- `module_trendline_break_enabled` {false, true} with `dca_count_breakdown = 0` pinned and a size
  multiplier swept over {0.33, 0.5, 1.0}. Decider: does it add expectancy *on top of* the S/R+zone
  book, i.e. measure the delta with the module on versus off, not the module standalone.
- `module_chart_patterns_enabled` does not need a sweep for the ship/don't-ship call — he answered it.
  What needs sweeping is the confluence weight patterns carry, which is CF-31's problem, not this one.

### Config change

- `module_chart_patterns_enabled` — **no change** (`false`). Correct outcome; the SPEC's rationale
  should be re-sourced from "he disowns it" to S4-R38 "never on a pattern alone", which is stronger
  and is what he actually said.
- `module_trendline_break_enabled` — **no change** (`false`).
- `module_scalp_enabled` — **change `false` → `true`.** Recommended, with the floor change below.
  Flagged as a reversal of CF-37; see the counter-evidence above before accepting it.
- `scalp_tf_floor` — **change `"15m"` → `"30m"`** (S5-R34, S5 `[01:41:45]`; S8 `[01:34:48]` on
  low-timeframe unreliability). Keep `"15m"` and `"5m"` as alternatives; `"5m"` remains reachable only
  via `counter_trend_demote_to_scalp` (S7-R10).
- `scalp_tf_ceiling` — **no change** (`"2H"`). S5-R34 and his stated preference agree; S8-R14's 4H
  stays as the alternative.
- `disowned_modules_still_score_confluence` — **no change** (`true`).

---

## Q15 — Golden pocket: 0.66 or 0.65, and is it ever the 0.786?

**Question.** Confirm golden pocket = 0.618–0.66 as the entry level, 0.786 as a separate DCA level.
And should 0.886 be in the set?

### Verdict

**All three confirmed, and the "interchangeable" premise is not supported by the tape.**

1. **Golden pocket = [0.618, 0.66]. STATED.** 0.65 is other people's convention and he says so
   explicitly while rejecting it for himself. **The dispute is also moot for a band implementation:
   0.65 already lies inside [0.618, 0.66].** It only bites if you place a single limit at the band
   edge, and there he is unambiguous — 0.66. No change.

2. **"Golden pocket" never means 0.786.** In every one of the ~20 co-occurrences he enumerates them as
   two distinct levels, usually in the same breath and always in the same order (GP shallower, 0.786
   deeper). The S8 "interchangeable" reading rests on exactly two timestamps, and neither supports it:
   `[01:07:57]` mentions the golden pocket alone with no 0.786 anywhere near it, and `[01:14:50]`
   reads "lines up with the golden pocket, the 786 fib" — a two-item list whose conjunction the
   auto-captioner dropped, exactly as it did at S6 `[01:32:28]` ("Golden pocket 786 fib") and S6
   `[01:29:20]`. **Recommend S8's exclusion note and the S8 number-table row be corrected**; they
   currently assert a conflation that does not exist.

3. **0.886 stays OFF. STATED.** He calls it "a really cool one" and says in the same sentence he has
   not back-tested it, then defines his own set as the middle three of five. No change.

**One correction the question did not ask for.** `fib_entry_level = 0.618–0.66` rests on TBOT1's live
behaviour. In the session that *teaches* fibs he says something different and more restrictive: the
0.786 is the DCA and **the entry is an SR point, not a fib**. The fib is confluence on an SR entry,
never the entry reason. This is consistent with `single_class_trade_forbidden = true` and with the
pipeline putting fibs last, so it needs no key change — but `fib_entry_level` should be read as "the
fib level that may coincide with an entry", not "where entries go."

**Confidence:** `stated` on all three parts.

### Evidence

- S6 `[01:26:22]` — "**There's only two of them that I've back tested that I found to be very
  accurate. It is called the golden pocket which is the space between the 618 and the 66 fib**… and
  the 786 fib. **These two have the highest reversal points out there.**" ← the definition, and the
  two-level list.
- S6 `[01:40:01]` — "**some people will say that the golden pocket lies between the 618 and the 65.
  I was always — when I read and did my own back testing and I had my own mentor — he told me the
  golden pocket is the 66. So I've always used the 66. Some people use the 65.** Okay, and then the
  786. I would recommend highlighting your 66 fib. **You can do both of them.**"
- S6 `[01:40:37]` — "in my notes… it will say that the most important ones are going to be **the
  golden pocket and the 786 fib.**" Two items.
- S6 `[01:38:53]` — 0.886: "**that one's a really cool one as well. I just haven't back tested it.**
  I know a lot of people live and die by the 886."
- S6 `[01:41:14]`–`[01:41:52]` — "so 886, 786, 66, 618… and the 236. **If you want to have five fib
  settings just those. I use the three middle ones.**" Middle three of {886, 786, 66, 618, 236} =
  **{0.786, 0.66, 0.618}**. 0.886 is excluded by his own arithmetic.
- S6 `[02:03:52]` — "we reject right off the golden pocket. Okay, **we reject right off the 786 fib.**"
  Two separate rejections at two separate prices, one sentence apart.
- S6 `[01:53:26]` — "we got our bounce from the golden pocket briefly, **but the next point is the 786
  fib at 90.6**." Explicitly different prices, GP first.
- TBOT1 `[00:03:31]` — "bounce from the golden pocket and go higher. **I'm not discounting a move down
  to the 786 fib.**" GP shallow, 786 deep.
- TBOT1 `[00:26:30]` — "you can play the golden pocket one or two times, but after the third time it's
  going to get weaker. So **786 perfectly aligns with this OB down here in the 3-day. That's where I'd
  be looking to get long.**"
- On the entry/DCA split, S6 `[01:56:54]`–`[01:57:29]` — "**I just like to find the 786 fib and see if
  it lines up. The 786 fib is usually my DCA point.** Although the golden pocket can offer a bounce,
  the 786 fib is usually my DCA point. **And then my entry is always going to be an SR point or a
  resistance point.** 786 is my favourite fib."
- The S8 passages the conflation claim rests on:
  - S8 `[01:07:57]` — "Adding more confluence for that long. Okay, let's take it from this low. **Maybe
    a golden pocket bounce within the order block.**" No 0.786 present.
  - S8 `[01:14:50]` — "This is a 4 hour order block that I drew wick to highs, **lines up with the
    golden pocket, the 786 fib.**" A list of two, matching his phrasing elsewhere.

**Cuts against:** S6 `[01:45:16]` — "In this one, **I will use all my fibs, not just the golden
pocket**, because you need multiple points of rejection" — scoped to price-discovery TP-finding with
trend-based extensions, where the whole set including 0.886 is on. So `fib_886_enabled = false` is
correct for *entry/DCA* levels but the price-discovery TP path (`tp_count_price_discovery_max = 5`,
S6-R36) legitimately uses more levels. Also TBOT1-A1 is right that the band is never numerically
stated in the live session — the definition comes only from S6, which is fine, because S6 is the
session that teaches fibs.

### What a sweep would settle

Nothing material — this is the only one of my five that is fully stated. If anything is swept, sweep
`golden_pocket_band` upper bound `{0.65, 0.66}` purely to confirm the difference is noise at
band-fill granularity, and `fib_886_enabled {false, true}` to check he was right not to trust it.
Decider for both: fill rate × win rate at the level. Expect no separation on the first; if 0.886
shows a real edge, that is new information he did not have, and it is a *finding*, not an override.

### Config change

- `golden_pocket_band` — **no change** (`[0.618, 0.66]`). Note in the source column that 0.65 falls
  inside the band, so the conflict only exists for single-price orders.
- `fib_levels_active` — **no change** (`[0.618, 0.66, 0.786]`). Now backed by his own "middle three of
  five" arithmetic rather than inference.
- `fib_886_enabled` — **no change** (`false`).
- `fib_entry_level` / `fib_dca_level` — **no change** (`0.618–0.66` / `0.786`), with the reading note
  above: the fib is confluence on an SR entry, never the entry reason on its own.
- **Documentation fix, not a config fix:** CF-33's "S8 uses golden pocket and 0.786 interchangeably"
  and the matching S8 extract lines (§2 definitions, the number table row "Fib used for entries |
  0.786 'golden pocket'") assert a conflation the transcript does not contain. They should be struck
  or downgraded to an ASR artefact.

---

## Summary of config changes

| Key | From | To | Basis |
|---|---|---|---|
| `sufficient_gap_pct_by_tf["30m"]` | 3.5 | **4.0** | stated, S5 `[00:54:07]` |
| `module_scalp_enabled` | false | **true** | inferred; reverses CF-37, see Q14 |
| `scalp_tf_floor` | "15m" | **"30m"** | stated, S5-R34 / S5 `[01:41:45]` |
| `mid_range_search_pct` allowed set | incl. `0` | **drop `0`** | stated, S4 `[00:17:53]` |
| *(new)* `msb_deviation_invalidates` | — | **true** | derived, S2 `[00:25:56]` |

Everything else in Q11–Q15: no change. Four rows of `sufficient_gap_pct_by_tf` (2H, 4H, 8H, 12H) and
`mid_range_band_pct` and `msb_retest_timeout_bars` remain **[OUR CHOICE]** and are the three highest-
value sweeps out of this batch.
