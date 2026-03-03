from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

STATIC_DIR = Path(__file__).resolve().parent / "dashboard_static"


def repo_root() -> Path:
    # scripts/dashboard_api.py -> repo root is parent of scripts/
    return Path(__file__).resolve().parents[1]


def resolve_latest_run(root: Path, mode: str, profile: str) -> Path:
    parent = root / "artifacts" / mode / profile
    latest_path = parent / "LATEST.json"

    payload = json.loads(latest_path.read_text(encoding="utf-8"))

    run_path = payload.get("run_path")
    if run_path:
        run_dir = Path(run_path)
    else:
        run_dir = parent / payload["run_dir"]

    if not run_dir.exists():
        raise FileNotFoundError(f"Latest run dir does not exist: {run_dir}")

    return run_dir


async def tail_jsonl(path: Path, *, start_at_end: bool, poll_s: float = 0.25):
    with path.open("r", encoding="utf-8") as f:
        if start_at_end:
            f.seek(0, 2)

        try:
            while True:
                line = f.readline()
                if line:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError:
                        await asyncio.sleep(poll_s)
                else:
                    await asyncio.sleep(poll_s)

        except asyncio.CancelledError:
            return


app = FastAPI(title="Virtual Bus Dashboard API")

# For local dev: allow a separate frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/dash", StaticFiles(directory=STATIC_DIR, html=True), name="dash")

@app.get("/")
def root():
    return FileResponse(STATIC_DIR / "index.html")

@app.get("/api/latest")
def api_latest(mode: str = Query(...), profile: str = Query(...)):
    root = repo_root()
    run_dir = resolve_latest_run(root, mode, profile)

    meta_path = run_dir / "run_meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}

    return {
        "mode": mode,
        "profile": profile,
        "run_dir": run_dir.name,
        "run_path": str(run_dir),
        "run_meta": meta,
        "files": {
            "frames": str(run_dir / "frames.jsonl"),
            "signals": str(run_dir / "signals.jsonl"),
            "events": str(run_dir / "events.jsonl"),
        },
    }

@app.get("/health")
def health():
    return {"ok": True, "static_dir": str(STATIC_DIR), "index_exists": (STATIC_DIR / "index.html").exists()}

@app.websocket("/ws/stream")
async def ws_stream(
    websocket: WebSocket,
    mode: str,
    profile: str,
    stream: str = "frames",
    start_at_end: bool = True,
):
    await websocket.accept()

    root = repo_root()
    run_dir = resolve_latest_run(root, mode, profile)

    filename = {
        "frames": "frames.jsonl",
        "signals": "signals.jsonl",
        "events": "events.jsonl",
    }.get(stream)

    if filename is None:
        await websocket.send_json({"type": "error", "message": f"Unknown stream: {stream}"})
        await websocket.close()
        return

    path = run_dir / filename
    if not path.exists():
        await websocket.send_json({"type": "error", "message": f"Missing file: {path.name}"})
        await websocket.close()
        return

    await websocket.send_json({"type": "attached", "run_dir": run_dir.name, "stream": stream})

    try:
        async for obj in tail_jsonl(path, start_at_end=start_at_end):
            await websocket.send_json({"type": "data", "payload": obj})

    except WebSocketDisconnect:
        # Browser/tab closed -> normal
        return

    except asyncio.CancelledError:
        # Server shutting down -> normal
        return