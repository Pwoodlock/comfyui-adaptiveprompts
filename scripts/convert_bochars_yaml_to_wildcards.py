"""
Convert "billions_of_characters.yaml" (BoChars) into cc-prompt-studio .txt wildcards.

Input:  wildcards_curvy_exotic/CURSOR__/billions_of_characters.yaml
Output: wildcards_curvy_exotic/**.txt  (BoChars/, clothings/, random/, etc.)

Also rewrites BoChars-style weighted bracket syntax:
  {0.45::A|0.45::B|0.1::C}
into cc-prompt-studio bracket-choice weights:
  {A%0.45|B%0.45|C%0.1}

Notes:
- Output is intentionally local-only; repo .gitignore ignores wildcard contents.
- This is a best-effort conversion; any lines that already use cc-prompt-studio syntax are left unchanged.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable


_BO_WEIGHT_OPT_RE = re.compile(r"^\s*([0-9]*\.?[0-9]+)\s*::\s*(.*)\s*$", re.DOTALL)


def _rewrite_bochars_weight_brackets(text: str) -> str:
    """
    Rewrite occurrences of {w::opt|w::opt|...} into {opt%w|opt%w|...}.
    Rewrites any top-level choices inside braces that match the w::opt pattern.
    Unweighted (or empty) choices are preserved.
    """
    if "{" not in text or "::" not in text:
        return text

    out = []
    i = 0
    n = len(text)
    while i < n:
        if text[i] != "{":
            out.append(text[i])
            i += 1
            continue

        # find matching } at the same nesting level
        depth = 0
        j = i
        while j < n:
            c = text[j]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        if j >= n or text[j] != "}":
            # unmatched, append rest
            out.append(text[i:])
            break

        inner = text[i + 1 : j]

        # Split on top-level | (no nested support needed for this pack; keep it simple)
        parts = inner.split("|")
        converted = []
        changed_any = False
        for p in parts:
            m = _BO_WEIGHT_OPT_RE.match(p)
            if not m:
                converted.append(p.strip())
                continue
            w = m.group(1)
            opt = m.group(2).strip()
            changed_any = True
            # Keep empty option as empty (rare)
            if opt:
                converted.append(f"{opt}%{w}")
            else:
                converted.append("")

        if changed_any:
            out.append("{" + "|".join(converted) + "}")
        else:
            out.append("{" + inner + "}")

        i = j + 1

    return "".join(out)


def _iter_leaf_lists(obj: Any, path_parts: list[str]) -> Iterable[tuple[list[str], list[str]]]:
    """
    Yield (path_parts, values) for each leaf list[str] found in obj.
    """
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
        values: list[str] = []
        for item in obj:
            if item is None:
                continue
            s = str(item).replace("\r", "").strip()
            if not s:
                continue
            s = _rewrite_bochars_weight_brackets(s)
            values.append(s)
        if values:
            yield (path_parts, values)
        return

    return


def _safe_relpath(parts: list[str]) -> Path:
    """
    BoChars keys are simple (no embedded / paths typically), but we still normalize.
    """
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
    try:
        import yaml  # type: ignore
    except Exception as exc:
        raise SystemExit(f"PyYAML is required but not available: {exc}")

    repo_root = Path(__file__).resolve().parents[1]
    src = repo_root / "wildcards_curvy_exotic" / "CURSOR__" / "billions_of_characters.yaml"
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
        dst = out_root / (str(rel) + ".txt")
        dst.parent.mkdir(parents=True, exist_ok=True)
        with dst.open("w", encoding="utf-8", newline="\n") as wf:
            for v in values:
                wf.write(v + "\n")
        written += 1

    print(f"[convert_bochars_yaml_to_wildcards] Wrote {written} files under {out_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

