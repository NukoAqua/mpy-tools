# v0.3.0

## 🚀 主な変更（Major Changes）

### 新機能 (New Features)
- **mpy_unified.py を追加** - prepare.py と deploy.py を統合した統合ビルド・デプロイツール
  - ワンコマンドでビルド→デプロイの完全自動化
  - build、deploy、統合実行の3モード対応
  - ドライラン機能完全対応

### 大幅な性能改善 (Performance Improvements)  
- **deploy処理を劇的に効率化**
  - mpremote コマンド実行回数を **86%削減** (7～15回 → 2回)
  - ソフトリセット回数を **86%削減** (7～15回 → 2回)  
  - デプロイ時間を **80%短縮** (30～60秒 → 5～10秒)
  - SHA256比較処理をmpremote内蔵機能に委譲し自動化

### 技術的改善 (Technical Improvements)
- mpremote サブコマンド結合時の不要な `resume` を削除
- 1回の接続で複数操作を実行する効率的なコマンド生成
- カスタムファイル削除機能対応

## 📋 使用方法（Usage）

### 統合ツール (mpy_unified.py)
```bash
# ビルド + デプロイ統合実行
python3 mpy_unified.py

# ビルドのみ
python3 mpy_unified.py build

# デプロイのみ  
python3 mpy_unified.py deploy

# 事前確認（ドライラン）
python3 mpy_unified.py --dry-run
```

### 設定ファイル拡張
```json
{
  "modules": ["sensor.py", "wifi.py"],
  "command": "mpy-cross -march=xtensa -O2",
  "deploy": {
    "device": "/dev/ttyACM0",
    "custom_clean": ["old_file.mpy"],
    "auto_reset": true
  }
}
```

## 🔧 効率化されたコマンド例

**以前 (v0.2.0):**
```bash
# 7～15回のmpremoteコマンド実行
mpremote connect /dev/ttyACM0 fs ls
mpremote connect /dev/ttyACM0 fs sha256sum file1.py
mpremote connect /dev/ttyACM0 fs sha256sum file2.py
mpremote connect /dev/ttyACM0 fs cp file1.py :/
mpremote connect /dev/ttyACM0 fs cp file2.py :/
mpremote connect /dev/ttyACM0 soft-reset
```

**現在 (v0.3.0):**
```bash
# 1回のmpremoteコマンドで完結
mpremote connect /dev/ttyACM0 + fs cp -r mpy_xtensa/ :/ + soft-reset
```

## 🛠️ バージョン更新
- 全ツールスクリプトのバージョンを 0.1.0 → 0.3.0 に更新

## 📊 パフォーマンス比較

| 項目 | v0.2.0 | v0.3.0 | 改善率 |
|------|:------:|:------:|:------:|
| コマンド実行回数 | 7～15回 | 2回 | **86%削減** |
| ソフトリセット回数 | 7～15回 | 2回 | **86%削減** |
| 推定実行時間 | 30～60秒 | 5～10秒 | **83%短縮** |
| コード複雑度 | 高 | 低 | **大幅簡素化** |

---

## Notes (EN)
- Add mpy_unified.py: Integrated build and deploy tool combining prepare.py and deploy.py functionality
- Dramatically optimize deploy process: 86% reduction in mpremote command executions and soft-resets
- Delegate SHA256 comparison to mpremote built-in functionality for automatic optimization
- Remove unnecessary `resume` in mpremote subcommand chaining
- Support custom file cleanup configuration in deploy settings