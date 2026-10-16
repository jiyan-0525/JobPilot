"""Local persistence under data/: candidate profiles and cached job searches.

Minimal JSON implementation that is enough for steps 1-2; upgrade to SQLite once
matching (step 3) needs queries across many jobs.
"""
from __future__ import annotations

import json
import os
import time

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


def save_profile(profile: dict, data_dir: str = DATA_DIR) -> str:
    """Save the profile as a timestamped JSON file and return its path."""
    os.makedirs(data_dir, exist_ok=True)
    name = profile.get("name") or "profile"
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)[:40]
    ts = time.strftime("%Y%m%d-%H%M%S")
    path = os.path.join(data_dir, f"profile_{safe}_{ts}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)
    return path


def save_jobs(jobs: list[dict], keyword: str = "jobs", data_dir: str = DATA_DIR) -> str:
    """Cache a job search result as a timestamped JSON file; return its path."""
    os.makedirs(data_dir, exist_ok=True)
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in keyword)[:40] or "jobs"
    ts = time.strftime("%Y%m%d-%H%M%S")
    path = os.path.join(data_dir, f"jobs_{safe}_{ts}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(jobs, f, ensure_ascii=False, indent=2)
    return path
