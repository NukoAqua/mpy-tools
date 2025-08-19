# mpy-tools

MicroPython 用の開発ユーティリティ集です。モジュールのバージョン管理、ビルド（`.mpy` 生成）、および ESP32 系デバイスへのデプロイを、シンプルな CLI で実行できます。

## 主なスクリプト
- `prepare.py`: ソースとサブモジュールからファイルを収集し、`.py` を `mpy-cross` で `.mpy` にコンパイルして `mpy_<arch>/` に出力。`version.json` も生成します。
- `deploy.py`: `mpy_<arch>/` などの出力ディレクトリを USB（mpremote）または WebREPL でデバイスへ差分デプロイします。
- `update_version.py`: `src/` を走査し、ファイルの変更検知に応じて各モジュールの `__version__` を自動バンプし、`src/version.json` を更新します。

詳細は以下の各ドキュメントをご覧ください。
- PREPARE: [PREPARE.md](./PREPARE.md)
- DEPLOY: [DEPLOY.md](./DEPLOY.md)
- UPDATE_VERSION: [UPDATE_VERSION.md](./UPDATE_VERSION.md)

## セットアップ
1. 仮想環境（任意）
   - `python -m venv .venv && source .venv/bin/activate`
2. ツールのインストール
   - `pip install mpy-cross mpremote python-dotenv`
   - または `uv pip install mpy-cross mpremote python-dotenv`

## クイックスタート
補足: このリポジトリではスクリプト実体が `tools/` 配下にあります。PATH を通さない場合は `python3 tools/...` で実行してください。PATH を通す場合は、作業シェルで一度だけ以下を実行すると `prepare.py` などをそのまま呼べます。

- PATH を追加: `source path/to/mpy-tools-path.sh`
  - 例（サブモジュールとして `mpy-tools/` に配置）: `source mpy-tools/mpy-tools-path.sh`
  - 例（このリポジトリ直下）: `source ./mpy-tools-path.sh`
1. バージョン更新・`version.json` 生成/更新
   - `python3 tools/update_version.py`（PATH 済みなら `update_version.py`）
2. バンドル（コピー/コンパイル）と出力生成
   - 事前確認: `python3 tools/prepare.py -n`（PATH 済みなら `prepare.py -n`）
   - 実行: `python3 tools/prepare.py`（PATH 済みなら `prepare.py`）
3. デプロイ（USB/mpremote）
   - 事前確認: `python3 tools/deploy.py --source mpy_xtensa --dry-run`（PATH 済みなら `deploy.py ...`）
   - 実行: `python3 tools/deploy.py --source mpy_xtensa`
4. デプロイ（WebREPL）
   - `.env` に `WEBREPL_HOST`, `WEBREPL_PORT`, `WEBREPL_PASSWORD` を設定
   - 事前確認: `python3 tools/deploy.py -w --source mpy_xtensa --dry-run`
   - 実行: `python3 tools/deploy.py -w --source mpy_xtensa`

## ツール概要

### prepare.py（ビルド/バンドル）
- 目的: `src/` と `prepare.json` の `submodules` からファイルを集約し、`copy_only` はコピー、`modules` は `mpy-cross` で `.mpy` にコンパイルして出力します。
- 特徴:
  - `prepare.json` の `command` から `-march=<arch>` を検出し、出力先（例: `mpy_xtensa`）を自動調整
  - `src/version.json` を作成し、モジュールの `__version__` と SHA-256 を記録
  - 出力ディレクトリ側にも `version.json` を出力（実在ファイルのハッシュで再構成）
- 主なコマンド:
  - `python3 tools/prepare.py -n`（ドライラン）
  - `python3 tools/prepare.py`（実行）
  - `python3 tools/prepare.py status` / `python3 tools/prepare.py clean`
- 設定ファイル: `prepare.json`
  - キー: `command`, `copy_only`, `modules`, `submodules`
  - 仕様と例: [PREPARE.md](./PREPARE.md)

### deploy.py（デバイスへデプロイ）
- 目的: 出力ディレクトリ（例: `mpy_xtensa/`）を、USB（`mpremote`）または WebREPL でデバイスへ反映します。
- 特徴:
  - SHA-256 による差分計算（新規/更新/削除）
  - `webrepl_cfg.py` は削除保護
  - サブディレクトリを含む再帰コピーに対応
  - WebREPL は `.env`/環境変数で接続設定を読込
- 主なコマンド:
  - `python3 tools/deploy.py --source mpy_xtensa`（自動検出）
  - `python3 tools/deploy.py --source mpy_xtensa --device /dev/ttyACM0`
  - `python3 tools/deploy.py --source mpy_xtensa --dry-run`
  - `python3 tools/deploy.py -w --source mpy_xtensa [--dry-run]`
- 詳細: [DEPLOY.md](./DEPLOY.md)

### update_version.py（バージョン管理）
- 目的: `src/` を走査し、`version.json` を更新。変更検知時は `__version__` を `patch`/`minor`/`major` 方針で自動バンプして書き戻します。
- 特徴:
  - `__version__ = "x.x.x"` と `__version__ = const("x.x.x")` に対応
  - `version.json` にのみ存在し `src/` に無いファイルは「欠落」としてレポート
- 主なコマンド:
  - `python3 tools/update_version.py [--bump patch|minor|major]`
  - `python3 tools/update_version.py --src src --version-file src/version.json`
- 詳細: [UPDATE_VERSION.md](./UPDATE_VERSION.md)

## リポジトリ構成（抜粋）
- `src/`: アプリケーションのソース（このリポジトリまたはサブモジュールに配置）
- `mpy_<arch>/`: `prepare.py` が生成する出力（`.mpy` と `version.json`）
- `prepare.json`: `prepare.py` の設定（リポジトリ直下、無ければ `src/prepare.json` を探索）
- `tools/`: スクリプト・補助ツール（本リポジトリではスクリプト実体が `tools/` 配下）

## 開発・検証のヒント
- ドライランを活用: `prepare.py -n`, `deploy.py --dry-run`
- ハッシュ/バージョン確認: 生成された `version.json` を確認
- WebREPL を使う場合は `.env` に接続情報を記述（機密はコミットしない）

## Contributing / 言語ポリシー
- コントリビューションガイド: [CONTRIBUTING.md](./CONTRIBUTING.md)
- リポジトリ内コミュニケーションは日本語推奨です。

## License

This project is licensed under the MIT License - see the [LICENSE](./LICENSE) file for details.

## License (JP)

このプロジェクトは [MIT License](./LICENSE) のもとで公開されています。  
自由に利用できますが、著作権表示は残してくださいね。

日本語訳は [LICENSE.ja.md](./LICENSE.ja.md) をご覧ください（参考用）。
