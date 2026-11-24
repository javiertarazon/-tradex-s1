"""Chequeo final de riesgo del candidato MIXTO antes de desplegarlo.

DD compuesto exacto a varios niveles de riesgo y bajo tres escenarios de coste.
Bootstrap simple del DD para estimar P(DD > 15%). Solo lectura.
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import s1_regime_ga as G
import xau_cost_lab as lab

P = G.prep(lab.load())
SO = dict(rb=16, max_rng=5.0, imp=1.05, hours=(13, 14, 15, 16, 17))
SIM = dict(ksl=5.2, ktp_mult=4.5, tgt=1.25, hold=72, comm=0.07, swap=True)


def yr(ts):
    import pandas as pd
    return int(pd.Timestamp(int(ts), unit="s").year)


def build(spread):
    s, _, _ = G.signals(P, **SO, buf=0.0, atr_cap=0.16, strict=True,
                        start=260, cache={})
    return G.sim(P, s, **SIM, spread=spread)


def dd(rs, risk):
    eq, peak, worst = 1.0, 1.0, 0.0
    for r in rs:
        eq *= (1.0 + r * risk / 100.0)
        peak = max(peak, eq)
        worst = min(worst, eq / peak - 1.0)
    return abs(worst) * 100.0


print("CANDIDATO MIXTO: rb16 rng5.0 imp1.05 13-17 hold72 KSL5.2 KTP23.4")
rng = np.random.default_rng(20261124)
for spread in (0.69, 0.90, 1.20):
    tr = build(spread)
    full = [x["R"] for x in tr]
    oos = [x["R"] for x in tr if yr(x["entry_ts"]) >= 2025]
    line = "spread %.2f | n=%d R=%+.1f | " % (spread, len(full), sum(full))
    for risk in (1.0, 1.25, 1.5):
        line += "DD@%.2f%%=%4.1f%% " % (risk, dd(full, risk))
    print(line)
    if spread == 0.69:
        boot = np.array([dd(rng.choice(full, size=len(full), replace=True), 1.5)
                         for _ in range(20000)])
        print("   bootstrap 20k @1.5%%: p50=%.1f%% p95=%.1f%% p99=%.1f%% P(DD>15%%)=%.2f%%" %
              (np.percentile(boot, 50), np.percentile(boot, 95),
               np.percentile(boot, 99), 100.0 * float((boot > 15).mean())))
        print("   OOS R=%+.1f n=%d | DD OOS@1.5%%=%.1f%%" %
              (sum(oos), len(oos), dd(oos, 1.5)))
