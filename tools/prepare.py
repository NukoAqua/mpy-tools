#!/usr/bin/env python3
"""
MicroPython 統合準備スクリプト
設定とサブモジュールからファイルを集約し、出力ディレクトリに配置します。
`boot.py`/`main.py`はコピー、その他は`mpy-cross`でコンパイルします。
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

def parse_arch_from_command(command: str) -> str | None:
    """mpy-crossコマンドラインから -march=<arch> を抽出"""
    if not command:
        return None
    m = re.search(r"-march=([A-Za-z0-9_]+)", command)
    return m.group(1) if m else None

def load_config(config_file: str | None = None):
    """設定ファイルを読み込み。明示パスが無い場合は候補から探索"""
    candidates = []
    if config_file:
        candidates.append(config_file)
    # Fallback search paths
    candidates.extend([
        "prepare.json",
        "src/prepare.json",
    ])
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

def find_file_in_submodules(filename, submodules):
    """サブモジュール内でファイルを検索"""
    for submodule in submodules:
        submodule_path = Path(submodule) / "src" / filename
        if submodule_path.exists():
            print(f"  サブモジュールで発見: {submodule_path}")
            return submodule_path
    return None

def collect_module_versions(src_dir="src", module_list=None, copy_only_list=None, submodules=None):
    """srcフォルダとサブモジュールからバージョン情報とSHA-256ハッシュを収集"""
    versions = {}
    hashes = {}
    src_path = Path(src_dir)
    
    print(f"モジュールのバージョン情報とハッシュを収集中...")
    
    all_files = []
    if module_list:
        all_files.extend(module_list)
    if copy_only_list:
        all_files.extend(copy_only_list)
    
    for filename in all_files:
        # まずsrc/ディレクトリで検索
        file_path = src_path / filename
        
        # src/にない場合はサブモジュールで検索
        if not file_path.exists() and submodules:
            file_path = find_file_in_submodules(filename, submodules)
            if not file_path:
                print(f"  警告: {filename} が見つかりません - スキップします")
                continue
        elif not file_path.exists():
            print(f"  警告: {filename} が見つかりません - スキップします")
            continue
        
        try:
            # ファイル内容を読み込み
            with open(file_path, 'rb') as f:
                file_bytes = f.read()
            
            # SHA-256ハッシュを計算
            sha256_hash = hashlib.sha256(file_bytes).hexdigest()
            hashes[filename] = sha256_hash
            
            # テキストとして再読み込みしてバージョン情報を取得
            content = file_bytes.decode('utf-8')
            
            # __version__ = "x.x.x" または __version__ = const("x.x.x") の形式を検索
            version_patterns = [
                r'__version__\s*=\s*["\']([^"\']+)["\']',  # 通常の文字列
                r'__version__\s*=\s*const\s*\(\s*["\']([^"\']+)["\']\s*\)'  # const()関数
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

def create_version_json(versions, hashes, src_dir="src", dry_run=False):
    """収集したバージョン情報とハッシュをversion.jsonファイルとして保存"""
    if dry_run:
        print(f"[DRY RUN] version.json作成予定: {Path(src_dir) / 'version.json'}")
        print(f"[予定] 総モジュール数: {len(versions)}")
        versioned_modules = sum(1 for v in versions.values() if v not in ["unknown", "error"])
        print(f"[予定] バージョン情報あり: {versioned_modules}")
        return True
    
    version_data = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "description": "PaquaAutoDrain + ESP32s3base unified modules",
        "source_directory": src_dir,
        "format": "py",
        "architecture": "source",
        "modules": versions,
        "SHA-256": hashes
    }
    
    version_file = Path(src_dir) / "version.json"
    
    try:
        with open(version_file, 'w', encoding='utf-8') as f:
            json.dump(version_data, f, indent=2, ensure_ascii=False)
        
        print(f"version.jsonを作成しました: {version_file}")
        print(f"  総モジュール数: {len(versions)}")
        
        # バージョン情報があるモジュール数をカウント
        versioned_modules = sum(1 for v in versions.values() if v not in ["unknown", "error"])
        print(f"  バージョン情報あり: {versioned_modules}")
        
        return True
        
    except Exception as e:
        print(f"エラー: version.json作成中にエラー: {e}")
        return False

def check_mpy_cross():
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
        print("  または MicroPython ツールチェーンをインストールしてください")
        return False

def create_device_src_dir(device_src_dir="mpy_xtensa", dry_run=False):
    """出力ディレクトリを作成"""
    device_src_path = Path(device_src_dir)
    
    if dry_run:
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

def copy_only_files(copy_only_list, submodules=None, src_dir="src", device_src_dir="mpy_xtensa", dry_run=False, preserve_dirs=False):
    """指定されたファイルをそのままコピー（プリコンパイルしない）"""
    src_path = Path(src_dir)
    device_src_path = Path(device_src_dir)
    
    if dry_run:
        print(f"\n[DRY RUN] コピーのみファイル処理予定...")
    else:
        print(f"\nコピーのみファイルを処理中...")
    
    results = []
    
    for filename in copy_only_list:
        # まずsrc/ディレクトリで検索
        file_path = src_path / filename
        
        # src/にない場合はサブモジュールで検索
        if not file_path.exists() and submodules:
            file_path = find_file_in_submodules(filename, submodules)
            if not file_path:
                print(f"  警告: {filename} が見つかりません - スキップします")
                results.append({'file': filename, 'success': False})
                continue
        elif not file_path.exists():
            print(f"  警告: {filename} が見つかりません - スキップします")
            results.append({'file': filename, 'success': False})
            continue
        
        try:
            # ファイルサイズ取得
            original_size = file_path.stat().st_size
            
            # 出力先パス
            dest_path = device_src_path / filename if not preserve_dirs else device_src_path / Path(filename)
            if preserve_dirs and not dry_run:
                dest_path.parent.mkdir(parents=True, exist_ok=True)
            
            if dry_run:
                print(f"  [予定] コピー: {file_path} -> {dest_path} ({original_size} bytes)")
                results.append({'file': filename, 'success': True})
            else:
                shutil.copy2(file_path, dest_path)
                print(f"  コピー: {file_path} -> {dest_path} ({original_size} bytes)")
                results.append({'file': filename, 'success': True})
            
        except Exception as e:
            if dry_run:
                print(f"  [予定] コピー: {file_path} -> {dest_path} ({original_size} bytes)")
                results.append({'file': filename, 'success': True})
            else:
                print(f"  エラー: {filename} のコピーに失敗: {e}")
                results.append({'file': filename, 'success': False})
    
    return results

def compile_module(filename, command, submodules=None, src_dir="src", device_src_dir="mpy_xtensa", dry_run=False, preserve_dirs=False):
    """単一モジュールをコンパイルして出力ディレクトリに配置"""
    src_path = Path(src_dir)
    
    # まずsrc/ディレクトリで検索
    file_path = src_path / filename
    
    # src/にない場合はサブモジュールで検索
    if not file_path.exists() and submodules:
        file_path = find_file_in_submodules(filename, submodules)
        if not file_path:
            print(f"  警告: {filename} が見つかりません - スキップします")
            return False
    elif not file_path.exists():
        print(f"  警告: {filename} が見つかりません - スキップします")
        return False
    
    if dry_run:
        print(f"  [予定] コンパイル: {filename}")
    else:
        print(f"  コンパイル中: {filename}")
    
    # ファイルサイズ取得（コンパイル前）
    original_size = file_path.stat().st_size
    
    if dry_run:
        # ドライランでは仮の圧縮率を表示
        estimated_compressed_size = int(original_size * 0.7)  # 概算30%削減
        compression_ratio = (1 - estimated_compressed_size / original_size) * 100
        device_mpy_path = (Path(device_src_dir) / f"{Path(filename).stem}.mpy") if not preserve_dirs else (Path(device_src_dir) / Path(filename).with_suffix('.mpy'))
        
        print(f"    [予定] 成功: {original_size} bytes -> {estimated_compressed_size} bytes "
              f"({compression_ratio:.1f}% 削減 - 推定)")
        print(f"    [予定] 配置: {device_mpy_path}")
        return True
    
    # 一時的にファイルの親ディレクトリでコンパイル
    temp_mpy_path = file_path.parent / f"{Path(filename).stem}.mpy"
    
    # mpy-crossコマンド実行
    cmd = command.strip().split() + [str(file_path)]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        # コンパイル結果の確認
        if temp_mpy_path.exists():
            compiled_size = temp_mpy_path.stat().st_size
            compression_ratio = (1 - compiled_size / original_size) * 100
            
            # 出力先パス
            device_mpy_path = (Path(device_src_dir) / f"{Path(filename).stem}.mpy") if not preserve_dirs else (Path(device_src_dir) / Path(filename).with_suffix('.mpy'))
            if preserve_dirs:
                device_mpy_path.parent.mkdir(parents=True, exist_ok=True)
            
            # .mpyファイルをmpy_xtensaに移動
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

def create_device_version_json(src_dir="src", device_src_dir="mpy_xtensa", dry_run=False, architecture: str | None = None):
    """出力ディレクトリ用のversion.jsonを作成（mpyファイルのSHA-256ハッシュを計算）"""
    version_file = Path(device_src_dir) / "version.json"
    device_src_path = Path(device_src_dir)
    
    if dry_run:
        print(f"[DRY RUN] 出力用version.json作成予定: {version_file}")
        return
    
    # 元のversion.jsonを読み込み
    try:
        with open(Path(src_dir) / "version.json", "r") as f:
            version_data = json.load(f)
        
        # 出力用に更新
        version_data["compiled_at"] = datetime.now().isoformat(timespec="seconds")
        version_data["format"] = "mpy"
        if architecture:
            version_data["architecture"] = architecture
        version_data["optimization"] = "O2"
        
        # 実際に存在するファイルを基にモジュール情報を再構築
        new_modules = {}
        new_hashes = {}
        
        print(f"統合ファイルのハッシュを計算中...")
        
        # 出力ディレクトリ内の全ファイルをスキャン
        for file_path in device_src_path.rglob('*'):
            if file_path.is_file():
                relative_path = file_path.relative_to(device_src_path)
                filename = str(relative_path)
                
                # ファイルのSHA-256ハッシュを計算
                try:
                    with open(file_path, 'rb') as f:
                        file_bytes = f.read()
                    file_hash = hashlib.sha256(file_bytes).hexdigest()
                    new_hashes[filename] = file_hash
                    
                    # バージョン情報は元の情報から引き継ぎ（拡張子変換）
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
        
        # 出力用 version.json に保存
        with open(version_file, "w") as f:
            json.dump(version_data, f, indent=2, ensure_ascii=False)
        
        print(f"出力用version.jsonを作成: {version_file}")
        print(f"  統合ファイル数: {len(new_modules)}")
        print(f"  ハッシュ計算済み: {len([h for h in new_hashes.values() if h not in ['error', 'missing']])}")
        
    except FileNotFoundError:
        print(f"警告: {Path(src_dir) / 'version.json'} が見つかりません")
    except Exception as e:
        print(f"エラー: version.json作成中にエラー: {e}")

def clean_device_src(device_src_dir="mpy_xtensa", dry_run=False):
    """出力ディレクトリを削除"""
    device_src_path = Path(device_src_dir)
    
    if dry_run:
        if device_src_path.exists():
            print(f"[DRY RUN] 出力ディレクトリ削除予定: {device_src_path}")
        else:
            print("[DRY RUN] 出力ディレクトリは存在しません（削除不要）")
        return
    
    if device_src_path.exists():
        shutil.rmtree(device_src_path)
        print(f"出力ディレクトリを削除しました: {device_src_path}")
    else:
        print("出力ディレクトリは存在しません")

def show_summary(copy_results, compile_results, device_src_dir="mpy_xtensa", dry_run=False):
    """処理結果のサマリーを表示"""
    total_copy = len(copy_results)
    success_copy = sum(1 for r in copy_results if r['success'])
    failed_copy = total_copy - success_copy
    
    total_compile = len(compile_results)
    success_compile = sum(1 for r in compile_results if r['success'])
    failed_compile = total_compile - success_compile
    
    print(f"\n=== 処理結果 ===")
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
    
    # device_srcディレクトリの内容表示
    device_src_path = Path(device_src_dir)
    if device_src_path.exists():
        mpy_files = list(device_src_path.rglob('*.mpy'))
        other_files = [f for f in device_src_path.rglob('*') if f.is_file() and not f.name.endswith('.mpy')]
        
        print(f"\n=== 出力ディレクトリ ===")
        print(f"mpyファイル: {len(mpy_files)} 個")
        print(f"その他ファイル: {len(other_files)} 個")
        print(f"場所: {device_src_path.absolute()}")

def show_usage():
    """使用方法を表示"""
    print("使用方法:")
    print(f"  {sys.argv[0]}                 - 統合処理実行")
    print(f"  {sys.argv[0]} clean           - 出力ディレクトリを削除")
    print(f"  {sys.argv[0]} status          - 現在の状態を表示")

def show_status(src_dir="src", device_src_dir="mpy_xtensa"):
    """現在の状態を表示"""
    print("=== ステータス ===")
    
    # srcディレクトリの状態
    src_path = Path(src_dir)
    if src_path.exists():
        py_files = list(src_path.rglob('*.py'))
        print(f"{src_dir}/ 内の.pyファイル: {len(py_files)} 個")
    else:
        print("srcディレクトリが見つかりません")
    
    # prepare.jsonから設定を読み込んでサブモジュール状態を表示
    config = load_config()
    if config and config.get('submodules'):
        for submodule in config['submodules']:
            submodule_path = Path(submodule) / "src"
            if submodule_path.exists():
                submodule_py_files = list(submodule_path.glob('*.py'))
                print(f"{submodule}/src/内の.pyファイル: {len(submodule_py_files)} 個")
            else:
                print(f"{submodule}サブモジュールが見つかりません")
    else:
        print("サブモジュール設定がありません")
    
    # 出力ディレクトリの状態
    device_src_path = Path(device_src_dir)
    if device_src_path.exists():
        mpy_files = list(device_src_path.rglob('*.mpy'))
        other_files = [f for f in device_src_path.rglob('*') if f.is_file() and not f.name.endswith('.mpy')]
        print(f"{device_src_dir}/ 内の.mpyファイル: {len(mpy_files)} 個")
        print(f"{device_src_dir}/ 内のその他ファイル: {len(other_files)} 個")
    else:
        print("出力ディレクトリは存在しません")

def main():
    """メイン処理"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='MicroPython バンドル準備ツール',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
使用例:
  python3 prepare.py                      # 統合処理実行
  python3 prepare.py --dry-run            # 処理内容の事前確認
  python3 prepare.py clean                # 出力ディレクトリ削除
  python3 prepare.py status               # 現在の状態表示
        '''
    )
    
    parser.add_argument(
        'command',
        nargs='?',
        choices=['clean', 'status'],
        help='実行するコマンド (clean: ディレクトリ削除, status: 状態表示)'
    )
    parser.add_argument(
        '--dry-run', '-n',
        action='store_true',
        help='実際の処理を行わず、予定される処理内容のみを表示'
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
        '--preserve-dirs', action='store_true',
        help='出力時にサブディレクトリ構造を保持する'
    )
    
    args = parser.parse_args()
    
    print("MicroPython バンドル準備ツール")
    print("=" * 45)
    
    # コマンド処理
    if args.command == "clean":
        clean_device_src(dry_run=args.dry_run)
        return
    elif args.command == "status":
        show_status(src_dir=args.src_dir, device_src_dir=args.output_dir)
        return
    
    # 設定読み込み
    config = load_config(args.config)
    if not config:
        return
    arch = parse_arch_from_command(config.get('command', ''))
    if arch:
        print(f"検出されたアーキテクチャ: {arch}")
        # デフォルト出力名が xtensa の場合のみ自動補正
        if args.output_dir == 'mpy_xtensa' and arch != 'xtensa':
            auto_out = f"mpy_{arch}"
            print(f"出力ディレクトリを自動調整: {args.output_dir} -> {auto_out}")
            args.output_dir = auto_out
    
    # mpy-crossの確認
    if args.dry_run:
        print(f"\n[DRY RUN] mpy-cross確認をスキップ")
    elif not check_mpy_cross():
        return
    
    # src/version.json作成（処理前）
    print(f"\n=== {args.src_dir}/version.json作成 ===")
    if args.dry_run:
        print(f"[DRY RUN] モジュールのバージョン情報とハッシュ収集予定")
        # ドライランでも設定ファイルから情報は取得
        module_versions, module_hashes = collect_module_versions(
            args.src_dir, 
            config.get('modules', []), 
            config.get('copy_only', []),
            config.get('submodules', [])
        )
        create_version_json(module_versions, module_hashes, args.src_dir, dry_run=True)
    else:
        module_versions, module_hashes = collect_module_versions(
            args.src_dir, 
            config.get('modules', []), 
            config.get('copy_only', []),
            config.get('submodules', [])
        )
        if not create_version_json(module_versions, module_hashes, args.src_dir):
            print(f"警告: {args.src_dir}/version.json作成に失敗しました")
    
    # mpy_xtensaディレクトリ作成
    device_src_path = create_device_src_dir(device_src_dir=args.output_dir, dry_run=args.dry_run)
    
    # コピーのみファイルの処理
    copy_results = []
    if config.get('copy_only'):
        copy_results = copy_only_files(
            config['copy_only'], 
            config.get('submodules', []),
            src_dir=args.src_dir,
            device_src_dir=args.output_dir,
            dry_run=args.dry_run,
            preserve_dirs=args.preserve_dirs
        )
    
    # コンパイル実行
    compile_results = []
    if config.get('modules'):
        if args.dry_run:
            print(f"\n[DRY RUN] コンパイル予定...")
        else:
            print(f"\nコンパイル開始...")
        print(f"コマンド: {config['command']}")
        print(f"対象モジュール: {len(config['modules'])} 個")
        print(f"出力先: {args.output_dir}/")
        
        for module in config['modules']:
            success = compile_module(
                module,
                config['command'],
                config.get('submodules', []),
                src_dir=args.src_dir,
                device_src_dir=args.output_dir,
                dry_run=args.dry_run,
                preserve_dirs=args.preserve_dirs
            )
            compile_results.append({'module': module, 'success': success})
    
    # mpy_xtensa用version.json作成
    create_device_version_json(src_dir=args.src_dir, device_src_dir=args.output_dir, dry_run=args.dry_run, architecture=arch)
    
    # 結果表示
    show_summary(copy_results, compile_results, device_src_dir=args.output_dir, dry_run=args.dry_run)
    
    # 使用方法の説明
    if args.dry_run:
        print(f"\n=== 次のステップ [DRY RUN] ===")
        print(f"実際の処理実行: python3 {sys.argv[0]}")
        print(f"ステータス確認: python3 {sys.argv[0]} status")
        print(f"ESP32 へ転送: deploy.py で {args.output_dir}/ をデプロイ")
    else:
        print(f"\n=== 使用方法 ===")
        print(f"ステータス確認: python3 {sys.argv[0]} status")
        print(f"出力削除: python3 {sys.argv[0]} clean")
        print(f"ESP32 へ転送: {args.output_dir}/ 内のファイルをデバイスにアップロード")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n中断されました")
        sys.exit(1)
    except Exception as e:
        print(f"\n予期しないエラーが発生しました: {e}")
        sys.exit(1)
