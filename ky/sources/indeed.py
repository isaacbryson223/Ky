"""Read job results from the Indeed connector inside Claude.

Indeed doesn't allow scraping, but Claude's official Indeed connector
returns results as Markdown blocks like:

    **Job Title:** Certified Nursing Assistant - CNA
    **Job Id:** JOBSEARCH_100007
    **Company:** Example Care
    **Location:** Sacramento, CA
    **Posted on:** October 11, 2026
    **Job Type:** Part-time
    **Compensation:** $20 - $27 an hour
    **View Job URL:** https://to.indeed.com/...

This turns that text (search results or one job's details) into `Job`s.
"""

from __future__ import annotations

import re
from datetime import datetime

from ..models import Job
from .base import parse_pay

FIELD = re.compile(r"\*\*(Job Title|Job Id|Company|Location|Posted on|Job Type|Compensation|View Job URL):\*\*\s*(.+)")


def _date(s: str) -> str:
    for fmt in ("%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(s.strip(), fmt).date().isoformat()
        except ValueError:
            pass
    return ""


def _job(fields: dict[str, str], description: str = "") -> Job:
    lo, hi, period = parse_pay(fields.get("Compensation", ""))
    return Job(
        title=fields.get("Job Title", "").strip(),
        employer=fields.get("Company", "").strip(),
        location=fields.get("Location", "").strip(),
        url=fields.get("View Job URL", "").strip(),
        description=description.strip(),
        source="Indeed",
        posted=_date(fields.get("Posted on", "")),
        pay_min=lo, pay_max=hi, pay_period=period,
        schedule=fields.get("Job Type", "").strip(),
        external_id=fields.get("Job Id", "").strip(),
    )


def parse_search(markdown: str) -> list[Job]:
    """Parse the Indeed connector's search_jobs result."""
    jobs, cur = [], {}
    for line in (markdown or "").splitlines():
        m = FIELD.search(line)
        if not m:
            continue
        key, val = m.group(1), m.group(2)
        if key == "Job Title" and cur:
            jobs.append(_job(cur))
            cur = {}
        cur[key] = val
    if cur:
        jobs.append(_job(cur))
    return [j for j in jobs if j.title]


def parse_details(markdown: str) -> Job:
    """Parse the Indeed connector's get_job_details result (header + description)."""
    text = markdown or ""
    fields: dict[str, str] = {}
    title = re.search(r"^\s*#+\s*(.+)$", text, re.M)
    if title:
        fields["Job Title"] = title.group(1)
    last = 0
    for m in FIELD.finditer(text):
        fields.setdefault(m.group(1), m.group(2))
        last = m.end()
    return _job(fields, text[last:])
