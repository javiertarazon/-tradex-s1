"""Simulador multi-posicion usando el nucleo validado de G.sim.

Para cada señal se calcula su trade de forma aislada (misma logica SL/TP/hold
que el EA), y despues se aplica un limite de N posiciones simultaneas.
El guarda de DD se simula sobre la curva ordenada por tiempo de salida.

Solo lectura.
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
T = P["t"]
SO = dict(rb=16, max_rng=6.0, imp=1.05, hours=tuple(range(12, 19)))
SIM = dict(ksl=5.2, ktp_mult=3.5, tgt=1.25, hold=96, spread=0.69,
           comm=0.07, swap=True)


def candidates(spread=0.69):
    s, _, _ = G.signals(P, **SO, buf=0.0, atr_cap=0.16, strict=True,
                        start=260, cache={})
    out = []
    for sig in s:
        tr = G.sim(P, [sig], **{**SIM, "spread": spread})
        if tr:
            out.append(tr[0])
    return out


def take_n(cands, n):
    """Selecciona hasta n posiciones simultaneas, max 1 entrada por vela."""
    order = sorted(cands, key=lambda x: x["entry_ts"])
    active, chosen, used_bars = [], [], set()
    for x in order:
        e = x["entry_ts"]
        if e in used_bars:
            continue
        active = [a for a in active if a > e]
        if len(active) >= n:
            continue
        chosen.append(x)
        used_bars.add(e)
        active.append(x["exit_ts"])
    return sorted(chosen, key=lambda x: x["exit_ts"])


def equity(trades, risk, threshold=0.0, lock_h=0):
    eq, peak, ath, worst = 1.0, 1.0, 1.0, 0.0
    lock_until, triggers = 0, 0
    for x in trades:
        ts = x["entry_ts"]
        if ts < lock_until:
            continue
        eq *= (1.0 + x["R"] * risk / 100.0)
        peak = max(peak, eq)
        ath = max(ath, eq)
        worst = min(worst, eq / ath - 1.0)
        dd = 100.0 * (peak - eq) / peak
        if threshold > 0 and dd >= threshold:
            lock_until = ts + lock_h * 3600
            peak = eq
            triggers += 1
    return (eq - 1.0) * 100.0, abs(worst) * 100.0, triggers


def stats(trades):
    R = np.array([x["R"] for x in trades])
    if len(R) == 0:
        return 0, 0.0, 0.0
    w, l = R[R > 0], R[R <= 0]
    pf = w.sum() / -l.sum() if len(l) and l.sum() < 0 else 99.0
    return len(R), R.sum(), pf


base = candidates(0.69)
base_stress = candidates(1.20)
print("candidatos calculados: %d (base) / %d (estresado)" % (len(base), len(base_stress)))
print("n | trades full/oos | R full/oos | PF full/oos | retorno@riesgo | DD obs / DD estresado")
for n in (1, 2, 3, 4, 6):
    tr = take_n(base, n)
    trs = take_n(base_stress, n)
    nf, rf, pf = stats(tr)
    oos = [x for x in tr if pd.Timestamp(x["entry_ts"], unit="s").year >= 2025]
    no, ro, pfo = stats(oos)
    for risk in (0.5, 0.75, 1.0, 1.5):
        ret, dd, _ = equity(tr, risk, 17.0, 48)
        _, dds, _ = equity(trs, risk, 17.0, 48)
        print("%d | %3d / %3d | %+6.1f / %+6.1f | %4.2f / %4.2f | %.2f%%: %+7.1f%% | %5.1f%% / %5.1f%%" %
              (n, nf, no, rf, ro, pf, pfo, risk, ret, dd, dds))
    print()
