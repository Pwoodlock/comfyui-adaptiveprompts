"""Quick test - extract bbw/curvy tags"""
import sys
sys.path.insert(0, "D:/Trellis/ComfyUI-Easy-Install/ComfyUI/custom_nodes/cc-prompt-studio/scripts")

from search_and_extract_wildcards import create_curated_wildcards

base_dir = "D:/Trellis/ComfyUI-Easy-Install/ComfyUI/custom_nodes/cc-prompt-studio"

presets = {
    "bbw_curvy": ["bbw", "chubby", "curvy", "thick", "plus size", "voluptuous"],
}

files = create_curated_wildcards(base_dir, presets)
print(f"\nCreated: {files}")
print("Use as: __my_presets/bbw_curvy__")
