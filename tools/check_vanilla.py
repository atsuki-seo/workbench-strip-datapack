#!/usr/bin/env python3
"""L2: 1.21.1 のバニラデータとの照合(ネットワーク必要)。

misode/mcmeta の固定コミットから、アイテムレジストリ・バニラレシピ・アイテムタグを取得し、
WorkbenchStrip/ の生成物と照合する。取得した内容はメモリ上でだけ使い、保存しない。
各ゴールについて `PASS <ID>` / `FAIL <ID>: <理由>` を1行ずつ出力し、FAIL が1つでもあれば終了コード1で終わる。
G-V4 は参考情報なので `INFO` として出力し、合否には使わない。
標準ライブラリだけを使う。
"""

import http.client
import json
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RECIPE_DIR = ROOT / "WorkbenchStrip" / "data" / "workbench_strip" / "recipe"
ADVANCEMENT_DIR = ROOT / "WorkbenchStrip" / "data" / "workbench_strip" / "advancement"

# 計画 1.1 の固定先
REPO = "misode/mcmeta"
DATA_SHA = "aacd2a457333b258d044a642f38270c8cddbc628"  # 1.21.1-data
SUMMARY_SHA = "7cffbcdad5fa36f22acef6bd4b869ecad4ca3fd9"  # 1.21.1-summary

VANILLA_RECIPE_PREFIX = "data/minecraft/recipe/"
VANILLA_ITEM_TAG_PREFIX = "data/minecraft/tags/item/"

EXPECTED_ITEM_IDS = 114
EXPECTED_VANILLA_RECIPES = 1290

# G-V3: 1個置きにしたときに一致するバニラレシピ(仕様書5章・計画 C7)
WOODS = ("oak", "spruce", "birch", "jungle", "acacia", "dark_oak", "mangrove", "cherry")
EXPECTED_SINGLE_CONFLICTS = (
    {(f"{w}_{s}", f"{w}_planks") for w in WOODS for s in ("log", "wood")}
    | {(f"{w}_{s}", f"{w}_planks") for w in ("crimson", "warped") for s in ("stem", "hyphae")}
    | {("bamboo_block", "bamboo_planks"), ("waxed_copper_block", "copper_ingot_from_waxed_copper_block")}
)

failures = 0


def report(goal_id: str, problems: list[str]) -> None:
    global failures
    if problems:
        failures += 1
        shown = "; ".join(problems[:5])
        if len(problems) > 5:
            shown += f"; ...(他 {len(problems) - 5} 件)"
        print(f"FAIL {goal_id}: {shown}")
    else:
        print(f"PASS {goal_id}")


def fetch(url: str, retries: int = 5) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "workbench-strip-check"})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read()
        except (OSError, http.client.HTTPException):
            if attempt == retries - 1:
                raise
            time.sleep(1 + attempt)
    raise AssertionError("unreachable")


def fetch_json(url: str):
    return json.loads(fetch(url).decode("utf-8"))


def raw_url(sha: str, path: str) -> str:
    return f"https://raw.githubusercontent.com/{REPO}/{sha}/{path}"


def load_vanilla() -> tuple[set[str], dict[str, dict], dict[str, dict], set[str], set[str]]:
    """(アイテムID集合, レシピ名→JSON, タグ名→JSON) を返す。IDは名前空間付き。"""
    registries = fetch_json(raw_url(SUMMARY_SHA, "registries/data.min.json"))
    items = {f"minecraft:{i}" for i in registries["item"]}
    triggers = {f"minecraft:{t}" for t in registries["trigger_type"]}

    tree = fetch_json(f"https://api.github.com/repos/{REPO}/git/trees/{DATA_SHA}?recursive=1")
    if tree.get("truncated"):
        raise RuntimeError("git tree の一覧が途中で切れている")
    blobs = [e["path"] for e in tree["tree"] if e["type"] == "blob" and e["path"].endswith(".json")]
    recipe_paths = [p for p in blobs if p.startswith(VANILLA_RECIPE_PREFIX)]
    tag_paths = [p for p in blobs if p.startswith(VANILLA_ITEM_TAG_PREFIX)]

    with ThreadPoolExecutor(max_workers=16) as pool:
        recipe_jsons = list(pool.map(lambda p: fetch_json(raw_url(DATA_SHA, p)), recipe_paths))
        tag_jsons = list(pool.map(lambda p: fetch_json(raw_url(DATA_SHA, p)), tag_paths))

    recipes = {p[len(VANILLA_RECIPE_PREFIX):-len(".json")]: j for p, j in zip(recipe_paths, recipe_jsons)}
    tags = {f"minecraft:{p[len(VANILLA_ITEM_TAG_PREFIX):-len('.json')]}": j for p, j in zip(tag_paths, tag_jsons)}
    advancement_prefix = "data/minecraft/advancement/"
    advancements = {f"minecraft:{p[len(advancement_prefix):-len('.json')]}" for p in blobs if p.startswith(advancement_prefix)}
    return items, recipes, tags, triggers, advancements


class Matcher:
    """1.21.1 の材料書式({item} / {tag} / その配列)が、あるアイテムを受け付けるかを判定する。"""

    def __init__(self, tags: dict[str, dict]):
        self.tags = tags
        self.cache: dict[str, frozenset[str]] = {}

    def expand_tag(self, tag: str, stack: tuple[str, ...] = ()) -> frozenset[str]:
        if tag in self.cache:
            return self.cache[tag]
        if tag in stack:
            raise RuntimeError(f"タグが循環している: {' -> '.join(stack + (tag,))}")
        result = set()
        for value in self.tags.get(tag, {}).get("values", []):
            ref = value["id"] if isinstance(value, dict) else value
            if ref.startswith("#"):
                result |= self.expand_tag(ref[1:], stack + (tag,))
            else:
                result.add(ref)
        self.cache[tag] = frozenset(result)
        return self.cache[tag]

    def accepts(self, ingredient, item: str) -> bool:
        if isinstance(ingredient, list):
            return any(self.accepts(alt, item) for alt in ingredient)
        if "item" in ingredient:
            return ingredient["item"] == item
        if "tag" in ingredient:
            return item in self.expand_tag(ingredient["tag"])
        raise RuntimeError(f"未知の材料の書式: {ingredient!r}")


def conflicts(recipes: dict[str, dict], matcher: Matcher, item: str, n: int) -> list[str]:
    """item を n 個置いたときに一致するバニラレシピ名の一覧(計画 1.2 の判定方法)。"""
    found = []
    for name, r in recipes.items():
        rtype = r.get("type")
        if rtype == "minecraft:crafting_shapeless":
            ings = r["ingredients"]
            if len(ings) == n and all(matcher.accepts(i, item) for i in ings):
                found.append(name)
        elif rtype == "minecraft:crafting_shaped":
            cells = [c for row in r["pattern"] for c in row if c != " "]
            if len(cells) == n and all(matcher.accepts(r["key"][c], item) for c in cells):
                found.append(name)
    return sorted(found)


def load_pack_recipes() -> list[tuple[str, str, str, int]]:
    """(kind, 変換元ID, 変換先ID, 個数) の一覧。IDは名前空間付き。"""
    rows = []
    for path in sorted(RECIPE_DIR.glob("*/*.json")):
        r = json.loads(path.read_text(encoding="utf-8"))
        rows.append((path.parent.name, r["ingredients"][0]["item"], r["result"]["id"], len(r["ingredients"])))
    return rows


def main() -> int:
    pack = load_pack_recipes()
    if len(pack) != 84:
        print(f"FAIL G-V1: 生成物のレシピが {len(pack)} 件(期待 84)。先に tools/generate.py を実行する")
        return 1

    try:
        items, recipes, tags, triggers, vanilla_advancements = load_vanilla()
    except (OSError, http.client.HTTPException, RuntimeError, KeyError, json.JSONDecodeError) as e:
        print(f"FAIL G-V1: バニラデータを取得できない: {e}")
        return 1
    print(f"INFO 取得: item レジストリ {len(items)} 件、バニラレシピ {len(recipes)} 件、アイテムタグ {len(tags)} 件")
    matcher = Matcher(tags)

    # G-V1
    used = {src for _, src, _, _ in pack} | {dst for _, _, dst, _ in pack}
    problems = [f"1.21.1 に存在しない: {i}" for i in sorted(used - items)]
    if len(used) != EXPECTED_ITEM_IDS:
        problems.append(f"生成物のアイテムIDが {len(used)} 種(期待 {EXPECTED_ITEM_IDS})")
    report("G-V1", problems)

    # G-V2
    problems = []
    for kind, src, _, n in pack:
        hit = conflicts(recipes, matcher, src, n)
        if hit:
            problems.append(f"{kind}/{src} ×{n} がバニラの {hit} と一致する")
    report("G-V2", problems)

    # G-V3
    problems = []
    if len(recipes) != EXPECTED_VANILLA_RECIPES:
        problems.append(f"バニラレシピが {len(recipes)} 件(期待 {EXPECTED_VANILLA_RECIPES})")
    single = {(src.removeprefix("minecraft:"), hit) for _, src, _, _ in pack for hit in conflicts(recipes, matcher, src, 1)}
    problems += [f"想定外の競合: {pair}" for pair in sorted(single - EXPECTED_SINGLE_CONFLICTS)]
    problems += [f"検出されなかった競合: {pair}" for pair in sorted(EXPECTED_SINGLE_CONFLICTS - single)]
    report("G-V3", problems)

    # G-V5: 解放用の進捗が使うトリガー・親の進捗・アイテムが 1.21.1 に存在する
    problems = []
    adv_files = sorted(ADVANCEMENT_DIR.rglob("*.json"))
    if len(adv_files) != 84:
        problems.append(f"解放用の進捗が {len(adv_files)} 件(期待 84)")
    for path in adv_files:
        adv = json.loads(path.read_text(encoding="utf-8"))
        rel = path.relative_to(ADVANCEMENT_DIR).as_posix()
        parent = adv.get("parent")
        if parent is not None and parent not in vanilla_advancements:
            problems.append(f"{rel}: 親の進捗 {parent} が 1.21.1 にない")
        for name, crit in adv.get("criteria", {}).items():
            if crit.get("trigger") not in triggers:
                problems.append(f"{rel}: {name} のトリガー {crit.get('trigger')} が 1.21.1 にない")
            for pred in crit.get("conditions", {}).get("items", []):
                if pred.get("items") not in items:
                    problems.append(f"{rel}: {name} のアイテム {pred.get('items')} が 1.21.1 にない")
    report("G-V5", problems)

    # G-V4(参考情報)
    double = sorted((src.removeprefix("minecraft:"), hit) for _, src, _, _ in pack for hit in conflicts(recipes, matcher, src, 2))
    print(f"INFO G-V4: 全84件を2個置きにした場合の競合 {len(double)} 件")
    for src, hit in double:
        print(f"INFO G-V4:   {src} ×2 -> {hit}")

    print(f"{'NG' if failures else 'OK'}: FAIL {failures} 件")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
