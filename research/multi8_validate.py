"""Validacion final de la config multi8 h72 antes de desplegarla.

- DD desde maximo historico (ATH), no desde pico reiniciado
- bootstrap P(DD>20%)
- desglose por ano y direccion
- comparativa con la config multi6 vigente
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from multi_risk_guard_sweep import SIG, sim_fast, take_n, equity, pf_of

CFG = dict(hold=72, ktp=4.5, n=8, risk=1.10, th=16.0)
OLD = dict(hold=96, ktp=3.5, n=6, risk=0.75, th=14.0)


def build(cfg, spread):
    return take_n(sim_fast(SIG, cfg["ktp"], cfg["hold"], spread), cfg["n"])


def boot_dd(tr, risk, th, nboot=20000, seed=20261124):
    R = np.array([x["R"] for x in tr])
    rng = np.random.default_rng(seed)
    out = np.empty(nboot)
    for b in range(nboot):
        sample = rng.choice(R, size=len(R), replace=True)
        eq, pk, ath, worst = 1.0, 1.0, 1.0, 0.0
        lock = 0
        for k, r in enumerate(sample):
            eq *= (1.0 + r * risk / 100.0)
            pk = max(pk, eq)
            ath = max(ath, eq)
            worst = min(worst, eq / ath - 1.0)
            if 100.0 * (pk - eq) / pk >= th:
                lock = k + 192  # 48h ~ 192 velas M15
                pk = eq
        out[b] = abs(worst) * 100.0
    return out


for label, cfg in (("NUEVA multi8 h72", CFG), ("VIGENTE multi6 h96", OLD)):
    base = build(cfg, 0.69)
    stress = build(cfg, 1.20)
    ret, dd, trig = equity(base, cfg["risk"], cfg["th"])
    _, dds, _ = equity(stress, cfg["risk"], cfg["th"])
    b = boot_dd(base, cfg["risk"], cfg["th"])
    print("\n=== %s ===" % label)
    print("hold=%d ktp=%.1f n=%d riesgo=%.2f%% guarda=%.1f%%" %
          (cfg["hold"], cfg["ktp"], cfg["n"], cfg["risk"], cfg["th"]))
    print("trades=%d  retorno=%+.1f%%  PF=%.2f  OOS_PF=%.2f  DDobs=%.1f%% DDstr=%.1f%% disparos=%d" %
          (len(base), ret, pf_of(base),
           pf_of([x for x in base if pd.Timestamp(x["entry_ts"], unit="s").year >= 2025]),
           dd, dds, trig))
    print("bootstrap P(DD>20%%)=%.2f%%  p95 DD=%.1f%%  mediana=%.1f%%" %
          (100.0 * (b > 20).mean(), np.percentile(b, 95), np.median(b)))
    print("\nanio  trades  long short   R     PF")
    for y in range(2022, 2027):
        yr_tr = [x for x in base if pd.Timestamp(x["entry_ts"], unit="s").year == y]
        if not yr_tr:
            continue
        print("%d  %5d  %4d %5d  %+6.1f  %4.2f" %
              (y, len(yr_tr), sum(1 for x in yr_tr if x["side"] > 0),
               sum(1 for x in yr_tr if x["side"] < 0),
               sum(x["R"] for x in yr_tr), pf_of(yr_tr)))
