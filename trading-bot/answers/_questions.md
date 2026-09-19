
1. **Zone invalidation — 50% or 70–80%, and measured how?**
   You say a zone is dead once ~50% of it fills (S5/S6), but you also say your order-block rule is
   "around 70 to 80%" of liquidity taken (S7), and elsewhere that a 50%-filled order block is still
   playable. Which is it — (a) 50% of zone depth, (b) 70–80% of zone depth, or (c) 50% for
   supply/demand zones and 70–80% for single-candle order blocks? And is the level breached by any
   **wick** through it, or does it need a candle **close** beyond it?

2. **Third-touch rule vs replaying a zone.**
   You say don't take the same level after its third touch, but you also say you'll replay a demand
   zone as many times as you like until 50% fills, and you count seven bounces approvingly. Is the
   third-touch rule (a) only for bare support/resistance lines, with zones governed purely by the 50%
   rule, (b) a size reduction rather than a veto, or (c) a hard veto everywhere? If it's a size
   reduction, what size at touches 3, 4 and 5?

3. **DCA size split.**
   You always say "light at entry, heavier at the DCA", but never a ratio. For a two-leg entry, is it
   30/70, 25/75, or something else? For three legs — 20/30/50? The blended average is the whole point
   of the ladder, so this number decides break-even, every TP-trail decision and the position size.

4. **What fraction comes off at each TP?**
   The only split you've given is 50/50 for two TPs and 40/30/30 for three (S4). Is that still what
   you run? And when you place TPs at whatever structural levels happen to exist, rather than a fixed
   two or three, how does the split adapt?

5. **Minimum confluence count, and how to count overlaps.**
   You say "I need confluence" and refuse order-block-only, fib-only, pattern-only, trendline-only and
   SFP-only trades — but never a number. Is three the floor? And when an SR point, a supply zone and
   an order block all sit at the same price, is that three confluences or one?

6. **Swing high / swing low detection.**
   Every structure rule, every SFP, every fib anchor and every order block depends on "a swing point"
   and "a directional change in price", and neither is ever defined. How many candles either side must
   a high be the highest of before you'd call it a swing high — 3? 5? — and how big does a move have to
   be before you'd call it a directional change: a fixed percentage, an ATR multiple, or a break of the
   prior swing?

7. **Which timeframe governs?**
   For a trade you're placing on the 1H: which timeframe do you read trend and market structure on,
   which one has to confirm the MSB close, and which one decides whether an SFP is valid? (The same
   sweep was a valid daily SFP and an invalid 12H SFP in S8 and you didn't say which wins.)

8. **Normal leverage position size.**
   S3 says a normal position is 20% of portfolio, S7 says 10%, and spot is 6–12%. For a leverage swing
   with a 4–5% max loss, what's the notional and what leverage are you using to get there?

9. **Counter-trend: cancel it, or halve it?**
   In S7 you say you'd have cancelled a bullish setup once the trend flipped to lower highs; a minute
   later you say it's fine to play against the trend at half size. Which one does the bot do — hard
   veto, or 0.5× size with a 2–3% loss cap? And does a counter-trend trade always have to be demoted
   to a scalp on a lower timeframe?

10. **Resting limits at the SR point vs waiting for the flip.**
    S4 says explicitly: do not put a limit at the line waiting for the flip, wait for breakout + retest
    + hold, then enter. Everywhere else you say "I always enter my positions at SR points and DCA
    lower", which is a resting limit. Is the difference that S4 is talking about a level that hasn't
    flipped yet, and the SR-point entries are on levels that already have?

11. **Where does the entry go after a structure break?**
    S7 says short the retest of the broken higher low; S8 says don't short the close, wait for the next
    lower high; S3 says don't act until a lower high has actually formed. Are those three the same
    thing said differently, or three different entries? And how many candles do you wait for that
    retest before you abandon the setup?

12. **Mid-range as a band.**
    "No trades at mid-range" only works if mid-range has a width. How far either side of the mid-range
    line is the no-trade zone — 10% of the range height? 15%? And is mid-range the geometric 50% or the
    nearest S/R level to it?

13. **Sufficient gap for 2H, 4H, 8H and 12H.**
    You gave numbers for 15m, 30m, 1H, daily and 2-day, but not for the timeframes you actually trade
    most. What's the minimum move away from a zone on the 4H and the 12H?

14. **Are the pattern, trend-line and scalp modules meant to ship at all?**
    You taught a full pattern library (S4), a full trend-line breakdown method (S8) and a full scalping
    session (S8), and said in each case that you don't trade them yourself. Should the bot run those as
    live strategies, or only use the patterns as extra confluence on your S/R and zone setups?

15. **Golden pocket: 0.66 or 0.65 — and is "golden pocket" ever the 0.786?**
    S6 says 0.618–0.66 and notes others use 0.65. In S8 you use "golden pocket" and "0.786"
    interchangeably. Confirm: golden pocket = 0.618–0.66, entry level; 0.786 = separate, DCA level. And
    do you want 0.886 in the set given you said you hadn't back-tested it?

---

# § Undefined primitives
