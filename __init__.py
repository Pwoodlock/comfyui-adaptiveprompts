import os
from .py.prompt_repack import PromptRepack
from .py.prompt_replace import PromptReplace
from .py.prompt_generator import PromptGenerator, PromptGeneratorAdvanced, PromptContextMerge
from .py.prompt_sequencer import PromptSequencer
from .py.weight_lifter import WeightLifter
from .py.image_nodes import SaveImageAndText
from .py.prompt_alias import PromptAliasSwap
from .py.prompt_splitter import PromptSplitter
from .py.prompt_mixer import PromptMixer
from .py.prompt_shuffle import PromptShuffle, PromptShuffleAdvanced
from .py.string_utils import *
from .py.misc_utils import *
from .py.math_utils import *

# cc-prompt-studio: Unified Character Prompt node
from .py.character_prompt_studio import CharacterPromptStudio
from .py.llm_janitor import CCLLMJanitor
from .py.wildcard_tools import WildcardTools, WildcardSearchExtract, WildcardPreview

# Web directory for JavaScript extensions (custom widgets, UI enhancements)
WEB_DIRECTORY = "./js"

NODE_CLASS_MAPPINGS = {
    "PromptGenerator": PromptGenerator,
    "PromptGeneratorAdvanced": PromptGeneratorAdvanced,
    "PromptSequencer": PromptSequencer,
    "PromptRepack": PromptRepack,
    "PromptAliasSwap": PromptAliasSwap,
    "PromptReplace": PromptReplace,
    "WeightLifter": WeightLifter,
    "PromptSplitter": PromptSplitter,
    "PromptMixer": PromptMixer,
    "PromptShuffle": PromptShuffle,
    "PromptShuffleAdvanced": PromptShuffleAdvanced,
    "PromptContextMerge": PromptContextMerge,
    "PromptCleanup": PromptCleanup,
    "NormalizeLoraTags": LoraTagNormalizer,
    "StringSplit": StringSplit,
    "StringAppend3": StringAppend3,
    "StringAppend8": StringAppend8,
    "ScaledSeedGenerator": ScaledSeedGenerator,
    "TagCounter": TagCounter,
    "SaveImageAndText": SaveImageAndText,
    "RandomFloats": RandomFloats4,
    "RandomIntegers": RandomIntegers4,

    # cc-prompt-studio: Unified Character Prompt node
    "CharacterPromptStudio": CharacterPromptStudio,
    "CCLLMJanitor": CCLLMJanitor,
    "WildcardTools": WildcardTools,
    "WildcardSearchExtract": WildcardSearchExtract,
    "WildcardPreview": WildcardPreview,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "PromptGenerator": "Prompt Generator",
    "PromptGeneratorAdvanced": "Prompt Generator (Advanced)",
    "PromptSequencer": "Prompt Sequencer",
    "PromptRepack": "Prompt Repack",
    "PromptAliasSwap": "Prompt Alias Swap",
    "PromptReplace": "Prompt Replace",
    "PromptContextMerge": "Prompt Context Merge",
    "WeightLifter": "Weight Lifter",
    "PromptSplitter": "Prompt Splitter",
    "PromptMixer": "Prompt Mixer",
    "PromptShuffle": "Prompt Shuffle",
    "PromptShuffleAdvanced": "Prompt Shuffle (Advanced)",
    "PromptCleanup": "Prompt Cleanup",
    "NormalizeLoraTags": "Normalize Lora Tags",
    "StringSplit": "String Split",
    "StringAppend3": "String Append",
    "StringAppend8": "String Append",
    "ScaledSeedGenerator": "Scaled Seed Generator",
    "TagCounter": "Tag Counter",
    "SaveImageAndText": "Save Image And Text",
    "RandomFloats": "Random Floats 4",
    "RandomIntegers": "Random Integers 4",

    # cc-prompt-studio: Unified Character Prompt node
    "CharacterPromptStudio": "Character Prompt Studio",
    "CCLLMJanitor": "CC LLM Janitor",
    "WildcardTools": "Wildcard Tools",
    "WildcardSearchExtract": "Wildcard Search & Extract",
    "WildcardPreview": "Wildcard Preview",
}

def register_nodes(comfy):
    for name, cls in NODE_CLASS_MAPPINGS.items():
        display_name = NODE_DISPLAY_NAME_MAPPINGS.get(name, name)
        comfy.register_node(cls, display_name=display_name)

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
