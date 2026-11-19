"""S1 - regimen, filtros y optimizacion genetica con validacion fuera de muestra.

Datos: XAUUSD M15 2022-08 -> 2026-11 (Dukascopy, cache local).
Costes: spread 0.69 USD/oz, comision 0.07 USD/oz, swap real Dukascopy por noche.

Reglas de honestidad:
  * la senal se decide al cierre de la vela i y se ejecuta en i+1
  * se cobra spread al entrar y al salir (via spread completo, conservador)
  * swap aplicado por noches reales con triple el miercoles
  * el GA se entrena SOLO en el tramo de train; el test nunca entra en la fitness
"""
import sys, os, json, math, random
import numpy as np
import pandas as pd

import paths
import xau_cost_lab as lab
from indicators import atr, ema

SPREAD = 0.69
COMM = 0.07
SWAP_L = -1.7434872355   # USD/oz/noche largo
SWAP_S = 0.8733026744    # USD/oz/noche corto
HOUR_SETS = [(13, 14, 15, 16), (13, 14, 15), (14, 15, 16), (13, 14, 15, 16, 17)]


# ---------------------------------------------------------------- preparacion
def prep(m15):
    df = m15.reset_index() if "time" not in m15.columns else m15.copy()
    df = df.sort_values("time").reset_index(drop=True)
    t = df["time"].values.astype("datetime64[s]").astype("i8")
    o, h, l, c = (df[k].values.astype("f8") for k in ("open", "high", "low", "close"))
    a = atr(h, l, c, 14)

    h1 = df.set_index("time").resample("1h", label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    h4 = df.set_index("time").resample("4h", label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    t1 = h1.index.values.astype("datetime64[s]").astype("i8")
    c1 = h1["close"].values.astype("f8")
    e20, e50 = ema(c1, 20), ema(c1, 50)
    t4 = h4.index.values.astype("datetime64[s]").astype("i8")
    c4 = h4["close"].values.astype("f8")
    f50, f200 = ema(c4, 50), ema(c4, 200)

    ref = t + 900
    i1 = np.searchsorted(t1, ref, side="right") - 1
    i1 = np.where((i1 >= 0) & (t1[np.clip(i1, 0, len(t1) - 1)] + 3600 > ref), i1 - 1, i1)
    i4 = np.searchsorted(t4, ref, side="right") - 1
    i4 = np.where((i4 >= 0) & (t4[np.clip(i4, 0, len(t4) - 1)] + 14400 > ref), i4 - 1, i4)
    i1 = np.clip(i1, 0, len(t1) - 1)
    i4 = np.clip(i4, 0, len(t4) - 1)

    up1 = (c1[i1] > e20[i1]) & (e20[i1] > e50[i1])
    dn1 = (c1[i1] < e20[i1]) & (e20[i1] < e50[i1])
    up4 = (c4[i4] > f50[i4]) & (f50[i4] > f200[i4])
    dn4 = (c4[i4] < f50[i4]) & (f50[i4] < f200[i4])
    sep1 = (e20[i1] - e50[i1]) / np.maximum(a, 1e-9)
    sep4 = (f50[i4] - f200[i4]) / np.maximum(a, 1e-9)

    body = np.abs(c - o)
    avg_body = pd.Series(body).rolling(12).mean().shift(1).values
    med_atr = pd.Series(a).rolling(40).median().values
    hours = (t % 86400) // 3600
    dow = ((t // 86400) + 4) % 7   # 1970-01-01 = jueves -> 0=lunes

    # regimen macro: tendencia y volatilidad diarias
    dd = df.set_index("time").resample("1D").agg({"open": "first", "high": "max",
                                                  "low": "min", "close": "last"}).dropna()
    dd["ret"] = np.log(dd["close"]).diff()
    dd["vol20"] = dd["ret"].rolling(20).std() * np.sqrt(252)
    dd["sma50"] = dd["close"].rolling(50).mean()
    dd["slope20"] = dd["close"].pct_change(20)
    dd["dd_hi"] = dd["close"] / dd["close"].rolling(60).max() - 1.0
    dd_idx = dd.index.values.astype("datetime64[s]").astype("i8")
    # alinear por dia
    day = t // 86400 * 86400
    pos = np.searchsorted(dd_idx, day + 86400, side="right") - 1
    pos = np.clip(pos, 0, len(dd) - 1)
    vol20 = dd["vol20"].values[pos]
    slope20 = dd["slope20"].values[pos]
    dd_hi = dd["dd_hi"].values[pos]

    return dict(t=t, o=o, h=h, l=l, c=c, a=a, hours=hours, dow=dow,
                body=body, avg_body=avg_body, med_atr=med_atr, idx1=i1, idx4=i4,
                up1=up1, dn1=dn1, up4=up4, dn4=dn4, sep1=sep1, sep4=sep4,
                vol20=vol20, slope20=slope20, dd_hi=dd_hi)


def signals(P, rb=16, max_rng=2.8, imp=1.10, buf=0.04, hours=(13, 14, 15, 16),
            atr_cap=0.0, strict=True, start=260, cache=None):
    n = len(P["t"])
    if cache is not None and rb in cache:
        hh, ll = cache[rb]
    else:
        hh = pd.Series(P["h"]).rolling(rb).max().shift(1).values
        ll = pd.Series(P["l"]).rolling(rb).min().shift(1).values
        if cache is not None:
            cache[rb] = (hh, ll)
    a = P["a"]
    span = hh - ll
    ok = (np.isfinite(a) & (a > 0) & np.isfinite(span) & (span > 0))
    ok &= (span / np.maximum(a, 1e-9) <= max_rng)
    ok &= (P["body"] >= P["avg_body"] * imp)
    ok &= np.isin(P["hours"], hours)
    if atr_cap > 0:
        ok &= (100.0 * a / P["c"] <= atr_cap)
    ok &= (P["idx1"] >= 220) & (P["idx4"] >= 220)
    ok &= np.arange(n) >= start
    ok[:-1] &= np.arange(n)[:-1] < n - 1

    b = buf * a
    up = ok & (P["c"] > hh + b)
    dn = ok & (P["c"] < ll - b)
    if strict:
        up &= P["up1"] & P["up4"]
        dn &= P["dn1"] & P["dn4"]
    else:
        up &= ~(P["dn1"] | P["dn4"])
        dn &= ~(P["up1"] | P["up4"])

    out = []
    for i in np.flatnonzero(up):
        out.append((int(i), 1, float(hh[i]), float(ll[i])))
    for i in np.flatnonzero(dn):
        out.append((int(i), -1, float(hh[i]), float(ll[i])))
    out.sort()
    return out, hh, ll


def nights(entry_ts, exit_ts):
    d0 = entry_ts // 86400
    d1 = exit_ts // 86400
    n = int(d1 - d0)
    if n <= 0:
        return 0
    extra = 0
    for d in range(int(d0) + 1, int(d1) + 1):
        wd = (d + 4) % 7          # 0 = lunes
        if wd == 2:                # miercoles -> triple
            extra += 2
    return n + extra


def sim(P, sig, ksl=4.4, ktp_mult=2.9, tgt=1.25, hold=96, spread=SPREAD, comm=COMM,
        swap=True):
    t, o, h, l, c = P["t"], P["o"], P["h"], P["l"], P["c"]
    tmap = {int(x): k for k, x in enumerate(t)}
    tr = []
    last_exit = 0
    for i, side, hi, lo in sig:
        ts = int(t[i])
        if ts + 900 <= last_exit:
            continue
        ei = tmap.get(ts + 900)
        if ei is None or ei >= len(t) - 1:
            continue
        a = P["a"][i]
        entry = c[i]
        span = hi - lo
        if side > 0:
            sl = min(lo, entry - ksl * a)
            tp = entry + max(tgt * span, ktp_mult * ksl * a)
        else:
            sl = max(hi, entry + ksl * a)
            tp = entry - max(tgt * span, ktp_mult * ksl * a)
        risk = abs(entry - sl)
        if risk <= 0:
            continue
        end = min(len(t), ei + 1 + hold)
        exit_px, reason, xi = None, "time", None
        for j in range(ei, end):
            if side > 0:
                hsl, htp = l[j] <= sl, h[j] >= tp
            else:
                hsl, htp = h[j] >= sl, l[j] <= tp
            if hsl:
                exit_px = min(o[j], sl) if side > 0 else max(o[j], sl)
                reason, xi = "sl", j
                break
            if htp:
                exit_px = max(o[j], tp) if side > 0 else min(o[j], tp)
                reason, xi = "tp", j
                break
        if exit_px is None:
            xi = end - 1
            exit_px = float(c[xi])
            reason = "time"
        gross = (exit_px - entry) * side
        R = (gross - spread - comm) / risk
        sw = 0.0
        if swap:
            nn = nights(ts, int(t[xi]))
            rate = SWAP_L if side > 0 else SWAP_S
            sw = rate * nn / risk
        tr.append(dict(entry_ts=ts, exit_ts=int(t[xi]), R=R + sw, R_gross=R,
                       side=side, risk=risk, reason=reason, atr=a, entry=entry,
                       atr_pct=100.0 * a / entry, hold_bars=xi - ei + 1))
        last_exit = int(t[xi])
    return tr


def stat(tr, label=""):
    if not tr:
        return dict(label=label, n=0)
    R = np.array([x["R"] for x in tr])
    w, lo = R[R > 0], R[R <= 0]
    eq = np.cumsum(R)
    peak = np.maximum.accumulate(eq)
    t = R.mean() / (R.std(ddof=1) / math.sqrt(len(R))) if len(R) > 2 and R.std(ddof=1) > 0 else 0.0
    return dict(label=label, n=int(len(R)), wr=round(100 * (R > 0).mean(), 1),
                pf=round(float(w.sum() / -lo.sum()), 3) if len(lo) and lo.sum() < 0 else 99.0,
                R=round(float(R.sum()), 2), dd=round(float((peak - eq).max()), 2),
                t=round(float(t), 2), expR=round(float(R.mean()), 3))


def by_year(tr):
    if not tr:
        return {}
    df = pd.DataFrame(tr)
    df["y"] = pd.to_datetime(df.exit_ts, unit="s").dt.year
    out = {}
    for y, g in df.groupby("y"):
        R = g.R.values
        out[int(y)] = dict(n=len(g), R=round(float(R.sum()), 2),
                           pf=round(float(R[R > 0].sum() / -R[R <= 0].sum()), 2) if (R <= 0).any() else 99.0)
    return out


# ------------------------------------------------------------------ reporting
def block(P, sig_kw, sim_kw, label):
    sig, _, _ = signals(P, **sig_kw)
    tr = sim(P, sig, **sim_kw)
    s = stat(tr, label)
    s["anual"] = by_year(tr)
    return s, tr


if __name__ == "__main__":
    m15 = lab.load()
    P = prep(m15)
    print(f"barras={len(P['t'])}  desde={pd.to_datetime(P['t'][0],unit='s')}  hasta={pd.to_datetime(P['t'][-1],unit='s')}")

    base_sig = dict(rb=16, max_rng=2.8, imp=1.10, buf=0.04, hours=(13, 14, 15, 16))
    base_sim = dict(ksl=4.4, ktp_mult=2.9, tgt=1.25, hold=96)
    s, tr = block(P, base_sig, base_sim, "base")
    print(json.dumps(s, ensure_ascii=False))
    pd.DataFrame(tr).to_csv(os.path.join(paths.RESULTS, "base_trades.csv"), index=False)
