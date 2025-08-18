# Fix Log: MicroPython ツールの中立化とリファクタリング

## 概要
本リポジトリを別プロジェクト由来のハードコードから中立化し、設定/CLIドリブンに再設計。COMMON_TOOLS.md の提案に基づき、バンドル準備・デプロイ・バージョン管理の各ツールを改善しました。

## 変更点
- prepare.py
  - オプション追加: `--config/-c`, `--src-dir`, `--output-dir/-o`, `--preserve-dirs`。
  - 設定自動探索: 明示パスがなければ `prepare.json` → `src/prepare.json` を探索。
  - 出力/文言の中立化、日時は `datetime.now().isoformat()` を使用。
  - `version.json` 生成を汎用化。出力側は再帰集計（`rglob`）。
- deploy.py
  - 一般化: バナーと説明をMicroPython向けに中立化。既定WebREPLホストを `micropython.local` に。
  - 再帰コピー対応: ローカルは `rglob` 集計、リモートは `mpremote fs mkdir` を挟んでサブディレクトリ作成後に `cp`。
  - デバイス検出を拡張: `/dev/tty*`, `COM*`, “Espressif” を許容。メッセージも一般化。
  - CLI拡張: `--webrepl-host`, `--webrepl-port`, `--webrepl-password` を追加（環境変数/`.env`と併用）。
- update_version.py
  - CLI化: `--src`, `--version-file`, `--bump {patch,minor,major}` を追加。
  - バージョン増分方針を選択式に（従来のminor固定を解消）。
- COMMON_TOOLS.md
  - 上記の更新点を追記し、現状と整合化。

## 使い方（抜粋）
- バンドル:
  - ドライラン: `python3 prepare.py -n -c prepare.json --src-dir src --output-dir mpy_xtensa`
  - 実行: `python3 prepare.py -c prepare.json --preserve-dirs`
- デプロイ:
  - USB: `python3 deploy.py --source mpy_xtensa --dry-run` → 問題なければ `--dry-run` を外す
  - WebREPL: `python3 deploy.py -w --source mpy_xtensa --webrepl-host micropython.local --webrepl-password <pw>`
- バージョン管理:
  - `python3 update_version.py --src src --bump patch`

## 補足/注意
- WebREPLではサブディレクトリの事前作成が必要になる場合があります（USB接続時の `mpremote fs mkdir` は実施済み）。必要であればWebREPL側のmkdir対応も拡張可能です。
- `prepare.json` の `modules`/`copy_only` にサブパスを含める場合、`--preserve-dirs` で出力側の階層を維持できます。
- 残存する固有名や固定値があれば指摘ください。追加の置換・切り出し（サブモジュール化/パッケージ化）にも対応可能です。
