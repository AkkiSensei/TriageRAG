"""Reproducible latency benchmark comparing TriageRAG telemetry configurations.

Safety Property (R12, Determinism):
Measures execution latency across N repeated triage graph invocations under
controlled, pure synthetic patient inputs without network calls or mutable global state.
Evaluates overhead of OpenTelemetry instrumentation relative to disabled baseline.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import statistics
import time
from pathlib import Path
from typing import Any

from triagerag.config import get_data_dir
from triagerag.contracts.scenarios import get_preloaded_scenario
from triagerag.contracts.schemas import FixedClock
from triagerag.engine.registry import load_registry
from triagerag.llm.fake import FakeLLM, FakeLLMProfile
from triagerag.orchestration.langgraph_workflow import run_triage_graph
from triagerag.orchestration.telemetry import TelemetryManager
from triagerag.rag.service import RetrievalService

REPO_ROOT = Path(__file__).resolve().parent.parent


def _run_single_triage(
    patient: Any,
    overrides: list[Any],
    registry: Any,
    retriever: Any,
    llm: Any,
    clock: Any,
) -> float:
    """Execute one triage workflow run and return elapsed duration in milliseconds."""
    t0 = time.perf_counter()
    resp, _ = run_triage_graph(
        patient=patient,
        overrides=overrides,
        registry=registry,
        index=retriever,
        llm=llm,
        clock=clock,
    )
    t1 = time.perf_counter()
    assert resp is not None
    return (t1 - t0) * 1000.0


def benchmark_configuration(
    config_name: str,
    env_vars: dict[str, str],
    iterations: int = 100,
    warmup: int = 10,
) -> dict[str, Any]:
    """Run benchmark iterations for a specific telemetry environment configuration."""
    # Apply environment
    old_env = {}
    for k, v in env_vars.items():
        old_env[k] = os.environ.get(k)
        os.environ[k] = v

    try:
        # Re-initialize TelemetryManager
        manager = TelemetryManager.get_instance()
        manager.shutdown()
        manager.initialize()

        patient, overrides = get_preloaded_scenario("CLEAN")
        registry = load_registry(get_data_dir())
        service = RetrievalService.create_default(get_data_dir(), backend="bm25")
        retriever = service.index
        llm = FakeLLM(profile=FakeLLMProfile.COMPLIANT)
        clock = FixedClock(patient.assessed_at)

        # Warmup
        for _ in range(warmup):
            _run_single_triage(patient, overrides, registry, retriever, llm, clock)

        # Timed runs
        latencies: list[float] = []
        # Suppress console exporter output to isolate telemetry instrumentation overhead
        # from terminal I/O streaming latency
        with contextlib.redirect_stdout(io.StringIO()):
            for _ in range(iterations):
                dur = _run_single_triage(patient, overrides, registry, retriever, llm, clock)
                latencies.append(dur)

        sorted_lat = sorted(latencies)
        mean_val = statistics.mean(latencies)
        median_val = statistics.median(latencies)
        stdev_val = statistics.stdev(latencies) if len(latencies) > 1 else 0.0

        p95_idx = int(0.95 * len(sorted_lat))
        p99_idx = int(0.99 * len(sorted_lat))
        p95_val = sorted_lat[min(p95_idx, len(sorted_lat) - 1)]
        p99_val = sorted_lat[min(p99_idx, len(sorted_lat) - 1)]
        max_val = max(latencies)
        min_val = min(latencies)

        return {
            "config": config_name,
            "iterations": iterations,
            "mean_ms": round(mean_val, 3),
            "median_p50_ms": round(median_val, 3),
            "p95_ms": round(p95_val, 3),
            "p99_ms": round(p99_val, 3),
            "max_ms": round(max_val, 3),
            "min_ms": round(min_val, 3),
            "stdev_ms": round(stdev_val, 3),
        }
    finally:
        # Restore environment
        for k, old_v in old_env.items():
            if old_v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = old_v
        TelemetryManager.get_instance().shutdown()


def run_all_benchmarks(
    iterations: int = 100,
    warmup: int = 10,
    out_file: Path | None = None,
) -> list[dict[str, Any]]:
    """Run benchmarks across all primary configurations."""
    configs = [
        (
            "Config 1: Telemetry Disabled",
            {"TRIAGERAG_TELEMETRY_ENABLED": "false"},
        ),
        (
            "Config 2: In-Memory Tracing",
            {
                "TRIAGERAG_TELEMETRY_ENABLED": "true",
                "TRIAGERAG_TELEMETRY_EXPORTER": "in_memory",
            },
        ),
        (
            "Config 3: Console Exporter",
            {
                "TRIAGERAG_TELEMETRY_ENABLED": "true",
                "TRIAGERAG_TELEMETRY_EXPORTER": "console",
            },
        ),
    ]

    results: list[dict[str, Any]] = []
    print("=" * 80)
    print(f"TRIAGERAG OPENTELEMETRY LATENCY BENCHMARK (N={iterations}, Warmup={warmup})")
    print("=" * 80)

    for name, env_vars in configs:
        print(f"--> Benchmarking {name} ...")
        res = benchmark_configuration(name, env_vars, iterations=iterations, warmup=warmup)
        results.append(res)

    print("\n" + "=" * 80)
    print("BENCHMARK RESULTS SUMMARY (in milliseconds)")
    print("=" * 80)
    header = (
        f"| {'Configuration':<32} | {'Mean (ms)':<9} | {'P50 (ms)':<8} | "
        f"{'P95 (ms)':<8} | {'P99 (ms)':<8} | {'Max (ms)':<8} | {'StdDev':<7} |"
    )
    separator = f"|{'-' * 34}|{'-' * 11}|{'-' * 10}|{'-' * 10}|{'-' * 10}|{'-' * 10}|{'-' * 9}|"
    print(header)
    print(separator)
    for r in results:
        row = (
            f"| {r['config']:<32} | {r['mean_ms']:<9.3f} | {r['median_p50_ms']:<8.3f} | "
            f"{r['p95_ms']:<8.3f} | {r['p99_ms']:<8.3f} | {r['max_ms']:<8.3f} | {r['stdev_ms']:<7.3f} |"
        )
        print(row)
    print("=" * 80)

    # Overhead analysis relative to disabled baseline
    disabled_p95 = results[0]["p95_ms"]
    disabled_mean = results[0]["mean_ms"]
    print("\nOVERHEAD ANALYSIS (relative to Telemetry Disabled):")
    for r in results[1:]:
        mean_delta = r["mean_ms"] - disabled_mean
        p95_delta = r["p95_ms"] - disabled_p95
        print(
            f"  * {r['config']}: Mean delta = +{mean_delta:.3f} ms, P95 delta = +{p95_delta:.3f} ms"
        )

    if out_file:
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"\n[OK] Benchmark report written to {out_file}")

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="TriageRAG OpenTelemetry latency benchmark")
    parser.add_argument(
        "-n", "--iterations", type=int, default=100, help="Number of benchmark iterations"
    )
    parser.add_argument("-w", "--warmup", type=int, default=10, help="Number of warmup iterations")
    parser.add_argument(
        "--out",
        type=Path,
        default=REPO_ROOT / "eval/reports/telemetry_benchmark.json",
        help="Report output path",
    )
    args = parser.parse_args()

    run_all_benchmarks(
        iterations=args.iterations,
        warmup=args.warmup,
        out_file=args.out,
    )


if __name__ == "__main__":
    main()
