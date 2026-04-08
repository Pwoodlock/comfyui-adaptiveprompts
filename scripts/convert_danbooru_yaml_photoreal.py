"""
Convert danbooru YAML tag packs into photoreal-friendly wildcard .txt files.

Why this exists:
- The danbooru YAML packs are useful for "variables" (face/hair/body),
  but they contain anime-centric / non-photoreal / explicit entries we don't want.
- This script converts only the parts we care about and filters the rest.

Inputs (expected):
  wildcards_curvy_exotic/CURSOR__/custom_wildcards/danbooru/{face,hair,body}.yaml

Outputs (local-only, gitignored):
  wildcards_curvy_exotic/face/inbox_danbooru_clean/*.txt
  wildcards_curvy_exotic/hair/inbox_danbooru_clean/*.txt
  wildcards_curvy_exotic/body/inbox_danbooru_clean/*.txt

Filtering:
- Drops lines with obvious anime/ASCII/emoticon content.
- Drops explicit/violent sexual terms and non-human anatomy.
- Drops "uwu" style emoticons and ASCII faces.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable


DROP_SUBSTRINGS = [
    # anime / meme / ascii
    "uwu",
    "0w0",
    "/|_/|",
    "o_o",
    "0_0",
    "^_^",
    "xd",
    "x3",
    # explicit / violent sexual content
    "rape",
    "ahegao",
    "fucked",
    "in heat",
    # non-human anatomy / furry adjacency
    "knotted",
    "spiked penis",
    "extra penises",
]

DROP_REGEXES = [
    re.compile(r"^[/\\;:()><\^0-9_@+|.=v-]{2,}$", re.IGNORECASE),  # mostly emoticon/ascii
]


def keep_line(s: str) -> bool:
    t = s.strip()
    if not t:
        return False
    low = t.lower()
    for sub in DROP_SUBSTRINGS:
        if sub in low:
            return False
    for rx in DROP_REGEXES:
        if rx.match(t):
            return False
    return True


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
            if keep_line(s):
                vals.append(s)
        if vals:
            yield (path_parts, vals)
        return
    return


def write_group(out_dir: Path, parts: list[str], values: list[str]) -> None:
    # parts like ["face","emotions"] -> emotions.txt
    # keep it shallow: filename = "_".join(parts[1:])
    leaf_name = "_".join(parts[1:]) if len(parts) > 1 else parts[0]
    leaf_name = leaf_name.replace(" ", "_")
    dst = out_dir / f"{leaf_name}.txt"
    out_dir.mkdir(parents=True, exist_ok=True)
    with dst.open("w", encoding="utf-8", newline="\n") as f:
        for v in values:
            f.write(v + "\n")


def convert_one(yaml_path: Path, out_dir: Path, allow_top: str) -> int:
    import yaml  # type: ignore

    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8", errors="ignore"))
    if not isinstance(data, dict) or allow_top not in data:
        return 0

    written = 0
    for parts, values in _iter_leaf_lists(data[allow_top], [allow_top]):
        # Special case: drop body/penis entirely for photoreal human female workflows
        if allow_top == "body" and len(parts) >= 2 and parts[1].lower() == "penis":
            continue
        write_group(out_dir, parts, values)
        written += 1
    return written


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    base = repo_root / "wildcards_curvy_exotic" / "CURSOR__" / "custom_wildcards" / "danbooru"

    face_yaml = base / "face.yaml"
    hair_yaml = base / "hair.yaml"
    body_yaml = base / "body.yaml"

    out_face = repo_root / "wildcards_curvy_exotic" / "face" / "inbox_danbooru_clean"
    out_hair = repo_root / "wildcards_curvy_exotic" / "hair" / "inbox_danbooru_clean"
    out_body = repo_root / "wildcards_curvy_exotic" / "body" / "inbox_danbooru_clean"

    total = 0
    if face_yaml.exists():
        total += convert_one(face_yaml, out_face, "face")
    if hair_yaml.exists():
        total += convert_one(hair_yaml, out_hair, "hair")
    if body_yaml.exists():
        total += convert_one(body_yaml, out_body, "body")

    print(f"[convert_danbooru_yaml_photoreal] wrote_groups={total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

