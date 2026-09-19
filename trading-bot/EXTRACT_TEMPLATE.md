# Extract format (use these exact headings, in this order)

# <LABEL> — <one-line topic of the session>
Source: transcripts/<FILE>  |  Runtime covered: <first ts> to <last ts>

## 1. Scope
Two or three sentences: what this session actually teaches.

## 2. Definitions
Every term the instructor defines, in HIS words (paraphrased tightly), with timestamp.
Flag where his definition deliberately differs from the "textbook" one.
Format: **term** — definition. `[hh:mm:ss]`

## 3. Hard rules
Only things that could be written as code. Number them <LABEL>-R1, R2, ...
Each: one-sentence rule, then `params:` any numbers/thresholds, then `[hh:mm:ss]`.
If he gives a rule and later softens or contradicts it, capture BOTH and say so.

## 4. Parameters and thresholds
Markdown table: | parameter | value | applies to | timestamp |
Include every number he states (percentages, candle counts, win rates, timeframes,
risk limits, R:R, fill fractions).

## 5. Entry model
How a setup is identified and where entries/DCAs are placed. Be concrete about
ordering (first entry vs final DCA) and what price level each attaches to.

## 6. Stops
Placement logic, and what makes a stop too wide.

## 7. Take profit and trade management
TP placement, how many, stop-loss trailing rules on TP hits.

## 8. Invalidation and re-entry
When a zone/setup dies; when the same setup may be taken again.

## 9. Timeframes
Which timeframes for which style, and any higher-timeframe confirmation logic.

## 10. Confluence
What counts as a confluence, how many he wants, whether he weights them.

## 11. Explicitly excluded
Things he says he does NOT trade or does not believe in.

## 12. Ambiguities for the bot
Anything underspecified that a coder must decide. Be specific about what is missing.
Number them <LABEL>-A1, A2, ...

## 13. Contradictions
Anything in THIS session that conflicts with itself or that you suspect will
conflict with other sessions. Number <LABEL>-C1, C2, ...
