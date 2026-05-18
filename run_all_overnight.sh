#!/bin/bash
# run_all_overnight.sh
# Just run:  bash run_all_overnight.sh
# Then leave your laptop plugged in overnight.
# It will process all 1500 questions in batches of 20.
# If it crashes or you stop it, just re-run — already-done questions are skipped.

INPUT="CS180_DataCollection_1500.xlsx"
OUT_PREFIX="council_run1"
BATCH=20
TOTAL=1500

echo "Starting overnight run at $(date)"
echo "Total questions: $TOTAL, batch size: $BATCH"
echo ""

for START in $(seq 0 $BATCH $((TOTAL - 1))); do
    echo "===== Batch start-row=$START at $(date) ====="
    python ollama_council_batch_v2.py \
      --input "$INPUT" \
      --out-prefix "$OUT_PREFIX" \
      --start-row $START \
      --limit $BATCH \
      --answer-models llama3.1:8b mistral \
      --chairman-models llama3.1:8b mistral \
      --judge-model llama3.1:8b
    echo "Batch done. Resting 10 seconds..."
    sleep 10
done

echo ""
echo "ALL DONE at $(date)"
echo "Results saved to: ${OUT_PREFIX}_detailed.xlsx and ${OUT_PREFIX}_summary.xlsx"
