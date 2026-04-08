"""
Remove LoRA and LyCORIS tags from wildcard files.

Removes <lora:name:weight> and <lyco:name:weight> patterns from prompts.
"""

import re
from pathlib import Path


def remove_lora_tags(input_file: str, output_file: str = None) -> dict:
    """
    Remove LoRA tags from prompt file.

    Args:
        input_file: Input wildcard file path
        output_file: Output file path (default: overwrites input)

    Returns:
        Stats dict
    """
    input_path = Path(input_file)

    if output_file is None:
        output_path = input_path
    else:
        output_path = Path(output_file)

    # Pattern to match LoRA and LyCORIS tags - complete, incomplete, and partial
    # Matches: <lora:name>, <lora:name:weight>, <lyco:name>, <lyco:name:weight>, etc.
    lora_pattern = re.compile(r'<(lora|lyco):[^>]*', re.IGNORECASE)

    prompts_cleaned = []
    lora_tags_removed = 0
    total_lines = 0

    print(f"Reading: {input_path}")

    with open(input_path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            total_lines += 1
            original = line.strip()

            # Find and count LoRA tags
            loras_found = lora_pattern.findall(original)

            if loras_found:
                lora_tags_removed += len(loras_found)
                # Remove LoRA tags
                cleaned = lora_pattern.sub('', original)
                # Clean up extra commas/whitespace
                cleaned = re.sub(r',\s*,', ',', cleaned)  # Double commas
                cleaned = re.sub(r'^\s*,\s*', '', cleaned)  # Leading comma
                cleaned = re.sub(r',\s*$', '', cleaned)  # Trailing comma
                cleaned = cleaned.strip()
                prompts_cleaned.append(cleaned)
            else:
                prompts_cleaned.append(original)

    # Write output
    with open(output_path, 'w', encoding='utf-8') as f:
        for prompt in prompts_cleaned:
            f.write(prompt + '\n')

    return {
        'total_lines': total_lines,
        'lora_tags_removed': lora_tags_removed,
        'lines_with_loras': len([l for l in prompts_cleaned if lora_pattern.sub('', l) != l]),
        'output_file': str(output_path)
    }


if __name__ == "__main__":
    base_dir = Path(__file__).parent.parent
    input_file = base_dir / "wildcards" / "NSFW" / "NSFW_combined.txt"

    print("=" * 50)
    print("Removing LoRA and LyCORIS Tags")
    print("=" * 50)

    stats = remove_lora_tags(str(input_file))

    print(f"\nResults:")
    print(f"  Total lines: {stats['total_lines']:,}")
    print(f"  Tags removed: {stats['lora_tags_removed']:,}")
    print(f"  Lines affected: {stats['lines_with_loras']:,}")
    print(f"\nUpdated: {stats['output_file']}")
