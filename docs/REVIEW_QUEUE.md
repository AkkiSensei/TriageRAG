# TRIAGERAG — CLINICIAN CANDIDATE RULE REVIEW QUEUE

> **Research prototype. Synthetic data only. Not a medical device. Not for clinical use.**
> All rules below are **UNSOURCED DRAFT / RETRIEVED_UNREVIEWED**. Nothing here is active in production.
> Human Decision Gate HD-7: A clinical reviewer must sign off before any rule reaches `REVIEWED`.
> BLOCK severity rules require two independent clinical sign-offs (dual control).

## 1. Candidate Rule Review Protocol
1. Verify that the verbatim quote exists in the referenced FDA SPL drug label chunk.
2. Verify that the extracted numeric boundaries/thresholds match clinical guideline evidence.
3. Review the proposed consequence and action text for clarity and non-invented facts.
4. Assign `REVIEWED` (with reviewer ID and date) or `REJECTED` (with clinical justification).

## 2. Pending Candidates Queue

| Rule ID | Type | Target | Cand. Sev. | Source Chunk | Verbatim Evidence Quote | Status |
|---|---|---|---|---|---|---|
| `AUTO_MINED_CNS_01` | `condition_contraindication` | `morphine` | `BLOCK` | `EVID_MORPHINE_CONTRAINDICATIONS_e062e995` | "Do not administer Morphine in the presence of uncorrected severe hemodynamic ins..." | **PENDING_CLINICIAN_REVIEW** |
| `AUTO_MINED_CV_01` | `condition_contraindication` | `adenosine` | `BLOCK` | `EVID_ADENOSINE_CONTRAINDICATIONS_a50e23c6` | "Do not administer Adenosine in the presence of uncorrected severe hemodynamic in..." | **PENDING_CLINICIAN_REVIEW** |
| `AUTO_MINED_AC_01` | `condition_contraindication` | `warfarin` | `BLOCK` | `EVID_WARFARIN_CONTRAINDICATIONS_9ecc946d` | "Do not administer Warfarin in the presence of uncorrected severe hemodynamic ins..." | **PENDING_CLINICIAN_REVIEW** |
| `AUTO_MINED_AC_02` | `route_concentration` | `heparin` | `BLOCK` | `EVID_HEPARIN_CONTRAINDICATIONS_379a9600` | "Do not administer Heparin in the presence of uncorrected severe hemodynamic inst..." | **PENDING_CLINICIAN_REVIEW** |
| `AUTO_MINED_CV_03` | `route_concentration` | `verapamil` | `BLOCK` | `EVID_VERAPAMIL_CONTRAINDICATIONS_ed2e6862` | "Do not administer Verapamil in the presence of uncorrected severe hemodynamic in..." | **PENDING_CLINICIAN_REVIEW** |
| `AUTO_MINED_CV_04` | `pair` | `amiodarone+digoxin` | `HIGH` | `EVID_AMIODARONE_DRUG_INTERACTIONS_a83671ae` | "Concomitant administration of Amiodarone with other agents sharing metabolic pat..." | **PENDING_CLINICIAN_REVIEW** |
| `AUTO_MINED_CNS_02` | `pair` | `tramadol+ondansetron` | `HIGH` | `EVID_TRAMADOL_DRUG_INTERACTIONS_59d067bd` | "Concomitant administration of Tramadol with other agents sharing metabolic pathw..." | **PENDING_CLINICIAN_REVIEW** |
| `AUTO_MINED_CNS_03` | `pair` | `morphine+diazepam` | `BLOCK` | `EVID_MORPHINE_DRUG_INTERACTIONS_7659c16d` | "Concomitant administration of Morphine with other agents sharing metabolic pathw..." | **PENDING_CLINICIAN_REVIEW** |
| `AUTO_MINED_CNS_04` | `class_interaction` | `BENZODIAZEPINES+OPIOIDS` | `BLOCK` | `EVID_DIAZEPAM_DRUG_INTERACTIONS_1fc7296f` | "Concomitant administration of Diazepam with other agents sharing metabolic pathw..." | **PENDING_CLINICIAN_REVIEW** |

---
## 3. Human Decision Status (HD-7)
- **Decision**: HD-7 Clinical reviewer sign-off & dual control for BLOCK (open).
- **Fail-closed default**: Everything remains `verified: false`, `source_status: RETRIEVED_UNREVIEWED`.
- **Audit Trail**: Every reviewer action must be committed with git signature and ADR record.
