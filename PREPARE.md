# PREPARE

MicroPython バンドル準備ツール。ソースとサブモジュールからファイルを収集し、`.py` を `mpy-cross` で `.mpy` にコンパイルして出力ディレクトリにまとめます。あわせて `src/version.json` および 出力用 `mpy_*/version.json` を生成します。

## 主な機能
- 収集元: `src/` と `prepare.json` の `submodules` に列挙された各サブモジュールの `src/`
- コピー/コンパイル: `copy_only` のファイルはコピー、それ以外は `mpy-cross` でコンパイル
- バージョン情報: 各 `.py` から `__version__` を抽出し `version.json` に記録（`const("x.x.x")` 形式も対応）
- ハッシュ管理: `.py` / `.mpy` の SHA-256 を算出し `version.json` に保存
- アーキ検出: `prepare.json` の `command` から `-march` を検出し、出力先を自動命名（例: `-march=xtensa` → `mpy_xtensa`）
- ドライラン: 実行内容・統計を表示のみ

## 使い方
- ドライラン: `python3 prepare.py -n`
- 実行: `python3 prepare.py`
- 状態確認: `python3 prepare.py status`
- 出力削除: `python3 prepare.py clean`

## オプション
- `command`: サブコマンド。`clean`（出力削除）/`status`（状態表示）
- `--dry-run, -n`: 変更せず計画のみ表示
- `--config, -c <path>`: 設定ファイルパス。未指定時は `prepare.json` または `src/prepare.json` を自動探索
- `--src-dir <dir>`: ソースディレクトリ（既定: `src`）
- `--output-dir, -o <dir>`: 出力ディレクトリ（既定: `mpy_xtensa`。`-march` に応じ自動補正）
- `--preserve-dirs`: 出力でサブディレクトリ構造を保持（既定はフラット配置）

## 実行フロー（概要）
- `src/` と `submodules/*/src/` から `copy_only` + `modules` のファイルを探索
- 事前に `src/version.json` を生成（`__version__` と SHA-256 を収集）
- 出力ディレクトリを作成（既存ならクリア）
- `copy_only` をコピー、`modules` を `mpy-cross` でコンパイルして配置
- 出力用 `version.json` を作成（出力中の全ファイルをスキャンして SHA-256 を再計算）
- サマリー表示（件数、失敗、出力ディレクトリの内容）

## 必要ツール
- Python 3.11+
- `mpy-cross`（インストール例: `pip install mpy-cross`）

---

# prepare.json 設定仕様

`prepare.py` の動作を制御する設定ファイル。既定ではリポジトリ直下の `prepare.json` を読み込み、見つからない場合は `src/prepare.json` を探索します。

例（tools/prepare.json より抜粋）:
```
{
  "command": "mpy-cross -march=xtensa -O2 ",
  "copy_only": [
    "boot.py",
    "main.py",
    "config.json"
  ],
  "modules": [
    "app.py",
    "wifi.py"
  ],
  "submodules": [
    "ESP32s3base"
  ]
}
```

各キーの説明:
- `command`: `mpy-cross` 実行コマンドの完全文字列。
  - `-march=<arch>` を含めるとアーキを検出し出力先を自動補正（例: `xtensa`, `armv7m` など）。
  - 任意の最適化指定（例: `-O2`）も付与可能。
- `copy_only`: そのままデバイスへコピーするファイルリスト。`.py` に限定せず `json` 等も可。
  - 例: `boot.py`, `main.py`, 各種設定/データファイル。
- `modules`: `mpy-cross` でコンパイルする `.py` のリスト。
  - 出力は既定でフラットに `<stem>.mpy`。`--preserve-dirs` で相対ディレクトリ構造を保持し `<path>.mpy` として出力。
- `submodules`: 追加の検索元。各項目の直下にある `src/` を探索します。
  - 検索順は「`src/` → サブモジュール群」。見つからない場合は警告してスキップします。

検索とバージョン取得:
- ファイルは `src/<name>` → `<submodule>/src/<name>` の順で探索。
- `__version__ = "x.x.x"` または `__version__ = const("x.x.x")` を抽出。見つからない場合は `unknown` として記録。

出力ファイル:
- `src/version.json`: 収集時点の `.py` のバージョンと SHA-256。
- `mpy_*/version.json`: 出力ディレクトリ内の実在ファイルを再スキャンし、`.mpy` などのハッシュと対応づけて保存。

ヒント:
- `--dry-run` で、コピー/コンパイルの対象と件数、推定サイズ削減などを確認できます。
- `--preserve-dirs` でパッケージ構成（サブディレクトリ）をそのまま維持して出力可能です。
