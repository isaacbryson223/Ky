"""Jooble job search API (free key): https://jooble.org/api/about"""

from __future__ import annotations

import os

from ..models import Job
from .base import Source, parse_pay, strip_html


class JoobleSource(Source):
    name = "Jooble"

    def configured(self) -> bool:
        return bool(os.environ.get("JOOBLE_API_KEY"))

    def search(self, query: str, location: str, radius_miles: int) -> list[Job]:
        url = f"https://jooble.org/api/{os.environ.get('JOOBLE_API_KEY')}"
        body = {"keywords": query, "location": location, "radius": str(int(radius_miles * 1.609)), "page": "1"}
        data = self._post(url, json=body)
        return [self.parse(r) for r in data.get("jobs", [])]

    @staticmethod
    def parse(r: dict) -> Job:
        desc = strip_html(r.get("snippet", ""))
        lo, hi, period = parse_pay(r.get("salary", "") or desc)
        return Job(
            title=strip_html(r.get("title", "")),
            employer=r.get("company", ""),
            location=r.get("location", ""),
            url=r.get("link", ""),
            description=desc,
            source="Jooble",
            posted=(r.get("updated") or "")[:10],
            pay_min=lo,
            pay_max=hi,
            pay_period=period,
            schedule=r.get("type", ""),
            external_id=str(r.get("id", "")),
        )
