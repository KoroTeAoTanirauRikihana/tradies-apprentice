"""Copies the current Tradie's Apprentice knowledge base out of its own
dedicated vault (Electrician_Apprentice_Vault) into this standalone
project's own knowledge/ folder, so the public app's backend never has a
live path dependency into Koro's own machine. Same pattern as the Seer's
Apprentice and Tohunga's Apprentice public apps.

Real filtering, not a blind copy - drops paragraphs tagged "Gap - flagged"
or "Lower confidence", same honesty-tier vocabulary used consistently
across every knowledge document in this project.
"""
from __future__ import annotations

import re
from pathlib import Path

SOURCE = (
    Path.home()
    / "Documents"
    / "Electrician_Apprentice_Vault"
    / "Knowledge"
)
DEST = Path(__file__).resolve().parent / "knowledge"

_UNVERIFIED_MARKERS = (
    re.compile(r"gap\s*[-—]\s*flagged", re.IGNORECASE),
    re.compile(r"lower confidence", re.IGNORECASE),
)


def _is_verified_paragraph(paragraph: str) -> bool:
    return not any(marker.search(paragraph) for marker in _UNVERIFIED_MARKERS)


def _filter_verified(text: str) -> str:
    paragraphs = re.split(r"\n\s*\n", text)
    kept = [p for p in paragraphs if _is_verified_paragraph(p)]
    return "\n\n".join(kept)


def sync() -> dict:
    if not SOURCE.is_dir():
        raise FileNotFoundError(f"Source knowledge folder not found: {SOURCE}")
    DEST.mkdir(parents=True, exist_ok=True)
    for old in DEST.glob("**/*.md"):
        old.unlink()

    synced_files = 0
    dropped_paragraphs = 0
    for path in sorted(SOURCE.glob("**/*.md")):
        original = path.read_text(encoding="utf-8")
        filtered = _filter_verified(original)
        dropped_paragraphs += len(re.split(r"\n\s*\n", original)) - len(
            re.split(r"\n\s*\n", filtered)
        )
        relative = path.relative_to(SOURCE)
        dest_path = DEST / relative
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_text(filtered, encoding="utf-8")
        synced_files += 1

    return {"synced_files": synced_files, "dropped_paragraphs": dropped_paragraphs}


def main() -> None:
    result = sync()
    print(
        f"Synced {result['synced_files']} knowledge file(s) from {SOURCE} to {DEST} "
        f"(dropped {result['dropped_paragraphs']} unverified paragraph(s))."
    )


if __name__ == "__main__":
    main()
