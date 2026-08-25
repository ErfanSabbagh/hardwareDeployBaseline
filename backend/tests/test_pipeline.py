from fastapi.testclient import TestClient

from app.generator import generate
from app.models import HardwareConfig, PinAssignment
from app.compiler import compile_sketch


def test_unknown_board():
    result = generate(HardwareConfig(boardId="nope", outputs=[]))
    assert result.ok is False
    assert any("Unknown board" in e for e in result.errors)


def test_pin_conflict():
    cfg = HardwareConfig(
        boardId="uno",
        inputs=[PinAssignment(pin="13", component="button")],
        outputs=[PinAssignment(pin="13", component="led")],
    )
    result = generate(cfg)
    assert result.ok is False
    assert any("more than once" in e for e in result.errors)


def test_analog_only_rejected_as_output_on_nano():
    cfg = HardwareConfig(
        boardId="nano",
        outputs=[PinAssignment(pin="A6", component="led")],
    )
    result = generate(cfg)
    assert result.ok is False


def test_uno_led_generates_sketch():
    cfg = HardwareConfig(
        boardId="uno",
        outputs=[PinAssignment(pin="13", component="led", role="status")],
        intent="blink the LED",
    )
    result = generate(cfg)
    assert result.ok
    assert result.language == "cpp"
    src = result.files[0].content
    assert "pinMode(statusPin, OUTPUT)" in src
    assert "Serial.begin(115200)" in src


def test_pi_generates_python():
    cfg = HardwareConfig(
        boardId="raspberry-pi",
        outputs=[PinAssignment(pin="17", component="led", role="lamp")],
    )
    result = generate(cfg)
    assert result.ok
    assert result.language == "python"
    assert "gpiozero" in result.files[0].content
    assert result.deployKind == "ssh"


def test_pi_logs_need_host():
    from app.pi_deploy import read_logs

    result = read_logs(None, None, None, "/tmp/x", 0)
    assert result.ok is False
    assert "host" in result.logs.lower() or "user" in result.logs.lower()


def test_mega_generates_sketch():
    cfg = HardwareConfig(
        boardId="mega",
        outputs=[PinAssignment(pin="13", component="led", role="status")],
        intent="blink",
    )
    result = generate(cfg)
    assert result.ok
    assert result.flashProfile == "mega"


def test_mock_compile(monkeypatch):
    monkeypatch.setenv("MOCK_COMPILE", "1")
    compiled = compile_sketch("uno", "void setup(){} void loop(){}")
    assert compiled.ok
    assert compiled.mock
    assert compiled.hex and compiled.hex.strip().startswith(":")
