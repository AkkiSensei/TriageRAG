"""Tests for GeminiProvider configuration, timeout, and bounded retry hardening."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest


def test_gemini_provider_requires_api_key() -> None:
    from triagerag.llm.gemini import GeminiProvider

    with (
        patch.dict("os.environ", {}, clear=True),
        pytest.raises(ValueError, match="GEMINI_API_KEY environment variable is required"),
    ):
        GeminiProvider()


def test_gemini_provider_model_name_reconciliation() -> None:
    """Verifies that TRIAGERAG_MODEL_NAME takes precedence over GEMINI_MODEL."""
    from triagerag.llm.gemini import GeminiProvider

    mock_genai = MagicMock()
    mock_google = MagicMock()
    mock_google.genai = mock_genai

    with (
        patch.dict(
            "os.environ",
            {
                "GEMINI_API_KEY": "fake_key",
                "TRIAGERAG_MODEL_NAME": "custom-triagerag-model",
                "GEMINI_MODEL": "default-gemini-model",
            },
        ),
        patch.dict(sys.modules, {"google": mock_google, "google.genai": mock_genai}),
    ):
        provider = GeminiProvider(timeout_seconds=25.0)
        assert provider.model_name == "custom-triagerag-model"
        assert provider.timeout_seconds == 25.0
        mock_genai.Client.assert_called_once_with(
            api_key="fake_key",
            http_options={"timeout": 25000},
        )


def test_gemini_provider_retry_on_transient_failure() -> None:
    """Verifies bounded retry logic on transient errors."""
    from triagerag.contracts.enums import PopulationCategory
    from triagerag.contracts.schemas import PlanContext
    from triagerag.llm.gemini import GeminiProvider

    mock_client = MagicMock()
    # First attempt fails, second attempt succeeds
    mock_response = MagicMock()
    mock_response.text = '{"matched_protocol_title": "Test", "steps": []}'
    mock_client.models.generate_content.side_effect = [
        RuntimeError("Transient network glitch"),
        mock_response,
    ]

    mock_genai = MagicMock()
    mock_genai.Client.return_value = mock_client
    mock_google = MagicMock()
    mock_google.genai = mock_genai

    with (
        patch.dict("os.environ", {"GEMINI_API_KEY": "fake_key"}),
        patch.dict(sys.modules, {"google": mock_google, "google.genai": mock_genai}),
        patch("time.sleep", return_value=None),
    ):
        provider = GeminiProvider()
        context = PlanContext(
            population_category=PopulationCategory.adult,
            allowed_drug_ids=["epinephrine"],
            retrieved_chunks=[],
        )
        plan = provider.draft_plan(context)
        assert plan.matched_protocol_title == "Test"
        assert mock_client.models.generate_content.call_count == 2
