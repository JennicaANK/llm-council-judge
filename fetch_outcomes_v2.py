"""
fetch_outcomes_v2.py
--------------------
Fetches resolved outcomes for the NEW 2,000 question dataset.

Improvements over v1:
  - Uses market_id (saved in DataCollection_v2.py) for direct market lookup
  - Properly handles multi-choice questions by matching outcome prices
  - Works for both binary (Yes/No) and multi-choice (e.g. Mbappe vs Kane)

Usage:
    python3 fetch_outcomes_v2.py

Output:
    new_questions_resolved.xlsx   - same as input with correct_answer filled in
    fetch_outcomes_v2_log.txt     - log of what was found / skipped
"""

import re
import time
import requests
import pandas as pd
from pathlib import Path

INPUT_FILE  = "new_questions.xlsx"
OUTPUT_FILE = "new_questions_resolved.xlsx"
LOG_FILE    = "fetch_outcomes_v2_log.txt"

GAMMA_MARKETS_URL = "https://gamma-api.polymarket.com/markets"
GAMMA_EVENTS_URL  = "https://gamma-api.polymarket.com/events"
SLEEP_S = 0.3


def fetch_market_by_id(market_id: str) -> dict:
    """Fetch a single market directly by its ID."""
    try:
        r = requests.get(f"{GAMMA_MARKETS_URL}/{market_id}", timeout=15)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return {}


def fetch_event_by_slug(slug: str) -> dict:
    """Fallback: fetch event by slug."""
    try:
        r = requests.get(GAMMA_EVENTS_URL, params={"slug": slug}, timeout=15)
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list) and data:
                return data[0]
    except Exception:
        pass
    return {}


def extract_slug(link: str) -> str:
    if not link or str(link).strip() == "":
        return ""
    link = str(link).split("#")[0].rstrip("/")
    match = re.search(r"/event/([^/?#]+)", link)
    return match.group(1) if match else ""


def get_winner_from_market(market: dict) -> str:
    """
    Given a market dict, find the winning outcome.
    Returns the outcome label (e.g. 'Yes', 'No', 'Mbappe', 'Kane') or empty string.
    """
    if not market:
        return ""

    # Must be closed to have a resolved outcome
    if not market.get("closed", False):
        return ""

    outcomes_raw = market.get("outcomes", "[]")
    prices_raw   = market.get("outcomePrices", "[]")

    try:
        import json
        outcomes = json.loads(outcomes_raw) if isinstance(outcomes_raw, str) else list(outcomes_raw)
        prices   = json.loads(prices_raw)   if isinstance(prices_raw, str)   else list(prices_raw)
        prices   = [float(p) for p in prices]
    except Exception:
        return ""

    if not outcomes or not prices or len(outcomes) != len(prices):
        return ""

    max_price = max(prices)
    if max_price < 0.95:
        return ""  # not clearly resolved

    winner_idx = prices.index(max_price)
    return str(outcomes[winner_idx])


def get_winner_from_event(event: dict, question_text: str) -> str:
    """
    Fallback: search through event markets to find the resolved one.
    For multi-choice events structured as multiple binary sub-markets,
    find the sub-market that resolved 'Yes' and return its question text
    stripped to just the option name.
    """
    markets = event.get("markets", [])
    if not markets:
        return ""

    q_lower = str(question_text).lower().strip()

    # First try: find market whose question matches directly
    for m in markets:
        if not m.get("closed", False):
            continue
        winner = get_winner_from_market(m)
        mq = str(m.get("question", "")).lower()
        if mq and (mq in q_lower or q_lower in mq):
            return winner

    # Second try: for events with multiple binary sub-markets (e.g. "Will Mbappe score more?")
    # find the one that resolved 'Yes' and extract the option name from its question
    for m in markets:
        if not m.get("closed", False):
            continue
        winner = get_winner_from_market(m)
        if winner.lower() == "yes":
            # Try to extract the key noun from the sub-market question
            mq = str(m.get("question", ""))
            # Strip common prefixes
            for prefix in ["Will ", "Does ", "Is ", "Did ", "Has "]:
                if mq.startswith(prefix):
                    mq = mq[len(prefix):]
                    break
            # Return first word/phrase as the winner (e.g. "Mbappe score more?" -> "Mbappe")
            first_word = mq.split()[0].rstrip("?.,") if mq else ""
            if first_word:
                return first_word

    # Third try: just return winner from first closed market
    for m in markets:
        if m.get("closed", False):
            winner = get_winner_from_market(m)
            if winner:
                return winner

    return ""


def main():
    print(f"Reading {INPUT_FILE}...")
    df = pd.read_excel(INPUT_FILE)
    print(f"Loaded {len(df)} rows")
    print(f"Binary: {(df['is_binary'] == 'Yes').sum()}, Multi-choice: {(df['is_binary'] == 'No').sum()}")

    log_lines = []
    resolved_count  = 0
    not_resolved    = 0
    already_count   = 0

    for i, row in df.iterrows():
        qid       = row.get("id", i + 1)
        market_id = str(row.get("market_id", "")).strip()
        link      = str(row.get("question_link", "")).strip()
        q_text    = str(row.get("question_text", "")).strip()
        is_binary = str(row.get("is_binary", "")).strip()

        # Skip if already resolved
        existing = row.get("correct_answer", "")
        if pd.notna(existing) and str(existing).strip() not in ["", "nan"]:
            already_count += 1
            continue

        winner = ""

        # Try direct market lookup first (we have market_id in v2 dataset)
        if market_id and market_id != "nan":
            market = fetch_market_by_id(market_id)
            winner = get_winner_from_market(market)
            time.sleep(SLEEP_S)

        # Fallback to event slug lookup
        if not winner:
            slug = extract_slug(link)
            if slug:
                event = fetch_event_by_slug(slug)
                winner = get_winner_from_event(event, q_text)
                time.sleep(SLEEP_S)

        if winner:
            df.at[i, "correct_answer"] = winner
            msg = f"[{qid}] ✅ [{is_binary}] {q_text[:60]} → {winner}"
            resolved_count += 1
        else:
            msg = f"[{qid}] ⚠️  Not resolved: {q_text[:60]}"
            not_resolved += 1

        log_lines.append(msg)

        if (i + 1) % 100 == 0:
            print(f"  Processed {i+1}/{len(df)} — resolved: {resolved_count}")

    df.to_excel(OUTPUT_FILE, index=False)
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(log_lines))

    print(f"\n=== DONE ===")
    print(f"Total rows:        {len(df)}")
    print(f"Resolved:          {resolved_count}")
    print(f"Already had answer:{already_count}")
    print(f"Not resolved yet:  {not_resolved}")
    print(f"Saved to:          {OUTPUT_FILE}")
    print(f"Log:               {LOG_FILE}")

    # Quick breakdown
    resolved_df = df[df["correct_answer"].notna() & (df["correct_answer"].astype(str).str.strip() != "")]
    binary_resolved = resolved_df[resolved_df["is_binary"] == "Yes"]
    multi_resolved  = resolved_df[resolved_df["is_binary"] == "No"]
    print(f"\nBinary resolved:     {len(binary_resolved)}")
    print(f"Multi-choice resolved:{len(multi_resolved)}")


if __name__ == "__main__":
    main()