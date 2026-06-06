import ast
import json
import re
import statistics
from pathlib import Path

import ollama
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
INPUT_FILE = BASE_DIR / "LLM_Council_Final_Results copy.txt"
COUNCIL_RESULTS_FILE = BASE_DIR / "council_judged_results.csv"
COUNCIL_SUMMARY_FILE = BASE_DIR / "council_judged_summary.csv"

START_INDEX = 0
END_INDEX = None

# Council chairmen
CHAIRMEN = {
    "Llama": "llama3.1:latest",
    "Mistral": "mistral:latest",
}

# Pick how you want to judge the final council answers.
JUDGE_MODEL = "llama3.1:latest"


def call_model(model, system, user):
    response = ollama.chat(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        options={"temperature": 0},
    )
    return response["message"]["content"].strip()


def parse_fullresults(text):
    pattern = re.compile(
        r"Question\s+(\d+):\s*(.*?)\nResponses:\s*(\[[\s\S]*?\])\nRankings:",
        re.MULTILINE,
    )

    rows = []
    for match in pattern.finditer(text):
        q_num = int(match.group(1))
        question = match.group(2).strip()
        responses_raw = match.group(3).strip()

        try:
            responses = ast.literal_eval(responses_raw)
        except Exception as e:
            print(f"Skipping question {q_num}: could not parse responses: {e}")
            continue

        parsed_responses = []
        for item in responses:
            model_name = str(item.get("model", "")).strip()
            answer = str(item.get("response", "")).strip()
            if model_name and answer:
                parsed_responses.append({
                    "model": model_name,
                    "response": answer,
                })

        if parsed_responses:
            rows.append({
                "question_number": q_num,
                "question": question,
                "responses": parsed_responses,
            })

    return rows


def build_council_answer(question, responses, chairman_model):
    candidate_text = "\n\n".join(
        f"{i}. Model: {r['model']}\nAnswer: {r['response']}"
        for i, r in enumerate(responses, start=1)
    )

    system = """
You are the chairman of an AI council.

You will be given a question and several candidate answers from different models.

Your task:
- compare all answers carefully
- keep the strongest correct parts
- discard weak, irrelevant, or clearly incorrect claims
- synthesize one best final answer

Rules:
- answer the original question directly
- be concise but complete
- do not mention the models
- do not mention that this is a council synthesis
- output only the final answer
""".strip()

    user = f"""Question:
{question}

Candidate answers:
{candidate_text}

Produce the single best final answer.
"""

    return call_model(chairman_model, system, user)


def judge_answer(question, answer, judge_model):
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

    user = f"""Question:
{question}

Answer:
{answer}
"""

    output = call_model(judge_model, system, user)

    try:
        parsed = json.loads(output)
        score = int(parsed["score"])
        reason = str(parsed.get("reason", "")).strip()
        score = max(1, min(5, score))
        return score, reason, output
    except Exception:
        return 1, "Failed to parse judge output.", output


def write_progress(results):
    results_df = pd.DataFrame(results)
    results_df.to_csv(COUNCIL_RESULTS_FILE, index=False)

    summary_rows = []
    for chairman_name in CHAIRMEN:
        scores = results_df[results_df["chairman"] == chairman_name]["score"].tolist()

        mean_score = round(statistics.mean(scores), 2) if scores else 0
        std_score = round(statistics.pstdev(scores), 2) if len(scores) > 1 else 0.0
        count = len(scores)

        summary_rows.append({
            "Model": chairman_name,
            "Council Mean/Std": f"{mean_score} ± {std_score} (N={count})",
            "Mean": mean_score,
            "Std": std_score,
            "Count": count,
        })

    summary_df = pd.DataFrame(summary_rows)
    summary_df.to_csv(COUNCIL_SUMMARY_FILE, index=False)


def main():
    print("Reading:", INPUT_FILE)
    text = INPUT_FILE.read_text(encoding="utf-8")
    data = parse_fullresults(text)

    data = data[START_INDEX:END_INDEX]

    if not data:
        print("No questions parsed.")
        return

    print(f"Parsed {len(data)} questions")

    results = []

    # Optional: clear old files at the start
    if COUNCIL_RESULTS_FILE.exists():
        COUNCIL_RESULTS_FILE.unlink()
    if COUNCIL_SUMMARY_FILE.exists():
        COUNCIL_SUMMARY_FILE.unlink()

    for idx, item in enumerate(data, start=1):
        q_num = item["question_number"]
        question = item["question"]
        responses = item["responses"]

        print(f"[{idx}/{len(data)}] Question {q_num}")

        for chairman_name, chairman_model in CHAIRMEN.items():
            print(f"  Building council answer with CHAIRMAN={chairman_name}")
            council_answer = build_council_answer(question, responses, chairman_model)

            print(f"  Judging council answer for CHAIRMAN={chairman_name}")
            score, reason, raw = judge_answer(question, council_answer, JUDGE_MODEL)

            row = {
                "question_number": q_num,
                "question": question,
                "chairman": chairman_name,
                "chairman_model": chairman_model,
                "judge_model": JUDGE_MODEL,
                "source_models": ", ".join(r["model"] for r in responses),
                "council_answer": council_answer,
                "score": score,
                "reason": reason,
                "judge_raw": raw,
            }

            results.append(row)

            # Save after every judged result
            write_progress(results)

            print(
                f"    Saved progress: q={q_num}, chairman={chairman_name}, score={score}"
            )

    print("\nDone.")
    print("Detailed results:", COUNCIL_RESULTS_FILE)
    print("Summary:", COUNCIL_SUMMARY_FILE)

    results_df = pd.DataFrame(results)
    summary_rows = []
    for chairman_name in CHAIRMEN:
        scores = results_df[results_df["chairman"] == chairman_name]["score"].tolist()
        mean_score = round(statistics.mean(scores), 2) if scores else 0
        std_score = round(statistics.pstdev(scores), 2) if len(scores) > 1 else 0.0
        count = len(scores)

        summary_rows.append({
            "Model": chairman_name,
            "Council Mean/Std": f"{mean_score} ± {std_score} (N={count})",
        })

    summary_df = pd.DataFrame(summary_rows)
    print()
    print(summary_df.to_string(index=False))


if __name__ == "__main__":
    main() 