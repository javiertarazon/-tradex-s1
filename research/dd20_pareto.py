"""Frontera Pareto frecuencia vs retorno con DD < 20% duro.

Filtros:
  - DD observado a 1.5% < 18%
  - DD estresado (spread 1.20) a 1.5% < 19%
  - OOS PF >= 2.0  (evita sobreajuste)
  - bootstrap P(DD>20%) < 5%

Objetivo: encontrar configuraciones que superen al preset actual en
frecuencia Y en retorno. Solo lectura.
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

P = G.prep(lab.load())
CACHE = {}
SIM = dict(ksl=5.2, tgt=1.25, comm=0.07, swap=True)
HOURS_SETS = [(13, 14, 15, 16, 17), tuple(range(12, 19)), tuple(range(9, 20))]
RISKS = (1.25, 1.5, 1.75)
BOOT = 5000  # cribado; los finalistas se revalidan con 20000 en otro script


def yr(ts):
    return int(pd.Timestamp(int(ts), unit="s").year)


def st(rs, lo, hi):
    sel = [x for x in rs if lo <= yr(x["entry_ts"]) < hi]
    if not sel:
        return dict(n=0, R=0.0, pf=0.0)
    R = np.array([x["R"] for x in sel])
    w, l = R[R > 0], R[R <= 0]
    return dict(n=len(sel), R=float(R.sum()),
                pf=float(w.sum() / -l.sum()) if len(l) and l.sum() < 0 else 99.0)


def dd(rs, risk):
    eq, peak, worst = 1.0, 1.0, 0.0
    for r in rs:
        eq *= (1.0 + r * risk / 100.0)
        peak = max(peak, eq)
        worst = min(worst, eq / peak - 1.0)
    return abs(worst) * 100.0


rows = []
for rb, rng, imp, hours, hold, ktp in itertools.product(
        [16, 18, 20], [4.2, 5.0, 6.0], [0.95, 1.05], HOURS_SETS,
        [72, 96, 120], [3.5, 4.5]):
    s, _, _ = G.signals(P, rb=rb, max_rng=rng, imp=imp, buf=0.0, hours=hours,
                        atr_cap=0.16, strict=True, start=260, cache=CACHE)
    tr = G.sim(P, s, **SIM, ktp_mult=ktp, hold=hold, spread=0.69)
    trs = G.sim(P, s, **SIM, ktp_mult=ktp, hold=hold, spread=1.20)
    rs = np.array([x["R"] for x in tr])
    q = st(tr, 2025, 2027)
    f = st(tr, 2022, 2027)
    if q["pf"] < 2.0 or f["n"] < 100:
        continue
    for risk in RISKS:
        d = dd(rs, risk)
        ds = dd([x["R"] for x in trs], risk)
        if d >= 18.0 or ds >= 19.0:
            continue
        rows.append(dict(rb=rb, rng=rng, imp=imp, hours=hours, hold=hold,
                         ktp=ktp, risk=risk, f=f, q=q, dd=d, dds=ds, rs=rs))

print("supervivientes (DD<18%% obs, <19%% estresado, OOS PF>=2): %d" % len(rows))

# --- frontera Pareto en (n_trades, retorno)
best = {}
for x in rows:
    key = (x["f"]["n"], round(x["f"]["R"] * x["risk"], 1))
    if key not in best:
        best[key] = x
pts = sorted(best.values(), key=lambda x: x["f"]["n"])
pareto = []
for x in pts:
    ret = x["f"]["R"] * x["risk"]
    if any(y["f"]["R"] * y["risk"] >= ret and y["f"]["n"] >= x["f"]["n"]
           and (y["f"]["R"] * y["risk"] > ret or y["f"]["n"] > x["f"]["n"])
           for y in rows):
        continue
    pareto.append(x)

rngnp = np.random.default_rng(20261124)
print("\nFRONTERA PARETO (no dominadas): n / retorno")
print("rb rng imp  horas hold ktp rsk | FULL  n    R  retorno%%  PF | OOS  n    R  PF | DDobs DDstr | P>20%%")
for x in pareto:
    b = np.array([dd(rngnp.choice(x["rs"], size=len(x["rs"]), replace=True), x["risk"])
                  for _ in range(BOOT)])
    p = 100.0 * float((b > 20).mean())
    if p >= 5.0:
        continue
    f, q = x["f"], x["q"]
    hs = "%d-%d" % (x["hours"][0], x["hours"][-1])
    print("%2d %4.1f %4.2f %-6s %4d %4.1f %4.1f | %4d %+6.1f %+7.1f %4.2f | %3d %+6.1f %4.2f | %5.1f %5.1f | %5.2f%%" %
          (x["rb"], x["rng"], x["imp"], hs, x["hold"], x["ktp"], x["risk"],
           f["n"], f["R"], f["R"] * x["risk"], f["pf"],
           q["n"], q["R"], q["pf"], x["dd"], x["dds"], p))

print("\nMEJORES POR COMPUESTO n + retorno%% (con bootstrap P>20%% < 5%%)")
cands = []
for x in rows:
    b = np.array([dd(rngnp.choice(x["rs"], size=len(x["rs"]), replace=True), x["risk"])
                  for _ in range(BOOT)])
    p = 100.0 * float((b > 20).mean())
    if p < 5.0:
        cands.append((x["f"]["n"] + x["f"]["R"] * x["risk"], x, p))
cands.sort(key=lambda z: -z[0])
print("score  rb rng imp  horas hold ktp rsk | FULL  n    R  retorno%%  PF | OOS  n    R  PF | DDobs DDstr | P>20%%")
for score, x, p in cands[:25]:
    f, q = x["f"], x["q"]
    hs = "%d-%d" % (x["hours"][0], x["hours"][-1])
    print("%5.0f %2d %4.1f %4.2f %-6s %4d %4.1f %4.1f | %4d %+6.1f %+7.1f %4.2f | %3d %+6.1f %4.2f | %5.1f %5.1f | %5.2f%%" %
          (score, x["rb"], x["rng"], x["imp"], hs, x["hold"], x["ktp"], x["risk"],
           f["n"], f["R"], f["R"] * x["risk"], f["pf"],
           q["n"], q["R"], q["pf"], x["dd"], x["dds"], p))
