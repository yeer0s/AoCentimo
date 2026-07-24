#!/usr/bin/env python3
"""
Portugal IRS estimator + golden-case validator (multi-year, income years 2022-2025).

MOAT asset for the portugal-irs-estimator skill. Plain Python 3.10+ stdlib only:
no network, no environment access, no eval/exec/subprocess, no writes outside the
skill folder. Fiscal constants are loaded from:
  - assets/constants.json            (income year 2025, declared 2026)
  - assets/constants-multiyear.json  (income years 2022, 2023, 2024)

The estimator is YEAR-PARAMETERIZED. A case with no "income_year" defaults to 2025
and reproduces the original single-year behaviour exactly. A case with
"income_year": 2022|2023|2024 is computed against that year's own bracket table,
IAS, specific deduction, rent cap, global-cap endpoints, and IRS Jovem schedule.

Any year-value that could not be confirmed is stored in the constants as the literal
string "UNKNOWN"; the estimator REFUSES to compute a path that depends on it and
raises a clear error naming the year and field, rather than guessing.

Modes
-----
  python scripts/validate.py --selftest
      Recompute every bundled golden case (2025 corpus) AND every retro-audit case
      (2022-2024 corpus) from inputs, compare to the hand-derived expected values,
      and run the UNKNOWN-refusal guard test. Exit 0 ONLY if everything passes.
      This is the hard gate.

  python scripts/validate.py <candidate.json>
      Score a user-produced output against the estimator (measurement mode).
      Exit 0 on successful scoring.
"""

import argparse
import json
import sys
from decimal import Decimal, ROUND_HALF_UP, getcontext
from pathlib import Path

getcontext().prec = 34

HERE = Path(__file__).resolve().parent
ASSETS = HERE.parent / "assets"
CONSTANTS_PATH = ASSETS / "constants.json"
MULTIYEAR_PATH = ASSETS / "constants-multiyear.json"
GOLDEN_PATH = ASSETS / "golden-cases.json"
RETRO_PATH = ASSETS / "retro-cases.json"

CENT = Decimal("0.01")
UNKNOWN = "UNKNOWN"


def load_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def D(x):
    """Coerce int/float/str/Decimal to Decimal via str (avoids float noise)."""
    if isinstance(x, Decimal):
        return x
    if x is None:
        return Decimal("0")
    return Decimal(str(x))


def cents(x):
    return D(x).quantize(CENT, rounding=ROUND_HALF_UP)


def _outcome(apuramento):
    """Signed apuramento -> outcome label (retention_total - coleta_liquida)."""
    if apuramento > 0:
        return "REEMBOLSO"
    if apuramento < 0:
        return "A_PAGAR"
    return "NEUTRO"


class UnknownValueError(ValueError):
    """Raised when a computation path depends on an UNKNOWN (unconfirmed) constant."""


def _scalar(node, key, default=0):
    """Read a constant that may be stored bare or wrapped in a {value: ...} object."""
    if node is None:
        return default
    if isinstance(node, dict):
        return node.get(key, default)
    return node


def _require_known(value, year, field):
    if value == UNKNOWN:
        raise UnknownValueError(
            "Income year %s field '%s' is UNKNOWN (unconfirmed this build); "
            "computation refused rather than guessed." % (year, field))
    return value


class Estimator:
    """Loads cited constants for each income year and computes the liquidation chain.

    Internally every year is normalised to a uniform `params` dict so the compute
    chain is identical across years; only the numbers differ.
    """

    def __init__(self, constants_2025, multiyear=None):
        self.years = {2025: self._normalize_2025(constants_2025)}
        if multiyear:
            for ystr, block in multiyear.get("years", {}).items():
                self.years[int(ystr)] = self._normalize_multiyear(block, int(ystr))

    # ---- normalisation: constants.json (2025) ----
    def _normalize_2025(self, c):
        brackets = [(D(r["lower_eur"]), r["upper_eur"], D(r["taxa_normal"]))
                    for r in c["brackets_2025"]["rows"]]
        jv = c["irs_jovem_current_law"]
        pct = {
            1: D(jv["ten_year_schedule_exempt_pct"]["year_1"]),
        }
        for y in (2, 3, 4):
            pct[y] = D(jv["ten_year_schedule_exempt_pct"]["years_2_to_4"])
        for y in (5, 6, 7):
            pct[y] = D(jv["ten_year_schedule_exempt_pct"]["years_5_to_7"])
        for y in (8, 9, 10):
            pct[y] = D(jv["ten_year_schedule_exempt_pct"]["years_8_to_10"])
        ceiling = D(jv["annual_ceiling"]["ceiling_2025_eur"])
        cap = {y: ceiling for y in range(1, 11)}
        ded = c["deducoes_a_coleta"]
        return {
            "brackets": brackets,
            "spec_a": D(c["categoria_a_specific_deduction_eur"]["value"]),
            "jovem_pct": pct,
            "jovem_cap": cap,
            "jovem_max_year": 10,
            "dep_fixed": D(ded["dependent_fixed_eur"]["value"]),
            "health": (D(ded["health"]["rate"]), D(ded["health"]["cap_eur"])),
            "edu": (D(ded["education"]["rate"]), D(ded["education"]["cap_eur"])),
            "rent": (D(ded["rent_habitacao"]["rate"]), D(ded["rent_habitacao"]["cap_eur"])),
            "ppr_rate": D(ded["ppr"]["rate"]),
            "ppr_bands": {k: D(v) for k, v in ded["ppr"]["cap_by_age_band_eur"].items()},
            "gen_rate": D(ded["despesas_gerais_familiares"]["rate"]),
            "gen_cap_per_tp": D(ded["despesas_gerais_familiares"]["cap_eur_per_taxpayer"]),
            "gen_rate_mono": D(ded["despesas_gerais_familiares"]["monoparental_rate"]),
            "gen_cap_mono": D(ded["despesas_gerais_familiares"]["monoparental_cap_eur"]),
            # Artigo 78.º n.º 7 fixes the taper endpoints BY REFERENCE, so they are
            # derived here, never hard-coded:
            #   a)/b) lower  = "o valor do 1.º escalão do n.º 1 artigo 68.º"
            #   b)/c) upper  = "o valor mínimo do primeiro escalão do n.º 1 do
            #                   artigo 68.º-A"  -> the solidarity table's first floor.
            # These are DIFFERENT ARTICLES and they do not have to coincide. They
            # coincided in income year 2024 (both 80 000), which is how the upper
            # endpoint came to be hard-coded to Artigo 68.º's 8th-bracket ceiling and
            # then silently followed it to 83 696 when the 2025 brackets moved,
            # granting up to 73.30 EUR of deduction the statute does not allow.
            "gc_lower": D(brackets[0][1]),
            "gc_upper": D(c["taxa_adicional_solidariedade"]["bands"][0]["lower_eur"]),
            "gc_slope": Decimal("1500"),
            "gc_clamp_low": Decimal("1000"),
            "gc_clamp_high": Decimal("2500"),
            "gc_maj_min_deps": int(c["global_cap_2025"]["majoracao_dependentes"]["min_dependentes"]),
            "gc_maj_pct": D(c["global_cap_2025"]["majoracao_dependentes"]["pct_por_dependente"]),
            "deps": {k: D(v) for k, v in c["deducoes_a_coleta"]["dependentes_ascendentes"].items()
                     if isinstance(v, (int, float)) and not isinstance(v, bool)},
            "dep_half_factor": D(c["deducoes_a_coleta"]["reducao_dependente_em_duas_declaracoes"]["factor"]),
            "solidarity": [(D(b["lower_eur"]), b["upper_eur"], D(b["rate"]))
                           for b in c["taxa_adicional_solidariedade"]["bands"]],
            "me_ref": D(c["minimo_existencia"]["valor_referencia_eur"]),
            "me_excl_mult": D(c["minimo_existencia"]["exclusao_n4_multiplo_ias"]),
            "me_taper": c["minimo_existencia"]["taper_L_formula"],
            "ias": D(c["ias_2025_eur"]["value"]),
            "coeff_default": D(c["categoria_b_simplified"]["coefficient_services_151"]),
            "blocked": None,
        }

    # ---- normalisation: constants-multiyear.json (2022-2024) ----
    def _normalize_multiyear(self, b, year):
        try:
            rows = _require_known(b["brackets"]["rows"], year, "brackets")
            brackets = []
            for r in rows:
                _require_known(r["taxa_normal"], year, "brackets.taxa_normal")
                brackets.append((D(r["lower_eur"]), r["upper_eur"], D(r["taxa_normal"])))
            spec_a = D(_require_known(b["categoria_a_specific_deduction_eur"]["value"],
                                      year, "categoria_a_specific_deduction_eur"))
            ded = b["deducoes_a_coleta"]
            gc = b["global_cap"]
            jv = b["irs_jovem"]
            pct, cap = {}, {}
            for row in _require_known(jv["schedule"], year, "irs_jovem.schedule"):
                y = int(row["year"])
                pct[y] = D(_require_known(row["exempt_pct"], year, "irs_jovem.exempt_pct"))
                cap[y] = D(_require_known(row["cap_eur"], year, "irs_jovem.cap_eur"))
            return {
                "brackets": brackets,
                "spec_a": spec_a,
                "jovem_pct": pct,
                "jovem_cap": cap,
                "jovem_max_year": int(jv["max_year"]),
                "dep_fixed": D(ded["dependent_fixed_eur"]["value"]),
                "health": (D(ded["health"]["rate"]), D(ded["health"]["cap_eur"])),
                "edu": (D(ded["education"]["rate"]), D(ded["education"]["cap_eur"])),
                "rent": (D(_require_known(ded["rent_habitacao"]["rate"], year, "rent.rate")),
                         D(_require_known(ded["rent_habitacao"]["cap_eur"], year, "rent.cap_eur"))),
                "ppr_rate": D(ded["ppr"]["rate"]),
                "ppr_bands": {k: D(v) for k, v in ded["ppr"]["cap_by_age_band_eur"].items()},
                "gen_rate": D(ded["despesas_gerais_familiares"]["rate"]),
                "gen_cap_per_tp": D(ded["despesas_gerais_familiares"]["cap_eur_per_taxpayer"]),
                "gen_rate_mono": D(ded["despesas_gerais_familiares"].get("monoparental_rate")
                                   or ded["despesas_gerais_familiares"]["rate"]),
                "gen_cap_mono": D(ded["despesas_gerais_familiares"].get("monoparental_cap_eur")
                                  or ded["despesas_gerais_familiares"]["cap_eur_per_taxpayer"]),
                # Features added after the 2022-2024 corpus was cited. Absent here =>
                # NOT modelled for that year, surfaced as a flag on the result rather
                # than silently applied with a current-year number (see _assess).
                "gc_maj_min_deps": int(gc.get("majoracao_dependentes", {}).get("min_dependentes", 0) or 0),
                "gc_maj_pct": D(gc.get("majoracao_dependentes", {}).get("pct_por_dependente", 0) or 0),
                "deps": {k: D(v) for k, v in ded.get("dependentes_ascendentes", {}).items()
                         if isinstance(v, (int, float)) and not isinstance(v, bool)},
                "dep_half_factor": D(ded.get("reducao_dependente_em_duas_declaracoes", {})
                                     .get("factor", 0.5)),
                "solidarity": [(D(_bnd["lower_eur"]), _bnd["upper_eur"], D(_bnd["rate"]))
                               for _bnd in b.get("taxa_adicional_solidariedade", {}).get("bands", [])],
                "me_ref": b.get("minimo_existencia", {}).get("valor_referencia_eur", UNKNOWN),
                "me_excl_mult": D(b.get("minimo_existencia", {})
                                  .get("exclusao_n4_multiplo_ias", 0) or 0),
                "me_taper": UNKNOWN,
                "ias": D(_scalar(b.get("ias_eur"), "value")),
                "gc_lower": D(_require_known(gc["first_ceiling_eur"], year, "global_cap.first_ceiling_eur")),
                "gc_upper": D(_require_known(gc["last_ceiling_eur"], year, "global_cap.last_ceiling_eur")),
                "gc_slope": D(gc["slope_eur"]),
                "gc_clamp_low": D(gc["clamp_low_eur"]),
                "gc_clamp_high": D(gc["clamp_high_eur"]),
                "coeff_default": D(b["categoria_b_simplified"]["coefficient_services_151"]),
                "blocked": None,
            }
        except UnknownValueError as exc:
            return {"blocked": str(exc)}

    def _params_for(self, year):
        p = self.years.get(int(year))
        if p is None:
            raise ValueError(
                "No constants loaded for income year %s (have %s)."
                % (year, sorted(self.years)))
        if p.get("blocked"):
            raise UnknownValueError(
                "Income year %s is UNKNOWN-blocked: %s" % (year, p["blocked"]))
        return p

    # --- bracket tax on a single (already divided) coletável value ---
    def tax_on(self, p, rc):
        rc = D(rc)
        if rc <= 0:
            return Decimal("0")
        tax = Decimal("0")
        for lower, upper, rate in p["brackets"]:
            if upper is None:
                if rc > lower:
                    tax += (rc - lower) * rate
                break
            upper = D(upper)
            if rc > upper:
                tax += (upper - lower) * rate
            elif rc > lower:
                tax += (rc - lower) * rate
                break
            else:
                break
        return tax

    # --- IRS Jovem exempt slice for one taxpayer's qualifying income ---
    def jovem_exempt(self, p, qualifying_income, year_index):
        yi = int(year_index)
        pct = p["jovem_pct"].get(yi)
        if pct is None:
            raise ValueError(
                "IRS Jovem year must be 1..%d for this income year, got %r"
                % (p["jovem_max_year"], year_index))
        return min(pct * D(qualifying_income), p["jovem_cap"][yi])

    # --- net income (rendimento liquido) contributed by one taxpayer ---
    def taxpayer_components(self, p, tp):
        """Decompose one taxpayer into the pieces the liquidation chain needs.

        Returns net (rendimento líquido contributed to the household RC), gross
        (rendimentos brutos, the art. 70.º base) and espec (deduções específicas,
        the art. 70.º n.º 5 b) term). The split exists because the mínimo de
        existência is computed on gross and specific deductions, not on net.
        """
        jovem = tp.get("irs_jovem") or {}
        eligible = bool(jovem.get("eligible"))
        jcat = jovem.get("category", "A")
        jyear = jovem.get("year", 1)

        net = Decimal("0")
        espec = Decimal("0")

        # Categoria A: exemption on gross, then the specific deduction.
        # Artigo 25.º n.º 2: where mandatory social-security contributions EXCEED the
        # flat limit of n.º 1 a), the deduction is the full amount of those
        # contributions. Modelled when the case supplies ss_contributions; absent, the
        # flat figure applies (its own documented approximation).
        a_gross = D(tp.get("cat_a_gross", 0))
        if a_gross > 0 or (eligible and jcat == "A"):
            exempt_a = Decimal("0")
            if eligible and jcat == "A":
                exempt_a = self.jovem_exempt(p, a_gross, jyear)
            espec_a = max(p["spec_a"], D(tp.get("ss_contributions", 0)))
            espec += espec_a
            net_a = (a_gross - exempt_a) - espec_a
            if net_a < 0:
                net_a = Decimal("0")
            net += net_a

        # Categoria B simplified: coefficient first, then exemption on the result.
        b_gross = D(tp.get("cat_b_gross", 0))
        if b_gross > 0:
            coeff = D(tp.get("cat_b_coefficient", p["coeff_default"]))
            net_b_pre = coeff * b_gross
            exempt_b = Decimal("0")
            if eligible and jcat == "B":
                exempt_b = self.jovem_exempt(p, net_b_pre, jyear)
            net_b = net_b_pre - exempt_b
            if net_b < 0:
                net_b = Decimal("0")
            net += net_b
            # The art. 31.º coefficient IS the cat-B specific deduction (art. 70.º
            # n.º 5 b) names art. 31.º n.º 1 b) explicitly).
            espec += (b_gross - net_b_pre)

        return {
            "net": net,
            "gross": a_gross + b_gross,
            "espec": espec,
            # art. 70.º n.º 2 applies to titulares whose gross income is
            # predominantly cat A / anexo-I activities / pensions.
            "me_eligible": bool(tp.get("min_existencia_eligible", a_gross >= b_gross)),
        }

    def taxpayer_net(self, p, tp):
        """Back-compatible accessor: rendimento líquido only."""
        return self.taxpayer_components(p, tp)["net"]

    # --- Artigo 70.º mínimo de existência: abatimento ao rendimento coletável ---
    def minimo_existencia(self, p, comps, n_sujeitos_passivos, flags):
        """Abatimento por mínimo de existência, per titular, summed.

        Only art. 70.º n.º 2 a) is modelled — titulares whose rendimentos brutos do
        not exceed the valor de referência. The n.º 2 b)/c) taper depends on the
        variable L of n.º 3, whose formula could not be reconstructed from the
        offline capture without producing an absurd result (see constants.json
        minimo_existencia.taper_L_note); it is UNKNOWN and deliberately not guessed.
        Direction of error where the taper would have applied: OVERSTATES tax.
        """
        ref = p.get("me_ref", UNKNOWN)
        if ref == UNKNOWN:
            flags.append("minimo_existencia_nao_modelado_neste_ano")
            return Decimal("0")
        ref = D(ref)

        total_gross = sum((c["gross"] for c in comps), Decimal("0"))
        # n.º 4 a): no abatimento for ANY titular once household gross exceeds
        # 2,2 x 14 x IAS x n.º de sujeitos passivos.
        ceiling = p["me_excl_mult"] * Decimal("14") * p["ias"] * D(n_sujeitos_passivos)
        if p["me_excl_mult"] > 0 and p["ias"] > 0 and total_gross > ceiling:
            return Decimal("0")

        limite_desp_gerais = p["gen_cap_per_tp"]
        taxa_1 = p["brackets"][0][2]
        abat_total = Decimal("0")
        for c in comps:
            if not c["me_eligible"] or c["gross"] <= 0:
                continue
            if c["gross"] > ref:
                if p.get("me_taper") == UNKNOWN:
                    flags.append("minimo_existencia_taper_nao_modelado_brutos_acima_da_referencia")
                continue
            base = ref - (c["espec"] + limite_desp_gerais / taxa_1)
            # n.º 2 d): floor zero, ceiling (brutos - deduções específicas).
            base = max(Decimal("0"), min(base, c["gross"] - c["espec"]))
            abat_total += base
        return cents(abat_total)

    # --- Artigo 68.º-A taxa adicional de solidariedade ---
    def solidarity(self, p, rc_divided, flags):
        bands = p.get("solidarity") or []
        if not bands:
            if rc_divided > Decimal("80000"):
                flags.append("adicional_solidariedade_nao_modelado_neste_ano")
            return Decimal("0")
        extra = Decimal("0")
        for lower, upper, rate in bands:
            if upper is None:
                if rc_divided > lower:
                    extra += (rc_divided - lower) * rate
                break
            upper = D(upper)
            if rc_divided > upper:
                extra += (upper - lower) * rate
            elif rc_divided > lower:
                extra += (rc_divided - lower) * rate
                break
        return extra

    # --- Artigo 78.º-A dependentes e ascendentes (full, with majorações) ---
    def dependentes_ascendentes(self, p, ded, flags):
        """Return (deduction_eur, n_dependentes) per art. 78.º-A.

        `dependents` as a bare integer keeps the legacy behaviour (count x 600, no
        majorações). `dependents_detail` unlocks the full article: a list of
        {age, shared_residence, in_two_declarations}.
        """
        d = p.get("deps") or {}
        detail = ded.get("dependents_detail")
        if not detail:
            n = int(D(ded.get("dependents", 0)))
            if n:
                flags.append("dependentes_sem_detalhe_majoracoes_78a_nao_aplicadas")
            base = p["dep_fixed"] * D(n)
            asc = self._ascendentes(p, ded)
            return cents((base + asc) * self._meia_parte(p, ded)), n

        if not d:
            flags.append("majoracoes_78a_nao_disponiveis_neste_ano")
        total = Decimal("0")
        for i, dep in enumerate(detail):
            shared = bool(dep.get("shared_residence"))
            age = dep.get("age")
            base = (d.get("dependent_shared_residence_eur", Decimal("300")) if shared
                    else d.get("dependent_fixed_eur", p["dep_fixed"]))
            # n.º 2 a) and n.º 3 are NOT cumulative (n.º 4) — take the larger.
            maj_n2 = Decimal("0")
            maj_n3 = Decimal("0")
            if age is not None and age <= 3:
                maj_n2 = (d.get("maj_n2_shared_under3_eur", Decimal("63")) if shared
                          else d.get("maj_n2_dependent_under3_eur", Decimal("126")))
            if age is not None and i >= 1 and age <= 6:
                maj_n3 = (d.get("maj_n3_shared_second_plus_under6_eur", Decimal("150")) if shared
                          else d.get("maj_n3_second_plus_under6_eur", Decimal("300")))
            line = base + max(maj_n2, maj_n3)
            # art. 78.º n.º 9: same dependent on two declarations -> halved per SP.
            if dep.get("in_two_declarations"):
                line *= p["dep_half_factor"]
            total += line
        # dependent lines already carry their own n.º 9 halving; only the
        # ascendentes bundle takes the bundle-level factor.
        return cents(total + self._ascendentes(p, ded) * self._meia_parte(p, ded)), len(detail)

    @staticmethod
    def _meia_parte(p, ded):
        """art. 78.º n.º 9 halving factor, applied once at the deduction total."""
        return p["dep_half_factor"] if ded.get("dependentes_meia_parte") else Decimal("1")

    def _ascendentes(self, p, ded):
        n = int(D(ded.get("ascendants", 0)))
        if n <= 0:
            return Decimal("0")
        d = p.get("deps") or {}
        total = d.get("ascendant_fixed_eur", Decimal("525")) * D(n)
        if n == 1:
            total += d.get("ascendant_single_uplift_eur", Decimal("110"))
        return total

    def _cap(self, rate, cap_eur, expense):
        return cents(min(D(rate) * D(expense), D(cap_eur)))

    def global_limit(self, p, rc):
        """Global dedução-à-coleta cap for a given rendimento coletável."""
        rc = D(rc)
        if rc <= p["gc_lower"]:
            return None  # uncapped
        if rc > p["gc_upper"]:
            return p["gc_clamp_low"]
        raw = (p["gc_clamp_low"]
               + p["gc_slope"] * (p["gc_upper"] - rc) / (p["gc_upper"] - p["gc_lower"]))
        if raw < p["gc_clamp_low"]:
            raw = p["gc_clamp_low"]
        if raw > p["gc_clamp_high"]:
            raw = p["gc_clamp_high"]
        return cents(raw)

    # --- one liquidation unit: a set of taxpayers pooled under a single ---
    # quociente divisor, with one deductions bundle and one retention figure.
    # Called ONCE for single/joint (all taxpayers in one unit, divisor 1/2) and
    # ONCE PER taxpayer for tributação separada (each taxpayer alone, divisor 1).
    def _assess(self, p, taxpayers, divisor, ded, retention, limit_factor=Decimal("1")):
        ded = ded or {}
        retention = D(retention)
        n_taxpayers = max(1, len(taxpayers))
        flags = []

        # 1. rendimento coletável, then the art. 70.º abatimento
        comps = [self.taxpayer_components(p, tp) for tp in taxpayers]
        rc_pre = sum((c["net"] for c in comps), Decimal("0"))
        abat = self.minimo_existencia(p, comps, n_taxpayers, flags)
        rc = max(Decimal("0"), rc_pre - abat)

        # 2. coleta bruta with the art. 69.º quociente, + art. 68.º-A solidariedade.
        #    Both the general rates and the additional rate operate on the DIVIDED
        #    rendimento coletável and are multiplied back (art. 68.º-A n.º 3).
        rc_divided = rc / divisor
        coleta_geral = cents(self.tax_on(p, rc_divided) * divisor)
        coleta_solidariedade = cents(self.solidarity(p, rc_divided, flags) * divisor)
        coleta_bruta = cents(coleta_geral + coleta_solidariedade)

        # 3. deduções à coleta
        # Artigo 78.º n.º 14 a): "No caso do regime de tributacao separada, quando o
        # valor das deducoes a coleta e determinado por referencia ao agregado
        # familiar ... os limites dessas deducoes sao reduzidos para metade."
        # Halved: saude, educacao, encargos com imoveis and the n.º 7 global limit -
        # all defined per agregado. NOT halved: despesas gerais familiares (art.
        # 78.º-B already sets it "por sujeito passivo") and PPR (per taxpayer, by age
        # band). Dependentes are governed by n.º 9 instead. Which caps n.º 14 reaches
        # is the one part of this the offline captures cannot settle outright - the
        # reading applied here is recorded in documented_approximations.
        health = self._cap(p["health"][0], p["health"][1] * limit_factor, ded.get("health_expenses", 0))
        education = self._cap(p["edu"][0], p["edu"][1] * limit_factor, ded.get("education_expenses", 0))
        rent = self._cap(p["rent"][0], p["rent"][1] * limit_factor, ded.get("rent_paid", 0))

        ppr = Decimal("0.00")
        if D(ded.get("ppr_contribution", 0)) > 0:
            band = ded.get("ppr_age_band", "under_35")
            band_cap = p["ppr_bands"][band]
            ppr = cents(min(p["ppr_rate"] * D(ded["ppr_contribution"]), band_cap))

        subject_sum = health + education + rent + ppr

        dependents, n_dependentes = self.dependentes_ascendentes(p, ded, flags)

        # art. 78.º n.º 7 corpo: in tributação conjunta the limit band is chosen on the
        # rendimento coletável AFTER the art. 69.º divisor, not on the pooled figure.
        limit = self.global_limit(p, rc_divided)
        if limit is not None and limit_factor != Decimal("1"):
            limit = cents(limit * limit_factor)   # art. 78.º n.º 14 a)
        # art. 78.º n.º 8: households with three or more dependents get the limit
        # majorado by 5% PER DEPENDENT (all of them, not only those past the second).
        if limit is not None and p["gc_maj_min_deps"] and n_dependentes >= p["gc_maj_min_deps"]:
            limit = cents(limit * (Decimal("1") + p["gc_maj_pct"] * D(n_dependentes)))
        capped_subject = subject_sum if limit is None else min(subject_sum, limit)

        if ded.get("monoparental"):
            gen_rate, gen_cap = p["gen_rate_mono"], p["gen_cap_mono"] * n_taxpayers
        else:
            gen_rate, gen_cap = p["gen_rate"], p["gen_cap_per_tp"] * n_taxpayers
        general = cents(min(gen_rate * D(ded.get("general_family_expenses", 0)), gen_cap))

        total_deducoes = cents(capped_subject + general + dependents)

        # 4. coleta líquida + apuramento
        coleta_liquida = cents(max(Decimal("0"), coleta_bruta - total_deducoes))
        apuramento = cents(retention - coleta_liquida)

        return {
            "rendimento_coletavel": cents(rc),
            "abatimento_minimo_existencia": cents(abat),
            "coleta_bruta": coleta_bruta,
            "coleta_solidariedade": coleta_solidariedade,
            "global_limit": ("uncapped" if limit is None else str(limit)),
            "total_deducoes": total_deducoes,
            "coleta_liquida": coleta_liquida,
            "apuramento": apuramento,
            "outcome": _outcome(apuramento),
            "flags": sorted(set(flags)),
        }

    @staticmethod
    def _taxpayer_gross(tp):
        """Gross income used to pro-rata a case-level retention across spouses."""
        return D(tp.get("cat_a_gross", 0)) + D(tp.get("cat_b_gross", 0))

    # Deduction-attribution convention for tributação separada (documented in
    # constants.json documented_approximations): a case-level household
    # "deductions" bundle is split 50/50 across the two assessments (CIRS default
    # for shared dependents'/family expenses; direction of error: ignores the
    # optimised NIF allocation a couple could elect, so it neither over- nor
    # under-states systematically — it forgoes the best-case split). A
    # per-taxpayer "deductions" object on the taxpayer dict OVERRIDES this split.
    _SPLITTABLE_DED = (
        "health_expenses", "education_expenses", "rent_paid",
        "ppr_contribution", "general_family_expenses",
    )

    def _split_deductions(self, ded, n):
        if not ded:
            return {}
        share = D(1) / D(n)
        out = {}
        for k, v in ded.items():
            out[k] = D(v) * share if k in self._SPLITTABLE_DED else v
        # Dependentes/ascendentes are NOT split by expense share — art. 78.º n.º 9
        # halves the per-dependent deduction itself when the same dependent appears
        # on more than one declaration, which is exactly what tributação separada
        # produces. Flagged here and applied once, at the deduction total, so the
        # legacy integer-count path and the dependents_detail path agree.
        # art. 78.º n.º 9 halves the per-dependent deduction when the same dependent
        # appears on more than one declaration - which is what tributacao separada
        # produces. Apply it EXACTLY ONCE. The detail path halves per dependent line
        # (via in_two_declarations); the legacy integer path and ascendentes have no
        # per-line mechanism, so they use the bundle-level factor. Setting BOTH, as a
        # first version did, quartered the deduction: a single dependent flagged
        # in_two_declarations in a separada case yielded 300.00 combined instead of
        # 600.00. No bundled case exercised that combination.
        if ded.get("dependents_detail"):
            out["dependents_detail"] = [dict(d, in_two_declarations=True)
                                        for d in ded["dependents_detail"]]
        if ded.get("dependents") or ded.get("ascendants"):
            out["dependentes_meia_parte"] = True
        return out

    def _compute_separate(self, p, year, taxpayers, household_ded, household_retention):
        """Tributação separada: assess EACH taxpayer individually, then sum.

        Each spouse has their own rendimento coletável (divisor 1), own coleta,
        own deduções à coleta, own global-cap limit computed on THEIR OWN RC, and
        own retenção. The household comparison figure is the SUM of the individual
        liquidações — NOT one pooled assessment. Attribution conventions:
          * deductions: prefer a per-taxpayer "deductions" object; otherwise the
            case-level household bundle is split 50/50 (see _split_deductions).
          * retention: prefer a per-taxpayer "retention" field; otherwise the
            case-level retention_total is split PRO-RATA to each taxpayer's gross
            income (direction of error: a spouse whose withholding was actually
            heavier than their income share is under-credited, and vice-versa; the
            summed household apuramento is unaffected by the split — only the
            per-taxpayer breakdown is). Both conventions are documented in
            constants.json documented_approximations.
        """
        n = len(taxpayers)
        gross_list = [self._taxpayer_gross(tp) for tp in taxpayers]
        total_gross = sum(gross_list, Decimal("0"))
        household_split = self._split_deductions(household_ded, n)

        breakdown = []
        for i, tp in enumerate(taxpayers):
            unit_ded = tp["deductions"] if tp.get("deductions") else household_split
            if tp.get("retention") is not None:
                unit_ret = D(tp["retention"])
            elif total_gross > 0:
                unit_ret = household_retention * (gross_list[i] / total_gross)
            else:
                unit_ret = household_retention / D(n)
            breakdown.append(self._assess(p, [tp], Decimal("1"), unit_ded, unit_ret,
                                          limit_factor=Decimal("0.5")))

        def _sum(key):
            return cents(sum((u[key] for u in breakdown), Decimal("0")))

        combined_ap = _sum("apuramento")
        return {
            "income_year": int(year),
            "filing_status": "separate",
            "rendimento_coletavel": _sum("rendimento_coletavel"),
            "abatimento_minimo_existencia": _sum("abatimento_minimo_existencia"),
            "coleta_bruta": _sum("coleta_bruta"),
            "coleta_solidariedade": _sum("coleta_solidariedade"),
            "global_limit": "per-taxpayer (tributação separada)",
            "total_deducoes": _sum("total_deducoes"),
            "coleta_liquida": _sum("coleta_liquida"),
            "apuramento": combined_ap,
            "outcome": _outcome(combined_ap),
            "flags": sorted({f for u in breakdown for f in u["flags"]}),
            "per_taxpayer": breakdown,
        }

    def compute(self, case):
        year = case.get("income_year", 2025)
        p = self._params_for(year)

        filing = case.get("filing_status", "single")
        taxpayers = case.get("taxpayers", [])
        ded = case.get("deductions", {}) or {}
        retention = D(case.get("retention_total", 0))

        # Tributação separada with two (or more) taxpayers is NOT one pooled
        # assessment — assess each individually and sum. Single-taxpayer cases and
        # joint filing keep the exact pooled-quociente behaviour below unchanged.
        if filing == "separate" and len(taxpayers) >= 2:
            return self._compute_separate(p, year, taxpayers, ded, retention)

        divisor = Decimal("2") if filing == "joint" else Decimal("1")
        unit = self._assess(p, taxpayers, divisor, ded, retention)
        return {
            "income_year": int(year),
            "rendimento_coletavel": unit["rendimento_coletavel"],
            "abatimento_minimo_existencia": unit["abatimento_minimo_existencia"],
            "coleta_bruta": unit["coleta_bruta"],
            "coleta_solidariedade": unit["coleta_solidariedade"],
            "global_limit": unit["global_limit"],
            "total_deducoes": unit["total_deducoes"],
            "coleta_liquida": unit["coleta_liquida"],
            "apuramento": unit["apuramento"],
            "outcome": unit["outcome"],
            "flags": unit["flags"],
        }


def _build_estimator():
    constants = load_json(CONSTANTS_PATH)
    multiyear = load_json(MULTIYEAR_PATH) if MULTIYEAR_PATH.exists() else None
    return Estimator(constants, multiyear)


def run_golden_selftest(est):
    golden = load_json(GOLDEN_PATH)
    cases = golden["cases"]
    passed = failed = 0
    print("2025 golden corpus (income year 2025, declared 2026)")
    print("-" * 66)
    for case in cases:
        got = est.compute(case)
        exp = case["expected"]
        ok = (got["coleta_liquida"] == cents(exp["coleta_liquida"])
              and got["apuramento"] == cents(exp["apuramento"])
              and got["outcome"] == exp["outcome"])
        # For tributação-separada cases, also verify the per-taxpayer breakdown so
        # the sum can't accidentally match while the decomposition is wrong.
        if "per_taxpayer" in exp:
            got_pt = got.get("per_taxpayer", [])
            ok = ok and len(got_pt) == len(exp["per_taxpayer"])
            for g_tp, e_tp in zip(got_pt, exp["per_taxpayer"]):
                ok = ok and (g_tp["coleta_liquida"] == cents(e_tp["coleta_liquida"])
                             and g_tp["apuramento"] == cents(e_tp["apuramento"]))
        if ok:
            passed += 1
            print("PASS  %-34s CL=%s  apur=%s  %s"
                  % (case["id"], got["coleta_liquida"], got["apuramento"], got["outcome"]))
        else:
            failed += 1
            print("FAIL  %-34s" % case["id"])
            print("      expected CL=%s apur=%s %s"
                  % (cents(exp["coleta_liquida"]), cents(exp["apuramento"]), exp["outcome"]))
            print("      got      CL=%s apur=%s %s"
                  % (got["coleta_liquida"], got["apuramento"], got["outcome"]))
    print("2025 golden: %d/%d passed, %d failed (bar %s)."
          % (passed, passed + failed, failed, golden["_meta"]["min_bar"]))
    return passed, failed


def run_retro_selftest(est):
    if not RETRO_PATH.exists():
        print("RETRO corpus missing (%s)" % RETRO_PATH.name)
        return 0, 1
    retro = load_json(RETRO_PATH)
    cases = retro["cases"]
    passed = failed = 0
    print("\nRetro-audit corpus (income years 2022-2024)")
    print("-" * 66)
    for case in cases:
        try:
            orig = est.compute(case["scenario_original"])
            corr = est.compute(case["scenario_corrected"])
        except ValueError as exc:
            failed += 1
            print("FAIL  %-30s raised %s" % (case["id"], exc))
            continue
        exp = case["expected"]
        recoverable = cents(orig["coleta_liquida"] - corr["coleta_liquida"])
        ok = (orig["coleta_liquida"] == cents(exp["cl_original"])
              and corr["coleta_liquida"] == cents(exp["cl_corrected"])
              and recoverable == cents(exp["recoverable"]))
        # flag consistency: no_recovery flags require recoverable == 0; others > 0.
        flag = exp.get("recoverable_flag", "")
        if flag == "no_recovery_cap_bound":
            ok = ok and recoverable == Decimal("0.00")
        elif flag in ("recoverable", "recoverable_below_materiality",
                      "unrecoverable_time_barred"):
            ok = ok and recoverable > Decimal("0.00")
        if ok:
            passed += 1
            print("PASS  %-30s y%s  recuperavel=%s  [%s]"
                  % (case["id"], orig["income_year"], recoverable, flag))
        else:
            failed += 1
            print("FAIL  %-30s" % case["id"])
            print("      exp cl_orig=%s cl_corr=%s recuperavel=%s"
                  % (cents(exp["cl_original"]), cents(exp["cl_corrected"]),
                     cents(exp["recoverable"])))
            print("      got cl_orig=%s cl_corr=%s recuperavel=%s"
                  % (orig["coleta_liquida"], corr["coleta_liquida"], recoverable))
    print("retro: %d/%d passed, %d failed (bar %s)."
          % (passed, passed + failed, failed, retro["_meta"]["min_bar"]))
    return passed, failed


def run_unknown_guard_test(est):
    """Prove the estimator REFUSES an UNKNOWN-blocked path rather than guessing."""
    print("\nUNKNOWN-refusal guard")
    print("-" * 66)
    synthetic = {
        "brackets": {"rows": [{"lower_eur": 0.0, "upper_eur": None, "taxa_normal": UNKNOWN}]},
        "categoria_a_specific_deduction_eur": {"value": UNKNOWN},
        "deducoes_a_coleta": {
            "dependent_fixed_eur": {"value": 600.0},
            "health": {"rate": 0.15, "cap_eur": 1000.0},
            "education": {"rate": 0.30, "cap_eur": 800.0},
            "rent_habitacao": {"rate": 0.15, "cap_eur": UNKNOWN},
            "ppr": {"rate": 0.20, "cap_by_age_band_eur": {"under_35": 400.0}},
            "despesas_gerais_familiares": {"rate": 0.35, "cap_eur_per_taxpayer": 250.0},
        },
        "global_cap": {"first_ceiling_eur": UNKNOWN, "last_ceiling_eur": UNKNOWN,
                       "slope_eur": 1500.0, "clamp_low_eur": 1000.0, "clamp_high_eur": 2500.0},
        "irs_jovem": {"max_year": 5, "schedule": [{"year": 1, "exempt_pct": UNKNOWN, "cap_eur": UNKNOWN}]},
        "categoria_b_simplified": {"coefficient_services_151": 0.75},
    }
    est.years[1900] = est._normalize_multiyear(synthetic, 1900)
    try:
        est.compute({"income_year": 1900, "taxpayers": [{"cat_a_gross": 20000.0}]})
    except UnknownValueError:
        print("PASS  refused to compute UNKNOWN-blocked income year 1900")
        del est.years[1900]
        return 0
    del est.years[1900]
    print("FAIL  did NOT refuse an UNKNOWN-blocked year")
    return 1


def run_selftest():
    est = _build_estimator()
    print("IRS estimator self-test (multi-year 2022-2025)")
    print("=" * 66)
    gp, gf = run_golden_selftest(est)
    rp, rf = run_retro_selftest(est)
    guard = run_unknown_guard_test(est)
    print("=" * 66)
    total_fail = gf + rf + guard
    print("SUMMARY: 2025 golden %d passed/%d failed | retro %d passed/%d failed | "
          "unknown-guard %s" % (gp, gf, rp, rf, "PASS" if guard == 0 else "FAIL"))
    return 0 if total_fail == 0 else 1


def run_score(candidate_path):
    est = _build_estimator()
    golden = load_json(GOLDEN_PATH)
    golden_by_id = {c["id"]: c for c in golden["cases"]}
    try:
        cand = load_json(Path(candidate_path))
    except Exception as exc:  # noqa: BLE001
        print("ERROR: could not read candidate JSON: %s" % exc)
        return 1
    if isinstance(cand, dict) and "cases" in cand:
        items = cand["cases"]
    elif isinstance(cand, list):
        items = cand
    else:
        items = [cand]

    print("Scoring candidate output against the IRS estimator")
    print("=" * 66)
    checked = matched = 0
    for item in items:
        cid = item.get("id", "<no-id>")
        if "taxpayers" in item or "filing_status" in item:
            source_case = item
        elif cid in golden_by_id:
            source_case = golden_by_id[cid]
        else:
            print("SKIP  %-34s (no inputs and unknown id)" % cid)
            continue
        got = est.compute(source_case)
        checked += 1
        claim_cl = item.get("coleta_liquida")
        claim_ap = item.get("apuramento")
        if claim_cl is None and claim_ap is None:
            print("CALC  %-34s CL=%s  apur=%s  %s"
                  % (cid, got["coleta_liquida"], got["apuramento"], got["outcome"]))
            continue
        cl_ok = claim_cl is None or cents(claim_cl) == got["coleta_liquida"]
        ap_ok = claim_ap is None or cents(claim_ap) == got["apuramento"]
        if cl_ok and ap_ok:
            matched += 1
            print("MATCH %-34s CL=%s  apur=%s  %s"
                  % (cid, got["coleta_liquida"], got["apuramento"], got["outcome"]))
        else:
            print("DIFF  %-34s" % cid)
            print("      claimed  CL=%s  apur=%s" % (claim_cl, claim_ap))
            print("      computed CL=%s  apur=%s  %s"
                  % (got["coleta_liquida"], got["apuramento"], got["outcome"]))
    print("=" * 66)
    print("SCORE: %d checked, %d matched the estimator." % (checked, matched))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="IRS multi-year estimator: --selftest (gate) or score a candidate JSON.")
    parser.add_argument("--selftest", action="store_true",
                        help="Validate the 2025 golden set + retro corpus + unknown-guard (gate).")
    parser.add_argument("candidate", nargs="?", default=None,
                        help="Path to a candidate JSON output to score against the estimator.")
    args = parser.parse_args(argv)

    if args.selftest:
        return run_selftest()
    if args.candidate:
        return run_score(args.candidate)
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
