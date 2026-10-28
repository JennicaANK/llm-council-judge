# LLM-as-Council for Timely Question Prediction
**San Jose State University | Spring 2026 | Aye Nyein Kyaw**

## Project Summary

This project investigates whether a group of language models working together (LLM-as-Council) can answer real-world prediction questions more accurately than a single model alone. Questions were collected from Polymarket, a prediction market where users bet on real-world outcomes. All models were run locally via Ollama on a university GPU server (NVIDIA DGX Spark).

---

## Repository Structure

```
├── DataCollection.py                 # Collects questions from Polymarket API (old dataset)
├── DataCollection_v2.py              # Collects unresolved questions, skips finance/crypto
├── single_llm_judge.py               # Runs each model individually + LLM-as-judge scoring
├── ollama_council_batch_v2.py        # Runs LLM council + judge, saves after every question
├── fetch_outcomes.py                 # Fetches resolved outcomes from Polymarket API
├── compare_predictions.py            # Compares model predictions against real outcomes
├── new_questions.xlsx                # New dataset: 2,000 unresolved questions
├── new_questions.txt                 # Plain text version for server runs
├── single_llm_results.csv            # Single-model results (old dataset, 1,492 questions)
├── single_llm_summary.csv            # Single-model summary (old dataset)
├── comparison_summary.xlsx           # Accuracy vs ground truth (old dataset)
├── council_run2_summary.xlsx         # 2-model council summary (old dataset)
├── council_run3_summary.xlsx         # 3-model council summary (old dataset)
├── fetch_outcomes_v2.py   
├── compare_predictions_v2.py 
├── rescore_predictions.py            # Corrected scoring (use this for accuracy)
└── README.md
```

---

## Datasets

### Dataset 1 (Old) — 1,492 questions, already resolved
- Collected April 7, 2026 via Polymarket Gamma API
- Categories: crypto, finance, sports, politics, AI benchmarks
- All resolved by May 2026
- Ground truth fetched for 947 verified binary questions

### Dataset 2 (New) — 2,000 questions, unresolved at time of collection
- Collected July 2026 via Polymarket Gamma API
- Finance and crypto categories excluded
- Categories: politics, sports, science, culture, entertainment
- Resolution dates: July–December 2026
- 1,630 binary (Yes/No), 370 multi-choice

---

## Models Used

All models run locally via [Ollama](https://ollama.com) on NVIDIA DGX Spark server.

| Model | String | Parameters |
|---|---|---|
| Llama 3.1 8B | llama3.1:8b-instruct-q4_K_M | 8B |
| Mistral 7B | mistral:latest | 7B |
| QWEN 3 8B | qwen3:8b | 8B |
| Gemma 2 9B | gemma2:9b | 9B |
| Phi-3 Medium | phi3:medium | 14B |
| DeepSeek R1 8B | deepseek-r1:8b | 8B |

Judge model: Llama 3.1 8B in all experiments.

---

## Method

**Single-model evaluation:** Each model answers every question independently in 2–4 sentences. A Llama 3.1 8B judge scores each answer 1–5 on correctness, completeness, clarity, and usefulness.

**LLM-as-Council:**
1. All answer models answer the question independently, using a structured "Predicted answer / Reasoning" format
2. A chairman model reads all answers and writes one final council answer
3. A Llama 3.1 8B judge scores the council answer 1–5 on clarity, reasoning quality, relevance, and overall quality (explicitly not real-world correctness)

**Ground truth:** Resolved outcomes are fetched from the Polymarket Gamma API. Accuracy is computed by `rescore_predictions.py` (see "Scoring correction" below).

---

## Scoring correction (October 2026)

My original comparison scripts (`compare_predictions.py`, `compare_predictions_v2.py`) counted a prediction as correct if the true answer appeared anywhere inside it as a substring. Because "no" appears inside words like "not", "know" and "November", many non-answers were counted as correct whenever a market resolved No. This inflated every accuracy number I reported earlier (for example, 55% for the 2-model council).

`rescore_predictions.py` replaces that logic. It extracts one label per answer using whole-word matching, treats refusals and non-answers as wrong, and reports parse rate, 95% confidence intervals, trivial baselines, and paired McNemar tests. I spot-checked the extracted labels by hand: council labels were all correct in my sample (32/32), and about 10% of single-model labels were wrong.

---

## Results — Old Dataset (947 verified binary questions)

| Setup | Accuracy | 95% CI | Gave a clear answer | Accuracy when it answered |
|---|---|---|---|---|
| 3-model council, Llama chairman | 33.1% | 30.2–36.2 | 53.5% | 61.9% |
| 2-model council, Llama chairman | 25.7% | 23.0–28.5 | 41.3% | 62.2% |
| 3-model council, Mistral chairman | 21.4% | 18.9–24.2 | 33.7% | 63.5% |
| 2-model council, Mistral chairman | 18.2% | 15.8–20.8 | 29.3% | 62.1% |
| 3-model council, QWEN chairman (n=860) | 17.7% | 15.3–20.4 | 25.9% | 68.2% |
| Single Mistral | 0.4% | 0.2–1.1 | 0.7% | — |
| Single QWEN | 0.2% | 0.1–0.8 | 1.1% | — |
| Single Llama | 0.1% | 0.0–0.6 | 0.2% | — |
| **Baseline: always "No"/"Under"** | **61.9%** | 58.7–64.9 | 100% | 61.9% |

## Results — New Dataset (1,975 resolved questions)

| Setup | Accuracy | Gave a clear answer | Accuracy when it answered | Mean judge score |
|---|---|---|---|---|
| Council, Llama chairman | 36.0% | 62.6% | 57.6% | 4.79 |
| Council, Mistral chairman | 22.0% | 41.6% | 52.7% | 4.40 |
| Single Phi-3 | 16.5% | 46.4% | 35.4% | 3.60 |
| Council, QWEN chairman (n=1,926) | 11.6% | 23.8% | 48.7% | 4.79 |
| Single DeepSeek R1 | 3.1% | 8.1% | 39.0% | 3.70 |
| Single Llama | 2.1% | 4.8% | 43.6% | 3.56 |
| Single Mistral | 1.5% | 4.8% | 31.6% | 3.46 |
| Single Gemma 2 | 1.4% | 3.6% | 39.4% | 3.68 |
| Single QWEN | 1.4% | 3.4% | 39.7% | 3.60 |
| **Baseline: always "No"** (1,611 binary questions) | **67.0%** | 100% | 67.0% | — |

Single-model and council judge scores use different rubrics, so they should not be compared with each other.

## Key findings

- **No setup beats a trivial baseline.** Always answering "No" scores 62% (old) and 67% (new). Even on the questions where the council committed to an answer, it was right only 58–62% of the time.
- **The council's main effect is getting models to commit to an answer.** Single models rarely gave a clear Yes/No, because their prompt never asked for one. Council outputs were structured, so they committed far more often. Because the prompts differ, this is not a clean test of whether councils reason better.
- **The Llama chairman is the strongest chairman** on both datasets (McNemar p < 0.001 vs. Mistral and QWEN), mainly because it abstains less often.
- **Judge scores do not track accuracy.** In the new council run, QWEN and Llama chairmen received the same mean judge score (4.79) but reached 11.6% and 36.0% accuracy.
- **Single models often invented past results**, for example stating that a team "was leading" in a match that had not happened yet.

## Limitations

- Single-model and council runs used different prompts, temperatures, and judge rubrics.
- Questions were passed as plain text, so models never saw the allowed answer choices.
- Llama 3.1 8B was both the judge and one of the answer and chairman models, which allows self-preference bias.
- Some single-model answers open with "Yes," or "No," without making a real prediction; about 10% of extracted single-model labels were wrong in a manual spot check.
- Council runs had timeouts on a shared server; 129 (old) and 908 (new) error rows were dropped.

## Next steps

- Rerun single models with the same structured prompt the council uses, so the comparison is controlled
- Pass answer choices to all models
- Use a judge model that is not also a contestant
- Compare against the Polymarket market price as a stronger baseline

---

## How to Reproduce

### 1. Install dependencies
```bash
pip install requests openpyxl python-dateutil pandas
# Install Ollama from https://ollama.com
ollama pull llama3.1:8b
ollama pull mistral
ollama pull qwen3:8b
```

### 2. Collect new unresolved questions
```bash
python3 DataCollection_v2.py --out new_questions.xlsx --target 2000 --days 180
```

### 3. Run single-model judge
```bash
python3 single_llm_judge.py
```

### 4. Run council
```bash
python3 ollama_council_batch_v2.py \
  --input new_questions.txt \
  --out-prefix council_run \
  --limit 2000 \
  --answer-models llama3.1:latest mistral:latest qwen3:8b \
  --chairman-models llama3.1:latest mistral:latest qwen3:8b \
  --judge-model llama3.1:latest
```

### 5. Fetch ground truth and compare
```bash
python3 python3 fetch_outcomes_v2.py
python3 rescore_predictions.py --dataset new
```

---

## Infrastructure

- Server: NVIDIA DGX Spark (spark-833c), accessed via Tailscale SSH
- Working directory: /home/ayenyeinkyaw/
- All models run via Ollama — no cloud API costs

---

## References

- [LLM Council (Karpathy)](https://github.com/karpathy/llm-council)
- [Chain-of-Thought Prompting — Wei et al. 2022](https://arxiv.org/abs/2201.11903)
- [GPQA Benchmark — Rein et al. 2023](https://arxiv.org/abs/2311.12022)
- [Humanity's Last Exam — Phan et al. 2025](https://arxiv.org/abs/2501.14249)
- [Polymarket Gamma API](https://gamma-api.polymarket.com/events)