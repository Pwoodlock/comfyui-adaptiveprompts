"""
Wildcard Tools Node

ComfyUI node for wildcard text processing operations.
Clean, format, deduplicate, and save wildcard files directly from the UI.
"""

import os
import re
from pathlib import Path
from typing import List, Tuple, Set

from .generator import SeededRandom, process_file_wildcard
from .wildcard_utils import build_category_options, _default_package_root


class WildcardTools:
    """
    Wildcard text processing node.

    Operations:
    - Clean formatting (commas, whitespace)
    - Remove duplicates
    - Sort alphabetically
    - Save to my_presets/ folder
    """

    def __init__(self):
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        # Default presets location (can be overridden per wildcard set at runtime)
        self._package_root = base_dir
        self.presets_dir = os.path.join(base_dir, "wildcards", "my_presets")
        # Ensure directory exists
        Path(self.presets_dir).mkdir(parents=True, exist_ok=True)

    @classmethod
    def INPUT_TYPES(cls):
        labels, mapping, tooltip = build_category_options()
        cls._CATEGORY_LABELS = labels
        cls._CATEGORY_MAP = mapping
        return {
            "required": {
                "input_text": ("STRING", {
                    "multiline": True,
                    "default": "",
                    "tooltip": "Raw wildcard text or prompt tags to process"
                }),
                "operation": ([
                    "clean_only",
                    "deduplicate",
                    "sort",
                    "clean_dedupe",
                    "clean_dedupe_sort",
                    "extract_unique",
                    "extract_and_sort"
                ], {
                    "default": "clean_dedupe_sort",
                    "tooltip": "Operation to perform on input text"
                }),
            },
            "optional": {
                "separator": ("STRING", {
                    "default": ",",
                    "tooltip": "Separator between tags (default: comma)"
                }),
                "wildcard_folder": (labels, {
                    "default": labels[0] if labels else "wildcards",
                    "tooltip": tooltip
                }),
                "save_to_file": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "Save results to my_presets/ folder"
                }),
                "filename": ("STRING", {
                    "default": "my_wildcards",
                    "tooltip": "Filename (without .txt) when saving"
                }),
            }
        }

    RETURN_TYPES = ("STRING", "STRING", "INT")
    RETURN_NAMES = ("processed_text", "stats", "count")
    FUNCTION = "process"
    CATEGORY = "cc-prompt-studio/utils"

    def _clean_text(self, text: str, separator: str = ",") -> str:
        """Clean up formatting issues."""
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        # Fix comma spacing
        text = re.sub(r'\s*,\s*', f'{separator} ', text)
        # Remove leading/trailing separators
        text = text.strip(f'{separator} ')
        # Remove empty entries
        parts = [p.strip() for p in text.split(separator) if p.strip()]
        return f'{separator} '.join(parts)

    def _deduplicate(self, text: str, separator: str = ",") -> Tuple[str, int]:
        """Remove duplicate tags while preserving order."""
        parts = [p.strip() for p in text.split(separator)]
        seen: Set[str] = set()
        unique: List[str] = []
        duplicates = 0

        for part in parts:
            if part and part not in seen:
                seen.add(part)
                unique.append(part)
            elif part:
                duplicates += 1

        result = f'{separator} '.join(unique)
        return result, duplicates

    def _sort(self, text: str, separator: str = ",") -> str:
        """Sort tags alphabetically (case-insensitive)."""
        parts = [p.strip() for p in text.split(separator) if p.strip()]
        parts.sort(key=lambda x: x.lower())
        return f'{separator} '.join(parts)

    def _extract_unique(self, text: str, separator: str = ",") -> Tuple[str, int]:
        """Extract unique tags from messy text."""
        # Split on common separators
        parts = re.split(r'[,;\n]+', text)
        seen: Set[str] = set()
        unique: List[str] = []

        for part in parts:
            part = part.strip()
            if part and part not in seen:
                seen.add(part)
                unique.append(part)

        result = f'{separator} '.join(unique)
        return result, len(unique)

    def process(
        self,
        input_text: str,
        operation: str,
        separator: str = ",",
        wildcard_folder: str = "wildcards",
        save_to_file: bool = False,
        filename: str = "my_wildcards"
    ) -> Tuple[str, str, int]:
        """
        Process wildcard text.

        Args:
            input_text: Raw input text
            operation: Operation to perform
            separator: Tag separator
            save_to_file: If True, save to my_presets/
            filename: Output filename

        Returns:
            (processed_text, stats, count)
        """
        if not input_text:
            return ("", "No input text", 0)

        original_count = len([t for t in re.split(r'[,;\n]+', input_text) if t.strip()])
        result = input_text
        duplicates_removed = 0
        operations_performed = []

        # Apply operation
        if operation == "clean_only":
            result = self._clean_text(result, separator)
            operations_performed.append("cleaned")

        elif operation == "deduplicate":
            result, duplicates_removed = self._deduplicate(result, separator)
            operations_performed.append(f"deduplicated ({duplicates_removed} removed)")

        elif operation == "sort":
            result = self._sort(result, separator)
            operations_performed.append("sorted")

        elif operation == "clean_dedupe":
            result = self._clean_text(result, separator)
            result, duplicates_removed = self._deduplicate(result, separator)
            operations_performed.append(f"cleaned, deduplicated ({duplicates_removed} removed)")

        elif operation == "clean_dedupe_sort":
            result = self._clean_text(result, separator)
            result, duplicates_removed = self._deduplicate(result, separator)
            result = self._sort(result, separator)
            operations_performed.append(f"cleaned, deduplicated ({duplicates_removed} removed), sorted")

        elif operation == "extract_unique":
            result, final_count = self._extract_unique(result, separator)
            operations_performed.append(f"extracted {final_count} unique tags")

        elif operation == "extract_and_sort":
            result, final_count = self._extract_unique(result, separator)
            result = self._sort(result, separator)
            operations_performed.append(f"extracted {final_count} unique tags, sorted")

        # Count final result
        final_count = len([t for t in result.split(separator) if t.strip()])

        # Build stats
        stats = f"Original: {original_count} | Final: {final_count}"
        if operations_performed:
            stats += f" | Operations: {', '.join(operations_performed)}"

        # Save to file if requested
        if save_to_file and result:
            # Resolve presets dir for selected wildcard set (defaults to package-root wildcards/)
            folder_map = getattr(self.__class__, "_CATEGORY_MAP", {}) or {}
            wildcard_root = folder_map.get(wildcard_folder) or os.path.join(self._package_root, "wildcards")
            presets_dir = os.path.join(wildcard_root, "my_presets")
            Path(presets_dir).mkdir(parents=True, exist_ok=True)

            # Clean filename
            filename = re.sub(r'[^\w\-_]', '_', filename)
            if not filename.endswith('.txt'):
                filename = f"{filename}.txt"

            filepath = os.path.join(presets_dir, filename)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(result)

            stats += f" | Saved to: my_presets/{filename}"

        return (result, stats, final_count)


class WildcardSearchExtract:
    """
    Search through existing wildcard files and extract matching lines.
    """

    def __init__(self):
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        self.base_dir = base_dir

    @classmethod
    def INPUT_TYPES(cls):
        labels, mapping, tooltip = build_category_options()
        cls._CATEGORY_LABELS = labels
        cls._CATEGORY_MAP = mapping
        return {
            "required": {
                "keywords": ("STRING", {
                    "multiline": True,
                    "default": "bbw, chubby, curvy",
                    "tooltip": "Comma-separated keywords to search for"
                }),
                "save_filename": ("STRING", {
                    "default": "extracted",
                    "tooltip": "Filename (without .txt) for extracted results"
                }),
            },
            "optional": {
                "wildcard_folder": (labels, {
                    "default": labels[0] if labels else "wildcards",
                    "tooltip": tooltip
                }),
                "case_sensitive": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "Match case (default: false)"
                }),
                "match_all": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "Only return lines containing ALL keywords (default: any keyword)"
                }),
            }
        }

    RETURN_TYPES = ("STRING", "STRING", "INT")
    RETURN_NAMES = ("extracted_text", "summary", "match_count")
    FUNCTION = "search"
    CATEGORY = "cc-prompt-studio/utils"

    def search(
        self,
        keywords: str,
        save_filename: str,
        wildcard_folder: str = "wildcards",
        case_sensitive: bool = False,
        match_all: bool = False
    ) -> Tuple[str, str, int]:
        """Search wildcard files for keywords."""
        # Parse keywords
        keyword_list = [k.strip() for k in keywords.split(',') if k.strip()]

        if not keyword_list:
            return ("", "No keywords provided", 0)

        folder_map = getattr(self.__class__, "_CATEGORY_MAP", {}) or {}
        wildcard_dir = folder_map.get(wildcard_folder) or os.path.join(self.base_dir, "wildcards")
        matches: Set[str] = set()

        # Search through all .txt files (except my_presets)
        for txt_file in Path(wildcard_dir).rglob("*.txt"):
            # Skip my_presets and log files
            if "my_presets" in str(txt_file) or "log" in txt_file.name.lower():
                continue

            try:
                with open(txt_file, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue

                        search_line = line if case_sensitive else line.lower()

                        # Check if line matches keywords
                        keyword_checks = [
                            kw.lower() if not case_sensitive else kw
                            for kw in keyword_list
                        ]

                        if match_all:
                            # Must contain ALL keywords
                            if all(kw in search_line for kw in keyword_checks):
                                matches.add(line)
                        else:
                            # Must contain ANY keyword
                            if any(kw in search_line for kw in keyword_checks):
                                matches.add(line)

            except Exception as e:
                pass  # Skip unreadable files

        # Convert to sorted list
        result_list = sorted(matches)
        result_text = "\n".join(result_list)

        # Build summary
        summary = f"Keywords: {', '.join(keyword_list)} | Mode: {'ALL' if match_all else 'ANY'} | Matches: {len(result_list)}"

        # Save to file
        if result_list:
            presets_dir = os.path.join(wildcard_dir, "my_presets")
            Path(presets_dir).mkdir(parents=True, exist_ok=True)
            filename = re.sub(r'[^\w\-_]', '_', save_filename)
            if not filename.endswith('.txt'):
                filename = f"{filename}.txt"

            filepath = os.path.join(presets_dir, filename)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(result_text)

            summary += f" | Saved to: my_presets/{filename}"

        return (result_text, summary, len(result_list))


class WildcardPreview:
    """
    Preview outputs of a wildcard token quickly (sampling).

    This is meant to speed up creative iteration: you can explore what a wildcard
    file or folder wildcard will yield without digging through files.
    """

    @classmethod
    def INPUT_TYPES(cls):
        labels, mapping, tooltip = build_category_options()
        cls._CATEGORY_LABELS = labels
        cls._CATEGORY_MAP = mapping

        return {
            "required": {
                "wildcard_token": ("STRING", {
                    "default": "__wildcards/example__",
                    "tooltip": "Wildcard token to preview. Examples: __cats/poses__, __styles/*__, __styles/prefix*__"
                }),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
                "samples": ("INT", {"default": 10, "min": 1, "max": 200}),
                "wildcard_folder": (labels, {
                    "default": labels[0] if labels else "wildcards",
                    "tooltip": tooltip
                }),
            },
            "optional": {
                "deduplicate": ("BOOLEAN", {"default": True, "tooltip": "Remove duplicate sample lines"}),
                "show_indices": ("BOOLEAN", {"default": True, "tooltip": "Prefix lines with 1..N"}),
            }
        }

    RETURN_TYPES = ("STRING", "INT")
    RETURN_NAMES = ("preview", "unique_count")
    FUNCTION = "preview"
    CATEGORY = "cc-prompt-studio/utils"

    @staticmethod
    def _normalize_token(token: str) -> str:
        t = (token or "").strip()
        if t.startswith("__") and t.endswith("__") and len(t) >= 4:
            t = t[2:-2]
        # tokens can be written as __cat/file__ or cat/file
        return t.strip().strip("/")

    def preview(self, wildcard_token: str, seed: int, samples: int, wildcard_folder: str,
                deduplicate: bool = True, show_indices: bool = True):
        token = self._normalize_token(wildcard_token)
        if not token:
            return ("", 0)

        folder_map = getattr(self.__class__, "_CATEGORY_MAP", {}) or {}
        wildcard_root = folder_map.get(wildcard_folder)
        if not wildcard_root:
            wildcard_root = os.path.join(_default_package_root(), "wildcards")

        rng = SeededRandom(seed)
        out: List[str] = []
        for _ in range(int(samples)):
            picked = process_file_wildcard(token, rng.next_rng(), wildcard_root, bracket_ctx=None)
            if picked is None:
                picked = ""
            picked = str(picked).strip()
            if picked:
                out.append(picked)

        if deduplicate:
            # preserve order while dropping dupes
            seen = set()
            unique = []
            for s in out:
                if s not in seen:
                    seen.add(s)
                    unique.append(s)
            out = unique

        if show_indices:
            text = "\n".join(f"{i+1}. {s}" for i, s in enumerate(out))
        else:
            text = "\n".join(out)

        return (text, len(out))
