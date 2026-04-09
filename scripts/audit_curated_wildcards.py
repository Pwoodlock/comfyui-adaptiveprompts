"""
Audit curated wildcards for:
- furry/anthro content (strict)
- stylized/anime signals (soft; report only)
- prompt-soup pollution markers (report only)

SAFE MODE:
- does not modify or move files
- produces a JSON report

Default target:
  wildcards_curvy_exotic/  (excluding CURSOR__/ and reports/backups)
Output:
  wildcards_curvy_exotic/CURSOR__/reports/curated_audit_report.json
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


FURRY_SUBSTRINGS = [
    # user hard-ban list
    "furry",
    "anthro",
    "pokemon",
    "blaziken",
    "e621",
    "scalie",
    # phrases
    "fluffy fur",
    "furry art",
]

FURRY_WORDS = [
    # anatomy/creature cues (match as whole words only)
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
    """
    Whole-word match using \b boundaries. This avoids false positives like:
    - ponytail, fishtail, tailback
    while still matching standalone tags like "tail" or "tail,".
    """
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
class FileFinding:
    path: str
    lines: int
    furry_hits: int
    stylized_hits: int
    pollution_hits: int
    examples: list[str]


def audit_file(fp: Path, example_cap: int = 5) -> FileFinding:
    lines = 0
    furry_hits = 0
    stylized_hits = 0
    pollution_hits = 0
    examples: list[str] = []

    # keep audits snappy on giant prompt-soup files
    max_nonempty = 5000
    nonempty_seen = 0

    for raw in _iter_text_lines(fp):
        lines += 1
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
            if len(examples) < example_cap:
                examples.append(s)
            continue

        if any(m in low for m in STYLIZED_MARKERS):
            stylized_hits += 1
            if len(examples) < example_cap:
                examples.append(s)

        if any(m in low for m in POLLUTION_MARKERS):
            pollution_hits += 1
            if len(examples) < example_cap:
                examples.append(s)

    return FileFinding(
        path=str(fp),
        lines=lines,
        furry_hits=furry_hits,
        stylized_hits=stylized_hits,
        pollution_hits=pollution_hits,
        examples=examples,
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=None, help="Curated wildcards root (defaults to wildcards_curvy_exotic)")
    ap.add_argument("--out", default=None, help="Output JSON path")
    ap.add_argument(
        "--max-files",
        type=int,
        default=2500,
        help="Max number of .txt files to scan (default: 2500) to keep runtime bounded.",
    )
    args = ap.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    root = Path(args.root) if args.root else (repo_root / "wildcards_curvy_exotic")
    out = Path(args.out) if args.out else (root / "CURSOR__" / "reports" / "curated_audit_report.json")

    exclude_dirs = {
        "CURSOR__",
        "wildcard_backups",
        "__pycache__",
    }

    findings: list[FileFinding] = []
    scanned_files = 0
    for fp in root.rglob("*.txt"):
        # exclude CURSOR__ and internal folders
        parts = set(fp.parts)
        if any(d in parts for d in exclude_dirs):
            continue
        scanned_files += 1
        if args.max_files and scanned_files > int(args.max_files):
            break
        findings.append(audit_file(fp))

    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "root": str(root),
        "files_scanned": len(findings),
        "files_scanned_cap": int(args.max_files),
        "summary": {
            "files_with_furry_hits": sum(1 for f in findings if f.furry_hits > 0),
            "files_with_stylized_hits": sum(1 for f in findings if f.stylized_hits > 0),
            "files_with_pollution_hits": sum(1 for f in findings if f.pollution_hits > 0),
        },
        "findings": [asdict(f) for f in findings if (f.furry_hits or f.stylized_hits or f.pollution_hits)],
    }
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[audit_curated_wildcards] wrote {out} findings={len(payload['findings'])} scanned={len(findings)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

