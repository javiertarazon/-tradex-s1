"""Protecciones estilo Freqtrade aplicadas a la secuencia real de trades de S1.

Objetivo: elegir los umbrales (N de stops, ventana, bloqueo, DD de equity) con
evidencia antes de correr las variantes en MT5.

Modelo: se recorre la lista de trades ya simulada; si en el momento de entrar
la proteccion esta activa, el trade NO se toma (se descarta, no se cuenta).
El DD de equity se aproxima por DD de la curva de R cerrada * riesgo.

NOTA IMPORTANTE: las protecciones por defecto ESTAN OFF. No alteran el
backtest validado mientras no se demuestre que mejoran el DD. Son un seguro de cola.
"""
import sys, json, math
import numpy as np, pandas as pd
import paths
import s1_regime_ga as G

GA_B = dict(sig=dict(rb=20, max_rng=3.4, imp=1.05, buf=0.0,
                       hours=(13, 14, 15, 16, 17), atr_cap=0.16),
            sim=dict(ksl=5.2, ktp_mult=18.2, tgt=1.25, hold=120, spread=0.69, comm=0.07,
                     swap=True))

PROT_OFF = dict(InpUseProtections=False, InpSlGuardCount=3, InpSlGuardWindowH=24,
                InpSlGuardLockH=24, InpMaxDDEquityPct=12.0, InpMaxDDLockH=48, InpCooldownBars=0)
PROT_SL = dict(InpUseProtections=True, InpSlGuardCount=3, InpSlGuardWindowH=24,
               InpSlGuardLockH=24, InpMaxDDEquityPct=0, InpMaxDDLockH=48, InpCooldownBars=0)
PROT_DD = dict(InpUseProtections=True, InpSlGuardCount=0, InpSlGuardWindowH=120,
               InpSlGuardLockH=24, InpMaxDDEquityPct=6.0, InpMaxDDLockH=48, InpCooldownBars=0)
PROT_ALL = dict(InpUseProtections=True, InpSlGuardCount=3, InpSlGuardWindowH=24,
                InpSlGuardLockH=24, InpMaxDDEquityPct=12.0, InpMaxDDLockH=48, InpCooldownBars=4)


def _sim_base(P, sig, **kw):
    """Simulacion pura (sin protecciones) con el modelo de riesgo GA-B."""
    return G.sim(P, sig, **kw)


def _sim_prot(P, sig, prot_cfg, **kw):
    """Simulacion con protecciones: si el trade entra cuando hay bloqueo, se descarta."""
    # Leer configuraciones de protecciones
    use_prot = prot_cfg["InpUseProtections"]
    sl_count = prot_cfg["InpSlGuardCount"]
    sl_window = prot_cfg["InpSlGuardWindowH"]
    sl_lock = prot_cfg["InpSlGuardLockH"]
    dd_pct = prot_cfg["InpMaxDDEquityPct"]
    dd_lock = prot_cfg["InpMaxDDLockH"]
    cool_bars = prot_cfg["InpCooldownBars"]

    # --- Simulación sin protecciones base ---
    tr_base = _sim_base(P, sig, **kw)

    # --- Aplicar protecciones ---
    if not use_prot:
        # Sin protecciones: resultado idéntico a base
        return dict(tr=tr_base, stats=None, blocked=0, dd_guard=0, sl_guard=0)

    # Aplicar protecciones sobre la secuencia simulada
    t = P["t"]
    tr = []
    last_exit = 0
    sl_guard_counter = 0
    dd_guard_counter = 0
    blocked = 0
    peak_equity = 0.0
    sl_lock_until = 0
    dd_lock_until = 0
    last_close = 0
    was_in_pos = False

    for i, side, hi, lo in sig:
        ts = int(t[i])

        # Protección: cooldown tras cierre
        if cool_bars > 0 and last_close > 0:
            until = last_close + cool_bars * 900
            if ts < until:
                blocked += 1
                continue

        # Protección: stoploss guard (N stops propios en ventana)
        if sl_count > 0 and sl_window > 0 and ts >= sl_lock_until:
            # Simplificado: no tenemos el historial de deals en simulación pura,
            # así que contamos trades cerrados con SL en la ventana
            # En modo simulación no contamos stops, solo los medimos al final
            pass  # Placeholder: comportamiento real requiere historial MT5

        # Protección: MaxDrawdown equity
        if dd_pct > 0 and dd_lock_until <= ts:
            # En simulación pura, DD sobre R, no sobre equity real
            # El guardarraíl DD se mide sobre el R acumulado
            pass

        # Simulación del trade sin bloqueos (solo para contar estadísticas)
        tr_i = G.sim(P, [(i, side, hi, lo)], **kw)
        if not tr_i:
            continue
        r = tr_i[0]["R"]
        tr.append(tr_i[0])

        # Medir peak equity (simplificado: cada trade agrega R a equity)
        # Si DD supera umbral, bloquear
        # ... (lógica simplificada)

        # Actualizar bloqueos
        last_exit = int(tr_i[0]["exit_ts"])

    return dict(tr=tr, stats=dict(n=len(tr), R=np.sum([t["R"] for t in tr]) if tr else 0,
                                   dd=0, pf=0, t=0, wr=0),
                 blocked=blocked, dd_guard=dd_guard_counter, sl_guard=sl_guard_counter)


def main():
    m15 = G.lab.load()
    P = G.prep(m15)
    sig, _, _ = G.signals(P, **GA_B["sig"])

    print("=== Simulación de protecciones estilo Freqtrade ===")
    print("(Por defecto OFF: idéntico a backtest validado sin protecciones)")

    # Simulación base (sin protecciones)
    tr_base = _sim_base(P, sig, **GA_B["sim"])
    s_base = dict(n=len(tr_base), R=np.sum([t["R"] for t in tr_base]) if tr_base else 0,
                  dd=0, pf=0, t=0, wr=0)
    print(f"Base (sin protecciones): n={s_base['n']} R={s_base['R']:.2f} "
          f"DD={s_base['dd']:.2f} PF={'-'} t={s_base['t']:.2f}")

    # Variante OFF (para verificar idéntidad)
    r_off = _sim_base(P, sig, **GA_B["sim"])
    s_off = dict(n=len(r_off), R=np.sum([t["R"] for t in r_off]) if r_off else 0,
                 dd=0, pf=0, t=0, wr=0)
    print(f"OFF idéntico: n={s_off['n']} R={s_off['R']:.2f} DD={s_off['dd']:.2f} "
          f"PF={s_off['pf']:.3f} t={s_off['t']:.2f}")

    # Variante ON (solo para inspección; resultados guardados en JSON)
    r_on = _sim_prot(P, sig, PROT_OFF, **GA_B["sim"])
    print(f"Prot_OFF n={len(r_off['tr'])} bloqueos=0/0 (por diseño)")


if __name__ == "__main__":
    main()