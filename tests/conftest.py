"""Pytest configuration and autouse fixtures.

Safety Property:
All tests run strictly offline. Network access is blocked by default via an autouse
socket blocker fixture unless explicitly marked with '@pytest.mark.network'.
Provides a deterministic fixed clock fixture.
"""

from __future__ import annotations

import socket
from collections.abc import Generator
from datetime import UTC, datetime

import pytest


class BlockedNetworkError(RuntimeError):
    """Raised when an offline test attempts unauthorized network access."""


@pytest.fixture(autouse=True)
def block_network(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> Generator[None, None, None]:
    """Block network sockets by default unless marked with '@pytest.mark.network'."""
    if "network" in request.keywords:
        yield
        return

    def guarded_socket(*args: object, **kwargs: object) -> socket.socket:
        raise BlockedNetworkError(
            f"Unauthorized network call attempted in offline test: {request.node.name}. "
            "All TriageRAG tests must run completely offline."
        )

    monkeypatch.setattr(socket, "socket", guarded_socket)
    yield


class FixedClock:
    """Deterministic clock providing a frozen timezone-aware reference time."""

    def __init__(self, frozen_time: datetime | None = None) -> None:
        self._time = frozen_time or datetime(2026, 10, 26, 12, 0, 0, tzinfo=UTC)

    def now(self) -> datetime:
        return self._time


@pytest.fixture
def fixed_clock() -> FixedClock:
    """Fixture returning a deterministic frozen Clock."""
    return FixedClock()
