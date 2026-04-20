"""Deterministic, offline LLM + embedding adapter.

The mock adapter is the default backend so the full pipeline runs with zero setup
and every test is reproducible. It intentionally returns structured, realistic
output for the specific prompt families used by this agent.

Detection is keyword-based on the system prompt. This is brittle on purpose —
the real adapters use their own JSON-mode parsing; the mock just needs to be
good enough to exercise the whole pipeline.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass

from .llm_base import EmbeddingResponse, LLMResponse


def _hash_vector(text: str, dim: int = 128) -> list[float]:
    """Deterministic dense embedding: hash-based bag of words into `dim` buckets."""
    vec = [0.0] * dim
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9\-']+", text.lower())
    for token in tokens:
        h = int(hashlib.sha256(token.encode()).hexdigest(), 16)
        idx = h % dim
        sign = 1.0 if (h >> 8) % 2 == 0 else -1.0
        vec[idx] += sign
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


@dataclass
class MockAdapter:
    model: str = "mock-lm"
    provider: str = "mock"

    def complete(
        self,
        *,
        system: str,
        user: str,
        json_mode: bool = False,
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        sys_lower = system.lower()
        text: str
        if "extraction judge" in sys_lower or "judge_extraction" in sys_lower:
            text = json.dumps(
                {
                    "pass": True,
                    "score": 0.985,
                    "issues": [],
                    "sub_scores": {
                        "text_fidelity": 0.99,
                        "numbering_fidelity": 1.0,
                        "marks_fidelity": 1.0,
                    },
                }
            )
        elif "answer judge" in sys_lower or "judge_answer" in sys_lower:
            text = json.dumps(
                {
                    "pass": True,
                    "score": 0.93,
                    "issues": [],
                    "sub_scores": {
                        "correctness": 0.94,
                        "grounding": 0.95,
                        "completeness": 0.90,
                        "clarity": 0.96,
                        "age_fit": 0.97,
                    },
                    "repair_instructions": [],
                }
            )
        elif "chapter match judge" in sys_lower or "judge_match" in sys_lower:
            text = json.dumps({"pass": True, "score": 0.95, "issues": []})
        elif "chapter classifier" in sys_lower or "classify" in sys_lower:
            text = self._mock_classify(user)
        elif "chapter selector" in sys_lower or "selector parser" in sys_lower:
            text = self._mock_selector(user)
        elif "teacher" in sys_lower or "generate_answer" in sys_lower:
            text = self._mock_answer(user)
        elif "repair" in sys_lower:
            text = self._mock_answer(user)
        else:
            text = json.dumps({"ok": True, "echo": user[:120]})
        input_tokens = max(1, len(user.split()) + len(system.split()))
        output_tokens = max(1, len(text.split()))
        return LLMResponse(
            text=text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=0.0,
            meta={"mock": True, "model": self.model},
        )

    @staticmethod
    def _mock_classify(user: str) -> str:
        # Look only at the QUESTION line so we don't match keywords that appear
        # in the CHAPTERS section of the prompt.
        qm = re.search(r"QUESTION:\s*(.+)", user, re.IGNORECASE)
        lower = (qm.group(1) if qm else user).lower()
        chapters = re.findall(r'chapter_id[":\s]+([a-z_0-9]+)', user.lower())
        primary = chapters[0] if chapters else "ch_generic"
        # Database keywords are checked first because "network" as a word also
        # appears in common DB questions (e.g. "social network database").
        db_keywords = ("database", "sql", "primary key", "foreign key", "table", "schema", "select", "insert")
        net_keywords = ("topology", "network", "lan", "wan", "packet", "router", "protocol", "switch")
        if any(k in lower for k in db_keywords):
            primary = "ch_databases"
        elif any(k in lower for k in net_keywords):
            primary = "ch_networks"
        return json.dumps(
            {
                "primary_chapter": primary,
                "secondary_chapters": [],
                "confidence": 0.92,
                "justification": "keyword match",
            }
        )

    @staticmethod
    def _mock_selector(user: str) -> str:
        specs = []
        for m in re.finditer(r"(ch_[a-z0-9_]+)\s*:\s*([^\n]+)", user):
            specs.append({"chapter_id": m.group(1), "title": m.group(2).strip()})
        if not specs:
            specs = [{"chapter_id": "ch_generic", "title": "Generic"}]
        return json.dumps({"chapters": specs})

    @staticmethod
    def _mock_answer(user: str) -> str:
        # Pull one "evidence" sentence from the context block if present.
        evidence_ids = re.findall(r"\[chunk:([a-z0-9_\-]+)\]", user)
        question = ""
        qm = re.search(r"QUESTION:\s*(.+)", user, re.IGNORECASE)
        if qm:
            question = qm.group(1).strip()
        direct = question.rstrip("?.") if question else "See the retrieved source material."
        evidence_snippets = re.findall(r"\[chunk:[a-z0-9_\-]+\]\s+([^\n]+)", user)
        evidence_ids = evidence_ids[:3] or ["src_fallback_000"]
        exam_style = (
            "In brief: " + (evidence_snippets[0] if evidence_snippets else direct)
        )[:300]
        steps = [
            "Read what the question is asking for.",
            "Recall the key idea from the chapter: "
            + (evidence_snippets[0] if evidence_snippets else "see chapter notes."),
            "Answer clearly in one or two sentences, using the evidence above.",
        ]
        return json.dumps(
            {
                "direct_answer": direct,
                "exam_style_answer": exam_style,
                "step_by_step_explanation": steps,
                "simple_example": "Think of a small school network as a concrete example.",
                "common_mistake": "Do not answer from memory — cite the chapter source.",
                "evidence_chunk_ids": evidence_ids,
                "answer_confidence": 0.92,
            }
        )


@dataclass
class MockEmbeddingAdapter:
    model: str = "mock-embeddings"
    provider: str = "mock"
    dimensions: int = 128

    def embed(self, texts: list[str]) -> EmbeddingResponse:
        vectors = [_hash_vector(t, dim=self.dimensions) for t in texts]
        return EmbeddingResponse(
            vectors=vectors,
            input_tokens=sum(len(t.split()) for t in texts),
            cost_usd=0.0,
        )
