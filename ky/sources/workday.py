"""Hospital career sites hosted on Workday (very common for health systems).

Uses the same public JSON the employer's own careers page loads in a browser.
Add employers in config/employers.yaml, e.g.:

    - name: Example Health
      platform: workday
      url: https://examplehealth.wd5.myworkdayjobs.com/en-US/External

Only titles that look like target roles get their full description fetched,
to keep requests light.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from urllib.parse import urlparse

from ..models import Job
from ..vocab import ROLE_TIERS
from .base import Source, SourceError, strip_html

_TIER_RES = [re.compile(p, re.I) for _, _, p in ROLE_TIERS]


def parse_workday_url(url: str) -> tuple[str, str, str]:
    """-> (host, tenant, site) from a careers URL."""
    u = urlparse(url)
    host = u.netloc
    tenant = host.split(".")[0]
    parts = [p for p in u.path.split("/") if p]
    parts = [p for p in parts if not re.fullmatch(r"[a-z]{2}-[A-Z]{2}", p)]  # drop locale
    if not parts:
        raise ValueError(f"Can't find the site name in Workday URL: {url}")
    return host, tenant, parts[0]


def posted_on_to_date(text: str, today: date | None = None) -> str:
    today = today or date.today()
    t = (text or "").lower()
    if "today" in t:
        d = today
    elif "yesterday" in t:
        d = today - timedelta(days=1)
    else:
        m = re.search(r"(\d+)\+?\s*day", t)
        if not m:
            return ""
        d = today - timedelta(days=int(m.group(1)))
    return d.isoformat()


class WorkdaySource(Source):
    name = "Workday"
    min_interval = 1.5

    def __init__(self, employers: list[dict], session=None):
        super().__init__(session)
        self.employers = [e for e in employers if (e.get("platform") or "").lower() == "workday"]
        self._seen: set[str] = set()

    def configured(self) -> bool:
        return bool(self.employers)

    def search(self, query: str, location: str, radius_miles: int) -> list[Job]:
        jobs: list[Job] = []
        for emp in self.employers:
            try:
                jobs += self._search_employer(emp, query)
            except (SourceError, ValueError, KeyError) as e:
                # one broken employer shouldn't stop the run
                from .base import log
                log.warning("Workday %s: %s", emp.get("name"), e)
        return jobs

    def _search_employer(self, emp: dict, query: str) -> list[Job]:
        host, tenant, site = parse_workday_url(emp["url"])
        base = f"https://{host}/wday/cxs/{tenant}/{site}"
        data = self._post(f"{base}/jobs", json={"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": query})
        out = []
        for p in data.get("jobPostings", []):
            path = p.get("externalPath", "")
            key = f"{host}{path}"
            if not path or key in self._seen:
                continue
            self._seen.add(key)
            if not any(r.search(p.get("title", "")) for r in _TIER_RES):
                continue
            detail = self._get(f"{base}{path}")
            out.append(self.parse(detail, p, emp, f"https://{host}/{site}{path}"))
        return out

    @staticmethod
    def parse(detail: dict, listing: dict, emp: dict, url: str) -> Job:
        info = detail.get("jobPostingInfo") or {}
        from .base import parse_pay
        desc = strip_html(info.get("jobDescription", ""))
        lo, hi, period = parse_pay(desc)
        return Job(
            title=info.get("title") or listing.get("title", ""),
            employer=emp.get("name") or (detail.get("hiringOrganization") or {}).get("name", ""),
            location=info.get("location") or listing.get("locationsText", ""),
            url=info.get("externalUrl") or url,
            description=desc,
            source=f"Workday ({emp.get('name', '')})",
            posted=(info.get("startDate") or "")[:10] or posted_on_to_date(listing.get("postedOn", "")),
            pay_min=lo,
            pay_max=hi,
            pay_period=period,
            schedule=info.get("timeType", ""),
            external_id=info.get("jobReqId") or "",
        )
