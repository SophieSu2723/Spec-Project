#!/usr/bin/env python3
"""Score results/*.jsonl against dataset gold labels. Stdlib only.
Usage: python3 score.py [--results results] [--data dataset_v3.2.jsonl] [--baseline P0]
"""
import argparse, json, os, collections
from math import comb

LABELS = ["open", "canceled", "fulfilled", "full"]
CLOSED = {"canceled", "fulfilled", "full"}

def mcnemar_exact(b, c):
    n = b + c
    if n == 0: return 1.0
    k = min(b, c)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n)

def holm(ps):
    order = sorted(range(len(ps)), key=lambda i: ps[i]); out = [0] * len(ps); prev = 0
    for rank, i in enumerate(order):
        prev = max(prev, min(1.0, ps[i] * (len(ps) - rank))); out[i] = prev
    return out

def err_dir(g, p):
    if p is None: return "invalid"
    if g == p: return "correct"
    if g in CLOSED and p == "open": return "false_open"
    if g == "open" and p in CLOSED: return "false_closed"
    return "wrong_closure"

def main():
    HERE = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default=os.path.join(HERE, "results"))
    ap.add_argument("--data", default=os.path.join(HERE, "dataset_v3.2.jsonl"))
    ap.add_argument("--baseline", default="P0")
    ap.add_argument("--exploratory", nargs="*", default=["P5R"], help="variants excluded from the Holm family, reported with raw p only")
    ap.add_argument("--outdir", default=HERE)
    a = ap.parse_args()
    gold = {o["id"]: o for o in map(json.loads, open(a.data, encoding="utf-8"))}
    R = {}
    for fn in sorted(os.listdir(a.results)):
        if fn.endswith(".jsonl"):
            R[fn[:-6]] = {r["id"]: r for r in map(json.loads, open(os.path.join(a.results, fn), encoding="utf-8"))}
    for v, rs in R.items():
        print(f"\n===== {v}  (n={len(rs)}) =====")
        ok = lambda r: r["pred"] == gold[r["id"]]["gold_status"]
        acc = sum(ok(r) for r in rs.values()) / len(rs)
        inv = sum(r["pred"] is None for r in rs.values())
        trunc = sum(r.get("done_reason") == "length" for r in rs.values())
        print(f"accuracy {acc:.3f} | invalid {inv} | truncated {trunc}")
        for key in ("level", "lang", "gold_status", "scenario"):
            g = collections.defaultdict(list)
            for r in rs.values(): g[gold[r["id"]][key]].append(ok(r))
            print(f"  by {key}: " + "  ".join(f"{k}={sum(x)/len(x):.2f}({len(x)})" for k, x in sorted(g.items())))
        d = collections.Counter(err_dir(gold[r["id"]]["gold_status"], r["pred"]) for r in rs.values())
        print("  error direction:", dict(d))
        cm = collections.Counter((gold[r["id"]]["gold_status"], r["pred"] or "invalid") for r in rs.values())
        cols = LABELS + ["invalid"]
        print("  confusion (rows=gold, cols=pred)")
        print("    " + "".join(f"{c:>11}" for c in cols))
        for g_ in LABELS: print(f"    {g_:<10}" + "".join(f"{cm[(g_, c)]:>11}" for c in cols))
    if a.baseline in R:
        base = R[a.baseline]
        def test(v):
            ids = [i for i in R[v] if i in base]
            b = sum(1 for i in ids if base[i]["pred"] == gold[i]["gold_status"] and R[v][i]["pred"] != gold[i]["gold_status"])
            c = sum(1 for i in ids if base[i]["pred"] != gold[i]["gold_status"] and R[v][i]["pred"] == gold[i]["gold_status"])
            return (v, len(ids), b, c, mcnemar_exact(b, c))
        main_v = [v for v in R if v != a.baseline and v not in a.exploratory]
        expl_v = [v for v in R if v in a.exploratory]
        rows = [test(v) for v in main_v]
        adj = holm([r[4] for r in rows]) if rows else []
        print(f"\n===== McNemar exact vs {a.baseline} (b = only baseline correct, c = only variant correct) =====")
        print(f"  Holm family: {', '.join(main_v)}")
        for r, p in zip(rows, adj):
            print(f"  {r[0]}: n={r[1]} b={r[2]} c={r[3]} p={r[4]:.4f} p_holm={p:.4f}")
        for v in expl_v:
            r = test(v)
            print(f"  {r[0]} (exploratory, unadjusted): n={r[1]} b={r[2]} c={r[3]} p={r[4]:.4f}")
    write_matrices(R, gold, a)

def write_matrices(R, gold, a):
    import csv
    os.makedirs(a.outdir, exist_ok=True)
    cols = [("overall", lambda g: True), ("L1", lambda g: g["level"] == "L1"), ("L3", lambda g: g["level"] == "L3"),
            ("EN", lambda g: g["lang"] == "EN"), ("ZH", lambda g: g["lang"] == "ZH"), ("MIX", lambda g: g["lang"] == "MIX"),
            ("open", lambda g: g["gold_status"] == "open"), ("canceled", lambda g: g["gold_status"] == "canceled"),
            ("fulfilled", lambda g: g["gold_status"] == "fulfilled"), ("full", lambda g: g["gold_status"] == "full")]
    acc = {}
    for v, rs in R.items():
        acc[v] = []
        for _, f in cols:
            sel = [r for r in rs.values() if f(gold[r["id"]])]
            acc[v].append(sum(r["pred"] == gold[r["id"]]["gold_status"] for r in sel) / len(sel) if sel else float("nan"))
    names = [c[0] for c in cols]
    with open(os.path.join(a.outdir, "matrix_accuracy.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["prompt"] + names)
        for v in R: w.writerow([v] + [f"{x:.3f}" for x in acc[v]])
    if a.baseline in R:
        with open(os.path.join(a.outdir, "matrix_delta.csv"), "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f); w.writerow(["prompt"] + names)
            for v in R: w.writerow([v] + [f"{(x - y) * 100:+.1f}" for x, y in zip(acc[v], acc[a.baseline])])
    print(f"\nWrote matrix_accuracy.csv / matrix_delta.csv to {a.outdir}")
    try:
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        import numpy as np
        M = np.array([acc[v] for v in R]); fig, ax = plt.subplots(figsize=(10, 0.7 * len(R) + 1.5))
        im = ax.imshow(M, vmin=0, vmax=1, cmap="RdYlGn", aspect="auto")
        ax.set_xticks(range(len(names))); ax.set_xticklabels(names); ax.set_yticks(range(len(R))); ax.set_yticklabels(list(R))
        for i in range(M.shape[0]):
            for j in range(M.shape[1]): ax.text(j, i, f"{M[i, j]:.2f}", ha="center", va="center", fontsize=9)
        ax.axvline(0.5, color="white", lw=3); ax.axvline(2.5, color="white", lw=3); ax.axvline(5.5, color="white", lw=3)
        fig.colorbar(im, ax=ax, label="accuracy"); fig.tight_layout()
        fig.savefig(os.path.join(a.outdir, "matrix_accuracy.png"), dpi=200); print("Wrote matrix_accuracy.png")
    except ImportError:
        print("matplotlib not installed: skipped heatmap (pip install matplotlib numpy)")

if __name__ == "__main__":
    main()
