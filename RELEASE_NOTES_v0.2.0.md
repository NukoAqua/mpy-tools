# v0.2.0

主な変更
- mpy-tools-path.sh を追加（スクリプト配置場所に依存しない PATH 追加ヘルパー）
- README のクイックスタートに PATH 設定手順と `tools/` 実行例を追記
- コマンド例を `tools/` レイアウトに統一

使い方（例）
- PATH 追加: `source path/to/mpy-tools-path.sh`
  - サブモジュール: `source mpy-tools/mpy-tools-path.sh`
  - リポ直下: `source ./mpy-tools-path.sh`
- PATH 追加後は `prepare.py`, `deploy.py`, `update_version.py` を直接実行可能

Notes (EN)
- Add location-agnostic PATH helper: `mpy-tools-path.sh`
- Update README Quick Start with PATH setup and tools/ usage
- Align command examples with `tools/` layout
