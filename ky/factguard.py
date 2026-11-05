"""Fact guard: every claim in a tailored resume must trace back to her profile.

Checks a tailored resume (the JSON shape in agent/prompts/tailor.md) against
the profile and returns problems. `clean()` removes anything unsupported so a
resume with an invented fact never reaches her.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field

from .profile import Profile
from .vocab import CERT_ALIASES, find_terms

NUM_RE = re.compile(r"(?<![\w.])\$?\d[\d,]*(?:\.\d+)?%?\+?")


@dataclass
class GuardReport:
    problems: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").lower()).strip()


def _numbers(s: str) -> set[str]:
    return {m.group(0).strip("$+%").replace(",", "") for m in NUM_RE.finditer(s or "")}


def _cert_codes_in(text: str) -> set[str]:
    return {code for code, aliases in CERT_ALIASES.items() if find_terms(text, aliases, whole=True)}


def _bullet_ok(bullet: str, source_text: str, source_nums: set[str], her_certs: set[str]) -> str | None:
    bad_nums = _numbers(bullet) - source_nums
    if bad_nums:
        return f"number(s) {', '.join(sorted(bad_nums))} not in her profile"
    bad_certs = _cert_codes_in(bullet) - her_certs
    if bad_certs:
        return f"mentions {', '.join(sorted(bad_certs))}, which she doesn't hold"
    for tool in ("epic", "cerner", "meditech"):
        if re.search(rf"\b{tool}\b", bullet, re.I) and tool not in source_text:
            return f"mentions {tool.title()}, not in her profile"
    return None


def check(resume: dict, profile: Profile) -> GuardReport:
    return _run(resume, profile, fix=False)[0]


def clean(resume: dict, profile: Profile) -> tuple[dict, GuardReport]:
    """Return a copy with unsupported items removed, plus what was removed."""
    report, fixed = _run(copy.deepcopy(resume), profile, fix=True)
    return fixed, report


def _run(resume: dict, profile: Profile, fix: bool) -> tuple[GuardReport, dict]:
    rep = GuardReport()
    src = profile.all_text()
    src_nums = _numbers(src)
    her_certs = profile.cert_codes()
    jobs = {(_norm(j.get("employer")), _norm(j.get("title"))): j for j in profile.experience}
    vols = {_norm(v.get("org")): v for v in profile.volunteer}
    schools = {_norm(e.get("school")) for e in profile.education}

    # certifications
    keep = []
    for c in resume.get("certifications") or []:
        codes = _cert_codes_in(c)
        if (codes and codes <= her_certs) or (not codes and _norm(c) and _norm(c) in src):
            keep.append(c)
        else:
            rep.problems.append(f"Certification '{c}' is not in her profile")
    resume["certifications"] = keep

    # experience
    exp_keep = []
    for e in resume.get("experience") or []:
        key = (_norm(e.get("employer")), _norm(e.get("title")))
        real = jobs.get(key)
        if not real:
            rep.problems.append(f"Job '{e.get('title')}' at '{e.get('employer')}' is not in her profile")
            continue
        for k in ("start", "end"):
            if str(e.get(k, "")).strip() and _norm(str(e.get(k))) != _norm(str(real.get(k))):
                rep.problems.append(f"{e.get('employer')}: {k} date '{e.get(k)}' doesn't match profile")
                e[k] = real.get(k)
        e["bullets"] = _filter_bullets(e.get("bullets") or [], src, src_nums, her_certs, rep, e.get("employer"))
        exp_keep.append(e)
    resume["experience"] = exp_keep

    # volunteer
    vol_keep = []
    for v in resume.get("volunteer") or []:
        if _norm(v.get("org")) not in vols:
            rep.problems.append(f"Volunteer role at '{v.get('org')}' is not in her profile")
            continue
        real = vols[_norm(v.get("org"))]
        if v.get("hours") not in (None, "", 0) and str(v.get("hours")) != str(real.get("hours")):
            rep.problems.append(f"Volunteer hours '{v.get('hours')}' don't match profile ({real.get('hours')})")
            v["hours"] = real.get("hours")
        v["bullets"] = _filter_bullets(v.get("bullets") or [], src, src_nums, her_certs, rep, v.get("org"))
        vol_keep.append(v)
    resume["volunteer"] = vol_keep

    # education
    edu_keep = []
    for ed in resume.get("education") or []:
        if _norm(ed.get("school")) not in schools:
            rep.problems.append(f"School '{ed.get('school')}' is not in her profile")
            continue
        if ed.get("gpa") and _norm(str(ed.get("gpa"))) not in src:
            rep.problems.append(f"GPA '{ed.get('gpa')}' is not in her profile")
            ed["gpa"] = ""
        edu_keep.append(ed)
    resume["education"] = edu_keep

    # summary + skills: numbers and certs only
    summary = resume.get("summary", "")
    why = _bullet_ok(summary, src, src_nums, her_certs)
    if why:
        rep.problems.append(f"Summary: {why}")
        if fix:
            resume["summary"] = _strip_bad_sentences(summary, src, src_nums, her_certs)
    for group, items in (resume.get("skills") or {}).items():
        ok = []
        for s in items or []:
            if _bullet_ok(s, src, src_nums, her_certs):
                rep.problems.append(f"Skill '{s}' isn't supported by her profile")
            else:
                ok.append(s)
        resume["skills"][group] = ok
    return rep, resume


def _filter_bullets(bullets, src, src_nums, her_certs, rep, where):
    out = []
    for b in bullets:
        why = _bullet_ok(b, src, src_nums, her_certs)
        if why:
            rep.problems.append(f"{where}: removed bullet ({why}): {b}")
        else:
            out.append(b)
    return out


def _strip_bad_sentences(text, src, src_nums, her_certs):
    parts = re.split(r"(?<=[.!?])\s+", text)
    return " ".join(p for p in parts if not _bullet_ok(p, src, src_nums, her_certs))
