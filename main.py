#!/usr/bin/env python3
"""FAA outage-attribution forecaster for make.fun (polymarket-faa-attribution-02).

Each case asks for minute-by-minute five-quantile forecasts, four hours ahead,
for a small set of Polymarket Yes/No markets. This entry forecasts every market
from its own price history and only ties the markets together when their prices
look like shares of a single outcome — which the FAA markets are not.

For one market and one horizon, the centre of the forecast is the last price
plus a drift that leans against recent up-jumps: a price that jumped up in the
last hour tends to give back about three fifths of that jump over the next
four hours, while a down-jump tends to stick. Around that centre, the spread
comes from the market's own past — recency-weighted empirical quantiles of how
far the price moved over the same horizon before, squeezed down, because the
next four hours are usually calmer than the last three days. When the
checkpoint prices add up like mutually exclusive outcomes, the centres are
nudged so their sum glides toward 1.02; for the four independent FAA markets
that nudge is switched off by its guard.

Standard library only; no network. The same input gives byte-identical output.
"""

import json, math, os, sys

QUANTILES = (0.05, 0.25, 0.5, 0.75, 0.95)
GRID_H = (1, 2, 3, 5, 8, 12, 20, 30, 45, 60, 90, 120, 180, 240)
HALF_LIFE_MIN = 1440.0
CORE_SHRINK = 0.3
TAIL_SHRINK = 0.4
SUM_AIM = 1.02
GAUSS_Z = (
    -1.6448536269514722, -0.6744897501960817, 0.0,
    0.6744897501960817, 1.6448536269514722,
)


def clamp01(v):
    if v < 0.0:
        return 0.0
    if v > 1.0:
        return 1.0
    return v


def quantile_of(samples, tau):
    """Weighted quantile: first value whose cumulative weight reaches tau."""
    if not samples:
        return 0.0
    ordered = sorted(samples)
    total = 0.0
    for _, w in ordered:
        total += w
    if total <= 0:
        return ordered[len(ordered) // 2][0]
    cutoff = tau * total
    running = 0.0
    for value, w in ordered:
        running += w
        if running >= cutoff:
            return value
    return ordered[-1][0]


def change_offsets(history):
    """Per coarse horizon, the centred empirical offset fan for one market."""
    n = len(history)
    table = {}
    for h in GRID_H:
        if h >= n:
            continue
        samples = []
        for i in range(n - h):
            age = n - 1 - i - h
            samples.append((history[i + h] - history[i], 0.5 ** (age / HALF_LIFE_MIN)))
        qs = [quantile_of(samples, t) for t in QUANTILES]
        med = qs[2]
        table[h] = [
            (qs[0] - med) * TAIL_SHRINK,
            (qs[1] - med) * CORE_SHRINK,
            0.0,
            (qs[3] - med) * CORE_SHRINK,
            (qs[4] - med) * TAIL_SHRINK,
        ]
    return table


def fan_offsets(h):
    """Gaussian fan offsets, used only when a market has no empirical shape."""
    scale = 0.0025 * math.sqrt(h)
    return [z * scale for z in GAUSS_Z]


def offsets_at(table, h):
    """Offset fan for horizon h: exact, interpolated, or the Gaussian fan."""
    if h in table:
        return table[h]
    keys = sorted(table)
    if not keys:
        return fan_offsets(h)
    below = None
    above = None
    for k in keys:
        if k < h:
            below = k
        elif k > h and above is None:
            above = k
    if below is None:
        return table[above]
    if above is None:
        return table[below]
    frac = (h - below) / (above - below)
    lo = table[below]
    hi = table[above]
    return [lo[j] + frac * (hi[j] - lo[j]) for j in range(5)]


def cohere_sums(grid, prepared, steps):
    """Nudge the medians so their sum glides toward SUM_AIM.

    Only runs when the checkpoint prices add up like mutually exclusive
    outcomes (between 0.7 and 1.3). At each horizon the correction is shared
    across markets in proportion to each market's checkpoint price and is
    capped at 0.1 in either direction, so one wild horizon cannot drag the
    whole forecast.
    """
    count = len(prepared)
    s0 = sum(last for _, last, _, _ in prepared)
    if s0 > 0.7 and s0 < 1.3:
        for h in range(steps):
            s = sum(grid[mid][h][2] for mid, _, _, _ in prepared)
            aim = s0 + (SUM_AIM - s0) * ((h + 1) / 240.0)
            delta = aim - s
            if delta > 0.1:
                delta = 0.1
            elif delta < -0.1:
                delta = -0.1
            if abs(delta) <= 1e-12:
                continue
            for mid, last, _, _ in prepared:
                share = (last / s0) if s0 > 0.0 else (1.0 / count)
                shift = delta * share
                row = grid[mid][h]
                grid[mid][h] = [q + shift for q in row]


def forecast_case(case):
    steps = int(case.get("horizon_minutes", 240))
    universe = case["markets"]
    prepared = []
    for m in universe:
        history = m["prices"]
        n = len(history)
        last = history[-1]
        up_move = (last - history[-61]) if n > 60 else 0.0
        drift = -0.05 * last - 0.6 * max(up_move, 0.0)
        prepared.append((m["id"], last, drift, change_offsets(history)))
    grid = {}
    for mid, last, drift, fan in prepared:
        rows = []
        for step in range(1, steps + 1):
            centre = last + drift * (step / 240.0)
            off = offsets_at(fan, step)
            rows.append([centre + o for o in off])
        grid[mid] = rows
    # Sum coherence lives in cohere_sums above: it glides the medians' sum
    # toward SUM_AIM when the checkpoint prices look mutually exclusive,
    # and does nothing for the independent FAA markets (sum about 0.2).
    cohere_sums(grid, prepared, steps)
    result_rows = []
    for mid, _, _, _ in prepared:
        rows = []
        for row in grid[mid]:
            r = [round(clamp01(q), 6) for q in row]
            for k in range(1, len(r)):
                if r[k] < r[k - 1]:
                    r[k] = r[k - 1]
            rows.append(r)
        result_rows.append({"id": mid, "q": rows})
    result = {"forecasts": result_rows}
    return result


def run():
    in_dir = os.environ.get("MAKEFUN_INPUT_DIR") or "/input"
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR") or "/output"
    names = sorted(fn for fn in os.listdir(in_dir) if fn.endswith(".in"))
    if not names:
        sys.stderr.write("no .in files in %s\n" % in_dir)
        return 1
    os.makedirs(out_dir, exist_ok=True)
    for name in names:
        case_id = name[: -len(".in")]
        with open(os.path.join(in_dir, name), "r", encoding="utf-8") as f:
            case = json.loads(f.read())
        result = forecast_case(case)
        text = json.dumps(result, separators=(",", ":"))
        with open(os.path.join(out_dir, case_id + ".out"), "w", encoding="utf-8") as f:
            f.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
