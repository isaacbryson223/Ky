"""Adzuna job search API (free key): https://developer.adzuna.com"""

from __future__ import annotations

import os

from ..models import Job
from .base import Source, strip_html


class AdzunaSource(Source):
    name = "Adzuna"
    url = "https://api.adzuna.com/v1/api/jobs/us/search/{page}"

    def configured(self) -> bool:
        return bool(os.environ.get("ADZUNA_APP_ID") and os.environ.get("ADZUNA_APP_KEY"))

    def search(self, query: str, location: str, radius_miles: int) -> list[Job]:
        params = {
            "app_id": os.environ.get("ADZUNA_APP_ID"),
            "app_key": os.environ.get("ADZUNA_APP_KEY"),
            "what": query,
            "where": location,
            "distance": int(radius_miles * 1.609),  # Adzuna uses km
            "results_per_page": 50,
            "max_days_old": 30,
            "sort_by": "date",
            "content-type": "application/json",
        }
        data = self._get(self.url.format(page=1), params=params)
        return [self.parse(r) for r in data.get("results", [])]

    @staticmethod
    def parse(r: dict) -> Job:
        lo, hi = r.get("salary_min"), r.get("salary_max")
        period = "year" if (lo or hi or 0) > 1000 else ("hour" if (lo or hi) else "")
        return Job(
            title=strip_html(r.get("title", "")),
            employer=(r.get("company") or {}).get("display_name", ""),
            location=(r.get("location") or {}).get("display_name", ""),
            url=r.get("redirect_url", ""),
            description=strip_html(r.get("description", "")),
            source="Adzuna",
            posted=(r.get("created") or "")[:10],
            pay_min=lo,
            pay_max=hi,
            pay_period=period,
            schedule=" ".join(x for x in (r.get("contract_time"), r.get("contract_type")) if x).replace("_", " "),
            external_id=str(r.get("id", "")),
        )
