"""Per-job summaries.

If ANTHROPIC_API_KEY is set (e.g. as a GitHub Actions secret), the
top-scoring jobs get a short AI-written summary plus a one-line fit
rationale against the candidate profile. Every other job — and every
job when no key is configured — gets a plain extractive summary, so the
scraper is fully functional with zero API cost by default.
"""
from __future__ import annotations

import logging
import os

from .common import Job

logger = logging.getLogger(__name__)

AI_SUMMARY_LIMIT = int(os.environ.get("AI_SUMMARY_LIMIT", "25"))
MODEL = os.environ.get("ANTHROPIC_SUMMARY_MODEL", "claude-haiku-4-5")


def extractive_summary(job: Job, max_len: int = 280) -> str:
    text = job.description.strip()
    if len(text) <= max_len:
        return text
    return text[:max_len].rsplit(" ", 1)[0] + "…"


def summarize_jobs(jobs: list[Job], profile_summary: str) -> dict[str, str]:
    """Returns {job.id: summary}. Never raises — any AI failure just
    falls back to the extractive summary for that job.

    Expects each `job` to already carry a `score_info` attribute (set by
    `common.score_job`), used only to prioritise which jobs get the
    costlier AI treatment.
    """
    summaries = {job.id: extractive_summary(job) for job in jobs}

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.info("No ANTHROPIC_API_KEY set — using extractive summaries only")
        return summaries

    try:
        import anthropic
    except ImportError:
        logger.warning("anthropic package not installed — using extractive summaries only")
        return summaries

    client = anthropic.Anthropic(api_key=api_key)
    top_jobs = sorted(jobs, key=lambda j: j.score_info["score"], reverse=True)[:AI_SUMMARY_LIMIT]

    for job in top_jobs:
        try:
            msg = client.messages.create(
                model=MODEL,
                max_tokens=200,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            "Profil du candidat:\n"
                            f"{profile_summary}\n\n"
                            "Offre d'emploi:\n"
                            f"Titre: {job.title}\n"
                            f"Entreprise: {job.company}\n"
                            f"Description: {job.description[:3000]}\n\n"
                            "En français, en 2 phrases maximum : résume l'offre, "
                            "puis indique en une phrase pourquoi elle correspond "
                            "(ou pas) au profil du candidat. Pas d'introduction, "
                            "va droit au but."
                        ),
                    }
                ],
            )
            text = "".join(getattr(block, "text", "") for block in msg.content).strip()
            if text:
                summaries[job.id] = text
        except Exception:
            logger.exception("AI summary failed for %s — keeping extractive summary", job.url)

    return summaries
