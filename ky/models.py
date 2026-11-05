"""Shared data types."""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Job:
    title: str
    employer: str
    location: str
    url: str
    description: str
    source: str
    posted: str = ""            # ISO date (YYYY-MM-DD) when known
    pay_min: float | None = None
    pay_max: float | None = None
    pay_period: str = ""        # "hour" or "year"
    schedule: str = ""          # e.g. "Full-time", "Per diem", "Nights"
    distance_miles: float | None = None
    external_id: str = ""
    via: str = ""               # where it was found: Indeed, ZipRecruiter, a hospital site…
    # Filled in by scoring
    clinical_score: int = 0
    fit_score: int = 0
    tier: str = ""
    role_label: str = ""
    missing: list[str] = field(default_factory=list)  # required certs she lacks
    badges: list[str] = field(default_factory=list)
    red_flags: list[str] = field(default_factory=list)
    reasons: dict[str, str] = field(default_factory=dict)

    @property
    def id(self) -> str:
        """Stable id from employer + normalized title + location, so reposts dedupe."""
        key = "|".join(_norm(x) for x in (self.employer, self.title, self.location))
        return hashlib.sha1(key.encode()).hexdigest()[:10]

    def hourly_pay(self) -> float | None:
        """Best estimate of hourly pay (uses the low end)."""
        val = self.pay_min if self.pay_min is not None else self.pay_max
        if val is None:
            return None
        if self.pay_period == "year" or val > 1000:
            return round(val / 2080, 2)
        return float(val)

    def pay_text(self) -> str:
        if self.pay_min is None and self.pay_max is None:
            return "Pay not listed"
        lo, hi = self.pay_min, self.pay_max
        if self.pay_period == "year" or (lo or hi or 0) > 1000:
            fmt = lambda v: f"${v:,.0f}"
            unit = "/yr"
        else:
            fmt = lambda v: f"${v:,.2f}"
            unit = "/hr"
        if lo is not None and hi is not None and hi != lo:
            return f"{fmt(lo)}–{fmt(hi)}{unit}"
        return f"{fmt(lo if lo is not None else hi)}{unit}"

    @property
    def page_key(self) -> str:
        """The same key the Ky helper page uses for this job (see helper/ky.html)."""
        return page_key(self.employer, self.title, self.location)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["id"] = self.id
        d["key"] = self.page_key
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Job":
        d = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(**d)


def _page_norm(s: str) -> str:
    s = re.sub(r"\(.*?\)", "", (s or "").lower())
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def page_key(company: str, title: str, location: str) -> str:
    """Port of the helper page's key: "j" + djb2 hash in base 36."""
    h = 5381
    for ch in f"{_page_norm(company)}|{_page_norm(title)}|{_page_norm(location)}":
        h = ((h << 5) + h + ord(ch)) & 0xFFFFFFFF
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    out = ""
    while True:
        h, r = divmod(h, 36)
        out = digits[r] + out
        if not h:
            break
    return "j" + out


def _norm(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"\b(sr|jr|i{1,3}|iv|level \d)\b", "", s)
    s = re.sub(r"\(.*?\)", "", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(s.split())
