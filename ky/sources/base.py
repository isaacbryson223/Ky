"""Common pieces for job sources.

Every source returns a list of `Job`. Sources only use official APIs or the
public JSON that an employer's own careers page loads. No logins, no CAPTCHAs,
no scraping of sites that forbid it. Requests are rate-limited.
"""

from __future__ import annotations

import html
import logging
import re
import time
from abc import ABC, abstractmethod
from typing import Any

import requests

from ..models import Job

log = logging.getLogger("ky.sources")

USER_AGENT = "AgentKy/0.1 (personal job search assistant; +https://github.com/isaacbryson223/ky)"


class SourceError(RuntimeError):
    pass


class Source(ABC):
    name: str = "source"
    min_interval: float = 1.0  # seconds between requests (politeness)

    def __init__(self, session: requests.Session | None = None):
        self.session = session or requests.Session()
        self.session.headers.setdefault("User-Agent", USER_AGENT)
        self._last = 0.0

    @abstractmethod
    def configured(self) -> bool:
        """True if this source has the keys/config it needs."""

    @abstractmethod
    def search(self, query: str, location: str, radius_miles: int) -> list[Job]:
        ...

    # ---- helpers ---------------------------------------------------------
    def _wait(self) -> None:
        delta = time.monotonic() - self._last
        if delta < self.min_interval:
            time.sleep(self.min_interval - delta)
        self._last = time.monotonic()

    def _get(self, url: str, **kw: Any) -> Any:
        self._wait()
        r = self.session.get(url, timeout=30, **kw)
        if r.status_code >= 400:
            raise SourceError(f"{self.name}: HTTP {r.status_code}")
        return r.json()

    def _post(self, url: str, **kw: Any) -> Any:
        self._wait()
        r = self.session.post(url, timeout=30, **kw)
        if r.status_code >= 400:
            raise SourceError(f"{self.name}: HTTP {r.status_code}")
        return r.json()


def strip_html(s: str) -> str:
    s = re.sub(r"(?i)<br\s*/?>|</p>|</li>|</div>|</h\d>", "\n", s or "")
    s = re.sub(r"(?i)<li[^>]*>", "• ", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    s = re.sub(r"[ \t\xa0]+", " ", s)
    s = re.sub(r"\n\s*\n+", "\n\n", s)
    return s.strip()


_PAY_RE = re.compile(
    r"\$\s?(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*(k)?(?:\s*(?:-|–|to)\s*\$?\s?(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*(k)?)?\s*(?:/|per|an|a)?\s*(hour|hr|year|yr|annual)?",
    re.I,
)


def parse_pay(text: str) -> tuple[float | None, float | None, str]:
    """Pull a pay range out of free text like '$22.50 - $28.10 per hour'."""
    for m in _PAY_RE.finditer(text or ""):
        lo = float(m.group(1).replace(",", "")) * (1000 if m.group(2) else 1)
        hi = m.group(3)
        hi_v = float(hi.replace(",", "")) * (1000 if m.group(4) else 1) if hi else None
        unit = (m.group(5) or "").lower()
        if lo < 7 and not hi_v:  # "$5 sign-on"-type noise
            continue
        period = "year" if unit in ("year", "yr", "annual") or lo > 1000 else "hour"
        if period == "hour" and lo > 200:
            continue
        return lo, hi_v, period
    return None, None, ""
