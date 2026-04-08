"""
Generic YAML->wildcards converter (nested mapping -> leaf list[str] -> .txt).

This converts YAML packs of the form:
  root_key:
    group:
      - "value"
      - "value"
    nested:
      sub:
        - "value"

into:
  <out_root>/<root_key>/group.txt
  <out_root>/<root_key>/nested/sub.txt

It preserves embedded path segments in keys like "Vision/Age" by splitting on '/'.

This script is safe to commit. The produced wildcard contents are ignored by git.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Iterable


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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Path to YAML/YML file")
    ap.add_argument("--out-root", required=True, help="Output directory root")
    args = ap.parse_args()

    try:
        import yaml  # type: ignore
    except Exception as exc:
        raise SystemExit(f"PyYAML is required but not available: {exc}")

    src = Path(args.input)
    out_root = Path(args.out_root)

    if not src.exists():
        raise SystemExit(f"Input not found: {src}")

    data = yaml.safe_load(src.read_text(encoding="utf-8", errors="ignore"))
    if not isinstance(data, dict):
        raise SystemExit("Unexpected YAML structure (expected mapping at root).")

    written = 0
    for parts, values in _iter_leaf_lists(data, []):
        rel = _safe_relpath(parts)
        if not rel.parts:
            continue
        dst = out_root / (str(rel) + ".txt")
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text("\n".join(values) + "\n", encoding="utf-8")
        written += 1

    print(f"[convert_yaml_tree_to_wildcards] wrote_files={written} out_root={out_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

