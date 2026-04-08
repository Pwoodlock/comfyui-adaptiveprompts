"""
Scan a wildcard "inbox" (CivitAI downloads, mixed packs) and produce a safety report.

Design goals:
- SAFE MODE: read-only, no file modifications, no moves.
- Fast enough for large packs (streams line-by-line).
- Help you decide what to promote into curated wildcards.

Default inbox:
  wildcards_curvy_exotic/CURSOR__/custom_wildcards

Output (default):
  wildcards_curvy_exotic/CURSOR__/reports/inbox_scan_report.json

Heuristic buckets:
- StructuredPack: .yaml/.yml/.json
- NameDump: mostly single-token lines (names), low punctuation, huge variety
- PromptSoup: long comma-chains / quality boilerplate / artist salad / lora tags
- CleanTags: short tag-like lines, low "pollution" markers
"""

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Iterable, Optional


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

_WS_RE = re.compile(r"\s+")
_LORA_RE = re.compile(r"<lora:[^>]+>", re.IGNORECASE)


@dataclass
class FileStats:
    path: str
    ext: str
    bytes: int
    lines: int
    nonempty_lines: int
    unique_sampled: int
    avg_len: float
    max_len: int
    comma_rate: float
    marker_hits: int
    lora_hits: int
    bucket: str
    notes: list[str]


def _iter_text_lines(fp: Path, limit_lines: Optional[int] = None) -> Iterable[str]:
    # errors=ignore because these packs can have random encodings
    with fp.open("r", encoding="utf-8", errors="ignore") as f:
        for i, line in enumerate(f):
            if limit_lines is not None and i >= limit_lines:
                break
            yield line.rstrip("\n").rstrip("\r")


def _normalize_for_uniqueness(s: str) -> str:
    s = s.strip()
    s = _LORA_RE.sub("", s)
    s = s.lower()
    s = _WS_RE.sub(" ", s)
    return s


def _classify(ext: str, avg_len: float, max_len: int, comma_rate: float,
              marker_hits: int, lora_hits: int, unique_sampled: int, nonempty: int) -> tuple[str, list[str]]:
    notes: list[str] = []

    if ext in (".yaml", ".yml", ".json"):
        return "StructuredPack", ["Structured data file (convertable)"]

    # Prompt soup signals
    if marker_hits > 0:
        notes.append(f"pollution_markers={marker_hits}")
    if lora_hits > 0:
        notes.append(f"lora_tags={lora_hits}")

    prompt_soup_score = 0
    if avg_len >= 120:
        prompt_soup_score += 2
    elif avg_len >= 80:
        prompt_soup_score += 1
    if max_len >= 500:
        prompt_soup_score += 2
    elif max_len >= 250:
        prompt_soup_score += 1
    if comma_rate >= 2.5:
        prompt_soup_score += 2
    elif comma_rate >= 1.2:
        prompt_soup_score += 1
    if marker_hits >= 3:
        prompt_soup_score += 2
    elif marker_hits >= 1:
        prompt_soup_score += 1
    if lora_hits >= 1:
        prompt_soup_score += 1

    # Name dump signals: many unique short lines, low punctuation
    name_dump_score = 0
    if avg_len <= 28:
        name_dump_score += 1
    if comma_rate <= 0.15:
        name_dump_score += 1
    if nonempty >= 500 and unique_sampled >= min(400, nonempty):
        name_dump_score += 2
    elif nonempty >= 200 and unique_sampled >= min(160, nonempty):
        name_dump_score += 1

    if prompt_soup_score >= 4:
        return "PromptSoup", notes or ["Long/mixed prompt lines likely"]

    if name_dump_score >= 3:
        return "NameDump", notes or ["Likely name list / dump"]

    # Otherwise: treat as clean-ish tags / phrases
    bucket = "CleanTags"
    if avg_len > 60:
        notes.append("avg_len_high_for_tags")
    if comma_rate > 0.8:
        notes.append("comma_heavy")
    return bucket, notes


def scan_file(fp: Path, sample_unique_cap: int = 5000) -> FileStats:
    ext = fp.suffix.lower()
    size = fp.stat().st_size

    lines = 0
    nonempty = 0
    total_len = 0
    max_len = 0
    comma_total = 0
    marker_hits = 0
    lora_hits = 0

    # uniqueness: we keep a capped set to avoid RAM blowups on giant lists
    unique_norm = set()

    for raw in _iter_text_lines(fp):
        lines += 1
        s = raw.strip()
        if not s:
            continue
        nonempty += 1
        L = len(s)
        total_len += L
        if L > max_len:
            max_len = L
        comma_total += s.count(",")

        low = s.lower()
        for m in POLLUTION_MARKERS:
            if m in low:
                marker_hits += 1
        if "<lora:" in low:
            lora_hits += 1

        if len(unique_norm) < sample_unique_cap:
            unique_norm.add(_normalize_for_uniqueness(s))

    avg_len = (total_len / nonempty) if nonempty else 0.0
    comma_rate = (comma_total / nonempty) if nonempty else 0.0
    bucket, notes = _classify(
        ext=ext,
        avg_len=avg_len,
        max_len=max_len,
        comma_rate=comma_rate,
        marker_hits=marker_hits,
        lora_hits=lora_hits,
        unique_sampled=len(unique_norm),
        nonempty=nonempty,
    )

    return FileStats(
        path=str(fp),
        ext=ext,
        bytes=size,
        lines=lines,
        nonempty_lines=nonempty,
        unique_sampled=len(unique_norm),
        avg_len=round(avg_len, 2),
        max_len=max_len,
        comma_rate=round(comma_rate, 2),
        marker_hits=marker_hits,
        lora_hits=lora_hits,
        bucket=bucket,
        notes=notes,
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--inbox",
        default=None,
        help="Inbox directory to scan (defaults to wildcards_curvy_exotic/CURSOR__/custom_wildcards).",
    )
    ap.add_argument(
        "--out",
        default=None,
        help="Output JSON report path (defaults to wildcards_curvy_exotic/CURSOR__/reports/inbox_scan_report.json).",
    )
    ap.add_argument(
        "--max-files",
        type=int,
        default=5000,
        help="Safety limit for number of files to scan.",
    )
    args = ap.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    inbox = Path(args.inbox) if args.inbox else (repo_root / "wildcards_curvy_exotic" / "CURSOR__" / "custom_wildcards")
    out_path = Path(args.out) if args.out else (repo_root / "wildcards_curvy_exotic" / "CURSOR__" / "reports" / "inbox_scan_report.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not inbox.exists():
        raise SystemExit(f"Inbox not found: {inbox}")

    files = [p for p in inbox.rglob("*") if p.is_file()]
    files.sort(key=lambda p: p.stat().st_size, reverse=True)
    if len(files) > args.max_files:
        files = files[: args.max_files]

    results: list[FileStats] = []
    bucket_counts: Dict[str, int] = {}

    for fp in files:
        st = scan_file(fp)
        results.append(st)
        bucket_counts[st.bucket] = bucket_counts.get(st.bucket, 0) + 1

    payload = {
        "inbox": str(inbox),
        "file_count": len(results),
        "bucket_counts": bucket_counts,
        "results": [asdict(r) for r in results],
    }

    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # Print a short human summary
    print("[scan_wildcard_inbox] Done")
    print(f"  inbox: {inbox}")
    print(f"  report: {out_path}")
    for k in sorted(bucket_counts.keys()):
        print(f"  {k}: {bucket_counts[k]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

