"""Sweep de actividad - fase 2: granularidad, costes y consistencia anual.

Solo lectura. Compara candidatos de mayor frecuencia contra GA-B con:
  * train 2022-2024 / OOS 2025-2026 separados
  * costes normales (spread 0.69) y estresados (spread 1.20)
  * desglose por ano natural
  * sensibilidad a vecinos del parametro elegido
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

m15 = lab.load()
P = G.prep(m15)
T = P["t"]
CACHE = {}

SIG = dict(rb=20, max_rng=3.4, imp=1.05, buf=0.0, hours=(13, 14, 15, 16, 17),
           atr_cap=0.16, strict=True, start=260)
SIM = dict(ksl=5.2, ktp_mult=3.5, tgt=1.25, hold=120, spread=0.69, comm=0.07,
           swap=True)

TRAIN = (2022, 2025)
TEST = (2025, 2027)


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


sigs_cache = {}


def sigs(key, over):
    if key not in sigs_cache:
        s, _, _ = G.signals(P, **{**SIG, **over}, cache=CACHE)
        sigs_cache[key] = s
    return sigs_cache[key]


CAND = [
    ("BASE GA-B", {}),
    ("rango 4.2", {"max_rng": 4.2}),
    ("rango 5.0", {"max_rng": 5.0}),
    ("rango 6.0", {"max_rng": 6.0}),
    ("horas 8-20", {"hours": tuple(range(8, 21))}),
    ("horas 9-19", {"hours": tuple(range(9, 20))}),
    ("8-20 + rango 4.2", {"hours": tuple(range(8, 21)), "max_rng": 4.2}),
    ("8-20 + rango 5.0", {"hours": tuple(range(8, 21)), "max_rng": 5.0}),
    ("9-19 + rango 4.2", {"hours": tuple(range(9, 20)), "max_rng": 4.2}),
    ("rb18 + rango 4.2", {"rb": 18, "max_rng": 4.2}),
    ("rb16 + rango 4.2", {"rb": 16, "max_rng": 4.2}),
    ("rango 4.2 + hold72", {"max_rng": 4.2}),
    ("rango 4.2 + cap 0.25", {"max_rng": 4.2, "atr_cap": 0.25}),
]

print("CANDIDATO                     |    TRAIN 2022-24          |      OOS 2025-26           | OOS spread1.2")
print("                              |  n   PF     R    t    DD   |  n   PF     R    t    DD   |  PF    t")
results = {}
for name, over in CAND:
    s = sigs(name, over)
    sim = SIM
    if "hold72" in name:
        sim = {**SIM, "hold": 72}
    tr = G.sim(P, s, **sim)
    a, b = st(tr, *TRAIN), st(tr, *TEST)
    trs = G.sim(P, s, **{**sim, "spread": 1.20})
    c = st(trs, *TEST)
    results[name] = (a, b, c, tr)
    print("%-29s | %3d %4.2f %+6.1f %+5.2f %4.1f | %3d %4.2f %+6.1f %+5.2f %4.1f | %4.2f %+5.2f" %
          (name, a["n"], a["pf"], a["R"], a["t"], a["dd"],
           b["n"], b["pf"], b["R"], b["t"], b["dd"], c["pf"], c["t"]))

print("\nDESGLOSE ANUAL (n / PF / R) de los finalistas")
for name in ["BASE GA-B", "rango 4.2", "rango 5.0", "8-20 + rango 4.2", "9-19 + rango 4.2"]:
    tr = results[name][3]
    parts = []
    for y in (2022, 2023, 2024, 2025, 2026):
        q = st(tr, y, y + 1)
        parts.append("%d:%2d/%4.2f/%+5.1f" % (y, q["n"], q["pf"], q["R"]))
    print("  %-22s %s" % (name, "  ".join(parts)))

print("\nVECINOS DE 'rango 4.2' (robustez del parametro)")
for rv in (3.8, 4.0, 4.2, 4.4, 4.6, 4.8):
    key = "rango%.1f" % rv
    s = sigs(key, {"max_rng": rv})
    tr = G.sim(P, s, **SIM)
    a, b = st(tr, *TRAIN), st(tr, *TEST)
    print("  rango %.1f | TR %3d PF %4.2f | OOS %3d PF %4.2f t %+5.2f DD %4.1f" %
          (rv, a["n"], a["pf"], b["n"], b["pf"], b["t"], b["dd"]))

print("\nVECINOS DE '9-19 + rango 4.2'")
for rv in (4.0, 4.2, 4.4):
    for hs in [(9, 19), (10, 19)]:
        hours = tuple(range(hs[0], hs[1] + 1))
        key = "h%d-%d_r%.1f" % (hs[0], hs[1], rv)
        s = sigs(key, {"max_rng": rv, "hours": hours})
        tr = G.sim(P, s, **SIM)
        a, b = st(tr, *TRAIN), st(tr, *TEST)
        print("  %-12s | TR %3d PF %4.2f | OOS %3d PF %4.2f t %+5.2f DD %4.1f" %
              (key, a["n"], a["pf"], b["n"], b["pf"], b["t"], b["dd"]))
