"""FastAPI application for TriageRAG clinical decision support.

Safety Properties (Rules R1-R12):
1. Code decides; API is a stateless presentation adapter over the orchestrator.
2. Never exposes stack traces or unhashed patient data in logs/responses.
3. Decimals preserved as exact strings across all JSON endpoints.
4. CORS restricted to local Vite dev server by default.
"""

from __future__ import annotations

import contextlib
import logging
import os
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from triagerag.api.routes.audit import router as audit_router
from triagerag.api.routes.corpus import router as corpus_router
from triagerag.api.routes.eval import router as eval_router
from triagerag.api.routes.health import router as health_router
from triagerag.api.routes.protocols import router as protocols_router
from triagerag.api.routes.registry import router as registry_router
from triagerag.api.routes.scenarios import router as scenarios_router
from triagerag.api.routes.triage import router as triage_router
from triagerag.api.security import (
    SecurityConfig,
    SlidingWindowRateLimiter,
    create_security_middleware,
)
from triagerag.orchestration.telemetry import (
    TelemetryManager,
    extract_trace_context,
    get_active_trace_id_hex,
    inject_trace_context,
    sanitize_span_attributes,
)

logger = logging.getLogger("triagerag.api")

DISCLAIMER = "Research prototype. Synthetic data only. Not a medical device. Not for clinical use."


@contextlib.asynccontextmanager
async def app_lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application lifecycle for OpenTelemetry and other resources."""
    TelemetryManager.get_instance().initialize()
    try:
        yield
    finally:
        TelemetryManager.get_instance().shutdown()


def create_app(
    security_config: SecurityConfig | None = None,
    rate_limiter: SlidingWindowRateLimiter | None = None,
) -> FastAPI:
    app = FastAPI(
        title="TriageRAG Clinical Console API",
        description=(
            f"Deterministic emergency-triage decision support API. \n\n**DISCLAIMER:** {DISCLAIMER}"
        ),
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=app_lifespan,
    )

    # CORS configuration: Vite dev origin
    allowed_origins = os.getenv(
        "TRIAGERAG_CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000",
    ).split(",")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    # Security & Rate Limiting Middleware (AUB T7.5)
    sec_middleware = create_security_middleware(config=security_config, limiter=rate_limiter)
    app.middleware("http")(sec_middleware)

    # Middleware: Request body size limit (2MB)
    @app.middleware("http")
    async def limit_request_size(request: Request, call_next: Any) -> Any:
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > 2 * 1024 * 1024:
            return JSONResponse(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                content={"detail": "Request body too large (maximum 2MB allowed)"},
            )
        return await call_next(request)

    # OpenTelemetry ASGI Distributed Tracing Middleware (registered last so it is the outermost wrapper)
    @app.middleware("http")
    async def tracing_middleware(request: Request, call_next: Any) -> Any:
        manager = TelemetryManager.get_instance()
        tracer = manager.get_tracer()

        # 1. Extract incoming W3C trace context if supplied
        carrier: dict[str, str] = {k.lower(): v for k, v in request.headers.items()}
        extracted_ctx = extract_trace_context(carrier)

        # 2. Extract safe operational attributes (no query strings, no payloads, no PII)
        route_path = request.url.path.rstrip("/") or "/"
        safe_attrs = sanitize_span_attributes(
            {
                "http.method": request.method,
                "http.route": route_path,
            }
        )

        span_cm = None
        active_span = None
        try:
            span_cm = tracer.start_as_current_span(
                "http.request",
                context=extracted_ctx,
                attributes=safe_attrs,
                record_exception=False,
                set_status_on_exception=False,
            )
            active_span = span_cm.__enter__()
        except Exception:
            logger.debug("Failed to create HTTP root span; continuing without tracing.")
            span_cm = None
            active_span = None

        try:
            response = await call_next(request)

            # Record safe HTTP status code
            if (
                active_span is not None
                and hasattr(active_span, "is_recording")
                and active_span.is_recording()
            ):
                with contextlib.suppress(Exception):
                    status_attrs = sanitize_span_attributes(
                        {"http.status_code": response.status_code}
                    )
                    for k, v in status_attrs.items():
                        active_span.set_attribute(k, v)

            # Inject standard W3C propagation headers into response
            with contextlib.suppress(Exception):
                resp_carrier: dict[str, str] = {}
                inject_trace_context(resp_carrier)
                for k, v in resp_carrier.items():
                    response.headers[k] = v

                trace_id_hex = get_active_trace_id_hex()
                if trace_id_hex:
                    response.headers["X-Trace-Id"] = trace_id_hex

            return response
        except Exception as exc:
            if (
                active_span is not None
                and hasattr(active_span, "is_recording")
                and active_span.is_recording()
            ):
                with contextlib.suppress(Exception):
                    active_span.set_attribute("http.status_code", 500)
                    active_span.set_attribute("error.type", "application_error")
            if span_cm is not None:
                with contextlib.suppress(Exception):
                    span_cm.__exit__(type(exc), exc, exc.__traceback__)
                    span_cm = None
            raise
        finally:
            if span_cm is not None:
                with contextlib.suppress(Exception):
                    span_cm.__exit__(None, None, None)

    # Custom 422 validation error handler (clear field paths, no raw patient data logged)
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = []
        for err in exc.errors():
            loc = " -> ".join(str(part) for part in err.get("loc", []))
            errors.append({"field": loc, "message": err.get("msg", "Invalid value")})
        logger.warning("Validation error on %s: %s", request.url.path, errors)
        status_code = getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422)
        return JSONResponse(
            status_code=status_code,
            content={"detail": "Validation error", "errors": errors},
        )

    # Global 500 error handler: never leak internal stack traces to clients
    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error("Internal error processing request %s: %s", request.url.path, exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "An internal error occurred during processing.",
                "disclaimer": DISCLAIMER,
            },
        )

    # Include API routers under /api
    app.include_router(health_router, prefix="/api")
    app.include_router(scenarios_router, prefix="/api")
    app.include_router(triage_router, prefix="/api")
    app.include_router(registry_router, prefix="/api")
    app.include_router(protocols_router, prefix="/api")
    app.include_router(audit_router, prefix="/api")
    app.include_router(corpus_router, prefix="/api")
    app.include_router(eval_router, prefix="/api")
    app.include_router(health_router, prefix="")

    @app.get("/api")
    def api_info() -> dict[str, str]:
        return {
            "name": "TriageRAG Clinical API",
            "version": "0.1.0",
            "disclaimer": DISCLAIMER,
            "docs": "/docs",
        }

    # Serve built SPA frontend if available
    dist_dir = Path(__file__).resolve().parent.parent.parent.parent / "web" / "dist"
    if dist_dir.exists() and (dist_dir / "index.html").exists():
        assets_dir = dist_dir / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

        @app.get("/{full_path:path}")
        async def serve_spa(full_path: str) -> FileResponse:
            target = dist_dir / full_path
            if full_path and target.is_file():
                return FileResponse(target)
            return FileResponse(dist_dir / "index.html")
    else:

        @app.get("/")
        def root() -> dict[str, str]:
            return {
                "name": "TriageRAG Clinical API",
                "version": "0.1.0",
                "disclaimer": DISCLAIMER,
                "docs": "/docs",
            }

    return app


app = create_app()
