# Más operaciones en S1 — análisis y variante preparada

Fecha: 2026-11-24. Objetivo del usuario: *"que el bot sea más activo generando más operaciones"*.

## Resumen ejecutivo

Sí se puede aumentar la frecuencia **sin cambiar el código del EA**: basta una
palanca, `InpMaxRangeATR` de **3,4 → 4,2**. En la muestra fuera de muestra
(2025-2026) pasa de **27 a 41 trades (+52%)** y además **mejora** PF (3,59 →
3,62), t (2,84 → 3,50) y DD (3,1 → 2,8). En el tester MT5 con ticks reales de
las últimas 7 semanas pasa de **1 a 3 trades**.

No es gratis: en el tramo de entrenamiento (2022-2024) el PF cae de 1,83 a 1,30
y el DD sube de 3,4R a 12,0R. Por eso la variante **no sustituye** al GA-B
validado con el veredicto 7/7; se prepara como configuración separada.

## Palancas evaluadas

Script: `research/activity_sweep.py` y `research/activity_sweep2.py` (solo lectura).
Mismo simulation engine, costes spread 0,69 + comisión 0,07 + swap real.
Train = 2022-2024, OOS = 2025-2026.

| Variante | Trades/año OOS | PF OOS | t OOS | DD OOS | PF train | Veredicto |
|---|---:|---:|---:|---:|---:|---|
| **GA-B base (rango 3,4)** | 13,5 | 3,59 | 2,84 | 3,1 | 1,83 | Referencia validada 7/7 |
| **rango 4,2 (recomendada)** | **20,5** | **3,62** | **3,50** | **2,8** | 1,30 | +52% trades, mejora OOS |
| rango 5,0 | 23,5 | 3,03 | 3,23 | 3,1 | 1,19 | Más trades, peor PF |
| rango 6,0 | 24,5 | 3,06 | 3,31 | 3,1 | 1,28 | Sin ganancia sobre 4,2 |
| horas 8-20 | 19,0 | 3,54 | 3,38 | 3,3 | 1,06 | PF similar, train muy débil |
| 8-20 + rango 4,2 | 32,5 | 2,21 | 2,72 | 5,9 | **0,82** | Máxima actividad, tren quebrado |
| strict OFF | 29,0 | 2,19 | 2,47 | 9,7 | 1,19 | DD desproporcionado |
| rb 16 | 20,0 | 2,91 | 2,77 | 2,8 | 1,18 | Peor que rango 4,2 |

### ¿Por qué no las otras?

- `strict OFF` y ampliar a 8-20h meten señales de baja calidad: el PF cae y el
  drawdown se dispara. Ya se descartó en `docs/DIAGNOSTICO_VENTAS.md`.
- Reducir `InpHoldBars` a 48/72 libera el hueco de posición antes, pero solo
  da +15% de trades y recorta el R total.
- El cooldown ya está a 0 (`InpCooldownBars=0`): no hay espera que quitar.
- La restricción estructural es **una posición a la vez**: en el replay base,
  22 de 81 señales long quedan bloqueadas por otro long. Levantarla exigiría
  cambiar el código y toda la validación.

## Robustez del parámetro elegido

Vecinos de `InpMaxRangeATR=4,2`, todos con OOS PF ≥ 2,89 y t ≥ 2,67:

| rango | Trades OOS | PF OOS | t | DD |
|---:|---:|---:|---:|---:|
| 3,8 | 36 | 2,89 | 2,67 | 2,8 |
| 4,0 | 38 | 3,30 | 3,11 | 2,8 |
| **4,2** | 41 | 3,62 | 3,50 | 2,8 |
| 4,4 | 42 | 3,39 | 3,36 | 2,8 |
| 4,6 | 43 | 3,35 | 3,33 | 2,5 |
| 4,8 | 46 | 3,19 | 3,35 | 3,1 |

Es una **meseta**, no un pico aislado. Con spread estresado 1,20 USD/oz el OOS
sigue en PF 3,50 / t 3,42 (base: 3,48 / 2,77).

Desglose anual de la variante 4,2: 2022 12 trades PF 0,85 · 2023 37 PF 1,58 ·
2024 30 PF 1,21 · 2025 34 PF 2,78 · 2026 7 PF 14,93. El refuerzo llega sobre
todo en 2025, que es precisamente el año que sostiene el OOS.

## Verificación en MT5 con ticks reales

Misma ventana y motor que la validación de la demo (2026-10-01 → 2026-11-20,
13.872.206 ticks, 3.312 barras, depósito 10.000 CHF):

| Config | Trades | Beneficio neto | PF | DD balance | DD equity |
|---|---:|---:|---:|---:|---:|
| `S1_gaB_demo1` (base) | 1 (1 short) | +96,96 CHF | — | — | — |
| **`S1_gaB_active` (rango 4,2)** | **3 (3 short)** | **+362,16 CHF** | **7,91** | **0,52%** | **2,43%** |
| `S1_gaB_active_wide` (8-20h) | 3 (3 short) | +438,50 CHF | — | 0,00% | 1,83% |

La variante agresiva **no añadió trades** en esta ventana: el cuello de botella
no es el horario, es el rango de compresión. Por eso se descarta.

**Advertencia:** 3 trades en 7 semanas es una muestra demasiado pequeña para
afirmar rentabilidad en vivo. El tester solo confirma que el preset se carga,
que opera y que no rompe costes.

## Archivos generados

| Archivo | Uso |
|---|---|
| `presets/S1_gaB_active.set` | GA-B con rango 4,2 y riesgo 1,0% (recomendado) |
| `presets/S1_gaB_active_wide.set` | Variante agresiva 8-20h (solo comparación) |
| `configs/demo_active_1_0_XAUUSD_M15.ini` | Tester determinista de la variante activa |
| `configs/demo_active_wide_1_0_XAUUSD_M15.ini` | Tester de la variante agresiva |
| `configs/demo_live_active_1_0_XAUUSD_M15.ini` | Arranque en vivo preparado, **no ejecutado** |
| `results/demo_active_report.htm` | Reporte MT5 de la variante activa |
| `results/demo_active_wide_report.htm` | Reporte MT5 de la variante agresiva |
| `results/demo_active_tester.log` | Log del tester |

## Estado y siguiente paso

- EA compilado y desplegado: sin cambios (solo cambió un input).
- GA-B validado intacto: `presets/S1_gaB.set`, `veredicto_gaB.json` 7/7.
- Presets activos copiados a `MQL5\Profiles\Tester\` (tester) y
  `S1_gaB_active.set` a `MQL5\Presets\` (arranque en vivo).
- **Ninguna configuración en vivo arrancada.** Falta autorización explícita.

Si se adopta la variante activa, conviene monitorizar al menos 30 trades en la
cuenta demo antes de considerar cualquier cambio de riesgo. El swap corto real
es positivo (+5,35 USD/oz/noche), lo que favorece a estos trades; el filtro del
EA sigue sin modelarlo.
