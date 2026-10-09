#!/usr/bin/env python3
"""L0・L1: 期待値表と生成物のオフライン静的検証。

tests/<ターゲットID>/expected_conversions.tsv を正解として、build/<ターゲットID>/WorkbenchStrip/ と dist/ の zip を検証する。
使い方: check_static.py --target <ターゲットID> | --all
各ゴールについて `PASS <ID>` / `FAIL <ID>: <理由>` を1行ずつ出力し、FAIL が1つでもあれば終了コード1で終わる。
標準ライブラリだけを使う。
"""

import argparse
import hashlib
import json
import struct
import subprocess
import sys
import zipfile
from collections import Counter
from pathlib import Path

from targets import PACK_NAME, ROOT, Target, add_target_args, resolve_targets

GENERATE = ROOT / "tools" / "generate.py"

NAMESPACE = "workbench_strip"
KINDS = ("strip", "scrape", "unwax")
EXPECTED_COUNTS = {"strip": 21, "scrape": 27, "unwax": 36}
TOTAL = 84
ADVANCEMENT_PREFIX = f"data/{NAMESPACE}/advancement/recipes/"
ICON_REL = "pack.png"
# リポジトリ直下からパックのルートに同梱するファイル
BUNDLED_FILES = ("LICENSE", "README.md")
ICON_SIZE = 128
RECIPE_PREFIX = f"data/{NAMESPACE}/recipe/"

# G-E2: 2個置きになるべき変換元(仕様書5章を直接書き起こしたもの)
EXPECTED_DOUBLE_SOURCES = (
    {f"{w}_{s}" for w in ("oak", "spruce", "birch", "jungle", "acacia", "dark_oak", "mangrove", "cherry")
     for s in ("log", "wood")}
    | {f"{w}_{s}" for w in ("crimson", "warped") for s in ("stem", "hyphae")}
    | {"bamboo_block", "waxed_copper_block"}
)

JUNK_NAMES = (".DS_Store", "Thumbs.db", "desktop.ini")

failures = 0
current_label = ""


def report(goal_id: str, problems: list[str]) -> None:
    global failures
    if problems:
        failures += 1
        shown = "; ".join(problems[:5])
        if len(problems) > 5:
            shown += f"; ...(他 {len(problems) - 5} 件)"
        print(f"FAIL {current_label}{goal_id}: {shown}")
    else:
        print(f"PASS {current_label}{goal_id}")


def load_expected(target: Target) -> list[tuple[str, str, str, int]]:
    rows = []
    tsv = target.expected_tsv
    for lineno, line in enumerate(tsv.read_text(encoding="utf-8").splitlines(), 1):
        if not line:
            continue
        cols = line.split("\t")
        if len(cols) != 4:
            raise ValueError(f"{tsv.relative_to(ROOT)}:{lineno}: 列数が4ではない")
        kind, src, dst, n = cols
        rows.append((kind, src, dst, int(n)))
    return rows


def pack_files(target: Target) -> dict[str, bytes]:
    """build/<ターゲットID>/WorkbenchStrip/ 配下の全ファイル(パック内の相対パス → 内容)。"""
    return {
        p.relative_to(target.pack_dir).as_posix(): p.read_bytes()
        for p in sorted(target.pack_dir.rglob("*"))
        if p.is_file()
    }


def tree_digest(target: Target) -> dict[str, str]:
    return {rel: hashlib.sha256(data).hexdigest() for rel, data in pack_files(target).items()}


def run_generate(target: Target) -> None:
    subprocess.run([sys.executable, str(GENERATE), "--target", target.id], check=True, stdout=subprocess.DEVNULL)


def check_expected(expected: list[tuple[str, str, str, int]]) -> None:
    counts = Counter(kind for kind, *_ in expected)
    problems = [f"{k}: {counts.get(k, 0)} 件(期待 {v})" for k, v in EXPECTED_COUNTS.items() if counts.get(k, 0) != v]
    extra = set(counts) - set(EXPECTED_COUNTS)
    if extra:
        problems.append(f"未知の kind: {sorted(extra)}")
    report("G-E1", problems)

    doubles = [row for row in expected if row[3] == 2]
    problems = []
    if len(doubles) != 22:
        problems.append(f"2個置きが {len(doubles)} 行(期待 22)")
    sources = {src for _, src, _, _ in doubles}
    if sources != EXPECTED_DOUBLE_SOURCES:
        problems.append(f"過不足: 余分 {sorted(sources - EXPECTED_DOUBLE_SOURCES)} 不足 {sorted(EXPECTED_DOUBLE_SOURCES - sources)}")
    bad_n = [src for _, src, _, n in expected if n not in (1, 2)]
    if bad_n:
        problems.append(f"n が1か2でない: {bad_n}")
    report("G-E2", problems)

    dup = [src for src, c in Counter(src for _, src, _, _ in expected).items() if c > 1]
    report("G-E3", [f"重複した from: {dup}"] if dup else [])


def check_pack(target: Target, files: dict[str, bytes], expected: list[tuple[str, str, str, int]]) -> None:
    # 読み込み(G-S9 の UTF-8 / JSON 判定を兼ねる)
    parsed: dict[str, object] = {}
    parse_problems = []
    for rel, data in files.items():
        if rel == ICON_REL or rel in BUNDLED_FILES:
            continue
        try:
            parsed[rel] = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            parse_problems.append(f"{rel}: {e}")

    # G-S1
    problems = []
    mcmeta = parsed.get("pack.mcmeta")
    if not isinstance(mcmeta, dict) or not isinstance(mcmeta.get("pack"), dict):
        problems.append("pack.mcmeta がない、または pack オブジェクトがない")
    else:
        pack = mcmeta["pack"]
        if pack.get("pack_format") != target.pack_format or isinstance(pack.get("pack_format"), bool):
            problems.append(f"pack_format が {pack.get('pack_format')!r}(期待 {target.pack_format})")
        desc = pack.get("description")
        if not isinstance(desc, str) or not desc:
            problems.append(f"description が空でない文字列ではない: {desc!r}")
        elif desc.split("\n")[0] != PACK_NAME:
            problems.append(f"description の1行目が {PACK_NAME} ではない: {desc!r}")
    report("G-S1", problems)

    # G-S2
    problems = []
    for rel in files:
        if rel in ("pack.mcmeta", ICON_REL, *BUNDLED_FILES):
            continue
        parts = rel.split("/")
        is_recipe = rel.startswith(RECIPE_PREFIX) and len(parts) == 5 and parts[3] in KINDS
        is_advancement = rel.startswith(ADVANCEMENT_PREFIX) and len(parts) == 6 and parts[4] in KINDS
        if not ((is_recipe or is_advancement) and rel.endswith(".json")):
            problems.append(f"想定外のファイル: {rel}")
    for required in ("pack.mcmeta", ICON_REL, *BUNDLED_FILES):
        if required not in files:
            problems.append(f"必須ファイルがない: {required}")
    # 1.21 からは data/<名前空間>/ 直下のフォルダ名が単数形(advancement/recipes/ のような下位のフォルダは対象外)
    plural = [p for p in (target.pack_dir / "data").glob("*/*") if p.is_dir() and p.name in ("recipes", "advancements")]
    problems += [f"複数形のフォルダがある: {p.relative_to(target.pack_dir)}" for p in plural]
    report("G-S2", problems)

    recipes = {rel: obj for rel, obj in parsed.items() if rel.startswith(RECIPE_PREFIX)}

    # G-S3
    counts = Counter(rel.split("/")[3] for rel in recipes)
    problems = [f"{k}: {counts.get(k, 0)} 件(期待 {v})" for k, v in EXPECTED_COUNTS.items() if counts.get(k, 0) != v]
    if len(recipes) != TOTAL:
        problems.append(f"合計 {len(recipes)} 件(期待 {TOTAL})")
    report("G-S3", problems)

    # G-S4
    problems = []
    for rel, r in recipes.items():
        if not isinstance(r, dict) or set(r) != {"type", "category", "ingredients", "result"}:
            problems.append(f"{rel}: 最上位のキーが {sorted(r) if isinstance(r, dict) else type(r).__name__}")
            continue
        if r["type"] != "minecraft:crafting_shapeless":
            problems.append(f"{rel}: type が {r['type']!r}")
        if r["category"] != "building":
            problems.append(f"{rel}: category が {r['category']!r}")
        ings = r["ingredients"]
        if not isinstance(ings, list) or not ings:
            problems.append(f"{rel}: ingredients が空でないリストではない")
        else:
            for ing in ings:
                if not isinstance(ing, dict) or set(ing) != {"item"} or not isinstance(ing["item"], str):
                    problems.append(f"{rel}: ingredients の要素が {{item}} だけの dict ではない: {ing!r}")
        res = r["result"]
        if not isinstance(res, dict) or set(res) != {"id", "count"}:
            problems.append(f"{rel}: result のキーが {{id, count}} ではない: {res!r}")
    report("G-S4", problems)

    # 以降のチェックは G-S4 の形を前提に、壊れた要素は飛ばして読む
    def shape_ok(r) -> bool:
        return (
            isinstance(r, dict)
            and isinstance(r.get("ingredients"), list)
            and all(isinstance(i, dict) and isinstance(i.get("item"), str) for i in r["ingredients"])
            and isinstance(r.get("result"), dict)
            and isinstance(r["result"].get("id"), str)
        )

    # G-S5
    problems = []
    for rel, r in recipes.items():
        if not shape_ok(r):
            problems.append(f"{rel}: 形が不正で判定できない")
            continue
        items = {i["item"] for i in r["ingredients"]}
        count = r["result"].get("count")
        if len(items) != 1:
            problems.append(f"{rel}: 材料が1種類ではない: {sorted(items)}")
        if count not in (1, 2) or isinstance(count, bool):
            problems.append(f"{rel}: count が {count!r}")
        elif len(r["ingredients"]) != count:
            problems.append(f"{rel}: 材料 {len(r['ingredients'])} 個に対して count {count}")
    report("G-S5", problems)

    # G-S6・G-S7
    expected_kind = {src: kind for kind, src, _, _ in expected}
    problems_s6 = []
    actual = set()
    for rel, r in recipes.items():
        if not shape_ok(r):
            problems_s6.append(f"{rel}: 形が不正で判定できない")
            continue
        kind, stem = rel.split("/")[3], Path(rel).stem
        item = r["ingredients"][0]["item"]
        if item != f"minecraft:{stem}":
            problems_s6.append(f"{rel}: ファイル名と材料 {item} が一致しない")
        if expected_kind.get(stem) != kind:
            problems_s6.append(f"{rel}: フォルダ {kind} が期待値表の kind {expected_kind.get(stem)} と一致しない")
        actual.add((
            kind,
            item.removeprefix("minecraft:"),
            r["result"]["id"].removeprefix("minecraft:"),
            len(r["ingredients"]),
        ))
    report("G-S6", problems_s6)

    expected_set = set(expected)
    problems = [f"期待値表にない: {row}" for row in sorted(actual - expected_set)]
    problems += [f"生成物にない: {row}" for row in sorted(expected_set - actual)]
    report("G-S7", problems)

    # G-S8: 変換元ごとに、そのアイテムを持ったときにそのレシピだけを解放する進捗がある
    # (1.21.1 のバニラ data/minecraft/advancement/recipes/building_blocks/chiseled_copper.json と同じ形)
    problems = []
    advancements = {rel: obj for rel, obj in parsed.items() if rel.startswith(ADVANCEMENT_PREFIX)}
    want_files = set()
    for kind, src, _, _ in expected:
        rel = f"{ADVANCEMENT_PREFIX}{kind}/{src}.json"
        want_files.add(rel)
        recipe_id = f"{NAMESPACE}:{kind}/{src}"
        want = {
            "parent": "minecraft:recipes/root",
            "criteria": {
                f"has_{src}": {
                    "conditions": {"items": [{"items": f"minecraft:{src}"}]},
                    "trigger": "minecraft:inventory_changed",
                },
                "has_the_recipe": {
                    "conditions": {"recipe": recipe_id},
                    "trigger": "minecraft:recipe_unlocked",
                },
            },
            "requirements": [["has_the_recipe", f"has_{src}"]],
            "rewards": {"recipes": [recipe_id]},
        }
        if rel not in advancements:
            problems.append(f"進捗がない: {rel}")
        elif advancements[rel] != want:
            problems.append(f"内容が想定と違う: {rel}")
    problems += [f"想定外の進捗: {rel}" for rel in sorted(set(advancements) - want_files)]
    ticks = [rel for rel, obj in parsed.items() if '"minecraft:tick"' in json.dumps(obj)]
    problems += [f"起動直後に達成される minecraft:tick を使っている: {rel}" for rel in ticks]
    report("G-S8", problems)

    # G-S9
    problems = list(parse_problems)
    for rel, r in recipes.items():
        if not shape_ok(r):
            continue
        ids = [i["item"] for i in r["ingredients"]] + [r["result"]["id"]]
        problems += [f"{rel}: {i} が minecraft: で始まらない" for i in ids if not i.startswith("minecraft:")]
    report("G-S9", problems)

    # G-S11
    problems = []
    icon = files.get(ICON_REL)
    if icon is None:
        problems.append("pack.png がない")
    elif icon[:8] != b"\x89PNG\r\n\x1a\n" or icon[12:16] != b"IHDR":
        problems.append("pack.png が PNG ではない")
    else:
        width, height = struct.unpack(">II", icon[16:24])
        if (width, height) != (ICON_SIZE, ICON_SIZE):
            problems.append(f"pack.png が {width}x{height}(期待 {ICON_SIZE}x{ICON_SIZE})")
    report("G-S11", problems)

    # G-S12
    problems = []
    if not target.pack_dir.is_dir():
        problems.append(f"{target.pack_dir.relative_to(ROOT)}/ がない")
    if not target.zip_path.is_file():
        problems.append(f"{target.zip_path.relative_to(ROOT)} がない")
    # 旧名・旧配置(build/ に移す前はリポジトリ直下の WorkbenchStrip/)の生成物
    stale = [p.relative_to(ROOT).as_posix() for p in (ROOT / "workbench_strip", ROOT / "dist" / "workbench_strip.zip", ROOT / PACK_NAME) if p.exists()]
    problems += [f"旧名・旧配置の生成物が残っている: {p}" for p in stale]
    report("G-S12", problems)

    # G-S13
    problems = []
    for name in BUNDLED_FILES:
        source = ROOT / name
        if not source.is_file():
            problems.append(f"リポジトリ直下に {name} がない")
        elif files.get(name) != source.read_bytes():
            problems.append(f"{target.pack_dir.relative_to(ROOT)}/{name} がリポジトリ直下の {name} と一致しない")
    report("G-S13", problems)


def check_zip(target: Target, files: dict[str, bytes]) -> None:
    zip_path = target.zip_path
    if not zip_path.is_file():
        for goal in ("G-Z1", "G-Z2", "G-Z3"):
            report(goal, [f"{zip_path.relative_to(ROOT)} がない"])
        return

    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        contents = {n: zf.read(n) for n in names if not n.endswith("/")}

    problems = []
    if "pack.mcmeta" not in names:
        problems.append("zip の直下に pack.mcmeta がない")
    nested = [n for n in names if n.endswith("/pack.mcmeta")]
    if nested:
        problems.append(f"{nested} がある(フォルダごと zip にしている)")
    report("G-Z1", problems)

    problems = [f"zip にだけある: {n}" for n in sorted(set(contents) - set(files))]
    problems += [f"フォルダにだけある: {n}" for n in sorted(set(files) - set(contents))]
    problems += [f"内容が異なる: {n}" for n in sorted(set(files) & set(contents)) if files[n] != contents[n]]
    report("G-Z2", problems)

    junk = [n for n in names if n.startswith("__MACOSX/") or Path(n).name in JUNK_NAMES or Path(n).name.startswith("._")]
    report("G-Z3", [f"余計なファイル: {junk}"] if junk else [])


def check_target(target: Target) -> None:
    global current_label
    current_label = f"[{target.id}] "

    try:
        expected = load_expected(target)
    except (OSError, ValueError) as e:
        report("G-E1", [f"期待値表を読めない: {e}"])
        return
    check_expected(expected)

    # G-S10: 2回生成して、全ファイルの SHA-256 一覧が同じことを確認する。以降のチェックはこの生成物を対象にする
    def zip_digest() -> str | None:
        return hashlib.sha256(target.zip_path.read_bytes()).hexdigest() if target.zip_path.is_file() else None

    run_generate(target)
    first, first_zip = tree_digest(target), zip_digest()
    run_generate(target)
    second, second_zip = tree_digest(target), zip_digest()
    problems = [f"内容が変わった: {rel}" for rel in sorted(set(first) | set(second)) if first.get(rel) != second.get(rel)]
    zip_rel = target.zip_path.relative_to(ROOT)
    if not first:
        problems.append(f"{target.pack_dir.relative_to(ROOT)}/ が生成されていない")
    if first_zip is None:
        problems.append(f"{zip_rel} が生成されていない")
    elif first_zip != second_zip:
        problems.append(f"{zip_rel} の内容が変わった")
    report("G-S10", problems)

    files = pack_files(target)
    check_pack(target, files, expected)
    check_zip(target, files)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    add_target_args(parser)
    for target in resolve_targets(parser.parse_args()):
        check_target(target)

    print(f"{'NG' if failures else 'OK'}: FAIL {failures} 件")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
