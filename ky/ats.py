"""Job match (ATS) check: which skills a posting asks for does a resume cover?

Same logic as `atsReport` in helper/ky.html, so the daily check and the helper
page agree. Uses the keyword vocabulary (with synonyms) in ky/vocab.py.
"""

from __future__ import annotations

from .vocab import ATS_KEYWORDS, has_any


def resume_text(r: dict) -> str:
    parts: list[str] = [r.get("target_title", ""), r.get("summary", ""), *(r.get("certifications") or [])]
    for e in r.get("experience") or []:
        parts += [e.get("title", ""), *(e.get("bullets") or [])]
    for e in r.get("education") or []:
        parts += [e.get("program", ""), e.get("details", "")]
    for group in (r.get("skills") or {}).values():
        parts += list(group or [])
    for v in r.get("volunteer") or []:
        parts += [v.get("role", ""), *(v.get("bullets") or [])]
    return "\n".join(str(p) for p in parts if p)


def ats_report(job_title: str, job_description: str, resume: dict) -> dict:
    post = f"{job_title}\n{job_description or ''}"
    res = resume_text(resume)
    relevant = [k for k, syn in ATS_KEYWORDS.items() if has_any(post, syn)]
    matched = [k for k in relevant if has_any(res, ATS_KEYWORDS[k])]
    missing = [k for k in relevant if k not in matched]
    pct = int(100 * len(matched) / len(relevant) + 0.5) if relevant else None
    return {"matched": matched, "missing": missing, "total": len(relevant), "pct": pct}
