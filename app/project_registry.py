"""Subscribe local projects to pseudo-jarvis (sync rule + registry file)."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

VOICE_RULE_FILENAME = "voice-input-confirmation.mds"
VOICE_RULE_GITIGNORE_ENTRY = "./.cursor/rules/voice-input-confirmation.mds"
MDS_PATH_FILE = "mds-path.txt"
SUBSCRIBED_PROJECTS_FILE = "subscribed-projects.txt"


def install_root() -> Path:
    """pseudo-jarvis repo root (source) or PyInstaller bundle resource root."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent.parent


def setup_variables_dir() -> Path:
    """
    Directory holding ``mds-path.txt`` and ``subscribed-projects.txt``.

    Uses ``setup-variables/`` in the install root when present; otherwise
    ``~/Library/Application Support/pseudo-jarvis/setup-variables/``.
    """
    local = install_root() / "setup-variables"
    if local.is_dir():
        return local

    persist = Path.home() / "Library" / "Application Support" / "pseudo-jarvis" / "setup-variables"
    persist.mkdir(parents=True, exist_ok=True)

    mds_path_file = persist / MDS_PATH_FILE
    if not mds_path_file.is_file():
        default_rule = install_root() / ".cursor" / "rules" / "voice-input-confirmation.mds"
        if default_rule.is_file():
            mds_path_file.write_text(str(default_rule.resolve()) + "\n", encoding="utf-8")

    subscribed_file = persist / SUBSCRIBED_PROJECTS_FILE
    if not subscribed_file.is_file():
        subscribed_file.write_text(f"{install_root().resolve()}/\n", encoding="utf-8")

    return persist


def _read_text_file(name: str) -> str:
    path = setup_variables_dir() / name
    if not path.is_file():
        raise FileNotFoundError(
            f"Missing {path}. Run ./setup.sh from the pseudo-jarvis repo first."
        )
    return path.read_text(encoding="utf-8").strip()


def voice_input_confirmation_source() -> Path:
    """Path to ``voice-input-confirmation.mds`` (path stored in ``mds-path.txt``)."""
    source = Path(_read_text_file(MDS_PATH_FILE))
    if not source.is_file():
        raise FileNotFoundError(f"{VOICE_RULE_FILENAME} not found: {source}")
    return source


def list_subscribed_projects() -> list[str]:
    """Project root paths from ``subscribed-projects.txt`` (one per line)."""
    raw = _read_text_file(SUBSCRIBED_PROJECTS_FILE)
    projects: list[str] = []
    for line in raw.splitlines():
        line = line.strip()
        if line:
            projects.append(line)
    return projects


def _normalize_project_root(path: Path) -> str:
    """Store project roots with a trailing slash (matches setup.sh)."""
    resolved = path.expanduser().resolve()
    text = str(resolved)
    if not text.endswith("/"):
        text += "/"
    return text


def _gitignore_has_voice_rule_entry(content: str) -> bool:
    """True if ``content`` already ignores the voice-input-confirmation rule file."""
    target = VOICE_RULE_GITIGNORE_ENTRY.lstrip("./")
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        normalized = stripped.rstrip("/").lstrip("./")
        if normalized == target or stripped == VOICE_RULE_GITIGNORE_ENTRY:
            return True
    return False


def _ensure_voice_rule_in_gitignore(project_root: Path) -> None:
    """Append ``./.cursor/rules/voice-input-confirmation.mds`` to the project ``.gitignore``."""
    gitignore_path = project_root / ".gitignore"
    if gitignore_path.is_file():
        content = gitignore_path.read_text(encoding="utf-8")
        if _gitignore_has_voice_rule_entry(content):
            return
        suffix = "" if content.endswith("\n") or not content else "\n"
        gitignore_path.write_text(
            content + suffix + VOICE_RULE_GITIGNORE_ENTRY + "\n",
            encoding="utf-8",
        )
    else:
        gitignore_path.write_text(VOICE_RULE_GITIGNORE_ENTRY + "\n", encoding="utf-8")


def add_subscribed_project(project_root: Path) -> tuple[str, bool]:
    """
    Copy ``voice-input-confirmation.mds`` into ``project_root/.cursor/rules/``, register the project,
    and list that file in the project ``.gitignore``.

    Returns ``(normalized_path, was_already_subscribed)``.
    """
    if not project_root.expanduser().is_dir():
        raise NotADirectoryError(f"Not a directory: {project_root}")

    normalized = _normalize_project_root(project_root)

    rules_dir = Path(normalized.rstrip("/")) / ".cursor" / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(voice_input_confirmation_source(), rules_dir / VOICE_RULE_FILENAME)

    subscribed_path = setup_variables_dir() / SUBSCRIBED_PROJECTS_FILE
    existing = list_subscribed_projects()
    already = normalized in existing

    if not already:
        with subscribed_path.open("a", encoding="utf-8") as handle:
            handle.write(normalized + "\n")

    _ensure_voice_rule_in_gitignore(Path(normalized.rstrip("/")))

    return normalized, already
