#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

RECOMMENDED_VERSION="3.12"

PYTHON_BIN=""
if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
else
    echo "============================================================"
    echo " [ERROR] Python is not installed or not found in PATH."
    echo " Please install Python (Recommended version: $RECOMMENDED_VERSION)."
    echo " Download from: https://www.python.org/downloads/"
    echo " On Linux, install it via your package manager."
    echo "============================================================"
    read -p "Press Enter to exit..."
    exit 1
fi

PY_VER=$($PYTHON_BIN -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "0.0")
PY_MAJOR=$($PYTHON_BIN -c "import sys; print(sys.version_info.major)" 2>/dev/null || echo "0")
PY_MINOR=$($PYTHON_BIN -c "import sys; print(sys.version_info.minor)" 2>/dev/null || echo "0")

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]; }; then
    echo "============================================================"
    echo " [WARNING] Detected Python $PY_VER, which is outdated."
    echo " This application requires Python 3.10 or higher."
    echo " Recommended version: Python $RECOMMENDED_VERSION."
    echo " Please download Python $RECOMMENDED_VERSION from: https://www.python.org/downloads/"
    echo "============================================================"
    read -p "Press Enter to exit..."
    exit 1
fi

echo "[INFO] Detected Python $PY_VER."

if [ ! -f "venv/bin/python" ]; then
    echo "[SETUP] Creating virtual environment..."
    $PYTHON_BIN -m venv --system-site-packages venv || $PYTHON_BIN -m venv venv
    echo "[SETUP] Installing dependencies..."
    ./venv/bin/pip install -r requirements.txt
else
    if ! ./venv/bin/python -c "import customtkinter, PySide6, PIL" >/dev/null 2>&1; then
        echo "[SETUP] Installing missing dependencies..."
        ./venv/bin/pip install -r requirements.txt
    fi
fi

echo "[START] Launching Steam Avatar Manager..."
exec ./venv/bin/python gui.py "$@"
