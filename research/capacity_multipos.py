"""Mide cuantas señales se descartan por el limite de una posicion a la vez.

Si el numero de señales es solo marginally mayor que el de trades, levantar el
limite no aporta frecuencia. Solo lectura.
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import s1_regime_ga as G
import xau_cost_lab as lab

P = G.prep(lab.load())
SO = dict(rb=16, max_rng=6.0, imp=1.05, hours=tuple(range(12, 19)))
SIM = dict(ksl=5.2, ktp_mult=3.5, tgt=1.25, hold=96, spread=0.69,
           comm=0.07, swap=True)

s, _, _ = G.signals(P, **SO, buf=0.0, atr_cap=0.16, strict=True,
                    start=260, cache={})
tr = G.sim(P, s, **SIM)

print("señales generadas: %d | trades aceptados: %d | descartados: %d (%.0f%%)" %
      (len(s), len(tr), len(s) - len(tr), 100.0 * (len(s) - len(tr)) / len(s)))

# Solapamiento: cuantas señales caen dentro de la ventana de una posicion abierta
t = P["t"]
exit_ts = [x["exit_ts"] for x in tr]
overlap = 0
for i, side, hi, lo in s:
    ts = int(t[i])
    if any(ts < e for e in exit_ts if e > ts - 96 * 900):
        overlap += 1
print("señales que solapan con una posicion abierta (aprox): %d" % overlap)

# Ano a ano
sig_y = pd.to_datetime([int(t[i]) for i, _, _, _ in s], unit="s").year
tr_y = pd.to_datetime([x["entry_ts"] for x in tr], unit="s").year
print("\nano  señales  trades  descartados")
for y in range(2022, 2027):
    ns = int((sig_y == y).sum())
    nt = int((tr_y == y).sum())
    print("%d  %6d  %6d  %6d" % (y, ns, nt, ns - nt))

# Distribucion de distancia entre señales consecutivas (en velas M15)
gaps = np.diff([int(t[i]) for i, _, _, _ in s]) / 900.0
print("\ngap entre señales: p10=%.0f p25=%.0f p50=%.0f p75=%.0f velas" %
      tuple(np.percentile(gaps, [10, 25, 50, 75])))
print("señales con gap < 96 velas (ventana de hold): %d / %d" %
      (int((gaps < 96).sum()), len(gaps)))
