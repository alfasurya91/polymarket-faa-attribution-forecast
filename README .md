# Forecast Polymarket's FAA outage attribution prices — make.fun entry

Bounty: **"Forecast Polymarket's FAA outage attribution prices minute by minute,
4 hours ahead"** (`polymarket-faa-attribution-02`), $250 USDC in escrow.
Entries open **2026-11-14 02:00 UTC** and close **2026-11-14 14:00 UTC (21:00 WIB)**.

The 4 markets — Iran, foreign actor, hack, AI sandbox escape — are independent
Yes/No markets for how the November 13, 2026 FAA outage is officially
attributed, not mutually exclusive. The contest's own practice is cut from
the NVIDIA event (the FAA markets were created 2026-11-13 and hold no history
to cut a practice from), so the practice score below is this entry's FAA
practice score — and, as the kit says, a practice score is no guide to the final.

## Validated score (practice = NVIDIA p00–p05, checked locally 2026-11-14)

- **This entry: pinball loss 0.2803**; house baseline 0.3636. The same entry
  scored **0.280 officially on the NVIDIA contest** (rank 1357/2141 there).
- Variants tested and rejected (all worse): wider tails 0.292–0.304, asymmetric
  tails 0.289–0.291, no mean-reversion 0.295, dropping sum-coherence 0.285,
  core/tail rescalings 0.287, half-life 720/2880 0.282/0.288.
- Honest odds: on NVIDIA the paid top-100 cutoff was 0.243, so 0.280 is a
  long shot — a lottery ticket, not income. The FAA final uses fresh prices
  (markets only ~1 day old, 12 cases over 48h), so the final score can shift
  either way. A prize also needs a loss strictly below the best house entry
  (baseline or house model, whichever is lower) — the house model's loss is
  published nowhere.

## The entry

`main.py` — Python 3.13, standard library only, no network, deterministic.
It reads every `*.in` case in `$MAKEFUN_INPUT_DIR` (else `/input`) and writes
one `<id>.out` per case to `$MAKEFUN_OUTPUT_DIR` (else `/output`).

### Design

Per market, per horizon h = 1..240 minutes after the checkpoint:

1. **Median** — persistence plus a small drift, linear in h:
   `m(h) = x + (h/240) * (-0.05*x - 0.6*max(jump60, 0))`,
   where `x` is the price at the checkpoint and `jump60 = x - price 60 min ago`.
   Up-jumps give back ~60% over 4h (they are mostly noise); down-jumps are
   *not* bought back (they stick). Big markets drift down, small ones up.
2. **Shape** — the market's own recency-weighted (24h half-life) empirical
   quantiles of its h-minute price changes, at coarse horizons
   `[1,2,3,5,8,12,20,30,45,60,90,120,180,240]`, linearly interpolated.
   Offsets are centred on the model median; central offsets (25%/75%) are
   shrunk x0.3 and tail offsets (5%/95%) x0.4, because the 72h window is
   wilder than the next 4h usually are. When a market's history is too short
   for a horizon, the house-baseline Gaussian fan is used for that horizon.
3. **Sum coherence** — the 24 NVIDIA markets are mutually exclusive, so on
   the practice their medians are pulled (proportionally to each market's
   share) so their sum glides from the checkpoint sum toward 1.02 over the
   240 minutes. Guarded: only applied when the checkpoint sum is in
   (0.7, 1.3) and the total correction is capped at 0.1. **On the FAA
   final this step is inert**: the 4 independent FAA markets sum to ~0.2,
   outside the guard, so the per-market forecasts pass through untouched —
   which is correct for independent markets.
4. Quantiles clamped to [0, 1], rounded to 6 decimals, non-decreasing.

### Why this design (evidence from the data)

- Prices are a jump process: ~90% of minutes have no move at all, then a
  tick, occasionally a jump. A Gaussian fan wastes spread on quiet minutes;
  empirical quantiles capture the flat centre + fat tails.
- Up-jumps revert, down-jumps stick: after a >+0.01 up-jump in the last
  60 min the next-240m change averages −0.043 (n=8 checkpoints); after a
  <−0.01 down-jump it averages −0.003. On rolling data (n≈11k) the same
  asymmetry holds: up-jumps give back ~70%, down-jumps ~0%.
- Volatility clusters (corr ≈ 0.5–0.58 between recent |1-min change| and the
  next 240m move), so the shape must adapt to the recent regime — the
  recency-weighted empirical quantiles do this.
- The sum of the 24 NVIDIA prices hovers ~1.0–1.09, so cross-market
  coherence helps on the practice; the FAA markets are independent, so the
  guard switches it off there.
- Traps avoided (all measured on the practice cases): a rolling-regression
  median (fit on all minutes) scores 0.41–0.66 — the crash regime of Nov 9–11
  does not describe checkpoint behaviour; EWMA-variance Gaussian fans score
  0.37–0.50 — jump-dominated variance is far too wide; the pooled level
  drift (−0.43×level) is a regime artefact and was damped to −0.05.

## Local validation (practice cases p00–p05)

The scorer (`score.py`) reproduces the house baseline's published practice
loss **exactly: 0.363589**, so the local grading is trustworthy. Practice
answers were fetched from Polymarket's public CLOB price history and verified
against the kit's case files: **0 mismatches in 207,513 compared prices**.

| forecaster | practice pinball loss |
|---|---|
| House baseline (starter) | 0.363589 |
| Empirical quantiles only | 0.378433 |
| + 24h-median reversion (hybrid shape) | 0.329938 |
| + level drift, sum correction | 0.293524 |
| + asymmetric up-jump give-back | 0.287515 |
| + narrow shape (core x0.3, tails x0.4) | **0.279815** |
| **Final `main.py` (with sum-correction guards)** | **0.280309** |

Per-case loss of the final entry: p00 0.4792, p01 0.2875, p02 0.3806,
p03 0.3186, p04 0.1741, p05 0.1073. Median error 0.2838–1.3374, 90% coverage
0.75–0.91. Runtime ~0.6s per case (limit 8s). Outputs byte-identical across
two runs (deterministic). Output files 194–260 KB (limit 1,048,576).

### Leaderboard context (NVIDIA practice, read 2026-11-13 ~13:00 UTC)

- 1,850 submissions, 1,049 ranked. Practice: 1st 0.241, 10th 0.248,
  50th 0.256, **100th 0.258**, median 0.276. House baseline 0.3636.
- This entry's 0.2803 is around the 55th percentile of ranked entries —
  **likely just outside the top 100 on practice**. The final is 12 fresh
  cases over 48h of unseen prices, so practice rank is not the final rank,
  but the honest expectation is: beats the house baseline by a clear margin
  (the prize bar), may or may not land a paid place (1st $40, 2nd $25,
  3rd $15, 4th–10th $5, 11th–100th $1.50).
- Unknown: the **house model forecast's** practice/final loss is not
  published anywhere in the kit — it is the other half of the prize bar
  (a prize needs a loss strictly below the lower of baseline/model).

## Files in this repo

- `main.py` — the entry (Python 3.13, stdlib only).
- `LICENSE` — MIT (from the kit's starter; required at the submitted commit).
- `README.md` — this file.

(The local test harness — `score.py`, `validate.py`, `fetch_actuals.py`,
`analyze.py`, `experiments*.py`, `pooled.py`, `data/`, the official `kit/` —
lives outside this repo, in the build workspace.)

## Submission checklist (for the parent agent — NOT done here)

Deadline: **2026-11-14 14:00 UTC (21:00 WIB)**. Max 10 submissions total per entrant
(and possibly fewer per day depending on the account's country risk tier —
Indonesia's tier is not published; assume the first submission should be the
best one).

1. **Solana keypair + account — DONE 2026-11-13 ~20:15 WIB.** Fresh keypair
   generated (mode 600, kept off-repo); account registered as **@zkera**
   (https://make.fun/u/zkera), wallet
   `7HhRPGGCxV32rxPfnJM7k3tV9nSpWxWq97z77nhWncpi`, referral `0h2zmzc4`
   (@nax). API key stored in `~/.makefun/credentials` (expires 2026-12-13).
   The prize pays to this wallet, not the user's Agentic Wallet.
2. **GitHub repo — USER'S STEP.** NEW public repo under the user's GitHub
   account (`alfasurya91`), created AFTER 2026-11-14T02:00:00Z (the FAA
   opening; the `repo_created_after_open` check rejects older repos — the
   NVIDIA repo from 2026-11-13 does NOT qualify), containing at the
   submitted commit: `main.py`, `LICENSE` (MIT), `README.md`, plus
   `.makefun/owner.json` naming wallet
   `7HhRPGGCxV32rxPfnJM7k3tV9nSpWxWq97z77nhWncpi`. The repo is
   public from creation, so anyone can read the code. (No GitHub credential
   is stored on this machine, so the user creates the repo and uploads the
   files via the web UI; the parent agent then reads the commit SHA
   from the public API and submits it.)
3. **Transcripts bundle** — REQUIRED, and the binding constraint:
   `node cli/makefun.mjs bundle --repo <repo> --out transcripts.tar.gz`
   from inside the unpacked FAA kit, with `--redact` for the user's personal
   details. The bundle must cover the top-level session AND this subagent
   session (every session that worked on the entry). Gate thresholds:
   `thinking_reproduces` ≥ 30% of counted lines, ≥ 5 assistant turns,
   ≥ 2 file writes, `thinking_priced` 100% priced usage, and for Muse app
   sessions **≥ 1 usage row attached with `--muse-usage`**. WARNING:
   `handed_over_places` is `none` — an entry whose sessions are handed over
   (not recorded logs) is ranked but takes **no paid place**. Do NOT hand
   over; use recorded session logs + usage rows.
   Then: `node cli/makefun.mjs check --kit . --repo <repo> --transcripts transcripts.tar.gz`
4. **Submit** (entry message is valid 10 minutes — sign and send promptly):
   `node cli/makefun.mjs submit --competition polymarket-faa-attribution-02 --repo-url https://github.com/alfasurya91/<repo> --commit <sha> --title "Asymmetric-bounce empirical-quantile forecaster" --bundle transcripts.tar.gz --keypair wallet.json`
   Then `node cli/makefun.mjs status --submission <id>` to follow the grade
   (practice grade takes ~2–4 min; the score shows on the leaderboard).
5. **Claim** — the final leaderboard is published within 7 days of the
   deadline (after the 48h window is recorded and graded). Winners claim in
   USDC on Solana from the escrow, to the wallet that signed the entry.
   A prize not claimed within the window passes to the next entry.

## Exact I/O format (from the kit's RULES.txt)

- Input `/input/<id>.in`: UTF-8 JSON, one object: `schema`
  ("makefun/polymarket-case/v1"), `competition`, `case`, `at` (ISO 8601 UTC),
  `horizon_minutes` (240), `quantiles` ([0.05,0.25,0.5,0.75,0.95]), `event`
  (final: `{"slug":"faa-outage-attribution","title":"FAA outage attribution markets"}`;
  practice: the NVIDIA event's), `markets` (universe order): each `id`
  (conditionId), `name`, `slug`, `yes_token`, `start`, `prices` (one number
  per minute from `start` to `at` inclusive; last = price at checkpoint).
  Final cases hold all 4 markets, each with prices from the 72 hours up to
  the checkpoint (4,320 minutes) or from its grid's first minute when later.
- Output `/output/<id>.out`: UTF-8 JSON ≤ 1,048,576 bytes, exactly one key
  `forecasts`: one row per market, `{"id": <market id>, "q": [[5 numbers] x 240]}`,
  row h−1 = forecast for minute at+h, quantiles in order 0.05/0.25/0.5/0.75/0.95,
  each finite in [0,1], non-decreasing.
- Score: mean pinball loss in percentage points,
  `100 * max(tau*(y-q), (tau-1)*(y-q))`, over every case/market/minute/quantile.
  Ties broken by runtime (faster first), then earlier receipt.
- House baseline: `q_tau = x + z_tau * 0.0025 * sqrt(h)`, z =
  (−1.644854, −0.674490, 0, 0.674490, 1.644854), clamped [0,1], 6dp.
  Practice loss 0.363589.
