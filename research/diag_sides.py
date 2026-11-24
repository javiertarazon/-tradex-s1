"""Diagnostico: por que S1 genera tan pocas ventas.

Cuenta cuantas velas sobreviven cada filtro, separando rupturas alcistas y
bajistas, con los parametros GA-B. Solo lectura: no modifica datos ni resultados.
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import paths
import s1_regime_ga as G
import xau_cost_lab as lab

m15 = lab.load()
P = G.prep(m15)
n = len(P["t"])

RB, MAXRNG, IMP, BUF = 20, 3.4, 1.05, 0.0
HOURS = (13, 14, 15, 16, 17)
CAP, START = 0.16, 260

hh = pd.Series(P["h"]).rolling(RB).max().shift(1).values
ll = pd.Series(P["l"]).rolling(RB).min().shift(1).values
span = hh - ll
a = P["a"]

base = np.isfinite(a) & (a > 0) & np.isfinite(span) & (span > 0)
base &= np.arange(n) >= START
f_hours = np.isin(P["hours"], HOURS)
f_cap = 100.0 * a / P["c"] <= CAP
f_rng = span / np.maximum(a, 1e-9) <= MAXRNG
f_body = P["body"] >= P["avg_body"] * IMP
f_idx = (P["idx1"] >= 220) & (P["idx4"] >= 220)

funnel = [
    ("velas totales", np.ones(n, dtype=bool)),
    ("tras start", np.arange(n) >= START),
    ("hora 13-17", base & f_hours),
    ("+ ATR/vol cap", base & f_hours & f_cap),
    ("+ rango/ATR", base & f_hours & f_cap & f_rng),
    ("+ vela impulso", base & f_hours & f_cap & f_rng & f_body),
    ("+ H1/H4 listos", base & f_hours & f_cap & f_rng & f_body & f_idx),
]
print("EMBUDO COMUN (ambos lados)")
for label, mask in funnel:
    print("  %-18s %6d" % (label, int(mask.sum())))

ok = base & f_hours & f_cap & f_rng & f_body & f_idx
up_brk = ok & (P["c"] > hh + BUF * a)
dn_brk = ok & (P["c"] < ll - BUF * a)
print("\nRUPTURAS (antes del filtro de tendencia)")
print("  arriba (long)  %6d" % int(up_brk.sum()))
print("  abajo  (short) %6d" % int(dn_brk.sum()))

up_strict = up_brk & P["up1"] & P["up4"]
dn_strict = dn_brk & P["dn1"] & P["dn4"]
print("\nTRAS STRICT TREND (up1&up4 / dn1&dn4)")
print("  long  %6d  (%.1f%% de rupturas)" % (int(up_strict.sum()), 100.0 * up_strict.sum() / max(1, up_brk.sum())))
print("  short %6d  (%.1f%% de rupturas)" % (int(dn_strict.sum()), 100.0 * dn_strict.sum() / max(1, dn_brk.sum())))

print("\nREGIMEN EN TODAS LAS VELAS")
for label, mask in [
    ("up1", P["up1"]), ("dn1", P["dn1"]),
    ("up4", P["up4"]), ("dn4", P["dn4"]),
    ("up1&up4", P["up1"] & P["up4"]),
    ("dn1&dn4", P["dn1"] & P["dn4"]),
    ("ni tendencia", ~P["up1"] & ~P["dn1"] & ~P["up4"] & ~P["dn4"]),
]:
    print("  %-14s %6d  %5.1f%%" % (label, int(mask.sum()), 100.0 * mask.sum() / n))

sig, _, _ = G.signals(P, rb=RB, max_rng=MAXRNG, imp=IMP, buf=BUF,
                      hours=HOURS, atr_cap=CAP, strict=True, start=START)
longs = [s for s in sig if s[1] > 0]
shorts = [s for s in sig if s[1] < 0]
print("\nSENALES FINALES GA-B: %d long / %d short" % (len(longs), len(shorts)))

years = sorted(set(P["t"][ok] // 31536000))
ys = pd.to_datetime(P["t"], unit="s").year
print("\nPOR ANO (rupturas -> finales)")
for y in sorted(set(ys)):
    m = (ys == y) & ok
    ub, db = m & (P["c"] > hh + BUF * a), m & (P["c"] < ll - BUF * a)
    us, ds = ub & P["up1"] & P["up4"], db & P["dn1"] & P["dn4"]
    print("  %d  long %3d->%3d | short %3d->%3d | dn1&dn4 en el ano %5.1f%%" %
          (y, int(ub.sum()), int(us.sum()), int(db.sum()), int(ds.sum()),
           100.0 * float(np.mean(P["dn1"][m] & P["dn4"][m]))))

# --- efecto secundario: una posicion abierta bloquea senales del lado opuesto
tr = G.sim(P, sig, ksl=5.2, ktp_mult=18.2 / 5.2, tgt=1.25, hold=120,
           spread=0.69, comm=0.07, swap=True)
n_long = sum(1 for x in tr if x["side"] > 0)
n_short = sum(1 for x in tr if x["side"] < 0)
print("\nTRADES SIMULADOS GA-B: %d long / %d short" % (n_long, n_short))

blocked = {"long_por_long": 0, "long_por_short": 0,
           "short_por_long": 0, "short_por_short": 0}
skipped = {"long": 0, "short": 0}
last_exit, last_side = 0, 0
for i, side, hi, lo in sig:
    ts = int(P["t"][i])
    if ts + 900 <= last_exit:
        k = "long" if side > 0 else "short"
        skipped[k] += 1
        if last_side != 0:
            key = ("long" if side > 0 else "short") + "_por_" + ("long" if last_side > 0 else "short")
            blocked[key] += 1
        continue
    # reconstruir salida con la misma regla que sim()
    ei = i + 1
    a = P["a"][i]
    entry = float(P["c"][i])
    span = hi - lo
    sl = (min(lo, entry - 5.2 * a) if side > 0 else max(hi, entry + 5.2 * a))
    tp = (entry + max(1.25 * span, 18.2 * a) if side > 0
          else entry - max(1.25 * span, 18.2 * a))
    end = min(len(P["t"]), ei + 1 + 120)
    xi = end - 1
    for j in range(ei, end):
        hit_sl = (P["l"][j] <= sl) if side > 0 else (P["h"][j] >= sl)
        hit_tp = (P["h"][j] >= tp) if side > 0 else (P["l"][j] <= tp)
        if hit_sl or hit_tp:
            xi = j
            break
    last_exit = int(P["t"][xi])
    last_side = side

print("SENALES BLOQUEADAS POR POSICION ABIERTA:")
print("  long  bloqueadas %2d de %2d (por long %d / por short %d)" %
      (skipped["long"], len(longs), blocked["long_por_long"], blocked["long_por_short"]))
print("  short bloqueadas %2d de %2d (por long %d / por short %d)" %
      (skipped["short"], len(shorts), blocked["short_por_long"], blocked["short_por_short"]))

hold_long = np.mean([x["hold_bars"] for x in tr if x["side"] > 0])
hold_short = np.mean([x["hold_bars"] for x in tr if x["side"] < 0])
print("HOLD MEDIO: long %.1f velas / short %.1f velas" % (hold_long, hold_short))

wins_long = [x["R"] for x in tr if x["side"] > 0]
wins_short = [x["R"] for x in tr if x["side"] < 0]
print("R MEDIO: long %+.3f / short %+.3f" % (np.mean(wins_long), np.mean(wins_short)))

print("\nCONTRASTE: strict trend ON vs OFF (solo diagnostico, no optimizacion)")
for strict in (True, False):
    s, _, _ = G.signals(P, rb=RB, max_rng=MAXRNG, imp=IMP, buf=BUF,
                        hours=HOURS, atr_cap=CAP, strict=strict, start=START)
    k = "ON " if strict else "OFF"
    for side, name in ((1, "long"), (-1, "short")):
        ss = [x for x in s if x[1] == side]
        tt = G.sim(P, ss, ksl=5.2, ktp_mult=18.2 / 5.2, tgt=1.25, hold=120,
                   spread=0.69, comm=0.07, swap=True)
        st = G.stat(tt)
        print("  strict=%s %-5s senales=%3d trades=%3d PF=%5.2f R=%+7.2f t=%+5.2f" %
              (k, name, len(ss), st["n"], st["pf"], st["R"], st["t"]))
