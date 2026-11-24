# CHANGELOG tradex-s1

## v1.11 — 2026-11-18

### Agregado
- Repositorio autocontenido `tradex-s1` con estructura completa (docs, src, presets, tools, research, results).
- Todos los scripts de research portados con rutas relativas (`paths.py`, `indicators.py`).
- Sustitución de dependencia `bot_mt5_gbpusd.indicators` por `research/indicators.py` (ATR, EMA locales).
- Archivos `research/paths.py`, `research/mt5_fetch.py`, `research/xau_cost_lab.py` actualizados para usar `paths` y entornos portables.
- `veredicto.py` y `paridad_ea.py` copiados de `herramientas/` con rutas absolutas reemplazadas por `paths`.
- `indicators.py`: funciones `atr`, `ema`, `rsi`, `heikin_ashi`, `ha_color` implementadas desde cero, idénticas a MT5 `iATR` / `iMA` EMA.
- `s1_regime_ga.py`: rutas absolutas substituidas por `import paths; import s1_regime_ga as G` (lab.load usa CSV cache o MT5_fetch).
- `s1_ga_run.py`, `s1_torneo.py`, `s1_paridad.py`, `s1_prot.py`: rutas absolutas (`C:\Users\...`) substituidas por `paths.RESULTS`, `os.path.join` y `import paths`.
- `xau_cost_lab.py`: import `from indicators import atr, ema` en lugar de `from bot_mt5_gbpusd.indicators import atr, ema`.
- `README.md` con estado 7/7, tablas de métricas, estructura, quickstart, limitaciones, veredicto.
- `CHANGELOG.md` iniciado.
- `doctores SISTEMA_OPERATIVO.md`, `PROTECCIONES.md`, `EXTRACCION_FRAMEWORKS.md`, `SINTESIS.md` copiados a `docs/`.

### Corregido
- **Etiqueta "OOS 2024" corregida**: en `SISTEMA_OPERATIVO.md` §6.1.1 y nueva §9, se aclara que el tramo "OOS 2024" es en realidad el tramo de entrenamiento de GA-B (2022-2024). El holdout real para GA-B es 2025-2026.
- **Rutas absolutas eliminadas** de todos los scripts de research: ningún archivo referencia `C:\Users\javie\...` o `C:\proyectos\...` ahora. Todo es relativo a `__file__` / `ROOT`.
- **Import `bot_mt5_gbpusd.indicators`** sustituido por `research/indicators.py` en `xau_cost_lab.py`, `s1_regime_ga.py`, `s1_paridad.py`.
- **Header `[TesterInputs]`** en todos los `.set` nuevos (confirmado: `S1_gaB.set`, `S1_gaA.set`, `S1_prot_*.set`, `S1_p_*.set`).

### Ajustado
- Protecciones estilo Freqtrade: **OFF por defecto** (documentado en README, PROTECCIONES.md y metricas_s1.json). No alteran el backtest validado; son seguro de cola.
- Escalera de riesgo documentada en `escalera_riesgo` de `metricas_s1.json` y README (0,5% → 2,5%, P95 DD 3,8% → 19,2%).
- Umbral DD 15% tolerable si aporta rentabilidad; riesgo máximo 1,0-1,5% por operación (bootstrap P95 DD 11,5% a 1,5%).
- GA: fitness `R/(DD+3)` con mínimo 12 trades; doble split temporal. Split A falla, split B converge al mismo atractor.
- Todos los `.set` nuevos llevan cabecera `[TesterInputs]` y son auditables contra el bloque "Parámetros de entrada" del informe.

### Qué se descartó en esta versión
- Nasdaq (USATECH), EURUSD ORB, USA500, familia ORB, MR2 D1, Donchian D1: definitivamente no rentables.
- `EA-milagro-carlos`, `botcopilot-sar`, `copilot-bot-v-4.11`: no rentables en real; ningún bot del usuario ha ganado dinero en real.

---

## v1.10 — 2026-11-17 (base anterior)

- EA TradeX_S1_XAU compilado v1.10, regresión exacta con protecciones OFF (46 trades, PF 3,05, 33.689,46 USD).
- Auditoría de 39 repos completada; diagnóstico forense ORB entregado.
- Métricas iniciales en `metricas_s1.json` sin las correcciones de etiqueta OOS ni la escalera de riesgo detallada.
- Herramientas `veredicto.py` y `paridad_ea.py` con rutas absolutas (no portables).