"""Request-scoped lifecycle event streaming for TriageRAG (ADR 0017).

Safety Properties (Rule R1, Rule R2, Rule R7):
1. Pure lifecycle emission: tracks real stage starts, completions, skips, and failures.
2. Request isolation: each request owns an isolated event queue; zero cross-talk.
3. Privacy allowlist: safe_summary contains only operation counts/status codes,
   strictly forbidding patient identifiers, vitals, drugs, allergies, complaint narratives,
   and exception tracebacks.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import threading
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from typing import Any

from triagerag.contracts.schemas import (
    StageStatus,
    TriageLifecycleEvent,
    TriageLifecycleEventType,
)

logger = logging.getLogger(__name__)

_CURRENT_EVENT_SINK: ContextVar[TriageEventSink | None] = ContextVar(
    "current_triage_event_sink", default=None
)


def get_current_event_sink() -> TriageEventSink | None:
    """Retrieve the current request-scoped lifecycle event sink."""
    return _CURRENT_EVENT_SINK.get()


def set_current_event_sink(sink: TriageEventSink | None) -> Token[TriageEventSink | None]:
    """Set the request-scoped lifecycle event sink for current task context."""
    return _CURRENT_EVENT_SINK.set(sink)


def reset_current_event_sink(token: Token[TriageEventSink | None]) -> None:
    """Reset the request-scoped lifecycle event sink."""
    _CURRENT_EVENT_SINK.reset(token)


class TriageEventSink:
    """Request-scoped lifecycle event sink yielding real execution events."""

    def __init__(self, request_id: str) -> None:
        self.request_id = request_id
        self._sequence = 0
        self._lock = threading.Lock()
        self._queue: asyncio.Queue[TriageLifecycleEvent | None] = asyncio.Queue()
        self._closed = False

    @property
    def is_closed(self) -> bool:
        return self._closed

    def emit(
        self,
        *,
        event_type: TriageLifecycleEventType,
        stage: str,
        status: StageStatus,
        safe_summary: str,
        data: dict[str, Any] | None = None,
    ) -> None:
        """Thread-safe emission of a sanitized lifecycle event."""
        if self._closed:
            return

        with self._lock:
            self._sequence += 1
            seq = self._sequence

        event = TriageLifecycleEvent(
            request_id=self.request_id,
            sequence=seq,
            timestamp=datetime.now(UTC),
            event_type=event_type,
            stage=stage,
            status=status,
            safe_summary=safe_summary,
            data=data,
        )

        try:
            self._queue.put_nowait(event)
        except Exception as exc:
            logger.debug("Failed to put event into async queue: %s", exc)

    def emit_started(self, stage: str, safe_summary: str) -> None:
        self.emit(
            event_type="stage.started",
            stage=stage,
            status="running",
            safe_summary=safe_summary,
        )

    def emit_completed(
        self, stage: str, safe_summary: str, data: dict[str, Any] | None = None
    ) -> None:
        self.emit(
            event_type="stage.completed",
            stage=stage,
            status="completed",
            safe_summary=safe_summary,
            data=data,
        )

    def emit_skipped(self, stage: str, safe_summary: str) -> None:
        self.emit(
            event_type="stage.skipped",
            stage=stage,
            status="skipped",
            safe_summary=safe_summary,
        )

    def emit_failed(self, stage: str, safe_summary: str) -> None:
        self.emit(
            event_type="stage.failed",
            stage=stage,
            status="failed",
            safe_summary=safe_summary,
        )

    def emit_run_completed(self, safe_summary: str, result_dict: dict[str, Any]) -> None:
        self.emit(
            event_type="run.completed",
            stage="explain",
            status="completed",
            safe_summary=safe_summary,
            data=result_dict,
        )

    def close(self) -> None:
        """Mark stream complete and signal end-of-stream to consumer."""
        if self._closed:
            return
        self._closed = True
        with contextlib.suppress(Exception):
            self._queue.put_nowait(None)

    async def __aiter__(self):
        """Asynchronously yield events until closed."""
        while True:
            item = await self._queue.get()
            if item is None:
                break
            yield item
