"""
Convert a Vision-style YAML wildcard pack into cc-prompt-studio .txt wildcard files.

Input:  wildcards_curvy_exotic/CURSOR__/Vision2.1.yaml
Output: wildcards_curvy_exotic/Vision/**.txt

Notes:
- Output is intentionally *local-only*; this repo's .gitignore ignores wildcard contents.
- YAML is expected to be a nested mapping where leaves are lists of strings.
  Example: {"Vision": {"Age": {"Adult": ["18 year old", ...]}}}
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Iterable


def _iter_leaf_lists(obj: Any, path_parts: list[str]) -> Iterable[tuple[list[str], list[str]]]:
    """
    Yield (path_parts, values) for each leaf list[str] found in obj.
    """
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k is None:
                continue
            _k = str(k).strip()
            if not _k:
                continue
            yield from _iter_leaf_lists(v, path_parts + [_k])
        return

    if isinstance(obj, list):
        values: list[str] = []
        for item in obj:
            if item is None:
                continue
            if isinstance(item, (str, int, float, bool)):
                s = str(item).strip()
                if s:
                    values.append(s)
            else:
                # Ignore nested structures inside lists; not expected for this pack
                s = str(item).strip()
                if s:
                    values.append(s)
        if values:
            yield (path_parts, values)
        return

    # scalars: nothing to emit
    return


def _safe_relpath(parts: list[str]) -> Path:
    """
    Build a relative path from YAML keys. We keep names mostly as-is so that
    existing tokens like __Vision/Age/Adult__ keep working.
    """
    cleaned: list[str] = []
    for p in parts:
        # YAML keys in this pack often include path segments like "Vision/Age".
        # Preserve those by splitting on / and \, so tokens like __Vision/Age/Adult__
        # map to Vision/Age/Adult.txt on disk.
        raw = str(p).strip()
        if not raw:
            continue
        raw = raw.replace("\\", "/")
        for seg in raw.split("/"):
            seg2 = seg.strip()
            if seg2:
                cleaned.append(seg2)
    return Path(*cleaned)


def main() -> int:
    try:
        import yaml  # type: ignore
    except Exception as exc:
        raise SystemExit(f"PyYAML is required but not available: {exc}")

    repo_root = Path(__file__).resolve().parents[1]
    src = repo_root / "wildcards_curvy_exotic" / "CURSOR__" / "Vision2.1.yaml"
    out_root = repo_root / "wildcards_curvy_exotic"

    if not src.exists():
        raise SystemExit(f"Input YAML not found: {src}")

    with src.open("r", encoding="utf-8", errors="ignore") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise SystemExit("Unexpected YAML structure (expected a mapping at root).")

    written = 0
    for parts, values in _iter_leaf_lists(data, []):
        rel = _safe_relpath(parts)
        if not rel.parts:
            continue

        # Write leaf list to <out_root>/<path>.txt
        dst = out_root / (str(rel) + ".txt")
        dst.parent.mkdir(parents=True, exist_ok=True)
        with dst.open("w", encoding="utf-8", newline="\n") as wf:
            for v in values:
                wf.write(v.replace("\r", "").strip() + "\n")
        written += 1

    print(f"[convert_vision_yaml_to_wildcards] Wrote {written} files under {out_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

