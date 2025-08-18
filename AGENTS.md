# Repository Guidelines

## Project Structure & Module Organization
- Root scripts: `prepare.py` (bundle/compile), `deploy.py` (device deploy), `update_version.py` (module versioning).
- Config: `prepare.json` controls copy/compile lists and submodules.
- Outputs: `mpy_xtensa/` (generated .mpy and `version.json`), created by `prepare.py`.
- Expected sources: `src/` in this repo and/or configured submodules (see `prepare.json`).

## Build, Test, and Development Commands
- Create env: `python -m venv .venv && source .venv/bin/activate`.
- Install tools: `pip install mpy-cross mpremote python-dotenv` (or `uv pip install ...`).
- Dry-run bundle: `python3 prepare.py -n` — validate config and show planned actions.
- Build bundle: `python3 prepare.py` — copies/compiles into `mpy_xtensa/` and writes `src/version.json`.
- Status/Clean: `python3 prepare.py status` / `python3 prepare.py clean`.
- Deploy (USB): `python3 deploy.py --source mpy_xtensa` (add `--dry-run` first; `--device` optional).
- Deploy (WebREPL): `python3 deploy.py -w --source mpy_xtensa` (requires `.env`).
- Version scan: `python3 update_version.py` — bumps `__version__` and updates `src/version.json` by hash.

## Coding Style & Naming Conventions
- Python 3.11+, 4-space indentation, PEP 8.
- Names: `snake_case` for functions/variables, `CamelCase` for classes, constants UPPER_CASE.
- Prefer type hints and docstrings; keep functions small and CLI-friendly.

## Testing Guidelines
- No test suite in this repo. Use `--dry-run` modes (`prepare.py`, `deploy.py`) to verify changes.
- Validate outputs: check `mpy_xtensa/` contents and hashes in `version.json`.
- For device tests, run deploy with `--dry-run` first, then actual deploy and confirm boot via serial/`mpremote`.

## Commit & Pull Request Guidelines
- Commits: concise, imperative, scoped; English or Japanese acceptable (e.g., "Add recursive deploy", "COMMON_TOOLS.md を更新").
- PRs: clear description, rationale, and usage notes. Include command examples and dry-run output; link issues when relevant.

## Security & Configuration Tips
- Do not commit secrets. `.env` is ignored; set `WEBREPL_HOST`, `WEBREPL_PORT`, `WEBREPL_PASSWORD` for WebREPL.
- Ensure `mpy-cross`/`mpremote` come from trusted sources; verify device ports before deploying.
