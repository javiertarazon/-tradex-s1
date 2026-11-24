# Revisión: últimas optimizaciones, EA `el elegido` y deriva v1.13

Fecha: 2026-11-24. Pedido: *"revisa los resultados de las últimas optimizaciones y cambios realizados y el nuevo asesor experto el elegido.exe"*.

## 1. Estado del repo

`main` en `d903c61`, limpio antes de esta revisión. El EA auditado sigue siendo
`TradeX_S1_XAU_Multi.mq5` v1.12 en `src/`, con preset recomendado
`presets/S1_multi8_h72_r125.set` (477 trades, +343,8%, DD 18,4%/18,2%,
bootstrap P(DD>20%) 2,0%/4,7%). No se arrancó ninguna demo en vivo.

## 2. Deriva detectada: el `.ex5` desplegado NO es el fuente commiteado

El `TradeX_S1_XAU_Multi.ex5` del terminal dice `version 1.13` y su `.mq5`
local (`MQL5\Experts\TradeX_S1_XAU_Multi.mq5`) difiere del fuente del repo:
**218 líneas añadidas, 31 eliminadas**, hash SHA256 distinto
(`F829B2AD…` local vs `7A27084F…` repo).

v1.13 añade:

- `InpMaxOpenRiskPct`, `InpMaxPosPerCluster`, `InpClusterHours`: compuertas
  de riesgo agregado (limitan N entradas de la misma señal).
- `InpMinFreeMarginFact`, `InpMinMarginLevelPct`, `StopsOk()`,
  `TerminalInfoInteger(TERMINAL_TRADE_ALLOWED)`: permisos, margen y
  distancia a stop.
- `OnTester()` devuelve `profit / equity_DD` con mínimo de trades, y registra
  un estres contrafactual de costes (spread +50%, comisión 10, slippage 100).
- CSV por configuración, con columnas `spread` y `cost_r`.

`paridad_ea.py` sobre el fuente v1.13: **5/5** (`results/paridad_v113.json`).
Pero **no está commiteado**, por lo que `veredicto.py` 7/7 no es reproducible
para él con los ticks locales disponibles (solo cubren desde 2026-10-01).
Los números del repo (incluido el +343,8%) corresponden al v1.12 auditado.
**No desplegar v1.13 hasta incorporar el fuente al repo y revalidar 7/7.**

## 3. Optimizaciones recientes del usuario sobre v1.13

Dos pasadas con ticks reales, 2024-01-01 → 2025-12-31, 126.227.603 ticks,
47.279 barras, calidad 99%, depósito 10.000 USD:

| Config (v1.13) | Parámetros clave | Balance final | PF base / estresado |
|---|---|---:|---:|
| A | rango 8,0 ATR, KSL 4,4, KTP 32,0, hold 72, riesgo 1,75%, 2 pos, sin cap ATR, cluster ON | 42.184,65 USD (+321,8%) | 2,02 / 1,94 |
| B | rango 8,0 ATR, KSL 4,4, KTP 32,0, hold 96, riesgo 1,75%, 2 pos, cap ATR 0,20, cluster ON | 30.109,99 USD (+201,1%) | 1,95 / 1,88 |

El estres de costes es una métrica nueva del propio EA, no una garantía.
Son **2 años en muestra**, con compuertas de cluster activas y-inline en un
binario no versionado: no sustituyen la validación 2022-2026 ni el bootstrap
de DD del preset recomendado. Sirven como pista, no como evidencia de despliegue.

## 4. `el elegido.ex5` (el EA nuevo)

No hay fuente `.mq5` de este EA en descargas, escritorio, documentos ni en el
terminal; solo el binario en `C:\Users\javie\Downloads\el elegido.ex5`
(SHA256 `7EC92594…`, 63.622 bytes). REA no puede abrir el formato `.ex5`
(propietario de MQL5), así que **no es auditable por código**.

Sus parámetros (del ini del tester) describen un EA distinto a S1:

- EMA 9 + VWAP, `InpTF=1`, OHLC4 off, VWAP sesión completa off.
- Filtro de spread 40 puntos, lote fijo **0,1**, sin SL/TP en la orden.
- Trailing: inicio 150 puntos, paso 60, bloqueo de beneficio 30, mínimo 90.
- Una sola posición, magic 20261002, dibujos y panel activados por defecto.

Backtest del ini preparado, 2024-01-01 → 2025-12-31, ticks reales
(126.227.603 ticks, 47.279 barras, calidad 99%, 10.000 USD, apalancamiento 1:100).
Solo se desactivaron dibujos/panel del tester para que terminara; la lógica de
entrada/salida y los parámetros de estrategia no se tocaron.

| Métrica | Resultado |
|---|---:|
| Operaciones ejecutadas | **3** (2 compras, 1 venta) |
| Beneficio neto | **+8,68 USD** (+0,087%) |
| Factor de beneficio | 0,00 (MT5 no calcula PF sin pérdidas) / Re.Fac. 1,87 |
| DD equity | 0,05% (4,65 USD) |
| OnTester | 0 |
| Duración de las posiciones | 3 s – 4 min 33 s |
| Distribución | ene-2024, feb-2024, dic-2024; **cero trades en 2025** |
| Entradas | `Cruce EMA>VWAP` / `Cruce EMA`; salidas por trailing SL con beneficio |

Evidencia: `results/el_elegido_review.htm`.

**Veredicto**: `el elegido` no es una versión nueva de TradeX_S1, sino un EA
de cruce EMA/VWAP con lote fijo y trailing. En 2 años casi no opera (3 trades)
y el beneficio es marginal. No hay base para considerarlo superior ni para
ponerlo en vivo. Su muestra es demasiado pequeña para estimar PF o DD, y al no
existir fuente no se puede auditar paridad, costes ni lógica de riesgo.

## 5. Comparativa directa

| EA / config | Periodo | Trades | Neto | PF | DD equity |
|---|---|---:|---:|---:|---:|
| `el elegido` (binario sin fuente) | 2024-2025, ticks reales | 3 | +8,68 USD | n/d | 0,05% |
| S1 multi8 r125 (repo, v1.12) | 2026-10-01→11-20, ticks reales | 9 | +2.015,98 CHF | 11,20 | 5,62% |
| S1 multi8 r125 (research) | 2022-2026 | 477 | +343,8% | 1,86 | 18,4% |

No se completó una pasada de S1 multi8 sobre 2024-2025 porque había otra
pasada del tester en curso (`el elegido_diag_spread100.ini`) y relanzar el
terminal habría interrumpido ese trabajo ajeno. Queda pendiente si se quiere
comparativa año a año con el mismo binario.

## 6. Decisiones / próximos pasos

1. Mantener el EA v1.12 del repo como referencia auditada; no reemplazarlo
   por el v1.13 del terminal sin commitear y revalidar.
2. No usar `el elegido` en vivo: sin fuente, muestra de 3 trades, lote fijo
   y sin SL/TP en la orden.
3. No arrancar ninguna demo: sigue requiriendo autorización explícita.
4. Si se quiere adoptar v1.13, antes: importar el `.mq5`, ejecutar
   `veredicto.py` 7/7 y `paridad_ea.py` 5/5, repetir el barrido de
   riesgo/guarda con las compuertas de cluster activadas y documentar la
   configuración resultante.
