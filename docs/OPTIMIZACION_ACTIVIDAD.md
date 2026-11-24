# Optimización de actividad con restricción de drawdown < 15%

Fecha: 2026-11-24. Pedido del usuario: *"resultados muy baja PnL, tenemos margen
de DD que sea menor a 15%, optimicemos dando prioridad a mayor número de trades
y mayor balance"*.

## Resultado elegido

`S1_opt_active.set`: **rb16, rango 4,2 ATR, KSL 5,2, KTP 23,4 (4,5×KSL),
hold 96 velas, sesión 13-17, riesgo 1,0%**, strict trend ON.

| Métrica | GA-B validado | Optimizado | Δ |
|---|---:|---:|---:|
| Trades totales 2022-2026 | 77 | **147** | **+91%** |
| Trades OOS 2025-2026 | 27 | **51** | **+89%** |
| R total 2022-2026 | +46,1 | **+64,2** | **+39%** |
| R OOS 2025-2026 | +25,7 | **+43,9** | **+71%** |
| PF OOS | 3,59 | 3,51 | −2% |
| t OOS | 2,84 | **3,69** | +30% |
| DD observado @1,0% | 3,4% | 10,5% | peor, pero < 15% |
| P(DD>15%) bootstrap @1,0% | 0,16% | **1,27%** | < 2% |

El FF sigue siendo alto (3,51 en OOS) y la significancia mejora. Se gana
frecuencia **y** balance con un coste de DD controlado.

## Proceso

1. **Grid de 768 combinaciones** (`research/activity_opt.py`) sobre rb, rango,
   impulso, horario, hold y KTP. Restricción dura: PF>1,5 y DD@1%<15% en full y
   OOS. Sobrevivieron 323.
2. **Finalistas con DD compuesto exacto** (`research/activity_finalists.py`):
   DD calculado sobre la curva de capital compuesta, no como suma lineal de R.
3. **Bootstrap de 20.000 remuestreos** (`research/activity_bootstrap.py`):
   estima P(DD>15%), que es la métrica que realmente importa para el límite duro.
4. **Refinamiento de la zona óptima** (`research/activity_refine.py`): el grid
   inicial no incluía `hold=96`; los vecinos revelaron que ese valor domina a
   los evaluados (más R con menor DD).
5. **Chequeo de costes** (`research/activity_risk_check.py`): a spread 1,20 el DD
   @1% sube de 9,1% a 9,9% en el candidato MIXTO; el ganador se revalidó en MT5.

### Por qué no los otros finalistas

| Candidato | Trades | R total | P(DD>15%) @1% | Motivo de descarte |
|---|---:|---:|---:|---|
| MAX_TRADES (rb16/6,0/12-18) | 227 | +49,9 | 9,13% | Cola de DD demasiado gruesa |
| MIXTO (rb16/5,0/hold72) | 192 | +48,2 | 3,98% | Casi no gana balance |
| BALANCE (rb18/6,0/hold120) | 147 | +58,2 | 4,57% | Más DD y menos R que el elegido |
| **Optimizado (rb16/4,2/hold96)** | **147** | **+64,2** | **1,27%** | **Elegido** |

### Sensibilidad del riesgo

| Riesgo | DD observado | P(DD>15%) |
|---:|---:|---:|
| **1,0% (usado)** | 10,5% | **1,27%** |
| 1,25% | 13,1% | 5,13% |
| 1,5% | 15,8% | >20% |

**No subir a 1,25% sin revalidar**: rompería el límite de DD con demasiada
frecuencia. El trabajo anterior a 1,5% no es aplicable aquí.

## Verificación MT5 (ticks reales, 2026-10-01 → 2026-11-20)

| Config | Trades | Neto | PF | DD balance | DD equity |
|---|---:|---:|---:|---:|---:|
| GA-B base | 1 | +96,96 CHF | — | — | — |
| Activo (rango 4,2) | 3 | +362,16 CHF | 7,91 | 0,52% | 2,43% |
| **Optimizado** | **3** | **+393,12 CHF** | **62,52** | **0,06%** | **2,43%** |

13.872.206 ticks, 3.312 barras, ejecución sin errores. El número de trades en
esta ventana corta sigue siendo 3: la frecuencia real esperada es de **~2
operaciones/mes**, no diaria. El límite estructural sigue siendo *una posición a
la vez*; levantarlo exigiría cambiar el EA y rehacer toda la validación.

## Archivos

- `presets/S1_opt_active.set` — preset optimizado (1,0% riesgo).
- `configs/opt_active_1_0_XAUUSD_M15.ini` — tester determinista.
- `configs/demo_live_opt_1_0_XAUUSD_M15.ini` — arranque en vivo, **no ejecutado**.
- `results/opt_active_report.htm`, `results/opt_active_tester.log` — evidencia MT5.
- `research/activity_opt.py`, `activity_finalists.py`, `activity_bootstrap.py`,
  `activity_risk_check.py`, `activity_refine.py` — análisis reproducible.

## Estado

GA-B validado (7/7) intacto y sin tocar. El EA no ha cambiado: solo inputs.
Preset desplegado en `MQL5\Profiles\Tester\` y `MQL5\Presets\`.
**Ninguna configuración arrancada en vivo**: requiere autorización explícita.
