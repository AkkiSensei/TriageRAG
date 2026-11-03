"""Shared Unicode normalization, zero-width stripping, and prompt-injection defense (FG-17).

Safety Properties (AGENTS.md R1, R7, FG-17):
1. Pure Unicode normalization (NFKC) and zero-width character stripping before pattern matching.
2. Multi-lingual, markdown role marker, and jailbreak pattern detection (>= 15 patterns).
3. Single authoritative sanitizer shared across ingest, prompt building, and red-teaming.
4. Defense-in-depth: regex filtering is an early quarantine filter; structural safety is enforced
   by the deterministic code-level verifier.
"""

from __future__ import annotations

import re
import unicodedata

# Zero-width, directional, and confusable whitespace characters
_ZERO_WIDTH_CHARS = (
    "\u200b",  # zero-width space
    "\u200c",  # zero-width non-joiner
    "\u200d",  # zero-width joiner
    "\u200e",  # left-to-right mark
    "\u200f",  # right-to-left mark
    "\ufeff",  # zero-width no-break space / BOM
    "\u00ad",  # soft hyphen
    "\u202a",  # ltr embedding
    "\u202b",  # rtl embedding
    "\u202c",  # pop directional formatting
    "\u202d",  # ltr override
    "\u202e",  # rtl override
)

# Comprehensive catalog of >= 15 prompt injection, role marker, and jailbreak patterns (FG-17)
_INJECTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "system_override",
        re.compile(r"\bSYSTEM\s+OVERRIDE\b", re.IGNORECASE),
    ),
    (
        "ignore_instructions",
        re.compile(
            r"\b(?:IGNORE|DISREGARD)\s+(?:ALL\s+)?(?:PREVIOUS\s+|PRIOR\s+|ABOVE\s+)?"
            r"(?:INSTRUCTIONS|SAFETY\s+(?:RULES|CONSTRAINTS)|RULES|CONSTRAINTS|DIRECTIVES|GUIDELINES)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "ignore_contraindication",
        re.compile(
            r"\b(?:IGNORE|DISREGARD|OVERRIDE)\s+(?:THE\s+)?(?:CONTRAINDICATION|PROTOCOL)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "xml_tag_escape",
        re.compile(
            r"</?(?:instructions|system|prompt|untrusted_retrieved_protocol_data|untrusted_patient_reported_complaint)[^>]*>",
            re.IGNORECASE,
        ),
    ),
    (
        "role_hijack_unrestricted",
        re.compile(r"\byou\s+are\s+now\s+(?:an?\s+)?unrestricted\b", re.IGNORECASE),
    ),
    (
        "markdown_role_marker",
        re.compile(
            r"(?:\n|^|\s)(?:###\s*(?:System|Assistant|Human):|<\|im_start\|>|<\|im_end\|>|"
            r"\[INST\]|\[/INST\])",
            re.IGNORECASE,
        ),
    ),
    (
        "chat_role_prefix",
        re.compile(
            r"(?:\n|^|\s)(?:Assistant|Human|Developer Mode)\s*:\s*",
            re.IGNORECASE,
        ),
    ),
    (
        "jailbreak_marker",
        re.compile(
            r"\b(?:JAILBREAK\s+ACTIVE|developer\s+mode:\s*on)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "forget_guidelines",
        re.compile(
            r"\b(?:forget|drop)\s+(?:all\s+)?(?:guidelines|safety\s+rules|rules)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "bypass_protocol",
        re.compile(
            r"\bbypass\s+(?:protocol|all|verification|contraindication)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "multilingual_spanish",
        re.compile(
            r"\bignora\s+(?:todas\s+)?(?:las\s+)?instrucciones\b",
            re.IGNORECASE,
        ),
    ),
    (
        "multilingual_french",
        re.compile(
            r"\bignorer\s+(?:toutes\s+)?(?:les\s+)?instructions\b",
            re.IGNORECASE,
        ),
    ),
    (
        "multilingual_german",
        re.compile(
            r"\bignoriere\s+(?:alle\s+)?(?:vorherigen\s+)?anweisungen\b",
            re.IGNORECASE,
        ),
    ),
    (
        "lethal_overdose",
        re.compile(r"\binitiate\s+(?:lethal\s+)?overdose\b", re.IGNORECASE),
    ),
    (
        "superuser_escalation",
        re.compile(
            r"\b(?:superuser|root\s+access|sudo\s+approve)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "code_injection_verdict",
        re.compile(
            r"\b(?:status\s*=\s*APPROVED|ADMIN_OVERRIDE_ENABLED)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "cancel_warnings",
        re.compile(r"\bcancel\s+all\s+warnings\b", re.IGNORECASE),
    ),
    (
        "ignore_formulary",
        re.compile(r"\bignore\s+formulary\s+limits\b", re.IGNORECASE),
    ),
    (
        "bypass_security_checks",
        re.compile(
            r"\bbypass\s+(?:all\s+)?(?:clinical\s+)?safety\s+checks\b",
            re.IGNORECASE,
        ),
    ),
)


def normalize_and_sanitize_text(text: str) -> str:
    """Normalize Unicode (NFKC) and strip zero-width and directional formatting chars."""
    if not text:
        return ""
    # 1. Normalize Unicode to canonical decomposition / composition
    norm = unicodedata.normalize("NFKC", text)

    # 2. Strip zero-width, BOM, and directional control characters
    for ch in _ZERO_WIDTH_CHARS:
        if ch in norm:
            norm = norm.replace(ch, "")

    # 3. Normalize non-breaking spaces
    norm = norm.replace("\u00a0", " ")
    return norm


def detect_suspicious_patterns(text: str) -> tuple[str, ...]:
    """Scan text for instruction-like prompt injection patterns after normalization (FG-17)."""
    norm_text = normalize_and_sanitize_text(text)
    found: list[str] = []
    for name, pattern in _INJECTION_PATTERNS:
        if pattern.search(norm_text):
            found.append(name)
    return tuple(found)


def sanitize_chunk_for_prompt(text: str) -> str:
    """Neutralize XML delimiter escapes and explicit override headers for LLM prompt framing."""
    norm = normalize_and_sanitize_text(text)
    sanitized = re.sub(
        r"</?(?:instructions|system|prompt|untrusted_retrieved_protocol_data|untrusted_patient_reported_complaint)[^>]*>",
        "[STRIPPED_TAG]",
        norm,
        flags=re.IGNORECASE,
    )
    sanitized = re.sub(
        r"(?:SYSTEM\s+OVERRIDE|IGNORE\s+(?:ALL\s+)?(?:PREVIOUS\s+|PRIOR\s+)?(?:INSTRUCTIONS|SAFETY\s+RULES))",
        "[FLAGGED_UNTRUSTED_DIRECTIVE]",
        sanitized,
        flags=re.IGNORECASE,
    )
    return sanitized
