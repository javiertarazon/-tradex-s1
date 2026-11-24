"""Techo de riesgo fijo para multi8 h72 con guarda variable."""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from dynamic_lot_lab import base, stress, equity

print("riesgo guarda | retorno  DDobs  DDstr")
rows = []
for risk in (1.10, 1.15, 1.20, 1.25, 1.30, 1.35, 1.40):
    for th in (12.0, 14.0, 16.0, 18.0):
        ret, d, trig = equity(base, risk, "fixed", 1, 1, th)
        _, ds, _ = equity(stress, risk, "fixed", 1, 1, th)
        rows.append((ret, risk, th, d, ds, trig))
        print("%5.2f%% %5.1f%% | %+8.1f%% %6.1f%% %6.1f%%  disparos=%d" %
              (risk, th, ret, d, ds, trig))
    print()

print("=== validos con DD estresado < 19.5% ===")
for ret, risk, th, d, ds, trig in sorted([r for r in rows if r[4] < 19.5], reverse=True)[:10]:
    print("riesgo %.2f%% guarda %.1f%% | ret %+8.1f%% DD %.1f/%.1f" %
          (risk, th, ret, d, ds))
