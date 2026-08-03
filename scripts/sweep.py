#!/usr/bin/env python3
"""Unified correctness gate for the portugal-irs skill.

Replaces the three separate sweeps that shipped with 56-organizer, 57-estimator and
58-deductions. Two changes of substance, not just consolidation:

1. THE CROSS-SKILL CHECK IS GONE, BY CONSTRUCTION. The old 58 sweep asserted that
   57's rent/health/education caps equalled 58's. That check could only ever detect
   DIVERGENCE between two copies — it certified agreement, never correctness, so the
   two files were free to be wrong in unison (and were: both carried the superseded
   income-year-2025 bracket rates for a year while every gate stayed green). There is
   now ONE assets/constants.json. Divergence is structurally impossible, so the check
   is not needed; correctness is checked instead, against the law, by the oracle.

2. THE GATE CAN NOW GO RED BECAUSE A NUMBER IS WRONG. Every check in the previous
   sweeps was structural — row counts, file hashes, staleness dates, string presence.
   oracle_checks() below is the first thing here that fails on a bad constant.

Offline, stdlib-only, no network, no subprocess.
"""

import argparse
import contextlib
import hashlib
import io
import json
import os
import re
import sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ASSETS = os.path.join(ROOT, "assets")
# Every file that quotes this gate's own check count back at the reader. Each one
# costs a check, so the total is self-referential by design: add a file here and
# the number every file must state goes up by one.
DOC_COUNT_FILES = ("README.md", "README.pt.md", "SKILL.md")
results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(("PASS  " if ok else "FAIL  ") + name + ("  - " + detail if detail else ""))


def _load(name):
    with open(os.path.join(ASSETS, name), encoding="utf-8") as fh:
        return json.load(fh)


def _int(v):
    """None rather than a raise — a missing or malformed year must FAIL the check
    that reads it, not crash the sweep before the other 45 checks have run."""
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def law_checks():
    law_dir = os.path.join(ASSETS, "law")
    files = sorted(f for f in os.listdir(law_dir) if f.endswith(".md") and f != "INDEX.md")
    check("law-snapshot-present", len(files) >= 11, "%d CIRS articles captured offline" % len(files))
    # Body definition MUST stay byte-identical to the one the digests were recorded
    # against at capture time (the 57-estimator sweep): split on "\n---\n\n", take
    # the remainder, strip trailing newlines. Redefining it silently invalidates
    # every recorded digest and destroys the tamper-evidence.
    #
    # An UNPARSEABLE digest is a FAILURE, never a skip. A first rewrite of this
    # check parsed the header as line.split("sha256/16:")[1].split()[0], which on
    # the real format ("**sha256/16:** <hash>") yields "**" -> stripped to "" -> and
    # an `if recorded and ...` guard then skipped the comparison entirely. All 12
    # captures printed green while nothing was verified. A guard whose all-clear is
    # reachable without doing the work is worse than no guard.
    stale, unreadable = [], []
    for f in files:
        text = open(os.path.join(law_dir, f), encoding="utf-8").read()
        m = re.search(r"sha256/16:\*\*\s*([0-9a-f]{16})", text)
        parts = text.split("\n---\n\n", 1)
        if not m or len(parts) != 2:
            unreadable.append(f)
            continue
        actual = hashlib.sha256(parts[1].rstrip("\n").encode("utf-8")).hexdigest()[:16]
        if m.group(1) != actual:
            stale.append(f)
    check("law-snapshot-digest-readable", not unreadable,
          "every capture states a parseable digest"
          if not unreadable else "NO DIGEST FOUND (check cannot run): %s" % unreadable)
    check("law-snapshot-integrity", not stale and not unreadable,
          "all %d captures match their recorded digest" % len(files)
          if not stale else "TAMPERED/STALE: %s" % stale)
    # The articles the engine actually computes against must all be present.
    need = {"irs68.md", "irs70.md", "irs78.md", "irs78a.md", "irs78e.md", "irs84.md"}
    missing = sorted(need - set(files))
    check("law-load-bearing-articles", not missing,
          "68/70/78/78-A/78-E/84 all captured" if not missing else "MISSING %s" % missing)


def constants_checks(today=None):
    today = today or date.today()
    c = _load("constants.json")
    rows = c["brackets_2025"]["rows"]
    check("bracket-rows", len(rows) == 9, "%d Artigo 68.º rows" % len(rows))
    check("bracket-monotonic", all(rows[i]["taxa_normal"] > rows[i - 1]["taxa_normal"]
                                   for i in range(1, len(rows))),
          "rates strictly progressive")
    check("bracket-contiguous",
          all(rows[i]["lower_eur"] == rows[i - 1]["upper_eur"] for i in range(1, len(rows))),
          "no gap or overlap between escalões")
    # Artigo 78.º n.º 7 fixes the taper endpoints by cross-reference to TWO DIFFERENT
    # articles: the lower from Artigo 68.º's 1st escalão, the upper from Artigo
    # 68.º-A's first band floor. This check previously asserted that BOTH tracked
    # Artigo 68.º's bracket ceilings — it encoded the very defect it was meant to
    # catch, and passed green while the upper endpoint was wrong by 3 696 EUR.
    lower = rows[0]["upper_eur"]
    upper = c["taxa_adicional_solidariedade"]["bands"][0]["lower_eur"]
    formula = c["global_cap_2025"]["formula"]
    check("global-cap-lower-endpoint-is-art68-1st",
          str(int(lower)) in formula, "lower endpoint = Artigo 68.º 1.º escalão (%s)" % int(lower))
    check("global-cap-upper-endpoint-is-art68a-floor",
          str(int(upper)) in formula and str(int(rows[-2]["upper_eur"])) not in formula,
          "upper endpoint = Artigo 68.º-A n.º 1 floor (%s), NOT the Artigo 68.º 8th "
          "ceiling (%s)" % (int(upper), int(rows[-2]["upper_eur"])))
    check("global-cap-uses-divided-rc",
          c["global_cap_2025"].get("rc_used") == "AFTER_ARTIGO_69_DIVISOR",
          "Artigo 78.º n.º 7 corpo (divisor) is recorded in the asset")
    maj = c["global_cap_2025"]["majoracao_dependentes"]
    check("global-cap-majoracao-n8",
          maj["min_dependentes"] == 3 and abs(maj["pct_por_dependente"] - 0.05) < 1e-9,
          "n.º 8: 5% per dependent from 3 dependents up")
    as_of = date.fromisoformat(c["_meta"]["as_of"])
    age = (today - as_of).days
    check("constants-staleness", age < 400, "%d days since as_of (%s)" % (age, as_of))
    if age > 180:
        print("      NOTE: constants older than 6 months — an Orçamento do Estado has "
              "probably intervened. Re-read Artigo 68.º before quoting a figure.")
    # A ROLLING AGE CANNOT SEE THE YEAR BOUNDARY, WHICH IS THE ONLY DATE THE
    # BRACKETS ACTUALLY MOVE ON. With as_of 2026-07-10 the check above is still
    # 175 days old on 1 January 2027 — it passes, and passes SILENTLY, because the
    # 6-month NOTE does not fire until the 7th. The first red would be 14 August
    # 2027, months after the filing season in which someone quoted last year's
    # brackets. This is exactly how the superseded income-year-2025 rates survived
    # a year behind a green gate (see the module docstring). The Orçamento do
    # Estado lands on 1 January, so the guard has to be keyed to the year, not to
    # elapsed days. Both checks stay: this one catches the calendar, the other
    # catches an asset that is simply rotting.
    declared = _int(c["_meta"].get("declared_year"))
    check("constants-declared-year", declared is not None and declared >= today.year,
          "declared_year %s, filing year %d" % (declared, today.year)
          if declared is not None and declared >= today.year
          else "declared_year %s is behind the calendar year %d — an Orçamento do "
               "Estado has intervened; re-read Artigo 68.º and restamp constants.json"
               % (declared, today.year))


def oracle_checks():
    """The only checks in this file that fail because a NUMBER is wrong."""
    sys.path.insert(0, HERE)
    try:
        import oracle as O
    except Exception as exc:  # noqa: BLE001
        check("oracle-import", False, str(exc))
        return
    _, orc = O._load()
    bad = orc.column_consistency()
    check("oracle-taxa-media-consistency", not bad,
          "taxa_media column reproduces the marginal rates"
          if not bad else "STALE rows %s — a rate was edited without regenerating" % [b[0] for b in bad])
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc_cross, rc_mut = O.crosscheck(), O.mutation_test()
    check("oracle-dual-path", rc_cross == 0,
          "estimator.py and oracle.py agree to the cent across 1782 profiles, "
          "30 boundary probes and the golden corpus")
    check("oracle-mutation-test", rc_mut == 0,
          "every injected rate defect is caught, or declared in oracle.BLIND_SPOTS")


def corpus_checks():
    g = _load("golden-cases.json")
    check("golden-bar", len(g["cases"]) >= g["_meta"]["min_bar"],
          "%d cases (bar %d)" % (len(g["cases"]), g["_meta"]["min_bar"]))
    check("golden-law-version", bool(g["_meta"].get("law_version")),
          "expected values are stamped with the law they were derived under")
    check("golden-dual-path-provenance",
          "DUAL-PATH" in g["_meta"].get("method", "").upper(),
          "corpus provenance is dual-path, not self-derived")

    # A provenance STRING is not a derivation. On 2026-07-24 the expected values were
    # regenerated after the Lei 55-A/2025 rate fix while the hand-written `workings`
    # prose was not, leaving 16 of 19 cases showing superseded arithmetic beside a
    # correct answer — and the string check above stayed green throughout. These two
    # checks compare the stated derivation to the values themselves, so prose can no
    # longer drift away from the numbers in silence.
    drift = [c["id"] for c in g["cases"]
             if c.get("derivation_check", {}).get("coleta_liquida") is None
             or abs(c["derivation_check"]["coleta_liquida"]
                    - float(c["expected"]["coleta_liquida"])) > 0.005
             or abs(c["derivation_check"]["apuramento"]
                    - float(c["expected"]["apuramento"])) > 0.005]
    check("golden-derivation-matches-expected", not drift,
          "every case's stated derivation equals its expected values"
          if not drift else "DRIFTED: %s" % drift[:4])

    # Any surviving `workings` prose must actually contain its own expected figure.
    # Prose that cannot state its own answer is stale by definition.
    mute = []
    for c in g["cases"]:
        w = c.get("workings")
        if not w:
            continue
        exp = float(c["expected"]["coleta_liquida"])
        if not any(abs(float(n) - exp) < 0.005 for n in re.findall(r"(\d+\.\d{2})", w)):
            mute.append(c["id"])
    check("golden-workings-not-stale", not mute,
          "live workings prose states its own expected value"
          if not mute else "STALE PROSE: %s" % mute[:4])
    r = _load("retro-cases.json")
    check("retro-bar", len(r["cases"]) >= r["_meta"]["min_bar"],
          "%d retro cases (bar %d)" % (len(r["cases"]), r["_meta"]["min_bar"]))
    m = _load("deduction-matrix.json")
    check("matrix-rows", len(m["rows"]) >= 15, "%d deduction rows" % len(m["rows"]))
    check("field-code-lexicon", len(_load("field-codes.json")["codes"]) >= 40,
          "%d Modelo 3 field codes" % len(_load("field-codes.json")["codes"]))
    # Single source of truth: no second copy of a fiscal constant anywhere.
    dupes = [f for f in os.listdir(ASSETS) if f.startswith("constants") and f.endswith(".json")]
    check("single-constants-source", sorted(dupes) == ["constants-multiyear.json", "constants.json"],
          "one current-year constants file + one retro file; no per-sub-skill copies")


def approximations_check():
    """Anything the engine does not model must be declared WITH a direction of error."""
    c = _load("constants.json")
    items = c["documented_approximations"]["items"]
    undirected = [i for i in items if not i.get("direction")]
    check("approximations-have-direction", not undirected,
          "%d documented approximations, all with a direction of error" % len(items)
          if not undirected else "missing direction: %s" % [i["item"][:40] for i in undirected])
    text = json.dumps(items, ensure_ascii=False).lower()
    for term, label in (("mínimo de existência", "minimo-existencia"),
                        ("solidariedade", "solidariedade"),
                        ("artigo 25", "art25-ss-floor")):
        check("approximation-declared:" + label, term.lower() in text,
              "the register mentions it")


def offline_check():
    """The privacy claim, enforced locally — not only in CI.

    'Zero network calls' is the main reason to trust this with a tax return, so
    it is a gate, not a sentence in a README. offline_audit.py parses every
    shipped file and fails on any networking/subprocess/ctypes import or any
    builtin eval/exec/__import__ call.
    """
    sys.path.insert(0, HERE)
    try:
        import offline_audit as OA
    except Exception as exc:  # noqa: BLE001
        check("offline-audit-import", False, str(exc))
        return
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        clean = not OA.audit(HERE)
        selftest_ok = OA.selftest() == 0
    check("offline-audit", clean,
          "no networking, subprocess, ctypes or dynamic-execution surface in scripts/")
    check("offline-audit-selftest", selftest_ok,
          "the audit was proven able to fail before its clean result was believed")


def disclaimer_check():
    """The output contract must survive edits to SKILL.md.

    This skill hands people euro figures they may act on. The disclaimer is the one
    piece of it that has legal weight, so it is asserted mechanically rather than
    trusted to survive future rewrites — in BOTH languages, and in the mandatory
    (not the advisory) form.
    """
    t = open(os.path.join(ROOT, "SKILL.md"), encoding="utf-8").read()
    for needle, label in (
            ("Not financial, tax or legal advice", "en-header"),
            ("Não é aconselhamento financeiro, fiscal ou jurídico", "pt-header"),
            ("verified by a contabilista certificado (OCC)", "en-verify-duty"),
            ("verificados por um contabilista certificado (OCC)", "pt-verify-duty"),
            ("MANDATORY OUTPUT CONTRACT", "contract-is-mandatory"),
            ("https://mowei.pt", "homepage")):
        check("disclaimer:" + label, needle in t, "present in SKILL.md")
    lic = os.path.join(ROOT, "LICENSE")
    check("license-present", os.path.exists(lic), "MIT LICENSE file shipped")
    if os.path.exists(lic):
        lt = open(lic, encoding="utf-8").read()
        check("license-is-mit", "MIT License" in lt and "WITHOUT WARRANTY OF ANY KIND" in lt,
              "MIT terms intact")
        # LICENSE must stay VERBATIM MIT. Appending a notice to it makes GitHub's
        # licence detector return NOASSERTION and the repo loses its MIT badge —
        # so the not-advice notice lives in its own file instead.
        check("license-is-unmodified-mit", "ADDITIONAL NOTICE" not in lt,
              "no appendix that would defeat licence detection")
    dis = os.path.join(ROOT, "DISCLAIMER.md")
    check("disclaimer-file-present", os.path.exists(dis), "DISCLAIMER.md shipped")
    if os.path.exists(dis):
        dt = open(dis, encoding="utf-8").read()
        flat = " ".join(dt.split())
        check("disclaimer-file-carries-duty",
              "verified by a contabilista certificado (OCC)" in flat,
              "DISCLAIMER.md states the verification duty")


def pii_check():
    # The needle list lives in this file, so this file is excluded — otherwise the
    # check reports itself and the real signal is buried in a guaranteed red.
    needles = ("@gmail.", "@hotmail.", "@outlook.", "@yahoo.", "@icloud.", "@sapo.pt",
               "NIF: 2", "IBAN PT50", "PT50 ", "+351 9", "@googlemail.")
    bad = []
    for root, _dirs, files in os.walk(ROOT):
        for f in files:
            if not f.endswith((".json", ".md", ".py")):
                continue
            path = os.path.join(root, f)
            if os.path.abspath(path) == os.path.abspath(__file__):
                continue
            t = open(path, encoding="utf-8", errors="ignore").read()
            for needle in needles:
                if needle in t:
                    bad.append((f, needle))
    check("pii-hygiene", not bad, "no personal identifiers in shipped assets"
          if not bad else "FOUND %s" % bad)


def run(today=None, quiet=False):
    """One full pass. Returns the results list.

    Was module-level straight-line code. It is a function so that --self-test can
    run the gate a second time under a different date and demand that it goes red;
    a guard nobody has ever seen fail is indistinguishable from one that cannot.
    """
    del results[:]
    with contextlib.redirect_stdout(io.StringIO() if quiet else sys.stdout):
        print("=" * 66)
        print("UNIFIED CORRECTNESS SWEEP — portugal-irs")
        print("=" * 66)
        law_checks()
        constants_checks(today)
        oracle_checks()
        corpus_checks()
        approximations_check()
        offline_check()
        disclaimer_check()
        pii_check()
        # The READMEs tell readers to run this file and quote its check count. A
        # stale number there is a self-inflicted credibility wound on a project
        # whose pitch is "verify every claim yourself" — so the count checks
        # ITSELF against the docs.
        docs = [d for d in DOC_COUNT_FILES if os.path.exists(os.path.join(ROOT, d))]
        total = len(results) + len(docs)   # this loop adds one check per doc
        for doc in docs:
            t = open(os.path.join(ROOT, doc), encoding="utf-8").read()
            # Only lines that invoke the gate. A LIVE claim is the number printed
            # beside the command the reader is told to run; the changelog's
            # "43 -> 45 checks" is a historical record and must stay as written.
            # Scanning the whole file conflated the two, and the only reason it
            # ever passed is that the last release happened to end on the same
            # number the changelog mentioned. Forcing history to track the current
            # count would be editing the record to make a check green.
            lines = [ln for ln in t.splitlines() if "sweep.py" in ln]
            claimed = set(re.findall(
                r"(\d+)\s*(?:/\s*\d+\s*)?(?:structural \+ numeric )?(?:checks|verifica)",
                "\n".join(lines)))
            check("doc-check-count:" + doc, all(int(c) == total for c in claimed),
                  "documents %d checks, which is what this run has"
                  % total if all(int(c) == total for c in claimed)
                  else "claims %s but this run has %d — update the doc"
                       % (sorted(claimed), total))
    return list(results)


def self_test():
    """Prove the gate can go red, and can come back green.

    Only the year-boundary check is exercised here. The numeric guards are
    mutation-tested in oracle.py --mutation-test; duplicating that would be
    ceremony. What was NOT covered anywhere until now is the calendar.
    """
    print("--- normal state ---")
    base = run(quiet=True)
    if any(not ok for _, ok, _ in base):
        print("SELF-TEST ABORTED: the gate is already red")
        return 1
    print("%d/%d green" % (len(base), len(base)))

    print("--- one year past the declared filing year ---")
    future = date(date.today().year + 1, 1, 1)
    failed = [n for n, ok, _ in run(today=future, quiet=True) if not ok]
    if "constants-declared-year" not in failed:
        print("SELF-TEST FAILED: constants a year stale did not raise the alarm — "
              "on 1 January the brackets move and this gate stayed green")
        return 1
    print("the gate caught the year rolling over: %s" % ", ".join(failed))

    print("--- restored ---")
    if any(not ok for _, ok, _ in run(quiet=True)):
        print("SELF-TEST FAILED: did not return to green")
        return 1
    print("green again")
    print()
    print("SELF-TEST OK — the gate knows how to fail and how to pass again")
    return 0


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("-v", "--verbose", action="store_true",
                    help="accepted for compatibility; every check already prints")
    ap.add_argument("--self-test", action="store_true",
                    help="prove the gate can go red, then come back green")
    # argparse exits 2 on an unknown flag. That matters: this file used to ignore
    # argv entirely, so `sweep.py --self-test` ran an ordinary sweep and exited 0
    # — a self-test that never ran, reported as a pass. Found 2026-08-03 by the
    # weekly staleness sweep, which had itself been recording that false green.
    args = ap.parse_args(argv)
    if args.self_test:
        return self_test()
    res = run()
    fails = [r for r in res if not r[1]]
    print("-" * 66)
    print("SWEEP " + ("PASS" if not fails else "FAIL") + ": " +
          "%d/%d checks green" % (len(res) - len(fails), len(res)) +
          ("" if not fails else " — DO NOT DELIVER until resolved"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
