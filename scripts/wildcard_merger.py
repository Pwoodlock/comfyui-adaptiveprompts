#!/usr/bin/env python3
"""
Wildcard File Merger Tool

Combines multiple small wildcard files into fewer, larger files.
Also cleans up problematic CivitAI lora tags.
"""

import os
import re
from pathlib import Path
from typing import List


class WildcardMerger:
    """Tool to merge wildcard files efficiently."""

    # Pattern to match CivitAI lora tags like <:lora:something:0.5>
    LORA_PATTERN = re.compile(r'<lora:[^>]+>', re.IGNORECASE)

    def __init__(self, source_dir: str, output_dir: str = None):
        self.source_dir = Path(source_dir)
        self.output_dir = Path(output_dir) if output_dir else self.source_dir

    def clean_lora_tags(self, text: str) -> str:
        """
        Remove CivitAI lora tags from text.

        Examples removed:
        <:lora:xl_more:0.5>
        <:lora:character:1.0>
        """
        return self.LORA_PATTERN.sub('', text)

    def clean_line(self, line: str) -> str:
        """Clean a single line of text."""
        # Remove lora tags
        line = self.clean_lora_tags(line)
        # Clean up extra whitespace
        line = re.sub(r'\s+', ' ', line)
        # Strip leading/trailing whitespace
        line = line.strip()
        # Remove trailing separators like ---, etc.
        line = re.sub(r'[-=]{3,}$', '', line).strip()
        return line

    def merge_all_to_one(self, output_filename: str = "all_combined.txt",
                        clean_loras: bool = True) -> int:
        """
        Merge ALL .txt files in source_dir into one file.

        Args:
            output_filename: Name of output file
            clean_loras: Whether to remove CivitAI lora tags

        Returns:
            Number of lines written
        """
        output_path = self.output_dir / output_filename
        lines_written = 0

        with open(output_path, 'w', encoding='utf-8') as out:
            for txt_file in sorted(self.source_dir.glob('*.txt')):
                # Skip the output file if it already exists
                if txt_file.name == output_filename:
                    continue

                with open(txt_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue

                        if clean_loras:
                            line = self.clean_line(line)

                        if line:
                            out.write(line + '\n')
                            lines_written += 1

        return lines_written

    def merge_by_count(self, lines_per_file: int = 1000,
                       output_prefix: str = "merged_",
                       clean_loras: bool = True) -> int:
        """
        Merge files into chunks of N lines each.

        Args:
            lines_per_file: Maximum lines per output file
            output_prefix: Prefix for output files
            clean_loras: Whether to remove CivitAI lora tags

        Returns:
            Number of output files created
        """
        all_lines = []
        files_created = 0

        # First, collect all lines
        for txt_file in sorted(self.source_dir.glob('*.txt')):
            with open(txt_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    if clean_loras:
                        line = self.clean_line(line)

                    if line:
                        all_lines.append(line)

        # Then write in chunks
        chunk_num = 1
        for i in range(0, len(all_lines), lines_per_file):
            chunk = all_lines[i:i + lines_per_file]
            output_path = self.output_dir / f"{output_prefix}{chunk_num}.txt"

            with open(output_path, 'w', encoding='utf-8') as out:
                for line in chunk:
                    out.write(line + '\n')

            files_created += 1
            chunk_num += 1

        return files_created

    def show_stats(self) -> dict:
        """Show statistics about the source directory."""
        stats = {
            'total_files': 0,
            'total_lines': 0,
            'total_size_mb': 0,
            'has_lora_tags': 0,
            'empty_files': 0
        }

        for txt_file in self.source_dir.glob('*.txt'):
            stats['total_files'] += 1
            stats['total_size_mb'] += txt_file.stat().st_size / (1024 * 1024)

            with open(txt_file, 'r', encoding='utf-8') as f:
                content = f.read()
                if not content.strip():
                    stats['empty_files'] += 1
                else:
                    lines = content.strip().split('\n')
                    stats['total_lines'] += len(lines)

                    # Check for lora tags
                    if self.LORA_PATTERN.search(content):
                        stats['has_lora_tags'] += 1

        return stats


def main():
    import sys

    if len(sys.argv) < 2:
        print("Usage: python wildcard_merger.py <source_directory> [output_directory]")
        print("\nExample:")
        print("  python wildcard_merger.py wildcards/NSFW_v1")
        print("  python wildcard_merger.py wildcards/NSFW_v1 wildcards/NSFW_v1_merged")
        sys.exit(1)

    source_dir = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else source_dir

    merger = WildcardMerger(source_dir, output_dir)

    # Show stats first
    print("[STATS] Source directory statistics:")
    stats = merger.show_stats()
    print(f"  Total files: {stats['total_files']:,}")
    print(f"  Total lines: {stats['total_lines']:,}")
    print(f"  Total size: {stats['total_size_mb']:.1f} MB")
    print(f"  Files with lora tags: {stats['has_lora_tags']:,}")
    print(f"  Empty files: {stats['empty_files']:,}")
    print()

    # Merge all to one file
    print("[MERGING] Merging to single file...")
    lines = merger.merge_all_to_one(
        output_filename="all_merged.txt",
        clean_loras=True
    )
    print(f"   Created: all_merged.txt with {lines:,} lines")

    # Also create chunks
    print("\n[MERGING] Creating chunked files (1000 lines each)...")
    chunks = merger.merge_by_count(
        lines_per_file=1000,
        output_prefix="chunk_",
        clean_loras=True
    )
    print(f"   Created: {chunks} chunk files")

    print(f"\n[DONE] Done! Output in: {output_dir}")


if __name__ == "__main__":
    main()
