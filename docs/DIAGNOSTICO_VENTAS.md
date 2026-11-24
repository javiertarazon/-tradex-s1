# Diagnóstico: por qué S1 casi no opera ventas

Fecha: 2026-11-24. Pregunta: el EA cierra muchos longs y muy pocos shorts
(en el veredicto GA-B: **39 BUY / 7 SELL**). ¿Es un bug o es diseño?

## Método

1. Auditoría de la lógica de entrada en `src\TradeX_S1_XAU.mq5` (líneas
   355-423) y su réplica en `research\s1_regime_ga.py` (`prep` / `signals`).
2. Conteo del embudo de filtros con los parámetros GA-B reales sobre la caché
   M15 2022-2026 (`research\diag_sides.py`, solo lectura).
3. Contraste strict trend ON/OFF y consulta del régimen actual vía MT5.

## 1. No hay asimetría en el detector de rupturas

Con los filtros comunes aplicados (hora 13-17, ATR, rango/ATR, vela de impulso):

| Ruptura | Velas |
|---|---:|
| Arriba (prepara COMPRA) | 224 |
| Abajo (prepara VENTA) | 225 |

La detección de rangos y el filtro de impulso son **simétricos**. Descartado:
bug de signo en el breakout.

## 2. El filtro de tendencia es el que elimina los shorts

El EA exige, con `InpStrictTrend=true`:

```mql5
long  -> up4 && up1   (H4 alcista Y H1 alcista)
short -> dn4 && dn1   (H4 bajista Y H1 bajista)
```

| Tras strict trend | Señales | % sobre rupturas |
|---|---:|---:|
| LONG | 81 | 36,2% |
| SHORT | 26 | 11,6% |

Causa raíz: el régimen bajista en H4 es mucho más raro que el alcista.

| Régimen | Velas | % |
|---|---:|---:|
| `up4` | 44.903 | 44,9% |
| `dn4` | 21.613 | 21,6% |
| `up1 && up4` | 27.121 | 27,1% |
| `dn1 && dn4` | 12.458 | **12,5%** |

Oro tuvo un sesgo alcista fuerte en el periodo. Exigir **ambos** timeframes
bajistas en el momento exacto de una ruptura de 20 velas M15 es poco probable.

## 3. El efecto año explica el resultado validado

| Año | Rupturas long → señales | Rupturas short → señales | `dn1&&dn4` en el año |
|---|---:|---:|---:|
| 2022 | 6 → 4 | 14 → 3 | 11,1% |
| 2023 | 77 → 21 | 90 → 15 | 17,8% |
| 2024 | 70 → 22 | 61 → **4** | 3,7% |
| 2025 | 56 → 31 | 44 → **1** | 1,2% |
| 2026 | 15 → 3 | 16 → 3 | 19,4% |

**2024 y 2025 son justo los años que sostienen la rentabilidad** (veredicto:
2024 +5,94R, 2025 +18,71R). En esos años el filtro casi anuló los shorts.
La escasez de ventas no es un fallo aislado: es consecuencia del mercado que
hizo rentable al robot.

## 4. Efecto secundario: una posición abierta bloquea señales

El EA opera una posición a la vez. En el replay de research:

- Longs: 22 de 81 señales bloqueadas (todas por otro long).
- Shorts: 8 de 26 señales bloqueadas (todas por otro short).
- Hold medio: 81,4 velas (long) vs 88,1 velas (short).

No hay canibalización cruzada relevante: el cuello de botella es el filtro de
tendencia, no la gestión de posiciones.

## 5. ¿Relajar el filtro? Contraste (solo diagnóstico, NO optimización)

| Config | Lado | Señales | Trades | PF | R | t |
|---|---|---:|---:|---:|---:|---:|
| strict ON | long | 81 | 59 | 2,40 | +37,25 | +2,86 |
| strict ON | short | 26 | 18 | **2,09** | +8,89 | +1,33 |
| strict OFF | long | 157 | 118 | 1,43 | +28,66 | +1,64 |
| strict OFF | short | 100 | 71 | **1,29** | +10,50 | +0,90 |

Relajar `InpStrictTrend` triplica los shorts (26 → 100), pero **reduce el PF
casi a la mitad (2,09 → 1,29) y pierde significancia (t 1,33 → 0,90)**. El filtro está
haciendo su trabajo de filtro de calidad. No es un bug.

## 6. Régimen actual (2026-11-24)

Consulta directa al terminal Dukascopy demo:

| TF | Close | EMA rápida | EMA lenta | `up` | `dn` |
|---|---:|---:|---:|---|---|
| H1 | 3624,39 | 3630,25 (20) | 3631,42 (50) | no | **sí** |
| H4 | 3624,37 | 3742,01 (50) | 3967,84 (200) | no | **sí** |

Hoy **sí hay tendencia bajista confirmada en H1 y H4**, por lo que el EA sí
permitiría shorts si entrara una ruptura bajista de rango en horario 13-17.

## Conclusión

- La escasez de ventas es **diseño + régimen de mercado**, no un error de código.
- El lado corto tiene **muestra insuficiente** (7 trades en el veredicto,
  18 en el replay de research): no se puede afirmar que tenga edge propio.
- **No recomendado** desactivar `InpStrictTrend` para generar más ventas:
  empeora PF y significancia, y además sería un ajuste por inspección del
  resultado (data snooping).
- Si se quiere explorar un módulo short, debe hacerse como **configuración
  separada con su propio OOS**, no como cambio del GA-B validado.

## Reproducir

```powershell
$py='D:\proyectos_javier\proyectos\TradingAgents\.venv\Scripts\python.exe'
& $py 'D:\proyectos_javier\proyectos\tradex-s1\research\diag_sides.py'
```
