"""Run telemetry — accumulates cost/token/latency and writes metrics.json."""
from __future__ import annotations

import datetime as _dt
import json
from collections import defaultdict
from pathlib import Path
from threading import Lock


class RunTelemetry:
    def __init__(self, run_id: str, run_dir: Path, max_cost_usd: float) -> None:
        self.run_id = run_id
        self.run_dir = Path(run_dir)
        self.max_cost_usd = max_cost_usd
        self.started_at = _dt.datetime.now(_dt.UTC).isoformat() + "Z"
        self.cost_by_stage: dict[str, float] = defaultdict(float)
        self.cost_by_model: dict[str, float] = defaultdict(float)
        self.input_tokens = 0
        self.output_tokens = 0
        self.llm_calls = 0
        self.llm_cache_hits = 0
        self.judge_pass: dict[str, dict[str, int]] = defaultdict(lambda: {"pass": 0, "fail": 0})
        self.tier_counts: dict[str, int] = defaultdict(int)
        self._lock = Lock()

    @property
    def total_cost(self) -> float:
        return sum(self.cost_by_stage.values())

    def record_llm(self, *, stage: str, model_id: str, input_tokens: int, output_tokens: int, cost_usd: float) -> None:
        with self._lock:
            self.cost_by_stage[stage] += cost_usd
            self.cost_by_model[model_id] += cost_usd
            self.input_tokens += input_tokens
            self.output_tokens += output_tokens
            self.llm_calls += 1

    def record_judge(self, *, stage: str, passed: bool) -> None:
        with self._lock:
            key = "pass" if passed else "fail"
            self.judge_pass[stage][key] += 1

    def record_tier(self, tier: str) -> None:
        with self._lock:
            self.tier_counts[tier] += 1

    def cost_exceeded(self) -> bool:
        return self.total_cost >= self.max_cost_usd

    def write(self) -> Path:
        data = {
            "run_id": self.run_id,
            "started_at": self.started_at,
            "finished_at": _dt.datetime.now(_dt.UTC).isoformat() + "Z",
            "cost_usd": {
                "total": self.total_cost,
                "by_stage": dict(self.cost_by_stage),
                "by_model": dict(self.cost_by_model),
            },
            "tokens": {"input": self.input_tokens, "output": self.output_tokens},
            "llm_calls": self.llm_calls,
            "llm_cache_hits": self.llm_cache_hits,
            "judge_pass_rates": {
                stage: (
                    counts["pass"] / (counts["pass"] + counts["fail"])
                    if (counts["pass"] + counts["fail"]) > 0
                    else 0.0
                )
                for stage, counts in self.judge_pass.items()
            },
            "tier_counts": dict(self.tier_counts),
        }
        path = self.run_dir / "metrics.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, default=str))
        return path
