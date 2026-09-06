# RDH Trading Bot — built from the 8 session recordings

## What's here
| Path | What it is |
|---|---|
| `SPEC.md` | The consolidated specification. 1,778 lines, every rule traced to a source ID. |
| `CONFLICTS.md` | 45 cross-session conflicts, each with a verdict, reasoning and a config key. Now carries the Q1–Q15 reversal notes. |
| `QUESTIONS_FOR_TRADER.md` | The original 15 questions. **13 are now answered from the recordings — send only Q6's candle count and Q13.** |
| `CHANGELOG_EVIDENCE.md` | What each of the 15 answers changed, at what confidence, with the evidence timestamp. |
| `answers/` | The three research write-ups the changes were derived from, with quotes. |
| `transcripts/` | All 8 session transcripts, timestamped. |
| `extracts/` | Per-session rule extracts — 317 hard rules. |
| `bot/` | The Python package. 912 tests passing. |
| `bot/SAMPLE_RUN.md` | A real backtest run on synthetic data. |
| `bot/README.md` | Install and usage. |

## Quick start
```bash
cd bot
python -m pytest -q                    # 912 tests
python -m tbot config                  # every setting with its source rule
python -m tbot backtest --csv data/synthetic_4h.csv
python -m tbot scan --csv data/synthetic_4h.csv
```

Real data: `python scripts/fetch_klines.py` (run locally — it hits Binance/Bybit public REST).

## What it does NOT do
No live trading. Order execution sits behind an unimplemented adapter that raises on
every live method. It generates trade plans and backtests them. Wiring it to an
exchange is a deliberate decision for you to make, after the rules are validated.

## Session 1
Still missing — download and copy are disabled on the Drive file and the player
won't stream. Needs a screen recording. Everything else came off YouTube.
