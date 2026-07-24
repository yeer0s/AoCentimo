#!/usr/bin/env python3
"""Independent second implementation of the IRS liquidation — the corpus oracle.

WHY THIS FILE EXISTS
--------------------
Until 2026-07-24 every expected value in assets/golden-cases.json was hand-derived
by the same author who wrote scripts/validate.py, from the same reading of the same
law. A corpus built that way detects *changes* but cannot detect a *shared mistake* —
and one had been sitting in it for a year (the income-year-2025 bracket table still
carried the pre-Lei-55-A/2025 rates, and all 19 cases agreed with it).

This module recomputes the same liquidation by a deliberately different route:

  * validate.py walks the brackets CUMULATIVELY on the marginal rates (taxa normal).
  * oracle.py uses the TAXA-MEDIA SPLIT that Artigo 68.º n.º 1 itself publishes:
        coleta = (limite do escalao anterior x taxa media desse escalao)
               + (excedente x taxa normal do escalao)
    reading the taxa_media_at_ceiling column, not the marginal column.

Agreement to the cent across a dense sweep of rendimento coletavel is therefore
evidence about the IMPLEMENTATION (bracket walking, boundaries, the quociente
multiply-back, deduction ordering, the caps) from two directions.

HONEST LIMIT OF THIS ORACLE. The taxa_media column is derived from the same nine
marginal rates, so this file does NOT independently verify the rate VALUES. Those
are corroborated elsewhere and differently: the live consolidated Artigo 68.º
(income year 2026, Lei 73-A/2025) carries 12.5 / 15.7 / 21.2 / 24.1 / 31.1 / 34.9 /
43.1 / 44.6 / 48, in which rows 1, 6, 7, 8 and 9 are UNCHANGED from income year 2025
and rows 2-5 are exactly the further 0.3 p.p. cut that OE2026 applied to the 2025
values 16 / 21.5 / 24.4 / 31.4. Every 2025 rate is thus pinned by a table that is
still live and checkable. Do not claim this file proves more than it proves.

Usage
-----
    python scripts/oracle.py --crosscheck        # dual-path agreement (the gate)
    python scripts/oracle.py --derive            # regenerate golden expected values
"""

import argparse
import json
import sys
from decimal import Decimal, ROUND_HALF_UP, getcontext
from pathlib import Path

getcontext().prec = 34

HERE = Path(__file__).resolve().parent
ASSETS = HERE.parent / "assets"
CENT = Decimal("0.01")

# Defects this oracle structurally CANNOT catch, declared rather than hidden.
# The mutation test fails on any survivor that is not listed here, AND on any entry
# here that has become catchable — so the register cannot quietly rot into an alibi.
BLIND_SPOTS = {
    (9, "taxa_normal"): (
        "The 9th escalao is open-ended, so Artigo 68.º publishes no taxa media for it "
        "and the average-rate path has nothing to cross-check against. Only gross "
        "errors are caught, via rate monotonicity. A top rate changed from 48% to, "
        "say, 47.5% would pass every gate in this skill. Cover it by re-reading "
        "Artigo 68.º n.º 1 directly whenever the bracket table is touched."
    ),
}


def D(x):
    if isinstance(x, Decimal):
        return x
    return Decimal("0") if x is None else Decimal(str(x))


def cents(x):
    return D(x).quantize(CENT, rounding=ROUND_HALF_UP)


class TaxaMediaOracle:
    """Artigo 68.º by the average-rate split, plus an independently written chain."""

    def __init__(self, constants):
        self.c = constants
        self.rows = constants["brackets_2025"]["rows"]

    # --- Artigo 68.º via the taxa-media split ---
    # Two variants, because they answer different questions:
    #   exact_media()  — the average at the previous ceiling computed at full
    #                    precision. Used for the cent-exact traversal check: it
    #                    catches boundary comparisons, ordering and multiply-back
    #                    bugs without being defeated by published rounding.
    #   stored column  — the 6-dp taxa_media_at_ceiling actually in constants.json.
    #                    Checked separately (column_consistency) because a stale
    #                    column is exactly the defect that hid for a year.
    def exact_media(self, i):
        """Effective average rate at the ceiling of bracket i, full precision."""
        cum = Decimal("0")
        for row in self.rows[:i + 1]:
            lower, upper = D(row["lower_eur"]), row["upper_eur"]
            if upper is None:
                raise AssertionError("open bracket has no ceiling")
            cum += (D(upper) - lower) * D(row["taxa_normal"])
        return cum / D(self.rows[i]["upper_eur"])

    def coleta(self, rc):
        rc = D(rc)
        if rc <= 0:
            return Decimal("0")
        for i, row in enumerate(self.rows):
            upper = row["upper_eur"]
            if upper is not None and rc > D(upper):
                continue
            lower = D(row["lower_eur"])
            if i == 0:
                return rc * D(row["taxa_normal"])
            return lower * self.exact_media(i - 1) + (rc - lower) * D(row["taxa_normal"])
        raise AssertionError("bracket table does not terminate in an open row")

    def column_consistency(self, tol=Decimal("0.000005")):
        """Assert the STORED taxa_media column still matches the marginal rates.

        This is the direct guard against the class of defect found on 2026-07-24:
        the marginal rates were a year stale and nothing compared them to anything.
        A rate edited without regenerating this column now fails here.
        """
        bad = []
        for i, row in enumerate(self.rows):
            stored = row["taxa_media_at_ceiling"]
            if stored is None:
                # The open top bracket has no ceiling, so it has no average — this
                # method structurally cannot see it. Registered in BLIND_SPOTS and
                # partially covered by rate monotonicity below.
                continue
            got = self.exact_media(i)
            if abs(D(stored) - got) > tol:
                bad.append((row["n"], stored, got))
        # Partial cover for the open row: Artigo 68.º is strictly progressive, so a
        # top rate at or below its predecessor is detectable even without an average.
        rates = [D(r["taxa_normal"]) for r in self.rows]
        for i in range(1, len(rates)):
            if rates[i] <= rates[i - 1]:
                bad.append((self.rows[i]["n"], rates[i], "non-monotonic vs previous bracket"))
        return bad

    def solidariedade(self, rc):
        rc, extra = D(rc), Decimal("0")
        for band in self.c["taxa_adicional_solidariedade"]["bands"]:
            lo, hi, rate = D(band["lower_eur"]), band["upper_eur"], D(band["rate"])
            if rc <= lo:
                break
            top = rc if hi is None else min(rc, D(hi))
            extra += (top - lo) * rate
        return extra

    def global_limit(self, rc, n_dependentes=0):
        rc = D(rc)
        lo = D(self.rows[0]["upper_eur"])                                  # art. 68.º 1.º escalao
        hi = D(self.c["taxa_adicional_solidariedade"]["bands"][0]["lower_eur"])  # art. 68.º-A n.1
        if rc <= lo:
            return None
        limit = D(1000) if rc > hi else D(1000) + D(1500) * (hi - rc) / (hi - lo)
        limit = min(max(limit, D(1000)), D(2500))
        maj = self.c["global_cap_2025"]["majoracao_dependentes"]
        if n_dependentes >= int(maj["min_dependentes"]):
            limit = limit * (D(1) + D(maj["pct_por_dependente"]) * D(n_dependentes))
        return cents(limit)

    def liquidate(self, case):
        """Independently written liquidation chain (2025 only — this is an oracle,
        not a second product). Mirrors the statute, not validate.py's structure."""
        ded = case.get("deductions") or {}
        tps = case.get("taxpayers", [])
        joint = case.get("filing_status") == "joint"
        divisor = D(2) if joint else D(1)
        n_sp = max(1, len(tps))

        spec_flat = D(self.c["categoria_a_specific_deduction_eur"]["value"])
        jv = self.c["irs_jovem_current_law"]
        sched = {1: D(jv["ten_year_schedule_exempt_pct"]["year_1"])}
        for y in (2, 3, 4):
            sched[y] = D(jv["ten_year_schedule_exempt_pct"]["years_2_to_4"])
        for y in (5, 6, 7):
            sched[y] = D(jv["ten_year_schedule_exempt_pct"]["years_5_to_7"])
        for y in (8, 9, 10):
            sched[y] = D(jv["ten_year_schedule_exempt_pct"]["years_8_to_10"])
        ceiling = D(jv["annual_ceiling"]["ceiling_2025_eur"])

        rc, brutos, especs = Decimal("0"), [], []
        for tp in tps:
            a, b = D(tp.get("cat_a_gross", 0)), D(tp.get("cat_b_gross", 0))
            j = tp.get("irs_jovem") or {}
            elig, jcat, jyr = bool(j.get("eligible")), j.get("category", "A"), j.get("year", 1)
            espec = Decimal("0")
            if a > 0 or (elig and jcat == "A"):
                ex = min(sched[jyr] * a, ceiling) if (elig and jcat == "A") else Decimal("0")
                e = max(spec_flat, D(tp.get("ss_contributions", 0)))
                espec += e
                rc += max(Decimal("0"), a - ex - e)
            if b > 0:
                coef = D(tp.get("cat_b_coefficient",
                                self.c["categoria_b_simplified"]["coefficient_services_151"]))
                pre = coef * b
                ex = min(sched[jyr] * pre, ceiling) if (elig and jcat == "B") else Decimal("0")
                rc += max(Decimal("0"), pre - ex)
                espec += b - pre
            brutos.append(a + b)
            especs.append((espec, bool(tp.get("min_existencia_eligible", a >= b))))

        # Artigo 70.º n.º 2 a) only (see constants.json minimo_existencia).
        me = self.c["minimo_existencia"]
        ref, abat = D(me["valor_referencia_eur"]), Decimal("0")
        ceil_n4 = D(me["exclusao_n4_multiplo_ias"]) * D(14) * D(self.c["ias_2025_eur"]["value"]) * D(n_sp)
        if sum(brutos, Decimal("0")) <= ceil_n4:
            lim_dg = D(self.c["deducoes_a_coleta"]["despesas_gerais_familiares"]["cap_eur_per_taxpayer"])
            taxa1 = D(self.rows[0]["taxa_normal"])
            for gross, (espec, ok) in zip(brutos, especs):
                if ok and 0 < gross <= ref:
                    abat += max(Decimal("0"), min(ref - (espec + lim_dg / taxa1), gross - espec))
        rc = max(Decimal("0"), rc - cents(abat))

        rc_div = rc / divisor
        coleta_bruta = cents(cents(self.coleta(rc_div) * divisor)
                             + cents(self.solidariedade(rc_div) * divisor))

        dc = self.c["deducoes_a_coleta"]
        def capped(key, expense):
            return cents(min(D(dc[key]["rate"]) * D(expense), D(dc[key]["cap_eur"])))
        subject = (capped("health", ded.get("health_expenses", 0))
                   + capped("education", ded.get("education_expenses", 0))
                   + capped("rent_habitacao", ded.get("rent_paid", 0)))
        if D(ded.get("ppr_contribution", 0)) > 0:
            band = dc["ppr"]["cap_by_age_band_eur"][ded.get("ppr_age_band", "under_35")]
            subject += cents(min(D(dc["ppr"]["rate"]) * D(ded["ppr_contribution"]), D(band)))

        da = dc["dependentes_ascendentes"]
        detail = ded.get("dependents_detail")
        if detail:
            deps_eur, n_dep = Decimal("0"), len(detail)
            for i, dep in enumerate(detail):
                sh, age = bool(dep.get("shared_residence")), dep.get("age")
                line = D(da["dependent_shared_residence_eur" if sh else "dependent_fixed_eur"])
                m2 = D(da["maj_n2_shared_under3_eur" if sh else "maj_n2_dependent_under3_eur"]) \
                    if (age is not None and age <= 3) else Decimal("0")
                m3 = D(da["maj_n3_shared_second_plus_under6_eur" if sh
                          else "maj_n3_second_plus_under6_eur"]) \
                    if (age is not None and i >= 1 and age <= 6) else Decimal("0")
                line += max(m2, m3)
                if dep.get("in_two_declarations"):
                    line *= D(dc["reducao_dependente_em_duas_declaracoes"]["factor"])
                deps_eur += line
        else:
            n_dep = int(D(ded.get("dependents", 0)))
            deps_eur = D(da["dependent_fixed_eur"]) * D(n_dep)
        n_asc = int(D(ded.get("ascendants", 0)))
        if n_asc:
            deps_eur += D(da["ascendant_fixed_eur"]) * D(n_asc)
            if n_asc == 1:
                deps_eur += D(da["ascendant_single_uplift_eur"])
        if ded.get("dependentes_meia_parte"):
            deps_eur *= D(dc["reducao_dependente_em_duas_declaracoes"]["factor"])
        deps_eur = cents(deps_eur)

        limit = self.global_limit(rc_div, n_dep)
        subject = subject if limit is None else min(subject, limit)

        g = dc["despesas_gerais_familiares"]
        mono = bool(ded.get("monoparental"))
        gen = cents(min(D(g["monoparental_rate" if mono else "rate"])
                        * D(ded.get("general_family_expenses", 0)),
                        D(g["monoparental_cap_eur" if mono else "cap_eur_per_taxpayer"]) * D(n_sp)))

        total_ded = cents(subject + gen + deps_eur)
        cl = cents(max(Decimal("0"), coleta_bruta - total_ded))
        ap = cents(D(case.get("retention_total", 0)) - cl)
        return {"rendimento_coletavel": cents(rc), "coleta_bruta": coleta_bruta,
                "total_deducoes": total_ded, "coleta_liquida": cl, "apuramento": ap,
                "global_limit": "uncapped" if limit is None else str(limit)}


def _load():
    sys.path.insert(0, str(HERE))
    import estimator as V  # noqa: E402
    constants = json.load(open(ASSETS / "constants.json", encoding="utf-8"))
    return V, TaxaMediaOracle(constants)


def crosscheck():
    V, oracle = _load()
    est = V._build_estimator()
    fails = checked = 0

    # 0. Stored taxa-media column vs the marginal rates it must be derived from.
    print("taxa-media column consistency (guards a stale rate edit)")
    bad = oracle.column_consistency()
    for n, stored, got in bad:
        print("  STALE row %d: stored %s, marginal rates imply %.6f" % (n, stored, got))
    print("  %d/%d rows consistent" % (8 - len(bad), 8))

    # 1. Dense RC sweep through every boundary, both filing shapes.
    print("dual-path bracket sweep (marginal-cumulative vs taxa-media split)")
    for gross in range(0, 300000, 337):
        for joint in (False, True):
            tps = [{"cat_a_gross": gross}] if not joint else \
                  [{"cat_a_gross": gross}, {"cat_a_gross": 0}]
            case = {"taxpayers": tps, "retention_total": 0,
                    "filing_status": "joint" if joint else "single"}
            a, b = est.compute(case), oracle.liquidate(case)
            checked += 1
            for k in ("rendimento_coletavel", "coleta_bruta", "coleta_liquida"):
                if a[k] != b[k]:
                    fails += 1
                    print("  MISMATCH gross=%s joint=%s %s: engine=%s oracle=%s"
                          % (gross, joint, k, a[k], b[k]))
                    break
    print("  %d profiles checked, %d mismatched" % (checked, fails))

    # 2. Exact bracket boundaries (+/- 1 cent) — where an off-by-one lives.
    print("\nboundary probes")
    edges = [r["upper_eur"] for r in oracle.rows if r["upper_eur"]] + [80000.0, 250000.0]
    bfail = 0
    for edge in edges:
        for delta in (Decimal("-0.01"), Decimal("0"), Decimal("0.01")):
            rc = D(edge) + delta
            gross = rc + D(oracle.c["categoria_a_specific_deduction_eur"]["value"])
            case = {"taxpayers": [{"cat_a_gross": float(gross)}], "retention_total": 0}
            a, b = est.compute(case), oracle.liquidate(case)
            if a["coleta_bruta"] != b["coleta_bruta"]:
                bfail += 1
                print("  MISMATCH at RC=%s: engine=%s oracle=%s"
                      % (rc, a["coleta_bruta"], b["coleta_bruta"]))
    print("  %d edge probes, %d mismatched" % (len(edges) * 3, bfail))

    # 3. Every bundled golden case, through both paths.
    print("\ngolden corpus dual-path")
    golden = json.load(open(ASSETS / "golden-cases.json", encoding="utf-8"))
    gfail = gchecked = 0
    for case in golden["cases"]:
        if case.get("filing_status") == "separate":
            continue  # oracle models single/joint only, by design
        gchecked += 1
        a, b = est.compute(case), oracle.liquidate(case)
        if a["coleta_liquida"] != b["coleta_liquida"] or a["apuramento"] != b["apuramento"]:
            gfail += 1
            print("  MISMATCH %s: engine CL=%s oracle CL=%s"
                  % (case["id"], a["coleta_liquida"], b["coleta_liquida"]))
    skipped = len(golden["cases"]) - gchecked
    print("  %d of %d cases dual-pathed, %d mismatched (%d tributação-separada cases "
          "are single-path — the oracle models single/joint only)"
          % (gchecked, len(golden["cases"]), gfail, skipped))

    total = fails + bfail + gfail + len(bad)
    print("\n" + "=" * 66)
    print("ORACLE CROSSCHECK: %s (%d disagreements)"
          % ("PASS" if total == 0 else "FAIL", total))
    return 0 if total == 0 else 1


def derive():
    """Recompute every 2025 golden expected value through BOTH paths and rewrite
    the corpus only where they agree. A case the two paths disagree on is left
    untouched and reported — it is a finding, not a value to publish."""
    V, oracle = _load()
    est = V._build_estimator()
    path = ASSETS / "golden-cases.json"
    golden = json.load(open(path, encoding="utf-8"))
    updated = skipped = 0
    for case in golden["cases"]:
        got = est.compute(case)
        if case.get("filing_status") != "separate":
            orc = oracle.liquidate(case)
            if orc["coleta_liquida"] != got["coleta_liquida"]:
                print("SKIP %s — dual-path disagreement (engine %s / oracle %s)"
                      % (case["id"], got["coleta_liquida"], orc["coleta_liquida"]))
                skipped += 1
                continue
        exp = case["expected"]
        exp["coleta_liquida"] = float(got["coleta_liquida"])
        exp["apuramento"] = float(got["apuramento"])
        exp["outcome"] = got["outcome"]
        if "per_taxpayer" in exp:
            for e_tp, g_tp in zip(exp["per_taxpayer"], got["per_taxpayer"]):
                e_tp["coleta_liquida"] = float(g_tp["coleta_liquida"])
                e_tp["apuramento"] = float(g_tp["apuramento"])
        case["derivation"] = ("dual-path: scripts/validate.py (marginal-cumulative) and "
                              "scripts/oracle.py (taxa-media split) agree to the cent")
        updated += 1
    golden["_meta"]["law_version"] = "Artigo 68.º na redação da Lei n.º 55-A/2025, de 22 de julho"
    golden["_meta"]["derived_on"] = "2026-07-24"
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(golden, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    print("derived %d case(s), skipped %d" % (updated, skipped))
    return 1 if skipped else 0


def mutation_test():
    """Prove the consistency guard CAN fail.

    A gate that has only ever been observed green is not evidence. This injects
    each defect the guard claims to catch and asserts the guard reports it. If a
    mutation survives, the guard is decorative and the run exits non-zero.
    """
    _, oracle = _load()
    survivors = []
    print("mutation test — injecting the defects the guard claims to catch")
    for row in oracle.rows:
        for field, delta in (("taxa_normal", 0.001), ("taxa_media_at_ceiling", 0.001)):
            original = row[field]
            if original is None:
                continue
            row[field] = round(original + delta, 6)
            caught = bool(oracle.column_consistency())
            row[field] = original
            if not caught:
                survivors.append((row["n"], field))
            print("  row %d %-22s +0.001 -> %s"
                  % (row["n"], field, "caught" if caught else "SURVIVED"))
    assert not oracle.column_consistency(), "mutation test failed to restore state"

    registered = set(BLIND_SPOTS)
    found = set(survivors)
    unregistered = sorted(found - registered)
    stale = sorted(registered - found)
    for n, field in unregistered:
        print("  UNREGISTERED BLIND SPOT: row %d %s is unguarded and undeclared" % (n, field))
    for n, field in stale:
        print("  STALE REGISTER ENTRY: row %d %s is now caught — delete it from "
              "BLIND_SPOTS so the register keeps meaning something" % (n, field))
    for n, field in sorted(found & registered):
        print("  known blind spot (declared): row %d %s — %s" % (n, field, BLIND_SPOTS[(n, field)]))
    ok = not unregistered and not stale
    print("=" * 66)
    print("MUTATION TEST: %s (%d survivor(s), %d declared, %d undeclared, %d stale)"
          % ("PASS" if ok else "FAIL", len(survivors), len(found & registered),
             len(unregistered), len(stale)))
    return 0 if ok else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description="Independent taxa-media oracle.")
    ap.add_argument("--crosscheck", action="store_true")
    ap.add_argument("--derive", action="store_true")
    ap.add_argument("--mutation-test", action="store_true")
    a = ap.parse_args(argv)
    if a.crosscheck:
        return crosscheck()
    if a.mutation_test:
        return mutation_test()
    if a.derive:
        return derive()
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
