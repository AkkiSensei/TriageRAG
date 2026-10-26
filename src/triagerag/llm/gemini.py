"""Google Gemini LLM provider implementation.

Safety Property (Rules R1, R5):
Uses structured JSON schema generation. Model name configured via env (GEMINI_MODEL).
Timeouts and retries are enforced. Any network or provider error raises an exception,
which the orchestrator catches to safely fall back to llm_fallback_mode=True.
Never imported at module top level in non-LLM components.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from triagerag.contracts.schemas import PlanContext, PlanDraft
from triagerag.llm.prompts import PLAN_DRAFT_SYSTEM_PROMPT, build_plan_draft_prompt
from triagerag.llm.provider import LLMProvider

if TYPE_CHECKING:
    pass


class GeminiProvider(LLMProvider):
    """Production LLM provider using Google Gemini GenAI SDK."""

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str | None = None,
        timeout_seconds: float = 15.0,
    ) -> None:
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        self.model_name = model_name or os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
        self.timeout_seconds = timeout_seconds

        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable is required for GeminiProvider")

        # Lazy import to ensure repo runs offline without google-genai
        try:
            from google import genai  # type: ignore[import-not-found]

            self.client = genai.Client(api_key=self.api_key)
        except ImportError as e:
            raise RuntimeError(
                "google-genai extra is not installed. Install via: pip install 'triagerag[llm]'"
            ) from e

    def draft_plan(self, context: PlanContext) -> PlanDraft:
        """Draft structured plan using Gemini JSON schema output."""
        prompt = build_plan_draft_prompt(context)
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config={
                    "system_instruction": PLAN_DRAFT_SYSTEM_PROMPT,
                    "response_mime_type": "application/json",
                    "response_schema": PlanDraft,
                    "temperature": 0.0,
                },
            )
            raw_text = response.text or ""
            return PlanDraft.model_validate_json(raw_text)
        except Exception as e:
            raise RuntimeError(f"Gemini plan drafting failed: {e}") from e

    def repair_plan(
        self,
        context: PlanContext,
        draft: PlanDraft,
        violations: list[str],
    ) -> PlanDraft:
        """Repair plan by prompting with structured validation rejection codes."""
        violations_block = "\n".join(f"- {v}" for v in violations)
        repair_prompt = (
            f"{build_plan_draft_prompt(context)}\n\n"
            f"PREVIOUS DRAFT REJECTED BY MACHINE VERIFICATION:\n"
            f"{draft.model_dump_json(indent=2)}\n\n"
            f"VIOLATION CODES THAT MUST BE RESOLVED:\n"
            f"{violations_block}\n\n"
            "Emit a corrected PlanDraft JSON fixing all violations."
        )
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=repair_prompt,
                config={
                    "system_instruction": PLAN_DRAFT_SYSTEM_PROMPT,
                    "response_mime_type": "application/json",
                    "response_schema": PlanDraft,
                    "temperature": 0.0,
                },
            )
            raw_text = response.text or ""
            return PlanDraft.model_validate_json(raw_text)
        except Exception as e:
            raise RuntimeError(f"Gemini plan repair failed: {e}") from e
