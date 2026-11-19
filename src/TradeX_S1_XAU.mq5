//+------------------------------------------------------------------+
//|                                              TradeX_S1_XAU.mq5   |
//|  S1 - XAU Expansion Breakout coste-consciente                    |
//|                                                                  |
//|  Tesis (auditoria 2026-11-18): la senal range-breakout del repo  |
//|  bot-estrategia-del-xauusd-nueva tiene edge bruto, pero el stop  |
//|  a 0.9 ATR vive dentro del ruido M15. Con stop 4.0-4.4 ATR, TP   |
//|  2.9x el stop, hold 96 velas y alineacion estricta H1+H4:        |
//|  PF 1.89 (con swap Dukascopy), +37.9R, DD 6.5R, t=2.60.          |
//|                                                                  |
//|  Sin look-ahead: decide al cierre de la vela M15 (shift 1) y     |
//|  ejecuta al open de la siguiente. SL/TP fijados en la entrada.   |
//+------------------------------------------------------------------+
#property copyright "TradeX"
#property version   "1.11"
#property strict

#include <Trade\Trade.mqh>

//--- Estrategia
input group "=== ESTRATEGIA S1 ==="
input int      InpRangeBars          = 16;      // Velas del rango de compresion
input double   InpMaxRangeATR        = 2.8;     // Rango maximo como multiplo de ATR
input double   InpImpulseMult        = 1.10;    // Cuerpo minimo vs cuerpo medio (x)
input double   InpBufferATR          = 0.04;    // Buffer de ruptura (x ATR)
input int      InpATRPeriod          = 14;      // Periodo ATR (M15)
input double   InpMaxATRPct          = 0.0;     // Techo de volatilidad: ATR/precio*100 (0 = desactivado)
input bool     InpStrictTrend        = true;    // Exigir alineacion H1 y H4
input int      InpHourStart          = 13;      // Hora servidor inicio (GMT+3)
input int      InpHourEnd            = 16;      // Hora servidor fin (inclusive)
input bool     InpAllowLong          = true;    // Permitir largos
input bool     InpAllowShort         = true;    // Permitir cortos

//--- Salida
input group "=== SALIDA COSTE-CONSECIENTE ==="
input double   InpKSL               = 4.4;      // Stop = KSL * ATR
input double   InpKTP               = 12.76;    // TP = KTP * ATR (2.9 * KSL)
input double   InpRangeTargetMult   = 1.25;     // TP minimo = x * ancho del rango
input int      InpHoldBars          = 96;       // Salida por tiempo en velas M15

//--- Riesgo
input group "=== GESTION DE RIESGO ==="
input double   InpRiskPercent       = 1.5;      // Riesgo por operacion (% balance)
input double   InpMaxCostPctR       = 8.0;      // Coste maximo (spread+comision) como % de R
input double   InpCommissionPerLot  = 7.0;      // Comision ida+vuelta USD/lote (para el filtro)
input int      InpSlippagePoints    = 30;       // Desviacion maxima (puntos)
input long     InpMagic             = 20261118; // Magic number
input string   InpComment           = "TradeX_S1";

//--- Protecciones (estilo Freqtrade). Por defecto OFF: no alteran el
//--- backtest validado mientras no se demuestre que mejoran el DD.
input group "=== PROTECCIONES (estilo Freqtrade) ==="
input bool     InpUseProtections     = false;   // Activar el bloque de protecciones
input int      InpSlGuardCount       = 3;       // StoplossGuard: N stops para bloquear
input int      InpSlGuardWindowH     = 24;      // StoplossGuard: ventana de conteo (horas)
input int      InpSlGuardLockH       = 24;      // StoplossGuard: duracion del bloqueo (horas)
input double   InpMaxDDEquityPct     = 12.0;    // MaxDrawdown sobre equity que dispara (%)
input int      InpMaxDDLockH         = 48;      // MaxDrawdown: duracion del bloqueo (horas)
input int      InpCooldownBars       = 0;       // Cooldown: velas M15 de espera tras cerrar (0=off)

//--- Estado
CTrade   g_trade;
int      g_hATR = INVALID_HANDLE;
int      g_hH1E20 = INVALID_HANDLE, g_hH1E50 = INVALID_HANDLE;
int      g_hH4E50 = INVALID_HANDLE, g_hH4E200 = INVALID_HANDLE;
datetime g_lastBar = 0;
double   g_point = 0.0;

//--- Registro de riesgo por posicion (para el CSV de auditoria)
long     g_posId[];
double   g_posRisk[];
int      g_posSide[];     // 0 buy, 1 sell
int      g_posCount = 0;

//--- Estado de las protecciones (inertes si InpUseProtections = false)
double   g_peakEquity   = 0.0;
datetime g_slLockUntil  = 0;
datetime g_ddLockUntil  = 0;
datetime g_lastClose    = 0;
bool     g_wasInPos     = false;
int      g_statSlGuard  = 0;
int      g_statDDGuard  = 0;
int      g_statBlocked  = 0;

//+------------------------------------------------------------------+
int OnInit()
{
   g_point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);

   g_hATR = iATR(_Symbol, PERIOD_M15, InpATRPeriod);
   g_hH1E20  = iMA(_Symbol, PERIOD_H1, 20, 0, MODE_EMA, PRICE_CLOSE);
   g_hH1E50  = iMA(_Symbol, PERIOD_H1, 50, 0, MODE_EMA, PRICE_CLOSE);
   g_hH4E50  = iMA(_Symbol, PERIOD_H4, 50, 0, MODE_EMA, PRICE_CLOSE);
   g_hH4E200 = iMA(_Symbol, PERIOD_H4, 200, 0, MODE_EMA, PRICE_CLOSE);

   if(g_hATR == INVALID_HANDLE || g_hH1E20 == INVALID_HANDLE || g_hH1E50 == INVALID_HANDLE ||
      g_hH4E50 == INVALID_HANDLE || g_hH4E200 == INVALID_HANDLE)
   {
      Print("Error creando indicadores");
      return(INIT_FAILED);
   }

   g_trade.SetExpertMagicNumber((ulong)InpMagic);
   g_trade.SetDeviationInPoints(InpSlippagePoints);
   g_trade.SetTypeFillingBySymbol(_Symbol);
   ArrayResize(g_posId, 0);
   ArrayResize(g_posRisk, 0);
   ArrayResize(g_posSide, 0);
   g_posCount = 0;

   g_peakEquity   = AccountInfoDouble(ACCOUNT_EQUITY);
   g_slLockUntil  = 0;
   g_ddLockUntil  = 0;
   g_lastClose    = 0;
   g_wasInPos     = false;
   g_statSlGuard  = 0;
   g_statDDGuard  = 0;
   g_statBlocked  = 0;
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   if(g_hATR   != INVALID_HANDLE) IndicatorRelease(g_hATR);
   if(g_hH1E20 != INVALID_HANDLE) IndicatorRelease(g_hH1E20);
   if(g_hH1E50 != INVALID_HANDLE) IndicatorRelease(g_hH1E50);
   if(g_hH4E50 != INVALID_HANDLE) IndicatorRelease(g_hH4E50);
   if(g_hH4E200!= INVALID_HANDLE) IndicatorRelease(g_hH4E200);
}

//+------------------------------------------------------------------+
double CalcLot(double entry, double sl)
{
   double balance   = AccountInfoDouble(ACCOUNT_BALANCE);
   double riskMoney = balance * InpRiskPercent / 100.0;
   double slDist    = MathAbs(entry - sl);
   if(slDist <= 0) return(0);

   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tickValue <= 0 || tickSize <= 0) return(0);

   double moneyPerLot = (slDist / tickSize) * tickValue;
   if(moneyPerLot <= 0) return(0);

   double lot     = riskMoney / moneyPerLot;
   double lotStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double lotMin  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double lotMax  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);

   if(lotStep > 0)
      lot = MathFloor(lot / lotStep) * lotStep;
   if(lot < lotMin)
      return(0);
   if(lot > lotMax)
      lot = lotMax;
   return(NormalizeDouble(lot, 2));
}

bool MyPosition(long &type, datetime &openTime)
{
   if(!PositionSelect(_Symbol))
      return(false);
   if((long)PositionGetInteger(POSITION_MAGIC) != InpMagic)
      return(false);
   type     = (long)PositionGetInteger(POSITION_TYPE);
   openTime = (datetime)PositionGetInteger(POSITION_TIME);
   return(PositionGetDouble(POSITION_VOLUME) > 0);
}

void RememberRisk(long posId, double riskMoney, int side)
{
   int n = ArraySize(g_posId);
   ArrayResize(g_posId, n + 1);
   ArrayResize(g_posRisk, n + 1);
   ArrayResize(g_posSide, n + 1);
   g_posId[n]   = posId;
   g_posRisk[n] = riskMoney;
   g_posSide[n] = side;
   g_posCount  = n + 1;
}

bool GetRemembered(long posId, double &riskMoney, int &side)
{
   for(int i = 0; i < g_posCount; i++)
   {
      if(g_posId[i] == posId)
      {
         riskMoney = g_posRisk[i];
         side      = g_posSide[i];
         return(true);
      }
   }
   return(false);
}

//+------------------------------------------------------------------+
//| PROTECCIONES (estilo Freqtrade)                                  |
//|                                                                  |
//|  1) StoplossGuard: si hay N stops propios dentro de una ventana   |
//|     de tiempo, se bloquea la operativa X horas.                   |
//|  2) MaxDrawdown sobre EQUITY: si el DD desde el pico supera el    |
//|     umbral, se bloquea X horas y se reinicia el pico (circuit      |
//|     breaker; si no, el bloqueo seria permanente).                  |
//|  3) CooldownPeriod: tras el cierre de una posicion, esperar N      |
//|     velas M15 antes de volver a entrar.                            |
//|                                                                  |
//|  Con InpUseProtections = false estas funciones no hacen nada y el  |
//|  resultado del backtest es exactamente el validado.                |
//+------------------------------------------------------------------+
void UpdateProtections()
{
   if(!InpUseProtections)
      return;

   datetime now = TimeCurrent();
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   if(eq > 0.0 && (g_peakEquity <= 0.0 || eq > g_peakEquity))
      g_peakEquity = eq;

   //--- 2) MaxDrawdown sobre equity
   if(InpMaxDDEquityPct > 0.0 && g_peakEquity > 0.0 && now >= g_ddLockUntil)
   {
      double ddPct = 100.0 * (g_peakEquity - eq) / g_peakEquity;
      if(ddPct >= InpMaxDDEquityPct)
      {
         g_ddLockUntil = now + (datetime)(InpMaxDDLockH * 3600);
         g_peakEquity  = eq;
         g_statDDGuard++;
         PrintFormat("PROT MaxDrawdown: DD equity %.2f%% >= %.2f%% -> bloqueo %dh (hasta %s)",
                     ddPct, InpMaxDDEquityPct, InpMaxDDLockH,
                     TimeToString(g_ddLockUntil, TIME_DATE | TIME_MINUTES));
      }
   }

   //--- 1) StoplossGuard: contar stops propios recientes
   if(InpSlGuardCount > 0 && InpSlGuardWindowH > 0 && now >= g_slLockUntil)
   {
      datetime from = now - (datetime)(InpSlGuardWindowH * 3600);
      if(HistorySelect(from, now + 60))
      {
         int nsl = 0;
         int tot = HistoryDealsTotal();
         for(int i = 0; i < tot; i++)
         {
            ulong d = HistoryDealGetTicket(i);
            if(d == 0) continue;
            if((long)HistoryDealGetInteger(d, DEAL_MAGIC) != InpMagic) continue;
            if((long)HistoryDealGetInteger(d, DEAL_ENTRY) != DEAL_ENTRY_OUT) continue;
            if((long)HistoryDealGetInteger(d, DEAL_REASON) != DEAL_REASON_SL) continue;
            nsl++;
         }
         if(nsl >= InpSlGuardCount)
         {
            g_slLockUntil = now + (datetime)(InpSlGuardLockH * 3600);
            g_statSlGuard++;
            PrintFormat("PROT StoplossGuard: %d stops en %dh -> bloqueo %dh (hasta %s)",
                        nsl, InpSlGuardWindowH, InpSlGuardLockH,
                        TimeToString(g_slLockUntil, TIME_DATE | TIME_MINUTES));
         }
      }
   }
}

//--- true si en este instante las protecciones impiden abrir
bool ProtectionBlocked()
{
   if(!InpUseProtections)
      return(false);

   datetime now = TimeCurrent();
   if(now < g_slLockUntil) return(true);
   if(now < g_ddLockUntil) return(true);

   if(InpCooldownBars > 0 && g_lastClose > 0)
   {
      datetime until = g_lastClose + (datetime)(InpCooldownBars * 900);
      if(now < until)
         return(true);
   }
   return(false);
}

//+------------------------------------------------------------------+
void OnTick()
{
   datetime t0 = iTime(_Symbol, PERIOD_M15, 0);
   if(t0 == 0 || t0 == g_lastBar)
      return;

   bool firstRun = (g_lastBar == 0);
   g_lastBar = t0;
   if(firstRun)
      return;

   long     posType;
   datetime posTime;
   bool     inPos = MyPosition(posType, posTime);

   //--- transicion abierto -> cerrado: marca de tiempo para el Cooldown
   if(g_wasInPos && !inPos)
      g_lastClose = TimeCurrent();
   g_wasInPos = inPos;

   //--- protecciones: se actualizan en cada vela nueva
   UpdateProtections();

   //---------------- SALIDAS ----------------
   if(inPos)
   {
      if(InpHoldBars > 0)
      {
         int bars = iBarShift(_Symbol, PERIOD_M15, posTime, false);
         if(bars >= InpHoldBars)
         {
            if(!g_trade.PositionClose(_Symbol))
               PrintFormat("Error cerrando por tiempo: %d", g_trade.ResultRetcode());
         }
      }
      return;   // una posicion a la vez
   }

   //---------------- PROTECCIONES ACTIVAS ----------------
   if(ProtectionBlocked())
   {
      g_statBlocked++;
      return;
   }

   //---------------- DATOS DE LA VELA DE SENAL (shift 1) ----------------
   double atr[];
   if(CopyBuffer(g_hATR, 0, 1, 1, atr) != 1) return;
   double a = atr[0];
   if(a <= 0 || !MathIsValidNumber(a)) return;

   datetime sigTime = iTime(_Symbol, PERIOD_M15, 1);
   MqlDateTime sdt; TimeToStruct(sigTime, sdt); int hour = sdt.hour;
   bool hourOk = (InpHourStart <= hour && hour <= InpHourEnd);
   if(!hourOk) return;

   // Techo de volatilidad (0 = desactivado). Hipotesis exploratoria:
   // en ATR/precio > 0.18-0.20 el edge medido desaparece.
   double atrPct = 0.0;
   if(InpMaxATRPct > 0.0)
   {
      double px = iClose(_Symbol, PERIOD_M15, 1);
      if(px <= 0) return;
      atrPct = 100.0 * a / px;
      if(atrPct > InpMaxATRPct) return;
   }

   int need = InpRangeBars + 2;
   if(Bars(_Symbol, PERIOD_M15) < need + 30) return;

   double rngHi = -DBL_MAX, rngLo = DBL_MAX;
   for(int i = 2; i < InpRangeBars + 2; i++)
   {
      double hi = iHigh(_Symbol, PERIOD_M15, i);
      double lo = iLow(_Symbol, PERIOD_M15, i);
      if(hi > rngHi) rngHi = hi;
      if(lo < rngLo) rngLo = lo;
   }
   double span = rngHi - rngLo;
   if(span <= 0) return;

   double c1 = iClose(_Symbol, PERIOD_M15, 1);
   double o1 = iOpen(_Symbol, PERIOD_M15, 1);
   if(c1 <= 0 || o1 <= 0) return;

   if(span / a > InpMaxRangeATR) return;

   double bodySum = 0.0;
   for(int i = 2; i <= 13; i++)
      bodySum += MathAbs(iClose(_Symbol, PERIOD_M15, i) - iOpen(_Symbol, PERIOD_M15, i));
   double avgBody = bodySum / 12.0;
   if(MathAbs(c1 - o1) < avgBody * InpImpulseMult) return;

   //---------------- REGIMEN H1 / H4 ----------------
   double e20[], e50[], f50[], f200[];
   if(CopyBuffer(g_hH1E20, 0, 1, 1, e20) != 1) return;
   if(CopyBuffer(g_hH1E50, 0, 1, 1, e50) != 1) return;
   if(CopyBuffer(g_hH4E50, 0, 1, 1, f50) != 1) return;
   if(CopyBuffer(g_hH4E200, 0, 1, 1, f200) != 1) return;

   double cH1 = iClose(_Symbol, PERIOD_H1, 1);
   double cH4 = iClose(_Symbol, PERIOD_H4, 1);
   if(cH1 <= 0 || cH4 <= 0) return;

   bool up1 = (cH1 > e20[0] && e20[0] > e50[0]);
   bool dn1 = (cH1 < e20[0] && e20[0] < e50[0]);
   bool up4 = (cH4 > f50[0] && f50[0] > f200[0]);
   bool dn4 = (cH4 < f50[0] && f50[0] < f200[0]);

   double buf = InpBufferATR * a;
   int side = -1;   // 0 buy, 1 sell

   if(c1 > rngHi + buf)
   {
      bool ok = InpStrictTrend ? (up4 && up1) : !(dn4 || dn1);
      if(ok) side = 0;
   }
   else if(c1 < rngLo - buf)
   {
      bool ok = InpStrictTrend ? (dn4 && dn1) : !(up4 || up1);
      if(ok) side = 1;
   }

   if(side < 0) return;
   if(side == 0 && !InpAllowLong) return;
   if(side == 1 && !InpAllowShort) return;

   //---------------- NIVELES ----------------
   double sl, tp;
   if(side == 0)
   {
      sl = MathMin(rngLo, c1 - InpKSL * a);
      tp = c1 + MathMax(InpRangeTargetMult * span, InpKTP * a);
   }
   else
   {
      sl = MathMax(rngHi, c1 + InpKSL * a);
      tp = c1 - MathMax(InpRangeTargetMult * span, InpKTP * a);
   }

   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(ask <= 0 || bid <= 0) return;
   double entry = (side == 0) ? ask : bid;
   double risk  = MathAbs(entry - sl);
   if(risk <= 0) return;

   // Si el hueco de apertura ya dejo el precio fuera del TP/SL, no operar
   if(side == 0 && entry >= tp) return;
   if(side == 1 && entry <= tp) return;

   //---------------- FILTRO DE COSTE ----------------
   double spread = ask - bid;
   double contract = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_CONTRACT_SIZE);
   if(contract <= 0) return;
   double commPrice = InpCommissionPerLot / contract;
   double costPctR = 100.0 * (spread + commPrice) / risk;
   if(costPctR > InpMaxCostPctR)
   {
      PrintFormat("Coste %.2f%% de R > %.2f%%: no se entra", costPctR, InpMaxCostPctR);
      return;
   }

   int digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   sl = NormalizeDouble(sl, digits);
   tp = NormalizeDouble(tp, digits);

   double lot = CalcLot(entry, sl);
   if(lot <= 0) return;

   bool sent = (side == 0)
      ? g_trade.PositionOpen(_Symbol, ORDER_TYPE_BUY,  lot, entry, sl, tp, InpComment)
      : g_trade.PositionOpen(_Symbol, ORDER_TYPE_SELL, lot, entry, sl, tp, InpComment);

   if(sent && g_trade.ResultRetcode() == TRADE_RETCODE_DONE)
   {
      double riskMoney = risk * contract * lot;
      long posId = 0;
      if(PositionSelect(_Symbol))
         posId = (long)PositionGetInteger(POSITION_IDENTIFIER);
      if(posId == 0)
         posId = (long)g_trade.ResultOrder();
      RememberRisk(posId, riskMoney, side);
      PrintFormat("%s lote=%.2f entry=%.3f sl=%.3f tp=%.3f atr=%.3f coste=%.2f%%R",
                  (side == 0 ? "COMPRA" : "VENTA"), lot, entry, sl, tp, a, costPctR);
   }
}

//+------------------------------------------------------------------+
//| CSV de trades para auditoria (Common\Files)                      |
//+------------------------------------------------------------------+
double OnTester()
{
   if(InpUseProtections)
      PrintFormat("PROTECCIONES: SlGuard=%d disparos, MaxDD=%d disparos, velas bloqueadas=%d",
                  g_statSlGuard, g_statDDGuard, g_statBlocked);

   HistorySelect(0, TimeCurrent() + 86400);
   int total = HistoryDealsTotal();
   if(total <= 0) return(0.0);

   int h = FileOpen("TradeX_S1_trades.csv", FILE_COMMON | FILE_WRITE | FILE_CSV | FILE_ANSI, ';');
   if(h == INVALID_HANDLE)
   {
      Print("No se pudo abrir CSV de trades: ", GetLastError());
      return(0.0);
   }
   FileWrite(h, "pos_id", "side", "open_time", "close_time", "volume", "open_price", "close_price",
             "profit", "swap", "commission", "risk_money", "R_simbolo", "R_net7");

   // Primera pasada: entradas por posicion
   long     inId[];
   datetime inTime[];
   double   inPrice[];
   int      inCount = 0;
   for(int i = 0; i < total; i++)
   {
      ulong deal = HistoryDealGetTicket(i);
      if(deal == 0) continue;
      if((long)HistoryDealGetInteger(deal, DEAL_ENTRY) != DEAL_ENTRY_IN) continue;
      long posId = (long)HistoryDealGetInteger(deal, DEAL_POSITION_ID);
      double riskMoney; int side;
      if(!GetRemembered(posId, riskMoney, side)) continue;
      int n = ArraySize(inId);
      ArrayResize(inId, n + 1);
      ArrayResize(inTime, n + 1);
      ArrayResize(inPrice, n + 1);
      inId[n]    = posId;
      inTime[n]  = (datetime)HistoryDealGetInteger(deal, DEAL_TIME);
      inPrice[n] = HistoryDealGetDouble(deal, DEAL_PRICE);
      inCount    = n + 1;
   }

   for(int i = 0; i < total; i++)
   {
      ulong deal = HistoryDealGetTicket(i);
      if(deal == 0) continue;
      long entryType = (long)HistoryDealGetInteger(deal, DEAL_ENTRY);
      if(entryType != DEAL_ENTRY_OUT) continue;

      long posId = (long)HistoryDealGetInteger(deal, DEAL_POSITION_ID);
      double riskMoney;
      int side;
      if(!GetRemembered(posId, riskMoney, side)) continue;
      if(riskMoney <= 0) continue;

      datetime openTime = 0;
      double openPrice = 0.0;
      for(int k = 0; k < inCount; k++)
      {
         if(inId[k] == posId)
         {
            openTime  = inTime[k];
            openPrice = inPrice[k];
            break;
         }
      }

      double volume = HistoryDealGetDouble(deal, DEAL_VOLUME);
      double profit = HistoryDealGetDouble(deal, DEAL_PROFIT);
      double swap   = HistoryDealGetDouble(deal, DEAL_SWAP);
      double comm   = HistoryDealGetDouble(deal, DEAL_COMMISSION);
      double rSym   = (profit + swap + comm) / riskMoney;
      double rNet7  = (profit + swap + comm - InpCommissionPerLot * volume) / riskMoney;
      datetime closeTime = (datetime)HistoryDealGetInteger(deal, DEAL_TIME);
      double closePrice = HistoryDealGetDouble(deal, DEAL_PRICE);

      FileWrite(h, (string)posId, (side == 0 ? "BUY" : "SELL"),
                TimeToString(openTime, TIME_DATE | TIME_SECONDS),
                TimeToString(closeTime, TIME_DATE | TIME_SECONDS),
                DoubleToString(volume, 2),
                DoubleToString(openPrice, 3),
                DoubleToString(closePrice, 3),
                DoubleToString(profit, 2), DoubleToString(swap, 2), DoubleToString(comm, 2),
                DoubleToString(riskMoney, 2), DoubleToString(rSym, 4), DoubleToString(rNet7, 4));
   }
   FileClose(h);
   return(0.0);
}
//+------------------------------------------------------------------+




