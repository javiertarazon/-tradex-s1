# Demo 1,4% – Registro de ejecución

## Fecha de inicio: YYYY-MM-DD
## Cuenta/MTA: [NÚMERO DE CUENTA]
## Símbolo: XAUUSD M15 [BROKER, EJ: PEPPERSTONE RAZOR]

## Parámetros de la corrida
- Riesgo por trade: 1,4% del balance
- Depósito: [MONTO EN USD]
- Spread asumido: 0,69 USD/oz (Dukascopy) o [VALUE, EJ: 0,1 para Pepperstone]
- Comisión: 0,07 USD/oz
- Swap largo: -1,7434872355 USD/oz/noche (Dukascopy) o [VALUE]
- Swap corto: +0,8733026744 USD/oz/noche (Dukascopy) o [VALUE]
- Magic number: 20261118
- Comentario: TradeX_S1
- Use Protections: false (recomendado para validación de edge)
- Horas servidor: 13-17

## Registro de trades (llenar después de cada sesión)
| # | Fecha (HH:MM) | Lado (BUY/SELL) | R múltiple | Resultado USD | Comentario |
|---|---|---|---|---|---|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |
| 4 | | | | | |
| 5 | | | | | |
| ... | | | | | |

## Validación de DD (hacer cada 10 trades o al finalizar sesión)
- DD balance actual: [PORCENTAJE, EJ: 8,2%]
- Pico de equity: [VALOR ABSOLUTO]
- ¿DD < 15%? [SÍ/NO]
- Si DD ≥ 12%: DETENER corrida y reducir riesgo a 1,0% de inmediato
- Si DD < 10%: Puede continuar con 1,4% o probar 1,5%

## Observaciones de fills y slippage
- Slippage máximo observado: [PUNTOS, EJ: 2 puntos]
- Spread real vs asumido: [DIFERENCIA, EJ: spread 0,8 vs asumido 0,69]
- Trades con relleno de gap al abrir: [NÚMERO]
- Errores/requotes: [CANTIDAD]
- Comentario general: [LO QUE SE NOTÓ EN LA SESIÓN]

## Estado final de la demo
- [ ] DD balance por debajo de 15% al finalizar
- [ ] CSV de trades generado correctamente en: Common\Files\TradeX_S1_trades.csv
- [ ] Todas las órdenes tienen fill registrado (sin rechazos/requotes fatales)
- [ ] Slippage dentro de lo esperado (< 30 puntos)
- [ ] Decisión sobre riesgo futuro: mantener 1,4% → reducir a 1,0% → o subir a 1,5%?

## Firmas
--- 
Ejecutado por: [NOMBRE]
Cuenta verificada: [SÍ/NO]
Fecha de conclusión: YYYY-MM-DD