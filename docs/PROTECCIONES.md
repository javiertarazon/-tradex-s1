# Protecciones estilo Freqtrade en S1: implementación y evidencia

**Fecha:** 18-nov-2026
**Estado:** implementadas en `TradeX_S1_XAU.mq5` v1.11, compiladas (0 errores,
0 warnings) y **desactivadas por defecto**. Este documento mide si sirven.

---

## 1. Qué se implementó

| Input | Default | Semántica |
|---|---|---|
| `InpUseProtections` | `false` | interruptor general; si está off, el EA se comporta exactamente igual que v1.10 |
| `InpSlGuardCount` | 3 | StoplossGuard: N stops propios para bloquear |
| `InpSlGuardWindowH` | 24 | ventana de conteo (horas) |
| `InpSlGuardLockH` | 24 | duración del bloqueo (horas) |
| `InpMaxDDEquityPct` | 12.0 | MaxDrawdown sobre **equity** que dispara el bloqueo (%) |
| `InpMaxDDLockH` | 48 | duración del bloqueo por DD (horas) |
| `InpCooldownBars` | 0 | velas M15 de espera tras cerrar (0 = off) |

Detalles de diseño:

- El DD se mide sobre `ACCOUNT_EQUITY` (incluye PnL flotante), como Freqtrade con
  `calculation_mode: "equity"`, no sobre balance.
- Al dispararse el DD se **reinicia el pico** a la equity actual. Sin eso el
  bloqueo se repetiría para siempre tras el primer evento.
- Los stops se cuentan leyendo el historial de deals con `DEAL_REASON_SL` y el
  magic propio; no se cuentan cierres por tiempo ni por TP.
- Con `InpUseProtections=false` las funciones retornan antes de tocar nada: la
  regresión contra v1.10 debe dar resultados idénticos, byte a byte.

---

## 2. Simulación previa sobre la secuencia real de trades

Antes de gastar tiempo de tester, apliqué la lógica de protección a la lista de
trades ya simulada (M15, 2022-08→2026-11). No es un backtest nuevo: es la misma
serie de operaciones con las reglas de bloqueo encima.

**GA-B, 77 trades, riesgo 1,5% (PF 2,33 / DD 3,45R / 5,2%)**

| Protección | Disparos | Trades descartados | Efecto |
|---|---|---|---|
| StoplossGuard N=2, W=24h | 0 | 0 | ninguno |
| N=2, W=72h | 0 | 0 | ninguno |
| N=2, W=120h | 1 | 0 | ninguno |
| N=3, W=120h | 0 | 0 | ninguno |
| MaxDD ≥ 5% | 1 | 0 | ninguno |
| MaxDD ≥ 6/8/10/12% | 0 | 0 | ninguno |
| Cooldown 2/8/16 velas | — | 0 | ninguno |

**Base, 93 trades, riesgo 1,5% (PF 1,76 / DD 7,13R / 10,7%)**

| Protección | Disparos | Trades descartados | Efecto |
|---|---|---|---|
| StoplossGuard N=2, W=24h | 1 | 0 | ninguno |
| N=2, W=120h | 3 | 0 | ninguno |
| MaxDD ≥ 5% | 5 | 0 | ninguno |
| MaxDD ≥ 6/8/10% | 1 | 0 | ninguno |
| Cooldown | — | 0-1 | +0,22R (ruido) |

### Por qué apenas muerden

S1 hace **una operación por semana de media** y mantiene 24 h. Los stops, por
construcción, quedan separados por días. Un guardia que bloquea 24-48 h después
de un evento casi nunca encuentra una señal nueva dentro de la ventana.

Consecuencia: en esta estrategia las protecciones **no son un optimizador de
DD**, son un seguro contra un escenario de cola (varias pérdidas seguidas en
pocas horas) que no aparece en la muestra. Activarlas no mejora nada medible;
dejarlas activas tampoco empeora. Es una decisión de gestión de riesgo, no de
rentabilidad.

---

## 3. En MT5 (equity real)

La simulación de arriba mide DD sobre la curva de trades **cerrados**. En MT5 el
DD de equity incluye el PnL flotante, que es mayor, así que el guardia de DD
puede disparar donde el modelo dice que no. Batería en ticks, 2024-2026, GA-B:

| Corrida | Protecciones | n | PF | DD bal | DD eq | Neto |
|---|---|---|---|---|---|---|
| regresión | OFF | 46 | 3,05 | 4,26% | 6,98% | 33.689,46 |
| prot_sl | SL 3/24h, lock 24h | 46 | 3,05 | 4,26% | 6,98% | 33.689,46 |
| prot_dd | MaxDD 12%, lock 48h | 46 | 3,05 | 4,26% | 6,98% | 33.689,46 |
| prot_all | SL + DD 12% + cooldown 4 | 46 | 3,05 | 4,26% | 6,98% | 33.689,46 |
| prot_dd6 | MaxDD 6%, lock 48h | 46 | 3,05 | 4,26% | 6,98% | 33.689,46 |

Lo que dice el log del tester:

- Con MaxDD **6%** se disparó una vez, el **2024-02-15 a las 12:00**, con DD de
  equity **6,04%** → bloqueo hasta 2024-02-17 (126 velas bloqueadas).
- Con MaxDD 12% no disparó nunca (el DD máximo del período es 6,98%).
- StoplossGuard no disparó en ninguna configuración, ni con N=3/W=24h.
- **Los cinco resultados son idénticos**: ni una operación descartada.

Dos conclusiones:

1. **La implementación es correcta y está probada** (dispara, bloquea, registra).
2. **No aporta nada medible a esta estrategia.** El bloqueo cae en un hueco sin
   señales. Activarlas no cambia el PF ni el DD; solo añade una red por si el
   mercado entrega varias pérdidas seguidas en horas, algo que no ha pasado en
   la muestra.

---

## 4. Recomendación

1. **Producción/demo: `InpUseProtections=true` con MaxDD 12% y bloqueo 48 h.**
   No cambia el edge en la muestra; acota el daño si el régimen rompe el patrón.
   Es lo que un desk real exige antes de dejar un EA solo.
2. **StoplossGuard con N=3/W=24h es placebo aquí.** Si se quiere que muerda, hay
   que usar W≥120h, y entonces bloquea operaciones rentables por un susto previo.
3. **Cooldown: dejar en 0.** No aporta.
4. No presentar estas protecciones como una mejora de resultados. No lo son: son
   gestión de riesgo.
