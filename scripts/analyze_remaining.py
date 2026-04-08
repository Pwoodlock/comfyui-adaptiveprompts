"""
Analyze remaining content in master NSFW file after extracts.
"""

from pathlib import Path
from collections import Counter


def analyze_remaining(master_file: str, extracted_files: list) -> dict:
    """Analyze what's left in master file."""
    # Get extracted prompts
    extracted = set()
    for ef in extracted_files:
        try:
            with open(ef, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    extracted.add(line.strip())
        except:
            pass

    # Read master and find remaining
    remaining = []
    with open(master_file, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            if line and line not in extracted:
                remaining.append(line)

    # Analyze remaining content
    words = Counter()
    for line in remaining:
        for word in line.lower().split(','):
            word = word.strip()
            if len(word) > 2:
                words[word] += 1

    return {
        'remaining_count': len(remaining),
        'extracted_count': len(extracted),
        'top_words': words.most_common(50)
    }


if __name__ == "__main__":
    base_dir = Path(__file__).parent.parent
    master_file = base_dir / "wildcards" / "NSFW" / "NSFW_combined.txt"

    extracted_files = [
        base_dir / "wildcards" / "my_presets" / "curvy_full_figured.txt",
        base_dir / "wildcards" / "my_presets" / "dark_skin_ethnic.txt",
        base_dir / "wildcards" / "my_presets" / "mature_beauty.txt",
    ]

    print("Analyzing remaining content...")
    result = analyze_remaining(str(master_file), extracted_files)

    print(f"\nMaster file total: {result['remaining_count'] + result['extracted_count']:,}")
    print(f"Extracted: {result['extracted_count']:,}")
    print(f"Remaining: {result['remaining_count']:,}")

    print(f"\nTop tags in REMAINING content:")
    for word, count in result['top_words']:
        print(f"  {word}: {count:,}")
