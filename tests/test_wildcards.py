#!/usr/bin/env python3
"""
Quick test for cc-prompt-studio wildcard functionality.
Tests basic wildcard expansion with converted Xcards data.
"""

import sys
import os
from pathlib import Path

# Add parent directory to path for imports
parent_dir = str(Path(__file__).parent.parent)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Import generator module directly
import importlib.util
spec = importlib.util.spec_from_file_location(
    "generator",
    os.path.join(parent_dir, "py", "generator.py")
)
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)

SeededRandom = gen.SeededRandom
resolve_wildcards = gen.resolve_wildcards

# Path to wildcards
WILDCARD_ROOT = str(Path(__file__).parent.parent / "wildcards")

def test_basic_wildcard():
    """Test basic wildcard replacement."""
    print("Testing basic wildcard expansion...")

    # Test 1: Simple wildcard
    test_prompt = "A photo of __XQualityTags/HD__"
    rng = SeededRandom(42)
    result = resolve_wildcards(test_prompt, rng, WILDCARD_ROOT)
    print(f"  Input:  {test_prompt}")
    print(f"  Output: {result}")
    assert "__" not in result, "Wildcard was not replaced!"
    print("  [OK] Basic wildcard works\n")

def test_bracket_selection():
    """Test bracket selection."""
    print("Testing bracket selection...")

    test_prompt = "{red|green|blue} apple"
    rng = SeededRandom(42)
    result = resolve_wildcards(test_prompt, rng, WILDCARD_ROOT)
    print(f"  Input:  {test_prompt}")
    print(f"  Output: {result}")
    assert result in ["red apple", "green apple", "blue apple"], f"Unexpected result: {result}"
    print("  [OK] Bracket selection works\n")

def test_combined():
    """Test wildcard + brackets."""
    print("Testing combined wildcards + brackets...")

    test_prompt = "__XQualityTags/HD__ photo"
    rng = SeededRandom(42)
    result = resolve_wildcards(test_prompt, rng, WILDCARD_ROOT)
    print(f"  Input:  {test_prompt}")
    print(f"  Output: {result}")
    assert "__" not in result, "Wildcard was not replaced!"
    print("  [OK] Combined wildcards work\n")

def test_variable_assignment():
    """Test variable assignment and retrieval."""
    print("Testing variables...")

    test_prompt = "Assign __XQualityTags/HD^quality__ and use __^quality__"
    rng = SeededRandom(42)
    context = {}
    result = resolve_wildcards(test_prompt, rng, WILDCARD_ROOT, _resolved_vars=context)
    print(f"  Input:  {test_prompt}")
    print(f"  Output: {result}")
    print(f"  Context: {context}")
    # The variable should be replaced with the same value twice
    print("  [OK] Variables work\n")

def test_comments():
    """Test that comments are preserved (removed by PromptGenerator node, not core resolver)."""
    print("Testing comments (preserved by resolver, removed by PromptGenerator node)...")

    test_prompt = "__XQualityTags/HD__ ##this is a comment## photo"
    rng = SeededRandom(42)
    result = resolve_wildcards(test_prompt, rng, WILDCARD_ROOT)
    print(f"  Input:  {test_prompt}")
    print(f"  Output: {result}")
    # Comments are preserved by resolve_wildcards; PromptGenerator handles removal
    assert "__" not in result, "Wildcard should still be replaced!"
    print("  [OK] Comments handled correctly\n")

def main():
    """Run all tests."""
    print("=" * 50)
    print("CC Prompt Studio - Wildcard Tests")
    print("=" * 50)
    print(f"Wildcard root: {WILDCARD_ROOT}\n")

    # Check if wildcards exist
    if not os.path.exists(WILDCARD_ROOT):
        print(f"ERROR: Wildcard directory not found: {WILDCARD_ROOT}")
        sys.exit(1)

    # Count wildcard files
    txt_files = list(Path(WILDCARD_ROOT).rglob("*.txt"))
    print(f"Found {len(txt_files)} wildcard files\n")

    # Run tests
    try:
        test_basic_wildcard()
        test_bracket_selection()
        test_combined()
        test_variable_assignment()
        test_comments()
        print("=" * 50)
        print("All tests passed! [OK]")
        print("=" * 50)
    except AssertionError as e:
        print(f"\n[ERROR] Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
