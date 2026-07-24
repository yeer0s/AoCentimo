#!/usr/bin/env python3
"""
Portugal IRS Dossier Organizer -- golden-corpus validation harness.

Plain Python 3.10+ standard library only. No network access, no environment
reads, no eval/exec/subprocess, no writes outside this skill's own folder.

Modes:
  python validate.py --selftest
      Re-derives every case's expected dossier output from its input using
      the deterministic mapping rules below, and compares that derivation
      against the case's stored "expected" block. Prints one PASS/FAIL line
      per case plus a summary line. Exits 0 only if every case passes -- this
      is the hard gate referenced by SKILL.md's Validate mode.

  python validate.py <candidate.json>
      Scores a candidate dossier output (produced by a person or an LLM
      working the same cases) against the golden "expected" values stored in
      cases.json. Prints a per-case, per-field match report and a summary.
      Exits 0 whenever scoring completes without a structural error --
      exit code is not a proxy for "candidate was correct", read the report.

Candidate JSON shape for mode 2 -- a dict keyed by case id, each value the
same shape as that case's "expected" block in cases.json:
  {
    "C01": {
      "income_annex_map": [...],
      "deduction_inventory": [...],
      "missing_documents": [...],
      "flags": [...],
      "filing_regime": ...
    },
    ...
  }
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
GOLDEN_PATH = SKILL_ROOT / "assets" / "organizer-cases.json"
DIVERGENCE_PATH = SKILL_ROOT / "assets" / "divergence-cases.json"
FIELD_CODES_PATH = SKILL_ROOT / "assets" / "field-codes.json"
FIELD_CODES_MIN = 60

# ---------------------------------------------------------------------------
# Deterministic mapping rules (income year 2025, filed 2026 -- see SKILL.md
# Domain playbook). Kept in one place so --selftest can prove the golden
# corpus's "expected" values are actually consistent with these rules, not
# hand-typed guesses.
# ---------------------------------------------------------------------------

ANNEX_MAP = {
    "categoria_a": "A",
    "categoria_h": "A",
    "categoria_b_simplificado": "B",
    "categoria_b_organizada": "C",
    "categoria_e": "E",
    "categoria_f": "F",
    "categoria_g": "G",
    "categoria_j": "J",
    "ifici_pending": "L",
}

MORTGAGE_INTEREST_CUTOFF_YEAR = 2011
CAT_B_JUSTIFICATION_GROSS_THRESHOLD_EUR = 29748.00
CAT_B_JUSTIFICATION_FLOOR_PCT = 15.0

FLAG_CODES = {
    "STOP_UNMAPPED": "Income item has no mapped Modelo 3 annex -- hard STOP, "
                      "route to OCC review, never assign a best-guess annex.",
    "REJECT_INELIGIBLE": "Deduction claimed against a condition that structurally "
                          "disqualifies it (e.g. mortgage interest on a post-2011 "
                          "contract) -- must be marked NotApplicable, not Missing.",
    "FLAG_MISSING_AT_COMMUNICATION": "Displaced-student rent claimed without the "
                          "AT 'Comunicacao de Renda' step completed -- must not be "
                          "accepted as Present until that step is confirmed.",
    "FLAG_MUTUALLY_EXCLUSIVE": "Education (propinas) and pensao de alimentos both "
                          "claimed for the same dependent -- these are mutually "
                          "exclusive per dependent, must be flagged for the "
                          "household to resolve, never both accepted.",
    "FLAG_WRONG_NIF": "A dependent's supporting invoice was issued under a "
                          "non-custodial parent's NIF under shared custody -- "
                          "cannot support this filer's claim as-is.",
    "FLAG_OCC_ROUTE": "Ex-NHR / IFICI ('NHR 2.0') election present -- this skill "
                          "flags Anexo L and routes to an OCC, it never resolves "
                          "eligibility itself.",
    "FLAG_BELOW_JUSTIFICATION_FLOOR": "Regime simplificado (Categoria B) taxpayer "
                          "above the gross-income threshold with justified "
                          "expenses under the 15% floor.",
    "FLAG_MISCATEGORIZED": "e-Fatura invoice sitting under the wrong category -- "
                          "needs a portal correction, not silent acceptance.",
}

DOC_HINTS = {
    "health": "recibo de saude -- request an itemized invoice from the provider, "
              "or check the e-Fatura 'Saude' category export",
    "education": "recibo de propinas/mensalidade -- request from the school or "
              "university",
    "general_family": "e-Fatura general-expense invoice -- confirm the NIF was "
              "given at point of sale, or add it via the e-Fatura app QR scan",
    "housing_rent": "recibo de renda -- request from the landlord or check the "
              "Portal das Financas 'Comunicacao de Renda' history",
    "housing_mortgage_interest": "annual mortgage interest statement from the "
              "bank (only relevant for contracts signed on or before "
              "31-12-2011)",
    "pensao_alimentos": "proof of pensao de alimentos payment (bank transfer "
              "records or the court-ordered payment schedule)",
    "ppr": "PPR annual contribution certificate from the fund manager",
    "disability": "atestado de incapacidade multiuso (disability certificate)",
}

_STATUS_VOCAB = {"Present", "Missing", "NotApplicable"}
_AMOUNT_STATUS_VOCAB = {"Confirmed", "Estimated", "Missing"}


def mk_flag(code, member, detail):
    return {"code": code, "member": member, "detail": detail}


# ---------------------------------------------------------------------------
# Rule engine
# ---------------------------------------------------------------------------

def derive_income_annex_map(members):
    rows = []
    flags = []
    missing_docs = []
    for m in members:
        for item in m.get("income_items", []):
            t = item["type"]
            row = {
                "member": m["id"],
                "income_type": t,
                "status": item.get("amount_status", "Confirmed"),
            }
            notes = []
            if t in ANNEX_MAP:
                row["annex"] = ANNEX_MAP[t]

                if t == "categoria_b_simplificado":
                    if item.get("first_year_activity"):
                        yr = item.get("year_of_activity", 1)
                        pct = 50 if yr == 1 else (25 if yr == 2 else 0)
                        if pct:
                            notes.append(
                                f"first-year activity reduction: {pct}% "
                                f"taxable-income reduction (year {yr} of atividade)"
                            )
                    gross = item.get("gross_annual_eur", 0)
                    coeff = item.get("coefficient")
                    justified = item.get("justified_expenses_pct")
                    if (
                        coeff in (0.75, 0.35)
                        and gross > CAT_B_JUSTIFICATION_GROSS_THRESHOLD_EUR
                        and justified is not None
                        and justified < CAT_B_JUSTIFICATION_FLOOR_PCT
                    ):
                        flags.append(mk_flag(
                            "FLAG_BELOW_JUSTIFICATION_FLOOR",
                            m["id"],
                            f"justified expenses {justified}% is below the 15% "
                            f"floor on gross income of {gross:.2f} EUR",
                        ))
                        notes.append(
                            "expense-justification floor not met -- increases "
                            "taxable income, confirm e-Fatura professional "
                            "expense total"
                        )

                if t == "categoria_j":
                    notes.append(
                        "foreign-source income -- Anexo J required regardless "
                        "of amount, including dormant/low-income accounts"
                    )

                if t == "ifici_pending":
                    flags.append(mk_flag(
                        "FLAG_OCC_ROUTE",
                        m["id"],
                        "ex-NHR/IFICI election present -- flag Anexo L and "
                        "route to an OCC, do not resolve eligibility",
                    ))
                    row["status"] = "Missing"
                    notes.append(
                        "IFICI/ex-NHR eligibility not resolved by this skill "
                        "-- OCC confirmation required before Anexo L is filed"
                    )
            else:
                row["annex"] = "UNMAPPED"
                row["status"] = "Missing"
                flags.append(mk_flag(
                    "STOP_UNMAPPED",
                    m["id"],
                    f"income type '{t}' has no mapped Modelo 3 annex -- needs "
                    f"OCC review before this dossier can be marked complete",
                ))
                missing_docs.append({
                    "item": f"{t} -- no mapped annex",
                    "blocks": "N/A (unmapped income)",
                    "where_to_get": "Escalate to an OCC for professional "
                                     "classification before filing; do not "
                                     "assign a best-guess annex.",
                })

            if notes:
                row["notes"] = "; ".join(notes)
            rows.append(row)
    return rows, flags, missing_docs


def derive_deduction_inventory(deduction_items):
    rows = []
    flags = []
    missing_docs = []

    by_dep = defaultdict(list)
    for it in deduction_items:
        if it.get("dependent"):
            by_dep[it["dependent"]].append(it)

    conflict_deps = set()
    for dep, items in by_dep.items():
        claimed_cats = {it["category"] for it in items if it.get("claimed")}
        if "education" in claimed_cats and "pensao_alimentos" in claimed_cats:
            conflict_deps.add(dep)

    for dep in sorted(conflict_deps):
        member = next(
            it["member"] for it in deduction_items
            if it.get("dependent") == dep and it["category"] == "education"
        )
        flags.append(mk_flag(
            "FLAG_MUTUALLY_EXCLUSIVE",
            member,
            f"dependent {dep}: education and pensao de alimentos both claimed "
            f"-- mutually exclusive per dependent, resolve before filing",
        ))
        missing_docs.append({
            "item": f"dependent {dep}: education vs pensao de alimentos choice",
            "blocks": "Anexo H (education or pensao de alimentos deduction)",
            "where_to_get": "Household decision required -- choose one "
                             "deduction for this dependent, cannot claim both",
        })

    for it in deduction_items:
        row = {
            "member": it["member"],
            "dependent": it.get("dependent"),
            "category": it["category"],
        }

        if not it.get("claimed", True):
            row["applicable"] = False
            row["document_status"] = "NotApplicable"
            rows.append(row)
            continue

        row["applicable"] = True

        if it["category"] == "housing_mortgage_interest":
            if it["contract_year"] <= MORTGAGE_INTEREST_CUTOFF_YEAR:
                row["document_status"] = (
                    "Present" if it.get("document_present") else "Missing"
                )
                if row["document_status"] == "Missing":
                    missing_docs.append({
                        "item": f"mortgage interest statement ({it['member']})",
                        "blocks": "Anexo H housing_mortgage_interest deduction",
                        "where_to_get": DOC_HINTS["housing_mortgage_interest"],
                    })
            else:
                row["applicable"] = False
                row["document_status"] = "NotApplicable"
                flags.append(mk_flag(
                    "REJECT_INELIGIBLE",
                    it["member"],
                    f"mortgage contract dated {it['contract_year']} postdates "
                    f"the 31-12-2011 cutoff -- interest is not deductible",
                ))

        elif it["category"] == "education" and it.get("displaced_student_rent"):
            if not it.get("comunicacao_at"):
                row["document_status"] = "Missing"
                flags.append(mk_flag(
                    "FLAG_MISSING_AT_COMMUNICATION",
                    it["member"],
                    f"displaced-student rent for dependent {it.get('dependent')} "
                    f"claimed without the AT 'Comunicacao de Renda' step -- "
                    f"cannot be accepted as Present until confirmed",
                ))
                missing_docs.append({
                    "item": f"AT 'Comunicacao de Renda' for dependent "
                            f"{it.get('dependent')}",
                    "blocks": "Anexo H displaced-student rent uplift",
                    "where_to_get": "Complete the 'Comunicacao de Renda' step "
                                     "in Portal das Financas before this rent "
                                     "can be counted as Present",
                })
            elif it.get("dependent") in conflict_deps:
                row["document_status"] = "Missing"
            else:
                row["document_status"] = (
                    "Present" if it.get("document_present") else "Missing"
                )
                if row["document_status"] == "Missing":
                    missing_docs.append({
                        "item": f"education receipt for dependent "
                                f"{it.get('dependent')}",
                        "blocks": "Anexo H education deduction",
                        "where_to_get": DOC_HINTS["education"],
                    })

        elif it.get("dependent") in conflict_deps and it["category"] in (
            "education", "pensao_alimentos",
        ):
            row["document_status"] = "Missing"

        elif (
            it.get("invoice_nif_holder")
            and it.get("custodial_parent")
            and it["invoice_nif_holder"] != it["custodial_parent"]
        ):
            row["document_status"] = "Missing"
            flags.append(mk_flag(
                "FLAG_WRONG_NIF",
                it["member"],
                f"invoice for dependent {it.get('dependent')} was issued under "
                f"{it['invoice_nif_holder']}'s NIF, not custodial parent "
                f"{it['custodial_parent']} -- cannot support this filer's claim "
                f"as-is",
            ))
            missing_docs.append({
                "item": f"correctly-attributed invoice for dependent "
                        f"{it.get('dependent')}",
                "blocks": f"Anexo H {it['category']} deduction",
                "where_to_get": "Request a reissued invoice under the "
                                 "custodial parent's NIF, or reallocate under "
                                 "the shared-custody agreement",
            })

        else:
            row["document_status"] = (
                "Present" if it.get("document_present") else "Missing"
            )
            if row["document_status"] == "Missing":
                hint = DOC_HINTS.get(
                    it["category"], "obtain the supporting document for this "
                                     "deduction category",
                )
                missing_docs.append({
                    "item": f"{it['category']} document ({it['member']})",
                    "blocks": f"Anexo H {it['category']} deduction",
                    "where_to_get": hint,
                })

        rows.append(row)

    return rows, flags, missing_docs


def derive_efatura_issues(efatura_items):
    missing_docs = []
    flags = []
    for e in efatura_items or []:
        status = e["status"]
        if status == "miscategorized":
            missing_docs.append({
                "item": f"invoice {e['invoice_id']} recategorization",
                "blocks": e.get("category_declared"),
                "where_to_get": (
                    f"e-Fatura portal -> select invoice {e['invoice_id']} -> "
                    f"'Alterar' -> set category to {e['category_correct']}"
                ),
            })
            flags.append(mk_flag(
                "FLAG_MISCATEGORIZED",
                None,
                f"invoice {e['invoice_id']} is declared as "
                f"{e['category_declared']}, should be {e['category_correct']}",
            ))
        elif status == "pending":
            missing_docs.append({
                "item": f"invoice {e['invoice_id']} validation",
                "blocks": e.get("category_correct", e.get("category_declared")),
                "where_to_get": "e-Fatura portal -> validate before the "
                                 "cycle's deadline",
            })
        elif status == "not_communicated":
            missing_docs.append({
                "item": f"invoice {e['invoice_id']} manual registration",
                "blocks": e.get("category_correct"),
                "where_to_get": "e-Fatura portal -> register manually with "
                                 "invoice number, date, issuer NIF, and value",
            })
        elif status == "validated":
            pass
        else:
            raise ValueError(f"unknown e-Fatura status: {status!r}")
    return missing_docs, flags


def derive_filing_regime(filing_status, election):
    if filing_status in ("married", "uniao_facto"):
        return election if election else "conjunta"
    return None


def derive_case(inp):
    """Deterministically derive the expected dossier output for one case's
    input, per the mapping/eligibility rules above."""
    income_rows, income_flags, income_missing = derive_income_annex_map(
        inp.get("members", [])
    )
    ded_rows, ded_flags, ded_missing = derive_deduction_inventory(
        inp.get("deduction_items", [])
    )
    efat_missing, efat_flags = derive_efatura_issues(inp.get("efatura_items", []))

    regime = derive_filing_regime(
        inp.get("filing_status"), inp.get("joint_separate_election")
    )

    all_flags = income_flags + ded_flags + efat_flags
    all_missing = income_missing + ded_missing + efat_missing

    return {
        "income_annex_map": income_rows,
        "deduction_inventory": ded_rows,
        "missing_documents": all_missing,
        "flags": all_flags,
        "filing_regime": regime,
    }


# ---------------------------------------------------------------------------
# Comparison (order-insensitive on list-of-dict fields)
# ---------------------------------------------------------------------------

def _normalize(obj):
    if isinstance(obj, dict):
        return {k: _normalize(v) for k, v in sorted(obj.items())}
    if isinstance(obj, list):
        normalized = [_normalize(x) for x in obj]
        return sorted(normalized, key=lambda x: json.dumps(x, sort_keys=True))
    return obj


def _diff_field(name, derived_val, expected_val):
    if _normalize(derived_val) != _normalize(expected_val):
        return (
            f"    field '{name}' mismatch:\n"
            f"      derived : {json.dumps(_normalize(derived_val), ensure_ascii=False)}\n"
            f"      expected: {json.dumps(_normalize(expected_val), ensure_ascii=False)}"
        )
    return None


def compare_case(derived, expected):
    problems = []
    for field in ("income_annex_map", "deduction_inventory", "missing_documents",
                  "flags", "filing_regime"):
        d = _diff_field(field, derived.get(field), expected.get(field))
        if d:
            problems.append(d)
    return problems


# ---------------------------------------------------------------------------
# Schema sanity checks (independent of rule derivation -- catches malformed
# authoring, e.g. a status value outside the documented vocabulary).
# ---------------------------------------------------------------------------

def schema_sanity_check(case):
    problems = []
    exp = case.get("expected", {})
    for row in exp.get("deduction_inventory", []):
        st = row.get("document_status")
        if st not in _STATUS_VOCAB:
            problems.append(
                f"    deduction_inventory row for {row.get('category')} has "
                f"out-of-vocabulary document_status {st!r} (expected one of "
                f"{sorted(_STATUS_VOCAB)})"
            )
    for row in exp.get("income_annex_map", []):
        st = row.get("status")
        if st not in _AMOUNT_STATUS_VOCAB:
            problems.append(
                f"    income_annex_map row for {row.get('income_type')} has "
                f"out-of-vocabulary status {st!r} (expected one of "
                f"{sorted(_AMOUNT_STATUS_VOCAB)})"
            )
    for fl in exp.get("flags", []):
        if fl.get("code") not in FLAG_CODES:
            problems.append(
                f"    flag code {fl.get('code')!r} is not in the documented "
                f"flag_codes vocabulary"
            )
    if not case.get("trap"):
        problems.append("    case has no 'trap' field")
    return problems


# ---------------------------------------------------------------------------
# CLI modes
# ---------------------------------------------------------------------------

def load_golden():
    with open(GOLDEN_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Divergencias-defense corpus integrity gate (assets/divergence-cases.json).
# Post-filing layer: schema + completeness checks over the fictional AT
# divergencia scenarios. This is an integrity gate (well-formed, complete,
# every deadline cited, every trap named), independent of the golden-corpus
# rule derivation above.
# ---------------------------------------------------------------------------

DIVERGENCE_REQUIRED_FIELDS = (
    "id", "title", "situation", "flag_type", "correct_response_path",
    "deadline_basis", "documents_needed", "trap", "severity",
    "escalate_to_occ", "is_negative_control",
)


def validate_divergence_corpus():
    """Return (ok, lines). ok is True only when the divergence corpus is
    well-formed and meets its bars: >=10 cases, >=1 negative control,
    >=1 must-escalate-to-OCC case, every deadline_basis non-empty, every
    trap named, controlled flag_type / severity / response_path vocab."""
    lines = []
    problems = []
    try:
        with open(DIVERGENCE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return False, ["FAIL  divergence-cases.json not found at "
                       + str(DIVERGENCE_PATH)]
    except json.JSONDecodeError as e:
        return False, ["FAIL  divergence-cases.json does not parse: " + str(e)]

    schema = data.get("_schema", {})
    flag_vocab = set(schema.get("flag_type_vocabulary", []))
    sev_vocab = set(schema.get("severity_vocabulary", []))
    path_vocab = set(schema.get("response_path_vocabulary", []))
    if not flag_vocab or not sev_vocab or not path_vocab:
        problems.append("_schema is missing a required vocabulary block "
                        "(flag_type / severity / response_path)")

    cases = data.get("cases", [])
    seen_ids = set()
    negative_controls = 0
    escalate_cases = 0

    for i, c in enumerate(cases):
        cid = c.get("id", "<no-id #%d>" % i)
        for fld in DIVERGENCE_REQUIRED_FIELDS:
            if fld not in c:
                problems.append("%s: missing required field '%s'" % (cid, fld))
        if cid in seen_ids:
            problems.append("%s: duplicate id" % cid)
        seen_ids.add(cid)

        # every deadline_basis non-empty
        db = c.get("deadline_basis", "")
        if not (isinstance(db, str) and db.strip()):
            problems.append("%s: deadline_basis is empty" % cid)

        # trap named per case
        trap = c.get("trap", "")
        if not (isinstance(trap, str) and trap.strip()):
            problems.append("%s: trap not named" % cid)

        # situation named
        sit = c.get("situation", "")
        if not (isinstance(sit, str) and sit.strip()):
            problems.append("%s: situation is empty" % cid)

        # controlled vocabularies
        ft = c.get("flag_type")
        if flag_vocab and ft not in flag_vocab:
            problems.append("%s: flag_type %r not in vocabulary" % (cid, ft))
        sv = c.get("severity")
        if sev_vocab and sv not in sev_vocab:
            problems.append("%s: severity %r not in vocabulary" % (cid, sv))
        rp = c.get("correct_response_path")
        if path_vocab and rp not in path_vocab:
            problems.append("%s: correct_response_path %r not in vocabulary"
                            % (cid, rp))

        # documents_needed must be a list; non-empty unless it's a
        # no-action informational case
        dn = c.get("documents_needed")
        if not isinstance(dn, list):
            problems.append("%s: documents_needed must be a list" % cid)
        elif not dn and c.get("correct_response_path") != "no_action":
            problems.append("%s: documents_needed empty on an actionable case"
                            % cid)

        # negative control integrity: informational/no_action pair
        if c.get("is_negative_control"):
            negative_controls += 1
            if c.get("correct_response_path") != "no_action":
                problems.append("%s: negative control must have response_path "
                                "'no_action'" % cid)
            if c.get("escalate_to_occ"):
                problems.append("%s: negative control must not escalate to OCC"
                                % cid)

        # escalate integrity: escalate flag pairs with escalate_occ path
        if c.get("escalate_to_occ"):
            escalate_cases += 1
            if c.get("correct_response_path") != "escalate_occ":
                problems.append("%s: escalate_to_occ case must have "
                                "response_path 'escalate_occ'" % cid)

    n = len(cases)
    if n < 10:
        problems.append("corpus has %d cases (bar: >=10)" % n)
    if negative_controls < 1:
        problems.append("no negative control present (bar: >=1)")
    if escalate_cases < 1:
        problems.append("no must-escalate-to-OCC case present (bar: >=1)")

    for p in problems:
        lines.append("FAIL  divergence:" + p)
    if not problems:
        lines.append("PASS  divergence-corpus  %d cases, %d negative control(s), "
                     "%d escalate-to-OCC case(s)"
                     % (n, negative_controls, escalate_cases))
    return (not problems), lines


# ---------------------------------------------------------------------------
# Modelo 3 field-code lexicon gate (assets/field-codes.json).
# Upgrades the dossier from "which annex" to "which quadro and code". This is
# an integrity + miscoding gate: schema/completeness/no-duplicate-pairs over
# the lexicon, plus >=6 planted miscoding checks validated AGAINST the lexicon
# (a household's wrong (annex, code) vs the correct one). Independent of the
# golden-corpus rule derivation and the divergence corpus above.
# ---------------------------------------------------------------------------

FIELD_CODE_REQUIRED_FIELDS = (
    "annex", "quadro", "code", "meaning", "common_error", "citation", "as_of",
)
FIELD_CODE_AS_OF = "2025 income campaign"
PLANTED_REQUIRED_FIELDS = ("id", "name", "wrong", "correct", "why")


def validate_field_codes():
    """Return (ok, lines). ok is True only when the field-code lexicon is
    well-formed and meets its bars: >=60 entries, no duplicate (annex, code)
    pairs, every required field non-empty, every citation present, as_of ==
    '2025 income campaign', AND every planted miscoding (>=6) resolves against
    the lexicon (correct pair present; wrong != correct; where the wrong pair
    also exists its meaning differs from the correct one)."""
    lines = []
    problems = []
    try:
        with open(FIELD_CODES_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return False, ["FAIL  field-codes.json not found at "
                       + str(FIELD_CODES_PATH)]
    except json.JSONDecodeError as e:
        return False, ["FAIL  field-codes.json does not parse: " + str(e)]

    codes = data.get("codes", [])
    index = {}          # (annex, code) -> meaning
    for i, c in enumerate(codes):
        label = "entry #%d" % i
        for fld in FIELD_CODE_REQUIRED_FIELDS:
            v = c.get(fld)
            if not (isinstance(v, str) and v.strip()):
                problems.append("%s: field %r empty or missing" % (label, fld))
        annex = c.get("annex")
        code = c.get("code")
        if annex and code:
            label = "%s/%s" % (annex, code)
            key = (annex, code)
            if key in index:
                problems.append("%s: duplicate (annex, code) pair" % label)
            index[key] = c.get("meaning", "")
        ao = c.get("as_of")
        if ao != FIELD_CODE_AS_OF:
            problems.append("%s: as_of %r != %r" % (label, ao, FIELD_CODE_AS_OF))

    n = len(codes)
    if n < FIELD_CODES_MIN:
        problems.append("lexicon has %d entries (bar: >=%d)"
                        % (n, FIELD_CODES_MIN))

    # Planted miscoding checks -- validated against the lexicon.
    planted = data.get("planted_miscodings", [])
    miscoding_checks = 0
    for i, m in enumerate(planted):
        mid = m.get("id", "<no-id #%d>" % i)
        for fld in PLANTED_REQUIRED_FIELDS:
            if fld not in m:
                problems.append("%s: planted miscoding missing field %r"
                                % (mid, fld))
        wrong = m.get("wrong", {})
        correct = m.get("correct", {})
        wkey = (wrong.get("annex"), wrong.get("code"))
        ckey = (correct.get("annex"), correct.get("code"))
        if not (isinstance(m.get("why"), str) and m["why"].strip()):
            problems.append("%s: planted miscoding 'why' not named" % mid)
        # the correct target must exist in the lexicon
        if ckey not in index:
            problems.append("%s: correct target %s not in lexicon"
                            % (mid, ckey))
        # a miscoding must actually be a mis-coding
        if wkey == ckey:
            problems.append("%s: wrong and correct codes are identical (%s)"
                            % (mid, ckey))
        # where the wrong pair also exists, its meaning must differ from
        # the correct one (otherwise it is not a distinct miscoding)
        if wkey in index and ckey in index and index[wkey] == index[ckey]:
            problems.append("%s: wrong and correct entries share a meaning"
                            % mid)
        if ckey in index and wkey != ckey:
            miscoding_checks += 1

    if miscoding_checks < 6:
        problems.append("only %d valid planted miscoding checks (bar: >=6)"
                        % miscoding_checks)

    for p in problems:
        lines.append("FAIL  field-codes:" + p)
    if not problems:
        lines.append("PASS  field-code-lexicon  %d codes, %d planted miscoding "
                     "check(s), no duplicate (annex, code) pairs"
                     % (n, miscoding_checks))
    return (not problems), lines


def run_selftest():
    data = load_golden()
    cases = data["cases"]
    total = len(cases)
    passed = 0
    trap_names = set()

    for case in cases:
        cid = case["id"]
        trap = case.get("trap", "<MISSING TRAP>")
        trap_names.add(trap)
        derived = derive_case(case["input"])
        problems = compare_case(derived, case["expected"])
        problems += schema_sanity_check(case)

        if not problems:
            print(f"PASS  {cid}  trap={trap!r}")
            passed += 1
        else:
            print(f"FAIL  {cid}  trap={trap!r}")
            for p in problems:
                print(p)

    negative_controls = sum(
        1 for c in cases if c.get("trap") == "negative control"
    )

    print("-" * 72)
    print(f"cases: {total}  distinct traps: {len(trap_names)}  "
          f"negative controls: {negative_controls}")
    print(f"SELFTEST: {passed}/{total} cases passed")

    # Post-filing divergencias-defense corpus integrity gate.
    print("-" * 72)
    div_ok, div_lines = validate_divergence_corpus()
    for ln in div_lines:
        print(ln)

    # Modelo 3 field-code lexicon gate.
    print("-" * 72)
    fc_ok, fc_lines = validate_field_codes()
    for ln in fc_lines:
        print(ln)

    dossier_ok = (passed == total and total >= 12 and negative_controls >= 1)
    print("-" * 72)
    print(f"OVERALL: dossier-corpus {'PASS' if dossier_ok else 'FAIL'}, "
          f"divergence-corpus {'PASS' if div_ok else 'FAIL'}, "
          f"field-code-lexicon {'PASS' if fc_ok else 'FAIL'}")

    if dossier_ok and div_ok and fc_ok:
        return 0
    return 1


def run_candidate_scoring(candidate_path):
    data = load_golden()
    cases = {c["id"]: c for c in data["cases"]}

    with open(candidate_path, "r", encoding="utf-8") as f:
        candidate = json.load(f)

    total_fields = 0
    matched_fields = 0
    fields = ("income_annex_map", "deduction_inventory", "missing_documents",
              "flags", "filing_regime")

    for cid, case in cases.items():
        cand_case = candidate.get(cid)
        print(f"--- {cid}  trap={case.get('trap')!r} ---")
        if cand_case is None:
            print("    NOT ATTEMPTED (missing from candidate file)")
            total_fields += len(fields)
            continue
        for field in fields:
            total_fields += 1
            d = _diff_field(field, cand_case.get(field), case["expected"].get(field))
            if d:
                print(f"    MISMATCH  {field}")
                print(d)
            else:
                matched_fields += 1
                print(f"    MATCH     {field}")

    print("=" * 72)
    pct = (100.0 * matched_fields / total_fields) if total_fields else 0.0
    print(f"SCORE: {matched_fields}/{total_fields} fields matched ({pct:.1f}%)")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Portugal IRS Dossier Organizer golden-corpus harness"
    )
    parser.add_argument("--selftest", action="store_true",
                         help="validate the bundled golden corpus end-to-end")
    parser.add_argument("candidate", nargs="?",
                         help="path to a candidate.json to score against the "
                              "golden corpus")
    args = parser.parse_args()

    if args.selftest:
        sys.exit(run_selftest())
    elif args.candidate:
        sys.exit(run_candidate_scoring(args.candidate))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
