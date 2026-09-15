# Answers, part 2 — questions 6 to 10

Method: extracts read as an index, then targeted greps of the raw transcripts in his own
vocabulary. Every quote below was read in context with its neighbouring 30-second blocks.
Confidence labels: `stated` / `derived` (arithmetic or counting off a worked example) /
`inferred` (consistent with behaviour, never stated) / `absent`.

---

## Q6 — Swing high / swing low detection, and "directional change in price"

**Question.** How many candles either side must a high be the highest of before it is a swing
high, and how big must a move be to count as a directional change?

### Verdict

Four separable parts, with four different confidences. Do not treat this as one answer.

**(a) The candle count — `absent`.** There is no fractal width, no lookback, no N-bar rule
anywhere in eight sessions. He never counts candles either side of a pivot, not once, not even
loosely. Keep `swing_k = 3` as a placeholder and sweep it; it remains **[OUR CHOICE]** and this
research does not upgrade it.

**(b) What he actually does instead — `stated`, and it is not a fractal.** His swing points are
**ordinal and relational**, defined by alternation against the previous same-kind extreme, and
they are **explicitly multi-valued at one moment in time**: several swing highs coexist and he
picks by eye. So `swing_k` is not modelling his method, it is standing in for it. The bot should
run pivot detection at **two widths (k=2 and k=5) simultaneously** and let `confluence_merge_atr`
dedup the overlaps, rather than pretending one k reproduces him. Marked `inferred` as a design
consequence.

**(c) Price source — `stated`, and the current default is right but for a reason the SPEC does not
record.** Structure (HH/HL/LH/LL, MSB, double bottoms) is read off **candle bodies / line chart**.
The **SFP raid level and the stop** are read off the **wick**. These are two different objects and
he says so. `swing_price_source = "body"` should be reclassified from P1's **[OUR CHOICE]** to
sourced, with the wick carve-out documented.

**(d) "Directional change" magnitude — `inferred`, but with his own numbers available.** He never
attaches a size to "directional change" in the order-block definition. But the only quantified
move-size test he owns is the **sufficient-gap-by-timeframe** table, and in every worked example
the order block and the supply/demand zone are marked off the **same impulse leg** whose gap he has
just checked out loud. Use his table as the directional-change threshold:

| TF | min move | Source |
|---|---|---|
| 15m / 1H | 3–5% ("3 to 5% totally fine") | S5 `[00:36:38]` |
| 1H | 5% "fine", 8% "perfect" | S5 `[00:35:30]` `[00:36:05]` |
| 30m | 4% "sufficient enough" | S5 `[00:54:07]` |
| 1D | ≥8–12%; **3–4% on the daily is explicitly NOT a strong move** | S5 `[00:36:05]` `[00:36:38]` |
| 2D | 13% | S5 `[01:17:59]` |

The structural point matters more than the rows: **his threshold is a percentage that scales with
timeframe, not an ATR multiple.** `dir_change_atr = 2.0` is the wrong parameterisation and, on the
timeframes I could sanity-check by hand, it is materially *looser* than his percentage floors —
i.e. the bot is currently calling directional changes he would not.

**(e) The one threshold he does state is separation, not amplitude — `stated`.** "Candles cannot be
next to each other." The literal floor is therefore **2 bars of separation** between the swing and
the candle that sweeps it; `sfp_min_bars_between = 3` is stricter than anything he says.

### Evidence

Absence, stated twice as a deferral:

> "You can take it from many swing low points. **It doesn't matter which one.** You will have
> different supports that come out." — S6 `[01:21:06]`

> "I mean, you have **multiple swing** you have multiple levels here, right? Like this is your
> swing high. This is your swing high. This is your swing high." — S7 `[01:31:23]`

Ordinal / relational definition (this is his whole method):

> "If this is the low, right? This is the first higher low. **It's higher than this low.** Okay,
> this is a higher high. **It is higher than this high.** Okay, another higher low, higher than
> this low, higher high and higher low." — S7 `[00:23:28]`

> "Now higher high has been made. This was your last higher low, right? We have a break of
> structure." — TBOT1 `[00:31:30]`

Price source split — bodies for structure:

> "I only use candle break uh **candle bodies** cuz look, right? If this is our last higher low,
> right, we close there, that is a break of structure." — S7 `[00:18:50]`

> "When you look at um bottoms and structures, you always want to go by candle bodies. Okay. So,
> **turn on your line chart** and take a look." — S7 `[01:10:48]`

> "Some analysts will say that structure breaks are with wicks. **For me, it's always been candle
> bodies.**" — S7 `[01:11:53]`

> "Your higher low. **Candle bodies is what I'm looking at** because if you remember, if you look
> at line charts, this is higher than this low." — S5 `[01:25:16]`

…wicks for the SFP level. **This cuts against a blanket `swing_price_source = "body"`** and is why
the carve-out has to be explicit:

> "We close the candle below the previous swing high point. Right, **swing high points are usually
> taken by wicks, not by bodies.** Okay, but the candle body closes below the swing high point and
> this wick has taken out all of its liquidity." — S7 `[01:14:44]`

Directional change tied to the sufficient-gap move (the OB and the zone share one leg):

> "Price bounced exactly from the SR point. Also the top of the demand zone… **This is also the
> last red candle before a directional change in price. So this order block is within this demand
> zone here.**" — S5 `[00:54:43]`

> "Price goes up, consolidates, breakout, **sufficient gap 30 minutes 4%. That's sufficient
> enough.** … Here is another example of a demand zone with a two candle. **This is also an order
> block.**" — S5 `[00:54:07]`

> "You need that **sufficient gap in price** and then you have your supply zone formed." — S6
> `[00:31:31]`

The rejections — these are the load-bearing evidence, per the brief:

> "Now a four or **3% move on the daily is not a strong move** from this breakout point. Okay,
> higher time frames need to have a higher move away from that zone." — S5 `[00:36:05]`

> "If we were to trickle down to a lower time frame, you have a supply zone that's formed here.
> Okay, but **this move isn't significant enough.**" — TBOT1 `[00:26:30]`

> "So and by the way **candles cannot be next to each other.**" — S7 `[01:19:52]`

> "See like **these are too close to each other. I don't like — I don't consider that an SFP.**"
> — S8 `[00:23:38]`

> "This is considered a **weak SFP because the candles are way too close to each other**, right?
> But we do have this high here." — S8 `[00:16:46]`

> "Now these are way too close to each other. If price goes up and is very close to each other,
> these will possibly not work out very strong. Whereas **the greater the distance, the more bids
> there are.**" — S7 `[01:24:56]` `[01:25:28]`

Cutting against a clean separation rule: `[00:16:46]` **demotes** a too-close SFP to "weak" and
re-anchors to a further high, while `[00:23:38]` **vetoes** one outright. He does not distinguish
the two cases. And note S7 `[01:25:28]` reads as *price* distance while S7 `[01:19:52]` reads as
*bar* distance — both keys (`sfp_min_bars_between`, `sfp_min_swing_separation_atr`) are justified
as concepts, neither number is his.

### What a sweep would need to settle it

- `swing_k` — sweep `{2, 3, 5}`, and separately the two-scale variant `{2 and 5 together}`.
  Metric: **count of detected structure breaks per 1,000 bars** against the rate he narrates on
  the same charts (he calls roughly one MSB per 15–40 daily bars on BTC), not PnL. PnL will
  reward whatever k happens to fit the sample; the narration rate is the actual target.
- `dir_change_atr` — if it stays an ATR multiple, sweep `{2.0, 3.0, 5.0, 8.0}`. Metric: fraction
  of detected order blocks whose impulse leg *also* clears `sufficient_gap_pct_by_tf`. Tune until
  that fraction is ≈1.0, which is the point where the ATR key stops disagreeing with his own table.
- `sfp_min_bars_between` — sweep `{2, 3, 5}`. Metric: SFP win rate stratified by separation, to
  find where his "too close → weak" downgrade actually bites.

### Config change

- `swing_k` — **no change** (3). Stays **[OUR CHOICE]**; nothing found upgrades it.
- `swing_price_source` — **no change** (`"body"`), but reclassify from **[OUR CHOICE]** to
  sourced (S7 `[00:18:50]`, `[01:10:48]`, `[01:11:53]`, S5 `[01:25:16]`), and record the wick
  carve-out for SFP raid levels and stops (S7 `[01:14:44]`).
- `dir_change_atr` — value **2.0 retained only as a secondary floor**; the primary test should
  become `sufficient_gap_pct_by_tf`. That requires a key that does not exist in §11:
  `dir_change_uses_sufficient_gap_table = true`. If no new key is permitted, sweep
  `dir_change_atr` upward per above — 2.0 is too permissive.
- `sfp_min_bars_between` — **no change** (3), but its floor is now sourced at **2**, not
  **[OUR CHOICE]** (S7 `[01:19:52]`).

---

## Q7 — Which timeframe governs

**Question.** For a 1H entry, which TF carries trend/structure, which confirms the MSB close, and
which decides SFP validity?

### Verdict

**Higher timeframe always wins. `stated`, verbatim, and it is the closest thing to a governing
principle in the corpus.**

Concretely, three rules:

1. **Trend and structure** are read on the timeframe the level/zone was drawn on, and where two
   timeframes disagree the **higher one takes precedence**. His swing band is **4H / 8H / 12H /
   1D**; his scalp band is **2H / 30m** (and 5/10/15m for live scalping). The 1H is **not in his
   swing band** — by his own taxonomy a 1H entry is either a scalp, or the execution leg of a
   structure read higher up. `structure_tf_offset = 2` (1H → 4H) puts structure at the *bottom
   edge* of his swing band; offset 3 (1H → 8H) lands on his stated favourite. `inferred`.
2. **MSB close** is confirmed on **candle bodies, on the timeframe the structure was drawn on** —
   not on the trade timeframe. `stated`.
3. **SFP validity is per-timeframe and the timeframes legitimately disagree.** He resolves this by
   trading the **highest timeframe on which the SFP is valid**, and demoting a LTF-only SFP to a
   scalp. This is a change from the current default. `inferred` from consistent behaviour.

A fourth, and the one that ties the sizing question to this one: **the structure timeframe sets
the play class and therefore the allocation**, not the other way round.

### Evidence

The governing principle, stated as a direct answer to a student question:

> "**What time frame are you on? Remember, higher time frame will always take precedence.** So if
> let's say you saw this on a 4 hour, right, you're missing out the SR point. … So, **use the
> higher time frame** like I know this range looks clearer, but…" — S7 `[00:21:45]` `[00:22:18]`

> "If you give me an eight hour or the 4 hour, **I always choose a higher time frame.**"
> — S5 `[01:42:18]`

The daily vetoing a lower-timeframe long, live:

> "The daily super bearish. Okay, **the 4 hour could get a bounce there, but it's just not worth
> getting into longs** at least until we reclaim that move up." — S8 `[00:41:12]`

> "I don't like this daily candle. Okay. Two, **Bitcoin daily candle looks extremely worse.** So,
> although the setup is there, right? Sometimes it's okay to not take the play." — S8 `[00:38:57]`

The timeframe bands:

> "Do you want to scalp or do you want to swing trade? If you want to swing trade, **the best time
> frames to do so are going to be 8 hour and 12 hour and the daily.** If you want to scalp, it's
> going to be **the 2 hour and the 30 minute**… 4 hour is also great too, because that's a swing
> time frame." — S5 `[01:41:45]` `[01:42:18]`

Structure timeframe → play class → allocation. This is the sentence that makes the two-tier map
his rather than ours:

> "If an analyst is saying 'hey, we have broken market structure,' see what they're talking about
> first. **Are they talking about low time frame? And if so, it's most likely going to be a scalp.
> If they're talking about a high time frame, it's most likely going to be a swing trade. That's
> how you know how much you can allocate to a play.**" — S7 `[00:50:09]`

MSB on the structure TF, bodies:

> "If you were on the **two-day chart**, okay, again this was your last higher low… Once we had
> this close below, if this is where your candles closed — and again, I only use candle bodies —
> if this is our last higher low, we close there, **that is a break of structure**." — S7
> `[00:18:50]` `[00:19:28]`

The S8 SFP conflict the question names, resolved by his own behaviour:

> "Let's say this is our high. We wicked above and closed below. **That's automatically a swing
> failure.** … Now, if we look at the **12-hour, we closed above, not an SFP**, right? Now, did we
> have any SFPs on a lower time frame? Let's see. We did." — S8 `[00:23:06]`

> "If I go to the 12 hour, right? **Not a swing failure.** … But on the daily, although we took out
> these highs… **that daily one had a nice move.**" — S8 `[00:16:46]` `[00:24:15]`

> "On a lower time frame, you could definitely take that. **But on the daily, it's a missed
> attempt.**" — S7 `[01:24:22]`

> "**Lower time frames are going to be weaker compared to higher time frames**, but you could have
> a lot that play out." — S7 `[01:26:03]`

Cutting against a strict HTF-only rule — he keeps a live LTF exception open:

> "We're only looking for the **current price action**, unless a high time frame price action
> works." — S7 `[01:20:25]`

> "Although we have an SFP, right? Sometimes it doesn't make sense to short it **because it's
> bullish**." — S7 `[01:29:41]`

And, honestly, the thing that makes offset 2 arbitrary: he moves between macro / 2-day / daily /
2H / "lower impulse" inside single explanations and treats all of them as trends at once (S7
`[00:24:02]`, `[00:33:13]`, `[00:29:13]`). No sentence in the corpus picks a number of ladder steps.

### What a sweep would need to settle it

- `structure_tf_offset` — sweep `{1, 2, 3}`. Metric: fraction of taken trades whose structure TF
  falls inside his stated swing band {4H, 8H, 12H, 1D} when the trade TF is 1H–4H. Offset 3 should
  win that test outright; the sweep exists to check it does not destroy trade count.
- `sfp_governing_timeframe` — sweep `{"trade_structure_tf", "highest_valid", "1D"}`. Metric:
  recall against the SFPs he actually calls on-screen in S7 `[01:19:52]`–`[01:34:15]` and S8
  `[00:16:11]`–`[00:24:46]`. `"trade_structure_tf"` will miss the S8 daily SFP whenever structure
  resolves to 12H — that single miss is the whole argument for changing it.

### Config change

- `sfp_governing_timeframe` — **`"trade_structure_tf"` → `"highest_valid"`**, bounded to timeframes
  between the trade TF and `structure_tf + 1`. This is the one substantive change here.
- `structure_tf_offset` — **no change** (2), but demote from **[OUR CHOICE]** to *sweep-first*, with
  3 as the evidence-favoured alternative (S5 `[01:42:18]`, S7 `[00:21:45]`).
- `htf_veto_enabled` / `htf_veto_timeframe` — **no change** (`true` / `"1D"`); both are now
  directly sourced (S8 `[00:38:57]`, `[00:41:12]`), not inferred.
- `msb_price_source` — **no change** (`"body_close"`); `stated` four times.
- `trend_timeframe` — **no change** (`"structure_tf"`).

---

## Q8 — Normal leverage position size

**Question.** S3 says 20% of portfolio, S7 says 10%, spot is 6–12%. For a leverage swing with a
4–5% max loss, what is the notional and what leverage gets you there?

### Verdict — `derived`, and the current default is wrong by roughly 7×

**The percent-of-portfolio figures are MARGIN, not notional.** Notional is derived from risk and
lands between **73% and 154% of portfolio equity** in his own worked example. `max_notional_pct_leverage
= 10.0` is a mislabelled margin figure being enforced as a notional ceiling, and because the SPEC
re-solves quantity from the clamped notional, **it silently caps every leverage trade at about
0.7% portfolio risk instead of the 4–5% he specifies.**

The arithmetic, from the fully worked S6 example (`[00:08:36]`–`[00:11:27]`), a $1,000 portfolio:

| | first attempt | second | final (accepted) |
|---|---|---|---|
| Entry leg | 15 @ 35.551 | 8 @ 35.551 | 7 @ 35.551 |
| DCA leg | 25 @ 40.11 | 15 @ 40.11 | 12 @ 40.11 |
| Total qty | 40 | 23 | **19** |
| Average entry | 38.38 | 38.38 | **38.38** |
| Stop | 41.23 | 41.23 | **41.23** |
| Stop distance | 2.85 (**7.43%**) | 2.85 | **2.85 (7.43%)** |
| Loss at stop | 40 × 2.85 = **$114** | 23 × 2.85 = **$65** | 19 × 2.85 = **$54** |
| % of portfolio | **11.4%** — "too high" | **6.5%** — "still too high" | **5.4%** — "this is okay" |
| **Notional (qty × avg)** | **$1,535 = 153.5%** | $883 = 88.3% | **$729 = 72.9%** |

He states $114, $54, 11.4%, 6.5% and "about 5.4%" out loud; the table uses his stated average
(38.38) and stop distance (2.85). Recomputing from the raw legs gives 38.40/38.43 and a stop
distance of 2.80, so his figures carry about 1% of rounding drift — immaterial to the conclusion,
and I have kept his numbers rather than mine. The notional row is the row he never says — and it
is **73% of the portfolio on the trade he accepts.** A 10% notional cap cannot produce any of
these three positions.

Now the margin reading resolves S7 cleanly. On $1,000: 10% = $100 margin, loss $50 = 5% of
portfolio = **50% of the money he put in**. That is only possible with leverage. At his stated
default of **10x**, $100 margin = $1,000 notional = 100% of equity, and a **5% adverse price move**
produces exactly the $50. Under the notional reading the same sentence would require a **50% stop**,
which is absurd against a 9–16% stop-width ceiling. The margin reading is the only one that closes.

Cross-check against S6: $729 notional / 10x = $72.9 margin = **7.3% of portfolio** — sitting just
under S7's 10% and nowhere near a 10% *notional* figure.

**So, to implement:**

```
loss_budget      = max_loss_pct_swing/100 * equity          # 4–5%
notional         = loss_budget / stop_pct                    # THE size, ~44%–100% of equity
margin           = notional / leverage
leverage default = 10x  (stated: "I always do 10x")
margin ceiling   = 10% of equity  (S7's figure, correctly labelled)
notional ceiling = 100% of equity (= 10% margin x 10x; binds only when stop_pct < 5%)
```

S3's 20% is the same quantity at a different date — 20% margin at 10x is 200% notional needing a
2.5% stop, which is scalp-tight. Keep 20.0 as a sweep alternative on the *margin* key, not the
notional key.

### Evidence

The stated ratio, twice in one breath:

> "If you go in with like **10% of your portfolio** into a play and that would cause you to lose
> like 50 — or 5% of your portfolio — go in with 5% and you would lose only 2.5%." — S7 `[00:20:33]`

Leverage explicitly as the free variable — this is the sentence that settles margin-vs-notional:

> "You have a $1,000 portfolio. **You enter each play with 10% of your portfolio.** Okay. So,
> **whatever the leverage is, you calculate that you only lose four to 5% of your port** in that
> swing play." — S7 `[00:25:54]`

The stated default leverage:

> "Position long. Leverage. **I always do 10x**, but whatever leverage you put, go ahead and put
> there." — S2 `[01:52:12]`

Margin semantics confirmed elsewhere, unprompted:

> "You might ask yourself like 7%'s not a lot. If you're on **10x leverage or 20x leverage, you
> just made a 70 to 140% of your margin.**" — S6 `[00:13:47]`

> "It'll tell you that hey, you made **20.76% on 10x leverage. It's a 2% unleveraged move.**"
> — S2 `[01:52:52]`

The worked sizing loop itself:

> "If my stops were to get hit, **I lose $114**. Okay, if you have a $1,000 portfolio, **this is
> 11.4%. This is too high.** So you have to play with your numbers. So let's do like 8 and 15…
> **$65, 6.5%** of your portfolio. If your stop loss were to get hit, **still too high.** All right,
> so let's do like seven and 12… now you lose, you know, **$54**… this is **about 5.4% which is
> fine**." — S6 `[00:10:53]` `[00:11:27]`

The S3 figure, in full:

> "If your portfolio is like $1,000 and you usually go in with each trade with like **20% of your
> portfolio** — not saying you're going to lose 20% if your stop loss were to get hit, because we
> have those rules. If it's a scalp, we lose only 2 to 3%. And if it's a swing play, we only lose
> four to 5%." — S3 `[00:04:25]`

Cutting against a hard 4–5%, live:

> "**I'm only going to be risking five to six% of my portfolio.**" — TBOT1 `[00:38:08]`

Spot, for contrast, genuinely is notional and genuinely is small:

> "It's easier to buy spot with like maybe 50 or 25K [of $200,000] and ride it." — S2 `[01:46:00]`

### Config change

- `max_notional_pct_leverage` — **10.0 → 100.0**. Alternatives to sweep: 73.0 (his literal accepted
  worked example), 155.0 (his first-attempt sizing, which he rejected on *risk*, not on notional),
  200.0 (S3's 20% margin at 10x). Source changes from S7-R8 to **derived, S6 `[00:08:36]`–`[00:11:27]`**.
- Two keys that do not exist in §11 and should: `margin_pct_leverage = 10.0` (alt 20.0, S3) and
  `default_leverage = 10.0` (stated, S2 `[01:52:12]`).
- Note for §8.8: the `if clamped: re-solve qty_total` branch is what converts this mislabelling
  into a silent 7× under-risking. With the ceiling at 100.0 the clamp binds only for stops tighter
  than 5%, which is the regime his 10x/10% rule of thumb was describing in the first place.
- `max_loss_pct_swing` / `max_loss_pct_swing_hard_cap` — **no change** (4.0 / 5.0). Every worked
  example targets 4–5% and he rejects 6.5% out loud; TBOT1's live 5–6% stays behind the existing
  `high_conviction_loss_pct_enabled` flag.

---

## Q9 — Counter-trend: cancel it, or halve it?

**Question.** Hard veto, or 0.5× with a 2–3% loss cap? And is a counter-trend trade always demoted
to a scalp?

### Verdict — `stated`. Both, and they are not the same situation. The existing defaults are correct.

The apparent contradiction dissolves on a distinction he draws himself but never labels:

- **A setup already armed as a with-trend trade, whose trend then flips against it → cancel the
  unfilled legs.** This is S7-R17. It is a *pending-order hygiene* rule, not a doctrine about
  counter-trend trading. Note the language is permissive — "it is okay to **not** take this trade" —
  not a prohibition.
- **A deliberately-chosen new counter-trend entry → allowed, at 0.5× size, with risk capped at
  2–3%, demoted to a scalp on a lower timeframe, with fast profit-taking.** `stated` numerically
  in two sessions plus the live one.

The demotion is not an extra penalty stacked on the halving — he presents it as the *mechanism* of
the halving: going counter-trend forces you to a lower timeframe, which makes it a scalp, which
*automatically* moves you from the 4–5% risk class to the 2–3% class. And the arithmetic is
self-consistent: `counter_trend_size_multiplier 0.5` × `max_loss_pct_swing 4.0` = **2.0%**, exactly
`max_loss_pct_counter_trend`. No key needs to move.

**Yes, always demoted.** `counter_trend_demote_to_scalp = true` is stated, not inferred.

### Evidence

The cancel, in full context — note it is a *pending* setup:

> "Let's say that we're using this order block and we have our setup like such. And let's say that
> we get this move down. So now we are consistently putting in lower highs. Okay, so obviously
> we're in a downtrend now. We have lost that trend. And **it is okay to not take this trade**
> because everything is in a downtrend. … **If I saw this and I had this setup, I would have
> cancelled it.**" — S7 `[00:16:33]` `[00:17:06]`

The halving, one minute and thirty seconds later, with numbers:

> "**It's okay to take plays like this**, but if you're in a downtrend and you're trying to long,
> you're playing against the trend, you would go in with **reduced position size or lower risk**.
> … If you can lose max four to 5% of your portfolio and you're playing against the trend, **risk
> only two to 3%**. **Use half of your usual amount** of going into plays with." — S7 `[00:19:28]`
> `[00:20:00]`

> "**It is okay to play against the trend but you have to be very cautious and have to take profits
> fast.**" — S7 `[00:20:33]`

The demotion, stated as the mechanism:

> "If you're **playing against the trend**, okay, **this is where you basically are going to be
> scalping it.**" — S7 `[00:25:12]`

> "If you're trading against this uptrend **you have to go to a lower time frame first. These will
> be scalp plays. Meaning that automatically it's already reduced** — if you have four to 5% on a
> swing play, **it's automatically reduced to 2 to 3%.**" — S7 `[00:25:54]` `[00:26:26]`

Corroborated in three other sessions:

> "When you're trading against the market, you want to go in with reduced size. So you go in with
> **$100 instead** [of $200 on a $1,000 portfolio]." — S3 `[00:04:25]`

> "When trading against the prevailing trend, **halve position size**." — S8-R1, `[00:00:01]`
> `[00:00:35]`

> "When shorting inside an uptrend, use **lower position size and lower risk**." — S5-R33
> `[00:42:50]`

Cutting against the halving — the S3-C9 impossibility, which I read as loose narration and discard:

> "**Your stop loss is still going to be the same in terms of how much you would lose.** But because
> you're going in with reduced position size, you typically want your stop loss… maybe you go in
> with like a **1% risk**." — S3 `[00:04:58]`

He means the stop *price* is unchanged; the loss in portfolio terms plainly halves in S7's
arithmetic on the next page. The 1% is a third figure with no worked example behind it.

Also cutting against a veto: TBOT1's headline BTC plan is a counter-trend long inside a downtrend
he insists is a downtrend (TBOT1 `[00:03:31]`–`[00:04:55]`). He does not hesitate.

### Config change

**No change.** All four defaults are confirmed and three of them should be reclassified from
inferred to sourced:

- `counter_trend_mode = "size_down_and_demote"` — confirmed; `"veto"` is a mis-reading of a
  pending-order rule and should be dropped from the alternatives list, not merely deprioritised.
- `counter_trend_size_multiplier = 0.5` — `stated` ("use half of your usual amount").
- `counter_trend_demote_to_scalp = true` — `stated` ("these will be scalp plays").
- `max_loss_pct_counter_trend = 2.0` — arithmetically consistent (0.5 × 4.0) and inside his stated
  2–3% band. Alternative 3.0 (his upper bound); drop 1.0 to a sweep-only value given S3-C9.
- The cancel rule is already implemented correctly — `bot/tbot/manage.py:583` transition **T08**,
  `ARMED + TREND_FLIPPED → CANCELLED`, action `_a_cancel_unfilled`, cited to S7-R17. That is exactly
  right and this research validates it rather than changing it.

---

## Q10 — Resting limits at the SR point vs waiting for the flip

**Question.** Is the difference that S4 is about a level that has not flipped yet, and the SR-point
entries are on levels that already have?

### Verdict — `stated`. Yes, that is exactly the difference, and CF-16's reading is correct.

Three things make it airtight rather than merely plausible:

1. **He defines an SR point as a level that has already changed roles.** So "I always enter at SR
   points" is, by definition, a statement about already-flipped levels. It cannot be a
   counter-example to S4.
2. **S4's prohibition is scoped to a bull-flag breakout** — a level that is *still resistance* and
   is expected to flip. He ranks three entries and puts the naked breakout last precisely because
   the flip has not happened.
3. **He defines the flip as break + retest + hold**, three components, which is what "wait for the
   flip" means operationally.

One refinement CF-16 does not capture, and it matters: there **is** an intermediate state. A level
becomes "an SR" the moment it is broken — *before* the retest. He does sometimes rest a light limit
there, and he calls that the impatient version of himself and says the correct play was to wait.
So the pre-flip resting limit is a real, permitted-but-inferior variant, not an impossibility.
It should exist as a flag, defaulted **off**.

Also note S4's *third* option — resting a limit at the bottom of the flag range — is a resting limit
at an unflipped level and he ranks it middle, not worst. So the prohibition is narrow: **do not rest
an order at the specific level you are waiting to see flip.** Resting limits at established
support/resistance elsewhere are fine everywhere in the corpus.

### Evidence

The prohibition, verbatim, in its bull-flag context:

> "You could wait for a breakout and retest of the top of the flag… and **think of it as an SR
> flip**, right? We break out. You're going to wait for that successful retest. … **You need to wait
> for that retest to happen. You're not going to place limit orders at the SR line. You're going to
> wait until the SR line is flipped to support and then you mark it long** with your stops somewhere
> below support." — S4 `[00:55:04]` `[00:55:38]`

> "Price breaks out, you immediately mark it long… **The second option is — and this option is the
> riskiest.** Breakout equals risky always on anything. Because you could easily have the price go
> up on one candle and then just dive back down." — S4 `[00:54:31]` `[00:55:04]`

The flip, defined:

> "**Reclaim is just a close above a certain level, and a flip is retesting it and then confirming
> support and then going higher.** … This is why I prefer the flips than trying to play the
> reclaims." — S8 `[00:38:14]` `[00:37:41]`

The SR point, defined — a level that has *already* changed roles:

> "I always enter my positions at SR points and DCA lower. If I can't DCA lower, then I average up.
> … SR points give you very nice returns whether they're **from a long time ago or they were
> previous supports turned into resistance and vice versa**." — S3 `[01:54:12]` `[01:54:49]`

The intermediate state, and his own verdict on it — this is the part CF-16 misses:

> "**An SR means pending retest.** Okay, so we have to — for example, let's say this is support.
> Support has to be broken, then this turns blue, and then if we don't get a retest… and we go back
> above with no retest, **that is a deviation**." — S2 `[00:25:19]` `[00:25:56]`

> "We broke above resistance. **This became an SR**, right? We came and bounced briefly from it.
> **My entry was light there.** My DCA came around 57360… **But if I was a little more patient and
> awake, then yes, I would have waited for the flip to happen. And then let's see what this candle
> would have done before entering.**" — S2 `[00:27:08]` `[00:27:41]`

He is describing his own trade and saying the disciplined version waits. That is S4-R19 and
S3-R13 spoken by the same person about the same fill.

Confirmation-candle count is timeframe-dependent, which is the existing `flip_extra_candle_below_tf`:

> "So we don't need a confirmation candle after the retest to confirm the flip? … Yes and no, it
> depends on the situation. **Lower time frames I want to say yes, but if you have a higher time
> frame such as the daily or 4 hour you can go without it.** It's going to be risky, but this is why
> we go in light." — S2 `[00:26:30]`

The all-limits rule, which keeps the retest entry a resting order and not a market fill:

> "**I never market into anything. So I always set limits.**" — S4 `[02:03:04]`

> "You're waiting for a flip to happen. … You can wait for a flip to happen. **Don't chase
> anything.**" — S7 `[01:21:31]`

Cutting against the clean split: he says "you will **mark it long**" (ASR for "market long") at the
confirmed retest in S4 `[00:55:38]`, which sits badly beside "I never market into anything." And
S3-C12 stands — he does enter on a breakout close above 61K in the same session he preaches SR-point
discipline. The rule is his stated method; the exceptions are his live behaviour.

### Config change

**No change to the entry-family keys** — CF-16's verdict survives contact with the transcripts intact:

- `entry_family_retest_enabled = true` — level already flipped ⇒ resting limits at the SR point
  and DCAs. Confirmed (S3 `[01:54:12]`).
- `entry_family_flip_pending_enabled = true` — level not yet flipped ⇒ nothing rests at the line;
  arm only after `flip_confirm_candles` completes. Confirmed (S4 `[00:55:38]`).
- `allow_market_orders = "trigger_family_only"` — no change; the S4 "mark it long" ambiguity is
  noted but the two explicit all-limits statements outrank one ASR-mangled clause.
- `flip_extra_candle_below_tf = "4H"` — no change; now directly sourced (S2 `[00:26:30]`).

One key to add, which does not exist in §11: `presr_light_limit_enabled` — a light first leg resting
at a level that has been broken but not yet retested, sized at the first-leg fraction only, default
**false**. It is the only entry he demonstrates that neither family covers, and he calls it his own
impatience (S2 `[00:27:41]`). Sweep it as an on/off pair; the metric is fill rate versus deviation
rate at freshly-broken levels — the trade-off he is describing is precisely that a pre-flip limit
fills more often but eats every deviation.

---

## Cross-cutting note

Q6 and Q8 are the two that should change behaviour. Q8 is a live defect rather than an open
question: `max_notional_pct_leverage = 10.0` enforces a margin figure as a notional ceiling, and
because §8.8 re-solves quantity from the clamped notional, every leverage trade the bot takes
currently risks roughly a seventh of the budget the risk ladder assigns it. His own worked example
sizes to 73% of portfolio notional. That is arithmetic, not interpretation, and it does not need
a sweep to confirm — only the backtest re-run afterwards.
