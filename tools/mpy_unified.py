#!/usr/bin/env python3
"""
MicroPython 統合ビルド・デプロイツール

prepare.pyとdeploy.pyの機能を統合し、ワンコマンドでビルドからデプロイまでを実行します。
- mpy-crossによるプリコンパイル
- mpremote/WebREPLによるデバイス転送
- SHA256ハッシュによる差分更新
"""

__version__ = "0.3.0"

import json
import os
import subprocess
import sys
import shutil
import re
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# Try to import python-dotenv for .env support
try:
    from dotenv import load_dotenv
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False


class MicroPythonBuildDeployTool:
    """MicroPython統合ビルド・デプロイツール"""
    
    def __init__(self, config_file: Optional[str] = None, src_dir: str = "src", 
                 output_dir: str = "mpy_xtensa", dry_run: bool = False, 
                 device: Optional[str] = None, use_webrepl: bool = False,
                 preserve_dirs: bool = False):
        self.config_file = config_file
        self.src_dir = src_dir
        self.output_dir = output_dir
        self.dry_run = dry_run
        self.device = device
        self.use_webrepl = use_webrepl
        self.preserve_dirs = preserve_dirs
        self.protected_files = {"webrepl_cfg.py"}
        
        # Load configuration
        self.config = self.load_config()
        if not self.config:
            raise ValueError("設定ファイルの読み込みに失敗しました")
            
        # Auto-adjust output directory based on architecture
        self.arch = self.parse_arch_from_command(self.config.get('command', ''))
        if self.arch and self.output_dir == 'mpy_xtensa' and self.arch != 'xtensa':
            self.output_dir = f"mpy_{self.arch}"
            
        # Load environment variables
        self.load_env_config()
        
        # WebREPL settings from config or environment
        deploy_config = self.config.get('deploy', {})
        self.webrepl_host = deploy_config.get('host', self.env_config.get('WEBREPL_HOST', 'micropython.local'))
        self.webrepl_port = int(deploy_config.get('port', self.env_config.get('WEBREPL_PORT', '8266')))
        self.webrepl_password = deploy_config.get('password', self.env_config.get('WEBREPL_PASSWORD', ''))
        self.webrepl_cli_path = Path(__file__).parent / "webrepl_cli.py"
        
        # Override with config file settings
        if not self.use_webrepl and deploy_config.get('use_webrepl', False):
            self.use_webrepl = True
            
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

    def parse_arch_from_command(self, command: str) -> str | None:
        """mpy-crossコマンドラインから -march=<arch> を抽出"""
        if not command:
            return None
        m = re.search(r"-march=([A-Za-z0-9_]+)", command)
        return m.group(1) if m else None

    def load_config(self):
        """設定ファイルを読み込み"""
        candidates = []
        if self.config_file:
            candidates.append(self.config_file)
        candidates.extend(["prepare.json", "src/prepare.json"])
        
        for path in candidates:
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
                    print(f"設定ファイル: {path}")
                    return cfg
            except FileNotFoundError:
                continue
            except json.JSONDecodeError as e:
                print(f"エラー: {path} の JSON 形式が正しくありません: {e}")
                return None
        
        print("エラー: 設定ファイルが見つかりません (prepare.json など)")
        return None

    def find_file_in_submodules(self, filename, submodules):
        """サブモジュール内でファイルを検索"""
        for submodule in submodules:
            submodule_path = Path(submodule) / "src" / filename
            if submodule_path.exists():
                print(f"  サブモジュールで発見: {submodule_path}")
                return submodule_path
        return None

    def collect_module_versions(self, module_list=None, copy_only_list=None, submodules=None):
        """srcフォルダとサブモジュールからバージョン情報とSHA-256ハッシュを収集"""
        versions = {}
        hashes = {}
        src_path = Path(self.src_dir)
        
        print(f"モジュールのバージョン情報とハッシュを収集中...")
        
        all_files = []
        if module_list:
            all_files.extend(module_list)
        if copy_only_list:
            all_files.extend(copy_only_list)
        
        for filename in all_files:
            file_path = src_path / filename
            
            if not file_path.exists() and submodules:
                file_path = self.find_file_in_submodules(filename, submodules)
                if not file_path:
                    print(f"  警告: {filename} が見つかりません - スキップします")
                    continue
            elif not file_path.exists():
                print(f"  警告: {filename} が見つかりません - スキップします")
                continue
            
            try:
                with open(file_path, 'rb') as f:
                    file_bytes = f.read()
                
                sha256_hash = hashlib.sha256(file_bytes).hexdigest()
                hashes[filename] = sha256_hash
                
                content = file_bytes.decode('utf-8')
                version_patterns = [
                    r'__version__\s*=\s*["\']([^"\']+)["\']',
                    r'__version__\s*=\s*const\s*\(\s*["\']([^"\']+)["\']\s*\)'
                ]
                
                version_found = False
                for pattern in version_patterns:
                    match = re.search(pattern, content)
                    if match:
                        version = match.group(1)
                        versions[filename] = version
                        print(f"  {filename}: {version} (SHA-256: {sha256_hash[:16]}...)")
                        version_found = True
                        break
                
                if not version_found:
                    versions[filename] = "unknown"
                    print(f"  {filename}: バージョン情報なし (SHA-256: {sha256_hash[:16]}...)")
                    
            except Exception as e:
                print(f"  エラー: {filename} の読み込みに失敗: {e}")
                versions[filename] = "error"
                hashes[filename] = "error"
        
        return versions, hashes

    def create_version_json(self, versions, hashes):
        """収集したバージョン情報とハッシュをversion.jsonファイルとして保存"""
        if self.dry_run:
            print(f"[DRY RUN] version.json作成予定: {Path(self.src_dir) / 'version.json'}")
            print(f"[予定] 総モジュール数: {len(versions)}")
            versioned_modules = sum(1 for v in versions.values() if v not in ["unknown", "error"])
            print(f"[予定] バージョン情報あり: {versioned_modules}")
            return True
        
        version_data = {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "description": "PaquaAutoDrain + ESP32s3base unified modules",
            "source_directory": self.src_dir,
            "format": "py",
            "architecture": "source",
            "modules": versions,
            "SHA-256": hashes
        }
        
        version_file = Path(self.src_dir) / "version.json"
        
        try:
            with open(version_file, 'w', encoding='utf-8') as f:
                json.dump(version_data, f, indent=2, ensure_ascii=False)
            
            print(f"version.jsonを作成しました: {version_file}")
            print(f"  総モジュール数: {len(versions)}")
            versioned_modules = sum(1 for v in versions.values() if v not in ["unknown", "error"])
            print(f"  バージョン情報あり: {versioned_modules}")
            return True
            
        except Exception as e:
            print(f"エラー: version.json作成中にエラー: {e}")
            return False

    def check_mpy_cross(self):
        """mpy-crossコマンドが利用可能かチェック"""
        try:
            result = subprocess.run(['mpy-cross', '--version'], 
                                  capture_output=True, text=True, check=True)
            print(f"mpy-cross が見つかりました: {result.stdout.strip()}")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("エラー: mpy-cross コマンドが見つかりません")
            print("インストール方法:")
            print("  pip install mpy-cross")
            return False

    def create_output_dir(self):
        """出力ディレクトリを作成"""
        device_src_path = Path(self.output_dir)
        
        if self.dry_run:
            if device_src_path.exists():
                print(f"[DRY RUN] 既存の出力ディレクトリクリア予定: {device_src_path}")
            print(f"[DRY RUN] 出力ディレクトリ作成予定: {device_src_path}")
            return device_src_path
        
        if device_src_path.exists():
            print(f"既存の出力ディレクトリをクリア: {device_src_path}")
            shutil.rmtree(device_src_path)

        device_src_path.mkdir()
        print(f"出力ディレクトリを作成しました: {device_src_path}")
        return device_src_path

    def copy_only_files(self, copy_only_list, submodules=None):
        """指定されたファイルをそのままコピー"""
        src_path = Path(self.src_dir)
        device_src_path = Path(self.output_dir)
        
        if self.dry_run:
            print(f"\n[DRY RUN] コピーのみファイル処理予定...")
        else:
            print(f"\nコピーのみファイルを処理中...")
        
        results = []
        
        for filename in copy_only_list:
            file_path = src_path / filename
            
            if not file_path.exists() and submodules:
                file_path = self.find_file_in_submodules(filename, submodules)
                if not file_path:
                    print(f"  警告: {filename} が見つかりません - スキップします")
                    results.append({'file': filename, 'success': False})
                    continue
            elif not file_path.exists():
                print(f"  警告: {filename} が見つかりません - スキップします")
                results.append({'file': filename, 'success': False})
                continue
            
            try:
                original_size = file_path.stat().st_size
                dest_path = device_src_path / filename if not self.preserve_dirs else device_src_path / Path(filename)
                if self.preserve_dirs and not self.dry_run:
                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                
                if self.dry_run:
                    print(f"  [予定] コピー: {file_path} -> {dest_path} ({original_size} bytes)")
                    results.append({'file': filename, 'success': True})
                else:
                    shutil.copy2(file_path, dest_path)
                    print(f"  コピー: {file_path} -> {dest_path} ({original_size} bytes)")
                    results.append({'file': filename, 'success': True})
                
            except Exception as e:
                if self.dry_run:
                    results.append({'file': filename, 'success': True})
                else:
                    print(f"  エラー: {filename} のコピーに失敗: {e}")
                    results.append({'file': filename, 'success': False})
        
        return results

    def compile_module(self, filename, command, submodules=None):
        """単一モジュールをコンパイル"""
        src_path = Path(self.src_dir)
        
        file_path = src_path / filename
        
        if not file_path.exists() and submodules:
            file_path = self.find_file_in_submodules(filename, submodules)
            if not file_path:
                print(f"  警告: {filename} が見つかりません - スキップします")
                return False
        elif not file_path.exists():
            print(f"  警告: {filename} が見つかりません - スキップします")
            return False
        
        if self.dry_run:
            print(f"  [予定] コンパイル: {filename}")
        else:
            print(f"  コンパイル中: {filename}")
        
        original_size = file_path.stat().st_size
        
        if self.dry_run:
            estimated_compressed_size = int(original_size * 0.7)
            compression_ratio = (1 - estimated_compressed_size / original_size) * 100
            device_mpy_path = (Path(self.output_dir) / f"{Path(filename).stem}.mpy") if not self.preserve_dirs else (Path(self.output_dir) / Path(filename).with_suffix('.mpy'))
            
            print(f"    [予定] 成功: {original_size} bytes -> {estimated_compressed_size} bytes "
                  f"({compression_ratio:.1f}% 削減 - 推定)")
            print(f"    [予定] 配置: {device_mpy_path}")
            return True
        
        temp_mpy_path = file_path.parent / f"{Path(filename).stem}.mpy"
        cmd = command.strip().split() + [str(file_path)]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            if temp_mpy_path.exists():
                compiled_size = temp_mpy_path.stat().st_size
                compression_ratio = (1 - compiled_size / original_size) * 100
                
                device_mpy_path = (Path(self.output_dir) / f"{Path(filename).stem}.mpy") if not self.preserve_dirs else (Path(self.output_dir) / Path(filename).with_suffix('.mpy'))
                if self.preserve_dirs:
                    device_mpy_path.parent.mkdir(parents=True, exist_ok=True)
                
                shutil.move(str(temp_mpy_path), str(device_mpy_path))
                
                print(f"    成功: {original_size} bytes -> {compiled_size} bytes "
                      f"({compression_ratio:.1f}% 削減)")
                print(f"    配置: {device_mpy_path}")
                
                return True
            else:
                print(f"    エラー: {temp_mpy_path} が作成されませんでした")
                return False
                
        except subprocess.CalledProcessError as e:
            print(f"    エラー: コンパイルに失敗しました")
            print(f"    コマンド: {' '.join(cmd)}")
            if e.stderr:
                print(f"    エラー詳細: {e.stderr}")
            return False

    def create_device_version_json(self):
        """出力ディレクトリ用のversion.jsonを作成"""
        version_file = Path(self.output_dir) / "version.json"
        device_src_path = Path(self.output_dir)
        
        if self.dry_run:
            print(f"[DRY RUN] 出力用version.json作成予定: {version_file}")
            return
        
        try:
            with open(Path(self.src_dir) / "version.json", "r") as f:
                version_data = json.load(f)
            
            version_data["compiled_at"] = datetime.now().isoformat(timespec="seconds")
            version_data["format"] = "mpy"
            if self.arch:
                version_data["architecture"] = self.arch
            version_data["optimization"] = "O2"
            
            new_modules = {}
            new_hashes = {}
            
            print(f"統合ファイルのハッシュを計算中...")
            
            for file_path in device_src_path.rglob('*'):
                if file_path.is_file():
                    relative_path = file_path.relative_to(device_src_path)
                    filename = str(relative_path)
                    
                    try:
                        with open(file_path, 'rb') as f:
                            file_bytes = f.read()
                        file_hash = hashlib.sha256(file_bytes).hexdigest()
                        new_hashes[filename] = file_hash
                        
                        original_name = filename.replace('.mpy', '.py')
                        if original_name in version_data.get("modules", {}):
                            new_modules[filename] = version_data["modules"][original_name]
                        else:
                            new_modules[filename] = "unknown"
                        
                        print(f"  {filename}: {file_hash[:16]}...")
                        
                    except Exception as e:
                        print(f"  エラー: {filename} のハッシュ計算に失敗: {e}")
                        new_hashes[filename] = "error"
                        new_modules[filename] = "error"
            
            version_data["modules"] = new_modules
            version_data["SHA-256"] = new_hashes
            
            with open(version_file, "w") as f:
                json.dump(version_data, f, indent=2, ensure_ascii=False)
            
            print(f"出力用version.jsonを作成: {version_file}")
            print(f"  統合ファイル数: {len(new_modules)}")
            print(f"  ハッシュ計算済み: {len([h for h in new_hashes.values() if h not in ['error', 'missing']])}")
            
        except FileNotFoundError:
            print(f"警告: {Path(self.src_dir) / 'version.json'} が見つかりません")
        except Exception as e:
            print(f"エラー: version.json作成中にエラー: {e}")

    def build(self) -> bool:
        """ビルド処理（prepare相当）"""
        print(f"=== ビルド処理開始 ===")
        print(f"ソース: {self.src_dir}")
        print(f"出力: {self.output_dir}")
        if self.arch:
            print(f"アーキテクチャ: {self.arch}")
        print()
        
        # mpy-crossの確認
        if self.dry_run:
            print(f"[DRY RUN] mpy-cross確認をスキップ")
        elif not self.check_mpy_cross():
            return False
        
        # バージョン情報収集
        print(f"=== {self.src_dir}/version.json作成 ===")
        if self.dry_run:
            print(f"[DRY RUN] モジュールのバージョン情報とハッシュ収集予定")
        
        module_versions, module_hashes = self.collect_module_versions(
            self.config.get('modules', []), 
            self.config.get('copy_only', []),
            self.config.get('submodules', [])
        )
        
        if not self.create_version_json(module_versions, module_hashes):
            if not self.dry_run:
                print(f"警告: {self.src_dir}/version.json作成に失敗しました")
        
        # 出力ディレクトリ作成
        self.create_output_dir()
        
        # コピーのみファイルの処理
        copy_results = []
        if self.config.get('copy_only'):
            copy_results = self.copy_only_files(
                self.config['copy_only'], 
                self.config.get('submodules', [])
            )
        
        # コンパイル実行
        compile_results = []
        if self.config.get('modules'):
            if self.dry_run:
                print(f"\n[DRY RUN] コンパイル予定...")
            else:
                print(f"\nコンパイル開始...")
            print(f"コマンド: {self.config['command']}")
            print(f"対象モジュール: {len(self.config['modules'])} 個")
            print(f"出力先: {self.output_dir}/")
            
            for module in self.config['modules']:
                success = self.compile_module(
                    module,
                    self.config['command'],
                    self.config.get('submodules', [])
                )
                compile_results.append({'module': module, 'success': success})
        
        # 出力用version.json作成
        self.create_device_version_json()
        
        # 結果表示
        self.show_build_summary(copy_results, compile_results)
        
        # 失敗があった場合はFalseを返す
        failed_copy = sum(1 for r in copy_results if not r['success'])
        failed_compile = sum(1 for r in compile_results if not r['success'])
        
        if failed_copy > 0 or failed_compile > 0:
            print(f"\n警告: ビルド処理中にエラーが発生しました")
            return False
        
        print(f"\n=== ビルド処理完了 ===")
        return True

    def show_build_summary(self, copy_results, compile_results):
        """ビルド結果のサマリーを表示"""
        total_copy = len(copy_results)
        success_copy = sum(1 for r in copy_results if r['success'])
        failed_copy = total_copy - success_copy
        
        total_compile = len(compile_results)
        success_compile = sum(1 for r in compile_results if r['success'])
        failed_compile = total_compile - success_compile
        
        print(f"\n=== ビルド結果 ===")
        print(f"コピーファイル: {total_copy} 個 (成功: {success_copy}, 失敗: {failed_copy})")
        print(f"コンパイルファイル: {total_compile} 個 (成功: {success_compile}, 失敗: {failed_compile})")
        
        if failed_copy > 0:
            print(f"\nコピー失敗ファイル:")
            for result in copy_results:
                if not result['success']:
                    print(f"  - {result['file']}")
        
        if failed_compile > 0:
            print(f"\nコンパイル失敗ファイル:")
            for result in compile_results:
                if not result['success']:
                    print(f"  - {result['module']}")

    # デプロイ関連のメソッドは次に実装
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
            port = line.split()[0]
            if port.startswith('/dev/tty') or port.startswith('COM') or 'Espressif' in line:
                devices.append(line)
        return devices
    
    def auto_select_device(self) -> Optional[str]:
        """デバイスを自動選択"""
        if self.device:
            print(f"指定デバイス使用: {self.device}")
            return self.device
        
        # 設定ファイルからデバイス取得
        deploy_config = self.config.get('deploy', {})
        config_device = deploy_config.get('device')
        if config_device:
            print(f"設定ファイルのデバイス使用: {config_device}")
            return config_device
        
        print("ESP32/MicroPythonデバイス検索中...")
        devices = self.list_devices()
        
        if not devices:
            print("ESP32/MicroPythonデバイスが見つかりません。")
            print("- デバイスがUSB接続されているか確認してください")
            print("- udevルール設定: sudo usermod -a -G dialout $USER")
            return None
        
        if len(devices) == 1:
            device = devices[0].split()[0]
            print(f"デバイス発見: {device}")
            return device
        
        print(f"複数のデバイスが見つかりました:")
        for i, device in enumerate(devices, 1):
            print(f"  {i}. {device.split()[0]}")
        print("--device オプションでデバイスを指定してください")
        return None

    def deploy_efficient(self, device: str) -> bool:
        """効率的なデプロイ処理（mpremote内蔵のSHA256比較を活用）"""
        output_path = Path(self.output_dir)
        
        if not output_path.exists():
            print(f"エラー: 出力ディレクトリが見つかりません: {self.output_dir}")
            print(f"ヒント: 先にbuildコマンドを実行して {self.output_dir}/ を作成してください")
            return False
        
        # ファイル数カウント
        local_files = list(output_path.rglob('*'))
        file_count = sum(1 for f in local_files if f.is_file())
        
        if file_count == 0:
            print("エラー: デプロイするファイルがありません")
            return False
        
        print(f"デプロイ対象: {file_count} ファイル")
        
        # デプロイ戦略選択
        deploy_config = self.config.get('deploy', {})
        clean_deploy = deploy_config.get('clean_deploy', False)
        custom_clean = deploy_config.get('custom_clean', [])
        
        if self.dry_run:
            print(f"\n[DRY RUN] 以下のコマンドが実行される予定です:")
            cmd_preview = f"mpremote connect {device}"
            if custom_clean:
                for file_to_remove in custom_clean:
                    cmd_preview += f" + fs rm {file_to_remove}"
            cmd_preview += f" + fs cp -r {self.output_dir}/ :/"
            if deploy_config.get('auto_reset', True):
                cmd_preview += " + soft-reset"
            print(f"  {cmd_preview}")
            print(f"\n注意: mpremoteが自動的にSHA256を比較し、同じファイルはスキップします")
            if custom_clean:
                print(f"カスタムクリーン: {len(custom_clean)} ファイル削除予定 ({', '.join(custom_clean)})")
            return True
        
        # コマンド構築
        cmd_parts = ["connect", device]
        
        # カスタムクリーン（特定ファイルの削除）
        if custom_clean:
            print(f"カスタムクリーン実行: {len(custom_clean)} ファイル削除予定")
            for file_to_remove in custom_clean:
                cmd_parts.extend(["+", "fs", "rm", file_to_remove])
        
        # 再帰的コピー（mpremoteがSHA256比較して差分のみ転送）
        cmd_parts.extend(["+", "fs", "cp", "-r", f"{self.output_dir}/", ":/"])
        
        # オプション：自動ソフトリセット
        if deploy_config.get('auto_reset', True):
            cmd_parts.extend(["+", "soft-reset"])
        
        print(f"\n効率的デプロイ実行中...")
        print(f"コマンド: mpremote {' '.join(cmd_parts)}")
        
        success, output = self.run_mpremote(cmd_parts)
        
        if success:
            # 出力から転送情報を抽出して表示
            if output:
                lines = output.split('\n')
                copied_files = [line for line in lines if 'cp' in line or 'skip' in line]
                if copied_files:
                    print(f"\n転送結果:")
                    for line in copied_files[:10]:  # 最初の10行のみ表示
                        print(f"  {line}")
                    if len(copied_files) > 10:
                        print(f"  ... 他 {len(copied_files) - 10} ファイル")
            
            print(f"\n✅ デプロイ成功！")
            return True
        else:
            print(f"\n❌ デプロイ失敗: {output}")
            return False

    def deploy(self) -> bool:
        """デプロイ処理（効率化版）"""
        print(f"=== デプロイ処理開始 ===")
        print(f"ソース: {self.output_dir}")
        print(f"モード: 効率的デプロイ (mpremote内蔵SHA256比較)")
        
        # WebREPL使用時の処理
        if self.use_webrepl:
            print(f"WebREPL モード: {self.webrepl_host}:{self.webrepl_port}")
            print("警告: WebREPL機能は現在未実装です。mpremoteモードを使用してください。")
            return False
        
        # デバイス選択
        device = self.auto_select_device()
        if not device:
            return False
        
        # 効率的デプロイ実行
        success = self.deploy_efficient(device)
        
        if success:
            print(f"\n=== デプロイ処理完了 ===")
        else:
            print(f"\n=== デプロイ処理失敗 ===")
        
        return success

    def build_and_deploy(self) -> bool:
        """ビルド + デプロイの統合処理"""
        print("MicroPython 統合ビルド・デプロイツール")
        print("=" * 60)
        
        # ビルド実行
        if not self.build():
            print("エラー: ビルド処理に失敗しました。デプロイを中止します。")
            return False
        
        print("\n" + "=" * 60)
        
        # デプロイ実行
        if not self.deploy():
            print("エラー: デプロイ処理に失敗しました。")
            return False
        
        print("\n" + "=" * 60)
        if self.dry_run:
            print("統合ドライラン完了！実際の処理は --dry-run なしで実行してください")
        else:
            print("統合ビルド・デプロイ完了！")
        
        return True


def main():
    """メイン関数"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='MicroPython 統合ビルド・デプロイツール',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
使用例:
  python3 mpy_unified.py                      # ビルド + デプロイ
  python3 mpy_unified.py build                # ビルドのみ
  python3 mpy_unified.py deploy               # デプロイのみ
  python3 mpy_unified.py --dry-run            # 全処理の事前確認
  python3 mpy_unified.py build --dry-run      # ビルドの事前確認
        '''
    )
    
    parser.add_argument(
        'command',
        nargs='?',
        choices=['build', 'deploy'],
        help='実行するコマンド (省略時は build + deploy を実行)'
    )
    parser.add_argument(
        '--config', '-c',
        help='設定ファイルのパス (デフォルト: prepare.json を自動探索)'
    )
    parser.add_argument(
        '--src-dir', default='src',
        help='ソースディレクトリ (デフォルト: src)'
    )
    parser.add_argument(
        '--output-dir', '-o', default='mpy_xtensa',
        help='出力ディレクトリ (デフォルト: mpy_xtensa)'
    )
    parser.add_argument(
        '--device', '-d',
        help='ESP32デバイスポート (例: /dev/ttyACM0)'
    )
    parser.add_argument(
        '--dry-run', '-n',
        action='store_true',
        help='実際の処理を行わず、予定される処理内容のみを表示'
    )
    parser.add_argument(
        '--webrepl', '-w',
        action='store_true',
        help='WebREPL経由でファイル転送'
    )
    parser.add_argument(
        '--preserve-dirs', action='store_true',
        help='出力時にサブディレクトリ構造を保持する'
    )
    
    args = parser.parse_args()
    
    try:
        tool = MicroPythonBuildDeployTool(
            config_file=args.config,
            src_dir=args.src_dir,
            output_dir=args.output_dir,
            device=args.device,
            dry_run=args.dry_run,
            use_webrepl=args.webrepl,
            preserve_dirs=args.preserve_dirs
        )
        
        success = False
        
        if args.command == 'build':
            success = tool.build()
        elif args.command == 'deploy':
            success = tool.deploy()
        else:
            # デフォルト: ビルド + デプロイ
            success = tool.build_and_deploy()
        
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\n\n操作がキャンセルされました")
        sys.exit(1)
    except Exception as e:
        print(f"\n予期しないエラー: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()