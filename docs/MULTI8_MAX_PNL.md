# Multi-posición: máximo PnL respetando DD < 20%

Fecha: 2026-11-24. Pedido del usuario: *"veo que hay margen para optimización
para generar más operaciones tanto de compra como de venta, mayor balance final;
el DD es bajo así que podemos arriesgar más; quizá aumentando el lotaje de forma
dinámica según el mercado"*.

## Resumen ejecutivo

**No se cambió el EA.** Se optimizaron solo parámetros del preset. El layout
recomendado `S1_multi8_h72_r125.set` da:

| Métrica | Multi6 anterior | **Multi8 recomendado** | Δ |
|---|---:|---:|---:|
| Posiciones simultáneas | 6 | **8** | +2 |
| Riesgo por posición | 0,75% | **1,25%** | +67% |
| Exposición máxima | 4,5% | **10,0%** | — |
| Trades 2022-2026 | 465 | **477** (todas las señales) | +2,6% |
| Retorno compuesto | +242,4% | **+343,8%** | **+42%** |
| DD observado (desde ATH) | 14,8% | **18,4%** | bajo 20% |
| DD con spread 1,20 | 15,0% | **18,2%** | bajo 20% |
| PF full / OOS | 1,86 / 2,96 | 1,86 / 2,96 | sin cambio |
| P(DD>20%) bootstrap base / estresado | 0,01% / — | **2,0% / 4,7%** | ver riesgo |

La señal y la salida no cambiaron: solo `hold` 96→72, `KTP` 18,2→23,4,
`riesgo` 0,75→1,25, `maxpos` 6→8 y `guarda` 14→18.

## 1. ¿Por qué no aparecen compras en el tester reciente?

No es un fallo del EA. En toda la serie 2022-2026 el generador produce
**380 compras / 97 ventas** (80/20). Pero en 2026 el régimen se invirtió:
**6 compras / 15 ventas**, que es exactamente la ventana del tester
(2026-10-01 → 2026-11-20). El EA tiene `InpAllowLong=true` y
`InpAllowShort=true`; toma ambas direcciones cuando la señal aparece.

| Año | Trades | Long | Short | R | PF |
|---|---:|---:|---:|---:|---:|
| 2022 | 27 | 21 | 6 | −5,9 | 0,64 |
| 2023 | 149 | 88 | 61 | +36,8 | 1,71 |
| 2024 | 123 | 110 | 13 | +14,7 | 1,32 |
| 2025 | 157 | 155 | 2 | +44,1 | 1,75 |
| 2026 | 21 | 6 | 15 | +29,9 | 8,02 |

Forzar un equilibrio 50/50 recortaría las operaciones rentables de 2024-2025.
La alternativa — ensanchar filtros — fue evaluada y **destruye el edge** (§2).

## 2. Techo de frecuencia del núcleo actual

Con rb16 / rango 6,0 ATR / impulso 1,05 / sesión 12-18 / strict trend hay
**477 señales** en 2022-2026. El preset captura las 477 con 8 posiciones: ya no
queda ninguna señal descartada. No existe más frecuencia disponible sin cambiar
el generador.

Se probó un grid de 192 configuraciones más permisivas (`rb` 8-16, `imp`
0,75-1,05, sesión 8-19, `ATR cap` 0,16-0,30, `strict` on/off). Ejemplos:

| Config | Señales | PF | PF OOS | Retorno @0,9% |
|---|---:|---:|---:|---:|
| rb8 / imp0,75 / 8-19 / cap0,30 | 2.054 | 1,24 | 1,62 | +60,6% |
| rb12 / imp0,75 / 4,2 / 8-19 / cap0,30 | 1.339 | 1,39 | 1,88 | +92,2% |
| **rb16 / imp1,05 / 12-18 / cap0,16 (vigente)** | **477** | **1,86** | **2,96** | — |

Cuadruplicar las señales reduce el PF a 1,24 y el retorno a la mitad. **Se
descartó**: más operaciones sin edge no son más beneficio.

## 3. Barrido de riesgo, guarda, hold y TP

Sobre las 477 señales y 8 posiciones se barrió `hold` 48/72/96,
`KTP` 3,5/4,5 × KSL, riesgo 0,6-1,4% y guarda 10-18%. Resultados relevantes:

| Hold | KTP | Riesgo | Guarda | Retorno | DD obs / estresado |
|---:|---:|---:|---:|---:|---:|
| 96 | 3,5 | 0,75% | 14% | +242,4% | 14,8% / 15,0% |
| 72 | 4,5 | 1,10% | 16% | +273,4% | 16,4% / 16,2% |
| 72 | 4,5 | 1,15% | 16% | +295,6% | 17,1% / 16,9% |
| 72 | 4,5 | 1,25% | 18% | **+343,8%** | **18,4% / 18,2%** |
| 72 | 4,5 | 1,30% | 18% | +369,9% | 19,1% / 18,9% |

A 1,40% el DD estresado llega al 26,6% aunque el guarda dispare: se descartó.
La relación riesgo↔guarda es **no monótona** (el guarda cambia qué trades se
saltan), por eso se validó cada finalista con bootstrap.

Bootstrap 20.000 reordenaciones (DD desde máximo histórico):

| Riesgo / guarda | Retorno | P(DD>20%) base | P(DD>20%) estresado | p99 base |
|---|---:|---:|---:|---:|
| 1,10% / 16% | +273,4% | 0,77% | 2,20% | 19,4% |
| 1,15% / 16% | +295,6% | 1,19% | 2,87% | 20,4% |
| **1,25% / 18%** | **+343,8%** | **2,02%** | **4,70%** | **21,8%** |
| 1,30% / 18% | +369,9% | 2,74% | 5,91% | 22,8% |

**Alternativa conservadora**: `S1_multi8_h72.set` (1,10% / guarda 16%) —
+273,4% con P(DD>20%) estresado 2,20%. Es la opción si se prefiere margen por
encima del PnL.

## 4. Lotaje dinámico: evaluado y descartado

Se modelaron cuatro esquemas, todos calculados en la vela de señal (sin
look-ahead), con el mismo `R_net7`:

| Esquema | Factor | Mejor resultado |
|---|---|---|
| ATR contraria | `ATR(-96)/ATR(now)` clip 0,5-1,5 | +265,6% @1,10% |
| **ATR propicia** | `ATR(now)/ATR(-96)` clip 0,7-1,3 | +291,6% @1,10%, DD 16,6/16,3 |
| Impulso | `cuerpo/cuerpo_medio` clip 0,7-1,3 | factor saturado en 1,3 → equivalente a riesgo ×1,3 |
| Combo | media geométrica de los anteriores | idéntico a impulso por saturación |

El mejor esquema dinámico (+291,6%) es **inferior al riesgo fijo 1,15%
(+295,6%)**, que no requiere tocar el EA, rehacer la paridad ni revalidar el
núcleo. Añadir un `InpLotMode` introduciría superficie de error (el factor debe
calcularse de forma idéntica en research y en MQL5) por una ganancia menor.
**Decisión: no implementar.** Esto responde a la sugerencia del usuario con
evidencia, no con una negativa sin medir.

## 5. Verificación MT5 (ticks reales, 2026-10-01 → 2026-11-20)

| Config | Trades | Neto CHF | PF | DD equity |
|---|---:|---:|---:|---:|
| 1 posición (DD20) | 4 | +377,84 | 3,28 | 3,62% |
| Multi6 (0,75%, guarda 14%) | 9 | +1.179,16 | 15,22 | 3,41% |
| Multi8 (1,10%, guarda 16%) | 9 | +1.681,94 | 10,13 | 4,85% |
| **Multi8 (1,25%, guarda 18%)** | **9** | **+2.015,98** | **11,20** | **5,62%** |

13.872.206 ticks, 3.312 barras, 0 errores. El CSV confirma 5 posiciones
simultáneas el 11-nov (14:00, 14:45, 15:30, 15:45, 16:15), cerradas el 12-nov.
`paridad_ea.py`: **5/5** sobre el EA sin cambios (`results/paridad_multi8.json`).

## 6. Riesgos que no se pueden ignorar

- **Concentración**: esas cinco posiciones son la misma señal repetida, no
  cinco ideas independientes. Es apalancamiento direccional sobre una sola
  dirección. En un gap adverso pueden golpear juntas.
- **El guarda bloquea entradas, no cierra posiciones abiertas**, y se evalúa
  por vela M15. El DD de la cuenta puede superar el umbral antes de que actúe.
- **Cola del bootstrap**: p99 = 21,8%; ~2% de las reordenaciones estresadas
  superan 20%. El límite es histórico/estimado, **no una garantía**.
- 9 trades en 7 semanas no prueban rentabilidad en vivo. La frecuencia
  histórica es ~100 operaciones/año.
- `veredicto.py` 7/7 (`results/veredicto_gaB.json`) sigue siendo de GA-B sobre
  el EA original. No se reejecutó para el EA multi: no hay CSVs de ticks de
  todo el periodo localmente. La equivalencia byte-a-byte con
  `InpMaxPositions=1` es la evidencia de que el núcleo no cambió.

## Archivos

- `presets/S1_multi8_h72_r125.set` — recomendado.
- `presets/S1_multi8_h72.set` — alternativa conservadora.
- `configs/multi8_h72_1_25_XAUUSD_M15.ini`, `configs/multi8_h72_1_10_XAUUSD_M15.ini`.
- `configs/demo_live_multi8_h72_r125_XAUUSD_M15.ini` — vivo, **no ejecutado**.
- `results/multi8_r125_report.htm`, `results/multi8_r125_tester.log`,
  `results/trades/multi8_r125_trades.csv`, `results/paridad_multi8.json`.
- `research/freq_direction_grid.py`, `freq_multi_search.py`,
  `multi_risk_guard_sweep.py`, `multi8_validate.py`, `dynamic_lot_lab.py`,
  `fixed_risk_ceiling.py`, `final_risk_boot.py`.

## Estado

EA multi sin cambios desde la última auditoría (0 errores / 0 warnings al
compilar). Presets desplegados en `MQL5\\Profiles\\Tester\\` y `MQL5\\Presets\\`.
**Nada arrancado en vivo**: requiere autorización explícita.
