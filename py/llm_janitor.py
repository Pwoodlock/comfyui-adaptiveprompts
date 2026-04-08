"""
CCLLMJanitor - LLM-Powered Wildcard Cleanup Node

Uses LM Studio (Gemma 4 or other models) to intelligently clean,
merge, validate, and deduplicate wildcard files.
"""

import os
import re
import shutil
import json
import urllib.request
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
    - Auto-detect wildcard folders from wildcards/ directory
    - Model probing and selection from LM Studio
    - Unload model function for VRAM management
    - Pre-defined cleanup contexts + custom instructions
    - Backup creation before modifications
    - Dry-run mode for safe testing
    - Operation guide output explains what each operation does
    """

    # LORA pattern to remove
    LORA_PATTERN = re.compile(r'<lora:[^>]+>', re.IGNORECASE)

    # Operation templates with descriptions
    OPERATIONS = {
        "basic_cleanup": {
            "system": "You are a wildcard file cleaner. Your job is to clean up prompt text.",
            "instructions": "Remove these from each line:\n- LoRA tags like <:lora:model:1.0>\n- Extra commas and punctuation\n- Excessive whitespace\n- Empty lines\n\nReturn the cleaned lines, one per line, separated by |.",
            "description": "[Basic Cleanup] No LLM - Removes LoRA tags, fixes punctuation, cleans whitespace. Fast local processing. Output: Single merged file with all cleaned prompts."
        },
        "nsfw_cleanup": {
            "system": "You are a wildcard file cleaner for NSFW/adult content.",
            "instructions": "Clean up these prompts:\n- Remove all LoRA tags\n- Remove 'unsafe', 'nsfw', 'sensitive' warnings\n- Fix CivitAI syntax issues\n- Standardize to comma-separated format\n\nReturn cleaned lines, separated by |.",
            "description": "[NSFW Cleanup] LLM - Removes LoRA tags and NSFW/safety warnings. Fixes CivitAI bracket syntax issues. Output: Cleaned adult content prompts."
        },
        "merge_consolidate": {
            "system": "You are a wildcard file organizer. Group these prompts into logical categories.",
            "instructions": "Analyze these prompts and organize them into themed groups. Return JSON with category names and arrays of prompts.\n\nFormat: {\"category1\": [\"prompt1\", \"prompt2\"], \"category2\": [\"prompt3\", \"prompt4\"]}",
            "description": "[Merge & Consolidate] LLM - Analyzes and groups prompts into themed categories. Creates separate .txt files per category. Great for organizing messy wildcard folders."
        },
        "deduplicate": {
            "system": "You are a duplicate detector. Remove duplicate and near-duplicate prompts.",
            "instructions": "Find and remove duplicate or very similar prompts. Keep only unique prompts. Return unique prompts, one per line, separated by |.",
            "description": "[Deduplicate] LLM - Finds and removes duplicate or near-duplicate prompts. Keeps only unique entries. Reduces file size and improves prompt variety."
        },
        "quality_check": {
            "system": "You are a prompt quality validator.",
            "instructions": "Analyze these prompts for quality issues. Identify:\n- Vague or low-quality prompts\n- Missing key details\n- Poor tag ordering\n\nReturn analysis with line numbers and issues.",
            "description": "[Quality Check] LLM - Validates prompt quality and identifies issues. Flags vague prompts, missing details, poor tag order. Output: Analysis report with issues found."
        },
        "custom": {
            "system": "You are a wildcard file assistant. Follow the user's custom instructions.",
            "instructions": "{user_custom_context}",
            "description": "[Custom] LLM - Use your own instructions via 'custom_context' input. Full control over LLM behavior. Specify exactly what you want done."
        }
    }

    @classmethod
    def _scan_wildcard_folders(cls) -> List[str]:
        """Scan wildcards/ directory for available folders."""
        base_dir = Path(__file__).parent.parent / "wildcards"

        if not base_dir.exists():
            return []

        folders = []
        for item in base_dir.iterdir():
            if item.is_dir():
                folders.append(item.name)

        return sorted(folders)

    @classmethod
    def INPUT_TYPES(cls):
        # Get available models from LM Studio
        models = cls._get_cached_models()
        model_list = models if models else ["(No LM Studio running)"]

        # Auto-detect wildcard folders
        folders = cls._scan_wildcard_folders()
        folder_list = folders if folders else ["(No folders found)"]

        return {
            "required": {
                "wildcard_folder": (folder_list, {
                    "default": folder_list[0] if folder_list else "",
                    "tooltip": "Select wildcard folder to process"
                }),
                "operation": (list(cls.OPERATIONS.keys()), {
                    "default": "basic_cleanup",
                    "tooltip": "Select operation type. Check 'operation_guide' output for full details."
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
                "unload_model": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "Unload LLM model from VRAM after processing (frees memory for ComfyUI)"
                }),
                "wait_for_model": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "Wait up to 60 seconds for LM Studio to load the model before processing"
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
                    "tooltip": "Preview changes WITHOUT writing files (safe testing mode)"
                }),
                "backup": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "Create backup before modifying files"
                }),

                # Output options
                "output_suffix": ("STRING", {
                    "default": "_cleaned",
                    "tooltip": "Suffix for output folder (e.g., NSFW_v1_cleaned)"
                }),
                "chunk_size": ("INT", {
                    "default": 1000,
                    "min": 100,
                    "max": 10000,
                    "tooltip": "Lines per output file (for merge operations)"
                }),
            }
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING", "INT")
    RETURN_NAMES = ("operation_guide", "summary", "preview", "result_output", "files_processed")
    FUNCTION = "process"
    OUTPUT_NODE = True  # Can execute without connecting outputs
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
        # Store backups outside wildcard folder to avoid detection
        root = source_path.parent.parent.parent  # Go up from wildcards/category/ to cc-prompt-studio root
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

    @classmethod
    def _unload_model(cls, model: str) -> str:
        """
        Unload model from LM Studio to free VRAM.

        Uses LM Studio REST API: POST /api/v1/models/unload
        Requires LM Studio 0.4.0+
        """
        try:
            import urllib.request
            import json

            # First, get loaded models to find the instance_id
            list_url = "http://localhost:1234/api/v1/models"
            list_request = urllib.request.Request(list_url)
            with urllib.request.urlopen(list_request, timeout=5) as response:
                models_data = json.loads(response.read().decode("utf-8"))
                print(f"[CC LLM Janitor] Loaded models: {models_data}")

                # Find matching model and get its instance_id
                instance_id = None
                if "data" in models_data:
                    for m in models_data["data"]:
                        if m.get("id") == model or m.get("id", "").endswith("/" + model):
                            instance_id = m.get("instance_id")
                            break

                if not instance_id:
                    # Try using model name directly as instance_id
                    instance_id = model

                print(f"[CC LLM Janitor] Attempting to unload instance_id: {instance_id}")

            # LM Studio unload endpoint (v1 API)
            url = "http://localhost:1234/api/v1/models/unload"
            payload = {"instance_id": instance_id}

            data = json.dumps(payload).encode("utf-8")
            request = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST"
            )

            with urllib.request.urlopen(request, timeout=30) as response:
                result = json.loads(response.read().decode("utf-8"))
                print(f"[CC LLM Janitor] Unload response: {result}")
                return f"Unloaded: {model}"

        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8") if e.fp else ""
            print(f"[CC LLM Janitor] HTTP Error {e.code}: {body}")
            if e.code == 404:
                return "Unload failed: API not found (need LM Studio 0.4.0+)"
            return f"Unload HTTP error: {e.code} - {body}"
        except Exception as exc:
            print(f"[CC LLM Janitor] Unload exception: {exc}")
            return f"Unload failed: {exc}"

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

    def _build_llm_prompt(self, operation: str, lines: List[str], custom_context: str = "") -> Tuple[str, str]:
        """Build the LLM prompt based on operation type."""
        op_config = self.OPERATIONS.get(operation, self.OPERATIONS["custom"])

        if operation == "custom":
            # Use custom context
            system_prompt = op_config["system"]
            instructions = custom_context or "Clean these wildcard prompts."
        else:
            system_prompt = op_config["system"]
            instructions = op_config["instructions"]

        # Limit input size for LLM
        sample_lines = lines[:500]
        input_text = "\n".join(sample_lines)

        remaining = len(lines) - 500
        user_prompt = f"""{instructions}

Here are the wildcard prompts to process (showing first 500):

{input_text}

... and {remaining} more lines"""

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
        unload_model: bool = False,
        wait_for_model: bool = False,
        custom_context: str = "",
        dry_run: bool = True,
        backup: bool = True,
        output_suffix: str = "_cleaned",
        chunk_size: int = 1000,
    ) -> Tuple[str, str, str, str, int]:
        """
        Process wildcard folder with LLM cleanup.

        Args:
            wildcard_folder: Folder name within wildcards/
            operation: Type of cleanup operation
            llm_model: Model to use
            refresh_models: Whether to refresh model list
            unload_model: Unload model from VRAM after processing
            custom_context: Custom instructions for operation=custom
            dry_run: Preview without writing files
            backup: Create backup before processing
            output_suffix: Suffix for output folder
            chunk_size: Lines per output file (for merge)

        Returns:
            (operation_guide, summary, preview, result_output, files_processed)
            - operation_guide: Description of what the selected operation does
            - summary: Processing summary with stats
            - preview: First 10 lines of result
            - result_output: Full result text
            - files_processed: Number of files processed
        """
        print(f"[CC LLM Janitor] PROCESS CALLED - wildcard_folder={wildcard_folder}, operation={operation}")

        # Get operation guide (always returned)
        op_guide = self.OPERATIONS.get(operation, {}).get("description", "Unknown operation")

        # Refresh models if requested
        if refresh_models:
            self._models_cache = None
            self._models_cache_time = 0

        # Determine paths
        base_dir = Path(__file__).parent.parent
        wildcard_dir = base_dir / "wildcards" / wildcard_folder

        print(f"[CC LLM Janitor] base_dir={base_dir}")
        print(f"[CC LLM Janitor] wildcard_dir={wildcard_dir}")
        print(f"[CC LLM Janitor] exists={wildcard_dir.exists()}")

        if not wildcard_dir.exists():
            print(f"[CC LLM Janitor] ERROR: Folder not found!")
            return (op_guide, f"Error: Folder '{wildcard_folder}' not found in wildcards/", "", "", 0)

        # Scan for files - recursive (will flatten later, using rglob for now)
        supported_extensions = ["*.txt", "*.md", "*.yml", "*.yaml", "*.json"]
        txt_files = []
        for ext in supported_extensions:
            txt_files.extend(wildcard_dir.rglob(ext))

        print(f"[CC LLM Janitor] Found {len(txt_files)} files (recursive scan)")

        if not txt_files:
            print(f"[CC LLM Janitor] ERROR: No supported files found!")
            return (op_guide, f"Error: No supported files found in {wildcard_folder}/\nSupported: txt, md, yml, yaml, json", "", "", 0)

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
            summary = f"Basic cleanup: {len(all_lines)} lines ->{len(processed)} lines"

            result_output = "\n".join(processed)

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
            print(f"[CC LLM Janitor] LLM operation: {operation}")
            print(f"[CC LLM Janitor] Total lines to process: {len(all_lines)}")
            print(f"[CC LLM Janitor] Using model: {llm_model}")

            system_prompt, user_prompt = self._build_llm_prompt(operation, all_lines, custom_context)

            print(f"[CC LLM Janitor] Calling LM Studio...")
            print(f"[CC LLM Janitor] Prompt length: {len(user_prompt)} chars")
            # Call LLM
            response = call_lm_studio(
                model=llm_model,
                user_prompt=user_prompt,
                system_prompt=system_prompt,
                wait_for_load=wait_for_model
            )
            print(f"[CC LLM Janitor] LLM response received, length: {len(response) if response else 0}")
            print(f"[CC LLM Janitor] Response preview: {response[:200] if response else 'None'}")

            processed = self._parse_llm_response(response, operation)
            preview_lines = processed[:10] if processed else [response[:500]]
            summary = f"LLM {operation}: {len(all_lines)} lines ->{len(processed)} results"

            result_output = "\n".join(processed)

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
            system_prompt, user_prompt = self._build_llm_prompt(operation, all_lines, custom_context)

            # Call LLM
            response = call_lm_studio(
                model=llm_model,
                user_prompt=user_prompt,
                system_prompt=system_prompt,
                wait_for_load=wait_for_model
            )

            # Try to parse as JSON
            try:
                data = json.loads(response)
                # Write categorized files
                output_dir = wildcard_dir.parent / f"{wildcard_folder}{output_suffix}"
                output_dir.mkdir(exist_ok=True)

                files_written = 0
                result_lines = []

                for category, items in data.items():
                    if isinstance(items, list):
                        result_lines.append(f"Category: {category} ({len(items)} items)")
                        result_lines.extend(items)

                result_output = "\n".join(result_lines)

                if not dry_run:
                    for category, items in data.items():
                        if isinstance(items, list):
                            cat_file = output_dir / f"{category}.txt"
                            with open(cat_file, 'w', encoding='utf-8') as f:
                                for item in items:
                                    f.write(item + '\n')
                            files_written += 1

                preview_lines = list(data.keys())[:10]
                summary = f"LLM merge: {len(all_lines)} lines ->{files_written} categories"

            except json.JSONDecodeError:
                summary = f"LLM merge: Error parsing response - {response[:200]}"
                preview_lines = [response[:500]]
                result_output = response

        # Build preview
        preview = "\n".join(preview_lines[:10])
        if len(preview_lines) > 10:
            preview += f"\n... and {len(preview_lines) - 10} more lines"

        # Add operation info to summary
        summary = f"CC LLM Janitor - {operation.upper()}\n{summary}"
        summary += f"\nFolder: {wildcard_folder}"
        summary += f"\nFiles: {len(txt_files)}"

        # Add backup info
        if backup_path:
            summary += f"\nBackup: {backup_path}"

        if dry_run:
            summary += "\n[DRY RUN] - No files were modified"

        # Unload model if requested
        if unload_model and not dry_run:
            unload_result = self._unload_model(llm_model)
            summary += f"\n{unload_result}"

        files_processed = len(txt_files)

        # Write output to file for JavaScript display
        try:
            import folder_paths
            output_dir = Path(folder_paths.get_output_directory())
            js_display_file = output_dir / "cc_llm_janitor_output.json"
            with open(js_display_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "operation_guide": op_guide,
                    "summary": summary,
                    "preview": preview,
                    "result_output": result_output,
                    "files_processed": files_processed
                }, f, ensure_ascii=False, indent=2)
            print(f"[CC LLM Janitor] Wrote display file: {js_display_file}")
        except Exception as e:
            print(f"[CC LLM Janitor] Failed to write display file: {e}")

        return (op_guide, summary, preview, result_output, files_processed)


NODE_CLASS_MAPPINGS = {
    "CCLLMJanitor": CCLLMJanitor
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "CCLLMJanitor": "CC LLM Janitor"
}
