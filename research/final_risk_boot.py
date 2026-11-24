"""Bootstrap P(DD>20%) para los finalistas de riesgo fijo."""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from dynamic_lot_lab import base, stress, equity, factor_of

CAND = [(1.10, 16.0), (1.15, 16.0), (1.20, 18.0),
        (1.25, 18.0), (1.30, 18.0)]


def boot(tr, risk, th, nboot=20000, seed=20261124):
    R = np.array([x["R"] for x in tr])
    rng = np.random.default_rng(seed)
    out = np.empty(nboot)
    for b in range(nboot):
        eq, pk, ath, worst = 1.0, 1.0, 1.0, 0.0
        lock, k = 0, 0
        for r in rng.choice(R, size=len(R), replace=True):
            if k < lock:
                k += 1
                continue
            eq *= (1.0 + r * risk / 100.0)
            pk = max(pk, eq)
            ath = max(ath, eq)
            worst = min(worst, eq / ath - 1.0)
            if 100.0 * (pk - eq) / pk >= th:
                lock = k + 192
                pk = eq
            k += 1
        out[b] = abs(worst) * 100.0
    return out


print("riesgo guarda | retorno  DDobs DDstr | P>20%  p95  p99  max | P>20% estresado")
for risk, th in CAND:
    ret, d, _ = equity(base, risk, "fixed", 1, 1, th)
    _, ds, _ = equity(stress, risk, "fixed", 1, 1, th)
    b = boot(base, risk, th)
    bs = boot(stress, risk, th)
    print("%5.2f%% %5.1f%% | %+7.1f%% %5.1f %5.1f | %5.2f%% %5.1f %5.1f %5.1f | %5.2f%%" %
          (risk, th, ret, d, ds, 100.0 * (b > 20).mean(),
           np.percentile(b, 95), np.percentile(b, 99), b.max(),
           100.0 * (bs > 20).mean()))
