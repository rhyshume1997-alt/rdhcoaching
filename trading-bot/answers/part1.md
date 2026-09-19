# Part 1 — Questions 1–5, answered from the recordings

Method note: every quote below was pulled from `transcripts/` at the timestamp given. Where a
verdict differs from `CONFLICTS.md`, the departure is stated explicitly. Where the corpus is
silent I say so rather than inventing a number.

---

## Q1 — Zone invalidation: 50% or 70–80%, and wick or close?

**Question.** Is a level/zone dead at 50% of its depth or at 70–80%, and is the threshold breached
by a wick or only by a close beyond it?

**Verdict.** Option **(c)**, with a wick test.

- **Supply/demand zone (multi-candle):** dead at **50% of zone depth**, midpoint frozen as the box
  was originally drawn. No re-take of that setup afterwards; a *different* setup may be built lower.
- **Single-candle order block:** dead at **~75% of the OB range taken** (his band is 70–80%). A
  50%-filled OB is explicitly still playable. 100%-filled is unambiguously dead.
- **Measurement:** **wick touch**, not close. Any wick through the 50% line kills the zone.
- **Override (survives):** a dead OB is re-armed if an independent higher-timeframe support with
  ≤3 touches sits there — but the trade is then taken on that support, not on the OB.

**Confidence.** `stated` for the two thresholds and for the OB/zone split. `inferred` for
wick-vs-close (he never uses the words "wick" or "close" about the 50% line; the verb he uses is
"breached"/"pierced" and the mechanism he describes is limit orders filling, which happens on a
wick).

**Evidence.**

The zone rule, stated as a rule:
> "there is a rule on how many times you can play this… you can play the same setup, this same
> exact setup over and over again until it that 50% mark of the zone… If this **50% line is
> breached**, this zone is no longer valid" — S5 `[00:38:52]`

> "The reason why you don't take that trade is because **50% of the bids that were in this range
> have already been filled**. The final bids remain down here." — S5 `[00:41:10]`

The order-block rule, stated separately and in the same breath as a denial that the 50% rule
applies to it:
> "And now this order block is invalid because all the liquidity has been taken. **So this one
> doesn't have a rule where you know 50% has to be taken.** But… if this has like you know um what
> like **70 or 80%** right like maybe you don't start at the top of the order block unless you have
> … a strong support on top of it." — S7 `[00:07:14]`–`[00:07:47]`

> "**So my rule for order blocks are like around 70 80%** otherwise if it's a strong support you
> can go ahead and play it right." — S7 `[00:08:54]`

The 50%-filled OB he still takes — this is the passage that makes a single 50% threshold
untenable:
> "Now notice here I mentioned that **this has 50% of the order block filled** but because this all
> this liquidity hasn't been grabbed you can easily just play the bottom of the support line if you
> want or **you can still still play this order block because I have enough confluence to play
> it**." — S7 `[00:37:57]`

The HTF-support rescue of a fully-taken OB:
> "let's say it was and we only had two bounces from it. Although the liquidity has been taken from
> this order block… we had a bounce here, we confirmed the support, here's a second touch, then we
> have a third touch. **That is a great area to go long although the liquidity has been taken.**"
> — S7 `[00:08:22]`

100%-filled OB is dead:
> "order block has been **completely filled**. So if this goes back up you don't play the order
> block again." — S8 `[00:34:48]`
> "this one already **most of the liquidity is already taken out**… Most of it has been filled and
> bounced again." — S8 `[00:47:20]`

Wick, not close — the strongest indications:
> "notice how this **pierced through** 50%" — S5 `[01:23:02]`
> "If … like, hey, is this 50% or is this not? **Round it.** This is about 50%. I would call that a
> 50% fill." — S5 `[01:22:28]`

Cutting against a wick test: he never applies the word "breach" to a wick anywhere else, and every
*level* rule in the corpus is a close rule ("the candle needs to close below", S2 `[00:02:51]`;
"closing exactly on it does not count", S8). But those are about a level changing identity
(support → SR), which is a different event from a zone's bids being consumed. Nothing in the corpus
ties the 50% line to a candle close.

**Config change.**
- `zone_fill_invalidation_pct` = **50** — no change (now `stated`, scoped to zones only).
- `zone_fill_measure` = **`"wick_touch"`** — no change (still `inferred`; keep as a sweep key).
- `zone_fill_reference` = **`"as_originally_drawn"`** — no change.
- **New key required:** `ob_fill_invalidation_pct` = **75** (band 70–80), measured with the existing
  `ob_liquidity_measure` (P15). Today P15 is dead code because it only fires when
  `zone_fill_invalidation_pct` is set to 70/80; splitting the key activates it and removes the
  contradiction CF-08 papered over.
- `dead_zone_htf_support_rescue` = **true**, `dead_zone_rescue_max_touches` = **3** — no change.

---

## Q2 — Third-touch rule vs replaying a zone

**Question.** Is "don't take it after the third touch" a hard veto, and how does it square with
replaying a zone until 50% fills?

**Verdict.** **(a) plus (b), scoped by object class — and the veto is at the 4th touch, not the 3rd.**

- **Bare S/R line:** touches **1, 2 and 3 are tradeable; the 4th is vetoed.** "After the third
  touch" means after the third has happened, i.e. from the fourth. He demonstrates this reading
  himself.
- **Supply/demand zone or order block:** touch count does **not** veto. The fill rule of Q1 governs.
  He replays a supply zone three times in one demonstration and stops only when 50% fills.
- **Range boundary:** playable until the range breaks — he takes the 5th, 6th and 7th touch and
  calls it correct.
- **Size decay applies to all three** and is a real rule, but the *only* touch index he ever
  attaches to a size reduction is the **5th**. It is a size reduction, not a veto.
- **Touch counts are per-object, not per-price.** A stale line plus a fresh zone at the same price
  is traded on the fresh object's touch index.

**Confidence.** `stated` for the class split and for the 5th-touch size reduction. `derived` (by
counting the touches in his replay demonstrations) for "the 3rd touch is playable, the 4th is not".
`absent` for the actual size multipliers at touches 3, 4 and 5 — he never gives one.

**Evidence.**

The rule as stated, immediately followed by him numbering the touches — this is what fixes the
off-by-one:
> "We've had **three touches** of this mid-range… **that's the third touch**. Remember I said
> **after the third touch** I typically do not want to trade or play that same or take that same
> trade again. Okay, **this is the fourth touch and we just blew through it**." — S5 `[00:24:35]`

> "one, two, three, four touches and then we broke out, right? So, **I am not taking a trade after
> the third touch of either support or resistance.**" — S5 `[00:25:40]`–`[00:26:16]`

Independently, a third touch endorsed outright:
> "we had a bounce here, we confirmed the support, here's a second touch, then we have a third
> touch. **That is a great area to go long**" — S7 `[00:08:22]`
> "you have your support line… so we know already **strong support, third touch**, weak resistance"
> — S4 `[01:04:03]`

The class split, said out loud:
> "**three touches of — so range trading versus support is different**, right? Like if you're
> trading a range, like if there was no solidified range, then yes, **I would not take it after the
> third touch. But with the range**, since it's an easy invalidation… your chances of being wrong
> in a range are like 30%." — S4 `[00:44:23]`
> "one, two, three, four. I'm actually **five touches. I'm going to keep taking this trade until I'm
> wrong.**" — S4 `[00:44:55]`

The zone demonstration — count the plays he takes and the one he refuses:
> "Order block filled, went high, order block rejected, came back down. Right here is a mini supply
> zone. Comes down. **50% did not fill. Rejected again. 50% did not fill.** … There you go. **50%
> did fill at that point. So, you could have taken this supply zone three separate times with the
> same play.**" — S6 `[00:52:38]`–`[00:53:12]`

That is three plays of one object with no reference to touch count, and the stop condition is the
fill line, not the third touch. Same pattern in S5's whole 01:19–01:37 replay block, and:
> "it's the 3-day demand zone. **We did not get a 50% fill. So, this can be played again.**"
> — S6 `[00:02:50]`

Size reduction, not veto — the only indexed instance:
> "Now, we've had one, two, three, four touches of this resistance. So **I would go in with a
> smaller position only because it's going to be the fifth touch.** Um, but **supply and SR is going
> to be the first touch.** Got an order block." — S8 `[00:54:14]`

That last sentence is also the answer to per-object counting: at one price he carries a 5th-touch
resistance line and a 1st-touch supply zone and SR simultaneously, and sizes off the combination.

> "But be careful when we have multiple touches. You might be either one, **lower your risk, meaning
> you go with lower position size**, or two, um **you just don't take the trade**." — S4 `[00:32:46]`

Cutting against the verdict — the hard-veto and the 1–2-only readings both exist:
> "Here's the fourth. Here's the fifth. Here's the sixth. So, **would I long this level again? No.
> It's a very weak support.** But if there is **one or two touches** of support and the move is far
> away from it, then yes, you would want to play that again." — S2 `[00:31:11]`
> "you can play the golden pocket **one or two times, but after the third time**, it's going to get
> weaker" — TBOT1 `[00:26:30]`

And in TBOT1 he then trades the weak levels anyway, flagging them rather than skipping:
> "this has been your demand zone that's been holding… it's **getting weaker and weaker every single
> time we touch it. But, a scalp opportunity**" — TBOT1 `[00:22:24]`
> "Every time we've come here, we've seen the bounce, but it's getting weaker and weaker… **So, an
> area to play this SR point**" — TBOT1 `[00:25:17]`

**If absent.** The decay *curve* is the gap. He states the principle ("weaker every touch"), one
anchor point (5th touch → smaller), and two "still playable" data points (3rd touch of an HTF
support; 5th–7th touch of a range boundary). Nothing fixes the multipliers.
Sweep `touch_size_decay` over shapes anchored at touch 1 = 1.0 and monotone non-increasing:
flat `[1,1,1,1,1]`, current `[1.0,1.0,0.66,0.5,0.33]`, shifted `[1.0,1.0,1.0,0.66,0.5]`,
steep `[1.0,0.75,0.5,0.25,0.0]`. Decide on **expectancy per trade at touch index ≥3**, split out by
object class, with a secondary check that total return at index ≥3 stays positive — the question is
whether late touches are worth taking at all, and a flat curve that still wins says the decay is
cosmetic.

**Config change.**
- `line_touch_hard_limit` = **3** — no change. Confirmed: `is_playable` uses `touch_count <= limit`,
  so touches 1–3 pass and the 4th is vetoed, which is exactly what S5 `[00:24:35]` demonstrates.
- `zone_touch_uses_fill_rule_not_count` = **true** — no change; upgraded from `inferred` to
  `derived` on the S6 `[00:52:38]` three-play demonstration.
- `range_boundary_touch_limit` = **6** — no change (S4 `[00:44:55]` takes the 5th).
- `touch_size_decay` → **`[1.0, 1.0, 1.0, 0.66, 0.5]`** (shift the existing curve one index right).
  Reason: the current curve cuts size at the 3rd touch, but the 3rd touch is a touch he explicitly
  calls "a great area" (S7 `[00:08:22]`), and the only touch index he ever attaches a reduction to
  is the 5th (S8 `[00:54:14]`). The curve shape remains **OURS** either way — this is a sweep key,
  not a settled number.

---

## Q3 — DCA size split

**Question.** What is the ratio between the light first entry and the heavier DCA legs?

**Verdict.**
- **Three legs: 18 / 29 / 53** (round to **20 / 30 / 50**).
- **Two legs: 39 / 61** (round to **40 / 60**).
- **Wick-heavy / hard-to-stop charts: first leg 20–30% of total → 25 / 75.**
- Position size, break-even and every TP-trail decision run off the **blended average**, never
  entry 1.

**Confidence.** `derived` — solved arithmetically from the one worked ladder in the corpus where he
gives both prices and quantities, and cross-checked against two of his own verbal descriptions and
one independent statement in another session. `stated` only for the wick-heavy first leg.

**Evidence — the arithmetic.**

He builds a three-leg LINK short live and reads out the resulting average:

> "So entry points **17.28 17.858 and 18.181**. … And these are just random numbers. I haven't
> calculated based on how much I would lose. But if you just plug in numbers, right? Let's do
> **let's actually do 35. Let's do 55. And let's do 100.** Okay. So all in all **average price will
> be uh 17.921**. … Okay. Notice how **it's closer to the last DCA point**." — S6 `[00:38:49]`–`[00:40:05]`

Check: (35 × 17.28 + 55 × 17.858 + 100 × 18.181) / 190 = 3405.09 / 190 = **17.9215**. His 17.921 is
exact, so the quantities are real, not approximate.

Total = 190 units, which he confirms independently: "we are making **$190 for every dollar move**"
(S6 `[00:40:40]`), and "if your entry filled only… for every dollar down, you were making **$35**"
(S6 `[00:47:31]`).

So the **three-leg split is 35 : 55 : 100 = 18.42% / 28.95% / 52.63%**.

The two-leg case comes out of the same ladder when the third rung does not fill. He states that
average too:

> "So, **17.63** somewhere there. Okay. And you have a **total of 90 coins**, right? So 90.74."
> — S6 `[00:48:10]`

Check: (35 × 17.28 + 55 × 17.858) / 90 = 1586.99 / 90 = **17.6332** — again exact. 90 units =
35 + 55, so the **two-leg split is 35 : 55 = 38.9% / 61.1%**, and the average sits 61% of the way
from entry to DCA. That matches how he describes it in words on the same chart:

> "if 17.28 is your um entry and 17.85 is your DCA, your average should be **somewhere in the middle
> or close up here**" — S6 `[00:46:58]`

Two independent cross-checks that these ratios are his habit and not a one-off:

1. Entry + first DCA = (35+55)/190 = **47.4% ≈ half of the position** — which is precisely the
   property he claims for his preferred ladder in an earlier session:
   > "if you had went in that 15 30 35 50 55% and your first DCA filled then you would have had at
   > least you know **half of your position size guaranteed**" — S2 `[00:21:45]`
2. The 3-leg shape reproduces his stated qualitative outcome, "**closer to the last DCA point**"
   (S6 `[00:40:05]`), while the 2-leg shape reproduces "**somewhere in the middle**" (S7
   `[00:07:14]`, S6 `[00:13:47]`). A 30/70 two-leg split would put the average 70% of the way down,
   which is not "the middle"; 50/50 would put it exactly mid, which contradicts "heavier bids".

The wick-heavy number is stated outright:
> "this wick makes it very hard to place stop losses… so maybe if you want to play long, **you go in
> very light there, like I'm talking about 20 to 30%** and then **you have your heavier bids at
> support**" — S6 `[01:54:34]`–`[01:55:08]`

The ordering rule, stated in six sessions and never contradicted:
> "Entry at the SR is going to be **light compared to your DCA**." — S2 `[00:13:52]`
> "our **heavier bids are always at the bottom** or the top of your shorting" — S2 `[00:15:33]`
> "your final DCA usually comes at support… this is going to be your **heaviest bid**" — S5 `[00:37:46]`
> "**Your entry it will always be the lighter portion of your total overall bids.**" — S5 `[00:40:34]`
> "SR points, this is why we **go in very light with our least amount of capital, then DCA
> heavier**." — S7 `[00:22:18]`
> "once an SR is there, **I go in light and then DCA heavier**" — S8 `[00:21:24]`
> "it's an SR point. Okay, **very light, heavier DCA** at the top here." — S8 `[00:48:34]`

Cutting against the verdict:
- He disclaims the numbers as he types them: "**these are just random numbers**" (S6 `[00:39:23]`).
  The disclaimer is about the absolute quantities driving the loss calculation — he says so in the
  next breath ("I haven't calculated based on how much I would lose") — not about the shape. But it
  is a real caveat.
- 50/50 appears twice as an illustration (S2 `[00:20:36]`) and once as acceptable **on spot** ("or
  even if you did 50/50 **because this is spot**", S2 `[01:00:07]`). Spot has no stop, so the
  blended average matters less; this is a scope carve-out, not a contradiction.
- The student-built calculator defaults to 33/33/33 (S4 `[02:04:56]`), but he says on the same page
  "**I haven't used this**".
- S2 `[00:21:11]` sketches a six-leg ramp "5%, 10%, 15%, 20%, 25, 30" — a linear 1:2:3:4:5:6 ramp —
  and then rejects six legs. Normalised to three legs a linear ramp gives 16.7/33.3/50, i.e. the
  same family as 18/29/53. It is weak corroboration of the shape.

**Config change.**
- `dca_size_split_3` = **`[0.18, 0.29, 0.53]`** (or the rounded `[0.20, 0.30, 0.50]` — they are
  within a percentage point). Existing default `[0.20, 0.30, 0.50]` is **confirmed**; its label in
  §11.3 should change from **OUR ratio** to **derived, S6 `[00:38:49]`**.
- `dca_size_split_2` = **`[0.39, 0.61]`** — **changed** from `[0.30, 0.70]`. This is the one real
  correction in this section: 30/70 was a guess, 39/61 is his own arithmetic.
- `dca_size_split_wick_heavy_2` = **`[0.25, 0.75]`** — changed from `[0.20, 0.80]` to the midpoint
  of his stated 20–30% band. Sweep 0.20–0.30 on the first leg.
- `size_and_stop_computed_from` = **`"average_entry"`** — no change; he does every worked
  calculation off the blended average (S6 `[00:40:40]`: "18.456 minus our average entry").

---

## Q4 — What fraction comes off at each TP?

**Question.** Is 50/50 (two TPs) and 40/30/30 (three TPs) still the split, and how does it adapt
when the number of structural TPs varies?

**Verdict.** **Two TPs → 50/50. Three TPs → 40/30/30.** Confirmed as the answer to a direct
question, and never revised. **Four or more TPs: nothing in the corpus.** The only generalisable
thing he gives is the *reason* — TP1 takes the largest share because it is the most likely to fill
— so any n-TP split must be monotonically front-loaded with the largest slice at TP1. Do not treat
the current 4- and 5-leg rows as his.

**Confidence.** `stated` for n=2 and n=3. `absent` for n≥4.

**Evidence.**

Asked point-blank and answered:
> "**What percent do you take at TP1 or TP2?** So, if I was taking, you know, solely TP1 at
> mid-range and TP2 at [range highs], **it's going to be 50/50**, right?" — S4 `[00:17:53]`

> "let's say I long here, my first TP is here, my second TP's here, my third TP's there, then **my
> first TP will always be the greater… that 40%. Right? because it's the it's the most likely one to
> get hit. So if it's three TPS, I have 40 30 30. If it's two TPS, then I do 50/50.**" — S4 `[00:18:27]`

Never restated and never contradicted in S5, S6, S7, S8 or TBOT1. Those sessions place TPs
constantly but only ever name the *levels*:
> "TP1, TP2 and TP3" — TBOT1 `[00:17:20]`, S8 `[00:49:09]`, S8 `[01:40:08]`
> "TP1 would be about a **18% move. 34 and 56**" — S8 `[01:55:11]` (distances, no fractions)

The complication the question is really about — his TPs sit at whatever structure exists, so n is
not fixed:
> "your **theoretical final TP** will be range lows. However, **I don't suggest this**… because
> **you're going to want to take profit at levels of support**" — S4 `[00:12:28]`
> "again, **you're going to take profits at levels of resistance**. I'm just saying, as a swing
> trader, they typically look for **two TPS**" — S4 `[00:13:34]`
> "this is your **TP1, two, three, four, five**" — S6 `[01:46:22]` (fib-extension ladder in price
> discovery — five TPs named, no fractions given)

So the corpus supports: pick the levels first, count them, then apply the split for that count —
which exists only for 2 and 3.

**If absent (n ≥ 4).** Parametrise instead of hard-coding two invented rows. Replace `tp_split_4`
and `tp_split_5` with a single front-loading parameter `tp_split_decay` ∈ [0.55, 1.00], where slice
*i* ∝ `decay^(i-1)` renormalised to 1.0. Note his n=2 and n=3 rows are **not** geometric (50/50 is
flat; 40/30/30 is one big slice then flat), so `decay` cannot be fitted to them — pin n=2 and n=3
to his stated values and let `decay` govern only n≥4, seeded at 0.80 (→ 34/27/22/17 at n=4), which
keeps TP1 the largest and the tail monotone. Sweep 0.55–1.00 in steps of 0.05. Metric: **realised R per
trade on setups where ≥4 structural TPs were placed**, with a tie-break on the fraction of trades
that reach TP2 before being trailed out (CF-29 moves the stop to TP1 on TP2, so back-loading the
split directly increases the chance of being trailed out of the remainder for nothing).

**Config change.**
- `tp_split_2` = **`[0.50, 0.50]`** — no change, now `stated`.
- `tp_split_3` = **`[0.40, 0.30, 0.30]`** — no change, now `stated`.
- `tp_split_4` / `tp_split_5` — **no change to the values, but they stay flagged OURS.** Preferred:
  add `tp_split_decay` (default 0.75, sweep 0.55–1.00) and derive n≥4 from it so the invented rows
  stop looking like his.
- `tp_residual_policy` = **`"trail_out"`** — no change; he accepts being trailed out and calls it
  correct (S5 `[00:40:00]`).

---

## Q5 — Minimum confluence count, and how to count overlaps

**Question.** Is three the floor, and do co-located objects count once or separately?

**Verdict.**
- **Minimum = 3 confluences**, counted as **raw objects**, not as a weighted score. Two is a
  marginal setup he will decline; one is never a trade.
- **Objects of different classes at the same price count separately.** An SR point, a supply zone
  and a resistance line at one price is **three**, and he counts it that way out loud.
- **One exception, which he also states: an order block sitting inside a supply/demand zone is not
  a separate confluence.** The zone absorbs it — "more consolidation demand zone over the order
  block".
- **Two objects of the same class at one price count once.**
- The stated hard negatives stand independently of the count: never OB-only, fib-only,
  pattern-only, trend-line-only, SFP-only, BTC.D-only.

**Confidence.** `derived` for the floor of 3 (counting the stacks he takes and the stacks he
declines, plus one direct verbal endorsement). `stated` for cross-class stacking and for the
OB-inside-zone exception. `absent` for the *weights* — he ranks classes but never scores them.

**Evidence — the floor.**

The one direct endorsement, given in answer to a student:
> "you're like, 'Hey, Arsh, like **I have trend line, I have SR line. Okay, I have demand zone. I
> have three uh possible confluences** for me to take this trade, right? **Is this a good one?**'
> **Yes. The more you can find, the better** it's going to be." — S5 `[01:43:55]`

He takes trades at exactly three, and says "three" as the reason:
> "I chose this one because the golden pocket fib lines perfectly with it. So I have two confluences
> along with the retest of the downtrend point. Okay. **So three. That's why I'm taking this one
> here.**" — S5 `[01:05:33]`
> "we have **one SR, two supply zone, three confluences**. Um, nope, no fibs there. So, if we go
> back up there, **I think it's a short**." — S8 `[00:53:41]`
> "**SR is your first confluence**, right? Use your lines first, your supply zone. You have this
> **trend line that's three**." — S5 `[01:38:21]`

He declines at one, and hesitates at two:
> "there's **no confluence here**. You see like that's all I have. **Just the order block.**"
> — S6 `[00:55:31]`
> "I don't take trades based off OBS alone. **I need confluence.**" — S6 `[00:45:16]`
> "got to ask yourself **how many confluences do we have? All right we have an SR level we have an
> order block**" — S8 `[00:40:06]`, on a setup he had just said "**sometimes it's okay to not take
> the play**" about (S8 `[00:38:57]`)

Four is his comfortable number, three is the floor:
> "I not only have the breakout and retest um SR downtrend, I have a demand zone, I have fibs, and I
> have an SR point horizontally. So **I have four confluences** for taking this trade." — S5 `[01:04:27]`
> "This OB is within the supply zone. We have golden pocket. Okay, so we have **four confluences**
> there." — S6 `[01:35:26]`
> "we have two confluences and probably some fibs if I were to draw it correctly. So we have **about
> three confluences** to go from there." — S2 `[00:31:46]`

**Evidence — counting overlaps.**

Cross-class stacking at one price counts separately. This is unambiguous in S8 `[00:53:41]` above
(SR + supply zone + resistance = three at one level) and in S8 `[00:54:14]`, where he treats the
touch history of each object separately at the same price: "supply and SR is going to be the first
touch". Also:
> "you know that **now you have two confluences**. You have a possible order block **or** a supply
> and demand zone **and then you have your SR lines** that tie in with everything" — S5 `[00:58:40]`
> "A 30 minute order block is now a two-hour SR point. **So you have extra confluence there.**"
> — S5 `[00:59:48]`

The exception, stated:
> "this demand zone **has an order block within it. But what am I going to use? More consolidation —
> demand zone over the order block here.**" — S6 `[01:07:32]`

And demonstrated: at S5 `[01:04:27]` he counts to four and then adds, without incrementing,
"**this would also be an order block as well. It's an order block within a zone.**" The OB does not
become a fifth.

Ranking, which is what the weights were built from — note he ranks but never scores:
> "**support resistance first.** Two, plot out your **supply and demand zones**. Okay. Three, …
> indicators… then **fibs**" — S6 `[01:03:33]`
> "**FIB should be the last one to draw** to get confluence… **I would use FIBS over patterns 100%
> of the time.**" — S6 `[01:56:54]`
> "patterns should **only** be used as confluence" — S4 `[02:07:46]`

Cutting against the verdict: at S6 `[00:18:57]` he counts three — "the **only** confluence that we
have is resistance one, supply zone two, and a potential SR three" — and calls the trade "risky",
then waits for a trend-line touch or a deeper move before liking it. So three is a floor, not a
green light; conviction still scales above it. And in S8 `[00:53:41]` the three he counts are SR,
supply zone and *resistance* — SR and resistance are the same class in our model, which is a live
argument against `confluence_dedup_same_class`. Two readings are possible (they may be two levels at
different prices in the same stack) and the transcript does not settle it.

**If inferred.** The floor itself is well-evidenced. The **weights** are not: he never assigns a
number to any class. Sweep `confluence_weights` over `"flat"` versus the §6.1 map, crossed with
`min_confluence_count` ∈ {2, 3, 4}. Metric: **win rate and expectancy at each gate setting, plus
trade count** — the tell is whether the weighted map rejects trades he demonstrably takes. It
already does on paper: S5 `[01:05:33]`'s stack (golden pocket 1.0 + trend-line retest 0.75 +
consolidation point) scores below 3.0 weighted, yet he takes it and names "three" as the reason. Also
sweep `confluence_merge_atr` 0.15–0.50 — that number is **OURS** and it decides what "at the same
price" means, which the whole counting rule depends on.

**Config change.**
- `min_confluence_count` = **3** — no change to the value.
- `confluence_weights` = **`"flat"`** — **changed** from the §6.1 map. Gate on the raw object count,
  which is what he actually does; keep the §6.1 weighted map for *ranking* two candidate setups
  against each other ("more confluence" comparisons, S6 `[00:18:25]`, S8 `[00:42:25]`) and for
  `high_conviction_score`, not for the entry gate. As it stands the weighted gate silently rejects
  three-object stacks he takes.
- `confluence_dedup_same_class` = **true** — no change, but flagged: S8 `[00:53:41]` is a possible
  counter-example.
- `ob_inside_zone_precedence` = **`"zone_wins"`** — no change; upgraded to `stated` on S6 `[01:07:32]`.
- `single_class_trade_forbidden` = **true** — no change.
- `confluence_merge_atr` = **0.25** — no change; still **OURS**, sweep it.
