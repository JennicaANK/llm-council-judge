"""
rescore_predictions.py
----------------------
Re-scores saved single-model and council predictions against real Polymarket
outcomes. Replaces the substring-based is_match() in compare_predictions.py and
compare_predictions_v2.py, which counted answers like "not likely" or
"I don't know" as correct whenever the true answer was "No" (because "no" is a
substring of "not" and "know").

What this script does differently:
  1. Extracts ONE label per answer (yes/no, over/under, or a named option) from
     the answer line only, using whole-word matching. Anything else is marked
     unparseable / ambiguous / refusal / error instead of being fuzzy-matched.
  2. Strips <think>...</think> blocks (DeepSeek R1, QWEN 3) before parsing.
  3. Drops council error rows (chairman_model is empty) instead of keeping them
     as a "chairman=nan" setup.
  4. Drops questions whose text appears more than once in the resolved file,
     since matching is done by question text and duplicates can't be mapped.
  5. Reports, per setup: accuracy (unparseable = wrong), parse rate, accuracy on
     parsed answers only, refusal rate, binary-only accuracy, and a 95% Wilson
     confidence interval.
  6. Reports trivial baselines (always "No", always "Yes", always "Under",
     always "Over") so model accuracy can be compared against them.
  7. Runs paired McNemar tests between setups, since every setup answered the
     same questions.

Usage (run in the folder that has the result files):
  python3 rescore_predictions.py --dataset old
  python3 rescore_predictions.py --dataset new

Outputs (prefix rescored_old_ or rescored_new_):
  *_rows.xlsx      one row per (question, setup) with extracted label + status
  *_summary.xlsx   accuracy table per setup
  *_baselines.xlsx trivial baselines
  *_pairwise.xlsx  McNemar tests between setups
"""

import argparse
import math
import re
from itertools import combinations
from pathlib import Path

import pandas as pd

CONFIGS = {
    "old": {
        "resolved": "CS180_DataCollection_resolved.xlsx",
        "single": "single_llm_results.csv",
        "council": [
            ("council_run2_detailed.xlsx", "2-model council"),
            ("council_run3_detailed.xlsx", "3-model council"),
        ],
        # In the old dataset, multi-choice outcomes were fetched incorrectly,
        # so only these answer types have trustworthy ground truth.
        "binary_only_types": ["(Yes, No)", "(No, Yes)", "(Over, Under)", "(Under, Over)"],
        "out_prefix": "rescored_old",
    },
    "new": {
        "resolved": "new_questions_resolved.xlsx",
        "single": "new_single_llm_results.csv",
        "council": [("new_council_detailed.xlsx", "6-model council")],
        "binary_only_types": None,
        "out_prefix": "rescored_new",
    },
}

REFUSAL_RE = re.compile(
    r"\b(i cannot|i can ?not|i cant|i am unable|i m unable|unable to (predict|provide|determine|answer|know)"
    r"|i do ?nt have (access|real ?time)|i do not have (access|real ?time)|as an ai"
    r"|cannot (predict|determine|know)|i do ?nt know|i do not know|impossible to (predict|know|say))\b"
)
THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
ANSWER_LINE_RE = re.compile(
    r"(?:council answer|predicted answer|final answer|answer)\s*[:\-]\s*(.+)", re.IGNORECASE
)


# ── Text helpers ──────────────────────────────────────────────────────────────

def is_blank(x) -> bool:
    return x is None or (isinstance(x, float) and math.isnan(x)) or str(x).strip() in ("", "nan", "None")


def norm(x) -> str:
    if is_blank(x):
        return ""
    t = str(x).lower()
    t = t.replace("’", "'").replace("'", "")       # don't -> dont, can't -> cant
    t = re.sub(r"[^\w\s]", " ", t)                  # punctuation -> space (keeps word boundaries)
    return re.sub(r"\s+", " ", t).strip()


def strip_think(x) -> str:
    return "" if is_blank(x) else THINK_RE.sub(" ", str(x)).strip()


def answer_span(raw: str) -> str:
    """The part of the response that states the answer: the 'Answer:' line if
    there is one, otherwise the first sentence."""
    m = ANSWER_LINE_RE.search(raw)
    if m:
        return m.group(1).splitlines()[0]
    return re.split(r"(?<=[.!?])\s|\n", raw.strip(), maxsplit=1)[0]


def parse_options(answer_type, correct) -> list:
    """Options from answer_type like '(Yes, No)' or '(Mbappe, Kane)'."""
    opts = []
    if not is_blank(answer_type):
        inner = str(answer_type).strip().strip("()[]")
        opts = [norm(o) for o in inner.split(",") if norm(o)]
    c = norm(correct)
    if not opts:
        if c in ("yes", "no"):
            opts = ["yes", "no"]
        elif c in ("over", "under"):
            opts = ["over", "under"]
    if c and c not in opts:
        opts.append(c)  # counted in the summary as an options mismatch
    return opts


def extract_label(text, options, strict=False, question=""):
    """Return (label, status). status is one of:
    ok, ambiguous, refusal, unparseable, error, empty, no_options.

    strict=True is used for single-model answers, which are free-form
    paragraphs with no 'Answer:' line. In strict mode a label is accepted ONLY
    if the answer opens with an option ("No, ...", "Yes.", "Over ..."), and the
    first sentence is not a refusal. Words like "no" in the middle of a
    sentence ("there is no public information") are never used as a label.
    Spread questions in strict mode count only if the answer is exactly an
    option name, because models mostly just explained the spread line."""
    if is_blank(text):
        return None, "empty"
    raw = strip_think(text)
    if not raw or raw.upper().startswith("ERROR"):
        return None, "error"
    if not options:
        return None, "no_options"

    if strict:
        span = norm(answer_span(raw))
        if REFUSAL_RE.search(span):
            return None, "refusal"
        if "spread" in norm(question):
            return (span, "ok") if span in options else (None, "unparseable")
        for o in sorted(options, key=len, reverse=True):
            if span == o or span.startswith(o + " "):
                return o, "ok"
        if REFUSAL_RE.search(norm(raw)):
            return None, "refusal"
        return None, "unparseable"

    span = norm(answer_span(raw))
    # 1) answer line starts with an option ("No, because ...")
    for o in sorted(options, key=len, reverse=True):
        if span == o or span.startswith(o + " "):
            return o, "ok"
    # 2) exactly one option appears as a whole word in the answer line
    hits = [o for o in options if re.search(rf"\b{re.escape(o)}\b", span)]
    if len(hits) == 1:
        return hits[0], "ok"
    if len(hits) > 1:
        return None, "ambiguous"
    if REFUSAL_RE.search(norm(raw)):
        return None, "refusal"
    return None, "unparseable"


# ── Stats helpers ─────────────────────────────────────────────────────────────

def wilson_ci(k: int, n: int, z: float = 1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (round(100 * (center - half), 2), round(100 * (center + half), 2))


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact McNemar p-value on discordant counts b and c."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


# ── Loading ───────────────────────────────────────────────────────────────────

def load_resolved(cfg):
    df = pd.read_excel(cfg["resolved"])
    df = df[~df["correct_answer"].apply(is_blank)].copy()
    if cfg["binary_only_types"]:
        df = df[df["answer_type"].astype(str).str.strip().isin(cfg["binary_only_types"])]
    df["q_norm"] = df["question_text"].apply(norm)

    dup_mask = df.duplicated("q_norm", keep=False)
    n_dup = int(dup_mask.sum())
    df = df[~dup_mask].copy()

    answer_type_col = df["answer_type"] if "answer_type" in df.columns else pd.Series([None] * len(df), index=df.index)
    df["options"] = [parse_options(a, c) for a, c in zip(answer_type_col, df["correct_answer"])]
    df["correct_label"] = df["correct_answer"].apply(norm)
    df["is_binary_q"] = df["options"].apply(lambda o: set(o) in ({"yes", "no"}, {"over", "under"}))
    return df, n_dup


def load_predictions(cfg):
    frames = []

    single = pd.read_csv(cfg["single"])
    frames.append(pd.DataFrame({
        "q_norm": single["question"].apply(norm),
        "setup": "Single — " + single["model"].astype(str),
        "prediction_raw": single["answer"],
        "judge_score": pd.to_numeric(single.get("score"), errors="coerce"),
        "judge_rubric": "single (correctness/completeness/clarity/usefulness)",
    }))

    n_error_rows = 0
    for fname, label in cfg["council"]:
        if not Path(fname).exists():
            print(f"  Skipping {fname} (not found)")
            continue
        c = pd.read_excel(fname)
        err = c["chairman_model"].apply(is_blank)
        n_error_rows += int(err.sum())
        c = c[~err].copy()
        c["q_norm"] = c["question_text"].apply(norm)
        # if a (question, chairman) pair was saved twice, keep the last one
        c = c.drop_duplicates(["q_norm", "chairman_model"], keep="last")
        frames.append(pd.DataFrame({
            "q_norm": c["q_norm"],
            "setup": f"Council ({label}) — chairman=" + c["chairman_model"].astype(str),
            "prediction_raw": c["council_answer"],
            "judge_score": pd.to_numeric(c.get("judge_overall"), errors="coerce"),
            "judge_rubric": "council (clarity/reasoning/relevance/overall)",
        }))

    preds = pd.concat(frames, ignore_index=True)
    # one row per (question, setup); repeated question text in the input would
    # otherwise be counted twice
    preds = preds.drop_duplicates(["q_norm", "setup"], keep="last")
    return preds, n_error_rows


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", choices=["old", "new"], required=True)
    ap.add_argument("--examples", type=int, default=3,
                    help="How many unparseable examples to print per setup")
    args = ap.parse_args()
    cfg = CONFIGS[args.dataset]
    prefix = cfg["out_prefix"]

    print(f"=== Rescoring the {args.dataset} dataset ===")
    resolved, n_dup = load_resolved(cfg)
    print(f"Resolved questions used: {len(resolved)}  (dropped {n_dup} rows with duplicate question text)")
    n_mismatch = int(sum(norm(c) not in parse_options(a, None)
                         for a, c in zip(resolved.get("answer_type", [None] * len(resolved)),
                                         resolved["correct_answer"])
                         if not is_blank(a)))
    if n_mismatch:
        print(f"  Note: {n_mismatch} questions have a correct_answer that is not in their answer_type options")

    preds, n_err = load_predictions(cfg)
    print(f"Dropped {n_err} council error rows (no chairman_model)")

    rows = preds.merge(resolved[["q_norm", "question_text", "correct_label", "options", "is_binary_q"]],
                       on="q_norm", how="inner")
    labels = [extract_label(p, o, strict=s.startswith("Single"), question=q)
              for p, o, s, q in zip(rows["prediction_raw"], rows["options"], rows["setup"], rows["question_text"])]
    rows["predicted_label"] = [l for l, _ in labels]
    rows["parse_status"] = [s for _, s in labels]
    rows["correct"] = rows["predicted_label"] == rows["correct_label"]

    # ── per-setup summary ──
    summary = []
    for setup, g in rows.groupby("setup"):
        n = len(g)
        k = int(g["correct"].sum())
        parsed = g[g["parse_status"] == "ok"]
        gb = g[g["is_binary_q"]]
        lo, hi = wilson_ci(k, n)
        summary.append({
            "setup": setup,
            "n_questions": n,
            "correct": k,
            "accuracy_%": round(100 * k / n, 2) if n else None,
            "ci95_low": lo,
            "ci95_high": hi,
            "parse_rate_%": round(100 * len(parsed) / n, 2) if n else None,
            "accuracy_on_parsed_%": round(100 * parsed["correct"].mean(), 2) if len(parsed) else None,
            "refusal_rate_%": round(100 * (g["parse_status"] == "refusal").mean(), 2),
            "ambiguous_rate_%": round(100 * (g["parse_status"] == "ambiguous").mean(), 2),
            "n_binary": len(gb),
            "binary_accuracy_%": round(100 * gb["correct"].mean(), 2) if len(gb) else None,
            "mean_judge_score": round(g["judge_score"].mean(), 3) if g["judge_score"].notna().any() else None,
            "judge_rubric": g["judge_rubric"].iloc[0],
        })
    summary = pd.DataFrame(summary).sort_values("accuracy_%", ascending=False)

    # ── baselines ──
    baselines = []
    yn = resolved[resolved["options"].apply(lambda o: set(o) == {"yes", "no"})]
    ou = resolved[resolved["options"].apply(lambda o: set(o) == {"over", "under"})]
    for name, subset, label in [("Always 'No' (Yes/No questions)", yn, "no"),
                                ("Always 'Yes' (Yes/No questions)", yn, "yes"),
                                ("Always 'Under' (Over/Under questions)", ou, "under"),
                                ("Always 'Over' (Over/Under questions)", ou, "over")]:
        if len(subset):
            k = int((subset["correct_label"] == label).sum())
            lo, hi = wilson_ci(k, len(subset))
            baselines.append({"baseline": name, "n_questions": len(subset), "correct": k,
                              "accuracy_%": round(100 * k / len(subset), 2), "ci95_low": lo, "ci95_high": hi})
    binary_q = resolved[resolved["is_binary_q"]]
    if len(binary_q):
        k = int(binary_q["correct_label"].isin(["no", "under"]).sum())
        baselines.append({"baseline": "Always 'No'/'Under' (all binary questions)", "n_questions": len(binary_q),
                          "correct": k, "accuracy_%": round(100 * k / len(binary_q), 2),
                          "ci95_low": wilson_ci(k, len(binary_q))[0], "ci95_high": wilson_ci(k, len(binary_q))[1]})
    baselines = pd.DataFrame(baselines)

    # ── paired McNemar tests ──
    wide = rows.pivot_table(index="q_norm", columns="setup", values="correct", aggfunc="first")
    pairwise = []
    for a, b in combinations(wide.columns, 2):
        both = wide[[a, b]].dropna()
        if both.empty:
            continue
        x, y = both[a].astype(bool), both[b].astype(bool)
        only_a, only_b = int((x & ~y).sum()), int((~x & y).sum())
        pairwise.append({
            "setup_A": a, "setup_B": b, "n_shared": len(both),
            "acc_A_%": round(100 * x.mean(), 2), "acc_B_%": round(100 * y.mean(), 2),
            "A_right_B_wrong": only_a, "B_right_A_wrong": only_b,
            "mcnemar_p": round(mcnemar_exact(only_a, only_b), 4),
        })
    pairwise = pd.DataFrame(pairwise).sort_values("mcnemar_p") if pairwise else pd.DataFrame()

    # ── save + print ──
    rows.drop(columns=["options"]).to_excel(f"{prefix}_rows.xlsx", index=False)
    summary.to_excel(f"{prefix}_summary.xlsx", index=False)
    baselines.to_excel(f"{prefix}_baselines.xlsx", index=False)
    pairwise.to_excel(f"{prefix}_pairwise.xlsx", index=False)

    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 30)
    print("\n=== ACCURACY (unparseable answers count as wrong) ===")
    print(summary[["setup", "n_questions", "accuracy_%", "ci95_low", "ci95_high", "parse_rate_%",
                   "accuracy_on_parsed_%", "refusal_rate_%", "binary_accuracy_%", "mean_judge_score"]]
          .to_string(index=False))
    print("\n=== TRIVIAL BASELINES ===")
    print(baselines.to_string(index=False) if len(baselines) else "(none)")
    if len(pairwise):
        print("\n=== PAIRED McNEMAR TESTS (smallest p first) ===")
        print(pairwise.head(15).to_string(index=False))

    print("\n=== PARSE STATUS COUNTS ===")
    print(rows.pivot_table(index="setup", columns="parse_status", values="q_norm", aggfunc="count", fill_value=0)
          .to_string())

    if args.examples:
        print(f"\n=== UP TO {args.examples} NON-PARSED EXAMPLES PER SETUP (check these by eye) ===")
        for setup, g in rows[rows["parse_status"] != "ok"].groupby("setup"):
            print(f"\n-- {setup}")
            for _, r in g.head(args.examples).iterrows():
                snippet = re.sub(r"\s+", " ", strip_think(r["prediction_raw"]))[:160]
                print(f"   [{r['parse_status']}] correct={r['correct_label']!r}  answer={snippet!r}")

    print("\nNote: single-model and council judge scores come from different rubrics, "
          "so they should not be compared to each other directly.")
    print(f"\nSaved: {prefix}_rows.xlsx, {prefix}_summary.xlsx, {prefix}_baselines.xlsx, {prefix}_pairwise.xlsx")


if __name__ == "__main__":
    main()
