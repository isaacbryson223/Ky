"""Any job board or employer that offers an RSS feed.

    - name: County Health Jobs
      platform: rss
      url: https://example.gov/jobs/feed.rss

The feed is fetched once per run and filtered by the search query.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

from ..models import Job
from .base import Source, SourceError, parse_pay, strip_html


class RSSSource(Source):
    name = "RSS"

    def __init__(self, employers: list[dict], session=None):
        super().__init__(session)
        self.feeds = [e for e in employers if (e.get("platform") or "").lower() == "rss"]
        self._cache: dict[str, list[Job]] = {}

    def configured(self) -> bool:
        return bool(self.feeds)

    def search(self, query: str, location: str, radius_miles: int) -> list[Job]:
        words = [w for w in query.lower().split() if len(w) > 2]
        out = []
        for feed in self.feeds:
            for job in self._load(feed):
                hay = f"{job.title} {job.description}".lower()
                if all(w in hay for w in words):
                    out.append(job)
        return out

    def _load(self, feed: dict) -> list[Job]:
        if feed["url"] not in self._cache:
            self._wait()
            r = self.session.get(feed["url"], timeout=30)
            if r.status_code >= 400:
                raise SourceError(f"RSS {feed.get('name')}: HTTP {r.status_code}")
            self._cache[feed["url"]] = self.parse_feed(r.text, feed)
        return self._cache[feed["url"]]

    @staticmethod
    def parse_feed(xml_text: str, feed: dict) -> list[Job]:
        root = ET.fromstring(xml_text)
        jobs = []
        for item in root.iter("item"):
            get = lambda tag: (item.findtext(tag) or "").strip()
            desc = strip_html(get("description"))
            lo, hi, period = parse_pay(desc)
            posted = ""
            if get("pubDate"):
                try:
                    posted = parsedate_to_datetime(get("pubDate")).date().isoformat()
                except (TypeError, ValueError):
                    pass
            jobs.append(Job(
                title=strip_html(get("title")),
                employer=feed.get("employer") or feed.get("name", ""),
                location=feed.get("location", ""),
                url=get("link"),
                description=desc,
                source=f"RSS ({feed.get('name', '')})",
                posted=posted,
                pay_min=lo, pay_max=hi, pay_period=period,
            ))
        return jobs
