"""Compile Arduino sketches with arduino-cli.

Set MOCK_COMPILE=1 to skip the toolchain (CI / machines without AVR cores).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from .models import CompileResponse
from .registry import get_board

COMPILE_TIMEOUT = int(os.environ.get("COMPILE_TIMEOUT_SEC", "120"))


def compile_sketch(board_id: str, source: str) -> CompileResponse:
    board = get_board(board_id)
    if not board:
        return CompileResponse(ok=False, logs=f"Unknown board '{board_id}'", boardId=board_id)
    if board.get("family") != "arduino" or not board.get("fqbn"):
        return CompileResponse(
            ok=False,
            logs=f"Board '{board_id}' has no Arduino FQBN / compile strategy.",
            boardId=board_id,
        )

    if os.environ.get("MOCK_COMPILE") == "1":
        return CompileResponse(
            ok=True,
            hex=_mock_hex(),
            logs="MOCK_COMPILE=1: skipped arduino-cli, returned placeholder Intel HEX.\n",
            boardId=board_id,
            mock=True,
        )

    fqbn = board["fqbn"]
    cli = os.environ.get("ARDUINO_CLI", "arduino-cli")
    if not shutil.which(cli) and not Path(cli).exists():
        return CompileResponse(
            ok=False,
            logs=(
                f"{cli} not found on PATH. Install arduino-cli or run via Docker Compose.\n"
                "Alternatively set MOCK_COMPILE=1 for a UI-only demo."
            ),
            boardId=board_id,
        )

    work = Path(tempfile.mkdtemp(prefix="hw-compile-"))
    sketch_dir = work / "sketch"
    build_dir = work / "build"
    try:
        sketch_dir.mkdir()
        build_dir.mkdir()
        (sketch_dir / "sketch.ino").write_text(source, encoding="utf-8")
        proc = subprocess.run(
            [
                cli,
                "compile",
                "--fqbn",
                fqbn,
                "--output-dir",
                str(build_dir),
                str(sketch_dir),
            ],
            capture_output=True,
            text=True,
            timeout=COMPILE_TIMEOUT,
            check=False,
        )
        logs = (proc.stdout or "") + (proc.stderr or "")
        hex_path = _find_hex(build_dir)
        if proc.returncode != 0 or hex_path is None:
            extra = "" if hex_path else "\nNo .hex artefact produced."
            return CompileResponse(ok=False, logs=logs + extra, boardId=board_id)
        hex_text = hex_path.read_text(encoding="utf-8", errors="replace")
        return CompileResponse(ok=True, hex=hex_text, logs=logs, boardId=board_id)
    except subprocess.TimeoutExpired:
        return CompileResponse(
            ok=False,
            logs=f"Compile timed out after {COMPILE_TIMEOUT}s.",
            boardId=board_id,
        )
    except Exception as exc:  # noqa: BLE001 — surface any toolchain failure to the UI
        return CompileResponse(ok=False, logs=str(exc), boardId=board_id)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _find_hex(build_dir: Path) -> Path | None:
    hexes = sorted(build_dir.glob("*.hex"))
    # Prefer the sketch without bootloader (arduino-cli default for --output-dir)
    for path in hexes:
        if "bootloader" not in path.name.lower():
            return path
    return hexes[0] if hexes else None


def _mock_hex() -> str:
    # Minimal valid-looking Intel HEX (empty-ish record + EOF). Not flashable.
    return ":020000040000FA\n:00000001FF\n"
