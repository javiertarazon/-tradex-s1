"""Torneo de candidatos: base, filtros de regimen y ganadores del GA, ano a ano."""
import sys, json, math, os
import numpy as np, pandas as pd
import paths
import s1_regime_ga as G

OUT = paths.RESULTS
m15 = G.lab.load()
P = G.prep(m15)
CACHE = {}
T = P["t"]


def stats(tr):
    if not tr:
        return dict(n=0, R=0.0, pf=0.0, dd=0.0, t=0.0, wr=0.0)
    R = np.array([x["R"] for x in tr])
    w, lo = R[R > 0], R[R <= 0]
    t = R.mean() / (R.std(ddof=1) / math.sqrt(len(R))) if len(R) > 2 and R.std(ddof=1) > 0 else 0.0
    eq = np.cumsum(R)
    return dict(n=int(len(R)), R=round(float(R.sum()), 2),
                pf=round(float(w.sum() / -lo.sum()), 3) if len(lo) and lo.sum() < 0 else 99.0,
                dd=round(float((np.maximum.accumulate(eq) - eq).max()), 2),
                t=round(float(t), 2), wr=round(100 * (R > 0).mean(), 1))


def yearly(tr):
    if not tr:
        return {}
    d = pd.DataFrame(tr)
    d["y"] = pd.to_datetime(d.exit_ts, unit="s").dt.year
    return {int(y): stats(g.to_dict("records")) for y, g in d.groupby("y")}


def ev(sig, sim):
    s, _, _ = G.signals(P, **sig, cache=CACHE)
    return G.sim(P, s, **sim)


B = dict(rb=16, max_rng=2.8, imp=1.10, buf=0.04, hours=(13, 14, 15, 16), atr_cap=0.0)
BS = dict(ksl=4.4, ktp_mult=2.9, tgt=1.25, hold=96)

CAND = []
CAND.append(("base", dict(B), dict(BS)))
CAND.append(("base + atr<=0.16", {**B, "atr_cap": 0.16}, dict(BS)))
CAND.append(("base + atr<=0.18", {**B, "atr_cap": 0.18}, dict(BS)))
CAND.append(("base + atr<=0.20", {**B, "atr_cap": 0.20}, dict(BS)))
CAND.append(("base + atr<=0.16 + k5.2 h120", {**B, "atr_cap": 0.16},
             {"ksl": 5.2, "ktp_mult": 2.9, "tgt": 1.25, "hold": 120}))
CAND.append(("GA-A (rb20/3.4/buf0/h13-17/cap.16, k5.2 tgt x, hold240)", 
             dict(rb=20, max_rng=3.4, imp=1.05, buf=0.0, hours=(13, 14, 15, 16, 17), atr_cap=0.16),
             dict(ksl=5.2, ktp_mult=3.1, tgt=1.0, hold=240)))
CAND.append(("GA-B (rb20/3.4/buf0/h13-17/cap.16, k5.2 3.5x tgt1.25 h120)",
             dict(rb=20, max_rng=3.4, imp=1.05, buf=0.0, hours=(13, 14, 15, 16, 17), atr_cap=0.16),
             dict(ksl=5.2, ktp_mult=3.5, tgt=1.25, hold=120)))
CAND.append(("solo entradas GA (resto base)",
             dict(rb=20, max_rng=3.4, imp=1.05, buf=0.0, hours=(13, 14, 15, 16, 17), atr_cap=0.16),
             dict(BS)))
CAND.append(("base + horas 13-17", {**B, "hours": (13, 14, 15, 16, 17)}, dict(BS)))
CAND.append(("base + rb20/3.4/buf0", {**B, "rb": 20, "max_rng": 3.4, "buf": 0.0}, dict(BS)))
CAND.append(("base + k5.2 h120", dict(B), {"ksl": 5.2, "ktp_mult": 2.9, "tgt": 1.25, "hold": 120}))

rows = []
for name, sig, sim in CAND:
    tr = ev(sig, sim)
    s = stats(tr)
    s["anual"] = yearly(tr)
    s["name"] = name
    rows.append(s)
    yr = " ".join(f"{y}:{v['R']:+6.1f}" for y, v in s["anual"].items())
    print(f"{name:58s} n={s['n']:3d} PF={s['pf']:5.2f} R={s['R']:7.2f} DD={s['dd']:5.2f} t={s['t']:5.2f}  {yr}")

pd.DataFrame([{k: v for k, v in r.items() if k != "anual"} for r in rows]).to_csv(
    os.path.join(OUT, "torneo.csv"), index=False)
with open(os.path.join(OUT, "torneo.json"), "w", encoding="utf-8") as fh:
    json.dump(rows, fh, indent=1, ensure_ascii=False)
