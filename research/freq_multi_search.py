"""Busca mas frecuencia multi-posicion con equilibrio long/short y DD<20%.

Fase 1: grid de senales + sim single-pos (criba de calidad).
Fase 2: sim multi-posicion (n=8) sobre finalistas, barrido de riesgo con
        guarda 14%/48h, costes base y estresados.

sim_fast replica exactamente G.sim pero con el mapa de tiempos precalculado
(solo lectura; no toca el modulo validado).
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
from multipos_sim import take_n, equity

P = G.prep(lab.load())
TMAP = {int(x): k for k, x in enumerate(P["t"])}
N = len(P["t"])
T, O, H, L, C = P["t"], P["o"], P["h"], P["l"], P["c"]
A = P["a"]
SIM = dict(ksl=5.2, tgt=1.25, comm=0.07, swap=True)
CACHE = {}


def yr(ts):
    return int(pd.Timestamp(int(ts), unit="s").year)


def sim_fast(sig, ktp_mult=3.5, hold=96, spread=0.69, comm=0.07, swap=True):
    out = []
    last_exit = 0
    for i, side, hi, lo in sig:
        ts = int(T[i])
        if ts + 900 <= last_exit:
            continue
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
        exit_px, reason, xi = None, "time", None
        for j in range(ei, end):
            if side > 0:
                hsl, htp = L[j] <= sl, H[j] >= tp
            else:
                hsl, htp = H[j] >= sl, L[j] <= tp
            if hsl:
                exit_px = min(O[j], sl) if side > 0 else max(O[j], sl)
                reason, xi = "sl", j
                break
            if htp:
                exit_px = max(O[j], tp) if side > 0 else min(O[j], tp)
                reason, xi = "tp", j
                break
        if exit_px is None:
            xi = end - 1
            exit_px = float(C[xi])
            reason = "time"
        gross = (exit_px - entry) * side
        R = (gross - spread - comm) / risk
        sw = 0.0
        if swap:
            d0, d1 = ts // 86400, int(T[xi]) // 86400
            nn = int(d1 - d0)
            if nn > 0:
                extra = 0
                for d in range(int(d0) + 1, int(d1) + 1):
                    if (d + 4) % 7 == 2:
                        extra += 2
                rate = G.SWAP_L if side > 0 else G.SWAP_S
                sw = rate * (nn + extra) / risk
        out.append(dict(entry_ts=ts, exit_ts=int(T[xi]), R=R + sw,
                        side=side, risk=risk, atr=a,
                        atr_pct=100.0 * a / entry, impulse=float(C[i]) / max(P["avg_body"][i], 1e-9)))
        last_exit = int(T[xi])
    return out


def st(tr, lo=2022, hi=2027):
    sel = [x for x in tr if lo <= yr(x["entry_ts"]) < hi]
    if not sel:
        return 0, 0.0, 0.0
    R = np.array([x["R"] for x in sel])
    w, l = R[R > 0], R[R <= 0]
    return len(sel), float(R.sum()), float(w.sum() / -l.sum()) if len(l) and l.sum() < 0 else 99.0


# ---------------- fase 1 ----------------
RB = [8, 10, 12, 16]
IMP = [0.75, 0.9, 1.05]
RNG = [4.2, 6.0]
HOURS = [(8, 19), (12, 18)]
CAP = [0.16, 0.30]
STRICT = [True, False]

rows = []
for rb, imp, rng, hours, cap, strict in itertools.product(RB, IMP, RNG, HOURS, CAP, STRICT):
    s, _, _ = G.signals(P, rb=rb, max_rng=rng, imp=imp,
                        hours=tuple(range(hours[0], hours[1] + 1)), buf=0.0,
                        atr_cap=cap, strict=strict, start=260, cache=CACHE)
    if len(s) < 430:
        continue
    share = 100.0 * sum(1 for x in s if x[1] > 0) / len(s)
    tr = sim_fast(s)
    n, R, pf = st(tr)
    on, oR, opf = st(tr, 2025, 2027)
    if n < 150 or pf < 1.20 or opf < 1.30 or share < 25.0:
        continue
    rows.append(dict(rb=rb, imp=imp, rng=rng, hours=hours, cap=cap, strict=strict,
                     nsig=len(s), share=share, n=n, R=R, pf=pf,
                     on=on, opf=opf, sig=s))

print("=== FASE 1 supervivientes: %d ===" % len(rows))
print("rb imp rng horas  cap strict | senales long% | trades  R   PF  OOSn OOSPF")
for x in sorted(rows, key=lambda z: -z["nsig"])[:80]:
    hs = "%d-%d" % (x["hours"][0], x["hours"][-1])
    print("%2d %4.2f %4.1f %-6s %4.2f %-5s | %6d %5.1f | %5d %+5.1f %5.2f %4d %5.2f" %
          (x["rb"], x["imp"], x["rng"], hs, x["cap"], x["strict"],
           x["nsig"], x["share"], x["n"], x["R"], x["pf"], x["on"], x["opf"]))

# ---------------- fase 2 ----------------
print("\n=== FASE 2 multi-posicion n=8, guarda 14%/48h ===")
print("rb imp rng horas  cap strict | #pos trades long%  R    PF OOSn OOSPF | riesgo | retorno  DDobs DDstr")

finalists = sorted(rows, key=lambda z: -(z["n"] + z["R"]))[:14]
results = []
for x in finalists:
    base = sim_fast(x["sig"], spread=0.69)
    stress = sim_fast(x["sig"], spread=1.20)
    tb = take_n(base, 8)
    ts_ = take_n(stress, 8)
    n, R, pf = st(tb)
    on, oR, opf = st(tb, 2025, 2027)
    share = 100.0 * sum(1 for z in tb if z["side"] > 0) / max(n, 1)
    hs = "%d-%d" % (x["hours"][0], x["hours"][-1])
    for risk in (0.5, 0.6, 0.75, 0.9):
        ret, d, _ = equity(tb, risk, 14.0, 48)
        _, ds, _ = equity(ts_, risk, 14.0, 48)
        if ds >= 20.0:
            continue
        print("%2d %4.2f %4.1f %-6s %4.2f %-5s | %4d %5d %5.1f %+5.1f %5.2f %4d %5.2f | %.2f%% | %+7.1f%% %5.1f%% %5.1f%%" %
              (x["rb"], x["imp"], x["rng"], hs, x["cap"], x["strict"],
               len(tb), n, share, R, pf, on, opf, risk, ret, d, ds))
        results.append((ret, x, risk, n, share, pf, opf, d, ds))

print("\n=== TOP 12 por retorno (DD estresado < 20%) ===")
for ret, x, risk, n, share, pf, opf, d, ds in sorted(results, key=lambda z: -z[0])[:12]:
    hs = "%d-%d" % (x["hours"][0], x["hours"][-1])
    print("rb%2d imp%4.2f rng%4.1f %-6s cap%4.2f %-5s rsk%.2f | %3d trades long%4.1f%% PF%4.2f OOS%4.2f | ret%+7.1f%% DD%5.1f/%.1f" %
          (x["rb"], x["imp"], x["rng"], hs, x["cap"], x["strict"], risk,
           n, share, pf, opf, ret, d, ds))
