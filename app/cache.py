"""Per-stage output cache.

Each stage writes a JSON file at
    runs/<run_id>/stage_outputs/<stage>/<id>.json
containing {"input_hash": ..., "data": ...}.
A stage skips a record when the file exists and its input_hash matches.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def stage_path(run_dir: Path, stage: str, record_id: str) -> Path:
    d = run_dir / "stage_outputs" / stage
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{record_id}.json"


def read_cached(run_dir: Path, stage: str, record_id: str, input_hash: str) -> Any | None:
    p = stage_path(run_dir, stage, record_id)
    if not p.exists():
        return None
    try:
        payload = json.loads(p.read_text())
    except Exception:
        return None
    if payload.get("input_hash") != input_hash:
        return None
    return payload.get("data")


def write_cached(run_dir: Path, stage: str, record_id: str, input_hash: str, data: Any) -> Path:
    p = stage_path(run_dir, stage, record_id)
    p.write_text(json.dumps({"input_hash": input_hash, "data": data}, default=str, indent=2))
    return p


def write_error(run_dir: Path, stage: str, record_id: str, message: str) -> Path:
    d = run_dir / "errors" / stage
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{record_id}.error.json"
    p.write_text(json.dumps({"stage": stage, "id": record_id, "message": message}))
    return p
