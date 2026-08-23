from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from . import SHARED_DIR

# When the backend image copies shared/ next to app/
_FALLBACK_SHARED = Path(__file__).resolve().parents[1] / "shared"


def _shared_dir() -> Path:
    if SHARED_DIR.exists():
        return SHARED_DIR
    return _FALLBACK_SHARED


@lru_cache
def load_boards() -> list[dict[str, Any]]:
    path = _shared_dir() / "boards.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["boards"]


@lru_cache
def load_components() -> list[dict[str, Any]]:
    path = _shared_dir() / "components.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["components"]


def get_board(board_id: str) -> dict[str, Any] | None:
    for board in load_boards():
        if board["id"] == board_id:
            return board
    return None


def get_component(component_id: str) -> dict[str, Any] | None:
    for component in load_components():
        if component["id"] == component_id:
            return component
    return None


def pin_by_id(board: dict[str, Any], pin_id: str) -> dict[str, Any] | None:
    for pin in board.get("pins", []):
        if pin["id"] == pin_id:
            return pin
    return None
