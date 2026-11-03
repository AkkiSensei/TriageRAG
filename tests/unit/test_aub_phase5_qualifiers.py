"""Unit tests for Phase 5 Task T5.2: THEN-Clause Qualifier Verification.

Safety Property (AUB-GRD-01, Rule R1, Rule R2, Task T5.2):
1. Verifies that instructions citing qualified THEN clauses ("repeat", "consider", "after",
   "continue", "withhold", "until") retain those qualifiers.
2. Rejects instructions that drop "repeat" (e.g., "Administer immediately" citing a repeat-dose
   node), preventing citation laundering of second-line or refractory therapies into
   first-line orders.
"""

from __future__ import annotations

from triagerag.verify.qualifiers import verify_step_qualifiers

REPEAT_CHUNK = (
    "3. IF signs of systemic hypoperfusion, compensatory tachycardia, or refractory shock "
    "continue after initial therapy:\n"
    "   THEN repeat administration of intramuscular epinephrine and establish wide-bore "
    "vascular access."
)

CONSIDER_CHUNK = (
    "4. IF beta-blocker therapy is active on patient home medication profile:\n"
    "   THEN monitor closely for refractory hypotension and consider glucagon protocol."
)

AFTER_CHUNK = (
    "2. IF persistent ischemic chest discomfort without contraindications:\n"
    "   THEN administer oral beta-blocker as formulary-directed after verifying absence of "
    "conduction blocks."
)

PLAIN_CHUNK = (
    "1. IF patient presents with acute respiratory distress or laryngeal edema:\n"
    "   THEN administer intramuscular epinephrine into the anterolateral mid-thigh immediately."
)

IF_CONDITIONAL_CHUNK = (
    "1. IF persistent ischemic chest discomfort without contraindications:\n"
    "   THEN consider administering oral metoprolol if hemodynamically stable."
)

PARENT_CHUNK = (
    "# ANAPHYLAXIS CLINICAL EMERGENCY PROTOCOL (SYNTHETIC)\n"
    "Initial assessment and stabilization guidelines for adult patients."
)


class TestQualifierVerification:
    """Tests for qualifier preservation between drafted instruction and cited THEN clause."""

    def test_repeat_qualifier_dropped_is_rejected(self) -> None:
        """Reject 'Administer immediately' when citing a repeat-dose clause."""
        instruction = "Administer epinephrine 0.5 mg intramuscularly immediately"
        is_ok, reason = verify_step_qualifiers(instruction, REPEAT_CHUNK)

        assert not is_ok
        assert reason is not None
        assert "QUALIFIER_DROPPED" in reason
        assert "'repeat'" in reason

    def test_repeat_qualifier_preserved_is_accepted(self) -> None:
        """Accept instruction that explicitly states repeat administration."""
        instruction = "Repeat administration of intramuscular epinephrine 0.5 mg IM"
        is_ok, reason = verify_step_qualifiers(instruction, REPEAT_CHUNK)

        assert is_ok
        assert reason is None

    def test_repeat_qualifier_equivalent_second_dose_accepted(self) -> None:
        """Accept instruction that specifies second or subsequent dose."""
        instruction = "Administer second dose of intramuscular epinephrine for persistent shock"
        is_ok, reason = verify_step_qualifiers(instruction, REPEAT_CHUNK)

        assert is_ok
        assert reason is None

    def test_consider_qualifier_dropped_is_rejected(self) -> None:
        """Reject unconditional order when citing a 'consider' clause."""
        instruction = "Administer glucagon 1 mg IV"
        is_ok, reason = verify_step_qualifiers(instruction, CONSIDER_CHUNK)

        assert not is_ok
        assert reason is not None
        assert "QUALIFIER_DROPPED" in reason
        assert "'consider'" in reason

    def test_consider_qualifier_preserved_is_accepted(self) -> None:
        """Accept instruction that retains 'consider' wording."""
        instruction = "Monitor blood pressure and consider glucagon protocol"
        is_ok, reason = verify_step_qualifiers(instruction, CONSIDER_CHUNK)

        assert is_ok
        assert reason is None

    def test_after_qualifier_dropped_is_rejected(self) -> None:
        """Reject instruction that drops post-condition verification qualifier."""
        instruction = "Administer oral beta-blocker metoprolol"
        is_ok, reason = verify_step_qualifiers(instruction, AFTER_CHUNK)

        assert not is_ok
        assert reason is not None
        assert "QUALIFIER_DROPPED" in reason
        assert "'after'" in reason

    def test_after_qualifier_preserved_is_accepted(self) -> None:
        """Accept instruction that retains 'after' verification qualifier."""
        instruction = "Administer oral beta-blocker after verifying absence of conduction blocks"
        is_ok, reason = verify_step_qualifiers(instruction, AFTER_CHUNK)

        assert is_ok
        assert reason is None

    def test_if_qualifier_dropped_is_rejected(self) -> None:
        """Reject instruction that drops 'if' conditional prerequisite in THEN clause."""
        instruction = "Consider administering oral metoprolol immediately"
        is_ok, reason = verify_step_qualifiers(instruction, IF_CONDITIONAL_CHUNK)

        assert not is_ok
        assert reason is not None
        assert "QUALIFIER_DROPPED" in reason
        assert "'if'" in reason

    def test_if_qualifier_preserved_is_accepted(self) -> None:
        """Accept instruction that preserves 'if' conditional prerequisite."""
        instruction = "Consider administering oral metoprolol if hemodynamically stable"
        is_ok, reason = verify_step_qualifiers(instruction, IF_CONDITIONAL_CHUNK)

        assert is_ok
        assert reason is None

    def test_plain_chunk_without_qualifiers_passes(self) -> None:
        """Plain immediate instruction passes on node without conditional qualifiers."""
        instruction = "Administer epinephrine 0.5 mg IM immediately into anterolateral thigh"
        is_ok, reason = verify_step_qualifiers(instruction, PLAIN_CHUNK)

        assert is_ok
        assert reason is None

    def test_parent_chunk_passes(self) -> None:
        """Non-IF/THEN overview text passes without qualifier checks."""
        instruction = "Review general resuscitation protocol guidelines"
        is_ok, reason = verify_step_qualifiers(instruction, PARENT_CHUNK)

        assert is_ok
        assert reason is None
