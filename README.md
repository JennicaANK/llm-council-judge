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

**Single-model evaluation:**
Each model answers every question independently. The judge scores the answer 1-5 on correctness, completeness, clarity, and usefulness.

**LLM-as-Council:**
1. All answer models answer the question independently
2. A chairman model reads all answers and synthesizes one final council answer
3. The judge scores the council answer 1-5

---

## Results — Old Dataset (1,492 questions)

### Single-model judge scores

| Model | Mean | Stdev | N |
|---|---|---|---|
| Llama 3.1 8B | 3.77 | 1.41 | 1,492 |
| Mistral 7B | 4.37 | 0.99 | 1,492 |
| QWEN 3 8B | 4.57 | 0.69 | 1,492 |

### 2-model council (Llama + Mistral)

| Chairman | Mean | Stdev | N |
|---|---|---|---|
| Llama 3.1 8B | 4.86 | 0.43 | 1,491 |
| Mistral 7B | 4.67 | 0.47 | 1,492 |

### 3-model council (Llama + Mistral + QWEN)

| Chairman | Mean | Stdev | N |
|---|---|---|---|
| QWEN 3 8B | 4.93 | 0.25 | 1,363 |
| Llama 3.1 8B | 4.90 | 0.31 | 1,486 |
| Mistral 7B | 4.59 | 0.50 | 1,486 |

### Ground truth accuracy (947 verified binary questions)

| Setup | Accuracy | Mean Judge Score |
|---|---|---|
| 2-model council, Llama chairman | 55.12% | 4.93 |
| 3-model council, Llama chairman | 54.19% | 4.91 |
| 2-model council, Mistral chairman | 53.96% | 4.73 |
| 3-model council, Mistral chairman | 53.55% | 4.64 |
| Single QWEN | 49.52% | 4.63 |
| 3-model council, QWEN chairman | 46.86% | 4.94 |
| Single Mistral | 35.90% | 4.70 |
| Single Llama | 23.23% | 4.45 |

### Key findings

- The council significantly improved Llama accuracy (23% to 55%, +32 points)
- Adding QWEN as a third model did not improve council accuracy — the 2-model council remained the best setup
- QWEN scored higher alone (49.52%) than as a chairman (46.86%), despite having the highest judge score as chairman (4.94) — judge scores do not always correlate with factual correctness
- Llama's large improvement is partly explained by refusal laundering: single Llama frequently refused financial and betting questions (scored 1 by judge), while in the council Mistral's answer was always available for synthesis

---

## Results — New Dataset (2,000 questions, in progress)

### Single-model judge scores

| Model | Mean | Stdev | N |
|---|---|---|---|
| DeepSeek R1 8B | 3.711 | 1.642 | 2,000 |
| Gemma 2 9B | 3.679 | 1.734 | 2,000 |
| QWEN 3 8B | 3.610 | 1.664 | 2,000 |
| Phi-3 Medium | 3.599 | 1.498 | 2,000 |
| Llama 3.1 8B | 3.558 | 1.482 | 2,000 |
| Mistral 7B | 3.463 | 1.674 | 2,000 |

Council run and ground truth validation in progress.

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
python3 fetch_outcomes.py
python3 compare_predictions.py
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