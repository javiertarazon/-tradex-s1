# Sistema operativo de validación (lo que sí se adopta de los 5 repos)

**Fecha:** 18-nov-2026
**Idea:** los repos no aportaron estrategias, pero sí un método. Este documento
convierte ese método en dos herramientas ejecutables y lo aplica a S1. No es
teoría: los números de abajo salen de correrlas hoy.

```
datos reales -> backtest MT5 (ticks) -> veredicto.py (G1-G7) -> paridad_ea.py (5 reglas)
                                        ^
                    pruebas transversales: retraso de señal, arranques escalonados
```

---

## 1. `tools/veredicto.py` — las puertas G1–G7 en código

Entra el CSV que escribe `OnTester` y sale PASS/FAIL por puerta. Juzga con
`R_net7` (el más conservador: descuenta spread, swap y comisión por lote).

| Puerta | Criterio |
|---|---|
| G1 datos | ≥2 años y ≥30 trades |
| G2 costes | R_neto/R_bruto ≥ 0,90 y coste medio ≤ 0,10R |
| G3 robustez | ninguna variante con PF < 65% del base ni DD > 150% |
| G4 in-sample | n ≥ 30, PF ≥ 1,5, t ≥ 2,0, DD ≤ 15% al riesgo declarado |
| G5 out-of-sample | n ≥ 10, PF ≥ 1,2, R > 0, t ≥ 1,0 |
| G6 bootstrap | P95 del DD (20.000 remuestreos) ≤ 15% |
| G7 estabilidad | ≥60% de años en positivo y peor año > −20% del R total |

Salida real sobre GA-B (46 trades en ticks, 2024-2026), con el holdout
correcto de 2025-2026:

```
| G1 datos          | PASS | 3 anos con datos, 46 trades                          |
| G2 costes         | PASS | R_net7/R_simbolo=0.995, coste medio=0.004R/trade      |
| G3 robustez       | PASS | peor PF=2.07 (72% del base), peor DD=4.09R            |
| G4 in-sample      | PASS | n=46 PF=2.86 t=3.07 DD=4.8% (a 1.5%)                  |
| G5 out-of-sample  | PASS | n=28 PF=4.19 R=+30.00 t=3.26                          |
| G6 bootstrap      | PASS | P95 DD=11.5% a 1.5% riesgo (P(DD>15%)=0.94%)          |
| G7 estabilidad    | PASS | 3/3 anos positivos, peor ano=+5.94R                   |

Puertas superadas: 7/7
VEREDICTO: CAPITAL REAL (con escalera de riesgo)
```

Uso reproducible (mismo comando que generó `results/veredicto_gaB.json`):

```powershell
$py='D:\proyectos_javier\proyectos\TradingAgents\.venv\Scripts\python.exe'
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
```

Detalle importante que la herramienta deja a la vista: **G5 no lo decide el
nombre del fichero**. En nuestro caso el tramo etiquetado "OOS 2024" es en
realidad el tramo de entrenamiento de GA-B (el GA se entrenó con 2022-2024). El
holdout de verdad para GA-B es 2025-2026 (`OOS2526_gaB.csv`). La herramienta no
adivina eso: hay que pasarle `--train-end 2025`, como en el comando anterior.
Con el CSV equivocado y sin el corte, el resultado es 5/7 "SOLO DEMO"; con este
comando es 7/7 "CAPITAL REAL".

---

## 2. `tools/paridad_ea.py` — las 5 reglas de NautilusTrader

Revisa el `.mq5` en dos segundos, sin tester ni terminal:

| Regla | Qué comprueba |
|---|---|
| R1 sin look-ahead | ninguna lectura de precio con `shift 0` |
| R2 niveles en la orden | SL y TP van en el envío, no se colocan después |
| R3 sizing real | lote desde balance/equity y `SYMBOL_TRADE_TICK_VALUE` |
| R4 sin pendientes | ni limits/stops diferidos ni modificaciones |
| R5 sin bifurcación tester | el código no cambia según corra en tester o en vivo |

Resultado sobre S1: **5/5**. Control negativo (fichero con `iClose(...,0)`,
`BUY_LIMIT`, lote fijo y `MQLInfoInteger(MQL_TESTER)`): **0/5**. La herramienta
discrimina; no es un sello de goma.

Nota de alcance: `iTime(...,0)` se tolera porque solo se usa como reloj para
detectar vela nueva; el dato de tiempo de la vela en curso no filtra futuro.

---

## 3. Pruebas transversales de S1 (recursive-analysis adaptado)

### 3.1 Retraso de ejecución

Entrar 1, 2 y 3 velas M15 después de la señal. Si el edge solo existe con el
fill inmediato, es fragilidad de timing, no ventaja.

| Retraso | n | PF | % del base | R | DD (R) | t |
|---|---|---|---|---|---|---|
| 0 velas | 77 | 2,33 | 100% | +46,14 | 3,45 | 3,17 |
| 1 vela | 77 | 2,19 | 93,7% | +40,19 | 3,66 | 2,92 |
| 2 velas | 77 | 1,97 | 84,5% | +33,59 | 4,00 | 2,50 |
| 3 velas | 77 | 1,93 | 82,8% | +32,27 | 4,49 | 2,41 |

Criterio de Freqtrade: ≥70% del PF con retraso. **Pasa con margen.**

### 3.2 Arranques escalonados

Empezar el histórico en fechas distintas. Si el resultado depende del arranque,
hay estado oculto o indicadores mal inicializados.

| Desde | n | PF | R | DD (R) | t |
|---|---|---|---|---|---|
| 2022-08 | 77 | 2,33 | +46,14 | 3,45 | 3,17 |
| 2022-11 | 74 | 2,15 | +39,95 | 3,45 | 2,81 |
| 2023-02 | 68 | 2,31 | +41,63 | 3,45 | 2,99 |
| 2023-05 | 63 | 2,30 | +37,66 | 3,45 | 2,88 |
| 2023-08 | 59 | 2,25 | +34,94 | 3,45 | 2,70 |
| 2023-11 | 48 | 2,52 | +32,43 | 3,29 | 2,76 |
| 2024-02 | 43 | 2,82 | +32,95 | 3,12 | 2,93 |

Sin deriva: el PF se mueve entre 2,15 y 2,82 sin relación con la fecha de corte.
**Pasa.**

### 3.3 Años naturales (M15, GA-B)

| Año | n | PF | R | DD (R) |
|---|---|---|---|---|
| 2022 | 5 | 2,62 | +3,83 | 2,36 |
| 2023 | 26 | 2,16 | +12,65 | 3,45 |
| 2024 | 19 | 1,35 | +4,00 | 2,20 |
| 2025 | 22 | 2,39 | +13,79 | 3,12 |
| 2026 | 5 | 99,0 | +11,87 | 0,00 |

2024 sigue siendo el año flojo (PF 1,35), igual que en el EA. No es un artefacto
del motor: es el régimen.

---

## 4. Cómo se evalúa un candidato nuevo (procedimiento)

1. **G1/G2 antes de codificar:** ¿hay ticks reales del símbolo y del bróker? ¿el
   coste cabe en el presupuesto de R? Si no, se descarta sin escribir código.
2. **Implementar con paridad:** correr `paridad_ea.py`; 5/5 o no se backtestea.
3. **In-sample en ticks (Model=4)** y `veredicto.py` con `--risk`.
4. **OOS real** (tramo que el optimizador nunca vio) en ticks.
5. **Robustez:** variantes de parámetros alrededor del óptimo, retraso de señal,
   arranques escalonados.
6. **Solo si G1–G7 pasan:** escalera de riesgo (0,5% → 1,0% → 1,5%) con
   seguimiento de ejecución (slippage real, spread real, fills).

---

## 5. Qué no resuelve

- No crea edge. Si el OOS no confirma, la herramienta lo dice y no hay nada que
  optimizar alrededor.
- No sustituye los ticks reales. Un backtest con barras sigue siendo una
  aproximación aunque pase las 7 puertas.
- No valida ejecución en vivo. Eso solo lo mide la demo con registro de fills.

---

## 6. Relación con los 5 repos

Ver `EXTRACCION_FRAMEWORKS.md`. Resumen: Freqtrade aportó las protecciones y el
método de análisis; NautilusTrader, el principio de paridad; Hummingbot se
rechaza por mercado; Vibe-Trading ya estaba incorporado; awesome-list es un
índice de candidatos, nunca una fuente de parámetros.
