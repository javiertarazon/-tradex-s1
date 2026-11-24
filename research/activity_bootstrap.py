"""Comparacion final: trades, R y P(DD>15%) por candidato y nivel de riesgo.

Bootstrap 20.000 remuestreos sobre la serie de R de cada candidato.
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import s1_regime_ga as G
import xau_cost_lab as lab

P = G.prep(lab.load())
CACHE = {}
SIM = dict(ksl=5.2, tgt=1.25, spread=0.69, comm=0.07, swap=True)

CAND = [
    ("BASE GA-B",        dict(rb=20, max_rng=3.4, imp=1.05, hours=(13, 14, 15, 16, 17)), dict(ktp_mult=3.5, hold=120)),
    ("MAX_TRADES",       dict(rb=16, max_rng=6.0, imp=1.05, hours=tuple(range(12, 19))), dict(ktp_mult=4.5, hold=72)),
    ("MIXTO",            dict(rb=16, max_rng=5.0, imp=1.05, hours=(13, 14, 15, 16, 17)), dict(ktp_mult=4.5, hold=72)),
    ("CALIDAD",          dict(rb=20, max_rng=4.2, imp=1.05, hours=(13, 14, 15, 16, 17)), dict(ktp_mult=4.5, hold=120)),
    ("BALANCE",          dict(rb=18, max_rng=6.0, imp=1.05, hours=(13, 14, 15, 16, 17)), dict(ktp_mult=3.5, hold=120)),
]


def yr(ts):
    return int(pd.Timestamp(int(ts), unit="s").year)


def dd(rs, risk):
    eq, peak, worst = 1.0, 1.0, 0.0
    for r in rs:
        eq *= (1.0 + r * risk / 100.0)
        peak = max(peak, eq)
        worst = min(worst, eq / peak - 1.0)
    return abs(worst) * 100.0


rng = np.random.default_rng(20261124)
print("CANDIDATO   |  n FULL / n OOS | R FULL / R OOS | DD obs@1% | P(DD>15%) @1.0% @1.25% @1.5% | p95 DD @1%")
for name, so, sim in CAND:
    s, _, _ = G.signals(P, **so, buf=0.0, atr_cap=0.16, strict=True, start=260, cache=CACHE)
    tr = G.sim(P, s, **SIM, **sim)
    full = np.array([x["R"] for x in tr])
    oos = np.array([x["R"] for x in tr if yr(x["entry_ts"]) >= 2025])
    probs = []
    for risk in (1.0, 1.25, 1.5):
        boot = np.array([dd(rng.choice(full, size=len(full), replace=True), risk)
                         for _ in range(20000)])
        probs.append(float((boot > 15).mean()) * 100.0)
        if risk == 1.0:
            p95 = float(np.percentile(boot, 95))
    print("%-11s | %4d / %4d       | %+6.1f / %+6.1f | %5.1f%%     | %8.2f%% %8.2f%% %7.2f%% | %5.1f%%" %
          (name, len(full), len(oos), full.sum(), oos.sum(), dd(full, 1.0),
           probs[0], probs[1], probs[2], p95))
