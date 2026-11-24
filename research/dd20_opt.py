"""Optimizacion con restriccion de DD < 20% y prioridad a trades + balance.

Nuevo requerimiento del usuario: mas frecuencia y mas PnL; DD puede subir
siempre que no supere el 20%. Se evaluan tambien niveles de riesgo 1.0/1.5/2.0%.
Solo lectura.
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
SIM = dict(ksl=5.2, tgt=1.25, spread=0.69, comm=0.07, swap=True)
RISKS = (1.0, 1.5, 2.0)
DD_LIMIT = 20.0


def yr(ts):
    return int(pd.Timestamp(int(ts), unit="s").year)


def st(rs, lo, hi):
    sel = [x for x in rs if lo <= yr(x["entry_ts"]) < hi]
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


GRID = dict(
    rb=[16, 18, 20],
    rng=[4.2, 5.0, 6.0],
    imp=[0.95, 1.05],
    hours=[(13, 14, 15, 16, 17), tuple(range(12, 19)), tuple(range(9, 20))],
    hold=[72, 96, 120],
    ktp=[3.5, 4.5],
)
rows = []
for rb, rng, imp, hours, hold, ktp in itertools.product(
        GRID["rb"], GRID["rng"], GRID["imp"], GRID["hours"], GRID["hold"], GRID["ktp"]):
    s, _, _ = G.signals(P, rb=rb, max_rng=rng, imp=imp, buf=0.0, hours=hours,
                        atr_cap=0.16, strict=True, start=260, cache=CACHE)
    tr = G.sim(P, s, **SIM, ktp_mult=ktp, hold=hold)
    f, q = st(tr, 2022, 2027), st(tr, 2025, 2027)
    if f["n"] < 60 or q["n"] < 20 or f["pf"] < 1.4 or q["pf"] < 1.8:
        continue
    all_r = [x["R"] for x in tr]
    for risk in RISKS:
        d = dd(all_r, risk)
        if d >= DD_LIMIT:
            continue
        rows.append(dict(rb=rb, rng=rng, imp=imp, hours=hours, hold=hold,
                         ktp=ktp, risk=risk, f=f, q=q, dd=d,
                         allR=all_r))

print("supervivientes: %d (DD < %.0f%%)" % (len(rows), DD_LIMIT))
rows.sort(key=lambda x: -(x["f"]["n"] + x["f"]["R"] * x["risk"] * 1.5))
print("\nTOP 25 POR COMPUESTO (trades + 1.5*retorno%%)")
print("rb rng imp  horas hold ktp rsk | FULL n   R   PF   DD%% | OOS n   R   PF  | retorno%%(full/oos)")
for x in rows[:25]:
    f, q = x["f"], x["q"]
    hs = "%d-%d" % (x["hours"][0], x["hours"][-1])
    print("%2d %4.1f %4.2f %-6s %4d %4.1f %4.1f | %4d %+6.1f %4.2f %5.1f | %3d %+6.1f %4.2f | %6.1f / %6.1f" %
          (x["rb"], x["rng"], x["imp"], hs, x["hold"], x["ktp"], x["risk"],
           f["n"], f["R"], f["pf"], x["dd"], q["n"], q["R"], q["pf"],
           f["R"] * x["risk"], q["R"] * x["risk"]))

print("\nTOP 15 POR TRADES (DD<20%)")
for x in sorted(rows, key=lambda r: -r["f"]["n"])[:15]:
    f, q = x["f"], x["q"]
    hs = "%d-%d" % (x["hours"][0], x["hours"][-1])
    print("%2d %4.1f %4.2f %-6s %4d %4.1f r%.1f | FULL %3d R%+6.1f PF%4.2f DD%4.1f | OOS %3d R%+6.1f PF%4.2f" %
          (x["rb"], x["rng"], x["imp"], hs, x["hold"], x["ktp"], x["risk"],
           f["n"], f["R"], f["pf"], x["dd"], q["n"], q["R"], q["pf"]))

print("\nTOP 15 POR RETORNO (R*riesgo, DD<20%)")
for x in sorted(rows, key=lambda r: -r["f"]["R"] * r["risk"])[:15]:
    f, q = x["f"], x["q"]
    hs = "%d-%d" % (x["hours"][0], x["hours"][-1])
    print("%2d %4.1f %4.2f %-6s %4d %4.1f r%.1f | FULL %3d R%+6.1f ret%+6.1f%% PF%4.2f DD%4.1f | OOS %3d R%+6.1f" %
          (x["rb"], x["rng"], x["imp"], hs, x["hold"], x["ktp"], x["risk"],
           f["n"], f["R"], f["R"] * x["risk"], f["pf"], x["dd"], q["n"], q["R"]))

print("\nBOOTSTRAP P(DD>20%%) de los 8 mejores por compuesto")
rngnp = np.random.default_rng(20261124)
for x in rows[:8]:
    b = np.array([dd(rngnp.choice(x["allR"], size=len(x["allR"]), replace=True), x["risk"])
                  for _ in range(20000)])
    print("rb%d r%.1f h%d-%d hold%d ktp%.1f r%.1f%% | n=%d ret=%.1f%% DD=%.1f%% P>20%%=%.2f%% p95=%.1f%%" %
          (x["rb"], x["rng"], x["hours"][0], x["hours"][-1], x["hold"], x["ktp"], x["risk"],
           x["f"]["n"], x["f"]["R"] * x["risk"], x["dd"],
           100.0 * float((b > 20).mean()), float(np.percentile(b, 95))))
