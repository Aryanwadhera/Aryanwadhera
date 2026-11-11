#!/usr/bin/env python3
"""Fetch the contribution calendar into data/profile.json.

Run daily by .github/workflows/profile-cards.yml, then scripts/render_cards.py
turns the JSON into cards. Needs GITHUB_TOKEN (provided automatically in Actions).
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

LOGIN = os.environ.get("PROFILE_LOGIN", "aryanwadhera")
ROOT = Path(__file__).resolve().parent.parent
OUT_FILE = ROOT / "data" / "profile.json"

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""


def main() -> None:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        sys.exit("GITHUB_TOKEN is not set")

    body = json.dumps({"query": QUERY, "variables": {"login": LOGIN}}).encode("utf-8")
    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "profile-cards-refresh",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)
    if payload.get("errors"):
        sys.exit(f"GraphQL error: {payload['errors']}")

    user = (payload.get("data") or {}).get("user")
    if user is None:
        sys.exit(f"No GitHub user named {LOGIN!r}")

    calendar = user["contributionsCollection"]["contributionCalendar"]
    days = [
        {"date": day["date"], "count": day["contributionCount"]}
        for week in calendar["weeks"]
        for day in week["contributionDays"]
    ]

    out = {"login": LOGIN, "days": days}
    OUT_FILE.parent.mkdir(exist_ok=True)
    OUT_FILE.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(days)} days to {OUT_FILE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
