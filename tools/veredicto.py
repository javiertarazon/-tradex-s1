#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Veredicto automatico de un candidato de trading: puertas G1-G7.

Convierte el protocolo de auditoria en codigo ejecutable. Entra un CSV de
trades reales (el que escribe OnTester del EA) y sale un PASS/FAIL por puerta,
una tabla por ano y por lado, y el bootstrap de drawdown.

Uso:
    python veredicto.py --label "S1 GA-B" \
        --base S1_ticks_trades_gaB.csv \
        --oos OOS2024_gaB.csv \
        --variant rb18=S1_ticks_rb18.csv --variant rb22=S1_ticks_rb22.csv \
        --risk 1.5 --out veredicto_gaB.json

Columnas usadas: close_time, side, R_simbolo (neto de spread y swap),
R_net7 (neto ademas de comision por lote). Se juzga con R_net7, el conservador.

Puertas:
  G2 costes      degradacion R_net7/R_simbolo >= 0.90 y coste medio <= 0.10R
  G3 robustez    ningun variante con PF < 65% del base ni DD > 150% del base
  G4 in-sample   n>=30, PF>=1.5, t>=2.0, DD<=15%
  G5 out-of-sample  n>=10, PF>=1.2, R>0, t>=1.0
  G6 bootstrap   P95 del DD a riesgo dado <= 15%
  G7 estabilidad 60%+ de anos en positivo y peor ano > -20% del R total

Sin dependencias externas.
"""
import argparse
import csv
import glob
import json
import math
import os
import random
import sys

SEP = ";"
R_COL = "R_net7"
R_RAW = "R_simbolo"
MIN_YEAR_TRADES = 5


# ------------------------------------------------------------------ lectura
def load(path):
    if not os.path.isfile(path):
        raise SystemExit(f"No existe el fichero: {path}")
    rows = []
    with open(path, "r", encoding="latin-1", newline="") as fh:
        rd = csv.DictReader(fh, delimiter=SEP)
        for raw in rd:
            try:
                r = float(str(raw[R_COL]).replace(",", "."))
            except (TypeError, ValueError):
                continue
            if not math.isfinite(r):
                continue
            ct = str(raw.get("close_time", ""))
            try:
                year = int(ct[:4])
            except ValueError:
                year = 0
            rows.append({
                "year": year,
                "side": str(raw.get("side", "")).strip().upper(),
                "R": r,
                "Rraw": float(str(raw.get(R_RAW, r)).replace(",", ".") or r),
                "open": ct[:10],
                "open_full": ct,
            })
    if not rows:
        raise SystemExit(f"CSV sin trades validos: {path}")
    rows.sort(key=lambda x: x["open"])
    return rows


# ------------------------------------------------------------------ metricas
def drawdown(R):
    eq = 0.0
    peak = 0.0
    dd = 0.0
    for r in R:
        eq += r
        peak = max(peak, eq)
        dd = max(dd, peak - eq)
    return dd


def stats(rows):
    R = [x["R"] for x in rows]
    n = len(R)
    wins = [r for r in R if r > 0]
    losses = [r for r in R if r <= 0]
    gross_w = sum(wins)
    gross_l = -sum(losses)
    mean = sum(R) / n
    var = sum((r - mean) ** 2 for r in R) / (n - 1) if n > 1 else 0.0
    sd = math.sqrt(var)
    t = mean / (sd / math.sqrt(n)) if sd > 0 and n > 1 else 0.0
    return {
        "n": n,
        "R": round(sum(R), 2),
        "pf": round(gross_w / gross_l, 3) if gross_l > 0 else 99.0,
        "wr": round(100.0 * len(wins) / n, 1),
        "expR": round(mean, 3),
        "ddR": round(drawdown(R), 2),
        "t": round(t, 2),
        "stderr": round(sd / math.sqrt(n), 3) if n > 0 else 0.0,
        "avgW": round(gross_w / len(wins), 2) if wins else 0.0,
        "avgL": round(-gross_l / len(losses), 2) if losses else 0.0,
    }


def by_key(rows, key):
    out = {}
    for r in rows:
        out.setdefault(r[key], []).append(r)
    return {k: stats(v) for k, v in sorted(out.items())}


def max_streak_loss(rows):
    best = cur = 0
    for r in rows:
        if r["R"] <= 0:
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best


def bootstrap(rows, risk, n_iter=20000, seed=20261118):
    """Remuestrea el orden y la composicion de la serie de R."""
    R = [x["R"] for x in rows]
    n = len(R)
    rng = random.Random(seed)
    dds = []
    for _ in range(n_iter):
        sample = [R[rng.randrange(n)] for _ in range(n)]
        dds.append(drawdown(sample) * risk)
    dds.sort()

    def pct(p):
        idx = min(len(dds) - 1, max(0, int(round(p * (len(dds) - 1)))))
        return dds[idx]

    return {
        "risk": risk,
        "p50": round(pct(0.50), 2),
        "p95": round(pct(0.95), 2),
        "p99": round(pct(0.99), 2),
        "max": round(dds[-1], 2),
        "p_dd_over_15": round(100.0 * sum(1 for d in dds if d > 15.0) / len(dds), 2),
    }


# ------------------------------------------------------------------ puertas
def gate(name, ok, detail):
    return {"gate": name, "pass": bool(ok), "detail": detail}


def evaluate(base, oos, variants, risk, pf_min=1.5, t_min=2.0, dd_max=15.0,
             oos_pf_min=1.2, oos_t_min=1.0, train_end=None):
    s = stats(base)
    gates = []

    # G1 - datos: longitud suficiente del historico (se informa, no se juzga aqui)
    years = sorted({r["year"] for r in base if r["year"]})
    span = (years[-1] - years[0] + 1) if years else 0
    gates.append(gate("G1 datos", span >= 2 and s["n"] >= 30,
                      f"{span} anos con datos, {s['n']} trades"))

    # G2 - costes: cuanto se come el coste del resultado bruto
    raw = sum(x["Rraw"] for x in base)
    net = sum(x["R"] for x in base)
    keep = (net / raw) if raw > 0 else 1.0
    cost_per_trade = (raw - net) / s["n"]
    gates.append(gate("G2 costes", keep >= 0.90 and cost_per_trade <= 0.10,
                      f"R_net7/R_simbolo={keep:.3f}, coste medio={cost_per_trade:.3f}R/trade"))

    # G3 - robustez de parametros
    if variants:
        worst_pf = min(v["pf"] for v in variants.values())
        worst_dd = max(v["ddR"] for v in variants.values())
        ok3 = worst_pf >= 0.65 * s["pf"] and worst_dd <= 1.5 * max(s["ddR"], 0.01)
        gates.append(gate("G3 robustez", ok3,
                          f"peor PF={worst_pf:.2f} ({100*worst_pf/s['pf']:.0f}% del base), "
                          f"peor DD={worst_dd:.2f}R"))
    else:
        gates.append(gate("G3 robustez", False, "sin variantes: no evaluable"))

    # G4 - in-sample con ticks reales
    ok4 = s["n"] >= 30 and s["pf"] >= pf_min and s["t"] >= t_min and s["ddR"] * risk <= dd_max
    gates.append(gate("G4 in-sample", ok4,
                      f"n={s['n']} PF={s['pf']:.2f} t={s['t']:.2f} "
                      f"DD={s['ddR']*risk:.1f}% (a {risk}%)"))

    # G5 - out-of-sample
    if oos:
        so = stats(oos)
        ok5 = so["n"] >= 10 and so["pf"] >= oos_pf_min and so["R"] > 0 and so["t"] >= oos_t_min
        gates.append(gate("G5 out-of-sample", ok5,
                          f"n={so['n']} PF={so['pf']:.2f} R={so['R']:+.2f} t={so['t']:.2f}"))
    else:
        so = None
        gates.append(gate("G5 out-of-sample", False, "sin tramo OOS: no evaluable"))

    # G6 - bootstrap de drawdown
    bs = bootstrap(base, risk)
    ok6 = bs["p95"] <= dd_max
    gates.append(gate("G6 bootstrap", ok6,
                      f"P95 DD={bs['p95']:.1f}% a {risk}% riesgo "
                      f"(P(DD>15%)={bs['p_dd_over_15']:.2f}%)"))

    # G7 - estabilidad interanual
    ystats = by_key(base, "year")
    judged = {y: v for y, v in ystats.items() if v["n"] >= MIN_YEAR_TRADES}
    pos = sum(1 for v in judged.values() if v["R"] > 0)
    share = pos / len(judged) if judged else 0.0
    worst = min((v["R"] for v in judged.values()), default=0.0)
    ok7 = share >= 0.60 and worst > -0.20 * max(s["R"], 1e-9)
    gates.append(gate("G7 estabilidad", ok7,
                      f"{pos}/{len(judged)} anos positivos, peor ano={worst:+.2f}R"))

    # --- guardarrail: el tramo "OOS" no puede estar contenido en el in-sample
    warn = []
    if oos:
        if train_end:
            inside = [x for x in oos if x["open_full"] < train_end]
            if inside:
                warn.append(
                    f"AVISO: {len(inside)} trades OOS son anteriores al corte de "
                    f"entrenamiento ({train_end}). El holdout no es limpio.")
        else:
            keys = {(x["open_full"], x["side"]) for x in base}
            dup = sum(1 for x in oos if (x["open_full"], x["side"]) in keys)
            share_dup = dup / len(oos)
            if share_dup >= 0.5:
                warn.append(
                    f"AVISO: {100*share_dup:.0f}% de los trades OOS ya estan en el in-sample. "
                    "Ese tramo NO es un holdout independiente: el optimizador pudo verlo. "
                    "Declara el corte con --train-end para que el juicio sea correcto.")
            oy = {x["year"] for x in oos}
            by_ = {x["year"] for x in base}
            if oy and oy <= by_:
                warn.append(
                    f"AVISO: los anos OOS {sorted(oy)} estan dentro del rango del in-sample "
                    f"{sorted(by_)}. Comprobar en que tramo se entreno el optimizador.")

    return s, so, gates, bs, ystats, warn


# ------------------------------------------------------------------ salida
def render(label, s, so, gates, bs, ystats, base, risk, warn=None):
    L = []
    L.append(f"## Veredicto: {label}")
    L.append("")
    L.append(f"**Riesgo asumido por operacion:** {risk}% del balance")
    L.append("")
    L.append("| Puerta | Estado | Evidencia |")
    L.append("|---|---|---|")
    for g in gates:
        L.append(f"| {g['gate']} | {'PASS' if g['pass'] else 'FAIL'} | {g['detail']} |")
    passed = sum(1 for g in gates if g["pass"])
    L.append("")
    L.append(f"**Puertas superadas: {passed}/{len(gates)}**")
    L.append("")
    for w in (warn or []):
        L.append(f"> {w}")
        L.append("")

    L.append("| Metrica | Base | " + ("OOS |" if so else ""))
    L.append("|---|---|" + ("---|" if so else ""))
    for k in ("n", "R", "pf", "wr", "expR", "ddR", "t"):
        row = f"| {k} | {s[k]} |"
        if so:
            row += f" {so[k]} |"
        L.append(row)
    L.append("")

    L.append("### Por ano")
    L.append("")
    L.append("| Ano | n | R | PF | WR |")
    L.append("|---|---|---|---|---|")
    for y, v in ystats.items():
        L.append(f"| {y} | {v['n']} | {v['R']:+.2f} | {v['pf']:.2f} | {v['wr']:.1f}% |")
    L.append("")

    L.append("### Por lado")
    L.append("")
    L.append("| Lado | n | R | PF | WR |")
    L.append("|---|---|---|---|---|")
    for side, v in by_key(base, "side").items():
        L.append(f"| {side} | {v['n']} | {v['R']:+.2f} | {v['pf']:.2f} | {v['wr']:.1f}% |")
    L.append("")

    L.append("### Bootstrap de drawdown (20.000 remuestreos)")
    L.append("")
    L.append(f"| Riesgo | P50 | P95 | P99 | max | P(DD>15%) |")
    L.append("|---|---|---|---|---|---|")
    L.append(f"| {risk}% | {bs['p50']}% | {bs['p95']}% | {bs['p99']}% | {bs['max']}% | "
             f"{bs['p_dd_over_15']}% |")
    L.append("")
    L.append(f"Racha maxima de perdidas: {max_streak_loss(base)} operaciones")
    L.append("")
    return "\n".join(L)


def verdict(gates):
    by = {g["gate"]: g["pass"] for g in gates}
    if by.get("G4 in-sample") and by.get("G5 out-of-sample") and all(by.values()):
        return "CAPITAL REAL (con escalera de riesgo)"
    if by.get("G4 in-sample"):
        return "SOLO DEMO: el edge aparece in-sample pero el OOS no confirma"
    return "NO-GO: ni siquiera in-sample supera las puertas"


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser(description="Veredicto G1-G7 sobre trades reales")
    ap.add_argument("--label", default="candidato")
    ap.add_argument("--base", required=True, help="CSV in-sample (ticks)")
    ap.add_argument("--oos", default=None, help="CSV out-of-sample")
    ap.add_argument("--variant", action="append", default=[],
                    help="nombre=ruta.csv (repetible)")
    ap.add_argument("--risk", type=float, default=1.5)
    ap.add_argument("--train-end", default=None,
                    help="corte de entrenamiento (YYYY-MM-DD); los trades posteriores son OOS")
    ap.add_argument("--pf-min", type=float, default=1.5)
    ap.add_argument("--t-min", type=float, default=2.0)
    ap.add_argument("--dd-max", type=float, default=15.0)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    base_all = load(args.base)
    train_end = None
    is_only = None
    if args.train_end:
        train_end = args.train_end.replace("-", ".")
        if len(train_end) == 4:
            train_end += ".01.01"
        is_rows = [x for x in base_all if x["open_full"] < train_end]
        if not is_rows:
            raise SystemExit("--train-end deja el in-sample sin trades")
        is_only = stats(is_rows)
        print(f"Muestra completa: {len(base_all)} trades | "
              f"IS puro hasta {train_end}: {len(is_rows)} trades "
              f"(PF {is_only['pf']:.2f}, R {is_only['R']:+.2f})\n")
        base = base_all
    else:
        base = base_all
    oos = load(args.oos) if args.oos else None
    variants = {}
    for spec in args.variant:
        if "=" not in spec:
            raise SystemExit(f"--variant necesita nombre=ruta: {spec}")
        name, path = spec.split("=", 1)
        for p in glob.glob(path) or [path]:
            try:
                variants[f"{name}:{os.path.basename(p)}"] = stats(load(p))
            except SystemExit:
                print(f"  aviso: {p} sin trades", file=sys.stderr)

    s, so, gates, bs, ystats, warn = evaluate(base, oos, variants, args.risk,
                                              args.pf_min, args.t_min, args.dd_max,
                                              train_end=train_end)
    md = render(args.label, s, so, gates, bs, ystats, base, args.risk, warn)
    md += f"\n**VEREDICTO: {verdict(gates)}**\n"
    print(md)

    if args.out:
        payload = {
            "label": args.label,
            "risk": args.risk,
            "base": s,
            "is_only": is_only,
            "oos": so,
            "variants": variants,
            "gates": gates,
            "bootstrap": bs,
            "by_year": ystats,
            "by_side": by_key(base, "side"),
            "warnings": warn,
            "verdict": verdict(gates),
        }
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=1, ensure_ascii=False)
        print(f"(json -> {args.out})")


if __name__ == "__main__":
    main()
