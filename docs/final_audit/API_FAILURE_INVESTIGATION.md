# Forensic Investigation: API Request Behavior & Shell Tokenization Analysis

> **DISCLAIMER:** Research prototype. Synthetic data only. Not a medical device. Not for clinical use.

---

## 1. Executive Summary

During manual verification in Turn 11, a CLI `curl` command executed from PowerShell returned HTTP `422 Unprocessable Content` with exit code `1`, while a subsequent identical JSON payload sent via Python `urllib.request` succeeded immediately with HTTP `200 OK` and verdict `BLOCKED`.

A forensic investigation was conducted to determine whether this observed behavior was caused by server instability, race conditions, or client-side payload corruption.

**Conclusion:** The backend server remained 100% stable throughout the session. The initial request failure was caused by client-side shell tokenization in PowerShell: unescaped backslash-quotes (`\"`) inside a double-quoted string resulted in payload truncation to `b"{\\"`. The FastAPI backend correctly intercepted this invalid JSON, returned HTTP 422, injected safe W3C telemetry headers, and emitted zero internal LangGraph node spans. Subsequent requests succeeded without restart.

---

## 2. Forensic Evidence & Server Logs

### A. Uvicorn Server Access Logs (Process PID 8396)
```text
INFO:     127.0.0.1:57748 - "GET /api/scenarios HTTP/1.1" 200 OK
INFO:     127.0.0.1:57750 - "GET /api/scenarios/BLOCK HTTP/1.1" 200 OK
Validation error on /api/triage: [{'field': 'body -> 1', 'message': 'JSON decode error'}]
INFO:     127.0.0.1:57711 - "POST /api/triage HTTP/1.1" 422 Unprocessable Content
INFO:     127.0.0.1:57712 - "GET /api/scenarios/BLOCK HTTP/1.1" 200 OK
INFO:     127.0.0.1:57713 - "POST /api/triage HTTP/1.1" 200 OK
```

### B. Raw Received Body Probe
A local HTTP probe listening on loopback intercepted the exact string delivered by PowerShell's `curl.exe` invocation:
```text
RECEIVED RAW BODY:
{\
```

### C. Client Command Line
```powershell
curl.exe -i -s -X POST http://127.0.0.1:8000/api/triage -H "Content-Type: application/json" -d "{\"patient\": ...}" | Select-Object -First 15
```

---

## 3. Root Cause Analysis

1. **PowerShell Argument Parsing (`\"` in Double Quotes):**
   - In PowerShell, backslash (`\`) is not the escape character; backtick (`` ` ``) is.
   - When PowerShell parses `-d "{\"patient\": ...}"`, it interprets `\"` as an escape for `"`, but in parameter binding to native Windows executables (`curl.exe`), the quotes are stripped or tokenized incorrectly.
   - As demonstrated by the loopback probe, `curl.exe` transmitted only the leading two bytes: `b"{\\"`.

2. **Backend Fast Fail-Closed Interception:**
   - FastAPI received the body `b"{\\"`.
   - Python's standard `json.loads` raised `json.decoder.JSONDecodeError: Expecting property name enclosed in double quotes: line 1 column 2 (char 1)`.
   - FastAPI's `RequestValidationError` handler in `src/triagerag/api/app.py` intercepted the error before the request could reach the triage orchestrator or LangGraph state machine.
   - The ASGI `tracing_middleware` recorded `http.status_code: 422`, injected W3C `traceparent` and `X-Trace-Id` headers into the response, and closed the root span without invoking LangGraph (0 internal node spans emitted).

3. **Client Exit Code:**
   - The command piped output to `Select-Object -First 15`. When PowerShell's pipeline receives the first 15 lines, it terminates the pipe downstream. Native Windows executables writing to a closed stdout handle raise an error or set `$LASTEXITCODE = 1`.

---

## 4. Verification & Regression Coverage

The issue is fully covered by automated regression tests in [`tests/integration/test_api_stability_and_malformed_json.py`](file:///c:/Users/Ritunjay%20Deo/OneDrive/Desktop/TriageRAG/tests/integration/test_api_stability_and_malformed_json.py):

1. `test_reproduce_exact_truncated_json_payload_422`:
   - Submits `b"{\\"` directly to `/api/triage`.
   - Asserts response is HTTP 422 with `JSON decode error`.
   - Asserts safe W3C headers (`traceparent`, `x-trace-id`) are present.
   - Asserts zero internal node spans (`langgraph.node.*`) are emitted.
2. `test_server_stability_subsequent_request_succeeds_with_200`:
   - Immediately submits a valid `BLOCK` scenario JSON payload to the same server process.
   - Asserts response is HTTP 200 with verdict `BLOCKED`.
   - Asserts all 8 operational node spans execute and export cleanly.

