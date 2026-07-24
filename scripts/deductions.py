#!/usr/bin/env python3
"""
validate.py - schema-validate the cited CIRS art. 78 deduction matrix and run the
planted-case expense scanner for the Portugal IRS Deductions Maximizer skill.

Stdlib only. No network, no environment access, no eval/exec/subprocess, no writes.

Modes
-----
  python scripts/validate.py --selftest
      Schema-check assets/deduction-matrix.json + run every bundled planted case
      through the scanner. Prints per-item PASS/FAIL and a summary line.
      Exit 0 ONLY if every schema check and every planted case passes. This is the gate.

  python scripts/validate.py <candidate.json>
      Score a user-produced expense set against the matrix (measurement).
      Prints the findings the scanner detects. Exit 0 on successful scoring.

The matrix is the single source of truth for rates/caps; the scanner reads it, it
does not hard-code fiscal numbers.
"""

import argparse
import json
import os
import re
import sys
from decimal import Decimal

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MATRIX_PATH = os.path.join(ROOT, "assets", "deduction-matrix.json")
CASES_PATH = os.path.join(ROOT, "assets", "planted-cases.json")
DOUTRINA_PATH = os.path.join(ROOT, "assets", "doutrina-index.json")

REQUIRED_ROW_FIELDS = [
    "id", "category", "legal_basis", "rate", "cap", "income_year",
    "efatura_category", "boundary_conditions", "manual_registration_needed",
    "citation", "as_of",
]
REQUIRED_CAP_FIELDS = ["value", "unit", "scope"]

# Factual cells that must each be cited (row has a valid citation URL) OR set to UNKNOWN.
FACTUAL_CELLS = ["rate", "cap.value"]

AS_OF_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
URL_RE = re.compile(r"^https?://")

MIN_MATRIX_ROWS = 22
MIN_PLANTED_CASES = 8

# Doutrina layer (AT binding-ruling index) integrity bars.
REQUIRED_DOUTRINA_FIELDS = [
    "ruling_ref", "date_or_year", "source_url", "holding",
    "matrix_row_ids", "confidence",
]
VALID_CONFIDENCE = {"primary", "secondary"}
MIN_DOUTRINA_ENTRIES = 25
MIN_ANNOTATED_ROWS = 10


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #
def load_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def load_matrix():
    data = load_json(MATRIX_PATH)
    return data.get("rows", [])


# --------------------------------------------------------------------------- #
# Schema validation
# --------------------------------------------------------------------------- #
def is_valid_citation(cit):
    """A citation is valid if it is a real URL or the honest sentinel UNKNOWN."""
    if not isinstance(cit, str):
        return False
    return bool(URL_RE.match(cit)) or cit == "UNKNOWN"


def cell_value(row, dotted):
    cur = row
    for part in dotted.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def cited_or_unknown(row, dotted):
    """A factual cell passes if its value is UNKNOWN, or the row carries a URL citation."""
    val = cell_value(row, dotted)
    if val == "UNKNOWN":
        return True
    return bool(URL_RE.match(row.get("citation", "")))


def schema_check(rows):
    """Return (ok, list_of_error_strings)."""
    errors = []

    if len(rows) < MIN_MATRIX_ROWS:
        errors.append(f"row count {len(rows)} < minimum bar {MIN_MATRIX_ROWS}")

    seen_ids = set()
    for i, row in enumerate(rows):
        tag = row.get("id", f"<row {i}>")

        for field in REQUIRED_ROW_FIELDS:
            if field not in row or row[field] in (None, ""):
                errors.append(f"[{tag}] missing required field '{field}'")

        rid = row.get("id")
        if rid in seen_ids:
            errors.append(f"[{tag}] duplicate id")
        seen_ids.add(rid)

        cap = row.get("cap")
        if not isinstance(cap, dict):
            errors.append(f"[{tag}] cap must be an object")
        else:
            for cf in REQUIRED_CAP_FIELDS:
                if cf not in cap or cap[cf] in (None, ""):
                    errors.append(f"[{tag}] cap missing '{cf}'")

        # as_of present and ISO-shaped
        as_of = row.get("as_of", "")
        if not (isinstance(as_of, str) and AS_OF_RE.match(as_of)):
            errors.append(f"[{tag}] as_of missing or not YYYY-MM-DD")

        # income_year present
        if not row.get("income_year"):
            errors.append(f"[{tag}] income_year missing")

        # citation shape
        if not is_valid_citation(row.get("citation")):
            errors.append(f"[{tag}] citation must be a URL or the string UNKNOWN")

        # every factual cell cited-or-UNKNOWN
        for cellpath in FACTUAL_CELLS:
            if not cited_or_unknown(row, cellpath):
                errors.append(
                    f"[{tag}] factual cell '{cellpath}'='{cell_value(row, cellpath)}' "
                    f"is neither cited nor UNKNOWN"
                )

        # manual_registration_needed must be boolean
        if not isinstance(row.get("manual_registration_needed"), bool):
            errors.append(f"[{tag}] manual_registration_needed must be true/false")

    return (len(errors) == 0), errors


# --------------------------------------------------------------------------- #
# Scanner
# --------------------------------------------------------------------------- #
def parse_rate(rate_str):
    """Return (fraction, is_of_iva) or (None, False) if the rate is not numeric."""
    if not isinstance(rate_str, str):
        return None, False
    m = re.match(r"\s*(\d+(?:\.\d+)?)\s*%", rate_str)
    if not m:
        return None, False
    frac = Decimal(m.group(1)) / Decimal(100)
    return frac, ("of IVA" in rate_str)


def numeric_cap(cap):
    val = cap.get("value") if isinstance(cap, dict) else None
    if isinstance(val, bool):
        return None
    if isinstance(val, (int, float)):
        return Decimal(str(val))
    return None


def cap_group(row):
    """All art. 78-F IVA-exigencia sectors share one cap; everything else caps per row."""
    if "78-F" in row.get("legal_basis", ""):
        return "IVA-78F"
    return row["id"]


def scan(case, matrix_by_id):
    """Run all detectors against one case; return a sorted, de-duplicated list of finding codes."""
    findings = set()
    deadline = case.get("deadline", None) or "2026-03-02"
    run_date = case.get("run_date", "")
    members = {m["id"]: m for m in case.get("household", {}).get("members", [])}

    credit_by_group = {}
    group_cap = {}

    for exp in case.get("expenses", []):
        row = matrix_by_id.get(exp["matrix_id"])
        if row is None:
            continue

        # ---- cap exceedance (aggregate credit per cap group) ----
        frac, is_iva = parse_rate(row.get("rate"))
        if frac is not None:
            base = Decimal(str(exp.get("iva_borne", 0))) if is_iva else Decimal(str(exp.get("spend", 0)))
            credit = base * frac
            g = cap_group(row)
            credit_by_group[g] = credit_by_group.get(g, Decimal(0)) + credit
            cap_val = Decimal("250") if g == "IVA-78F" else numeric_cap(row.get("cap"))
            if cap_val is not None:
                group_cap[g] = cap_val

        # ---- downgrade: specific category sitting in general expenses ----
        claimed = exp.get("claimed_category", "")
        true_sector = row.get("efatura_category", "")
        if claimed == "Despesas Gerais Familiares" and true_sector != "Despesas Gerais Familiares":
            if true_sector == "Saude":
                findings.add("HEALTH_IN_GENERAL")
            else:
                findings.add("MISCATEGORIZED_DOWNGRADE")

        # ---- displaced-student rent without AT communication ----
        if exp["matrix_id"] == "educacao-deslocado-renda" and not exp.get("at_communication", True):
            findings.add("DISPLACED_RENT_NO_COMMUNICATION")

        # ---- post-deadline pending invoice ----
        if run_date and run_date > deadline and exp.get("status") == "pending":
            findings.add("POST_DEADLINE_PENDING")

        # ---- wrong-NIF allocation: owner filing outside the agregado while a member is inside ----
        owner = members.get(exp.get("nif_owner"))
        if owner is not None and owner.get("in_agregado") is False:
            if any(m.get("in_agregado") for m in members.values()):
                findings.add("WRONG_NIF_ALLOCATION")

        # ---- missing manual registration ----
        if row.get("manual_registration_needed") and exp.get("status") == "not_registered":
            findings.add("MISSING_MANUAL_REGISTRATION")

    # ---- cap exceedance verdict ----
    for g, total in credit_by_group.items():
        cap_val = group_cap.get(g)
        if cap_val is not None and total > cap_val:
            findings.add("CAP_EXCEEDANCE")

    # ---- propinas / pensao double-claim (per child) ----
    edu_children = set()
    pensao_children = set()
    for exp in case.get("expenses", []):
        cid = exp.get("child_id")
        if not cid:
            continue
        row = matrix_by_id.get(exp["matrix_id"])
        if row is None:
            continue
        if row["id"].startswith("educacao") and exp.get("is_propina"):
            edu_children.add(cid)
        if row["id"] == "pensao-alimentos":
            pensao_children.add(cid)
    if edu_children & pensao_children:
        findings.add("PROPINAS_PENSAO_DOUBLE")

    return sorted(findings)


# --------------------------------------------------------------------------- #
# Doutrina layer integrity
# --------------------------------------------------------------------------- #
def load_doutrina():
    data = load_json(DOUTRINA_PATH)
    return data.get("entries", [])


def doutrina_check(rows):
    """Cross-validate the AT binding-ruling index against the matrix.

    Returns (ok, errors, stats). Enforces:
      - every index entry is complete per schema (all required fields, valid
        confidence, non-empty matrix_row_ids, a real source_url);
      - every matrix_row_id in every entry resolves to a real matrix row id;
      - every matrix-row `doutrina` ref resolves to an index entry ruling_ref;
      - the numeric bars (>= MIN_DOUTRINA_ENTRIES entries, 100% with a
        source_url, >= MIN_ANNOTATED_ROWS annotated matrix rows).
    """
    errors = []
    entries = load_doutrina()
    row_ids = {r.get("id") for r in rows}
    ref_index = {}

    with_url = 0
    for i, e in enumerate(entries):
        tag = e.get("ruling_ref", f"<entry {i}>")

        for field in REQUIRED_DOUTRINA_FIELDS:
            val = e.get(field)
            if val in (None, "") or (isinstance(val, list) and not val):
                errors.append(f"[{tag}] missing/empty required field '{field}'")

        ref = e.get("ruling_ref")
        if ref in ref_index:
            errors.append(f"[{tag}] duplicate ruling_ref")
        if ref:
            ref_index[ref] = e

        if e.get("confidence") not in VALID_CONFIDENCE:
            errors.append(f"[{tag}] confidence must be one of {sorted(VALID_CONFIDENCE)}")

        url = e.get("source_url", "")
        if isinstance(url, str) and URL_RE.match(url):
            with_url += 1
        else:
            errors.append(f"[{tag}] source_url must be a real URL (100% coverage required)")

        mrids = e.get("matrix_row_ids")
        if isinstance(mrids, list):
            for rid in mrids:
                if rid not in row_ids:
                    errors.append(f"[{tag}] matrix_row_id '{rid}' does not resolve to a real matrix row")
        else:
            errors.append(f"[{tag}] matrix_row_ids must be a list")

    # every matrix-row doutrina ref must resolve to an index entry
    annotated_rows = 0
    for row in rows:
        refs = row.get("doutrina")
        if refs is None:
            continue
        if not isinstance(refs, list):
            errors.append(f"[{row.get('id')}] doutrina must be a list")
            continue
        if refs:
            annotated_rows += 1
        for ref in refs:
            if ref not in ref_index:
                errors.append(
                    f"[{row.get('id')}] doutrina ref '{ref}' does not resolve to a doutrina-index entry"
                )

    if len(entries) < MIN_DOUTRINA_ENTRIES:
        errors.append(f"doutrina entry count {len(entries)} < minimum bar {MIN_DOUTRINA_ENTRIES}")
    if annotated_rows < MIN_ANNOTATED_ROWS:
        errors.append(f"annotated matrix rows {annotated_rows} < minimum bar {MIN_ANNOTATED_ROWS}")

    stats = {
        "entries": len(entries),
        "with_url": with_url,
        "annotated_rows": annotated_rows,
        "primary": sum(1 for e in entries if e.get("confidence") == "primary"),
        "secondary": sum(1 for e in entries if e.get("confidence") == "secondary"),
    }
    return (len(errors) == 0), errors, stats


# --------------------------------------------------------------------------- #
# Selftest
# --------------------------------------------------------------------------- #
def run_selftest():
    rows = load_matrix()
    matrix_by_id = {r["id"]: r for r in rows}
    cases = load_json(CASES_PATH).get("cases", [])

    all_ok = True
    print("=" * 66)
    print("SCHEMA CHECK  (assets/deduction-matrix.json)")
    print("=" * 66)
    ok, errors = schema_check(rows)
    cited = sum(
        1 for r in rows for c in FACTUAL_CELLS
        if cited_or_unknown(r, c)
    )
    total_cells = len(rows) * len(FACTUAL_CELLS)
    unknown_rows = sum(1 for r in rows if r.get("citation") == "UNKNOWN"
                       or any(cell_value(r, c) == "UNKNOWN" for c in FACTUAL_CELLS))
    if ok:
        print(f"  PASS  {len(rows)} rows, {cited}/{total_cells} factual cells cited-or-UNKNOWN, "
              f"{unknown_rows} row(s) carry an honest UNKNOWN")
    else:
        all_ok = False
        print(f"  FAIL  {len(errors)} schema error(s):")
        for e in errors:
            print(f"          - {e}")

    print("=" * 66)
    print(f"PLANTED CASES  ({len(cases)} cases)")
    print("=" * 66)
    if len(cases) < MIN_PLANTED_CASES:
        all_ok = False
        print(f"  FAIL  case count {len(cases)} < minimum bar {MIN_PLANTED_CASES}")

    neg_controls = 0
    passed = 0
    for case in cases:
        expected = sorted(case.get("expected_findings", []))
        if not expected:
            neg_controls += 1
        got = scan(case, matrix_by_id)
        good = (got == expected)
        passed += 1 if good else 0
        all_ok = all_ok and good
        status = "PASS" if good else "FAIL"
        print(f"  [{status}] {case['case_id']}")
        if not good:
            print(f"           expected: {expected}")
            print(f"           got     : {got}")

    if neg_controls < 1:
        all_ok = False
        print("  FAIL  no negative-control case present (need >= 1 with zero findings)")

    print("=" * 66)
    print("DOUTRINA LAYER  (assets/doutrina-index.json)")
    print("=" * 66)
    d_ok, d_errors, d_stats = doutrina_check(rows)
    if d_ok:
        print(
            f"  PASS  {d_stats['entries']} ruling entries "
            f"({d_stats['primary']} primary / {d_stats['secondary']} secondary), "
            f"{d_stats['with_url']}/{d_stats['entries']} with source_url, "
            f"{d_stats['annotated_rows']} matrix rows annotated; "
            f"all matrix_row_ids and doutrina refs resolve"
        )
    else:
        all_ok = False
        print(f"  FAIL  {len(d_errors)} doutrina integrity error(s):")
        for e in d_errors:
            print(f"          - {e}")

    print("=" * 66)
    summary = (
        f"SELFTEST {'PASS' if all_ok else 'FAIL'}: "
        f"schema {'ok' if ok else 'FAILED'}, "
        f"{len(rows)} matrix rows, "
        f"{cited}/{total_cells} factual cells cited-or-UNKNOWN, "
        f"{passed}/{len(cases)} planted cases pass, "
        f"{neg_controls} negative control(s), "
        f"{d_stats['entries']} doutrina entries / {d_stats['annotated_rows']} rows annotated "
        f"({'ok' if d_ok else 'FAILED'})"
    )
    print(summary)
    return 0 if all_ok else 1


# --------------------------------------------------------------------------- #
# Candidate scoring
# --------------------------------------------------------------------------- #
def score_candidate(path):
    rows = load_matrix()
    matrix_by_id = {r["id"]: r for r in rows}
    data = load_json(path)
    cases = data.get("cases", [data]) if isinstance(data, dict) else data

    print(f"Scoring {len(cases)} case(s) from {os.path.basename(path)} against the matrix:")
    for case in cases:
        cid = case.get("case_id", "<unnamed>")
        got = scan(case, matrix_by_id)
        expected = case.get("expected_findings")
        line = f"  {cid}: findings = {got}"
        if expected is not None:
            match = "MATCH" if sorted(expected) == got else "DIFF"
            line += f"  (expected {sorted(expected)} -> {match})"
        print(line)
    return 0


# --------------------------------------------------------------------------- #
def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate the CIRS art. 78 deduction matrix and scanner.")
    parser.add_argument("candidate", nargs="?", help="path to a candidate expense-set JSON to score")
    parser.add_argument("--selftest", action="store_true", help="run the bundled golden set (gate)")
    args = parser.parse_args(argv)

    if args.selftest:
        return run_selftest()
    if args.candidate:
        return score_candidate(args.candidate)
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
