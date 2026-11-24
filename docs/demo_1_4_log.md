# Demo 1,0% – Registro de ejecución (preparación 2026-11-23)

> El archivo conserva su nombre histórico (`demo_1_4_log.md`), pero la corrida
> preparada usa **1,0% por trade**. El escalado a 1,4% queda condicionado a los
> checkpoints de abajo.

## Fecha de inicio: 2026-11-23 (preparación / puesta en marcha)
## Cuenta/MTA: 1617652162 · Dukascopy-demo-mt5-1 · 0023618.3201CHF
## Símbolo: XAUUSD M15 (Dukascopy-demo-mt5-1)

## Parámetros de la corrida
- Riesgo por trade: **1,0% del balance** (100 CHF sobre 10.000 CHF)
- Depósito / balance actual: **10.000 CHF** (divisa de cuenta: CHF)
- Apalancamiento: 1:100
- Preset: `presets/S1_gaB.set` con `InpRiskPercent=1.0` (el resto de GA-B intacto)
- Parámetros clave: `InpRangeBars=20`, `InpKSL=5.2`, `InpKTP=18.2`,
  `InpHoldBars=120`, horas servidor `13-17`, `InpMaxCostPctR=8.0`
- Spread asumido: **0,495 USD/oz** (495 puntos, medido en vivo 2026-11-23)
- Comisión: **7,0 USD/lote ida+vuelta** → 0,07 USD/oz usado por el filtro
- Swap largo real: **-1068,3349778 USD/lote/noche** (≈ -10,68 USD/oz/noche)
- Swap corto real: **+535,1228126 USD/lote/noche** (≈ +5,35 USD/oz/noche)
- Magic number: 20261118
- Comentario: TradeX_S1
- Use Protections: false (validación de edge)
- Horas servidor: 13-17
- EA: `TradeX_S1_XAU.ex5` compilado el 2026-11-23 con **0 errores, 0 warnings**

## Validación previa del filtro de coste (2026-11-23)
- ATR(14) M15 en vivo: **13,8381 USD/oz**
- Distancia de stop GA-B: `5,2 × ATR` = **71,96 USD/oz**
- Coste spread+comisión: `0,495 + 0,07` = **0,565 USD/oz**
- `coste % de R = 100 × 0,565 / 71,96` = **0,79% R**
- Límite del EA: **8,0% R** → **PASA**
- **Aviso importante:** el filtro del EA **no incluye swap**. Con swap largo real
  de -10,68 USD/oz/noche y `HoldBars=120` (~30 h, 1-2 rollovers), una posición
  larga de 0,01 lote puede perder ~10,7-21,4 USD, es decir **10-21% del riesgo
  de 100 CHF**, solo por swap. No escalar riesgo sin medir el swap real primero.
- **Aviso netting:** usar una cuenta/símbolo sin otras posiciones XAUUSD de otro
  magic; el EA no reconoce posiciones ajenas y puede sumar sobre ella.

## Artefactos preparados
- EA compilado: `src\TradeX_S1_XAU.ex5` → copiado a
  `MQL5\Experts\TradeX_S1_XAU.ex5`
- Set del tester: `presets\S1_gaB.set` → copiado a
  `MQL5\Profiles\Tester\TradeX_S1_XAU.set` con `InpRiskPercent=1.0`
- Config del tester: `configs\demo_1_0_XAUUSD_M15.ini`
- Auditorías: `veredicto.py` **7/7 CAPITAL REAL**, `paridad_ea.py` **5/5**

## Resultado de la prueba de tester (2026-11-23 — NO es operación en vivo)
- Config: `configs\demo_1_0_XAUUSD_M15.ini`
- Periodo: 2026-10-01 → 2026-11-20, M15, **Model=4 (ticks reales)**
- Datos: 13.872.206 ticks de XAUUSD, 3.312 barras; prueba pasada en 7,769 s
- Balance final: **10.096,96 CHF** (+96,96 CHF, **+0,97%**)
- Trades: **1** (SELL 0,03, 2026-11-13 13:30 → 2026-11-16 20:30)
- `R_simbolo=1,0137`, `R_net7=1,0115`, swap `+1,35`, comisión `0,00`
- Filtro de coste en la entrada: **2,24% R** (ATR 6,130, spread 0,645) < 8,0% → PASS
- Salida: `Common\Files\TradeX_S1_trades.csv` (copia en `results\demo_1_0_trades.csv`)
- `OnTester result = 0` (no hay optimización; solo verificación de ejecución)

## Registro de trades (tester; la demo en vivo sigue pendiente)
| # | Fecha (HH:MM) | Lado (BUY/SELL) | R múltiple (net7) | Resultado | Swap | Comentario |
|---|---|---|---|---|---|---|
| 1 | 2026-11-13 13:30 → 11-16 20:30 | SELL 0,03 | +1,0115 | +96,96 CHF | +1,35 | Fill exacto, sin requote |
| 2 | | | | | | |
| 3 | | | | | | |
| ... | | | | | | |

## Validación de DD (cada 10 trades o al finalizar sesión)
- DD balance en la prueba: **0%** (1 trade ganador)
- Muestra insuficiente para decidir escalado: **se requieren ≥30 trades**
- Si DD ≥ 12%: **DETENER** y revisar fills/swap antes de cualquier escalado
- Si DD < 10% tras ≥30 trades con fills limpios: evaluar 1,25%, luego 1,4%
- No pasar a 1,5% sin validación de swap y slippage reales

## Observaciones de fills y slippage (tester)
- Slippage máximo observado: **0 puntos** (fill en bid/ask cotizado)
- Spread real en la entrada: **0,645 USD/oz** vs 0,495 asumido (+0,150)
- Swap recibido en el corto: **+1,35** (coherente con swap_short positivo)
- Trades con relleno de gap al abrir: **0**
- Errores/requotes: **0** (`TRADE_RETCODE_DONE`)
- Comentario: el EA respeta SL/TP en la orden y el filtro de coste pasa con margen

## Estado final
- [x] EA compilado sin errores y desplegado en el terminal
- [x] Tester con real ticks completado y CSV de trades generado
- [x] Filtro de coste validado con spread real (2,24% R < 8%)
- [x] Fills y swap registrados sin rechazos
- [ ] **Demo en vivo con 1,0% ejecutada (pendiente)**
- [ ] ≥30 trades en vivo con DD < 15% antes de escalar
- [ ] Decisión: mantener 1,0% → 1,25% → 1,4% → o reducir

## Firmas
---
Preparado por: OpenCode (agente)
Cuenta verificada: SÍ (demo Dukascopy, login 1617652162)
Resultado registrado: 2026-11-23 (tester); cierre de demo en vivo: YYYY-MM-DD
