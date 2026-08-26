"""Config-driven scraper: every entry in `scraper/sources_config.json`
(built-in or added through the web app's "Gérer les sites" panel) is run
through this single generic implementation instead of needing its own
Python file.

Strategy, in order of preference:
 1. Load each search-results page in a headless browser (survives
    client-side rendering).
 2. Pull candidate job-detail links out of it using the site's
    `detail_link_hints` substrings.
 3. On each detail page, prefer the schema.org/JobPosting JSON-LD block
    (the de-facto standard job boards embed for Google for Jobs) over any
    hand-picked CSS — far more stable across markup changes, and works
    the same way regardless of which site it came from.

This only works for sites that (a) return a crawlable list of job links
for a text search and (b) expose JobPosting structured data (or at least
enough visible text to fall back on) — heavily anti-bot or login-gated
sites (LinkedIn, most ATS portals) won't work here. See README.md
"Ajouter un site" for guidance on what makes a good candidate.
"""
from __future__ import annotations

import logging
from urllib.parse import urlencode

from .. import profile as P
from ..common import (
    Job,
    RobotsCache,
    dump_debug_html,
    extract_jobposting_jsonld,
    fetch_html_via_browser,
    polite_delay,
)

logger = logging.getLogger(__name__)


def _search_url(config: dict, term: str, region: str, page: int) -> str:
    base_url = config["base_url"].rstrip("/")
    search_path = config["search_path"]
    term_param = config.get("term_param", "term")
    location_param = config.get("location_param")
    page_param = config.get("page_param", "page")

    params = {}
    if location_param:
        params[term_param] = term
        params[location_param] = region
    else:
        params[term_param] = f"{term} {region}"
    if page_param:
        params[page_param] = page

    return f"{base_url}{search_path}?{urlencode(params)}"


def _extract_detail_links(config: dict, html: str) -> list[str]:
    from bs4 import BeautifulSoup

    base_url = config["base_url"].rstrip("/")
    hints = config.get("detail_link_hints") or []
    soup = BeautifulSoup(html, "lxml")
    links: set[str] = set()
    for a in soup.select("a[href]"):
        href = a["href"]
        if any(hint in href for hint in hints):
            if href.startswith("/"):
                href = base_url + href
            links.add(href.split("?")[0])
    return sorted(links)


def scrape(config: dict, robots: RobotsCache) -> list[Job]:
    name = config.get("name") or config.get("id") or config["base_url"]
    base_url = config["base_url"].rstrip("/")
    search_path = config["search_path"]
    search_terms = config.get("search_terms") or P.DEFAULT_SEARCH_TERMS
    regions = config.get("regions") or P.DEFAULT_REGIONS
    max_pages = int(config.get("max_pages_per_query", 1))
    max_jobs = int(config.get("max_jobs", 40))

    jobs: dict[str, Job] = {}

    if not robots.allowed(base_url + search_path):
        logger.warning("%s: robots.txt disallows %s, skipping", name, search_path)
        return []

    if not config.get("detail_link_hints"):
        logger.warning(
            "%s: no detail_link_hints configured — this source will never "
            "match any job link. Edit it in 'Gérer les sites' or "
            "scraper/sources_config.json.",
            name,
        )
        return []

    for term in search_terms:
        for region in regions:
            for page in range(1, max_pages + 1):
                if len(jobs) >= max_jobs:
                    break
                url = _search_url(config, term, region, page)
                try:
                    html = fetch_html_via_browser(url)
                except Exception:
                    logger.exception("%s: failed to load search page %s", name, url)
                    continue

                links = _extract_detail_links(config, html)
                if not links:
                    logger.warning(
                        "%s: no job links found for term=%r region=%r page=%s — "
                        "check detail_link_hints, see debug dump",
                        name, term, region, page,
                    )
                    dump_debug_html(f"{config.get('id', name)}_{term}_{region}_p{page}", html)
                    continue

                for link in links:
                    if link in jobs or len(jobs) >= max_jobs:
                        continue
                    if not robots.allowed(link):
                        continue
                    polite_delay()
                    try:
                        detail_html = fetch_html_via_browser(link)
                    except Exception:
                        logger.exception("%s: failed to load detail page %s", name, link)
                        continue
                    posting = extract_jobposting_jsonld(detail_html)
                    job = Job.from_jsonld(
                        source=name, url=link, posting=posting, fallback_html=detail_html
                    )
                    if job:
                        jobs[link] = job
            if len(jobs) >= max_jobs:
                break
        if len(jobs) >= max_jobs:
            break

    logger.info("%s: collected %d job postings", name, len(jobs))
    return list(jobs.values())
