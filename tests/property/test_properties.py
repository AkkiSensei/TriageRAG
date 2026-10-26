"""Hypothesis property-based tests for safety invariants.

Safety Properties (Rules R1, R2, R8, R12):
1. Unit conversions round-trip (e.g. mcg <-> mg <-> g) within Decimal precision.
2. Magnitude tripwires: any dose >= 10x or <= 0.1x of reference always triggers tripwire.
3. Fail-closed: any skip or unresolved entity guarantees the verdict is NEVER CHECKED_CLEAR.
4. Ordering stability: alerts are deterministically sorted regardless of rule evaluation order.
"""

from __future__ import annotations

from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from triagerag.contracts.enums import DoseUnit, Severity, Verdict
from triagerag.contracts.schemas import Alert, ExplicitDose, Provenance
from triagerag.engine.rule_engine import _sort_alerts
from triagerag.engine.verdict import resolve_verdict
from triagerag.normalize.units import check_magnitude_tripwire, convert_dose


# 1. Unit conversion round-trips (mcg <-> mg, mg <-> g)
@given(
    amount=st.decimals(
        min_value=Decimal("0.001"),
        max_value=Decimal("100000.0"),
        places=3,
        allow_nan=False,
        allow_infinity=False,
    )
)
def test_unit_conversion_round_trip_mcg_mg(amount: Decimal) -> None:
    """Converting mcg -> mg -> mcg returns the exact original Decimal."""
    d = ExplicitDose(amount=amount, unit=DoseUnit.mcg)
    to_mg = convert_dose(d, DoseUnit.mg)
    back_to_mcg = convert_dose(to_mg, DoseUnit.mcg)
    assert back_to_mcg.amount == amount


@given(
    amount=st.decimals(
        min_value=Decimal("0.001"),
        max_value=Decimal("100000.0"),
        places=3,
        allow_nan=False,
        allow_infinity=False,
    )
)
def test_unit_conversion_round_trip_mg_g(amount: Decimal) -> None:
    """Converting mg -> g -> mg returns the exact original Decimal."""
    d = ExplicitDose(amount=amount, unit=DoseUnit.mg)
    to_g = convert_dose(d, DoseUnit.g)
    back_to_mg = convert_dose(to_g, DoseUnit.mg)
    assert back_to_mg.amount == amount


# 2. Magnitude tripwires
@given(
    reference=st.decimals(
        min_value=Decimal("1.0"),
        max_value=Decimal("1000.0"),
        places=2,
        allow_nan=False,
        allow_infinity=False,
    ),
    multiplier=st.decimals(
        min_value=Decimal("10.0"),
        max_value=Decimal("1000.0"),
        places=2,
        allow_nan=False,
        allow_infinity=False,
    ),
)
def test_magnitude_tripwire_high_deviation(reference: Decimal, multiplier: Decimal) -> None:
    """Any dose >= 10x reference must trip the magnitude tripwire."""
    requested = reference * multiplier
    assert check_magnitude_tripwire(requested, reference) is True


@given(
    reference=st.decimals(
        min_value=Decimal("1.0"),
        max_value=Decimal("1000.0"),
        places=2,
        allow_nan=False,
        allow_infinity=False,
    ),
    multiplier=st.decimals(
        min_value=Decimal("0.001"),
        max_value=Decimal("0.100"),
        places=3,
        allow_nan=False,
        allow_infinity=False,
    ),
)
def test_magnitude_tripwire_low_deviation(reference: Decimal, multiplier: Decimal) -> None:
    """Any dose <= 0.1x reference must trip the magnitude tripwire."""
    requested = reference * multiplier
    assert check_magnitude_tripwire(requested, reference) is True


# 3. Fail-Closed: Any skip guarantees verdict is NEVER CHECKED_CLEAR
@given(
    has_block=st.booleans(),
    has_alert=st.booleans(),
)
def test_fail_closed_skip_never_checked_clear(has_block: bool, has_alert: bool) -> None:
    """Rule R2: When has_skip_or_unresolved=True, verdict is NEVER CHECKED_CLEAR."""
    verdict = resolve_verdict(
        has_block=has_block,
        has_skip_or_unresolved=True,
        has_alert=has_alert,
    )
    assert verdict != Verdict.CHECKED_CLEAR
    assert verdict in (Verdict.BLOCKED, Verdict.UNVERIFIED)


# 4. Ordering stability of alerts
@given(
    severities=st.lists(
        st.sampled_from([Severity.BLOCK, Severity.HIGH, Severity.MODERATE, Severity.INFO]),
        min_size=1,
        max_size=20,
    )
)
def test_alert_ordering_stability(severities: list[Severity]) -> None:
    """Alerts are deterministically ordered by severity (BLOCK > HIGH > MODERATE > INFO)
    then by rule_id.
    """
    prov = Provenance(
        source_doc="TEST",
        section_ref="T1",
        version_or_date="2026",
    )
    alerts = [
        Alert(
            rule_id=f"RULE_{i:03d}",
            severity=sev,
            rule_type="test",
            consequence="Test consequence",
            action="Test action",
            provenance=prov,
        )
        for i, sev in enumerate(severities)
    ]

    sorted_once = _sort_alerts(alerts)
    # Permute and sort again
    import random

    permuted = list(alerts)
    random.shuffle(permuted)
    sorted_twice = _sort_alerts(permuted)

    # Output ordering must be identical
    assert [a.rule_id for a in sorted_once] == [a.rule_id for a in sorted_twice]
