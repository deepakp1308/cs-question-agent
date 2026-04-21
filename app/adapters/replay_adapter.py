"""Replay adapter: returns pre-generated answers from a transcripts file.

Use this when you want to ship Claude/GPT-quality answers in a deterministic,
reproducible pipeline without committing API keys — or when an outside model
(for example, the Cursor coding assistant) produces answers that the pipeline
should pick up without re-calling any paid API.

The transcript file is YAML (or JSON) of the form:

    - match: "state two advantages of star topology"   # lowercase substring
      role: generator                                  # generator | classifier | judge
      response: |
        {"direct_answer": "...", "exam_style_answer": "...", ...}

The adapter chooses the first entry whose `match` value (lowercased) is a
substring of the user prompt. If nothing matches, it falls back to the mock
adapter so the pipeline still completes. Cost is recorded as zero.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .llm_base import LLMResponse
from .mock_adapter import MockAdapter

ENV_TRANSCRIPT_DIR = "CS_AGENT_TRANSCRIPTS_DIR"


def _load_transcripts(dirs: list[Path]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for d in dirs:
        if not d.exists():
            continue
        for p in sorted(d.iterdir()):
            if p.suffix.lower() not in (".yaml", ".yml", ".json"):
                continue
            try:
                if p.suffix.lower() == ".json":
                    data = json.loads(p.read_text())
                else:
                    data = yaml.safe_load(p.read_text())
            except Exception:
                continue
            if isinstance(data, list):
                entries.extend([e for e in data if isinstance(e, dict)])
    return entries


@dataclass
class ReplayAdapter:
    model: str = "replay"
    provider: str = "replay"
    _entries: list[dict[str, Any]] = field(default_factory=list)
    _fallback: MockAdapter = field(default_factory=MockAdapter)

    def __post_init__(self) -> None:
        dirs: list[Path] = []
        env_dir = os.environ.get(ENV_TRANSCRIPT_DIR)
        if env_dir:
            dirs.append(Path(env_dir))
        # Default locations.
        dirs.append(Path("transcripts"))
        dirs.append(Path("igcse_input/transcripts"))
        self._entries = _load_transcripts(dirs)

    def _lookup(self, *, role: str, user: str) -> str | None:
        haystack = user.lower()
        for e in self._entries:
            match = str(e.get("match", "")).lower().strip()
            if not match:
                continue
            wanted_role = e.get("role")
            if wanted_role and wanted_role != role:
                continue
            if match in haystack:
                return str(e.get("response", ""))
        return None

    def _role_of(self, system: str) -> str:
        s = system.lower()
        if "extraction judge" in s:
            return "judge_extraction"
        if "chapter match judge" in s:
            return "judge_match"
        if "answer judge" in s:
            return "judge_answer"
        if "chapter classifier" in s or "classify" in s:
            return "classifier"
        if "selector parser" in s or "chapter selector" in s:
            return "selector"
        if "teacher" in s or "expert" in s:
            return "generator"
        return "other"

    def complete(
        self,
        *,
        system: str,
        user: str,
        json_mode: bool = False,
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        role = self._role_of(system)
        canned = self._lookup(role=role, user=user)
        if canned is not None:
            return LLMResponse(
                text=canned,
                input_tokens=0,
                output_tokens=len(canned.split()),
                cost_usd=0.0,
                meta={"replay": True, "role": role, "model": self.model},
            )
        # Fallback: let the mock adapter answer so the pipeline completes.
        resp = self._fallback.complete(
            system=system, user=user, json_mode=json_mode, temperature=temperature, max_tokens=max_tokens
        )
        resp.meta.update({"replay": False, "fallback": "mock", "role": role})
        return resp
