"""Registry and rules explorer endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from triagerag.api.routes.triage import get_cached_registry
from triagerag.api.schemas import RegistrySummaryResponse, RuleSummaryDto
from triagerag.contracts.enums import SourceStatus

router = APIRouter(prefix="/registry", tags=["registry"])


@router.get("/summary", response_model=RegistrySummaryResponse)
def get_registry_summary() -> RegistrySummaryResponse:
    registry = get_cached_registry()

    by_severity: dict[str, int] = {}
    by_source_status: dict[str, int] = {}
    unreviewed = 0

    for rule in registry.rules:
        sev = str(rule.severity.value).upper()
        by_severity[sev] = by_severity.get(sev, 0) + 1

        src_status = str(rule.provenance.source_status.value).upper()
        by_source_status[src_status] = by_source_status.get(src_status, 0) + 1

        if rule.provenance.source_status != SourceStatus.REVIEWED:
            unreviewed += 1

    return RegistrySummaryResponse(
        formulary_drugs_count=len(registry.formulary_drugs),
        rules_count=len(registry.rules),
        rules_by_severity=by_severity,
        rules_by_source_status=by_source_status,
        aliases_count=len(registry.aliases),
        acronyms_count=len(registry.acronyms.acronyms),
        coverage_gaps=registry.coverage_gaps,
        unreviewed_count=unreviewed,
    )


@router.get("/rules", response_model=list[RuleSummaryDto])
def list_rules() -> list[RuleSummaryDto]:
    registry = get_cached_registry()
    rules_dto: list[RuleSummaryDto] = []

    for rule in registry.rules:
        dto = RuleSummaryDto(
            id=rule.id,
            rule_type=str(getattr(rule, "type", rule.__class__.__name__)),
            severity=rule.severity.value,
            status=rule.status.value,
            source_status=rule.provenance.source_status.value,
            content_origin=rule.provenance.content_origin.value,
            verified=rule.provenance.verified,
            requires_fields=rule.requires_fields,
            consequence=rule.consequence,
            action=rule.action,
        )
        rules_dto.append(dto)

    return rules_dto
