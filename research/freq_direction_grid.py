"""Fase A/B: por que hay tan pocas compras y donde estan las senales perdidas.

A: grid vectorizado de senales (barato) con desglose long/short.
B: simulate single-position sobre los finalistas para cribar calidad.

Solo lectura. No modifica ningun archivo de configuracion.
"""
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
SIM = dict(ksl=5.2, tgt=1.25, comm=0.07, swap=True, spread=0.69)
CACHE = {}


def yr(ts):
    return int(pd.Timestamp(int(ts), unit="s").year)


def st(tr, lo=2022, hi=2027):
    sel = [x for x in tr if lo <= yr(x["entry_ts"]) < hi]
    if not sel:
        return 0, 0.0, 0.0
    R = np.array([x["R"] for x in sel])
    w, l = R[R > 0], R[R <= 0]
    return len(sel), float(R.sum()), float(w.sum() / -l.sum()) if len(l) and l.sum() < 0 else 99.0


def dd(rs, risk=1.0):
    eq, pk, worst = 1.0, 1.0, 0.0
    for r in rs:
        eq *= (1.0 + r * risk / 100.0)
        pk = max(pk, eq)
        worst = min(worst, eq / pk - 1.0)
    return abs(worst) * 100.0


# ---------- diagnostico del preset actual ----------
s0, _, _ = G.signals(P, rb=16, max_rng=6.0, imp=1.05, hours=tuple(range(12, 19)),
                     buf=0.0, atr_cap=0.16, strict=True, start=260, cache={})
tr0 = G.sim(P, s0, **SIM, ktp_mult=3.5, hold=96)
nl = sum(1 for x in s0 if x[1] > 0)
ns = sum(1 for x in s0 if x[1] < 0)
print("=== PRESET ACTUAL ===")
print("senales: %d long / %d short (long %.1f%%)" % (nl, ns, 100.0 * nl / len(s0)))
nlt = sum(1 for x in tr0 if x["side"] > 0)
nst = sum(1 for x in tr0 if x["side"] < 0)
print("trades single-pos: %d long / %d short (long %.1f%%)" %
      (nlt, nst, 100.0 * nlt / len(tr0)))
print("\nanio | senales long short | trades long short")
for y in range(2022, 2027):
    sy = [x for x in s0 if yr(P["t"][x[0]]) == y]
    ty = [x for x in tr0 if yr(x["entry_ts"]) == y]
    print("%d | %5d %4d %5d | %5d %4d %5d" %
          (y, len(sy), sum(1 for x in sy if x[1] > 0),
           sum(1 for x in sy if x[1] < 0), len(ty),
           sum(1 for x in ty if x["side"] > 0),
           sum(1 for x in ty if x["side"] < 0)))

# ---------- fase A: grid de senales ----------
RB = [8, 10, 12, 14, 16, 20]
RNG = [4.2, 5.0, 6.0, 7.5]
IMP = [0.75, 0.9, 1.05]
HOURS = [(0, 23), (8, 19), (10, 19), (12, 18)]
CAP = [0.16, 0.30]
STRICT = [True, False]

rows = []
for rb, rng, imp, hours, cap, strict in itertools.product(RB, RNG, IMP, HOURS, CAP, STRICT):
    s, _, _ = G.signals(P, rb=rb, max_rng=rng, imp=imp, hours=hours, buf=0.0,
                        atr_cap=cap, strict=strict, start=260, cache=CACHE)
    if len(s) < 480:
        continue
    nl = sum(1 for x in s if x[1] > 0)
    share = nl / len(s)
    if share < 0.25:
        continue
    rows.append(dict(rb=rb, rng=rng, imp=imp, hours=hours, cap=cap, strict=strict,
                     n=len(s), nl=nl, share=share * 100.0, sig=s))

print("\n=== FASE A: configuraciones con >=480 senales y >=25%% long: %d ===" % len(rows))
rows.sort(key=lambda x: -x["n"])
print("rb rng imp  horas   cap strict | senales  long  long%")
for x in rows[:30]:
    hs = "%d-%d" % (x["hours"][0], x["hours"][-1])
    print("%2d %4.1f %4.2f %-7s %4.2f %-5s | %6d %5d %5.1f" %
          (x["rb"], x["rng"], x["imp"], hs, x["cap"], x["strict"],
           x["n"], x["nl"], x["share"]))

# ---------- fase B: calidad de los finalistas ----------
print("\n=== FASE B: simulacion single-pos de los 30 finalistas ===")
print("rb rng imp  horas   cap strict | sen long% | trades  R    PF  OOSn OOSPF DD1%")
res = []
for x in rows[:30]:
    tr = G.sim(P, x["sig"], **SIM, ktp_mult=3.5, hold=96)
    n, R, pf = st(tr)
    on, oR, opf = st(tr, 2025, 2027)
    d = dd([z["R"] for z in tr], 1.0)
    if n < 180 or pf < 1.4 or opf < 1.7:
        continue
    hs = "%d-%d" % (x["hours"][0], x["hours"][-1])
    print("%2d %4.1f %4.2f %-7s %4.2f %-5s | %5d %5.1f | %5d %+5.1f %5.2f %4d %5.2f %5.1f" %
          (x["rb"], x["rng"], x["imp"], hs, x["cap"], x["strict"],
           x["n"], x["share"], n, R, pf, on, opf, d))
    res.append((x, tr, n, R, pf, on, opf, d))

print("\nsupervivientes fase B: %d" % len(res))
