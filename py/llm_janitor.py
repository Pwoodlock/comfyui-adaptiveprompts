"""
CCLLMJanitor - LLM-Powered Wildcard Cleanup Node

Uses LM Studio (Gemma 4 or other models) to intelligently clean,
merge, validate, and deduplicate wildcard files.
"""

import os
import re
import shutil
import json
from datetime import datetime
from pathlib import Path
from typing import List, Tuple, Dict

from .lm_studio_client import (
    get_lm_studio_models,
    call_lm_studio,
    is_sdk_available,
    get_sdk_error
)


class CCLLMJanitor:
    """
    LLM-powered wildcard cleanup and organization node.

    Features:
    - Probe LM Studio for available models
    - Pre-defined cleanup contexts (basic, nsfw, merge, deduplicate, quality_check)
    - Custom instructions
    - Backup creation before modifications
    - Dry-run mode for previewing changes
    """

    # LORA pattern to remove
    LORA_PATTERN = re.compile(r'<lora:[^>]+>', re.IGNORECASE)

    # Operation templates
    OPERATIONS = {
        "basic_cleanup": {
            "system": "You are a wildcard file cleaner. Your job is to clean up prompt text.",
            "instructions": "Remove these from each line:\n- LoRA tags like <:lora:model:1.0>\n- Extra commas and punctuation\n- Excessive whitespace\n- Empty lines\n\nReturn the cleaned lines, one per line, separated by |."
        },
        "nsfw_cleanup": {
            "system": "You are a wildcard file cleaner for NSFW/adult content.",
            "instructions": "Clean up these prompts:\n- Remove all LoRA tags\n- Remove 'unsafe', 'nsfw', 'sensitive' warnings\n- Fix CivitAI syntax issues\n- Standardize to comma-separated format\n\nReturn cleaned lines, separated by |."
        },
        "merge_consolidate": {
            "system": "You are a wildcard file organizer. Group these prompts into logical categories.",
            "instructions": "Analyze these prompts and organize them into themed groups. Return JSON with category names and arrays of prompts.\n\nFormat: {\"category1\": [\"prompt1\", \"prompt2\"], \"category2\": [\"prompt3\", \"prompt4\"]}"
        },
        "deduplicate": {
            "system": "You are a duplicate detector. Remove duplicate and near-duplicate prompts.",
            "instructions": "Find and remove duplicate or very similar prompts. Keep only unique prompts. Return unique prompts, one per line, separated by |."
        },
        "quality_check": {
            "system": "You are a prompt quality validator.",
            "instructions": "Analyze these prompts for quality issues. Identify:\n- Vague or low-quality prompts\n- Missing key details\n- Poor tag ordering\n\nReturn analysis with line numbers and issues."
        },
        "custom": {
            "system": "You are a wildcard file assistant. Follow the user's custom instructions.",
            "instructions": "{user_custom_context}"
        }
    }

    @classmethod
    def INPUT_TYPES(cls):
        # Get available models from LM Studio
        models = cls._get_cached_models()
        model_list = models if models else ["(No LM Studio running)"]

        return {
            "required": {
                "wildcard_folder": ("STRING", {
                    "default": "",
                    "tooltip": "Wildcard folder to process (relative to wildcards/)"
                }),
                "operation": (list(cls.OPERATIONS.keys()), {
                    "default": "basic_cleanup",
                    "tooltip": "Select cleanup operation type"
                }),
            },
            "optional": {
                # LLM Settings
                "llm_model": (model_list, {
                    "default": model_list[0] if model_list else "default",
                    "tooltip": "LM Studio model to use"
                }),
                "refresh_models": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "Click to refresh available models from LM Studio"
                }),

                # Context/Template
                "custom_context": ("STRING", {
                    "default": "",
                    "multiline": True,
                    "tooltip": "Custom LLM instructions (when operation=custom)"
                }),

                # Processing Options
                "dry_run": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "Preview changes without writing files"
                }),
                "backup": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "Create backup before modifying"
                }),

                # Output options
                "output_suffix": ("STRING", {
                    "default": "_cleaned",
                    "tooltip": "Suffix for output folder (default: _cleaned)"
                }),
            }
        }

    RETURN_TYPES = ("STRING", "STRING", "INT")
    RETURN_NAMES = ("summary", "preview", "files_processed")
    FUNCTION = "process"
    CATEGORY = "cc-prompt-studio/utilities"

    # Model cache
    _models_cache = None
    _models_cache_time = 0

    @classmethod
    def _get_cached_models(cls) -> List[str]:
        """Get cached models or fetch if cache is old (>30 seconds)."""
        import time
        now = time.time()

        if cls._models_cache and (now - cls._models_cache_time < 30):
            return cls._models_cache

        # Fetch fresh models
        cls._models_cache = get_lm_studio_models()
        cls._models_cache_time = now
        return cls._models_cache

    @classmethod
    def _create_backup(cls, source_path: Path, backup_name: str) -> Path:
        """Create a backup of the source folder."""
        # Parent of wildcards is the cc-prompt-studio root
        root = source_path.parent.parent.parent  # Go up from wildcards/category/ to root
        backup_dir = root / "wildcard_backups" / backup_name

        try:
            backup_dir.mkdir(parents=True, exist_ok=True)
            shutil.copytree(source_path, backup_dir)
            return backup_dir
        except Exception as exc:
            # If backup fails, create in alternative location
            alt_backup = source_path.parent / f"{backup_name}_backup"
            shutil.copytree(source_path, alt_backup)
            return alt_backup

    def _load_wildcard_file(self, filepath: Path) -> List[str]:
        """Load a wildcard file and return list of lines."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            return [line.strip() for line in lines if line.strip()]
        except Exception as exc:
            return []

    def _clean_lines_basic(self, lines: List[str]) -> List[str]:
        """Basic cleanup - regex-based, no LLM needed."""
        cleaned = []
        for line in lines:
            # Remove lora tags
            line = self.LORA_PATTERN.sub('', line)
            # Clean up whitespace
            line = re.sub(r'\s+', ' ', line)
            line = line.strip()
            # Remove trailing separators
            line = re.sub(r'[-=]{3,}$', '', line).strip()
            if line:
                cleaned.append(line)
        return cleaned

    def _build_llm_prompt(self, operation: str, lines: List[str]) -> str:
        """Build the LLM prompt based on operation type."""
        op_config = self.OPERATIONS.get(operation, self.OPERATIONS["custom"])

        # Prepare the prompt
        if operation == "custom":
            # Use custom context
            system_prompt = op_config["system"]
            instructions = self.custom_context or "Clean these wildcard prompts."
        else:
            system_prompt = op_config["system"]
            instructions = op_config["instructions"]

        # Limit input size for LLM
        sample_lines = lines[:500]  # First 500 lines
        input_text = "\n".join(sample_lines)

        user_prompt = f"""{instructions}

Here are the wildcard prompts to process (showing first 500):

{input_text}

{"rest": f"... and {len(lines) - 500} more lines"}"""

        return system_prompt, user_prompt

    def _parse_llm_response(self, response: str, operation: str) -> List[str]:
        """Parse LLM response based on operation type."""
        if not response:
            return []

        lines = response.strip().split('\n')

        if operation == "merge_consolidate":
            # Try to parse JSON response
            try:
                data = json.loads(response)
                if isinstance(data, dict):
                    # Flatten all categories into one list
                    result = []
                    for category_items in data.values():
                        if isinstance(category_items, list):
                            result.extend(category_items)
                    return result
            except json.JSONDecodeError:
                pass

        # Default: split by common separators
        result = []
        for line in lines:
            # Split by | or comma
            parts = re.split(r'[|,]', line)
            result.extend([p.strip() for p in parts if p.strip()])

        return result

    def process(
        self,
        wildcard_folder: str,
        operation: str,
        llm_model: str = "default",
        refresh_models: bool = False,
        custom_context: str = "",
        dry_run: bool = True,
        backup: bool = True,
        output_suffix: str = "_cleaned",
    ) -> Tuple[str, str, int]:
        """
        Process wildcard folder with LLM cleanup.

        Args:
            wildcard_folder: Folder name within wildcards/
            operation: Type of cleanup operation
            llm_model: Model to use
            refresh_models: Whether to refresh model list
            custom_context: Custom instructions for operation=custom
            dry_run: Preview without writing
            backup: Create backup before processing
            output_suffix: Suffix for output folder

        Returns:
            (summary, preview, files_processed)
        """
        # Refresh models if requested
        if refresh_models:
            self._models_cache = None
            self._models_cache_time = 0

        # Determine paths
        base_dir = Path(__file__).parent.parent
        wildcard_dir = base_dir / "wildcards" / wildcard_folder

        if not wildcard_dir.exists():
            return (f"Error: Folder '{wildcard_folder}' not found in wildcards/", "", 0)

        # Scan for files
        txt_files = list(wildcard_dir.glob("*.txt"))
        if not txt_files:
            return (f"Error: No .txt files found in {wildcard_folder}/", "", 0)

        # Create backup
        backup_path = None
        if backup and not dry_run:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = self._create_backup(wildcard_dir, f"{wildcard_folder}_{timestamp}")
        elif backup:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"Would create: wildcard_backups/{wildcard_folder}_{timestamp}/"

        # Collect all lines from all files
        all_lines = []
        for filepath in txt_files:
            lines = self._load_wildcard_file(filepath)
            all_lines.extend(lines)

        # For operations that don't need LLM (basic cleanup)
        if operation == "basic_cleanup":
            processed = self._clean_lines_basic(all_lines)
            preview_lines = processed[:10]
            summary = f"Basic cleanup: {len(all_lines)} lines → {len(processed)} lines"

            if not dry_run:
                # Write output
                output_dir = wildcard_dir.parent / f"{wildcard_folder}{output_suffix}"
                output_dir.mkdir(exist_ok=True)
                output_file = output_dir / "all_merged.txt"
                with open(output_file, 'w', encoding='utf-8') as f:
                    for line in processed:
                        f.write(line + '\n')

        # For LLM operations
        elif operation in ["nsfw_cleanup", "deduplicate", "quality_check", "custom"]:
            system_prompt, user_prompt = self._build_llm_prompt(operation, all_lines)

            # Call LLM
            response = call_lm_studio(
                model=llm_model,
                user_prompt=user_prompt,
                system_prompt=system_prompt
            )

            processed = self._parse_llm_response(response, operation)
            preview_lines = processed[:10] if processed else [response[:500]]
            summary = f"LLM {operation}: {len(all_lines)} lines → {len(processed)} results"

            if not dry_run:
                # Write output
                output_dir = wildcard_dir.parent / f"{wildcard_folder}{output_suffix}"
                output_dir.mkdir(exist_ok=True)
                output_file = output_dir / "result.txt"
                with open(output_file, 'w', encoding='utf-8') as f:
                    for line in processed:
                        f.write(line + '\n')

        # For merge operation
        elif operation == "merge_consolidate":
            system_prompt, user_prompt = self._build_llm_prompt(operation, all_lines)

            # Call LLM
            response = call_lm_studio(
                model=llm_model,
                user_prompt=user_prompt,
                system_prompt=system_prompt
            )

            # Try to parse as JSON
            try:
                data = json.loads(response)
                # Write categorized files
                output_dir = wildcard_dir.parent / f"{wildcard_folder}{output_suffix}"
                output_dir.mkdir(exist_ok=True)

                files_written = 0
                for category, items in data.items():
                    if isinstance(items, list):
                        cat_file = output_dir / f"{category}.txt"
                        with open(cat_file, 'w', encoding='utf-8') as f:
                            for item in items:
                                f.write(item + '\n')
                        files_written += 1

                preview_lines = list(data.keys())[:10]
                summary = f"LLM merge: {len(all_lines)} lines → {files_written} categories"

            except json.JSONDecodeError:
                summary = f"LLM merge: Error parsing response - {response[:200]}"
                preview_lines = [response[:500]]

        # Build preview
        preview = "\n".join(preview_lines[:10])
        if len(preview_lines) > 10:
            preview += f"\n... and {len(preview_lines) - 10} more lines"

        # Add backup info
        if backup_path:
            summary += f"\nBackup: {backup_path}"

        files_processed = len(txt_files)

        return (summary, preview, files_processed)
