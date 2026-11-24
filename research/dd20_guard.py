"""Simula el circuit breaker de equity del EA (InpUseProtections=true).

El EA, cuando el DD desde el pico de equity alcanza el umbral, bloquea nuevas
entradas durante N horas y reinicia el pico. Esto convierte el limite de DD en
una restriccion enforcement por codigo, no solo estadistica.

Compara candidatos con/sin guarda a varios riesgos y umbrales. Solo lectura.
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
SIM = dict(ksl=5.2, tgt=1.25, comm=0.07, swap=True)

CAND = [
    ("FREQ 16/6.0/12-18/h96/k3.5", dict(rb=16, max_rng=6.0, imp=1.05, hours=tuple(range(12, 19))), dict(ktp_mult=3.5, hold=96)),
    ("MIX  16/4.2/12-18/h96/k4.5", dict(rb=16, max_rng=4.2, imp=1.05, hours=tuple(range(12, 19))), dict(ktp_mult=4.5, hold=96)),
    ("BAL  16/5.0/13-17/h96/k4.5", dict(rb=16, max_rng=5.0, imp=1.05, hours=(13, 14, 15, 16, 17)), dict(ktp_mult=4.5, hold=96)),
    ("OPT  16/4.2/13-17/h96/k4.5", dict(rb=16, max_rng=4.2, imp=1.05, hours=(13, 14, 15, 16, 17)), dict(ktp_mult=4.5, hold=96)),
]


def build(so, sim, spread=0.69):
    s, _, _ = G.signals(P, **so, buf=0.0, atr_cap=0.16, strict=True,
                        start=260, cache={})
    return G.sim(P, s, **SIM, **sim, spread=spread)


def run_guard(tr, risk, threshold, lock_h):
    """Devuelve (n_taken, retorno%, DD desde maximo historico, n_bloqueos).

    `peak` sigue la logica del EA (se reinicia al dispararse el guarda).
    `ath` es el maximo historico real: el DD que se ve en la cuenta.
    """
    eq, peak, ath, worst = 1.0, 1.0, 1.0, 0.0
    lock_until = 0
    taken, triggers = 0, 0
    for x in tr:
        ts = x["entry_ts"]
        if ts < lock_until:
            continue
        taken += 1
        eq *= (1.0 + x["R"] * risk / 100.0)
        peak = max(peak, eq)
        ath = max(ath, eq)
        worst = min(worst, eq / ath - 1.0)
        dd = 100.0 * (peak - eq) / peak
        if threshold > 0 and dd >= threshold:
            lock_until = int(x["exit_ts"]) + lock_h * 3600
            peak = eq
            triggers += 1
    return taken, (eq - 1.0) * 100.0, abs(worst) * 100.0, triggers


print("SIN GUARDA (referencia)")
print("candidate                      | risk |  n  | retorno% | DD obs")
for name, so, sim in CAND:
    tr = build(so, sim)
    for risk in (1.5, 2.0):
        n, ret, dd, _ = run_guard(tr, risk, 0, 0)
        print("%-29s | %4.2f | %3d | %+8.1f | %5.1f%%" % (name, risk, n, ret, dd))

print("\nCON GUARDA (umbral 17%, bloqueo 48h)")
print("candidate                      | risk |  n  | retorno% | DD obs | disparos")
for name, so, sim in CAND:
    tr = build(so, sim)
    for risk in (1.5, 2.0):
        n, ret, dd, tg = run_guard(tr, risk, 17.0, 48)
        print("%-29s | %4.2f | %3d | %+8.1f | %5.1f%% | %d" % (name, risk, n, ret, dd, tg))

print("\nBARRIDO DE UMBRAL (candidato OPT, riesgo 2.0%, bloqueo 48h)")
_, so, sim = CAND[3]
tr = build(so, sim)
for th in (14.0, 15.0, 16.0, 17.0, 18.0):
    n, ret, dd, tg = run_guard(tr, 2.0, th, 48)
    print("umbral %4.1f%% | n=%3d ret=%+7.1f%% DD=%5.1f%% disparos=%d" % (th, n, ret, dd, tg))

print("\nBARRIDO DE UMBRAL (candidato MIX, riesgo 2.0%, bloqueo 48h)")
_, so, sim = CAND[1]
tr = build(so, sim)
for th in (14.0, 15.0, 16.0, 17.0, 18.0):
    n, ret, dd, tg = run_guard(tr, 2.0, th, 48)
    print("umbral %4.1f%% | n=%3d ret=%+7.1f%% DD=%5.1f%% disparos=%d" % (th, n, ret, dd, tg))

print("\nCOSTES ESTRESADOS spread 1.20 con guarda 17%/48h")
for name, so, sim in CAND:
    tr = build(so, sim, spread=1.20)
    for risk in (1.5, 2.0):
        n, ret, dd, tg = run_guard(tr, risk, 17.0, 48)
        print("%-29s | %4.2f | %3d | %+8.1f | %5.1f%% | %d" % (name, risk, n, ret, dd, tg))
