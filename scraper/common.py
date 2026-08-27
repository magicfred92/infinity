"""Shared scraping utilities: robots.txt compliance, headless-browser
fetching, schema.org/JobPosting extraction, the Job data model, and the
keyword-based relevance scorer used by every source module.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import logging
import random
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

from . import profile as P

logger = logging.getLogger(__name__)

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

DEBUG_DIR = Path(__file__).resolve().parent.parent / "debug"


def polite_delay(lo: float = 2.5, hi: float = 5.0) -> None:
    """Small randomised pause between requests to the same site."""
    time.sleep(random.uniform(lo, hi))


def dump_debug_html(name: str, html: str) -> None:
    """Saves a page's HTML for later inspection when a scraper comes up
    empty — the first thing to check when calibrating selectors after
    a real run. Never raises; debugging aid only."""
    try:
        DEBUG_DIR.mkdir(parents=True, exist_ok=True)
        safe_name = re.sub(r"[^a-zA-Z0-9_.-]+", "_", name)
        path = DEBUG_DIR / f"{safe_name}.html"
        path.write_text(html, encoding="utf-8")
        logger.warning("Dumped debug HTML to %s", path)
    except Exception:
        logger.exception("Could not write debug HTML for %s", name)


class RobotsCache:
    """Fetches and caches robots.txt per host so every scraper checks
    permission before hitting a URL instead of assuming it's allowed."""

    def __init__(self, user_agent: str = "*"):
        self._user_agent = user_agent
        self._parsers: dict[str, RobotFileParser] = {}

    def _parser_for(self, url: str) -> RobotFileParser:
        parsed = urlparse(url)
        host = f"{parsed.scheme}://{parsed.netloc}"
        if host not in self._parsers:
            rp = RobotFileParser()
            rp.set_url(host + "/robots.txt")
            try:
                rp.read()
            except Exception:
                logger.warning("Could not fetch robots.txt for %s; assuming allowed", host)
            self._parsers[host] = rp
        return self._parsers[host]

    def allowed(self, url: str) -> bool:
        try:
            return self._parser_for(url).can_fetch(self._user_agent, url)
        except Exception:
            return True


_playwright_ctx = None
_browser = None


def fetch_html_via_browser(url: str, wait_ms: int = 3500) -> tuple[str, dict]:
    """Loads `url` in headless Chromium and returns (html, meta).

    `meta` carries `status` (HTTP status of the initial navigation),
    `final_url` (after any redirect), and `title` — logged whenever a
    search page yields no links, so a future run's plain Actions log is
    enough to tell "wrong URL/redirected" from "bot-check page" from
    "markup changed" without needing to download the debug artifact.

    Uses a single lazily-started browser instance for the process
    lifetime so a scraping run doesn't pay Chromium startup cost per
    page. Call `shutdown_browser()` once done."""
    global _playwright_ctx, _browser
    from playwright.sync_api import sync_playwright

    if _playwright_ctx is None:
        _playwright_ctx = sync_playwright().start()
    if _browser is None:
        _browser = _playwright_ctx.chromium.launch(headless=True)

    page = _browser.new_page(user_agent=BROWSER_UA)
    try:
        response = page.goto(url, timeout=30000, wait_until="domcontentloaded")
        page.wait_for_timeout(wait_ms)
        html = page.content()
        meta = {
            "status": response.status if response else None,
            "final_url": page.url,
            "title": page.title(),
        }
        return html, meta
    finally:
        page.close()


_BOT_CHECK_MARKERS = (
    "captcha",
    "just a moment",
    "attention required",
    "access denied",
    "unusual traffic",
    "are you a human",
    "verify you are human",
    "cloudfront",
    "request blocked",
)


def looks_like_bot_check(html: str) -> bool:
    """Cheap heuristic to flag a page as an anti-bot interstitial or error
    page rather than real content — used for diagnostics on empty search
    results, and to avoid fabricating a "job" out of an error page."""
    low = html.lower()
    return any(marker in low for marker in _BOT_CHECK_MARKERS)


def shutdown_browser() -> None:
    global _playwright_ctx, _browser
    if _browser is not None:
        _browser.close()
        _browser = None
    if _playwright_ctx is not None:
        _playwright_ctx.stop()
        _playwright_ctx = None


def extract_jobposting_jsonld(html: str) -> Optional[dict]:
    """Job boards that want Google for Jobs indexing embed a
    schema.org/JobPosting JSON-LD block on the detail page — this is far
    more stable to parse than hand-picked CSS classes, so it's preferred
    whenever present."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    for script in soup.find_all("script", {"type": "application/ld+json"}):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        candidates = data if isinstance(data, list) else [data]
        for item in candidates:
            if isinstance(item, dict) and item.get("@type") == "JobPosting":
                return item
    return None


def _text_or_none(value) -> Optional[str]:
    if isinstance(value, str):
        return value.strip() or None
    return None


def _location_from_jsonld(loc) -> str:
    if isinstance(loc, list):
        loc = loc[0] if loc else {}
    if not isinstance(loc, dict):
        return _text_or_none(loc) or ""
    address = loc.get("address") or {}
    if isinstance(address, dict):
        parts = [address.get("addressLocality"), address.get("addressRegion")]
        return ", ".join(p for p in parts if p)
    return _text_or_none(address) or ""


@dataclasses.dataclass
class Job:
    source: str
    url: str
    title: str
    company: str
    location: str
    date_posted: Optional[str]
    description: str
    id: str = dataclasses.field(init=False)

    def __post_init__(self):
        self.id = hashlib.sha1(self.url.encode("utf-8")).hexdigest()[:12]

    @classmethod
    def from_jsonld(
        cls, source: str, url: str, posting: Optional[dict], fallback_html: str
    ) -> Optional["Job"]:
        if posting:
            title = _text_or_none(posting.get("title")) or "Sans titre"
            org = posting.get("hiringOrganization") or {}
            company = _text_or_none(org.get("name")) if isinstance(org, dict) else _text_or_none(org)
            company = company or "Entreprise non précisée"
            location = _location_from_jsonld(posting.get("jobLocation") or {})
            description = _text_or_none(posting.get("description")) or ""
            description = re.sub("<[^>]+>", " ", description)
            description = re.sub(r"\s+", " ", description).strip()
            date_posted = _text_or_none(posting.get("datePosted"))
            return cls(
                source=source,
                url=url,
                title=title,
                company=company,
                location=location,
                date_posted=date_posted,
                description=description,
            )

        # Fallback: no structured data found on the page. Grab whatever
        # visible text is available so the job still surfaces (with a
        # lower score, since location/date can't be reliably extracted
        # this way) rather than silently dropping it — unless the page is
        # actually an anti-bot interstitial or error page (e.g. a
        # CloudFront/Akamai block), in which case there's no job to show
        # and fabricating one from the error text would be worse than
        # dropping it.
        from bs4 import BeautifulSoup

        if looks_like_bot_check(fallback_html):
            logger.warning("%s: %s looks like a bot-check/error page, skipping", source, url)
            return None

        soup = BeautifulSoup(fallback_html, "lxml")
        title_tag = soup.find("h1")
        title = title_tag.get_text(strip=True) if title_tag else None
        if not title or re.search(r"\berror\b|\bforbidden\b", title.lower()):
            return None
        body_text = soup.get_text(" ", strip=True)
        return cls(
            source=source,
            url=url,
            title=title,
            company="Entreprise non précisée",
            location="",
            date_posted=None,
            description=body_text[:2000],
        )


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

FRENCH_SPEAKING_REGIONS = {"GE", "VD", "FR", "VS", "NE", "JU", "ROMANDIE"}


_KEYWORD_PATTERN_CACHE: dict[str, re.Pattern] = {}


def _word_boundary_pattern(phrase: str) -> re.Pattern:
    """Compiles (and caches) a case-insensitive, word-boundary-anchored
    pattern for `phrase`. Plain substring matching would let a short
    keyword like "ong" (NGO) match inside "au l-ong- de", or "sion"
    (Valais) match inside "déci-sion-"/"mis-sion-" — both observed in
    practice on the first real scrape, hence the word boundaries rather
    than a simpler `needle in haystack` check."""
    pattern = _KEYWORD_PATTERN_CACHE.get(phrase)
    if pattern is None:
        pattern = re.compile(r"\b" + re.escape(phrase.lower()) + r"\b", re.UNICODE)
        _KEYWORD_PATTERN_CACHE[phrase] = pattern
    return pattern


def _count_keyword_hits(text: str, keywords: list[str]) -> list[str]:
    text_low = re.sub(r"\s+", " ", text.lower())
    return [kw for kw in keywords if _word_boundary_pattern(kw).search(text_low)]


def guess_region(text: str) -> Optional[str]:
    text_low = re.sub(r"\s+", " ", text.lower())
    for needle, region in P.LOCATION_KEYWORDS.items():
        if _word_boundary_pattern(needle).search(text_low):
            return region
    return None


def _recency_score(date_posted: Optional[str]) -> int:
    if not date_posted:
        return 0
    try:
        dt = datetime.fromisoformat(date_posted.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return 0
    age_days = (datetime.now(timezone.utc) - dt).days
    if age_days <= 7:
        return 3
    if age_days <= 30:
        return 1
    return 0


# Keep these caps/weights in sync with `max_possible` below.
_TITLE_WEIGHT, _TITLE_CAP = 3, 3
_SKILL_WEIGHT, _SKILL_CAP = 2, 6
_SECTOR_WEIGHT, _SECTOR_CAP = 1, 3
_REGION_MATCH_BONUS = 8
_REGION_MISMATCH_PENALTY = -12
_RECENCY_CAP = 3

_MAX_POSSIBLE = (
    _TITLE_WEIGHT * _TITLE_CAP
    + _SKILL_WEIGHT * _SKILL_CAP
    + _SECTOR_WEIGHT * _SECTOR_CAP
    + _REGION_MATCH_BONUS
    + _RECENCY_CAP
)


def score_job(job: Job) -> dict:
    haystack = f"{job.title} {job.description} {job.company}"
    title_hits = _count_keyword_hits(haystack, P.TITLE_KEYWORDS)
    skill_hits = _count_keyword_hits(haystack, P.SKILL_KEYWORDS)
    sector_hits = _count_keyword_hits(haystack, P.SECTOR_KEYWORDS)

    # The structured `location` field is authoritative when it matches
    # anything at all — checked alone first, before falling back to
    # scanning the full description. Scanning description text directly
    # is what tagged a Bern-based posting as "VD" in practice: the job
    # was in Bern, but the text also named a Lausanne branch office, and
    # dict-iteration order happened to hit "lausanne" before "bern".
    region = guess_region(job.location) or guess_region(f"{job.location} {job.description}")
    if region in FRENCH_SPEAKING_REGIONS:
        region_score = _REGION_MATCH_BONUS
    elif region is None:
        region_score = 0  # unknown — neither rewarded nor penalised
    else:
        region_score = _REGION_MISMATCH_PENALTY

    recency_score = _recency_score(job.date_posted)

    raw = (
        _TITLE_WEIGHT * min(len(title_hits), _TITLE_CAP)
        + _SKILL_WEIGHT * min(len(skill_hits), _SKILL_CAP)
        + _SECTOR_WEIGHT * min(len(sector_hits), _SECTOR_CAP)
        + region_score
        + recency_score
    )
    normalised = max(0, min(100, round(100 * raw / _MAX_POSSIBLE)))
    return {
        "score": normalised,
        "matched_keywords": sorted(set(title_hits + skill_hits + sector_hits)),
        "region": region,
    }
