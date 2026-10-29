"""Google Gemini LLM provider implementation.

Safety Property (Rules R1, R5):
Uses structured JSON schema generation. Model name configured via env (GEMINI_MODEL).
Timeouts and retries are enforced. Any network or provider error raises an exception,
which the orchestrator catches to safely fall back to llm_fallback_mode=True.
Never imported at module top level in non-LLM components.
"""

from __future__ import annotations

import os
import time
from typing import TYPE_CHECKING, Any

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
        max_retries: int = 2,
    ) -> None:
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        # Reconcile TRIAGERAG_MODEL_NAME (.env.example) and GEMINI_MODEL
        self.model_name = (
            model_name
            or os.environ.get("TRIAGERAG_MODEL_NAME")
            or os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
        )
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable is required for GeminiProvider")

        # Lazy import to ensure repo runs offline without google-genai
        try:
            from google import genai  # type: ignore[import-not-found]

            # Enforce timeout in client HTTP options
            self.client = genai.Client(
                api_key=self.api_key,
                http_options={"timeout": int(self.timeout_seconds * 1000)},
            )
        except ImportError as e:
            raise RuntimeError(
                "google-genai extra is not installed. Install via: pip install 'triagerag[llm]'"
            ) from e

    def _generate_with_retry(self, contents: str, config: dict[str, Any]) -> Any:
        """Execute model content generation with bounded retries and timeout enforcement."""
        # Include timeout in call config options
        config["http_options"] = {"timeout": int(self.timeout_seconds * 1000)}

        last_err: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                return self.client.models.generate_content(
                    model=self.model_name,
                    contents=contents,
                    config=config,
                )
            except Exception as e:
                last_err = e
                if attempt < self.max_retries:
                    time.sleep(0.5 * (2**attempt))
        raise RuntimeError(
            f"Gemini request failed after {self.max_retries + 1} attempts: {last_err}"
        ) from last_err

    def draft_plan(self, context: PlanContext) -> PlanDraft:
        """Draft structured plan using Gemini JSON schema output."""
        prompt = build_plan_draft_prompt(context)
        try:
            response = self._generate_with_retry(
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
            response = self._generate_with_retry(
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
