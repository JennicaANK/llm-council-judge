# CS180 — LLM-as-Council for Timely Question Prediction
**San Jose State University | Spring 2026 | Aye Nyein Kyaw**

## Project Summary
This project builds a benchmark of timely prediction questions sourced from Polymarket and evaluates how well individual LLMs and an LLM-as-Council ensemble answer them. Answers are scored by an LLM-as-Judge workflow.

---

## Repository Structure
```
├── DataCollection.py               # Pulls questions from Polymarket API → Excel
├── ollama_council_batch_v2.py      # Runs LLM council + judge, saves incrementally
├── run_all_overnight.sh            # Batch runner script
├── CS180_DataCollection_1500.xlsx  # Full question dataset (1500 questions)
├── council_run1_detailed.xlsx      # Raw results: 879 questions × 2 chairmen
├── council_run1_summary_FINAL.xlsx # Final summary stats (normalized to 1-5 scale)
└── README.md                       # This file
```

---

## Dataset
- **Source**: Polymarket (prediction market)
- **Total collected**: 1,500 questions
- **Questions processed by council**: 879
- **Categories**: Finance, crypto, sports, politics, AI benchmarks

---

## Method: LLM-as-Council
1. **Answer models** (llama3.1:8b + mistral) each answer the question independently
2. **Chairman model** (llama3.1:8b or mistral) reads both answers and produces one council answer
3. **Judge model** (llama3.1:8b) scores the council answer on clarity, reasoning quality, relevance, overall (1–5 scale)

---

## Results Summary (879 questions, normalized to 1-5 scale)

| Chairman Model | N | Mean Overall | Median | Stdev |
|---|---|---|---|---|
| llama3.1:8b | 878 | 4.577 | 5.0 | 0.516 |
| mistral | 876 | 4.298 | 4.0 | 0.461 |

**Note on scale**: Questions 1–20 were scored on a 1–10 scale (initial run). Questions 21–879 were scored on 1–5. All scores normalized to 1–5 for comparison.

---

## How to Reproduce

### 1. Install dependencies
```bash
pip install requests openpyxl python-dateutil pandas
# Install Ollama app from https://ollama.com
ollama pull llama3.1:8b
ollama pull mistral
```

### 2. Collect questions
```bash
python DataCollection.py \
  --template CS180_DataCollection_1500.xlsx \
  --out new_questions.xlsx \
  --target 100 \
  --days 7
```

### 3. Run the council (safe batches of 20)
```bash
bash run_all_overnight.sh
# or manually:
python ollama_council_batch_v2.py \
  --input CS180_DataCollection_1500.xlsx \
  --out-prefix council_run1 \
  --start-row 0 --limit 20 \
  --answer-models llama3.1:8b mistral \
  --chairman-models llama3.1:8b mistral \
  --judge-model llama3.1:8b
```

---

## Key Findings
- llama3.1:8b as chairman consistently outscored mistral as chairman (mean 4.58 vs 4.30 on 1–5 scale)
- Both models frequently refused to predict on financial/betting questions (sports spreads, stock prices), falling back to the other model's answer
- Questions with binary choices (Yes/No) received higher judge scores than multi-choice questions
- Mistral often declined to give a specific prediction; llama3.1:8b more willingly committed to an answer

---

## References
- [LLM Council (Karpathy)](https://github.com/karpathy/llm-council)
- [Chain-of-Thought Prompting](https://arxiv.org/abs/2201.11903)
- [GPQA Benchmark](https://arxiv.org/abs/2311.12022)
- [Polymarket API](https://gamma-api.polymarket.com/events)
