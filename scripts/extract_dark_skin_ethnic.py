"""
Extract Dark Skin & Ethnic Prompts
"""

import re
from pathlib import Path


def extract_keywords(input_file: str, keywords: list, output_file: str) -> int:
    """Extract prompts containing any of the keywords."""
    seen = set()
    matches = []

    with open(input_file, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line_lower = line.lower()
            if any(kw.lower() in line_lower for kw in keywords):
                if line not in seen:
                    seen.add(line)
                    matches.append(line.strip())

    # Write output
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        for prompt in matches:
            f.write(prompt + '\n')

    return len(matches)


if __name__ == "__main__":
    base_dir = Path(__file__).parent.parent
    input_file = base_dir / "wildcards" / "NSFW" / "NSFW_combined.txt"
    output_file = base_dir / "wildcards" / "my_presets" / "dark_skin_ethnic.txt"

    keywords = [
        "dark skin", "dark-skinned", "darker skin",
        "african", "africa", "nigerian", "nigeria",
        "ebony", "black girl", "black woman",
        "persian", "iranian", "middle eastern", "arab",
        "indian", "south asian",
        "ethiopian", "somali", "ghanaian"
    ]

    print("Extracting dark skin & ethnic prompts...")
    print(f"Keywords: {', '.join(keywords)}")

    count = extract_keywords(str(input_file), keywords, str(output_file))

    print(f"\nExtracted {count:,} prompts")
    print(f"Output: my_presets/dark_skin_ethnic.txt")
    print(f"\nUse as: __my_presets/dark_skin_ethnic__")
