from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class PinAssignment(BaseModel):
    pin: str
    component: str
    role: str = ""


class HardwareConfig(BaseModel):
    boardId: str
    inputs: list[PinAssignment] = Field(default_factory=list)
    outputs: list[PinAssignment] = Field(default_factory=list)
    intent: str = ""


class CompileRequest(BaseModel):
    boardId: str
    source: str


class GenerateRequest(BaseModel):
    config: HardwareConfig


class PipelineRequest(BaseModel):
    config: HardwareConfig


class PiDeployRequest(BaseModel):
    source: str
    host: Optional[str] = None
    user: Optional[str] = None
    password: Optional[str] = None
    remotePath: str = "/home/{user}/hw-deploy/app.py"


class GeneratedFile(BaseModel):
    path: str
    content: str
    language: str


class GenerateResponse(BaseModel):
    ok: bool
    language: str
    files: list[GeneratedFile]
    telemetryHints: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    deployKind: str = ""
    flashProfile: Optional[str] = None
    defaultBaud: Optional[int] = None
    notes: str = ""


class CompileResponse(BaseModel):
    ok: bool
    hex: Optional[str] = None
    logs: str = ""
    boardId: str = ""
    mock: bool = False


class PipelineResponse(BaseModel):
    ok: bool
    generate: GenerateResponse
    compile: Optional[CompileResponse] = None
    errors: list[str] = Field(default_factory=list)


class PiDeployResponse(BaseModel):
    ok: bool
    logs: str = ""
    remotePath: str = ""
    downloadHint: str = ""
