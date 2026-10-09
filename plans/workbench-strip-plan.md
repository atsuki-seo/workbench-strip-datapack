# 実装計画: WorkbenchStrip データパック

- 元仕様: `~/Downloads/workbench_strip_spec.md`(以下「仕様書」)
- 作成日: 2026-10-10
- 対象: Minecraft Java Edition 1.21.1 / `pack_format` 48 / 名前空間 `workbench_strip`
- 正式名: **WorkbenchStrip**(フォルダ名・zip のファイル名で表す。D5)

この計画は、仕様書を一次データと突き合わせて再調査した結果(第1章)と、タスク分解(第3章)、機械的に合否を判定できるゴール(第4章)をまとめたものです。

---

## 1. 再調査の結果

### 1.1 参照した一次データ

| 略称 | 内容 | 固定先 |
|---|---|---|
| mcmeta-data | 1.21.1 のバニラデータ(レシピ・タグ・進捗) | `misode/mcmeta` タグ `1.21.1-data` = `aacd2a457333b258d044a642f38270c8cddbc628` |
| mcmeta-assets | 1.21.1 のアセット(アイテムモデル) | `misode/mcmeta` タグ `1.21.1-assets` = `451045f224aefbb4d2f91b1adf04f9a04df40820` |
| mcmeta-summary | 1.21.1 のレジストリ一覧 | `misode/mcmeta` タグ `1.21.1-summary` = `7cffbcdad5fa36f22acef6bd4b869ecad4ca3fd9` |
| wiki | Minecraft Wiki の `Pack_format` / `Data_pack` / `Java_Edition_1.21.2` | — |

mcmeta はバニラのデータジェネレーター出力を版ごとにタグ付けしたリポジトリです。本計画ではこれを「1.21.1 の正解データ」として扱います(公式配布物そのものではない点は制約として残ります)。

### 1.2 仕様書の主張の検証

| # | 仕様書の主張 | 結果 | 根拠 |
|---|---|---|---|
| C1 | 1.21.1 のデータパックは `pack_format` 48 | 正しい | wiki `Pack_format`: 48 は 1.21–1.21.1、57 は 1.21.2–1.21.3 |
| C2 | 1.21.1 の `ingredients` は `{ "item": ... }` 形式。文字列形式は 1.21.2 以降 | 正しい | mcmeta の `oak_planks.json` が 1.21.1 では `{"tag": "minecraft:oak_logs"}`、1.21.2 では `"#minecraft:oak_logs"` |
| C3 | `result` は `{ "id", "count" }` | 正しい | mcmeta-data の `oak_planks.json` / `copper_ingot_from_waxed_copper_block.json` |
| C4 | 1.21 からフォルダ名は単数形(`recipe` / `advancement`) | 正しい | wiki `Data_pack`(24w21a で改名)。mcmeta-data でも `data/minecraft/recipe/` `data/minecraft/advancement/` |
| C5 | 3章の変換元・変換先(84件、計114種のID)はすべて 1.21.1 に存在する | 正しい | 114種すべてについて mcmeta-assets の `models/item/<id>.json` が HTTP 200。mcmeta-summary の `item` レジストリ(1333件)にも `waxed_copper_block` がある |
| C6 | ペールオークは 1.21.1 に存在しない | 正しい | mcmeta-summary の `item` に `pale_oak_log` がない。1.21.1-assets では 404、1.21.4-assets では 200 |
| C7 | 1個置きで競合するバニラレシピは 22 件(原木・木・幹・菌糸 20、竹ブロック 1、錆止めされた銅ブロック 1) | 正しい | 1.21.1 のバニラレシピ全1290件(crafting_shaped 634、crafting_shapeless 253 など)を機械判定。1個置きで一致したのは仕様書の表と同じ22件(`*_planks` 20、`bamboo_planks`、`copper_ingot_from_waxed_copper_block`)だけ |
| C8 | 競合する22件は2個置きにすれば競合しない | 正しい | 同じ機械判定で、上記22件の変換元を2個置いたときに一致するバニラレシピは0件 |
| C9 | 進捗トリガー `minecraft:tick` が使える | 正しい | mcmeta-summary の `trigger_type` レジストリに `tick` がある |
| C10 | 2つのレシピが一致したときの結果は、読み込み順や直前に使ったレシピで決まる | 未確認 | ゲームのソースコードは確認していない。採用方針では競合が0件になるので、この計画には影響しない |

機械判定の方法: 変換元アイテム X を n 個置いたとき、次のどちらかに当てはまるバニラレシピがあれば「競合」とする。

- `crafting_shapeless` で、材料がちょうど n 個あり、すべての材料が X を受け付ける
- `crafting_shaped` で、パターンの空きでないマスがちょうど n 個あり、それらすべてのキーが X を受け付ける

タグは mcmeta-data の `tags/item/` を再帰的に展開する。`crafting_special_*` は対象外(どれも原木や銅ブロックを材料にしない、という推論による)。

### 1.3 新しく分かったこと・仕様書の曖昧な点

| # | 内容 | 計画での扱い |
|---|---|---|
| F1 | **別案B(全部2個→2個)には、仕様書にない競合が7件ある。** `*cut_copper_slab` を2個縦に並べると、バニラの shaped レシピ `*chiseled_copper` に一致する。該当するのは `oxidized_` / `weathered_` / `exposed_` の3件と、`waxed_` の4段階で、計7件 | 確定した方針(D1)ではハーフは1個→1個なので影響しない |
| F2 | 8章の「`workbench_strip` フォルダを zip にまとめる」は、zip の直下に `workbench_strip/` フォルダができる手順とも読める。wiki では、`pack.mcmeta` がデータパックのルートにあることでパックを認識する | zip の**直下**に `pack.mcmeta` と `data/` を置く、と定義する(G-Z1) |
| F3 | 10.3 の #21「84件のレシピが表示される」は、手で数えるのが現実的ではない | 機械判定の代替案を L4 に置く(`/data get entity @s recipeBook` の出力を数える。1.21.1 のプレイヤーデータでこれが読めるかは**未確認**) |
| F4 | 10.1 の #1「`/datapack list` で有効」の出力形式は確認していない | L3 では `WorkbenchStrip` を含む行が出ることだけを判定する |
| F5 | 3.3 の「`waxed_` + 通常ID」は、各段階のIDに `waxed_` を付けるという意味(例: `copper_block` → `waxed_copper_block`、`exposed_copper` → `waxed_exposed_copper`) | この解釈で期待値表を作る。C5 で全IDの存在を確認済み |

### 1.4 ローカル環境(2026-10-10 時点)

| ツール | 状態 |
|---|---|
| python3 | 3.14.5 あり |
| jq / zip / unzip | あり |
| node / npm | あり |
| Java | **なし**(`java -version` が "Unable to locate a Java Runtime")。L3 の実サーバー検証には Java の導入が必要 |
| git | 作業ディレクトリは git リポジトリではない |

---

## 2. 要判断事項と、この計画の前提

D1・D2 は 2026-10-10 に利用者が仕様書のおすすめ案で確定した。

| # | 判断事項 | 結論 | 状態 | 参考: 採用しなかった案 |
|---|---|---|---|---|
| D1 | 競合する22件の方針(仕様書 11章-1) | 「22件だけ2個→2個」。残り62件は1個→1個 | **確定** | 別案A(石切台)は作業台ではなくなる。別案B(全部2個→2個)は F1 の7件の競合が出る |
| D2 | 進捗でレシピを解放するか(仕様書 11章-2) | 解放する。2026-10-10 に利用者の依頼で方式を変更: 起動直後(`minecraft:tick`)に全84件を解放するのをやめ、レシピごとの進捗84件で、**変換元のアイテムを手に入れたときにそのレシピだけを解放する**。形は 1.21.1 のバニラ(`recipes/building_blocks/chiseled_copper.json` など)と同じで、`inventory_changed` か `recipe_unlocked` で達成し、親は `minecraft:recipes/root`。仕様書6章の「最初の tick で解放」とは異なる | **確定** | 解放しない場合、レシピブックに表示されない。`doLimitedCrafting` が `true` のときは作れない |
| D3 | zip の構造(F2) | zip の直下に `pack.mcmeta` を置く | 計画で定義 | — |
| D4 | L3(実サーバー)と L4(実クラフト)をどこまでやるか | L1・L2 は必須。L3・L4 は利用者が導入作業と規約への同意を行ったうえで実施する | 未定 | 実施しない場合は、その旨を完了報告に書く |
| D5 | 正式名 WorkbenchStrip をどう反映するか | フォルダ名を `WorkbenchStrip/`、zip を `dist/WorkbenchStrip.zip` にする。`pack.mcmeta` の `description` の1行目を `WorkbenchStrip` にする(zip ではパックIDが `file/WorkbenchStrip.zip` になり、拡張子なしの名前を出すため)。2行目は選択画面の幅に収めるため `作業台で樹皮・錆・ロウを除去` にする。選択画面のパック名が `WorkbenchStrip.zip` と拡張子付きで出ることは、2026-10-10 に利用者が 1.21.1 の画面で確認し、zip のまま受け入れると決定した。名前空間・レシピIDは `workbench_strip` のまま | 2026-10-10 に利用者の依頼で反映 | 名前空間を変える案は不可(wiki `Identifier`: 名前空間は小文字・数字・`_` `-` `.` だけ)。1.21.1 の `pack.mcmeta` に名前のフィールドはない(wiki `Pack.mcmeta`) |
| D6 | アイコン | `pack.png`(128x128、32x32 のドット絵を4倍に拡大)を `tools/icon.py` で生成する。左上が原木、右上が樹皮を剥いだ原木、左下が酸化した銅、右下が銅ブロック、中央が作業台 | 2026-10-10 に利用者の依頼で反映 | wiki `Data_pack`: ルートの `pack.png` がデータパック選択画面に表示される(1.16.2 から)。推奨サイズは wiki に記載がなく**未確認** |

---

## 3. タスク分解

### 3.1 リポジトリ構成(完成形)

```
workbench-strip-datapack/
├─ plans/workbench-strip-plan.md        # この文書
├─ tests/expected_conversions.tsv       # 期待値表(仕様書から直接書き起こす。生成ロジックとは独立)
├─ tools/
│  ├─ generate.py                       # レシピ・進捗・pack.mcmeta・pack.png を生成し、zip を作る
│  ├─ icon.py                           # アイコン(pack.png)のドット絵を描く
│  ├─ check_static.py                   # L1: オフラインの静的検証
│  └─ check_vanilla.py                  # L2: 1.21.1 のバニラデータとの照合(ネットワーク必要)
├─ WorkbenchStrip/                      # 生成物(データパック本体)
│  ├─ pack.mcmeta
│  ├─ pack.png
│  └─ data/workbench_strip/
│     ├─ advancement/recipes/{strip,scrape,unwax}/*.json
│     └─ recipe/{strip,scrape,unwax}/*.json
└─ dist/WorkbenchStrip.zip              # 配布物
```

### 3.2 タスク一覧

| ID | タスク | 依存 | 完了条件(第4章のゴール) |
|---|---|---|---|
| T0 | D1〜D4 を確定する(D1・D2 は確定済み。D4 は L3 に着手する前に決める) | — | 第2章の表で D4 が確定している |
| T1 | `tests/expected_conversions.tsv` を作る。仕様書3章・5章から84行を**手で列挙**する。列は `kind  from  to  n`(kind は strip / scrape / unwax、n は置く個数で、結果の個数も同じ) | T0 | G-E1〜G-E3 |
| T2 | `tools/generate.py` を作る。木材リスト、銅の9系統、段階の接頭辞、競合する22件の集合をデータとして定義し、3章のルールで生成する。出力先を毎回消してから書く。JSON はキーの順序とインデントを固定する | T0 | G-S1〜G-S10 |
| T3 | `generate.py` で、レシピごとの解放用の進捗(`advancement/recipes/<kind>/<from>.json`)を生成する | T2 | G-S8 |
| T4 | `generate.py` で `dist/WorkbenchStrip.zip` を作る。zip の直下に `pack.mcmeta` と `data/` を置き、`.DS_Store` などは入れない | T2 | G-Z1〜G-Z3 |
| T5 | `tools/check_static.py` を作り、L1 の全ゴールを判定する。標準ライブラリだけを使う | T1, T2 | `python3 tools/check_static.py` の終了コードが0 |
| T6 | `tools/check_vanilla.py` を作り、L2 の全ゴールを判定する。1.1 の固定タグ(SHA)から取得する | T2 | `python3 tools/check_vanilla.py` の終了コードが0 |
| T7 | (任意・L3)1.21.1 の専用サーバーで読み込みを検証する | T4 | G-R1〜G-R3 |
| T8 | (任意・L4)作業台で動作を確認する(仕様書10章 + 追加項目) | T7 | 第4.5節のチェックリストがすべて合格 |

`check_static.py` は期待値表(T1)を正解として生成物を検証します。生成ロジックと期待値を別々に書くことで、生成ルールの誤りが検証をすり抜けないようにします。

---

## 4. 機械的に検証可能なゴール

各ゴールには、判定方法と合格基準を書いています。L1・L2 はスクリプトの終了コードで合否が決まります。各チェックは `PASS <ID>` / `FAIL <ID>: <理由>` を1行ずつ出力し、1つでも FAIL があれば終了コードを1にします。

### 4.1 L0: 期待値表(`tests/expected_conversions.tsv`)

| ID | ゴール | 判定方法 | 合格基準 |
|---|---|---|---|
| G-E1 | 件数が仕様書どおり | `awk -F'\t' '{c[$1]++} END{for(k in c) print k, c[k]}'` | strip 21、scrape 27、unwax 36(合計84) |
| G-E2 | 2個置きの行が競合する22件と同じ | `awk -F'\t' '$4==2' \| wc -l` と、その行の `from` の集合 | 22行。`from` の集合が、8種の `*_log` / `*_wood`、`crimson`・`warped` の `*_stem` / `*_hyphae`、`bamboo_block`、`waxed_copper_block` と一致する |
| G-E3 | `from` に重複がない | `cut -f2 \| sort \| uniq -d` | 出力が空 |

### 4.2 L1: 静的検証(`tools/check_static.py`、オフライン)

| ID | ゴール | 合格基準 |
|---|---|---|
| G-S1 | `pack.mcmeta` が正しい | JSON として読める。`pack.pack_format == 48`。`pack.description` が空でない文字列で、1行目が `WorkbenchStrip` |
| G-S2 | ディレクトリ構成が正しい | `WorkbenchStrip/` 配下のファイルが、`pack.mcmeta`、`pack.png`、`data/workbench_strip/advancement/recipes/{strip,scrape,unwax}/*.json`、`data/workbench_strip/recipe/{strip,scrape,unwax}/*.json` だけ。`data/workbench_strip/` 直下に `recipes/`・`advancements/`(複数形)がない |
| G-S3 | レシピの件数 | strip 21、scrape 27、unwax 36(合計84) |
| G-S4 | レシピのスキーマ(1.21.1 の書式) | 全84件で、最上位のキーがちょうど `{type, category, ingredients, result}`。`type == "minecraft:crafting_shapeless"`、`category == "building"`。`ingredients` の各要素は**キーが `item` だけの dict**(文字列や `tag` は FAIL)。`result` のキーがちょうど `{id, count}` |
| G-S5 | 個数の整合 | 各レシピの `ingredients` がすべて同じ `item` で、`len(ingredients) == result.count` で、値は1か2 |
| G-S6 | 命名規則 | ファイル名(拡張子なし)が、材料のIDから `minecraft:` を除いたものと同じ。フォルダが期待値表の `kind` と一致する |
| G-S7 | 変換内容が期待値表と完全に一致 | 生成物から作った `(kind, from, to, n)` の集合と期待値表の集合の対称差が空 |
| G-S8 | 解放用の進捗 | 期待値表の84行それぞれに `advancement/recipes/<kind>/<from>.json` があり、内容が次と完全に一致する: `parent` が `minecraft:recipes/root`、条件 `has_<from>`(`inventory_changed`、`items: [{items: "minecraft:<from>"}]`)と `has_the_recipe`(`recipe_unlocked`、`recipe: workbench_strip:<kind>/<from>`)、`requirements` が両者の OR、`rewards.recipes` がそのレシピ1件だけ。ほかの進捗がなく、`minecraft:tick` をどこにも使っていない |
| G-S9 | 名前空間 | 材料と結果のIDがすべて `minecraft:` で始まる。`pack.png` 以外のファイルがすべて UTF-8 の JSON として読める |
| G-S10 | 生成が再現できる | `generate.py` を2回実行し、`WorkbenchStrip/` 配下の全ファイルと zip の SHA-256 が2回とも同じ |
| G-S11 | アイコン | `pack.png` が PNG で、128x128 |
| G-S12 | 正式名 | `WorkbenchStrip/` と `dist/WorkbenchStrip.zip` があり、旧名の `workbench_strip/`・`dist/workbench_strip.zip` が残っていない |

### 4.3 L1: zip の検証(`check_static.py` に含める)

| ID | ゴール | 合格基準 |
|---|---|---|
| G-Z1 | zip の直下に `pack.mcmeta` がある | `zipfile.ZipFile.namelist()` に `pack.mcmeta` があり、`<フォルダ>/pack.mcmeta` の形の項目はない |
| G-Z2 | 中身がフォルダ版と同じ | zip のファイル一覧と各ファイルの内容が、`WorkbenchStrip/` 配下と完全に一致する |
| G-Z3 | 余計なファイルがない | `.DS_Store`、`__MACOSX/` などが含まれない |

### 4.4 L2: バニラデータとの照合(`tools/check_vanilla.py`、ネットワーク必要)

1.1 の固定タグから `raw.githubusercontent.com` / `api.github.com` に問い合わせます。取得した内容はメモリ上でだけ使い、リポジトリには保存しません(保存してオフラインで再現できるようにするかは、実装時に利用者が判断します)。

| ID | ゴール | 合格基準 |
|---|---|---|
| G-V1 | 全IDが 1.21.1 に存在する | 生成物に出てくる全アイテムID(114種)が mcmeta-summary の `item` レジストリに含まれる |
| G-V2 | 実際の配置でバニラと競合しない | 各レシピの変換元を、そのレシピの個数 n だけ置いたとき、1.2 の判定方法で一致するバニラレシピが0件 |
| G-V3 | 判定ロジック自体の自己テスト | 全84件を「1個置き」と仮定して判定すると、一致するのがちょうど仕様書5章の22件(1.2 の C7 と同じ組み合わせ)になる。ずれた場合は、判定ロジックかデータ取得に問題があるとみなして FAIL |
| G-V5 | 解放用の進捗が 1.21.1 で有効 | 84件の進捗について、`parent` が mcmeta-data の進捗に、トリガーが mcmeta-summary の `trigger_type` に、条件のアイテムが `item` レジストリに存在する |
| G-V4 | (参考情報で、合否には使わない)別案Bの影響 | 全84件を「2個置き」と仮定した競合を出力する。現時点の結果は F1 の7件 |

### 4.5 L3: 実サーバーでの読み込み(任意)

**事前に利用者が行うこと(この計画では代行しない)**

- Java の導入(1.21.1 が要求するバージョンは導入時に公式情報で確認する。本調査では未確認)
- Mojang 公式からの 1.21.1 `server.jar` のダウンロード(外部からのダウンロード)
- `eula.txt` での Minecraft EULA への同意(利用規約への同意なので、利用者自身が行う)

**手順の概要**: 新しいテスト用ワールドの `world/datapacks/` に `dist/WorkbenchStrip.zip` を置く → `java -jar server.jar nogui` で起動する → 標準入力から `datapack list` と `stop` を送る → ログを保存する。

| ID | ゴール | 合格基準 |
|---|---|---|
| G-R1 | 読み込みエラーがない | `logs/latest.log` に `workbench_strip` または `WorkbenchStrip` を含む `ERROR` / `WARN` 行がない。`Parsing error` と `Couldn't load` に該当する行もない |
| G-R2 | パックが有効になっている | `datapack list` の出力に `WorkbenchStrip` を含む行がある(出力形式は未確認なので、文字列が含まれるかだけで判定する) |
| G-R3 | サーバーが正常に終了する | `stop` のあとプロセスの終了コードが0 |

### 4.6 L4: 作業台での動作確認(任意。基本は手動で、一部は自動化できる)

仕様書10章の #1〜#21 を、合否のチェックリストとして使います。ただし D2 の変更により、#20 の期待結果は「変換元を手に入れると、そのレシピが解放されて作れる」、#21 は「手に入れた変換元のレシピだけが表示される」と読み替えます。追加する項目は次のとおりです。

| # | 区分 | 入力 | 期待結果 | 追加する理由 |
|---|---|---|---|---|
| 22 | 範囲外の個数 | `oak_log` × 3 | 本パックのレシピは一致しない(結果欄が空) | 2個→2個のレシピが3個では一致しないことの確認 |
| 23 | 競合なし(1個→1個) | `waxed_oxidized_cut_copper_slab` × 1 | `oxidized_cut_copper_slab` × 1 | F1 のハーフ系統を1個置きにしたときの確認 |
| 24 | バニラ維持 | `cut_copper_slab` × 2 を縦に置く | `chiseled_copper` × 1 | 本パックがバニラの shaped レシピを妨げないことの確認 |
| 25 | 機械判定の代替(F3) | 変換元84種をすべて手に入れたあと `/data get entity @s recipeBook.recipes` | `workbench_strip:` で始まる要素が84件 | #21 の代替。プレイヤーデータでこれが読めるかは未確認なので、実施して確認する |
| 26 | 名前とアイコン | ワールド作成画面でデータパック選択を開く | `WorkbenchStrip` という名前と、`pack.png` のアイコンが表示される | D5・D6 の反映確認。2026-10-10 の利用者の確認では、パック名は `WorkbenchStrip.zip`(ファイル名)、説明文1行目は `WorkbenchStrip`、アイコンも表示された。説明文2行目が切れたため短くした。短くした文面での表示は未確認 |
| 27 | 起動直後に解放されない | 新しいワールドに入り、変換元を何も持たない状態でレシピブックを開く | 本パックのレシピが表示されない | D2 の変更の確認 |
| 28 | 変換元で解放される | `oak_log` を1個手に入れる | `workbench_strip:strip/oak_log` だけが解放され、レシピブックに表示される。`oak_wood` など他のレシピは解放されない | D2 の変更の確認 |

自動化の案(任意): node の `mineflayer` を使って、オフラインモードのローカルサーバーにボットを接続します。`/give` で素材を渡し、作業台のスロットに直接配置して、結果スロットを読み取ります。mineflayer が 1.21.1 に対応しているかは未確認です。導入には npm からのダウンロードが必要なので、実施するかは利用者が判断します。

---

## 5. 完了の定義

1. T1〜T6 が完了し、次の2つがどちらも終了コード0で終わる。

   ```bash
   python3 tools/check_static.py
   ```

   ```bash
   python3 tools/check_vanilla.py
   ```

2. L3・L4 を実施した場合は、G-R1〜G-R3 と 4.6 のチェックリストがすべて合格している。実施しなかった場合は、そのことと理由を完了報告に書く。
3. 第2章の D4 の結論を完了報告に書く(D1・D2 は確定済み)。

## 6. 導入時の注意(仕様書9章の再確認)

- **対象**: ワールドの `datapacks/` フォルダ。**影響**: レシピ84件と、レシピ解放用の進捗84件(進捗画面には表示されない)が追加される。既存のブロックやアイテムは変更しない。
- 共有サーバーでは全プレイヤーのレシピに影響するので、導入前に管理者や参加者へ確認する。導入と `/reload` は利用者自身が行う。
- 導入前にワールドのバックアップを取ることを推奨する。
