"""
fetch_outcomes.py
-----------------
Fetches the resolved outcome for each question from the Polymarket Gamma API
and saves it back into the correct_answer column of the Excel file.

Usage:
    python3 fetch_outcomes.py

Output:
    CS180_DataCollection_resolved.xlsx  — same as input but with correct_answer filled in
    fetch_outcomes_log.txt              — log of what was found / skipped
"""

import re
import time
import requests
import pandas as pd
from pathlib import Path

INPUT_FILE  = "CS180_DataCollection_1500.xlsx"
OUTPUT_FILE = "CS180_DataCollection_resolved.xlsx"
LOG_FILE    = "fetch_outcomes_log.txt"

GAMMA_URL   = "https://gamma-api.polymarket.com/events"
SLEEP_S     = 0.3   # be polite to the API


def extract_slug(link: str) -> str | None:
    """Extract the event slug from a Polymarket link."""
    if not link or str(link).strip() == "":
        return None
    # Remove fragment (#...) and trailing slashes
    link = str(link).split("#")[0].rstrip("/")
    # Match /event/<slug> or /sports/.../<slug>
    match = re.search(r"/event/([^/?#]+)", link)
    if match:
        return match.group(1)
    # Some links are /sports/nhl/slug style
    parts = link.rstrip("/").split("/")
    if len(parts) >= 1:
        return parts[-1]
    return None


def fetch_event(slug: str) -> dict | None:
    """Fetch event data from Gamma API by slug."""
    try:
        r = requests.get(GAMMA_URL, params={"slug": slug}, timeout=15)
        if r.status_code != 200:
            return None
        data = r.json()
        if isinstance(data, list) and len(data) > 0:
            return data[0]
        return None
    except Exception as e:
        return None


def get_resolved_outcome(event: dict, question_text: str) -> str | None:
    """
    Find the resolved outcome from an event's markets.
    Returns the winning outcome label, or None if not resolved.
    """
    markets = event.get("markets", [])
    if not markets:
        return None

    # Try to find the market whose question matches our question_text
    # Fall back to first market if no match
    target_market = None
    q_lower = str(question_text).lower().strip()

    for m in markets:
        mq = str(m.get("question", "")).lower().strip()
        if mq and (mq in q_lower or q_lower in mq or mq == q_lower):
            target_market = m
            break

    if target_market is None:
        target_market = markets[0]

    # Check if resolved
    if not target_market.get("closed", False):
        return None

    # Parse outcomes and prices
    outcomes_raw = target_market.get("outcomes", "[]")
    prices_raw   = target_market.get("outcomePrices", "[]")

    try:
        import ast, json
        if isinstance(outcomes_raw, str):
            outcomes = json.loads(outcomes_raw)
        else:
            outcomes = list(outcomes_raw)

        if isinstance(prices_raw, str):
            prices = json.loads(prices_raw)
        else:
            prices = list(prices_raw)

        prices = [float(p) for p in prices]
    except Exception:
        return None

    if not outcomes or not prices or len(outcomes) != len(prices):
        return None

    # The winner has price closest to 1.0
    max_price = max(prices)
    if max_price < 0.95:
        # Not clearly resolved
        return None

    winner_idx = prices.index(max_price)
    return str(outcomes[winner_idx])


def main():
    print(f"Reading {INPUT_FILE}...")
    df = pd.read_excel(INPUT_FILE)
    print(f"Loaded {len(df)} rows")

    log_lines = []
    resolved_count   = 0
    not_found_count  = 0
    already_count    = 0
    error_count      = 0

    for i, row in df.iterrows():
        q_num  = row.get("id", i + 1)
        link   = row.get("question_link", "")
        q_text = row.get("question_text", "")

        # Skip if already has a correct answer
        existing = row.get("correct_answer", "")
        if pd.notna(existing) and str(existing).strip() not in ["", "nan"]:
            already_count += 1
            continue

        slug = extract_slug(link)
        if not slug:
            msg = f"[{q_num}] No slug found for link: {link}"
            log_lines.append(msg)
            not_found_count += 1
            continue

        event = fetch_event(slug)
        if event is None:
            msg = f"[{q_num}] API returned nothing for slug: {slug}"
            log_lines.append(msg)
            not_found_count += 1
            time.sleep(SLEEP_S)
            continue

        outcome = get_resolved_outcome(event, q_text)

        if outcome:
            df.at[i, "correct_answer"] = outcome
            msg = f"[{q_num}] ✅ {q_text[:60]} → {outcome}"
            resolved_count += 1
        else:
            msg = f"[{q_num}] ⚠️  Not resolved or unclear: {q_text[:60]}"
            not_found_count += 1

        log_lines.append(msg)

        # Print progress every 50
        if (i + 1) % 50 == 0:
            print(f"  Processed {i+1}/{len(df)} — resolved so far: {resolved_count}")

        time.sleep(SLEEP_S)

    # Save results
    df.to_excel(OUTPUT_FILE, index=False)

    # Save log
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(log_lines))

    print(f"\n=== DONE ===")
    print(f"Total rows        : {len(df)}")
    print(f"Resolved outcomes : {resolved_count}")
    print(f"Already had answer: {already_count}")
    print(f"Not found/unclear : {not_found_count}")
    print(f"Errors            : {error_count}")
    print(f"\nSaved to : {OUTPUT_FILE}")
    print(f"Log      : {LOG_FILE}")


if __name__ == "__main__":
    main()
