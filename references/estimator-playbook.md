---
name: portugal-irs-estimator
description: Use when a Portugal resident (native or expat) wants to estimate their IRS (personal income tax) liability, refund, or amount owed from salary/freelance/other income plus withholding and deductions, understand WHY the number comes out that way, decide between joint vs separate filing, IRS Jovem opt-in, or a year-end PPR contribution, OR audit an already-filed PAST return (2022-2024) to recover money left on the table. Scope-outs: does not file the Modelo 3, does not connect to Portal das Financas, does not replace a contabilista certificado (OCC) for complex cases (multiple property sales, foreign income treaties, business restructuring). Ships with a stdlib year-parameterized IRS estimator (income years 2022-2025: brackets, quociente, deduction caps, global-cap formula, and the year-by-year IRS Jovem regime) plus a retro-refund engine validated against 14 current-year + 9 hand-computed retro-audit golden cases with cited correction-path deadlines, distilled from production Portuguese fiscal-engine operating experience.
version: 4.1.0
---

# Portugal IRS Estimator & Refund Navigator

## What this skill does

This skill builds a plain-language IRS (Imposto sobre o Rendimento das Pessoas Singulares) estimate from the numbers the user already has — payslips, recibos verdes totals, e-Fatura summaries, and withholding certificates — and walks the full computation chain from gross income to final refund or payment. It cross-checks the estimate against Portugal's free public calculators and the official Portal das Finanças simulator rather than presenting a single black-box number. It compares filing scenarios (joint vs separate, IRS Jovem opt-in, a year-end PPR top-up) so the user can see the euro difference before deciding. It does NOT touch Portal das Finanças, does not require any login, and does not submit anything on the user's behalf.

## The moat asset

This skill ships with an executable IRS estimator, not just prose rules: a plain-Python-stdlib calculator for the 2025 income year (declared 2026), bundled with a hand-computed golden set that gates every delivery.

- **`scripts/validate.py`** — a self-contained (stdlib-only: no network, no subprocess, no eval) estimator that walks the full liquidation chain: the 9-row Artigo 68.º bracket table, categoria A specific deduction (€4,462.15), the quociente conjugal divide-by-2/multiply-back, deduções à coleta with their per-category caps (health 15%/€1,000, education 30%/€800, rent 15%/€700, PPR age bands €400/€350/€300, general family 35%/€250 per taxpayer, €600/dependent), the income-scaled global cap `1000 + 1500·(83696 − RC)/(83696 − 8059)` clamped to [€1,000, €2,500], the IRS Jovem 10-year exemption ladder against the 55×IAS (€28,737.50) ceiling, and the categoria B 0.75 simplified-regime coefficient.
- **`assets/constants.json`** — every numeric constant with its source cited per bracket row and per cap, plus a **DOCUMENTED APPROXIMATIONS** block naming what the model omits (solidarity surtax, IRS Jovem progressividade, the cat-B 15%-justified-expenses reduction, education/rent cap refinements, withholding simulation, arredondamento) each with the **direction of error** stated.
- **`assets/golden-cases.json`** — 14 cases (min bar 12), each hand-computed *first* (the arithmetic chain lives in a `workings` field) and only then confirmed reproducible by the harness. They span a single cat-A earner, a joint couple with quociente, IRS Jovem year-1 vs year-5, cat-B simplified regime, the refund/a-pagar boundary, global-cap binding vs non-binding, an exact bracket-edge coletável, a PPR age-band-cap boundary, a joint+IRS-Jovem split, a cat-B+IRS-Jovem case, a high earner hitting the flat €1,000 cap, and a zero-income negative control.
- **`assets/constants-multiyear.json`** (v4.0.0) — the same cited-constant asset for **income years 2022, 2023 and 2024**, so the estimator can compute a *past* return on the law as it actually stood that year. Each year carries its own full 9-row Artigo 68.º bracket table, IAS (2022 €443.20 / 2023 €480.43 / 2024 €509.26), categoria-A specific deduction (frozen €4,104 in 2022–2023, raised to €4,350.24 in 2024 by Lei 32/2024), the **rent cap that actually moved** (€502 → €502 → €600 → €700 across 2022→2025), global-cap endpoints that auto-track each year's bracket ceilings, and — the hard part — the **IRS Jovem regime *as it stood that year*, which changed materially every year**: 2022 was 30/30/20/20/10% over 5 years (caps 7.5/7.5/5/5/2.5×IAS); 2023 jumped to 50/40/30/30/25% (12.5/10/7.5/7.5/5×IAS); 2024 to 100/75/50/50/25% (40/30/20/20/10×IAS); then the 2025 reform (in `constants.json`) went to 100/75×3/50×3/25×3 over 10 years with a flat 55×IAS ceiling and no study requirement. Every year-value is source-cited (AT official IRS-Jovem folhetos 2022/2023/2024 read verbatim; Lei 33/2024 / Lei 32/2024; corroborating practitioner tables). Any value that could not be confirmed is stored as the literal `"UNKNOWN"` and the estimator **refuses** to compute a path that depends on it (guard test in the self-test) rather than guessing.
- **`assets/retro-cases.json`** (v4.0.0) — 9 hand-computed **retro-audit** golden cases (min bar 8) that turn the multi-year engine into a *refund finder*: each recomputes a past return with a missed item and reports `recoverable = coleta_liquida_original − coleta_liquida_corrected`. They span a missed PPR (2024), missed rent (2023), unvalidated health invoices (2024), IRS-Jovem-year-1 not opted into (2024, €3,723 recoverable), a **negative control** where the missed PPR recovers nothing because the global cap was already binding, a **time-barred** 2022 case (real €502 arithmetic but every instrument's deadline lapsed), a **below-materiality** €6 case, a joint education case, and a cat-B PPR case. Each case names its **correction instrument and deadline**.

**Why it is hard to reproduce (not impossible — hard):** the value is not any single constant (those are public law) but the *assembled, self-consistent chain across four different years' rules* — bracket cumulation, quociente reversal, the order in which caps and the global limit compose, which deductions sit inside vs outside that limit, and the four distinct IRS Jovem regimes — pinned by hand-derived golden sets that make a silent regression fail loudly. Assembling the historical tables correctly (the 2024 mid-year Lei 33/2024 table alone is routinely confused with both the OE2024 draft and the 2025 table) and wiring the retro-recovery arithmetic to the *correct legal correction path and its deadline* is the work. The asset is **distilled from operating experience with production Portuguese fiscal-calculation engines**: structural knowledge of public tax law only, containing zero proprietary code.

**How each mode uses it:** Execute mode runs the estimator as an independent recomputation of the manual chain before cross-checking against the public calculators; a **Retro pass is an Execute variant over a past income year** (2022–2024) that recomputes the filed return, quantifies recoverable euros, and routes to the correct correction instrument (see Execute step R and the Retro-audit decision table). Validate mode treats the self-test as a hard gate. **Hard-gate wiring: a failing or un-run `python scripts/validate.py --selftest` (must exit 0 — all 14 current-year golden cases, all 9 retro cases, and the UNKNOWN-refusal guard must PASS) means the estimator is not trustworthy this session — do not deliver a final REEMBOLSO/A PAGAR or a recoverable-refund figure until it passes.**

### Offline law snapshot (assets/law/)

Ten load-bearing CIRS articles ship as dated, hashed, verbatim captures of the AT's
consolidated text (retrieved 2026-07-10 from info.portaldasfinancas.gov.pt): art. 68.º
(rates), 70.º (minimo de existencia), 78.º and 78.º-A through 78.º-F (the deduction
family), and 83.º-A (pensoes de alimentos). See `assets/law/INDEX.md`.

- **Purpose:** offline/air-gapped verification of rule TEXT when no network is available.
- **Year discipline:** the snapshot is the law as consolidated at retrieval — parts already
  reflect income-year-2026 amendments (notably the art. 68.º table, Lei 73-A/2025), while
  this skill's operational constants target income year 2025 (filed 2026). Each snapshot
  header says which; when they differ, the constants/matrix govern the current filing
  season and the snapshot governs "what does the statute say".
- **Decay:** snapshots decay with every budget law. For live filings, the live page (URL in
  each file header) outranks the snapshot; the snapshot outranks model memory.

### Automatic correctness sweep (scripts/sweep.py)

A second deterministic gate that runs alongside the golden-corpus selftest:
`python scripts/sweep.py` (stdlib only, offline, exit 0 = green). It checks, automatically:

- **Asset integrity** — the golden corpus parses and still meets its numeric bars; the
  multi-year constants (≥3 income years, 9 bracket rows each) and the retro-audit corpus
  (≥8 cases, with the negative-control / time-barred / below-materiality flags all present)
  parse and meet their bars; the four correction-path instruments are present and cited; law
  snapshots (where bundled) re-hash to their recorded sha256 (tamper/corruption detection).
- **Staleness** — retrieval and as-of dates are age-checked: a warning past ~10 months, a
  hard FAIL past ~14 months (a budget law has almost certainly superseded values by then).
- **Cross-skill agreement** — when sibling suite skills are installed, shared fiscal values
  (rent/health/education caps, the two education uplifts) are compared between the
  estimator's constants and the deduction matrix; any drift fails the sweep. A yearly
  refresh must update both sides or the sweep catches the miss.
- **PII hygiene** — MEMORY.md and any profile file are scanned for NIF-shaped, IBAN-shaped,
  and email-shaped strings; a hit fails the sweep (the no-PII contract, enforced by code).
- **Protocol presence** — income-year labeling convention and the weak-model contract are
  confirmed present.

**When it runs (automatic triggers):** at session start whenever Monitor mode opens a
check-in; before ANY Validate-mode delivery; and after any edit to assets (including a
yearly refresh). **The Validate hard gate is dual:** `python scripts/validate.py --selftest`
exit 0 AND `python scripts/sweep.py` exit 0 — a run failing either is presented as
draft-with-gaps, never as done.

## Requirements

**Zero-setup path (default): none.** No API keys, no logins, no Portal das Finanças credentials — ever. This skill only reads files the user pastes or uploads and reads public web pages.

Works from whatever subset of these the user has on hand:
- Payslip(s) or an annual salary summary (rendimento bruto, retenção na fonte total, Segurança Social)
- Recibos verdes annual total + retenção na fonte withheld (if category B / self-employed)
- e-Fatura year-end summary by category (saúde, educação, habitação, despesas gerais familiares) — screenshot, PDF export, or pasted totals
- Household composition: married/civil union or single, number of dependents, ages
- Age (for IRS Jovem eligibility) and, if applicable, which year of professional activity this is
- Any PPR (Plano Poupança Reforma) contributions made or being considered
- IMI / rent paid, if relevant to the habitação deduction

If the user only has rough figures ("I earn about €1,800/month, no idea about deductions"), the skill still produces a working estimate with stated assumptions, clearly flagged as rough.

## Modes

Every engagement runs through one or more of these five modes. Each has a stated purpose, required inputs, produced outputs, and a **failable check** — a concrete condition that blocks moving to the next mode if it isn't met.

### Research

**Purpose:** establish the correct legal/fiscal context before touching any number — income year, filing window, and which rule version applies.

**Inputs:** today's date (or the date the user says they're planning around), the income year in question, any prior fiscal profile already built this session or by 56-portugal-irs-organizer.

**Outputs:** a stated income year, filing window, and a one-line note on whether that window is currently open, upcoming, or closed as of today.

**Failable check:** if the user's question spans a year boundary (e.g. "what will I owe next year" or a PPR timing decision made in December) and only one year's table has been pulled, STOP and pull both years' tables before proceeding — do not silently apply one year's assumptions to a question that spans two.

### Plan

**Purpose:** decide which computation branches actually apply to this household before gathering numbers, so the conversation doesn't ask for irrelevant fields.

**Inputs:** income categories present (A/B/F/G/H), household structure (single/married/civil union, dependents), age (IRS Jovem candidacy), any PPR activity, whether a joint/separate or IRS Jovem decision is live this year.

**Outputs:** a short plan naming which Domain playbook subsections will be invoked (e.g. "categoria A + B, married, IRS Jovem year 2, no PPR decision this year — skip conjugal-divorce edge cases and mais-valias").

**Failable check:** if any household member has income with no mapped annex/category in the Domain playbook (e.g. categoria G capital gains, foreign income), STOP and flag it for routing to an OCC before drafting a plan that silently omits it.

### Execute

**Purpose:** run the actual computation chain and produce the estimate. This is the v1 Workflow, unchanged in substance, folded in here.

**Fiscal profile (reuse pattern):** if a fiscal profile already exists in this session or was built by 56-portugal-irs-organizer (income year, household type, dependents, category A/B totals, e-Fatura category summaries), reuse it instead of re-asking. Otherwise gather the minimum fields below inline as step 1.

1. **Establish the income year and filing context.** Default to the current live filing campaign: rendimentos 2025, entrega 1 Abril–30 Junho 2026, e-Fatura validation deadline 2 Março 2026 (as-of 2026-07-10 — this window may already be closed depending on when the skill runs; check the current date and say so explicitly). If the user is planning ahead for rendimentos 2026 (declared 2027), use the 2026 tables and flag the change points explicitly (see Domain playbook).

2. **Collect inputs conversationally**, category by category (rendimento categoria A salary, categoria B recibos verdes, categoria F rents, categoria H pensions, categoria G capital gains) — only ask for categories the user indicates apply. Do not ask for NIF, IBAN, or full name; ask only for the numbers needed for the calculation.

3. **Compute the chain step by step, showing each stage:**
   a. Rendimento bruto (gross by category)
   b. Deduções específicas per category (categoria A: €4,462.15 flat, 2025; categoria B simplified regime: apply the coefficient — see Domain playbook)
   c. Rendimento líquido per category → sum → rendimento global líquido
   d. Rendimento coletável (after any losses to carry forward, if applicable)
   e. Quociente familiar (household divisor) applied
   f. Escalões + taxas (apply the 2025-income-year bracket table) → coleta bruta (before quociente reversal — remember to multiply back by the divisor)
   g. Deduções à coleta — health, education, habitação, PPR, general household expenses, per-category caps AND the income-bracket-dependent global cap (see Domain playbook) → coleta líquida
   h. Compare coleta líquida to total retenções na fonte + pagamentos por conta → apuramento: reembolso (refund) if retentions > coleta líquida, or valor a pagar if the reverse
   i. Note the ADICIONAL DE SOLIDARIEDADE (state if it applies — very high incomes only, >€80k coletável, currently outside normal-household scope but flag if inputs suggest it)
   j. **Independently recompute with the bundled estimator (asset step).** Run `python scripts/validate.py --selftest` first to confirm the estimator is trustworthy this session (it must exit 0, all golden cases PASS); then use `scripts/validate.py` as a second, mechanical pass over sub-steps a–i — the manual chain and the estimator's coleta líquida / apuramento should agree to the cent before you trust the number. Read `assets/constants.json`'s DOCUMENTED APPROXIMATIONS block so you know, and can state to the user, which effects (solidarity surtax, IRS Jovem progressividade, cat-B 15%-justified-expenses) the estimator deliberately omits and in which direction. See **The moat asset**.

4. **Run the IRS Jovem branch, if age-eligible (18–35 inclusive on 31 Dec of the tax year).** Determine which year of the 10-year schedule applies, compute the exempt slice, and show both scenarios (with/without IRS Jovem) side by side — see Domain playbook and Scenario comparison below. IRS Jovem is opt-in per declaration; a lower nominal tax isn't automatically better once deduções à coleta interactions and future-year eligibility are considered, so always show both numbers.

5. **Run the tributação conjunta vs separada comparison** if the household is married/civil union. The two regimes are computed by genuinely different mechanics, and the estimator (`scripts/validate.py`) now implements both correctly: **conjunta** pools both spouses into one rendimento coletável, divides by the quociente divisor 2, applies the brackets, then multiplies the coleta back by 2; **separada** assesses each spouse individually (own RC at divisor 1, own coleta, own deduções à coleta capped against their own global limit, own retenção) and the household figure is the **SUM** of the two individual liquidações — it does not pool income (pooling two earners as one over-taxes them under progressivity). Attribution defaults for separada: a case-level household deductions bundle is split 50/50 and a case-level retention is split pro-rata to gross, but per-taxpayer `deductions`/`retention` override those (see `constants.json` documented_approximations). Compute both ways and present the euro delta plainly — do not just assert which is better.

6. **Cross-check against the public calculators — this is the trust step, always do it, never skip:**
   - Point the user to https://mowei.pt/ferramentas/modelo3-irs to sanity-check the category-by-category breakdown
   - Point to https://mowei.pt/ferramentas/irs-acerto-reembolso to independently verify the refund/payment figure
   - If category A only: https://mowei.pt/ferramentas/salario-liquido to reconcile the withholding assumption
   - If category B: https://mowei.pt/ferramentas/recibos-verdes to reconcile the coefficient and IVA regime assumption
   - If IRS Jovem applies: https://mowei.pt/ferramentas/irs-jovem-deducoes to verify the exemption-year schedule
   - Direct the user to the official Portal das Finanças IRS simulator (via https://www.gov.pt/servicos/simular-e-entregar-a-declaracao-anual-do-irs — no login required for the standalone simulator/pre-filing estimate) as the authoritative cross-check, and to https://mowei.pt/ferramentas/calendario-fiscal/ for the exact current-year deadlines
   - Explain to the user exactly what to type into each tool and what field of the estimate that tool's output should match. If the skill's number and a public calculator disagree by more than a rounding difference, say so explicitly and walk through which input differs — do not silently pick one.

7. **Deliver the output** using the templates in Output format below.

**R. Retro pass (Execute variant over a past income year, 2022–2024).** When the user wants to check an *already-filed* past return for money left on the table, run Execute against that year instead of the current one: pass `"income_year": 2022|2023|2024` so the estimator loads that year's own bracket table, IAS, specific deduction, rent cap, global-cap endpoints, and the IRS-Jovem regime *as it stood that year* from `assets/constants-multiyear.json` (never the current year's numbers — the IRS Jovem schedule and the rent cap both changed every year). Compute the return **twice**: once as it was filed (`scenario_original`) and once with the missed item added (`scenario_corrected`); the recoverable amount is `coleta_liquida_original − coleta_liquida_corrected`. Then, and this is the load-bearing step, map the situation to the **correct correction instrument and its deadline** using the *Retro-audit and correction paths* decision table in the Domain playbook — a recomputation that finds €X is worthless if you point the user at a lapsed instrument. State three things every time: the recoverable euros, the instrument + where it is filed, and whether the deadline is still open as of today. If the arithmetic recovers money but the window has closed (or the only long-window instrument, revisão oficiosa, does not cover a pure voluntary omission), say it is **unrecoverable** and route to an OCC — do not imply a refund the taxpayer cannot actually claim. Below a stated materiality (~€25) flag the low value rather than push a filing. Confirm the estimator self-test passed (Validate hard gate) before quoting any recoverable figure.

**Failable check:** if the computed coleta líquida vs a public-calculator cross-check (step 6) disagrees by more than a rounding difference and the discrepancy hasn't been traced to a specific differing input, STOP — do not deliver a final REEMBOLSO/A PAGAR figure with an unexplained mismatch still open. **Retro variant:** never present a recoverable-refund figure without naming the correction instrument AND stating whether its deadline is open as of today; an unrecoverable (time-barred) recomputation is delivered as "€X arithmetic, but unrecoverable because [instrument] lapsed", never as a refund.

### Monitor

**Purpose:** the recurring, calendar-driven and rule-change watch duties that apply even when no active estimate is being built — this mode is what makes the skill useful outside the April–June filing window.

**Inputs:** the user's known filing profile (income year, categories, any pending decisions), today's date.

**Duties to watch for and proactively surface when relevant:**
- **Deadlines:** e-Fatura validation deadline (~2 March), filing window open/close (1 April–30 June for the standard campaign), any PPR year-end contribution deadline (31 December), IRS Jovem opt-in is per-declaration so re-check eligibility each filing year rather than assuming last year's answer carries forward.
- **Pending invoices:** if the user mentions category B activity, remind them e-Fatura validation is what feeds the automatic specific-deduction justification (the 15%-of-gross rule) — unvalidated invoices before the March deadline can shrink the deduction they expected.
- **Rule changes:** bracket ceilings, deduction caps, the IAS (which drives the IRS Jovem ceiling), and PPR limits are set annually by the Orçamento do Estado and can change mid-cycle. Flag explicitly whenever a new OE is enacted or when the user's question spans a year boundary.
- **Withholding-table changes:** Finanças periodically adjusts monthly retenção na fonte tables to track the final tax more closely — a smaller refund than a prior year is often the withholding table doing its job correctly, not an error (see field lesson below); check the current year's table before assuming something's wrong.

**Failable check:** if the user is asking a what-if question that touches a date after the next known rule-change point (a new OE, a new IAS publication, a bracket update) and the estimate hasn't been labeled with which year's rules were used, STOP and add the year label before answering.

### Validate

**Purpose:** the pre-delivery gate — nothing goes to the user as a final answer without passing this.

**Inputs:** the completed computation chain, cross-check results, and any scenario comparisons from Execute mode.

**Outputs:** a pass/fail against the Reproducibility & QA rubric below, plus the final disclaimer-bearing output.

**Failable check:** apply the hard gate in the Reproducibility & QA rubric section verbatim — if any condition there fails, do NOT deliver the estimate as final; state what's missing and continue gathering instead. **Estimator hard gate:** additionally confirm `python scripts/validate.py --selftest` exits 0 with **every** case reporting PASS — all 14 current-year (2025) golden cases, all 9 retro-audit cases (2022–2024), and the UNKNOWN-refusal guard. A failing or un-run selftest means the estimator asset is not trustworthy this session, so do not deliver a final REEMBOLSO/A PAGAR figure **or a recoverable-refund figure** (see The moat asset). For any **Retro** delivery, additionally confirm the recoverable figure is accompanied by the correct correction instrument and a today-relative deadline check (Execute step R / the Retro-audit decision table) — an unrecoverable time-barred recomputation is never delivered as a refund.

## Domain playbook

### 2025 income year (Lei n.º 55-A/2025, de 22 de julho) — filed 2026, current live campaign

- 9 escalões (brackets), each with a taxa normal (marginal) and taxa média (average, applied to the first tranche). 2025 bracket limits were updated ~4.6% for inflation versus 2024 (1st bracket ceiling rose from €7,703 to €8,059); marginal rates were unchanged from 2024 for the 2025 income year. **This skill does not hard-code the exact 9 bracket boundary euro amounts and rates** — verify the current authoritative table at Portal das Finanças (Artigo 68.º CIRS) or the mowei.pt calculators before quoting a specific coleta figure to the user; bracket tables shift every Orçamento do Estado and must never be memorized into skill logic without a same-session check.
- Formula: coleta = (rendimento coletável ÷ N) × taxa normal do escalão − parcela a abater do escalão, then × N (where N = quociente familiar divisor). Equivalently: split rendimento coletável/N into the "taxa média" tranche (the full lower-bracket ceiling taxed at that bracket's average rate) plus the excess taxed at the next bracket's taxa normal.
- Dedução específica categoria A (2025): flat €4,462.15 per taxpayer with category A income (equal to 8.54× IAS, subject to the annual update — verify current year).
- Deduções à coleta (2025 income year, as researched 2026-07-10 — verify before quoting to a user near the filing deadline, as OE amendments can shift these):
  - Despesas gerais familiares: 35% up to €250/sujeito passivo (45% up to €335 for monoparental households)
  - Despesas de saúde: 15% up to €1,000
  - Despesas de educação: 30% up to €800 per household (cap rises to €1,100 where the excess over €800 is displaced-student rent — dependent ≤25, >50 km from home, rents counted up to €400/yr; separate rule: +10 p.p. majoração with a €1,000 global limit for interior/regiões autónomas education)
  - Habitação (rendas): 15% of rent paid, up to €700 (2025 declaration), scaled down for rendimento coletável between €8,059–€30,000, capped lower above €30,000
  - PPR: 20% of the annual contribution, capped by age — €400 max (needs €2,000 saved) under 35; €350 max (needs €1,750) 35–50; €300 max (needs €1,500) over 50, up to age 70
  - **Global cap on combined deduções à coleta** scales with rendimento coletável — no cap below €8,059 coletável, then a declining cap (€2,500 falling to €1,000) through €83,696, and a flat €1,000 above €83,696 (income year 2025). Always recompute this cap for the household's actual coletável rather than assuming the deductions are additive without limit.
  - **[field lesson]** Even accounting for all the caps above, users are routinely surprised when a large retenção-na-fonte figure produces a modest refund (e.g. €2,300 withheld all year, only €600 refunded) — the gap is not an error, it's the difference between "tax withheld" and "tax owed," and Finanças' periodically-updated withholding tables are specifically designed to shrink that gap year over year (source: Contas Poupança, PodTEXT "Tenho uma retenção na fonte de 2300€ mas só recebo 600€ de reembolso no IRS. Porquê?", contaspoupanca.pt). Always show the retenções-vs-coleta-líquida delta explicitly (Output format step h) rather than just the final refund number, so this isn't a surprise at delivery time.
  - **[field lesson]** A shrinking refund versus the prior year is frequently just the withholding table catching up to the real tax owed, not a rule change or a mistake — Contas Poupança's 2025 piece "Contribuintes surpreendidos com simulação do IRS, mas descida do reembolso era expectável" documents exactly this pattern going into the 2026 campaign (source: contaspoupanca.pt, 2025-03-31); Doutor Finanças' "Reembolso de IRS pode ser menor em 2026. Saiba porquê" covers the same mechanism (source: doutorfinancas.pt). When a user reports "my refund is smaller than last year," check the withholding-table story before assuming a deduction was missed.
  - **[field lesson]** Different simulators (Portal das Finanças, third-party tools, even the same portal's own automatic-vs-manual paths) can disagree on the refund figure by a nontrivial margin, and users post confused about which one is "right" — two live examples on Fórum de Finanças Pessoais by Doutor Finanças: "Duvidas, Valor reembolso diferente da simulação" and "Valor de reembolso muito superior a outros simuladores" (source: forumfinancas.pt, topic IDs 15551 and 13184). This is exactly why step 6 (cross-check) requires tracing any disagreement to a specific differing input rather than silently picking a number — see Execute mode's failable check.

### 2026 income year (declared 2027) — differs, flag explicitly, do not silently reuse 2025 numbers

- Orçamento do Estado 2026 updates bracket ceilings by 3.51% (inflation adjustment) and cuts marginal rates on escalões 2–5 by 0.3 percentage points versus 2025.
- IRS Jovem income ceiling for 2026 is 55× the 2026 IAS (IAS 2026 = €537.13) = €29,542.15/year — this is a 2026-specific figure; recompute if the IAS changes.
- When a user asks "what will I owe next year" or is planning a PPR/timing decision that spans the year boundary, compute BOTH years' tables and label each result with its income year unambiguously — never present a 2026-income-year number without the label, and never silently substitute 2025 assumptions into a 2026 question.

### IRS Jovem (research current-law version, 2025 reform onward)

- Age window: 18–35 inclusive, tested on 31 December of the tax year. Turning 36 mid-year forfeits eligibility for that year.
- No longer requires any academic qualification (the secondary-education completion requirement was removed starting the 2025 reform) — do not apply an education-level filter.
- Applies to both categoria A (salário) and categoria B (recibos verdes) income.
- 10-year progressive exemption schedule from first qualifying year of activity: Year 1 = 100% exempt, Years 2–4 = 75%, Years 5–7 = 50%, Years 8–10 = 25%. The exemption applies to the qualifying income up to the annual ceiling; income above the ceiling and any non-qualifying income is taxed normally.
- Annual ceiling: 55× IAS. Confirm the year's IAS value before computing — this is an annually-indexed figure, do not hard-code a euro amount across income years without checking.
- IRS Jovem is a per-declaration election. If a user skipped it in an earlier year of eligibility, the remaining years of the 10-year schedule and their percentages are what's left — do not assume they can restart at Year 1.
- Starting 2026, taxpayers covered by IRS Jovem can choose between IRS Automático or the traditional manual Modelo 3 — note this as a filing-mechanics choice distinct from the opt-in-to-the-exemption decision itself.
- Edge case to catalog: a user with IRS Jovem eligibility who is also filing jointly with a non-eligible spouse — the exemption applies only to the eligible spouse's qualifying income, not to the joint coletável as a whole. Compute per-taxpayer before combining.
- Edge case: a user who changed jobs or had a gap year in professional activity — the 10-year clock runs from first year of activity, not from current-employer tenure; a gap year does not reset it, but confirm the user's own start-of-activity registration date (início de atividade) with Finanças rather than assuming.
- **[field lesson]** Users starting professional activity mid-year genuinely don't know how "Year 1" of the 10-year schedule is bounded — a Fórum de Finanças Pessoais by Doutor Finanças thread asks exactly this: someone starting work in September 2025 wants to know if Year 1 runs September–December 2025 (a partial calendar year) or September 2025–August 2026 (source: forumfinancas.pt, "IRS jovem" topic 23582). Always state explicitly to the user which interpretation applies (the exemption year tracks the income/tax year, i.e. the partial-calendar-year reading, not a rolling 12-month window from the start date) rather than assuming the user already knows this.

### Recibos verdes / categoria B simplified regime

- Coeficiente 0.75 for services listed in the Artigo 151.º CIRS table (most professional/consulting services) — only 75% of gross is taxable before further deductions.
- Coeficiente 0.35 for other services not on the 151.º list.
- Coeficiente 0.15 for certain hospitality/local-lodging income; other coefficients exist for specific activities (e.g. 0.10 for sales of goods) — ask the user which activity code applies rather than assuming 0.75 by default.
- From 2023 onward, deduction under the simplified regime additionally requires justifying expenses (invoices with the user's NIF, e-Fatura-registered) equal to at least 15% of gross annual income for coefficients 0.75/0.35, or the taxpayer's specific deduction is capped to the actual justified amount if lower — flag this as a common surprise (users assume the 25%/65% "automatic" reduction is unconditional; it is not, post-2023).
- **[field lesson]** The 15%-of-gross justified-expenses requirement only bites above a specific income threshold, not for every category-B filer: the automatic flat specific deduction of €4,587.09 already equals 15% of €29,748, so anyone invoicing below roughly €29,748/year with coefficient 0.75/0.35 income needs zero justifying invoices — this threshold detail is easy to miss and worth stating explicitly to lower-earning freelancers who assume they need to hunt for receipts (source: reporting synthesized from Portal das Finanças regime-simplificado guidance and cross-referenced practitioner explainers surfaced during this wave's research, e.g. simuladorneto.pt "Despesas Dedutíveis Recibos Verdes 2026"). Confirm the current year's exact threshold (it moves with the flat deduction, which is IAS-indexed) before quoting it.
- Regime simplificado ceiling: category B income up to €200,000/year; above that, organized accounting (contabilidade organizada) is mandatory — out of scope for this skill, route to an OCC.
- First-year-of-activity exemption on the first €X of the deduction (isenção parcial) applies in the initial year and second year of activity at reduced levels — flag this as an edge case to verify per the user's actual início-de-atividade date rather than assume.

### Quociente familiar / conjugal (household divisor)

- Married/civil-union joint filing: divide combined rendimento coletável by 2 before applying brackets, then multiply the resulting coleta by 2 (this is why the "taxa média" step matters — it's not just "half the income at half the tax").
- Each dependent adds €600 as a deduction à coleta (post-2015 model; the divisor no longer directly includes dependents, unlike the pre-2015 quociente familiar which added 0.3 per dependent to the divisor — do not use the old +0.3-per-dependent divisor model, it was replaced).
- Monoparental households get an enhanced deduction and higher despesas-gerais-familiares percentage (45%/€335 vs 35%/€250) — always ask household structure, not just "married y/n".

### Tributação conjunta vs separada — decision framework

- Compute both: (a) joint, using the divide-by-2/multiply-by-2 mechanism above, pooling both spouses' income and deductions into ONE rendimento coletável; (b) separate, each spouse assessed individually at divisor 1 (own RC, own coleta, own deduções à coleta capped against their own global limit, own retenção) with the household figure being the SUM of the two individual liquidações — shared deductions are allocated per spouse (household expenses/dependents split 50/50 by default, or assigned to one spouse). The estimator implements both mechanics; do not pool the two spouses' income for the separada branch.
- Joint filing tends to help more when incomes are asymmetric (one high earner, one low/zero earner) because it smooths both partners toward the household's blended marginal bracket.
- Separate filing can help when both partners have similar high incomes and each would otherwise push the other into a higher bracket via the joint sum — but PT's divide-by-2 mechanism already neutralizes much of this; the separate-filing win is more often about deduction allocation flexibility (assigning categoria B expenses, health deductions, or IRS Jovem eligibility to the one spouse who benefits most) than about bracket arithmetic. Always compute both — assumptions about which "usually wins" fail household-specific edge cases (e.g., one spouse IRS Jovem eligible, one not).
- **[field lesson]** If neither spouse actively elects an option by 30 June, Finanças defaults to separate filing automatically — a couple who intended joint filing and did nothing can be defaulted into the wrong outcome. If this happens, a corrected joint declaration filed manually before the deadline replaces the automatic one and Finanças re-runs the acerto de contas (including reversing any refund already issued under the automatic/separate path) (source: DECO PROteste, "IRS em conjunto ou em separado em 2026," deco.proteste.pt). Always tell married/civil-union users this default explicitly — don't assume they know inaction defaults to separate.
- Always show the euro delta, not just a recommendation — the user makes the final election in the Modelo 3, not this skill.

### PPR contribution before year-end — decision framework

- A PPR contribution made by 31 December of the tax year is deductible at 20%, capped by age (see caps above). Compute the marginal benefit: min(20% × contribution, age cap) against the coleta líquida, and check whether the household is already at or near the global deduções-à-coleta cap for their bracket (a PPR deduction is worthless past the cap).
- Flag the early-withdrawal penalty tradeoff: PPR funds withdrawn before the minimum holding period (or outside qualifying reasons) trigger a clawback of the tax benefit plus a penalty — this is a liquidity decision, not just a tax one. Point to https://mowei.pt/ferramentas/ppr-beneficio-fiscal and https://mowei.pt/ferramentas/ppr-comparador for the numeric comparison, but always state the liquidity tradeoff in words, not just the euro benefit.

### Retro-audit and correction paths

The retro engine (Execute step R, income years 2022–2024) recomputes a filed return and finds recoverable euros; this subsection is the legal spine that turns that number into money the taxpayer can actually claim. **A recovery figure without the right instrument and a live deadline is worthless** — always deliver the euros, the instrument, and the "is the window open today?" answer together. All instruments and deadlines below were confirmed against CPPT / LGT / CIRS and OCC/practitioner guidance during the 2026-07-10 research run (full citations also in `constants-multiyear.json` `_meta.correction_paths`).

| Situation | Instrument | Deadline (outer bound) | Where filed | Citation |
|---|---|---|---|---|
| Missed deduction (PPR / rent / health / education) discovered within the reclamação window | **Declaração de substituição a favor** / **reclamação graciosa** | **120 dias** do termo do prazo de pagamento (IRS special: 2 anos, CIRS art. 140) | e-Balcão / Direção de Finanças competente | CPPT art. 59, 70, 102; CIRS art. 140 |
| Missed deduction, 120-day window lapsed but within 4 years, *and* the error is imputable to the services | **Revisão oficiosa** | **4 anos** da liquidação (LGT art. 78 n.º 1) | Direção de Finanças / e-Balcão | LGT art. 78 |
| IRS Jovem eligible but not opted into on the filed return | **Declaração de substituição a favor** (benefit *option*) | Tied to the reclamação window (120 dias); option-timing is **contested by AT** — OCC-gated | e-Balcão | CPPT art. 59; AT practice on benefit options |
| Voluntary correction that **raises** tax (regularizing an under-declaration) | **Declaração de substituição** | 30 dias após o prazo penalty-free, else within reclamação (120 d) / impugnação (90 d) | e-Balcão | CPPT art. 59; CPPT art. 102 |
| Discovery beyond 4 years from the facto tributário (or a pure voluntary omission with no live instrument) | **None — time-barred** | Caducidade **4 anos** do facto tributário | N/A (route to OCC only to confirm no exceptional ground) | LGT art. 45 |

**Key honesty rule baked into the table:** revisão oficiosa's 4-year window requires *erro imputável aos serviços*. A taxpayer's own forgotten deduction is generally **not** that, so a simple "I forgot my PPR three years ago" is often **not** rescued by the 4-year route once the 120-day reclamação window has closed — the `unrecoverable_time_barred` retro case exists precisely to model this. Never promise the 4-year window for a pure omission without OCC confirmation.

### Strategic canon

Adjacent operator wisdom this skill's design leans on — not tax law, but the decision discipline around it.

- **Thinking, Fast and Slow (Daniel Kahneman).** The mind runs two systems: System 1 (fast, intuitive, pattern-matching) and System 2 (slow, deliberate) — most predictable errors come from System 1 shortcuts System 2 lazily rubber-stamps. Anchoring drags an estimate toward whatever number arrived first; the planning fallacy makes people trust an inside-view story over the outside view (base rates from comparable cases); WYSIATI — "what you see is all there is" — builds a confident story from only the evidence in front of you. Applied here: a user anchors hard on last year's refund figure and reads this year's different number as wrong rather than as a different year's rules; the "expected refund" framing invites planning-fallacy optimism the skill counters by always cross-checking against multiple public calculators (the outside view, Execute mode step 6); and WYSIATI is exactly what happens when a user omits an income category they forgot they had — the estimate looks complete because nothing visibly contradicts it.
- **Thinking in Bets (Annie Duke).** Every decision is a bet on an uncertain future, and the core trap is "resulting" — judging a decision's quality by how it turned out rather than by the quality of the reasoning given what was knowable at the time. Good process can still produce a disappointing outcome. Applied here: joint-vs-separate, IRS Jovem opt-in, and PPR timing are all bets made under incomplete information (next year's bracket table isn't known yet, income can shift) — the skill's job is to show the euro delta and the reasoning behind each scenario, not to imply the option with the bigger number was self-evidently "right." A user whose IRS Jovem opt-in produced a smaller refund than the alternative didn't necessarily choose badly — resulting is the trap the scenario-comparison table exists to prevent.
- **Financial Intelligence (Berman & Knight).** Non-finance readers can and should read financials, because finance is more art — assumptions, estimates, judgment calls — than it looks from outside; the numbers are a model of reality, not reality itself. Applied here: every REEMBOLSO/A PAGAR figure this skill produces is a model built on stated assumptions — which income year's rules, which activity coefficient, whether e-Fatura invoices are validated, whether a cap was hit — and those assumptions deserve the same explicit naming that Financial Intelligence gives to accruals and revenue-recognition timing in a P&L. The computation-chain output format's itemized, capped deduction list is this skill's version of "read the notes before you believe the headline number."

## Adjacent disciplines (vertical & horizontal)

### Upstream (where the inputs come from)

- **SAF-T (PT)** — the OECD-designed Standard Audit File for Tax that Portugal's Autoridade Tributária mandates (legal basis in the VAT code, technical format fixed by Portaria n.º 321-A/2007); it's the standardized XML export that invoicing/accounting software produces and that ultimately feeds e-Fatura and AT audit access. Matters here because it's the invisible backbone behind every e-Fatura total a user pastes into this skill — the number didn't appear by magic, it was extracted from a SAF-T-compliant system.
- **ATCUD + QR code invoice requirements (Portaria n.º 195/2020, implementing DL n.º 28/2019)** — the unique document code and mandatory two-dimensional QR code that must appear on every fiscally relevant Portuguese invoice, built from an AT-assigned series validation code. Matters here because it's what makes a recibo verde or a category-B invoice traceable and matchable to the e-Fatura record a user reports — a document without a valid ATCUD is a red flag for the "is this invoice actually validated" question the skill asks in Execute mode.
- **The e-Fatura communication pipeline (DL n.º 198/2012, de 24 de agosto)** — the law requiring VAT-relevant economic agents to transmit invoice elements to the AT (in real time, via SAF-T(PT) file by the 5th of the following month, or other approved electronic means), created specifically to fight informality and reward consumers who demand invoices. Matters here because it's the legal mechanism that makes the e-Fatura year-end category summary (saúde, educação, habitação, despesas gerais) a usable input in the first place.
- **Bank statement export practices** — CSV/PDF exports a user downloads directly from their own bank, used to cross-check recibos verdes totals and PPR contribution amounts. No formal Portuguese standard governs the export format itself; it stays user-initiated and file-level by this skill's own design (see Integrations), never an API pull.

### Downstream (who consumes the outputs)

- **Contabilistas certificados (OCC professional standards)** — the Ordem dos Contabilistas Certificados, a public professional body (DL n.º 452/99, restructured by DL n.º 139/2015) with mandatory membership for anyone signing off on organized accounting or complex tax filings. Matters here because it's exactly who this skill routes a user to whenever a case exceeds its scope (mais-valias, RNH/IFICI, organized accounting) — the OCC is the professional backstop this skill is explicitly not trying to replace.
- **The Modelo 3 filing process and AT validation/divergências workflow** — the actual annual declaration and the AT's automated cross-check against e-Fatura and employer-reported data, which can flag divergências the taxpayer must resolve before the declaration is accepted. Matters here because this skill's estimate is a rehearsal for that process, not a substitute for it — a discrepancy this skill can't explain is exactly the kind of thing the AT's own divergências check would also catch.
- **Records-retention duties** — Portuguese tax law (Artigo 123.º CIRC — livros e registos — plus Artigo 130.º CIRC — dossier fiscal — and Artigo 52.º CIVA) requires books, accounting records, and supporting documents to be archived for 10 civil years from the end of the year the taxable event occurred; ISO 15489 is the international records-management standard behind the discipline of organizing that archive so it's actually retrievable when needed. Matters here because it's the horizon a user should keep e-Fatura exports and payslips for, well beyond the current filing campaign this skill helps with.

### Horizontal (sibling crafts)

- **Financial-literacy infrastructure — Todos Contam / Plano Nacional de Formação Financeira (jointly run by Banco de Portugal, CMVM, and ASF since 2011)** — Portugal's official financial-education portal and its supervising initiative. Matters here because it's the government-endorsed adjacent resource for the general household-finance literacy (budgeting, savings, credit) that sits just outside this skill's tax-specific scope.
- **GDPR data-minimization** — the privacy craft this skill actively practices: process figures locally within the conversation, never persist names/NIFs/IBANs, retain only non-identifying category labels if any summary is needed (see Disclaimer's PII handling rule). Matters here because a tax-estimation tool is a natural magnet for exactly the identifiers GDPR treats as high-sensitivity, and minimization is the discipline that keeps this skill from becoming a liability.
- **Open Banking / PSD2** — named explicitly as the deliberately-rejected adjacent capability. PSD2-based account aggregation could auto-pull salary and transaction data instead of asking the user to paste figures, the way FIZ pulls data via AT credentials — but this skill is file-level by design (see Integrations and the Competitive wedge in RESEARCH.md): no OAuth, no bank connections, no standing account access, ever. The convenience Open Banking would buy is traded away on purpose for zero standing credential exposure.

## Value-chain positioning: top-down & bottom-up

### Top-down

The household KPIs this skill moves:
- **Estimate-vs-official-simulator delta (%)** — escalate to "trace the input, don't just report the gap" if the delta exceeds roughly 5–10% (Execute mode step 6's failable check already gates delivery on this).
- **Scenario deltas in euros** — conjunta vs separada, IRS Jovem on vs off — the number a household actually decides on, not a single point estimate.
- **Assumptions count declared per estimate** — how many stated assumptions (income year, coefficient, cap proximity) sit behind the headline REEMBOLSO/A PAGAR figure; fewer, more precisely sourced assumptions means a firmer number.

Sponsor questions a partner/household-CFO would ask, mapped to the mode that answers them:
1. "Is this the right year's rules?" → **Research** mode.
2. "Which decisions are actually live for us this year?" → **Plan** mode.
3. "What's the number, and why?" → **Execute** mode.
4. "What should we watch for between now and the filing deadline?" → **Monitor** mode.

Plan mode is the entry point from the top — it's where the household's actual decision surface (which categories, which live choices) gets scoped before any number is computed, the same way a CFO scopes what actually needs modeling before the analyst builds the spreadsheet.

### Bottom-up

Pattern-to-signal escalation rules, with real thresholds:
- If an income category recurs unmapped across **2+ conversations** in the same filing year (e.g. category G capital gains keeps coming up but the skill keeps flagging it out of scope) → escalate to routing the household to an OCC rather than re-flagging it each time.
- If the estimate-vs-public-simulator drift recurs across **2+ estimate runs** with the same unexplained direction and magnitude → escalate to suspecting a wrong input assumption (activity coefficient, withholding table year) rather than a rounding artifact, and re-verify that assumption against Portal das Finanças before the next run.
- If category-B pending/unvalidated e-Fatura invoices pile up across **multiple months** approaching the ~2 March validation deadline → escalate the reminder from Monitor mode's routine deadline note to an explicit warning that the 15%-justified-expenses threshold (for gross income above ~€29,748/year) may not be met.

Monitor and Validate modes are the sensors that feed these signals — Monitor watches the calendar and rule-change surface continuously, Validate is the pre-delivery gate that catches an unresolved discrepancy before it reaches the household as a final number.

**Chain:** household member → this skill → mowei.pt calculators and the official Portal das Finanças simulator → OCC/AT (for filing, complex cases, and final validation).

## Integrations

**File-level only.** No OAuth, no APIs requiring credentials, no daemons, no background sync. The user exports, downloads, or screenshots files themselves and pastes/uploads them into the conversation; this skill never initiates a connection to any external account.

| Tool / Source | Free or Paid | Format consumed | Format produced |
|---|---|---|---|
| e-Fatura portal (manual export) | Free | Screenshot, PDF export, or pasted year-end category totals | — (input only) |
| Portal das Finanças (viewed in browser by the user) | Free | User-transcribed figures from the pre-filled declaration / IRS simulator screen — never a login or session token | — (input only) |
| Bank statements (recibos verdes income, PPR contributions) | Free (user's own bank) | CSV or PDF export the user downloads themselves | — (input only) |
| mowei.pt ferramentas (modelo3-irs, irs-acerto-reembolso, salario-liquido, recibos-verdes, irs-jovem-deducoes, calendario-fiscal, ppr-beneficio-fiscal, ppr-comparador) | Free, no login | Manual entry by the user (this skill tells them what to type) | Web page output the user reads and compares against this skill's numbers |
| Portal das Finanças official IRS simulator (gov.pt entry point) | Free, no login for standalone simulation | Manual entry by the user | Web page output for authoritative cross-check |
| This skill's own output | — | — | Plain-text computation chain, scenario comparison table, cross-check checklist, next-step list (Markdown/plain text the user can paste into a spreadsheet or note) |

## Reproducibility & QA rubric

**Named intermediate artifacts** (so two runs on the same inputs are comparable):
1. `fiscal-profile` — the gathered inputs (income year, categories, household structure, ages, PPR activity), non-PII, session-scoped only.
2. `computation-chain` — the step-by-step Output format §1 result.
3. `scenario-comparison` — Output format §2, when joint/separate, IRS Jovem, or PPR branches are run.
4. `cross-check-checklist` — Output format §3, naming which public tool verifies which line.
5. `next-step-list` — Output format §4.

**0–2 scoring rubric per dimension** (2 = fully met, 1 = partially met, 0 = not met — self-score before delivery):
- **Completeness:** all income categories the user mentioned are reflected in the computation-chain artifact; all live decisions (IRS Jovem, joint/separate, PPR) the user raised have a scenario-comparison row.
- **Correctness-of-year-labeling:** every euro figure in every artifact carries an explicit income-year label (2025 or 2026); no figure appears unlabeled or with an ambiguous year.
- **PII hygiene:** no name, NIF, IBAN, address, or specific euro amount tied to an identifiable person appears in any artifact intended to persist beyond the conversation (per the Disclaimer's PII handling rule).
- **Actionability:** every deduction row in the computation-chain artifact states whether its supporting document (invoice, e-Fatura validation, PPR statement) is present or missing, so the user knows what's estimate-only versus confirmed.

**Hard gate — do NOT deliver a final estimate unless:**
- Every euro figure carries an income-year label.
- No PII appears in any artifact meant to persist (memory file, session summary) beyond the live conversation.
- Every deduction row cites document-present/missing status.
- Any discrepancy versus a public-calculator cross-check (Execute mode step 6) has been traced to a specific differing input, or explicitly flagged as unresolved with a recommendation to verify at Portal das Finanças.
- The Validate mode's failable check (above) has been run and passed.

**As-of assumptions:** this skill's Domain playbook figures are dated 2026-07-10 against the 2025 income year (rendimentos 2025, declared 2026) unless the conversation explicitly establishes the 2026 income year (declared 2027). **Verify before relying:** bracket boundaries, deduction caps, the IAS, and PPR limits are set annually by the Orçamento do Estado and can change mid-cycle by separate law — re-check the current authoritative figures at Portal das Finanças or the mowei.pt calculators before quoting any number to a user filing more than a few months after this file's date above.

## Output format

**1. Computation chain summary (always produced):**
```
Rendimento bruto (by category): ...
− Deduções específicas: ...
= Rendimento líquido: ...
[quociente familiar applied: ÷N → ...]
Escalão aplicável: [Nº], taxa normal X%, taxa média Y%
Coleta bruta: ...
− Deduções à coleta (itemized, capped): ...
= Coleta líquida: ...
− Retenções na fonte + pagamentos por conta: ...
= REEMBOLSO ESTIMADO / A PAGAR ESTIMADO: €___
Income year: 2025 (declared 2026) | Estimate confidence: [rough / firm pending e-Fatura validation]
```

**2. Scenario comparison table** (when relevant — joint/separate, IRS Jovem on/off, PPR before/after):
| Scenario | Coleta líquida | Reembolso/Pagar | Delta vs baseline |

**3. Cross-check checklist** — the specific mowei.pt tool(s) and Portal das Finanças simulator to run, what to enter, and what output should match which line of the chain above.

**4. Next-step list** — anything the user should confirm directly with Finanças or an OCC (início de atividade date, IRS Jovem year count, ambiguous activity coefficient, anything near a cap).

Every output ends with the Disclaimer below.

## Handoff dossier contribution

When a handoff dossier folder exists (created by the flagship organizer's
`scripts/dossier.py`, default `handoff-dossier-<income-year>/` next to the household's
documents) — or the user asks for one — this skill writes its contribution there as part
of Execute: **08-estimates.md** (the full computation chain, scenario deltas in euros,
the assumptions list, and the cross-check result vs the official simulator) and appends
to **06-outliers-questions-suggestions.md** (estimate-vs-simulator drift beyond ~5%,
scenario recommendations phrased as suggestions for review). Validate confirms the files
were written and stub-free before the run is logged. The dossier holds the household's
real figures by design — the no-PII rule governs MEMORY.md, not this deliverable.

### Recommendation format (mandatory for every recommendation delivered)

Every recommendation the assistant delivers — an allocation move, a PPR top-up, a filing
choice, a correction filing — is presented in this fixed template, never free prose:

- **Recommendation:** one sentence, action-first.
- **Assumptions:** the facts it depends on (income year, regime, household composition).
- **Evidence:** the source — a document in the dossier (file + row), an asset row
  (matrix/doutrina/constants id), or a computed golden-path result.
- **Euro impact:** computed by shipped code (state which script), or UNKNOWN — never a
  model-estimated number.
- **Risks / what could make this wrong:** at least one named risk.
- **Deadline:** the operative date and its legal basis, or "none".
- **Missing documents:** what would firm this up, or "none".
- **Professional review:** REQUIRED / recommended / not needed — with the reason.

## Persistent memory & run log

This skill maintains a per-user memory file at `MEMORY.md` in its own folder.

- **Session start:** read `MEMORY.md` first. Entries under Preferences override the
  skill's defaults (e.g. preferred output language, household filing preference,
  category conventions).
- **After every run:** append one Run-log row — date, mode, scope expressed as counts
  (e.g. "3 members, 14 documents", never names or amounts), outcome, and any deviation
  from the expected workflow.
- **User corrections:** when the user corrects a default or states a standing
  preference, upsert it under Preferences and confirm in one line what was recorded.
- **Hard no-PII rule:** memory stores patterns and counts only — structural
  anonymization always ("a two-earner household with one displaced student", never a
  name, NIF, address, or identifiable amount). Document payloads never enter memory.
- **20-row cap:** when the Run log exceeds 20 rows, roll the oldest rows' durable
  insights up into Lessons and delete the rows.
- **Validate-gate wiring:** a run is NOT complete until its memory entry is written —
  this is part of the Validate mode's hard gate.

## Offline operation (no-internet contract)

This skill is fully operable with zero network access — an explicit design contract:

- The estimate is computed entirely by the bundled stdlib engine against bundled, cited,
  income-year-labeled constants (2022-2025). No step of the computation ever needs a
  network.
- **The cross-check step ("the trust step") applies only when online.** Offline, the
  independent checks are: the engine's own golden corpus (selftest), the sweep's
  cross-skill agreement checks, and the law snapshot in `assets/law/`. Record
  "cross-check vs official simulator deferred: offline" in the dossier's
  09-validation-record — visible, never silent — and cross-check on the next online
  session before filing.
- The sweep's staleness age-gates are the offline substitute for "is this still current":
  past ~14 months the engine's constants hard-fail rather than compute on superseded law.

## Supported-feature matrix (what this skill will and will not do)

| Status | Scope |
|---|---|
| **SUPPORTED** | Categoria A; Categoria B simplified regime (0.75 services coefficient); single / joint / separate filing (separate = two individual assessments, summed); IRS Jovem (all regime versions 2022-2025); PPR scenarios; deducoes a coleta with per-category and global caps; retro passes over 2022-2024 with correction-instrument routing |
| **PARTIAL** (documented approximations, each with direction of error) | Solidarity surtax not modeled; IRS Jovem exemption-with-progression not modeled; Categoria B 15% justified-expenses rule not modeled; rent-cap taper not modeled; withholding tables not simulated |
| **UNSUPPORTED → STOP + route to OCC** | Categoria G capital-gains computation; Anexo J treaty math; englobamento elections on capital income; organized accounting; any income year outside 2022-2025 (the engine refuses rather than extrapolates) |

The engine hard-refuses out-of-scope inputs (UNKNOWN-guard) — it never extrapolates a
missing year or an unmodeled regime.

## Host-model qualification & weak-model operating contract

This skill may be run by strong hosted models or small local models (privacy-first
deployments). Correctness is therefore located in the artifacts, not the model. Two
mechanisms enforce this:

### Qualification exam (first run, and after any model change)

1. Sample 3 cases from the bundled golden corpus (inputs only — do not read expected
   outputs) and have the assistant solve them blind.
2. Write its answers as a candidate file and score them with the bundled harness:
   `python scripts/validate.py <candidate.json>` (measurement mode).
3. **Gate:** all 3 cases substantially correct -> the model is qualified for full Execute
   mode. Any material miss -> run in **downgraded mode**: document organization,
   checklists, deadline tracking, and walkthroughs of the external calculators only — the
   assistant must not present self-computed figures. Re-qualify after a model upgrade.
4. Record the exam result (date, model name, score) in MEMORY.md's Run log.

### Weak-model operating contract (always in force; strict-mode for unqualified models)

- **No mental arithmetic.** Every computed figure comes from the bundled stdlib scripts or
  an external calculator the user operates — never from the model's own arithmetic.
- **Echo-before-use (read-back verification).** After ingesting any file, the assistant
  states what it read (row/document counts, column names, 2-3 sampled rows, totals). A
  number that was not echoed from a source or produced by shipped code may not appear in
  any output.
- **One mode at a time.** Announce the active mode; complete its failable check before
  moving on; never combine modes in one pass.
- **Copy, do not paraphrase, legal text.** When citing a rule, quote the snapshot in
  `assets/law/` or the cited source verbatim — no from-memory restatements of statutes.
- **Uncertainty is a STOP, not a guess.** Anything unmapped, ambiguous, or outside the
  playbook is flagged and routed (OCC / official simulator), exactly as the mode gates
  require.

## Security & permissions (marketplace disclosure)

- **Network:** no required network access — the skill runs fully offline from user-supplied
  files. When the user asks for a live cross-check, the assistant may READ public,
  unauthenticated web pages only: `mowei.pt` (free calculators) and
  `info.portaldasfinancas.gov.pt` / `portaldasfinancas.gov.pt` (official public reference
  pages). It never accesses authenticated surfaces, never logs in, and never transmits user
  data anywhere.
- **Environment variables:** none. No API keys, no tokens, nothing read from the environment.
- **File access:** reads only files the user explicitly supplies (bank/e-Fatura/payslip
  exports, receipts) plus this skill's own folder (MEMORY.md, the shared household
  fiscal-profile file, assets/, scripts/). Never system paths, SSH keys, or the home
  directory at large.
- **Commands & code:** the only executables shipped are `scripts/validate.py` and `scripts/sweep.py` (the automatic correctness sweep) — both plain Python
  3.10+ standard library, no eval/exec/subprocess, no network, no environment access, no
  writes outside the skill folder. The only instructed commands are
  `python scripts/validate.py --selftest` (and candidate scoring via the same script) and
  `python scripts/sweep.py`.
- **Irreversible actions:** none. The skill produces local draft files and analysis only —
  it never files, submits, e-signs, pays, or logs in on the user's behalf.
- **Secrets:** none present. All bundled test personas, merchants, and figures are fictional.

## Limitations & maintenance

- **Fiscal rules change annually.** Bracket boundaries, rates, deduction caps, PPR limits, and the IAS (which drives the IRS Jovem ceiling) are set by each Orçamento do Estado and can also change mid-cycle by separate law. This skill's Domain playbook is dated 2026-07-10 against the 2025-income-year rules; re-verify every figure before relying on it for a filing more than a few months old.
- **Does not compute:** organized-accounting (contabilidade organizada) category B, mais-valias on property sales, foreign income double-taxation treaty relief, non-habitual resident (RNH) or the newer IFICI incentivized-professional regime, or the adicional de solidariedade for very high incomes — these are structurally more complex and higher-stakes; route to an OCC.
- **Does not file anything.** Output is a draft estimate and explanation, not a submitted Modelo 3.
- **Does not connect to Portal das Finanças** and never will — this is the structural design choice, not a missing feature.
- **Bracket/deduction figures embedded in this file are a snapshot** and are deliberately left partially unquantified (see 2025 bracket boundary note above) specifically so the assistant re-verifies live rather than trusting stale memorized numbers.
- **Field-lesson sourcing is honestly thin in places.** Portuguese-language IRS discussion is concentrated on Fórum de Finanças Pessoais (by Doutor Finanças) and a handful of personal-finance publishers (Contas Poupança, Doutor Finanças, DECO PROteste) rather than Reddit/Hacker News — general web search returned no indexed r/portugal or r/PortugalExpats threads on these exact topics during this wave's research; do not assume Reddit coverage exists just because it does for other markets. See RESEARCH.md § Practitioner lessons (field reports) for the full source list.

## Disclaimer

Outputs from this skill are drafts for the user's own review, not tax advice. This product is not affiliated with the Autoridade Tributária e Aduaneira (AT) or any Portuguese government body. Final figures and the actual Modelo 3 filing should be confirmed with a contabilista certificado (OCC) or directly with the AT before acting on any number produced here.

**PII handling:** process all documents and figures locally within the conversation only. Never write names, NIFs, IBANs, addresses, or specific euro amounts tied to an identifiable person into any persistent note, memory file, or log — retain only counts, category labels, and non-identifying patterns (e.g. "categoria A + B, married, 2 dependents, IRS Jovem year 3") if any session summary is needed.

**Standard framing for every output:** This is educational information, not financial, tax, or legal advice. Confirm filing positions and classifications with a contabilista certificado (OCC) or the Autoridade Tributária before acting.

## Changelog

- v1.0.0 (2026-07-10): wave-1 floor — computation chain, IRS Jovem, quociente familiar/conjugal, recibos verdes coefficients, joint/separate + PPR decision frameworks, mowei.pt + Portal das Finanças cross-check workflow.
- v2.0.0 (2026-07-10): wave-2 practice depth — restructured Workflow into five failable Modes (Research/Plan/Execute/Monitor/Validate); added six practitioner field lessons (retenção-vs-final-tax confusion, shrinking-refund-is-expected, simulator disagreement, IRS Jovem first-year-window ambiguity, category-B 15%-justified-expenses threshold, joint/separate default-to-separate trap) into the Domain playbook; added file-level-only Integrations table; added Reproducibility & QA rubric with named artifacts, scoring dimensions, and a hard delivery gate; added an honest field-lesson-sourcing note to Limitations. All v1.0.0 content preserved verbatim, including the education-cap (€800/€1,100/€1,000), global-cap (€8,059 coletável threshold), and rent-cap (€700) sentences.
- v3.0.0 (2026-07-10): wave-3 context depth — added Strategic canon subsection (Thinking Fast and Slow, Thinking in Bets, Financial Intelligence, each with a stated framework and this-skill application) at the end of Domain playbook; added Adjacent disciplines section (Upstream: SAF-T PT, ATCUD/QR Portaria 195/2020, e-Fatura DL 198/2012 pipeline, bank-export practice; Downstream: OCC professional standards, Modelo 3/divergências workflow, 10-year records retention + ISO 15489; Horizontal: Todos Contam financial-literacy infrastructure, GDPR data-minimization, Open Banking/PSD2 named as deliberately rejected); added Value-chain positioning section (top-down household KPIs + sponsor questions mapped to modes, bottom-up pattern-to-signal escalation rules with real thresholds, closing chain statement). All v1.0.0/v2.0.0 content preserved verbatim; no other section touched.
- 2026-07-10 v3.1.0 — persistent per-user memory layer (MEMORY.md: Preferences / Lessons / Run log) wired into the Validate hard gate; hard no-PII rule.
- 2026-07-10 v3.2.0 — wave-4 MOAT asset: added a stdlib IRS-2025 estimator (`scripts/validate.py`) with the full 9-row Artigo 68.º bracket table + caps + global-cap formula + IRS Jovem ladder in `assets/constants.json` (every row/cap source-cited; DOCUMENTED APPROXIMATIONS block with directions of error), and 14 hand-computed golden cases in `assets/golden-cases.json` (min bar 12). Wired The moat asset section, an Execute-mode independent-recompute step (3j), and a Validate-mode selftest hard gate (`--selftest` must exit 0). All prior content preserved verbatim.
- 2026-07-10 v3.3.0 — marketplace security & permissions disclosure block (network scope, env-none, file scope, stdlib-only validate.py, no irreversible actions); packaging pass.
- 2026-07-10 v3.4.0 — offline CIRS law snapshot (10 dated verbatim articles) + host-model qualification exam (golden-corpus mode-2 scoring) + weak-model operating contract (no mental arithmetic, echo-before-use, verbatim-law rule).
- 2026-07-10 v3.5.0 — automatic correctness sweep (scripts/sweep.py): asset re-hashing, staleness age-gates, cross-skill value-agreement, code-enforced PII hygiene; Validate gate is now dual (selftest AND sweep).
- 2026-07-10 v3.6.0 — handoff-dossier contribution contract (writes its files into the flagship's dossier folder; Validate confirms).
- 2026-07-10 v4.0.0 — **multi-year retro-refund engine.** Added `assets/constants-multiyear.json` (income years 2022/2023/2024: full Artigo 68.º tables, IAS, categoria-A specific deduction, the year-varying rent cap, global-cap endpoints, and the IRS-Jovem regime *as it stood each year* — every value source-cited to AT official IRS-Jovem folhetos read verbatim + Lei 33/2024 / Lei 32/2024; unconfirmed values would be literal `UNKNOWN` and refused). Made `scripts/validate.py` year-parameterized (loads 2025 from `constants.json`, 2022–2024 from the new file; refuses UNKNOWN-blocked paths) — **all 14 original 2025 golden cases pass unchanged**. Added `assets/retro-cases.json` (9 hand-computed retro-audit cases, min bar 8: missed PPR/rent/health/education, IRS-Jovem-not-claimed, a no-recovery negative control, a time-barred case, a below-materiality case). Added the *Retro-audit and correction paths* Domain-playbook decision table (declaração de substituição / reclamação graciosa 120 d / revisão oficiosa 4 anos / caducidade 4 anos — five cited rows) and a Retro pass (Execute step R). Extended the Validate hard gate and `scripts/sweep.py` (multi-year + retro corpus + correction-path presence checks). No prior content weakened; all disclaimers, anchors and 2025 constants preserved verbatim.
- 2026-07-13 v4.1.0 — offline-operation contract, supported-feature matrix (engine hard-refusal boundary), independent per-taxpayer separate-filing computation with hand-computed golden cases, recommendation format, standardized disclaimer.
