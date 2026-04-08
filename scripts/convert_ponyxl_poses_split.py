"""
Convert PonyXl-poses.yaml into two wildcard trees:
- ponyxl_safe/**.txt      (non-explicit pose/action lines)
- ponyxl_spicy/**.txt     (lines marked sexual intent / explicit anatomy terms)

This avoids accidental contamination of your normal photoreal prompt flow.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable


EXPLICIT_SUBSTRINGS = [
    "sexual intent",
    "explicit",
    "nudity",
    "nipples",
    "clitoris",
    "pussy",
    "vagina",
    "urethra",
    "anus",
    "spread",
    "fellatio",
]


def _is_explicit(line: str) -> bool:
    low = line.lower()
    return any(s in low for s in EXPLICIT_SUBSTRINGS)


def _iter_leaf_lists(obj: Any, path_parts: list[str]) -> Iterable[tuple[list[str], list[str]]]:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k is None:
                continue
            key = str(k).strip()
            if not key:
                continue
            yield from _iter_leaf_lists(v, path_parts + [key])
        return
    if isinstance(obj, list):
        vals: list[str] = []
        for item in obj:
            if item is None:
                continue
            s = str(item).replace("\r", "").strip()
            if s:
                vals.append(s)
        if vals:
            yield (path_parts, vals)
        return
    return


def _safe_relpath(parts: list[str]) -> Path:
    cleaned: list[str] = []
    for p in parts:
        raw = str(p).strip().replace("\\", "/")
        if not raw:
            continue
        for seg in raw.split("/"):
            seg2 = seg.strip()
            if seg2:
                cleaned.append(seg2)
    return Path(*cleaned)


def write_leaf(out_root: Path, rel: Path, lines: list[str]) -> None:
    dst = out_root / (str(rel) + ".txt")
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    try:
        import yaml  # type: ignore
    except Exception as exc:
        raise SystemExit(f"PyYAML is required but not available: {exc}")

    repo_root = Path(__file__).resolve().parents[1]
    src = repo_root / "wildcards_curvy_exotic" / "CURSOR__" / "PonyXl-poses.yaml"
    if not src.exists():
        raise SystemExit(f"Input not found: {src}")

    data = yaml.safe_load(src.read_text(encoding="utf-8", errors="ignore"))
    if not isinstance(data, dict):
        raise SystemExit("Unexpected YAML structure (expected mapping at root).")

    out_safe = repo_root / "wildcards_curvy_exotic" / "ponyxl_safe"
    out_spicy = repo_root / "wildcards_curvy_exotic" / "ponyxl_spicy"

    wrote = 0
    for parts, values in _iter_leaf_lists(data, []):
        rel = _safe_relpath(parts)
        if not rel.parts:
            continue
        safe_lines = [v for v in values if not _is_explicit(v)]
        spicy_lines = [v for v in values if _is_explicit(v)]

        if safe_lines:
            write_leaf(out_safe, rel, safe_lines)
            wrote += 1
        if spicy_lines:
            write_leaf(out_spicy, rel, spicy_lines)
            wrote += 1

    print(f"[convert_ponyxl_poses_split] wrote_files={wrote} safe_root={out_safe} spicy_root={out_spicy}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

