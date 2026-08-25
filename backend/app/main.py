from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .compiler import compile_sketch
from .generator import generate
from .models import (
    CompileRequest,
    GenerateRequest,
    PiDeployRequest,
    PiLogsRequest,
    PipelineRequest,
    PipelineResponse,
)
from .pi_deploy import deploy_python, read_logs
from .registry import get_board, load_boards, load_components

FRONTEND_DIR = Path(os.environ.get("FRONTEND_DIR", Path(__file__).resolve().parents[2] / "frontend"))
if not FRONTEND_DIR.exists():
    FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"

app = FastAPI(title="Hardware Deploy IDE", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"ok": True, "mockCompile": os.environ.get("MOCK_COMPILE") == "1"}


@app.get("/api/boards")
def boards():
    return {"boards": load_boards()}


@app.get("/api/components")
def components():
    return {"components": load_components()}


@app.post("/api/generate")
def api_generate(req: GenerateRequest):
    return generate(req.config)


@app.post("/api/compile")
def api_compile(req: CompileRequest):
    return compile_sketch(req.boardId, req.source)


@app.post("/api/pipeline")
def api_pipeline(req: PipelineRequest):
    gen = generate(req.config)
    if not gen.ok:
        return PipelineResponse(ok=False, generate=gen, errors=gen.errors)

    board = get_board(req.config.boardId)
    family = (board or {}).get("family")
    if family == "arduino":
        source = gen.files[0].content
        compiled = compile_sketch(req.config.boardId, source)
        return PipelineResponse(
            ok=compiled.ok,
            generate=gen,
            compile=compiled,
            errors=[] if compiled.ok else ["Compilation failed — see logs."],
        )
    return PipelineResponse(ok=True, generate=gen)


@app.post("/api/deploy/pi")
def api_deploy_pi(req: PiDeployRequest):
    return deploy_python(req.source, req.host, req.user, req.password, req.remotePath)


@app.post("/api/pi/logs")
def api_pi_logs(req: PiLogsRequest):
    return read_logs(req.host, req.user, req.password, req.logPath, req.sinceBytes)


if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
