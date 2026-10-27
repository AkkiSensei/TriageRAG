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
from typing import Any

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

    class GuardedSocket(socket.socket):
        def connect(self, address: Any) -> None:
            if isinstance(address, tuple) and len(address) >= 2:
                host = address[0]
                if host in ("127.0.0.1", "localhost", "::1"):
                    super().connect(address)
                    return
            raise BlockedNetworkError(
                f"Unauthorized network call to {address!r} attempted in offline test: "
                f"{request.node.name}. All TriageRAG tests must run completely offline."
            )

        def connect_ex(self, address: Any) -> int:
            if isinstance(address, tuple) and len(address) >= 2:
                host = address[0]
                if host in ("127.0.0.1", "localhost", "::1"):
                    return int(super().connect_ex(address))
            raise BlockedNetworkError(
                f"Unauthorized network call to {address!r} attempted in offline test: "
                f"{request.node.name}. All TriageRAG tests must run completely offline."
            )

    monkeypatch.setattr(socket, "socket", GuardedSocket)
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


@pytest.fixture(scope="session")
def clinical_registry() -> Any:
    """Cached ClinicalRegistry loaded from repository data directory."""
    from triagerag.config import get_data_dir
    from triagerag.engine.registry import ClinicalRegistry

    return ClinicalRegistry.load_from_directory(get_data_dir())


@pytest.fixture(scope="session")
def bm25_index() -> Any:
    """Cached BM25ClinicalIndex loaded from synthetic protocols."""
    from triagerag.config import get_data_dir
    from triagerag.rag.index import BM25ClinicalIndex
    from triagerag.rag.ingest import ingest_protocols

    chunks = ingest_protocols(get_data_dir())
    return BM25ClinicalIndex(chunks)
