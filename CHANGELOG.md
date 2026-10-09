# Changelog

このプロジェクトのバージョンは [Semantic Versioning](https://semver.org/lang/ja/) に従います。
Minecraft のバージョンはパックのバージョン番号には入れず、配布物の名前とリリースノートで表します。
`release.yml` は、タグ `vX.Y.Z` に対応する `## [X.Y.Z]` の節をリリースノートに使います。

## [Unreleased]

### 変更

- 複数の Minecraft バージョンを開発できるように、生成・検証をターゲット単位(`targets/<ターゲットID>.json`)に分けた。生成物の中身は変わらない
