"""Entry point: run every enabled source from sources_config.json, score
+ summarise the results, and write docs/data/jobs.json for the static
site to render.

Usage:
    python -m scraper.main
"""
from __future__ import annotations

import dataclasses
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import profile as P
from .common import Job, RobotsCache, score_job, shutdown_browser
from .sources import generic
from .summarize import summarize_jobs

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
logger = logging.getLogger("scraper.main")

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / "scraper" / "sources_config.json"
OUTPUT_PATH = REPO_ROOT / "docs" / "data" / "jobs.json"
# The site's "Gérer les sites" panel reads its own copy from docs/data/
# so it works over plain HTTP without needing GitHub API read access.
CONFIG_MIRROR_PATH = REPO_ROOT / "docs" / "data" / "sources_config.json"


def load_sources_config() -> list[dict]:
    if not CONFIG_PATH.exists():
        logger.warning("%s not found — no sources to scrape", CONFIG_PATH)
        return []
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        logger.exception("%s is not valid JSON — no sources to scrape", CONFIG_PATH)
        return []


def run() -> None:
    sources = load_sources_config()
    robots = RobotsCache()
    all_jobs: dict[str, Job] = {}
    source_status: dict[str, dict] = {}

    for config in sources:
        name = config.get("name") or config.get("id") or "source sans nom"
        if not config.get("enabled", True):
            logger.info("%s: disabled, skipping", name)
            continue
        try:
            jobs = generic.scrape(config, robots)
            source_status[name] = {"ok": True, "count": len(jobs)}
        except Exception:
            logger.exception("Source %s failed entirely", name)
            jobs = []
            source_status[name] = {"ok": False, "count": 0}
        for job in jobs:
            # A job can be cross-posted between searches; keep the first
            # copy seen.
            all_jobs.setdefault(job.url, job)

    shutdown_browser()

    jobs = list(all_jobs.values())
    for job in jobs:
        job.score_info = score_job(job)

    summaries = summarize_jobs(jobs, P.PROFILE["summary"])

    jobs.sort(key=lambda j: j.score_info["score"], reverse=True)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "profile": P.PROFILE,
        "source_status": source_status,
        "jobs": [
            {
                **dataclasses.asdict(job),
                **job.score_info,
                "summary": summaries.get(job.id, ""),
            }
            for job in jobs
        ],
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logger.info("Wrote %d jobs to %s", len(jobs), OUTPUT_PATH)

    CONFIG_MIRROR_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_MIRROR_PATH.write_text(
        json.dumps(sources, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    if source_status and all(not s["ok"] for s in source_status.values()):
        logger.error("Every source failed — exiting non-zero so the workflow surfaces it")
        sys.exit(1)


if __name__ == "__main__":
    run()
