"""Abstract base class for LLM providers.

Safety Property (Rules R1, R5):
The LLM is an isolated drafting service. It never emits verdicts or runs
safety math. If drafting fails or violates constraints, execution safely degrades.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from triagerag.contracts.schemas import PlanContext, PlanDraft


class LLMProvider(ABC):
    """Abstract interface for protocol plan drafting models."""

    @abstractmethod
    def draft_plan(self, context: PlanContext) -> PlanDraft:
        """Draft a protocol plan strictly conforming to the PlanDraft schema."""

    @abstractmethod
    def repair_plan(
        self,
        context: PlanContext,
        draft: PlanDraft,
        violations: list[str],
    ) -> PlanDraft:
        """Attempt to repair a rejected plan draft using structured violation codes."""
