# WorkbenchStrip

作業台のクラフトで、斧の右クリックと同じ「樹皮はぎ・錆び落とし・ロウ除去」ができる Minecraft Java Edition 用のデータパックです。

- 対象: Minecraft Java Edition **1.21.1**(`pack_format` 48)
- Mod・コマンドは不要。斧も不要で、耐久値も減りません

## できること

| 機能 | 件数 | 例 |
|---|---|---|
| 樹皮はぎ | 21 | `oak_log` ×2 → `stripped_oak_log` ×2 |
| 錆び落とし(1回で1段階) | 27 | `oxidized_copper` ×1 → `weathered_copper` ×1 |
| ロウ除去 | 36 | `waxed_exposed_cut_copper_slab` ×1 → `exposed_cut_copper_slab` ×1 |

- 樹皮はぎ: 1.21.1 の木材11種(oak、spruce、birch、jungle、acacia、dark_oak、mangrove、cherry、crimson、warped、bamboo)の原木・木・幹・菌糸・竹ブロックすべて
- 錆び落とし・ロウ除去: 銅の9系統(ブロック・カット・階段・ハーフ・チゼル・グレート・バルブ・ドア・トラップドア)
- 原木・木・幹・菌糸・竹ブロック・錆止めされた銅ブロックの22件は、バニラのレシピ(板材・銅インゴット)と重ならないように「同じ素材2個 → 2個」です。1個だけ置いた場合は、今までどおり板材などになります
- レシピは、変換元のアイテムを手に入れたときにレシピブックへ解放されます

## 導入

1. [Releases](https://github.com/atsuki-seo/workbench-strip-datapack/releases) から `WorkbenchStrip.zip` をダウンロードします。
2. ワールドの `datapacks` フォルダに、zip のまま置きます。
3. ワールドに入っている場合は `/reload` を実行します。

導入前にワールドのバックアップを取っておくことをおすすめします。共有サーバーでは全プレイヤーのレシピに影響するため、管理者や参加者に確認してから導入してください。

## 制約

- 変換できるのはアイテムとして持っているブロックだけです。設置済みのブロックには作用しません
- 看板・吊り看板のロウ除去には対応していません
- ペールオーク(1.21.2 以降で追加)には対応していません

## 開発

Python 3 の標準ライブラリだけで動きます。

| コマンド | 内容 |
|---|---|
| `python3 tools/generate.py` | `WorkbenchStrip/`(データパック本体)と `dist/WorkbenchStrip.zip` を生成する |
| `python3 tools/check_static.py` | オフラインの静的検証。`tests/expected_conversions.tsv` を正解として生成物を検証する(生成もやり直す) |
| `python3 tools/check_vanilla.py` | 1.21.1 のバニラデータ([misode/mcmeta](https://github.com/misode/mcmeta) の固定コミット)と照合する。ネットワークが必要 |

検証スクリプトは、すべて合格すると終了コード0で終わります。設計と検証の詳細は [plans/workbench-strip-plan.md](plans/workbench-strip-plan.md) にあります。

## ライセンス

[MIT License](LICENSE)

NOT AN OFFICIAL MINECRAFT PRODUCT. NOT APPROVED BY OR ASSOCIATED WITH MOJANG OR MICROSOFT.
