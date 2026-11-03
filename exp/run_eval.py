#!/usr/bin/env python3
"""Run closure-status prompts against a local Ollama model.

Usage:
  python3 run_eval.py --dry-run                      # print one filled prompt per variant, no model call
  python3 run_eval.py --split dev --prompts P0       # quick trial on the 24 dev scenarios
  python3 run_eval.py                                # all 6 prompts x 72 scenarios
Resumes automatically: finished (prompt, id) pairs in results/ are skipped.
"""
import argparse, json, os, re, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
EVAL_TIME = "2026-11-17 18:00 (UTC+8)"
VARIANTS = ["P0", "P1", "P2", "P3", "P4", "P5"]
FILES = {"P0": "P0_baseline.txt", "P1": "P1_definitions.txt", "P2": "P2_decision_order.txt",
         "P3": "P3_reasoning_step.txt", "P4": "P4_chinese_instructions.txt"}
LABEL_RE = re.compile(r"^\s*STATUS:\s*(open|canceled|fulfilled|full)\s*$", re.I)

def template_for(variant, lang):
    name = f"{variant}_few_shot_{lang}.txt" if variant in ("P5", "P5R") else FILES[variant]
    with open(os.path.join(HERE, "prompts", name), encoding="utf-8") as f:
        return f.read()

def build_prompt(variant, o):
    t = template_for(variant, o["lang"])
    # str.replace, not str.format: conversation text may contain braces
    return (t.replace("{target_id}", o["first_request"])
             .replace("{eval_time}", EVAL_TIME)
             .replace("{conversation}", "\n".join(o["conversation"])))

def parse(raw):
    """Last line of the form 'STATUS: <label>'. Returns label or None (invalid)."""
    for line in reversed(raw.strip().splitlines()):
        m = LABEL_RE.match(line)
        if m:
            return m.group(1).lower()
    return None

def call_ollama(host, model, prompt, a):
    body = {"model": model, "stream": False,
            "messages": [{"role": "user", "content": prompt}],
            "options": {"temperature": 0, "seed": a.seed, "num_predict": a.max_tokens, "num_ctx": a.num_ctx}}
    req = urllib.request.Request(host + "/api/chat", json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read())

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="qwen2.5:7b-instruct-q4_K_M")
    ap.add_argument("--host", default="http://localhost:11434")
    ap.add_argument("--data", default=os.path.join(HERE, "dataset_v3.2.jsonl"))
    ap.add_argument("--out", default=os.path.join(HERE, "results"))
    ap.add_argument("--prompts", nargs="+", default=VARIANTS)
    ap.add_argument("--split", choices=["all", "dev", "held-out"], default="all")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--max-tokens", type=int, default=512)
    ap.add_argument("--num-ctx", type=int, default=8192)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    data = [json.loads(l) for l in open(a.data, encoding="utf-8")]
    if a.split != "all": data = [o for o in data if o["split"] == a.split]
    if a.limit: data = data[:a.limit]
    os.makedirs(a.out, exist_ok=True)

    if a.dry_run:
        for v in a.prompts:
            o = data[0]
            print(f"===== {v} | {o['id']} {o['lang']} =====\n{build_prompt(v, o)}\n")
        return

    for v in a.prompts:
        path = os.path.join(a.out, f"{v}.jsonl")
        done = set()
        if os.path.exists(path):
            done = {json.loads(l)["id"] for l in open(path, encoding="utf-8") if l.strip()}
        todo = [o for o in data if o["id"] not in done]
        print(f"[{v}] {len(done)} done, {len(todo)} to run", flush=True)
        with open(path, "a", encoding="utf-8") as f:
            for k, o in enumerate(todo, 1):
                prompt = build_prompt(v, o)
                t0 = time.time()
                try:
                    r = call_ollama(a.host, a.model, prompt, a)
                except Exception as e:
                    sys.exit(f"Ollama call failed ({e}). Is `ollama` running? Re-run to resume.")
                raw = r["message"]["content"]
                rec = {"id": o["id"], "prompt": v, "model": a.model, "raw": raw, "pred": parse(raw),
                       "seconds": round(time.time() - t0, 2),
                       "prompt_tokens": r.get("prompt_eval_count"), "output_tokens": r.get("eval_count"),
                       "done_reason": r.get("done_reason")}
                f.write(json.dumps(rec, ensure_ascii=False) + "\n"); f.flush()
                if k % 12 == 0 or k == len(todo):
                    print(f"  [{v}] {k}/{len(todo)}", flush=True)

if __name__ == "__main__":
    main()
