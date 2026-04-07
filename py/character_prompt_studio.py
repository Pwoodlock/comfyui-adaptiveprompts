"""
Character Prompt Studio - Unified Prompt Generation Node

Combines functionality from multiple Adaptive Prompts nodes into one unified interface:
- Wildcard resolution (from PromptGenerator)
- Tag shuffling (from PromptShuffle)
- Tag deduplication (from PromptCleanup)
- Comment hiding (from PromptGeneratorAdvanced)
- Text cleanup (from PromptCleanup)

Design principle: Reuse existing code rather than rewriting to make
updates/refactoring easier.
"""

import os
import re
import random
from typing import List, Tuple, Dict

# Import existing functionality - reuse, don't rewrite!
from .generator import resolve_wildcards, SeededRandom
from .wildcard_utils import (
    build_category_options,
    _normalize_input_context,
    _ensure_bucket_dict,
    _default_package_root
)

# Import cleanup functions from string_utils
from .string_utils import PromptCleanup


class CharacterPromptStudio:
    """
    Unified Character Prompt Generation Node

    Combines wildcard expansion, shuffling, deduplication, and cleanup
    in a single node with discoverable wildcard categories.
    """

    def __init__(self):
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        self.input_dir = os.path.join(base_dir, "wildcards")

    @classmethod
    def _scan_wildcard_categories(cls) -> Dict[str, List[str]]:
        """
        Scan wildcard directory to build category->files mapping.

        Returns:
            Dict mapping category names to lists of wildcard filenames
        """
        base_dir = _default_package_root()
        wildcard_dir = os.path.join(base_dir, "wildcards")

        categories = {}

        if not os.path.exists(wildcard_dir):
            return categories

        # Scan each subdirectory
        for category_name in sorted(os.listdir(wildcard_dir)):
            category_path = os.path.join(wildcard_dir, category_name)
            if not os.path.isdir(category_path):
                continue

            # Get all .txt files in this category
            files = []
            for filename in sorted(os.listdir(category_path)):
                if filename.endswith('.txt'):
                    # Remove .txt extension for display
                    files.append(filename[:-4])

            if files:
                categories[category_name] = files

        return categories

    @classmethod
    def INPUT_TYPES(cls):
        # Build shared label list for wildcard folders
        labels, mapping, tooltip = build_category_options()
        cls._CATEGORY_LABELS = labels
        cls._CATEGORY_MAP = mapping

        # Scan for available wildcard categories
        categories = cls._scan_wildcard_categories()
        category_list = list(categories.keys()) if categories else ["None"]
        category_list.sort()

        # Build tooltip showing available categories
        category_tooltip = "Available wildcard categories:\n" + "\n".join(f"- {cat}" for cat in category_list[:10])
        if len(category_list) > 10:
            category_tooltip += f"\n... and {len(category_list) - 10} more"

        return {
            "required": {
                "prompt": ("STRING", {
                    "multiline": True,
                    "default": "",
                    "tooltip": "Main prompt. Use __category/file__ syntax."
                }),
                "seed": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 0xffffffffffffffff,
                    "tooltip": "Random seed for deterministic output"
                }),
            },
            "optional": {
                # Action button - set to TRUE to refresh
                "refresh": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "🔄 Click to refresh wildcard cache after adding new files/folders"
                }),

                # Wildcard category browser (shows available categories)
                "wc_category": (category_list, {
                    "default": category_list[0] if category_list else "",
                    "tooltip": category_tooltip
                }),

                # Processing Options
                "hide_comments": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "Remove ## comment ## blocks from output"
                }),
                "shuffle_tags": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "Randomize tag order"
                }),
                "shuffle_amount": ("INT", {
                    "default": 5,
                    "min": 0,
                    "max": 100,
                    "tooltip": "Number of shuffle moves (0 = full shuffle)"
                }),
                "deduplicate": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "Remove duplicate tags"
                }),
                "cleanup_commas": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "Clean up extra commas"
                }),
                "cleanup_whitespace": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "Clean up extra whitespace"
                }),

                # Wildcard folder selection
                "wildcard_folder": (labels, {
                    "default": labels[0] if labels else "Default",
                    "tooltip": tooltip
                }),

                # Context chaining (compatible with other Adaptive Prompts nodes)
                "context": ("DICT", {}),
            }
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("prompt", "wildcards_used", "categories_list")
    FUNCTION = "process"
    CATEGORY = "cc-prompt-studio/generation"

    def _shuffle_tags(self, text: str, amount: int, seed: int) -> str:
        """
        Shuffle tags using PromptShuffle logic (reused).

        Args:
            text: Prompt text to shuffle
            amount: Number of shuffle moves (0 = full shuffle)
            seed: Random seed

        Returns:
            Shuffled text
        """
        # Reuse PromptShuffle shuffle_strings logic
        rng = random.Random(seed) if seed != 0 else random.Random()
        separator = ","

        parts = text.split(separator)
        n = len(parts)

        if n <= 1:
            return text

        if amount <= 0:
            # Full shuffle
            rng.shuffle(parts)
            return separator.join(parts)

        # Limited shuffle - perform `amount` single-item moves
        moves_done = 0
        attempts = 0
        max_attempts = amount * 10 + 100

        while moves_done < amount and attempts < max_attempts:
            attempts += 1
            src = rng.randrange(n)
            dest = rng.randrange(n)
            if src == dest:
                continue

            item = parts.pop(src)
            if src < dest:
                dest -= 1
            parts.insert(dest, item)
            moves_done += 1

        return separator.join(parts)

    def _deduplicate_tags(self, text: str) -> str:
        """
        Remove duplicate tags while preserving order.

        Args:
            text: Prompt text

        Returns:
            Text with duplicates removed
        """
        tags = [t.strip() for t in text.split(',')]
        seen = set()
        unique = []
        for tag in tags:
            if tag and tag not in seen:
                seen.add(tag)
                unique.append(tag)
        return ', '.join(unique)

    def _track_wildcards_used(self, text: str) -> str:
        """
        Extract all wildcard references from text for display.

        Args:
            text: Prompt text

        Returns:
            String listing all wildcards used
        """
        pattern = r'__([a-zA-Z0-9_\-/*^]+?)__'
        matches = re.findall(pattern, text)
        if matches:
            return ', '.join(set(matches))
        return ""

    def process(
        self,
        prompt: str,
        seed: int,
        refresh: bool = False,
        wc_category: str = "",
        hide_comments: bool = True,
        shuffle_tags: bool = False,
        shuffle_amount: int = 5,
        deduplicate: bool = True,
        cleanup_commas: bool = True,
        cleanup_whitespace: bool = True,
        wildcard_folder: str = None,
        context: dict = None
    ) -> Tuple[str, str]:
        """
        Process prompt with all enabled options.

        Args:
            prompt: Input prompt text
            seed: Random seed
            refresh: If TRUE, clears cache and rescans wildcard folders
            wc_category: Selected wildcard category (for info only)
            hide_comments: Remove comment blocks
            shuffle_tags: Enable tag shuffling
            shuffle_amount: Number of shuffle moves
            deduplicate: Remove duplicate tags
            cleanup_commas: Clean up extra commas
            cleanup_whitespace: Clean up whitespace
            wildcard_folder: Wildcard folder to use
            context: Variable context from previous nodes

        Returns:
            (processed_prompt, wildcards_used, categories_list)
        """
        # Handle wildcard refresh when refresh button is clicked
        if refresh:
            from .wildcard_utils import clear_category_cache
            clear_category_cache()
            # Also clear our cached categories
            if hasattr(self.__class__, '_WILDCARD_CATEGORIES'):
                delattr(self.__class__, '_WILDCARD_CATEGORIES')

        # Build categories list (always fresh when refresh=True)
        categories = self._scan_wildcard_categories()
        categories_list = "📁 Wildcard Categories:\n"
        for cat, files in sorted(categories.items()):
            categories_list += f"  • {cat}: {len(files)} files\n"

        rng = SeededRandom(seed)

        # Normalize incoming context
        normalized_context = _normalize_input_context(context)

        # Determine wildcard folder to use
        folder_map = getattr(self.__class__, "_CATEGORY_MAP", {})
        folder_name = folder_map.get(wildcard_folder, "wildcards")

        # Track wildcards used in original prompt
        wildcards_used = self._track_wildcards_used(prompt)

        # Handle comment blocks first (they get processed but not shown)
        comment_blocks = re.findall(r"##(.*?)##", prompt, flags=re.DOTALL)
        for block in comment_blocks:
            _ = resolve_wildcards(block, rng, folder_name, _resolved_vars=normalized_context)

        # Remove comments if requested
        if hide_comments:
            prompt = re.sub(r"##.*?##", "", prompt, flags=re.DOTALL)

        # Resolve wildcards (reuse existing function)
        result = resolve_wildcards(prompt, rng, folder_name, _resolved_vars=normalized_context)

        # Apply processing options in order
        if deduplicate:
            result = self._deduplicate_tags(result)

        if shuffle_tags:
            result = self._shuffle_tags(result, shuffle_amount, seed)

        # Cleanup using PromptCleanup logic (reuse existing)
        # Note: PromptCleanup.process returns a tuple (string,), so we extract the first element
        if cleanup_commas or cleanup_whitespace:
            cleaned = PromptCleanup.process(
                result,
                cleanup_commas=cleanup_commas,
                cleanup_newlines="false",
                cleanup_whitespace=cleanup_whitespace,
                remove_lora_tags=False,
                fix_brackets="false"
            )
            # PromptCleanup returns a tuple, extract the string
            result = cleaned[0] if isinstance(cleaned, tuple) else cleaned

        # Ensure context buckets are normalized
        for k, v in list(normalized_context.items()):
            if not isinstance(v, dict):
                normalized_context[k] = _ensure_bucket_dict(v)

        return (result, wildcards_used, categories_list)


# For compatibility with wildcard dropdown updates
def clear_category_cache():
    """Clear the cached wildcard categories (call after adding new wildcards)."""
    if hasattr(CharacterPromptStudio, '_WILDCARD_CATEGORIES'):
        delattr(CharacterPromptStudio, '_WILDCARD_CATEGORIES')
    if hasattr(CharacterPromptStudio, '_CATEGORY_MAP'):
        delattr(CharacterPromptStudio, '_CATEGORY_MAP')
