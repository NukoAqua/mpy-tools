# Common Tools Assessment

## Candidates for Submodule (Reusable)
- `tools/prepare.py` + `src/prepare.json`: Config-driven bundling (copy/compile) suitable for reuse with minor tweaks.
- `tools/deploy.py`: USB/WebREPL deploy flow is broadly reusable with generic defaults.
- `tools/webrepl_cli.py`: Standalone MicroPython WebREPL client; ready as-is.
- `tools/update_version.py`: Generic version/hash management for `src/`; small CLI improvements suggested.

## Project-Local (Refactor Before Reuse)
- `tools/debug_monitor.py`, `tools/start_debug.sh`, `tools/DEBUG_MONITOR_README.md`, `tools/debug_config.json`: Branded and Paqua-specific (hosts, paths, commands). Could be made generic via config/plugins.
- `tools/test_phase25_commands.py`: Protocol/command set tied to this project.

## Per-Tool Findings & Fixes
- `prepare.py`
  - Hard-coded dates → use `datetime.now().isoformat()`.
  - Fixed output dir `mpy_xtensa/` → add `--output-dir`/config `output_dir`.
  - Flattens directories → add `preserve_dirs: true` option.
  - Fixed config path `src/prepare.json` → add `--config`.
- `deploy.py`
  - Brand/defaults: host `PaquaAutoDrain.local`, banner strings → replace with neutral defaults; require explicit host via env or args.
  - Only top-level files copied → walk recursively and create remote subdirs.
  - Device discovery matches “Espressif Device” → also accept `/dev/ttyUSB*`/`/dev/ttyACM*` or encourage `--device`.
- `update_version.py`
  - Fixed `src`/`version.json` paths → add `--src`, `--version-file`.
  - Bump policy fixed to minor → add `--bump {patch,minor,major}`.
- `webrepl_cli.py`
  - Generic; consider adding README/examples only.
- `debug_monitor.py`
  - Title/branding hard-coded → parameterize via config.
  - Defaults for `syslog_server`, `syslog_path`, `rest_api_base` → move to config with neutral defaults.
  - `DEBUG_COMMANDS` is project-specific → load from external JSON or plugin module path.
- `start_debug.sh`
  - Hard-coded server/banner → read from config; keep generic messaging.
  - Ship `.example` config; don’t commit real endpoints.
- Vendor folders
  - `tools/micropython*`, `tools/mpy-cross*` → exclude from submodule; document install/build instead.

## Proposed Submodule Layout
- `mpy-tools/`
  - `bundle/prepare.py`, `bundle/prepare.example.json`
  - `deploy/deploy.py`, `deploy/webrepl_cli.py`
  - `versioning/update_version.py`
  - `debug/debug_monitor.py` (after plugin-izing), `debug/start_debug.sh`, `debug/debug_config.example.json`
  - `README.md` with `uv`, `mpremote`, `mpy-cross` setup

## Actionable Changes (Summary)
- Replace hard-coded dates; parameterize paths/options.
- Add CLI flags noted above; support recursive deploy.
- Externalize branding, hosts, paths, and command maps to config/plugins.
- Provide `.example` configs; remove vendor binaries from the submodule.

## Next Steps
- Option A: Extract generic parts into `tools/common/` here and refactor incrementally.
- Option B: Create a standalone `mpy-tools` repo, move the generic tools, then add it here as a Git submodule.
