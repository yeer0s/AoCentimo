"""Handoff Dossier — scaffolder and readiness linter.

Creates and checks the standardized handoff folder the Portuguese Personal Finance Desk
produces for immediate handoff to a contabilista certificado (OCC), the household's own
filing session, or a spouse.

Usage:
    python scripts/dossier.py --init  <folder> [--year 2025]   # scaffold (idempotent: only adds missing files)
    python scripts/dossier.py --check <folder> [--full]        # readiness lint; exit 0 = handoff-ready

Rules: plain Python stdlib; no network, no subprocess, no environment access. Writes ONLY
inside the <folder> the user designates (create it OUTSIDE the skill folder, next to the
household's own documents). The dossier deliberately contains the household's real fiscal
data - it is the user's own deliverable for handoff; the skill's no-PII rule governs
MEMORY.md and skill-internal notes, never this folder.
"""
import argparse, datetime, os, re, sys

FILL = "<<FILL"

def t_readme(year):
    return """# Handoff Dossier — IRS income year {y} (filed {y1})

**Prepared:** {today} · by the Portuguese Personal Finance Desk skill suite (draft for review)
**For:** the reviewer — contabilista certificado (OCC), the household's own filing session, or both.

## How to read this folder

| File | What it holds |
|---|---|
| 01-fiscal-profile.md | Household composition, income types, regimes, filing preference |
| 02-income-annex-map.md | Every income item mapped to its Modelo 3 annex, with document status |
| 03-deduction-inventory.md | Per-member deduction categories: Present / Missing / Not applicable |
| 04-movements-ledger.csv | All movements (categorized bank ledger, deductible flags) — from the Budget skill |
| 04b-monthly-closing.md | Monthly closing summaries — from the Budget skill |
| 05-missing-documents.md | What is still missing and where to get each item |
| 06-outliers-questions-suggestions.md | Outliers found, open questions for the reviewer, optimization suggestions |
| 07-deadline-map.md | Dated actions for this cycle |
| 08-estimates.md | Estimate computation chain + scenario comparisons — from the Estimator skill |
| 09-validation-record.md | Gate evidence: selftest + sweep results, qualification status, as-of labels |

## Status summary

<<FILL: three lines - COMPLETE: what is done | MISSING: what is not | DECISIONS NEEDED: what the reviewer must decide>>

**Every figure in this dossier is a draft for professional review — not tax advice. Not affiliated with the AT.**
""".format(y=year, y1=year + 1, today=datetime.date.today().isoformat())

def t_profile(year):
    return """# 01 — Household fiscal profile (income year {y})

<<FILL: agregado members + ages | income types per member | regimes (IRS Jovem / recibos verdes simplified / ex-NHR) | tributacao conjunta vs separada preference | housing situation>>
""".format(y=year)

def t_annexmap(year):
    return """# 02 — Income-to-annex map (Modelo 3, income year {y})

| # | Household member | Income item | Annex | Quadro/Code | Amount status | Supporting document |
|---|---|---|---|---|---|---|
<<FILL: one row per income item; Quadro/Code = the Modelo 3 quadro + campo/benefit code from assets/field-codes.json where the lexicon covers it (e.g. A / Q4 401), else leave "—"; amount status = confirmed-from-document / estimated / missing; unmapped items go to 06 as outliers>>
""".format(y=year)

def t_deductions(year):
    return """# 03 — Deduction inventory (income year {y})

| Member | Category | Status | Document | Notes (cap position, boundary cases) |
|---|---|---|---|---|
<<FILL: one row per member x category (health / education / general-family / housing / PPR / donations / disability / alimony)>>
""".format(y=year)

def t_missing():
    return """# 05 — Missing documents

| Document | Blocks what | Where to get it | Deadline pressure |
|---|---|---|---|
<<FILL: one row per gap, plain-language where-to-get-it>>
"""

def t_outliers():
    return """# 06 — Outliers, questions, suggestions

## Outliers

<<FILL: unmapped income items, boundary cases, anomalies (duplicates, category mismatches, cap exceedances), OCC-routed items - one bullet each, with the file/row it came from>>

## Questions

<<FILL: open questions for the reviewer/OCC - numbered, answerable, each with the decision it unblocks>>

## Suggestions

<<FILL: optimization suggestions with euro impact where computable (NIF allocation, PPR window, habit fixes, category corrections) - clearly labeled as suggestions for review, not advice>>
"""

def t_deadlines(year):
    return """# 07 — Deadline map (cycle: {y} income, filed {y1})

| Date | Action | Status |
|---|---|---|
<<FILL: dated actions anchored to today - validation deadline, reclamacao window, submission window, PPR/donation windows>>
""".format(y=year, y1=year + 1)

def t_validation():
    return """# 09 — Validation record

- Selftest: <<FILL: paste the final summary line of `python scripts/validate.py --selftest`>>
- Sweep: <<FILL: paste the final summary line of `python scripts/sweep.py`>>
- Host-model qualification: <<FILL: qualified / downgraded mode, date, model>>
- Income-year labels: <<FILL: confirm every euro figure in this dossier carries its income year>>
- Memory entry: <<FILL: confirm the run was logged to MEMORY.md (counts only, no PII)>>
"""

def t_estimates(year):
    return """# 08 — Estimates & scenarios (Estimator skill; income year {y})

<<FILL: computation chain (bruto -> deducoes especificas -> coletavel -> coleta -> deducoes a coleta -> apuramento) + scenario deltas (conjunta vs separada, IRS Jovem, PPR top-up) + assumptions list + cross-check result vs official simulator>>
""".format(y=year)

def t_closing():
    return """# 04b — Monthly closing summaries (Budget skill)

<<FILL: per-month income / fixed / variable / savings rate + over-budget categories + deductible-flag handoffs>>
"""

CORE = {
    "00-README.md": t_readme,
    "01-fiscal-profile.md": t_profile,
    "02-income-annex-map.md": t_annexmap,
    "03-deduction-inventory.md": t_deductions,
    "05-missing-documents.md": t_missing,
    "06-outliers-questions-suggestions.md": t_outliers,
    "07-deadline-map.md": t_deadlines,
    "09-validation-record.md": t_validation,
}
BUNDLE = {
    "04-movements-ledger.csv": None,   # written by the Budget skill (CSV, no template)
    "04b-monthly-closing.md": t_closing,
    "08-estimates.md": t_estimates,
}

def render(fn_or_none, year):
    f = fn_or_none
    if f is None:
        return None
    try:
        return f(year)
    except TypeError:
        return f()

def cmd_init(folder, year):
    os.makedirs(folder, exist_ok=True)
    made = 0
    for name, tpl in list(CORE.items()) + list(BUNDLE.items()):
        p = os.path.join(folder, name)
        if os.path.exists(p):
            continue
        content = render(tpl, year)
        if content is None:
            continue  # CSV contributed by sibling skill; not templated
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(content)
        made += 1
        print("OK    scaffolded " + name)
    print("INIT complete: " + str(made) + " file(s) added in " + folder)
    print("Next: fill every <<FILL: ...>> stub, then run --check before handoff.")
    return 0

def cmd_check(folder, full):
    problems = []
    def is_filled(p):
        t = open(p, encoding="utf-8", errors="ignore").read()
        return FILL not in t, t
    for name in CORE:
        p = os.path.join(folder, name)
        if not os.path.isfile(p):
            problems.append(name + ": MISSING"); continue
        ok, t = is_filled(p)
        if not ok:
            problems.append(name + ": unfilled <<FILL>> stub(s) remain")
        if name.startswith("06"):
            for h in ("## Outliers", "## Questions", "## Suggestions"):
                if h not in t:
                    problems.append(name + ": section missing: " + h)
        if name.startswith("09"):
            # gate evidence must look like the ACTUAL harness summary lines, not a bare "pass"
            if not re.search(r"(SELFTEST[^\n]*PASS|\d+/\d+ cases passed)", t, re.I):
                problems.append(name + ": no real selftest summary line pasted (expected e.g. 'SELFTEST: 14/14 cases passed')")
            if not re.search(r"(SWEEP PASS|\d+/\d+ checks green)", t, re.I):
                problems.append(name + ": no real sweep summary line pasted (expected e.g. 'SWEEP PASS: 28/28 checks green')")
    for name in BUNDLE:
        p = os.path.join(folder, name)
        if os.path.isfile(p):
            if not name.endswith(".csv"):
                ok, _ = is_filled(p)
                if not ok:
                    problems.append(name + ": unfilled <<FILL>> stub(s) remain")
        elif full:
            problems.append(name + ": MISSING (required with --full / bundle install)")
        else:
            print("INFO  " + name + " absent - sibling-skill contribution (ok for single-skill install)")
    # integrity manifest verification (if the dossier was sealed with --hash)
    man = os.path.join(folder, "10-hash-manifest.sha256")
    if os.path.isfile(man):
        import hashlib
        recorded = {}
        for line in open(man, encoding="utf-8"):
            parts = line.strip().split("  ", 1)
            if len(parts) == 2:
                recorded[parts[1]] = parts[0]
        for fn, h in recorded.items():
            p = os.path.join(folder, fn)
            if not os.path.isfile(p):
                problems.append("manifest: " + fn + " listed but missing"); continue
            actual = hashlib.sha256(open(p, "rb").read()).hexdigest()
            if actual != h:
                problems.append("manifest: " + fn + " CHANGED since sealing (re-run --hash after edits)")
    for pr in problems:
        print("FAIL  " + pr)
    if problems:
        print("DOSSIER CHECK: FAIL (" + str(len(problems)) + ") - NOT handoff-ready")
        return 1
    print("DOSSIER CHECK: PASS - handoff-ready" + (" (manifest verified)" if os.path.isfile(man) else ""))
    return 0

def cmd_hash(folder):
    """Seal the dossier: write a sha256 manifest of every file (tamper-evidence for handoff)."""
    import hashlib
    man = os.path.join(folder, "10-hash-manifest.sha256")
    lines = []
    for f in sorted(os.listdir(folder)):
        p = os.path.join(folder, f)
        if not os.path.isfile(p) or f == "10-hash-manifest.sha256":
            continue
        lines.append(hashlib.sha256(open(p, "rb").read()).hexdigest() + "  " + f)
    with open(man, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print("OK    sealed " + str(len(lines)) + " file(s) into 10-hash-manifest.sha256")
    print("Recipient can verify integrity: python scripts/dossier.py --check <folder>")
    return 0

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--init", metavar="FOLDER")
    ap.add_argument("--check", metavar="FOLDER")
    ap.add_argument("--hash", metavar="FOLDER", help="seal the dossier with a sha256 manifest")
    ap.add_argument("--year", type=int, default=datetime.date.today().year - 1)
    ap.add_argument("--full", action="store_true")
    a = ap.parse_args()
    if a.init:
        sys.exit(cmd_init(a.init, a.year))
    if a.hash:
        sys.exit(cmd_hash(a.hash))
    if a.check:
        sys.exit(cmd_check(a.check, a.full))
    ap.print_help(); sys.exit(2)

main()
