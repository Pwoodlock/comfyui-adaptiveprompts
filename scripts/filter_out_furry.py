"""
Filter out unwanted content from wildcard files.
"""

from pathlib import Path


def filter_file(input_file: str, output_file: str, unwanted: list) -> int:
    """Remove lines containing unwanted keywords."""
    kept = []

    with open(input_file, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line_lower = line.lower()
            if not any(kw.lower() in line_lower for kw in unwanted):
                kept.append(line.strip())

    # Write output
    with open(output_file, 'w', encoding='utf-8') as f:
        for prompt in kept:
            f.write(prompt + '\n')

    return len(kept)


if __name__ == "__main__":
    base_dir = Path(__file__).parent.parent
    input_file = base_dir / "wildcards" / "my_presets" / "mature_beauty.txt"
    output_file = base_dir / "wildcards" / "my_presets" / "mature_beauty.txt"

    # Filter out furry/anthro content
    unwanted = [
        "furry", "anthro", "pokemon", "blaziken",
        "e621", "scalie", "avian", "feathers",
        "fluffy fur", "furry art", "paws", "muzzle",
        "snout", "tail", "beak", "talons"
    ]

    print("Filtering out unwanted content...")
    print(f"Removing: {', '.join(unwanted)}")

    original_count = sum(1 for _ in open(input_file, 'r', encoding='utf-8', errors='ignore'))
    kept_count = filter_file(str(input_file), str(output_file), unwanted)

    print(f"\nOriginal: {original_count:,}")
    print(f"Removed: {original_count - kept_count:,}")
    print(f"Final: {kept_count:,}")
    print(f"\nUpdated: my_presets/mature_beauty.txt")
