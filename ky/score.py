"""Clinical Hours Score, Fit Score, badges and red flags."""

from __future__ import annotations

import re
from datetime import date

from .models import Job
from .profile import Profile
from .vocab import (CERT_ALIASES, PATIENT_CARE_SIGNALS, PREFERRED_HINTS, REQUIRED_HINTS,
                    ROLE_TIERS, find_terms, has_any)

# Licensed roles she can't do yet (unless the title says assistant/aide/tech).
LICENSED_TITLES = re.compile(
    r"\b(registered nurse|rn|lvn|lpn|nurse practitioner|np|crna|physician|pharmacist|therapist)\b", re.I)
# Not entry-level patient-care work, whatever else the title says.
NOT_ENTRY_TITLES = re.compile(
    r"\b(manager|director|supervisor|educator|instructor|teacher|student|lead|coordinator ii|travel|"
    r"registered alcohol|counselor|sales|recruiter|billing|biller|coder|receptionist)\b", re.I)

SETTING_HOSPITAL = ["hospital", "medical center", "acute care", "emergency department", "emergency room",
                    "icu", "intensive care", "med-surg", "medical-surgical", "inpatient", "trauma", "telemetry unit"]
SETTING_FACILITY = ["skilled nursing", "snf", "nursing home", "rehab", "rehabilitation center", "assisted living",
                    "long-term care", "long term care", "dialysis center", "clinic", "urgent care", "hospice", "memory care"]
SETTING_HOME = ["home care", "home health", "in-home", "client's home", "clients' homes"]

BADGES = {
    "Paid training": ["paid training", "will train", "we will train", "on-the-job training", "earn your cna",
                      "cna training provided", "free cna", "tuition-free", "paid cna", "sponsored certification",
                      "we will certify", "certification provided", "training program provided"],
    "Tuition help": ["tuition assistance", "tuition reimbursement", "education assistance", "educational assistance",
                     "nursing school", "career ladder", "pathway to rn", "path to rn", "scholarship", "student loan"],
    "Flexible schedule": ["per diem", "prn", "flexible schedul", "flexible hours", "part-time", "part time",
                          "weekend option", "self-scheduling"],
    "No experience needed": ["no experience", "entry level", "entry-level", "new grad", "no prior experience",
                             "students encouraged"],
    "Magnet hospital": ["magnet"],
}
RED_FLAGS = {
    "Asks you to pay for training/application": ["training fee", "application fee", "pay for your training",
                                                 "pay for training", "registration fee", "purchase a starter kit",
                                                 "upfront fee"],
    "Asks for SSN/bank info early": ["social security number", "bank account", "routing number", "send your ssn"],
    "Commission-based": ["commission only", "commission-only", "100% commission"],
}

# Same wording the helper page shows ("Needs CNA license")
CERT_DISPLAY = {"BLS": "BLS/CPR", "CNA": "CNA license", "CPT": "Phlebotomy certificate", "EKG": "EKG certificate",
                "EMT": "EMT certificate", "MA": "Medical Assistant certificate", "HHA": "Home Health Aide certificate",
                "ACLS": "ACLS", "PALS": "PALS", "CPhT": "Pharmacy Tech license", "CRCST": "Sterile Processing certificate",
                "First Aid": "First Aid"}

SHIFT_WORDS = {
    "days": ["day shift", "days", "7a-7p", "7am-7pm", "7a-3p"],
    "evenings": ["evening", "pm shift", "3p-11p", "swing"],
    "nights": ["night", "noc", "7p-7a", "7pm-7am", "11p-7a"],
    "weekends": ["weekend"],
}


def classify(title: str) -> tuple[str, str]:
    if NOT_ENTRY_TITLES.search(title or ""):
        return "", ""
    if LICENSED_TITLES.search(title or "") and not re.search(r"assistant|aide|tech", title or "", re.I):
        return "", ""
    for tier, label, pat in ROLE_TIERS:
        if re.search(pat, title or "", re.I):
            return tier, label
    return "", ""


def cert_requirements(description: str) -> dict[str, str]:
    """-> {cert_code: 'required'|'preferred'} for certs a posting mentions."""
    out: dict[str, str] = {}
    sentences = re.split(r"(?<=[.;!?\n])\s+|\n", description or "")
    for code, aliases in CERT_ALIASES.items():
        for s in sentences:
            if not find_terms(s, aliases):
                continue
            # "CPR" alone inside a long sentence is usually BLS-ish; fine.
            level = "preferred" if has_any(s, PREFERRED_HINTS) else ("required" if has_any(s, REQUIRED_HINTS) else "preferred")
            if out.get(code) != "required":
                out[code] = level
    return out


def _days_old(posted: str, today: date) -> int | None:
    try:
        return (today - date.fromisoformat(posted[:10])).days
    except (ValueError, TypeError):
        return None


def score_job(job: Job, profile: Profile, today: date | None = None,
              tier_bonus: dict[str, int] | None = None) -> Job:
    today = today or date.today()
    text = f"{job.title}\n{job.description}\n{job.schedule}".lower()
    job.tier, label = classify(job.title)
    job.role_label = label
    job.missing = []
    job.badges, reasons = [], {}
    job.red_flags = [f for f in job.red_flags if f == "Reposted many times"]

    # ---- Clinical Hours Score -------------------------------------------
    clinical = {"A": 60, "B": 40, "C": 15}.get(job.tier, 0)
    if has_any(text, SETTING_HOSPITAL) or re.search(r"hospital|medical center", job.employer, re.I):
        clinical += 15
        setting = "hospital"
    elif has_any(text, SETTING_FACILITY):
        clinical += 8
        setting = "care facility/clinic"
    elif has_any(text, SETTING_HOME):
        clinical += 5
        setting = "home care"
    else:
        setting = "setting unclear"
    signals = find_terms(text, PATIENT_CARE_SIGNALS)
    clinical += min(15, 3 * len(signals))
    if re.search(r"full[- ]time|36 hours|40 hours|\b(0\.9|1\.0) fte", text):
        clinical += 10
    else:
        clinical += 5
    clinical += (tier_bonus or {}).get(job.tier, 0)
    job.clinical_score = max(0, min(100, clinical))
    reasons["clinical"] = (f"Tier {job.tier or '-'} ({label or 'not a target role'}), {setting}"
                           + (f", hands-on duties: {', '.join(signals[:4])}" if signals else ""))

    # ---- Fit Score ---------------------------------------------------------
    fit, notes = 50, []
    has = profile.cert_codes(today)
    for code, level in cert_requirements(job.description).items():
        if code in has:
            fit += 10
            notes.append(f"has {code}")
        elif level == "required":
            fit -= 30
            notes.append(f"missing required {code}")
            job.missing.append(CERT_DISPLAY.get(code, code))
        else:
            fit -= 5
            notes.append(f"{code} preferred")

    if job.distance_miles is not None:
        maxd = profile.get("max_commute_miles", 20)
        if job.distance_miles <= maxd:
            fit += 10
        else:
            fit -= 20
            notes.append(f"{job.distance_miles:.0f} mi away")

    shifts_ok = {s.lower() for s in (profile.get("availability") or {}).get("shifts_ok", [])}
    job_shifts = {k for k, words in SHIFT_WORDS.items() if has_any(text, words)}
    if job_shifts:
        if job_shifts & shifts_ok:
            fit += 10
            notes.append("shift fits")
        else:
            fit -= 15
            notes.append(f"shift ({', '.join(sorted(job_shifts))}) may clash with school")

    pay, minimum = job.hourly_pay(), profile.get("pay_minimum_hourly")
    if pay and minimum:
        if pay >= minimum:
            fit += 10
        else:
            fit -= 15
            notes.append(f"pay below ${minimum}/hr")

    age = _days_old(job.posted, today)
    if age is not None:
        if age <= 7:
            fit += 10
            notes.append("new posting")
        elif age <= 14:
            fit += 5
        elif age > 45:
            fit -= 15
            job.red_flags.append("Posting is over 45 days old")
        elif age > 30:
            fit -= 10

    exp_req = re.search(r"(\d+)\+?\s*(?:years?|yrs?|months?)\s+(?:of\s+)?(?:recent\s+)?(?:\w+\s+){0,3}experience\s+(?:is\s+)?required|minimum of (\d+) years?", text)
    if exp_req and not profile.patient_care_jobs():
        fit -= 10
        notes.append("asks for experience")

    # ---- Badges & red flags ------------------------------------------------
    for badge, words in BADGES.items():
        if has_any(text, words):
            job.badges.append(badge)
    if "No experience needed" in job.badges:
        fit += 10
    if "Paid training" in job.badges:
        fit += 5
    for flag, words in RED_FLAGS.items():
        if has_any(text, words):
            job.red_flags.append(flag)
    if not job.employer or job.employer.lower() in ("unknown employer", "confidential", "private company", "n/a"):
        job.red_flags.append("Employer not named")

    job.fit_score = max(0, min(100, fit))
    reasons["fit"] = ", ".join(notes) or "no blockers found"
    job.reasons = reasons
    return job


def rank(jobs: list[Job]) -> list[Job]:
    """Target roles only, red-flagged last, best first."""
    jobs = [j for j in jobs if j.tier]
    return sorted(jobs, key=lambda j: (len([f for f in j.red_flags if f != "Posting is over 45 days old"]) > 0,
                                        -(j.clinical_score + j.fit_score), -j.clinical_score))


def is_alert_worthy(job: Job) -> bool:
    serious = [f for f in job.red_flags if f not in ("Posting is over 45 days old",)]
    if serious:
        return False
    return (job.clinical_score >= 85 and job.fit_score >= 85) or (
        "Paid training" in job.badges and job.clinical_score >= 60 and job.fit_score >= 50)
