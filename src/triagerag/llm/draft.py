"""Safe plan drafting execution wrapper.

Safety Property (Rules R1, R5):
Guarantees that drafting failures never crash the system and never elevate
safety clearance. Catches all provider exceptions and enables safe fallback.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from triagerag.contracts.schemas import PlanContext, PlanDraft
    from triagerag.llm.provider import LLMProvider

logger = logging.getLogger(__name__)


def draft_plan_safe(
    provider: LLMProvider,
    context: PlanContext,
) -> tuple[PlanDraft | None, str | None]:
    """Execute LLM plan drafting with complete fault isolation.

    Returns:
        (PlanDraft, None) on success.
        (None, error_str) on provider failure or exception.
    """
    try:
        draft = provider.draft_plan(context)
        return draft, None
    except Exception as e:
        logger.error("LLM plan drafting failed: %s", e)
        return None, str(e)
