# CONFLICTS.md — Authoritative reconciliation for the trading bot

Scope: S2–S8 (eight-part course) + TBOT1 (live walkthrough). Every genuine disagreement across
~317 rules / ~198 ambiguities / ~85 flagged contradictions, merged by topic and resolved into one
implementable rule each. A coder should be able to build from this file without re-reading the
transcripts.

## How to read an entry

- **Positions** are stated fairly, with source rule IDs. Where a rule ID does not exist (the point
  was only made in a contradiction or ambiguity note), the note ID is cited instead.
- **Verdict** is the rule the bot implements. It is always mechanical. Nothing resolves to
  "use judgement".
- **Config key** appears whenever the disagreement is a legitimate tunable. Defaults are chosen
  conservatively; alternatives are the other side(s) of the argument so a backtest can settle it.
  Each key is on its own bullet line: key name, default, then alternatives.

## Status — re-mined against the recordings (Q1–Q15)

Fifteen questions were put back to the source recordings. Thirteen came back with an answer. Where
that answer contradicts a verdict below, **the new evidence wins and the verdict is marked
REVERSED** in place, with the transcript timestamp that overturned it. Nothing has been deleted:
the original reasoning is left standing above each reversal so the change of mind is auditable.

| Q | Entry | Reversal | Confidence |
|---|---|---|---|
| Q1 | CF-08 | Order blocks get their own threshold, `ob_fill_invalidation_pct = 75`. The declared departure from precedence 1 is withdrawn. | stated |
| Q2 | CF-07 | `touch_size_decay` shifts one index right — the 3rd touch is full size, the 5th is the first cut. | inferred |
| Q3 | CF-18 | `dca_size_split_2` 30/70 → **39/61**, derived from his own worked ladder; the 3-leg row is confirmed and re-sourced. | derived |
| Q4 | CF-28 | n=2 and n=3 upgraded from "the only numbers" to `stated`; n≥4 confirmed **absent** and stays OURS. | stated / absent |
| Q5 | CF-31 | The entry gate counts **raw objects**; the §6.1 weight map is demoted to ranking and conviction. | derived |
| Q6 | CF-11, P1, P2 | `swing_price_source` is sourced, not [OUR CHOICE], with a wick carve-out for the SFP raid level and stop; the order-block impulse leg gets his percentage floor. | stated / inferred |
| Q7 | CF-20 | `sfp_governing_timeframe` → `highest_valid`. | inferred |
| Q8 | CF-02 | **A live defect.** `max_notional_pct_leverage` 10.0 was a *margin* figure enforced as a *notional* ceiling → 100.0, plus `margin_pct_leverage` and `default_leverage`. | derived |
| Q9 | CF-03 | No change; `"veto"` struck from the alternatives — it mis-read a pending-order rule. | stated |
| Q10 | CF-16 | Verdict survives intact; one entry it does not cover gets a flag, `presr_light_limit_enabled`, default off. | stated |
| Q11 | CF-22 | New key `msb_deviation_invalidates` — his real invalidation is a deviation close, not a bar count. | derived |
| Q12 | CF-26 | `mid_range_search_pct = 0` (pure geometric 50 %) struck from the allowed set. | stated |
| Q13 | CF-11 | The 30m row was **wrong**: 3.5 → 4.0. The "log-interpolation" justification for the other four rows is withdrawn. | stated |
| Q14 | CF-37 | `module_scalp_enabled` false → **true**, floored at `scalp_tf_floor = 30m`. Precedence rule 4 mis-fired on a personal-fit statement. | inferred |
| Q15 | CF-33 | No config change; the "S8 uses golden pocket and 0.786 interchangeably" claim is **struck** as an ASR artefact. | stated |

Two questions remain open and are recorded as such: **Q6(a)** the swing-detection candle count, and
**Q13**'s four missing timeframe rows (2H / 4H / 8H / 12H). Neither has any basis in the corpus and
neither has been invented here. See `CHANGELOG_EVIDENCE.md` for the sweep plans.

## Status — visual evidence pass (F1–F5)

A second pass was run against **paused video frames** rather than transcripts: seek, pause, hide the
player chrome, screenshot, measure. What the pictures show is recorded in `FRAME_FINDINGS.md`; the
consequences for this file are below. Frames are cited as `Sn mm:ss`, distinct from the `[hh:mm:ss]`
transcript timestamps used everywhere else.

| F | Entry | Outcome | Confidence |
|---|---|---|---|
| F1 | CF-13, CF-14 | **Weakened by pass 2, still shipped off.** The two-box zone (body core + wick band) appears in ~1 frame in 4; the one clear example (S6 52:38) was measured **mid-drag** and the same drawing at 53:46 reads 0.33× instead of 0.83×; S6 54:22 and S8 33:56 show a single box. `zone_wick_band_enabled` stays **false**; `zone_wick_band_max_ratio` sweep widened to 0.30–1.00. What survives: every **settled** box is body-anchored top and bottom. | one ambiguous frame, contradicted by three |
| F2 | CF-18 | **Corroborated, no change.** An independent frame reproduces `dca_size_split_2` to within 1.5 points. | derived, now doubly sourced |
| F3 | CF-02 | **Method corrected.** No position-size tool exists in any frame; the margin-vs-notional fix rests on the spoken worked example alone. | uncorroborated, uncontradicted |
| F4 | P1 (`swing_k`) | **Bounded, not decided.** One readable frame caps the left-side width at 4. Sweep narrows from open to 2–4. | partial — one instance |
| F5 | CF-11 | **Confirmed absent.** No percentage readout exists on any 2H/4H/8H/12H chart. Video is exhausted; sweep only. | negative result |

A **second frame pass** (FRAME_FINDINGS.md, pass 2) revisited F1 and produced three more entries:

| F | Entry | Outcome | Confidence |
|---|---|---|---|
| F6 | CF-14 | **Default changed — and the parameterisation with it.** Three independent frames (TBOT1 4:11 BTCUSDT.P 1H Binance, TBOT1 1:09:19 OMUSDT.P 1H Binance, S8 1:28:33 SOLUSDT.P 4H MEXC) put the stop **0.48 / 0.49 / 0.58 zone-heights** below the box bottom; the same three distances are 0.66 % / 2.70 % / 0.81 % of entry. New key `stop_buffer_zone_fraction` (**0.5**, sweep 0.45–0.60) places every stop anchored to a zone; `stop_buffer_atr` (0.15) stays as the fallback for stops that are not. | three frames, three pairs, three timeframes, two exchanges |
| F7 | CF-17, CF-18 | **Corroborated, no change.** Entries sit at a zone **edge**, never mid-box: DOGE 2H short at the bottom edge (1.00 of the way down), SOL 4H long at the top edge (0.01). That is the existing ladder — first entry at the near edge, final DCA at the far edge. The frames cannot say **which** line is the first entry and which the DCA: none is labelled. | two frames, geometry only |
| F8 | CF-31 | **Weak support, no change.** ONDO 1D shows 5 overlapping objects at the trade price; BONK 12H shows 2–3 strictly at price and 5–6 within a risk-box height. Consistent with `min_confluence_count = 3`; two data points, neither labelled as a threshold. | weak — recorded, not acted on |

**F9** came out of *re-reading the pass-2 frames*, not out of a new batch — the position tool's own
Risk/Reward and Amount readouts, which the pass-2 write-up had used only for the stop geometry:

| F | Entry | Outcome | Confidence |
|---|---|---|---|
| F9 (a) | CF-42 | **Default changed.** Four frames show his position tool's R:R readout: **3.17** (TBOT1 4:11, BTCUSDT.P 1H), **5.00** (TBOT1 22:59, HYPEUSDT.P 4H), **2.97** (TBOT1 1:09:19, OMUSDT.P 1H), **2.13** (S8 1:28:33, SOLUSDT.P 4H). That tool measures to its single **target line** — a final target, not a first partial — so `rr_measured_to` moves from `"tp1"` to `"final_tp"`. `min_rr` stays 2.0 and is re-sourced: four observed trades now stand above it, the lowest at 2.13. | four frames for the ratios; the measurement convention is **our reading of TradingView**, not his words |
| F9 (b) | CF-01, CF-02 | **Corroborated, no change.** The stop-side "Amount" reads exactly **750** in all three frames where it is visible, across three pairs, two timeframes and two exchanges. Constant cash risk per trade — which is the risk-first backwards solve the bot already implements. | three frames, unambiguous glyphs |

Precedence for these: a single frame does **not** override a verdict built from the transcripts. F1
therefore ships as a flag, not as a default, and pass 2 lowered its standing further. F2, F4, F5, F7
and F8 change no default at all — they change what a sweep should search and what is no longer worth
re-asking. **F6 is the exception**: three independent frames agreeing on a *ratio* are enough to
replace an [OUR CHOICE] invention (`stop_buffer_atr` as the only stop parameterisation), because
what they replace had no evidential standing at all. **F9(a) is the second exception**, on the same
reasoning: `rr_measured_to = "tp1"` was an [OUR CHOICE] pick between two options he never discusses,
and four frames of the readout he actually looks at point at the other one. Note what F9(a) does
*not* rest on: he never says how his tool measures R:R. That it measures to the target line is our
reading of TradingView, and it is recorded as an inference on the key itself.

## Precedence rules applied

1. Later session supersedes earlier on the same topic.
2. TBOT1 is behaviour, not doctrine. Where his live behaviour diverges from a taught rule, the
   taught rule stays the default and the divergence becomes a **conviction/size modifier**. Both are
   recorded.
3. A rule with a number beats a rule with an adjective.
4. Material he disowns ("I don't actually trade this") ships **disabled by default**.
5. Where nothing decides it, a config key with a conservative default. No invented threshold is ever
   presented as his.

### Departures from precedence (declared)

| Where | Departure | Justification |
|---|---|---|
| CF-08 | ~~Rule 1 not followed: S7's later 70–80% is rejected in favour of S5/S6's 50%~~ **WITHDRAWN (Q1).** No departure is needed: the two thresholds measure two different objects and both are his. See CF-08. |
| CF-29 | Rule 1 partially not followed: TP count is split by trade class, not set to the latest value | S8/TBOT1's "3 TPs" is stated only for scalps and live calls; S4/S6's "2 TPs" is stated for swing/range. Both survive, scoped. |
| CF-30 | Rule 3 overrides rule 1 | S4-R10 gives the only numeric TP splits (50/50, 40/30/30). Every later session leaves the fraction unstated. The number wins over later silence. |
| CF-37 | **Partly reversed (Q14)**: rule 4 mis-fired on the scalp module — "I suck at scalping" is a personal-fit statement, not a claim about the method, and he names the 2H as his own scalp chart. Rule 1 not followed for RSI | S8 disowns RSI/divergences (rule 4 → disabled), TBOT1 later trades them as a hard rule. Resolved as confluence-only, i.e. neither a full veto nor a standalone signal. |
| CF-40 | Rule 1 not followed for the 4H boundary | S8-R14 (latest) puts 4H inside "scalp"; S5-R34 and S6 both treat 4H as his primary swing timeframe and S6 states it is the timeframe he actually trades. 4H is assigned to swing. |
| CF-25 | Rule 1 not followed for "my higher low" | S8's confluence-weighted higher low is later but explicitly non-mechanical (S8-C2). Rule 5 forces the technical definition as default. |

---

# A. Risk and position sizing

## CF-01 — Maximum loss per trade

**Positions**
- 2–3% (scalp) / 4–5% (swing) of portfolio — S2-R20, S3-R24, S5-R32, S7-R8. Consistent across four sessions.
- 5–6% swing — S2-C1 (a live self-correction *away* from 5–6%, so it is a slip on tape) and TBOT1-R13 (5–6% on the SOL cycle-top swing short).
- 5% as a hard ceiling — S6-R11 ("$55 max" on $1,000).
- 1.5% when price action is unclear (1/3 size) — S6-R26.
- 2–3% counter-trend — S7-R9; 1% counter-trend — S3-R25.

**Verdict** — One ladder, applied to the account the trade belongs to (see CF-05 for spot):
swing 4.0% target / 5.0% hard cap; scalp 2.5% cap; counter-trend 2.0% cap; low-conviction 1.5% cap.
Sizing is always solved backwards: `qty = (loss_budget × equity) / |stop − average_entry|` (S6-R12
is the only worked method and it is deterministic). TBOT1's 5–6% is recorded as a
**conviction escalation**, not the default: it is available only when the setup passes the
high-conviction gate (CF-33) and only for swing, and it is off by default.

**Why** — 4–5% is stated identically in S2, S3, S5, S6 and S7; the 5–6% figure appears twice, once
as an immediately-corrected misspeak and once as live behaviour on a single trade. Precedence 2
turns the live divergence into a size modifier.

- `max_loss_pct_swing` — default 4.0; alternatives 5.0 (his stated ceiling), 3.0 (conservative)
- `max_loss_pct_swing_hard_cap` — default 5.0; alternative 6.0 (TBOT1-R13)
- `max_loss_pct_scalp` — default 2.5; alternatives 2.0, 3.0
- `max_loss_pct_counter_trend` — default 2.0; alternatives 1.0 (S3-R25), 3.0 (S7-R9)
- `max_loss_pct_low_conviction` — default 1.5; alternative 2.0
- `high_conviction_loss_pct_enabled` — default false; when true uses `max_loss_pct_swing_hard_cap`

> ### F9 addendum — the pictures show a constant cash risk, which is what this model produces
>

> **CORRECTION — the constant is $250, not $750.** `Amount` is the account **balance** at that
> leg on a $1,000 nominal base, so `risk = 1000 - Amount(stop leg) = $250` and
> `reward = Amount(target leg) - 1000`. Five frames confirm it: BTC 1H 1792.2, HYPE 4H 2249.04,
> OM 1H 1741.7, SOL 4H 1531.53, BTC 1D 1651.82 — each `Amount - 1000` reproduces
> `qty x target distance` to within 0.4%, while `750 x R:R` misses every one by 18–65%.
> Independently, `qty x stop distance = 250.00` on all **eight** position-tool frames, 2022-11 to
> 2025-06. What is corroborated is unchanged — a constant cash risk, i.e. the risk-first solve —
> but the portfolio inference of 15,000–18,750 is **withdrawn**, having been built on the misread
> field. $250 on a $1,000 nominal base is 25% per trade: a teaching template, not a live sizing
> rule. See `docs/measurement/CORRECTION-risk-figure-v2.txt`.

> The stop-side **"Amount"** on his position tool reads exactly **750** in all three frames where
> it is visible: TBOT1 4:11 (BTCUSDT.P 1H), TBOT1 22:59 (HYPEUSDT.P 4H), TBOT1 1:09:19
> (OMUSDT.P 1H) — three pairs, two timeframes, two exchanges. He sizes every trade to the same
> cash risk, and solving quantity backwards out of the loss at stop is exactly how you get that.
> **Corroboration of the model, not of the percentage:** nothing in the frames says what fraction
> of the account 750 is. Recorded on `max_loss_pct_swing` and `max_loss_pct_swing_hard_cap`;
> no default changed.
>
> The arithmetic it implies, recorded **as an inference and not as fact**: a constant 750 at the
> stated 4–5% band implies a portfolio of roughly **15,000–18,750**. His account size is never
> shown in any frame (F3), so this cannot be checked, the implication runs the wrong way (the
> percentage is the evidenced thing, not the account), and **no account-size key is derived from
> it or added.** Full table in `FRAME_FINDINGS.md` F9 and in the CF-42 addendum.

## CF-02 — Normal notional position size

**Positions**
- 20% of portfolio is a normal leverage position — S3 params table `[00:03:53]`.
- 10% of portfolio is the default, with leverage set so max loss lands at 4–5% — S7-R8.
- 6–12% per spot position, 5–6 positions, ~60–70% deployed — S4-R31, S8-R35.
- ~20% of the spot balance across 1–2 trades — S2-R34. 12% of portfolio into one spot play — S2 `[01:00:42]`.
- S2-A18/S3-A12 both flag that notional and risk are conflated throughout and never mapped.

**Verdict** — Notional is a *derived* quantity, not an input. Risk budget (CF-01) and stop distance
determine quantity; notional is then clamped to a per-trade ceiling so a wide stop cannot produce an
absurd exposure. Leverage default ceiling 10% of equity; spot 12% high-conviction / 6% low-conviction,
with a portfolio-wide spot deployment cap of 70%.

**Why** — S7 is the latest statement that ties notional and risk together and is the only one that
reconciles them (10% deployed producing a 4–5% loss). S3's 20% is an earlier, standalone figure.

> ### REVERSED — Q8 (`derived`, S6 `[00:08:36]`–`[00:11:27]`). This was a live defect, not a preference.
>
> **The percent-of-portfolio figures are MARGIN, not notional.** S7 `[00:25:54]`: *"You have a
> $1,000 portfolio. You enter each play with 10% of your portfolio. Okay. So, **whatever the
> leverage is**, you calculate that you only lose four to 5% of your port in that swing play."* The
> leverage is the free variable, which only makes sense if the 10 % is the margin posted. S7
> `[00:20:33]` closes it: 10 % in, 5 % of portfolio lost = **half of what you put in**, which under
> a notional reading needs a 50 % stop — absurd against `max_stop_pct_leverage` = 9 %.
>
> His fully worked sizing loop (S6, $1,000 portfolio, average entry 38.38, stop 41.23, distance
> 2.85) tries three sizes and states the loss each time: 40 units → **$114 = 11.4 %** *"too high"*;
> 23 → **$65 = 6.5 %** *"still too high"*; 19 → **$54 = 5.4 %** *"this is okay"*. The row he never
> says is the notional of the one he accepts: 19 × 38.38 = **$729 = 72.9 % of the portfolio.** A
> 10 % notional ceiling cannot produce any of the three, let alone the accepted one.
>
> Because SPEC §8.8 **re-solves quantity from the clamped notional**, the mislabelling did not merely
> cap exposure — it discarded the CF-01 risk budget. Every leverage trade was landing at ≈0.74 %
> portfolio risk against a 4 % budget, a silent 5.4× under-risking. That is arithmetic, not
> interpretation. Regression test: `tests/test_risk.py::TestQ8HisWorkedSizingExample`.
>
> Cross-check: $729 notional at his stated 10x (S2 `[01:52:12]`, *"I always do 10x"*) is $72.9 of
> margin = 7.3 % of the portfolio — just under S7's 10 %, and nowhere near a 10 % *notional* figure.
> S3's 20 % is the same quantity at a different date: 20 % margin at 10x is 200 % notional needing a
> 2.5 % stop, which is scalp-tight. It survives as a sweep alternative on the **margin** key.

> ### F3 — METHOD CORRECTION. The Q8 fix is uncorroborated by the frames, and uncontradicted.
>
> A frame pass looked for the tool behind these numbers, expecting a TradingView position-size
> tool whose readout would settle margin-vs-notional on sight. **There is no position-size tool in
> any frame.** The on-chart position tool appears with its stats labels turned *off*. What he
> actually uses is two things:
>
> 1. a **web average-cost calculator** (coinguides.org) for the blended entry — this is the tool
>    visible in the F2 frames on CF-18; and
> 2. the **Windows calculator** for the loss figure — legible on screen: `2.85 × 23 = 65.55`.
>
> The `2.85` is consistent with the distance from the $38.385 average entry down to the $35.51 leg,
> but he never labels it as a stop. Read it as inferred arithmetic, not a stated risk figure.
>
> **Never visible in any frame: account size, leverage, position value, or a labelled stop.** So
> the margin-vs-notional resolution above rests **entirely on the spoken worked example** at S6
> `[00:08:36]`–`[00:11:27]`. The frames do not contradict it — nothing on screen is inconsistent
> with a 72.9 % notional at 10x — but neither do they corroborate it. Its confidence stays
> `derived`, on one source, and this is recorded so the gap is not mistaken for confirmation.

- `max_notional_pct_leverage` — default **100.0** (= 10 % margin × 10x); alternatives 73.0 (his accepted worked example), 155.0 (his rejected first attempt), 200.0 (S3's 20 % margin at 10x). ~~default 10.0; alternatives 5.0, 20.0~~ — Q8. **F3: uncorroborated by the frames (no position-size tool exists on screen), uncontradicted**
- `margin_pct_leverage` — **new (Q8)** — default 10.0 (S7 `[00:25:54]`); alternative 20.0 (S3 `[00:04:25]`)
- `default_leverage` — **new (Q8)** — default 10.0 (S2 `[01:52:12]`, stated)
- `spot_notional_pct_high_conviction` — default 12.0
- `spot_notional_pct_low_conviction` — default 6.0
- `max_total_spot_deployment_pct` — default 70.0; alternative 60.0

## CF-03 — Counter-trend trades: veto, or reduced size?

**Positions**
- Hard veto — S7-R17 / S7-C1: a pending bullish setup is *cancelled* once the trend flips to lower highs.
- Reduced size — S3-R25 (half notional, 1% risk), S5-R33 (lower size, lower risk), S7-R9 (5% notional, 2–3% risk), S8-R1 (0.5×).
- Reduced size **plus** a timeframe demotion — S7-R10: counter-trend trades must drop a timeframe and be taken as scalps with fast profit-taking.
- S3-C9 flags an internal impossibility: he halves the position *and* says the loss stays the same *and* says risk drops to 1%.
- TBOT1-C10: he takes a counter-trend BTC long inside a downtrend he insists is a downtrend.

**Verdict** — Size modifier, not veto, with a demotion. A counter-trend setup is allowed at
`counter_trend_size_multiplier` × normal notional, capped by `max_loss_pct_counter_trend`, and is
classified as a scalp (TP ladder and holding rules of the scalp class). S3-C9 is resolved by
discarding the "loss stays the same" clause: halving size halves risk, and the 1%/2–3% figures are
the risk cap, not an additional constraint.

**Why** — Four sessions plus the live session all reduce size; only one clause in S7 vetoes, and S7
itself re-permits counter-trend trades fifteen minutes later. Rule 3 favours the numeric versions.

- `counter_trend_mode` — default "size_down_and_demote"; alternatives "veto", "size_down"
- `counter_trend_size_multiplier` — default 0.5; alternative 0.33
- `counter_trend_demote_to_scalp` — default true

> ### CONFIRMED — Q9 (`stated`). All four defaults survive; one alternative is struck.
>
> The apparent contradiction dissolves on a distinction he draws but never labels. **A setup already
> armed as a with-trend trade whose trend then flips → cancel the unfilled legs** (S7 `[00:17:06]`,
> *"If I saw this and I had this setup, I would have cancelled it"*) — that is pending-order hygiene,
> and the language around it is permissive (*"it is okay to **not** take this trade"*), not
> prohibitive. **A deliberately-chosen new counter-trend entry → allowed**, at half size, capped at
> 2–3 %, demoted to a scalp (S7 `[00:19:28]`–`[00:26:26]`).
>
> So `"veto"` is **struck from the alternatives**: it was a mis-reading of the pending-order rule,
> not a position anyone in the corpus holds. The demotion is not a second penalty stacked on the
> halving — he presents it as the *mechanism*: *"If you're trading against this uptrend you have to
> go to a lower time frame first. These will be scalp plays. Meaning that automatically it's already
> reduced — if you have four to 5% on a swing play, it's automatically reduced to 2 to 3%."*
> The arithmetic is self-consistent: 0.5 × 4.0 % = exactly `max_loss_pct_counter_trend`.

## CF-04 — Concurrent position caps

**Positions**
- Swing account runs **one** play at a time; scalp account may run many — S2-R32.
- Maximum 2 leverage positions at once — S4-R30; clarified as 2 *per account and per exchange*, so the true global cap is 2 × accounts — S4-C8.
- Maximum 5–6 spot positions — S4-R31.

**Verdict** — Per-bucket caps: leverage-swing 2, leverage-scalp 2, spot 5. Global leverage cap 4.
S2's "one swing play" is treated as superseded by S4's explicit cap (precedence 1) but is retained as
the conservative alternative.

**Why** — S4 is later and states the cap numerically and twice; S2's figure is a passing description
of his own account layout.

- `max_concurrent_leverage_swing` — default 2; alternative 1 (S2-R32)
- `max_concurrent_leverage_scalp` — default 2
- `max_concurrent_leverage_global` — default 4; alternative 2 (strict reading of S4-R30)
- `max_concurrent_spot` — default 5; alternative 6

## CF-05 — Spot positions have no stop, but every sizing rule needs one

**Positions**
- No stop-loss orders on spot; manual close when the support under the final DCA flips to resistance — S2-R29, S6 `[00:43:29]`/`[00:57:49]`.
- "So now I always use stop-losses" — S2 `[01:49:23]`; and stops are mandatory for challenge swing plays — S2-C4.
- Spot uses an *alert* at the level plus a close-below-and-flip check — S8-R36; leverage must have a hard stop because of liquidation risk — S8-R37.
- Spot bag invalidation is a **daily close** below the level, wicks do not count — TBOT1-R18.
- S6-C10 flags directly that the 4–5% loss budget cannot be computed for a stopless spot trade.

**Verdict** — Two stop regimes, selected by vehicle.
*Leverage*: hard exchange stop, duplicated per S4-R34 (two orders, second offset by
`duplicate_stop_offset_bps`). Sizing per CF-01.
*Spot*: no resting stop. A **synthetic stop** at the same structural price is used *only* for sizing
(so the risk budget still binds), and the exit trigger is a candle close beyond the level on the
structure timeframe, plus the flip confirmation of CF-15. Slippage past the synthetic stop is
accepted and logged as excess risk.

**Why** — S8 is the last word and separates the two cleanly; TBOT1 confirms close-based spot
invalidation in live use. The synthetic stop is our construct to keep sizing well-defined — it is
not his.

- `spot_exit_mode` — default "close_below_level_then_flip"; alternatives "close_below_level", "hard_stop"
- `spot_synthetic_stop_for_sizing` — default true
- `spot_invalidation_timeframe` — default "1D"; alternative = trade timeframe
- `duplicate_stop_offset_bps` — default 1.5 (S4-R34 worked example ≈1.3 bps); alternative 0 (single stop)

## CF-06 — A stop that is "too wide": reduce size, downgrade the vehicle, or skip?

**Positions**
- Reduce position size, never tighten the stop — S5-R24, S5 `[00:51:53]`, S7 `[00:14:13]`.
- Downgrade the vehicle: take it on spot or low leverage instead of cancelling — TBOT1-R7, TBOT1-C3.
- Tighten the stop by dropping a timeframe — S4-R16, S5-R25, S6-R19, S7-R26, S8 `[01:21:46]`.
- Skip the trade: reject zones that are "way too wide and not concise" — S8-R23; reject an 18% stop in favour of a 9% one — S7-R7; reject a 17% SFP stop — S7-R26.
- S6-A12 flags that no maximum stop width is ever operative, because any width satisfies the 5% budget at small enough size.

**Verdict** — Ordered escalation, evaluated in this sequence:
1. Attempt an LTF tightening: drop `stop_tighten_tf_steps` timeframes and re-anchor on the nearest
   qualifying wick/consolidation there.
2. If the stop still exceeds `max_stop_pct_leverage`, downgrade the vehicle to spot (or leverage ≤3×).
3. If the vehicle cannot be downgraded (leverage-only account, or spot excluded by the coin filter),
   skip the trade.
Position size is *always* solved from the risk budget regardless of which branch fires — that part
is not optional.

**Why** — All four behaviours are real and they are not alternatives; they are stages he runs in
order across the worked examples. Making the order explicit is the only way to make them coexist.

- `max_stop_pct_leverage` — default 9.0 (S7-R7's accepted variant); alternatives 10.0, 16.0 (his loosest accepted)
- `wide_stop_policy` — default "tighten_then_downgrade_then_skip"; alternatives "size_down_only", "skip"
- `stop_tighten_tf_steps` — default 2 (e.g. 8H → 1H); alternative 1
- `min_stop_pct` — default 0.5 (S7-C8's "too tight" $0.90 on SOL ≈0.5%); alternative 0.0 (no floor)

---

# B. Level and zone lifecycle

## CF-07 — Touch-count decay vs zone replay *(the single most-flagged conflict)*

**Positions**
- Levels degrade with each touch; 1–2 touches playable, 4th–6th touch "very weak", do not long — S2-R15.
- Each touch weakens support; he counts six touches before the break — S3-R18, S3-A25.
- Do not take the same trade after the **third** touch of a plain S/R level — S4-R14, S5-R2.
- Inside a *confirmed range* he takes the 5th, 6th and 7th touch and calls it correct — S4-R13, S4-C1.
- A zone may be re-taken indefinitely as long as the 50% line has not filled; seven bounces counted approvingly — S5-R28, S5-C3, S6-R10, S6-R25.
- Repeated touches still make it "weak weak support" — S6-R40, S6-C8, S6-A21.
- 2nd–3rd touch of an HTF support is a "great area" — S7-R4.
- Reduce size from the 5th touch — S8-R22.
- 1–2 plays off a golden pocket, unreliable from the third — TBOT1-R3; but he takes those trades anyway — TBOT1-C1.

**Verdict** — Three object classes, three rules, plus a size decay that applies to all of them.
1. **Bare S/R line (no zone, not a range boundary)**: hard veto after `line_touch_hard_limit` touches.
2. **Supply/demand zone or order block**: governed by the fill rule (CF-08), *not* by touch count —
   but with the size decay applied.
3. **Confirmed range boundary**: playable until the range dies (CF-28), with the size decay applied.
The size decay is a multiplier on notional by touch index, which is exactly what TBOT1 does in
practice (precedence 2: his behaviour is a conviction modifier, not an override).

`touch_size_decay = [1.00, 1.00, 0.66, 0.50, 0.33]` (touch 1..5+), applied on top of the risk budget.

**Why** — He states the third-touch veto for *lines*, the 50%-fill rule for *zones*, and the
keep-playing rule for *ranges*, and he says out loud that "range trading versus support is different"
(S4-C1). Nothing else reconciles S5-R2 with S5-R28 without discarding one of them. The decay curve is
OUR construction of "weaker every touch" — the shape is not his.

- `line_touch_hard_limit` — default 3 (S4-R14, S5-R2); alternatives 4, 6 (S3-R18)
- `range_boundary_touch_limit` — default 6 (S4-C1 takes the 5th–7th); alternatives 5, 999 (until broken)
- `touch_size_decay` — default **[1.0, 1.0, 1.0, 0.66, 0.5]**; alternatives flat [1,1,1,1,1], previous [1.0, 1.0, 0.66, 0.5, 0.33], steep [1.0, 0.75, 0.5, 0.25, 0.0] — **REVERSED, Q2** (`inferred`)
- `zone_touch_uses_fill_rule_not_count` — default true (upgraded to `derived` on S6 `[00:52:38]`, where he plays one supply zone three times and stops on the fill line, never the touch count); alternative false

> ### REVERSED (curve only) — Q2 (`inferred`). The class split and the veto index are confirmed.
>
> The verdict above is right about *which* rule governs *which* object, and the off-by-one is
> settled: he numbers the touches himself — *"that's the third touch… this is the fourth touch and we
> just blew through it"* (S5 `[00:24:35]`) — so touches 1–3 play and the 4th is vetoed, which is what
> `touch_count <= line_touch_hard_limit` already implements.
>
> The **curve** was wrong. It cut size at the 3rd touch, and the 3rd touch is one he explicitly
> endorses: *"here's a second touch, then we have a third touch. That is a great area to go long"*
> (S7 `[00:08:22]`); *"strong support, third touch"* (S4 `[01:04:03]`). The **only** touch index he
> ever attaches a reduction to is the 5th: *"we've had one, two, three, four touches of this
> resistance. So I would go in with a smaller position only because it's going to be the fifth
> touch"* (S8 `[00:54:14]`). The curve is therefore shifted one index right. The shape is still
> **OURS** and is still the sweep; what changed is that it no longer contradicts him at index 3.

## CF-08 — Zone / order-block invalidation threshold

**Positions**
- 50% of zone depth filled ⇒ the setup is dead and must not be re-taken — S5-R28, S6-R10.
- Rationale is probabilistic ("about 60% of the time"), and he concedes bounces still happen after a 50% fill — S5-C4.
- "My rule for order blocks is around 70–80%" liquidity taken — S7-R3.
- "This one doesn't have a rule where 50% has to be taken" and later a 50%-filled OB is still played — S7-C2, S7 `[00:37:57]`.
- An OB that is "completely filled" is dead — S8-R21.
- A filled OB is rescued by a strong HTF support with few touches sitting on it — S7-R4, S7-C3.

**Verdict** — One threshold: **50% of zone depth**, measured on the zone as originally drawn.
Beyond it the setup is dead and no re-take is permitted (a *different* setup may be built lower —
S5-R29). The S7 rescue clause survives as an explicit override: a dead zone is re-armed if an
independent HTF support/resistance with touch index ≤3 sits inside the remaining half, in which case
the trade is taken on that level, not on the zone.

**Why** — Declared departure from precedence 1. 50% is stated in S5, S6 and operated in S8's re-entry
logic; S7's 70–80% appears once, is contradicted twice inside S7 itself, and measures a different
thing (liquidity taken from a single OB candle vs depth of a multi-candle zone).

> ### REVERSED — Q1 (`stated`, S7 `[00:07:14]`–`[00:08:54]`). One threshold was one too few.
>
> The verdict above forced a single number onto two different objects, and the declared departure
> from precedence 1 existed only to make that possible. He splits them himself, in one breath:
>
> *"And now this order block is invalid because all the liquidity has been taken. **So this one
> doesn't have a rule where you know 50% has to be taken.** But… if this has like you know um what
> like **70 or 80%**…"* — S7 `[00:07:14]`; *"**So my rule for order blocks are like around 70 80%**
> otherwise if it's a strong support you can go ahead and play it right."* — S7 `[00:08:54]`
>
> And the passage that makes a single 50 % threshold untenable — a half-filled order block he
> **takes**: *"notice here I mentioned that **this has 50% of the order block filled** but because
> all this liquidity hasn't been grabbed… **you can still play this order block because I have
> enough confluence to play it**."* — S7 `[00:37:57]`
>
> So: **supply/demand zone = 50 % of zone depth** (S5 `[00:38:52]`, unchanged), **single-candle order
> block = ~75 % of liquidity taken** (his 70–80 band), measured by **P15** — the deepest wick through
> the body range. This also revives dead code: P15 previously ran only when
> `zone_fill_invalidation_pct` was raised to 70/80, a setting nothing shipped, so the order-block
> measure had never executed in a live configuration.

- `zone_fill_invalidation_pct` — default 50 (now `stated`, and **scoped to multi-candle zones only**); alternative 100 (S8-R21). ~~alternatives 70, 80 (S7-R3)~~ — those belong to the order-block key
- `ob_fill_invalidation_pct` — **new (Q1)** — default 75 (midpoint of his stated 70–80 band); sweep 70 / 75 / 80
- `zone_fill_measure` — default "wick_touch" (any wick through the midpoint); alternative "close_beyond"
- `zone_fill_reference` — default "as_originally_drawn"; alternative "remeasured_after_each_touch"
- `dead_zone_htf_support_rescue` — default true; `dead_zone_rescue_max_touches` default 3

## CF-09 — What an order block *is*

**Positions**
- Exactly one candle: the last opposite-colour candle before a directional change. Never two — S6-R1, S6-R2, S6-R3.
- The candle/zone the move originated from, drawn wick-to-highs; a multi-candle object — S8 `[00:34:48]`, TBOT1-A3.
- A bearish OB is "the last **red** candle before directional change" — S7 `[00:39:36]` / S7-C4 — using the identical phrase he uses for the bullish OB, which makes one of them wrong.
- An OB is usually found *inside* a demand zone and is played differently from the zone — S5 `[00:33:12]`, S5-A14, S5-C9.

**Verdict** — OB = exactly one candle (S6-R3, asked and answered directly). Bearish OB = last
**green** candle before a down move; bullish OB = last **red** candle before an up move (S6-R1/R2).
S7-C4 is a mis-statement and is discarded. The OB *box* runs from the candle's open/close body, with
wick inclusion per CF-14. An OB is never a standalone signal (CF-33) and, where it sits inside a
zone, the zone's boundaries and fill rule govern — S6-R31 ("more consolidation demand zone over the
order block").

**Why** — S6 defines it under direct questioning and repeats the colour mapping four times; S7 states
the colour once, in a sentence that is internally impossible.

- `ob_max_candles` — default 1; alternative 3 (treat as a mini-zone)
- `ob_box_source` — default "body_with_small_wick"; alternatives "body_only", "full_range"
- `ob_inside_zone_precedence` — default "zone_wins"

## CF-10 — Supply/demand zones: his continuation definition vs the textbook reversal definition

**Positions**
- HIS demand zone: price goes **up**, consolidates horizontally, continues **up** — S5-R15, S6-R5. HIS supply zone: down, consolidate, continue down — S6-R4, S7 `[00:46:12]`.
- Textbook demand zone: price comes down, consolidates, goes up (reversal) — S5 `[00:32:06]`, S6 `[00:32:38]`.
- S6-C1: at `[00:31:31]` he states his supply zone *backwards* (up-consolidate-down), matching the textbook.
- S6-A26: he trades **both** definitions throughout, with no selection rule.
- TBOT1 uses the textbook framing exclusively ("big move down followed by consolidation drifting up creates the supply zone").

**Verdict** — Detect both classes and label them. `zone_class ∈ {continuation, reversal}`. Both are
tradeable; the continuation class carries a conviction bonus in the confluence score because it is
the one he built, back-tested and named as his own. S6-C1 is treated as a misspeak: his supply zone
is down-consolidate-down (three statements plus every worked example against one).

**Why** — He never picks between them and demonstrably trades both; a selection rule would be
invented. Labelling both and weighting them is the only faithful encoding.

- `zone_direction_mode` — default "both"; alternatives "continuation_only", "reversal_only"
- `zone_continuation_confluence_bonus` — default 1.0 (one extra confluence point); alternative 0

## CF-11 — "Sufficient gap" (the move away that validates a zone)

**Positions**
- Explicit per-timeframe table — S5-R16: 15m/1h 3–5% (8% on 1h "perfect", 5% "fine"); 30m 4%; daily ≥8–12% (3–4% is NOT strong); 2-day 13%.
- S5-C2: on the 1h, 8% is "perfect", 5% is "fine", and 3–5% is "totally fine" — a 4% move is simultaneously valid and below the first-stated bar.
- Move-away strength given only as adjectives elsewhere: 2% weak/scalp-only, 5% "a lot", 26–27% justifies a swing short — S6-R8, S6-A6.
- S5-A2: nothing at all is given for 2h, 4h, 8h or 12h — precisely his primary trading timeframes.
- S6-A2: "sufficient gap" is called undefined outright.

**Verdict** — A per-timeframe minimum table, ATR-normalised as the primary test with the percentage
floor as a secondary guard. Table below is his stated numbers where he gave them and a
log-interpolation across timeframe for the gaps he never covered — **the interpolated rows are OUR
choice and are marked as such**.

| TF | min gap % | source |
|---|---|---|
| 15m | 3.0 | S5-R16 |
| 30m | **4.0** | S5-R16 / S5 `[00:54:07]` — **corrected from 3.5, Q13** |
| 1H | 4.0 | S5-R16 (lower bound of "3–5% totally fine") |
| 2H | 5.0 | **interpolated (ours)** |
| 4H | 6.0 | **interpolated (ours)** |
| 8H | 7.0 | **interpolated (ours)** |
| 12H | 7.5 | **interpolated (ours)** |
| 1D | 8.0 | S5-R16 (lower bound of 8–12%) |
| 2D | 13.0 | S5-R16 |
| 3D+ | 15.0 | **extrapolated (ours)** |

Secondary test: `move_away ≥ sufficient_gap_atr_mult × ATR(14)` on the zone's timeframe. A zone
must pass both.

**Why** — Rule 3: his numbers exist for five timeframes and must be honoured. Rule 5: the four
missing timeframes are ours and are flagged. The ATR test makes the rule transfer across coins at
different volatilities, which the raw percentages do not.

> ### REVERSED (one row) + justification withdrawn — Q13 (`stated` / `absent`).
>
> **The 30m row was a mislabelled guess.** §5.5 and this entry both cite S5-R16 for `30m = 3.5`, but
> S5-R16's own params say *"30m: 4% sufficient"* and the transcript says it outright: *"Price goes up,
> consolidates, breakout, **sufficient gap 30 minutes 4%. That's sufficient enough.**"* (S5
> `[00:54:07]`). 3.5 came from smoothing the ladder into a rising staircase. Corrected to **4.0**,
> which also makes the ≤1H rows read the way he speaks — a flat 3–5 % band with 4 % as the operating
> point, not a staircase.
>
> **The "log-interpolation across timeframe" justification is withdrawn.** His anchors are mutually
> inconsistent, so the missing rows are not derivable from them: fitting `gap = a·T^b`, the 1H (4 %)
> → 1D (8 %) step is a 24× timeframe move for a 2× gap move (`b ≈ 0.22`), while 1D (8 %) → 2D (13 %)
> is a 2× move for a 1.63× gap move (`b ≈ 0.70`). No single exponent fits both — they disagree by a
> factor of three. Extrapolating the 1D→2D slope backwards puts the 12H at ~4.9 %, *below* the 1H;
> naive volatility scaling (`b = 0.5`) puts the 4H at 8 %, past his own daily floor. The existing
> 5.0/6.0/7.0/7.5 sits inside the two defensible brackets and is **kept as a value and kept as a
> guess** — but it is no longer presented as interpolated from anything.
>
> **Consequence.** The percentage table is guessed exactly where he trades most: S5 `[01:41:45]` names
> 8H, 12H and the daily as his swing timeframes and the 2H as his scalp timeframe. On 2H–12H the
> **ATR test should be treated as the binding one** and the percentage as a loose floor — the reverse
> of how this entry framed it. And note S6 `[00:45:16]` calls a 5 % move on a 4H chart *"a lot"*,
> which is *below* the interpolated 4H row of 6.0: his own worked 4H example would fail the table.
>
> **Q6 addendum (`inferred`).** This table is also now the order block's move-size test
> (`dir_change_uses_sufficient_gap_table`). He never sizes "directional change", but in every worked
> example the order block and the zone are marked off the same impulse leg whose gap he has just
> checked out loud (S5 `[00:54:07]`), and his threshold is a *percentage that scales with timeframe*
> — *"higher time frames need to have a higher move away from that zone"* (S5 `[00:36:05]`) — which
> `dir_change_atr` alone cannot express.

> ### F5 — CONFIRMED ABSENT in the frames. Do not re-litigate this from video.
>
> Q13 established that the 2H/4H/8H/12H rows are not *spoken* anywhere. A frame pass then checked
> whether they are *shown* — whether a measure-tool readout on one of those charts pins a row down.
> It does not. **Every genuine measure-tool reading in the corpus sits on 1H or 30m.**
>
> | Frame | Chart | Reading | Note |
> |---|---|---|---|
> | S5 36:05 | 1H | 8.10 % | **measured across a hand-drawn illustration, not candles — MUST NOT be used** |
> | S5 51:25 | 1H | 4.48 % | real candles |
> | S5 55:51 | 30m | 0.51 % | real candles; subject unknown, not a threshold |
> | S6 52:38 | 1D | −4.19 % | real candles |
> | S5 1:00:22 | 2H | none | he is drawing a rectangle, not measuring |
> | S5 1:30:30 | 12H | −2.58 % | legend bar-change, i.e. that candle's own move — not a measure |
>
> **The trap this avoids.** The 8.10 % at S5 36:05 sits on a 1H chart and reads like a clean
> threshold. It is drawn over a *sketch* — a hand-drawn illustration of a zone, not real candles.
> Any process that scraped percentages mechanically would have banked it as evidence for a 1H rule.
> It is recorded here so nobody re-derives it.
>
> **Consequence.** Video is exhausted as a source for these rows. The 2H/4H/8H/12H rows stay
> **[OUR CHOICE]** and a **backtest sweep is the only remaining route** — which is why this key
> carries no `sweep_bracket`: none is derivable from the corpus. The per-row search sets stay in
> `CHANGELOG_EVIDENCE.md` Q13.

- `sufficient_gap_pct_by_tf` — default as table above (**his rows: 15m, 30m, 1H, 1D, 2D. OURS: 2H, 4H, 8H, 12H, 3D+**); alternative "his_upper_bounds" (5/5/8/…/12/13). Sweep the four OURS rows independently — see `CHANGELOG_EVIDENCE.md`. **F5: confirmed absent from the frames too; no bracket is derivable**
- `dir_change_uses_sufficient_gap_table` — **new (Q6)** — default true
- `sufficient_gap_atr_mult` — default 2.0; alternatives 1.5, 3.0
- `sufficient_gap_require_both_tests` — default true; alternative false (percentage only)

## CF-12 — Zone size: too small, and too wide

**Positions**
- Reject zones/OBs that are too small, in raw dollars: "$100 is way too tiny", a $10-wide ETH supply zone rejected for a $20–30 one, a $0.30 ENS OB called weak — S6-R48, S6-A5.
- Reject zones that are "way too wide and not concise" — S8-R23, S8-A8.
- A zone must contain at least two full candle bodies (two halves = one full); 1.5 candles is invalid — S5-R17.
- Longer consolidation = stronger zone — S5-R18, S6-R6 — with no minimum or maximum candle count (S6-A7).
- Zone within a zone: take the larger one, because its consolidation is longer — S5-R30 — which pushes the opposite way from S8-R23's "concise" requirement.

**Verdict** — Normalise to ATR and candle count, since his raw dollar figures do not transfer.
Zone is valid when: depth ∈ [`min_zone_depth_atr`, `max_zone_depth_atr`] × ATR(14) on the zone's
timeframe, **and** body count ≥ 2 (S5-R17 is the only hard number and it stands). Zone-within-zone
resolves to the larger zone only if the larger one still passes `max_zone_depth_atr`; otherwise the
inner zone is used.

**Why** — Rule 5. His size statements are all instrument-specific dollars; converting them to ATR is
our normalisation and is flagged. S5-R17's two-body minimum is a real number and survives unchanged.

- `min_zone_depth_atr` — default 0.5; alternatives 0.3, 0.75
- `max_zone_depth_atr` — default 3.0; alternatives 2.0, 5.0
- `min_zone_bodies` — default 2 (S5-R17); alternative 3
- `zone_within_zone_policy` — default "larger_if_within_max_depth"; alternative "always_larger" (S5-R30 literal)

## CF-13 — Zone box boundaries: wicks or bodies

**Positions**
- Zone construction uses candle **bodies** only; wicks excluded — S5-R17, S5 `[00:47:48]`.
- Exclude a giant wick; include small wicks "because they're very close to the candle bodies" — S5-R19, S6-R9.
- Entries go **at the wicks**, at the points of most touch — S5-R23.
- Structure and double bottoms are body-only, but stops are placed off wicks — S7-C7.
- Include a ~2% wick, exclude a 3–4% wick — S7-R7 (the only numbers anywhere).
- Do not include an insignificant wick; test whether including it changes the outcome — S8-R24. A ~$0.50 wick judged immaterial — S8-A6.
- S5-C7 states flatly: "body-only is not actually the rule."

**Verdict** — Scope-dependent, made explicit:
- **Zone/OB box**: body-anchored, extended to include a wick only if `wick_len ≤ wick_include_max_pct × price` (default 2.0%, from S7-R7).
- **Entry price**: the point-of-most-touch inside the box (see Undefined Primitive P20), which is
  usually the wick cluster — so entries may sit at wick prices even when the box is body-drawn.
- **Structure (HH/HL/LH/LL, MSB, double tops/bottoms)**: bodies only, no exceptions — S7-R11, S5-R44.
- **Stops**: wick-anchored, subject to the oversized-wick rule (CF-14).

**Why** — Every apparent contradiction here is a scope collision. He is consistent *within* each
scope; he simply never says the scopes are different.

- `wick_include_max_pct` — default 2.0 (S7-R7); alternatives 1.0, 3.0
- `wick_include_max_atr` — default 0.5; alternative disabled
- `zone_box_source` — default "body_plus_small_wick"; alternatives "body_only", "full_range"
- `zone_wick_band_enabled` — **new (F1)** — default **false**
- `zone_wick_band_max_ratio` — **new (F1)** — default 1.0; sweep bracket 0.83–1.0

> ### F1 — the box is TWO boxes (frame evidence, shipped OFF)
>
> **S6 frame 52:38, LINK 1D, his own label "Bullish OB".** Paused and measured, he has drawn **two
> nested boxes**, not one: an inner, darker box whose lower edge sits on the candle **bodies**, and
> an outer, lighter box sharing the same upper edge but extended down to the **wick** lows. The wick
> band measured **≈83 %** of the inner body-box height; the body box is ≈55 % of the full body+wick
> extent.
>
> Three further frames corroborate the *body* anchoring with wicks left outside — S5 1:30:30 (BONK
> 12H, upper wicks ~45 % typical / ~90 % max excluded, lower ~50–65 % / ~110 % max), S5 1:24:41 boxes
> A and B (ZEC 1D) — but each shows only the single inner box.
>
> **What it reconciles.** The verdict above already treats the body/wick split as a *scope*
> collision. F1 says it is also an *object* collision: "draw your boxes on candle bodies" (S5, S6)
> and "usually wicks are going to give you that entry point" (S5 `[01:05:00]`) are both true of the
> same drawing because the drawing is two objects. **Body box = the core, where the entries are
> priced. Wick band = the outer extent, where the stop goes.**
>
> **Semantics when `zone_wick_band_enabled` is true.** A `Zone` carries both extents:
> `box_top`/`box_bottom` stay the body core and keep feeding P20 and the entry ladder unchanged;
> `wick_band_top`/`wick_band_bottom` hold the outer band, which shares the core's near edge and
> extends past its far edge to the wick extreme of the formation window. CF-14 then places the stop
> beyond the band rather than beyond the body box. `zone_wick_band_max_ratio` (1.0) caps the
> extension at that multiple of the body-box height; past the cap the wick is treated as an
> **outlier and excluded** and the band collapses onto the body edge — the CF-13 giant-wick
> instinct applied one level out. The measured example was 83 %, so the default cap admits it.
>
> **Why it is off by default.** One clear frame is not enough to restructure zone geometry, and
> precedence rule 5 forbids presenting an invented default as his. With the flag down no zone
> carries a band and every number the detector and the plan builder produce is **byte-identical**
> to the single-box model — there is a test that asserts exactly that. `FRAME_FINDINGS.md` asks for
> **3–5 more frames** of him drawing a zone before the default flips.

## CF-14 — Stop anchoring: beyond the wick, or at the body when the wick is oversized

**Positions**
- Stop goes beyond the wick of the swing likely to be swept — S2-R12; above the rejection wick — S3-R15; below the support wick — S4/S5-R24; beyond the far side of the zone — S6-R17; above/below the raiding wick on an SFP — S7-R21/R22, S8-R18.
- Do **not** place the stop beyond an oversized wick; use the candle body instead. Rejected wick: $0.60 on a ~$17 coin (≈3.4%) — S6-R18.
- Never anchor to a capitulation wick — TBOT1-R6, TBOT1-C4 — while simultaneously treating the capitulation wick as a valid *entry* target (TBOT1-R22).
- Do not place the stop above a separate distinct resistance level — that level is its own trade — S5-R25.
- A stop landing inside another support/demand area is a bad stop — S6-R19 — but he places one anyway (S6-A13).
- Buffer beyond the wick is never quantified in words — S2-A8, TBOT1-A14 (BTC 93.5K entry / stop below 92K implies ~1.5%). The **pictures** quantify it: see the F6 addendum below.

**Verdict** — Deterministic anchor selection:
1. Candidate anchor = extreme of the qualifying wick at the far edge of the zone.
2. If that wick is a **capitulation wick** (Primitive P12) or exceeds `stop_wick_max_pct` (3.0%,
   from S6-R18's rejected $0.60/$17), fall back to the candle **body** extreme.
3. If the resulting stop would sit beyond an independent opposing S/R level, move the stop to just
   inside that level and re-run the LTF tightening of CF-06 instead of straddling it.
4. Apply the buffer beyond the anchor:
   a. **against a zone** — `stop_buffer_zone_fraction × zone height` (0.5) beyond the box's far
      edge (**F6**, three frames);
   b. **otherwise** — `stop_buffer_atr × ATR(14)` (0.15 ATR ≈ his ~1.5% on BTC), still OUR number.

**Why** — Rules 2 and 3 come straight from S6-R18 and S5-R25. The buffer is OUR number — he never
gives one, and his own worked example was "almost got wicked".

- `stop_wick_max_pct` — default 3.0; alternatives 2.0, 3.4 (his exact rejected wick)
- `stop_buffer_atr` — default 0.15; alternatives 0.05, 0.25, 0.5 — **fallback only after F6**
- `stop_buffer_zone_fraction` — default 0.5; sweep 0.45–0.60 (**F6**, measured 0.48 / 0.49 / 0.58)
- `stop_never_beyond_opposing_level` — default true (S5-R25)

> ### F1 addendum — where "the far side of the zone" is, when the zone has two sides
>
> S6-R17's *"beyond the far side of the zone"* is unambiguous while a zone is one box. Under the
> CF-13 F1 geometry it has two candidate far sides, and the frames answer which: the **wick band**,
> not the body core. When `zone_wick_band_enabled` is true and the setup hangs off a zone, step 1's
> candidate anchor is checked against `Zone.wick_band_stop_edge` and the stop is pushed **beyond the
> band** if the bar anchor did not already clear it. It is only ever *widened* — never tightened —
> so a band shallower than the anchor is a no-op (S5-R24: widening is always safe).
>
> Order of precedence is unchanged: the band applies after the anchor and buffer, and **before**
> steps 3 and 4, so the `stop_never_beyond_opposing_level` clip still overrides it. The band also
> does **not** survive the CF-06 step-1 LTF tightening: CF-06 is an established risk override and
> F1 is a single-frame observation, so where they collide the established rule wins.
>
> With the flag off (the default) no zone carries a band, the band edge is `None`, and CF-14 runs
> exactly as specified above.
>
> **Pass 2 weakens this addendum.** The two-box drawing is in roughly one frame in four and the one
> clear example was mid-drag; the flag stays off and now needs more than the 3–5 further frames
> pass 1 asked for. The stop rule that *did* survive contact with the pass-2 frames is F6 below,
> and it reads the **body** box, which is the geometry the bot already had.
>
> ### F6 addendum — the buffer is a fraction of the zone height, not a percentage and not an ATR
>
> Three frames, each with a position tool and a zone box on screen, different pairs, timeframes and
> exchanges:
>
> | Frame | Chart | Stop below box bottom, as a fraction of box height | Same, as % of entry |
> |---|---|---|---|
> | TBOT1 4:11 | BTCUSDT.P 1H Binance | **0.48** | 0.66 % |
> | TBOT1 1:09:19 | OMUSDT.P 1H Binance | **0.49** | 2.70 % |
> | S8 1:28:33 | SOLUSDT.P 4H MEXC | **0.58** | 0.81 % |
>
> The fraction clusters (0.48–0.58, mean ≈ 0.52); the percentage spans a factor of four; no ATR
> multiple is visible on any frame. So `stop_buffer_atr = 0.15` was the wrong **parameterisation**,
> not merely the wrong number — and it was an [OUR CHOICE] invention, so three agreeing frames beat
> it. `stop_buffer_zone_fraction` (0.5) now places any stop anchored to a zone; `stop_buffer_atr`
> keeps every stop that is *not* (levels, SFPs, structure breaks) and the CF-06 step-1 LTF
> re-anchor, where the higher-timeframe zone does not exist.
>
> Precedence is unchanged: step 3's `stop_never_beyond_opposing_level` clip still overrides the F6
> stop, and the CF-06 ladder (tighten → downgrade → skip) still runs after it. One guard is ours:
> if a DCA leg reaches past the far edge of its own box, the zone stop would not invalidate the
> whole ladder, so F6 stands down to the ATR fallback and records why.
>
> The frames also corroborate the spoken rule at TBOT1 22:57 — the stop sits **below the candle
> bodies but not below the deepest / capitulation wick**. Four frames now support it. The zone box
> is body-drawn, so an F6 stop satisfies it by construction; on the non-zone branch P12 enforces it.
> A cross-check on the first frame: TBOT1-A14 records that trade as *"BTC 93.5K entry / stop below
> 92K"*, and the frame geometry reconstructs the entry at ~93.9K — 0.4 % apart, two independent
> routes to the same trade.

## CF-15 — What confirms a flip

**Positions**
- Close through the level → SR/"pending retest" → retest and reject → confirmed. Long side: the retest candle must **close above** — S2-R1/R2/R3.
- On lower timeframes require an **extra confirmation candle** after the retest; on 4H/1D you may act without it, "yes and no, it depends" — S2-R7, S2-C3.
- A three-candle sequence: body closes beyond, a later candle retests and closes beyond, the next candle **opens** beyond — S4-R5.
- Two candles: one breakout close + one retest close, enter as soon as the following candle opens — S5-R3.
- Close beyond the level; closing exactly *on* it does not count — S8-R41.
- Flip ≠ reclaim: a flip needs break + retest + hold with multiple bounces; a reclaim is just a close back through — S8-R12 (definitions), S8-R28.
- Deviation: close through with no retest-and-rejection ⇒ level keeps its identity — S2-R4, S3-R17, S7/S8 definitions.

**Verdict** — Two-candle confirmation as the default: (1) a **body** close strictly beyond the level,
(2) a later candle that retests within the level's tolerance band and closes back on the correct
side. Entry arms at the open of the candle after (2). S4-R5's third candle ("next candle opens
beyond") is folded into this as the entry timing rather than a third confirmation. The extra
confirmation candle of S2-R7 is a config flag, on by default for timeframes below
`flip_extra_candle_below_tf`.

Deviation handling is unchanged and unanimous: a reclaim close before any retest reverts the level.
An SR stays "pending retest" for at most `pending_sr_expiry_bars` — nobody gives an expiry (S2-A15)
so a pending state would otherwise live forever in a backtest.

**Why** — S5-R3 is the latest clean statement and matches S8-R41; S4-R5's extra candle is timing, not
evidence. S2-R7's LTF confirmation is kept because it is the only timeframe-conditional confirmation
rule anywhere and he never withdraws it.

- `flip_confirm_candles` — default 2; alternative 3 (S4-R5 literal)
- `flip_extra_candle_below_tf` — default "4H" (S2-R7); alternatives "1H", disabled
- `flip_requires_body_close` — default true
- `pending_sr_expiry_bars` — default 60; alternatives 30, 200, 0 (never expires) — **OUR number, not his**

---

# C. Entry mechanics

## CF-16 — Resting limit at the SR point vs entry only after the flip completes

**Positions**
- "I always enter my positions at SR points and DCA lower" — S3-R13, stated as absolute. Same in S5-R20, S6-R14, S7-R18, S8-R16.
- Do **not** pre-place limit orders at the SR line before the flip; wait for breakout + retest + hold, then enter — S4-R19, S4 `[00:55:38]`.
- Naked breakout entries are explicitly the riskiest option and are excluded — S4-R19, S4-C7.
- Never market into anything; always limits — S4-R32, TBOT1-R25.
- SFP entries are market-on-close — S5-R3/S7-R21/S8-R5 — which is neither a resting limit nor a post-flip entry.
- S3-C12 warns: he also enters on a breakout close above 61K and on an ATH retest in the same session, so "SR point only" is not an exclusive gate.

**Verdict** — Two entry families, both enabled, distinguished by whether the level has already flipped:
- **Retest family (default)**: the level has *already* flipped (an SR point exists). Resting limit
  orders at the SR point and at the DCA levels below/above. This covers S3-R13, S5-R20, S6-R14,
  S7-R18, S8-R16 and is the bot's primary entry.
- **Flip-pending family**: the level has *not* yet flipped. No order may rest at the line. The entry
  arms only after the CF-15 confirmation completes. This is S4-R19 and it governs all pattern
  breakouts, range-boundary breaks and trend-line breaks.
- **Trigger family**: SFP and MSB-retest entries, which are event-driven (CF-20, CF-23).
Market orders are permitted *only* for the trigger family, where the signal is defined on a close.

**Why** — S4-R19 and S3-R13 are not actually in conflict once you notice S4 is talking about a level
that has not flipped yet and S3 about one that has. Nothing else lets both survive intact.

- `entry_family_retest_enabled` — default true
- `entry_family_flip_pending_enabled` — default true
- `entry_family_trigger_enabled` — default true
> ### CONFIRMED, with one addition — Q10 (`stated`). The verdict survives contact with the tape.
>
> Three things make it airtight rather than merely plausible. **(1)** He *defines* an SR point as a
> level that has already changed roles — *"previous supports turned into resistance and vice versa"*
> (S3 `[01:54:49]`) — so "I always enter at SR points" is a statement about already-flipped levels
> and cannot be a counter-example to S4. **(2)** S4's prohibition is scoped to a bull-flag breakout,
> a level that is *still resistance*. **(3)** He defines the flip as break + retest + hold (S8
> `[00:38:14]`), which is what "wait for the flip" means operationally.
>
> **The one thing this entry misses**: there is an intermediate state. A level becomes "an SR" the
> moment it is broken, *before* the retest — *"An SR means pending retest"* (S2 `[00:25:19]`) — and he
> does sometimes rest a light limit there: *"We broke above resistance. This became an SR, right? We
> came and bounced briefly from it. **My entry was light there.** My DCA came around 57360… But if I
> was a little more patient and awake, then yes, **I would have waited for the flip to happen.**"*
> (S2 `[00:27:08]`–`[00:27:41]`). Permitted-but-inferior in his own words, so it ships **off**.

- `allow_market_orders` — default "trigger_family_only"; alternatives "never" (S4-R32 literal), "always"
- `presr_light_limit_enabled` — **new (Q10)** — default **false**; alternative true (S2 `[00:27:08]`). Sweep as an on/off pair; the metric is fill rate against deviation rate at freshly-broken levels

## CF-17 — How many DCAs

**Positions**
- Max 2–3; six is explicitly forbidden; "one or two DCAs, one or two or three" — S2-R9, S2-C2. On a daily chart, "no reason to have more than one".
- Calculator default: entry + 2 DCAs at 33/33/33, or entry + 1 — S4 `[02:04:56]` — but he says he has never used that sheet (S4-A7).
- Zone width decides: tight zone 1 DCA, wide zone 2 — S5-R22.
- Default 1, occasionally 2, zero when the zone/range is tight — S6-R16.
- Max 1 DCA on scalps, zero acceptable — S8-R17. **Never** DCA a trend-line/breakdown play: one entry, one stop, multiple TPs — S8-R11.
- He specifies the DCA level and then declines to use it on the same trade — TBOT1-C6.
- SMC-style 5–6 order ladders are explicitly rejected — S6 `[01:01:51]`.

**Verdict** — DCA count by play class, with a global maximum of 2:
| Play class | DCAs |
|---|---|
| Zone / SR swing entry | 1 default, 2 if zone depth ≥ `dca2_min_zone_depth_atr` |
| Scalp | 1 max, 0 if the zone is tight |
| Breakdown / trend-line / pattern-breakout | 0 (single entry) |
| SFP | 0 (single entry) |
Six-leg ladders are hard-forbidden. TBOT1-C6's "I'm not going to DCA on this one" becomes a
conviction flag: when conviction is low the DCA leg is armed but sized to zero, i.e. the bot takes
the first entry only.

**Why** — The count is timeframe- and play-type dependent everywhere it is stated; S8 is the latest
and is the only session that separates it by play type explicitly.

- `dca_count_default` — default 1; alternatives 0, 2
- `dca_count_max` — default 2; alternative 3 (S2-R9 upper bound)
- `dca_count_scalp_max` — default 1; alternative 0
- `dca_count_breakdown` — default 0 (S8-R11)
- `dca2_min_zone_depth_atr` — default 1.5 — **OUR number** (S5-R22 gives only instrument dollars)

> ### F7 addendum — the entries sit on the box edges
>
> Two pass-2 frames measure where the entry lines sit inside the box: a DOGE 2H **short** entered at
> the **bottom** edge (fraction 1.00 of the way down the box) and a SOL 4H **long** at the **top**
> edge (0.01). Never mid-box. That is exactly the ladder this verdict already builds — first entry
> at the near edge, final DCA at the far edge — so nothing changes.
>
> Honest limit: **none of the entry lines in the frames is labelled**, so the frames cannot say
> which line is the first entry and which is the DCA. They corroborate the *geometry* (entries live
> on edges), not the ordering, and not `dca2_min_zone_depth_atr`, which stays OUR number.

## CF-18 — DCA size weighting and where the average lands

**Positions**
- First entry light, heaviest fill at the far end of the ladder — S2-R8, S5-R20, S5-R21, S6-R13, S7-R18, S8-R16.
- Average sits **closer to the final DCA** — S6-R13 (LINK 35/55/100 → avg 17.921, "closer to the last DCA point").
- Average sits **mid-zone** — S7-R18, S5-R21, S8-R16 ("so the blended average lands between them").
- 50/50 as an illustrative simplification — S2 `[00:20:36]`; 33/33/33 in the calculator — S4.
- First tranche 20–30% on wick-heavy charts — S6-R27.
- The 35/55/100 split is explicitly disclaimed: "these are just random numbers" — S6-A8.
- The final heaviest rung is not fixed to the zone bottom: "you can DCA at any support level you want" — S5-C5.

**Verdict** — Fixed splits by leg count, weighted toward the last leg (which satisfies both
"heaviest at the end" and, at two legs, a near-mid average):
- 2 legs: **30 / 70**
- 3 legs: **20 / 30 / 50**
Wick-heavy charts (`wick_heavy` flag from the liquidity screen) use 20/80 and 15/25/60.
The average entry is a *derived* value and every downstream calculation (break-even, risk budget,
TP trailing) uses it — never entry 1.

**Why** — Rule 5. Nobody gives a ratio; 50/50 and 33/33/33 both contradict the stated ordering, and
the one worked split is disclaimed. 30/70 reproduces S6-R13's "average nearer the final DCA" while
staying inside S7-R18's "roughly mid-zone".

> ### REVERSED — Q3 (`derived`). "Nobody gives a ratio" was wrong: he gives one, twice, in numbers.
>
> The one worked ladder in the corpus has both prices and quantities, and he reads the resulting
> average back off the exchange — which is what makes it checkable rather than illustrative. S6
> `[00:38:49]`: entries *"17.28 17.858 and 18.181"*, quantities *"let's actually do 35. Let's do 55.
> And let's do 100"*, average *"17.921"*. Check: (35×17.28 + 55×17.858 + 100×18.181)/190 =
> **17.9215** — exact. He confirms the total independently: *"we are making $190 for every dollar
> move"* (S6 `[00:40:40]`). So **three legs = 35:55:100 = 18.4 / 29.0 / 52.6**, and the shipped
> [0.20, 0.30, 0.50] was already right — its label moves from *OUR ratio* to **derived**.
>
> The two-leg case is the same ladder with the third rung unfilled, and he states that average too:
> *"So, **17.63** somewhere there. Okay. And you have a **total of 90 coins**"* (S6 `[00:48:10]`).
> Check: (35×17.28 + 55×17.858)/90 = **17.6332** — exact again. So **two legs = 35:55 = 39 / 61**,
> not 30/70. It also reproduces his own description of where the blend lands, *"somewhere in the
> middle"* (S6 `[00:46:58]`), which 30/70 does not.
>
> Two cross-checks that this is his habit and not a one-off: entry + first DCA = (35+55)/190 =
> **47.4 %**, precisely the property he claims for his preferred ladder — *"then you would have had
> at least you know **half of your position size** guaranteed"* (S2 `[00:21:45]`) — and the 3-leg
> shape reproduces *"closer to the last DCA point"* while the 2-leg shape reproduces *"somewhere in
> the middle"*, which is exactly the S6-R13 / S7-R18 disagreement this entry was written to resolve.
> The two are not in conflict; they describe different leg counts.
>
> On the disclaimer: *"these are just random numbers"* (S6 `[00:39:23]`) is about the absolute
> quantities driving the loss calculation — he says so in the next breath, *"I haven't calculated
> based on how much I would lose"* — not about the shape. It is a real caveat and it is why this is
> `derived` rather than `stated`.

> ### F2 — CORROBORATED by an independent frame. No default change.
>
> **S6 frames 9:40–10:53, ORDI 1D.** Two entry lines on the chart and a web average-cost calculator
> open beside them, all three numbers legible:
>
> ```
>   15 units @ $35.51        <- lighter leg
>   25 units @ $40.11        <- heavier leg
>   average cost for 40 units = $38.385
> ```
>
> 15/40 = **37.5 %**, 25/40 = **62.5 %**. The shipped `[0.39, 0.61]` was derived from his **LINK**
> ladder on S6 `[00:48:10]` — a different coin, a different session segment, a different tool. Two
> unrelated worked examples landing **within 1.5 points** of each other is the strongest
> confirmation any parameter in this project has, and it upgrades the confidence on this key
> without moving the number.
>
> A third example from the same frame run — his mid-edit rework at 11:27, 7 @ 35.51 and 15 @ 40.11
> over 22 units = **31.8 / 68.2** — puts the **observed range across three examples at 32–39 % on
> the first leg**. That is the sweep bracket: **0.32–0.40**, recorded on the key itself as
> `sweep_bracket` so a sweep reads it off the config rather than out of this prose.
>
> Note also what the frame does *not* show: no position-size tool, no account size, no leverage.
> See the F3 addendum on CF-02.

- `dca_size_split_2` — default **[0.39, 0.61]** (derived, S6 `[00:48:10]`; **corroborated by F2**, S6 frame 9:40–10:53 = 37.5/62.5); sweep bracket **0.32–0.40**; alternatives [0.50, 0.50] (spot only, S2 `[01:00:07]`), [0.30, 0.70]. ~~default [0.30, 0.70]~~ — Q3
- `dca_size_split_3` — default [0.20, 0.30, 0.50] — **confirmed and re-sourced to derived, S6 `[00:38:49]`**; alternatives [0.18, 0.29, 0.53] (his exact ratio), [0.33, 0.33, 0.33]
- `dca_size_split_wick_heavy_2` — default **[0.25, 0.75]** — midpoint of his stated 20–30 % first leg (S6 `[01:54:34]`); sweep 0.20–0.30. ~~default [0.20, 0.80]~~ — Q3
- `size_and_stop_computed_from` — default "average_entry"; alternative "first_entry"

## CF-19 — Averaging **up** when the DCA never fills

**Positions**
- If price never trades down to the DCA, average **up** at the next SR point rather than chasing — S3-R13; and only at an SR point, never into a supply zone or open air — S3-R14. Worked: SOL 25% filled, avg 150.6 → ~152.
- Everywhere else the ladder is strictly one-directional: heavier bids *below* for longs — S2-R8, S5-R20, S6-R13, S7-R18, S8-R16.
- Once a support level is lost, stop adding — S2-R31; never add to a leverage position to fix the liquidation price — S4-R33.
- S3-A10 flags there is no trigger condition: after how long, or after what price event, does the bot conclude the DCA will not fill?

**Verdict** — **Disabled by default.** Averaging up appears once, in one session, with no trigger
condition, and every other session's ladder is monotonic. When enabled, it fires only if: the first
entry is filled, price has moved `average_up_trigger_atr` in favour without filling the DCA, the
add-price is an SR point (not a zone interior), and the blended average still leaves the trade inside
its risk budget with the original stop.

**Why** — Rule 5: a rule with no trigger cannot be a default. It is preserved as a switch because
S3-R13 states it plainly and it is not contradicted, only unsupported.

- `average_up_enabled` — default false; alternative true (S3-R13)
- `average_up_trigger_atr` — default 2.0 — **OUR number**
- `average_up_only_at_sr_point` — default true (S3-R14)

## CF-20 — SFP entry: timing, standalone use, and validity

**Positions**
- Bearish SFP entered "as soon as that candle closed"; bullish SFP entered on "the next candle open" — S7-C6, S7-R21/R22, S8-R5.
- If missed, rest a limit at the prior swing high/low with the same wick stop — S5-R6, S7-R27, S8-R6 (chase captures ~1%, the limit ~2%).
- Do not market-enter if the reversal candle already closed far from the swept level — S5-R7 (no threshold, S5-A3).
- Never trade SFPs standalone; zones must be pre-marked and the SFP arrives as late confluence — S7-R30, S8 usage.
- "You can take 20 SFP trades, get stopped on 3–4, and still be net winning" — immediately followed by "I highly suggest you do not do that" — S7-C5.
- Do not take an SFP against the prevailing trend — S7-R31.
- The SFP candle cannot be adjacent to the swing candle it raids — S7-R25; swing points too close together give weak SFPs — S7-R28, S8-R4.
- Timeframe authority unresolved: the same sweep is a valid daily SFP and an invalid 12H SFP — S8-A3.

**Verdict** — One convention: **enter at the close price of the confirming candle**, executed on the
next open (the two are the same instant in a bar-close backtest; the close price is the reference for
R:R). Missed entries rest a limit at the prior swing point with the wick stop. SFP is
**confluence-only** by default — it may not be the sole reason for a trade — with a standalone mode
behind a flag for backtesting S7-C5's claim. Trend veto (S7-R31) applies. Adjacency and separation
become numeric: `sfp_min_bars_between` and `sfp_min_swing_separation_atr`. Governing timeframe is
the trade's own structure timeframe, not whichever timeframe happens to make the SFP valid.

**Why** — S7-C6 is a phrasing artefact, not a real disagreement. S7-C5 is resolved by his own
explicit instruction in the very next sentence (rule 4-adjacent: he tells you not to).

- `sfp_entry_price` — default "confirming_close"; alternative "next_open"
- `sfp_standalone_enabled` — default false; alternative true (S7-C5's claim, backtest-only)
- `sfp_min_bars_between` — default 3 — **OUR number** (S7-A11 unresolved)
- `sfp_min_swing_separation_atr` — default 1.0 — **OUR number** (S7-A12, S8-A1 unresolved)
- `sfp_max_close_distance_atr` — default 1.5 (S5-R7's "already had a huge move") — **OUR number**
- `sfp_trend_veto` — default true (S7-R31)
> ### REVERSED — Q7 (`inferred`, S8 `[00:23:06]`, S7 `[01:24:22]`).
>
> SFP validity legitimately *differs* by timeframe and he resolves it by trading the **highest**
> timeframe on which the SFP is valid, demoting a lower-timeframe-only SFP to a scalp: *"Let's say
> this is our high. We wicked above and closed below. **That's automatically a swing failure.** …
> Now, if we look at the **12-hour, we closed above, not an SFP**"* (S8 `[00:23:06]`); *"On a lower
> time frame, you could definitely take that. **But on the daily, it's a missed attempt.**"* (S7
> `[01:24:22]`); *"**Lower time frames are going to be weaker compared to higher time frames**"* (S7
> `[01:26:03]`). Under the governing principle of the whole corpus — *"**higher time frame will
> always take precedence**"* (S7 `[00:21:45]`) — `"trade_structure_tf"` misses the S8 daily SFP
> whenever structure resolves to 12H, which is the single case the question was built from. The
> search is bounded below by the trade timeframe and above by `structure_tf + 1` rung.

- `sfp_governing_timeframe` — default **"highest_valid"**; alternatives "trade_structure_tf", "1D". ~~default "trade_structure_tf"~~ — Q7
- `sfp_raid_price_source` — **new (Q6)** — default "wick" (S7 `[01:14:44]`); alternative "body". Structure is read off bodies, but *"swing high points are usually taken by wicks, not by bodies"* — the raid level and the stop beyond it are the one carve-out from `swing_price_source`

## CF-21 — Re-entry after a stop-out: trigger, and how many times

**Positions**
- After a stop-out, wait for an **SFP** before re-entering — S2-R13, S5-R38.
- Re-enter the same setup with the stop relocated beyond the wick that stopped you — S4-R12.
- Re-enter when price **closes back above** the lost support — S6-R24.
- Re-enter allowed after an MSB retest — S7 `[00:33:48]`.
- Re-short as soon as price breaks back below the trend line, repeatedly — S8-R10 (his example: 1 win from 2 attempts). No cap stated — S8-A20.
- Pre-planned stacked conditionals: if the shallow order stops, the deeper one triggers and is played until broken — TBOT1-R26; and re-entry is a *different* trigger at a different level — TBOT1 `[00:06:38]`.
- Zone-level re-takes are governed separately by CF-08.

**Verdict** — Re-entry is permitted on any of: (a) an SFP at the same level, (b) a candle close back
beyond the lost level, or (c) a pre-armed deeper conditional order. Capped at
`reentry_max_attempts_per_level` attempts per level per `reentry_window_bars`, with a
`reentry_cooldown_bars` gap, and the level's touch counter (CF-07) continues to increment across
re-entries so size decays. The stop is relocated beyond the wick that caused the stop-out (S4-R12).

**Why** — All three triggers are stated and none is retracted; the missing piece everywhere is a cap,
which is a pure backtest parameter.

- `reentry_trigger` — default "sfp_or_close_reclaim"; alternatives "sfp_only" (S2-R13), "close_reclaim_only" (S6-R24), "any"
- `reentry_max_attempts_per_level` — default 2 — **OUR number**
- `reentry_cooldown_bars` — default 3 — **OUR number**
- `reentry_window_bars` — default 100 — **OUR number**
- `reentry_stacked_conditionals_enabled` — default true (TBOT1-R26)

---

# D. Structure and trend

## CF-22 — Market structure break: what confirms it, and where the entry goes

**Positions**
- Cut when a close below the last higher low is followed by a lower low and a lower high — S2-R28 (three events).
- Exit only after a two-step confirmation: close below the last higher low, **then** a subsequent lower high — S3-R21. "Do not exit on the break alone."
- MSB = a candle **body** close beyond the last opposing swing point. Full stop — S7-R12, S7-R13.
- After a bullish MSB, wait for a retest of the broken lower high to hold as support before going long — S7-R15; mirror for bearish — S7-R16.
- After a structure break, do **not** short the close; wait for the next lower high — S8-R26.
- Break of structure permits buying the *next* higher low — TBOT1-R15, TBOT1 `[00:31:30]`.
- S7-A20: the retest has no timeout and no invalidation.

**Verdict** — Separate *detection* from *action*.
- **Detection**: MSB fires on a single body close beyond the last opposing swing point (S7-R12/R13).
  This is the flag other rules read.
- **Exit action** (closing an existing position): fires on detection alone, because S2-R28 and
  S3-R21's extra confirmation costs a full leg. Configurable to the two-step version.
- **Entry action** (opening a new position in the new direction): requires detection **plus** the
  retest holding — S7-R15/R16, S8-R26, TBOT1-R15 all agree. The retest must occur within
  `msb_retest_timeout_bars` or the setup expires.

**Why** — The apparent three-way split is a scope collision: S3-R21 is about exiting a macro bag,
S7-R12 is about detecting the event, S8-R26 is about entering. Separating them removes the conflict
entirely and preserves all three.

- `msb_exit_mode` — default "break_only"; alternative "break_plus_lower_high" (S3-R21, S2-R28)
- `msb_entry_requires_retest` — default true
> ### CONFIRMED, with one missing key — Q11 (`derived`).
>
> S7's "short the retest of the broken higher low", S8's "wait for the next lower high" and S3's
> "don't act until a lower high has formed" are **one entry described three times at increasing
> strictness**, not three entries — and CF-22's separation of the S3 *exit* rule from the entry is
> correct. The entry price is the first swing high that prints after the break, capped at the broken
> level; when price rallies all the way back, that rally's peak *is* the next lower high *and* is the
> broken level retested, which is why the three descriptions sound different.
>
> **He refuses to bound the wait.** There is no candle count anywhere in eight sessions; the closest
> he comes is *"**Next candle or however many candles it takes**"* (S4 `[00:35:08]`). His invalidation
> is a condition, not a clock: *"if we reclaim it without a retest, meaning if we close back above,
> then this is just a **deviation** of that level"* (S2 `[00:25:56]`). §11 had **no key for that at
> all**, which made an [OUR CHOICE] bar count the only invalidation an MSB carried. That is the more
> important gap than the timeout value.

- `msb_retest_timeout_bars` — default 20 — **OUR number**, and he explicitly declines to bound it (S7-A20, S4 `[00:35:08]`). Sweep {10, 20, 40, 60, disabled}; expect it to be flat
- `msb_deviation_invalidates` — **new (Q11)** — default true (S2 `[00:25:56]`)
- `msb_price_source` — default "body_close" (S7-R12)

## CF-23 — Which "last higher low" — technical, or his confluence-weighted one

**Positions**
- The technical last higher low, read off bodies — S7-R12, S5-R44.
- "My higher low": the deeper swing carrying demand-zone/major-support confluence. He stays bullish until *his* level breaks, and concedes a break of the technical one "does break market structure" while still calling himself bullish — S8-C2, S8 `[00:04:35]`–`[00:08:04]`.

**Verdict** — Technical higher low is the structural truth and drives MSB detection. His
confluence-weighted level is implemented as a **separate, secondary invalidation** for spot/long-term
bags only (`bias_invalidation_level`), selected as the deepest swing low within the last
`bias_level_lookback_bars` that carries ≥`bias_level_min_confluence` confluences. A break of the
technical level downgrades conviction and blocks new longs; a break of the bias level closes the bag.

**Why** — Declared departure from precedence 1. S8's version is later but explicitly non-mechanical
and he admits it disagrees with the structure he just taught. Rule 5 forces the mechanical default,
with his version preserved as a distinct, named object rather than silently overriding structure.

- `higher_low_selection` — default "technical"; alternative "confluence_weighted" (S8-C2)
- `bias_level_enabled` — default true (spot/long-term only)
- `bias_level_min_confluence` — default 2 — **OUR number**
- `bias_level_lookback_bars` — default 200 — **OUR number**

## CF-24 — Which timeframe defines "the trend"

**Positions**
- Counter-trend sizing depends on a trend that is never given a timeframe — S3-A11, S7-A8: he moves between macro, 2-day, daily, 2h and "lower impulse" inside one explanation and treats all of them as trends at once.
- HTF and LTF trend can disagree by design; a macro uptrend can contain a full LTF downtrend — S7 `[00:24:02]`.
- Higher timeframe wins: define the zone on the HTF even if the LTF looks cleaner — S7-R20; the daily overrides the lower timeframe — S8 `[00:38:57]`.
- MSB confirmation timeframe is used interchangeably across 2-day, daily, 2h and 1h — S7-A9.

**Verdict** — A fixed two-tier map. Every trade has a **trade timeframe** (where the entry is placed)
and a **structure timeframe** = trade TF + `structure_tf_offset` steps up the ladder
[15m, 30m, 1H, 2H, 4H, 8H, 12H, 1D, 2D, 3D, 1W]. Trend, MSB, counter-trend classification and the
HTF veto are all evaluated on the structure timeframe and only there. Default offset 2 (e.g. 1H trade
→ 4H structure; 4H trade → 12H structure).

**Why** — Rule 5 in its purest form: nothing in eight sessions picks a timeframe, and every
structure-dependent rule is unusable without one.

- `structure_tf_offset` — default 2; alternatives 1, 3
- `htf_veto_enabled` — default true (S7-R20, S8 `[00:38:57]`)
- `htf_veto_timeframe` — default "1D"; alternative = structure TF

---

# E. Range and mid-range

## CF-25 — Trading at mid-range

**Positions**
- Take no trade at all while price is *at* or consolidating on mid-range — S4-R8, S5-R14, S8-R30, and repeatedly in the exclusions ("sit on your hands", "I don't care", "I'm not taking anything").
- Mid-range longs are allowed when price is at/consolidating under the range highs; mid-range shorts when price is at range lows — S4-R6, S4-R7.
- "You always long range lows and only at range lows" (S5 `[00:21:13]`) softened three minutes later to "although you can take longs at mid-range, you have to see your situation" — S5-C1, S5-R13.
- Reconciled by him at S4 `[00:34:02]`: price *at* mid-range = no trade; limits *set* at mid-range from the extremes = fine. But the narration keeps blurring it — S4-C5.
- He issues five live scalps during mid-range chop in the same session he says no trades should be taken there — S8-C6.
- Scalpers taking mid-range breaks with very tight stops is called a legitimate play — S5-C11.

**Verdict** — His own reconciliation, made numeric. Define `mid_range_band` as
±`mid_range_band_pct` of range height around the mid-range level. Then:
- Price **inside** the band ⇒ no new entries, either direction. Hard gate.
- Price **at the range extremes** (outside the band) ⇒ resting limit orders *may* be placed at
  mid-range, targeting the opposite boundary (S4-R6/R7), provided a structural stop exists between
  the mid-range entry and the far boundary (S5-R13 — if the only support is the range low, skip).
- S8-C6 is recorded as behaviour, not doctrine: it lowers conviction, it does not open the gate.

**Why** — He states the reconciliation explicitly once; everything else is narration on charts.
Mid-range being a *level* rather than a *band* is the whole reason he keeps contradicting himself.

- `mid_range_band_pct` — default 15.0 (% of range height, each side); alternatives 10.0, 20.0 — **OUR number** (S4-A3, S8-A14)
- `mid_range_limits_from_extremes_enabled` — default true (S4-R6/R7)
- `mid_range_requires_intermediate_stop` — default true (S5-R13)

## CF-26 — Range construction and range death

**Positions**
- Range low = the first support touch after a resistance/SR level is broken above and flipped — S4-R3. Range high = confirmed by a **second** touch; a first rejection in price discovery does not count — S4-R4.
- Where two candidate lines compete, draw at the "points of most touch" — S4-R4, S4-A2 (no tolerance given).
- Mid-range is explicitly *not* the 50% midpoint; it is wherever it aligns with S/R — S4 definition, S4-A1.
- "Until proven wrong" is used to mean a stop-out, a body close beyond the boundary, and the full flip sequence, interchangeably — S4-A16.
- Range low is tradeable before the range high exists — S4 `[00:23:37]`.
- No lookback, no minimum range height, no staleness rule, no nested-range selection — S4-A15.

**Verdict** — Range detection is a bot construct (Primitive P8). Range dies when a **body close**
beyond a boundary is followed by the CF-15 flip confirmation in the opposite direction — the
strictest of his three usages, chosen because the loose readings kill ranges on every wick. Mid-range
is the highest-touch-count S/R level within ±`mid_range_search_pct` of the geometric 50%, falling
back to geometric 50% when none exists (this is OUR resolution of S4-A1; he only says "not exactly
50%").

**Why** — Rule 5. Nothing in the corpus defines a range algorithmically; the death condition is the
only place he offers alternatives, and the strict one is the conservative choice.

- `range_death_mode` — default "close_beyond_plus_flip"; alternatives "close_beyond", "single_stopout"
> ### CONFIRMED, one alternative struck — Q12 (`stated` / `absent`).
>
> This entry calls the mid-range level "OUR resolution of S4-A1". It is not ours: he was asked this
> exact question and answered it. *"Do we mark the mid-range at exactly the middle of the range or it
> should align with support and resistance? Uh, good question. **It will usually align with support
> and resistance.**"* (S4 `[00:17:53]`); *"let's call this our mid-range at this point… **even though
> it's not exactly in the middle**"* (S4 `[00:24:12]`). So `mid_range_search_pct = 0` — the pure
> geometric 50 % — is **struck from the allowed set**; it contradicts him on tape. The geometric
> midpoint survives only as the *fallback* when no S/R level sits in the search band.
>
> The **band width** (CF-25's `mid_range_band_pct`) stays `absent`, and the question may be the wrong
> shape: what he actually gates on is a **state, not a distance**. Six phrasings across S4, S5 and S8
> all say *consolidating* — *"whenever we are consolidating on or under mid-range… this is an area
> where you have to sit on your hands"* (S4 `[00:12:28]`), *"when we are at mid-range and we're just
> chopping, I just sit patience"* (S8 `[01:37:43]`) — and none gives a distance. One thing that *is*
> stated and must not be lost: the veto is on price **being** at mid-range now; a resting limit *at*
> mid-range placed while price sits at a range extreme is explicitly permitted (S4 `[00:34:02]`).

- `mid_range_search_pct` — default 10.0 (± around geometric 50%); ~~alternative 0 (pure 50%)~~ **struck, Q12**; sweep {5, 10, 15}
- `range_min_height_atr` — default 3.0 — **OUR number**
- `range_max_age_bars` — default 300 — **OUR number**

---

# F. Take profit and trade management

## CF-27 — How many take-profits

**Positions**
- Two TPs is the swing/range default: TP1 mid-range, TP2 the opposite boundary — S4 `[00:08:32]`, S4-R1/R2.
- Two TPs in every worked example — S6-R20, S6 params table.
- Two to three TPs, at structural levels; never one entry and one TP — S5-R26.
- Three TPs on scalps — S8-R19; three TPs as the default in live calls — TBOT1-R17.
- Price-discovery ladder uses TP1–TP5 from fib extensions — S6-R36.
- S7 gives no TP ladder at all — S7-A16, S7-C10.

**Verdict** — By trade class: swing/range **2 TPs**, scalp **3 TPs**, price discovery **up to 5**
(extension levels). Never fewer than 2 (S5-R26 is an explicit prohibition).

**Why** — Declared partial departure from precedence 1: the "3 TPs" statements are scoped to scalps
and live calls, the "2 TPs" statements to swings and ranges. Both survive under scope rather than one
overwriting the other.

- `tp_count_swing` — default 2; alternative 3
- `tp_count_scalp` — default 3; alternative 2
- `tp_count_price_discovery_max` — default 5 (S6-R36)
- `tp_min_count` — default 2 (S5-R26, hard)

## CF-28 — What fraction closes at each TP

**Positions**
- 2 TPs = 50/50; 3 TPs = 40/30/30, front-loaded because TP1 is most likely to fill — S4-R10. The only numbers in the entire corpus.
- Never stated again: S5-A12, S6-A11, S7-A17, S8-A10 and TBOT1-A9 all flag the fraction as missing.
- The "final TP" of a measured move is theoretical; real TPs go at intervening levels — S4 `[00:53:25]`, S5-R39 — which S4-A14 notes conflicts operationally with a fixed split when the number of levels varies.

**Verdict** — S4-R10's splits, applied to the *number of TPs actually placed*: 2 → 50/50, 3 →
40/30/30, 4 → 40/25/20/15, 5 → 35/25/20/12/8 (the 4- and 5-leg rows are OUR extrapolation of his
front-loading principle and are flagged as such). Any residual after the last TP is closed by the
trailing stop (CF-29), not left open.

**Why** — Declared departure from precedence 1 in favour of precedence 3: the only numbers in the
corpus are S4's, and every later session is silent rather than contradictory.

- `tp_split_2` — default [0.50, 0.50]; alternative [0.60, 0.40]
- `tp_split_3` — default [0.40, 0.30, 0.30]; alternative [0.50, 0.25, 0.25]
- `tp_split_4` / `tp_split_5` — defaults [0.40,0.25,0.20,0.15] / [0.35,0.25,0.20,0.12,0.08] — **OURS, and Q4 confirms nothing in the corpus supports them.** Not changed: inventing a value here is exactly what an `absent` finding forbids. Sweep plan in `CHANGELOG_EVIDENCE.md`

> ### CONFIRMED — Q4 (`stated` for n=2 and n=3, `absent` for n≥4).
>
> S4-R10 is not merely "the only numbers"; it is an answer to a direct question and it was never
> revised. *"**What percent do you take at TP1 or TP2?** So, if I was taking, you know, solely TP1 at
> mid-range and TP2 at [range highs], **it's going to be 50/50**"* (S4 `[00:17:53]`), and *"**my first
> TP will always be the greater… that 40%. Right? because it's the most likely one to get hit. So if
> it's three TPS, I have 40 30 30. If it's two TPS, then I do 50/50.**"* (S4 `[00:18:27]`). Both rows
> upgrade from "the corpus is otherwise silent" to `stated`.
>
> For n≥4 the corpus is genuinely empty, and the 4- and 5-leg rows must not be presented as his. The
> only generalisable thing he gives is the *reason* — TP1 takes the largest share because it is the
> most likely to fill — so any n-TP split must be monotonically front-loaded. Note his own rows are
> **not** geometric (50/50 is flat; 40/30/30 is one big slice then flat), so no decay parameter can be
> fitted to them.
- `tp_residual_policy` — default "trail_out"; alternative "close_at_last_tp"

## CF-29 — Stop trailing on TP hits

**Positions**
- TP1 hit → stop to break-even; TP2 hit → stop to TP1 — S4-R11, S5-R27. Stated identically in two sessions, deterministic, "no discretion stated".
- TP2 hit → move stop to TP1 **or** break-even — S6-R21. The TP1→BE step is absent from S6.
- On a double top after a large run: take partial profit and move stop to break-even — S8-R25.
- No trailing rule at all in S7 (S7-A16) or TBOT1 (TBOT1-A10, "no 'move stop to breakeven on TP1' statement").
- He accepts being trailed out and calls it correct behaviour: TP2 hit, stop to TP1, price returned and closed him at TP1 — S5 `[00:40:00]`.

**Verdict** — TP1 → break-even (average entry, not first entry); TP2 → TP1 price; TP3+ → previous TP.
S6-R21's "or break-even" is read as a looser restatement of the same ladder, not an alternative, and
is discarded. Being trailed out is a normal, accepted outcome and the setup may then be re-taken
subject to CF-08 and CF-21.

**Why** — Two sessions state it identically and mechanically; the third states a subset of it; the
last two are silent. Precedence 1 does not apply to silence.

- `trail_on_tp1` — default "break_even"; alternatives "none", "tp_minus_one_atr"
- `trail_on_tp2` — default "tp1_price"; alternative "break_even" (S6-R21)
- `break_even_reference` — default "average_entry"; alternative "first_entry"

## CF-30 — Exit at break-even when the trade "doesn't react"

**Positions**
- "If we're not getting a nice immediate reaction, I'm getting out break even" — S6-R22; also exit if the level that justified the trade is lost.
- Cut a short that fills at resistance and then consolidates under it without moving down; cut a long that fills at support and sits there — S4-R15 ("usually happens after the third or fourth touch", duration threshold not given).
- Against this: after placing zone limits you "wait passively — it could take minutes, hours, days" — S5 `[00:38:20]`.
- Exit a short if the shorted level flips into support — S6-R23. Cut a trend-line short immediately on a close back above the line — S7-R39, S8-R9.
- S6-A17 flags the trigger as subjective: no bar count, no time limit, no adverse-excursion threshold.

**Verdict** — Two distinct exits, only one of which is time-based:
- **Structural stale exit** (unanimous, keep): the level that justified the trade is lost — a close
  beyond it, or the level flipping against you. Immediate exit at market, accepting the small loss.
- **Time-based stale exit** (contested, off by default): close at break-even or better after
  `stale_exit_bars` bars in trade with adverse excursion ≥ `stale_exit_mae_atr` and no TP hit.
The passive-waiting statement (S5) governs *unfilled orders*, not filled positions — that is the
scope that removes the apparent conflict.

**Why** — S5's "wait days" is about limits that have not filled; S6-R22 is about a position that has
filled. Once separated they agree. The time trigger stays off because it has no number anywhere.

- `stale_exit_enabled` — default false; alternative true
- `stale_exit_bars` — default 8 — **OUR number**
- `stale_exit_mae_atr` — default 1.0 — **OUR number**
- `structural_stale_exit_enabled` — default true (S6-R22/R23, S7-R39, S8-R9)

---

# G. Confluence, fibs and indicators

## CF-31 — Minimum confluence count

**Positions**
- No minimum is ever stated. Flagged in every single session: S2-A14, S3-A22, S4-A11, S5-A13, S6-A14, S7 §10, S8-A15, TBOT1-A5.
- Observed counts: 3 (S2 Injective; S5 SOL entry level; S5 homework; S6 `[00:18:57]`; S8 DOGE short), 4 (S5 SOL trade; S6 `[01:35:26]`; TBOT1 typical), 5–6 (S3 `[01:41:34]` before he "fired out a whole bunch of plays").
- Hard negatives that *are* stated: never OB alone (S6-R29), never fibs alone (S6-R30), never patterns alone (S4-R38), never SFP alone (S7-R30), never trend lines alone (S7-R39), never BTC.D alone (S3 `[00:59:40]`).
- Between two candidates, take the one with more confluence — S6-R31, S8 `[00:42:25]`, TBOT1 `[00:23:30]`.
- "The more you can find, the better", and 3 confirmed as "a good one" — S5 `[01:43:55]`.
- TBOT1-A4 flags a real counting problem: an SR point, a supply zone and an order block at one price may be three objects or one.

**Verdict** — `min_confluence_count = 3`, computed on a **deduplicated, weighted** score. The single
explicit endorsement anywhere is S5's "3 is a good one", and it matches the modal observed count. The
stated negatives become a hard rule of their own: no single-class trade, regardless of score.
Deduplication: objects of different classes within `confluence_merge_atr` of each other count once
each *only if* they are of different classes; two objects of the same class at the same price count
once (Primitive P14).

Weights follow his stated hierarchy (S6-R28, S6-R38, S6 §10): S/R and SR points 1.5; supply/demand
zone 1.25; order block 1.0; fib golden pocket / 0.786 1.0; trend line 0.75; chart pattern 0.5;
SFP 0.5; range boundary 1.0; cross-market gate = veto, not a score (TBOT1 §10). **The weights are
OURS** — he ranks but never scores (S6-A15).

**Why** — Rule 5 with the one numeric endorsement he gives. Weighting is unavoidable because he makes
pairwise "more confluence" comparisons between stacks of different *kinds*, which cannot be done on
raw counts.

> ### REVERSED — Q5 (`derived`, S5 `[01:05:33]`, S8 `[00:53:41]`). The floor is right; the gate was not.
>
> **3 is confirmed** and better sourced than this entry claims — he endorses it in answer to a
> student (*"I have trend line, I have SR line. Okay, I have demand zone. I have three uh possible
> confluences… Is this a good one?" **"Yes. The more you can find, the better."*** S5 `[01:43:55]`),
> and he counts to three out loud as the reason for taking a trade: *"So I have two confluences along
> with the retest of the downtrend point. Okay. **So three. That's why I'm taking this one here.**"*
> (S5 `[01:05:33]`); *"we have **one SR, two supply zone, three confluences**"* (S8 `[00:53:41]`).
>
> **What he counts is objects, not weight.** He ranks the classes (S6 `[01:03:33]`: S/R first, then
> zones, then indicators, then fibs) but never scores them — which this entry already conceded by
> marking the weights OURS. Used as a *gate*, that invented map silently rejects stacks he
> demonstrably takes: S5 `[01:05:33]`'s golden pocket (1.0) + trend-line retest (0.75) +
> consolidation point scores **below 3.0** weighted, and he takes it and says "three".
>
> So the gate counts **raw deduplicated objects** (`confluence_gate_mode = "raw_count"`), and the
> §6.1 map is kept for what he actually does with his ranking: choosing between two candidate stacks
> (S6 `[00:18:25]`, S8 `[00:42:25]`) and the §6.3 high-conviction threshold. The reasoning in "Why"
> above — that weighting is unavoidable because he makes pairwise comparisons — is correct about
> *ranking* and was wrongly extended to *eligibility*.
>
> The dedup rule is confirmed and one exception is now `stated`: an order block inside a
> supply/demand zone is **not** a separate confluence — *"this demand zone has an order block within
> it. But what am I going to use? **More consolidation — demand zone over the order block here.**"*
> (S6 `[01:07:32]`), and at S5 `[01:04:27]` he counts to four and then adds the contained order block
> *without incrementing*. Flagged against `confluence_dedup_same_class`: S8 `[00:53:41]`'s three are
> SR + supply zone + *resistance*, and SR and resistance are one class in our model.

> ### F8 addendum — two frames, weak support, no change
>
> A pass-2 frame of ONDO 1D shows **5** overlapping objects at the trade price; a BONK 12H frame
> shows **2–3** strictly at price and **5–6** within a risk-box height. Both are at or above the
> floor of 3, which is consistent with the verdict, and the BONK frame is a useful reminder that
> the count depends on the tolerance band you count within (`confluence_merge_atr`). Neither frame
> is labelled with a threshold and two data points cannot move a default: recorded as weak
> supporting evidence only. `min_confluence_count` stays 3.

- `min_confluence_count` — default 3.0, now a **count of objects**; alternatives 2.0, 4.0
- `confluence_gate_mode` — **new (Q5)** — default "raw_count"; alternative "weighted_score" (the previous behaviour, kept for sweeps)
- `confluence_weights` — default map above, **demoted to ranking and conviction only**; alternative "flat" (all 1.0)
- `confluence_merge_atr` — default 0.25 — **OUR number**
- `confluence_dedup_same_class` — default true
- `single_class_trade_forbidden` — default true (S4-R38, S6-R29, S6-R30, S7-R30, S7-R39)

## CF-32 — Chart-prep order of operations: where do fibs and patterns sit

**Positions**
- S6-R28 gives the full sequence: clear chart → high timeframe → S/R (incl. SR points and trend lines) → supply/demand → indicators → **fibs** → **patterns**.
- Same session, S6-C2: "I prefer fibs first, patterns after" `[01:08:09]` vs "fibs should be the last one to draw to get confluence" `[01:56:54]` — and in the same breath "I would use fibs over patterns 100% of the time".
- S4-R38: S/R first, then supply/demand zones, then patterns on top — patterns are confluence only.
- S7 entry model: structure first (bodies), then static levels, then fibs, with SFP arriving **last** as second-order confluence — S7-R30.
- S6-R38: when fibs disagree with drawn S/R, S/R wins. "Everything is noise when there are support and resistance lines already drawn."

**Verdict** — One canonical pipeline:
1. Structure (bodies): swing points, trend, last HL/LH.
2. Support/resistance, SR points, trend lines.
3. Supply/demand zones and order blocks.
4. Context charts (BTC.D / USDT.D / DXY) — regime gate only, per CF-35.
5. Fibs (golden pocket, 0.786) — checked for coincidence with objects from 2–3, never as a level of their own.
6. Chart patterns — confluence only.
7. SFP — second-order confluence, evaluated only after price interacts with a level from 2–3.
Conflicts between fibs and drawn S/R resolve to S/R (S6-R38), which is what "fibs are drawn last"
actually means operationally.

**Why** — S6-C2 dissolves once you notice "last to draw" and "ranked above patterns" answer different
questions: drawing order vs tie-break authority. Fibs are drawn at step 5 and *lose* every tie to
S/R, which satisfies both statements.

- `pipeline_order` — default as above; alternative "patterns_before_fibs" (S6 `[01:08:09]`)
- `fib_loses_ties_to_sr` — default true (S6-R38)
- `sfp_evaluated_last` — default true (S7-R30)

## CF-33 — Golden pocket band, and the 0.786 naming collision

**Positions**
- Golden pocket = 0.618–**0.66**; he notes others use 0.65 and says "you can do both" — S6-R32, S6-C5, S6-A23.
- Only two fib levels are tradeable: the golden pocket and the 0.786 — S6-R32. Recommended five-level set {0.236, 0.618, 0.66, 0.786, 0.886}; he uses the middle three — S6-R33.
- 0.886 is in the recommended list but explicitly not back-tested by him — S6-A22.
- The 0.786 is the standard DCA level — S6-R15, TBOT1-R5.
- ~~S8 uses "golden pocket" and "0.786" **interchangeably** — S8 `[01:07:57]`, `[01:14:50]`, S8 definitions.~~ **STRUCK (Q15): the transcript does not contain this conflation — see the reversal note below.**
- TBOT1-A1: the golden pocket is never numerically defined in the live session at all.

**Verdict** — Golden pocket = [0.618, 0.66]. The 0.786 is a **separate** level and the S8
interchangeable usage is a verbal slip, not a redefinition — it is contradicted by S6's explicit
two-level list and by TBOT1's consistent entry-at-GP / DCA-at-0.786 split. Active fib set
{0.618, 0.66, 0.786}; 0.886 available but off by default (rule 4: he has not back-tested it).
Entry sits at the golden pocket, DCA at the 0.786 (TBOT1-R5, S6-R15).

**Why** — S6 is the session that teaches fibs and it is unambiguous; S8's usage is loose narration in
a session about something else.

- `golden_pocket_band` — default [0.618, 0.66]; alternatives [0.618, 0.65], [0.618, 0.66] ∪ [0.65]
- `fib_levels_active` — default [0.618, 0.66, 0.786]; alternative [0.236, 0.618, 0.66, 0.786, 0.886]
- `fib_886_enabled` — default false (S6-A22); alternative true
- `fib_entry_level` — default 0.618–0.66; `fib_dca_level` — default 0.786

> ### CONFIRMED, and one *position* struck — Q15 (`stated`). No config change.
>
> All three parts hold, and the "interchangeable" premise turns out to be unsupported. In every one
> of the ~20 co-occurrences he enumerates them as two distinct levels, in the same order (GP
> shallower, 0.786 deeper): *"we reject right off the golden pocket. Okay, **we reject right off the
> 786 fib**"* — two rejections at two prices, one sentence apart (S6 `[02:03:52]`); *"we got our
> bounce from the golden pocket briefly, **but the next point is the 786 fib at 90.6**"* (S6
> `[01:53:26]`). The claim rested on exactly two S8 timestamps and neither supports it:
> `[01:07:57]` mentions the golden pocket with no 0.786 anywhere near it, and `[01:14:50]` reads
> *"lines up with the golden pocket, the 786 fib"* — a two-item list whose conjunction the
> auto-captioner dropped, exactly as it did at S6 `[01:32:28]` (*"Golden pocket 786 fib"*). **This is
> an ASR artefact and the S8 extract lines asserting it should be struck, not merely down-weighted.**
>
> On 0.65 vs 0.66: the dispute is moot for a band implementation — 0.65 already lies inside
> [0.618, 0.66]. It only bites for a single limit at the band edge, and there he is unambiguous:
> *"my mentor… told me the golden pocket is the 66. So I've always used the 66. Some people use the
> 65."* (S6 `[01:40:01]`). 0.886 stays off by his own arithmetic: *"so 886, 786, 66, 618… and the 236.
> If you want to have five fib settings just those. **I use the three middle ones.**"* (S6
> `[01:41:14]`–`[01:41:52]`) — the middle three of five excludes it.
>
> One correction the question did not ask for: `fib_entry_level` should be read as *"the fib level
> that may coincide with an entry"*, never *"where entries go"*. In the session that teaches fibs he
> is explicit — *"The 786 fib is usually my DCA point… **And then my entry is always going to be an SR
> point or a resistance point.**"* (S6 `[01:56:54]`–`[01:57:29]`). No key changes; this is consistent
> with `single_class_trade_forbidden` and with fibs being drawn last.

## CF-34 — Fib draw direction

**Positions**
- Bullish fibs (looking for longs/bounces) are drawn **swing low → swing high**; bearish fibs (looking for shorts/rejections) **swing high → swing low** — S6-R34, S6-R35, S7-R1, and S6-C6 where he corrects himself onto exactly this ("actually, there's a right way… swing high to swing low").
- TBOT1 §5 records the opposite convention in live use: "swing-low→swing-high for shorts/retracement-downs and swing-high→swing-low for longs".
- TBOT1-A2: the anchor pair is never specified and he draws it differently on different charts.
- S6-A16: "you can take it from many swing low points. It doesn't matter which one" — explicitly non-deterministic.

**Verdict** — S6/S7 convention: **bullish fib = swing low → swing high; bearish fib = swing high →
swing low.** TBOT1's inversion is a transcription/narration artefact of a live session — S6-C6 has
him explicitly self-correcting *to* the S6 convention after initially saying there is no right way.
Anchors are selected mechanically by Primitive P1 (most recent qualifying swing pair on the structure
timeframe), which is OUR rule — his is admittedly arbitrary.

**Why** — Precedence 2: taught rule wins over live behaviour, and here the taught rule was stated
three times across two sessions including an on-tape correction.

- `fib_draw_convention` — default "s6" (bullish = low→high); alternative "tbot1" (inverted)
- `fib_anchor_selection` — default "most_recent_qualifying_swing_pair"; alternatives "largest_leg", "manual"

## CF-35 — Context charts: priority, and the broken DXY correlation

**Positions**
- Fixed priority: USDT.D (1), DXY (2), BTC.D (3), BVOL (4) — S3-R11. Check USDT.D and DXY every day; BTC.D only on alert — S3-R12.
- DXY's stated relationship has been inverted/broken for ~7 months and he cannot explain it — S3-R10 note, S3-C8, S3-A21. A bot cannot both weight it second and treat it as unreliable.
- BTC.D and USDT.D are traded **inverse** (buy at resistance, sell at support) — S3-R8, S3-R9, S3-C4. Strictly scoped to those two charts, never to price charts.
- BTC.D is "confluence only, I don't recommend trading off it" — S3-C5 — while the session's takeaway is a direct buy/sell rule.
- S6-R28 step 5 reduces all of this to "BTC.D if trading alts, USDT.D if majors, DXY" with no read rules — S6-A28.
- TBOT1-R19: stay risk-off on alts while BTC.D and USDT.D trend up; TBOT1-R20: if a coin's USDT pair, BTC pair and BTC itself are all at resistance, do not long — an explicit **veto**.
- No entry, stop or size number ever attaches to any of these signals — S3-A5, S3-A6.

**Verdict** — Context charts are a **regime gate**, never a signal source. They can only (a) veto a
trade, (b) reduce size, or (c) permit normal size. They never generate an entry.
- `USDT.D` and `BTC.D`: inverted TA, scoped to those tickers only. USDT.D at resistance ⇒ risk-on for
  alts; at support ⇒ risk-off / take profit (S3-R32).
- `BVOL`: zone touch sets a volatility-event flag that reduces leverage size for
  `bvol_event_window_hours`; it produces **no directional signal** (S3-R3).
- `DXY`: **disabled by default** (rule 4-adjacent — he says the relationship is broken and
  unexplained). When enabled, gated on a rolling correlation check he never proposes and which is
  therefore OURS.
- TBOT1-R20's all-pairs-at-resistance veto is implemented as a hard veto.

**Why** — S3-C8 is unresolvable as stated: a chart cannot be second-most-important and unreliable.
Rule 5 forces the conservative branch, which is to not act on it.

- `dxy_gate_enabled` — default false; alternative true
- `dxy_gate_min_rolling_corr` — default 0.4 over 90 days — **OUR construct**
- `context_priority` — default ["USDT.D", "BTC.D", "BVOL"] (DXY omitted); alternative S3-R11's full order
- `bvol_zone` — default [0.81, 1.40] (S3-R7 current box); alternatives [0.19, 0.81], [1.8, 2.2]
- `bvol_event_window_hours` — default 72; alternatives 48, 96 (S3-C2 gives all three)
- `bvol_size_multiplier` — default 0.5 during the window; alternative 0.0 (stand aside)
- `all_pairs_at_resistance_veto` — default true (TBOT1-R20)

## CF-36 — RSI and divergences: disowned, then traded

**Positions**
- "I don't use divergences — they could be very misleading", "I don't use RSI, which I never do" — S8-C3, S8 `[01:24:49]`, S8 exclusions.
- Yet the only SOL long he identifies in S8 rests on a bullish divergence, and the CRV thesis is partly a divergence read — S8-C3.
- His RSI thresholds are non-standard: below 50 = oversold, above 80 = highly overbought, 50 = reset — S8-R40, S8-C4.
- TBOT1-R11 states divergence trading as a **hard rule** in both directions and cites a 53% payout, plus a weekly bearish divergence used as the cycle-top thesis.
- TBOT1's decision procedure has "check RSI divergence" as step 10 of 17 — routine, not exceptional.
- Only indicator he uses is the 200 EMA, daily only, sometimes — S6 `[01:09:27]`; "I have no indicators on my chart whatsoever."

**Verdict** — Divergence is a **confluence contributor only** (weight 0.5), never a standalone entry
and never a veto. RSI thresholds default to **standard 30/70** with his 50/80 as an alternative,
because his version is internally inconsistent (S8-C4) and is stated once. The 200 EMA is available
as a confluence contributor, daily only, off by default.

**Why** — Declared departure from precedence 1. S8 disowns it (rule 4 → would ship disabled), TBOT1
later uses it routinely (rule 1 + rule 2 → behaviour becomes a modifier). Confluence-only is the
intersection: it can never open a trade by itself, but it can raise a stack from 2.5 to 3.0.

- `rsi_divergence_mode` — default "confluence_only"; alternatives "off" (S8 literal), "standalone" (TBOT1-R11)
- `rsi_period` — default 14; `rsi_timeframe` — default = structure TF — **OURS** (S8-A19: never specified)
- `rsi_oversold` / `rsi_overbought` — defaults 30 / 70; alternatives 50 / 80 (S8-R40)
- `ema200_confluence_enabled` — default false; daily only when true (S6)

---

# H. Universe, calendar and disowned modules

## CF-37 — Modules he teaches but disowns *(precedence rule 4)*

**Positions**
- **Trend-line breakdowns / breakouts / chart patterns**: "why am I sharing this with you if I don't trade it myself" — S8-C1, S8 exclusions `[00:28:52]`, `[00:30:37]`. Reason given: the manual-stop problem.
- **Scalping / low timeframes**: "I suck at scalping" — S5 exclusions; "this is why I don't scalp", scalping and chop are on his stated list of weaknesses — S8-C1, S8 `[01:34:48]`; "chop is weakness, I don't typically trade chop" — S2.
- **Trend-line inverse H&S**: "I don't even try to play them" — S5-R41 note.
- **Fair value gaps, ICT, SMC** — S5 exclusions, flat refusals.
- **Fib channels, spirals, arcs** — S6 exclusions.
- **Day trading**: "I'm not a day trader, I'm a swing trader" — S2 `[end]`.
- Against this: S4 devotes half a session to the pattern library with mechanical measured-move targets; S8 devotes a whole session to scalps; TBOT1 calls scalps on ~20 charts.

**Verdict** — Ship the following **disabled by default**, fully implemented and backtest-selectable:
`module_chart_patterns`, `module_trendline_break`, `module_scalp`, `module_fvg` (never implemented —
he refuses it outright), `module_ict_smc` (not implemented). The pattern module, when enabled, is
confluence-only and can never be the sole reason for a trade (S4-R38 — which he states even while
teaching it). Everything the disabled modules contribute to *confluence scoring* remains active:
a bull flag still counts 0.5 toward the stack even when the pattern module cannot open a trade.

**Why** — Precedence rule 4, applied literally. His disowning is not hedging: for trend lines he
gives the mechanical reason (no hard stop), and for scalping he says outright that low timeframes are
"highly unreliable" and he expects more losses than wins there.

> ### PARTLY REVERSED — Q14. Three disavowals, three different kinds, three different answers.
>
> **Chart patterns — outcome right, premise wrong.** He never says patterns don't work. He says
> *pattern-only* trading didn't work **for him, once, historically**, and that the fix was ordering:
> *"Yes, I traded patterns alone. I did not find any success in doing so. **So that's why I have my
> support resistance lines first and then I add these confluence on top of it.**"* (S4 `[01:48:29]`).
> He then describes actively trading pattern breakout+retest as his own method — *"you're waiting for
> the breakout retest and then you mark it long… **That's how I play it**"* (S4 `[01:47:57]`). Keep
> the default; re-source the rationale from "he disowns it" to S4-R38's *never on a pattern alone*,
> which is stronger and is what he actually said. `absent` from this entry and worth keeping: the
> measured-move target remains live as a **TP level** — it is what S4's whole pattern library is for.
>
> **Trend-line breakdown — genuinely "I don't, but it works".** Default unchanged. Worth recording
> that the reason he gives is about *him at a screen*, not about the edge: *"You don't have a
> stop-loss. **You have to watch this play as it develops**… you have to be at your computer or at
> your phone"* (S8 `[00:28:52]`, `[00:30:37]`) — the one objection in the corpus that does not
> transfer to a bot. Not enough to flip the default, but if it is enabled for a backtest his stated
> constraints bind: **small size, one entry, no DCA, close on reclaim, re-enter on the next
> breakdown** (S8 `[00:31:44]`, `[00:35:55]`). And a split this entry blurs: **trend lines themselves
> are not disowned** — S6-R28 puts them in step 3 of chart prep and he counts one as a live
> confluence (S5 `[01:38:21]`). Only trend-line-*breakdown-as-a-trigger* is off.
>
> **Scalp — REVERSED (`inferred`).** Precedence rule 4 mis-fired here. *"I suck at scalping. **I know
> my strengths and weaknesses.**"* (S5 `[00:20:02]`) is a personal-fit statement, framed identically
> to *"chop is weakness… I know what my weaknesses are"* (S2 `[01:26:28]`) and *"I suck at trading
> XRP"* — and he finishes the thought with *"**And if you're good at scalping, then this is going to
> be heaven for you**"* (S5 `[00:20:36]`). What he actually quit is named: *"when I was day trading, I
> was taking like **150 trades a day**… that required me spending so many hours watching charts…
> **The stress wasn't worth it.**"* (S8 `[01:34:48]`–`[01:35:25]`) — a reliability claim bundled with
> an effort claim, and the effort half does not transfer to a bot. Against the veto, in his own
> words: *"**If you want to scalp, it's going to be the 2 hour and the 30 minute for me personally**"*
> (S5 `[01:41:45]`) and *"**if I'm looking to scalp, whether it be a few trades within the day or
> whatever, the two-hour chart for me is my favourite**"* (S5 `[01:42:50]`). Both cannot be literal,
> so the correct control is a **floor, not a veto**. The spec also already carried a scalp risk branch
> he specified himself — `max_loss_pct_scalp`, `tp_count_scalp`, `dca_count_scalp_max`,
> `scalp_excludes_btc` — which a hard veto left as dead code.
>
> **Counter-evidence, and it is not weak:** his own live S8 scalp session, run on 15m and 1H charts,
> went *"**One for three.** Soul got stopped and Doge got stopped"* (S8 `[01:57:24]`) — his evidence,
> against the low end, from the same session as the disavowal. That is the argument for the 30m floor
> rather than for the veto, and it is why this is the one recommendation marked `inferred` against a
> prior verdict.

- `module_chart_patterns_enabled` — default false (confluence-only), **re-sourced to S4-R38 / S4 `[01:48:29]`**; alternative true
- `module_trendline_break_enabled` — default false; alternative true — when on, pin `dca_count_breakdown = 0` and sweep a size multiplier over {0.33, 0.5, 1.0}
- `module_scalp_enabled` — default **true**; alternative false. ~~default false~~ — **REVERSED, Q14** (`inferred`)
- `scalp_tf_floor` — default **"30m"** (S5-R34, S5 `[01:41:45]`); alternatives "15m", "5m" (reachable only via `counter_trend_demote_to_scalp`, S7-R10). ~~default "15m"~~ — Q14
- `disowned_modules_still_score_confluence` — default true

## CF-38 — Timeframe classes: is 4H a swing or a scalp?

**Positions**
- Swing/spot on **4H or higher**; leverage and scalps on 1H or lower; anything under 4H is a quick trade of minutes to hours — S4-R37.
- Swing = 8H, 12H, daily; 4H "also counts as swing". Scalp = 2H and 30m, and he prefers the 2H "100% of the time" — S5-R34.
- His primary trading timeframe is **4H**, plus spot — S6 `[00:57:15]`. Scalps are "anything under 4 hours".
- Scalping timeframes are 5m/10m/15m — S7-R10, S7 `[00:00:01]`.
- **Scalp = any setup on the 4-hour timeframe or lower** — S8-R14.
- S6-C11 flags the whole problem: he states 4H as his timeframe while the worked sizing example is a daily swing and the fib walkthroughs are 1H.

**Verdict** — Swing floor **4H inclusive**; scalp ceiling **2H inclusive**. A 4H setup is a swing.
Trade class drives risk budget (CF-01), DCA count (CF-17), TP count (CF-27) and holding expectations,
so the boundary must be a single value.

**Why** — Declared departure from precedence 1: S8-R14 is latest but S6 states 4H is the timeframe he
actually trades and S5-R34 explicitly admits 4H into the swing set. Two sessions against one, and the
one is a session about scalping in which the boundary was drawn to include the material being taught.

- `swing_tf_floor` — default "4H"; alternative "8H" (S5-R34 strict)
- `scalp_tf_ceiling` — default "2H"; alternative "4H" (S8-R14)
- `scalp_tf_floor` — default "15m"; alternative "5m" (S7-R10)

## CF-39 — Calendar blackouts: events and weekends

**Positions**
- Do not trade FOMC days at all; wait for the event, then for a range to form, then trade the range — S2-R27.
- On event days (CPI, FOMC, conferences) trade only higher timeframes; avoid 15m/1h — S5-R36.
- Block **leverage** on FOMC days and major geopolitical headlines; **spot dip-buying is still allowed** — S8-R2, S8 `[01:29:08]`.
- Do not trade weekends; wait for Monday's range — S5-R37. Weekend volume/volatility are low.
- Read BVOL Thursday–Sunday; Mon–Thu are the "nice days to trade" — S3-R4, softened by mid-week Fed days — S3-C3.
- Discount weekend signals, "no volume, nothing worth touching" — TBOT1-R24 — yet he issues live weekend scalps in the same session and turns the filter into a user preference — TBOT1-C8.

**Verdict** — Two independent gates.
*Event gate*: within `event_blackout_hours` of a scheduled high-impact event, block **leverage**
entries and force the structure timeframe up by one step for anything else. Spot entries permitted.
After the event, a range must form (`event_resume_requires_range = true`) before leverage re-arms.
*Weekend gate*: block **leverage** entries; permit spot. Resume on the Monday open, and the Monday
range (S5-R8/R9) is available as its own setup.

**Why** — S8 is the latest and the most precise, and it converts S2's blanket ban into a
leverage-scoped one, which also reconciles S5-R37 with TBOT1's weekend behaviour (he was calling
spot-ish scalp levels, not opening leverage).

- `event_blackout_mode` — default "leverage_only"; alternatives "all" (S2-R27), "none"
- `event_blackout_hours` — default 24 — **OUR number**
- `event_resume_requires_range` — default true (S2-R27)
- `weekend_mode` — default "leverage_blocked"; alternatives "block_all" (S5-R37), "normal"
- `event_tf_step_up` — default 1 (S5-R36)

## CF-40 — Tradeable universe: memecoins, illiquid names, size of the watchlist

**Positions**
- Exclude coins with erratic wicking / low liquidity — S2-R35 (no numeric threshold, S2-A20).
- "I don't trade meme coins really" — S4 exclusions — then he buys Mumu on-chain with the week's profits — S4-C4.
- Meme coins get full ATH-breakout treatment (POPCAT, FLOKI, DOGE) — S3 `[01:46:34]`.
- Low-cap/brand-new memecoins excluded entirely ("TA doesn't work, most are rug pulls, I trade high cap only"), with BONK and PEPE carved out as high-cap enough — S6 exclusions, S6-R45.
- Meme coins spot-only, never leverage — S7-R38, S6-R45; newly listed coins spot-only — S6-R44.
- Scalp only high-cap, high-volume, volatile coins; reject ~615K–1M daily volume names; SOL at 378M is acceptable — S8-R31. Do not scalp BTC — S8-R32, while his own set is SOL/ETH/BTC — S8-R33.
- Universe size: 4–5 regularly traded coins — S3-R29; **1–3** coins so you learn their levels — S8-R33.
- "Memes are dead, I wouldn't touch this" — TBOT1 — followed by full entry/stop/TP plans on POPCAT, DOGE and FARTCOIN — TBOT1-C5.

**Verdict** — A tiered eligibility filter, not a blanket exclusion:
- **Tier A (leverage + spot)**: market-cap rank ≤ `leverage_max_mcap_rank`, 30-day median USD volume
  ≥ `min_daily_volume_usd`, wick-ratio screen passed (Primitive P18).
- **Tier B (spot only)**: passes volume but fails rank, or is a memecoin, or is newly listed
  (< `new_listing_days`), or fails the wick screen. Covers S6-R44, S6-R45, S7-R38.
- **Tier C (excluded)**: below the volume floor, barcoding, or airdrop-driven charts he names.
Watchlist size capped at `universe_max_symbols`, defaulting to S8's tighter figure. BTC is eligible
for swing and spot but excluded from the scalp module (S8-R32) — which is not in conflict with S8-R33
because that list is his swing/spot set.

**Why** — The meme exclusions are all *vehicle* exclusions on inspection (spot yes, leverage no), not
universe exclusions, which is why he keeps calling levels on coins he says he doesn't trade. Tiering
reproduces his actual behaviour exactly.

- `leverage_max_mcap_rank` — default 100 (S2's large/mid-cap boundary); alternatives 50, 200
- `min_daily_volume_usd` — default 50_000_000; alternatives 10_000_000, 100_000_000 (S8-R31 rejects ≤1M, accepts 378M — the floor between is ours)
- `new_listing_days` — default 30 — **OUR number** (S6-R44 gives none)
- `universe_max_symbols` — default 3 (S8-R33); alternative 5 (S3-R29)
- `scalp_excludes_btc` — default true (S8-R32)
- `memecoin_vehicle` — default "spot_only"; alternatives "excluded", "any"

## CF-41 — Shorting policy

**Positions**
- "I haven't taken a short since last year… the risk-to-reward isn't there. I'd rather long and keep the uptrend" — S7 exclusions `[00:31:36]` — in a session whose worked examples are overwhelmingly shorts — S7-C9.
- "You know me, I don't like to short strength" — TBOT1-R12 — then "any impulse up, I'd be looking to short", plus short plans on BNB specifically *because* it has been outperforming — TBOT1-C2.
- Never be net short in a bull market; net short is fine in a bear market — S4-R36.
- Never short in price discovery — S3-R28, S6-R37.
- Never short at support; only at a broken-and-flipped level — S4-R9.
- Will not short for a 1–2% expected move — S3-R15, S7 `[00:31:36]`.
- More supply zones form in downtrends, so bias short there — S6-R49.

**Verdict** — Shorts enabled, gated:
1. Never in price discovery (hard).
2. Never at unbroken support (hard).
3. Never net short while the structure timeframe is in an uptrend (S4-R36) — the position-level
   version of "don't short strength".
4. Expected move to TP1 must be ≥ `min_expected_move_pct` for the timeframe, else skip.
5. Counter-trend shorts (short while structure TF is up) take the CF-03 size reduction.
TBOT1-C2 resolves as: he shorts strength *into a marked resistance inside a downtrend*, never
strength in open space. Rule 3 above encodes exactly that and it is the only reading under which both
his statements are true.

**Why** — S7-C9 and TBOT1-C2 are both self-descriptions ("you know me"), not rules; the mechanical
constraints (price discovery, unbroken support, net-short regime, minimum move) are all stated as
rules and are mutually consistent.

- `shorts_enabled` — default true; alternative false (S7 `[00:31:36]` literal)
- `net_short_allowed_in_uptrend` — default false (S4-R36)
- `short_in_price_discovery` — default false (hard, S3-R28/S6-R37)
- `min_expected_move_pct` — default {scalp 2.0, swing 5.0}; alternatives {1.0, 3.0} — from S3-R15/S6-R8/S8 "1% = weak"

## CF-42 — Minimum risk-to-reward

**Positions**
- Reject setups whose R:R is about 1:1 — S3-R26 (his alternative: stop below support, ~6% upside vs ~2% for the chase).
- Skip a mid-range long when there is no support between entry and the range low to anchor a stop, because "the R:R is not there" — S5-R13.
- Missed-entry chases are refused specifically on R:R grounds — S7-R27, S8-R6 (chase ~1% vs limit ~2%).
- No R:R floor is ever stated — TBOT1-A11: "the best R:R you can get" with no number.

**Verdict** — `min_rr = 2.0`, measured from **average entry** to the **final TP** against the stop
(the basis was TP1 until F9, below). 1:1 is explicitly rejected (S3-R26) and every worked preference
he expresses is roughly 3:1 (6% vs 2%, twice). 2.0 was the conservative midpoint and OUR number;
since F9 it is **derived with support** — four observed trades sit above it, the lowest at 2.13 —
but he still never states a floor, so it is not *his* number either.

**Why** — Rule 5 chose the floor. The *basis* was chosen by F9, from the pictures.

- `min_rr` — default 2.0; alternatives 1.5, 3.0; **sweep 2.0–2.5** (F9 observed range 2.13–5.00)
- `rr_measured_to` — default **"final_tp"** (F9); alternative "tp1" (what shipped before F9)
- `rr_measured_from` — default "average_entry"; alternative "first_entry"

> ### F9 addendum — the tool measures to the target line, not to the first partial
>
> Four frames show the TradingView **position tool** he draws with, each carrying its own
> Risk/Reward readout:
>
> | Frame | Chart | R:R shown | Target amount | Risk amount |
> |---|---|---|---|---|
> | TBOT1 4:11 | BTCUSDT.P 1H | 3.17 | 1792.2 | **750** |
> | TBOT1 22:59 | HYPEUSDT.P 4H | 5.00 | 2249.04 | **750** |
> | TBOT1 1:09:19 | OMUSDT.P 1H | 2.97 | 1741.7 | **750** |
> | S8 1:28:33 | SOLUSDT.P 4H | 2.13 | 1531.53 | not shown |
>
> **What this changes.** The tool has one target line, so its ratio is measured to a **final**
> target. The bot ladders 2–5 structural TPs (§8.7) and TP1 is by construction the **nearest**
> qualifying level, so R:R to TP1 is always the smallest ratio the ladder offers. Gating at 2.0
> measured to TP1 was therefore a materially stricter test than the one these frames show him
> passing, and it was rejecting plans he would take. On the canonical worked plan in the test
> suite (entries 100 / 97 blended to 98.17, stop 93.80, TPs 106 and 115) the two bases read
> **1.79 to TP1** and **3.85 to the final TP** — the old basis vetoed that plan at G14 and the new
> one passes it, comfortably inside the observed 2.13–5.00 band. `rr_measured_to` therefore
> defaults to `"final_tp"`; `"tp1"` is kept as the recorded alternative and the plan carries both
> figures.
>
> **What this does not rest on.** He never says how his tool computes R:R. That a TradingView
> position tool measures to its target line is **our reading of the tool**, not his words. The four
> ratios are what is directly evidenced; the convention that explains them is an inference, and the
> key's own note says so.
>
> **`min_rr` is re-sourced, not re-valued.** It stays 2.0. What changes is its standing: it was a
> pure [OUR CHOICE] midpoint, and it is now a floor that four observed trades clear, the lowest at
> 2.13. Recorded as derived-with-support with the observed range 2.13–5.00 and a sweep bracket of
> **2.0–2.5** — a sweep should ask whether the floor belongs just under the lowest observation or
> at it.
>
> **Risk per trade is a fixed cash amount (F9 part b).** The stop-side "Amount" reads exactly
> **750** in all three frames where it is visible — three different pairs, two timeframes, two
> exchanges. He sizes every trade to the same cash risk, which is exactly the risk-first solve of
> §8.8 (CF-01/CF-02: quantity comes backwards out of the loss at stop). Recorded as corroboration
> of the **model** on `max_loss_pct_swing` and `max_loss_pct_swing_hard_cap` — not of either
> percentage. The arithmetic it implies, **as an inference and not a fact**: a constant 750 at his
> stated 4–5% max loss implies a portfolio of roughly **15,000–18,750**. Consistent, and nothing
> more than that — his account size is never shown in any frame (F3), the implication runs from the
> percentage to the account rather than the other way, and **no account-size key is added**.

## CF-43 — Cutting losers vs holding long-term bags

**Positions**
- Cut the moment the support level is lost; stop DCAing a coin whose support is gone — S2-R31, S2 `[00:53:24]`, S7 `[01:04:23]`.
- For the long-term book: "if it's a long-term hold, I wouldn't suggest cutting anything"; "I wouldn't sell it completely… you can definitely derisk" — S2-C6.
- Stated once, explicitly: "if you are an investor, this does not apply to you" — S2 `[00:53:58]`.
- Long-term exit is a macro event: HTF close below the last higher low, then sell into the retest, accepting being 20–30% off the top — S7-R36, S3-R21.
- Withdraw initial capital at 3x (partial at 2x) — S2-R18.

**Verdict** — Account-scoped switch, exactly as he says once. Accounts: `long_term`, `spot_short`,
`leverage_swing`, `leverage_scalp`, `challenge`. Cut-on-level-loss applies to the three trading
accounts. `long_term` uses only the macro exit (CF-22 two-step, on the HTF) and the 3x/2x capital
withdrawal, and never cuts on a level loss.

**Why** — Not really a contradiction once the scope sentence is honoured — but it is only said once
in two hours, so it must be encoded explicitly or the bot will liquidate the investment book on a 4H
support break.

- `account_scoped_cut_rules` — default true
- `long_term_exit_mode` — default "macro_msb_two_step" (S3-R21 + S7-R36)
- `long_term_derisk_multiple` — default 3.0 full / 2.0 partial (S2-R18)

## CF-44 — Challenge-account goal and cadence

**Positions**
- 20% weekly (leverage, last bull run) — S2 `[01:19:47]`; 8% weekly as "more attainable" — S2 `[01:20:55]`; 5–10% weekly for a $1,000 spot account; 1–2% per day for leverage — S2 `[01:39:55]`.
- His personal goal stated as "5% a day **or** 5% a week" in one sentence — S2-C7.
- Weekly cadence for spot, daily or weekly for leverage — S2-R33.
- Goal compounds off the previous period's closing balance — S2-R23. Stop trading for the period once the goal is hit — S2-R22. Never chase a missed goal the following week — S2 `[01:29:52]`.
- Never increase risk-per-trade after a winning streak; de-risking down is fine — S2-R24.
- Two losing trades in a day ends the day — S2-R21 (a "loss" is never defined, nor is the day boundary — S2-A23).

**Verdict** — Pure config; nothing in the corpus decides it. Default to the conservative published
figure: **8% weekly**, compounding, spot cadence weekly / leverage weekly. Stop-on-goal and
no-chase-next-period are hard. A "loss" = any trade closed below average entry net of fees. The day
boundary is the exchange daily close (CF-45).

**Why** — Rule 5. Four goal levels and two cadences are given for one mechanism; picking the most
conservative published number is the only non-inventive choice.

- `challenge_goal_pct` — default 8.0; alternatives 5.0, 10.0, 20.0
- `challenge_cadence` — default "weekly"; alternative "daily" (leverage only)
- `challenge_stop_on_goal` — default true (S2-R22)
- `daily_loss_count_limit` — default 2 (S2-R21)
- `loss_definition` — default "closed_below_average_entry_net_fees"; alternative "stop_out_only"
- `risk_ratchet_up_allowed` — default false (S2-R24, hard)

## CF-45 — When does the day start

**Positions**
- The crypto daily candle opens at **5:00 pm** (his exchange/local time) — S5-R8; the Monday range is built from it — S5-R9.
- Daily candle close is **5:00 PM PST** — S8-R44.
- S5-A17 flags that without the exchange and timezone the Monday high/low is undefined.
- S2-A23 flags that the two-losses-per-day counter has no defined reset.

**Verdict** — 5:00 PM Pacific during **daylight time** = 00:00 UTC, which is the standard exchange
daily boundary and is almost certainly what he means. Default `day_boundary_utc = "00:00"` for candle
construction, the Monday range, and the daily loss counter. Flagged: if he literally means 17:00 PST
(standard time), the boundary is 01:00 UTC and every daily candle in the backtest is offset by an
hour — this is question Q13.

**Why** — Rule 5 plus the overwhelming convention of the exchanges he names (Binance/Bybit/BitGet all
close the daily at 00:00 UTC). Choosing his literal words over the exchange convention would make
every "daily close" rule in the corpus disagree with the data.

- `day_boundary_utc` — default "00:00"; alternative "01:00" (literal 17:00 PST)
- `monday_range_source_tf` — default "1D" (S5-R8); execution 1H/30m (S5-R9)

---

# Dismissed as apparent-only (not conflicts)

These were flagged separately in different sessions but are additive, scope-separated, or a plain
mis-speak. No reconciliation needed; noted so a coder does not re-litigate them.

- **Order blocks / zones / fibs "deferred then used"** (S2-C9, S4-C9, S5-C9, S5-C10) — later sessions
  supply the definitions. Additive, not contradictory.
- **BTC.D / USDT.D inverse TA vs normal TA** (S3-C4) — he flags the inversion himself and scopes it to
  those two tickers. Just scope it.
- **"No TA on BVOL" vs drawing a box on it** (S3-C1) — he means no trend/structure/direction analysis;
  a static horizontal band is the one permitted operation.
- **Fibonacci "complete nonsense" vs 45 minutes of fib teaching** (S6-C7) — the dismissal targets
  spirals, arcs, channels and exotic levels, which are separately excluded. Rhetoric, not a rule.
- **"There's no right way to draw fibs" reversed four seconds later** (S6-C6) — a self-correction on
  tape. Take the correction.
- **His supply zone stated backwards once** (S6-C1) — one statement against three plus every worked
  example. Mis-speak.
- **SFP "sellside liquidity" above a swing high** (S5-C8) — inverted label, correct direction. Encode
  the direction.
- **Bearish OB called "the last red candle"** (S7-C4) — impossible as written, resolved by S6-R1/R2.
  Covered in CF-09 only because a coder reading S7 alone would build the wrong detector.
- **Win rates 7/10, 8/10, 10-for-14, 7-for-7, 77–82%** (S4-C2, S5-A19) — recollections, no sample, no
  win definition. Not usable for sizing or validation; do not encode as a target.
- **Consolidation under resistance bullish vs ignored at mid-range** (S4-C3) — the mid-range gate
  (CF-25) simply outranks the read. Not a conflict once mid-range is a hard gate.
- **"CME gaps must fill" double negative** (S3-C6) — he calls it a meme chart and tells you not to
  trade it. CME gaps are a confluence contributor at most (S8 `[00:24:46]`), never a signal.
- **CRV TPs given as 18/34/56 then 20/33/50** (S8-C11) — same ladder, rounded twice.
- **Cash reserve 20% floor vs "more than 20% right now"** (S2-C5) — a floor and a current state. Floor.
- **Trend line 3 touches vs "change your trend lines to fit your narrative"** (S3-C10, S8-A4) — the
  3-touch rule is unanimous across S2/S3/S4/S5/S8; the narrative remark is an aside about there being
  multiple valid lines, which Primitive P3 handles by scoring all of them.

---

# Config key index

Grouped by area, with the count per group. Total: **177 named keys** across 45 conflicts, plus the
parameters introduced in § Undefined primitives (which overlap where a primitive supplies a key that
a conflict also references), plus the **8 keys added by the Q1–Q15 re-mining**:
`ob_fill_invalidation_pct` (CF-08/Q1), `margin_pct_leverage` and `default_leverage` (CF-02/Q8),
`confluence_gate_mode` (CF-31/Q5), `sfp_raid_price_source` (CF-20/Q6),
`dir_change_uses_sufficient_gap_table` (CF-11/Q6), `msb_deviation_invalidates` (CF-22/Q11) and
`presr_light_limit_enabled` (CF-16/Q10). The implementation's `Config` surface is 242 keys
(SPEC §11.13's 234 plus these 8).

| Area | Conflicts | Keys |
|---|---|---|
| Risk & sizing (CF-01…CF-06) | 6 | 25 |
| Level & zone lifecycle (CF-07…CF-14) | 8 | 30 |
| Entry mechanics (CF-15…CF-21) | 7 | 28 |
| Structure & trend (CF-22…CF-24) | 3 | 11 |
| Range & mid-range (CF-25…CF-26) | 2 | 7 |
| TP & management (CF-27…CF-30) | 4 | 15 |
| Confluence, fibs, indicators (CF-31…CF-36) | 6 | 25 |
| Universe, calendar, disowned modules (CF-37…CF-45) | 9 | 36 |
| **Total** | **45** | **177** |

Keys marked **OUR number** in the body have no basis in the transcripts and exist only because the
bot cannot run without them. They should be the first parameters swept in any backtest, and none of
them should ever be described to the trader as his.

---

# § Unresolvable without the trader

Ordered by how much they block implementation. Each is phrased so it can be sent to him verbatim.

> ### STATUS after the Q1–Q15 re-mining
>
> **Thirteen of these fifteen were answered from the recordings and no longer need him.** They are
> struck through below with the verdict and the reversal, if any; the full evidence is in
> `answers/part1.md`, `answers/part2.md`, `answers/part3.md`, and the applied changes in
> `CHANGELOG_EVIDENCE.md`.
>
> **Two still need him, and neither has been invented in the meantime:**
>
> * **Q6(a) — the swing-detection candle count.** There is no fractal width, no lookback and no
>   N-bar rule anywhere in eight sessions; he never counts candles either side of a pivot, not once.
>   What he does instead is *ordinal and relational* and explicitly multi-valued at one moment —
>   *"you have multiple swing… this is your swing high. This is your swing high. This is your swing
>   high"* (S7 `[01:31:23]`), *"You can take it from many swing low points. **It doesn't matter which
>   one.**"* (S6 `[01:21:06]`). `swing_k = 3` stands as a placeholder and stays **[OUR CHOICE]**.
>   **F4 bounds it without deciding it.** Of seven frames requested for candle-counting, four were
>   unusable — he is sketching freehand over a blank chart, or the chart is in line mode, so there
>   are no candles to count. The one confident reading is **S7 34:30**, a 4H swing high marked with
>   an arrow tip: the **5th** candle to its left *exceeds* the marked point, so the left-side
>   requirement there is **at most 4**. That rules out a width of **≥5 for that instance only**; it
>   does **not** distinguish 2, 3 and 4, all of which remain admissible. Three of the four measured
>   right-side counts are floors rather than true counts, because the chart's live edge truncates
>   them. Net effect: the default does not move, and the sweep narrows from an open range to
>   **2–4** — recorded as `sweep_bracket` on the key.
> * **Q13 — sufficient gap on 2H, 4H, 8H and 12H.** Nothing is given for any of the four, which are
>   precisely the timeframes he trades most. Worse, the rows cannot be interpolated: his 1H→1D and
>   1D→2D slopes disagree by a factor of three, so no exponent fits both. The values stand and stay
>   labelled **[OUR CHOICE]**.
>
> Six further items are answered but rest on `absent` sub-parts that a sweep, not the trader, should
> settle: the touch-decay *curve* (Q2), the TP split for n≥4 (Q4), the confluence *weights* (Q5), the
> MSB retest timeout (Q11 — he refuses to bound it) and the mid-range *band width* (Q12 — he gates on
> a state, not a distance).

1. ~~**Zone invalidation — 50% or 70–80%, and measured how?**~~ — **ANSWERED (Q1, `stated`):** (c). Zones 50 % of depth, order blocks ~75 % of liquidity taken, wick test. See CF-08.
   You say a zone is dead once ~50% of it fills (S5/S6), but you also say your order-block rule is
   "around 70 to 80%" of liquidity taken (S7), and elsewhere that a 50%-filled order block is still
   playable. Which is it — (a) 50% of zone depth, (b) 70–80% of zone depth, or (c) 50% for
   supply/demand zones and 70–80% for single-candle order blocks? And is the level breached by any
   **wick** through it, or does it need a candle **close** beyond it?

2. ~~**Third-touch rule vs replaying a zone.**~~ — **ANSWERED (Q2, `stated`/`derived`):** (a)+(b), scoped by object class; the veto is at the 4th touch, and the only indexed size cut he gives is the 5th. The multipliers remain `absent`. See CF-07.
   You say don't take the same level after its third touch, but you also say you'll replay a demand
   zone as many times as you like until 50% fills, and you count seven bounces approvingly. Is the
   third-touch rule (a) only for bare support/resistance lines, with zones governed purely by the 50%
   rule, (b) a size reduction rather than a veto, or (c) a hard veto everywhere? If it's a size
   reduction, what size at touches 3, 4 and 5?

3. ~~**DCA size split.**~~ — **ANSWERED (Q3, `derived`):** 39/61 and 20/30/50, solved off his own worked LINK ladder. See CF-18.
   You always say "light at entry, heavier at the DCA", but never a ratio. For a two-leg entry, is it
   30/70, 25/75, or something else? For three legs — 20/30/50? The blended average is the whole point
   of the ladder, so this number decides break-even, every TP-trail decision and the position size.

4. ~~**What fraction comes off at each TP?**~~ — **ANSWERED (Q4, `stated`):** yes, 50/50 and 40/30/30, given as an answer to a direct question. n≥4 is `absent`. See CF-28.
   The only split you've given is 50/50 for two TPs and 40/30/30 for three (S4). Is that still what
   you run? And when you place TPs at whatever structural levels happen to exist, rather than a fixed
   two or three, how does the split adapt?

5. ~~**Minimum confluence count, and how to count overlaps.**~~ — **ANSWERED (Q5, `derived`):** three, counted as raw objects; cross-class stacks count separately; an OB inside a zone does not. See CF-31.
   You say "I need confluence" and refuse order-block-only, fib-only, pattern-only, trendline-only and
   SFP-only trades — but never a number. Is three the floor? And when an SR point, a supply zone and
   an order block all sit at the same price, is that three confluences or one?

6. **Swing high / swing low detection.** — **STILL OPEN for the candle count (Q6(a), `absent`).** The price source *is* answered (`stated`: bodies for structure, wicks for the SFP raid level and stop) and "directional change" now runs off his sufficient-gap table (`inferred`). The N-bar width is not in the corpus at all.
   Every structure rule, every SFP, every fib anchor and every order block depends on "a swing point"
   and "a directional change in price", and neither is ever defined. How many candles either side must
   a high be the highest of before you'd call it a swing high — 3? 5? — and how big does a move have to
   be before you'd call it a directional change: a fixed percentage, an ATR multiple, or a break of the
   prior swing?

7. ~~**Which timeframe governs?**~~ — **ANSWERED (Q7, `stated`/`inferred`):** higher timeframe always wins, stated verbatim; the SFP is judged on the highest timeframe that validates it. See CF-20, CF-24.
   For a trade you're placing on the 1H: which timeframe do you read trend and market structure on,
   which one has to confirm the MSB close, and which one decides whether an SFP is valid? (The same
   sweep was a valid daily SFP and an invalid 12H SFP in S8 and you didn't say which wins.)

8. ~~**Normal leverage position size.**~~ — **ANSWERED (Q8, `derived`):** the percentages are MARGIN. Notional is derived from risk and lands at 73–154 % of equity in his own worked example. This was a live defect. See CF-02.
   S3 says a normal position is 20% of portfolio, S7 says 10%, and spot is 6–12%. For a leverage swing
   with a 4–5% max loss, what's the notional and what leverage are you using to get there?

9. ~~**Counter-trend: cancel it, or halve it?**~~ — **ANSWERED (Q9, `stated`):** both, and they are different situations — cancel an *armed* setup whose trend flipped; halve a *deliberate* new counter-trend entry, always demoted to a scalp. See CF-03.
   In S7 you say you'd have cancelled a bullish setup once the trend flipped to lower highs; a minute
   later you say it's fine to play against the trend at half size. Which one does the bot do — hard
   veto, or 0.5× size with a 2–3% loss cap? And does a counter-trend trade always have to be demoted
   to a scalp on a lower timeframe?

10. ~~**Resting limits at the SR point vs waiting for the flip.**~~ — **ANSWERED (Q10, `stated`):** yes, exactly that difference. Plus one intermediate state CF-16 missed, now `presr_light_limit_enabled`. See CF-16.
    S4 says explicitly: do not put a limit at the line waiting for the flip, wait for breakout + retest
    + hold, then enter. Everywhere else you say "I always enter my positions at SR points and DCA
    lower", which is a resting limit. Is the difference that S4 is talking about a level that hasn't
    flipped yet, and the SR-point entries are on levels that already have?

11. ~~**Where does the entry go after a structure break?**~~ — **ANSWERED (Q11, `derived`):** one entry described three times at increasing strictness. The wait is unbounded by design; the invalidation is a deviation close. See CF-22.
    S7 says short the retest of the broken higher low; S8 says don't short the close, wait for the next
    lower high; S3 says don't act until a lower high has actually formed. Are those three the same
    thing said differently, or three different entries? And how many candles do you wait for that
    retest before you abandon the setup?

12. ~~**Mid-range as a band.**~~ — **PART-ANSWERED (Q12):** the *level* is `stated` — the S/R level, not the geometric 50 % — and the geometric alternative is struck. The *band width* is `absent`, and he gates on a state ("consolidating"), not a distance. See CF-26, CF-25.
    "No trades at mid-range" only works if mid-range has a width. How far either side of the mid-range
    line is the no-trade zone — 10% of the range height? 15%? And is mid-range the geometric 50% or the
    nearest S/R level to it?

13. **Sufficient gap for 2H, 4H, 8H and 12H.** — **STILL OPEN (Q13, `absent`).** Nothing for any of the four. One side-finding: the **30m row was wrong** and is corrected 3.5 → 4.0 (`stated`, S5 `[00:54:07]`).
    You gave numbers for 15m, 30m, 1H, daily and 2-day, but not for the timeframes you actually trade
    most. What's the minimum move away from a zone on the 4H and the 12H?

14. ~~**Are the pattern, trend-line and scalp modules meant to ship at all?**~~ — **ANSWERED (Q14):** patterns confluence-only (`stated`), trend-line breakdown off (`stated` disavowal), scalp **on** with a 30m floor (`inferred`, reverses CF-37). See CF-37.
    You taught a full pattern library (S4), a full trend-line breakdown method (S8) and a full scalping
    session (S8), and said in each case that you don't trade them yourself. Should the bot run those as
    live strategies, or only use the patterns as extra confluence on your S/R and zone setups?

15. ~~**Golden pocket: 0.66 or 0.65 — and is "golden pocket" ever the 0.786?**~~ — **ANSWERED (Q15, `stated`):** all three confirmed, and the "interchangeable" premise is an ASR artefact that does not survive the tape. See CF-33.
    S6 says 0.618–0.66 and notes others use 0.65. In S8 you use "golden pocket" and "0.786"
    interchangeably. Confirm: golden pocket = 0.618–0.66, entry level; 0.786 = separate, DCA level. And
    do you want 0.886 in the set given you said you hadn't back-tested it?

---

# § Undefined primitives

Everything below is depended on by rules across every session and is defined by nobody. Each entry
gives a concrete, standard algorithm with parameters. **These are OUR choices, not his** — they are
the first things to sweep in a backtest and the first things to correct if he answers the questions
above.

**P1 — Swing point (pivot) detection.**
Fractal pivot: a swing high at bar *i* is a bar whose **body high** (max(open, close)) is the highest
of the window [i−k, i+k]; mirror for swing lows. `swing_k = 3` on the structure timeframe (5 for
weekly/monthly). Ties broken toward the earlier bar. Bodies, not wicks, per S7-R11 and S5-R44.
A pivot is confirmed only after k bars have closed — no repainting.
Params: `swing_k = 3` (alt 2, 5), `swing_price_source = "body"`. **F4 sweep bracket: 2–4** — the
S7 34:30 frame caps the left-side width at 4 at that one point, so candidates ≥5 can be dropped.

**P2 — "Directional change in price" (for order blocks).**
A directional change at bar *j* exists when price moves ≥ `dir_change_atr × ATR(14)` away from bar
*j*'s close within `dir_change_max_bars`, without first retracing more than 33% of that move. The
order block is then the last opposite-colour candle at or before *j*.
Params: `dir_change_atr = 2.0` (alt 1.5, 3.0), `dir_change_max_bars = 10`.

**P3 — Horizontal level construction and clustering.**
Candidate levels = all confirmed P1 pivots on the structure timeframe over `level_lookback_bars`
(default 500). Cluster candidates whose prices are within `level_cluster_atr × ATR(14)`
(default 0.25). A cluster becomes a **level** at `level_min_touches` (default 2, per S4-R4 and S7's
"two touches is enough to call an SR point"). The level's price is the volume-weighted mean of its
member pivots — this is the machine version of "points of most touch". Levels are re-clustered on
every new confirmed pivot, never on intrabar data.
Params: `level_lookback_bars = 500`, `level_cluster_atr = 0.25`, `level_min_touches = 2`.

**P4 — Touch definition and counting.**
A **touch** occurs when a bar's range intersects the level's tolerance band
(`level_tolerance_atr × ATR(14)`, default 0.15) **and** the bar closes on the level's original side.
Consecutive bars inside the band count as **one** touch; the counter increments again only after
price has left the band by ≥ `touch_reset_atr` (default 0.5 ATR) and returned. A body close through
the level ends the touch sequence and starts the flip state machine (CF-15) instead. Touch counters
reset when the level flips role or when the level's cluster is rebuilt.
Params: `level_tolerance_atr = 0.15`, `touch_reset_atr = 0.5`.

**P5 — Zone box boundaries.**
For a consolidation of N ≥ 2 candles (S5-R17): the box top = highest body top; box bottom = lowest
body bottom. Extend to a wick only if the wick's length ≤ `wick_include_max_pct` of price (2.0%,
S7-R7) **and** ≤ 0.5 × ATR(14). Otherwise the wick is excluded. For a single-candle order block, the
box is that candle's body under the same wick test.
Params: `wick_include_max_pct = 2.0`, `wick_include_max_atr = 0.5`.

**P6 — 50% fill measurement.**
Zone midpoint = (box_top + box_bottom) / 2, computed once when the zone is created and never
re-measured. Fill occurs when any bar's **wick** trades through the midpoint (conservative: kills the
zone earlier than a close-based test). Alternative `close_beyond` available for sweeping.
Params: `zone_fill_measure = "wick_touch"`, `zone_fill_reference = "as_originally_drawn"`.

**P7 — Mid-range.**
Geometric mid = (range_high + range_low) / 2. Search for the highest-touch-count P3 level within
±`mid_range_search_pct` (10%) of range height around geometric mid; if one exists, that level is
mid-range, else geometric mid is used. The no-trade band is ±`mid_range_band_pct` (15%) of range
height around it.
Params: `mid_range_search_pct = 10.0`, `mid_range_band_pct = 15.0`.

**P8 — Range detection and staleness.**
A range exists when, over a window of ≥ `range_min_bars` (default 20) on the structure timeframe,
price has produced ≥2 touches of an upper level and ≥2 of a lower level (P3/P4), the two levels are
≥ `range_min_height_atr` (3.0) apart, and no body close has occurred beyond either level. The range
dies per CF-26. A range older than `range_max_age_bars` (300) with no touch in
`range_stale_bars` (60) is retired. Nested ranges: the one on the highest timeframe wins (S7-R20).
Params: `range_min_bars = 20`, `range_min_height_atr = 3.0`, `range_max_age_bars = 300`, `range_stale_bars = 60`.

**P9 — "At the level" / retest tolerance.**
Identical band to P4: `level_tolerance_atr × ATR(14)`, default 0.15. Used for retest detection,
limit-order placement offsets, and "price is at range lows/highs". Limit orders are placed at the
level price itself, not at the band edge.

**P10 — Sufficient-gap anchor and measurement.**
Measured from the **breakout candle's close** to the **extreme** (high for up-moves, low for
down-moves) reached before price retraces more than 50% of that excursion, expressed as a percentage
of the breakout close, and also in ATR (CF-11). This is the reading most consistent with his
"move away from this breakout point" phrasing; S5-A1 confirms he never says.
Params: `sufficient_gap_anchor = "breakout_close_to_extreme"`, `sufficient_gap_retrace_cutoff = 0.5`.

**P11 — Trend / regime classification.**
On the structure timeframe, over the last `trend_pivot_count` (default 4) confirmed P1 pivots:
uptrend = the last two swing highs and last two swing lows are each higher than their predecessors;
downtrend = the mirror; anything else = **range/neutral**. Neutral counts as "not counter-trend" for
CF-03 (a counter-trend penalty only applies against a *confirmed* opposing trend).
Params: `trend_pivot_count = 4`, `trend_timeframe` = structure TF.

**P12 — Capitulation wick.**
A bar whose wick (in the direction of the flush) is ≥ `capitulation_wick_atr` × ATR(14)
(default 3.0) **and** ≥ `capitulation_wick_body_ratio` × its own body (default 3.0), and whose volume
is ≥ `capitulation_volume_mult` × the 20-bar median (default 2.0). Capitulation wicks are excluded as
stop anchors (TBOT1-R6) and are permitted as entry targets (TBOT1-R22) — which is exactly the
distinction TBOT1-C4 leaves unresolved.
Params: `capitulation_wick_atr = 3.0`, `capitulation_wick_body_ratio = 3.0`, `capitulation_volume_mult = 2.0`.

**P13 — "Consolidates horizontally".**
Over the consolidation window: the linear-regression slope of closes, expressed as total drift across
the window, must be ≤ `consolidation_max_drift_atr` (default 0.75 ATR), **and** the window's
high-to-low height must be ≤ `consolidation_max_height_atr` (default 2.0 ATR). This rejects the
downward-drifting consolidations he rejects by eye (S5-R15, S5-A5, S6-A27).
Params: `consolidation_max_drift_atr = 0.75`, `consolidation_max_height_atr = 2.0`, `consolidation_min_bars = 2` (S5-R17).

**P14 — Confluence scoring and deduplication.**
Collect all objects whose price is within `confluence_merge_atr` (0.25 ATR) of the candidate entry
price. Score = Σ weights (CF-31). Within a single class, only the highest-weighted object counts.
Across classes, all count. Cross-market gates (BTC.D/USDT.D/BTC pair/beta parent) are **vetoes**, not
score contributors (TBOT1 §10). Trade requires score ≥ `min_confluence_count` and ≥2 distinct classes.

**P15 — "Liquidity taken" from an order block (for the S7 threshold, if enabled).**
Percentage of the OB candle's body range that price has traded through since the OB formed, measured
from the OB's outer edge inward using the deepest **wick** penetration. Only used when
`zone_fill_invalidation_pct` is set to the S7 values.
Params: `ob_liquidity_measure = "deepest_wick_through_body_range"`.

**P16 — Session and day boundary.**
`day_boundary_utc = "00:00"` (CF-45). Daily candles, the Monday range (S5-R8), the two-loss daily
counter (S2-R21) and the challenge-account period all key off this. Week boundary = Monday 00:00 UTC.
Weekend = Saturday 00:00 UTC through Monday 00:00 UTC.

**P17 — "Immediate reaction" / stale trade.**
No reaction = after `stale_exit_bars` (8) bars in trade, price has not reached
`reaction_threshold_atr` (0.75 ATR) in favour of the position and MAE ≥ `stale_exit_mae_atr` (1.0
ATR). Off by default (CF-30) because no number exists anywhere for it.

**P18 — Illiquidity / "barcoding" / wick-heavy screen.**
A symbol fails the screen if any of: 30-day median USD volume < `min_daily_volume_usd`; median
(wick length / candle range) over the last 200 bars on the trade timeframe >
`max_median_wick_ratio` (default 0.55); or the fraction of bars whose total wick exceeds 2× the body
is > `max_wicky_bar_fraction` (default 0.40). Failing symbols are demoted to spot-only (CF-40), not
excluded outright — that reproduces his actual behaviour (S6-R45, S7-R38).
Params: `max_median_wick_ratio = 0.55`, `max_wicky_bar_fraction = 0.40`.

**P19 — Stop buffer.**
`stop_buffer_atr × ATR(14)` beyond the chosen anchor (CF-14), default 0.15 ATR. He never gives one;
his own worked example was "almost got wicked", which implies something small, so 0.15 is the
conservative reading of "small" rather than a number he supplied.

**P20 — "Points of most touch" (entry price inside a zone).**
Within the zone box, bin prices at `pmt_bin_atr` (0.05 ATR) resolution over the zone's formation
window plus all subsequent touches; the entry price is the bin with the highest count of bar
intersections, breaking ties toward the price nearest the zone's outer edge (which is where his
"lightest entry at the SR point" sits). This is the machine version of S4-R4, S5-R23 and S5-A15.
Params: `pmt_bin_atr = 0.05`.

---

# Discord written-record pass — 2026-09-14

Source: the instructor's own Discord server (Pepe Academy). Seven `#class-session-*` note
channels read verbatim, plus the risk-management Google Doc he links in session one, plus
server-wide `from:arshmeister` searches. This is his **written** record, distinct from the
video transcripts in `transcripts/`.

**Standing finding that shapes everything below.** The written corpus is a *definitions*
layer. He states a rule and defers every magnitude to class. Across seven sessions it
yields exactly four numbers: three trendline touches, 50% zone fill, 48–72h, and the
golden pocket. Where a written source and a transcript disagree on a **definition**, the
written source wins. Where a **number** exists only in a transcript, it stays — there is
no written alternative.

## CF-46 — DCA ladder: the percentages are stated, the basis is not  **UNRESOLVED**

`dca_size_split_3` corrected to **[0.15, 0.325, 0.525]** — the midpoint of his stated
15 / 30-35 / 50-55, written three times (`#class-session-one` M2, `#class-session-five` M8,
and the risk doc). Supersedes the derived `[0.2, 0.3, 0.5]`.

What is *not* settled is whether those percentages apply to **capital** or to **quantity**.
His prose says "15% of my allowed capital". His only worked example (DOT) was typed into a
contracts-based calculator:

```
20 @ 29.23 + 50 @ 28.48 + 150 @ 27.93  =  220 units at 28.1732   (exact)
```

That example **cannot** settle the basis: its prices span only 4.45%, so capital- and
quantity-weighting land within 0.6 points of each other. It also runs a 9/23/68 ladder,
not his stated one — read as round teaching numbers, not an execution.

Needs a ladder with prices far enough apart to separate the two. Until then `plan.py`
keeps its current basis and this stays open.

## CF-47 — "entries are valid once" vs the re-entry mechanism  **UNRESOLVED**

Risk doc: *"My entries are valid once unless otherwise stated. If you miss the play, move
on. Once a trade hits a TP, the trade becomes immediately invalid."*

Against `reentry_trigger = sfp_or_close_reclaim` (CF-21, S2-R13, S6-R24) and
`reentry_max_attempts_per_level = 2` (OUR number).

**Not treated as a correction.** The passage sits in a document addressed to subscribers
about acting on *his posted calls*, and reads as "don't chase a call you missed" rather
than as a mechanical re-entry rule. The transcripts independently describe a re-entry
trigger. Both keys unchanged; recorded so the next session does not read the doc as
settling it.

## CF-48 — BVOL24H is a dead instrument  **BLOCKING, needs a decision**

`BVOL24H` does not resolve on TradingView (checked 2026-09-14, every asset class). The
one `BVOL` hit is an unrelated Gate perpetual on a DeFi token and must not be substituted.

`regime.py` degrades gracefully, so the bot runs. The consequence is quieter and worse:
`bvol_event` can never fire, so `bvol_size_multiplier = 0.5` never halves leverage. The
bot permanently runs without a size reduction it believes it has.

`METHOD.md` calls this "the layer to build first". It is pointing at a feed that does not
exist. Either substitute a live volatility source (DVOL, or realised vol from our own
candles) or remove the three keys. Not a config edit.

Also from `#class-session-three`: the zone coordinates are **explicitly perishable** —
"currently 0.8-1.71... it can change. This all depends of liquidity in the market." The
shipped `[0.81, 1.4]` differs from the written figure, but neither should be hardcoded.

## CF-49 — a 50%-filled zone is DEMOTED, not killed  **NOT YET IMPLEMENTED**

`#class-session-five` M5: *"You can continue to play that area if 50% fills but its no
longer a zone confluence, **its just support**."*

`primitives.py:708` sets `is_dead = fill_pct >= zone_fill_invalidation_pct`, and
`manage.py:590` treats that as terminal. One boolean where he has two states. Every
post-fill setup he would still take as a plain support level is currently discarded.

He also applies the threshold loosely — M7, *"we filled close to 50% so we will call this
a 50% fill"* — so the exact number matters less than the missing demoted state.

## CF-50 — the half-candle rule  **NOT YET IMPLEMENTED**

`min_zone_bodies = 2` counts whole bodies. `#class-session-five` M6: *"2 halves make one
whole. Meaning, if you ever get a zone with 1 whole candle and 2 halves, that is a valid
zone."* His own PEPE example is 3½ candles. A whole-body count rejects a zone he accepts.

## CF-51 — "not ever alone"  **NOT YET IMPLEMENTED**

`#class-session-five` M5 rule 2: *"You set these zones with confluence of support and
resistance, **not ever alone**."* Restated for trendlines in `#class-session-seven`.

`min_confluence_count = 3` is a raw object count — three of anything passes. He requires
an S/R specifically. Different rule, and stricter.

## CF-52 — funding-rate filter  **DOES NOT EXIST IN THE BOT**

Risk doc: `0.01` neutral, `+0.75` high, `-0.75` low. *"When a funding fee is high
(positive) chances for a sell off is super high and I recommend not longing or having a
tight stop loss."* Zero config keys. Funding rates come off the same public endpoints the
dashboard already uses.

## CF-53 — no averaging up without a flip  **DOES NOT EXIST IN THE BOT**

Risk doc: *"DO NOT average up on longs UNLESS a previous resistance is turned to support.
Only time you should add size."* Mirrored for shorts.

## Corroborated, no change

| Claim | Source | Status |
|---|---|---|
| Position size 6–12% of port, futures = 10% of total, 10x | risk doc | **Resolves CONFLICTS #1**, the project's longest-standing blocker. `margin_pct_leverage = 10.0` sits inside his stated band. |
| Never more than 2 concurrent positions | risk doc | Conflicts with `max_concurrent_leverage_global = 4`. His reason is mechanical: four positions leave no margin to fund the DCA legs. |
| Stop to BE at TP1, to TP1 at TP2 | session one + risk doc | **Resolves CONFLICTS #4** — third independent statement, backs the Session 4 version. |
| TP splits 40/30/30 | session one + risk doc | `tp_split_3` already exact. `tp_count_swing` corrected 2 → 3. |
| Swing ≥ 4H, scalp < 4H | session one | `swing_tf_floor = 4H` exact. |
| Max loss 5% swing, 2–3% scalp | session one | `max_loss_pct_swing_hard_cap = 5.0`, `max_loss_pct_scalp = 2.5`. Exact. |
| Zones are bodies | session five | Confirmed. **But S/R levels use "whatever the highest touch points are (wicks vs bodies)"** — a different rule for a different object. Check `detectors/levels.py`. |
| Trendline valid at 3 touches | session seven | `trendlines.py` already requires ≥ 3. |
| Order block = last opposing candle before the directional change | session six | Matches. No mitigation, imbalance or displacement requirement stated. |
| No DCA on breakout entries | session seven | `dca_count_breakdown = 0` already. |
| Golden pocket 0.618–0.66 | session six | Exact. The 0.786 half is absent from writing, not contradicted. |
| Zone detection: impulse → consolidation → continuation + timeframe-scaled gap | session five M1/M3 | **Kills the archive's "zone DETECTION is not specified anywhere" claim.** Matches `detectors/zones.py`. |
