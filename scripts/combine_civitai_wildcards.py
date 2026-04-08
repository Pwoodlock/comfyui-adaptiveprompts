"""
Combine Civitai Prompt Files into Clean Wildcard

Reads individual prompt files and combines into one clean wildcard file.
- One prompt per line
- Remove duplicates
- Clean formatting
"""

import os
from pathlib import Path
from typing import Set


def combine_prompts(source_dir: str, output_file: str) -> dict:
    """
    Combine individual prompt files into one wildcard file.

    Args:
        source_dir: Directory containing .txt prompt files
        output_file: Output wildcard file path

    Returns:
        Stats dict with counts
    """
    source_path = Path(source_dir)
    seen: Set[str] = set()
    prompts = []
    duplicates = 0
    empty_files = 0

    print(f"Reading from: {source_path}")

    # Read all .txt files
    for txt_file in sorted(source_path.glob("*.txt")):
        try:
            with open(txt_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read().strip()

            if not content:
                empty_files += 1
                continue

            # Check for duplicate
            if content in seen:
                duplicates += 1
            else:
                seen.add(content)
                prompts.append(content)

        except Exception as e:
            print(f"Error reading {txt_file}: {e}")

    # Write output
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        for prompt in prompts:
            f.write(prompt + '\n')

    stats = {
        'total_files': len(list(source_path.glob("*.txt"))),
        'unique_prompts': len(prompts),
        'duplicates_removed': duplicates,
        'empty_files': empty_files,
        'output_file': str(output_path)
    }

    return stats


if __name__ == "__main__":
    base_dir = Path(__file__).parent.parent
    source = base_dir / "wildcards" / "NSFW"
    output = base_dir / "wildcards" / "NSFW_combined.txt"

    print("=" * 50)
    print("Combining Civitai Wildcards")
    print("=" * 50)

    stats = combine_prompts(str(source), str(output))

    print(f"\nResults:")
    print(f"  Total files read: {stats['total_files']:,}")
    print(f"  Unique prompts: {stats['unique_prompts']:,}")
    print(f"  Duplicates removed: {stats['duplicates_removed']:,}")
    print(f"  Empty files: {stats['empty_files']:,}")
    print(f"\nOutput: {stats['output_file']}")
    print(f"\nUse as: __NSFW_combined__")
