"""Ky's command line. Mostly used by Claude behind the scenes (scheduled job
checks), but anyone can run it.

    ky score  results.md --profile profile.json [--seen seen.json] [--limit 5]
    ky check  tailored.json --profile profile.json [--fix out.json]
    ky search --zip 95814 [--radius 20]      (uses job APIs set up in .env)
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from . import factguard
from .config import load_settings
from .dedupe import dedupe
from .models import Job
from .profile import Profile, ProfileError
from .score import rank, score_job
from .sources import all_sources, load_employers, run_search
from .sources.indeed import parse_details, parse_search


def _load_jobs(path: Path) -> list[Job]:
    text = path.read_text(encoding="utf-8")
    if text.lstrip().startswith(("[", "{")):
        data = json.loads(text)
        if isinstance(data, dict):  # {"result": "...markdown..."} from the connector, or {"jobs": [...]}
            if "result" in data:
                return parse_search(data["result"]) or [parse_details(data["result"])]
            data = data.get("jobs", [])
        return [Job.from_dict(d) for d in data]
    # Indeed connector markdown; details blocks start with "### "
    chunks = [c for c in text.split("\n### ") if c.strip()]
    if len(chunks) > 1 or text.lstrip().startswith("###"):
        return [parse_details(("### " if not c.startswith("###") else "") + c) for c in chunks]
    return parse_search(text)


def cmd_score(a) -> int:
    profile = Profile.load(Path(a.profile))
    jobs: list[Job] = []
    for f in a.files:
        jobs += _load_jobs(Path(f))
    seen = set()
    if a.seen and Path(a.seen).exists():
        seen = set(json.loads(Path(a.seen).read_text()))
    jobs = [j for j in dedupe(jobs) if j.id not in seen and j.page_key not in seen]
    ranked = rank([score_job(j, profile) for j in jobs])
    if a.limit:
        ranked = ranked[: a.limit]
    json.dump([j.to_dict() for j in ranked], sys.stdout, indent=2)
    print()
    return 0


def cmd_check(a) -> int:
    profile = Profile.load(Path(a.profile))
    resume = json.loads(Path(a.file).read_text(encoding="utf-8"))
    fixed, rep = factguard.clean(resume, profile)
    if a.fix:
        Path(a.fix).write_text(json.dumps(fixed, indent=2), encoding="utf-8")
    print(json.dumps({"ok": rep.ok, "problems": rep.problems}, indent=2))
    return 0 if rep.ok else 1


def cmd_search(a) -> int:
    s = load_settings()
    profile = Profile.load(Path(a.profile)) if a.profile else None
    jobs, status = run_search(all_sources(load_employers(s.employers_path)), a.zip, a.radius)
    print(json.dumps(status), file=sys.stderr)
    jobs = dedupe(jobs)
    if profile:
        jobs = rank([score_job(j, profile) for j in jobs])
    json.dump([j.to_dict() for j in jobs], sys.stdout, indent=2)
    print()
    return 0


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    p = argparse.ArgumentParser(prog="ky", description="Agent Ky — clinical-hours job helper")
    sub = p.add_subparsers(dest="cmd", required=True)

    sc = sub.add_parser("score", help="score and rank jobs (Indeed connector output or JSON)")
    sc.add_argument("files", nargs="+")
    sc.add_argument("--profile", required=True, help="profile.yaml or profile.json")
    sc.add_argument("--seen", help="JSON list of job ids already shown to her")
    sc.add_argument("--limit", type=int, default=0)
    sc.set_defaults(fn=cmd_score)

    ck = sub.add_parser("check", help="fact-check a tailored resume against her profile")
    ck.add_argument("file")
    ck.add_argument("--profile", required=True)
    ck.add_argument("--fix", help="write a cleaned copy here")
    ck.set_defaults(fn=cmd_check)

    se = sub.add_parser("search", help="search job APIs configured in .env")
    se.add_argument("--zip", required=True)
    se.add_argument("--radius", type=int, default=20)
    se.add_argument("--profile")
    se.set_defaults(fn=cmd_search)

    a = p.parse_args(argv)
    try:
        return a.fn(a)
    except ProfileError as e:
        print(f"Profile problem: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
