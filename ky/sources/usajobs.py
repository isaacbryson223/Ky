"""USAJOBS API (federal jobs, including VA hospitals): https://developer.usajobs.gov"""

from __future__ import annotations

import os

from ..models import Job
from .base import Source, strip_html


class USAJobsSource(Source):
    name = "USAJOBS"
    url = "https://data.usajobs.gov/api/search"

    def configured(self) -> bool:
        return bool(os.environ.get("USAJOBS_API_KEY") and os.environ.get("USAJOBS_EMAIL"))

    def search(self, query: str, location: str, radius_miles: int) -> list[Job]:
        headers = {
            "Host": "data.usajobs.gov",
            "User-Agent": os.environ.get("USAJOBS_EMAIL", ""),
            "Authorization-Key": os.environ.get("USAJOBS_API_KEY", ""),
        }
        params = {
            "Keyword": query,
            "LocationName": location,
            "Radius": radius_miles,
            "ResultsPerPage": 50,
            "DatePosted": 30,
            "WhoMayApply": "public",
        }
        data = self._get(self.url, headers=headers, params=params)
        items = (data.get("SearchResult") or {}).get("SearchResultItems") or []
        return [self.parse(i.get("MatchedObjectDescriptor") or {}) for i in items]

    @staticmethod
    def parse(d: dict) -> Job:
        pay = (d.get("PositionRemuneration") or [{}])[0]
        interval = (pay.get("RateIntervalCode") or "").upper()
        period = "hour" if interval in ("PH", "PER HOUR") else ("year" if pay else "")

        def num(v):
            try:
                return float(v)
            except (TypeError, ValueError):
                return None

        details = ((d.get("UserArea") or {}).get("Details") or {})
        desc = "\n\n".join(
            x for x in (
                details.get("JobSummary"),
                "Duties:\n" + "\n".join(details.get("MajorDuties") or []) if details.get("MajorDuties") else "",
                "Qualifications:\n" + (d.get("QualificationSummary") or "") if d.get("QualificationSummary") else "",
            ) if x
        )
        return Job(
            title=d.get("PositionTitle", ""),
            employer=d.get("OrganizationName") or d.get("DepartmentName", ""),
            location=d.get("PositionLocationDisplay", ""),
            url=(d.get("ApplyURI") or [d.get("PositionURI", "")])[0],
            description=strip_html(desc),
            source="USAJOBS",
            posted=(d.get("PublicationStartDate") or "")[:10],
            pay_min=num(pay.get("MinimumRange")),
            pay_max=num(pay.get("MaximumRange")),
            pay_period=period,
            schedule=", ".join(s.get("Name", "") for s in d.get("PositionSchedule") or []),
            external_id=str(d.get("PositionID", "")),
        )
