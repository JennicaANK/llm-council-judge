"""
DataCollection_v2.py
--------------------
Collects UNRESOLVED Polymarket questions into an Excel file.

Key changes from v1:
  - Targets questions that have NOT resolved yet (active=true, closed=false)
  - Uses chunked pagination to avoid the API offset limit
  - Skips Finance/Crypto/Sports-betting categories automatically
  - Saves market_id so fetch_outcomes.py can later match multi-choice correctly
  - Also writes a plain questions.txt alongside the Excel

Usage:
  python3 DataCollection_v2.py --out new_questions.xlsx --target 2000 --days 180
  python3 DataCollection_v2.py --out new_questions.xlsx --target 2000 --days 180 --market-type binary
"""

import argparse
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from dateutil import parser as dtparser
from openpyxl import Workbook, load_workbook

GAMMA_EVENTS_URL = "https://gamma-api.polymarket.com/events"

EXCLUDED_CATEGORIES = {
    "Crypto", "crypto", "Finance", "finance",
    "Financial Markets", "Sports Betting", "sports betting",
}

COLUMNS = [
    "id", "question_link", "market_id",
    "question_text", "category",
    "date_collected", "resolution_date",
    "correct_answer", "answer_type", "is_binary",
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def safe_parse_dt(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return dtparser.isoparse(s)
    except Exception:
        return None


def parse_outcomes(outcomes_field: Any) -> List[str]:
    if outcomes_field is None:
        return []
    if isinstance(outcomes_field, list):
        return [str(x) for x in outcomes_field]
    if isinstance(outcomes_field, str):
        s = outcomes_field.strip()
        try:
            val = json.loads(s)
            if isinstance(val, list):
                return [str(x) for x in val]
        except Exception:
            pass
        for delim in ["|", ",", ";"]:
            if delim in s and len(s) < 400:
                parts = [p.strip().strip('"').strip("'") for p in s.split(delim)]
                parts = [p for p in parts if p]
                if len(parts) >= 2:
                    return parts
    return []


def is_binary(outcomes: List[str]) -> bool:
    norm = {o.strip().lower() for o in outcomes}
    return norm in [{"yes", "no"}, {"over", "under"}]


def outcomes_to_answer_type(outcomes: List[str]) -> str:
    if not outcomes:
        return ""
    return "(" + ", ".join(outcomes) + ")"


def build_event_link(event_slug: Optional[str]) -> str:
    if not event_slug:
        return ""
    return f"https://polymarket.com/event/{event_slug}"


# ── API fetch with chunked pagination ────────────────────────────────────────

def fetch_events_within_window(
    start_utc: datetime,
    end_utc: datetime,
    limit: int = 100,
    sleep_s: float = 0.3,
) -> List[Dict[str, Any]]:
    """
    Fetch active unresolved events by splitting the window into 14-day chunks.
    This avoids the API's offset limit error.
    """
    all_events: List[Dict[str, Any]] = []
    seen_ids = set()

    chunk_start = start_utc
    chunk_days = 14

    while chunk_start < end_utc:
        chunk_end = min(chunk_start + timedelta(days=chunk_days), end_utc)
        offset = 0

        print(f"  Fetching chunk {chunk_start.date()} → {chunk_end.date()}...")

        while True:
            params = {
                "active":       "true",
                "closed":       "false",
                "limit":        str(limit),
                "offset":       str(offset),
                "end_date_min": iso(chunk_start),
                "end_date_max": iso(chunk_end),
                "order":        "end_date",
                "ascending":    "true",
            }
            r = requests.get(GAMMA_EVENTS_URL, params=params, timeout=30)

            if r.status_code == 422:
                print(f"    Offset limit hit at offset={offset}, moving to next chunk")
                break
            if r.status_code != 200:
                print(f"    Warning: API error {r.status_code}, skipping")
                break

            batch = r.json()
            if not isinstance(batch, list) or len(batch) == 0:
                break

            for ev in batch:
                eid = ev.get("id") or ev.get("slug")
                if eid and eid not in seen_ids:
                    seen_ids.add(eid)
                    all_events.append(ev)

            if len(batch) < limit:
                break

            offset += limit
            time.sleep(sleep_s)

        chunk_start = chunk_end
        time.sleep(sleep_s)

    return all_events


# ── Excel helpers ─────────────────────────────────────────────────────────────

def create_fresh_workbook(path: str) -> None:
    wb = Workbook()
    ws = wb.active
    ws.append(COLUMNS)
    wb.save(path)


def load_existing(path: str):
    wb = load_workbook(path)
    ws = wb.active
    headers = [ws.cell(1, c).value for c in range(1, ws.max_column + 1)]
    col = {str(h).strip(): i + 1 for i, h in enumerate(headers) if h is not None}

    existing_links, existing_q = set(), set()
    max_id = 0
    next_row = 2

    for r in range(2, ws.max_row + 1):
        link = ws.cell(r, col.get("question_link", 2)).value
        qtxt = ws.cell(r, col.get("question_text", 4)).value
        qid  = ws.cell(r, col.get("id", 1)).value
        if link: existing_links.add(str(link).strip())
        if qtxt: existing_q.add(str(qtxt).strip())
        try:
            if qid: max_id = max(max_id, int(qid))
        except Exception:
            pass
        if link or qtxt:
            next_row = r + 1

    return wb, ws, col, max_id, next_row, existing_links, existing_q


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out",         required=True)
    ap.add_argument("--target",      type=int, default=500)
    ap.add_argument("--days",        type=int, default=90)
    ap.add_argument("--days-min",    type=int, default=3)
    ap.add_argument("--market-type", choices=["binary", "all"], default="all")
    args = ap.parse_args()

    out_path = Path(args.out)
    txt_path = out_path.with_suffix(".txt")

    if not out_path.exists():
        create_fresh_workbook(str(out_path))
        print(f"Created new file: {out_path}")

    wb, ws, col, max_id, next_row, existing_links, existing_q = load_existing(str(out_path))

    # Ensure all columns exist
    for c_name in COLUMNS:
        if c_name not in col:
            nc = ws.max_column + 1
            ws.cell(1, nc, c_name)
            col[c_name] = nc

    now       = datetime.now(timezone.utc)
    win_start = now + timedelta(days=args.days_min)
    win_end   = now + timedelta(days=args.days)

    print(f"Fetching events resolving between {win_start.date()} and {win_end.date()}...")
    events = fetch_events_within_window(win_start, win_end, limit=100)
    print(f"Found {len(events)} unique events from API")

    added    = 0
    curr_id  = max_id + 1
    collected = datetime.now().date().isoformat()
    skipped_cat    = 0
    skipped_binary = 0

    for ev in events:
        if added >= args.target:
            break

        ev_category = (ev.get("category") or "").strip() or "Uncategorized"
        if ev_category in EXCLUDED_CATEGORIES:
            skipped_cat += 1
            continue

        ev_slug = ev.get("slug", "")
        ev_end  = safe_parse_dt(ev.get("endDate"))
        if not ev_end:
            continue

        for m in (ev.get("markets") or []):
            if added >= args.target:
                break

            q = (m.get("question") or ev.get("title") or "").strip()
            if not q:
                continue

            link      = build_event_link(ev_slug)
            market_id = str(m.get("id") or m.get("conditionId") or "").strip()
            outcomes  = parse_outcomes(m.get("outcomes"))
            binary    = is_binary(outcomes)

            if args.market_type == "binary" and not binary:
                skipped_binary += 1
                continue

            if link in existing_links or q in existing_q:
                continue

            ws.cell(next_row, col["id"]).value              = curr_id
            ws.cell(next_row, col["question_link"]).value   = link
            ws.cell(next_row, col["market_id"]).value       = market_id
            ws.cell(next_row, col["question_text"]).value   = q
            ws.cell(next_row, col["category"]).value        = ev_category
            ws.cell(next_row, col["date_collected"]).value  = collected
            ws.cell(next_row, col["resolution_date"]).value = ev_end.date().isoformat()
            ws.cell(next_row, col["correct_answer"]).value  = ""
            ws.cell(next_row, col["answer_type"]).value     = outcomes_to_answer_type(outcomes)
            ws.cell(next_row, col["is_binary"]).value       = "Yes" if binary else "No"

            existing_links.add(link)
            existing_q.add(q)
            next_row += 1
            curr_id  += 1
            added    += 1

    wb.save(str(out_path))
    print(f"\n✅ Added {added} questions to {out_path}")
    print(f"   Skipped finance/crypto categories: {skipped_cat} events")
    if args.market_type == "binary":
        print(f"   Skipped non-binary markets: {skipped_binary}")

    if added < args.target:
        print(f"\nNote: only {added} found. Try --days {args.days * 2} for a wider window.")

    # Write txt
    questions = []
    for r in range(2, ws.max_row + 1):
        q = ws.cell(r, col["question_text"]).value
        if q and str(q).strip():
            questions.append(str(q).strip())

    txt_path.write_text("\n".join(questions), encoding="utf-8")
    print(f"✅ Saved {len(questions)} questions to {txt_path}")


if __name__ == "__main__":
    main()