# tradex-s1 — S1 Range Breakout coste-consciente (XAUUSD M15)

Repositorio autocontenido con la estrategia validada GA-B (v1.11), herramientas de auditoría y documentación completa. **Base para la siguiente fase (demo 1,0%).**

---

## Estado actual (18-nov-2026)

| Métrica | Valor | Comentario |
|---|---|---|
| **Trades IS (ticks 2024-2026)** | 46 | Ticks reales Dukascopy |
| **PF** | 3,05 | Fitness `R/(DD+3)` |
| **R total** | +33.689,46 USD | Depósito $50.000 |
| **DD balance** | 4,26% | Bajo riesgo 1,5%/trade |
| **DD equity** | 6,98% | Dentro del techo 15% |
| **Sharpe** | 9,04 | Muy alto (ticks reales) |
| **OOS real 2025-2026** | 28 trades, PF 4,28 | Corrida aislada, inputs explícitos |
| **Robustez 8 variantes** | 8/8 rentables | PF 2,07-4,14, DD 3,17-4,09R |
| **Puertas G1-G7** | 7/7 | CAPITAL REAL (ver veredicto.py) |

---

## Arquitectura del repo

```
tradex-s1/
├─ docs/                # Documentos maestros (SISTEMA_OPERATIVO.md, PROTECCIONES.md, etc.)
├─ src/                 # TradeX_S1_XAU.mq5 v1.11 (fuente EA)
├─ presets/             # Ficheros .set del tester MT5 (S1_gaB.set, variantes, protecciones)
├─ tools/               # veredicto.py, paridad_ea.py (auditoría automatizada)
├─ research/
│  ├─ indicators.py     # ATR, EMA locales (reemplaza bot_mt5_gbpusd.indicators)
│  ├─ paths.py          # Rutas relativas al repo (sin absolutados)
│  ├─ mt5_fetch.py      # Descarga MT5 (solo para refrescar cache)
│  ├─ xau_cost_lab.py   # Experimento coste-aware (versión portable)
│  ├─ s1_regime_ga.py   # Preparación + generación de señales + signals/sim
│  ├─ s1_ga_run.py      # Marco de optimización genética (doble split)
│  ├─ s1_torneo.py      # Torneos de candidatos anuales
│  ├─ s1_paridad.py     # 5 reglas de paridad (look-ahead, sizing, etc.)
│  └─ s1_prot.py        # Protecciones estilo Freqtrade (off por defecto)
├─ results/
│  ├─ trades/           # CSVs de trades (IS, OOS, variantes, prot_*, base_*)
│  ├─ reports/          # HTMls del tester (S1_ticks_2024_2026.htm, etc.)
│  ├─ metricas_s1.json  # Métricas agregadas (ver resumen arriba)
│  ├─ veredicto_gaB.json
│  ├─ paridad_s1.json
│  └─ resultados de la optimización genética
├─ tools/veredicto.py     # 7 puertas G1-G7 (valida datos, costes, robustez, IS, OOS, bootstrap, estabilidad)
└─ tools/paridad_ea.py    # 5 reglas de paridad NautilusTrader
```

---

## Requisitos previos

- Python 3.9+ con `pandas`, `numpy`, `MetaTrader5` (solo para refrescar la cache de datos).
- El CSV `research/data/xau_m15_2022_2026.csv` debe estar presente (6 MB; se incluye o se genera con `mt5_fetch.py`).
- Si se corre el EA en MT5, necesidad de `terminal64.exe` y credenciales Dukascopy.

---

## Instalación / primeros pasos

```powershell
# 1. Clonar o copiar el repo a la carpeta deseada
git clone https://github.com/javiertarazon/-tradex-s1.git tradex-s1
cd tradex-s1

# 2. Verificar que el CSV de datos existe
Get-Item research\data\xau_m15_2022_2026.csv

# 3. (Opcional) Refrescar la cache desde MT5
$py='D:\proyectos_javier\proyectos\TradingAgents\.venv\Scripts\python.exe'
& $py research\mt5_fetch.py

# 4. Ejecutar validación rápida (sin MT5, solo lógica interna)
& $py research\s1_paridad.py
# Debe imprimir 1 lag=0 PF=2.32 ... 3 años naturales coherentes

# 5. Ejecutar veredicto G1-G7 (7/7, decisión CAPITAL REAL)
& $py tools\veredicto.py --label "S1 GA-B v1.11 (ticks)" `
  --base results\trades\S1_ticks_trades_gaB.csv `
  --oos  results\trades\OOS2526_gaB.csv `
  --train-end 2025 `
  --variant rb18=results\trades\S1_ticks_rb18.csv `
  --variant rb22=results\trades\S1_ticks_rb22.csv `
  --variant cap18=results\trades\S1_ticks_cap18.csv `
  --variant cap14=results\trades\S1_ticks_cap14.csv `
  --variant ksl48=results\trades\S1_ticks_ksl48.csv `
  --variant ksl56=results\trades\S1_ticks_ksl56.csv `
  --variant h168=results\trades\S1_ticks_h168.csv `
  --variant he18=results\trades\S1_ticks_he18.csv `
  --risk 1.5 --out results\veredicto_gaB.json

# 6. Ejecutar paridad EA (5/5 reglas)
& $py tools\paridad_ea.py src\TradeX_S1_XAU.mq5
```

---

## Documentos clave

| Documento | Qué contiene |
|---|---|
| `docs/SISTEMA_OPERATIVO.md` | Procedimiento completo: datos → backtest → veredicto → pruebas transversales. |
| `docs/PROTECCIONES.md` | Medición de protecciones estilo Freqtrade (off por defecto; inertes: 1 trade/semana). |
| `docs/EXTRACCION_FRAMEWORKS.md` | Resumen de los 5 repos auditados; qué se adoptó y qué se descartó. |
| `docs/SINTESIS.md` | Síntesis ejecutiva: correcciones, ajustes, métricas, escalera de riesgo, OOS. |
| `docs/DIAGNOSTICO_VENTAS.md` | Por qué el EA genera pocas ventas: embudo de filtros y contraste strict ON/OFF. |
| `docs/ACTIVIDAD_S1.md` | Cómo aumentar la frecuencia de trades: sweep de palancas y variante `S1_gaB_active`. |
| `docs/OPTIMIZACION_ACTIVIDAD.md` | Optimización con DD<15%: preset `S1_opt_active`, +91% trades y +39% R. |
| `results/metricas_s1.json` | JSON con todas las métricas por variante, año, costo, robustez, etc. |

---

## Resultados resumidos

### GA-B (la elegida, v1.11)

- **IS ticks 2024-2026**: 46 trades, PF 3,05, +33.689,46 USD, DD balance 4,26%, DD equity 6,98%, Sharpe 9,04.
- **OOS real 2025-2026**: 28 trades, PF 4,28, +26.921,16 USD, DD balance 4,26%, DD equity 5,23%, Sharpe 11,38.
- **IS puro 2024**: 18 trades, PF 1,60, R +5,94.
- **Robustez**: 8 variantes sobre el óptimo → 8/8 rentables, PF 2,07-4,14, DD 3,17-4,09R. **Meseta confirmada**.

### Pruebas transversales (pasan con margen)

- **Retraso de señal**: con 3 velas de retraso PF 1,93 (83% del base). Criterio Freqtrade ≥70%: **Pasa**.
- **Arranques escalonados**: PF se mueve 2,15-2,82 sin relación con fecha de corte. **Pasa**.
- **Años naturales**: 2024 flojo (PF 1,35), 2025-2026 fuertes. No es artefacto del motor.

### Protecciones estilo Freqtrade

- **OFF por defecto**: no alteran el backtest validado (son inertes en S1; ~1 trade/semana bloqueado).
- **ON en producción**: recomendado como seguro de cola (no como optimizador).
- **MT5 medición real**: disparo MaxDD 6% el 2024-02-15 → DD equity 6,04%, 126 velas bloqueadas, 0 trades descartados. Resultados idénticos con protecciones ON/OFF.

### Escalera de riesgo (bootstrap P95 DD)

| Riesgo %/trade | P95 DD | ¿< 15%? |
|---|---|---|
| 0,5% | 3,8% | Sí |
| 1,0% | 7,7% | Sí |
| 1,25% | 9,6% | Sí |
| 1,5% | 11,5% | Sí (margen) |
| 2,0% | 15,3% | **No** (cruza 15%) |
| 2,5% | 19,2% | No |

*Recomendado máximo 1,5% por trade (bootstrap P95 DD 11,5%, P(DD>15%) = 0,94%).*

---

## Decisiones tomadas (por qué este repo)

1. **Modelo=4 (ticks reales)** como estándar; Model=0/1 solo como OOS aproximado.
2. **GA-B validado**: fitness `R/(DD+3)` con mínimo 12 trades; doble split temporal (A falla, B converge).
3. **Parámetros GA-B**: rb=20, MaxRangeATR=3.4, ImpulseMult=1,05, BufferATR=0, ATRPeriod=14, MaxATRPct=0,16, StrictTrend=true, horas servidor 13-17, KSL=5,2, KTP=18,2, RangeTargetMult=1,25, HoldBars=120.
4. **Protecciones OFF por defecto**: no alteran resultados; son seguro de cola.
5. **Riesgo 1,0-1,5% por trade**: bootstrap P95 DD 11,5% a 1,5%; a 2,0% ya cruza 15%.
6. **Resultados reproducibles**: todos los scripts usan rutas relativas (`paths.py`, `indicators.py`); la dependencia externa `bot_mt5_gbpusd.indicators` ha sido sustituida.
7. **OOS real 2025-2026**: holdout semilimpio (no entró en fitness, pero sirvió para desempatar GA-A vs GA-B).

---

## Limitaciones

- Sin OOS real antes de 2024-01 en ticks (Dukascopy solo tiene XAUUSD desde enero 2024).
- 88% del R viene de 2025-2026; 2024 aporta solo +3,9R.
- max DD en R duro 147 días (may-oct 2026).
- slippage no modelado más allá de 30 puntos de desviación.
- swap Pepperstone no confirmado.
- solo 16 cortos: el lado corto no está probado de manera robusta.

---

## Siguientes pasos (después de este repositorio)

1. **Demo 1,0%**: registrar una ejecución real con riesgo 1,0% por trade, seguimiento de fills y slippage.
2. **Validar OOS 2024**: recolectar ticks pre-2024 de otro broker (Pepperstone/IC Markets) si es necesario.
3. **Mejorar side corto**: recolectar más datos del lado corto en oro.
4. **Integrar swap real**: comparar swap Pepperstone vs Dukascopy antes de contar en la fitness.
5. **Auto-audit en CI**: incorporar `veredicto.py` y `paridad_ea.py` como pasos gate en la integración continua.