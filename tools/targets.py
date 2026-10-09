"""ターゲット(対応する Minecraft のバージョン)の設定を読み込む共通モジュール。

ターゲット1つにつき targets/<ターゲットID>.json を1つ置く。各スクリプトの --target / --all の解決もここで行う。
標準ライブラリだけを使う。
"""

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGETS_DIR = ROOT / "targets"
PACK_NAME = "WorkbenchStrip"

# 材料の書き方の違いは、版番号の比較ではなく、この名前付きの設定値で切り替える
INGREDIENT_STYLES = ("item_object",)


@dataclass(frozen=True)
class Target:
    id: str
    pack_format: int
    recipe_ingredient_style: str
    mcmeta_data_sha: str
    mcmeta_summary_sha: str
    overworld_woods: tuple[str, ...]
    nether_woods: tuple[str, ...]
    bamboo: bool
    copper_families: tuple[str, ...]
    minecraft_verified: str

    @property
    def build_dir(self) -> Path:
        return ROOT / "build" / self.id

    @property
    def pack_dir(self) -> Path:
        return self.build_dir / PACK_NAME

    @property
    def expected_tsv(self) -> Path:
        return ROOT / "tests" / self.id / "expected_conversions.tsv"

    @property
    def zip_path(self) -> Path:
        return ROOT / "dist" / dist_zip_name(self.id)


def target_ids() -> list[str]:
    return sorted(p.stem for p in TARGETS_DIR.glob("*.json"))


def dist_zip_name(target_id: str) -> str:
    """配布物の名前。ターゲットが1つの間は WorkbenchStrip.zip のまま、2つ以上になったら版を付ける。"""
    if len(target_ids()) <= 1:
        return f"{PACK_NAME}.zip"
    return f"{PACK_NAME}-{target_id}.zip"


def load_target(target_id: str) -> Target:
    path = TARGETS_DIR / f"{target_id}.json"
    if not path.is_file():
        raise SystemExit(f"ターゲット {target_id!r} がない(targets/{target_id}.json)。あるのは: {', '.join(target_ids())}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if raw["id"] != target_id:
        raise SystemExit(f"{path.name}: id {raw['id']!r} がファイル名と一致しない")
    style = raw["recipe_ingredient_style"]
    if style not in INGREDIENT_STYLES:
        raise SystemExit(f"{path.name}: 未対応の recipe_ingredient_style {style!r}(対応: {', '.join(INGREDIENT_STYLES)})")
    return Target(
        id=raw["id"],
        pack_format=raw["pack_format"],
        recipe_ingredient_style=style,
        mcmeta_data_sha=raw["mcmeta"]["data"],
        mcmeta_summary_sha=raw["mcmeta"]["summary"],
        overworld_woods=tuple(raw["woods"]["overworld"]),
        nether_woods=tuple(raw["woods"]["nether"]),
        bamboo=raw["woods"]["bamboo"],
        copper_families=tuple(raw["copper_families"]),
        minecraft_verified=raw["minecraft"]["verified"],
    )


def add_target_args(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--target", metavar="ID", help="対象のターゲットID(例: mc1.21.1)")
    group.add_argument("--all", action="store_true", help="targets/ にある全ターゲットを対象にする")


def resolve_targets(args: argparse.Namespace) -> list[Target]:
    ids = target_ids() if args.all else [args.target]
    if not ids:
        raise SystemExit("targets/ にターゲットがない")
    return [load_target(i) for i in ids]
