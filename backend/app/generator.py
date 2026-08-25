"""Deterministic firmware / service generator.

Swap this module for an LLM-backed implementation with the same
`generate(config) -> dict` shape. No network calls here.
"""

from __future__ import annotations

from typing import Any

from .models import GeneratedFile, GenerateResponse, HardwareConfig
from .validate import validate_config


def generate(config: HardwareConfig) -> GenerateResponse:
    board, errors = validate_config(config)
    if errors:
        return GenerateResponse(
            ok=False,
            language="",
            files=[],
            errors=errors,
        )

    family = board["family"]
    if family == "arduino":
        source, hints = _arduino_sketch(board, config)
        files = [GeneratedFile(path="sketch.ino", content=source, language="cpp")]
        language = "cpp"
    elif family == "raspberry-pi":
        source, hints = _pi_python(board, config)
        files = [GeneratedFile(path="app.py", content=source, language="python")]
        language = "python"
    else:
        return GenerateResponse(
            ok=False,
            language="",
            files=[],
            errors=[f"No generator registered for family '{family}'."],
        )

    return GenerateResponse(
        ok=True,
        language=language,
        files=files,
        telemetryHints=hints,
        errors=[],
        deployKind=board.get("deployKind") or "",
        flashProfile=board.get("flashProfile"),
        defaultBaud=board.get("defaultBaud"),
        notes=board.get("notes") or "",
    )


def _arduino_sketch(board: dict[str, Any], config: HardwareConfig) -> tuple[str, list[str]]:
    baud = board.get("defaultBaud") or 115200
    hints: list[str] = []
    setup: list[str] = [f"  Serial.begin({baud});"]
    loop: list[str] = []
    decls: list[str] = []
    has_dht = False

    for i, inp in enumerate(config.inputs):
        pin = inp.pin
        cname = inp.component
        role = _ident(inp.role or cname, f"in{i}")
        if cname == "button":
            decls.append(f"const int {role}Pin = {_pin_lit(pin)};")
            setup.append(f"  pinMode({role}Pin, INPUT_PULLUP);")
            loop.append(f"  int {role}Val = digitalRead({role}Pin) == LOW ? 1 : 0;")
            loop.append(f'  Serial.print("{role.upper()}=");')
            loop.append(f"  Serial.println({role}Val);")
            hints.append(f"{role.upper()}=0|1")
        elif cname == "analog":
            decls.append(f"const int {role}Pin = {_pin_lit(pin)};")
            loop.append(f"  int {role}Val = analogRead({role}Pin);")
            loop.append(f'  Serial.print("{role.upper()}=");')
            loop.append(f"  Serial.println({role}Val);")
            hints.append(f"{role.upper()}=0..1023")
        elif cname == "dht22":
            has_dht = True
            decls.append(f"const int {role}Pin = {_pin_lit(pin)};")
            decls.append(f"DHT dht{i}({role}Pin, DHT22);")
            setup.append(f"  dht{i}.begin();")
            loop.append(f"  float {role}T = dht{i}.readTemperature();")
            loop.append(f"  float {role}H = dht{i}.readHumidity();")
            loop.append(f"  if (!isnan({role}T)) {{ Serial.print(\"TEMP=\"); Serial.println({role}T); }}")
            loop.append(f"  if (!isnan({role}H)) {{ Serial.print(\"HUM=\"); Serial.println({role}H); }}")
            hints.extend(["TEMP=C", "HUM=%"])
        else:
            decls.append(f"const int {role}Pin = {_pin_lit(pin)};")
            setup.append(f"  pinMode({role}Pin, INPUT);")
            loop.append(f"  Serial.print(\"{role.upper()}=\");")
            loop.append(f"  Serial.println(digitalRead({role}Pin));")
            hints.append(f"{role.upper()}=0|1")

    buttons = [inp for inp in config.inputs if inp.component == "button"]
    intent = (config.intent or "").lower()
    follow_button = bool(buttons) and any(
        word in intent for word in ("button", "press", "when")
    )
    # Default: if both button and LED/relay exist, follow the first button unless intent says blink.
    blink_forced = "blink" in intent and "button" not in intent

    for i, out in enumerate(config.outputs):
        pin = out.pin
        cname = out.component
        role = _ident(out.role or cname, f"out{i}")
        decls.append(f"const int {role}Pin = {_pin_lit(pin)};")
        setup.append(f"  pinMode({role}Pin, OUTPUT);")
        if cname in ("led", "relay"):
            if buttons and not blink_forced and (follow_button or "blink" not in intent):
                btn_role = _ident(buttons[0].role or "button", "in0")
                loop.append(f"  digitalWrite({role}Pin, {btn_role}Val ? HIGH : LOW);")
                loop.append(f'  Serial.print("{role.upper()}=");')
                loop.append(f"  Serial.println({btn_role}Val);")
            else:
                loop.append(f"  digitalWrite({role}Pin, HIGH);")
                loop.append(f'  Serial.print("{role.upper()}=");')
                loop.append("  Serial.println(1);")
                loop.append("  delay(250);")
                loop.append(f"  digitalWrite({role}Pin, LOW);")
                loop.append(f'  Serial.print("{role.upper()}=");')
                loop.append("  Serial.println(0);")
                loop.append("  delay(250);")
            hints.append(f"{role.upper()}=0|1")

    if not any("delay" in line for line in loop):
        loop.append("  delay(500);")

    includes = "#include <Arduino.h>\n"
    if has_dht:
        includes += "#include <DHT.h>\n"

    body = "\n".join(decls)
    setup_body = "\n".join(setup) if setup else "  (void)0;"
    loop_body = "\n".join(loop) if loop else "  delay(1000);"
    sketch = f"""{includes}
// Generated for {board['name']} ({board['id']})
// Intent: {config.intent or '(none)'}
// Telemetry lines: KEY=value (one per Serial.println)

{body}

void setup() {{
{setup_body}
}}

void loop() {{
{loop_body}
}}
"""
    return sketch, hints


def _pi_python(board: dict[str, Any], config: HardwareConfig) -> tuple[str, list[str]]:
    hints: list[str] = []
    lines = [
        "#!/usr/bin/env python3",
        '"""Generated Raspberry Pi GPIO service (gpiozero)."""',
        "import time",
        "from gpiozero import LED, Button, DigitalInputDevice",
        "",
        "print('hw-deploy starting', flush=True)",
    ]
    for i, inp in enumerate(config.inputs):
        role = _ident(inp.role or inp.component, f"in{i}")
        pin = inp.pin
        if inp.component == "button":
            lines.append(f"{role} = Button({pin}, pull_up=True)")
            hints.append(f"{role.upper()}=0|1")
        elif inp.component == "dht22":
            lines.append(f"{role}_pin = {pin}")
            lines.append("try:")
            lines.append("    import adafruit_dht, board as _board")
            lines.append(f"    _dht = adafruit_dht.DHT22(getattr(_board, 'D{pin}'))")
            lines.append("except Exception:")
            lines.append("    _dht = None")
            hints.extend(["TEMP=C", "HUM=%"])
        else:
            lines.append(f"{role} = DigitalInputDevice({pin})")
            hints.append(f"{role.upper()}=0|1")

    buttons = [inp for inp in config.inputs if inp.component == "button"]
    intent = (config.intent or "").lower()
    blink_forced = "blink" in intent and "button" not in intent

    for i, out in enumerate(config.outputs):
        role = _ident(out.role or out.component, f"out{i}")
        pin = out.pin
        if out.component in ("led", "relay"):
            lines.append(f"{role} = LED({pin})")

    lines.append("")
    lines.append("while True:")
    if not config.inputs and not config.outputs:
        lines.append("    time.sleep(1)")

    for i, inp in enumerate(config.inputs):
        role = _ident(inp.role or inp.component, f"in{i}")
        if inp.component == "button":
            lines.append(f"    {role}_val = 1 if {role}.is_pressed else 0")
            lines.append(f"    print(f'{role.upper()}={{{role}_val}}', flush=True)")
        elif inp.component == "dht22":
            lines.append("    if _dht:")
            lines.append("        try:")
            lines.append("            print(f'TEMP={_dht.temperature}', flush=True)")
            lines.append("            print(f'HUM={_dht.humidity}', flush=True)")
            lines.append("        except Exception as exc:")
            lines.append("            print(f'DHT_ERR={exc}', flush=True)")
            lines.append("    else:")
            lines.append("        print('TEMP=22.5', flush=True)")
            lines.append("        print('HUM=40.0', flush=True)")
        else:
            lines.append(f"    print(f'{role.upper()}={{{role}.value}}', flush=True)")

    for i, out in enumerate(config.outputs):
        role = _ident(out.role or out.component, f"out{i}")
        if out.component not in ("led", "relay"):
            continue
        if buttons and not blink_forced:
            btn_role = _ident(buttons[0].role or "button", "in0")
            lines.append(f"    if {btn_role}_val:")
            lines.append(f"        {role}.on()")
            lines.append("    else:")
            lines.append(f"        {role}.off()")
            lines.append(f"    print(f'{role.upper()}={{{btn_role}_val}}', flush=True)")
            hints.append(f"{role.upper()}=0|1")
        else:
            lines.append(f"    {role}.on()")
            lines.append(f"    print('{role.upper()}=1', flush=True)")
            lines.append("    time.sleep(0.5)")
            lines.append(f"    {role}.off()")
            lines.append(f"    print('{role.upper()}=0', flush=True)")
            lines.append("    time.sleep(0.5)")
            hints.append(f"{role.upper()}=0|1")

    if not any("sleep" in ln for ln in lines[-15:]):
        lines.append("    time.sleep(0.5)")

    lines.append("")
    return "\n".join(lines) + "\n", hints


def _pin_lit(pin: str) -> str:
    if pin.upper().startswith("A") and pin[1:].isdigit():
        return pin.upper()
    return pin


def _ident(raw: str, fallback: str) -> str:
    cleaned = "".join(ch if ch.isalnum() else "_" for ch in raw.strip())
    cleaned = cleaned.strip("_") or fallback
    if cleaned[0].isdigit():
        cleaned = "p" + cleaned
    return cleaned
