# 設計: 複数の Minecraft バージョンを開発できる体制

- 作成日: 2026-10-10
- 対象リポジトリ: `atsuki-seo/workbench-strip-datapack`(public)
- 現状: v1.0.0(Minecraft Java Edition 1.21.1 / `pack_format` 48)を公開済み。対応するのは当面 1.21.1 だけ

この文書は、ブランチ・GitHub のルール・GitHub Actions の設計です。第9章の判断事項は、2026-10-10 にすべて推奨案で確定しました。ここに書いた設定はまだ適用していません。適用の順番と手順は第8章にあります。

---

## 1. 前提として確認した事実

### 1.1 Minecraft 側

| # | 事実 | 根拠 |
|---|---|---|
| M1 | 1.21 以降、データパックの `pack_format` はほぼ毎回変わっている: 48(1.21–1.21.1)、57(1.21.2–1.21.3)、61(1.21.4)、71(1.21.5)、80(1.21.6)、81(1.21.7–1.21.8)、88.0(1.21.9–1.21.10)、94.1(1.21.11)、101.1(26.1–26.1.2)、107.1(26.2)、121.0(26.3) | wiki `Template:Data_pack_format` |
| M2 | 1.21.9(88.0)からは番号にマイナー版が付き、`pack.mcmeta` は `min_format` / `max_format` で書く。古い版も対象にするときは、廃止予定の `pack_format` / `supported_formats` も併記する必要がある(データパックの版が 82 未満の場合) | wiki `Pack_format`、`Pack.mcmeta` |
| M3 | レシピの `ingredients` は、1.21.1 では `{"item": ...}` 形式、1.21.2 以降は文字列形式 | 計画書 C2(mcmeta の `oak_planks.json`) |
| M4 | 使えるアイテムは版によって違う(例: ペールオークは 1.21.4 で追加) | 計画書 C6 |
| M5 | `pack.mcmeta` の `overlays` を使うと、1つのパックの中に版ごとの差分を持たせられる | wiki `Pack.mcmeta` |

M1〜M4 から、**版ごとの違いの多くは「データの違い」**だと分かります(使える木材・銅の系統、`pack_format`、JSON の書き方)。版ごとに生成ロジックがまったく別になるわけではありません。ただし、1.21.9 以降で銅の系統が増えたかどうかは**未確認**です。

### 1.2 GitHub 側

| # | 事実 | 根拠 |
|---|---|---|
| G1 | ルールセットは、ブランチとタグの両方を対象にできる。ルールには、削除の制限、更新の制限、強制 push の禁止、直線履歴の強制、PR の必須化(必要な承認数は 0〜10)、ステータスチェックの必須化がある | GitHub Docs「Available rules for rulesets」 |
| G2 | このリポジトリでルールセットの API(`GET /repos/{owner}/{repo}/rulesets`)は `[]` を返した。現在ルールセットはない | 2026-10-10 に実行して確認 |
| G3 | 無料プランの public リポジトリでルールセットを作れるかは、ドキュメントの要約からは確認できなかった。G2 の応答から、使える見込みとみている | 推論(G2 からの推測) |
| G4 | immutable releases を有効にすると、公開後の Release ではタグと添付ファイルが固定される。Release を削除したあとも、**同じタグ名は再利用できない**。設定は有効にした以降の Release だけに効く。下書きで作り、添付をすべて付けてから公開する流れが推奨されている | GitHub Docs「Immutable releases」、GitHub Changelog(2025-10-28 GA) |
| G5 | このリポジトリでは immutable releases は無効(`enabled: false`) | 2026-10-10 に API で確認 |
| G6 | REST API の利用上限は、認証なしで 60 回/時、Actions の `GITHUB_TOKEN` で 1,000 回/時/リポジトリ | GitHub Docs「Rate limits for the REST API」 |
| G7 | 現在のマージ設定は、merge commit・squash・rebase のすべてを許可し、マージ後のブランチ自動削除は無効 | 2026-10-10 に API で確認 |

---

## 2. 方針(結論)

**Minecraft のバージョンごとにブランチを分けない。** 長く使うブランチは `main` 1本にします。対応する Minecraft のバージョンは「ターゲット」として設定ファイルに並べ、生成スクリプトがターゲットごとに zip を作ります。

| 案 | 内容 | 長所 | 短所 | 判断 |
|---|---|---|---|---|
| A. 版ごとにブランチ | `mc/1.21.1`、`mc/1.21.4` などを長く使うブランチにする | ブランチを見ればその版の状態が分かる | 修正のたびに全ブランチへの cherry-pick が要り、ブランチ間で生成ロジックや期待値表がずれていく。CI の設定もブランチごとに要る | 不採用 |
| **B. main + ターゲット設定** | `main` に全ターゲットの設定を置き、ターゲットごとに生成・検証・zip 化する | 修正は1回で全版に反映される。CI のマトリクスで全版を毎回検証できる | 生成スクリプトに版ごとの分岐が入る | **採用** |
| C. overlays で1つの zip | `pack.mcmeta` の `overlays` で、1つの zip を全版に対応させる | 配布物が1つで済む | 版ごとの読み込みの違いを1つのパックで扱うので、検証が重い。M2 のように `pack.mcmeta` の書式自体が変わる | 将来の選択肢(第9章 J4) |

案 B でも、短命の作業ブランチと、必要になったときだけ作る保守ブランチ(第4章)は使います。

---

## 3. ターゲットの設計

### 3.1 ターゲット設定ファイル

ターゲット1つにつき、`targets/<ターゲットID>.json` を1つ置きます。現時点では `mc1.21.1` だけです。

```json
{
  "id": "mc1.21.1",
  "minecraft": { "min": "1.21", "max": "1.21.1", "verified": "1.21.1" },
  "pack_format": 48,
  "recipe_ingredient_style": "item_object",
  "mcmeta": {
    "data": "aacd2a457333b258d044a642f38270c8cddbc628",
    "summary": "7cffbcdad5fa36f22acef6bd4b869ecad4ca3fd9"
  },
  "woods": {
    "overworld": ["oak", "spruce", "birch", "jungle", "acacia", "dark_oak", "mangrove", "cherry"],
    "nether": ["crimson", "warped"],
    "bamboo": true
  },
  "copper_families": ["copper_block", "cut_copper", "cut_copper_stairs", "cut_copper_slab",
                      "chiseled_copper", "copper_grate", "copper_bulb", "copper_door", "copper_trapdoor"]
}
```

- `minecraft.verified` には、L2(バニラデータとの照合)で実際に照合した版を書きます。`pack_format` 48 は 1.21 にも対応しますが、照合しているのは 1.21.1 のデータだけです(第9章 J6)。
- `recipe_ingredient_style` のように、書式の違いは**名前の付いた設定値**で切り替えます。生成スクリプトに版番号の比較(`if version >= ...`)を直接書きません。
- 名前空間 `workbench_strip` とレシピID(`workbench_strip:<kind>/<from>`)は、全ターゲットで共通にします。プレイヤーデータに記録されるので、版によって変えません。

### 3.2 ディレクトリ構成(移行後)

```
targets/mc1.21.1.json
tests/mc1.21.1/expected_conversions.tsv   # ターゲットごとに手で書き起こす(生成ロジックとは独立)
tools/generate.py      --target <id> | --all
tools/check_static.py  --target <id> | --all
tools/check_vanilla.py --target <id> | --all
build/<id>/WorkbenchStrip/                # 生成物(.gitignore)
dist/<配布名>.zip                          # 配布物(.gitignore。名前は第9章 J1)
CHANGELOG.md
```

### 3.3 共通の不変条件

ターゲットが増えても、次は全ターゲットで検証します。今のゴール ID は、ターゲットごとに実行する形でそのまま使います。

- 期待値表との完全一致(G-S7)、解放用の進捗の形(G-S8)、zip の構造(G-Z1〜G-Z3)
- バニラとの競合がないこと(G-V2)と、判定ロジックの自己テスト(G-V3。期待する競合の組はターゲット設定または期待値表の側に持たせる)
- 同じ入力から同じ出力が作られること(G-S10)

---

## 4. ブランチ戦略

| ブランチ | 寿命 | 用途 | マージ先 |
|---|---|---|---|
| `main` | 永続 | 唯一の長期ブランチ。常にリリースできる状態に保ち、全ターゲットの CI が通っている | — |
| `feat/<topic>` | 短命 | 機能の追加 | `main`(squash) |
| `fix/<topic>` | 短命 | 不具合の修正 | `main`(squash) |
| `target/<mcバージョン>` | 短命 | 新しい Minecraft バージョンへの対応(第7章) | `main`(squash) |
| `ci/<topic>`・`docs/<topic>` | 短命 | CI・文書の変更 | `main`(squash) |
| `maint/v<major>` | 必要になったときだけ | メジャー版を上げたあと、古いメジャー版に修正を出すとき。最後の `v<major>.x.y` タグから作る。今は作らない | 修正は `main` に入れてから cherry-pick |

- マージは squash だけにします。1つの PR が `main` 上で1コミットになり、リリースとの対応が追いやすくなります。
- Minecraft の版を理由にした長期ブランチは作りません(第2章)。

---

## 5. バージョン・タグ・リリース

### 5.1 パックのバージョン(SemVer)

| 区分 | 上げる条件 | 例 |
|---|---|---|
| MAJOR | 利用者のワールドに影響する互換性のない変更 | ターゲットの削除、レシピIDの変更・削除、個数ルールの変更(例: 1個→1個を2個→2個に) |
| MINOR | 互換性のある追加 | ターゲットの追加、レシピの追加 |
| PATCH | 挙動を変えない修正 | 誤った変換先の修正、説明文・アイコン・文書の修正 |

Minecraft のバージョンは、パックのバージョン番号には入れません。ターゲットとして、配布物の名前(J1)とリリースノートで表します。

### 5.2 タグとリリースの流れ

1. `main` の `CHANGELOG.md` に `## [X.Y.Z]` の節を書いて PR でマージする
2. `main` の先頭に注釈付きタグ `vX.Y.Z` を付けて push する
3. `release.yml`(第6.2節)が全ターゲットを生成・検証する。下書きの Release を作って zip と `SHA256SUMS.txt` を添付し、そのあと公開する
4. immutable releases を有効にしていれば、この時点でタグと添付ファイルが固定される(G4)

**注意**: immutable releases を有効にすると、今回の v1.0.0 のように、同じタグ名で作り直すことはできなくなります(G4)。誤りに気付いたら PATCH を上げて出し直します。

---

## 6. GitHub Actions

すべてのワークフローに共通する方針:

- 既定の権限は `permissions: contents: read` にし、書き込みが要るジョブだけで権限を足す
- 外部の action はコミット SHA で固定する(SHA の値は実装時に取得する)。更新は Dependabot(`github-actions`)で受け取る
- PR のトリガーには `pull_request` を使い、`pull_request_target` は使わない。シークレットも使わない(`GITHUB_TOKEN` だけ)

### 6.1 `ci.yml`(PR と `main` への push)

| ジョブ | 内容 |
|---|---|
| `targets` | `targets/*.json` を読み、ターゲットIDの一覧をマトリクス用に出力する |
| `check (<target>)` | マトリクスでターゲットごとに `generate.py` → `check_static.py` → `check_vanilla.py` を実行する。`GITHUB_TOKEN` を環境変数で渡し、`check_vanilla.py` の GitHub API 呼び出しを認証付きにする(G6。認証なしの 60 回/時は、共有ランナーでは他の利用者と分け合うことになる可能性がある。推論)。mcmeta の取得結果は `actions/cache` に、キーをコミット SHA にしてキャッシュする(SHA を固定しているので内容は変わらない) |
| `commit-email`(PR のみ) | PR に含まれるコミットの author / committer のメールアドレスが、すべて `@users.noreply.github.com` で終わることを確かめる。会社のアドレスが公開リポジトリに入るのを防ぐ |
| `ci-ok` | 上のジョブがすべて成功したら成功する集約ジョブ。ルールセットで必須にするのはこのジョブだけにする。こうすると、ターゲットが増えてマトリクスのジョブ名が変わっても、ルールセットを直さずに済む |

### 6.2 `release.yml`(`v*` タグの push と、手動実行)

1. タグのコミットが `main` に含まれていることを確かめる(`git merge-base --is-ancestor`)
2. タグのバージョンに対応する `CHANGELOG.md` の節があることを確かめ、その本文をリリースノートにする
3. 全ターゲットについて生成・L1・L2 を実行する
4. 下書きの Release を作り、全ターゲットの zip と `SHA256SUMS.txt` を添付してから公開する(このジョブだけ `contents: write`)

手動実行(`workflow_dispatch`)では `dry_run` を既定にし、生成物を Actions の artifact として残すだけで Release は作りません。リリースの手順を、本物の Release を作らずに試すためです。

### 6.3 `mc-watch.yml`(任意。週1回の定期実行)

新しい Minecraft のリリースが出ていて、どのターゲットの `minecraft.max` にも含まれていなければ、Issue を作ります(`issues: write`)。新しい版を知る情報源(misode/mcmeta のタグ、または Mojang の版一覧)は実装時に決めて確かめます(未確認)。

### 6.4 CI ではやらないこと

L3(実サーバーでの読み込み)は CI に入れません。`server.jar` のダウンロードと EULA への同意が必要で、これは利用者が判断することだからです(計画書 D4)。版を追加するときの手動チェックリストで扱います(第7章)。

---

## 7. 新しい Minecraft バージョンを追加する手順

1. `target/<mcバージョン>` ブランチを作る
2. その版の mcmeta タグ(`<版>-data` / `<版>-summary`)のコミット SHA と、`pack_format`(wiki)を確かめる
3. `targets/mc<版>.json` を書く。書式の違い(M2・M3)は、名前の付いた設定値で表す
4. `tests/mc<版>/expected_conversions.tsv` を、その版のアイテムに合わせて**手で**書き起こす(生成ロジックから作らない)
5. 生成スクリプトと検証スクリプトに、必要な書式の切り替えを足す。既存ターゲットの生成結果が変わっていないこと(G-S10 と期待値表)を確かめる
6. その版で、L3・L4 のチェックリストを手動で実施する
7. PR を出す(CI の全ターゲットが合格したらマージ)→ `CHANGELOG.md` に追記 → MINOR を上げてリリース

---

## 8. 移行計画(今やること。ターゲットは 1.21.1 だけ)

| 段階 | 内容 | 外部への影響 | 合格基準 |
|---|---|---|---|
| P1 | 第3章の構成に作り替える(`targets/mc1.21.1.json`、`--target` 引数、`build/` 配下への出力) | なし(ローカル) | M-1、M-2 |
| P2 | `ci.yml`・`release.yml`・`dependabot.yml`・`CHANGELOG.md` を追加する | PR を作る(public) | M-3、M-4 |
| P3 | リポジトリ設定を変える: squash だけ許可、マージ後にブランチを自動削除 | リポジトリ設定の変更 | M-5 |
| P4 | ルールセットを作る(第8.1節) | 以後 `main` への直接 push ができなくなる | M-6 |
| P5 | immutable releases を有効にする | 以後の Release は作り直せなくなる(G4) | M-7 |

P2〜P5 は、それぞれ実行前に利用者の確認を取ります。P1・P2 だけなら、パックの中身は変わらないのでリリースは不要です。

### 8.1 ルールセットの内容

| ルールセット | 対象 | ルール |
|---|---|---|
| `main` | 既定のブランチ | 削除の制限、強制 push の禁止、直線履歴の強制、PR の必須化(必要な承認数は 0。管理者が1人なので、自分の PR を自分で承認できないため)、ステータスチェック `ci-ok` の必須化(strict) |
| `release-tags` | タグ `v*` | 削除の制限、更新の制限、強制 push の禁止 |

バイパスは誰にも許可しません。緊急時は、管理者がルールセットを一時的に無効にして対応します。

### 8.2 機械的に確かめられる合格基準

| ID | 合格基準 |
|---|---|
| M-1 | `python3 tools/generate.py --target mc1.21.1` で作った zip の中身(ファイルの一覧と各ファイルのバイト列)が、v1.0.0 の Release の `WorkbenchStrip.zip`(SHA-256 `8bda8fc7…05b1`)と一致する。配布名(J1)を変えない場合は、zip 自体の SHA-256 も一致する |
| M-2 | `check_static.py --all` と `check_vanilla.py --all` が、どちらも終了コード0 |
| M-3 | P2 の PR で `ci.yml` の全ジョブが成功し、`ci-ok` が成功する |
| M-4 | `release.yml` を `dry_run` で手動実行すると、artifact の zip が M-1 と同じ中身になり、Release は作られない |
| M-5 | `GET /repos/{owner}/{repo}` で `allow_squash_merge=true`、`allow_merge_commit=false`、`allow_rebase_merge=false`、`delete_branch_on_merge=true` |
| M-6 | `GET /repos/{owner}/{repo}/rulesets` に、第8.1節の2つのルールセットが `enforcement: active` で並ぶ。各ルールの内容が表と一致する |
| M-7 | `GET /repos/{owner}/{repo}/immutable-releases` が `enabled: true` |

---

## 9. 要判断事項

2026-10-10 に、利用者が J1〜J6 をすべて推奨案で確定した。

| # | 判断事項 | 結論(推奨案で確定) | 推奨案の短所 |
|---|---|---|---|
| J1 | 配布物(zip)の名前 | ターゲットが1つの間は `WorkbenchStrip.zip` のまま。2つ目のターゲットを足すときに、`WorkbenchStrip-mc<版>.zip` に変える | 名前を変えるとき、ゲーム内のパック名(ファイル名)も変わる。添付ファイルの URL も途中で変わる |
| J2 | immutable releases を有効にするか | 有効にする | 誤ったリリースを同じタグで直せなくなり、PATCH を上げることになる |
| J3 | 1人で管理する間も、`main` への直接 push を禁止するか | 禁止する(PR 必須、承認数 0) | 小さな修正でも PR が要る |
| J4 | 将来、overlays で zip を1つにまとめるか | 今はしない。ターゲットが3つ以上になり、配布物の数が負担になったら検討する | 利用者は、自分の版に合う zip を選ぶ必要がある |
| J5 | 次にどの版を対応するか | 今は決めない(利用者の指示どおり 1.21.1 だけ) | — |
| J6 | 1.21(1.21.1 ではない版)を別に照合するか | `minecraft.min` を 1.21 にしたまま、照合は 1.21.1 だけにする。リリースノートにその旨を書く | 1.21 での動作は、`pack_format` が同じことからの推論になる |
