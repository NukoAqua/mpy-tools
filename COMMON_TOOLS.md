# Common Tools Assessment

## Candidates for Submodule (Reusable)
- `prepare.py` + `prepare.json`: Config-driven bundling (copy/compile) suitable for reuse with minor tweaks.
- `deploy.py`: USB/WebREPL deploy flow is broadly reusable with generic defaults.
- `webrepl_cli.py`: Standalone MicroPython WebREPL client; ready as-is.
- `update_version.py`: Generic version/hash management for `src/`; small CLI improvements suggested.

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
