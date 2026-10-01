# Real endpoint definitions: TCGA-CDR

Run 2026-09-30 by `run_cdr.py`. Results in `results.json` (aggregate counts only, no patient
identifiers). Source: TCGA Pan-Cancer Clinical Data Resource (Liu et al., *Cell* 2018), Table S1,
open access, `raw/TCGA-CDR-SupplementalTableS1.xlsx`, sha256 `ea594c0f...e75a5a`.

## What was done

1. **Encoded three published CDR endpoints** as planner profiles, from the CDR's own notes
   sheets: OS (death from any cause), PFS (new tumor event or any death), PFI (new tumor event
   or death with tumor; censored at last contact or death without tumor). Model fields bound
   to CDR columns: progression = `new_tumor_event_dx_days_to`, death = `death_days_to` when
   Dead, last contact = `last_contact_days_to`, death with tumor = Dead and `tumor_status`
   WITH TUMOR (the CDR's own proxy).
2. **Fidelity.** Derived each endpoint from the raw CDR day fields with the package evaluator
   and compared with the published values.
3. **Planner.** Asked which additional fields make three real reuse questions answerable.
4. **Real-patient check, no model.** Grouped patients by the published source endpoint plus a
   supplement and counted groups whose published target still differs. Zero means the
   supplement determined the target on these patients. Then removed each supplement field,
   and ran a control with the fields the planner did not choose.

Kill rule set before looking: more than 10 percent disagreement in step 2 for reasons the model
cannot express would make this a stated limit, not evidence. It did not fire.

## Results

**Patients:** 11,103 unredacted. Model chronology assumptions broken by 1 record (new tumor
event after death) and 1 record (last contact after death) out of 3,567 deaths.

**Fidelity:** OS 11,038 of 11,038 (100%); PFS 10,850 of 10,851; PFI 10,850 of 10,851 (99.99%).
The single disagreement is an event day where the new tumor event and death days differ. This
shows the encoding matches the CDR's published rules. It is not clinical validation: the CDR
derived its endpoints from these same columns.

**Planner answers (Z3 4.15.4, complete within the model):**

| Shared endpoint | Needed endpoint | Minimal supplement | Each field necessary |
|---|---|---|---|
| PFS | PFI | new tumor event day + death-with-tumor flag | yes |
| OS | PFI | new tumor event day + death-with-tumor flag | yes |
| PFI | PFS | death day | yes |

**Real-patient check (published values, patients in groups whose target conflicts):**

| Question | Shared only | With planner's supplement | Remove one field | Control: unchosen fields |
|---|---|---|---|---|
| PFS to PFI (10,851) | 2,360 patients, 440 groups | **0** | without flag: 601 / without day: 1,039 | death + last contact: 450 patients, 168 groups |
| OS to PFI (10,846) | 6,017 patients, 1,566 groups | **0** | without flag: 601 / without day: 5,193 | death + last contact: 5,424 patients |
| PFI to PFS (10,851) | 2,557 patients, 520 groups | **0** | 2,557 | other three fields: 355 patients, 73 groups |

The control matters: the unchosen fields split patients into more groups than the planner's
supplement (6,725 vs 5,307 for PFS to PFI) yet leave conflicts. Granularity alone does not
explain the result; the planner chose the right information, not just more of it.

## Limits

- Determined on these 10,851 patients, which is evidence, not proof for other datasets.
- The CDR's DFI exclusions, cause-of-death adjudication for DSS, and the PFI.1/PFI.2 variants
  are not encoded.
- `tumor_status` is the CDR's proxy for death with tumor and does not establish cause of death.
