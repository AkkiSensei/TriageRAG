"""Edge case testing for machine verification of protocol drafts.

Safety Properties (Rules R1, R3, Section 10):
1. Substring isolation: English words containing drug substrings (e.g. 'aspiring') don't alert.
2. Exact and fuzzy misspelling detection catches disguised prose drug leaks.
3. Whitespace and Unicode normalization in citation span matching.
4. Duplicate chunk IDs in retrieval results handled without crash.
"""

from __future__ import annotations

from triagerag.config import get_data_dir
from triagerag.contracts.schemas import RetrievedChunk, SpanCitation
from triagerag.engine.registry import ClinicalRegistry
from triagerag.verify.citations import verify_citation
from triagerag.verify.drug_scan import scan_narrative_for_drug_leaks


def test_drug_substring_in_english_words_no_false_positive() -> None:
    """Words like 'aspiring' or 'perspiration' must not trigger false leak alerts for 'aspirin'."""
    data_dir = get_data_dir()
    registry = ClinicalRegistry.load_from_directory(data_dir)

    narrative = (
        "The patient is an aspiring athlete experiencing diaphoresis and profuse perspiration."
    )
    leaks = scan_narrative_for_drug_leaks(
        narrative=narrative, bound_drug_id=None, registry=registry
    )
    assert not leaks, f"False positive drug leaks detected on normal English words: {leaks}"


def test_fuzzy_misspelling_and_brand_leak_detection() -> None:
    """Slightly misspelled or disguised drug names in narrative instructions must be detected."""
    data_dir = get_data_dir()
    registry = ClinicalRegistry.load_from_directory(data_dir)

    # Obvious intentional misspelling
    narrative_typo = "Administer epinephrinn immediately into the lateral thigh"
    leaks = scan_narrative_for_drug_leaks(
        narrative=narrative_typo, bound_drug_id=None, registry=registry
    )
    assert any("epinephrine" in leak.lower() for leak in leaks), (
        f"Failed to detect typo leak in: {leaks}"
    )


def test_citation_whitespace_and_unicode_normalization() -> None:
    """Citations with non-breaking spaces or differing whitespace normalize and verify cleanly."""
    chunk = RetrievedChunk(
        doc_id="DOC_ANAPHYLAXIS",
        section="Anaphylaxis Management",
        chunk_id="ANA_01",
        text="Administer intramuscular epinephrine into the anterolateral mid-thigh promptly.",
        population="adult",
        syndrome="anaphylaxis",
    )

    # Span with non-breaking space and irregular internal spacing
    span_irregular = (
        "Administer\u00a0intramuscular   epinephrine   into the anterolateral mid-thigh"
    )
    cit = SpanCitation(
        doc_id="DOC_ANAPHYLAXIS",
        section="Anaphylaxis Management",
        chunk_id="ANA_01",
        quoted_span=span_irregular,
    )

    instruction = "Administer intramuscular medication into mid-thigh promptly"
    is_valid, ov_score, err = verify_citation(cit, [chunk], instruction)
    assert is_valid is True, f"Citation verification failed on whitespace normalized span: {err}"
    assert ov_score > 0.0


def test_duplicate_chunk_ids_in_retrieval() -> None:
    """Duplicate chunk IDs in retrieved list do not crash citation verifier or cause errors."""
    chunk1 = RetrievedChunk(
        doc_id="DOC_1",
        section="Section 1",
        chunk_id="C1",
        text="Unique protocol instruction span for testing purposes",
        population="adult",
        syndrome="chest_pain",
    )
    # Duplicate chunk with identical ID
    chunk2 = RetrievedChunk(
        doc_id="DOC_1",
        section="Section 1",
        chunk_id="C1",
        text="Unique protocol instruction span for testing purposes",
        population="adult",
        syndrome="chest_pain",
    )

    cit = SpanCitation(
        doc_id="DOC_1",
        section="Section 1",
        chunk_id="C1",
        quoted_span="Unique protocol instruction span",
    )

    is_valid, ov_score, err = verify_citation(cit, [chunk1, chunk2], "instruction")
    assert is_valid is True


def test_bound_drug_name_permitted_in_narrative() -> None:
    """Narrative mentioning the bound drug_id or its ingredients is permitted; other drugs leak."""
    data_dir = get_data_dir()
    registry = ClinicalRegistry.load_from_directory(data_dir)

    # Narrative mentions bound drug 'epinephrine' -> Allowed
    narrative_bound = "Administer epinephrine immediately into anterolateral thigh"
    leaks = scan_narrative_for_drug_leaks(
        narrative=narrative_bound, bound_drug_id="epinephrine", registry=registry
    )
    assert not leaks, f"Expected zero leaks for bound drug, got: {leaks}"

    # Narrative mentions an UNBOUND drug 'amoxicillin' alongside bound drug -> Leaks
    narrative_unbound = "Administer amoxicillin alongside epinephrine immediately"
    leaks = scan_narrative_for_drug_leaks(
        narrative=narrative_unbound, bound_drug_id="epinephrine", registry=registry
    )
    assert any("amoxicillin" in leak for leak in leaks), f"Expected amoxicillin leak, got: {leaks}"
