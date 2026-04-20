"""Anthropic (Claude) adapter — activated when ANTHROPIC_API_KEY is set."""
from __future__ import annotations

from dataclasses import dataclass

from .llm_base import LLMResponse

_PRICES = {
    "claude-3-5-haiku-latest": (0.0008, 0.004),
    "claude-3-5-sonnet-latest": (0.003, 0.015),
    "claude-sonnet-4": (0.003, 0.015),
    "claude-sonnet-4.6": (0.003, 0.015),
    "claude-opus-4": (0.015, 0.075),
}


def _price(model: str, i: int, o: int) -> float:
    pin, pout = _PRICES.get(model, (0.003, 0.015))
    return (i / 1000.0) * pin + (o / 1000.0) * pout


@dataclass
class AnthropicAdapter:
    model: str = "claude-3-5-sonnet-latest"
    provider: str = "anthropic"

    def complete(
        self,
        *,
        system: str,
        user: str,
        json_mode: bool = False,
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        import anthropic  # lazy

        client = anthropic.Anthropic()
        sys_prompt = system
        if json_mode:
            sys_prompt += "\n\nReturn ONLY valid JSON. Do not wrap in markdown."
        resp = client.messages.create(
            model=self.model,
            system=sys_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": user}],
        )
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        in_tok = resp.usage.input_tokens
        out_tok = resp.usage.output_tokens
        return LLMResponse(
            text=text,
            input_tokens=in_tok,
            output_tokens=out_tok,
            cost_usd=_price(self.model, in_tok, out_tok),
            raw=resp,
            meta={"provider": "anthropic", "model": self.model},
        )
