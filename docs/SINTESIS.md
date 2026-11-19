# TradeX — Síntesis de la auditoría y propuesta de sistema nuevo

**Fecha:** 18-nov-2026
**Alcance:** 172 repos públicos de `javiertarazon`; 39 de temática trading/finanzas revisados; 9 auditados a fondo con réplica de señales y costes reales; 17 copias/cascarones y 5 vacíos descartados por blob SHA/estructura; 9 repos de terceros clasificados hoy.
**Estándar:** M15 real con SL prioritario, relleno de gap al open, spread real, comisión 7 USD/lote y swap real. Los ticks (Model=4) se usaron como puerta final de S1 y ya está cerrada (§6.1).

---

## 1. Resumen ejecutivo

1. **Ningún bot del usuario es rentable tal como está.** De 9 auditorías, 0 superan costes reales con significancia. El patrón se repite: backtester sin costes, relleno exacto, grid search sobre el mismo tramo y resultado declarado in-sample.
2. **El único motor honesto** (`bot-estrategia-del-xauusd-nueva`) tenía un edge bruto real pero moría por ruido y coste: PF 1.09, +8.7R, DD 20.5R, t=0.63, con 2023 en −16.8R.
3. **Hallazgo nuevo de hoy:** ese mismo motor, **sin tocar la señal**, pasa a PF 1.89–2.04 y t=2.4–2.9 cambiando tres cosas de diseño: alineación estricta H1+H4, stop 4.0–4.4 ATR y hold 24–30 h. 93 operaciones, +37.9R con swap, DD 6.5R, **todos los años ≥ 0** (2023 +4.1R, 2024 +0.9R, 2025 +20.5R, 2026 +13.3R).
4. **Convertido en EA y validado con ticks reales (Model=4, 208M ticks, 99% reales):** PF 2.17, 69 trades, +31.282 USD (+62.6%) sobre 50.000 con riesgo 1.5%, DD balance 6.93% y equity 8.92%, Sharpe 6.66. La meseta aguanta: PF 2.11–2.29 con KSL 3.5/4.4/5.3 y hold 96/120. **Es el primer sistema del audit que pasa la puerta G4.**
5. **Pero falla el out-of-sample.** Partiendo la muestra: 2024 solo da **PF 1,30 y t=0,55** (indistinguible de ruido) mientras 2025–2026 da PF 2,63 y t=2,90. El edge existe en el régimen de oro acelerado, no en general. **No se pone capital real.**
6. **Hallazgo colateral:** el rendimiento se concentra en los trades con ATR/precio bajo (3 de 3 años). Añadido `InpMaxATRPct` al EA, desactivado por defecto, como hipótesis a medir en demo.
7. **La propuesta** sigue siendo un sistema de 2 estrategias (breakout XAU coste-consciente + MR2 D1 USA30 como diversificador débil) sobre un motor honesto, con puertas de validación numéricas y escalera de riesgo hasta DD 15%. Esperanza realista: **8–14% anual con DD 10–15%**, no un milagro.

---

## 2. El hallazgo: por qué el XAU funcionaba mal y cómo se arregla

### 2.1 Diagnóstico

La señal original (rango de 16 velas M15 comprimido ≤2.8 ATR, ruptura con buffer 0.04 ATR, filtro H1/H4, ventana 13–16) tiene edge bruto, pero:

- El stop a 0.9 ATR está **dentro del ruido M15**: 55% de acierto pero las pérdidas son del mismo tamaño que las ganancias.
- El TP a 2.6 ATR se alcanza pocas veces; el 40% de las salidas son por tiempo.
- El coste (spread 0.57–0.69 + comisión 0.07 USD/oz) es fijo; con riesgo pequeño pesa más.
- El filtro de tendencia usaba **OR** (“si H4 o H1 va en contra, no opero”), lo que deja pasar rupturas contra la tendencia de uno de los dos marcos.
- La ventana 13–16 en servidor GMT+3 = **10–13 UTC**, no la apertura NY que el autor creía.

### 2.2 Experimento (misma señal, solo diseño de salida y régimen)

XAUUSD M15, 99.916 velas, 2022-08 → 2026-11, spread 0.69, comisión 0.07, swap real Dukascopy (−1.743 USD/oz/noche largo, +0.873 corto, triple miércoles).

| Variante | N | WR | PF sin swap | PF con swap | Total R | DD R | t | Coste/R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Base del repo (0.9 ATR, hold 6 h) | 247 | 55.1% | 1.09 | 1.11 | +8.7 | 20.5 | 0.63 | 6.5% |
| k=2.8 ATR, hold 24 h | 234 | 41.0% | 1.26 | — | +37.4 | 19.4 | 1.57 | 6.9% |
| k=4.0 ATR, hold 30 h, tendencia estricta | 94 | 45.7% | 1.92 | **1.79** | +39.1 | 6.7 | 2.44 | 4.8% |
| **k=4.4 ATR, hold 24 h, tendencia estricta** | **93** | **51.6%** | **2.04** | **1.89** | **+37.9** | **6.5** | **2.60** | **4.4%** |
| k=4.0, hold 24 h, ventana 16–19 + estricta | 42 | 61.9% | 3.46 | 3.51 | +34.4 | 2.1 | 3.40 | 3.3% |

**Desglose anual del mejor (con swap):**

| Año | N | PF | R |
|---|---:|---:|---:|
| 2022 (ago–dic) | 4 | 0.61 | −0.9 |
| 2023 | 21 | 1.33 | +4.1 |
| 2024 | 23 | 1.08 | +0.9 |
| 2025 | 25 | 3.27 | +20.5 |
| 2026 (ene–nov) | 20 | 2.97 | +13.3 |

**Por lado:** largos 68 trades PF 2.30 (+36.3R); cortos 25 trades PF 1.10 (+1.5R). El edge es **largo y de régimen alcista**; los cortos son casi ruido.

**Meseta de parámetros:** k de 3.2 a 5.0 y hold de 96 a 168 velas dan PF 1.75–2.02 (sin swap) en 93–96 trades. No es un pico aislado de grid search: es una región estable. La mejora es monótona al alejar el stop del ruido.

**Lectura correcta:** el edge no estaba en la señal, estaba en **dejar respirar la posición y alinearse con el marco superior**. El stop ancho no “arriesga más” en términos de cuenta: se compensa bajando el tamaño por operación (riesgo fijo en %).

### 2.3 Lo que aún invalida el resultado

| Riesgo | Evidencia | Mitigación |
|---|---|---|
| OOS inexistente | Dukascopy M15 solo desde 2022-08 | Walk-forward 2022–24 / 2025–26 + forward demo |
| Concentración 2025–26 | 89% del R en 22 meses | Test de régimen: exige ATR/tendencia; aceptar que es estrategia de tendencia |
| Swap del bróker real | Usado swap Dukascopy; Pepperstone puede ser peor | Pedir swap real y reejecutar; el resultado ya está ajustado a −1.74 USD/oz/noche |
| Sin slippage | Relleno al open con gap | Añadir 0.05–0.10 USD/oz; el PF cae ~0.03–0.05 |
| M15 ≠ ticks | Sin Model=4 | EA + ticks Dukascopy/Pepperstone antes de real |
| Muestra | 93 trades, 21–25/año | Mínimo 2 años forward o ampliar a otros activos |

---

## 3. Valles planos: qué son y qué los causa

Un valle plano no es “mala racha”: es un tramo donde **el edge neto es ≈0 durante semanas o meses**. En estos repos hay cuatro causas medibles:

1. **Coste > edge (la dominante).** En XAU M15 con SL 0.9 ATR el coste ronda 6.5–25% de R según el momento del día. Con edge bruto 0.08–0.15R, cualquier subida de spread convierte el sistema en plano. Evidencia: FluxoV2 pasa de PF 1.036 (coste 0.16) a 0.850 (coste real 0.64) y −120R.
2. **Régimen equivocado.** El breakout XAU base pierde −16.8R en 2023 (rango/mean-reversion) y gana en 2025 (tendencia). El valle de 2023 no es aleatorio: es el filtro de tendencia haciendo su trabajo mal (OR en vez de AND).
3. **Ventana horaria desplazada.** El servidor es GMT+3 y los repos asumen UTC. Eso convierte una ventana de 3 h en otra distinta y crea tramos planos artificiales (el “edge” está en horas que no son).
4. **Sobreajuste y muestra corta.** `tune_params()` de TM75 recorre 384–576 combos sobre 5 meses; los 6 trades de bot-unificado dan Sharpe 9.08. Curvas planas aquí son el ruido de un ajuste sin sustancia.

**Regla de diseño:** un valle plano se investiga con atribución (¿coste? ¿régimen? ¿horario? ¿azar?) antes de tocar parámetros. Si el 80% del PnL viene de <25% de los meses, el sistema no está listo.

---

## 4. Ideas reutilizables, repo por repo

| Repo | Veredicto | Qué se queda | Qué se tira |
|---|---|---|---|
| `bot-estrategia-del-xauusd-nueva` | **Base real** | Motor honesto, `RiskBook`, trailing adaptativo, `evaluate_range_breakout_variant` | Ventana horaria y filtro OR; sus perfiles base/aggressive fallan |
| `bot-voltaje-xauusd` (FluxoV2) | Descartado | Indicadores puros (flujo, Bayes, régimen), Monte Carlo | Edge dependiente de `tick_volume` de Deriv; coste irreal |
| `bot-unificado-...` | Descartado | `DynamicRiskManager` (Kelly, escalado por DD, racha), detección ADX/ATR, risk-parity | Datos sintéticos; RF de 60 MB sin uso |
| `Mirofish-quant-polymarket` | No operable (otra clase) | Puertas de validación: EV neto vs ask, Brier/log-loss, CLV, bootstrap por evento | Mercados de predicción, sin backtest |
| `botcopilot-sar` | Descartado | Nada | PSAR no usado en señal; PnL con `np.random`; sin comisión |
| `copilot-bot-v-4.11` + 4 copias | Descartado | Nada | Entrena y predice sobre el 100%; motor sin costes; modelos solo de Volatility 75 |
| `bot-tm-volatily-75` | Descartado | Nada | Sin costes; grid search 384–576 combos / 5 meses; 5/5 símbolos negativos |
| `bot-institucional-qwen-trae` | Descartado | Nada | Datos ausentes; fuga multi-símbolo; etiqueta de volatilidad, no dirección |
| `EA-milagro-carlos` | Descartado | Nada | PF 0.15–0.18, DD 84–92% |
| `Vibe-Trading` (HKUDS) | **Referencia metodológica** | Strict OOS con control aleatorio, risk x-ray, guards de look-ahead, motor multi-mercado | Stack 59 MB; no es una estrategia; no MT5 nativo |
| `day-trader-skill` | Herramienta | Plantilla `size.py`, reglas de entry/exit, replay `timemachine` | Acciones US intradía; sin backtest de edge |
| `TradingAgents` | Herramienta | Capa de análisis/decision (ya usada en US500) | No produce señal cuantitativa validada |
| `opentrader`, `Kronos`, `Sol-Onchain-Analyst`, `Moltbot-solana`, `agente-copilot`, `multi-agente-orquetador` | Descartados | Ideas sueltas (DCA/grid, modelo de velas) | Otra clase de activo, sin ejecución MT5, o solo scaffolding |
| `metatrader-mcp-server` | Infraestructura | Puente MCP ↔ MT5 para operar/leer | No es estrategia |

---

## 5. Propuesta: TradeX Regime-Cost Engine (RCE)

**Tesis:** el problema de estos bots no es la falta de ideas, es que **optimizan la señal cuando el enemigo es el coste y el régimen**. RCE invierte el orden: primero un motor que no miente, luego una señal que sobrevive al coste, luego el riesgo.

### 5.1 Arquitectura

```
tradex/
  data/        carga MT5 + caché CSV/Parquet, reloj normalizado a UTC
  engine/      simulador honesto: SL prioritario, gap al open, spread variable,
               comisión, swap (triple miércoles), hold máximo, sin solapamiento
  features/    ATR, ADX, EMA H1/H4, compresión de rango, percentil de volatilidad
  signals/     S1 XAU expansion-breakout | S2 MR2 D1 USA30 | registro de candidatos
  risk/        riesgo fijo 1.0–1.5%, de-risking por DD, heat máximo 3R,
               correlación, kill-switch diario/semanal
  validate/    puertas G0–G7, walk-forward, Monte Carlo, atribución de valles
  report/      equity, tabla anual, R-múltiplos, informe de valle
```

### 5.2 Señal S1 — XAU Expansion Breakout (la que hoy tiene evidencia)

- Universo: XAUUSD M15; rango de 16 velas ≤2.8 ATR; cuerpo ≥1.10× cuerpo medio; buffer 0.04 ATR.
- Régimen: **H1 y H4 alineados** (EMA20>EMA50 y EMA50>EMA200 para largo; inverso para corto). Sin alineación, no hay trade.
- Entrada: cierre de la vela de ruptura, ejecución al open siguiente.
- Stop: 4.0–4.4 ATR (nunca dentro del rango); TP: 2.9× el stop; time exit 96–120 velas.
- Ventana: 13–16 hora servidor (10–13 UTC). La variante 16–19 tiene mejor PF pero solo 42 trades: se mantiene como **sombra**, no como producción.
- Filtro de coste pre-trade: si `(spread + comisión + swap_estimado) / riesgo > 8%`, no operar.

### 5.3 Señal S2 — MR2 D1 USA30 (diversificador débil)

PF 1.58, DD 7.7%, t≈1.6, 2021–2026. No es operable por sí sola; se mantiene solo si su correlación con S1 es <0.2 y aporta en el bootstrap de cartera. Si no, se descarta.

### 5.4 Gestión de riesgo y escalera hasta DD 15%

1. Riesgo por trade: **1.0%** inicial (DD esperado ~7%).
2. Si 20 trades con PF>1.2 y DD realizado <6% → **1.25%**.
3. Si 50 trades y DD <8% → **1.5%** (DD ~10%).
4. Techo: **1.8%** solo si el DD p95 de Monte Carlo ≤15%. Nunca más.
5. De-risking: al alcanzar −5R desde el máximo, riesgo ×0.5 hasta recuperar.
6. Heat máximo de cartera: 3R abiertos; máximo 2 posiciones correlacionadas.
7. Kill-switch: −8R en 20 trades o −10% de equity → parar y revisar.

Con 1.5% y +37.9R en 4.3 años: ~57% acumulado (~11%/anual), DD ~10%. Con compounding y 1.8%: ~13–15%/anual, DD 13–15%. **Eso es el techo realista; cualquier promesa mayor es un backtest mentiroso.**

### 5.5 Validación por puertas (no se pasa a la siguiente sin cerrar la anterior)

| Puerta | Criterio |
|---|---|
| G0 Código | Sin look-ahead, SL prioritario, gap al open, sin solapamiento, sin `np.random` en PnL |
| G1 Costes | Spread real por hora, comisión, swap, slippage 0.05–0.10 USD/oz |
| G2 IS | 2022-08→2024-12: PF ≥1.2 y DD ≤10R |
| G3 OOS | 2025-01→2026-11: PF ≥1.2 y al menos 2 trimestres positivos |
| G4 Ticks | Model=4 sobre 12 meses: PF dentro de ±15% del M15 y DD ≤15% |
| G5 Robustez | Meseta ±25% en k, hold y ventana; PF no cae >20% |
| G6 Monte Carlo | 1.000 bootstrap por bloques: DD p95 ≤15%, PF p05 ≥1.05 |
| G7 Forward | 8 semanas demo; desviación de PF ≤25% |

**Ningún candidato actual ha pasado G3–G7.** S1 pasó G0–G2 y G5; G3 es parcial (2025–26 concentrado).

### 5.6 Qué NO hará RCE

- No usará volumen de Deriv como filtro (no reproducible en Dukascopy).
- No hará grid search sobre el tramo que se reporta.
- No operará símbolos sin datos independientes (Volatility 75).
- No mezclará símbolos en un mismo DataFrame sin separar fronteras (fuga del repo 6).
- No confundirá sharpe de 6 trades con evidencia.

---

## 6. Lista corta definitiva

**A. Con base real (trabajar)**
1. `bot-estrategia-del-xauusd-nueva` → S1 XAU wide-stop. **Prioridad 1.**
2. MR2 D1 USA30 → S2 diversificador. **Prioridad 3** (solo si correlación baja).

**B. Referencia metodológica (no ejecutar)**
3. `Vibe-Trading` → copiar ideas de strict OOS/risk-xray, no el stack.
4. `Mirofish` → puertas de EV neto/Brier/bootstrap.

**C. Herramientas**
5. `metatrader-mcp-server`, `day-trader-skill` (plantillas de sizing/exit).

**D. Descartados (34)**
Todos los demás de la familia ML/PSAR/ORB/Donchian/FluxoV2/TM75/CIP-Lite/sintéticos/Polymarket-crypto, más 17 copias/cascarones, 5 vacíos y los 9 terceros sin estrategia (opentrader, Kronos, Sol-Onchain, agente-copilot, multi-agente, Moltbot, xauusd-trader sin checkout).

---

## 6.1 Validación de S1 en ticks reales (Fase 1 cerrada el 2026-11-18)

Motor: `TradeX_S1_XAU.mq5` compilado y ejecutado en el terminal Dukascopy (build 6320),
XAUUSD M15, Model=4, 2024-01-01 → 2026-11-18, 207.909.791 ticks, calidad **99% ticks reales**.
Depósito 50.000 USD, riesgo 1.5% por operación, comisión del tester 0 (el CSV descuenta 7 USD/lote como testigo).

| Configuración | n | PF informe | PF CSV (neto com.) | R total | DD balance | DD equity | DD en R | t |
|---|---|---|---|---|---|---|---|---|
| Base KSL 4.4 / hold 96 | 69 | **2.17** | 2.15 | +33.6 | 6.93% | 8.92% | 4.89 | 2.68 |
| KSL 3.5 | 71 | 2.21 | 2.15 | +38.4 | 6.70% | — | 4.71 | 2.79 |
| KSL 5.3 | 69 | 2.11 | 2.11 | +28.9 | 6.36% | — | 4.44 | 2.46 |
| Hold 120 velas | 69 | 2.29 | 2.25 | +38.3 | 6.52% | — | 5.43 | 2.91 |

Beneficio neto del caso base: **+31.282 USD (+62.6%)**, Sharpe del informe 6.66.

**Lo que refuerza el resultado**
- La meseta de parámetros se mantiene en ticks: PF 2.11–2.29 en las cuatro configuraciones, sin acantilados.
- El coste real de spread medido es ~2% de R (stop ~37 USD de media), no el 6.5% que temíamos; el filtro `InpMaxCostPctR=8` casi nunca se dispara. La comisión de 7 USD/lote mueve el PF de 2.17 a 2.15.
- Exposición del 6.9% del tiempo (24,5 h por operación de media): no es un sistema que necesite estar pegado a la pantalla.

**Lo que lo debilita (y hay que decirlo)**
- **No hay OOS pre-2024 en ticks**: Dukascopy solo sirve ticks XAUUSD desde 2024-01. El OOS 2022–2023 solo existe en M15 con ticks sintéticos, y ahí S1 da PF 1.89.
- Concentración temporal: 2024 +3.9R (26 trades, 42% acierto), 2025 +18.8R, 2026 +10.8R. **El 88% del beneficio está en 2025–2026.**
- El drawdown máximo en R tarda **147 días** en recuperarse (mayo → octubre 2026) y la racha perdedora máxima es de 5 trades. Con 1.5% de riesgo eso es ~7% de cuenta y cinco meses de travesía.
- El lado corto no está probado: 16 operaciones, PF 1.40, +3.5R de 33.6R totales.

**Veredicto:** S1 **pasa la puerta G4** (PF ≥ 1.6 y DD ≤ 12% en ticks) y es el primer sistema del audit que lo consigue. Pero **falla G5** (OOS independiente) — ver §6.1.1.

### 6.1.1 Ruptura de muestra: 2024 como out-of-sample

> **Corrección (18-nov, ver §9.4):** esta etiqueta es optimista. Los parámetros del
> caso base se eligieron mirando M15 hasta 2026, así que 2024 no es un holdout
> limpio. Se conserva la sección porque el número (PF 1,30, t=0,55) sigue siendo
> el mejor retrato del año flojo, pero el único corte limpio es el de GA-B
> (2025-2026).

Ejecuté el EA compilado por separado, sin tocar parámetros: 2024 solo (OOS) y 2025–2026 (IS).

| Tramo | n | WR | PF informe | PF CSV | R | DD balance | DD equity | t | p |
|---|---|---|---|---|---|---|---|---|---|
| **2024 (OOS)** | 26 | 42,3% | **1,30** | 1,31 | +3,9 | 4,25% | 5,84% | **0,55** | 0,29 |
| 2025–2026 (IS) | 43 | 60,5% | 2,63 | 2,80 | +29,7 | 7,02% | 8,99% | 2,90 | 0,002 |

Variantes sobre el 2024 OOS: KSL 3.5 → **PF 0,97** (pierde), KSL 5.3 → 1,13, hold 120 → 1,27, hold 1000 → 1,20 con DD 9,25%.

**Qué significa esto, sin maquillaje:** el resultado de 2024 es indistinguible de cero (t=0,55). La única configuración que gana en los dos tramos es la base, y lo hace con un PF que en 2024 es de 1,3. El sistema no tiene un edge demostrado; tiene un edge **observado en un régimen concreto** (oro acelerando en 2025–2026). Un seguidor de tendencia que en un año alcista del oro (+27% en 2024) solo saca +5,8% no es un sistema robusto: es un sistema que necesita que el régimen sea el suyo.

**Consecuencia operativa:** no se pone capital real. El forward demo sigue teniendo sentido, pero con un objetivo distinto: no medir PnL (5 trades en 8 semanas no prueban nada), sino **medir ejecución** — deslizamiento real, spread en la ventana 13–16, diferencia entre el fill del EA y el del backtest.

### 6.1.2 Hallazgo colateral: techo de volatilidad

Explorando qué separa los trades buenos de los malos apareció un patrón consistente: **cuanto más alta la volatilidad relativa en la entrada (ATR(14)/precio), peor el resultado**. Dividiendo cada año por su mediana de ATR%:

| Año | mitad ATR bajo | mitad ATR alto |
|---|---|---|
| 2024 | +6,04R | −2,13R |
| 2025 | +15,18R | +3,65R |
| 2026 | +10,47R | +0,37R |

3 de 3 años en la misma dirección. Añadí al EA el input `InpMaxATRPct` (por defecto **0 = desactivado**). Con umbral 0,18:

| Tramo | PF sin filtro | PF con filtro | R sin | R con |
|---|---|---|---|---|
| 2024 | 1,30 | 1,46 | +3,91 | +5,06 |
| 2025–2026 | 2,80 | 6,31 | +29,67 | +27,73 |

Pero en el tramo 2022–2023 (M15) el filtro **empeora** (PF 1,31 → 1,16) y el umbral 0,18 sale de mirar los mismos trades que luego mido. Es una hipótesis, no una mejora validada: se queda desactivada y se registra en la demo para decidir con datos nuevos.

---

## 6.2 Bróker: datos y ejecución son dos decisiones distintas

**Para datos históricos: Dukascopy, sin discusión.** Es el único que sirvió 208M ticks reales de XAUUSD desde 2024-01, con calidad verificada al 99%. Pepperstone solo tiene ago–nov 2026. Para construir y auditar sistemas, la cuenta demo Dukascopy se queda.

**Para cuenta real: el problema es el swap del largo en oro.** Dukascopy cobra −1.743 USD/oz/noche por largo y paga +0.873 por corto (triple los miércoles). S1 mantiene posiciones una media de 24,5 h, muchas de ellas multi-día: el swap es un coste estructural, no un detalle.

Candidatos a comparar antes de abrir cuenta real:

| Criterio | Por qué importa en S1 |
|---|---|
| Swap largo XAUUSD | Es el mayor coste recurrente del sistema (holds de 1–5 días) |
| Comisión por lote | El CSV ya descuenta 7 USD/lote; si es más, el PF baja |
| Spread medio en 13–16 servidor | La ventana de entrada es la de mayor liquidez, pero el TP se toca fuera |
| Regulación y retirada | Cuenta real, no demo |

Recomendación operativa: **mantener Dukascopy como motor de datos/backtest y pedir a Pepperstone e IC Markets el swap publicado de XAUUSD antes de elegir live.** Si el swap del largo es peor que −1.74 USD/oz, reejecutar el backtest con ese valor: el sistema puede seguir siendo rentable, pero el margen se estrecha y cambia el riesgo máximo tolerado.

**Orden recomendado:** forward demo en Dukascopy (donde ya está todo montado) durante 8 semanas → en paralelo, comparar swap real de los dos candidatos → elegir live con datos, no con intuición.

---

## 7. Plan de ejecución propuesto

**Fase 1 — Convertir S1 en EA y validar con ticks (2–3 días). ✅ CERRADA 2026-11-18**
- EA MQ5 con inputs: `KSl=4.4`, `KTP=12.76`, `HoldBars=96`, `Hours=13-16`, `StrictTrend=true`.
- `.set` con cabecera `[TesterInputs]` y auditoría contra el bloque “Parámetros de entrada”.
- Model=4 sobre 2022-08→2026-11 (Dukascopy) y 12 meses Pepperstone si hay ticks.
- Criterio: PF ≥1.6 y DD ≤12% en ticks; si no, archivar.
- **Resultado:** PF 2.17, DD 6.93% balance / 8.92% equity, 69 trades, +31.282 USD. Pasa G4.
- **G5 fallado:** 2024 aislado da PF 1,30 y t=0,55. Ver §6.1.1.
- **No cumplido:** el rango 2022–2023 no tiene ticks reales; Pepperstone solo tiene ago–nov 2026.

**Fase 2 — Motor RCE y cartera (3–4 días).**
- Portar el simulador honesto a módulo reutilizable + swap + slippage.
- Añadir S2 y medir correlación/bootstrap de cartera.
- Implementar escalera de riesgo y kill-switch.

**Fase 3 — Forward demo (8 semanas).**
- S1 con **1,0%** de riesgo, registro diario de spread/swap real y desviación vs backtest.
- Registro obligatorio en cada entrada: ATR%, spread, fill vs precio teórico, slippage en puntos.
- Criterio de éxito **de ejecución** (no de PnL): slippage medio < 30 puntos, spread medio en ventana ≤ 1,0 USD, fill dentro de 1 tick del teórico en ≥ 90% de las entradas.
- No se sube a real sin G7 (ejecución conforme + 3 meses sin desviaciones).

**Fase 4 — Ampliar universo (solo si Fase 3 pasa).**
- Probar la misma lógica coste-consciente en USA500/USA30 D1 y EURUSD D1, con datos 2021–2023.
- Cualquier nuevo candidato entra por las mismas puertas, no por entusiasmo.

---

## 8. Decisiones que necesito de ti

1. **Fase 1 cerrada, G4 pasado, G5 fallado.** S1 está construido y validado en ticks, y la partición 2024 confirma que el edge es de régimen, no estructural. No hay capital real.
2. **Siguiente paso recomendado:** forward demo a **1,0% de riesgo** durante 8 semanas, con el objetivo de medir ejecución (deslizamiento, spread, fill) y no PnL. Registrar ATR% en cada entrada para decidir después si el techo de volatilidad merece la pena.
3. **Bróker:** mantener Dukascopy para datos y demo; pedir swap publicado de XAUUSD a Pepperstone e IC Markets antes de abrir real. Ver §6.2.

**Escalera de riesgo condicionada al resultado del demo** (bootstrap sobre los 69 trades, 20.000 remuestreos):

| Riesgo | DD mediano | DD p95 | P(DD>15%) | Retorno mediano |
|---|---|---|---|---|
| 0,75% | 3,8% | 7,1% | 0,0% | +28% |
| 1,00% | 5,1% | 9,3% | 0,1% | +38% |
| 1,25% | 6,4% | 11,5% | 0,9% | +50% |
| 1,50% | 7,6% | 13,6% | 2,7% | +62% |
| 1,75% | 8,8% | 15,8% | 6,8% | +75% |
| 2,00% | 10,0% | 17,8% | 12,5% | +89% |

El bootstrap asume que el edge observado es real; como el OOS dice que no lo sabemos, **1,0% es el techo razonable hasta que el demo demuestre algo**. La escalera solo se sube si el demo bate el backtest en ejecución y la volatilidad no se sale de rango.

---

## Anexo — Artefactos

- `resultados/tradex/robust.csv`: 60 combinaciones (ventana × tendencia × k × hold) con IS/OOS, PF, DD, t y coste/R.
- `resultados/tradex/cost_lab.csv`: primer barrido coste-aware (base → k4).
- `resultados/tradex/S1_ticks_2024_2026.htm`: informe MT5 Model=4 principal (99% ticks reales, 208M ticks).
- `resultados/tradex/S1_ticks_trades.csv`: 69 trades del caso base con R neto de comisión.
- `resultados/tradex/S1_ticks_trades_k35.csv`, `_k53.csv`, `_h120.csv`: robustez en ticks.
- `resultados/tradex/S1_split_2024_OOS.htm` y `S1_split_2025_2026_IS.htm`: informes de la ruptura de muestra.
- `resultados/tradex/OOS2024_*.csv`, `IS2025_2026_*.csv`, `REG2024_off.csv`: trades de cada tramo (incluye la corrida de regresión con `InpMaxATRPct=0`).
- `resultados/tradex/metricas_s1.json`: métricas consolidadas (M15 + ticks + split + volatilidad + bróker).
- `TradeX_S1_XAU/TradeX_S1_XAU.mq5`: fuente del EA validado (v1.10, añade `InpMaxATRPct`).
- `C:\Users\javie\AppData\Local\Temp\opencode\utbot\xau_cost_lab.py`: réplica parametrizada y simulador con swap.
- `C:\Users\javie\AppData\Local\Temp\opencode\utbot\xau_swap.py`: revaluación con swap real Dukascopy.
- `C:\Users\javie\AppData\Local\Temp\opencode\utbot\xau_robust.py`: mesh de robustez IS/OOS.

---

# 9. Cierre del 18-nov: GA-B, robustez y correcciones de etiqueta

## 9.1 De dónde sale GA-B

Optimización genética con doble split temporal y fitness `R/(DD+3)` con mínimo de
12 trades (equivalente a Calmar, adoptado de Freqtrade). Split A (train 2022-2023
→ test 2024) **falla** en test (PF 0,93-1,00). Split B (train 2022-2024 → test
2025-2026) da PF 3,2-3,8 en el tramo no visto. Ambos splits convergen al mismo
atractor: `rb=20, MaxRangeATR=3.4, ImpulseMult=1.05, BufferATR=0, horas 13-17,
MaxATRPct=0.16, KSL=5.2, hold 120`, con el TP entre 3,1× y 3,5× KSL.

## 9.2 Ticks reales, 2024-01-01 → 2026-11-18 (Model=4, 208M ticks, 99% reales)

| Config | Trades | PF | Neto USD | DD balance | DD equity | Sharpe | Recuperación |
|---|---|---|---|---|---|---|---|
| Base v1.10 | 69 | 2,17 | 31.282,72 | 6,93% | 8,92% | 6,66 | 4,02 |
| GA-A | 44 | 2,59 | 27.465,56 | 4,47% | 6,98% | 6,03 | 7,69 |
| **GA-B** | **46** | **3,05** | **33.689,46** | **4,26%** | **6,98%** | **9,04** | **9,43** |

GA-B gana en PF, DD, Sharpe y beneficio absoluto, con 23 operaciones menos.

## 9.3 Robustez (8 variantes en ticks, 2024-2026)

| Variante | n | PF | R | DD (R) | t |
|---|---|---|---|---|---|
| base GA-B | 46 | 2,86 | 35,94 | 3,17 | 3,07 |
| rb18 | 51 | 2,87 | 40,44 | 3,17 | 3,14 |
| rb22 | 40 | 4,14 | 41,85 | 3,17 | 3,91 |
| cap18 | 63 | 2,07 | 31,15 | 3,17 | 2,42 |
| cap14 | 30 | 3,15 | 26,57 | 3,17 | 2,75 |
| ksl48 | 46 | 2,87 | 38,46 | 3,20 | 3,12 |
| ksl56 | 46 | 2,63 | 31,19 | 3,20 | 2,77 |
| h168 | 46 | 2,81 | 35,88 | 4,09 | 2,90 |
| h18 | 47 | 2,71 | 34,85 | 3,17 | 2,94 |

8/8 variantes rentables, 7/8 con PF ≥ 2,5, DD entre 3,17 y 4,09 R. Es una
**meseta**, no un pico: mover los parámetros ±10-20% no rompe el sistema. El único
punto flojo es `cap18`, que confirma que subir el techo de volatilidad empeora.

## 9.4 El out-of-sample de verdad (y la corrección de etiqueta)

**Corrección importante:** el tramo 2024 que este documento llamaba "OOS" en
§6.1.1 **no es out-of-sample** para el caso base. Los parámetros del caso base se
eligieron mirando M15 hasta 2026, y para GA-B el 2024 fue directamente parte del
entrenamiento del algoritmo genético. Etiquetarlo como OOS era optimista.

El único corte limpio disponible es el de GA-B: el GA nunca vio 2025-2026.

| Tramo | n | PF | Neto | DD balance | DD equity | Sharpe |
|---|---|---|---|---|---|---|
| IS puro 2024 (dentro del train de GA-B) | 18 | 1,60 | +5,94R | 4,61% | — | — |
| **OOS real 2025-2026 (corrida aislada)** | **28** | **4,28** | **26.921,16** | **4,26%** | **5,23%** | **11,38** |

Matiz honesto: 2025-2026 no se usó para calcular la fitness, pero **sí para
desempatar GA-A contra GA-B** (ambos tenían la misma fitness en train). Eso hace
del holdout un tramo *semilimpio*: la cifra 4,28 está sesgada al alza. Un rango
realista para el futuro es **PF 1,6-2,3**, que es lo que dan 2024 y la muestra
completa, no 4,28.

## 9.5 Protecciones (v1.11)

Implementadas (StoplossGuard, MaxDrawdown sobre equity, Cooldown), compiladas con
0 errores y 0 warnings, y **off por defecto**. Verificación:

- **Regresión exacta:** con `InpUseProtections=false` el resultado es idéntico
  byte a byte al validado (46 trades, PF 3,05, 33.689,46 USD).
- **El código funciona:** con MaxDD 6% disparó el 2024-02-15 (DD equity 6,04%) y
  bloqueó 48 h (126 velas). Con 12% no disparó nunca.
- **No descartan ni una operación**: S1 opera una vez por semana, así que un
  bloqueo de 24-48 h casi nunca encuentra una señal dentro. Son un seguro de
  cola, no un optimizador de DD. Detalle en `PROTECCIONES_S1.md`.

## 9.6 Pruebas transversales (recursive-analysis adaptado)

- **Retraso de señal:** PF 2,33 → 2,19 → 1,97 → 1,93 con 0/1/2/3 velas de
  retraso (83% del base con 3 velas). El edge no vive del timing fino.
- **Arranques escalonados:** PF entre 2,15 y 2,82 según la fecha de inicio. Sin
  estado oculto.
- **Paridad:** 5/5 reglas de NautilusTrader verificadas en el código; el control
  negativo da 0/5.

## 9.7 Veredicto final

GA-B pasa **7/7 puertas** de `herramientas/veredicto.py`. Pero el techo realista
no es el 4,28 del holdout, sino el 1,6-2,3 que dan el año flojo y la muestra
completa. Con DD de equity del 6,98% a 1,5% de riesgo y bootstrap P95 del 11,5%,
la escalera admite **1,0-1,5% por operación**, no más.

Siguiente paso lógico: demo a 1,0% con registro de ejecución (slippage, spread y
fill reales), que es lo único que ninguna de estas pruebas puede medir.

## 9.8 Artefactos nuevos de esta ronda

- `herramientas/veredicto.py` — puertas G1-G7 ejecutables, con detección de OOS
  contaminado.
- `herramientas/paridad_ea.py` — auditor estático de paridad research/live.
- `resultados/SISTEMA_OPERATIVO.md` — el procedimiento completo, con los números.
- `resultados/PROTECCIONES_S1.md` — medición de las protecciones.
- `resultados/EXTRACCION_FRAMEWORKS.md` — qué se adoptó de los 5 repos.
- `resultados/tradex/S1_ticks_*.csv` — 8 variantes de robustez.
- `resultados/tradex/OOS2526_gaB.csv` — OOS real 2025-2026.
- `resultados/tradex/veredicto_gaB.json` — veredicto completo en JSON.

