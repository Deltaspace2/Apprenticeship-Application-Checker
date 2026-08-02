#!/usr/bin/env python3
"""Daily checker for UK degree-apprenticeship application windows.

Two modes per target (set in targets.json):
  - keyword mode (default): checks page text for 'open'/'closed' signals.
  - list mode ("list_mode": true): reads the VAC ids of every vacancy on a
    gov.uk 'Find an apprenticeship' results page and alerts on any NEW one.
    Ignores the daily 'Closes in N days' countdowns, so no false pings.

Compares against the last run (state.json) and pings Telegram on change.
Requires: requests, beautifulsoup4  (pip install requests beautifulsoup4)
"""

import json
import os
import re
import sys
import hashlib
from pathlib import Path

import requests
from bs4 import BeautifulSoup

STATE_FILE = Path("state.json")
TARGETS_FILE = Path("targets.json")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
}

VAC_HREF = re.compile(r"/apprenticeship/(VAC\d+)", re.IGNORECASE)


def load_json(path, default):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def fetch(url):
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.text


def extract_text(html, selector=None):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    root = soup.select_one(selector) if selector else soup
    if root is None:                      # selector missed -> use whole page
        root = soup
    return " ".join(root.get_text(" ", strip=True).split()).lower()


def extract_listings(html):
    """Return {VAC_ID: job_title} for a gov.uk results page."""
    soup = BeautifulSoup(html, "html.parser")
    listings = {}
    for a in soup.find_all("a", href=True):
        m = VAC_HREF.search(a["href"])
        if m:
            vac = m.group(1).upper()
            title = " ".join(a.get_text(" ", strip=True).split())
            if title and vac not in listings:   # keep titled link, skip image links
                listings[vac] = title
    return listings


def check_keyword_target(t):
    """Return {open, hash, error, snippet}."""
    try:
        html = fetch(t["url"])
    except Exception as e:
        return {"open": False, "hash": "", "error": str(e), "snippet": ""}

    text = extract_text(html, t.get("selector"))
    open_kws = [k.lower() for k in t.get("open_keywords", [])]
    closed_kws = [k.lower() for k in t.get("closed_keywords", [])]

    has_open = any(k in text for k in open_kws) if open_kws else False
    has_closed = any(k in text for k in closed_kws) if closed_kws else False
    is_open = has_open and not has_closed

    h = hashlib.sha256(text.encode("utf-8")).hexdigest()
    snippet = ""
    for k in open_kws:
        i = text.find(k)
        if i != -1:
            snippet = "..." + text[max(0, i - 40): i + 60] + "..."
            break
    return {"open": is_open, "hash": h, "error": None, "snippet": snippet}


def check_list_target(t):
    """Return {ids: {VAC: title}, error}."""
    try:
        html = fetch(t["url"])
    except Exception as e:
        return {"ids": {}, "error": str(e)}
    return {"ids": extract_listings(html), "error": None}


def notify(messages):
    token = os.environ.get("TELEGRAM_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    body = "\n\n".join(messages)
    print(body)
    if not token or not chat_id:
        print("No Telegram creds set - skipping push notification.")
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data={"chat_id": chat_id, "text": body},
            timeout=30,
        )
    except Exception as e:
        print(f"Telegram send failed: {e}")


def main():
    targets = load_json(TARGETS_FILE, [])
    if not targets:
        print("targets.json is empty. Add some targets first.")
        sys.exit(0)

    old = load_json(STATE_FILE, {})
    new = {}
    alerts = []

    for t in targets:
        name = t["name"]
        prev = old.get(name, {})

        # ---- LIST MODE: alert on any new vacancy id -------------------------
        if t.get("list_mode"):
            res = check_list_target(t)
            new[name] = res
            if res["error"]:
                print(f"[error] {name}: {res['error']}")
                if not prev.get("error"):
                    alerts.append(f"WARNING - {name}: page couldn't be reached "
                                  f"({res['error']}).\n{t['url']}")
                continue

            prev_ids = set((prev.get("ids") or {}).keys())
            curr = res["ids"]
            fresh = [v for v in curr if v not in prev_ids]

            if prev_ids and fresh:            # only alert once a baseline exists
                lines = "\n".join(f"- {curr[v]} ({v})" for v in fresh)
                alerts.append(f"NEW cyber apprenticeship(s) listed:\n{lines}\n{t['url']}")

            note = f"{len(curr)} listings" + (
                f", {len(fresh)} NEW" if prev_ids else " (baseline set)")
            print(f"[ok] {name}: {note}")
            continue

        # ---- KEYWORD MODE ---------------------------------------------------
        res = check_keyword_target(t)
        new[name] = res
        if res["error"]:
            print(f"[error] {name}: {res['error']}")
            if not prev.get("error"):
                alerts.append(f"WARNING - {name}: page couldn't be reached "
                              f"({res['error']}).\n{t['url']}")
            continue

        if res["open"] and not prev.get("open"):
            alerts.append(f"APPLICATIONS OPEN - {name}\n{t['url']}"
                          + (f"\nmatched: {res['snippet']}" if res["snippet"] else ""))
        elif t.get("watch_changes") and prev.get("hash") and res["hash"] != prev["hash"]:
            alerts.append(f"Page changed - {name}\n{t['url']}")

        print(f"[ok] {name}: {'OPEN' if res['open'] else 'closed'}")

    STATE_FILE.write_text(json.dumps(new, indent=2), encoding="utf-8")

    if alerts:
        notify(alerts)
    else:
        print("No changes.")


if __name__ == "__main__":
    main()