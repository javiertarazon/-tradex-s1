"""Sweep de actividad: mas trades sin perder el edge validado.

Compara palancas sueltas y combinaciones contra GA-B, separando siempre
train (2022-2024) de OOS (2025-2026). Solo lectura; no escribe resultados.
"""
import math
import sys

import numpy as np
import pandas as pd

HERE = __import__("os").path.dirname(__import__("os").path.abspath(__file__))
sys.path.insert(0, HERE)

import s1_regime_ga as G
import xau_cost_lab as lab

m15 = lab.load()
P = G.prep(m15)
T = P["t"]
CACHE = {}

SIG = dict(rb=20, max_rng=3.4, imp=1.05, buf=0.0, hours=(13, 14, 15, 16, 17),
           atr_cap=0.16, strict=True, start=260)
SIM = dict(ksl=5.2, ktp_mult=3.5, tgt=1.25, hold=120, spread=0.69, comm=0.07, swap=True)

TRAIN = (2022, 2025)   # [lo, hi)
TEST = (2025, 2027)


def year_of(ts):
    return int(pd.Timestamp(int(ts), unit="s").year)


def get_sigs(overrides, strict=None):
    s, _, _ = G.signals(P, **{**SIG, **overrides, "strict": strict if strict is not None else SIG["strict"]},
                        cache=CACHE)
    return s


def stats(tr, lo, hi):
    sel = [x for x in tr if lo <= year_of(x["entry_ts"]) < hi]
    if not sel:
        return dict(n=0, yr=0.0, pf=0.0, R=0.0, t=0.0, dd=0.0)
    R = np.array([x["R"] for x in sel])
    w, l = R[R > 0], R[R <= 0]
    t = R.mean() / (R.std(ddof=1) / math.sqrt(len(R))) if len(R) > 2 and R.std(ddof=1) > 0 else 0.0
    eq = np.cumsum(R)
    return dict(n=len(sel), yr=len(sel) / (hi - lo),
                pf=float(w.sum() / -l.sum()) if len(l) and l.sum() < 0 else 99.0,
                R=float(R.sum()), t=t, dd=float((np.maximum.accumulate(eq) - eq).max()))


def evaluate(name, sig, sim=SIM):
    tr_tr = G.sim(P, [s for s in sig if TRAIN[0] <= year_of(T[s[0]]) < TRAIN[1]], **sim)
    tr_te = G.sim(P, [s for s in sig if TEST[0] <= year_of(T[s[0]]) < TEST[1]], **sim)
    a, b = stats(tr_tr, *TRAIN), stats(tr_te, *TEST)
    print("%-42s | TR %4d %5.1f/a PF %4.2f R %+6.1f t %+4.2f | OOS %4d %5.1f/a PF %4.2f R %+6.1f t %+4.2f DD %4.1f" %
          (name, a["n"], a["yr"], a["pf"], a["R"], a["t"],
           b["n"], b["yr"], b["pf"], b["R"], b["t"], b["dd"]))
    return name, a, b


base = get_sigs({})
rows = [evaluate("BASE GA-B (46 trades/3anos en tester)", base)]

# --- palancas sueltas
rows.append(evaluate("strict OFF (ambos lados)", get_sigs({}, strict=False)))
short_only = sorted([s for s in base if s[1] > 0] + [s for s in get_sigs({}, strict=False) if s[1] < 0],
                    key=lambda x: x[0])
rows.append(evaluate("strict OFF solo SHORT", short_only))
rows.append(evaluate("horas 9-19", get_sigs({"hours": tuple(range(9, 20))})))
rows.append(evaluate("horas 8-20", get_sigs({"hours": tuple(range(8, 21))})))
rows.append(evaluate("rb 16", get_sigs({"rb": 16})))
rows.append(evaluate("max_rng 5.0", get_sigs({"max_rng": 5.0})))
rows.append(evaluate("impulso 0.9", get_sigs({"imp": 0.9})))
rows.append(evaluate("ATR cap 0.25", get_sigs({"atr_cap": 0.25})))
rows.append(evaluate("hold 48", base, {**SIM, "hold": 48}))
rows.append(evaluate("hold 72", base, {**SIM, "hold": 72}))

# --- combinaciones moderadas
rows.append(evaluate("horas 9-19 + hold 72", get_sigs({"hours": tuple(range(9, 20))}),
                     {**SIM, "hold": 72}))
rows.append(evaluate("horas 9-19 + imp 0.9 + hold 72", get_sigs({"hours": tuple(range(9, 20)), "imp": 0.9}),
                     {**SIM, "hold": 72}))
rows.append(evaluate("strict OFF short + hold 72", short_only, {**SIM, "hold": 72}))
rows.append(evaluate("horas 9-19 + rb16 + hold 72", get_sigs({"hours": tuple(range(9, 20)), "rb": 16}),
                     {**SIM, "hold": 72}))

print("\nSELECCION: OOS con PF>=2, t>=2 y mas trades/anio que la base")
base_oos = rows[0][2]["yr"]
cands = [r for r in rows[1:] if r[2]["pf"] >= 2.0 and r[2]["t"] >= 2.0 and r[2]["yr"] > base_oos]
for name, a, b in sorted(cands, key=lambda r: -r[2]["yr"]):
    print("  %-42s OOS %5.1f/a PF %4.2f t %+4.2f (x%.2f)" %
          (name, b["yr"], b["pf"], b["t"], b["yr"] / base_oos))
if not cands:
    print("  NINGUNO: mas actividad implica perder PF o significancia.")
