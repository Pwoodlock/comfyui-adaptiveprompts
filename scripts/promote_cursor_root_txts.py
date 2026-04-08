"""
Promote .txt wildcard lists from wildcards_curvy_exotic/CURSOR__/ (root) into curated folders.

Goals:
- Copy-only (never delete source).
- Avoid overwrites (if destination exists, create a unique name).
- Keep the curated tree organized by simple, predictable rules.
- Produce a manifest JSON so you can see exactly what moved where.

This is intentionally conservative: it doesn't try to understand content deeply.
It just gets your staging files into the right buckets fast.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional


@dataclass
class MoveRecord:
    src: str
    dst: str
    category: str


def _norm_name(name: str) -> str:
    # normalize spaces and weird duplicates (e.g. "liptstick colors.txt")
    n = name.strip()
    n = re.sub(r"\s+", "_", n)
    n = n.replace("&", "and")
    n = n.replace("__", "_")
    return n


def _ensure_unique_path(dst: Path) -> Path:
    if not dst.exists():
        return dst
    stem = dst.stem
    suf = dst.suffix
    parent = dst.parent
    for i in range(2, 9999):
        cand = parent / f"{stem}_dup{i}{suf}"
        if not cand.exists():
            return cand
    raise RuntimeError(f"Could not find unique filename for {dst}")


def _category_for_file(stem_lc: str) -> tuple[str, Path]:
    """
    Return (category, relative_destination_dir).
    """
    # lighting / camera
    if stem_lc.startswith("lighting") or stem_lc.endswith("lighting"):
        return "lighting", Path("lighting") / "inbox_cursor_root"
    if "camera" in stem_lc or "angle" in stem_lc:
        return "camera", Path("camera") / "inbox_cursor_root"

    # setting / locations
    if "location" in stem_lc or stem_lc.endswith("locations") or stem_lc in {"cities", "womanbedrooms", "womanbeds"}:
        return "setting", Path("setting") / "inbox_cursor_root"

    # outfit / clothing / footwear / accessories
    if stem_lc.startswith("clothes") or stem_lc.startswith("dress") or stem_lc in {"sleeves", "fasteners", "fabrics", "patterns"}:
        return "outfit", Path("outfit") / "inbox_cursor_root"
    if stem_lc in {"shoes", "socks"}:
        return "footwear", Path("outfit") / "footwear" / "inbox_cursor_root"
    if stem_lc in {"jewels", "necklaces", "jewelrymaterials"}:
        return "accessories", Path("outfit") / "accessories" / "inbox_cursor_root"

    # hair / face
    if stem_lc.startswith("hair"):
        return "hair", Path("hair") / "inbox_cursor_root"
    if stem_lc in {"eyes", "eyeshapes", "eyebrows", "faceshapes", "facemods", "makeup", "lipstickcolors", "liptstick_colors"}:
        return "face", Path("face") / "inbox_cursor_root"

    # body / subject
    if stem_lc in {"skintones"}:
        return "subject", Path("subject") / "inbox_cursor_root"
    if stem_lc in {"nationalities"}:
        return "subject", Path("subject") / "inbox_cursor_root"
    if stem_lc in {"realnames"}:
        return "names_opt_in", Path("subject") / "opt_in_names"

    # mood / emotions
    if stem_lc.endswith("emotions") or stem_lc in {"broademotions", "happyemotions"}:
        # explicit variants go to opt-in spicy
        if "sex" in stem_lc or "orgasm" in stem_lc:
            return "spicy_emotions", Path("details") / "opt_in_spicy"
        return "mood", Path("mood") / "inbox_cursor_root"

    # poses / positions
    if stem_lc.startswith("positions") or stem_lc in {"positions"}:
        return "pose", Path("pose") / "inbox_cursor_root"

    # colors / misc details
    if "color" in stem_lc or stem_lc.endswith("colors"):
        return "colors", Path("details") / "colors" / "inbox_cursor_root"

    if stem_lc in {"flags", "movies", "videogames", "looks", "words1", "words2"}:
        return "details_misc", Path("details") / "misc" / "inbox_cursor_root"

    # default catch-all
    return "misc", Path("details") / "misc" / "inbox_cursor_root"


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    cursor_root = repo_root / "wildcards_curvy_exotic" / "CURSOR__"
    curated_root = repo_root / "wildcards_curvy_exotic"
    manifest_path = cursor_root / "reports" / "cursor_root_promotion_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    if not cursor_root.exists():
        raise SystemExit(f"CURSOR__ root not found: {cursor_root}")

    files = sorted([p for p in cursor_root.iterdir() if p.is_file() and p.suffix.lower() == ".txt"])
    records: list[MoveRecord] = []

    for src in files:
        stem_lc = _norm_name(src.stem).lower()
        category, rel_dir = _category_for_file(stem_lc)
        dst_dir = curated_root / rel_dir
        dst_dir.mkdir(parents=True, exist_ok=True)

        dst_name = _norm_name(src.name)
        dst = _ensure_unique_path(dst_dir / dst_name)
        dst.write_bytes(src.read_bytes())

        records.append(MoveRecord(src=str(src), dst=str(dst), category=category))

    payload = {
        "source_dir": str(cursor_root),
        "curated_root": str(curated_root),
        "file_count": len(records),
        "records": [asdict(r) for r in records],
    }
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print("[promote_cursor_root_txts] Done")
    print(f"  promoted_files: {len(records)}")
    print(f"  manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

