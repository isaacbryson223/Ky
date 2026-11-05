"""Merge duplicate postings found on several sites (or reposted)."""

from __future__ import annotations

from collections import defaultdict

from .models import Job


def _quality(j: Job) -> tuple:
    # Prefer: direct employer source, has pay, longer description
    direct = j.source.startswith(("Workday", "RSS", "USAJOBS"))
    return (direct, j.pay_min is not None, len(j.description))


def dedupe(jobs: list[Job], repost_threshold: int = 3) -> list[Job]:
    groups: dict[str, list[Job]] = defaultdict(list)
    for j in jobs:
        groups[j.id].append(j)
    out = []
    for group in groups.values():
        best = max(group, key=_quality)
        if not best.posted:
            best.posted = max((g.posted for g in group if g.posted), default="")
        # how many *separate* postings (not the same posting seen on several sites)
        distinct = {(g.source, g.external_id or g.url) for g in group if g.source == best.source}
        if len(distinct) >= repost_threshold and "Reposted many times" not in best.red_flags:
            best.red_flags.append("Reposted many times")
        out.append(best)
    return out
