"""Shortlist final bajo DD<20%: P(DD>20%) por riesgo y costes estresados."""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import s1_regime_ga as G
import xau_cost_lab as lab

P = G.prep(lab.load())
SIM = dict(ksl=5.2, tgt=1.25, comm=0.07, swap=True)

SHORT = [
    ("A 227 trades 12-18 r6.0 h72", dict(rb=16, max_rng=6.0, imp=1.05, hours=tuple(range(12, 19))), dict(ktp_mult=4.5, hold=72)),
    ("B 158 trades 13-17 r5.0 h96", dict(rb=16, max_rng=5.0, imp=1.05, hours=(13, 14, 15, 16, 17)), dict(ktp_mult=4.5, hold=96)),
    ("C 147 trades 13-17 r4.2 h96", dict(rb=16, max_rng=4.2, imp=1.05, hours=(13, 14, 15, 16, 17)), dict(ktp_mult=4.5, hold=96)),
    ("D 192 trades 13-17 r5.0 h72", dict(rb=16, max_rng=5.0, imp=1.05, hours=(13, 14, 15, 16, 17)), dict(ktp_mult=4.5, hold=72)),
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


def build(so, sim, spread):
    s, _, _ = G.signals(P, **so, buf=0.0, atr_cap=0.16, strict=True,
                        start=260, cache={})
    return G.sim(P, s, **SIM, **sim, spread=spread)


rng = np.random.default_rng(20261124)
print("CANDIDATO                      | riesgo |  n  | R total | retorno% | DD obs | P(DD>20%) | p95 DD | P(DD>15%)")
for name, so, sim in SHORT:
    tr = build(so, sim, 0.69)
    rs = np.array([x["R"] for x in tr])
    oos = [x["R"] for x in tr if yr(x["entry_ts"]) >= 2025]
    for risk in (1.0, 1.25, 1.5, 1.75, 2.0):
        b = np.array([dd(rng.choice(rs, size=len(rs), replace=True), risk)
                      for _ in range(20000)])
        print("%-30s | %5.2f%% | %3d | %+6.1f | %+8.1f | %6.1f%% | %8.2f%% | %6.1f%% | %7.2f%%" %
              (name, risk, len(rs), rs.sum(), rs.sum() * risk, dd(rs, risk),
               100.0 * float((b > 20).mean()), float(np.percentile(b, 95)),
               100.0 * float((b > 15).mean())))
    print("   OOS: n=%d R=%+.1f PF=%.2f | DD OOS@1.5%%=%.1f%%" %
          (len(oos), sum(oos),
           sum(x for x in oos if x > 0) / -sum(x for x in oos if x <= 0),
           dd(oos, 1.5)))

print("\nCOSTES ESTRESADOS (spread 1.20) - DD observado por riesgo")
for name, so, sim in SHORT:
    rs = np.array([x["R"] for x in build(so, sim, 1.20)])
    print("  %-30s n=%d R=%+.1f | DD@1%% %.1f%% @1.5%% %.1f%% @2%% %.1f%%" %
          (name, len(rs), rs.sum(), dd(rs, 1.0), dd(rs, 1.5), dd(rs, 2.0)))
