"""Healthcare vocabulary: certifications, role tiers and ATS keywords.

Each keyword has synonyms so Ky can tell whether the candidate *truthfully*
has a skill even when her profile words it differently.
"""

from __future__ import annotations

import re

# Canonical certification -> phrases that mean it in postings or profiles.
CERT_ALIASES: dict[str, list[str]] = {
    "BLS": ["bls", "basic life support", "cpr", "cpr/bls", "bls/cpr", "healthcare provider cpr"],
    "CNA": ["cna", "certified nursing assistant", "certified nurse assistant", "certified nurse aide",
            "nurse aide certification", "nursing assistant certification", "cna certification", "cna license"],
    "CPT": ["cpt-1", "cpt 1", "certified phlebotomy technician", "phlebotomy certification",
            "phlebotomy technician certification", "phlebotomy license"],
    "EKG": ["cet", "certified ekg technician", "ekg certification", "ecg certification", "certified ecg technician"],
    "EMT": ["emt", "emt-b", "emt-basic", "emergency medical technician", "nremt"],
    "MA": ["ccma", "certified clinical medical assistant", "certified medical assistant", "rma",
           "registered medical assistant", "medical assistant certification"],
    "HHA": ["hha certification", "home health aide certification", "home health aide certificate", "certified home health aide"],
    "ACLS": ["acls", "advanced cardiovascular life support"],
    "PALS": ["pals", "pediatric advanced life support"],
    "CPhT": ["cpht", "ptcb", "pharmacy technician certification", "licensed pharmacy technician"],
    "CRCST": ["crcst", "cbspd", "sterile processing certification", "cspdt"],
    "First Aid": ["first aid"],
}

# Phrases that signal a cert is REQUIRED (vs. preferred) when they appear near it.
REQUIRED_HINTS = ["required", "must have", "must possess", "must hold", "current", "valid", "active"]
PREFERRED_HINTS = ["preferred", "a plus", "desired", "nice to have", "or willing to obtain",
                   "within 30 days", "within 60 days", "within 90 days", "will train", "we will certify"]

# Role tiers for the Clinical Hours Score. Patterns are regexes on the job title.
ROLE_TIERS: list[tuple[str, str, str]] = [
    # (tier, label, title regex)
    ("A", "Nursing Assistant / CNA", r"\b(cna|c\.n\.a|nurs(e|ing) (assistant|aide|asst)|nurse aide)\b"),
    ("A", "Patient Care Technician", r"\b(patient care (tech|technician|assistant|associate)|pct|pca)\b"),
    ("A", "ER/ED Technician", r"\b(er|ed|emergency( department| room)?) (tech|technician)\b"),
    ("A", "EMT", r"\bemt\b|emergency medical tech"),
    ("A", "Home Health Aide", r"\b(home health aide|hha|caregiver|personal care aide|direct support professional|dsp)\b"),
    ("A", "Behavioral Health Tech", r"\b(behavioral|mental|psych(iatric)?) health (tech|technician|worker|associate)\b|\bmental health tech"),
    ("A", "Dialysis Tech", r"\b(dialysis|hemodialysis|patient care) tech|\bpct\b.*dialysis|dialysis"),
    ("A", "Medical Assistant", r"\b(clinical )?medical assistant\b|\bmedical asst\b|\bcma\b|\bccma\b"),
    ("A", "Unit/Clinical Tech", r"\b(clinical|unit|surgical|ortho|orthopedic|cardiac|monitor) (tech|technician|associate)\b"),
    ("B", "Medication Technician", r"\b(medication|med) (tech|technician|aide)\b"),
    ("B", "Phlebotomist", r"\bphlebotom"),
    ("B", "EKG/Monitor Tech", r"\b(ekg|ecg|telemetry|monitor) (tech|technician)\b"),
    ("B", "Rehab Aide", r"\b(rehab(ilitation)?|physical therapy|pt|occupational therapy|ot) (aide|tech|technician)\b"),
    ("B", "Patient Transporter", r"\b(patient )?transport(er|ation)\b"),
    ("B", "Sitter / Patient Safety", r"\b(sitter|patient safety (attendant|assistant|companion)|safety companion)\b"),
    ("B", "OR / Surgical Aide", r"\b(or|operating room|surgical) (aide|assistant|attendant)\b"),
    ("C", "Unit Secretary / HUC", r"\b(unit secretary|unit clerk|health unit coordinator|huc|unit coordinator)\b"),
    ("C", "Medical Scribe", r"\bscribe\b"),
    ("C", "Sterile Processing", r"\b(sterile processing|central sterile|spd) "),
    ("C", "Pharmacy Tech", r"\bpharmacy tech"),
]

# Job types she can pick in the helper ("Fine-tune my search"): id, label, Indeed searches, on by default.
# Keep in sync with ROLE_OPTIONS in helper/ky.html.
ROLE_OPTIONS: list[tuple[str, str, list[str], bool]] = [
    ("cna", "CNA / Nursing assistant", ["certified nursing assistant", "nursing assistant hospital"], True),
    ("pct", "Patient care tech", ["patient care technician"], True),
    ("er", "ER tech", ["emergency room technician"], True),
    ("care", "Caregiver / Home health", ["caregiver"], True),
    ("ma", "Medical assistant", ["medical assistant"], True),
    ("phleb", "Phlebotomy", ["phlebotomist"], True),
    ("bh", "Behavioral health", ["behavioral health technician"], True),
    ("ekg", "EKG / Monitor tech", ["EKG technician"], False),
    ("sitter", "Sitter / Transport", ["patient sitter", "patient transporter"], False),
]
DEFAULT_ROLES = [r[0] for r in ROLE_OPTIONS if r[3]]

# Search queries Ky runs on each source.
SEARCH_TERMS = [
    "patient care technician",
    "certified nursing assistant",
    "nursing assistant",
    "emergency department technician",
    "medical assistant",
    "phlebotomist",
    "EKG technician",
    "behavioral health technician",
    "home health aide",
    "patient sitter",
    "dialysis technician",
    "EMT",
]

# Duty words that show direct patient care in a description.
PATIENT_CARE_SIGNALS = [
    "vital signs", "vitals", "activities of daily living", "adls", "adl", "bathing", "toileting",
    "feeding", "ambulat", "transfer", "reposition", "turning", "specimen", "venipuncture",
    "blood draw", "ekg", "ecg", "blood glucose", "fingerstick", "intake and output", "i&o",
    "bedside", "direct patient care", "hands-on patient care", "catheter", "wound", "oral care",
    "patient hygiene", "bed bath", "ostomy", "telemetry", "cpr", "restrain", "sitter", "1:1",
]

# ATS keyword vocabulary: canonical keyword -> synonyms that count as evidence.
ATS_KEYWORDS: dict[str, list[str]] = {
    "vital signs": ["vital signs", "vitals", "blood pressure", "pulse", "temperature", "respirations"],
    "activities of daily living (ADLs)": ["activities of daily living", "adls", "adl", "bathing", "dressing", "toileting", "grooming"],
    "patient transfers": ["transfer", "transfers", "mobility", "ambulat", "wheelchair", "gait belt", "lift"],
    "infection control": ["infection control", "infection prevention", "hand hygiene", "ppe", "isolation precautions", "sanitiz"],
    "patient safety": ["patient safety", "fall prevention", "safely", "safety"],
    "documentation": ["document", "charting", "recorded", "logged", "record"],
    "electronic health records (EHR)": ["ehr", "emr", "electronic health record", "electronic medical record", "epic", "cerner", "meditech"],
    "Epic": ["epic"],
    "HIPAA": ["hipaa", "patient confidentiality", "patient privacy"],
    "medical terminology": ["medical terminology"],
    "specimen collection": ["specimen", "venipuncture", "blood draw", "phlebotomy", "urine sample"],
    "EKG": ["ekg", "ecg", "electrocardiogram"],
    "blood glucose monitoring": ["blood glucose", "glucometer", "fingerstick", "point of care testing", "poct"],
    "intake and output": ["intake and output", "i&o"],
    "medication reminders": ["medication reminder"],
    "dementia care": ["dementia", "alzheimer", "memory care"],
    "patient communication": ["communicat", "report", "explain"],
    "escalating changes in condition": ["changes in condition", "change in condition", "reported changes", "reporting changes", "escalat"],
    "customer service": ["customer service", "customer", "guest", "visitor"],
    "teamwork": ["team", "collaborat"],
    "time management": ["time management", "busy", "fast-paced", "multitask", "prioritiz"],
    "de-escalation": ["de-escalat", "calm", "conflict", "complaint"],
    "bilingual (Spanish)": ["spanish", "bilingual"],
    "CPR / BLS": ["bls", "cpr", "basic life support"],
    "stocking supplies": ["restock", "stock", "supplies", "supply"],
    "patient transport": ["escort", "transport"],
    "compassionate care": ["compassion", "empath", "dignity", "respect"],
}


def find_terms(text: str, phrases: list[str]) -> list[str]:
    """Return phrases (from the list) found in text, using word-ish boundaries."""
    t = (text or "").lower()
    found = []
    for p in phrases:
        pat = re.escape(p.lower())
        # boundary at start; allow stems like "ambulat" to match "ambulation"
        if re.search(rf"(?<![a-z0-9]){pat}", t):
            found.append(p)
    return found


def has_any(text: str, phrases: list[str]) -> bool:
    return bool(find_terms(text, phrases))
