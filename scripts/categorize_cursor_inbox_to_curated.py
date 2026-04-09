"""
Categorize CURSOR__/custom_wildcards (and CURSOR__ root txts) into curated folders.

Goals:
- copy-only (never delete source)
- never overwrite (adds _dupN)
- conservative: only moves files we can confidently categorize by filename / path

Defaults:
  inbox_root = wildcards_curvy_exotic/CURSOR__/custom_wildcards
  cursor_root = wildcards_curvy_exotic/CURSOR__
  curated_root = wildcards_curvy_exotic

This script is safe to commit. Generated wildcard contents stay local (gitignored).
"""

from __future__ import annotations

import argparse
import re
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Rule:
    pattern: re.Pattern[str]
    dest_rel_dir: str


def _copy_no_overwrite(src: Path, dst: Path) -> Path:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not dst.exists():
        shutil.copy2(src, dst)
        return dst
    stem = dst.stem
    suf = dst.suffix
    for i in range(2, 999):
        cand = dst.with_name(f"{stem}_dup{i}{suf}")
        if not cand.exists():
            shutil.copy2(src, cand)
            return cand
    raise RuntimeError(f"Too many duplicates for {dst}")


def _iter_txt_files(root: Path) -> list[Path]:
    out: list[Path] = []
    if not root.exists():
        return out
    for p in root.rglob("*.txt"):
        if p.is_file():
            out.append(p)
    return out


def _review_already_has(review_dir: Path, name: str) -> bool:
    """
    Prevent the review bucket from ballooning across repeated runs.
    We only copy a file into review if a file with the exact same name
    is not already present.
    """
    return (review_dir / name).exists()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--curated-root", default=None)
    ap.add_argument("--cursor-root", default=None)
    ap.add_argument("--inbox-root", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument(
        "--copy-uncategorized-to-review",
        action="store_true",
        help="Copy uncategorized files into details/misc/inbox_needs_review/ for manual browsing.",
    )
    ap.add_argument(
        "--report-json",
        default=None,
        help="Optional path to write a JSON report (categorized + uncategorized file lists).",
    )
    args = ap.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    curated_root = Path(args.curated_root) if args.curated_root else (repo_root / "wildcards_curvy_exotic")
    cursor_root = Path(args.cursor_root) if args.cursor_root else (curated_root / "CURSOR__")
    inbox_root = Path(args.inbox_root) if args.inbox_root else (cursor_root / "custom_wildcards")

    # Conservative rules based on filename/path keywords
    rules: list[Rule] = [
        # explicit/sex (opt-in)
        Rule(re.compile(r"(nsfw|sex|porn|explicit|nude|nudity|pussy|vagina|penis|anal|cum|creampie)", re.I),
             "details/opt_in_spicy/inbox_custom_wildcards"),
        # animals / furry-ish buckets (quarantine for review; user wants no anthro/furry women)
        Rule(re.compile(r"(animals?|beast|bird|wings|tail|muzzle|snout|paws|anthro|furry|scalie|e621)", re.I),
             "details/quarantine_animals_furry/inbox_custom_wildcards"),
        # fantasy / non-photoreal style buckets (opt-in)
        Rule(re.compile(r"(fantasy|wizard|angel|demon|orc|elf|dragon|monster|magic|horror)", re.I),
             "details/opt_in_stylized_fantasy/inbox_custom_wildcards"),
        # artists/styles/3d engines (prompt-soup-ish)
        Rule(re.compile(r"(artist|artstation|cgsociety|greg|rutkowski|midjourney|3d|engine|unreal|octane)", re.I),
             "details/prompt_soup_styles/inbox_custom_wildcards"),
        # props / objects / items
        Rule(re.compile(r"(item|items|object|objects|prop|props|tools|parts|weapons|sword|gun|rifle|pistol|knife|shield|armor)", re.I),
             "details/props_objects/inbox_custom_wildcards"),
        # hands / gestures
        Rule(re.compile(r"(hand|hands|finger|fingers|gesture|gestures|posture|pose|poses)", re.I),
             "details/pose_hands_gestures/inbox_custom_wildcards"),
        # colors / patterns / prints
        Rule(re.compile(r"(color|colors|palette|pattern|patterns|print|prints|striped|polka|floral|plaid|zebra|leopard)", re.I),
             "properties/colors_patterns/inbox_custom_wildcards"),
        # composition / perspective / focus / shading
        Rule(re.compile(r"(composition|compostion|perspective|focus|framing|format)", re.I),
             "camera/inbox_custom_wildcards"),
        Rule(re.compile(r"(compoisiton)", re.I),
             "camera/inbox_custom_wildcards"),
        Rule(re.compile(r"(shading|shadow|shadows)", re.I),
             "lighting/inbox_custom_wildcards"),
        # prompts / styles / subject matter
        Rule(re.compile(r"(prompts?)", re.I),
             "details/prompt_soup_styles/inbox_custom_wildcards"),
        Rule(re.compile(r"(art styles|styles\\b)", re.I),
             "details/prompt_soup_styles/inbox_custom_wildcards"),
        Rule(re.compile(r"(subject\\s*matter)", re.I),
             "details/misc/inbox_custom_wildcards"),
        Rule(re.compile(r"(subject\\s*matter|subject\\s*matter\\.txt|subject\\s*matter$|subject\\s*matter\\b)", re.I),
             "details/misc/inbox_custom_wildcards"),
        Rule(re.compile(r"\\byear\\b", re.I),
             "details/misc/inbox_custom_wildcards"),
        Rule(re.compile(r"(errors?)", re.I),
             "details/misc/inbox_custom_wildcards"),
        # food / drink
        Rule(re.compile(r"(food|foods|drink|drinks|coffee|tea|wine|beer|cocktail|cake|fruit)", re.I),
             "details/food_drink/inbox_custom_wildcards"),
        # nature / plants
        Rule(re.compile(r"(plant|plants|tree|trees|flower|flowers|garden|forest|jungle|mountain|lake|river|waterfall)", re.I),
             "scenes/nature/inbox_custom_wildcards"),
        # vehicles / tech / audio
        Rule(re.compile(r"(vehicle|vehicles|car|cars|truck|bike|motor|train|plane|ship|boat)", re.I),
             "setting/vehicles/inbox_custom_wildcards"),
        Rule(re.compile(r"(technology|tech|cyber|robot|android|computer|phone|camera|audio|sound|music|instruments|playback)", re.I),
             "details/tech_audio/inbox_custom_wildcards"),
        # danbooru packs
        Rule(re.compile(r"(danbooru)", re.I),
             "details/inbox_danbooru/inbox_custom_wildcards"),
        # rpg roles/classes (stylized)
        Rule(re.compile(r"(warrior|soldier|rogue|shaman|cleric|wizard|monk|artificer|dwarf|ogre|goblin|giant|spirit)", re.I),
             "details/opt_in_stylized_fantasy/rpg_roles/inbox_custom_wildcards"),
        # cultures / people
        Rule(re.compile(r"(nationalit|ethnic|culture|country|countries|brazil|arab|afric|europe|indian|native)", re.I),
             "person/ethnicity/inbox_custom_wildcards"),
        # age / maturity
        Rule(re.compile(r"(age|ages|milf|mature|older|cougar|50|60|70)", re.I),
             "person/age/inbox_custom_wildcards"),
        # skin / complexion
        Rule(re.compile(r"(skin|complexion|melanin|ebony|dark[_ -]?skin|brown[_ -]?skin|black[_ -]?skin)", re.I),
             "person/skin/inbox_custom_wildcards"),
        # hair
        Rule(re.compile(r"(hair|hairstyle|hairstyles|braid|bangs|ponytail|bun)", re.I),
             "hair/inbox_custom_wildcards"),
        # face / beauty
        Rule(re.compile(r"(face|faces|eyes|eye|eyebrow|eyebrows|lips|lipstick|makeup|blush|eyeliner|mascara|freckles)", re.I),
             "face/inbox_custom_wildcards"),
        # body shapes / anatomy
        Rule(re.compile(r"(body|build|bbw|curvy|thick|volupt|plump|chubby|hips|waist|thigh|ass|butt|boobs|breast)", re.I),
             "body/inbox_custom_wildcards"),
        # feet / legs focus
        Rule(re.compile(r"(feet|foot|toes|soles|legs|calves|ankle)", re.I),
             "details/feet/inbox_custom_wildcards"),
        # bras / lingerie
        Rule(re.compile(r"(bra_|^bra$|bras|bralette|lingerie|corset|bustier|garter|panties|thong|stockings|tights|hosiery)", re.I),
             "outfit/lingerie/inbox_custom_wildcards"),
        # general clothes
        Rule(re.compile(r"(clothes|clothing|outfit|wardrobe|jacket|shirt|top|blouse|pants|jeans|shorts|skirt|dress|gown|coat|sweater|hoodie)", re.I),
             "outfit/inbox_custom_wildcards"),
        # dresses / skirts
        Rule(re.compile(r"(dress|dresses|skirt|gown)", re.I),
             "outfit/dresses/inbox_custom_wildcards"),
        # footwear / legwear
        Rule(re.compile(r"(legwear|stockings|thighhigh|pantyhose|kneehigh|socks|heels|boots|shoes|sandals)", re.I),
             "outfit/footwear/inbox_custom_wildcards"),
        # jewelry / accessories
        Rule(re.compile(r"(jewel|jewelry|necklace|earring|ring|bracelet|choker|piercing|accessor|glasses|sunglasses|hat|headwear)", re.I),
             "outfit/accessories/inbox_custom_wildcards"),
        # camera / composition
        Rule(re.compile(r"(camera|lens|angle|framing|composition|closeup|close-up|dutch)", re.I),
             "camera/inbox_custom_wildcards"),
        # lighting
        Rule(re.compile(r"(light|lighting|backlight|rim light|softbox|contrast)", re.I),
             "lighting/inbox_custom_wildcards"),
        # mood / emotions
        Rule(re.compile(r"(mood|emotion|smile|smiling|sad|angry|shy|confident|flirty|seductive|expression)", re.I),
             "mood/inbox_custom_wildcards"),
        # poses
        Rule(re.compile(r"(pose|poses|position|positions)", re.I),
             "pose/inbox_custom_wildcards"),
        # locations / settings
        Rule(re.compile(r"(location|locations|room|rooms|bedroom|bathroom|kitchen|living|garden|rooftop|scene|scenes|setting)", re.I),
             "setting/inbox_custom_wildcards"),
        # materials / fabrics
        Rule(re.compile(r"(fabric|fabrics|material|materials|latex|leather|denim|silk|satin|lace|cotton|wool|velvet|mesh)", re.I),
             "matter/inbox_custom_wildcards"),
    ]

    def pick_dest(src: Path) -> Path | None:
        key = (str(src.relative_to(inbox_root)) if inbox_root in src.parents else src.name).replace("\\", "/")
        # include parent folder signal too (helps catch misspellings like "compoisiton/")
        key = f"{src.parent.name}/{key}"
        for r in rules:
            if r.pattern.search(key):
                return curated_root / Path(*r.dest_rel_dir.split("/")) / src.name
        return None

    # Copy from CURSOR__/custom_wildcards/*
    copied = 0
    skipped = 0
    review_copied = 0
    review_dir = curated_root / "details" / "misc" / "inbox_needs_review"
    categorized_paths: list[str] = []
    uncategorized_paths: list[str] = []
    for src in _iter_txt_files(inbox_root):
        dst = pick_dest(src)
        if not dst:
            skipped += 1
            uncategorized_paths.append(str(src))
            if args.copy_uncategorized_to_review and not args.dry_run:
                if not _review_already_has(review_dir, src.name):
                    (review_dir).mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, review_dir / src.name)
                    review_copied += 1
            continue
        if args.dry_run:
            copied += 1
            categorized_paths.append(str(src))
            continue
        _copy_no_overwrite(src, dst)
        copied += 1
        categorized_paths.append(str(src))

    # Also rehome obvious single files that were promoted into details/misc
    misc_inbox = curated_root / "details" / "misc" / "inbox_cursor_root"
    if misc_inbox.exists():
        for src in misc_inbox.glob("*.txt"):
            name = src.name.lower()
            # only handle the obvious ones; keep the rest in misc
            if "bras" in name or name.startswith("bra"):
                dst = curated_root / "outfit" / "lingerie" / "bras" / "inbox_cursor_root" / src.name
            elif "hair" in name:
                dst = curated_root / "hair" / "inbox_cursor_root" / src.name
            elif "dress" in name or "skirt" in name or "gown" in name:
                dst = curated_root / "outfit" / "dresses" / "inbox_cursor_root" / src.name
            elif "ethnic" in name or "nationalit" in name or "races" in name:
                dst = curated_root / "person" / "ethnicity" / "inbox_cursor_root" / src.name
            else:
                continue

            if args.dry_run:
                copied += 1
            else:
                _copy_no_overwrite(src, dst)
                copied += 1

    print(
        "[categorize_cursor_inbox_to_curated] "
        f"curated_root={curated_root} inbox_root={inbox_root} copied={copied} skipped_uncategorized={skipped} "
        f"review_copied={review_copied} dry_run={bool(args.dry_run)}"
    )

    if args.report_json:
        import json

        outp = Path(args.report_json)
        outp.parent.mkdir(parents=True, exist_ok=True)
        outp.write_text(
            json.dumps(
                {
                    "curated_root": str(curated_root),
                    "inbox_root": str(inbox_root),
                    "copied": copied,
                    "skipped_uncategorized": skipped,
                    "review_copied": review_copied,
                    "dry_run": bool(args.dry_run),
                    "categorized": categorized_paths,
                    "uncategorized": uncategorized_paths,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"[categorize_cursor_inbox_to_curated] wrote_report={outp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

