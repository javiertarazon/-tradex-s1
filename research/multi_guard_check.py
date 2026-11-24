"""Umbral del guarda para la variante multi-posicion (n=6, riesgo 0.75%)."""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from multipos_sim import candidates, take_n, equity

base = candidates(0.69)
stress = candidates(1.20)

print("n=6 riesgo 0.75% - barrido del umbral de DD")
print("umbral | DD obs / estresado | retorno base / estresado | disparos")
for th in (12.0, 13.0, 14.0, 15.0, 16.0, 17.0):
    tr = take_n(base, 6)
    trs = take_n(stress, 6)
    r, d, tg = equity(tr, 0.75, th, 48)
    rs, ds, tgs = equity(trs, 0.75, th, 48)
    print("%5.1f%% | %5.1f%% / %5.1f%% | %+8.1f%% / %+8.1f%% | %d / %d" %
          (th, d, ds, r, rs, tg, tgs))

print("\nComparacion rapida de riesgo con guarda 15%")
for risk in (0.65, 0.70, 0.75, 0.80):
    tr = take_n(base, 6)
    trs = take_n(stress, 6)
    r, d, _ = equity(tr, risk, 15.0, 48)
    rs, ds, _ = equity(trs, risk, 15.0, 48)
    print("riesgo %.2f%% | retorno %+7.1f%% | DD %5.1f%% / estresado %5.1f%%" %
          (risk, r, d, ds))
