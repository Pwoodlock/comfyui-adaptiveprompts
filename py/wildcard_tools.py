"""
Wildcard Tools Node

ComfyUI node for wildcard text processing operations.
Clean, format, deduplicate, and save wildcard files directly from the UI.
"""

import os
import re
from pathlib import Path
from typing import List, Tuple, Set


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
        self.presets_dir = os.path.join(base_dir, "wildcards", "my_presets")
        # Ensure directory exists
        Path(self.presets_dir).mkdir(parents=True, exist_ok=True)

    @classmethod
    def INPUT_TYPES(cls):
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
            # Clean filename
            filename = re.sub(r'[^\w\-_]', '_', filename)
            if not filename.endswith('.txt'):
                filename = f"{filename}.txt"

            filepath = os.path.join(self.presets_dir, filename)
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
        self.presets_dir = os.path.join(base_dir, "wildcards", "my_presets")
        Path(self.presets_dir).mkdir(parents=True, exist_ok=True)

    @classmethod
    def INPUT_TYPES(cls):
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
        case_sensitive: bool = False,
        match_all: bool = False
    ) -> Tuple[str, str, int]:
        """Search wildcard files for keywords."""
        # Parse keywords
        keyword_list = [k.strip() for k in keywords.split(',') if k.strip()]

        if not keyword_list:
            return ("", "No keywords provided", 0)

        wildcard_dir = os.path.join(self.base_dir, "wildcards")
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
            filename = re.sub(r'[^\w\-_]', '_', save_filename)
            if not filename.endswith('.txt'):
                filename = f"{filename}.txt"

            filepath = os.path.join(self.presets_dir, filename)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(result_text)

            summary += f" | Saved to: my_presets/{filename}"

        return (result_text, summary, len(result_list))
