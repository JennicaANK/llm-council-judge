"""
compare_predictions_v2.py
--------------------------
Compares single-model and council predictions against real Polymarket outcomes
for the NEW 2,000 question dataset.

Requires:
  - new_questions_resolved.xlsx     (questions with correct_answer filled in)
  - new_single_llm_results.csv      (single-model answers: all 6 models)
  - new_council_detailed.xlsx       (council answers: 3 chairmen)

Output:
  - new_comparison_results.xlsx     (full comparison table)
  - new_comparison_summary.xlsx     (accuracy per model/setup)
"""

import re
import pandas as pd
from pathlib import Path

RESOLVED_FILE  = "new_questions_resolved.xlsx"
SINGLE_FILE    = "new_single_llm_results.csv"
COUNCIL_FILE   = "new_council_detailed.xlsx"
OUTPUT_FILE    = "new_comparison_results.xlsx"
SUMMARY_FILE   = "new_comparison_summary.xlsx"


def normalize(text: str) -> str:
    if not text or str(text).strip() in ["", "nan", "None"]:
        return ""
    text = str(text).lower().strip()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def is_match(predicted: str, correct: str) -> bool:
    p = normalize(predicted)
    c = normalize(correct)
    if not p or not c:
        return False
    if p == c:
        return True
    if c in p or p in c:
        return True
    return False


def main():
    # ── Load resolved questions ───────────────────────────────────────────────
    print("Loading resolved questions...")
    resolved = pd.read_excel(RESOLVED_FILE)
    resolved = resolved[resolved["correct_answer"].notna()].copy()
    resolved = resolved[resolved["correct_answer"].astype(str).str.strip() != ""]
    print(f"  Total with verified outcomes: {len(resolved)}")

    # Separate binary and multi-choice for reporting
    binary = resolved[resolved["is_binary"] == "Yes"]
    multi  = resolved[resolved["is_binary"] == "No"]
    print(f"  Binary: {len(binary)}, Multi-choice: {len(multi)}")

    resolved["q_norm"] = resolved["question_text"].astype(str).apply(normalize)

    # ── Load single-model results ─────────────────────────────────────────────
    print("Loading single-model results...")
    single = pd.read_csv(SINGLE_FILE)
    single["q_norm"] = single["question"].astype(str).apply(normalize)
    print(f"  Rows: {len(single)}")

    # ── Load council results ──────────────────────────────────────────────────
    print("Loading council results...")
    council = pd.read_excel(COUNCIL_FILE)
    council["q_norm"] = council["question_text"].astype(str).apply(normalize)
    print(f"  Rows: {len(council)}")

    # ── Build comparison ──────────────────────────────────────────────────────
    rows = []

    for _, res_row in resolved.iterrows():
        q_norm   = res_row["q_norm"]
        q_text   = res_row["question_text"]
        correct  = str(res_row["correct_answer"]).strip()
        is_bin   = res_row.get("is_binary", "")

        # Single-model rows
        single_q = single[single["q_norm"] == q_norm]
        for _, s_row in single_q.iterrows():
            model_name = s_row.get("model", "")
            predicted  = str(s_row.get("answer", "")).strip()
            rows.append({
                "question":       q_text,
                "correct_answer": correct,
                "is_binary":      is_bin,
                "setup":          f"Single — {model_name}",
                "model":          model_name,
                "chairman":       None,
                "predicted":      predicted,
                "correct":        is_match(predicted, correct),
                "judge_score":    s_row.get("score", None),
            })

        # Council rows
        council_q = council[council["q_norm"] == q_norm]
        for _, c_row in council_q.iterrows():
            chairman  = str(c_row.get("chairman_model", "")).strip()
            predicted = str(c_row.get("council_answer", "")).strip()
            rows.append({
                "question":       q_text,
                "correct_answer": correct,
                "is_binary":      is_bin,
                "setup":          f"Council — chairman={chairman}",
                "model":          "council",
                "chairman":       chairman,
                "predicted":      predicted,
                "correct":        is_match(predicted, correct),
                "judge_score":    c_row.get("judge_overall", None),
            })

    comparison = pd.DataFrame(rows)
    print(f"\nTotal comparison rows: {len(comparison)}")
    print(f"Questions matched: {comparison['question'].nunique()}")

    comparison.to_excel(OUTPUT_FILE, index=False)

    # ── Summary ───────────────────────────────────────────────────────────────
    summary_rows = []
    for setup, g in comparison.groupby("setup"):
        n         = len(g)
        n_correct = g["correct"].sum()
        accuracy  = round(n_correct / n * 100, 2) if n > 0 else 0
        mean_judge = round(g["judge_score"].dropna().astype(float).mean(), 3) if g["judge_score"].notna().any() else None
        n_binary  = len(g[g["is_binary"] == "Yes"])
        summary_rows.append({
            "setup":            setup,
            "n_questions":      n,
            "n_binary":         n_binary,
            "correct":          int(n_correct),
            "accuracy_%":       accuracy,
            "mean_judge_score": mean_judge,
        })

    summary = pd.DataFrame(summary_rows).sort_values("accuracy_%", ascending=False)
    summary.to_excel(SUMMARY_FILE, index=False)

    print(f"\n=== ACCURACY SUMMARY ===")
    print(summary.to_string(index=False))
    print(f"\nSaved to: {OUTPUT_FILE}, {SUMMARY_FILE}")


if __name__ == "__main__":
    main()