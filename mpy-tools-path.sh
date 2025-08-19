#!/usr/bin/env bash
# Add mpy-tools/tools to PATH for this shell session.
# Usage: source path/to/mpy-tools-path.sh

# Require Bash when sourced
if [ -z "${BASH_SOURCE[0]:-}" ]; then
  echo "Please source this script with bash." >&2
  return 1 2>/dev/null || exit 1
fi

# Resolve this repo's tools directory relative to this script
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
MPY_TOOLS_DIR="${SCRIPT_DIR}/tools"

if [ ! -d "${MPY_TOOLS_DIR}" ]; then
  echo "tools directory not found at ${MPY_TOOLS_DIR}" >&2
  return 1 2>/dev/null || exit 1
fi

case ":${PATH}:" in
  *:"${MPY_TOOLS_DIR}":*) ;;
  *) export PATH="${MPY_TOOLS_DIR}:${PATH}" ;;
esac

echo "mpy-tools on PATH: ${MPY_TOOLS_DIR}"
