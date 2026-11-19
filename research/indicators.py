"""Indicadores mínimos usados por el laboratorio de S1.

Se sustituye la dependencia externa ``bot_mt5_gbpusd.indicators`` (paquete que
no se distribuía con el material de investigación) por estas dos funciones.

Semántica deliberada:
  * ``atr``  -> ATR de Wilder (suavizado exponencial alpha = 1/period), que es
                el mismo que usa ``iATR`` de MetaTrader 5 en el EA.
  * ``ema``  -> EMA clásica alpha = 2/(period+1) sembrada con el primer valor.

Cualquier cambio aquí altera los resultados del backtest de investigación. El
script ``research/s1_paridad.py`` es la prueba de regresión: sus cifras deben
coincidir con las publicadas en ``results/``.
"""
import numpy as np


def ema(x, period):
    """EMA clásica. Devuelve un array de la misma longitud que x."""
    x = np.asarray(x, dtype="f8")
    n = len(x)
    out = np.full(n, np.nan, dtype="f8")
    if n == 0 or period <= 0:
        return out
    alpha = 2.0 / (period + 1.0)
    out[0] = x[0]
    for i in range(1, n):
        out[i] = alpha * x[i] + (1.0 - alpha) * out[i - 1]
    return out


def atr(high, low, close, period=14):
    """ATR de Wilder. Las primeras ``period`` posiciones son NaN."""
    high = np.asarray(high, dtype="f8")
    low = np.asarray(low, dtype="f8")
    close = np.asarray(close, dtype="f8")
    n = len(close)
    out = np.full(n, np.nan, dtype="f8")
    if n == 0 or period <= 0:
        return out
    tr = np.empty(n, dtype="f8")
    tr[0] = high[0] - low[0]
    for i in range(1, n):
        tr[i] = max(high[i] - low[i],
                    abs(high[i] - close[i - 1]),
                    abs(low[i] - close[i - 1]))
    if n <= period:
        return out
    out[period] = tr[1:period + 1].mean()
    alpha = 1.0 / period
    for i in range(period + 1, n):
        out[i] = alpha * tr[i] + (1.0 - alpha) * out[i - 1]
    return out


def rsi(close, period=14):
    """RSI de Wilder (no se usa en S1; se mantiene por completitud)."""
    close = np.asarray(close, dtype="f8")
    n = len(close)
    out = np.full(n, np.nan, dtype="f8")
    if n <= period:
        return out
    delta = np.diff(close, prepend=close[0])
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    ag = gain[1:period + 1].mean()
    al = loss[1:period + 1].mean()
    for i in range(period, n):
        if i > period:
            ag = (ag * (period - 1) + gain[i]) / period
            al = (al * (period - 1) + loss[i]) / period
        out[i] = 100.0 if al == 0 else 100.0 - 100.0 / (1.0 + ag / al)
    return out


def heikin_ashi(o, h, l, c):
    """Velas Heikin-Ashi (no se usa en S1; se mantiene por completitud)."""
    o, h, l, c = (np.asarray(a, dtype="f8") for a in (o, h, l, c))
    n = len(c)
    ha_c = (o + h + l + c) / 4.0
    ha_o = np.empty(n, dtype="f8")
    ha_h = np.empty(n, dtype="f8")
    ha_l = np.empty(n, dtype="f8")
    ha_o[0] = (o[0] + c[0]) / 2.0
    for i in range(n):
        if i > 0:
            ha_o[i] = (ha_o[i - 1] + ha_c[i - 1]) / 2.0
        ha_h[i] = max(h[i], ha_o[i], ha_c[i])
        ha_l[i] = min(l[i], ha_o[i], ha_c[i])
    return ha_o, ha_h, ha_l, ha_c


def ha_color(ha_o, ha_c):
    """1 = vela HA alcista, -1 = bajista."""
    ha_o = np.asarray(ha_o, dtype="f8")
    ha_c = np.asarray(ha_c, dtype="f8")
    return np.where(ha_c >= ha_o, 1, -1)
