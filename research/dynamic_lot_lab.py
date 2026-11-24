"""Prueba si el lotaje dinamico mejora la config multi8 h72.

Factores evaluados (todos calculados en la vela de senal, sin look-ahead):
  ATR_CONTRA : ATR(96 velas atras) / ATR actual  -> mas riesgo en calma
  ATR_PRO    : ATR actual / ATR(96 velas atras)  -> mas riesgo en turbulencia
  IMPULSO    : cuerpo / cuerpo medio
  COMBO      : media geometrica de ATR_CONTRA e IMPULSO

Solo lectura. Si ningun esquema gana, no se toca el EA.
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
TMAP = {int(x): k for k, x in enumerate(P["t"])}
N = len(P["t"])
T, O, H, L, C = P["t"], P["o"], P["h"], P["l"], P["c"]
A, AB = P["a"], P["avg_body"]
SIG, _, _ = G.signals(P, rb=16, max_rng=6.0, imp=1.05,
                      hours=tuple(range(12, 19)), buf=0.0, atr_cap=0.16,
                      strict=True, start=260, cache={})


def candidates(spread):
    out = []
    for i, side, hi, lo in SIG:
        ts = int(T[i])
        ei = TMAP.get(ts + 900)
        if ei is None or ei >= N - 1:
            continue
        a = A[i]
        entry = C[i]
        span = hi - lo
        if side > 0:
            sl = min(lo, entry - 5.2 * a)
            tp = entry + max(1.25 * span, 4.5 * 5.2 * a)
        else:
            sl = max(hi, entry + 5.2 * a)
            tp = entry - max(1.25 * span, 4.5 * 5.2 * a)
        risk = abs(entry - sl)
        if risk <= 0:
            continue
        end = min(N, ei + 1 + 72)
        exit_px, xi = None, None
        for j in range(ei, end):
            hsl = L[j] <= sl if side > 0 else H[j] >= sl
            htp = H[j] >= tp if side > 0 else L[j] <= tp
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
        R = ((exit_px - entry) * side - spread - 0.07) / risk
        d0, d1 = ts // 86400, int(T[xi]) // 86400
        nn = int(d1 - d0)
        extra = sum(2 for d in range(int(d0) + 1, int(d1) + 1) if (d + 4) % 7 == 2)
        R += (G.SWAP_L if side > 0 else G.SWAP_S) * (nn + extra) / risk if nn > 0 else 0.0
        ref = A[max(0, i - 96)]
        out.append(dict(entry_ts=ts, exit_ts=int(T[xi]), R=R,
                        atr_contra=ref / max(a, 1e-9),
                        atr_pro=a / max(ref, 1e-9),
                        impulse=float(C[i]) / max(AB[i], 1e-9)))
    return out


def take_n(cands, n=8):
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


def clip(v, lo, hi):
    return min(hi, max(lo, v))


def factor_of(mode, x, lo, hi):
    if mode == "fixed":
        return 1.0
    if mode == "atr_contra":
        return clip(x["atr_contra"], lo, hi)
    if mode == "atr_pro":
        return clip(x["atr_pro"], lo, hi)
    if mode == "impulso":
        return clip(x["impulse"], lo, hi)
    if mode == "combo":
        return clip(np.sqrt(x["atr_contra"] * x["impulse"]), lo, hi)
    raise ValueError(mode)


def equity(trades, risk, mode, lo, hi, th=16.0):
    eq, pk, ath, worst = 1.0, 1.0, 1.0, 0.0
    lock, trig = 0, 0
    for x in trades:
        if x["entry_ts"] < lock:
            continue
        f = factor_of(mode, x, lo, hi)
        eq *= (1.0 + x["R"] * risk * f / 100.0)
        pk = max(pk, eq)
        ath = max(ath, eq)
        worst = min(worst, eq / ath - 1.0)
        if 100.0 * (pk - eq) / pk >= th:
            lock = x["entry_ts"] + 48 * 3600
            pk = eq
            trig += 1
    return (eq - 1.0) * 100.0, abs(worst) * 100.0, trig


base = take_n(candidates(0.69))
stress = take_n(candidates(1.20))
print("candidatos=%d / estresados=%d" % (len(base), len(stress)))
print("modo        lo  hi  riesgo | retorno   DDobs  DDstr | factor medio")
rows = []
for mode, lo, hi in [("fixed", 1, 1),
                     ("atr_contra", 0.7, 1.3), ("atr_contra", 0.5, 1.5),
                     ("atr_pro", 0.7, 1.3),
                     ("impulso", 0.7, 1.3), ("impulso", 0.6, 1.5),
                     ("combo", 0.7, 1.3), ("combo", 0.6, 1.5)]:
    fmean = np.mean([factor_of(mode, x, lo, hi) for x in base])
    for risk in (0.8, 0.9, 1.0, 1.1, 1.2):
        ret, d, _ = equity(base, risk, mode, lo, hi)
        _, ds, _ = equity(stress, risk, mode, lo, hi)
        if ds >= 19.5:
            continue
        rows.append((ret, mode, lo, hi, risk, d, ds, fmean))
        print("%-11s %.1f %.1f  %.2f%% | %+8.1f%% %6.1f%% %6.1f%% | %.3f" %
              (mode, lo, hi, risk, ret, d, ds, fmean))
    print()

print("=== TOP 10 ===")
for ret, mode, lo, hi, risk, d, ds, fm in sorted(rows, reverse=True)[:10]:
    print("%-11s %.1f-%.1f r%.2f%% | ret %+8.1f%% DD %.1f/%.1f" %
          (mode, lo, hi, risk, ret, d, ds))
