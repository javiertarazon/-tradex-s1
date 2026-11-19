"""S1 - diagnostico de regimen + optimizacion genetica con doble split temporal."""
import sys, json, math, random, os
import numpy as np
import pandas as pd
import paths
import s1_regime_ga as G

OUT = paths.RESULTS
os.makedirs(OUT, exist_ok=True)

m15 = G.lab.load()
P = G.prep(m15)
CACHE = {}
TMAP = {int(x): k for k, x in enumerate(P["t"])}
T = P["t"]


def ts_of(s):
    return pd.Timestamp(int(T[s]) , unit="s")


def dd_R(R):
    eq = np.cumsum(R)
    return float((np.maximum.accumulate(eq) - eq).max())


def run(gen, sig_filter=None):
    sig, _, _ = G.signals(P, **gen["sig"], cache=CACHE)
    if sig_filter is not None:
        sig = [s for s in sig if sig_filter(int(T[s[0]]))]
    tr = G.sim(P, sig, **gen["sim"])
    return tr


def stats(tr):
    if not tr:
        return dict(n=0, R=0.0, pf=0.0, dd=0.0, t=0.0, wr=0.0)
    R = np.array([x["R"] for x in tr])
    w, lo = R[R > 0], R[R <= 0]
    t = R.mean() / (R.std(ddof=1) / math.sqrt(len(R))) if len(R) > 2 and R.std(ddof=1) > 0 else 0.0
    return dict(n=int(len(R)), R=round(float(R.sum()), 2),
                pf=round(float(w.sum() / -lo.sum()), 3) if len(lo) and lo.sum() < 0 else 99.0,
                dd=round(dd_R(R), 2), t=round(float(t), 2),
                wr=round(100 * (R > 0).mean(), 1))


def yearly(tr):
    if not tr:
        return {}
    d = pd.DataFrame(tr)
    d["y"] = pd.to_datetime(d.exit_ts, unit="s").dt.year
    return {int(y): stats(g.to_dict("records")) for y, g in d.groupby("y")}


BASE = dict(
    sig=dict(rb=16, max_rng=2.8, imp=1.10, buf=0.04, hours=(13, 14, 15, 16), atr_cap=0.0),
    sim=dict(ksl=4.4, ktp_mult=2.9, tgt=1.25, hold=96),
)

# ------------------------------------------------------------------ 1. regimen
tr = run(BASE)
df = pd.DataFrame(tr)
df["i"] = df.entry_ts.map(TMAP)
df["year"] = pd.to_datetime(df.exit_ts, unit="s").dt.year
df["vol20"] = P["vol20"][df.i.values]
df["slope20"] = P["slope20"][df.i.values]
df["dd_hi"] = P["dd_hi"][df.i.values]
df["sep1"] = np.abs(P["sep1"][df.i.values])
df["sep4"] = np.abs(P["sep4"][df.i.values])
df["body_atr"] = P["body"][df.i.values] / P["a"][df.i.values]
df["hour"] = P["hours"][df.i.values]
df["dow"] = P["dow"][df.i.values]
df.to_csv(os.path.join(OUT, "base_trades_feat.csv"), index=False)

print("=== BASE por ano ===")
print(json.dumps(yearly(tr), ensure_ascii=False))
print()

print("=== feature vs R (todos los trades con swap) ===")
for c in ["atr_pct", "vol20", "slope20", "dd_hi", "sep1", "sep4", "body_atr", "hold_bars"]:
    print(f"  corr({c:9s}) = {df[c].corr(df.R):+.3f}   "
          f"mediana={df[c].median():.4f}")
print()

print("=== split por mediana ANUAL de cada feature (R del semestre bajo / alto) ===")
for c in ["atr_pct", "vol20", "sep4", "slope20", "dd_hi"]:
    line = []
    for y, g in df.groupby("year"):
        if len(g) < 6:
            continue
        med = g[c].median()
        line.append(f"{y}: {g[g[c] <= med].R.sum():+6.2f}/{g[g[c] > med].R.sum():+6.2f}")
    print(f"  {c:9s} " + "  ".join(line))
print()

# ------------------------------------------------------------------ 2. GA
GRID = dict(
    rb=[12, 14, 16, 18, 20],
    max_rng=[2.2, 2.4, 2.6, 2.8, 3.0, 3.2, 3.4],
    imp=[1.0, 1.05, 1.1, 1.15, 1.2, 1.3, 1.4, 1.5],
    buf=[0.0, 0.02, 0.04, 0.06, 0.08, 0.10],
    ksl=[2.8, 3.2, 3.6, 4.0, 4.4, 4.8, 5.2, 5.6, 6.0],
    ktp_mult=[2.2, 2.4, 2.6, 2.8, 2.9, 3.1, 3.3, 3.5],
    tgt=[0.8, 1.0, 1.1, 1.25, 1.4, 1.6],
    hold=[48, 72, 96, 120, 144, 168, 192, 240],
    atr_cap=[0.0, 0.16, 0.18, 0.20, 0.22, 0.26, 0.30],
    hours=[(13, 14, 15, 16), (13, 14, 15), (14, 15, 16), (13, 14, 15, 16, 17)],
)
GENES = list(GRID.keys())


def rand_genome(rng):
    g = {k: rng.randrange(len(GRID[k])) for k in GENES}
    return g


def decode(g):
    v = {k: GRID[k][g[k]] for k in GENES}
    return dict(sig=dict(rb=v["rb"], max_rng=v["max_rng"], imp=v["imp"], buf=v["buf"],
                         hours=v["hours"], atr_cap=v["atr_cap"]),
                sim=dict(ksl=v["ksl"], ktp_mult=v["ktp_mult"], tgt=v["tgt"], hold=v["hold"]))


def mutate(g, rng, p=0.22):
    g = dict(g)
    for k in GENES:
        if rng.random() < p:
            g[k] = rng.randrange(len(GRID[k]))
    return g


def crossover(a, b, rng):
    return {k: (a[k] if rng.random() < 0.5 else b[k]) for k in GENES}


def fitness(g, lo_ts, hi_ts, min_n=12):
    gen = decode(g)
    tr = run(gen, sig_filter=lambda ts: lo_ts <= ts < hi_ts)
    if len(tr) < min_n:
        return -99.0, None
    R = np.array([x["R"] for x in tr])
    tot = float(R.sum())
    if tot <= 0:
        return tot, tr
    dd = dd_R(R)
    return tot / (dd + 3.0), tr


def ga(lo_ts, hi_ts, seed, pop=70, gens=40, tag=""):
    rng = random.Random(seed)
    P0 = [rand_genome(rng) for _ in range(pop)]
    best_hist = []
    for gen_i in range(gens):
        scored = []
        for g in P0:
            f, _ = fitness(g, lo_ts, hi_ts)
            scored.append((f, g))
        scored.sort(key=lambda x: -x[0])
        best_hist.append(scored[0][0])
        elite = [g for f, g in scored[:6]]
        newpop = [dict(e) for e in elite]
        while len(newpop) < pop:
            a = max(rng.sample(scored[:30], 3), key=lambda x: x[0])[1]
            b = max(rng.sample(scored[:30], 3), key=lambda x: x[0])[1]
            c = crossover(a, b, rng)
            c = mutate(c, rng)
            newpop.append(c)
        P0 = newpop
    scored = []
    for g in P0:
        f, _ = fitness(g, lo_ts, hi_ts)
        scored.append((f, g))
    scored.sort(key=lambda x: -x[0])
    uniq, seen = [], set()
    for f, g in scored:
        key = tuple(g[k] for k in GENES)
        if key in seen:
            continue
        seen.add(key)
        uniq.append((f, g))
        if len(uniq) >= 20:
            break
    return uniq, best_hist


Y = lambda y: int(pd.Timestamp(f"{y}-01-01").timestamp())
SPLITS = [
    ("A train 2022-2023 -> test 2024", Y(2022), Y(2024), Y(2024), Y(2025)),
    ("B train 2022-2024 -> test 2025-2026", Y(2022), Y(2025), Y(2025), Y(2027)),
]

report = {}
for name, tr_lo, tr_hi, te_lo, te_hi in SPLITS:
    print(f"=== GA split {name} ===")
    top, hist = ga(tr_lo, tr_hi, seed=1234 if tr_hi == Y(2024) else 4321)
    rows = []
    for f, g in top:
        gen = decode(g)
        trn = run(gen, sig_filter=lambda ts: tr_lo <= ts < tr_hi)
        tst = run(gen, sig_filter=lambda ts: te_lo <= ts < te_hi)
        rows.append(dict(fit=round(f, 3), params=gen, train=stats(trn), test=stats(tst)))
    for r in rows[:10]:
        print(f"  fit={r['fit']:6.2f}  train n={r['train']['n']:3d} PF={r['train']['pf']:5.2f} R={r['train']['R']:7.2f} dd={r['train']['dd']:5.2f}"
              f"  |  TEST n={r['test']['n']:3d} PF={r['test']['pf']:5.2f} R={r['test']['R']:7.2f} dd={r['test']['dd']:5.2f} t={r['test']['t']:5.2f}")
        print(f"      {json.dumps(r['params'], ensure_ascii=False)}")
    report[name] = rows
    print()

with open(os.path.join(OUT, "ga_report.json"), "w", encoding="utf-8") as fh:
    json.dump(report, fh, indent=1, ensure_ascii=False)

# base como referencia en los mismos tramos
print("=== base en cada tramo ===")
for name, tr_lo, tr_hi, te_lo, te_hi in SPLITS:
    a = run(BASE, sig_filter=lambda ts: tr_lo <= ts < tr_hi)
    b = run(BASE, sig_filter=lambda ts: te_lo <= ts < te_hi)
    print(f"  {name}: train {stats(a)}  ->  test {stats(b)}")
