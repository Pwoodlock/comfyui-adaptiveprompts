"""
Build a "global safe" wildcard set from wildcards_curvy_exotic.

Goal: create a local-only tree you can point ComfyUI at confidently:
- global_safe/           : no furry hits, no pollution hits, no stylized hits
- global_safe_opt_in/    : no furry hits, no pollution hits, but has stylized hits (anime/cartoon/etc.)

SAFE MODE:
- copy-only
- never overwrites; creates _dupN if needed
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


FURRY_SUBSTRINGS = [
    "furry",
    "anthro",
    "pokemon",
    "blaziken",
    "e621",
    "scalie",
    "fluffy fur",
    "furry art",
]

FURRY_WORDS = [
    "paws",
    "muzzle",
    "snout",
    "tail",
    "beak",
    "talons",
    # avoid false positive inside "Scandinavian"
    "avian",
]

STYLIZED_MARKERS = [
    "anime",
    "manga",
    "cartoon",
    "comic",
    "disney",
    "ghibli",
]

POLLUTION_MARKERS = [
    "masterpiece",
    "best quality",
    "ultra-detailed",
    "ultra high res",
    "8k",
    "trending on",
    "artstation",
    "cgsociety",
    "midjourney",
    "greg rutkowski",
    "<lora:",
]

_WORD_RE_CACHE: dict[str, re.Pattern[str]] = {}


def _has_whole_word(haystack_low: str, word: str) -> bool:
    pat = _WORD_RE_CACHE.get(word)
    if pat is None:
        pat = re.compile(rf"\\b{re.escape(word)}\\b", re.IGNORECASE)
        _WORD_RE_CACHE[word] = pat
    return pat.search(haystack_low) is not None


def _iter_text_lines(fp: Path) -> Iterable[str]:
    with fp.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            yield line.rstrip("\n").rstrip("\r")


@dataclass
class ScanSummary:
    path: str
    furry_hits: int
    stylized_hits: int
    pollution_hits: int


def scan(fp: Path) -> ScanSummary:
    furry_hits = 0
    stylized_hits = 0
    pollution_hits = 0
    # For giant "prompt soup" lists, don't scan the whole file.
    # We only need to detect if it's safe enough for global use.
    # This also prevents long hangs on multi-megabyte lists.
    max_nonempty = 3000
    nonempty_seen = 0

    for raw in _iter_text_lines(fp):
        s = raw.strip()
        if not s:
            continue
        nonempty_seen += 1
        if nonempty_seen > max_nonempty:
            break
        low = s.lower()

        furry = False
        if any(sub in low for sub in FURRY_SUBSTRINGS):
            furry = True
        else:
            for w in FURRY_WORDS:
                if _has_whole_word(low, w):
                    furry = True
                    break
        if furry:
            furry_hits += 1
            continue

        if any(m in low for m in STYLIZED_MARKERS):
            stylized_hits += 1

        if any(m in low for m in POLLUTION_MARKERS):
            pollution_hits += 1

    return ScanSummary(str(fp), furry_hits, stylized_hits, pollution_hits)


def _copy_no_overwrite(src: Path, dst: Path) -> Path:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not dst.exists():
        shutil.copy2(src, dst)
        return dst
    stem = dst.stem
    suf = dst.suffix
    for i in range(2, 999):
        cand = dst.with_name(f"{stem}_dup{i}{suf}")
        if not cand.exists():
            shutil.copy2(src, cand)
            return cand
    raise RuntimeError(f"Too many duplicates for {dst}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=None, help="Source root (defaults to wildcards_curvy_exotic)")
    ap.add_argument("--out", default=None, help="Output root (defaults to wildcards_curvy_exotic/global_safe_sets)")
    args = ap.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    root = Path(args.root) if args.root else (repo_root / "wildcards_curvy_exotic")
    out_root = Path(args.out) if args.out else (root / "global_safe_sets")

    exclude_dirs = {
        "CURSOR__",
        "wildcard_backups",
        "__pycache__",
        # opt-in explicit / stylized trees we already maintain separately
        "ponyxl_spicy",
        "z_image_extracted",
        # CRITICAL: never scan our own output tree (causes recursive nesting)
        "global_safe_sets",
    }

    safe_dir = out_root / "global_safe"
    optin_dir = out_root / "global_safe_opt_in_stylized"

    copied_safe = 0
    copied_optin = 0
    scanned = 0
    rejected = 0
    rejected_details: list[dict] = []

    # IMPORTANT: this curated tree can contain very large numbers of files.
    # By default we only include human-curated files and curated "inbox" drops,
    # and we skip massive vendor packs.
    include_path_snippets = [
        # keep it tight; these are the areas you explicitly care about
        str(root / "my_presets").lower(),
        str(root / "ponyxl_safe").lower(),
        str(root / "whis-legwear").lower(),
        str(root / "person").lower(),
        # include only curated drops (avoid massive legacy hair/outfit trees)
        str(root / "hair" / "inbox_cursor_root").lower(),
        str(root / "outfit" / "dresses" / "inbox_cursor_root").lower(),
        str(root / "lighting").lower(),
        str(root / "camera").lower(),
        str(root / "setting").lower(),
        str(root / "scenes").lower(),
    ]

    for fp in root.rglob("*.txt"):
        parts = set(fp.parts)
        if any(d in parts for d in exclude_dirs):
            continue
        fp_low = str(fp).lower()
        if not any(snip in fp_low for snip in include_path_snippets):
            continue
        # Avoid pulling in giant vendor packs that explode file counts.
        if "vendor_wildcards" in fp_low:
            continue
        # Allow curated inbox drops for hair/dresses, but keep misc inbox out (too noisy).
        if "inbox_cursor_root" in fp_low and not (
            "\\hair\\inbox_cursor_root\\" in fp_low
            or "\\outfit\\dresses\\inbox_cursor_root\\" in fp_low
        ):
            continue

        # Path sanity: reject overly deep or recursive paths
        rel = fp.relative_to(root)
        depth = len(rel.parts)
        if depth > 4:
            continue
        # Reject any path with repeated directory names (recursion indicator)
        part_counts = {}
        for p in rel.parts:
            part_counts[p] = part_counts.get(p, 0) + 1
            if part_counts[p] > 1:
                break
        else:
            part_counts = {}
        if part_counts and any(v > 1 for v in part_counts.values()):
            continue
        scanned += 1
        s = scan(fp)
        if s.furry_hits or s.pollution_hits:
            rejected += 1
            if len(rejected_details) < 200:
                rejected_details.append(asdict(s))
            continue

        rel = fp.relative_to(root)
        if s.stylized_hits:
            _copy_no_overwrite(fp, optin_dir / rel)
            copied_optin += 1
        else:
            _copy_no_overwrite(fp, safe_dir / rel)
            copied_safe += 1

    report = {
        "root": str(root),
        "out_root": str(out_root),
        "scanned": scanned,
        "copied_safe": copied_safe,
        "copied_opt_in_stylized": copied_optin,
        "rejected": rejected,
        "rejected_sample": rejected_details,
    }
    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "global_safe_build_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        "[build_global_safe_set] "
        f"scanned={scanned} copied_safe={copied_safe} copied_opt_in={copied_optin} rejected={rejected} out_root={out_root}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

