# DEPLOY

MicroPython デプロイツール。`mpy_xtensa/` などの出力ディレクトリ配下を ESP32/MicroPython デバイスへ安全かつ効率的に配置します。`mpremote`（USB）または WebREPL 経由で動作し、SHA-256 による差分更新と保護ファイルの扱いに対応します。

## 主な機能
- 差分更新: ローカルとデバイスの SHA-256 を比較し、新規/更新/削除を算出
- 安全な削除: `webrepl_cfg.py` は保護（削除対象から除外）
- 再帰コピー: サブディレクトリを含めてコピー（必要ならリモート側ディレクトリを自動作成）
- WebREPL: `.env`/環境変数から接続設定を読み込み（`WEBREPL_HOST/PORT/PASSWORD`）
- ドライラン: 実際の変更を行わず予定だけ表示

## 前提ツール
- `mpremote`（USB デプロイ）
- 任意: `python-dotenv`（`.env` 読み込みに利用）

## 使い方（USB/mpremote）
- 自動検出でデプロイ: `python3 deploy.py --source mpy_xtensa`
- デバイス指定: `python3 deploy.py --source mpy_xtensa --device /dev/ttyACM0`
- 変更の事前確認: `python3 deploy.py --source mpy_xtensa --dry-run`

ヒント:
- 権限エラー時は `dialout` グループ追加等を確認（例: `sudo usermod -a -G dialout $USER`）
- `mpremote` が未インストールの場合は `pip install mpremote`

## 使い方（WebREPL）
- 事前に `.env`（リポジトリルート）で `WEBREPL_HOST`, `WEBREPL_PORT`, `WEBREPL_PASSWORD` を設定
- ドライラン: `python3 deploy.py -w --source mpy_xtensa --dry-run`
- 実行: `python3 deploy.py -w --source mpy_xtensa`

備考:
- WebREPL ではデバイス側ハッシュ比較ができないため、全ファイルを転送します。
- 内部で `tools/webrepl_cli.py` を呼び出します。

## オプション
- `--device, -d <port>`: シリアルポートを指定（例: `/dev/ttyACM0`）。WebREPL モードでは無視
- `--source, -s <dir>`: デプロイ元ディレクトリ（既定: `mpy_xtensa`）
- `--dry-run, -n`: 変更せず計画のみ表示
- `--webrepl, -w`: WebREPL を使用（`.env` または環境変数が必要）
- `--webrepl-host <host>` / `--webrepl-port <port>` / `--webrepl-password <pw>`: WebREPL パラメータを明示指定

## 動作の流れ（USB）
- デバイス検出（単一なら自動選択。複数は一覧表示）
- ローカルの SHA-256 を再帰計算
- デバイスのファイル一覧と SHA-256 を取得
- 差分分類（新規・更新・削除）をサマリ表示
- 削除対象を削除（保護ファイル除外）
- 新規/更新ファイルをコピー
- ソフトリセットを実行

## トラブルシューティング
- `デバイスが見つからない`: ケーブル・ポート・権限・ボーレート/リセットを確認
- `mpremote がない`: `pip install mpremote` を実行
- `WebREPL 失敗`: `WEBREPL_PASSWORD` 設定、ホスト/ポート疎通、`webrepl_cli.py` の配置を確認
