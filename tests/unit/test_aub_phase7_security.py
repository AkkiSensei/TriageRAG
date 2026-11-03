"""Unit tests for Phase 7 API security, token authentication, and sliding-window rate limiting (AUB T7.5)."""

import pytest
from fastapi.testclient import TestClient

from triagerag.api.app import create_app
from triagerag.api.security import (
    SecurityConfig,
    SlidingWindowRateLimiter,
    is_path_exempt,
)


def test_sliding_window_rate_limiter_allows_and_blocks():
    """Verify sliding window allows requests within quota and blocks excess."""
    limiter = SlidingWindowRateLimiter(max_requests=3, window_seconds=10.0)

    # 3 requests at t=0 allowed
    allowed, _ = limiter.is_allowed("client-1", current_time=100.0)
    assert allowed is True
    allowed, _ = limiter.is_allowed("client-1", current_time=101.0)
    assert allowed is True
    allowed, _ = limiter.is_allowed("client-1", current_time=102.0)
    assert allowed is True

    # 4th request at t=103 should be denied
    allowed, retry_after = limiter.is_allowed("client-1", current_time=103.0)
    assert allowed is False
    assert retry_after == pytest.approx(7.0, rel=1e-2)  # 100.0 + 10.0 - 103.0 = 7.0

    # Different client has its own independent bucket
    allowed, _ = limiter.is_allowed("client-2", current_time=103.0)
    assert allowed is True

    # After sliding window passes (cutoff t > 100), oldest request expires
    allowed, _ = limiter.is_allowed("client-1", current_time=110.5)
    assert allowed is True


def test_path_exemption_rules():
    """Verify exempt paths (health, docs, root) vs protected endpoints."""
    assert is_path_exempt("/health") is True
    assert is_path_exempt("/api/health") is True
    assert is_path_exempt("/docs") is True
    assert is_path_exempt("/openapi.json") is True
    assert is_path_exempt("/assets/style.css") is True
    assert is_path_exempt("/api") is True
    assert is_path_exempt("/") is True

    assert is_path_exempt("/api/triage") is False
    assert is_path_exempt("/api/eval/summary") is False
    assert is_path_exempt("/api/scenarios") is False
    assert is_path_exempt("/api/protocols") is False


def test_api_auth_boundary_enforcement():
    """Verify 401 Unauthorized when auth is required and credentials are missing or invalid."""
    sec_cfg = SecurityConfig(api_key="super-secret-gate-token", require_auth=True)
    app = create_app(security_config=sec_cfg)
    client = TestClient(app)

    # Health check is exempt
    resp = client.get("/api/health")
    assert resp.status_code == 200

    # Protected endpoint without auth returns 401
    resp = client.get("/api/scenarios")
    assert resp.status_code == 401
    assert "Authentication required" in resp.json()["detail"]
    assert resp.headers.get("www-authenticate") == "Bearer"

    # Protected endpoint with invalid X-API-Key returns 401
    resp = client.get("/api/scenarios", headers={"x-api-key": "wrong-token"})
    assert resp.status_code == 401

    # Protected endpoint with valid X-API-Key succeeds
    resp = client.get("/api/scenarios", headers={"x-api-key": "super-secret-gate-token"})
    assert resp.status_code == 200

    # Protected endpoint with valid Bearer token succeeds
    resp = client.get("/api/scenarios", headers={"authorization": "Bearer super-secret-gate-token"})
    assert resp.status_code == 200


def test_rate_limiting_middleware_429():
    """Verify 429 Too Many Requests when request burst exceeds configured capacity."""
    limiter = SlidingWindowRateLimiter(max_requests=2, window_seconds=60.0)
    sec_cfg = SecurityConfig(require_auth=False)
    app = create_app(security_config=sec_cfg, rate_limiter=limiter)
    client = TestClient(app)

    resp1 = client.get("/api/health")
    assert resp1.status_code == 200

    resp2 = client.get("/api/health")
    assert resp2.status_code == 200

    # 3rd request from same client exceeds limit of 2
    resp3 = client.get("/api/health")
    assert resp3.status_code == 429
    assert resp3.json()["detail"].startswith("Rate limit exceeded")
    assert "retry-after" in resp3.headers
    assert int(resp3.headers["retry-after"]) >= 1
