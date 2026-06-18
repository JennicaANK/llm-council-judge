"""
compare_predictions.py
----------------------
Compares single-model and council predictions against real Polymarket outcomes.

Requires:
  - CS180_DataCollection_resolved.xlsx   (questions with correct_answer filled in)
  - single_llm_results.csv              (single-model answers: Llama, Mistral, QWEN)
  - council_run2_detailed.xlsx          (2-model council: Llama + Mistral)
  - council_run3_detailed.xlsx          (3-model council: Llama + Mistral + QWEN)

Output:
  - comparison_results.xlsx             (full comparison table)
  - comparison_summary.xlsx            (accuracy per model/setup)
"""

import re
import pandas as pd
from pathlib import Path

RESOLVED_FILE  = "CS180_DataCollection_resolved.xlsx"
SINGLE_FILE    = "single_llm_results.csv"
COUNCIL_FILES  = [
    ("council_run2_detailed.xlsx", "2-model council"),
    ("council_run3_detailed.xlsx", "3-model council"),
]
OUTPUT_FILE    = "comparison_results.xlsx"
SUMMARY_FILE   = "comparison_summary.xlsx"


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

    binary_types = ["(Yes, No)", "(No, Yes)", "(Over, Under)", "(Under, Over)"]
    resolved = resolved[resolved["answer_type"].astype(str).str.strip().isin(binary_types)]
    print(f"  Questions with verified binary outcomes: {len(resolved)}")
    resolved["q_norm"] = resolved["question_text"].astype(str).apply(normalize)

    # ── Load single-model results ─────────────────────────────────────────────
    print("Loading single-model results...")
    single = pd.read_csv(SINGLE_FILE)
    single["q_norm"] = single["question"].astype(str).apply(normalize)
    print(f"  Single-model rows: {len(single)}")

    # ── Load all council results ──────────────────────────────────────────────
    council_frames = []
    for fname, label in COUNCIL_FILES:
        if Path(fname).exists():
            df = pd.read_excel(fname)
            df["council_run"] = label
            df["q_norm"] = df["question_text"].astype(str).apply(normalize)
            council_frames.append(df)
            print(f"  Loaded {fname}: {len(df)} rows")
        else:
            print(f"  Skipping {fname} (not found)")

    council = pd.concat(council_frames, ignore_index=True) if council_frames else pd.DataFrame()

    # ── Build comparison table ────────────────────────────────────────────────
    rows = []

    for _, res_row in resolved.iterrows():
        q_norm  = res_row["q_norm"]
        q_text  = res_row["question_text"]
        correct = str(res_row["correct_answer"]).strip()

        # Single-model rows
        single_q = single[single["q_norm"] == q_norm]
        for _, s_row in single_q.iterrows():
            model_name = s_row.get("model", "")
            predicted  = str(s_row.get("answer", "")).strip()
            rows.append({
                "question":         q_text,
                "correct_answer":   correct,
                "setup":            f"Single — {model_name}",
                "model":            model_name,
                "chairman":         None,
                "council_run":      None,
                "predicted":        predicted,
                "correct":          is_match(predicted, correct),
                "judge_score":      s_row.get("score", None),
            })

        # Council rows
        if not council.empty:
            council_q = council[council["q_norm"] == q_norm]
            for _, c_row in council_q.iterrows():
                chairman  = str(c_row.get("chairman_model", "")).strip()
                predicted = str(c_row.get("council_answer", "")).strip()
                run_label = c_row.get("council_run", "")
                rows.append({
                    "question":         q_text,
                    "correct_answer":   correct,
                    "setup":            f"Council ({run_label}) — chairman={chairman}",
                    "model":            "council",
                    "chairman":         chairman,
                    "council_run":      run_label,
                    "predicted":        predicted,
                    "correct":          is_match(predicted, correct),
                    "judge_score":      c_row.get("judge_overall", None),
                })

    comparison = pd.DataFrame(rows)
    print(f"\nTotal comparison rows: {len(comparison)}")
    print(f"Questions matched: {comparison['question'].nunique()}")

    comparison.to_excel(OUTPUT_FILE, index=False)
    print(f"Saved full comparison to: {OUTPUT_FILE}")

    # ── Summary ───────────────────────────────────────────────────────────────
    summary_rows = []
    for setup, g in comparison.groupby("setup"):
        n          = len(g)
        n_correct  = g["correct"].sum()
        accuracy   = round(n_correct / n * 100, 2) if n > 0 else 0
        mean_judge = round(g["judge_score"].dropna().astype(float).mean(), 3) if g["judge_score"].notna().any() else None
        summary_rows.append({
            "setup":            setup,
            "n_questions":      n,
            "correct":          int(n_correct),
            "accuracy_%":       accuracy,
            "mean_judge_score": mean_judge,
        })

    summary = pd.DataFrame(summary_rows).sort_values("accuracy_%", ascending=False)
    summary.to_excel(SUMMARY_FILE, index=False)

    print(f"\n=== ACCURACY SUMMARY ===")
    print(summary.to_string(index=False))
    print(f"\nSaved summary to: {SUMMARY_FILE}")


if __name__ == "__main__":
    main()