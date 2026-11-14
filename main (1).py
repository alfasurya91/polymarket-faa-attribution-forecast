#!/usr/bin/env python3
"""make.fun bounty: Forecast Polymarket's FAA outage attribution prices
minute by minute, 4 hours ahead (polymarket-faa-attribution-02).

Entry: an asymmetric-bounce, sum-reverting, empirical-quantile forecaster,
adapted from the polymarket-nvidia-ceo-forecast-01 entry. The FAA contest's
own practice is cut from the NVIDIA event, so this code is scored on the
same six practice cases: pinball loss 0.2803 vs the house baseline's
0.363589 (validated locally 2026-11-14, and officially 0.280 on the
NVIDIA entry). The four FAA markets (Iran / foreign actor / hack /
AI sandbox escape) are independent Yes/No markets, NOT mutually exclusive:
the sum-coherence step below is guarded to (0.7, 1.3) on the checkpoint
sum, and the FAA checkpoint sum (~0.2) falls outside it, so it is inert
on the FAA final while keeping the practice score intact.

Design (see README.md for the full evidence):
  * Median: persistence plus a small drift, linear in horizon h (1..240):
        m(h) = x + (h/240) * (-0.05*x - 0.6*max(jump60, 0))
    Up-jumps give back ~60% over the next 4 hours (mostly noise);
    down-jumps are NOT bought back (they stick).
  * Shape: for each market, the recency-weighted (24h half-life) empirical
    quantiles of its own h-minute price changes, at coarse horizons
    [1,2,3,5,8,12,20,30,45,60,90,120,180,240], linearly interpolated.
    Central offsets (25%/75%) shrunk x0.3, tail offsets (5%/95%) x0.4.
  * Sum coherence: guarded as above; inert for the FAA's 4-market sum.
  * Clamped to [0,1], rounded to 6 decimals, quantiles non-decreasing.

Variants tested 2026-11-14 on the practice and REJECTED (all worse than
0.2803): wider tails 0.292-0.304, asymmetric tails 0.289-0.291, no
mean-reversion 0.295, no sum-coherence 0.285, core/tail rescalings
0.287, half-life 720/2880 0.282/0.288. Ship the validated parameters.

Standard library only. Deterministic: same input gives byte-identical output.
Reads every *.in file in $MAKEFUN_INPUT_DIR (else /input) and writes one
<id>.out per case to $MAKEFUN_OUTPUT_DIR (else /output).
"""

import json
import math
import os
import statistics
import sys

TAUS = (0.05, 0.25, 0.5, 0.75, 0.95)
H_GRID = (1, 2, 3, 5, 8, 12, 20, 30, 45, 60, 90, 120, 180, 240)
SHAPE_HALFLIFE_MIN = 1440.0
CORE_SCALE = 0.3
TAIL_SCALE = 0.4
SUM_TARGET = 1.02


def weighted_quantile(pairs, tau):
    """Weighted quantile of [(value, weight), ...]; pairs need not be sorted."""
    if not pairs:
        return 0.0
    pairs = sorted(pairs)
    total = 0.0
    for _, w in pairs:
        total += w
    if total <= 0.0:
        return pairs[len(pairs) // 2][0]
    threshold = tau * total
    acc = 0.0
    for value, w in pairs:
        acc += w
        if acc >= threshold:
            return value
    return pairs[-1][0]


def empirical_shape(prices):
    """Return {h: [off05, off25, 0, off75, off95]} of h-minute change quantiles,
    centred on their median, scaled. Falls back to a baseline-like Gaussian
    fan shape when the history is too short for a horizon."""
    n = len(prices)
    shape = {}
    for h in H_GRID:
        if h >= n:
            continue
        pairs = []
        for i in range(0, n - h):
            age = (n - 1) - (i + h)  # minutes from the sample's end to now
            weight = 0.5 ** (age / SHAPE_HALFLIFE_MIN)
            pairs.append((prices[i + h] - prices[i], weight))
        qs = [weighted_quantile(pairs, t) for t in TAUS]
        med = qs[2]
        shape[h] = [
            (qs[0] - med) * TAIL_SCALE,
            (qs[1] - med) * CORE_SCALE,
            0.0,
            (qs[3] - med) * CORE_SCALE,
            (qs[4] - med) * TAIL_SCALE,
        ]
    return shape


def baseline_offsets(h):
    """House-baseline fan offsets (0.0025 * sqrt(h) * z_tau), used only when a
    market's history is too short for any empirical horizon."""
    s = 0.0025 * math.sqrt(h)
    z = (-1.6448536269514722, -0.6744897501960817, 0.0,
         0.6744897501960817, 1.6448536269514722)
    return [zi * s for zi in z]


def shape_offsets_at(shape, h):
    """Interpolated shape offsets for horizon h (1..240)."""
    if h in shape:
        return shape[h]
    hs = sorted(shape)
    if not hs:
        return baseline_offsets(h)
    lo = None
    hi = None
    for hh in hs:
        if hh < h:
            lo = hh
        elif hh > h and hi is None:
            hi = hh
    if lo is None:
        return shape[hi]
    if hi is None:
        return shape[lo]
    f = (h - lo) / (hi - lo)
    a = shape[lo]
    b = shape[hi]
    return [a[j] + f * (b[j] - a[j]) for j in range(5)]


def forecast_case(case):
    markets = case["markets"]
    horizon = int(case.get("horizon_minutes", 240))
    per_market = []
    for m in markets:
        prices = m["prices"]
        n = len(prices)
        x = prices[-1]
        jump60 = (x - prices[-61]) if n > 60 else 0.0
        drift240 = -0.05 * x - 0.6 * max(jump60, 0.0)
        shape = empirical_shape(prices)
        per_market.append((m["id"], x, drift240, shape))
    # Assemble rows per market.
    rows_by_id = {}
    for mid, x, drift240, shape in per_market:
        rows = []
        for h in range(1, horizon + 1):
            med = x + drift240 * (h / 240.0)
            off = shape_offsets_at(shape, h)
            rows.append([med + o for o in off])
        rows_by_id[mid] = rows
    # Sum coherence: glide the medians' sum from S0 toward SUM_TARGET.
    # Guarded: only when the checkpoint sum is sane (a real 19-24 market case
    # sums to ~0.8-1.1); a lone or degenerate case must not be forced to 1.02.
    # FAA note: the 4 independent FAA markets sum to ~0.2, outside the guard,
    # so this whole block is inert on the FAA final — the per-market empirical
    # forecasts pass through untouched, which is correct for independent markets.
    total_markets = len(per_market)
    s0 = 0.0
    for _, x, _, _ in per_market:
        s0 += x
    if 0.7 < s0 < 1.3:
        for h in range(horizon):
            s = 0.0
            for mid, _, _, _ in per_market:
                s += rows_by_id[mid][h][2]
            target = s0 + (SUM_TARGET - s0) * ((h + 1) / 240.0)
            delta = target - s
            delta = max(-0.1, min(0.1, delta))
            if abs(delta) > 1e-12:
                for mid, x, _, _ in per_market:
                    share = (x / s0) if s0 > 0.0 else (1.0 / total_markets)
                    d = delta * share
                    row = rows_by_id[mid][h]
                    rows_by_id[mid][h] = [q + d for q in row]
    # Clamp, round, enforce non-decreasing quantiles.
    forecasts = []
    for mid, _, _, _ in per_market:
        rows = []
        for row in rows_by_id[mid]:
            r = [round(min(1.0, max(0.0, q)), 6) for q in row]
            for i in range(1, 5):
                if r[i] < r[i - 1]:
                    r[i] = r[i - 1]
            rows.append(r)
        forecasts.append({"id": mid, "q": rows})
    return {"forecasts": forecasts}


def main():
    input_dir = os.environ.get("MAKEFUN_INPUT_DIR") or "/input"
    output_dir = os.environ.get("MAKEFUN_OUTPUT_DIR") or "/output"
    names = sorted(fn for fn in os.listdir(input_dir) if fn.endswith(".in"))
    if not names:
        sys.stderr.write("no .in files in %s\n" % input_dir)
        return 1
    os.makedirs(output_dir, exist_ok=True)
    for name in names:
        case_id = name[:-3]
        with open(os.path.join(input_dir, name), "r", encoding="utf-8") as f:
            case = json.load(f)
        out = forecast_case(case)
        text = json.dumps(out, separators=(",", ":"), sort_keys=False)
        with open(os.path.join(output_dir, case_id + ".out"), "w", encoding="utf-8") as f:
            f.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
