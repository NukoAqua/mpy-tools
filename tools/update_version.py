#!/usr/bin/env python3
"""
Version management script for MicroPython projects

Updates version.json and increments __version__ in Python modules
when file changes are detected via SHA-256 hash comparison.

Usage:
    python3 update_version.py [--src src] [--version-file src/version.json] [--bump patch|minor|major]
"""

__version__ = "0.3.0"

import json
import hashlib
import os
import re
from datetime import date
import argparse
from pathlib import Path


def calculate_sha256(file_path):
    """Calculate SHA-256 hash of a file"""
    hash_sha256 = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    except Exception as e:
        print(f"Error calculating hash for {file_path}: {e}")
        return None


def increment_version(version_str, policy: str = 'minor'):
    """Increment version by policy: patch/minor/major"""
    try:
        parts = version_str.split('.')
        if len(parts) == 3:
            major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])
            if policy == 'patch':
                patch += 1
            elif policy == 'major':
                major += 1
                minor = 0
                patch = 0
            else:  # minor
                minor += 1
                # keep patch
            return f"{major}.{minor}.{patch}"
        else:
            # Handle non-standard version formats
            return version_str
    except ValueError:
        print(f"Warning: Could not parse version string: {version_str}")
        return version_str


def update_file_version(file_path, new_version):
    """Update __version__ in a Python file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Pattern to match __version__ = const("x.x.x") or __version__ = "x.x.x"
        pattern = r'(__version__\s*=\s*(?:const\s*\()?["\'])([^"\']+)(["\'](?:\s*\))?)'
        
        def replace_version(match):
            prefix = match.group(1)
            old_version = match.group(2)
            suffix = match.group(3)
            return f"{prefix}{new_version}{suffix}"
        
        new_content = re.sub(pattern, replace_version, content)
        
        if new_content != content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f"Updated {file_path}: version -> {new_version}")
            return True
        else:
            print(f"Warning: Could not find __version__ pattern in {file_path}")
            return False
            
    except Exception as e:
        print(f"Error updating version in {file_path}: {e}")
        return False


def get_current_version_from_file(file_path):
    """Extract current __version__ from a Python file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Pattern to match __version__ = const("x.x.x") or __version__ = "x.x.x"
        pattern = r'__version__\s*=\s*(?:const\s*\()?["\']([^"\']+)["\'](?:\s*\))?'
        match = re.search(pattern, content)
        
        if match:
            return match.group(1)
        else:
            # Default version for files without __version__
            return "0.1.0"
            
    except Exception as e:
        print(f"Error reading version from {file_path}: {e}")
        return "0.1.0"


def scan_python_files(src_dir):
    """Scan for all Python files in src directory"""
    python_files = []
    src_path = Path(src_dir)
    
    for file_path in src_path.rglob("*.py"):
        # Get relative path from src directory (not including "src/")
        rel_path = file_path.relative_to(src_path)
        python_files.append(str(rel_path))
    
    return python_files


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='MicroPython version manager')
    parser.add_argument('--src', default='src', help='Source directory to scan (default: src)')
    parser.add_argument('--version-file', default=None, help='Path to version.json (default: <src>/version.json)')
    parser.add_argument('--bump', choices=['patch','minor','major'], default='minor', help='Version bump policy (default: minor)')
    args = parser.parse_args()

    src_dir = args.src
    version_file = args.version_file or os.path.join(src_dir, "version.json")
    
    print("ESP32-S3 Version Management Script")
    print("=" * 40)
    
    # Check if src directory exists
    if not os.path.exists(src_dir):
        print(f"Error: {src_dir} directory not found!")
        return
    
    # Load existing version.json
    version_data = {}
    if os.path.exists(version_file):
        try:
            with open(version_file, 'r', encoding='utf-8') as f:
                version_data = json.load(f)
            print(f"Loaded existing {version_file}")
        except Exception as e:
            print(f"Error loading {version_file}: {e}")
            print("Creating new version.json...")
    else:
        print(f"{version_file} not found, creating new one...")
    
    # Initialize version.json structure if needed
    if not version_data:
        version_data = {
            "generated_at": str(date.today()),
            "description": "ESP32-S3 MicroPython modules version information",
            "source_directory": "src",
            "format": "py",
            "architecture": "source",
            "modules": {},
            "SHA-256": {}
        }
    
    # Update generated_at
    version_data["generated_at"] = str(date.today())
    
    # Scan for Python files
    current_files = scan_python_files(src_dir)
    print(f"Found {len(current_files)} Python files in {src_dir}/")
    
    # Track changes
    updated_files = []
    new_files = []
    
    # Check each current file
    for file_path in current_files:
        full_path = os.path.join(src_dir, file_path)
        current_hash = calculate_sha256(full_path)
        
        if current_hash is None:
            continue
        
        # Check if file is new or changed
        if file_path not in version_data["SHA-256"]:
            # New file
            current_version = get_current_version_from_file(full_path)
            version_data["modules"][file_path] = current_version
            version_data["SHA-256"][file_path] = current_hash
            new_files.append(file_path)
            print(f"NEW FILE: {file_path} (version: {current_version})")
            
        elif version_data["SHA-256"][file_path] != current_hash:
            # File changed
            old_version = version_data["modules"].get(file_path, "0.1.0")
            new_version = increment_version(old_version, args.bump)
            
            # Update __version__ in the file
            if update_file_version(full_path, new_version):
                # Recalculate hash after version update
                updated_hash = calculate_sha256(full_path)
                version_data["modules"][file_path] = new_version
                version_data["SHA-256"][file_path] = updated_hash
                updated_files.append((file_path, old_version, new_version))
                print(f"UPDATED: {file_path} ({old_version} -> {new_version})")
            else:
                # If version update failed, just update hash
                version_data["SHA-256"][file_path] = current_hash
                print(f"HASH UPDATED: {file_path} (version update failed)")
    
    # Check for missing files
    missing_files = []
    for file_path in list(version_data["SHA-256"].keys()):
        if file_path not in current_files:
            missing_files.append(file_path)
    
    # Report missing files
    if missing_files:
        print("\nMISSING FILES:")
        print("The following files are listed in version.json but not found in src/:")
        for file_path in missing_files:
            print(f"  - {file_path}")
        print("Consider removing these entries from version.json manually.")
    
    # Save updated version.json
    try:
        with open(version_file, 'w', encoding='utf-8') as f:
            json.dump(version_data, f, indent=2, ensure_ascii=False)
        print(f"\nSaved updated {version_file}")
    except Exception as e:
        print(f"Error saving {version_file}: {e}")
        return
    
    # Summary
    print("\nSUMMARY:")
    print(f"  Total files: {len(current_files)}")
    print(f"  New files: {len(new_files)}")
    print(f"  Updated files: {len(updated_files)}")
    print(f"  Missing files: {len(missing_files)}")
    
    if updated_files:
        print("\nVersion increments:")
        for file_path, old_ver, new_ver in updated_files:
            print(f"  {file_path}: {old_ver} -> {new_ver}")
    
    print("\nVersion management completed!")


if __name__ == "__main__":
    main()
