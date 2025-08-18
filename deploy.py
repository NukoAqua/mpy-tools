#!/usr/bin/env python3
"""
MicroPython デプロイツール

指定ディレクトリ配下のファイルをESP32系MicroPythonデバイスに効率的にデプロイします。
- SHA256ハッシュによる差分更新
- webrepl_cfg.py保護
- mpremoteツール / WebREPL による安全なファイル操作
"""

import os
import subprocess
import sys
import hashlib
import json
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# Try to import python-dotenv for .env support
try:
    from dotenv import load_dotenv
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False


class ESP32DeployTool:
    """MicroPython向け効率的デプロイツール"""
    
    def __init__(self, source_dir: str = "mpy_xtensa", device: Optional[str] = None, dry_run: bool = False, use_webrepl: bool = False,
                 webrepl_host: Optional[str] = None, webrepl_port: Optional[int] = None, webrepl_password: Optional[str] = None):
        self.source_dir = Path(source_dir)
        self.device = device
        self.dry_run = dry_run
        self.use_webrepl = use_webrepl
        self.protected_files = {"webrepl_cfg.py"}  # 削除から保護するファイル
        
        # Load environment variables
        self.load_env_config()
        
        # WebREPL settings
        self.webrepl_host = webrepl_host or self.env_config.get('WEBREPL_HOST', 'micropython.local')
        self.webrepl_port = int(webrepl_port or self.env_config.get('WEBREPL_PORT', '8266'))
        self.webrepl_password = webrepl_password if webrepl_password is not None else self.env_config.get('WEBREPL_PASSWORD', '')
        self.webrepl_cli_path = Path(__file__).parent / "webrepl_cli.py"
        
        if self.use_webrepl and not self.webrepl_password:
            print("警告: WebREPLモードが指定されましたが、WEBREPL_PASSWORDが設定されていません。")
        
    def load_env_config(self):
        """環境変数設定を読み込み"""
        self.env_config = {}
        
        # Load from .env file if available
        env_file = Path(__file__).parent.parent / ".env"
        if DOTENV_AVAILABLE and env_file.exists():
            load_dotenv(env_file)
            
        # Get environment variables
        self.env_config = {
            'WEBREPL_HOST': os.getenv('WEBREPL_HOST', 'micropython.local'),
            'WEBREPL_PORT': os.getenv('WEBREPL_PORT', '8266'),
            'WEBREPL_PASSWORD': os.getenv('WEBREPL_PASSWORD', ''),
            'DEBUG_DEPLOY': os.getenv('DEBUG_DEPLOY', 'false').lower() == 'true',
            'MPREMOTE_DEVICE': os.getenv('MPREMOTE_DEVICE', '')
        }
        
    def run_webrepl(self, args: List[str]) -> Tuple[bool, str]:
        """webrepl_cli.pyコマンドを実行"""
        if not self.webrepl_cli_path.exists():
            return False, f"webrepl_cli.pyが見つかりません: {self.webrepl_cli_path}"
            
        try:
            cmd = ["python3", str(self.webrepl_cli_path)] + args
            if self.env_config.get('DEBUG_DEPLOY'):
                print(f"WebREPL実行: {' '.join(cmd)}")
                
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return True, result.stdout.strip()
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() if e.stderr else str(e)
            return False, error_msg
        except FileNotFoundError:
            return False, "python3が見つかりません。"
    
    def run_mpremote(self, args: List[str]) -> Tuple[bool, str]:
        """mpremoteコマンドを実行"""
        try:
            cmd = ["mpremote"] + args
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return True, result.stdout.strip()
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() if e.stderr else str(e)
            return False, error_msg
        except FileNotFoundError:
            return False, "mpremoteが見つかりません。pip install mpremoteを実行してください。"
    
    def list_devices(self) -> List[str]:
        """利用可能なデバイスを検索"""
        success, output = self.run_mpremote(["connect", "list"])
        if not success:
            print(f"デバイス検索失敗: {output}")
            return []
        
        devices = []
        for line in output.split('\n'):
            line = line.strip()
            if not line or line.startswith('ls :'):
                continue
            # 代表的なポート名やキーワードを許容
            port = line.split()[0]
            if port.startswith('/dev/tty') or port.startswith('COM') or 'Espressif' in line:
                devices.append(line)
        return devices
    
    def auto_select_device(self) -> Optional[str]:
        """デバイスを自動選択"""
        if self.device:
            # 指定されたデバイスを使用
            print(f"指定デバイス使用: {self.device}")
            return self.device
        
        print("ESP32/MicroPythonデバイス検索中...")
        devices = self.list_devices()
        
        if not devices:
            print("ESP32/MicroPythonデバイスが見つかりません。")
            print("- デバイスがUSB接続されているか確認してください")
            print("- udevルール設定: sudo usermod -a -G dialout $USER")
            return None
        
        if len(devices) == 1:
            device = devices[0].split()[0]  # ポート部分のみ抽出
            print(f"デバイス発見: {device}")
            return device
        
        print(f"複数のデバイスが見つかりました:")
        for i, device in enumerate(devices, 1):
            print(f"  {i}. {device.split()[0]}")
        print("--device オプションでデバイスを指定してください")
        return None
    
    def get_device_files(self, device: str) -> Dict[str, str]:
        """デバイス上のファイル一覧とSHA256ハッシュを取得"""
        print("デバイスファイル情報取得中...")
        files_info = {}
        
        # ルートディレクトリのファイル一覧
        success, output = self.run_mpremote(["connect", device, "fs", "ls"])
        if not success:
            print(f"ファイル一覧取得失敗: {output}")
            return files_info
        
        # ファイル名を抽出
        device_files = []
        for line in output.split('\n'):
            line = line.strip()
            if line and not line.startswith('ls :') and not line.endswith('/'):
                # ファイル行から名前を抽出
                parts = line.split()
                if len(parts) >= 2:
                    filename = parts[-1]
                    device_files.append(filename)
        
        # 各ファイルのSHA256ハッシュを取得
        for filename in device_files:
            success, hash_output = self.run_mpremote([
                "connect", device, "fs", "sha256sum", filename
            ])
            if success:
                # ハッシュ値のみ抽出
                hash_value = hash_output.split()[-1] if hash_output else ""
                files_info[filename] = hash_value
                print(f"  {filename}: {hash_value[:16]}...")
            else:
                print(f"  {filename}: ハッシュ取得失敗")
                files_info[filename] = ""
        
        return files_info
    
    def get_local_files(self) -> Dict[str, str]:
        """ローカルファイルのSHA256ハッシュを取得（再帰）"""
        print(f"ローカルファイル情報取得中: {self.source_dir}/")
        files_info: Dict[str, str] = {}
        
        if not self.source_dir.exists():
            print(f"エラー: ソースディレクトリが見つかりません: {self.source_dir}")
            return files_info
        
        for file_path in self.source_dir.rglob("*"):
            if file_path.is_file():
                rel = str(file_path.relative_to(self.source_dir))
                try:
                    with open(file_path, 'rb') as f:
                        content = f.read()
                    hash_value = hashlib.sha256(content).hexdigest()
                    files_info[rel] = hash_value
                    print(f"  {rel}: {hash_value[:16]}...")
                except Exception as e:
                    print(f"  {rel}: 読み込み失敗 - {e}")
                    files_info[rel] = ""
        
        return files_info
    
    def calculate_diff(self, local_files: Dict[str, str], device_files: Dict[str, str]) -> Tuple[Set[str], Set[str], Set[str]]:
        """ファイル差分を計算"""
        local_set = set(local_files.keys())
        device_set = set(device_files.keys())
        
        # 新規ファイル（ローカルにあるがデバイスにない）
        new_files = local_set - device_set
        
        # 更新ファイル（ハッシュが異なる）
        updated_files = set()
        for filename in local_set & device_set:
            if local_files[filename] != device_files[filename]:
                updated_files.add(filename)
        
        # 削除ファイル（デバイスにあるがローカルにない、ただし保護ファイルは除外）
        obsolete_files = (device_set - local_set) - self.protected_files
        
        return new_files, updated_files, obsolete_files
    
    def remove_obsolete_files(self, device: str, obsolete_files: Set[str]) -> bool:
        """不要なファイルを削除"""
        if not obsolete_files:
            return True
        
        if self.dry_run:
            print(f"\n[DRY RUN] 不要ファイル削除予定: {len(obsolete_files)}個")
            for filename in obsolete_files:
                print(f"  [予定] 削除: {filename}")
            return True
        
        print(f"\n不要ファイル削除中: {len(obsolete_files)}個")
        failed_files = []
        
        for filename in obsolete_files:
            print(f"  削除: {filename}")
            success, output = self.run_mpremote([
                "connect", device, "fs", "rm", filename
            ])
            if not success:
                print(f"    削除失敗: {output}")
                failed_files.append(filename)
        
        if failed_files:
            print(f"警告: {len(failed_files)}個のファイル削除に失敗")
            return False
        
        return True

    def _ensure_remote_dirs(self, device: str, remote_path: str) -> None:
        """必要なリモートディレクトリを作成（既存なら無視）"""
        p = Path(remote_path)
        parts = list(p.parts)
        cur = Path('/')
        for i, part in enumerate(parts):
            if part in ('', '.'):
                continue
            cur = cur / part
            # 最後がファイル名っぽい場合はスキップ
            if i == len(parts) - 1 and '.' in part:
                break
            self.run_mpremote(["connect", device, "fs", "mkdir", f":{str(cur)}"])  # 失敗は無視

    def copy_files(self, device: str, files_to_copy: Set[str]) -> bool:
        """ファイルをデバイスにコピー（サブディレクトリ対応）"""
        if not files_to_copy:
            return True
        
        if self.dry_run:
            print(f"\n[DRY RUN] ファイルコピー予定: {len(files_to_copy)}個")
            for filename in files_to_copy:
                local_path = self.source_dir / filename
                print(f"  [予定] コピー: {filename}")
                print(f"    ソース: {local_path}")
                print(f"    デバイス: /{filename}")
            return True
        
        print(f"\nファイルコピー中: {len(files_to_copy)}個")
        failed_files = []
        
        for filename in files_to_copy:
            local_path = self.source_dir / filename
            print(f"  コピー: {filename}")
            # リモート側のディレクトリが必要なら作成
            parent = Path(filename).parent
            if str(parent) not in (".", ""):
                self._ensure_remote_dirs(device, f"/{parent}")
            
            success, output = self.run_mpremote([
                "connect", device, "fs", "cp", str(local_path), f":/{filename}"
            ])
            
            if success:
                print(f"    完了: {filename}")
            else:
                print(f"    失敗: {filename} - {output}")
                failed_files.append(filename)
        
        if failed_files:
            print(f"エラー: {len(failed_files)}個のファイルコピーに失敗")
            return False
        
        return True
    
    def copy_files_webrepl(self, files_to_copy: Set[str]) -> bool:
        """WebREPL経由でファイルをデバイスにコピー"""
        if not files_to_copy:
            return True
        
        if not self.webrepl_password:
            print("エラー: WebREPLパスワードが設定されていません")
            return False
        
        if self.dry_run:
            print(f"\n[DRY RUN] WebREPLファイルコピー予定: {len(files_to_copy)}個")
            for filename in files_to_copy:
                local_path = self.source_dir / filename
                print(f"  [予定] WebREPLコピー: {filename}")
                print(f"    ソース: {local_path}")
                print(f"    WebREPL: {self.webrepl_host}:/{filename}")
            return True
        
        print(f"\nWebREPLファイルコピー中: {len(files_to_copy)}個")
        failed_files = []
        
        for filename in files_to_copy:
            local_path = self.source_dir / filename
            remote_target = f"{self.webrepl_host}:/{filename}"
            
            print(f"  WebREPLコピー: {filename}")
            
            # Construct webrepl_cli.py command: local_file host:remote_file
            args = ["-p", self.webrepl_password, str(local_path), remote_target]
            
            success, output = self.run_webrepl(args)
            
            if success:
                print(f"    完了: {filename}")
            else:
                print(f"    失敗: {filename} - {output}")
                failed_files.append(filename)
        
        if failed_files:
            print(f"エラー: {len(failed_files)}個のWebREPLファイルコピーに失敗")
            return False
        
        return True
    
    def test_webrepl_connection(self) -> bool:
        """WebREPL接続テスト"""
        if not self.webrepl_password:
            print("エラー: WebREPLパスワードが設定されていません")
            return False
        
        print(f"WebREPL接続テスト中: {self.webrepl_host}:{self.webrepl_port}")
        
        # Test REPL connection
        args = ["-p", self.webrepl_password, self.webrepl_host]
        success, output = self.run_webrepl(args)
        
        if success:
            print("WebREPL接続成功")
            return True
        else:
            print(f"WebREPL接続失敗: {output}")
            return False
    
    def soft_reset_device(self, device: str) -> bool:
        """デバイスをソフトリセット"""
        if self.dry_run:
            print("\n[DRY RUN] ソフトリセット予定")
            print("  [予定] デバイスをソフトリセット")
            return True
        
        print("\nデバイスをソフトリセット中...")
        success, output = self.run_mpremote(["connect", device, "soft-reset"])
        
        if success:
            print("ソフトリセット完了")
            return True
        else:
            print(f"ソフトリセット失敗: {output}")
            return False
    
    def show_summary(self, new_files: Set[str], updated_files: Set[str], obsolete_files: Set[str]):
        """デプロイサマリーを表示"""
        print("\n" + "=" * 50)
        if self.dry_run:
            print("デプロイ予定サマリー [DRY RUN]")
        else:
            print("デプロイサマリー")
        print("=" * 50)
        
        if new_files:
            action = "新規予定" if self.dry_run else "新規ファイル"
            print(f"{action}: {len(new_files)}個")
            for filename in sorted(new_files):
                print(f"  + {filename}")
        
        if updated_files:
            action = "更新予定" if self.dry_run else "更新ファイル"
            print(f"{action}: {len(updated_files)}個")
            for filename in sorted(updated_files):
                print(f"  ~ {filename}")
        
        if obsolete_files:
            action = "削除予定" if self.dry_run else "削除ファイル"
            print(f"{action}: {len(obsolete_files)}個")
            for filename in sorted(obsolete_files):
                print(f"  - {filename}")
        
        if not (new_files or updated_files or obsolete_files):
            print("変更なし: デバイスは最新状態です")
        
        total_changes = len(new_files) + len(updated_files) + len(obsolete_files)
        if self.dry_run:
            print(f"\n総変更予定: {total_changes}個")
        else:
            print(f"\n総変更数: {total_changes}個")
    
    def deploy_webrepl(self) -> bool:
        """WebREPL経由でのデプロイ処理"""
        print(f"WebREPL モード: {self.webrepl_host}:{self.webrepl_port}")
        print("=" * 45)
        
        # WebREPL接続テスト
        if not self.test_webrepl_connection():
            print("エラー: WebREPL接続に失敗しました")
            return False
        
        # ローカルファイル情報取得
        local_files = self.get_local_files()
        if not local_files:
            print("エラー: デプロイするファイルがありません")
            return False
        
        print(f"\nWebREPL経由でファイル転送中: {len(local_files)}個")
        
        # WebREPLではハッシュ比較ができないため、全ファイルを転送
        files_to_copy = set(local_files.keys())
        
        # WebREPLファイルコピー
        if files_to_copy:
            if not self.copy_files_webrepl(files_to_copy):
                print("エラー: WebREPLファイル転送に失敗しました")
                return False
        
        print("\n" + "=" * 45)
        if self.dry_run:
            print("WebREPL ドライラン完了！実際のデプロイは --dry-run なしで実行してください")
        else:
            print("WebREPL デプロイ完了！")
        return True
    
    def deploy(self) -> bool:
        """メインデプロイ処理"""
        print("MicroPython デプロイツール")
        print("=" * 45)
        
        # WebREPL使用時の処理
        if self.use_webrepl:
            return self.deploy_webrepl()
        
        # デバイス選択
        device = self.auto_select_device()
        if not device:
            return False
        
        # ローカルファイル情報取得
        local_files = self.get_local_files()
        if not local_files:
            print("エラー: デプロイするファイルがありません")
            return False
        
        # デバイスファイル情報取得
        device_files = self.get_device_files(device)
        
        # 差分計算
        new_files, updated_files, obsolete_files = self.calculate_diff(local_files, device_files)
        
        # サマリー表示
        self.show_summary(new_files, updated_files, obsolete_files)
        
        # 変更がない場合は早期終了
        if not (new_files or updated_files or obsolete_files):
            if self.dry_run:
                print("\nドライラン完了: 変更はありません")
            else:
                print("\nデプロイ完了: 変更はありません")
            return True
        
        # 不要ファイル削除
        if obsolete_files:
            if not self.remove_obsolete_files(device, obsolete_files):
                print("警告: 一部ファイルの削除に失敗しました")
        
        # ファイルコピー（新規 + 更新）
        files_to_copy = new_files | updated_files
        if files_to_copy:
            if not self.copy_files(device, files_to_copy):
                print("エラー: ファイルコピーに失敗しました")
                return False
        
        # ソフトリセット
        if not self.soft_reset_device(device):
            print("警告: ソフトリセットに失敗しました")
        
        print("\n" + "=" * 45)
        if self.dry_run:
            print("ドライラン完了！実際のデプロイは --dry-run なしで実行してください")
        else:
            print("デプロイ完了！")
        return True


def main():
    """メイン関数"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='MicroPython デプロイツール',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
使用例:
  python3 deploy.py                           # 自動デバイス検出
  python3 deploy.py --device /dev/ttyACM0     # デバイス指定
  python3 deploy.py --source mpy_xtensa       # ソースディレクトリ変更
  python3 deploy.py --dry-run                 # 変更内容の事前確認
  python3 deploy.py --webrepl                 # WebREPL経由でデプロイ
  python3 deploy.py --webrepl --dry-run       # WebREPLドライラン
        '''
    )
    
    parser.add_argument(
        '--device', '-d',
        help='ESP32デバイスポート (例: /dev/ttyACM0)'
    )
    parser.add_argument(
        '--source', '-s',
        default='mpy_xtensa',
        help='ソースディレクトリ (デフォルト: mpy_xtensa)'
    )
    parser.add_argument(
        '--dry-run', '-n',
        action='store_true',
        help='実際の変更を行わず、予定される変更内容のみを表示'
    )
    parser.add_argument(
        '--webrepl', '-w',
        action='store_true',
        help='WebREPL経由でファイル転送（.envにWEBREPL_PASSWORDが必要）'
    )
    parser.add_argument('--webrepl-host', default=None, help='WebREPL ホスト名 (例: micropython.local)')
    parser.add_argument('--webrepl-port', type=int, default=None, help='WebREPL ポート (例: 8266)')
    parser.add_argument('--webrepl-password', default=None, help='WebREPL パスワード (未指定時は環境変数)')
    
    args = parser.parse_args()
    
    # WebREPLモードの場合のバリデーション
    if args.webrepl and args.device:
        print("警告: WebREPLモードでは--deviceオプションは無視されます")
    
    try:
        deploy_tool = ESP32DeployTool(
            source_dir=args.source,
            device=args.device,
            dry_run=args.dry_run,
            use_webrepl=args.webrepl,
            webrepl_host=args.webrepl_host,
            webrepl_port=args.webrepl_port,
            webrepl_password=args.webrepl_password
        )
        
        success = deploy_tool.deploy()
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\n\n操作がキャンセルされました")
        sys.exit(1)
    except Exception as e:
        print(f"\n予期しないエラー: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
