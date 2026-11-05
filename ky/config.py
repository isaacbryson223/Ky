"""Paths and settings. Everything personal lives in git-ignored files."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = Path(__file__).resolve().parent


def _home() -> Path:
    """Where Ky keeps data. Defaults to the current folder; override with KY_HOME."""
    return Path(os.environ.get("KY_HOME", Path.cwd())).resolve()


@dataclass
class Settings:
    home: Path
    profile_path: Path
    data_dir: Path
    output_dir: Path
    db_path: Path
    state_path: Path
    employers_path: Path
    model: str
    anthropic_key: str | None

    @property
    def has_claude(self) -> bool:
        return bool(self.anthropic_key)


def load_settings() -> Settings:
    home = _home()
    if load_dotenv is not None:
        load_dotenv(home / ".env")
    data_dir = Path(os.environ.get("KY_DATA_DIR", home / "data"))
    output_dir = Path(os.environ.get("KY_OUTPUT_DIR", home / "output"))
    employers = home / "config" / "employers.local.yaml"
    if not employers.exists():
        employers = home / "config" / "employers.yaml"
    return Settings(
        home=home,
        profile_path=Path(os.environ.get("KY_PROFILE", home / "profile.yaml")),
        data_dir=data_dir,
        output_dir=output_dir,
        db_path=data_dir / "ky.db",
        state_path=data_dir / "state.json",
        employers_path=employers,
        model=os.environ.get("KY_MODEL", "claude-sonnet-5-5"),
        anthropic_key=os.environ.get("ANTHROPIC_API_KEY") or None,
    )


def agent_file(name: str) -> Path:
    """Find a file under agent/ (system prompt and task prompts)."""
    for base in (_home(), REPO_ROOT):
        p = base / "agent" / name
        if p.exists():
            return p
    raise FileNotFoundError(f"agent/{name} not found")
