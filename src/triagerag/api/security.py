"""Security boundary and rate limiting for TriageRAG API.

Safety Properties (Rules R1-R12, AUB T7.5):
1. Research Prototype Boundary: Enforces defense-in-depth token/key authentication
   and sliding-window rate limiting for local/staging research deployments.
   Full production clinical deployments require integration with hospital-grade
   identity providers (OAuth2/OIDC, SMART-on-FHIR, mTLS).
2. Constant-time credential comparison (prevents timing side-channel attacks).
3. Sliding-window in-memory rate limiting with deterministic retry-after calculation
   and per-client isolation (prevents denial-of-service on inference and evaluation).
4. Public health, root, and documentation endpoints remain accessible without auth.
"""

from __future__ import annotations

import hmac
import logging
import os
import threading
import time
from collections import deque
from collections.abc import Awaitable, Callable

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse

logger = logging.getLogger("triagerag.api.security")

# Exempt paths that never require API authentication
EXEMPT_PREFIXES: tuple[str, ...] = (
    "/health",
    "/api/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/assets",
)
EXEMPT_EXACT_PATHS: tuple[str, ...] = (
    "/",
    "/api",
)


class SlidingWindowRateLimiter:
    """Thread-safe sliding-window rate limiter for client requests."""

    def __init__(self, max_requests: int = 60, window_seconds: float = 60.0) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._lock = threading.Lock()
        self._history: dict[str, deque[float]] = {}

    def is_allowed(self, client_id: str, current_time: float | None = None) -> tuple[bool, float]:
        """Check if client is within rate limits.

        Returns (allowed, retry_after_seconds).
        """
        now = time.monotonic() if current_time is None else current_time
        with self._lock:
            queue = self._history.setdefault(client_id, deque())
            # Evict timestamps older than sliding window
            cutoff = now - self.window_seconds
            while queue and queue[0] <= cutoff:
                queue.popleft()

            if len(queue) >= self.max_requests:
                oldest = queue[0]
                retry_after = max(1.0, (oldest + self.window_seconds) - now)
                return False, retry_after

            queue.append(now)
            return True, 0.0

    def reset(self) -> None:
        """Reset all rate limiting state."""
        with self._lock:
            self._history.clear()


class SecurityConfig:
    """Configuration for API security and rate limiting."""

    def __init__(
        self,
        api_key: str | None = None,
        require_auth: bool | None = None,
        rate_limit_per_minute: int | None = None,
        rate_limit_window_seconds: float = 60.0,
    ) -> None:
        self.api_key = api_key if api_key is not None else os.getenv("TRIAGERAG_API_KEY", "")
        self.require_auth = (
            require_auth
            if require_auth is not None
            else os.getenv("TRIAGERAG_REQUIRE_AUTH", "false").lower() in ("true", "1", "yes")
        )
        rpm_env = os.getenv("TRIAGERAG_RATE_LIMIT_PER_MINUTE")
        self.rate_limit_per_minute = (
            rate_limit_per_minute
            if rate_limit_per_minute is not None
            else (int(rpm_env) if rpm_env and rpm_env.isdigit() else 120)
        )
        self.rate_limit_window_seconds = rate_limit_window_seconds


def get_client_identifier(request: Request) -> str:
    """Derive client identifier from API key, authorization header, or client IP."""
    # Check X-API-Key or Bearer token first
    key = request.headers.get("x-api-key")
    if key:
        return f"key:{hash(key)}"
    auth = request.headers.get("authorization")
    if auth and auth.startswith("Bearer "):
        return f"token:{hash(auth[7:].strip())}"

    # Fall back to client IP (or forwarded IP if behind trusted reverse proxy)
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()
        return f"ip:{client_ip}"
    if request.client and request.client.host:
        return f"ip:{request.client.host}"
    return "ip:unknown"


def is_path_exempt(path: str) -> bool:
    """Determine whether path is exempt from authentication."""
    if path in EXEMPT_EXACT_PATHS:
        return True
    return any(path.startswith(prefix) for prefix in EXEMPT_PREFIXES)


def create_security_middleware(
    config: SecurityConfig | None = None,
    limiter: SlidingWindowRateLimiter | None = None,
) -> Callable[[Request, Callable[[Request], Awaitable[Response]]], Awaitable[Response]]:
    """Factory creating an ASGI HTTP middleware for authentication and rate limiting."""
    cfg = config or SecurityConfig()
    rate_limiter = (
        limiter
        if limiter is not None
        else SlidingWindowRateLimiter(
            max_requests=cfg.rate_limit_per_minute,
            window_seconds=cfg.rate_limit_window_seconds,
        )
    )

    async def security_middleware(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        path = request.url.path

        # 1. Rate Limiting Check
        client_id = get_client_identifier(request)
        allowed, retry_after = rate_limiter.is_allowed(client_id)
        if not allowed:
            logger.warning("Rate limit exceeded for client %s on %s", client_id, path)
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": "Rate limit exceeded. Please retry after the indicated interval.",
                    "retry_after_seconds": int(retry_after) + 1,
                },
                headers={"Retry-After": str(int(retry_after) + 1)},
            )

        # 2. Authentication Check (if enabled and path is not exempt)
        if cfg.require_auth and not is_path_exempt(path):
            expected_key = cfg.api_key
            if not expected_key:
                logger.error("Authentication required but TRIAGERAG_API_KEY is unset")
                return JSONResponse(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    content={"detail": "API authentication is improperly configured on server."},
                )

            # Check X-API-Key
            provided_key = request.headers.get("x-api-key")
            if not provided_key:
                # Check Authorization: Bearer <key>
                auth_header = request.headers.get("authorization", "")
                if auth_header.startswith("Bearer "):
                    provided_key = auth_header[7:].strip()

            if not provided_key or not hmac.compare_digest(
                provided_key.encode("utf-8"), expected_key.encode("utf-8")
            ):
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={
                        "detail": "Authentication required. Provide valid X-API-Key or Bearer token."
                    },
                    headers={"WWW-Authenticate": "Bearer"},
                )

        return await call_next(request)

    return security_middleware
