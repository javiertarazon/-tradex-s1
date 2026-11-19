#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Auditor estatico de paridad research/live para EAs de MT5.

Adapta las 5 reglas de NautilusTrader ("el mismo nucleo corre en backtest y en
vivo") a una revision de codigo fuente que se puede correr en dos segundos,
sin tester ni terminal.

Reglas:
  R1 sin look-ahead      toda lectura de precio/indicador usa shift >= 1
  R2 niveles en la orden SL y TP se envian al abrir, no se colocan despues
  R3 sizing real         el lote sale de balance/equity y del tick value del
                         simbolo, no de una constante
  R4 sin ordenes pendientes  nada de limits/stops diferidos ni modificaciones
  R5 sin bifurcacion tester  el codigo no cambia de comportamiento segun si
                         corre en tester o en vivo

Uso: python paridad_ea.py <archivo.mq5> [--json salida.json]
Codigo de salida: 0 si pasa todo, 1 si falla alguna regla.
"""
import argparse
import json
import os
import re
import sys

# ---------------------------------------------------------------- patrones
PRICE_CALL = re.compile(
    r"\b(iOpen|iHigh|iLow|iClose|iVolume|iRealVolume|iSpread|iTickVolume)\s*\(\s*"
    r"_Symbol\s*,\s*[A-Za-z0-9_]+\s*,\s*(-?\d+)\s*\)")
COPY_BUFFER = re.compile(
    r"\bCopyBuffer\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*,\s*\d+\s*,\s*(-?\d+)\s*,\s*(\d+)\s*,")
COPY_RATES = re.compile(
    r"\bCopyRates\s*\(\s*_Symbol\s*,\s*[A-Za-z0-9_]+\s*,\s*(-?\d+)\s*,\s*(\d+)\s*,")
ORDER_OPEN = re.compile(
    r"\b(PositionOpen|OrderSend|OrderOpen)\s*\(([^;]*?)\)\s*;", re.S)
PENDING = re.compile(r"\bORDER_TYPE_(BUY|SELL)_(LIMIT|STOP|STOP_LIMIT)\b")
MODIFY = re.compile(r"\b(PositionModify|OrderModify)\s*\(")
TESTER_BRANCH = re.compile(
    r"\b(MQLInfoInteger\s*\(\s*MQL_TESTER|MQLInfoInteger\s*\(\s*MQL_VISUAL_MODE|"
    r"ifdef\s+TESTER|ifndef\s+TESTER|IsTesting\s*\()")
BALANCE_SRC = re.compile(r"\bACCOUNT_(BALANCE|EQUITY|MARGIN_FREE)\b")
TICK_VALUE = re.compile(r"\bSYMBOL_TRADE_TICK_VALUE\b")
HARD_LOT = re.compile(
    r"\b(?:double|input\s+double)\s+(?:fixed_?lot|lot|Lot|lots|Lots|inpLot|inpLots|InpLot|"
    r"InpLots|InpFixedLot|InpLotSize)\s*=\s*[0-9]")


def strip_comments(src):
    """Quita comentarios conservando saltos de linea (para numerar bien)."""
    out = []
    i, n = 0, len(src)
    while i < n:
        ch = src[i]
        if ch == "/" and i + 1 < n and src[i + 1] == "/":
            while i < n and src[i] != "\n":
                i += 1
        elif ch == "/" and i + 1 < n and src[i + 1] == "*":
            i += 2
            while i + 1 < n and not (src[i] == "*" and src[i + 1] == "/"):
                if src[i] == "\n":
                    out.append("\n")
                i += 1
            i += 2
        elif ch == '"':
            out.append(ch)
            i += 1
            while i < n and src[i] != '"':
                if src[i] == "\\":
                    out.append(src[i])
                    i += 1
                if i < n:
                    out.append(src[i])
                    i += 1
            if i < n:
                out.append('"')
                i += 1
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def line_of(src, pos):
    return src.count("\n", 0, pos) + 1


def check(path):
    raw = open(path, "r", encoding="latin-1").read()
    src = strip_comments(raw)
    findings = []

    # ---------------------------------------------------------- R1
    bad = []
    for m in PRICE_CALL.finditer(src):
        shift = int(m.group(2))
        if shift < 1:
            bad.append((line_of(src, m.start()), m.group(0).strip()))
    for m in COPY_BUFFER.finditer(src):
        shift = int(m.group(2))
        count = int(m.group(3))
        if shift < 1 and count > 0:
            bad.append((line_of(src, m.start()),
                        f"CopyBuffer(..., shift={shift}, count={count})"))
    for m in COPY_RATES.finditer(src):
        start = int(m.group(1))
        if start < 1:
            bad.append((line_of(src, m.start()), f"CopyRates(..., start_pos={start})"))
    findings.append({
        "rule": "R1 sin look-ahead",
        "pass": not bad,
        "evidence": (f"{len(bad)} lecturas con shift 0" if bad else
                     "todas las lecturas de precio usan shift >= 1"),
        "lines": bad[:12],
    })

    # ---------------------------------------------------------- R2
    opens = list(ORDER_OPEN.finditer(src))
    no_sltp = []
    for m in opens:
        args = m.group(2)
        if not re.search(r"\bsl\b", args) or not re.search(r"\btp\b", args):
            no_sltp.append((line_of(src, m.start()), m.group(1) + "(sin sl/tp)"))
    findings.append({
        "rule": "R2 niveles en la orden",
        "pass": bool(opens) and not no_sltp,
        "evidence": (f"{len(opens)} envios, {len(no_sltp)} sin sl/tp" if opens
                     else "no se encontro ningun envio de orden"),
        "lines": no_sltp[:12],
    })

    # ---------------------------------------------------------- R3
    has_bal = bool(BALANCE_SRC.search(src))
    has_tv = bool(TICK_VALUE.search(src))
    hard = [(line_of(src, m.start()), m.group(0).strip())
            for m in HARD_LOT.finditer(src)]
    findings.append({
        "rule": "R3 sizing real",
        "pass": has_bal and has_tv,
        "evidence": (f"balance/equity={'si' if has_bal else 'no'}, "
                     f"tick_value={'si' if has_tv else 'no'}, "
                     f"lotes hardcodeados={len(hard)}"),
        "lines": hard[:12],
    })

    # ---------------------------------------------------------- R4
    pend = [(line_of(src, m.start()), m.group(0)) for m in PENDING.finditer(src)]
    mods = [(line_of(src, m.start()), m.group(1)) for m in MODIFY.finditer(src)]
    findings.append({
        "rule": "R4 sin ordenes pendientes",
        "pass": not pend and not mods,
        "evidence": f"{len(pend)} pendientes, {len(mods)} modificaciones",
        "lines": (pend + mods)[:12],
    })

    # ---------------------------------------------------------- R5
    br = [(line_of(src, m.start()), m.group(0).strip())
          for m in TESTER_BRANCH.finditer(src)]
    findings.append({
        "rule": "R5 sin bifurcacion tester",
        "pass": not br,
        "evidence": f"{len(br)} ramas condicionadas al entorno",
        "lines": br[:12],
    })

    return findings


def render(path, findings):
    L = [f"### {os.path.basename(path)}", "",
         "| Regla | Estado | Evidencia |", "|---|---|---|"]
    for f in findings:
        L.append(f"| {f['rule']} | {'PASS' if f['pass'] else 'FAIL'} | {f['evidence']} |")
    L.append("")
    for f in findings:
        if f["lines"]:
            L.append(f"**{f['rule']}**")
            for ln, txt in f["lines"]:
                L.append(f"- linea {ln}: `{txt}`")
            L.append("")
    passed = sum(1 for f in findings if f["pass"])
    L.append(f"**Paridad: {passed}/{len(findings)} reglas.**")
    L.append("")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description="Auditor de paridad research/live (MT5)")
    ap.add_argument("files", nargs="+")
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    payload = {}
    ok = True
    for p in args.files:
        if not os.path.isfile(p):
            print(f"No existe: {p}", file=sys.stderr)
            ok = False
            continue
        f = check(p)
        payload[p] = f
        print(render(p, f))
        ok = ok and all(x["pass"] for x in f)

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=1, ensure_ascii=False)
        print(f"(json -> {args.json})")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
