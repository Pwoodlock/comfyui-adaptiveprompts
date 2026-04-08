"""
Search and Extract Wildcards

Search through all wildcard files for keywords and extract matching lines.
Creates new curated wildcard files from your existing data.

Usage:
    python scripts/search_and_extract_wildcards.py

    Then enter keywords like: bbw, chubby, mature, persian, nigerian, booty, curvy
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Set


def get_wildcard_files(base_dir: str) -> Dict[str, Path]:
    """Scan for all wildcard .txt files."""
    wildcard_dir = Path(base_dir) / "wildcards"
    files = {}

    if not wildcard_dir.exists():
        return files

    for txt_file in wildcard_dir.rglob("*.txt"):
        # Skip log files and system files
        if "log" in txt_file.name.lower():
            continue
        # Store relative path as key
        rel_path = txt_file.relative_to(wildcard_dir)
        files[str(rel_path)] = txt_file

    return files


def search_keywords(files: Dict[str, Path], keywords: List[str]) -> Dict[str, Set[str]]:
    """
    Search for lines containing any of the keywords.

    Args:
        files: Dict of relative_path -> file_path
        keywords: List of keywords to search for

    Returns:
        Dict matching keyword -> set of matching lines
    """
    results = {keyword.lower(): set() for keyword in keywords}

    for rel_path, file_path in files.items():
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    # Check each keyword
                    line_lower = line.lower()
                    for keyword in keywords:
                        keyword_lower = keyword.lower()
                        if keyword_lower in line_lower:
                            results[keyword_lower].add(line)
        except Exception as e:
            print(f"Error reading {file_path}: {e}")

    return results


def create_curated_wildcards(
    base_dir: str,
    search_terms: dict,
    output_folder: str = "my_presets"
) -> List[Path]:
    """
    Create curated wildcard files from search results.

    Args:
        base_dir: Base directory of the project
        search_terms: Dict of {"filename": ["keyword1", "keyword2", ...]}
        output_folder: Name of output folder

    Returns:
        List of created file paths
    """
    wildcard_dir = Path(base_dir) / "wildcards"
    output_dir = wildcard_dir / output_folder
    output_dir.mkdir(exist_ok=True)

    files = get_wildcard_files(base_dir)

    created_files = []

    for filename, keywords in search_terms.items():
        results = search_keywords(files, keywords)

        # Combine all results for this file
        all_matches = set()
        for keyword_matches in results.values():
            all_matches.update(keyword_matches)

        if all_matches:
            output_path = output_dir / f"{filename}.txt"
            with open(output_path, 'w', encoding='utf-8') as f:
                for line in sorted(all_matches):
                    f.write(f"{line}\n")

            print(f"[OK] Created {output_folder}/{filename}.txt with {len(all_matches)} matches")
            created_files.append(output_path)
        else:
            print(f"[X] No matches found for {filename}")

    return created_files


def interactive_mode(base_dir: str):
    """Interactive mode for searching and extracting."""
    print("=" * 60)
    print("Wildcard Search & Extract")
    print("=" * 60)
    print(f"\nScanning: {base_dir}/wildcards\n")

    files = get_wildcard_files(base_dir)
    print(f"Found {len(files)} wildcard files\n")

    # Get search terms from user
    print("Enter keywords to search for (comma-separated):")
    print("Example: bbw, chubby, mature, persian, nigerian, booty, curvy, thick")
    user_input = input("\n> ").strip()

    if not user_input:
        print("No input. Exiting.")
        return

    keywords = [k.strip() for k in user_input.split(',') if k.strip()]

    print(f"\nSearching for: {', '.join(keywords)}\n")

    # Search
    results = search_keywords(files, keywords)

    # Show results
    total_matches = 0
    for keyword, matches in results.items():
        if matches:
            print(f"\n[*] '{keyword}' found {len(matches)} matches:")
            for match in list(matches)[:5]:  # Show preview
                print(f"   - {match[:80]}...")
            if len(matches) > 5:
                print(f"   ... and {len(matches) - 5} more")
            total_matches += len(matches)

    print(f"\n{'=' * 60}")
    print(f"Total matches: {total_matches}")

    if total_matches > 0:
        # Ask to save
        save = input("\nSave to new wildcard file? (y/n): ").strip().lower()
        if save == 'y':
            filename = input("Filename (without .txt): ").strip()
            if not filename:
                filename = "_".join(keywords)

            output_dir = Path(base_dir) / "wildcards" / "my_presets"
            output_dir.mkdir(exist_ok=True)

            output_path = output_dir / f"{filename}.txt"

            # Combine all matches
            all_matches = set()
            for matches in results.values():
                all_matches.update(matches)

            with open(output_path, 'w', encoding='utf-8') as f:
                for line in sorted(all_matches):
                    f.write(f"{line}\n")

            print(f"\n[OK] Saved to: wildcards/my_presets/{filename}.txt")
            print(f"  Use as: __my_presets/{filename}__")
        else:
            print("Not saved.")
    else:
        print("No matches found.")


if __name__ == "__main__":
    # Get base directory (script is in scripts/ folder)
    script_dir = Path(__file__).parent
    base_dir = script_dir.parent

    # Example usage - create curated files from presets
    # Uncomment and modify to run non-interactively:

    # presets = {
    #     "bbw_curvy": ["bbw", "chubby", "curvy", "plus size", "voluptuous"],
    #     "mature_beauty": ["mature", "milf", "older", "graceful"],
    #     "persian_middle_eastern": ["persian", "middle eastern", "iranian", "arab"],
    #     "african_curvy": ["nigerian", "african", "black", "ebony", "curvy"],
    # }
    # create_curated_wildcards(str(base_dir), presets)

    # Run interactive mode
    interactive_mode(str(base_dir))
