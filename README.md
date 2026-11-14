# FAA outage attribution forecaster

An entry for the make.fun bounty **polymarket-faa-attribution-02**: forecast
the prices of Polymarket's FAA outage attribution markets, minute by minute,
four hours ahead. The prize pool is **$250 USDC**. Entries opened
**2026-11-14 02:00 UTC** and close **2026-11-14 14:00 UTC (21:00 WIB)**.

## The four markets

The contest covers four Yes/No markets asking how the FAA outage of
November 13, 2026 ends up officially attributed:

- **Iran** — the outage is attributed to Iran
- **foreign actor** — attributed to some other foreign actor
- **hack** — attributed to a hack
- **AI sandbox escape** — attributed to an AI escaping its sandbox

These are independent markets, not four slices of one pie: more than one of
them could resolve Yes, or none of them. Their prices do not have to add up
to one, and the forecaster treats them that way.

## Practice score

The FAA markets were created on 2026-11-13 and hold too little history to
cut a practice set from, so the contest's practice is six cases cut from the
earlier NVIDIA CEO event. Validated locally on those six cases
(2026-11-14, with the kit's own scorer):

- **This entry: pinball loss 0.2803**
- House baseline (starter): **0.363589**

The scorer reproduces the baseline's published practice loss exactly, so the
local grading is trustworthy. Per case: p00 0.4792, p01 0.2875, p02 0.3806,
p03 0.3186, p04 0.1741, p05 0.1073. Two runs give byte-identical outputs,
each case takes well under a second, and output files are 194–260 KB
(limit 1,048,576 bytes).

A practice score is no guide to the final: the final runs on twelve fresh
cases over 48 hours of unseen prices, on markets barely a day old.

## How the forecast works

`main.py` is Python 3.13, standard library only, no network, deterministic.
For each market and each horizon h = 1..240 minutes after the checkpoint:

1. **Centre** — the last price plus a drift that leans against recent
   up-jumps: `m(h) = x + (h/240) * (-0.05*x - 0.6*max(jump60, 0))`, where
   `x` is the checkpoint price and `jump60` is how much the price rose over
   the last 60 minutes. An up-jump gives back about 60% of itself over the
   next four hours (up-jumps are mostly noise); a down-jump is not bought
   back (down-jumps stick).
2. **Spread** — the market's own recency-weighted empirical quantiles of its
   past h-minute price changes (24-hour half-life), at coarse horizons
   1, 2, 3, 5, 8, 12, 20, 30, 45, 60, 90, 120, 180 and 240 minutes,
   linearly interpolated in between. The offsets are centred on the median:
   the central ones (25%/75%) are shrunk by 0.3 and the tails (5%/95%) by
   0.4, because the next four hours are usually calmer than the last three
   days. When a market's history is too short for a horizon, the
   house-baseline Gaussian fan is used for that horizon instead.
3. **Sum coherence** — when the checkpoint prices add up like mutually
   exclusive outcomes (between 0.7 and 1.3), the medians are nudged,
   proportional to each market's share, so their sum glides toward 1.02
   over the 240 minutes, with the total correction capped at 0.1.
   **On the FAA final this step does nothing**: the four independent
   markets sum to about 0.2, outside the guard, so the per-market
   forecasts pass through untouched — which is the correct behaviour for
   independent markets.
4. Every quantile is clamped to [0, 1], rounded to 6 decimals, and forced
   non-decreasing within its row.

Why this shape and not a Gaussian fan: these prices are a jump process —
about 90% of minutes do not move at all, then a tick, occasionally a jump.
A Gaussian fan wastes spread on quiet minutes; empirical quantiles capture
the flat centre and the fat tails. Volatility also clusters, so the shape
has to adapt to the recent regime — the recency weighting does that.

## Honest odds

On the NVIDIA contest the paid top-100 cutoff was 0.243, and this entry's
practice loss is 0.280 — so on practice it sits around the middle of the
ranked entries, likely just outside the paid places. The final is twelve
fresh cases, so the final score can shift either way, and a prize also needs
a loss strictly below the best house entry (baseline or house model,
whichever is lower) — the house model's loss is published nowhere. Treat
this as a lottery ticket, not income. Prize split: 1st $40, 2nd $25,
3rd $15, 4th–10th $5, 11th–100th $1.50.

## Input and output

- Input: every `*.in` file in `$MAKEFUN_INPUT_DIR` (else `/input`). Each is
  one JSON object: `schema`, `competition`, `case`, `at`, `horizon_minutes`
  (240), `quantiles` ([0.05, 0.25, 0.5, 0.75, 0.95]), `event`, and
  `markets` — each market with `id`, `name`, `slug`, `yes_token`, `start`,
  and `prices` (one number per minute up to the checkpoint, last value is
  the checkpoint price).
- Output: one `<id>.out` per case in `$MAKEFUN_OUTPUT_DIR` (else `/output`).
  One JSON object with exactly one key, `forecasts`: one row per market,
  `{"id": <market id>, "q": [[5 numbers] x 240]}`, row h−1 being the
  forecast for the minute at+h, quantiles in the order
  0.05 / 0.25 / 0.5 / 0.75 / 0.95, each finite, in [0, 1], non-decreasing.
- Score: mean pinball loss in percentage points,
  `100 * max(tau*(y-q), (tau-1)*(y-q))`, over every case, market, minute
  and quantile. Ties are broken by runtime (faster first), then by earlier
  receipt.

## Running it locally

No dependencies beyond Python 3.13. Point the program at a directory of
`*.in` case files and a directory for the outputs:

    MAKEFUN_INPUT_DIR=/path/to/cases MAKEFUN_OUTPUT_DIR=/path/to/out python3 main.py

It reads every `*.in` file, writes one `<id>.out` per case, and prints
nothing on success. The same input always produces byte-identical output,
so a second run can be diffed against the first to check determinism. The
practice cases live in the kit under `input/` (p00–p05); the kit's scorer
reproduces the house baseline exactly, which is the quickest way to check
that a local grading setup is trustworthy.

## Files

- `main.py` — the entry (Python 3.13, standard library only).
- `LICENSE` — MIT (from the kit's starter; required at the submitted commit).
- `README.md` — this file.
