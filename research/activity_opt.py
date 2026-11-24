"""Optimizacion de actividad con restriccion dura de drawdown < 15%.

Objetivo del usuario: mas trades y mas balance, con DD por debajo del 15%.
Estrategia:
  1) grid sobre palancas de entrada y salida (strict trend se mantiene ON)
  2) restriccion: DD_R * riesgo < 15% en TODO el periodo y en OOS
  3) primary sort: n_trades, secondary: R total
  4) se imprimen tambien PF, t y el desglose train/OOS de cada finalista
Solo lectura; no escribe resultados.
"""
import itertools
import math
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import s1_regime_ga as G
import xau_cost_lab as lab

m15 = lab.load()
P = G.prep(m15)
T = P["t"]
CACHE = {}

SIM_BASE = dict(ksl=5.2, tgt=1.25, spread=0.69, comm=0.07, swap=True)
RISK = 1.0        # riesgo por trade usado para convertir DD_R a DD%
DD_LIMIT = 15.0   # % maximo de drawdown de equity


def yr(ts):
    return int(pd.Timestamp(int(ts), unit="s").year)


def st(tr, lo, hi):
    sel = [x for x in tr if lo <= yr(x["entry_ts"]) < hi]
    if not sel:
        return dict(n=0, pf=0.0, R=0.0, t=0.0, dd=0.0)
    R = np.array([x["R"] for x in sel])
    w, l = R[R > 0], R[R <= 0]
    t = float(R.mean() / (R.std(ddof=1) / math.sqrt(len(R)))) if len(R) > 2 and R.std(ddof=1) > 0 else 0.0
    eq = np.cumsum(R)
    return dict(n=len(sel), pf=float(w.sum() / -l.sum()) if len(l) and l.sum() < 0 else 99.0,
                R=float(R.sum()), t=t, dd=float((np.maximum.accumulate(eq) - eq).max()))


GRID_SIG = {
    "rb": [16, 18, 20, 22],
    "max_rng": [3.4, 4.2, 5.0, 6.0],
    "imp": [0.95, 1.05],
    "hours": [(13, 14, 15, 16, 17), (12, 13, 14, 15, 16, 17, 18),
              tuple(range(9, 20)), tuple(range(8, 21))],
}
GRID_SIM = {
    "hold": [72, 120, 160],
    "ktp_mult": [3.5, 4.5],
}

rows = []
combos = 0
for rb, rng, imp, hours, hold, ktp in itertools.product(
        GRID_SIG["rb"], GRID_SIG["max_rng"], GRID_SIG["imp"], GRID_SIG["hours"],
        GRID_SIM["hold"], GRID_SIM["ktp_mult"]):
    combos += 1
    s, _, _ = G.signals(P, rb=rb, max_rng=rng, imp=imp, buf=0.0, hours=hours,
                        atr_cap=0.16, strict=True, start=260, cache=CACHE)
    tr = G.sim(P, s, **SIM_BASE, ktp_mult=ktp, hold=hold)
    full = st(tr, 2022, 2027)
    oos = st(tr, 2025, 2027)
    ver = st(tr, 2024, 2027)
    if full["n"] < 40 or oos["n"] < 12:
        continue
    if full["pf"] < 1.5 or oos["pf"] < 1.5:
        continue
    # restriccion dura de DD sobre el riesgo preparado
    if full["dd"] * RISK >= DD_LIMIT or oos["dd"] * RISK >= DD_LIMIT:
        continue
    rows.append(dict(rb=rb, rng=rng, imp=imp, hours=hours, hold=hold, ktp=ktp,
                     full=full, oos=oos, ver=ver, sig=s))

print("combinaciones evaluadas: %d | supervivientes: %d | riesgo %.1f%% | DD limite %.0f%%" %
      (combos, len(rows), RISK, DD_LIMIT))

rows.sort(key=lambda x: (-x["full"]["n"], -x["full"]["R"]))

print("\nTOP 20 POR NUMERO DE TRADES (DD < 15% en full y OOS)")
print("rb rng imp  horas   hold ktp |  FULL:  n   R     PF   DD%   t  |  OOS:  n   R     PF   DD%   t  | 2024-26: n   R")
for x in rows[:20]:
    f, o, v = x["full"], x["oos"], x["ver"]
    hs = "%d-%d" % (x["hours"][0], x["hours"][-1])
    print("%2d %4.1f %4.2f %-7s %4d %4.1f | %5d %+6.1f %4.2f %4.1f %+5.2f | %4d %+6.1f %4.2f %4.1f %+5.2f | %4d %+6.1f" %
          (x["rb"], x["rng"], x["imp"], hs, x["hold"], x["ktp"],
           f["n"], f["R"], f["pf"], f["dd"] * RISK, f["t"],
           o["n"], o["R"], o["pf"], o["dd"] * RISK, o["t"],
           v["n"], v["R"]))

print("\nTOP 15 POR BALANCE (R total), mismo filtro")
for x in sorted(rows, key=lambda r: -r["full"]["R"])[:15]:
    f, o = x["full"], x["oos"]
    hs = "%d-%d" % (x["hours"][0], x["hours"][-1])
    print("%2d %4.1f %4.2f %-7s %4d %4.1f | FULL %4d %+6.1f PF %4.2f DD%4.1f | OOS %3d %+6.1f PF %4.2f DD%4.1f" %
          (x["rb"], x["rng"], x["imp"], hs, x["hold"], x["ktp"],
           f["n"], f["R"], f["pf"], f["dd"] * RISK,
           o["n"], o["R"], o["pf"], o["dd"] * RISK))

# --- comparacion con la referencia
s0, _, _ = G.signals(P, rb=20, max_rng=3.4, imp=1.05, buf=0.0,
                     hours=(13, 14, 15, 16, 17), atr_cap=0.16, strict=True,
                     start=260, cache=CACHE)
tr0 = G.sim(P, s0, **SIM_BASE, ktp_mult=3.5, hold=120)
print("\nREFERENCIA GA-B: FULL %s | OOS %s | 2024-26 %s" %
      (st(tr0, 2022, 2027), st(tr0, 2025, 2027), st(tr0, 2024, 2027)))
