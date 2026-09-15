# Corrections, 2026-09-06

Five corrections found by cross-checking this measurement archive against the
transcript-derived bot in `../../` (SPEC.md, CONFLICTS.md, FRAME_FINDINGS.md,
`bot/tbot/config.py`). The two workstreams had never been compared.

Nothing below is deleted from the original files. Each affected file carries a
banner pointing here, in line with the archive's own rule that a withdrawn claim
is recorded rather than removed.

House style of this directory is followed: no em dashes.

---

## C5. The BNB 1D worked example is on the wrong price scale

`00-MASTER.txt` Part 4 and `BOT-SPEC-handover.txt`.

The row as written takes one figure from each of two scales:

```
stop 12.60  target 28.60 | R:R 2.270 | qty*stop 235.08 | stop% 5.300
stop 13.40  target 28.60 | R:R 2.134 | qty*stop 250.00 | stop% 5.637   <- as written
stop 13.40  target 30.42 | R:R 2.270 | qty*stop 250.00 | stop% 5.637   <- correct
```

Printed labels on that frame: R:R **2.27**, stop **5.64%**. Every position-tool
frame in the archive: `qty x stop distance = 250.00`. Only the third row
satisfies all three constraints.

The arithmetic is exact. `28.6 x (13.4 / 12.6) = 30.42`, and `30.42 / 13.4 = 2.27`.
So the stop came from the printed label and the target came from a pixel
measurement calibrated on a misread stop leg of 12.6.

That is this project's own most-warned-about failure mode, from
`04-measurement-method.md`: a printed value combined with a mis-scaled measured
value. It survived four passes because the validation gate is scale-invariant
(see C9).

**Corrected BNB row:** stop 13.4, target 30.42, R:R 2.27, qty 18.657, risk 250,
reward 567.5.

**Prices in that frame move by 6.3%:**

```
                  as published    corrected
wick band top        248.56        249.25
body band top        242.20        242.49
body band bottom     237.79        237.80
stop                 250.34        251.14
```

The pixel rows, the ratios and every conclusion drawn from them are unaffected.
Entry still sits 0.5 px off the body band bottom; the stop still lands on the
wick band top. Only the absolute prices were wrong.

---

## C6. The reward-to-risk distribution is built on eight of nine labels

`00-MASTER.txt` Part 1, `BOT-SPEC-handover.txt`.

All nine printed R:R labels in the archive are now accounted for. `2.06` is the
LINK 4h 2024-01-30 frame, which failed the gate and is marked UNREADABLE, but
whose printed label was still legible. `2.27` is BNB (see C5).

```
nine labels : 1.60 2.06 2.13 2.27 2.61 2.97 3.17 5.00 5.00   median 2.61  mean 2.98
published 8 : 1.60 2.06 2.13 2.27 2.61 2.97 3.17 5.00        median 2.44  mean 2.73
```

The published set drops one of the two 5.00 readings with no note saying which
or why. If a default R:R is ever needed it should be **2.61 off nine labels**,
not 2.44 off eight.

Targets remain confidence-low either way. This is a description of his
behaviour, not a rule he states.

---

## C7. The 50% line does have an established role

`00-MASTER.txt` Part 2 ("has no established role", "off the critical path"),
`BOT-SPEC-handover.txt`, `07-open-questions.md` Q3.

The measurement is right and the conclusion drawn from it is wrong.

Right: on the BNB frame the blue ray sits 2.2 px off the body band midpoint on a
38.5 px box, 5.7% out, and is neither the entry nor the DCA. Nothing should code
it as an entry trigger.

Wrong: "off the critical path, the bot does not need it". It is the zone
lifecycle rule, and he states it out loud in a session this archive never had:

> "There is a rule on how many times you can play this. You can play the same
> setup over and over again until that 50% mark of the zone. If this 50% line is
> breached, this zone is no longer valid."
> - S5 `[00:38:52]`, `../../transcripts/S5.md`

And again, applying it:

> "It's the 3day demand zone. We did not get a 50% fill. So this can be played
> again."
> - S6 `[00:02:50]`, `../../transcripts/S6.md`

The bot implements this as `zone_fill_invalidation_pct = 50.0` (CF-08). The two
halves of the rule sat in different workstreams: this archive has him **drawing**
the line, the transcripts have him saying **what it does**. The recovered caption
from 2023-10-24, "this is not a DCA point, this is just the 50% line", is him
telling you it is not an entry, which is exactly what the measurement found.

Acting on "off the critical path" would delete a correct, stated rule. It is
also the most likely explanation of the OM entry exception: the question to ask
of that frame is not whether the zone had been touched but whether it had been
**50% filled**.

---

## C8. The caption blocker applies to the public channel only

`05-caption-findings.md` ("not obtainable, and dangerous to attempt", "this is
environmental, not channel-specific"), and the same claim repeated in
`00-MASTER.txt` Part 5, `RULES-STATE.txt` and `claude-code-pipeline.txt`.

The finding is sound for `@arshmeister21`. It is not true of the project, because
the bot repo contains eight complete transcripts, S2 to S8 plus TBOT1, harvested
through the very transcript panel those files record as rendering zero segments.

The difference is ownership:

| | public `@arshmeister21` | private S2 to S8 |
|---|---|---|
| transcript panel | expands, 0 segments | worked, produced 8 transcripts |
| why | ASR track `is_servable: false`, no `pot` token | operator owns them, and set the audio language |

`../../VIDEO_IDS.md`: "YouTube will not generate auto-captions until a video's
audio language is set. This was the original blocker and has been fixed on all 8
uploads."

**Consequence for the next action.** The archive names the yt-dlp pull as the
single highest-value move because Q1, Q2 and Q7 all unlock from it. Against the
transcripts that already exist:

- **Q7, confluence threshold. Already answered.** `min_confluence_count = 3`,
  CF-31, from S5 and S8 where he counts them aloud.
- **Q1, swing width. Probably answered, and the answer is that no rule exists.**
  No candle-count, fractal-width or N-bar definition appears in any of the eight
  sessions. Caveat: the quote usually cited for this, S6 `[01:21:06]` "you can
  take it from many swing low points, it doesn't matter which one", is about
  which swing to anchor a fib to, not about what qualifies as a swing. The solid
  finding is the absence across eight sessions, not the quote.
- **Q2, sufficient gap for 2H/4H/8H/12H. Still open**, and still needs the full
  public corpus, because it needs a negative.

So the pull is worth doing for one question, not three. `swing_k` should go to a
backtest sweep rather than wait on a transcript that probably does not contain
the answer.

Two further notes on the pull itself. The 23 video IDs listed across
`05-caption-findings.md` and `claude-code-pipeline.txt` are unmapped: the channel
inventory carries no video IDs, so no ID can be checked against a title. Resolve
titles to IDs with `yt-dlp --flat-playlist` first. And confirm that
`2022-10-19 "Supply and Demand Trading Method - Arsh way"` (1:27:54, 2.5k views)
is in the list. It is the most watched item on the channel, it is titled as the
method itself, and zone DETECTION is the one thing no document in either
workstream specifies.

---

## C9. The validation gate cannot catch a calibration error

`tools/frame-measure.js`, `04-measurement-method.md`.

Two problems, and the second is how C5 survived four passes.

**It can pass unconditionally.** Both sides of the comparison are ratios:

```
measured = |entryRow - targetRow| / |stopRow - entryRow|     a pixel ratio
printed  = targetDist / stopDist
```

If `stopDist` and `targetDist` are derived from pixels through a single scale,
`printed` is the pixel ratio and the error is exactly zero. Verified on the BNB
rows at two different scales: `measured 2.291, printed 2.291, err 0.00%, PASS`
both times. The gate is only meaningful when both distances are the tool's
**printed label** values. Nothing in the parameter names says so.

**It is blind to scale.** Even used correctly, a misread `stopDist` cancels in
the comparison but still corrupts the `scalePerPx` the function returns. The gate
reports PASS and hands back a wrong scale.

Fixed in `tools/frame-measure.js` by adding `qty x stopDist` as a second,
independent check on `stopDist` itself. It is free on any frame that prints a
quantity, and it is what caught C5.

Three smaller harness notes, not yet changed:

- `rowCoverage` counts any non-near-white pixel as coverage, so a row crossing a
  semi-transparent zone box fill reads high coverage from the fill alone and
  looks like a drawn level. Zone boxes are what is being measured. It also
  inverts entirely on a dark chart theme.
- `gate` uses absolute values, so it cannot detect a target or stop read on the
  wrong side of entry.
- `col()` compares each pixel to the last **reported** pixel rather than the
  previous one. Useful hysteresis on noise, but on a gradient it can drift an
  edge by a pixel, and the stop-overshoot question turns on a 15 px signal.

---

## Also corrected outside this directory

- **`stop_buffer_zone_fraction = 0.5`** in `bot/tbot/config.py` was a shipped
  default of the rule Part 2 of `00-MASTER.txt` withdrew. Re-sourced as DISPUTED,
  sweep bracket widened to 0.0 to 0.60 so a sweep can reach "snap to the
  structural level, no overshoot". Its supporting test was circular and has been
  rewritten. See `../../FRAME_FINDINGS.md` F6.
- **Risk of $750** in `FRAME_FINDINGS.md` F9(b), `SPEC.md` and `CONFLICTS.md`
  is corrected to **$250**, and the portfolio inference of 15,000 to 18,750 that
  rested on it is withdrawn. See `CORRECTION-risk-figure-v2.txt`, which had this
  right already.
