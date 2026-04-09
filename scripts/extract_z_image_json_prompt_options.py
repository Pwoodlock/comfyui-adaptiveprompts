"""
Extract OPTION_DATA from CURSOR__/z_image_json_prompt.py into wildcard .txt files.

Outputs are written under wildcards_curvy_exotic/z_image_extracted/{safe,opt_in_stylized}/...

- Safe: excludes obvious stylized / furry-ish entries (anime, cartoon, beast race, orc, etc.)
- Opt-in: everything else (still filtered for empties)

By default writes EN-only (splits "CN | EN" and keeps EN).
"""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
from typing import Any


STYLIZED_MARKERS = [
    "anime",
    "manga",
    "cartoon",
    "comic",
    "disney",
    "ghibli",
    "pixel art",
    "watercolor",
    "oil painting",
    "illustration",
    "fantasy",
    "orc",
    "beast",
    "beast race",
]

CURVY_EXOTIC_PREFER = [
    "bbw",
    "curvy",
    "thick",
    "voluptuous",
    "full-figured",
    "plump",
    "chubby",
    "mature",
    "milf",
]

# Lines containing any of these are dropped for the curvy_exotic profile,
# unless they also include a preferred marker above.
CURVY_EXOTIC_DROP = [
    "slender",
    "thin",
    "skinny",
    "teen",
    "child",
    "girl",
    "boy",
    "young",
]


def _is_stylized(text: str) -> bool:
    low = text.lower()
    return any(m in low for m in STYLIZED_MARKERS)


def _en_only(line: str) -> str:
    s = (line or "").strip().replace("\r", "")
    if " | " in s:
        parts = [p.strip() for p in s.split(" | ", 1)]
        if len(parts) == 2 and parts[1]:
            return parts[1]
    return s


def _write_txt(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # de-dupe, keep order
    seen: set[str] = set()
    out: list[str] = []
    for s in lines:
        s2 = s.strip()
        if not s2:
            continue
        if s2 in seen:
            continue
        seen.add(s2)
        out.append(s2)
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def _apply_profile(profile: str, group: str, filename: str, line: str) -> str | None:
    """
    Return:
    - str: (possibly rewritten) line to keep
    - None: drop line
    """
    if profile != "curvy_exotic":
        return line

    # Only apply aggressive filtering to subject descriptors.
    if str(group) != "subject" or str(filename) != "character_features.txt":
        return line

    low = line.lower()
    if any(p in low for p in CURVY_EXOTIC_PREFER):
        return line
    if any(d in low for d in CURVY_EXOTIC_DROP):
        return None

    # Neutral adult descriptors are fine to keep.
    return line


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--src",
        default=None,
        help="Path to z_image_json_prompt.py (defaults to wildcards_curvy_exotic/CURSOR__/z_image_json_prompt.py)",
    )
    ap.add_argument(
        "--out-root",
        default=None,
        help="Output root (defaults to wildcards_curvy_exotic/z_image_extracted)",
    )
    ap.add_argument(
        "--profile",
        default="general",
        choices=["general", "curvy_exotic"],
        help="Extraction profile. 'curvy_exotic' filters subject descriptors to avoid thin/young content.",
    )
    args = ap.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    src = Path(args.src) if args.src else (repo_root / "wildcards_curvy_exotic" / "CURSOR__" / "z_image_json_prompt.py")
    out_root = Path(args.out_root) if args.out_root else (repo_root / "wildcards_curvy_exotic" / "z_image_extracted")
    profile = str(args.profile or "general").strip() or "general"

    if not src.exists():
        raise SystemExit(f"Source not found: {src}")

    spec = importlib.util.spec_from_file_location("z_image_json_prompt", str(src))
    if spec is None or spec.loader is None:
        raise SystemExit("Failed to load module spec")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]

    cls = getattr(mod, "ZImageJSONPrompting", None)
    if cls is None:
        raise SystemExit("ZImageJSONPrompting not found in module")

    option_data: Any = getattr(cls, "OPTION_DATA", None)
    if not isinstance(option_data, dict):
        raise SystemExit("OPTION_DATA not found or invalid")

    wrote_safe = 0
    wrote_opt = 0

    for group, files in option_data.items():
        if not isinstance(files, dict):
            continue
        for filename, entries in files.items():
            if not isinstance(entries, list):
                continue
            rel = Path(str(group)) / Path(str(filename)).with_suffix("").name
            safe_lines: list[str] = []
            opt_lines: list[str] = []
            for e in entries:
                s = _en_only(str(e))
                if not s:
                    continue
                s2 = _apply_profile(profile, str(group), str(filename), s)
                if not s2:
                    continue
                if _is_stylized(s):
                    opt_lines.append(s2)
                else:
                    safe_lines.append(s2)

            if safe_lines:
                base = out_root if profile == "general" else (out_root / profile)
                _write_txt(base / "safe" / rel.with_suffix(".txt"), safe_lines)
                wrote_safe += 1
            if opt_lines:
                base = out_root if profile == "general" else (out_root / profile)
                _write_txt(base / "opt_in_stylized" / rel.with_suffix(".txt"), opt_lines)
                wrote_opt += 1

    print(
        f"[extract_z_image_json_prompt_options] profile={profile} wrote_safe={wrote_safe} wrote_opt_in={wrote_opt} out_root={out_root}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

