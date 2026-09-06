# Chart-frame readings — visual evidence pass

Source: paused frames from S5/S6/S7 (TradingView screen capture, "ARSHMEISTER | BloFin | MEXC").
Read at 1080p. Method: seek to timestamp, pause, hide player chrome, screenshot, measure.

This file records what the *pictures* show, as distinct from what the transcripts record him
*saying*. Where the two disagree, that is flagged explicitly.

---

## F1 — Zone geometry: he draws TWO nested boxes, not one  **[NEW — not in any transcript]**

**S6 52:38, LINK 1D, labelled "Bullish OB":**

- Inner (darker) box: top edge to **body** lows.
- Outer (lighter) box: same top edge, extended down to the **wick** lows.
- Wick band ≈ **83%** of the inner body-box height.
- The body box is ≈55% of the full body+wick extent.

Corroborating frames (single-box, body-anchored, with wick left outside):

| Frame | Chart | Anchor | Upper wick excluded | Lower wick excluded |
|---|---|---|---|---|
| S5 1:30:30 | BONK 12H | bodies | ~45% typical, ~90% max | ~50–65% typical, ~110% max |
| S5 1:24:41 box A | ZEC 1D | bodies | ~25% | ~60% |
| S5 1:24:41 box B | ZEC 1D | bodies | ~10% | ~35% |

**Why it matters.** The bot currently models a zone as one box on candle bodies. The frames say
the body box is the *core* and the wick extent is a second, outer band he draws deliberately.
That reconciles two things the transcripts left in tension: "draw your boxes on candle bodies"
(S5, S6) versus "usually wicks are going to give you that entry point" (S5 `[01:05:00]`).

Reading: **body box = where the entries go; wick band = where the stop goes.**

**Status: NOT implemented as default.** One clear frame is not enough to restructure zone
detection. Shipped behind `zone_wick_band_enabled` (default `false`). Needs 3–5 more frames of
him drawing a zone before it becomes the default geometry.

---

## F2 — DCA split: independently corroborated  **[CONFIRMS a derived value]**

**S6 9:40–10:53, ORDI 1D**, two entry lines and an average-cost calculator:

```
  15 units @ $35.51        <- lighter leg
  25 units @ $40.11        <- heavier leg
  average cost for 40 units = $38.385
```

15 / 40 = **37.5%**, 25 / 40 = **62.5%**.

The bot's `dca_size_split_2` is **[0.39, 0.61]**, derived independently from his LINK ladder on
S6 `[00:48:10]`. Two unrelated worked examples landing within 1.5 points of each other is the
strongest confirmation any parameter in this project has.

Second pass at 11:27 (mid-edit, he reworks it): 7 @ 35.51 and 15 @ 40.11 = 22 units → 31.8% /
68.2%. So the observed range across three examples is **32–39% on the first leg**.

**Action:** default unchanged at 39/61. Sweep bracket recorded as 0.32–0.40.

---

## F3 — He does not use a position-size tool  **[method correction]**

No TradingView position-size tool in any frame. The on-chart position tool has its stats labels
turned off. What he actually uses:

1. A web average-cost calculator (coinguides.org) for the blended entry.
2. The Windows calculator for the loss figure — visible: `2.85 × 23 = 65.55`.

`2.85` is consistent with the distance from the $38.385 average entry down to the $35.51 leg, but
he never labels it as a stop. Read as inferred arithmetic, not a stated risk figure.

**Never visible in any frame:** account size, leverage, position value, a labelled stop.

**Consequence:** the margin-vs-notional fix (Q8) still rests entirely on the *spoken* worked
example in S6 `[00:08:36]`–`[00:11:27]`, not on anything visible. It is not contradicted by the
frames, but it is not corroborated by them either.

---

## F4 — Swing width: still open, but bounded  **[partial]**

Four of seven requested frames were unusable — he is sketching freehand over a blank chart, or the
chart is in line mode, so there are no candles to count.

| Frame | Chart | Marked point | Left | Right | Quality |
|---|---|---|---|---|---|
| S7 34:30 | 4H | swing high (arrow tip) | **4** | 21 | confident |
| S7 30:19 | 4H | swing high (blue arc) | ≥20 | 4 | truncated at live edge |
| S7 33:48 | 3D | swing low (fib anchor) | ≥15 | 6 | truncated, heavy overdraw |
| S7 34:30 | 4H | swing low (blue arc) | ≥20 | 8 | truncated at live edge |

The binding reading is the 34:30 swing high: the **5th** candle to its left exceeds it, so the
left-side requirement there is **at most 4**.

**What this does and does not establish.** It rules out a width of 5 or more for that instance. It
does not distinguish 2, 3 or 4 — all remain admissible. Three of the four right-side counts are
floors, not true counts, because the chart's live edge cuts them off.

**Action:** `swing_k` stays at 3 and stays `[OUR CHOICE]`. The sweep bracket narrows from an open
range to **2–4**, which is a materially cheaper sweep. Any candidate ≥5 can be dropped.

---

## F5 — Sufficient gap by timeframe: confirmed absent  **[negative result]**

Every genuine measure-tool reading in the frames sits on **1H or 30m**. There is no percentage
readout on any 2H, 4H, 8H or 12H chart.

| Frame | Chart | Reading | Note |
|---|---|---|---|
| S5 36:05 | 1H | 8.10% | **measured across his hand-drawn illustration, not candles — do not treat as a threshold** |
| S5 51:25 | 1H | 4.48% | real candles |
| S5 55:51 | 30m | 0.51% | real candles; subject unknown, do not read as a threshold |
| S6 52:38 | 1D | −4.19% | real candles |
| S5 1:00:22 | 2H | none | drawing a rectangle, not measuring |
| S5 1:30:30 | 12H | −2.58% | legend bar-change, i.e. that candle's own move — not a measure |

**The trap this avoids:** the 8.10% at 36:05 sits on a 1H chart and looks like a clean threshold
reading. It is drawn over a sketch. Anything that scraped percentages mechanically would have
recorded it as evidence for a 1H rule.

**Action:** `sufficient_gap_pct_by_tf` rows for 2H/4H/8H/12H remain **[OUR CHOICE]**. Backtest
sweep is the only remaining route.

---

## Summary

| # | Question | Outcome |
|---|---|---|
| F1 | Zone geometry | **New finding** — nested body box + wick band. Behind a flag pending more frames. |
| F2 | DCA split | **Corroborated** independently. Confidence upgraded. |
| F3 | Sizing method | **Corrected** — no position tool; average-cost calculator plus Windows calc. |
| F4 | Swing width | **Bounded** — ≤4 at the one readable point. Sweep narrowed to 2–4. |
| F5 | Gap % by timeframe | **Confirmed absent.** Not recoverable from video. Sweep only. |

Two of five closed or advanced, one new structural finding, one negative result that saves effort,
and one near-miss trap avoided. The frames were worth pulling.

---

## Applied to the bot

Everything below is implemented and under test. **No default changed.** F1 is the only code-path
addition and it ships behind a flag that is off.

### New config keys (2) — `bot/tbot/config.py`

| Key | Type | Default | Source | Sweep bracket |
|---|---|---|---|---|
| `zone_wick_band_enabled` | bool | **`false`** | F1, S6 frame 52:38 — single-frame observation, needs corroboration | — |
| `zone_wick_band_max_ratio` | float | `1.0` | F1, same frame; measured example 83 % | 0.83–1.0 |

`KeySpec` gained a machine-readable `sweep_bracket` field so a parameter sweep reads its search
range off the config rather than out of prose. Brackets recorded: `dca_size_split_2` **0.32–0.40**
(F2), `swing_k` **2–4** (F4), `zone_wick_band_max_ratio` **0.83–1.0** (F1).
`sufficient_gap_pct_by_tf` deliberately carries **none** — F5 is a negative result and no bracket is
derivable.

### Behaviour when `zone_wick_band_enabled` is true

`Zone` carries both extents: `box_top`/`box_bottom` stay the **body core**, `wick_band_top`/
`wick_band_bottom` hold the **outer band** (sharing the core's near edge, extended past its far edge
to the wick extreme, capped at `zone_wick_band_max_ratio` × the core height — past the cap the wick
is an outlier and is excluded). Entries price off the body box exactly as before; CF-14 pushes the
stop **beyond the band**, widening only, never tightening. The band applies before the
`stop_never_beyond_opposing_level` clip and does not survive the CF-06 LTF tightening.

With the flag off — the default — no zone carries a band, the band edge is `None`, and every number
the detector and the plan builder produce is byte-identical to the single-box model. There are
tests that assert exactly that, in both places.

### Files changed

| File | Why |
|---|---|
| `bot/tbot/config.py` | F1's 2 new keys; `KeySpec.sweep_bracket`; F2/F4/F5 notes rewritten on `dca_size_split_2`, `swing_k`, `sufficient_gap_pct_by_tf` |
| `bot/tbot/models.py` | `Zone.wick_band_top` / `wick_band_bottom` and the `has_wick_band` / `wick_band_stop_edge` / `wick_band_depth` accessors |
| `bot/tbot/detectors/zones.py` | `wick_band()` — the F1 geometry, the ratio outlier rule, and the `F1` source id on banded zones |
| `bot/tbot/plan.py` | `place_stop(wick_band_edge=…)`; `build_plan` reads `Zone.wick_band_stop_edge` |
| `bot/tbot/dashboard/serialize.py` | the band is serialised so it is visible on the chart when on |
| `bot/tbot/dashboard/settings.py` | both keys added to the live-tunable list |
| `bot/configs/default.yaml` | regenerated — 244 keys, each with its source id and any sweep bracket |
| `bot/tbot/INTERFACES.md` | §7 ownership table: 2 new rows; key count 242 → 244 |
| `SPEC.md` | §2.4 Zone fields, P5, §5.5 (F1 geometry + F5 note), §8.5 (F1 stop step), §8.8 (F3 method correction), §8.9 scope table, §11.2 / §11.3 / §11.4, §11.13, §13, §14 |
| `CONFLICTS.md` | new F1–F5 status section; addenda on CF-02 (F3), CF-11 (F5), CF-13 (F1), CF-14 (F1), CF-18 (F2); Q6(a) and P1 narrowed by F4 |

### Not acted on

* **The three single-box corroborating frames** (S5 1:30:30 BONK 12H, S5 1:24:41 ZEC boxes A and B).
  Their excluded-wick percentages are wide ranges read off a chart — "~45 % typical, ~90 % max" —
  and they show only the inner box, so they support the *existing* body-anchoring rule rather than
  bounding `zone_wick_band_max_ratio`. They are cited as context, not turned into a threshold.
* **"The body box is ≈55 % of the full body+wick extent" (F1).** A restatement of the 83 % ratio on
  a different denominator, from the same single frame. One derived key per observation.
* **The `2.85 × 23 = 65.55` Windows-calculator reading (F3).** He never labels the 2.85 as a stop
  distance; it is consistent with one, which is not the same thing. Recorded in the docs as inferred
  arithmetic, not wired to any key.
* **The three real-candle percentage readings of F5** (4.48 % on 1H, 0.51 % on 30m, −4.19 % on 1D).
  Each is a measurement with an unknown subject — none is labelled as a threshold, and the 1H and 1D
  rows they would touch are already `stated`. The 8.10 % is recorded only as a trap to avoid.
* **The F4 right-side counts.** Three of four are floors truncated by the chart's live edge, so they
  bound nothing.

---
---

# Pass 2 — a second frame batch

Same method, a second batch of paused frames, chosen to attack the two things pass 1 left open:
where exactly the stop goes, and whether the F1 two-box zone is really his convention.

Naming: pass 1 used **F1–F5**. Pass 2 continues the numbering — **F6** stop distance, **F7** entry
placement, **F8** confluence count — and re-opens **F1**. Frames are cited `Sn mm:ss` /
`TBOT1 mm:ss`, distinct from the `[hh:mm:ss]` transcript timestamps.

| # | Question | Outcome |
|---|---|---|
| F6 | Stop distance | **Default changed, and the parameterisation with it.** Three frames. |
| F1 | Zone geometry | **Weakened.** Flag stays off; its ratio is not a trustworthy number. |
| F7 | Entry placement | **Corroborates existing behaviour.** No change. |
| F8 | Confluence count | **Weak support** for `min_confluence_count = 3`. No change. |

---

## F6 — The stop sits half a zone-height below the zone  **[DEFAULT CHANGED]**

Three independent frames, different pairs, different timeframes, different exchanges, each with a
position tool and a zone box on screen:

| Frame | Chart | Stop below zone bottom, as a fraction of zone height | Same, as % of entry |
|---|---|---|---|
| TBOT1 4:11 | BTCUSDT.P 1H Binance | **0.48** | 0.66 % |
| TBOT1 1:09:19 | OMUSDT.P 1H Binance | **0.49** | 2.70 % |
| S8 1:28:33 | SOLUSDT.P 4H MEXC | **0.58** | 0.81 % |

The fraction clusters tightly: 0.48–0.58, mean ≈ **0.52**. The price percentage does not:
0.66–2.70 %, a factor of four. No ATR multiple is readable on any frame.

**So the stable rule is fraction-of-zone-height** — not a price percentage, and not an ATR
multiple. That matters more than the number: the bot's `stop_buffer_atr = 0.15` was an
**[OUR CHOICE]** invention with no evidential standing at all, and it was the wrong *shape* of
parameter for a stop that hangs off a zone. Three agreeing frames beat an invention.

### What shipped

| Key | Type | Default | Sweep | Source |
|---|---|---|---|---|
| `stop_buffer_zone_fraction` | float | **0.5** | 0.45–0.60 | **F6** — TBOT1 4:11, TBOT1 1:09:19, S8 1:28:33 |

- A stop **anchored to a zone** is placed `stop_buffer_zone_fraction × zone height` beyond the
  box's far edge (`Zone.body_stop_edge`: `box_bottom` for demand, `box_top` for supply).
- `stop_buffer_atr` (0.15) **stays**, as the fallback for stops that are *not* zone-anchored —
  levels, SFPs, structure breaks — and for the CF-06 step-1 LTF re-anchor, where the higher-
  timeframe zone does not exist. Its `note` and every doc row now say so.
- **Precedence preserved.** `stop_never_beyond_opposing_level` still clips the F6 stop; the
  `min_stop_pct` floor still widens it; the CF-06 wide-stop ladder (tighten → downgrade → skip)
  still runs afterwards. The clip's "just inside" nudge and the F1 band push keep the P19 ATR
  buffer in both branches — they are offsets in their own right, and a zone-sized nudge there
  could land the clip on the wrong side of the entry.
- **One guard is ours.** If a DCA leg reaches past the far edge of its own box, the zone stop
  would not invalidate the whole ladder; F6 then stands down to P19 and records the reason. The
  frames show ladders inside the box and say nothing about this case, so the guard is
  **[OUR CHOICE]**.

### The three frames, reproduced under test

`tests/test_plan.py::test_f6_frame_is_reproduced_by_the_zone_fraction_rule` rebuilds each frame's
geometry from the two measured ratios plus one price anchor and asserts the rule lands on the
observed stop, with a tolerance of **0.10 × the zone height** — enough to cover the spread of the
readings themselves (0.48 / 0.49 / 0.58 against a 0.5 default) and nothing more:

| Frame | Entry | Zone box | Height | Observed stop | Computed | Miss |
|---|---|---|---|---|---|---|
| TBOT1 4:11 | 93 911 | 92 619.7 – 93 911 | 1 291.3 | 92 000 | 91 974.1 | 25.9 = **0.02 h** |
| TBOT1 1:09:19 | 524.00 | 524.00 – 552.87 | 28.87 | 509.0 | 509.56 | 0.56 = **0.02 h** |
| S8 1:28:33 | 140.00 | 138.04 – 140.00 | 1.96 | 136.91 | 137.07 | 0.16 = **0.08 h** |

How honest each price anchor is:

* **TBOT1 4:11** — *"stop loss below 92K"* is spoken on the frame (TBOT1 `[00:04:11]`), so the
  observed stop is 92 000 and the entry follows from the two ratios: 93 911. Cross-check: CF-14
  already records this trade from the transcript as *"BTC 93.5K entry / stop below 92K"*
  (TBOT1-A14) — 0.4 % from the reconstruction, by an independent route.
* **TBOT1 1:09:19** — *"Scalp long 524ish. Stop loss 509"* is spoken two seconds earlier
  (`[01:09:17]`), and 509 is where 0.49 × the box height lands from a box bottom at the entry.
  Read as the same trade; **that identification is an inference**. The spoken 509 is a rounded
  number, 0.85 (0.03 box heights) from the measured 509.85.
* **S8 1:28:33** — no price is readable or spoken (*"stop loss somewhere here"*), so the entry is
  a **nominal** 140.00 at SOL's scale. Only the ratios carry meaning on this frame.

A counter-test (`test_f6_the_atr_parameterisation_does_not_reproduce_the_frames`) shows the ATR
parameterisation missing all three by more than a quarter of a box height — it is measured from a
candle, so it is blind to the box the trader drew.

### Also corroborated (no code change — already implemented)

In every readable frame the stop sits **below the candle bodies but deliberately NOT below the
deepest / capitulation wick** — the spoken rule at TBOT1 22:57. **Four frames now support it.**
The zone box is body-drawn, so an F6 stop inherits this by construction; on the non-zone branch
P12 (capitulation wick) and `stop_wick_max_pct` already enforce it. Asserted in
`test_f6_stop_sits_below_the_bodies_but_not_below_the_capitulation_wick`.

---

## F1 revisited — the two-box zone is weaker, not stronger  **[METADATA CORRECTED, FLAG STAYS OFF]**

Pass 1 read the S6 52:38 wick band at **0.83×** the body box. Pass 2 read what is very likely the
**same drawing** at 53:46 as **0.33×** — and noted the rectangle was **mid-drag**, with overlapping
fills. Two other frames (S6 54:22, S8 33:56) show a **single** box, and the cleanest settled box in
the whole batch (S8 1:28:33) is a single box on body extremes.

- `zone_wick_band_enabled` stays **false**. Its note now records that the two-box form appears in
  roughly **one frame in four**, is **not his standard convention**, and that the one clear example
  was measured **mid-drag**.
- `zone_wick_band_max_ratio`'s sweep bracket widens from **0.83–1.00** to **0.30–1.00**, and both
  the note and SPEC §11.2 record that two readings of the same drawing disagree by a factor of
  **2.5**, so the ratio is **not currently a trustworthy number**.
- **The consistent part, and it is solid:** in every *settled* box measured across both passes, top
  and bottom both anchor to candle **bodies**. That is what §5.5 already implements.

Pass 1 asked for 3–5 more frames before flipping the flag. Pass 2 supplies four more frames and
they point the other way; the flag now needs a materially better example than the one it has.

---

## F7 — Entries sit on a zone edge, never mid-box  **[CORROBORATION, NO CHANGE]**

| Frame | Chart | Entry line | Position in box (0 = top, 1 = bottom) |
|---|---|---|---|
| DOGE 2H | short | bottom edge | **1.00** |
| SOL 4H | long | top edge | **0.01** |

That matches the existing model exactly: first entry at the **near** edge, final DCA at the **far**
edge (CF-17, CF-18). Recorded as corroboration on `dca_count_default` and `dca2_min_zone_depth_atr`;
**nothing changed**.

**Honest limit, recorded in the metadata:** none of the entry lines in these frames is labelled, so
the frames **cannot** distinguish which line is the first entry and which is the DCA. They
corroborate the geometry (entries live on edges), not the ordering, and not the depth threshold
that gates the second leg — `dca2_min_zone_depth_atr` stays **OUR number**.

---

## F8 — Confluence count: two frames, weak  **[RECORDED ONLY]**

| Frame | Chart | Objects at the trade price |
|---|---|---|
| ONDO 1D | clean | **5** overlapping objects at price |
| BONK 12H | busier | **2–3** strictly at price, **5–6** within a risk-box height |

Consistent with `min_confluence_count = 3`, and the BONK reading is a useful reminder that the
count depends on the tolerance band you count within (`confluence_merge_atr`). **Two data points,
neither labelled as a threshold.** Added as weak supporting evidence on the key's note; the default
is unchanged and the finding is deliberately not overstated.

---

## Explicitly rejected — do not mistake these for evidence later

* **The 26.99 % measure-tool reading on the MUMU 4H frame (S6 2:02:44).** It measures **one large
  move** and is not a stated threshold of any kind. It sits next to the `sufficient_gap_pct_by_tf`
  4H row (6.0 %) and would look like a correction to anything scraping percentages mechanically.
  It is not one. **Rejected.**
* **The 8.10 % on S5 36:05 (pass 1, restated here so the two sit together).** A 1H measure drawn
  across a **hand-drawn illustration**, not candles. **Rejected**, for the same class of reason.

Both are recorded here precisely so that a future pass does not rediscover either one and mistake
it for gap-threshold evidence. `sufficient_gap_pct_by_tf`'s 2H/4H/8H/12H rows remain
**[OUR CHOICE]**, and F5's verdict stands: video is exhausted, a backtest sweep is the only route.

* **The TBOT1 4:11 stop-label percentage.** The label renders as **1.84 %**; the arithmetic of the
  frame's own geometry gives **2.04 %** (= `(1 + f) / f` × 0.66 % with f = 0.48). The middle glyph
  is not legible at 1080p. **2.04 % is what is recorded**, with the discrepancy noted here and in
  the test docstring. Nothing is keyed off either number — the F6 default comes from the *fraction*,
  which was measured geometrically.

---

## Applied to the bot — pass 2

### Config keys

| Key | Old | New | Why |
|---|---|---|---|
| `stop_buffer_zone_fraction` | *(did not exist)* | **0.5** (sweep 0.45–0.60) | **F6** — three frames |
| `stop_buffer_atr` | 0.15 | 0.15 *(unchanged; scope narrowed to non-zone stops, note rewritten)* | F6 |
| `zone_wick_band_max_ratio` | 1.0, sweep 0.83–1.00 | 1.0, **sweep 0.30–1.00** | F1 re-read |
| `zone_wick_band_enabled` | false | false *(note rewritten: ~1 frame in 4, mid-drag)* | F1 re-read |
| `min_confluence_count` | 3.0 | 3.0 *(note: F8 weak support)* | F8 |
| `dca_count_default`, `dca2_min_zone_depth_atr` | unchanged | unchanged *(notes: F7 corroboration + its limit)* | F7 |

Key count **244 → 245**.

### Files changed

| File | Why |
|---|---|
| `bot/tbot/config.py` | `stop_buffer_zone_fraction`; `stop_buffer_atr` demoted to fallback in its note; F1 notes + widened bracket; F7/F8 corroboration notes; counts |
| `bot/tbot/primitives.py` | `stop_buffer_zone()` — **P19b**, the F6 buffer; P19's docstring scoped to the fallback |
| `bot/tbot/models.py` | `Zone.body_stop_edge` — the far **body** edge the F6 stop measures from |
| `bot/tbot/plan.py` | `place_stop(zone_stop_edge=…, zone_height=…, beyond_price=…)`; `build_plan` passes the zone geometry and the ladder extreme |
| `bot/tbot/dashboard/settings.py`, `bot/tbot/dashboard/gates.py` | the new key is live-tunable and named by gates G12/G13 |
| `bot/configs/default.yaml` | regenerated — 245 keys |
| `bot/tbot/INTERFACES.md`, `bot/tbot/cli.py` | ownership row for the new key, `Zone.body_stop_edge`, counts |
| `SPEC.md` | §2.4, P19/**P19b**, §5.5 (F1 weakened), §8.5 (rewritten around F6), §8.9 scope table, §11.2, §11.13 counts + brackets, §13, §14 |
| `CONFLICTS.md` | pass-2 F-status rows (F6/F7/F8) and F1 downgrade; CF-14 verdict step 4 + **F6 addendum**; CF-17 **F7 addendum**; CF-31 **F8 addendum** |
| `bot/tests/test_plan.py` | 12 F6 tests, including the three frame reproductions |
| `bot/tests/test_primitives.py`, `test_dashboard.py`, `test_integration.py` | key count 244 → 245; F6 spec assertions; F1 note assertions |

---
---

# Pass 3 — no new frames, a second reading of the pass-2 batch

Pass 2 used the position-tool frames for one thing: **where the stop sits** (F6). Each of those
frames also carries the tool's own **Risk/Reward** and **Amount** readouts, and pass 2 never read
them. This pass does. Nothing new was captured — this is the same batch, read again.

Numbering continues: **F9**, in two parts. F9(a) changes a default; F9(b) corroborates one.

| # | Question | Outcome |
|---|---|---|
| F9 (a) | What does `min_rr` measure to? | **Default changed.** `rr_measured_to` `tp1` → `final_tp`. Four frames. |
| F9 (b) | What is risk per trade? | **Corroborated.** A constant cash 750 on three frames. No change. |

---

## F9(a) — R:R is measured to the target line, not to a first partial  **[DEFAULT CHANGED]**

Four frames of the TradingView **position tool**, with its Risk/Reward readout visible:

| Frame | Chart | R:R shown | Target amount | Risk amount |
|---|---|---|---|---|
| TBOT1 4:11 | BTCUSDT.P 1H | **3.17** | 1792.2 | **750** |
| TBOT1 22:59 | HYPEUSDT.P 4H | **5.00** | 2249.04 | **750** |
| TBOT1 1:09:19 | OMUSDT.P 1H | **2.97** | 1741.7 | **750** |
| S8 1:28:33 | SOLUSDT.P 4H | **2.13** | 1531.53 | not shown |

Three of the four are the same frames F6 measured the stop on; TBOT1 22:59 is the frame pass 2
cited for the spoken *"not below the capitulation wick"* rule.

**The reading, and it is an inference.** A TradingView position tool has **one target line**, so
its R:R is the ratio to a **final** target. The observed 2.13–5.00 are therefore ratios to a final
target, not to a first partial. *He never says how his tool measures R:R.* The four numbers are
what the pictures show; the convention that explains them is **our reading of TradingView** and is
labelled as such on the key.

**Why that mattered to the bot.** `min_rr = 2.0` with `rr_measured_to = tp1` were both
**[OUR CHOICE]** — he states neither, and the pair was picked without noticing that they interact.
The bot ladders 2–5 TPs onto structural levels (§8.7) and TP1 is by construction the **nearest**
qualifying level, so R:R to TP1 is always the smallest ratio the ladder offers. Requiring 2.0 R
*there* is a much stricter test than requiring 2.0 R at the final target, and it is not the test
these four frames show him passing.

### The size of the gap, measured

On the canonical worked plan in the test suite — entries 100 and 97 blended to **98.17**, stop
**93.80**, TPs at **106** and **115**:

| Basis | R:R | Against `min_rr = 2.0` |
|---|---|---|
| to **TP1** (106) | **1.79** | **rejected** at G14 |
| to the **final TP** (115) | **3.85** | passes, and sits inside the observed 2.13–5.00 |

Across all 926 plans the pipeline constructs on the 300-bar synthetic run:

| | R:R to TP1 | R:R to the final TP |
|---|---|---|
| median | 3.64 | 7.49 |
| minimum | 0.81 | 1.99 |

Median ratio between the two bases: **1.55×** (mean 1.77×). The gap is not a rounding difference;
it is roughly a factor of one and a half on a typical plan, and larger on the 5-TP price-discovery
ladders.

### Yes, the gate was rejecting plans it should have passed

Stated plainly, because the brief asked for it plainly. On the 300-bar synthetic run, **255 of the
926 plans the bot constructed (27.5 %) were vetoed at G14 for an R:R below 2.0 measured to TP1,
while clearing 2.0 comfortably measured to the final TP.** Those are not marginal cases: their
median R:R to the final TP is well above the floor. The gate was doing what it was told; it was
told to measure in the wrong place.

### The rejection census, before and after

Same 300 analysed bars of `bot/data/synthetic_4h.csv`, shipped defaults, the **only** difference
being `rr_measured_to`:

| gate | reason | to TP1 | to final TP | delta |
|---|---|---:|---:|---:|
| G5 | `insufficient_confluence` | 6925 | 6925 | — |
| G4 | `weekend_blocked` | 3682 | 3682 | — |
| G0 | `anchor_beyond_price` | 1777 | 1777 | — |
| G11 | `touch_limit` | 776 | 776 | — |
| G8 | `htf_veto` | 337 | 337 | — |
| **G14** | **`rr_below_min`** | **257** | **2** | **−255** |
| G13 | `stop_too_tight` | 139 | 139 | — |
| G6 | `mid_range_no_trade` | 71 | 71 | — |
| G16 | `insufficient_tps` | 37 | 37 | — |
| G15 | `move_too_small` | 6 | 7 | **+1** |
| G0 | `zone_candidate_rejected` | 6 | 6 | — |
| G9 | `short_policy` | 2 | 2 | — |
| | **total** | **14015** | **13761** | **−254** |

Plans **published**: **663 → 917**. Plans **constructed**: **926 → 926** — unchanged, which is the
control: F9 touches nothing upstream of the gate, so exactly the same candidates were built and
only the verdict on them moved. `rr_below_min` goes from the sixth-largest rejection reason (1.8 %
of all rejections) to two cases in three hundred bars. One of the 255 released plans then failed
G15 on expected move, which is the +1 — the release is a cascade into the later gates, not a free
pass.

For scale against §4 of `bot/SAMPLE_RUN.md`: that run's census is reproduced here **exactly**,
row for row, on the `tp1` column. The 22-minute full run has not been regenerated; this probe
re-ran the same pipeline over the same 300 bars and tallied the same gates.


### What shipped

| Key | Old | New | Why |
|---|---|---|---|
| `rr_measured_to` | `"tp1"` | **`"final_tp"`** | **F9** — four frames of the readout he looks at. `"tp1"` stays as the recorded alternative. |
| `min_rr` | 2.0, `[OUR CHOICE]`, no bracket | **2.0** *(unchanged)*, **derived-with-support**, sweep **2.0–2.5** | **F9** — four observed trades at 2.13 / 2.97 / 3.17 / 5.00 put a floor of 2.0 under all of them. |

- `TradePlan` now carries **both** ratios (`rr_to_tp1`, `rr_to_final_tp`); `plan.rr_for_gate`
  picks the one `rr_measured_to` names and **G14 is applied to that**. Nothing is lost by the
  change of basis — both figures are printed by the CLI and serialised to the dashboard.
- **`min_rr` is re-sourced, not re-valued.** 2.0 stays. What changes is its standing: it was an
  invented midpoint, and it is now a floor that four observed trades clear. He still never states
  a number (TBOT1-A11, *"the best R:R you can get"*), so it is **not his number** either — it is
  ours, with support. SPEC §14.1 moves it out of the list of bare inventions and says why.
- **`rr_measured_from` was already inert** and stays that way: the *from* side is
  `sizing_reference`, which reads `size_and_stop_computed_from` (CF-18). The two keys are
  duplicates with the same members and the same default. That predates F9 and F9 does not fix it;
  it is recorded here so the next pass does not rediscover it as a bug F9 introduced.

---

## F9(b) — risk per trade is a fixed cash amount  **[CORROBORATION, NO CHANGE]**

The stop-side **"Amount"** reads exactly **750** in all three frames where it is legible:
BTCUSDT.P 1H, HYPEUSDT.P 4H and OMUSDT.P 1H — three pairs, two timeframes, two exchanges. He sizes
every trade to the same cash risk.

That is precisely what §8.8's risk-first solve produces (CF-01/CF-02: `qty = loss_budget /
|stop − average entry|`, quantity falling out of the loss at stop rather than the other way round).
The bot already implements it. Recorded as corroboration of the **model** on `max_loss_pct_swing`
and `max_loss_pct_swing_hard_cap`; **no default changed and no key added.**

**The arithmetic it implies — an inference, and labelled as one.** A constant 750 at his stated
4–5 % max loss implies a portfolio of roughly **15,000–18,750**. That is consistent, and it is all
it is: his account size is **never shown in any frame** (F3 established that), the implication runs
from the evidenced percentage to the unevidenced account rather than the other way, and one
constant across three frames is not a claim about what the constant is a percentage *of*. **No
account-size key is derived from it and none is added** — the inference lives in prose on the two
risk keys, in CF-01 and in §8.8, and nowhere in the config surface.

---

## Explicitly not concluded from these frames

* **That 750 fixes the account size.** See above. It is an inference in one direction only.
* **That 2.13 is his floor.** It is the *lowest observed* ratio in four trades, which is a
  different claim. It bounds the sweep (2.0–2.5) rather than setting the default.
* **That the target amounts (1792.2 / 2249.04 / 1741.7 / 1531.53) mean anything on their own.**
  They are the R:R numerators — 750 × the ratio, to within the tool's rounding — so they are the
  same observation counted twice, not a second one. No key is derived from them.
* **That the position tool's R:R is a *rule* he applies.** It is a readout on a drawing. What it
  evidences is the **basis** of the measurement; the floor still rests on S3-R26 and rule 5.

---

## Applied to the bot — pass 3

### Config keys

| Key | Old | New | Why |
|---|---|---|---|
| `rr_measured_to` | `"tp1"` | **`"final_tp"`** | F9(a) — four frames |
| `min_rr` | 2.0, `[OUR CHOICE]`, no bracket | 2.0 *(unchanged)*, re-sourced, **sweep 2.0–2.5** | F9(a) |
| `max_loss_pct_swing`, `max_loss_pct_swing_hard_cap` | unchanged | unchanged *(notes: F9(b) corroboration + the labelled inference)* | F9(b) |

Key count **245 → 245**. F9 adds no keys, and deliberately does not add an account-size one.

### Files changed

| File | Why |
|---|---|
| `bot/tbot/config.py` | `rr_measured_to` default + note + source; `min_rr` re-sourced with the observed range and a sweep bracket; F9(b) notes on the two swing risk keys |
| `bot/tbot/models.py` | `TradePlan.rr_to_final_tp` |
| `bot/tbot/plan.py` | computes `rr_to_final_tp`; new `rr_for_gate(config, plan)` — the CF-42 basis selector |
| `bot/tbot/qualify.py` | G14 takes the measured ratio as `rr` (was `rr_to_tp1`) and names F9 in its source ids |
| `bot/tbot/pipeline.py` | passes `rr_for_gate(cfg, plan)` into the §7.1 second pass instead of `plan.rr_to_tp1` |
| `bot/tbot/dashboard/serialize.py`, `bot/tbot/dashboard/gates.py` | `rr_to_final_tp` on the ticket; G14's explanation names the basis |
| `bot/tbot/cli.py`, `bot/tbot/backtest/engine.py` | tickets and the event log print the gated figure |
| `bot/configs/default.yaml` | regenerated — still 245 keys |
| `bot/tbot/INTERFACES.md` | `TradePlan` R:R bullet; the two §7 key rows |
| `SPEC.md` | §2.7 plan fields, §7.1 G14 row, §8.7 (the F9 basis), §8.8 (F9(b)), §11.9, §11.13 brackets, §14.1 |
| `CONFLICTS.md` | F9(a)/F9(b) status rows and the precedence paragraph; **CF-42 verdict rewritten + F9 addendum**; **CF-01 F9 addendum** |
| `bot/SAMPLE_RUN.md` | second staleness note: §4's `rr_below_min` row is the old basis |
| `bot/tests/test_plan.py`, `test_qualify.py`, `test_pipeline.py`, `test_primitives.py`, `test_dashboard.py` | 10 F9 tests |
