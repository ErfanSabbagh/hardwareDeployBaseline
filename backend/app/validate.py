from __future__ import annotations

from typing import Any

from .models import HardwareConfig, PinAssignment
from .registry import get_board, get_component, pin_by_id


def validate_config(config: HardwareConfig) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    board = get_board(config.boardId)
    if not board:
        return {}, [f"Unknown board '{config.boardId}'"]

    seen: dict[str, str] = {}
    assignments = [("input", a) for a in config.inputs] + [
        ("output", a) for a in config.outputs
    ]
    if not assignments:
        errors.append("Add at least one input or output pin.")

    for kind, assignment in assignments:
        _check_assignment(board, kind, assignment, seen, errors)

    return board, errors


def _check_assignment(
    board: dict[str, Any],
    kind: str,
    assignment: PinAssignment,
    seen: dict[str, str],
    errors: list[str],
) -> None:
    pin_id = assignment.pin.strip()
    if not pin_id:
        errors.append("A pin assignment is missing a pin id.")
        return
    if pin_id in seen:
        errors.append(f"Pin {pin_id} is used more than once ({seen[pin_id]} and {kind}).")
        return
    seen[pin_id] = kind

    pin = pin_by_id(board, pin_id)
    if not pin:
        errors.append(f"Pin {pin_id} is not on board {board['id']}.")
        return

    component = get_component(assignment.component)
    if not component:
        errors.append(f"Unknown component '{assignment.component}'.")
        return

    if component["kind"] != kind:
        errors.append(
            f"{component['name']} is an {component['kind']} but was placed as {kind}."
        )

    caps = set(pin.get("capabilities", []))
    needs = set(component.get("needs", []))
    if needs and not (needs & caps):
        errors.append(
            f"{component['name']} on {pin_id} needs {sorted(needs)}; "
            f"pin only has {sorted(caps)}."
        )

    if kind == "output" and caps == {"analog"}:
        errors.append(f"Pin {pin_id} is analog-only and cannot drive an output.")
