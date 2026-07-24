---
name: portugal-irs-organizer
description: Use when a Portugal tax resident (native or expat) wants to turn a messy folder of payslips, e-Fatura exports, receipts, and statements into a submission-ready IRS Modelo 3 dossier - onboarding a household fiscal profile, mapping income to annexes, building a deduction inventory, flagging missing documents, tracking e-Fatura and submission deadlines, and defending against the post-filing AT "divergencias" letter (trigger catalog, 15-day response protocol, juros/coima math, escalation ladder). Does not calculate exact tax owed, does not connect to Portal das Financas, and does not submit anything on the user's behalf. Ships with a 12-case fictional-household golden corpus + a 12-case divergencias-defense corpus + a 60+ entry Modelo 3 field-code lexicon (which quadro and campo, not just which annex) + stdlib validation harness that regression-tests dossier assembly and post-filing defense (annex mapping, quadro/code pre-fill, deduction flags, divergencia triggers, trap cases) like software.
version: 4.1.0
---

# Portugal IRS Dossier Organizer

## What this skill does

This skill helps a Portuguese tax household organize its own IRS (Imposto sobre o Rendimento das Pessoas Singulares) paperwork into a structured dossier ahead of Modelo 3 submission. It reads the documents the user supplies or pastes in — payslips, e-Fatura category summaries, medical/education receipts, bank interest statements, rental records, brokerage tax statements, donation receipts, PPR statements — and organizes them into a per-annex, per-member checklist with a missing-document list and a deadline map. It does not calculate the final tax owed or refund, does not read or write anything on Portal das Finanças, and does not replace a contabilista certificado (OCC) for anything beyond straightforward organizing.

## The moat asset

This skill ships a **golden-corpus regression harness**: `assets/golden/cases.json` holds 12 fully-worked fictional household cases (household profile + document inventory + e-Fatura category state as input; income-to-annex map rows, a per-member deduction inventory with Present/Missing/NotApplicable statuses, a missing-document list, and a flag list as expected output), and `scripts/validate.py` encodes the same deterministic mapping rules the Domain playbook describes (income type → annex, deduction eligibility conditions) as executable Python so the golden set can be re-derived and checked, not just eyeballed.

This is hard to reproduce, not impossible — a competitor would need to independently work through the same annex-mapping and deduction-eligibility edge cases (the post-2011 mortgage cutoff, the Categoria B 15%-justification floor, the propinas/pensão-de-alimentos mutual exclusivity, the shared-custody wrong-NIF trap, the IFICI/ex-NHR OCC-routing boundary, the unmapped-income STOP condition, and more) and encode them as a matching set of deterministic rules and golden answers, all field-lesson-sourced and cross-checked against the same mapping table this skill's own Execute mode uses. Every case names the specific trap it exercises, so the corpus doubles as documentation of exactly where a naive dossier-assembly attempt goes wrong.

How each mode uses it:
- **Execute** consults `assets/golden/cases.json`'s `_schema` block (status vocabulary, flag codes, annex letters) as the canonical modeling convention when classifying documents and building the Income-to-Annex Map and Deduction Inventory, so a live household dossier uses the same status/flag vocabulary the golden corpus is scored against.
- **Validate** runs the hard gate: `python scripts/validate.py --selftest` must exit 0 before a dossier is presented as complete. A failing or unrun selftest is treated the same as a failed rubric dimension — present the output as a draft-with-gaps, not as ready.

Score a real dossier output against the golden corpus the same way: `python scripts/validate.py <candidate.json>` (candidate JSON shaped like the `expected` block per case id) prints a per-case, per-field match report.

### Post-filing divergências-defense corpus (assets/divergence-cases.json)

The second moat asset is the **post-filing defense layer** — where competing organizers stop (at submission) and households panic (at the AT "divergências" letter). `assets/divergence-cases.json` holds 12 fictional AT-divergência scenarios, each with the flag type, the correct response path, a **cited deadline basis** (the exact article/source behind the clock), the documents that actually rebut the flag, the trap a naive response falls into, and a severity — including one **negative control** (an informational Portal message that needs no response) and one **must-escalate-to-OCC** case (residency + IFICI entanglement). It is hard to reproduce because it encodes the whole ladder — trigger catalog → 15-day response window → justificar-vs-substituir choice → juros compensatórios math → RGIT coima-reduction tiers → reclamação graciosa escalation — as scored, cited data, not prose, and every deadline and rate is anchored to a fetched official/practitioner source (AT folheto maio 2026, CIRS art. 51.º, CPPT art. 70.º, LGT arts. 35.º/60.º, RGIT arts. 29.º–31.º).

How each mode uses it:
- **Execute** builds the Deadline Map and the handoff dossier's post-filing outlier class from this corpus's deadline table and trigger catalog, so a live household's post-filing watch uses the same cited clocks the corpus is gated on.
- **Monitor** drives its July–December post-filing watch (below) off the corpus's trigger catalog and 15-day/120-day deadlines.
- **Validate** runs the integrity gate: `python scripts/validate.py --selftest` re-checks the divergence corpus (schema, ≥10 cases, ≥1 negative control, ≥1 escalate case, every deadline_basis non-empty, every trap named) in the same run that checks the 12 dossier cases — a failure in either blocks delivery.

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

### Modelo 3 field-code lexicon (assets/field-codes.json)

The third moat asset upgrades the dossier from **"which annex"** to **"which quadro and
which code"** — field-level pre-fill instruction. `assets/field-codes.json` holds 60+
verified entries across Anexo A (income campos 401/402/403/404/405/406/407/409/410/417/418,
quadro 4), Anexo B (regime-simplificado campos 401/402/403/408/417 + quadros 3/4A/5/6),
Anexo E (quadros 4A/4B/5), Anexo F (quadros 4/4.2/4.2A/4.2B/4.3/5/6/6G/7), Anexo H
(benefit codes 601/602/603/608 in quadro 6B, plus quadros 4/5/6A/6C/6C1/6C2/7/8), Anexo J
(quadros 4A–4F, campo 420, and the Tabela X country-code convention), and key Anexo G
entries (quadro 4 imóveis, quadro 9 valores mobiliários). Each entry carries `{annex,
quadro, code, meaning, common_error, citation, as_of}` — the one-line meaning, the single
most common household miscoding, and the filling-instruction source it was confirmed
against (fetched 2026-07-10). Codes that could not be confirmed this run were left OUT, not
padded with guesses.

It is hard to reproduce because it is not a form dump: every entry pairs the code with the
**specific miscoding a household makes** (pension income under the employment campo; alojamento
local under the professional-services campo; foreign dividends kept in the domestic capital
annex instead of Anexo J), and the harness ships **8 planted miscoding checks** validated
against the lexicon (a wrong (annex, code) vs the correct one), so the corpus doubles as a
catalog of exactly where naive pre-fill goes wrong — the same field-lesson depth as the two
existing corpora, now at campo granularity.

How each mode uses it:
- **Execute** emits the quadro+code per income/deduction row where the lexicon covers it
  (step 8), so the Income-to-Annex Map and the handoff dossier's 02 map carry a
  ready-to-transcribe `Annex / Quadro / Code` pointer, not just a letter.
- **Validate** runs the integrity + miscoding gate inside `--selftest`: 60+ entries, no
  duplicate (annex, code) pairs, every citation present, `as_of == "2025 income campaign"`,
  and ≥6 planted miscoding checks resolving against the lexicon — a failure shows
  `field-code-lexicon FAIL` in the OVERALL line and blocks delivery.

### Automatic correctness sweep (scripts/sweep.py)

A second deterministic gate that runs alongside the golden-corpus selftest:
`python scripts/sweep.py` (stdlib only, offline, exit 0 = green). It checks, automatically:

- **Asset integrity** — the golden corpus parses and still meets its numeric bars; law
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

- **Zero-setup path (default):** no API keys, no logins, no Portal das Finanças credentials, ever. Everything runs from files the user has already downloaded or pastes directly into the conversation.
- Works from any subset of: payslips (recibo de vencimento), the e-Fatura "Consulta de Faturas" category export or screenshots, medical/pharmacy/education receipts, bank annual interest statements (IRC declaration or extrato), rental income records (contrato + recibos de renda), brokerage annual tax statements (declaração fiscal anual), donation/mecenato receipts, PPR statements, and prior-year Modelo 3 PDFs (for continuity, not required).
- No file format is assumed — PDF, CSV, XLSX, screenshots, or pasted text are all acceptable; the assistant works with whatever the user has.
- The assistant should ask for a public IRS-related web page only when confirming a current-year threshold or deadline; it must never ask the user to log into or export data via their Portal das Finanças credentials, and must refuse if asked to do so.

## Modes

This skill runs as five explicit modes. A session normally moves Research → Plan → Execute → Validate once per filing season, with Monitor running continuously (or on each check-in) in the background of that cycle. Announce which mode is active when it isn't obvious from context, and do not silently skip a mode's failable check.

### Research

**Purpose:** establish (or refresh) the current-year facts the rest of the session depends on — annex numbering, deduction caps, IAS-linked thresholds, deadlines — before any household-specific work starts.

**Inputs:** today's date; the income year in scope; the household's prior-year profile file if one exists (to see what changed since last confirmed).

**Outputs:** a short "facts as of [date]" note confirming (or correcting) the figures in the Domain playbook for the income year in scope, and a flag list of anything that could not be confirmed without a live web check.

**Failable check:** if the income year in scope is not the one this file's Domain playbook is dated to, STOP and re-verify every euro figure and annex letter against `info.portaldasfinancas.gov.pt` before proceeding to Plan — do not carry forward a prior year's caps by assumption.

### Plan

**Purpose:** decide the shape of this session — new household (go to Onboarding) vs. returning household (load saved profile), what documents are expected this cycle, and what changed since the last run.

**Inputs:** the saved fiscal profile file if one exists; the user's statement of what changed this year (new job, new dependent, moved, started freelancing, etc.).

**Outputs:** either a routing decision straight to Onboarding (first run), or a diffed profile plus a personalized document-collection checklist for this cycle (see Onboarding step 7 for how the checklist is built).

**Failable check:** if no saved profile exists and this is not clearly a first run, STOP and run Onboarding before touching any document — guessing at household composition instead of asking produces a dossier that misclassifies income and deductions.

### Execute

**Purpose:** do the actual intake, classification, and dossier assembly. This is the operational core of the skill.

**Inputs:** the household's documents (payslips, e-Fatura export, receipts, statements); the fiscal profile from Plan/Onboarding; the Domain playbook mapping tables.

**Outputs:** the seven Output format artifacts (Household Fiscal Profile, Income-to-Annex Map, Deduction Inventory, Missing-Document Checklist, e-Fatura Validation Audit, Deadline Map, Next Steps).

**Steps:**
1. **Check for an existing fiscal profile.** Look for a saved profile file (see Onboarding). If found, load it and skip straight to step 4 unless the user says their situation changed this year.
2. **Run onboarding if no profile exists** (see dedicated section below).
3. **Save the fiscal profile locally** so this and other suite skills (salary/net-pay tools, deduction planners) can reuse it without re-asking.
4. **Intake documents.** Ask the user to point to a folder or paste/upload documents one category at a time. Confirm receipt of each category out loud ("got 3 payslips, 1 e-Fatura export").
5. **Classify each document to a Modelo 3 annex and category** using the Domain playbook mapping table, cross-checked against the `income_type_to_annex_map` and `_schema.status_vocabulary`/`flag_codes` in `assets/golden/cases.json` so classifications use the same conventions the golden corpus is scored against. Flag anything ambiguous (e.g., a payment that could be Category B or a hobby) instead of guessing silently.
6. **Build the per-member deduction inventory.** For each household member, list applicable deduction types (health, education, general/family, housing, PPR, dependents, disability) and mark each as Document Present / Document Missing / Not Applicable, citing the specific document that supports it.
7. **Run the e-Fatura validation audit.** Ask the user for their e-Fatura category export (or a screenshot of "Faturas com necessidade de ação"/pending invoices) and produce a fix list: which invoices are pending validation, which look mis-categorized, and what the deadline is this cycle.
8. **Assemble the annex-mapping table** — one row per income/deduction item, with the annex it belongs to, the household member, and the amount status (confirmed from a document vs. estimated vs. missing). Where `assets/field-codes.json` covers the item, also emit the **quadro and campo/benefit code** (e.g. a salary → `A / Q4 / 401`; a PPR contribution → `H / Q6B / 601`; foreign dividends → `J / Q4D`), and surface that entry's `common_error` as a one-line check so an easy miscoding (pension under the employment campo, alojamento local under the professional-services campo, foreign income left in the domestic annex) is caught before handoff. Leave the code column as "—" for any item the lexicon does not cover — never invent a campo number.
9. **Generate the missing-document checklist** with a plain-language "where to get it" instruction for each gap (see Output format).
10. **Generate the deadline map** for the current cycle, anchored to today's date, using the mowei.pt `calendario-fiscal` page as the reference source alongside official AT dates.
11. **Hand off, don't file.** Present the dossier as a review draft. Point the user to `modelo3-irs` and `irs-jovem-deducoes` on mowei.pt for free calculation help, and to Portal das Finanças or an OCC for actual submission. Never offer to submit, e-file, or log in on the user's behalf.
12. **Re-run trigger.** If the user's situation changed (new job, new dependent, moved house, started freelancing), re-run Onboarding to refresh the profile before continuing.

**Failable check:** if any household member has an income or deduction item with no mapped annex or category after checking the Domain playbook, STOP and resolve or explicitly flag it in the Income-to-Annex Map as "Unmapped — needs OCC review" before drafting the rest of the dossier — never assign a best-guess annex silently.

### Monitor

**Purpose:** hold the recurring, calendar-driven watch duties that don't fit a single working session — deadlines approaching, invoices still pending validation, and fiscal-rule changes that could invalidate the current profile or dossier.

**Inputs:** the Deadline Map produced in Execute; today's date; the saved fiscal profile's income-year label.

**Outputs:** a status nudge when a tracked date is within 14 days (e-Fatura validation deadline, Modelo 3 submission window open/close, the 16–31 March reclamação window for AT-computed deduction errors) and a rule-change alert if the user mentions a new Orçamento do Estado, a new IAS value, or a new-year filing season starting.

**Post-filing watch duty (July–December):** after the 30 June submission window closes, Monitor's job shifts to the divergências defense layer (see the Domain playbook's "Post-filing: divergências defense"). Each check-in in this period: (a) ask whether any AT "Divergência na declaração Mod. 3" notification has arrived (carta postal / ViaCTT / Portal reserved area); (b) if one has, start the 15-day response clock immediately and route to the response protocol — never let it lapse into a correção oficiosa with juros compensatórios; (c) surface the reclamação-graciosa 120-day fallback if the 15-day window was already missed. Drive the trigger catalog and clocks off `assets/divergence-cases.json`, not memory.

**Failable check:** if the current date has crossed into a new income year's filing season and the saved profile or Domain playbook figures are still labeled with the prior income year, STOP presenting cached deadline/cap figures as current — trigger Research mode again before answering any date or euro-figure question. Additionally, if a divergência notification is open and its 15-day (or extended 25-day) response window is within 5 days of lapsing, STOP and escalate that as the top-priority nudge before anything else.

### Validate

**Purpose:** the pre-delivery gate — the last check before the dossier is handed to the user, an OCC, or another suite skill.

**Inputs:** the assembled Output format artifacts from Execute.

**Outputs:** a pass/fail note against the Reproducibility & QA rubric, with every failed dimension listed as a named remaining gap (not silently fixed by fabricating a value).

**Failable check:** apply the "do NOT deliver unless" hard gate in the Reproducibility & QA rubric verbatim — if any condition there fails, do not present the dossier as complete; present it as a draft-with-gaps and name the gaps. This includes the golden-corpus gate: run `python scripts/validate.py --selftest` — a failing or unrun selftest is treated as a failed rubric dimension; do not deliver the dossier as complete until it exits 0. The same `--selftest` run now also gates the post-filing divergências-defense corpus (`assets/divergence-cases.json`) and the Modelo 3 field-code lexicon (`assets/field-codes.json`): the OVERALL line must show `divergence-corpus PASS` AND `field-code-lexicon PASS` (60+ codes, no duplicate annex+code pairs, ≥6 planted miscoding checks) alongside `dossier-corpus PASS`, or the run is draft-with-gaps.

## Onboarding (first run)

Run this guided intake before doing anything else the first time this skill is used for a household — this is the entry point Plan mode routes to when no saved profile exists. Ask questions in plain language, one topic block at a time, and accept "not sure" as an answer (mark it as a flag to resolve later, don't block progress).

**1. Agregado familiar (household composition)**
- Filing alone or with a spouse/partner (casado/unido de facto)?
- Tributação conjunta (joint) or separada (separate) preference — if unsure, note it as a decision to compare later, not settle now.
- Dependents: number, ages, and whether any are students away from home >50km (affects education deduction caps) or have a disability (affects specific thresholds).

**2. Income types per household member** — ask this per adult:
- Employment (trabalho dependente, Categoria A)?
- Pension (Categoria H)?
- Self-employed / recibos verdes (Categoria B) — simplified regime (regime simplificado) or organized accounting (contabilidade organizada)?
- Rental income (rendas, Categoria F)?
- Capital income — interest, dividends (Categoria E)?
- Capital gains — property, securities, crypto (Categoria G)?
- Foreign-source income of any kind (Categoria J)?

**3. Special regimes**
- Under 35 and want to check IRS Jovem eligibility?
- Former NHR (non-habitual resident) status ending, or newly applying for IFICI (the post-2024 NHR successor, "NHR 2.0")? If yes, flag Anexo L and note the household will need professional confirmation of eligible-activity classification.
- If Categoria B: simplified regime or organized accounting — this changes which coefficients and expense-justification rules apply.
- First year of self-employed activity? [field lesson] New freelancers commonly don't know Portugal offers a 50% reduction on Categoria B taxable income in year 1 and 25% in year 2 of a first-time activity — ask explicitly and flag it in the profile so Execute doesn't miss the incentive (source: practitioner freelancer-tax guides, see RESEARCH.md).

**4. Housing situation**
- Owner with a mortgage contracted on or before 31 December 2011 (only these qualify for the interest-deduction rule — post-2011 mortgages generally do not)?
- Renter (rendas may be deductible)?
- Neither (no housing-related deduction to track)?

**5. For expats specifically** — ask this whenever the household includes a non-native filer:
- Is this their first Portuguese IRS filing? [field lesson] The Portal das Finanças access password/credential for a first-time filer is posted by mail to the Portuguese address on file — someone still using an overseas mailing address, or who just arrived, needs to update the address (or use a fiscal representative) well before the filing window, or they will be locked out at submission time. Ask early enough to leave time for postal delivery.
- Any foreign bank accounts, foreign pensions, or foreign investment accounts, even dormant or low-income ones? [field lesson] Anexo J catches expats off guard because it applies to foreign-source income broadly, including a foreign account that produced little or no income in the year — don't let "it barely earned anything" rule out declaring it; flag for Anexo J review either way.

**6. Close the interview** by reading back a one-paragraph summary of the household profile and asking for a yes/correct or a correction.

**7. Save the profile.** Write a local profile file (e.g. `irs_profile_<year>.md` in the user's working folder, wherever they keep this dossier) containing ONLY: household composition counts, ages of dependents (no names), income-type flags per member (labeled Member 1 / Member 2, not by name), special-regime flags, housing category, and joint/separate preference. This file is meant to be reused by other Portuguese Personal Finance Desk skills (salary calculators, deduction planners) without re-asking these questions. Follow the PII rule in the Reproducibility & QA rubric below when writing it.

**8. Produce the personalized document-collection checklist** based on what step 2 revealed — e.g. a household with rental income gets "contrato de arrendamento + recibos de renda emitidos" on the list; a household with none does not.

### Resumable intake (intake-state.json)

Onboarding is a resumable state machine, not a one-shot interview. The assistant
maintains `intake-state.json` in the skill folder:

```json
{
  "stage": "3-income-types",
  "completed": ["1-agregado", "2-dependents"],
  "answers": { "adults": 2, "dependents": 1, "income_types": ["catA", "catB-simplified"] },
  "pending": ["4-regimes", "5-housing", "6-documents"],
  "updated": "YYYY-MM-DD"
}
```

Rules: labels and counts ONLY — real names, NIFs, and euro amounts never enter the state
file (they belong in the dossier, which is the user's own deliverable). On session start,
if the file exists with a non-empty `pending`, resume at the first pending stage and say
so ("resuming intake at step 4 of 6"). A completed intake writes the fiscal-profile file
and empties `pending`. The user can say "restart intake" to reset the file.

## Domain playbook

**Modelo 3 annex reference (2025 income year, filed 2026)** — confirm annex letters against the current-year Modelo 3 PDF at the start of a filing season, as the AT periodically adds/renames annexes:
- **Rosto (cover page):** household identification, agregado composition, joint/separate election.
- **Anexo A** — Categoria A (employment) and Categoria H (pensions). Joint filers include both spouses' income on one Anexo A; separate filers each submit their own.
- **Anexo B** — Categoria B, regime simplificado (self-employed/freelance, presumed-expense coefficients).
- **Anexo C** — Categoria B, contabilidade organizada (organized accounting).
- **Anexo E** — Categoria E, capital income (interest, dividends) — note many are subject to definitive withholding and only need declaring if the taxpayer opts for englobamento (aggregation).
- **Anexo F** — Categoria F, rental income.
- **Anexo G** — Categoria G, capital gains (property, securities, crypto) and other increases in wealth.
- **Anexo H** — tax benefits and deductions (health, education, general/family, housing, PPR, disability, donations) — this is where most of this skill's inventory work lands.
- **Anexo J** — foreign-source income of any category.
- **Anexo L** — IFICI / ex-NHR special regime election (post-2024 successor to the old NHR annex).
- Annex SS and other niche annexes (undivided inheritance, etc.) exist but are out of scope for wave-1 — flag and defer to an OCC if the household mentions one.

**Deduction rates and caps, income year 2025 (filed 2026) — as of July 2026 search, verify against `info.portaldasfinancas.gov.pt` before relying on exact euro figures for a live filing:**
- Health (saúde): 15% of qualifying expenses, cap €1,000.
- Education/training (educação, CIRS art. 78.º-D): 30% of qualifying expenses, cap €800 per household (agregado). Two distinct uplifts: (a) displaced students up to age 25 studying >50 km from home — rents count up to €400/yr and the household cap can rise to €1,100 where the excess over €800 corresponds to those rents; (b) establishments in interior territories/Autonomous Regions — +10 p.p. majoração with a €1,000 global limit.
- General & family expenses (encargos gerais familiares): 35% of e-Fatura-registered general expenses, cap €250 per taxpayer (€500 joint); single-parent households get 45% and a €335 cap.
- Housing rent (arrendamento): 15% of rent paid, cap €700 (household-wide, income year 2025).
- Housing mortgage interest: 15% of interest, cap €296 — **only for contracts signed on or before 31 December 2011**; this is the single most common user misunderstanding to check for.
- PPR contributions: 20% deductible, age-tiered caps — €400 under 35, €350 age 35–50, €300 over 50 (up to 70).
- Global cap on combined deductions (health+education+housing+alimony+PPR/benefits) for joint filers: uncapped below €8,059 rendimento coletável; a progressive formula between €8,059–€83,696; flat €1,000 cap above €83,696 (income year 2025 — OE2026 re-anchors the formula for income year 2026; verify next season).
- These figures apply to income year 2025. Do not carry them forward to a future income year without re-searching — the deduction basket, coefficients, and IAS-linked figures are revised most years.

**IRS Jovem (income year 2025, filed 2026):**
- Available to residents up to age 35, regardless of qualification level (the prior university/secondary-school requirement was dropped starting with income year 2025).
- Exemption ceiling: 55× IAS. For 2025 (IAS = €522.50) that is €28,737.50; note the IAS is re-set each year, so re-check before quoting a 2026-income-year figure.
- Exemption starts at 100% in year 1 and steps down across up to 10 years — do not assume a flat percentage; confirm the household's specific year in the regime.
- The `irs-jovem-deducoes` tool on mowei.pt is the recommended free calculator for the exact tier.

**Regime simplificado (Categoria B) coefficients, income year 2025:**
- 0.75 for professional-activity income listed in the Article 151 CIRS table (the common "recibos verdes" case).
- 0.35 for other service income not listed in the table, when a specific coefficient doesn't apply.
- 0.10 for subsidies and other unlisted Categoria B income.
- 0.50 for restricted-area local accommodation (alojamento local).
- When the 0.75 or 0.35 coefficient applies, the taxpayer must justify professional expenses equal to at least 15% of gross annual income (via e-Fatura-registered invoices) — flag this explicitly for any freelancer earning above roughly €29,748/year, since falling short of the 15% floor increases taxable income.
- [field lesson] First-time self-employed activity qualifies for a Categoria B taxable-income reduction — 50% in year 1, 25% in year 2 — that is easy to miss because it isn't obvious from the coefficient table alone; confirm "is this your first year of atividade aberta?" during Onboarding and flag it in the deduction inventory notes, not as a formal Anexo H deduction (source: practitioner freelancer-tax guides, see RESEARCH.md).

**IFICI / ex-NHR ("NHR 2.0"):**
- Applies a 20% flat rate to eligible Categoria A/B net income from qualifying activities, with most foreign-source income exempt (with progressivity).
- Initial registration deadline for new tax residents in a given year is mid-January of the following year; the Anexo L election itself is filed with the Modelo 3 by the normal June 30 deadline.
- This is a specialist area — the skill's job is to flag eligibility and route the household to Anexo L and professional confirmation, not to determine eligibility itself.

**e-Fatura validation edge cases:**
- An invoice sitting in "Faturas com necessidade de ação" past the validation deadline is typically excluded from that category's deduction — flag these as urgent, dated items, not routine ones.
- [field lesson] Missing the validation deadline entirely is not always a total loss: some expense categories are reported to the AT directly by the issuing entity and don't depend on manual e-Fatura validation, and in specific cases the taxpayer can still manually declare a value in Anexo H at their own responsibility. Don't tell a household who missed the deadline that the deduction is automatically zero — flag it as "reduced/uncertain, confirm with an OCC" instead (source: Contas Poupança, "IRS: Não validei as faturas. E agora?", see RESEARCH.md).
- A common miscategorization: a pharmacy purchase tagged as "Outros" instead of "Saúde," or a private-school payment tagged as a generic service. List category mismatches as their own checklist line, separate from missing invoices entirely. [field lesson] The fix is a manual step the user does themselves in the e-Fatura portal (select the invoice → "Alterar" → pick the correct category) — this skill should describe that exact click path in the Missing-Document/mis-categorization checklist rather than a vague "recategorize it" instruction, since users report not knowing where the control lives (source: e-konomista/Sage.com correction guides, see RESEARCH.md).
- Restaurant/general-expense invoices count toward "encargos gerais familiares" only when correctly categorized and NIF-associated — a receipt paid without giving the NIF at point of sale cannot retroactively be claimed at the register, but [field lesson] if the merchant didn't capture the NIF, the invoice can still sometimes be added by the buyer via the e-Fatura app's QR-code scan of the physical receipt, or entered manually with proof of purchase — flag this as a recovery option before writing the item off entirely (source: e-konomista, see RESEARCH.md).
- [field lesson] An invoice that never shows up in e-Fatura at all (not just miscategorized) can be past the issuer's own legal communication deadline (the 5th of the month following purchase, since January 2023 under OE2022 — previously the 12th under Law 119/2019) — if it's still missing after that window, the user can register it manually in the e-Fatura portal with the invoice number, date, issuer NIF, and value. Distinguish "not yet communicated, will appear" from "past deadline, register manually" in the Missing-Document Checklist (source: DECO PROteste / CRN-Contabilidade validation guides, see RESEARCH.md).
- [field lesson] Between 16–31 March each cycle there is a separate reclamação window where the taxpayer can review the AT's own pre-computed deduction values (as opposed to raw e-Fatura entries) and dispute errors or omissions before the return is filed — this is a second checkpoint distinct from the e-Fatura validation deadline and belongs on the Deadline Map as its own line, not folded into the validation deadline (source: Contas Poupança deadline coverage, see RESEARCH.md).

**Household-composition edge cases to catalog (for a future golden-corpus wave):**
- Divorced/separated parents splitting a dependent — this affects who can claim which portion of education/health deductions and typically needs a signed regulation-of-parental-responsibilities document; flag, don't resolve.
- A member who is tax-resident in Portugal for only part of the year (arrived/left mid-year) — residency-period income splitting is out of scope; flag to an OCC.
- Mixed Categoria A + B income in the same person (e.g., salaried plus freelance side income) — needs both Anexo A and Anexo B/C, and the specific deduction (Categoria A) does not apply to the Categoria B slice.
- A rental property with a mortgage where only part of the year was rented — mixing Anexo F rental deduction rules with the pre-2011 mortgage-interest rule requires care; flag as a specialist item.
- [field lesson] First-time expat filers frequently discover mid-onboarding that they cannot access Portal das Finanças at all yet, because their access password never arrived (sent by post to a Portuguese address they don't have or haven't updated) — treat "do you have a working Portal das Finanças login already" as its own onboarding checkpoint, separate from the household/income questions, since it can block the entire filing timeline if left to the end (source: expat filing guides, see RESEARCH.md).

### Post-filing: divergências defense

The product does not stop at submission. After the Modelo 3 is filed, the AT validates it against its own databases; where a mismatch or an unproven item is found, it raises a **"Divergência na declaração Mod. 3"** — sent by carta postal, ViaCTT, or the Portal das Finanças reserved area (source: AT folheto *"Divergências na declaração Mod. 3 IRS"*, maio 2026). Ignoring it does not make it disappear — it converts into a **correção oficiosa / liquidação adicional** with more tax due plus **juros compensatórios**. This section is the defense layer.

**Trigger catalog (what raises a flag) — official + practitioner-sourced:**
- **Deduction mismatch / e-Fatura vs declared** — a saúde/educação/geral deduction manually entered above the e-Fatura category total, or a category the AT excluded (e.g. a school payment tagged "Outros" not "Educação") (source: Doutor Finanças, e-konomista).
- **Rendas without recibo eletrónico** — a tenant's rent deduction with no matching recibo eletrónico de renda from the landlord's Categoria F declaration (source: practitioner divergência guides).
- **Foreign income omitted** — foreign dividends/interest/pensions with no Anexo J (CRS/bank cross-match); Anexo J is mandatory regardless of amount (source: AT folheto maio 2026).
- **Mais-valias imobiliárias** — property-sale valorization expenses declared in Anexo G without proof, or works outside the 12-year window of **CIRS art. 51.º** (source: AT folheto maio 2026).
- **Rendimentos ilíquidos / valores mobiliários** — sold shares/securities not declared in Anexo G (and Anexo J if foreign-held); declaration is mandatory whether the result is **positive OR negative** (source: AT folheto maio 2026).
- **Coerência de CAE, cadastro e rendimentos** — Categoria B income declared under an Anexo B field incompatible with the registered activity code (source: AT folheto maio 2026).
- **Retenção na fonte mismatch** — the withholding typed into Anexo A differs from the employer's DMR figure held by the AT (source: practitioner guides).

**Response protocol (the ladder):**
1. **Read what is actually flagged.** On Portal das Finanças: search bar → "Divergências de IRS" → *Consultar Divergências ▸ Aceder* → authenticate → **"+ info"** for the exact irregularity and its resolution instructions (source: AT folheto maio 2026). Do not guess the flag from the smaller-than-expected refund alone.
2. **Gather the exact supporting document** the flag calls for (see the trigger catalog and the divergence-cases corpus for the document-per-flag map).
3. **Respond within the prazo** by the right path: **Justificar** (ENVIAR JUSTIFICAÇÃO — a text box plus attached comprovativos, when the declared values are correct) or **Corrigir / declaração de substituição** (when there is a genuine error — submit the *full* declaration with *all* annexes, marked as a substituição, not a 1.ª declaração) (source: AT folheto maio 2026).
4. **Escalation ladder if unresolved:** missed the 15-day window / already got a liquidação adicional → **reclamação graciosa** within **120 days** (CPPT art. 70.º). Specialist substance (residency splitting, IFICI/Anexo L, organized accounting) → hand to an **OCC immediately**, do not self-draft the justification.

**Deadline table (income year 2025, filed 2026 — every row cited):**

| Deadline | Length | Basis (cited) |
|---|---|---|
| Respond to a divergência (justify or substitute) | **15 days** from notification; extendable to **25 days** with documented difficulty obtaining evidence | AT divergência notification practice — Doutor Finanças / CGD Saldo Positivo, 2026 |
| Substituição with **no coima** | inside the filing window **1 April – 30 June** | AT folheto maio 2026 (PENALIDADES) |
| Reclamação graciosa (against the liquidação) | **120 days** from the CPPT art. 102.º events | CPPT art. 70.º |
| Juros compensatórios accrual | day-by-day until the correction | LGT art. 35.º |
| Audiência prévia (before an adverse decision) | the AT must hear the taxpayer before deciding | LGT art. 60.º |

**Penalty math (cited rates):**
- **Juros compensatórios: 4%/year**, accrued day-by-day: `imposto × 0.04 × dias ÷ 365` (Portaria 291/2003; LGT art. 35.º n.º 10 → Código Civil art. 559.º).
- **Coima reduction (RGIT art. 30.º, Lei 7/2021, in force 2022):** **12.5%** of the legal minimum if payment is requested **before** any auto de notícia / participação / inspection begins; **50%** of the legal minimum up to the audiência-prévia deadline within an inspection — each conditioned on paying within **30 days** of the reduced-coima notification and regularising.
- **Coima minimum (RGIT art. 31.º):** where the coima varies with the tax due, the minimum is **10%** (individuals) / 20% (companies) of the tax owed.
- **Dispensa de coima (RGIT art. 29.º):** no coima where, cumulatively, the agent had no conviction/benefit in the prior **5 years**, there was no prejuízo efetivo to tax revenue, and the fault is regularised.

**When to hand to an OCC immediately (do not self-respond):** any divergência entangled with mid-year residency splitting, an IFICI/ex-NHR (Anexo L) election, contabilidade organizada (Anexo C), cross-border dual filing, or a mais-valias cost-basis dispute the household cannot document cleanly. The skill's job is to read the flag, name the document, and route — not to draft a justification that could lock in a wrong liquidação. See `assets/divergence-cases.json` for 12 worked scenarios (with a negative control and a must-escalate case).

### Strategic canon

*Adjacent operator wisdom — not tax law, but the operating discipline behind how this skill is designed and run.*

**Nudge (Thaler & Sunstein).** People are "Humans, not Econs" — predictably biased, so the choice architecture around them quietly determines outcomes; the fix is libertarian paternalism: set the default to the good option, strip friction from what you want chosen, add friction to what you don't, and design for the fact that people will make errors. Applied here: the Onboarding interview and the saved fiscal profile ARE choice architecture. Defaulting every household into "flag the NIF-on-every-invoice habit" and a recurring monthly e-Fatura check-in, rather than leaving those as optional asides, is the good default doing the work; the document-collection checklist reduces friction on gathering exactly what's needed instead of everything; and the "not sure" answer path in Onboarding, plus the Unmapped-item flag in Execute, are the skill expecting and designing for user error rather than assuming a clean intake.

**Thinking in Bets (Annie Duke).** Every decision is a bet on an uncertain future, and the cardinal error is "resulting" — judging a decision's quality by its outcome when luck (or, here, the AT's opaque validation logic) sits in between. The fix: think in probabilities, separate decision quality from outcome quality, and run premortems ("it's a year later and this failed — why?"). Applied here: the honest framing to run before filing is a premortem — "it is July and the AT flagged our declaration, why?" — which surfaces unmapped income, uncategorized invoices, and missing documents while there's still time to fix them. It also reframes a smaller-than-expected refund as a possible outcome-quality problem (an AT edge case) rather than automatically a decision-quality failure (a badly built dossier), and vice versa — a good refund doesn't retroactively prove the dossier was complete.

**High Output Management (Andrew Grove).** A manager's output is leveraged by watching a paired set of indicators — leading and lagging — and looking into the process before a defect ships, rather than waiting for the final number. Applied here: Monitor mode is the leading-indicator layer. Pending e-Fatura invoices and missing documents are leading indicators of a lost deduction; the eventual refund or amount owed is the lagging one, arriving too late to fix anything. Pairing "speed of intake" (how fast documents get classified) with "classification quality" (how many land Unmapped or mis-categorized) is exactly Grove's paired-indicator discipline — a fast but sloppy intake looks good on one metric and hides the defect that will surface in June.

## Adjacent disciplines (vertical & horizontal)

### Upstream (where the inputs come from)

- **SAF-T (PT)** (Standard Audit File for Tax, Portuguese version) — the AT-mandated XML export format that underlies Portugal's invoicing and accounting data pipeline; it is why e-Fatura and business invoicing systems can feed the AT a structured, machine-readable record at all. Matters here because it's the plumbing behind every e-Fatura category export the skill ingests — a household never touches SAF-T directly, but the export they hand over exists because businesses generate it.
- **ATCUD + QR code invoice requirements (Portaria 195/2020)** — every Portuguese invoice must carry a QR code and an ATCUD (unique document code assigned by the AT), mandatory since 1 January 2023. Matters here because it's what makes an invoice AT-traceable in the first place — a receipt without a working ATCUD/QR is a signal the document may be informal or non-compliant, worth a second look before it's filed as a deduction-supporting document.
- **The e-Fatura communication pipeline (DL 198/2012 family)** — the legal deadline structure (currently the 5th of the month following issuance, since January 2023 under OE2022; previously the 12th under Law 119/2019) that obliges issuers to report invoices to the AT; this is the deadline the Domain playbook's "past the issuer's own legal communication deadline" field lesson is built on. Matters here because it's the legal clock behind the difference between "not yet communicated, will appear" and "past deadline, register manually."
- **Bank statement export practices** — banks issue annual interest/IRC statements in whatever PDF/CSV format their own systems produce, with no shared national standard (unlike SAF-T for invoicing). Matters here because it's why this skill treats bank statements as free-form input rather than assuming a fixed schema the way it can for e-Fatura category exports.

### Downstream (who consumes the outputs)

- **Contabilistas certificados (OCC professional standards)** — the Ordem dos Contabilistas Certificados sets the professional standards this skill routes every ambiguous or specialist case to (organized accounting, capital gains cost-basis, cross-border residency splits). It matters because this skill's "flag, don't resolve" boundary only works if there's a real professional standard on the other end of the referral — OCC accreditation is that standard.
- **The Modelo 3 filing process and AT validation/divergências workflow** — the dossier this skill produces is a pre-filing draft; the actual filing goes through the AT's own Modelo 3 submission and its automated divergência checks (where the AT flags inconsistencies against its own pre-filled data). Matters because the dossier's whole job is to reduce the odds of tripping that downstream validation — a well-mapped annex table is directly what keeps the household off the AT's exception queue.
- **Records-retention duties** — Portuguese law (CIRC art. 123.º — livros e registos contabilísticos — CIRC art. 130.º — dossier fiscal — and CIVA art. 52.º) requires taxpayers to keep books, records, and supporting fiscal documents for 10 years; this applies to both physical and electronic archives (Decreto-Lei 28/2019). Matters here because the dossier and its supporting documents aren't disposable once filed — the household needs a retention plan, not just a filing event. **ISO 15489** (Records Management) is the international frame for that discipline — the principle that captured records need systematic control over their whole lifecycle, not just creation — even though this skill doesn't implement archival tooling itself.

### Horizontal (sibling crafts)

- **Financial-literacy infrastructure — Todos Contam / Plano Nacional de Formação Financeira** (the joint Banco de Portugal / CMVM / ASF financial-education initiative). What it is: a national portal and curriculum for financial literacy, including budgeting and credit simulators. Why it matters to this skill's user: it's the sibling craft that builds the household financial-literacy baseline (budgeting, saving habits) that this skill assumes and builds a tax-organizing layer on top of, rather than teaching from scratch.
- **GDPR data-minimization** — the principle (and the craft) this skill actively practices, not just adjacent to: the saved fiscal profile stores only counts, age bands, and category flags, never names, NIFs, or exact amounts. Why it matters: it's the reason the Reproducibility & QA rubric's PII-hygiene dimension exists at all — this skill's file-level, credential-free design is a direct application of data-minimization as an operating discipline, not a legal afterthought.
- **Open Banking / PSD2** — the EU framework that lets third parties pull transaction data directly from a user's bank account via API, with consent. Named explicitly here as the deliberately-rejected adjacent capability: this skill could technically ingest bank data faster via PSD2 aggregation, but it stays file-level by design — the user exports and pastes their own bank statement rather than granting API access to a financial account. That's a scope boundary, not a missing feature.

## Value-chain positioning: top-down & bottom-up

### Top-down

The household-level KPIs this skill moves:
- **Document-completeness %** per household member — the share of expected documents actually collected and classified.
- **Unmapped-income items** — target 0 by the time Execute hands off; every income/deduction item should land in an annex or be explicitly flagged for OCC review.
- **Pending e-Fatura invoices at deadline** — target 0 by the validation cutoff each cycle.
- **Days-before-deadline the dossier is ready** — how much runway exists before the Modelo 3 submission window closes, versus a last-week scramble.

Sponsor questions a household-CFO (the filing spouse/partner, or whoever owns the household's fiscal admin) would ask, mapped to the mode that answers them:
- "Are we ready to file, or still missing things?" → **Execute** (Missing-Document Checklist).
- "Did anything change this year that changes our numbers?" → **Plan** (diffed profile).
- "Are we about to miss a deadline?" → **Monitor** (Deadline Map nudges).
- "Is this actually correct, or just complete?" → **Validate** (the pre-delivery gate).

Plan mode is the entry point from the top — it's where a household-CFO's "what's different this year" question gets routed before any document touches the dossier.

### Bottom-up

Pattern-to-signal escalation rules, sensed by Monitor and Validate and surfaced upward:
1. **If the same income item recurs Unmapped across 2+ filing cycles** → escalate to a standing OCC consultation for that income type, not a repeated per-year flag — a recurring unmapped item usually means the household's income structure needs a professional read, not another guess.
2. **If the household's own deduction total drifts more than ~10% from the mowei.pt calculator estimate across 2 consecutive cycles** → escalate to re-running Onboarding in full rather than trusting the diffed profile — a repeated estimate-vs-simulator gap usually means the saved profile itself has drifted from the household's real situation.
3. **If pending e-Fatura invoices in one category (e.g. Saúde) pile up past the validation deadline in 2+ consecutive cycles** → escalate from "flag it in the audit" to a standing mid-year check-in reminder for that specific category, since a one-off miss is normal but a repeat pattern means the household's invoice-NIF habit at point of sale needs fixing, not just the paperwork.

Monitor and Validate modes are the sensors that feed these signals — Monitor watches the calendar-driven drift in real time, Validate catches it at the pre-delivery gate before a flawed pattern repeats into a third cycle.

**Chain:** household member → this skill (organizes and classifies) → mowei.pt calculators / official AT tools (compute the figure) → OCC / AT (files and confirms).

## Integrations

**File-level only.** This skill never uses OAuth, never calls an API requiring credentials, and never runs a background daemon or scheduled job against a third-party account. Every input listed below is a file the user exports or downloads themselves and pastes/uploads into the conversation; every mowei.pt reference is a page the user opens in their own browser as a manual cross-check, not something this skill connects to programmatically.

| Tool / Source | Free or Paid | Format consumed | Format produced |
|---|---|---|---|
| e-Fatura portal ("Consulta de Faturas" manual export) | Free | CSV/XLSX export, or screenshot/pasted text | — (input only) |
| Portal das Finanças pre-filled data (viewed by the user in their own browser, described back to the assistant) | Free | Pasted text/screenshot of what the user sees on screen | — (input only) |
| Bank annual interest / IRC statements | Free (bank-issued) | PDF/CSV downloaded by the user | — (input only) |
| Brokerage annual tax statement (declaração fiscal anual) | Free (broker-issued) | PDF/CSV downloaded by the user | — (input only) |
| Payslips (recibo de vencimento) | Free (employer-issued) | PDF or pasted text | — (input only) |
| Prior-year Modelo 3 PDF (optional, for continuity) | Free | PDF | — (input only) |
| mowei.pt `calendario-fiscal` | Free | — (reference page, opened manually) | — |
| mowei.pt `modelo3-irs` | Free | — (reference calculator, opened manually) | — |
| mowei.pt `irs-jovem-deducoes` | Free | — (reference calculator, opened manually) | — |
| This skill's own outputs | — | — | Markdown tables/checklists; a local `irs_profile_<year>.md` profile file |

## Reproducibility & QA rubric

**Named intermediate artifacts** (so two runs on the same household/documents are comparable):
- `irs_profile_<year>.md` — the saved fiscal profile from Onboarding/Plan.
- `income_annex_map_<year>.md` — the Income-to-Annex Map from Execute.
- `deduction_inventory_<year>.md` — the per-member Deduction Inventory from Execute.
- `missing_documents_<year>.md` — the Missing-Document Checklist.
- `efatura_audit_<year>.md` — the e-Fatura Validation Audit.
- `deadline_map_<year>.md` — the Deadline Map from Execute/Monitor.

**Scoring rubric (0–2 per dimension, applied in Validate mode):**

| Dimension | 0 | 1 | 2 |
|---|---|---|---|
| Completeness | Major income/deduction categories from Onboarding are unaddressed in the artifacts | Most categories addressed, some gaps unflagged | Every category the household reported has a corresponding row/status, including "flagged, unresolved" |
| Correctness-of-year-labeling | Euro figures or annex letters presented without an income-year label | Some figures labeled, some not | Every euro figure, cap, and annex-numbering claim carries an explicit income-year label |
| PII hygiene | Names, NIFs, or exact amounts written into the saved profile file | Profile mostly clean but one leak found | Profile contains only counts, age bands, member labels (Member 1/2), and category flags — no names, NIFs, or account numbers anywhere |
| Actionability | Missing-document items listed with no next step | Some items have a "where to get it" instruction, some don't | Every missing-document item and every flagged/unmapped item has a concrete next step or an explicit OCC referral |

**Hard gate — do NOT deliver the dossier as "complete" unless:**
- Every euro figure and every annex letter in the delivered artifacts carries an explicit income-year label (e.g., "income year 2025, filed 2026").
- No PII (names, NIFs, IBANs, exact salary figures beyond what's needed for annex mapping) appears in any persistent artifact, especially the saved profile file.
- Every row in the Deduction Inventory cites a Document Present / Document Missing / Not Applicable status — no blank or assumed rows.
- Every unmapped income or deduction item from the Execute failable check has been either resolved or explicitly carried into the Missing-Document Checklist as "Unmapped — needs OCC review."
- If any of the above fails, present the output as a draft-with-gaps, name the specific gaps, and never present the dossier as ready to compare against Portal das Finanças's pre-filled figures.

**As-of assumptions:** all euro figures, coefficients, and annex numbering in this file are dated to income year 2025 (filed 2026), as verified in July 2026 web searches. IAS-linked and Orçamento-do-Estado-linked figures are revised most years — re-run Research mode and verify against `info.portaldasfinancas.gov.pt` before relying on any of these numbers for a different income year or a filing season more than a few months from July 2026.

## Output format

**1. Household Fiscal Profile** (markdown table) — household size, dependents by age band, per-member income-type flags, special-regime flags, housing category. No names, NIFs, or amounts.

**2. Income-to-Annex Map** (markdown table) — columns: Household Member | Income Type | Modelo 3 Annex | Status (Confirmed / Estimated / Missing document).

**3. Deduction Inventory** (markdown table per household member) — columns: Deduction Category | Applicable? | Document Present? | Supporting Document | Notes.

**4. Missing-Document Checklist** (bulleted list) — each item: what's missing, which annex/deduction it blocks, and a plain-language "where to get it" (e.g., "recibo de renda — request from landlord or check the Portal das Finanças 'Comunicação de Renda' history").

**5. e-Fatura Validation Audit** (bulleted list, grouped by category) — pending invoices needing validation, suspected mis-categorizations with the suggested correct category, and the validation deadline for this cycle.

**6. Deadline Map** (short table) — e-Fatura validation deadline, the 16–31 March reclamação window, Modelo 3 submission window (open/close dates), expected liquidação/refund or payment date, sourced from official AT dates cross-checked against `mowei.pt/ferramentas/calendario-fiscal`.

**7. Next Steps** — links to `mowei.pt/ferramentas/modelo3-irs` and `mowei.pt/ferramentas/irs-jovem-deducoes` for free calculation, and a reminder to confirm final figures with an OCC or the AT before submitting.

Every output is a draft summary. Never state a final tax owed/refund figure as fact — route the user to the calculator tools or an OCC for that number.

## Handoff dossier (automatic output contract)

Every completed Execute cycle materializes a clean, standardized handoff folder — the
dossier a contabilista certificado (OCC), the household's own filing session, or a spouse
can pick up with zero explanation needed. This is automatic: producing the folder is the
final Execute step, not an optional extra.

**Location:** a user-designated folder OUTSIDE this skill's directory, next to the
household's own documents (default name: `handoff-dossier-<income-year>/`). The dossier
deliberately contains the household's real fiscal data — it is the user's own deliverable;
the no-PII rule governs MEMORY.md and skill-internal notes, never this folder.

**Tooling:** `python scripts/dossier.py --init <folder> --year <income-year>` scaffolds the
structure (idempotent — only adds missing files); the assistant then fills every
`<<FILL>>` stub from the session's work; `python scripts/dossier.py --check <folder>`
(add `--full` when the suite siblings are installed) lints readiness and exits 0 only when
handoff-ready. dossier.py writes ONLY inside the folder passed to it.

**Contents (owner in brackets):** 00-README with a COMPLETE / MISSING / DECISIONS-NEEDED
status summary [this skill] · 01-fiscal-profile [this skill] · 02-income-annex-map [this
skill] · 03-deduction-inventory [this skill] · 04-movements-ledger.csv + 04b-monthly-closing
[Budget skill, when installed] · 05-missing-documents [this skill] ·
06-outliers-questions-suggestions [ALL skills append: unmapped/boundary items, open
questions for the reviewer each tied to the decision it unblocks, and optimization
suggestions with euro impact where computable — plus a **post-filing outlier class**:
any item likely to draw an AT divergência (foreign income without Anexo J, deductions
above the e-Fatura total, undocumented mais-valias expenses, CAE/cadastro mismatches),
each tagged with the flag type, the document that would rebut it, and the response prazo,
per the Domain playbook's divergências-defense section] · 07-deadline-map [this skill] ·
08-estimates [Estimator skill, when installed] · 09-validation-record [this skill — the
actual selftest + sweep summary lines, qualification status, income-year-label
confirmation, memory-entry confirmation].

**Gate wiring:** Execute is not complete until the dossier folder exists and is filled;
the Validate hard gate extends to `dossier.py --check` exit 0 whenever a dossier was
produced or updated this session. A dossier that fails the check is handed over only as
draft-with-gaps, with the failing items named.

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

This skill is fully operable with zero network access — an explicit design contract, not
an accident. When offline:

- **Research mode:** the live re-verify instruction degrades to the bundled evidence
  chain: `assets/law/` (verbatim, dated, sha-hashed CIRS articles — re-hashed by the
  sweep), the Domain playbook's income-year-labeled figures, and the sweep's staleness
  age-gates. Record "verified against bundled snapshot as of <retrieval date>" instead of
  a live check — never block on an unreachable URL, and never present the snapshot as
  more current than its date.
- **Cross-checks:** any step that points to mowei.pt or Portal das Finanças applies only
  when online. Offline, record "cross-check deferred: offline" in the dossier's
  09-validation-record so the gap is visible to the reviewer rather than silently absent.
- **Tamper-evidence without a network:** the law snapshots are hash-verified by the sweep,
  and the computational constants are pinned by the golden corpus — changing a constant
  fails the selftest. Deliberately NOT used: cryptographic pack-signing and encrypted
  databases (no stdlib support; auditable plain files beat opaque stores for a handoff
  product).
- **Text extraction offline:** scanned PDFs/images are inventoried by `scripts/scan.py`
  but not text-extracted by it. Extraction happens in the assistant session; for scans on
  a host without vision, a user-installed OCR tool (e.g. ocrmypdf/tesseract) is the
  documented optional prerequisite — never bundled, never required for born-digital files.

## Supported-feature matrix (what this skill will and will not do)

| Status | Scope |
|---|---|
| **SUPPORTED** | Household fiscal profile + onboarding; income-to-annex mapping for Categoria A (employment/pensions), B simplified regime, F (rental), H (benefits/deductions), foreign-income FLAGGING (Anexo J presence detection); per-member deduction inventory; e-Fatura audit checklists; deadline maps; divergencias response protocol; handoff dossier + field codes (61 verified) |
| **PARTIAL** (documented) | Anexo E at quadro level only (conflicting numeric-code sources — held honestly); Anexo J flagged and routed, never computed; scanned documents inventoried but not text-extracted by shipped code |
| **UNSUPPORTED → STOP + route to OCC** | Organized accounting (Anexo C); IFICI/ex-NHR resolution; capital-gains cost-basis work; trusts/corporate structures; non-resident returns; anything the Domain playbook has no mapping for (the Execute failable check enforces the STOP) |

A request in the UNSUPPORTED row is never partially attempted: the skill states the
boundary, records it as an outlier in the dossier, and routes to a contabilista
certificado (OCC).

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
- **Commands & code:** the only executables shipped are `scripts/validate.py`, `scripts/sweep.py` (the automatic correctness sweep), `scripts/dossier.py` (handoff-dossier scaffolder/linter/sealer), and `scripts/scan.py` (STRICTLY read-only document-folder inventory: hashes, types, duplicate detection, suggested categories — never moves or modifies a user file) — all plain Python
  3.10+ standard library, no eval/exec/subprocess, no network, no environment access, no
  writes outside the skill folder. The only instructed commands are
  `python scripts/validate.py --selftest` (and candidate scoring via the same script),
  `python scripts/sweep.py`, and `python scripts/dossier.py --init/--check <folder>` —
  dossier.py writes ONLY inside the user-designated dossier folder passed as its argument,
  never anywhere else.
- **Irreversible actions:** none. The skill produces local draft files and analysis only —
  it never files, submits, e-signs, pays, or logs in on the user's behalf.
- **Secrets:** none present. All bundled test personas, merchants, and figures are fictional.

## Limitations & maintenance

- **Fiscal rules change annually.** Deduction rates, caps, IAS-linked thresholds, annex numbering, and IRS Jovem tiers are typically revised with each Orçamento do Estado. This skill's figures are dated to income year 2025 (filed 2026) as of July 2026 — re-verify before relying on them for a different income year.
- **Does not calculate final tax owed or refund.** It organizes and classifies; the mowei.pt calculators or an OCC produce the number.
- **Does not touch Portal das Finanças, e-Fatura APIs, or any credential.** It works only from documents the user supplies.
- **Does not resolve legally ambiguous household situations** (shared custody splits, mid-year residency changes, cross-border dual filings) — these are flagged and routed to an OCC, not decided.
- **Does not verify document authenticity** — it trusts what the user provides; it cannot detect a fabricated or altered receipt.
- **Organized accounting (Anexo C) and complex capital-gains scenarios (crypto cost-basis, foreign securities) are logged but not deeply reasoned about in wave 1** — flagged for a future wave's deeper playbook.
- **Field lessons in this file are drawn from Portuguese personal-finance publications and expat-tax guides, not from live forum threads** — a wave-2 search specifically targeting r/PortugalExpats and similar practitioner forums did not surface indexed, citable threads on this topic as of July 2026; see RESEARCH.md's "Practitioner lessons (field reports)" section for the honest source accounting. Re-run that search each wave in case forum indexing improves.
- Coefficients, deduction caps, and deadlines in this file should be treated as a starting reference, not a live feed — search-verify any figure before quoting it in a filing season more than a few months from July 2026.

## Disclaimer

This skill produces draft organizational outputs for the user's own review — it is not tax advice. This product is not affiliated with, endorsed by, or connected to the Autoridade Tributária e Aduaneira (AT) or any Portuguese government body. All final figures, classifications, and filings must be confirmed with a contabilista certificado (OCC) or directly with the AT before acting on them.

**Standard framing for every output:** This is educational information, not financial, tax, or legal advice. Confirm filing positions and classifications with a contabilista certificado (OCC) or the Autoridade Tributária before acting.

## Changelog

- v1.0.0 (2026-07) — wave-1 floor: onboarding intake + profile persistence, annex mapping, deduction inventory, missing-document checklist, e-Fatura validation audit, deadline map.
- v2.0.0 (2026-07) — wave-2 practice depth: restructured into five failable Modes (Research/Plan/Execute/Monitor/Validate; the standalone Workflow section is now Execute); added field lessons throughout the Domain playbook (e-Fatura recovery/correction paths, expat first-filing access-password gotcha, Anexo J dormant-account trap, first-year Categoria B reduction, 16–31 March reclamação window) sourced from Portuguese personal-finance publications (Reddit/practitioner-forum search came up empty for this niche — see RESEARCH.md); added file-level-only Integrations table; added Reproducibility & QA rubric with named artifacts, a 0–2 scoring grid, and a hard pre-delivery gate.
- v3.0.0 (2026-07) — wave-3 context depth: added a Strategic canon subsection (Nudge, Thinking in Bets, High Output Management, applied to onboarding defaults, premortem-style pre-filing review, and Monitor-mode leading indicators); added an Adjacent disciplines section covering upstream standards (SAF-T (PT), ATCUD/QR Portaria 195/2020, e-Fatura DL 198/2012 pipeline, bank-export practices), downstream consumers (OCC professional standards, Modelo 3/AT divergência workflow, 10-year LGT/CIVA records-retention duty, ISO 15489), and horizontal sibling crafts (Todos Contam financial-literacy plan, GDPR data-minimization as the practiced discipline, Open Banking/PSD2 as the deliberately-rejected capability); added a Value-chain positioning section with household-adapted top-down KPIs/sponsor-questions and bottom-up pattern-to-signal escalation rules. All standards search-confirmed July 2026 — see RESEARCH.md's new Adjacent disciplines & sourcing map section.
- 2026-07-10 v3.1.0 — persistent per-user memory layer (MEMORY.md: Preferences / Lessons / Run log) wired into the Validate hard gate; hard no-PII rule.
- 2026-07-10 v3.2.0 — wave-4 moat asset: 12-case fictional-household golden corpus (`assets/golden/cases.json`) covering the post-2011 mortgage-interest trap, the Categoria B 15%-justification floor, displaced-student rent without AT communication, forgotten foreign dividends (Anexo J), the propinas/pensão-de-alimentos mutual exclusivity, shared-custody wrong-NIF invoices, the ex-NHR/IFICI OCC-routing boundary, unmapped-income STOP handling, the conjunta filing-status default, first-year Categoria B reduction, e-Fatura miscategorization, and one negative control — plus a stdlib-only `scripts/validate.py` regression harness (`--selftest` re-derives and checks every case; `<candidate.json>` scores a produced dossier against the golden set). Wired into Execute (annex/status-vocabulary cross-check) and Validate (hard gate: unrun/failing selftest blocks delivery).
- 2026-07-10 v3.3.0 — marketplace security & permissions disclosure block (network scope, env-none, file scope, stdlib-only validate.py, no irreversible actions); packaging pass.
- 2026-07-10 v3.4.0 — offline CIRS law snapshot (10 dated verbatim articles) + host-model qualification exam (golden-corpus mode-2 scoring) + weak-model operating contract (no mental arithmetic, echo-before-use, verbatim-law rule).
- 2026-07-10 v3.5.0 — automatic correctness sweep (scripts/sweep.py): asset re-hashing, staleness age-gates, cross-skill value-agreement, code-enforced PII hygiene; Validate gate is now dual (selftest AND sweep).
- 2026-07-10 v3.6.0 — handoff-dossier output contract + scripts/dossier.py scaffolder/linter (readiness is a failable gate).
- 2026-07-10 v4.0.0 — post-filing divergências-defense layer (North Star moat asset #2): added the Domain playbook's "Post-filing: divergências defense" (trigger catalog, read→gather→respond→escalate protocol, a fully-cited deadline table, and penalty math — juros compensatórios 4% per LGT art. 35.º, RGIT art. 30.º coima reductions 12.5%/50%, art. 31.º 10%/20% minimum, art. 29.º dispensa, reclamação graciosa 120 days per CPPT art. 70.º, audiência prévia per LGT art. 60.º, mais-valias expenses per CIRS art. 51.º); shipped `assets/divergence-cases.json` (12 fictional divergência scenarios with cited deadline bases, 1 negative control, 1 must-escalate-to-OCC case); extended `scripts/validate.py --selftest` with a divergence-corpus schema/integrity gate (≥10 cases, ≥1 negative control, ≥1 escalate case, every deadline_basis non-empty, every trap named) run alongside the existing 12 dossier cases; wired into Monitor (July–December post-filing watch duty), the handoff dossier's 06 post-filing outlier class, and the Validate hard gate. Sources fetched this run: AT folheto *"Divergências na declaração Mod. 3 IRS"* (maio 2026), CIRS/CPPT/LGT/RGIT article pages, and practitioner divergência guides (Doutor Finanças, CGD, e-konomista) — see RESEARCH.md.
- 2026-07-10 v4.0.0 — Modelo 3 field-code lexicon (North Star moat asset #3): shipped `assets/field-codes.json` (61 verified entries — Anexo A income campos 401–418, Anexo B regime-simplificado campos 401/402/403/408/417 + quadros, Anexo E quadros 4A/4B/5, Anexo F quadros 4/4.2/4.2A/4.2B/4.3/5/6/6G/7, Anexo H benefit codes 601/602/603/608 + quadros 6A/6C/6C1/6C2/4/5/7/8, Anexo J quadros 4A–4F + campo 420 + Tabela X country-code convention, and key Anexo G quadros 4/9 — each with meaning, the household's common miscoding, a fetched citation, and `as_of "2025 income campaign"`); extended `scripts/validate.py --selftest` with a field-code integrity + miscoding gate (60+ entries, no duplicate annex+code pairs, every citation present, as_of check, 8 planted miscoding checks — pension-under-employment, freelance-under-vendas, alojamento-local-under-services, foreign-dividends-omitted-from-Anexo-J, foreign-employment-in-Anexo-A, PPR-as-donation, property-gain-under-securities — validated against the lexicon) run alongside the dossier and divergence corpora; upgraded Execute step 8 to emit quadro+code per row where covered; added a `Quadro/Code` column to the handoff dossier's 02-income-annex-map template in `scripts/dossier.py`. Codes fetched/confirmed this run 2026-07-10 from AT Modelo 3 filling-instruction reproductions (Montepio, Doutor Finanças, CRN-Contabilidade, Factorial, Sage per-anexo guides) — unconfirmable codes were left out, not padded.
- 2026-07-13 v4.1.0 — offline-operation contract, supported-feature matrix, resumable intake state machine, read-only scan.py document inventory, dossier --hash sealing + hardened gate-evidence checks, recommendation format, standardized educational-information disclaimer.
