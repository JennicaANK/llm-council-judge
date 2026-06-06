"""
single_llm_judge.py
-------------------
Asks each model individually (no council), then judges the answer 1-5.
Fills the LEFT column of the results table.

Output files:
  single_llm_results.csv   — one row per (question x model)
  single_llm_summary.csv   — mean / stdev / N per model
"""

import json
import statistics
from pathlib import Path

import ollama
import pandas as pd

# ── config ────────────────────────────────────────────────────────────────────
INPUT_FILE   = Path.home() / "questions.txt"
RESULTS_FILE = Path.home() / "single_llm_results.csv"
SUMMARY_FILE = Path.home() / "single_llm_summary.csv"

ANSWER_MODELS = {
    "Llama":   "llama3.1:latest",
    "Mistral": "mistral:latest",
}
JUDGE_MODEL = "llama3.1:latest"

START_INDEX = 0   # change if resuming partway through
END_INDEX   = None

# ── helpers ───────────────────────────────────────────────────────────────────

def call_model(model, system, user):
    response = ollama.chat(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        options={"temperature": 0},
    )
    return response["message"]["content"].strip()


def get_answer(question, model):
    system = (
        "You are a knowledgeable assistant. "
        "Answer the question directly and concisely in 2-4 sentences. "
        "Do not say you cannot answer."
    )
    return call_model(model, system, question)


def judge_answer(question, answer):
    system = """
You are an evaluator.

Score the answer from 1 to 5:
1 = very poor
2 = weak
3 = okay
4 = good
5 = excellent

Evaluate on:
- correctness
- completeness
- clarity
- usefulness

Return JSON only in exactly this format:
{"score": number, "reason": "short explanation"}
""".strip()

    user = f"Question:\n{question}\n\nAnswer:\n{answer}"
    output = call_model(JUDGE_MODEL, system, user)

    try:
        parsed = json.loads(output)
        score  = max(1, min(5, int(parsed["score"])))
        reason = str(parsed.get("reason", "")).strip()
        return score, reason, output
    except Exception:
        # try to extract a digit if JSON parsing fails
        import re
        match = re.search(r'"score"\s*:\s*([1-5])', output)
        if match:
            return int(match.group(1)), "parsed from raw", output
        return 1, "failed to parse judge output", output


def save_progress(results):
    df = pd.DataFrame(results)
    df.to_csv(RESULTS_FILE, index=False)

    summary_rows = []
    for model_name in ANSWER_MODELS:
        scores = df[df["model"] == model_name]["score"].tolist()
        if scores:
            summary_rows.append({
                "model":      model_name,
                "mean_score": round(statistics.mean(scores), 3),
                "stdev":      round(statistics.pstdev(scores), 3),
                "n":          len(scores),
                "summary":    f"{round(statistics.mean(scores),2)} ± {round(statistics.pstdev(scores),2)} (N={len(scores)})",
            })
    pd.DataFrame(summary_rows).to_csv(SUMMARY_FILE, index=False)


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    lines = INPUT_FILE.read_text(encoding="utf-8").splitlines()
    questions = [l.strip() for l in lines if l.strip()]
    questions = questions[START_INDEX:END_INDEX]

    print(f"Loaded {len(questions)} questions")
    print(f"Answer models : {list(ANSWER_MODELS.keys())}")
    print(f"Judge model   : {JUDGE_MODEL}")
    print(f"Output        : {RESULTS_FILE}\n")

    # load existing results so we can resume if interrupted
    if RESULTS_FILE.exists():
        existing = pd.read_csv(RESULTS_FILE)
        results = existing.to_dict("records")
        done_pairs = set(zip(existing["question_number"], existing["model"]))
        print(f"Resuming — {len(results)} rows already saved.\n")
    else:
        results = []
        done_pairs = set()

    total = len(questions)
    for i, question in enumerate(questions, start=START_INDEX + 1):
        print(f"[{i}/{total + START_INDEX}] {question[:80]}...")

        for model_name, model_id in ANSWER_MODELS.items():
            if (i, model_name) in done_pairs:
                print(f"  skip (already done): {model_name}")
                continue

            print(f"  Getting answer from {model_name}...")
            try:
                answer = get_answer(question, model_id)
            except Exception as e:
                print(f"  ERROR getting answer: {e}")
                answer = f"ERROR: {e}"

            print(f"  Judging {model_name}...")
            try:
                score, reason, raw = judge_answer(question, answer)
            except Exception as e:
                print(f"  ERROR judging: {e}")
                score, reason, raw = 1, f"ERROR: {e}", ""

            results.append({
                "question_number": i,
                "question":        question,
                "model":           model_name,
                "model_id":        model_id,
                "judge_model":     JUDGE_MODEL,
                "answer":          answer,
                "score":           score,
                "reason":          reason,
                "judge_raw":       raw,
            })
            done_pairs.add((i, model_name))
            save_progress(results)
            print(f"  Saved: {model_name} score={score}")

    print("\n=== DONE ===")
    print(f"Results : {RESULTS_FILE}")
    print(f"Summary : {SUMMARY_FILE}")

    summary = pd.read_csv(SUMMARY_FILE)
    print("\n" + summary[["model","mean_score","stdev","n"]].to_string(index=False))


if __name__ == "__main__":
    main()
