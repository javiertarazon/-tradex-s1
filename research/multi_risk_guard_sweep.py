"""Barrido conjunto de hold, TP, n posiciones, riesgo y umbral de guarda.

Objetivo: subir el retorno del preset multi sin pasar DD estresado 19%.
Solo lectura. Replica G.sim con tmap precalculado.
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
TMAP = {int(x): k for k, x in enumerate(P["t"])}
N = len(P["t"])
T, O, H, L, C = P["t"], P["o"], P["h"], P["l"], P["c"]
A = P["a"]
SO = dict(rb=16, max_rng=6.0, imp=1.05, hours=tuple(range(12, 19)))
SIG, _, _ = G.signals(P, **SO, buf=0.0, atr_cap=0.16, strict=True,
                      start=260, cache={})


def sim_fast(sig, ktp_mult=3.5, hold=96, spread=0.69):
    out = []
    for i, side, hi, lo in sig:
        ts = int(T[i])
        ei = TMAP.get(ts + 900)
        if ei is None or ei >= N - 1:
            continue
        a = A[i]
        entry = C[i]
        span = hi - lo
        if side > 0:
            sl = min(lo, entry - 5.2 * a)
            tp = entry + max(1.25 * span, ktp_mult * 5.2 * a)
        else:
            sl = max(hi, entry + 5.2 * a)
            tp = entry - max(1.25 * span, ktp_mult * 5.2 * a)
        risk = abs(entry - sl)
        if risk <= 0:
            continue
        end = min(N, ei + 1 + hold)
        exit_px, xi = None, None
        for j in range(ei, end):
            if side > 0:
                hsl, htp = L[j] <= sl, H[j] >= tp
            else:
                hsl, htp = H[j] >= sl, L[j] <= tp
            if hsl:
                exit_px = min(O[j], sl) if side > 0 else max(O[j], sl)
                xi = j
                break
            if htp:
                exit_px = max(O[j], tp) if side > 0 else min(O[j], tp)
                xi = j
                break
        if exit_px is None:
            xi = end - 1
            exit_px = float(C[xi])
        gross = (exit_px - entry) * side
        R = (gross - spread - 0.07) / risk
        d0, d1 = ts // 86400, int(T[xi]) // 86400
        nn = int(d1 - d0)
        extra = 0
        for d in range(int(d0) + 1, int(d1) + 1):
            if (d + 4) % 7 == 2:
                extra += 2
        rate = G.SWAP_L if side > 0 else G.SWAP_S
        sw = rate * (nn + extra) / risk if nn > 0 else 0.0
        out.append(dict(entry_ts=ts, exit_ts=int(T[xi]), R=R + sw,
                        side=side, atr_pct=100.0 * a / entry))
    return out


def take_n(cands, n):
    order = sorted(cands, key=lambda x: x["entry_ts"])
    active, chosen, used = [], [], set()
    for x in order:
        e = x["entry_ts"]
        if e in used:
            continue
        active = [a for a in active if a > e]
        if len(active) >= n:
            continue
        chosen.append(x)
        used.add(e)
        active.append(x["exit_ts"])
    return sorted(chosen, key=lambda x: x["entry_ts"])


def equity(trades, risk, th, lock_h=48):
    eq, pk, ath, worst = 1.0, 1.0, 1.0, 0.0
    lock_until, trig = 0, 0
    for x in trades:
        ts = x["entry_ts"]
        if ts < lock_until:
            continue
        eq *= (1.0 + x["R"] * risk / 100.0)
        pk = max(pk, eq)
        ath = max(ath, eq)
        worst = min(worst, eq / ath - 1.0)
        if th > 0 and 100.0 * (pk - eq) / pk >= th:
            lock_until = ts + lock_h * 3600
            pk = eq
            trig += 1
    return (eq - 1.0) * 100.0, abs(worst) * 100.0, trig


def pf_of(tr):
    R = np.array([x["R"] for x in tr])
    w, l = R[R > 0], R[R <= 0]
    return float(w.sum() / -l.sum()) if len(l) and l.sum() < 0 else 99.0


rows = []
for hold, ktp, n in itertools.product([48, 72, 96], [3.5, 4.5], [6, 8]):
    base = take_n(sim_fast(SIG, ktp, hold, 0.69), n)
    stress = take_n(sim_fast(SIG, ktp, hold, 1.20), n)
    p = pf_of(base)
    oos = [x for x in base if pd.Timestamp(x["entry_ts"], unit="s").year >= 2025]
    op = pf_of(oos)
    for risk, th in itertools.product([0.6, 0.75, 0.9, 1.0, 1.1], [10, 12, 14, 16]):
        ret, d, _ = equity(base, risk, th)
        _, ds, _ = equity(stress, risk, th)
        if ds >= 19.0 or p < 1.5 or op < 2.0:
            continue
        rows.append((ret, hold, ktp, n, risk, th, len(base), p, op, d, ds))

print("combinaciones validas (DD estresado<19%%, PF>=1.5, OOS PF>=2): %d" % len(rows))
print("\n=== TOP 25 por retorno ===")
print("retorno | hold ktp  n riesgo guarda | trades  PF  OOSPF | DDobs DDstr")
for ret, hold, ktp, n, risk, th, nt, p, op, d, ds in sorted(rows, reverse=True)[:25]:
    print("%+8.1f%% | %4d %4.1f %2d %5.2f%% %5.1f%% | %5d %4.2f %5.2f | %5.1f%% %5.1f%%" %
          (ret, hold, ktp, n, risk, th, nt, p, op, d, ds))

print("\n=== mejor por numero de trades ===")
for ret, hold, ktp, n, risk, th, nt, p, op, d, ds in sorted(rows, key=lambda z: -z[6])[:10]:
    print("%+8.1f%% | %4d %4.1f %2d %5.2f%% %5.1f%% | %5d %4.2f %5.2f | %5.1f%% %5.1f%%" %
          (ret, hold, ktp, n, risk, th, nt, p, op, d, ds))
