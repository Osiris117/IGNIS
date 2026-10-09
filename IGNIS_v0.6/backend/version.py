"""Single source of truth for the version exposed by the API and its engines."""

from pathlib import Path


APP_VERSION = (Path(__file__).resolve().parents[1] / "VERSION").read_text(encoding="utf-8").strip()
