# Extracción de los 5 repos: qué sirve, qué no, y qué implementamos

**Fecha:** 18-nov-2026
**Pregunta:** ¿podemos sacar estrategias y herramientas de Freqtrade, Hummingbot, NautilusTrader,
Vibe-Trading y awesome-open-source-trading para construir un bot rentable y mejorar S1?

**Respuesta corta:** estrategias no. Herramientas sí, y algunas son valiosas. Tres de los cinco
son infraestructura de ejecución, uno es metodología de auditoría y uno es un índice de enlaces.
Ninguno publica una señal con edge verificado que podamos portar.

---

## 1. Tabla de decisión

| Repo | Qué es en realidad | ¿Aporta estrategia? | Qué extraemos | Decisión |
|---|---|---|---|---|
| **Freqtrade** | Framework crypto con backtest, hyperopt y protecciones | No. Su valor es el andamiaje de validación | Protections (StoplossGuard, MaxDrawdown, Cooldown), lookahead-analysis, recursive-analysis, funciones de pérdida de hyperopt | **Adoptar el andamiaje** |
| **NautilusTrader** | Motor event-driven con paridad backtest/live | No | El principio de paridad y el checklist de ejecución | **Adoptar el principio** (no el stack) |
| **Hummingbot** | Market making y arbitraje crypto | No aplica | Solo la idea de coste de ejecución como variable de primera clase | **Rechazar** (mercado y horizonte distintos) |
| **Vibe-Trading** | Repo de agentes con logs auditables | Ya auditado: su valor es el registro, no la señal | Risk-xray, logs por corrida, OOS estricto | **Ya incorporado** en el protocolo G1–G7 |
| **awesome-open-source-trading** | Índice de ~450 proyectos y papers | No. Es un mapa de "rendimientos declarados" | Fuente de candidatos y de metodología, nunca de parámetros | **Usar como índice, no como evidencia** |

---

## 2. Freqtrade — el único que aporta piezas nuevas y verificables

### 2.1 Protections (lo más valioso)

Freqtrade define cuatro protecciones que se evalúan antes de abrir operación y que en backtest
solo se activan con `--enable-protections`:

| Protección | Semántica | Por qué nos importa |
|---|---|---|
| `StoplossGuard` | Si hay N stop-loss dentro de una ventana, bloquea operar durante X | S1 tuvo 5 pérdidas seguidas y 147 días de DD: esto lo habría cortado |
| `MaxDrawdown` (`calculation_mode: "equity"`) | Si el DD de equity supera un umbral, bloquea X tiempo | Nuestro techo declarado es DD ≤15%: esto lo hace ejecutable, no aspiracional |
| `CooldownPeriod` | Tras cerrar, no reentrar durante X | Evita reentradas impulsivas en la misma sesión |
| `LowProfitPairs` | Bloquea un símbolo con PnL pobre en ventana | Nosotros operamos un solo símbolo: se traduce en pausa global |

**Ya está implementado en `TradeX_S1_XAU.mq5` v1.11** como grupo `=== PROTECCIONES (estilo Freqtrade) ===`,
con `InpUseProtections=false` por defecto para no alterar el backtest validado.

Medición en la secuencia real de trades: **las tres protecciones disparan, pero no
descartan ni una operación** (S1 opera una vez por semana y los stops quedan a días
de distancia). Es decir: aquí no reducen el DD, son un seguro contra un escenario de
cola. Detalle y números en `PROTECCIONES.md`.

### 2.2 lookahead-analysis — el test que nos faltaba

Freqtrade encadena backtests y detecta sesgo mirando si los indicadores cambian al recalcular con
datos recortados. La idea central es válida para cualquier motor: **si el resultado depende de datos
que en vivo no estarían disponibles, el backtest miente**.

Adaptación a MT5 (3 pruebas, sin reescribir el motor):

1. **Desplazamiento de señal**: ejecutar el EA con las señales desplazadas una vela más
   (`shift 1 → 2`). Si el PF se mantiene, el sistema no depende del instante exacto; si colapsa,
   el edge estaba en el timing fino y es frágil.
2. **Recorte de historia**: repetir el backtest empezando en fechas distintas. Si el resultado
   depende de la fecha de arranque, hay estado oculto o indicadores mal inicializados.
3. **Latencia añadida**: entrar al cierre de la vela siguiente en vez del open inmediato. Mide
   cuánto del edge es sensibilidad al fill (esto ya lo hace el Model=4 con ticks reales).

La prueba 1 es la que Freqtrade llama "recursive-analysis" y es la más barata de ejecutar.

### 2.3 Funciones de pérdida de hyperopt

Freqtrade separa la función objetivo del resultado bruto: `SharpeHyperOptLoss`,
`SortinoHyperOptLoss`, `CalmarHyperOptLoss`, `MaxDrawdownHyperOptLoss`, `ProfitHyperOptLoss`.
Nuestro GA ya usa una variante de Calmar (`R / (DD + 3)`) con mínimo de 12 trades. Lo que
adoptamos de ellos es formalizar la restricción: **una configuración con menos de N trades no
puntúa**, aunque su ratio sea espectacular. Sin eso, el optimizador converge a 4 trades perfectos.

### 2.4 Lo que NO copiamos

- **FreqAI**: ML sobre precios con features derivadas del mismo precio. Es exactamente el patrón
  que falló en 9 de los repos auditados (entrenar y validar sobre el mismo tramo).
- **Pairlists**: selección dinámica de pares por volumen; nosotros operamos un símbolo.
- **Ecosistema crypto**: comisiones, funding y microestructura no se trasladan a XAUUSD.

---

## 3. NautilusTrader — el principio, no el código

Su tesis es "research-to-live parity": el mismo núcleo event-driven corre en backtest y en vivo,
así que lo que ves en research es lo que se ejecuta. Es la respuesta correcta al problema que
teníamos (backtests bonitos y cuentas reales perdedoras), pero **no hacen falta 40.000 líneas de
Python para conseguirlo en MT5**.

Checklist de paridad que aplicamos a S1 (5 reglas, todas verificables en el código):

1. La decisión se toma **solo con barras cerradas** (`shift >= 1`). Nunca con la barra en curso.
2. SL, TP y lote se fijan **en el momento de la orden**, no después por gestión.
3. El sizing usa `ACCOUNT_BALANCE` y `SYMBOL_TRADE_TICK_VALUE` del servidor, no constantes.
4. No hay órdenes pendientes ni modificaciones posteriores: lo que se envía es lo que se ejecuta.
5. El mismo `.ex5` corre en tester y en vivo; no hay versión "de backtest".

Riesgo de adoptar el stack completo: doble mantenimiento (Python + MQL5), dos fuentes de verdad y
meses de trabajo sin mejorar el edge. Se rechaza.

---

## 4. Hummingbot — no aplica, y decirlo ahorra tiempo

Market making y arbitraje en crypto: compite por latencia, por rebajas de comisión y por inventario.
Nuestro sistema opera M15 con holds de ~24 h y paga spread. No hay ninguna pieza reutilizable
salvo una idea ya incorporada: **el coste de ejecución es una variable de primera clase**, que en
S1 es `InpMaxCostPctR` (coste máximo como % de R).

Adoptar Hummingbot sería cambiar de negocio, no mejorar el nuestro.

---

## 5. Vibe-Trading — ya explotado

Se auditó en la ronda anterior. Aporta tres cosas que ya están en el protocolo:

- **Registro por corrida**: cada resultado con su dataset, versión y logs. Nuestro equivalente son
  los CSV de trades por corrida y los informes `.htm` archivados en `results/trades/`.
- **Risk-xray**: descomposición del riesgo por operación, lado y régimen. Es lo que produjo el
  hallazgo del ATR% y el reparto largo/corto (53 largos PF 2.47 vs 16 cortos PF 1.40).
- **OOS estricto**: no reportar in-sample como si fuera OOS. Es la razón por la que hoy sabemos
  que 2024 no confirma.

Lo que no se adopta: la capa de agentes. Añade una caja negra encima de una estrategia que todavía
no ha demostrado edge; primero se arregla el edge.

---

## 6. awesome-open-source-trading — un mapa, no una mina

El repo lista ~450 proyectos y ~110 documentos, con notas sobre qué está probado out-of-sample,
qué incluye costes y qué es reproducible. Es útil como **índice de metodología** y como **cantera
de candidatos**. Peligroso como **fuente de parámetros**: los "rendimientos declarados" son
exactamente el tipo de afirmación que en nuestra auditoría no sobrevivió al spread real.

Regla de uso: cualquier estrategia que salga de esa lista entra por las mismas puertas G1–G7, con
ticks reales, y se compara contra S1 en igualdad de condiciones. Sin excepciones por prestigio
del repo de origen.

---

## 7. Backlog priorizado (lo que se implementa)

| # | Pieza | Origen | Estado | Criterio de aceptación |
|---|---|---|---|---|
| 1 | Protecciones MQL5 (SLGuard, MaxDD equity, Cooldown) | Freqtrade | **Implementado y compilado (v1.11, 0 errores). Verificado en ticks: ver `PROTECCIONES.md`** | Con `InpUseProtections=false` el resultado debe ser idéntico al validado (regresión) |
| 2 | Test de desplazamiento de señal | Freqtrade recursive-analysis | **Hecho** | PF con 3 velas de retraso = 83% del base (criterio ≥70%): pasa |
| 3 | Objetivo Calmar + mínimo de trades en el GA | Freqtrade hyperopt | **Ya aplicado** | Ninguna configuración con < 12 trades puntúa |
| 4 | Checklist de paridad | NautilusTrader | **Automatizado en `tools/paridad_ea.py`**: S1 5/5, control negativo 0/5 | 5/5 reglas verificadas en el código |
| 5 | Pipeline de 10 candidatos del índice | awesome-list | Opcional | Cada uno pasa G1 (datos) y G2 (costes) antes de codificar |

---

## 8. Lo que esto NO resuelve

El problema medido de S1 no es de infraestructura: es que **2024 da PF 1,30 con t=0,55**. Las
protecciones reducen el daño de un drawdown y el GA mejora el perfil (PF 3,05 y DD 4,26% en ticks),
pero ninguna de las dos cosas crea edge donde no lo hay ni convierte un sistema de régimen en un
sistema estructural.

Por eso el orden es: protecciones → verificación en ticks → demo de ejecución → y solo entonces
capital. Cualquier afirmación de "bot rentable" antes de eso es una opinión, no un resultado.
