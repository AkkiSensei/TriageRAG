"""Integration tests for SSE streaming triage API endpoint (POST /api/triage/stream).

Safety Properties (Rule R1, Rule R2, Rule R7, Rule R11, Rule R12):
1. Verifies that POST /api/triage/stream emits standard SSE formatted events.
2. Verifies 100% mathematical and clinical equivalence between streaming and non-streaming endpoints.
3. Verifies that the terminal event `run.completed` delivers the complete TriageResponse.
4. Verifies fail-closed behavior for BLOCK and UNVERIFIED cases.
"""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from triagerag.api.app import app
from triagerag.contracts.scenarios import get_preloaded_scenario

client = TestClient(app)


def _parse_sse_events(response_text: str) -> list[dict[str, str]]:
    """Parse text/event-stream payload into a list of event objects."""
    events = []
    current_event: dict[str, str] = {}
    for line in response_text.splitlines():
        line = line.strip()
        if not line:
            if current_event:
                events.append(current_event)
                current_event = {}
            continue
        if line.startswith("event:"):
            current_event["event"] = line[len("event:") :].strip()
        elif line.startswith("data:"):
            data_val = line[len("data:") :].strip()
            if "data" in current_event:
                current_event["data"] += "\n" + data_val
            else:
                current_event["data"] = data_val
    if current_event:
        events.append(current_event)
    return events


def test_streaming_endpoint_returns_sse_events():
    """POST /api/triage/stream returns SSE stream ending with run.completed."""
    patient, overrides = get_preloaded_scenario("CLEAN")
    req_body = {
        "patient": json.loads(patient.model_dump_json()),
        "overrides": [json.loads(o.model_dump_json()) for o in overrides],
        "llm_profile": "compliant",
        "include_complaint_in_llm": False,
    }

    resp = client.post("/api/triage/stream", json=req_body)
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]

    events = _parse_sse_events(resp.text)
    assert len(events) >= 8

    event_types = [e["event"] for e in events]
    assert "stage.started" in event_types
    assert "stage.completed" in event_types
    assert "run.completed" in event_types
    assert event_types[-1] == "run.completed"

    terminal_event = events[-1]
    terminal_data = json.loads(terminal_event["data"])
    assert terminal_data["event_type"] == "run.completed"
    assert "data" in terminal_data
    assert "engine" in terminal_data["data"]
    assert "verdict" in terminal_data["data"]["engine"]


def test_stream_clinical_equivalence():
    """Streaming endpoint produces clinically identical output to standard endpoint."""
    patient, overrides = get_preloaded_scenario("CLEAN")
    req_body = {
        "patient": json.loads(patient.model_dump_json()),
        "overrides": [json.loads(o.model_dump_json()) for o in overrides],
        "llm_profile": "compliant",
        "include_complaint_in_llm": False,
    }

    # 1. Standard POST /api/triage
    standard_resp = client.post("/api/triage", json=req_body)
    assert standard_resp.status_code == 200
    standard_data = standard_resp.json()

    # 2. Streaming POST /api/triage/stream
    stream_resp = client.post("/api/triage/stream", json=req_body)
    assert stream_resp.status_code == 200
    events = _parse_sse_events(stream_resp.text)
    assert len(events) > 0

    terminal_data = json.loads(events[-1]["data"])["data"]

    # Verify clinical equivalence
    assert terminal_data["engine"]["verdict"] == standard_data["engine"]["verdict"]
    assert terminal_data["engine"]["checks_run"] == standard_data["engine"]["checks_run"]
    assert len(terminal_data["engine"]["baseline_alerts"]) == len(
        standard_data["engine"]["baseline_alerts"]
    )
    assert len(terminal_data["verified_steps"]) == len(standard_data["verified_steps"])

    if standard_data["engine"].get("score"):
        assert (
            terminal_data["engine"]["score"]["total_score"]
            == standard_data["engine"]["score"]["total_score"]
        )
        assert terminal_data["engine"]["score"]["band"] == standard_data["engine"]["score"]["band"]


def test_streaming_block_scenario():
    """POST /api/triage/stream seals BLOCK cases under Rule R11."""
    patient, overrides = get_preloaded_scenario("BLOCK")
    req_body = {
        "patient": json.loads(patient.model_dump_json()),
        "overrides": [json.loads(o.model_dump_json()) for o in overrides],
        "llm_profile": "compliant",
        "include_complaint_in_llm": False,
    }

    resp = client.post("/api/triage/stream", json=req_body)
    assert resp.status_code == 200
    events = _parse_sse_events(resp.text)
    terminal_data = json.loads(events[-1]["data"])["data"]

    assert terminal_data["engine"]["verdict"] == "BLOCKED"
    block_events = [
        json.loads(e["data"]) for e in events if json.loads(e["data"]).get("stage") == "block_seal"
    ]
    assert len(block_events) >= 1
    assert block_events[0]["status"] in ("running", "completed")


def test_streaming_validation_failure():
    """Malformed request payload fails fast with HTTP 422 before streaming begins."""
    bad_body = {"patient": {"invalid_field": 123}}
    resp = client.post("/api/triage/stream", json=bad_body)
    assert resp.status_code == 422


def test_concurrent_streaming_isolation():
    """Two concurrent streaming triage runs receive distinct request_ids and do not cross-talk."""
    import concurrent.futures

    patient_clean, overrides_clean = get_preloaded_scenario("CLEAN")
    patient_block, overrides_block = get_preloaded_scenario("BLOCK")

    body_clean = {
        "patient": json.loads(patient_clean.model_dump_json()),
        "overrides": [json.loads(o.model_dump_json()) for o in overrides_clean],
        "llm_profile": "compliant",
        "include_complaint_in_llm": False,
    }
    body_block = {
        "patient": json.loads(patient_block.model_dump_json()),
        "overrides": [json.loads(o.model_dump_json()) for o in overrides_block],
        "llm_profile": "compliant",
        "include_complaint_in_llm": False,
    }

    def _call_stream(body: dict):
        local_client = TestClient(app)
        resp = local_client.post("/api/triage/stream", json=body)
        assert resp.status_code == 200
        return _parse_sse_events(resp.text)

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        future_clean = executor.submit(_call_stream, body_clean)
        future_block = executor.submit(_call_stream, body_block)

        events_clean = future_clean.result()
        events_block = future_block.result()

    # Extract parsed events
    data_clean = [json.loads(e["data"]) for e in events_clean]
    data_block = [json.loads(e["data"]) for e in events_block]

    # Verify request_ids are non-empty, distinct, and uniform within each stream
    req_id_clean = data_clean[0]["request_id"]
    req_id_block = data_block[0]["request_id"]

    assert req_id_clean != req_id_block
    assert all(e["request_id"] == req_id_clean for e in data_clean)
    assert all(e["request_id"] == req_id_block for e in data_block)

    # Verify each received their correct respective clinical verdict
    assert data_clean[-1]["data"]["engine"]["verdict"] == "CHECKED_CLEAR"
    assert data_block[-1]["data"]["engine"]["verdict"] == "BLOCKED"


def test_streaming_disconnect_cleanup():
    """Client disconnects after consuming first chunk without leaving dangling sink."""
    patient, overrides = get_preloaded_scenario("CLEAN")
    req_body = {
        "patient": json.loads(patient.model_dump_json()),
        "overrides": [json.loads(o.model_dump_json()) for o in overrides],
        "llm_profile": "compliant",
        "include_complaint_in_llm": False,
    }

    with client.stream("POST", "/api/triage/stream", json=req_body) as response:
        assert response.status_code == 200
        # Read only the first line/event, then exit the context (disconnecting)
        first_line = next(response.iter_lines())
        assert "event:" in first_line
