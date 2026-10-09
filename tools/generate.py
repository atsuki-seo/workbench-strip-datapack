#!/usr/bin/env python3
"""WorkbenchStrip データパックを生成する。

- build/<ターゲットID>/WorkbenchStrip/ を毎回消してから、pack.mcmeta・pack.png(アイコン)・LICENSE・README.md・レシピ84件・解放用の進捗84件を書き出す
- dist/ に zip を、zip の直下に pack.mcmeta と data/ を置く形で作る(名前の決め方は targets.py の dist_zip_name)

データパックの表示名は、フォルダ名・zip のファイル名(WorkbenchStrip)で表す。
名前空間は小文字しか使えないので workbench_strip のままにする。

対象のバージョン(pack_format・木材・銅の系統・材料の書式)は targets/<ターゲットID>.json で決める。
使い方: generate.py --target <ターゲットID> | --all
標準ライブラリだけを使う。
"""

import argparse
import json
import shutil
import zipfile
from pathlib import Path

from icon import icon_png
from targets import PACK_NAME, ROOT, Target, add_target_args, resolve_targets

# 配布物に同梱する、リポジトリ直下のファイル(MIT ライセンスの条件に合わせて LICENSE を含める)
BUNDLED_FILES = ["LICENSE", "README.md"]

NAMESPACE = "workbench_strip"
# zip で導入するとパックIDが file/WorkbenchStrip.zip になるので、拡張子なしの名前を説明文の1行目に入れる
DESCRIPTION = f"{PACK_NAME}\n作業台で樹皮・錆・ロウを除去"  # 選択画面の幅に収まる長さにする

# 段階の接頭辞(通常→露出→風化→酸化の順)
STAGE_PREFIXES = ["", "exposed_", "weathered_", "oxidized_"]
WAX_PREFIX = "waxed_"


def conflicting_sources(target: Target) -> set[str]:
    """5章: 1個置きでバニラレシピと競合するため、2個→2個にする変換元。"""
    sources = (
        {f"{w}_log" for w in target.overworld_woods}
        | {f"{w}_wood" for w in target.overworld_woods}
        | {f"{w}_stem" for w in target.nether_woods}
        | {f"{w}_hyphae" for w in target.nether_woods}
        | {"waxed_copper_block"}
    )
    if target.bamboo:
        sources.add("bamboo_block")
    return sources


# zip 内のタイムスタンプを固定して、生成結果を再現できるようにする
ZIP_DATE_TIME = (1980, 1, 1, 0, 0, 0)


def copper_stage_id(family: str, prefix: str) -> str:
    """銅の系統と段階の接頭辞から、アイテムIDを返す。"""
    if family == "copper_block" and prefix:
        # ブロック系統だけは exposed_copper のように "_block" が付かない
        return f"{prefix}copper"
    return f"{prefix}{family}"


def build_conversions(target: Target) -> list[tuple[str, str, str]]:
    """(kind, from, to) の一覧を返す。"""
    conversions = []

    for wood in target.overworld_woods:
        for suffix in ("log", "wood"):
            conversions.append(("strip", f"{wood}_{suffix}", f"stripped_{wood}_{suffix}"))
    for wood in target.nether_woods:
        for suffix in ("stem", "hyphae"):
            conversions.append(("strip", f"{wood}_{suffix}", f"stripped_{wood}_{suffix}"))
    if target.bamboo:
        conversions.append(("strip", "bamboo_block", "stripped_bamboo_block"))

    for family in target.copper_families:
        stages = [copper_stage_id(family, prefix) for prefix in STAGE_PREFIXES]
        # 酸化→風化、風化→露出、露出→通常
        for i in range(len(stages) - 1, 0, -1):
            conversions.append(("scrape", stages[i], stages[i - 1]))

    for family in target.copper_families:
        for prefix in STAGE_PREFIXES:
            item = copper_stage_id(family, prefix)
            conversions.append(("unwax", f"{WAX_PREFIX}{item}", item))

    return conversions


def ingredient_json(style: str, source: str) -> dict:
    """材料1つ分の書式。版による違いは、版番号ではなく名前付きの書式で切り替える。"""
    if style == "item_object":
        return {"item": f"minecraft:{source}"}
    raise ValueError(f"未対応の recipe_ingredient_style: {style!r}")


def recipe_json(target: Target, source: str, result: str, count: int) -> dict:
    return {
        "type": "minecraft:crafting_shapeless",
        "category": "building",
        "ingredients": [ingredient_json(target.recipe_ingredient_style, source) for _ in range(count)],
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


def generate_pack(target: Target) -> list[str]:
    """build/<ターゲットID>/WorkbenchStrip/ を作り直し、生成したレシピIDの一覧を返す。"""
    pack_dir = target.pack_dir
    if pack_dir.exists():
        shutil.rmtree(pack_dir)

    write_json(
        pack_dir / "pack.mcmeta",
        {"pack": {"pack_format": target.pack_format, "description": DESCRIPTION}},
    )
    (pack_dir / "pack.png").write_bytes(icon_png())
    for name in BUNDLED_FILES:
        shutil.copyfile(ROOT / name, pack_dir / name)

    data_dir = pack_dir / "data" / NAMESPACE
    double_sources = conflicting_sources(target)
    recipe_ids = []
    for kind, source, result in build_conversions(target):
        count = 2 if source in double_sources else 1
        recipe_id = f"{NAMESPACE}:{kind}/{source}"
        write_json(data_dir / "recipe" / kind / f"{source}.json", recipe_json(target, source, result, count))
        # 変換元を手に入れたときに解放する(起動直後に全部は解放しない)
        write_json(
            data_dir / "advancement" / "recipes" / kind / f"{source}.json",
            unlock_advancement_json(source, recipe_id),
        )
        recipe_ids.append(recipe_id)
    return recipe_ids


def build_zip(target: Target) -> None:
    """パックの中身を、zip の直下に置く形でまとめる。"""
    zip_path = target.zip_path
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    if zip_path.exists():
        zip_path.unlink()

    files = sorted(p for p in target.pack_dir.rglob("*") if p.is_file() and p.name != ".DS_Store")
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in files:
            info = zipfile.ZipInfo(path.relative_to(target.pack_dir).as_posix(), date_time=ZIP_DATE_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, path.read_bytes())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    add_target_args(parser)
    for target in resolve_targets(parser.parse_args()):
        recipe_ids = generate_pack(target)
        build_zip(target)
        print(f"[{target.id}] generated {len(recipe_ids)} recipes -> {target.pack_dir.relative_to(ROOT)}/")
        print(f"[{target.id}] packed -> {target.zip_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
