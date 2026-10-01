# Cancer Reuse Decision Contracts

A decision contract records a shared cancer output and its version, the intended use, the
conditions that use needs, the checks run, and the analyst's action: proceed, revise the analysis,
or seek information. Replaying a contract after its purpose, source or evaluator changes marks the
earlier decision stale.

The planner takes a shared endpoint and a needed endpoint and reports the smallest sets of
additional fields that make the needed endpoint constructible, with a counterexample showing why
each field is required.

## Contents

| Path | Contents |
|---|---|
| `contracts.py` | Evaluator. Python standard library only |
| `contract.schema.json` | Contract structure |
| `examples/` | Nine contracts |
| `demo/` | Offline reports for each contract and for the planner. Open `demo/index.html` |
| `innovation/` | Planner, seven planning requests, release comparison, 86 saved solver inputs |
| `cdr/` | Planner checked against published TCGA-CDR endpoints |
| `evidence/` | Aggregate GDC captures, baseline comparison, admiral reference derivation |
| `tests/` | 42 core tests (14 planner tests are in `innovation/`) |
| `replay.py` | Reproduces every result from a fresh copy and compares it with the saved files |
| `AUTHORING-TUTORIAL.md` | Writing and recording a contract |

## Run

Python 3.10 or later.

```bash
python contracts.py examples/sample.json
python -m unittest discover -s tests
```

Exit code 0: conditions consistent and decision not stale. Exit code 2: violated, unknown, invalid
or stale.

Planner:

```bash
pip install z3-solver==4.15.4.0
python innovation/frontier.py innovation/requests/death-classification.json
```

## Reproduce

```bash
python replay.py
pip install -r requirements-verify.txt
python cdr/fetch_cdr.py
python replay.py --all
```

`fetch_cdr.py` downloads TCGA-CDR Table S1 from the GDC and verifies its checksum. The same steps
run in GitHub Actions on every push.

## Results

GDC TARGET-AML Gene Expression Quantification, Data Release 46.0, captured 2026-09-30:

| Selection | Files | Samples | Samples with more than one file | Aliquots |
|---|---|---|---|---|
| All | 3,227 | 3,064 | 160 | 3,227 |
| Primary blood-derived cancer, bone marrow | 1,892 | 1,787 | 102 | 1,892 |

TCGA-CDR, 11,103 patients. Encoded rules reproduce published PFS and PFI for 10,850 of 10,851
patients and OS for 11,038 of 11,038. Patients whose shared endpoint matches another patient's
while the needed endpoint differs:

| Shared to needed | Planner's fields | Shared only | With planner's fields | Unchosen fields |
|---|---|---|---|---|
| PFS to PFI | new tumor event day, death with tumor | 2,360 | 0 | 450 |
| OS to PFI | new tumor event day, death with tumor | 6,017 | 0 | 5,424 |
| PFI to PFS | death day | 2,557 | 0 | 355 |

Verification: Z3 4.15.4 and cvc5 1.3.1 agree on all 86 saved solver inputs. A second derivation
matches the evaluator on 640 synthetic cases. The evaluator matches admiral 1.4.2 on 28 reference
cases.

## Scope

Integer days; diagnosis or randomization origin; selected event and censoring rules; a
new-therapy cutoff. Results depend on stated date-order assumptions and on the candidate fields
named. No clinical validation, privacy certification or source authentication. No patient-level
records are included.

## Sources

- GDC API: https://docs.gdc.cancer.gov/API/Users_Guide/Search_and_Retrieval/
- TCGA-CDR: https://pmc.ncbi.nlm.nih.gov/articles/PMC6066282/
- admiral: https://pharmaverse.github.io/admiral/cran-release/reference/derive_param_tte.html
- Minimal useful views: https://doi.org/10.1145/3488370
- RO-Crate 1.1: https://www.researchobject.org/ro-crate/specification/1.1/
- Z3: https://github.com/Z3Prover/z3 ; cvc5: https://github.com/cvc5/cvc5

## Licence

MIT. Cory LeMay, 2026.
