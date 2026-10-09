#!/usr/bin/env python3
"""WorkbenchStrip データパックを生成する。

- WorkbenchStrip/ を毎回消してから、pack.mcmeta・pack.png(アイコン)・レシピ84件・解放用の進捗84件を書き出す
- dist/WorkbenchStrip.zip を、zip の直下に pack.mcmeta と data/ を置く形で作る

データパックの表示名は、フォルダ名・zip のファイル名(WorkbenchStrip)で表す。
名前空間は小文字しか使えないので workbench_strip のままにする。

対象は Minecraft Java Edition 1.21.1(pack_format 48)。標準ライブラリだけを使う。
"""

import json
import shutil
import zipfile
from pathlib import Path

from icon import icon_png

ROOT = Path(__file__).resolve().parent.parent
PACK_NAME = "WorkbenchStrip"
PACK_DIR = ROOT / PACK_NAME
DIST_ZIP = ROOT / "dist" / f"{PACK_NAME}.zip"

NAMESPACE = "workbench_strip"
PACK_FORMAT = 48
# zip で導入するとパックIDが file/WorkbenchStrip.zip になるので、拡張子なしの名前を説明文の1行目に入れる
DESCRIPTION = f"{PACK_NAME}\n作業台で樹皮・錆・ロウを除去"  # 選択画面の幅に収まる長さにする

# 3.1 樹皮はぎ
OVERWORLD_WOODS = ["oak", "spruce", "birch", "jungle", "acacia", "dark_oak", "mangrove", "cherry"]
NETHER_WOODS = ["crimson", "warped"]

# 3.2 / 3.3 銅の9系統。値は通常段階のID
COPPER_FAMILIES = [
    "copper_block",
    "cut_copper",
    "cut_copper_stairs",
    "cut_copper_slab",
    "chiseled_copper",
    "copper_grate",
    "copper_bulb",
    "copper_door",
    "copper_trapdoor",
]
# 段階の接頭辞(通常→露出→風化→酸化の順)
STAGE_PREFIXES = ["", "exposed_", "weathered_", "oxidized_"]
WAX_PREFIX = "waxed_"

# 5章: 1個置きでバニラレシピと競合するため、2個→2個にする変換元
CONFLICTING_SOURCES = (
    {f"{w}_log" for w in OVERWORLD_WOODS}
    | {f"{w}_wood" for w in OVERWORLD_WOODS}
    | {f"{w}_stem" for w in NETHER_WOODS}
    | {f"{w}_hyphae" for w in NETHER_WOODS}
    | {"bamboo_block", "waxed_copper_block"}
)

# zip 内のタイムスタンプを固定して、生成結果を再現できるようにする
ZIP_DATE_TIME = (1980, 1, 1, 0, 0, 0)


def copper_stage_id(family: str, prefix: str) -> str:
    """銅の系統と段階の接頭辞から、アイテムIDを返す。"""
    if family == "copper_block" and prefix:
        # ブロック系統だけは exposed_copper のように "_block" が付かない
        return f"{prefix}copper"
    return f"{prefix}{family}"


def build_conversions() -> list[tuple[str, str, str]]:
    """(kind, from, to) の一覧を返す。"""
    conversions = []

    for wood in OVERWORLD_WOODS:
        for suffix in ("log", "wood"):
            conversions.append(("strip", f"{wood}_{suffix}", f"stripped_{wood}_{suffix}"))
    for wood in NETHER_WOODS:
        for suffix in ("stem", "hyphae"):
            conversions.append(("strip", f"{wood}_{suffix}", f"stripped_{wood}_{suffix}"))
    conversions.append(("strip", "bamboo_block", "stripped_bamboo_block"))

    for family in COPPER_FAMILIES:
        stages = [copper_stage_id(family, prefix) for prefix in STAGE_PREFIXES]
        # 酸化→風化、風化→露出、露出→通常
        for i in range(len(stages) - 1, 0, -1):
            conversions.append(("scrape", stages[i], stages[i - 1]))

    for family in COPPER_FAMILIES:
        for prefix in STAGE_PREFIXES:
            item = copper_stage_id(family, prefix)
            conversions.append(("unwax", f"{WAX_PREFIX}{item}", item))

    return conversions


def recipe_json(source: str, result: str, count: int) -> dict:
    return {
        "type": "minecraft:crafting_shapeless",
        "category": "building",
        "ingredients": [{"item": f"minecraft:{source}"} for _ in range(count)],
        "result": {"id": f"minecraft:{result}", "count": count},
    }


def unlock_advancement_json(source: str, recipe_id: str) -> dict:
    """変換元を持ったとき(または解放済みのとき)に、そのレシピだけを解放する進捗。

    1.21.1 のバニラのレシピ解放用の進捗(例: recipes/building_blocks/chiseled_copper)と同じ形にする。
    """
    has_source = f"has_{source}"
    return {
        "parent": "minecraft:recipes/root",
        "criteria": {
            has_source: {
                "conditions": {"items": [{"items": f"minecraft:{source}"}]},
                "trigger": "minecraft:inventory_changed",
            },
            "has_the_recipe": {
                "conditions": {"recipe": recipe_id},
                "trigger": "minecraft:recipe_unlocked",
            },
        },
        "requirements": [["has_the_recipe", has_source]],
        "rewards": {"recipes": [recipe_id]},
    }


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")


def generate_pack() -> list[str]:
    """WorkbenchStrip/ を作り直し、生成したレシピIDの一覧を返す。"""
    if PACK_DIR.exists():
        shutil.rmtree(PACK_DIR)

    write_json(
        PACK_DIR / "pack.mcmeta",
        {"pack": {"pack_format": PACK_FORMAT, "description": DESCRIPTION}},
    )
    (PACK_DIR / "pack.png").write_bytes(icon_png())

    data_dir = PACK_DIR / "data" / NAMESPACE
    recipe_ids = []
    for kind, source, result in build_conversions():
        count = 2 if source in CONFLICTING_SOURCES else 1
        recipe_id = f"{NAMESPACE}:{kind}/{source}"
        write_json(data_dir / "recipe" / kind / f"{source}.json", recipe_json(source, result, count))
        # 変換元を手に入れたときに解放する(起動直後に全部は解放しない)
        write_json(
            data_dir / "advancement" / "recipes" / kind / f"{source}.json",
            unlock_advancement_json(source, recipe_id),
        )
        recipe_ids.append(recipe_id)
    return recipe_ids


def build_zip() -> None:
    """WorkbenchStrip/ の中身を、zip の直下に置く形でまとめる。"""
    DIST_ZIP.parent.mkdir(parents=True, exist_ok=True)
    if DIST_ZIP.exists():
        DIST_ZIP.unlink()

    files = sorted(p for p in PACK_DIR.rglob("*") if p.is_file() and p.name != ".DS_Store")
    with zipfile.ZipFile(DIST_ZIP, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in files:
            info = zipfile.ZipInfo(path.relative_to(PACK_DIR).as_posix(), date_time=ZIP_DATE_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, path.read_bytes())


def main() -> None:
    recipe_ids = generate_pack()
    build_zip()
    print(f"generated {len(recipe_ids)} recipes -> {PACK_DIR.relative_to(ROOT)}/")
    print(f"packed -> {DIST_ZIP.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
