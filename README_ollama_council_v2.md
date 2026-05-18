# Local LLM-as-Council workflow — v2
## What changed from v1
| Feature | v1 | v2 |
|---|---|---|
| Saves results | Only at the end (crash = data loss) | After **every single question** |
| Resume support | None — reruns everything | Skips (question_id, chairman) pairs already in the output file |
| Summary stats | mean, stdev, N | **mean, median, stdev, N** |
| Crash safety | Mac crashed at 1500 questions | Run in small batches; always resumable |

---

## 1) Install Ollama and pull models
```bash
# macOS — install the Ollama app first, then:
ollama pull llama3.1:8b
ollama pull mistral
```

---

## 2) Safe batch strategy (run in chunks of 20-50)

Because Ollama runs fully locally, each call is slow and memory-intensive.
**Do not try to run all 1500 at once.** Instead, repeat small runs:

```bash
# Batch 1: rows 0-19
python ollama_council_batch_v2.py \
  --input CS180_DataCollection_1500.xlsx \
  --out-prefix council_run1 \
  --start-row 0 --limit 20 \
  --answer-models llama3.1:8b mistral \
  --chairman-models llama3.1:8b mistral \
  --judge-model llama3.1:8b

# Batch 2: rows 20-39  (output file is the same; duplicates are skipped)
python ollama_council_batch_v2.py \
  --input CS180_DataCollection_1500.xlsx \
  --out-prefix council_run1 \
  --start-row 20 --limit 20 \
  --answer-models llama3.1:8b mistral \
  --chairman-models llama3.1:8b mistral \
  --judge-model llama3.1:8b

# Keep incrementing --start-row by 20 each time
# The script automatically skips anything already saved
```

You can also write a simple shell loop:
```bash
for START in 0 20 40 60 80 100; do
  python ollama_council_batch_v2.py \
    --input CS180_DataCollection_1500.xlsx \
    --out-prefix council_run1 \
    --start-row $START --limit 20 \
    --answer-models llama3.1:8b mistral \
    --chairman-models llama3.1:8b mistral \
    --judge-model llama3.1:8b
  sleep 5   # short rest between batches
done
```

---

## 3) Output files
| File | Contents |
|---|---|
| `council_run1_detailed.xlsx` | One row per (question × chairman). Has council answer, all judge scores, raw LLM output. |
| `council_run1_summary.xlsx` | Per-chairman: N, mean, **median**, stdev of `judge_overall`. |

---

## 4) Summary statistics produced
For each chairman model the summary file reports:

| Column | Meaning |
|---|---|
| `n` | Number of questions judged |
| `mean_judge_overall` | Average judge score (1–5) |
| `median_judge_overall` | Median judge score |
| `stdev_judge_overall` | Standard deviation |

These are the numbers that go in your **Week 4 / Week 5** deliverables and your final report.

---

## 5) Where you are on the syllabus right now

| Week | Task | Status |
|---|---|---|
| 1 | Build dataset ≥100 questions from Polymarket | ✅ Done (1500 collected) |
| 2 | LLM Council code, easy-to-use orchestration | ✅ Done (`ollama_council_batch_v2.py`) |
| 3 | Prompting experiments on dataset | ✅ Pilot (20 Qs done); **needs more runs** |
| 4 | Find metrics (Bleu, Accuracy, Judge scores…) | ✅ Judge scoring in place; add more metrics in report |
| 5 | Write code, evaluate with metrics | 🔄 In progress — keep running batches |
| 6 | Chain-of-thought reasoning, progress report | 📝 Write 1-page update |
| 7 | Modify prompts (elimination / exclusion) | 🔜 Next coding task |
| 8 | Transform questions to expert-level research problems | 🔜 |
| 9 | LLM-as-judge evaluation, test cases | ✅ Judge in place; write formal test cases |
| 10–12 | More code, test case summary | 🔜 |
| 13 | Save to gSheet, GitHub, gDrive | 🔜 |
| 14 | Code review + presentation | 🔜 |
| 15 | Final report | 🔜 |

---

## 6) Exact command history to document (reproducibility)

Keep a file called `commands.md` and paste every command you actually run, for example:

```
## Run 1 — 2026-05-16
python ollama_council_batch_v2.py \
  --input CS180_DataCollection_1500.xlsx \
  --out-prefix council_run1 \
  --start-row 0 --limit 20 \
  --answer-models llama3.1:8b mistral \
  --chairman-models llama3.1:8b mistral \
  --judge-model llama3.1:8b
# Result: 40 rows written (20 questions × 2 chairman models)
```

Your professor specifically asked for "exact command history and script versions" for reproducibility.

---

## One-sentence project description
> I am building a timely-question benchmark from Polymarket and using it to compare individual LLM answers against LLM-as-council answers, scored with an LLM-as-judge workflow.
