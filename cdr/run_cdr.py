"""Real endpoint definitions: run the planner on TCGA-CDR, then test its answer on real patients.

Source: TCGA Pan-Cancer Clinical Data Resource (Liu et al., Cell 2018), supplementary
table S1, open access from the GDC PanCanAtlas publications page:
  https://api.gdc.cancer.gov/data/1b5f413e-a8d1-4d10-92eb-7c4ae739ed81
saved as raw/TCGA-CDR-SupplementalTableS1.xlsx (sha256 recorded in results).

Four steps, all written before the data was examined:
  1. Encode three published CDR endpoints (OS, PFS, PFI) as planner profiles, from the
     CDR's own notes sheets, and bind the model's fields to real CDR columns.
  2. Fidelity: derive each endpoint from the raw CDR day fields with the package's
     evaluator and compare with the published values. Disagreements are reported by
     category, not hidden; each is a place where the CDR rule differs from the encoding.
  3. Planner: for real reuse questions (a study shared PFS or OS, a reuser needs PFI),
     ask the planner which additional fields are sufficient and necessary.
  4. Real-data check of the planner's answer, using published values only, no model:
     group patients by what is shared (the published source endpoint) plus a supplement,
     and count groups whose published target endpoint still differs. Zero conflicts means
     the supplement determined the target on these patients. Removing each supplement
     component should bring conflicts back: those are real-patient counterexamples.

Kill rule fixed in advance: if the fidelity check shows the encoding disagrees with the
published PFI for more than 10 percent of patients for reasons the model cannot express,
the result is reported as a stated limit, not as headline evidence.

Output: results.json with aggregate counts only. No patient barcodes are written.
"""
import collections
import hashlib
import json
import sys
from pathlib import Path

import openpyxl

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "innovation"))
import contracts as dc  # noqa: E402

XLSX = HERE / "raw" / "TCGA-CDR-SupplementalTableS1.xlsx"
CDR_URL = "https://www.cell.com/cell/fulltext/S0092-8674(18)30229-0"
SCOPE = ("TCGA-CDR Table S1 notes, encoded as event and censoring rules from diagnosis. "
         "CDR exclusions and cause-of-death adjudication are not modelled.")


def profile(events, censor):
    return {"origin": "diagnosis", "events": events, "censor_at": censor, "cutoff": None,
            "unit": "days", "definition_source": CDR_URL, "definition_scope": SCOPE}


PROFILES = {
    # OS: death from any cause; time is last contact or death, whichever is larger.
    "OS": profile(["death_any"], ["last_contact"]),
    # PFS (ExtraEndpoints): new tumor event or death from any cause.
    "PFS": profile(["progression", "death_any"], ["last_contact"]),
    # PFI: new tumor event or death with the cancer; censored at last contact or a death
    # without tumor.
    "PFI": profile(["progression", "death_with_tumor"], ["last_contact", "death_without_tumor"]),
}


CANDIDATES = ["progression", "death", "death_with_tumor", "last_contact"]


def chronology(rows):
    """How often real records break the model's stated chronology assumptions."""
    c = collections.Counter()
    for r in rows:
        h = history(r)
        if h["death"] is None:
            continue
        c["dead"] += 1
        if h["progression"] is not None and h["progression"] > h["death"]:
            c["new tumor event after death"] += 1
        if h["last_contact"] is not None and h["last_contact"] > h["death"]:
            c["last contact after death"] += 1
    return dict(c)


def num(v):
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return int(round(f))


def load():
    wb = openpyxl.load_workbook(XLSX, read_only=True)

    def sheet(name):
        rows = wb[name].iter_rows(values_only=True)
        hdr = next(rows)
        return {r[hdr.index("bcr_patient_barcode")]: dict(zip(hdr, r)) for r in rows
                if r[hdr.index("bcr_patient_barcode")]}

    main, extra = sheet("TCGA-CDR"), sheet("ExtraEndpoints")
    for k, r in main.items():
        r.update({c: v for c, v in extra.get(k, {}).items() if c not in r})
    return list(main.values())


def history(r):
    dead = r["vital_status"] == "Dead"
    return {
        "diagnosis": 0, "randomization": 0, "new_therapy": None, "last_pretherapy_assessment": None,
        "progression": num(r["new_tumor_event_dx_days_to"]),
        "death": num(r["death_days_to"]) if dead else None,
        "last_contact": num(r["last_contact_days_to"]),
        "death_with_tumor": bool(dead and r["tumor_status"] == "WITH TUMOR"),
    }


def published(r, name):
    ev, t = num(r[name]), num(r[name + ".time"])
    if ev is None or t is None:
        return None
    return {"elapsed_days": t, "event": bool(ev)}


def fidelity(rows):
    out = {}
    for name, p in PROFILES.items():
        n = agree = 0
        why = collections.Counter()
        for r in rows:
            pub = published(r, name)
            if pub is None:
                continue
            n += 1
            h = history(r)
            got = dc.derive(h, p)
            if got == pub:
                agree += 1
                continue
            if got is None:
                why["no raw day field to derive from"] += 1
            elif got["event"] != pub["event"]:
                if name == "PFI" and pub["event"] and not got["event"] and h["death"] is not None:
                    why["published event at a death the tumor_status field does not mark WITH TUMOR"] += 1
                elif h["progression"] is not None and h["death"] is not None and h["progression"] > h["death"]:
                    why["new tumor event recorded after death"] += 1
                else:
                    why["event flag differs, other"] += 1
            else:
                if h["progression"] is not None and pub["event"] and got["elapsed_days"] != pub["elapsed_days"]:
                    why["event day differs (new tumor event vs death day)"] += 1
                else:
                    why["censoring day differs"] += 1
        out[name] = {"patients_with_published_value": n, "agree": agree,
                     "agree_pct": round(100.0 * agree / n, 2) if n else None,
                     "disagreements_by_reason": dict(why.most_common())}
    return out


def plan(source, target, candidates):
    from frontier import Analyzer, binding
    a = Analyzer(PROFILES[source], PROFILES[target])
    base = ["source_elapsed_days", "source_event"]
    fr = a.frontier(base, candidates)
    return {"source": source, "target": target, "baseline": a.check(base)["status"],
            "candidates": candidates,
            "minimal_supplements": [{"fields": m["additional_components"],
                                     "minimality_established": m["minimality_established"]}
                                    for m in fr["minimal_supplements"]],
            "status": fr["status"], "solver": binding()["solver"]}


def supplement_value(h, field):
    return h[field]


def real_check(rows, source, target, supplement):
    """Group by published source endpoint plus supplement; count conflicting targets."""
    def conflicts(fields):
        groups = collections.defaultdict(set)
        n = 0
        for r in rows:
            s, t = published(r, source), published(r, target)
            if s is None or t is None:
                continue
            h = history(r)
            key = (s["elapsed_days"], s["event"]) + tuple(supplement_value(h, f) for f in fields)
            groups[key].add((t["elapsed_days"], t["event"]))
            n += 1
        bad = [k for k, v in groups.items() if len(v) > 1]
        members = collections.Counter()
        for r in rows:
            s, t = published(r, source), published(r, target)
            if s is None or t is None:
                continue
            h = history(r)
            members[(s["elapsed_days"], s["event"]) + tuple(supplement_value(h, f) for f in fields)] += 1
        return {"patients": n, "groups": len(groups), "conflicting_groups": len(bad),
                "patients_in_conflicting_groups": sum(members[k] for k in bad)}

    out = {"shared_only": conflicts([]), "with_supplement": conflicts(supplement)}
    out["remove_one"] = {f: conflicts([x for x in supplement if x != f]) for f in supplement}
    # Control: a supplement the planner did not choose, of at least as fine a grain.
    # If grouping granularity alone removed conflicts, these would also reach zero.
    others = [c for c in CANDIDATES if c not in supplement]
    out["control_unchosen_fields"] = {"fields": others, **conflicts(others)}
    return out


def main():
    rows = [r for r in load() if str(r.get("Redaction") or "").strip() == ""]
    res = {
        "source_file": XLSX.name,
        "source_sha256": hashlib.sha256(XLSX.read_bytes()).hexdigest(),
        "patients_unredacted": len(rows),
        "profiles": PROFILES,
        "field_binding": {
            "progression": "new_tumor_event_dx_days_to (smallest new tumor event day)",
            "death": "death_days_to when vital_status is Dead",
            "last_contact": "last_contact_days_to",
            "death_with_tumor": "vital_status Dead and tumor_status WITH TUMOR (the CDR's own proxy)",
        },
        "fidelity": fidelity(rows),
        "chronology_vs_model_assumptions": chronology(rows),
    }
    cands = CANDIDATES
    res["planner"] = [plan("PFS", "PFI", cands), plan("OS", "PFI", cands), plan("PFI", "PFS", cands)]
    res["real_check"] = {}
    for p in res["planner"]:
        for m in p["minimal_supplements"]:
            key = "%s->%s +%s" % (p["source"], p["target"], "+".join(m["fields"]))
            res["real_check"][key] = real_check(rows, p["source"], p["target"], m["fields"])
    out = HERE / "results.json"
    out.write_text(json.dumps(res, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: res[k] for k in ("patients_unredacted", "fidelity", "planner", "real_check")}, indent=1))


if __name__ == "__main__":
    main()
