#!/bin/bash
set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
source "$SCRIPT_DIR/venv/bin/activate"

# Export CUDA library paths from PyTorch / Nvidia pip packages
NV_PATHS=$(python3 -c 'import os, nvidia; print(":".join([os.path.join(root, "lib") for root, dirs, files in os.walk(nvidia.__path__[0]) if "lib" in dirs]))')
export LD_LIBRARY_PATH="$NV_PATHS:$LD_LIBRARY_PATH"

exec python3 "$SCRIPT_DIR/transcribe.py" "$@"
