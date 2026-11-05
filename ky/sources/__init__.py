"""Job sources. Add a new site by writing a `Source` subclass and listing it in `all_sources`."""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

from ..models import Job
from ..vocab import SEARCH_TERMS
from .adzuna import AdzunaSource
from .base import Source, SourceError
from .jooble import JoobleSource
from .rss import RSSSource
from .usajobs import USAJobsSource
from .workday import WorkdaySource

log = logging.getLogger("ky.sources")


def load_employers(path: Path) -> list[dict]:
    if not path or not Path(path).exists():
        return []
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("employers") or []


def all_sources(employers: list[dict]) -> list[Source]:
    return [AdzunaSource(), USAJobsSource(), JoobleSource(), WorkdaySource(employers), RSSSource(employers)]


def run_search(sources: list[Source], location: str, radius_miles: int,
               terms: list[str] | None = None) -> tuple[list[Job], dict[str, str]]:
    """Search every configured source for every term. Returns (jobs, status per source)."""
    terms = terms or SEARCH_TERMS
    jobs: list[Job] = []
    status: dict[str, str] = {}
    for src in sources:
        if not src.configured():
            status[src.name] = "not set up"
            continue
        count, errors = 0, 0
        for term in terms:
            try:
                found = src.search(term, location, radius_miles)
                jobs += found
                count += len(found)
            except (SourceError, OSError, ValueError) as e:
                errors += 1
                log.warning("%s '%s': %s", src.name, term, e)
        status[src.name] = f"{count} results" + (f", {errors} errors" if errors else "")
    return jobs, status


__all__ = ["Job", "Source", "all_sources", "load_employers", "run_search"]
