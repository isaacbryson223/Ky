"""The candidate's master facts (profile.yaml). The only source of truth about her."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from .vocab import CERT_ALIASES, find_terms

REQUIRED_FIELDS = ["name"]


class ProfileError(ValueError):
    pass


@dataclass
class Profile:
    data: dict[str, Any]

    # ---- loading ---------------------------------------------------------
    @classmethod
    def load(cls, path: Path) -> "Profile":
        if not Path(path).exists():
            raise ProfileError(
                f"No profile found at {path}. Run `ky onboard` or copy profile.example.yaml to profile.yaml."
            )
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        p = cls(data)
        p.validate()
        return p

    def validate(self) -> None:
        missing = [k for k in REQUIRED_FIELDS if not self.data.get(k)]
        if missing:
            raise ProfileError(f"profile.yaml is missing: {', '.join(missing)}")
        for i, job in enumerate(self.data.get("experience") or []):
            for k in ("title", "employer"):
                if not job.get(k):
                    raise ProfileError(f"experience #{i + 1} is missing '{k}'")
        for c in self.data.get("certifications") or []:
            if not c.get("name"):
                raise ProfileError("each certification needs a 'name'")

    def to_yaml(self) -> str:
        return yaml.safe_dump(self.data, sort_keys=False, allow_unicode=True)

    def redacted_yaml(self) -> str:
        """Profile without contact details, for sending to the language model."""
        d = dict(self.data)
        d["contact"] = {"email": "[redacted]", "phone": "[redacted]"}
        d.pop("zip", None)
        return yaml.safe_dump(d, sort_keys=False, allow_unicode=True)

    # ---- convenience ------------------------------------------------------
    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    @property
    def name(self) -> str:
        return self.data["name"]

    @property
    def first_name(self) -> str:
        return self.name.split()[0]

    @property
    def contact(self) -> dict[str, str]:
        return self.data.get("contact") or {}

    @property
    def certifications(self) -> list[dict[str, Any]]:
        return self.data.get("certifications") or []

    @property
    def experience(self) -> list[dict[str, Any]]:
        return self.data.get("experience") or []

    @property
    def education(self) -> list[dict[str, Any]]:
        return self.data.get("education") or []

    @property
    def volunteer(self) -> list[dict[str, Any]]:
        return self.data.get("volunteer") or []

    @property
    def skills(self) -> dict[str, list[str]]:
        return self.data.get("skills") or {}

    def cert_codes(self, today: date | None = None) -> set[str]:
        """Canonical cert codes she currently holds (expired ones excluded)."""
        today = today or date.today()
        codes: set[str] = set()
        for c in self.certifications:
            exp = str(c.get("expires") or "")
            if exp and _ym(exp) and _ym(exp) < (today.year, today.month):
                continue
            text = f"{c.get('name', '')} {c.get('full_name', '')}"
            for code, aliases in CERT_ALIASES.items():
                if code.lower() == str(c.get("name", "")).strip().lower() or find_terms(text, aliases, whole=True):
                    codes.add(code)
        return codes

    def expiring_certs(self, within_days: int = 60, today: date | None = None) -> list[dict[str, Any]]:
        today = today or date.today()
        out = []
        for c in self.certifications:
            ym = _ym(str(c.get("expires") or ""))
            if not ym:
                continue
            exp = date(ym[0], ym[1], 1)
            if 0 <= (exp - today).days <= within_days:
                out.append(c)
        return out

    def evidence_text(self) -> str:
        """Everything she has done/knows, as one lowercase string (for keyword matching)."""
        parts: list[str] = [str(self.data.get("goal", ""))]
        for job in self.experience:
            parts += [job.get("title", ""), *(job.get("duties") or []), *(job.get("numbers") or [])]
        for v in self.volunteer:
            parts += [v.get("role", ""), *(v.get("duties") or [])]
        for e in self.education:
            parts += [e.get("program", ""), *(e.get("prerequisites_done") or []),
                      *(e.get("prerequisites_in_progress") or [])]
        for group in self.skills.values():
            parts += list(group or [])
        for c in self.certifications:
            parts += [c.get("name", ""), c.get("full_name", "")]
        return "\n".join(str(p) for p in parts).lower()

    def all_text(self) -> str:
        """Full profile text, used by the fact guard."""
        return self.to_yaml().lower()

    def patient_care_jobs(self) -> list[dict[str, Any]]:
        return [j for j in self.experience if j.get("patient_care")]


def _ym(s: str) -> tuple[int, int] | None:
    try:
        y, m = s.strip()[:7].split("-")
        return int(y), int(m)
    except (ValueError, AttributeError):
        return None
