# Group-chat closure status: prompt comparison

How does prompt structure affect an LLM's identification of the closure status of a request in a group chat?

One model is fixed and only the prompt varies. Accuracy is read relatively across prompts, not as an absolute score.

## Task

Each scenario is a 12-message group chat. The target request is always m-03. The model must label its status at the evaluation time (2026-11-17 18:00, UTC+8) as one of:

| Label | Meaning |
|---|---|
| open | The initiator has not closed the request |
| canceled | The initiator ended it without completing it |
| fulfilled | The initiator confirms the goal is secured |
| full | A capacity-limited offer whose spots or items are all taken |

Decision priority used in annotation: canceled, full, fulfilled, open.

## Data

`dataset_v3.2.jsonl` has 72 scenarios: 12 skeletons (S01-S12) x 2 explicitness levels x 3 languages.

- Level: L1 = m-09 replies to m-03 and states the status; L3 = m-09 replies to m-07 and does not state it.
- Language: ZH, EN, MIX (Chinese matrix language with embedded English words).
- Balanced: 9 scenarios per Status x Level cell, 24 per language.
- Fields: id, conversation (12 lines), first_request, gold_status, level, lang, scenario, split (dev / held-out), revised.
- Only `conversation` and `first_request` are shown to the model. Everything else is for scoring.
- Reply markers are written as `[reply m-XX]` in all languages.

Annotation agreement: Final Status kappa = 0.963 (70/72 agree before adjudication).

### Data versions

| Version | Note |
|---|---|
| v3.1 | In ZH and MIX, the m-10 distractor "回复" had been replaced by "reply". Results from this version are superseded. |
| v3.2 | m-10 restored to "回复消息" (ZH) and "回复 messages" (MIX). Current version. |

Rule: do not edit a released dataset file. Any change is saved as a new version, and all prompts are rerun.

## Model and settings

qwen2.5:7b-instruct-q4_K_M via Ollama (ID 845dbda0ea48, 7.6B, Q4_K_M).
temperature 0, seed 42, num_ctx 8192, max tokens 512. No extra system prompt; the model's default template applies.

## Prompts (`prompts/`)

| ID | Change relative to P0 |
|---|---|
| P0 | Baseline: label names only, answer only, English, zero-shot |
| P1 | Adds label definitions |
| P2 | Adds decision order canceled > full > fulfilled > open |
| P3 | Asks to trace the reply thread before answering |
| P4 | Instructions in Chinese (labels stay English) |
| P5 | Adds 4 solved examples (not from the 72 scenarios); example file follows scenario language |
| P5R | Exploratory: P5 with example order reversed. Run after seeing P5 results. |

Every prompt ends with `STATUS: <label>`. Only the last such line is parsed. Anything else counts as invalid (and incorrect).

## Run

    python3 validate.py dataset_v3.2.jsonl      # data checks
    python3 run_eval.py --dry-run               # inspect filled prompts, no model call
    python3 run_eval.py --split dev --prompts P0 --limit 3   # trial
    python3 run_eval.py                         # P0-P5 on all 72 (resumable)
    python3 run_eval.py --prompts P5R           # exploratory variant
    python3 score.py                            # accuracy, confusion, error direction, McNemar

Requires Ollama running locally with the model pulled. Scripts use the Python standard library; the heatmap needs matplotlib and numpy.

`score.py` writes `matrix_accuracy.csv`, `matrix_delta.csv` and `matrix_accuracy.png`. McNemar exact tests compare each variant with P0; Holm correction covers P1-P5 only, and exploratory variants are reported unadjusted.

## Results (v3.2, n = 72)

| Prompt | Accuracy | vs P0 |
|---|---|---|
| P0 | 0.750 | |
| P1 | 0.792 | +4.2, n.s. |
| P2 | 0.806 | +5.6, n.s. |
| P3 | 0.597 | -15.3, p_holm = 0.004 |
| P4 | 0.708 | -4.2, n.s. |
| P5 | 0.403 | -34.7, p_holm < 0.001 |
| P5R (exploratory) | 0.569 | -18.1, p = 0.004 (unadjusted) |

Differences of two or three items are within noise: changing one unrelated sentence flipped one prediction in four of six prompts.

## Known limitations

- 72 scenarios, one model, one run per prompt.
- m-07 and m-09 are always in the target thread, so the reply thread is the same in every scenario. The P3 tracing step carries no information.
- P5 examples are shorter and cleaner than the test chats, and results depend on example order.
- Not fixed in v3.2: S04_L3 content differs across languages; A27, A48, A58 break the MIX matrix-language rule; A03 m-09 has no English word; some cross-language reference rules (D22) are violated; chats have no timestamps.

## Layout

    dataset_v3.2.jsonl
    prompts/
    run_eval.py  score.py  validate.py
    results/                 raw outputs, one JSONL per prompt
    matrix_*.csv / .png      score.py outputs
