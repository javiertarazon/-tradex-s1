"""Descarga de barras desde MetaTrader 5 (solo para refrescar la cache local).

Reemplaza la dependencia ``xau_bot.fetch`` del cuaderno original. El flujo
normal del repositorio NO pasa por aquí: ``xau_cost_lab.load()`` lee el CSV
incluido en ``research/data/``.
"""
import pandas as pd

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None


def fetch(symbol, tf, start, end):
    if mt5 is None:
        raise RuntimeError("MetaTrader5 no esta instalado: no se puede descargar")
    mt5.symbol_select(symbol, True)
    frames, cur, end = [], pd.Timestamp(start), pd.Timestamp(end)
    while cur < end:
        nxt = min(cur + pd.DateOffset(days=365), end)
        r = mt5.copy_rates_range(symbol, tf, cur.to_pydatetime(), nxt.to_pydatetime())
        if r is not None and len(r):
            frames.append(pd.DataFrame(r))
        cur = nxt
    if not frames:
        return None
    df = pd.concat(frames, ignore_index=True).drop_duplicates("time").sort_values("time")
    df["time"] = pd.to_datetime(df["time"], unit="s")
    return df.set_index("time")[["open", "high", "low", "close", "tick_volume"]]
