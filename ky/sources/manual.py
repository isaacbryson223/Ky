"""Add a job by hand: from a pasted description, a text file, or a URL.

This is how jobs from LinkedIn, Indeed, Handshake, Facebook groups or word of
mouth get into Ky, since those sites don't allow automated searching.
For a URL, Ky fetches the page once (like opening it in a browser) only if the
site allows it; otherwise paste the description.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

import requests

from ..models import Job
from .base import USER_AGENT, parse_pay, strip_html

# Sites that don't permit automated fetching: always ask her to paste instead.
NO_FETCH_DOMAINS = ("linkedin.com", "indeed.com", "glassdoor.com", "ziprecruiter.com", "facebook.com", "handshake")


def job_from_text(text: str, title: str = "", employer: str = "", location: str = "", url: str = "") -> Job:
    text = text.strip()
    if not title:
        first = next((ln.strip() for ln in text.splitlines() if ln.strip()), "Untitled job")
        title = first[:120]
    lo, hi, period = parse_pay(text)
    return Job(title=title, employer=employer or "Unknown employer", location=location, url=url,
               description=text, source="Manual", pay_min=lo, pay_max=hi, pay_period=period)


def fetch_url_text(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if any(d in host for d in NO_FETCH_DOMAINS):
        raise PermissionError(
            f"{host} doesn't allow automated access. Copy the job description and run:\n"
            f"  ky add --paste --url {url}"
        )
    r = requests.get(url, timeout=30, headers={"User-Agent": USER_AGENT})
    r.raise_for_status()
    html = re.sub(r"(?is)<(script|style|nav|footer|header)[^>]*>.*?</\1>", " ", r.text)
    title = re.search(r"(?is)<title[^>]*>(.*?)</title>", html)
    body = strip_html(html)
    return ((strip_html(title.group(1)) + "\n") if title else "") + body
