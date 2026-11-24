"""Refinamiento de la zona rb16/rango4.2/hold96 + bootstrap de los mejores."""
import itertools
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
HOURS = (13, 14, 15, 16, 17)


def yr(ts):
    return int(pd.Timestamp(int(ts), unit="s").year)


def st(tr, lo, hi):
    sel = [x for x in tr if lo <= yr(x["entry_ts"]) < hi]
    if not sel:
        return dict(n=0, R=0.0, pf=0.0, t=0.0)
    R = np.array([x["R"] for x in sel])
    w, l = R[R > 0], R[R <= 0]
    t = float(R.mean() / (R.std(ddof=1) / math.sqrt(len(R)))) if len(R) > 2 and R.std(ddof=1) > 0 else 0.0
    return dict(n=len(sel), R=float(R.sum()),
                pf=float(w.sum() / -l.sum()) if len(l) and l.sum() < 0 else 99.0, t=t)


def dd(rs, risk):
    eq, peak, worst = 1.0, 1.0, 0.0
    for r in rs:
        eq *= (1.0 + r * risk / 100.0)
        peak = max(peak, eq)
        worst = min(worst, eq / peak - 1.0)
    return abs(worst) * 100.0


import math
rows = []
for rb, rng, hold, ktp in itertools.product([16, 18, 20], [4.2, 5.0], [84, 96, 108, 120], [4.0, 4.5]):
    s, _, _ = G.signals(P, rb=rb, max_rng=rng, imp=1.05, buf=0.0, hours=HOURS,
                        atr_cap=0.16, strict=True, start=260, cache=CACHE)
    tr = G.sim(P, s, **SIM, ktp_mult=ktp, hold=hold)
    f, q = st(tr, 2022, 2027), st(tr, 2025, 2027)
    d1 = dd([x["R"] for x in tr], 1.0)
    if d1 > 12.0 or q["pf"] < 2.5:
        continue
    rows.append(dict(rb=rb, rng=rng, hold=hold, ktp=ktp, f=f, q=q, d1=d1,
                     allR=np.array([x["R"] for x in tr])))

rows.sort(key=lambda x: -(x["f"]["R"] + x["f"]["n"] * 0.25))
print("REFINAMIENTO (DD@1%% <= 12%%, OOS PF >= 2.5) - ordenado por R + 0.25*n")
print("rb rng hold ktp |  FULL  n    R   PF   t  |  OOS  n    R   PF   t  | DD@1%")
for x in rows[:22]:
    print("%2d %4.1f %4d %4.1f | %5d %+6.1f %4.2f %+5.2f | %4d %+6.1f %4.2f %+5.2f | %5.1f" %
          (x["rb"], x["rng"], x["hold"], x["ktp"],
           x["f"]["n"], x["f"]["R"], x["f"]["pf"], x["f"]["t"],
           x["q"]["n"], x["q"]["R"], x["q"]["pf"], x["q"]["t"], x["d1"]))

print("\nBOOTSTRAP P(DD>15%) de los 6 mejores")
rngnp = np.random.default_rng(20261124)
for x in rows[:6]:
    probs = []
    for risk in (1.0, 1.25):
        b = np.array([dd(rngnp.choice(x["allR"], size=len(x["allR"]), replace=True), risk)
                      for _ in range(20000)])
        probs.append(100.0 * float((b > 15).mean()))
    print("rb%d rng%.1f hold%d ktp%.1f | n=%d R=%+.1f | P>15%% @1%%=%.2f%% @1.25%%=%.2f%%" %
          (x["rb"], x["rng"], x["hold"], x["ktp"], x["f"]["n"], x["f"]["R"], probs[0], probs[1]))
