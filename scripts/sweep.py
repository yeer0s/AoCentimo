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
DOC_COUNT_FILES = ("README.md", "README.pt.md", "SKILL.md",
                   # The demo-GIF spec tells whoever records the asset which frame
                   # to end on. It sat at 43/43 for two releases while the gate
                   # produced 45 — nothing caught it, because the count check only
                   # looked at the three files above. A recorded GIF is the most
                   # public claim this repo makes and the hardest to re-check, so
                   # it belongs under the same guard.
                   # Forward slashes here and split on open, so the check NAME is
                   # byte-identical on Windows and on CI. A check whose name shifts
                   # with the platform cannot be grepped for across the two.
                   "docs/images/IMAGE-SPECS.md")
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


def law_checks(plant=None):
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
    need = {"irs25.md", "irs68.md", "irs69.md", "irs70.md", "irs78.md", "irs78a.md",
            "irs78e.md", "irs84.md"}
    missing = sorted(need - set(files))
    check("law-load-bearing-articles", not missing,
          "25/68/69/70/78/78-A/78-E/84 all captured" if not missing else "MISSING %s" % missing)

    # Every CIRS article the engine or its constants CITE must be captured too. The
    # check above is a hand-kept list, and a hand-kept list only tracks itself: until
    # 2026-09-28, Artigos 25.º, 31.º, 69.º and 12.º-B were cited as the authority for
    # numbers the engine returns while none of them was in the snapshot, and a
    # file-count check (>= 11) said nothing about which files. This one reads the
    # citations out of the engine, so a new citation without a capture goes red.
    uncaptured = uncaptured_citations(_engine_texts() + list(plant or ()), files)
    cited = sorted(set(_cited_articles(_engine_texts())), key=_article_sort_key)
    check("law-cited-articles-captured", not uncaptured,
          "all %d CIRS articles the engine cites are captured" % len(cited)
          if not uncaptured else "CITED BUT NOT CAPTURED: %s" % uncaptured)


# Files whose citations are claims about the law the ENGINE applies. The playbooks
# also cite other codes (RGIT, CPPT, LGT) and would need a parser for which code a
# citation belongs to; these files cite the CIRS unless they say otherwise.
ENGINE_FILES = ("assets/constants.json", "assets/constants-2026.json",
                "assets/constants-multiyear.json",
                "scripts/estimator.py", "scripts/oracle.py", "scripts/deductions.py")
CITE_RE = re.compile(r"(?:Artigo|art\.)\s*(\d+)\.?\s*º(?:-([A-Z]))?", re.IGNORECASE)


def _engine_texts():
    out = []
    for rel in ENGINE_FILES:
        p = os.path.join(ROOT, *rel.split("/"))
        if os.path.exists(p):
            out.append(open(p, encoding="utf-8").read())
    return out


def _cited_articles(texts):
    """CIRS articles cited in `texts`, as '25', '12-B'. Excluded by PROPERTY, never by
    number: a citation followed by "da Lei", "do Decreto-Lei" or "da Portaria" is an
    article of that instrument (Artigo 89.º da Lei n.º 45-A/2024, Artigo 15.º do
    Decreto-Lei n.º 97/2026), one preceded by another code's name belongs to that code
    (Estatuto dos Benefícios Fiscais art. 21.º), and one cited only to say it was
    revoked needs no capture — there is no text left to verify."""
    for t in texts:
        for m in CITE_RE.finditer(t):
            before, after = t[max(0, m.start() - 40):m.start()], t[m.end():m.end() + 40]
            if re.match(r"\s+(?:da\s+Lei|do\s+Decreto-Lei|da\s+Portaria)", after):
                continue
            if re.search(r"Benef[ií]cios Fiscais|EBF|RGIT|CPPT|LGT|CIVA", before):
                continue
            if re.search(r"was REVOKED|revogad", after, re.IGNORECASE):
                continue
            yield m.group(1) + ("-" + m.group(2).upper() if m.group(2) else "")


def _article_sort_key(a):
    num, _, suf = a.partition("-")
    return (int(num), suf)


def uncaptured_citations(texts, files):
    captured = set(files)
    return sorted({a for a in _cited_articles(texts)
                   if "irs%s.md" % a.replace("-", "").lower() not in captured},
                  key=_article_sort_key)


# Every income year with the current-law schema, one file each. The year is read from
# the file's own _meta.income_year; the file name is only where to look.
CURRENT_LAW_FILES = ("constants.json", "constants-2026.json")


def _current_law():
    """[(income_year, constants dict)] for every current-law file, oldest first."""
    out = [(_int(c["_meta"].get("income_year")), c) for c in map(_load, CURRENT_LAW_FILES)]
    return sorted(out, key=lambda yc: yc[0] or 0)


def _default_income_year():
    sys.path.insert(0, HERE)
    import estimator as E  # noqa: E402
    return E.DEFAULT_INCOME_YEAR


def constants_checks(today=None):
    today = today or date.today()
    years = _current_law()
    for year, c in years:
        tag = ":%s" % year
        rows = c["brackets_%s" % year]["rows"]
        check("bracket-rows" + tag, len(rows) == 9, "%d Artigo 68.º rows" % len(rows))
        check("bracket-monotonic" + tag, all(rows[i]["taxa_normal"] > rows[i - 1]["taxa_normal"]
                                             for i in range(1, len(rows))),
              "rates strictly progressive")
        check("bracket-contiguous" + tag,
              all(rows[i]["lower_eur"] == rows[i - 1]["upper_eur"] for i in range(1, len(rows))),
              "no gap or overlap between escalões")
        # Artigo 78.º n.º 7 fixes the taper endpoints by cross-reference to TWO DIFFERENT
        # articles: the lower from Artigo 68.º's 1st escalão, the upper from Artigo
        # 68.º-A's first band floor. This check previously asserted that BOTH tracked
        # Artigo 68.º's bracket ceilings — it encoded the very defect it was meant to
        # catch, and passed green while the upper endpoint was wrong by 3 696 EUR.
        gc = c["global_cap_%s" % year]
        lower = rows[0]["upper_eur"]
        upper = c["taxa_adicional_solidariedade"]["bands"][0]["lower_eur"]
        formula = gc["formula"]
        check("global-cap-lower-endpoint-is-art68-1st" + tag,
              str(int(lower)) in formula,
              "lower endpoint = Artigo 68.º 1.º escalão (%s)" % int(lower))
        check("global-cap-upper-endpoint-is-art68a-floor" + tag,
              str(int(upper)) in formula and str(int(rows[-2]["upper_eur"])) not in formula,
              "upper endpoint = Artigo 68.º-A n.º 1 floor (%s), NOT the Artigo 68.º 8th "
              "ceiling (%s)" % (int(upper), int(rows[-2]["upper_eur"])))
        check("global-cap-uses-divided-rc" + tag,
              gc.get("rc_used") == "AFTER_ARTIGO_69_DIVISOR",
              "Artigo 78.º n.º 7 corpo (divisor) is recorded in the asset")
        maj = gc["majoracao_dependentes"]
        check("global-cap-majoracao-n8" + tag,
              maj["min_dependentes"] == 3 and abs(maj["pct_por_dependente"] - 0.05) < 1e-9,
              "n.º 8: 5% per dependent from 3 dependents up")
        as_of = date.fromisoformat(c["_meta"]["as_of"])
        age = (today - as_of).days
        check("constants-staleness" + tag, age < 400,
              "%d days since as_of (%s)" % (age, as_of))
        if age > 180:
            print("      NOTE: income year %s constants older than 6 months — an Orçamento do "
                  "Estado has probably intervened. Re-read Artigo 68.º before quoting a "
                  "figure." % year)

    # A ROLLING AGE CANNOT SEE THE YEAR BOUNDARY, WHICH IS THE ONLY DATE THE
    # BRACKETS ACTUALLY MOVE ON. With as_of 2026-07-10 the staleness check is still
    # 175 days old on 1 January 2027 — it passes, and passes SILENTLY, because the
    # 6-month NOTE does not fire until the 7th. The first red would be 14 August
    # 2027, months after the filing season in which someone quoted last year's
    # brackets. This is exactly how the superseded income-year-2025 rates survived
    # a year behind a green gate (see the module docstring). The Orçamento do
    # Estado lands on 1 January, so the guard has to be keyed to the year, not to
    # elapsed days.
    #
    # Since 2026-09-28 the repo carries TWO current-law years, and the calendar asks
    # two different questions of them, so there are two checks:
    #
    # 1. constants-declared-year — does the repo carry the income year being FILED
    #    this calendar year at all? The newest declared_year must be >= the calendar
    #    year. With income year 2026 (declared 2027) this is green on 1 January 2027
    #    and red on 1 January 2028, when income year 2027 has to be added.
    # 2. constants-default-year — is the year a case gets WHEN IT NAMES NONE the one
    #    being filed this calendar year? DEFAULT_INCOME_YEAR's declared_year must
    #    EQUAL the calendar year. It goes red on 1 January 2027: from then on a
    #    household asking about "my IRS" means income year 2026, and a default of
    #    2025 would quietly answer last season's question. Flipping it is the moment
    #    to re-read the 2026 law — a 2026 figure can still change until 31 December
    #    2026 (Lei n.º 55-A/2025 did exactly that to 2025, in July) — and to restamp
    #    constants-2026.json as_of.
    declared = [_int(c["_meta"].get("declared_year")) for _, c in years]
    newest = max((d for d in declared if d is not None), default=None)
    ok = newest is not None and newest >= today.year
    check("constants-declared-year", ok,
          "newest declared_year %s covers the %d filing season" % (newest, today.year) if ok
          else "newest declared_year %s is behind the calendar year %d — an Orçamento do "
               "Estado has intervened; add the next income year's constants file"
               % (newest, today.year))
    default = _default_income_year()
    by_year = {y: _int(c["_meta"].get("declared_year")) for y, c in years}
    d_decl = by_year.get(default)
    ok = d_decl is not None and d_decl == today.year
    check("constants-default-year", ok,
          "DEFAULT_INCOME_YEAR %s is the year filed in %d" % (default, today.year) if ok
          else "DEFAULT_INCOME_YEAR %s (declared %s) is not the year filed in %d — flip "
               "estimator.DEFAULT_INCOME_YEAR to %s, re-read that year's law and restamp "
               "its as_of" % (default, d_decl, today.year, today.year - 1))


_INVISIBLE = dict.fromkeys(map(ord, "​‌‍⁠﻿"), None)


def _norm_law(text):
    """Whitespace-normalised, zero-width-stripped, table pipes flattened."""
    text = text.translate(_INVISIBLE).replace("\xa0", " ").replace("|", " ")
    return " ".join(text.split())


def provenance_checks(plant=None, mutate=None):
    """A cited figure must be findable in the text it is cited to.

    constants-2026.json records, for every CIRS figure it uses, the capture that
    holds it and the verbatim phrase. This re-reads the capture on every run, so a
    figure edited without its law, or a phrase that was never in the capture, goes
    red. Figures from outside the CIRS (the IAS portaria, the decreto-lei, the EBF)
    cannot be checked offline; they must at least name instrument, URL and date.
    """
    c = _load("constants-2026.json")
    if mutate:
        mutate(c)   # --self-test only: corrupt a value in memory, never on disk
    entries = list(c.get("provenance", {}).get("entries", [])) + list(plant or ())
    law_dir = os.path.join(ASSETS, "law")
    bodies = {}
    missing, undocumented, offline = [], [], 0
    for e in entries:
        cap = e.get("capture")
        if cap is None:
            if not all(e.get(k) for k in ("instrument", "url", "retrieved", "quote")):
                undocumented.append(e.get("constant"))
            continue
        if cap not in bodies:
            path = os.path.join(law_dir, cap)
            if not os.path.exists(path):
                missing.append("%s (no capture %s)" % (e.get("constant"), cap))
                continue
            bodies[cap] = _norm_law(open(path, encoding="utf-8").read().split("\n---\n\n", 1)[-1])
        if _norm_law(e.get("quote", "")) not in bodies[cap] or not e.get("quote"):
            missing.append(e.get("constant"))
        else:
            offline += 1
    check("constants-2026-quotes-in-capture", entries and not missing,
          "%d cited phrases found verbatim in assets/law/" % offline
          if entries and not missing else "NOT IN THE CITED CAPTURE: %s" % missing[:4])
    # The quotes above prove a phrase is in the law; they do not prove the NUMBER the
    # engine reads is the one in the phrase — a rate edited in `rows` leaves every
    # quote intact. So the stored values are rendered back into the statute's own
    # wording and looked up in the capture. This also covers the open 9th escalão,
    # which the oracle's taxa-média check structurally cannot see (BLIND_SPOTS).
    law68 = _norm_law(open(os.path.join(law_dir, "irs68.md"), encoding="utf-8").read()
                      .split("\n---\n\n", 1)[-1])

    def eur(v):
        return "{:,.0f}".format(v).replace(",", " ")

    def pct(v, dp):
        return ("{:.%df}" % dp).format(v * 100).replace(".", ",")

    unmatched = []
    rows = c["brackets_2026"]["rows"]
    for r in rows:
        lo, hi, rate, avg = r["lower_eur"], r["upper_eur"], r["taxa_normal"], r["taxa_media_at_ceiling"]
        if r["n"] == 1:
            phrase = "Até %s %s %s" % (eur(hi), pct(rate, 2), pct(avg, 3))
        elif hi is None:
            phrase = "Superior a %s %s" % (eur(lo), pct(rate, 2))
        else:
            phrase = "De mais de %s até %s %s %s" % (eur(lo), eur(hi), pct(rate, 2), pct(avg, 3))
        if phrase not in law68:
            unmatched.append("row %d (%s)" % (r["n"], phrase))
    scalars = (
        ("irs78e.md", "aplicando-se no ano de 2026 o limite de %s €"
         % ("%.2f" % c["deducoes_a_coleta"]["rent_habitacao"]["cap_eur"]).replace(".", ",")),
        ("irs70.md", "igual ao maior valor entre %s € e 1,5 × 14 × IAS"
         % eur(c["minimo_existencia"]["valor_referencia_eur"])),
        ("irs68a.md", "rendimento coletável superior a (euro) %s incidem"
         % eur(c["taxa_adicional_solidariedade"]["bands"][0]["lower_eur"])),
    )
    for cap, phrase in scalars:
        body = _norm_law(open(os.path.join(law_dir, cap), encoding="utf-8").read()
                         .split("\n---\n\n", 1)[-1])
        if phrase not in body:
            unmatched.append("%s (%s)" % (cap, phrase))
    check("constants-2026-values-match-law", not unmatched,
          "all %d Artigo 68.º rows (incl. the open 9th) and %d other figures, rendered back "
          "into the statute's wording, are found in their capture" % (len(rows), len(scalars))
          if not unmatched else "STORED VALUE NOT IN THE LAW: %s" % unmatched[:3])
    check("constants-2026-external-sources-documented", not undocumented,
          "%d non-CIRS figures name instrument, URL and retrieval date"
          % sum(1 for e in entries if e.get("capture") is None)
          if not undocumented else "UNDOCUMENTED: %s" % undocumented)


def oracle_checks():
    """The only checks in this file that fail because a NUMBER is wrong."""
    sys.path.insert(0, HERE)
    try:
        import oracle as O
    except Exception as exc:  # noqa: BLE001
        check("oracle-import", False, str(exc))
        return
    _, oracles = O._load()
    for year in sorted(oracles):
        bad = oracles[year].column_consistency()
        check("oracle-taxa-media-consistency:%d" % year, not bad,
              "taxa_media column agrees with the marginal rates"
              if not bad else "STALE rows %s — a rate was edited without its average"
                              % [b[0] for b in bad])
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc_cross, rc_mut = O.crosscheck(), O.mutation_test()
    check("oracle-dual-path", rc_cross == 0,
          "estimator.py and oracle.py agree to the cent across 1782 profiles and 30 "
          "boundary probes per income year (%s), and the golden corpus"
          % ", ".join(map(str, sorted(oracles))))
    check("oracle-mutation-test", rc_mut == 0,
          "every injected rate defect is caught, or declared in oracle.BLIND_SPOTS")


def corpus_checks():
    g = _load("golden-cases.json")
    check("golden-bar", len(g["cases"]) >= g["_meta"]["min_bar"],
          "%d cases (bar %d)" % (len(g["cases"]), g["_meta"]["min_bar"]))
    check("golden-law-version", bool(g["_meta"].get("law_version")),
          "expected values are stamped with the law they were derived under")
    # A case outside the default year was derived under a DIFFERENT law, so the
    # corpus-level stamp does not describe it: it must carry its own.
    default = _default_income_year()
    unstamped = [c["id"] for c in g["cases"]
                 if c.get("income_year", default) != default and not c.get("law_version")]
    check("golden-law-version-per-year", not unstamped,
          "every non-default-year case carries its own law_version"
          if not unstamped else "UNSTAMPED: %s" % unstamped[:4])
    # Every current-law income year has its own hand-derived, dual-pathed cases. A
    # year the engine computes with no golden case behind it is a year no one has
    # ever checked a number for.
    per_year = {}
    for c in g["cases"]:
        per_year[c.get("income_year", default)] = per_year.get(c.get("income_year", default), 0) + 1
    thin = {y: per_year.get(y, 0) for y, _ in _current_law() if per_year.get(y, 0) < 6}
    check("golden-covers-every-current-year", not thin,
          "cases per income year: %s" % ", ".join("%s=%d" % kv for kv in sorted(per_year.items()))
          if not thin else "FEWER THAN 6 CASES: %s" % thin)
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
    # Single source of truth: no second copy of a fiscal constant anywhere. Checked
    # as a PROPERTY — every income year is defined by exactly one file — rather than
    # as a list of file names, so that adding a year's file is not a violation and a
    # per-sub-skill copy of an existing year still is.
    files = sorted(f for f in os.listdir(ASSETS) if f.startswith("constants") and f.endswith(".json"))
    owners = {}
    for f in files:
        c = _load(f)
        ys = ([c["_meta"].get("income_year")] if "income_year" in c.get("_meta", {})
              else list(c.get("years", {})))
        for y in ys:
            owners.setdefault(_int(y), []).append(f)
    doubled = {y: fs for y, fs in owners.items() if len(fs) > 1 or y is None}
    stray = sorted(set(files) - set(CURRENT_LAW_FILES) - {"constants-multiyear.json"})
    check("single-constants-source", not doubled and not stray,
          "each income year %s defined by exactly one file (%s)"
          % (sorted(y for y in owners if y), ", ".join(files))
          if not doubled and not stray
          else "DEFINED TWICE: %s; UNREGISTERED FILES: %s" % (doubled, stray))


def approximations_check():
    """Anything the engine does not model must be declared WITH a direction of error."""
    c = _load("constants.json")
    items = c["documented_approximations"]["items"]
    undirected = [i for i in items if not i.get("direction")]
    check("approximations-have-direction", not undirected,
          "%d documented approximations, all with a direction of error" % len(items)
          if not undirected else "missing direction: %s" % [i["item"][:40] for i in undirected])
    # Income year 2026 inherits the register above and declares only what is new; a
    # new entry without a direction is exactly as unacceptable as an old one.
    c26 = _load("constants-2026.json")["documented_approximations"]
    extra = c26.get("items", [])
    bad26 = [i["item"][:40] for i in extra if not i.get("direction")]
    check("approximations-have-direction:2026",
          c26.get("inherits") == "constants.json" and not bad26,
          "inherits the constants.json register + %d 2026-specific entries, all directed"
          % len(extra) if not bad26 else "missing direction: %s" % bad26)
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


def run(today=None, quiet=False, plant=None, plant_quote=None, mutate_2026=None):
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
        law_checks(plant)
        constants_checks(today)
        provenance_checks(plant_quote, mutate_2026)
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
        docs = [d for d in DOC_COUNT_FILES
                if os.path.exists(os.path.join(ROOT, *d.split("/")))]
        total = len(results) + len(docs)   # this loop adds one check per doc
        for doc in docs:
            t = open(os.path.join(ROOT, *doc.split("/")), encoding="utf-8").read()
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

    The year-boundary check and the citation-coverage check are exercised here. The
    numeric guards are mutation-tested in oracle.py --mutation-test; duplicating
    that would be ceremony. What was NOT covered anywhere else is the calendar and
    the link between a citation and its captured text.
    """
    print("--- normal state ---")
    base = run(quiet=True)
    if any(not ok for _, ok, _ in base):
        print("SELF-TEST ABORTED: the gate is already red")
        return 1
    print("%d/%d green" % (len(base), len(base)))

    # The two calendar checks answer different questions, so each boundary has an
    # exact expected verdict, derived from what the repo CARRIES rather than
    # hard-coded: on 1 January Y the default year must always go red (it was the
    # year filed in Y-1), and constants-declared-year must go red exactly when no
    # carried year is declared in Y or later. With income year 2026 on board, that
    # means: 2027-01-01 -> default red, declared green; 2028-01-01 -> both red.
    newest = max(_int(c["_meta"].get("declared_year")) or 0 for _, c in _current_law())
    for boundary in (date.today().year + 1, date.today().year + 2):
        print("--- 1 January %d ---" % boundary)
        verdict = {n: ok for n, ok, _ in run(today=date(boundary, 1, 1), quiet=True)}
        want_declared = newest >= boundary
        if verdict.get("constants-default-year") is not False:
            print("SELF-TEST FAILED: on 1 January %d the default income year is last "
                  "season's and constants-default-year stayed green" % boundary)
            return 1
        if verdict.get("constants-declared-year") is not want_declared:
            print("SELF-TEST FAILED: on 1 January %d constants-declared-year said %s, but "
                  "the newest carried filing year is %d, so it must say %s"
                  % (boundary, verdict.get("constants-declared-year"), newest, want_declared))
            return 1
        print("constants-default-year RED (flip the default); constants-declared-year %s "
              "(newest carried filing year %d)" % ("green" if want_declared else "RED", newest))
        print("  red on this date: %s" % ", ".join(sorted(n for n, ok in verdict.items() if not ok)))

    print("--- a 2026 figure cited to a phrase its capture does not contain ---")
    failed = [n for n, ok, _ in run(quiet=True, plant_quote=[{
        "constant": "planted: top rate 47,5 %", "capture": "irs68.md",
        "quote": "Superior a 86 634 47,50"}]) if not ok]
    if "constants-2026-quotes-in-capture" not in failed:
        print("SELF-TEST FAILED: a quote absent from its capture passed as verified")
        return 1
    print("the gate caught the unsupported quote: %s" % ", ".join(failed))

    print("--- the 2026 top rate silently changed from 48 % to 47,5 % ---")
    # The oracle cannot see this (the open 9th escalão has no taxa média; see
    # oracle.BLIND_SPOTS). The value-match check must.
    def top_rate(c):
        c["brackets_2026"]["rows"][-1]["taxa_normal"] = 0.475
    failed = [n for n, ok, _ in run(quiet=True, mutate_2026=top_rate) if not ok]
    if "constants-2026-values-match-law" not in failed:
        print("SELF-TEST FAILED: a 2026 rate that is not in the law passed")
        return 1
    print("the gate caught the corrupted top rate: %s" % ", ".join(failed))

    print("--- a CIRS citation with no capture behind it ---")
    failed = [n for n, ok, _ in run(quiet=True, plant=["source: CIRS Artigo 999.º-Z"])
              if not ok]
    if "law-cited-articles-captured" not in failed:
        print("SELF-TEST FAILED: the engine cited an article the snapshot does not "
              "hold and this gate stayed green")
        return 1
    print("the gate caught the uncaptured citation: %s" % ", ".join(failed))

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
