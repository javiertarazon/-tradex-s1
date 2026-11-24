# Optimización de alta frecuencia con límite de DD < 20%

Fecha: 2026-11-24. Pedido del usuario: *"quiero más frecuencia y más PnL y si
el DD sube pero no supera el 20% es aceptable"*.

## Resultado elegido

`S1_dd20_freq.set`: **rb16 · rango 6,0 ATR · impulso 1,05 · sesión 12-18h ·
hold 96 · KSL 5,2 · KTP 18,2 (3,5×) · riesgo 1,5% · circuit breaker de equity
17% / 48 h**. Strict trend permanece ON.

| Métrica | Preset 15% (`S1_opt_active`) | **Nuevo (DD<20%)** | Δ |
|---|---:|---:|---:|
| Trades 2022-2026 | 147 | **192** | **+31%** |
| Trades OOS 2025-2026 | 51 | **71** | **+39%** |
| Retorno compuesto @riesgo | ~+68% (1,0%) | **+123,8% (1,5%)** | **+82%** |
| PF full / OOS | 1,98 / 3,51 | 1,63 / 2,14 | inferior, aún rentable |
| DD observado (desde máximo histórico) | 10,5% | **16,7%** | bajo 20% |
| DD con spread estresado 1,20 | — | **17,8%** | bajo 20% |

El retorno compuesto es la medida correcta: el EA calcula el lote sobre el
balance actual (`CalcLot`), por lo que el riesgo se reaplica sobre un balance
creciente. Las cifras lineales `ΣR × riesgo%` usadas en informes anteriores
subestiman el resultado real.

## El límite de 20% es enforcement por código

El EA ya contiene un circuit breaker (`UpdateProtections`, líneas 211-234 del
fuente), inactive por defecto. Se activa con:

- `InpUseProtections=true`
- `InpMaxDDEquityPct=17.0`
- `InpMaxDDLockH=48`
- `InpSlGuardCount=0`, `InpCooldownBars=0` (se aísla solo la guarda de DD)

Si el DD desde el pico de equity alcanza 17%, bloquea nuevas entradas 48 h y
reinicia el pico. El código **no cambió**: solo inputs, así que la paridad
research/live se mantiene.

### Por qué 1,5% y no 2,0%

A 2,0% de riesgo el DD **desde el máximo histórico** llega al 21,9% incluso con
la guarda activada (el reinicio del pico permite encadenar nuevas caídas).
La guarda limita el DD *desde el pico reiniciado*, no el DD global de la cuenta.

| Riesgo | DD observado | DD estresado | Veredicto |
|---:|---:|---:|---|
| 1,0% | ~11% | ~12% | seguro, poco PnL |
| 1,25% | ~14% | ~15% | seguro |
| **1,5%** | **16,7%** | **17,8%** | **elegido** |
| 2,0% | 21,9% | 23,3% | **rompe el límite** |

## Alternativas evaluadas (mismo límite)

| Candidato | Trades | Retorno compuesto | DD obs | DD estresado | OOS PF |
|---|---:|---:|---:|---:|---:|
| **FREQ (elegido)** | **192** | **+123,8%** | 16,7% | 17,8% | 2,14 |
| MIX rb16/4,2/12-18/h96 | 163 | +141,0% | 16,9% | 17,9% | 2,68 |
| BAL rb16/5,0/13-17/h96 | 158 | +139,5% | 15,2% | 16,2% | — |
| OPT rb16/4,2/13-17/h96 | 145 | +151,1% | 15,4% | 16,3% | 3,51 |

FREQ maximiza frecuencia (prioridad del usuario) y casi dobla el PnL del preset
anterior. Si se prefiere más PnL con menos calidad de señal, MIX; si se prefiere
máxima robustez, OPT.

## Proceso

1. `research/dd20_opt.py` — grid con DD<20%, tres niveles de riesgo; 422
   supervivientes.
2. `research/dd20_final.py` — P(DD>20%) por bootstrap y costes estresados.
3. `research/dd20_pareto.py` — filtro DD obs<18% / estresado<19% / OOS PF≥2.
4. `research/dd20_guard.py` — simulación del circuit breaker, corrigiendo el DD
   medido desde el máximo histórico (no desde el pico reiniciado).

## Verificación MT5 (ticks reales, 2026-10-01 → 2026-11-20)

| Config | Trades | Neto CHF | PF | DD balance | DD equity |
|---|---:|---:|---:|---:|---:|
| GA-B base | 1 | +96,96 | — | — | — |
| Optimizado 15% | 3 | +393,12 | 62,52 | 0,06% | 2,43% |
| **DD20 FREQ** | **4** | **+377,84** | **3,28** | **1,48%** | **3,62%** |

13.872.206 ticks, 3.312 barras, sin errores. `R_net7` de los 4 trades:
−0,0559, +2,9315, +0,4192, −0,8501.

**Honestidad**: 4 trades en 7 semanas no prueban rentabilidad en vivo. La
frecuencia esperada a largo plazo es de ~43 operaciones/año, no diaria. El
bloqueo estructural sigue siendo *una posición a la vez*; levantarlo exigiría
cambiar el EA y rehacer toda la auditoría.

## Auditoría

- `paridad_ea.py`: **5/5** reejecutada sobre el fuente sin cambios
  (`results/paridad_dd20.json`).
- `veredicto.py` **7/7** (`results/veredicto_gaB.json`) corresponde a GA-B y
  sigue vigente: el EA no se modificó. **No se ha reejecutado para este preset**
  porque los CSVs de ticks de todo el periodo no están disponibles localmente
  (los ticks reales locales empiezan el 2026-10-01). Las puertas G4/G5 no
  podrían evaluarse con solo 4 trades.

## Archivos

- `presets/S1_dd20_freq.set`
- `configs/dd20_freq_1_5_XAUUSD_M15.ini` (tester)
- `configs/demo_live_dd20_freq_1_5_XAUUSD_M15.ini` (vivo, **no ejecutado**)
- `results/dd20_freq_report.htm`, `results/dd20_freq_tester.log`
- `research/dd20_*.py`

## Estado

GA-B validado intacto. EA sin cambios. Preset desplegado en
`MQL5\Profiles\Tester\` y `MQL5\Presets\`. **Ninguna configuración arrancada
en vivo**: requiere autorización explícita.
