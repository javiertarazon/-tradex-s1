"""Analisis detallado de finalistas de activity_opt.py.

Ano a ano, DD compuesto exacto a 1.0% y 1.5% de riesgo, estres de costes y
robustez de vecinos. Solo lectura.
"""
import math
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
SIM_BASE = dict(ksl=5.2, tgt=1.25, spread=0.69, comm=0.07, swap=True)

FIN = [
    ("BASE GA-B",              dict(rb=20, max_rng=3.4, imp=1.05, hours=(13, 14, 15, 16, 17)), dict(hold=120, ktp_mult=3.5)),
    ("MAX_TRADES 16/6.0/12-18", dict(rb=16, max_rng=6.0, imp=1.05, hours=tuple(range(12, 19))), dict(hold=72, ktp_mult=4.5)),
    ("BALANCE 18/6.0/13-17",   dict(rb=18, max_rng=6.0, imp=1.05, hours=(13, 14, 15, 16, 17)), dict(hold=120, ktp_mult=3.5)),
    ("MIXTO 16/5.0/13-17",     dict(rb=16, max_rng=5.0, imp=1.05, hours=(13, 14, 15, 16, 17)), dict(hold=72, ktp_mult=4.5)),
    ("CALIDAD 20/4.2/13-17",   dict(rb=20, max_rng=4.2, imp=1.05, hours=(13, 14, 15, 16, 17)), dict(hold=120, ktp_mult=4.5)),
]


def yr(ts):
    return int(pd.Timestamp(int(ts), unit="s").year)


def stats(tr, lo=2022, hi=2027):
    sel = [x for x in tr if lo <= yr(x["entry_ts"]) < hi]
    if not sel:
        return dict(n=0, pf=0.0, R=0.0, t=0.0)
    R = np.array([x["R"] for x in sel])
    w, l = R[R > 0], R[R <= 0]
    t = float(R.mean() / (R.std(ddof=1) / math.sqrt(len(R)))) if len(R) > 2 and R.std(ddof=1) > 0 else 0.0
    return dict(n=len(sel), pf=float(w.sum() / -l.sum()) if len(l) and l.sum() < 0 else 99.0,
                R=float(R.sum()), t=t)


def dd_comp(tr, lo, hi, risk):
    sel = [x["R"] for x in tr if lo <= yr(x["entry_ts"]) < hi]
    eq, peak, worst = 1.0, 1.0, 0.0
    for r in sel:
        eq *= (1.0 + r * risk / 100.0)
        peak = max(peak, eq)
        worst = min(worst, eq / peak - 1.0)
    return abs(worst) * 100.0


def build(sig_over, sim_over, spread=0.69):
    s, _, _ = G.signals(P, rb=sig_over["rb"], max_rng=sig_over["max_rng"],
                        imp=sig_over["imp"], buf=0.0, hours=sig_over["hours"],
                        atr_cap=0.16, strict=True, start=260, cache=CACHE)
    return G.sim(P, s, **{**SIM_BASE, **sim_over, "spread": spread})


print("CANDIDATO                    | FULL n    R    PF   t  | OOS n    R    PF   t  |2024-26 n    R  | DDcomp@1% FULL/OOS | DDcomp@1.5% FULL/OOS")
for name, so, o in FIN:
    tr = build(so, o)
    f, q, v = stats(tr), stats(tr, 2025, 2027), stats(tr, 2024, 2027)
    d1 = (dd_comp(tr, 2022, 2027, 1.0), dd_comp(tr, 2025, 2027, 1.0))
    d15 = (dd_comp(tr, 2022, 2027, 1.5), dd_comp(tr, 2025, 2027, 1.5))
    print("%-27s | %5d %+6.1f %4.2f %+5.2f | %4d %+6.1f %4.2f %+5.2f | %5d %+6.1f | %5.1f / %5.1f       | %5.1f / %5.1f" %
          (name, f["n"], f["R"], f["pf"], f["t"], q["n"], q["R"], q["pf"], q["t"],
           v["n"], v["R"], d1[0], d1[1], d15[0], d15[1]))

print("\nDESGLOSE ANUAL (n / R / PF)")
for name, so, o in FIN:
    tr = build(so, o)
    parts = []
    for y in (2022, 2023, 2024, 2025, 2026):
        q = stats(tr, y, y + 1)
        parts.append("%d:%3d/%+6.1f/%4.2f" % (y, q["n"], q["R"], q["pf"]))
    print("  %-27s %s" % (name, " ".join(parts)))

print("\nCOSTES ESTRESADOS (spread 1.20) - OOS")
for name, so, o in FIN:
    tr = build(so, o, spread=1.20)
    q = stats(tr, 2025, 2027)
    print("  %-27s OOS %4d trades R %+6.1f PF %4.2f t %+5.2f" % (name, q["n"], q["R"], q["pf"], q["t"]))

print("\nVECINOS DE 'MIXTO 16/5.0/13-17' (rango y hold)")
for rv in (4.2, 5.0, 6.0):
    for hd in (48, 72, 96):
        so = dict(rb=16, max_rng=rv, imp=1.05, hours=(13, 14, 15, 16, 17))
        o = dict(hold=hd, ktp_mult=4.5)
        tr = build(so, o)
        f, q = stats(tr), stats(tr, 2025, 2027)
        print("  rng %.1f hold %3d | FULL %3d R %+6.1f PF %4.2f | OOS %3d R %+6.1f PF %4.2f t %+5.2f | DD1%% %4.1f DD1.5%% %4.1f" %
              (rv, hd, f["n"], f["R"], f["pf"], q["n"], q["R"], q["pf"], q["t"],
               dd_comp(tr, 2022, 2027, 1.0), dd_comp(tr, 2022, 2027, 1.5)))

print("\nVECINOS DE 'CALIDAD 20/4.2/13-17' (KTP y hold)")
for km in (3.5, 4.0, 4.5, 5.0):
    for hd in (96, 120, 160):
        so = dict(rb=20, max_rng=4.2, imp=1.05, hours=(13, 14, 15, 16, 17))
        o = dict(hold=hd, ktp_mult=km)
        tr = build(so, o)
        f, q = stats(tr), stats(tr, 2025, 2027)
        print("  ktp %.1f hold %3d | FULL %3d R %+6.1f PF %4.2f | OOS %3d R %+6.1f PF %4.2f t %+5.2f | DD1%% %4.1f DD1.5%% %4.1f" %
              (km, hd, f["n"], f["R"], f["pf"], q["n"], q["R"], q["pf"], q["t"],
               dd_comp(tr, 2022, 2027, 1.0), dd_comp(tr, 2022, 2027, 1.5)))
