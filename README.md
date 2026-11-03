# Closure-status experiment

Model: qwen2.5:7b-instruct-q4_K_M (Ollama, ID 845dbda0ea48), temperature 0, seed 42, num_ctx 8192, max tokens 512.
Data: dataset_v3.2.jsonl (72 scenarios). Prompts: prompts/ (P5 uses the file matching the scenario language).

    python3 validate.py dataset_v3.2.jsonl      # data checks
    python3 run_eval.py --dry-run               # inspect filled prompts
    python3 run_eval.py --split dev --prompts P0 --limit 3   # trial
    python3 run_eval.py                         # full run, resumable
    python3 score.py                            # accuracy, confusion, error direction, McNemar (Holm)
