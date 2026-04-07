#!/usr/bin/env python3
"""
Xcards YAML to Adaptive Prompts TXT Converter

Converts Xcards YAML format to hierarchical TXT files compatible with
Adaptive Prompts wildcard system.

Source: ComfyUI/models/wildcards/xcards/*.yaml
Target: ComfyUI/models/wildcards/cc-prompt-studio/
"""

import os
import re
import yaml
from pathlib import Path
from typing import Dict, List, Any


class XcardsConverter:
    """Convert Xcards YAML to Adaptive Prompts TXT format."""

    def __init__(self, source_dir: str, target_dir: str):
        self.source_dir = Path(source_dir)
        self.target_dir = Path(target_dir)
        self.target_dir.mkdir(parents=True, exist_ok=True)

    def convert_xcards_weight_to_adaptive(self, text: str) -> str:
        """
        Convert Xcards weight syntax to Adaptive Prompts syntax.

        Xcards: {1::option1|2::option2|1::option3}
        Adaptive: {option1|2$$option2|option3}

        Equal weights (1::) are removed as Adaptive Prompts treats
        unweighted options as having equal weight.
        """
        # Find all {...} blocks with Xcards weight syntax
        pattern = r'\{([^}]+)\}'

        def replace_weights(match):
            content = match.group(1)
            # Split by | first to get options
            parts = content.split('|')
            converted = []

            for part in parts:
                part = part.strip()
                # Check if it has weight syntax (number::)
                weight_match = re.match(r'(\d+)::(.+)', part)
                if weight_match:
                    weight = weight_match.group(1)
                    option = weight_match.group(2).strip()
                    # Skip weight 1 (default equal weight)
                    if weight == '1':
                        converted.append(option)
                    else:
                        converted.append(f"{weight}$$${option}")
                else:
                    converted.append(part)

            return '{' + '|'.join(converted) + '}'

        return re.sub(pattern, replace_weights, text)

    def flatten_values(self, values: List[str]) -> List[str]:
        """
        Flatten nested list structures and handle special cases.

        Xcards can have:
        - Simple strings: "item1"
        - Bracketed options: "{opt1|opt2}"
        - Multi-line bracketed options
        """
        result = []
        for value in values:
            if isinstance(value, list):
                # Recursively flatten nested lists
                result.extend(self.flatten_values(value))
            elif isinstance(value, str):
                # Clean up the value
                cleaned = value.strip()
                if cleaned and cleaned not in ['null', 'None']:
                    # Convert weight syntax
                    cleaned = self.convert_xcards_weight_to_adaptive(cleaned)
                    result.append(cleaned)
        return result

    def convert_yaml_file(self, yaml_path: Path) -> None:
        """Convert a single Xcards YAML file to TXT files."""
        print(f"Converting {yaml_path.name}...")

        try:
            with open(yaml_path, 'r', encoding='utf-8') as f:
                # Parse YAML, allowing duplicate keys with warnings
                data = yaml.safe_load(f)

            if not data:
                print(f"  Warning: No data found in {yaml_path.name}")
                return

            # Process each top-level category
            for category_name, subcategories in data.items():
                if not isinstance(subcategories, dict):
                    continue

                # Create category directory
                category_dir = self.target_dir / category_name
                category_dir.mkdir(parents=True, exist_ok=True)

                # Process each subcategory
                for subcategory_name, values in subcategories.items():
                    if not values:
                        continue

                    # Create TXT file for this subcategory
                    # Remove leading number/rank from subcategory name
                    clean_name = re.sub(r'^\d+', '', subcategory_name).strip('_')
                    if not clean_name:
                        clean_name = subcategory_name

                    output_path = category_dir / f"{clean_name}.txt"

                    # Flatten and convert values
                    flattened = self.flatten_values(values)

                    # Write to TXT file
                    with open(output_path, 'w', encoding='utf-8') as f:
                        for item in flattened:
                            # Handle multi-line bracketed options
                            if '\n' in item:
                                # Clean up extra whitespace from multi-line options
                                lines = [line.strip() for line in item.split('\n') if line.strip()]
                                cleaned_item = '\n'.join(lines)
                                f.write(cleaned_item + '\n')
                            else:
                                f.write(item + '\n')

                    print(f"  Created: {output_path.relative_to(self.target_dir)}")

        except yaml.YAMLError as e:
            print(f"  Error parsing YAML: {e}")
        except Exception as e:
            print(f"  Error: {e}")

    def convert_all(self) -> None:
        """Convert all YAML files in the source directory."""
        yaml_files = list(self.source_dir.glob('*.yaml'))
        yaml_files.extend(self.source_dir.glob('*.yml'))

        if not yaml_files:
            print(f"No YAML files found in {self.source_dir}")
            return

        print(f"Found {len(yaml_files)} YAML file(s)\n")

        for yaml_file in sorted(yaml_files):
            self.convert_yaml_file(yaml_file)

        print(f"\nConversion complete! Output: {self.target_dir}")
        print(f"Files created: {sum(1 for _ in self.target_dir.rglob('*.txt'))}")


def main():
    """Main entry point."""
    # Determine paths relative to this script
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent

    # Default paths
    source_dir = repo_root / '../../models/wildcards/xcards'
    target_dir = repo_root / '../../models/wildcards/cc-prompt-studio'

    # Allow command line overrides
    import sys
    if len(sys.argv) > 1:
        source_dir = Path(sys.argv[1])
    if len(sys.argv) > 2:
        target_dir = Path(sys.argv[2])

    # Resolve to absolute paths
    source_dir = source_dir.resolve()
    target_dir = target_dir.resolve()

    print(f"Source: {source_dir}")
    print(f"Target: {target_dir}")
    print("-" * 50)

    if not source_dir.exists():
        print(f"Error: Source directory not found: {source_dir}")
        sys.exit(1)

    converter = XcardsConverter(str(source_dir), str(target_dir))
    converter.convert_all()


if __name__ == '__main__':
    main()
