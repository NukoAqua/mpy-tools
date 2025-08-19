# UPDATE_VERSION

MicroPython モジュールのバージョン管理ツール。`src/` を走査し、`src/version.json` を更新します。各 `.py` の SHA-256 を比較し、変更があれば `__version__` をポリシーに従って自動インクリメントして書き戻します。

## 主な機能
- 走査: `src/` 以下の `.py` を再帰収集
- ハッシュ比較: `version.json` の SHA-256 と比較し、新規/変更/欠落を判定
- 自動バンプ: 変更検出時、`__version__` を `patch`/`minor`/`major` の方針で更新
- パターン対応: `__version__ = "x.x.x"` と `__version__ = const("x.x.x")` の両方に対応
- 出力: 最新の `modules`（バージョン）と `SHA-256` を `version.json` に保存

## 使い方
- 既定: `python3 update_version.py`
- ソースを変える: `python3 update_version.py --src mysrc`
- バンプ方針: `python3 update_version.py --bump patch`（既定は `minor`）
- `version.json` 明示: `python3 update_version.py --version-file src/version.json`

## オプション
- `--src <dir>`: 走査対象のソースディレクトリ（既定: `src`）
- `--version-file <path>`: `version.json` のパス（既定: `<src>/version.json`）
- `--bump patch|minor|major`: 変更検出時のバージョン更新ポリシー（既定: `minor`）

## 振る舞いの要点
- `__version__` が見つからないファイルは既定値 `0.1.0` として扱い、ファイル本体の更新は行いません
- バージョンを更新した場合はファイルを書き戻した後にハッシュを再計算します
- `version.json` にのみ存在して `src/` に無いファイルは「欠落」として一覧表示（削除はしない）

## 推奨ワークフロー
1) `python3 update_version.py` で `src/version.json` を最新化
2) `python3 prepare.py` でバンドル/コンパイル（`src/version.json` と `mpy_*/version.json` を生成）
3) `python3 deploy.py --source mpy_xtensa` でデプロイ（`--dry-run` 推奨）
