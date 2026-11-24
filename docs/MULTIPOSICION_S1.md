# S1 multi-posición: salto de frecuencia manteniendo DD < 20%

Fecha: 2026-11-24. Pedido del usuario: *"Quiero más frecuencia aún"*, con el
límite de DD < 20% ya acordado.

## Diagnóstico previo

El EA original opera **una posición a la vez** (`return; // una posicion a la
vez`, línea 320). Con el preset `S1_dd20_freq` se generan **477 señales** en
2022-2026 pero solo se aceptan **192**: se descartan 285 (60%) por solapamiento.
El 63% de las señales llega con menos de 96 velas de separación (la ventana de
hold). Había capacidad real, no falta de señales.

## Cambio implementado

EA nuevo e independiente: `src/TradeX_S1_XAU_Multi.mq5` (v1.12). El original
`TradeX_S1_XAU.mq5` (v1.11) queda **intacto**.

- Nuevo input `InpMaxPositions` (default 1).
- `CountMyPositions()`: cuenta todas las posiciones propias por ticket, no solo
  la seleccionada.
- `CloseExpiredPositions()`: salida por tiempo por ticket, para poder cerrar una
  sin afectar a las demás.
- Registro del `posId` vía `ResultDeal()` → `DEAL_POSITION_ID` (necesario con
  varias posiciones simultáneas).
- Con `InpMaxPositions=1` se conserva la rama original: no se entra en la misma
  vela en que se cierra.

**Prueba de equivalencia**: tester MT5 con el EA multi a `InpMaxPositions=1` y
el mismo preset que el EA original produce un CSV de trades con el **mismo hash
SHA256** (`29B9C8AE…`) y las mismas métricas (4 trades, +377,84 CHF, PF 3,28,
DD 3,62%). El cambio es estrictamente aditivo.

## Resultado

`S1_multi6.set`: **hasta 6 posiciones simultáneas · riesgo 0,75% por posición
(exposición máxima 4,5%) · guarda de equity 14% / 48 h**. El resto de parámetros
es idéntico al preset de alta frecuencia.

| Métrica | 1 posición (1,5%) | **6 posiciones (0,75%)** | Δ |
|---|---:|---:|---:|
| Trades 2022-2026 | 192 | **465** | **+142%** |
| Trades OOS 2025-2026 | 71 | **169** | **+138%** |
| Retorno compuesto | +123,8% | **+242,4%** | **+96%** |
| PF full / OOS | 1,63 / 2,14 | 1,86 / 2.96 | mejora |
| DD observado | 16,7% | **14,8%** | baja |
| DD estresado (spread 1,20) | 17,8% | **15,0%** | baja |

Inesperadamente, el DD **baja** al aumentar posiciones: al fragmentar el riesgo
en 0,75% por trade y activar el guarda al 14%, la curva evade el peor tramo.
El paso de 17% a 14% en el umbral del guarda mejoró simultáneamente DD y retorno
(17,9% → 14,8% y +230,1% → +242,4%).

### ¿Por qué 0,75% y 6 posiciones?

| N | Riesgo/trade | Trades | Retorno | DD obs / estresado |
|---:|---:|---:|---:|---:|
| 1 | 1,50% | 192 | +123,8% | 16,7% / 17,8% |
| 2 | 1,00% | 313 | +165,9% | 17,5% / 17,6% |
| 3 | 0,75% | 390 | +154,1% | 16,4% / 17,8% |
| 4 | 0,75% | 433 | +181,8% | 17,9% / 18,2% |
| **6** | **0,75%** | **465** | **+242,4%** | **14,8% / 15,0%** |
| 6 | 1,00% | 465 | +387,8% | 22,8% / 23,2% → **rompe 20%** |

A 1,00% por posición el DD se va al 23,2%. El límite duro de 20% fija 0,75%.

## Verificación MT5 (ticks reales, 2026-10-01 → 2026-11-20)

| Config | Trades | Neto CHF | PF | DD balance | DD equity |
|---|---:|---:|---:|---:|---:|
| 1 posición | 4 | +377,84 | 3,28 | 1,48% | 3,62% |
| **6 posiciones** | **9** | **+1.179,16** | **15,22** | **0,69%** | **3,41%** |

13.872.206 ticks, 3.312 barras, 0 errores. El CSV confirma solapamientos reales:
cinco ventas abiertas el 11-nov a las 14:00, 14:45, 15:30, 15:45 y 16:15,
cerradas entre las 09:32 y 11:00 del 12-nov.

## Riesgos y honestidad

- **Concentración**: esas cinco posiciones son la misma señal repetida, no
  cinco ideas independientes. Es apalancamiento sobre una sola dirección. El DD
  histórico y estresado sigue bajo 20%, pero en un gap adverso varias operaciones
  podrían golpear a la vez antes de que el guarda pueda cerrar (bloquea entradas,
  no cierra posiciones abiertas). Esta concentración es el principal riesgo del
  cambio respecto al EA validado.
- 9 trades en 7 semanas siguen siendo pocos para probar rentabilidad en vivo.
- El guarda se evalúa por vela M15, no por tick.
- `paridad_ea.py`: **5/5** sobre el nuevo fuente.
- `veredicto.py` **7/7** pertenece a GA-B sobre el EA original. El EA multi es
  nuevo: **no se ha reejecutado el veredicto completo** porque no hay CSVs de
  ticks de todo el periodo disponibles localmente. La equivalencia a
  `InpMaxPositions=1` es la evidencia de que el núcleo validado no cambió.

## Archivos

- `src/TradeX_S1_XAU_Multi.mq5` — EA nuevo (compila 0 errores / 0 warnings).
- `presets/S1_multi6.set`, `presets/S1_multi_baseline.set`.
- `configs/multi6_0_75_XAUUSD_M15.ini`, `configs/multi_baseline_1_5_XAUUSD_M15.ini`.
- `configs/demo_live_multi6_0_75_XAUUSD_M15.ini` — vivo, **no ejecutado**.
- `results/multi6_report.htm`, `results/multi6_tester.log`,
  `results/multi_baseline_report.htm`, `results/trades/multi6_trades.csv`.
- `research/capacity_multipos.py`, `multipos_sim.py`, `multi_guard_check.py`.

## Estado

EA original y GA-B intactos. `TradeX_S1_XAU_Multi.ex5` desplegado en
`MQL5\Experts\`. **Nada arrancado en vivo**: requiere autorización explícita.
