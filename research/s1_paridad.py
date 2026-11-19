"""Paridad y robustez temporal de S1 (adaptacion de recursive-analysis de Freqtrade).

Tres pruebas sobre M15 real, sin tester:
  1. RETRASO DE EJECUCION: entrar 0, 1, 2, 3 velas despues de la senal.
     Si el edge solo existe con fill inmediato, es fragilidad de timing, no ventaja.
  2. ARRANQUES ESCALONADOS: empezar el backtest 0/3/6/9/12/15 meses mas tarde.
     Si el resultado depende de la fecha de arranque, hay estado oculto.
  3. SUBMUESTRAS POR ANO NATURAL (control de consistencia).

Config: GA-B (la ganadora del GA de doble split).
"""
import os, sys, json, math
import numpy as np, pandas as pd
import paths
import s1_regime_ga as G

GA_B = dict(
    sig=dict(rb=20, max_rng=3.4, imp=1.05, buf=0.0,
             hours=(13, 14, 15, 16, 17), atr_cap=0.16),
    sim=dict(ksl=5.2, ktp_mult=18.2, tgt=1.25, hold=120, spread=0.69, comm=0.07, swap=True)
)


def stats(tr):
    if len(tr) < 3:
        return dict(n=len(tr), R=0.0, pf=0.0, dd=0.0, t=0.0, wr=0.0)
    R = np.array([x["R"] for x in tr])
    w, l = R[R > 0], R[R <= 0]
    eq = np.cumsum(R)
    m, sd = R.mean(), R.std(ddof=1)
    return dict(n=int(len(R)), R=round(float(R.sum()), 2),
                pf=round(float(w.sum() / -l.sum()), 3) if l.size and l.sum() < 0 else 99.0,
                dd=round(float((np.maximum.accumulate(eq) - eq).max()), 2),
                t=round(float(m / (sd / math.sqrt(len(R)))), 2) if sd > 0 else 0.0,
                wr=round(100 * float((R > 0).mean()), 1))


# --- version de sim con retardo de ejecucion ------------------------------
def sim_lag(P, sig, lag=0, **kw):
    t = P["t"]
    tmap = {int(x): k for k, x in enumerate(t)}
    tr, last_exit = [], 0
    o, h, l, c = P["o"], P["h"], P["l"], P["c"]
    for i, side, hi, lo in sig:
        ts = int(t[i])
        if ts + 900 <= last_exit:
            continue
        ei = tmap.get(ts + 900 * (1 + lag))
        if ei is None or ei >= len(t) - 1:
            continue
        a = P["a"][i]
        entry = float(c[i + lag]) if lag else float(c[i])
        span = hi - lo
        ksl, ktp, tgt, hold = kw["ksl"], kw["ktp_mult"], kw["tgt"], kw["hold"]
        if side > 0:
            sl = min(lo, entry - ksl * a)
            tp = entry + max(tgt * span, ktp * ksl * a)
        else:
            sl = max(hi, entry + ksl * a)
            tp = entry - max(tgt * span, ktp * ksl * a)
        risk = abs(entry - sl)
        if risk <= 0:
            continue
        end = min(len(t), ei + 1 + hold)
        px = None
        xi = None
        for j in range(ei, end):
            if side > 0:
                hit_sl, hit_tp = l[j] <= sl, h[j] >= tp
            else:
                hit_sl, hit_tp = h[j] >= sl, l[j] <= tp
            if hit_sl:
                px = min(o[j], sl) if side > 0 else max(o[j], sl)
                xi = j
                break
            if hit_tp:
                px = max(o[j], tp) if side > 0 else min(o[j], tp)
                xi = j
                break
        if px is None:
            xi = end - 1
            px = float(c[xi])
        gross = (px - entry) * side
        R = (gross - G.SPREAD - G.COMM) / risk
        nn = G.nights(ts, int(t[xi]))
        R += (G.SWAP_L if side > 0 else G.SWAP_S) * nn / risk
        tr.append(dict(entry_ts=ts, exit_ts=int(t[xi]), R=R))
        last_exit = int(t[xi])
    return tr


def main():
    m15 = G.lab.load()
    P = G.prep(m15)
    sig, _, _ = G.signals(P, **GA_B["sig"])
    out = {}

    print("=== 1. retraso de ejecucion (velas extra tras la senal) ===")
    base_pf = None
    for lag in (0, 1, 2, 3):
        tr = sim_lag(P, sig, lag=lag, **GA_B["sim"])
        s = stats(tr)
        out[f"lag{lag}"] = s
        if lag == 0:
            base_pf = s["pf"]
        keep = 100.0 * s["pf"] / base_pf if base_pf else 0.0
        print(f"  lag={lag} n={s['n']:3d} PF={s['pf']:5.2f} ({keep:5.1f}% del base) "
              f"R={s['R']:7.2f} DD={s['dd']:5.2f} t={s['t']:5.2f}")

    print()
    print("=== 2. arranques escalonados (meses de historia recortada) ===")
    t0 = int(P["t"][0])
    rows = []
    for months in (0, 3, 6, 9, 12, 15, 18):
        cut = int(pd.Timestamp(pd.to_datetime(t0, unit="s") + pd.DateOffset(months=months)).timestamp())
        tr = [x for x in sim_lag(P, sig, lag=0, **GA_B["sim"]) if x["entry_ts"] >= cut]
        s = stats(tr)
        rows.append((months, s))
        print(f"  desde {pd.to_datetime(cut, unit='s').date()} n={s['n']:3d} PF={s['pf']:5.2f} "
              f"R={s['R']:7.2f} DD={s['dd']:5.2f} t={s['t']:5.2f}")
    out["staggered"] = {str(m): s for m, s in rows}

    print()
    print("=== 3. anos naturales ===")
    tr = sim_lag(P, sig, lag=0, **GA_B["sim"])
    d = pd.DataFrame(tr)
    d["y"] = pd.to_datetime(d.exit_ts, unit="s").dt.year
    per = {}
    for y, g in d.groupby("y"):
        s = stats(g.to_dict("records"))
        per[int(y)] = s
        print(f"  {y}: n={s['n']:2d} PF={s['pf']:5.2f} R={s['R']:+6.2f} DD={s['dd']:4.2f}")
    out["years"] = per

    with open(os.path.join(paths.RESULTS, "paridad_s1.json"), "w",
              encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()