"""Experimento coste-aware sobre la senal range-breakout XAUUSD.

Hipotesis: el edge bruto de la senal (~0.08-0.30R) muere porque el coste fijo
(spread 0.57 + comision 0.07 USD/oz) pesa 20-28% de R con SL ~0.9 ATR.
Si el coste/R es el factor dominante, escalar el riesgo (SL/TP/hold) o filtrar
por volatilidad debe mejorar PF sin tocar la logica de entrada.

Se reutilizan indicadores y la simulacion honesta de xau_bot.py.
"""
import sys, os, json, math
import numpy as np
import pandas as pd

import paths
import mt5_fetch as X
from indicators import atr, ema

try:
    import MetaTrader5 as mt5
except ImportError:          # solo hace falta para refrescar la cache de datos
    mt5 = None

OUT = paths.RESULTS
CACHE = paths.M15_CACHE


def load():
    if os.path.exists(CACHE):
        df = pd.read_csv(CACHE)
        tcol = "time" if "time" in df.columns else df.columns[0]
        df[tcol] = pd.to_datetime(df[tcol])
        return df.set_index(tcol).rename_axis("time")
    if mt5 is None:
        raise RuntimeError(
            "No hay cache %s y MetaTrader5 no esta instalado.\n"
            "Instala MetaTrader5 (pip install MetaTrader5) o copia el CSV en research/data/."
            % CACHE)
    if not mt5.initialize(path=paths.MT5_PATH):
        raise RuntimeError("No se pudo inicializar MT5 en %s" % paths.MT5_PATH)
    m15 = X.fetch("XAUUSD", mt5.TIMEFRAME_M15, "2022-06-01", "2026-11-18")
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    m15.to_csv(CACHE)
    return m15


def build(m15, allowed_hours, strict_trend):
    df = m15.reset_index() if "time" not in m15.columns else m15.copy()
    df = df.set_index(pd.DatetimeIndex(df["time"]))
    t15 = df["time"].values.astype("datetime64[s]").astype("i8")
    o, h, l, c = (np.asarray(df[k], dtype="f8") for k in ("open", "high", "low", "close"))
    a15 = atr(h, l, c, 14)

    h1 = df.resample("1h", label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    h4 = df.resample("4h", label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    t1 = np.asarray(h1.index.values.astype("datetime64[s]").astype("i8"), dtype="i8")
    c1 = h1["close"].values.astype("f8")
    e20, e50 = ema(c1, 20), ema(c1, 50)
    t4 = np.asarray(h4.index.values.astype("datetime64[s]").astype("i8"), dtype="i8")
    c4 = h4["close"].values.astype("f8")
    f50, f200 = ema(c4, 50), ema(c4, 200)

    ref = t15 + 900
    i1 = np.searchsorted(t1, ref, side="right") - 1
    i1 = np.where((i1 >= 0) & (t1[np.clip(i1, 0, len(t1) - 1)] + 3600 > ref), i1 - 1, i1)
    i4 = np.searchsorted(t4, ref, side="right") - 1
    i4 = np.where((i4 >= 0) & (t4[np.clip(i4, 0, len(t4) - 1)] + 14400 > ref), i4 - 1, i4)

    n = len(t15)
    rng_hi = np.full(n, np.nan)
    rng_lo = np.full(n, np.nan)
    for i in range(16, n):
        rng_hi[i] = h[i - 16:i].max()
        rng_lo[i] = l[i - 16:i].min()
    body = np.abs(c - o)
    avg_body = pd.Series(body).rolling(12).mean().shift(1).values
    med_atr = pd.Series(a15).rolling(40).median().values
    hours = (t15 % 86400) // 3600
    ok_hour = np.isin(hours, allowed_hours)

    out = []
    for i in range(180, n - 1):
        if not ok_hour[i]:
            continue
        j1, j4 = i1[i], i4[i]
        if j1 < 220 or j4 < 220:
            continue
        a = a15[i]
        span = rng_hi[i] - rng_lo[i]
        if not np.isfinite(a) or a <= 0 or not np.isfinite(span) or span <= 0:
            continue
        if span / a > 2.8:
            continue
        if body[i] < avg_body[i] * 1.10:
            continue
        up1 = c1[j1] > e20[j1] > e50[j1]
        dn1 = c1[j1] < e20[j1] < e50[j1]
        up4 = c4[j4] > f50[j4] > f200[j4]
        dn4 = c4[j4] < f50[j4] < f200[j4]
        entry = c[i]
        buf = 0.04 * a
        side = None
        if entry > rng_hi[i] + buf:
            if (up4 and up1) if strict_trend else not (dn4 or dn1):
                side = "BUY"
        elif entry < rng_lo[i] - buf:
            if (dn4 and dn1) if strict_trend else not (up4 or up1):
                side = "SELL"
        if side is None:
            continue
        out.append(dict(i=i, side=side, entry=float(entry), atr=float(a), span=float(span),
                        hi=float(rng_hi[i]), lo=float(rng_lo[i]),
                        volrat=float(a / med_atr[i]) if np.isfinite(med_atr[i]) and med_atr[i] > 0 else 1.0,
                        ts=int(t15[i])))
    return out, (o, h, l, c, t15, a15, t1, c1, e20, e50, t4, c4, f50, f200, med_atr)


def sim(sigs, data, spread, comm, k_sl, k_tp, hold, vol_min=0.0, vol_max=99.0):
    o, h, l, c, t15, a15, *_ = data
    tmap = {int(ts): k for k, ts in enumerate(t15)}
    Rs, tr = [], []
    last_exit = 0
    for s in sigs:
        if not (vol_min <= s["volrat"] < vol_max):
            continue
        if s["ts"] + 900 <= last_exit:
            continue
        ei = tmap.get(s["ts"] + 900)
        if ei is None or ei >= len(t15) - 1:
            continue
        a = s["atr"]
        if s["side"] == "BUY":
            sl = min(s["lo"], s["entry"] - k_sl * a)
            tp = s["entry"] + max(1.25 * s["span"], k_tp * a)
        else:
            sl = max(s["hi"], s["entry"] + k_sl * a)
            tp = s["entry"] - max(1.25 * s["span"], k_tp * a)
        risk = abs(s["entry"] - sl)
        if risk <= 0:
            continue
        end = min(len(t15), ei + 1 + hold)
        exit_px, reason, xi = None, "time", None
        for j in range(ei, end):
            if s["side"] == "BUY":
                hsl, htp = l[j] <= sl, h[j] >= tp
            else:
                hsl, htp = h[j] >= sl, l[j] <= tp
            if hsl:
                exit_px = min(o[j], sl) if s["side"] == "BUY" else max(o[j], sl)
                reason, xi = "sl", j
                break
            if htp:
                exit_px = max(o[j], tp) if s["side"] == "BUY" else min(o[j], tp)
                reason, xi = "tp", j
                break
        if exit_px is None:
            xi = end - 1
            exit_px = float(c[xi])
            reason = "time"
        gross = (exit_px - s["entry"]) if s["side"] == "BUY" else (s["entry"] - exit_px)
        Rs.append((gross - spread - comm) / risk)
        tr.append(dict(exit_ts=int(t15[xi]), entry_ts=int(t15[ei]), R=Rs[-1], reason=reason,
                       usd=gross - spread - comm, risk=risk, side=s["side"],
                       cost_R=(spread + comm) / risk, volrat=s["volrat"]))
        last_exit = int(t15[xi])
    return np.array(Rs), tr


def stat(R, tr, label):
    if len(R) == 0:
        return dict(label=label, n=0)
    w, lo = R[R > 0], R[R <= 0]
    eq = np.cumsum(R)
    peak = np.maximum.accumulate(eq)
    t = R.mean() / (R.std(ddof=1) / math.sqrt(len(R))) if len(R) > 1 and R.std(ddof=1) > 0 else 0
    cost_R = np.mean([x["cost_R"] for x in tr])
    return dict(label=label, n=int(len(R)), wr=round(100 * (R > 0).mean(), 1),
                pf=round(w.sum() / -lo.sum(), 3) if len(lo) and lo.sum() < 0 else None,
                exp_R=round(float(R.mean()), 4), tot_R=round(float(R.sum()), 1),
                dd_R=round(float((peak - eq).max()), 1), t=round(float(t), 2),
                cost_pct_R=round(100 * float(cost_R), 1),
                usd_trade=round(float(np.mean([x["usd"] for x in tr])), 2))


def yearly(tr):
    if not tr:
        return {}
    df = pd.DataFrame(tr)
    df["y"] = pd.to_datetime(df.exit_ts, unit="s").dt.year
    out = {}
    for y, g in df.groupby("y"):
        R = g.R.values
        out[int(y)] = dict(n=len(g), pf=round(R[R > 0].sum() / -R[R <= 0].sum(), 2) if (R <= 0).any() else None,
                           R=round(float(R.sum()), 1), wr=round(100 * (R > 0).mean(), 0))
    return out


def main():
    if mt5 is None:
        raise RuntimeError("MetaTrader5 no esta instalado")
    if not mt5.initialize(path=paths.MT5_PATH):
        raise RuntimeError("No se pudo inicializar MT5 en %s" % paths.MT5_PATH)
    mt5.symbol_select("XAUUSD", True)
    info = mt5.symbol_info("XAUUSD")
    spread = info.spread * info.point
    comm = 7.0 / info.trade_contract_size
    m15 = load()
    print(f"barras={len(m15)} spread={spread:.3f} comm={comm:.3f}", flush=True)

    variants = [
        ("k2.8 h96", dict(hours=(13, 14, 15, 16), strict=False), (2.8, 8.1, 96, 0.0, 99)),
        ("k2.8+trend", dict(hours=(13, 14, 15, 16), strict=True), (2.8, 8.1, 96, 0.0, 99)),
        ("k2.8+vol<1", dict(hours=(13, 14, 15, 16), strict=False), (2.8, 8.1, 96, 0.0, 1.0)),
        ("k2.8+trend+vol<1", dict(hours=(13, 14, 15, 16), strict=True), (2.8, 8.1, 96, 0.0, 1.0)),
        ("k2.8 h48", dict(hours=(13, 14, 15, 16), strict=False), (2.8, 8.1, 48, 0.0, 99)),
        ("k2.8 horas16-19", dict(hours=(16, 17, 18, 19), strict=False), (2.8, 8.1, 96, 0.0, 99)),
        ("k4.0 h120", dict(hours=(13, 14, 15, 16), strict=False), (4.0, 11.6, 120, 0.0, 99)),
    ]
    rows, best = [], None
    for label, bkw, sp in variants:
        sigs, data = build(m15, bkw["hours"], bkw["strict"])
        R, tr = sim(sigs, data, spread, comm, sp[0], sp[1], sp[2], sp[3], sp[4])
        st = stat(R, tr, label)
        rows.append(st)
        print(json.dumps(st, ensure_ascii=False), flush=True)
        print("   anual: " + json.dumps(yearly(tr), ensure_ascii=False), flush=True)
    print("\nMEJOR: " + json.dumps(best[0], ensure_ascii=False))
    print("anual: " + json.dumps(best[1], ensure_ascii=False))
    pd.DataFrame(rows).to_csv(os.path.join(OUT, "cost_lab.csv"), index=False)
    mt5.shutdown()


if __name__ == "__main__":
    main()
