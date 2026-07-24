---
name: portugal-irs-deductions
description: Use when a Portugal tax resident wants to find, capture, allocate, or defend every deducao a coleta (tax credit) they are entitled to under CIRS art. 78 before the e-Fatura validation deadline or the IRS filing window - for individuals and households running their own IRS locally, not accountants filing on behalf of clients. Does not calculate Modelo 3 income tax itself, does not touch Portal das Financas credentials, and does not give legal or tax advice on disputed AT rulings. Ships with a fully cited machine-readable CIRS art. 78 deduction matrix (22+ rows, per-row as-of dates, honest UNKNOWN cells) plus a planted-case expense scanner and selftest harness, and a 25-entry AT binding-ruling (informacao vinculativa / ficha doutrinaria) index cross-linked to the matrix rows.
version: 4.1.0
---

# Portugal IRS Deductions Maximizer

## What this skill does

This skill turns the CIRS art. 78 deduction categories into an operational, year-round capture system: it tells the assistant what to check, when, and against which caps, so that expenses that would otherwise be lost by the February e-Fatura validation deadline get caught in time. It works from the user's own exported e-Fatura CSV/PDF, invoice photos, or manually pasted category totals - never from a live Portal das Financas session. It flags boundary cases (wrong NIF, wrong category, missing manual registration) rather than just listing the categories everyone already lists. It does not replace a contabilista certificado (OCC) and does not compute the underlying Modelo 3 tax liability - see the companion Modelo 3 / net-salary tools for that.

## The moat asset

This skill ships a machine-readable, individually cited operationalization of the Domain playbook that a generic assistant cannot reconstruct from a category list:

- **`assets/deduction-matrix.json`** - the 9+ CIRS art. 78 categories expanded into 27 rows, one per distinct rate/cap/uplift/income-year combination (e.g. education splits into base / displaced-student uplift / displaced-student rent / interior majoracao; the IVA-por-exigencia-de-fatura sectors each get their own row). Every row carries: legal basis, rate, cap with unit and per-household-vs-per-member scope, income-year label (2025-filed-2026 rows kept separate from confirmed OE2026 income-year-2026 rows), e-Fatura category mapping, boundary conditions, a manual-registration flag, an `as_of` date, and a citation. **Every factual cell is either backed by a source URL or set to the literal string `UNKNOWN`** - an honest UNKNOWN (currently on the interior-majoracao rate/cap and the public-transport-pass rate) outranks a guessed value.
- **`assets/planted-cases.json`** - nine golden expense-set cases, including a clean negative control, that pin the scanner's behaviour.
- **`scripts/validate.py`** - stdlib-only harness. It reads its fiscal numbers *from the matrix* rather than hard-coding them, so the matrix stays the single source of truth.
- **`assets/doutrina-index.json`** (v4.0.0) - 25 curated AT binding rulings (informacoes vinculativas / fichas doutrinarias) cross-linked to the specific matrix rows they clarify (see "### Doutrina layer" below).

**Why it is hard to reproduce (not impossible):** the value is not the category list - every Portuguese finance site publishes that. It is the per-row income-year separation, the per-cell citation-or-UNKNOWN discipline, and the executable scanner that catches the specific miscategorization/allocation traps from the field lessons. Re-deriving that from scratch, with honest sourcing, is the work.

**How each mode uses it:** Execute reads the matrix to place every expense in a specific row with a stated cap and to run the scanner's trap checks; Validate runs `scripts/validate.py --selftest` as a hard gate before any deliverable is released.

**Hard-gate wiring:** a run may not deliver its Output-format deliverables unless `python scripts/validate.py --selftest` has been run and exited 0 - a failing or unrun selftest blocks delivery.

### Doutrina layer

`assets/doutrina-index.json` is a curated index of **25 real AT binding rulings** - informacoes vinculativas / fichas doutrinarias (plus one ofício-circulado) - each pinned to the exact `deduction-matrix.json` row(s) it clarifies. Where the category list every finance site publishes tells the assistant *what* the caps are, the doutrina layer tells it *how the Autoridade Tributaria has actually resolved the boundary cases* that decide whether money is captured or lost:

- Each entry carries the **processo/identifier as published** (or the literal `UNKNOWN` when the source copy did not print it), the date, the legal basis, a faithful 1-2 sentence holding, the matrix row ids it touches, a `source_url` that was actually read, and a `confidence` flag - `primary` (the AT ficha text itself was read: portaldasfinancas.gov.pt or a verbatim mirror) or `secondary` (a press/OCC/law-firm summary). 23 of 25 are primary.
- Coverage spans the household-money boundaries: estudante deslocado (residencia universitaria, Pousada de Juventude, landlord invoice-marking, foreign/Erasmus), pensao de alimentos (adult child, retroactive payments, propinas summed in), health-service eligibility (electric stairlift CAE rule, reabilitacao psicomotora / pilates clinico / terapeuticas nao convencionais IVA-exemption gating art.78-C), explicacoes and extracurricular IVA-exemption gating art.78-D, shared-custody 15-Feb harmonisation, veterinary rate, PPR early-resgate reversal, donativos recibo elements, and the art.87 deficiencia-status gate.
- **Why hard to reproduce:** these holdings are scattered across individual PDF fichas on the AT portal (and mirror hosts); assembling them, reading each, and pinning each faithfully to the right cap row - with honest primary/secondary provenance and honest `UNKNOWN`s - is the work.
- **How the gate uses it:** `scripts/validate.py --selftest` now includes a **Doutrina layer** integrity section - every index entry must be schema-complete with a real `source_url`, every `matrix_row_ids` must resolve to a real matrix row, and every matrix-row `doutrina` ref must resolve back to an index entry (bars: >=25 entries, 100% with source_url, >=10 rows annotated - currently 15 rows annotated).

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

**Zero-setup path:** no API keys, no logins, no Portal das Financas credentials ever. This skill never asks for an AT password, an autenticacao.gov session, or any OAuth token - that is a structural, non-negotiable boundary, not a feature that's merely unused.

Works from whatever the user already has:
- An e-Fatura "Consultar Faturas" export (CSV or the on-screen category totals, copied/pasted or screenshotted)
- Photos or PDFs of invoices/receipts the user is unsure were captured correctly
- A plain description of a household situation (dependents, rental, PPR contributions, mortgage-pre-2011 status, divorced/shared custody)
- Prior-year IRS notes (categories used, any AT rejections) if the user has them

If the user has no export yet, the first workflow step is guiding them to pull one from Portal das Financas > Fatura > Consultar Faturas manually in their own browser - the skill reads what they paste back, it never automates the portal itself.

## Modes

This skill runs in five modes. Pick the mode that matches what the user is asking for; a single conversation often moves through several in sequence (Research → Plan → Execute), while Monitor and Validate are typically re-entered on their own on a later date.

### Research

- **Purpose:** establish the household's fiscal profile and pull together whatever raw data the user has (e-Fatura export, receipt photos, prior-year notes) before any category analysis starts.
- **Inputs:** household composition, dependents, displaced-student status, home-ownership status, PPR holder ages, court-ordered pensao de alimentos, nursing-home/apoio domiciliario dependents, approximate taxable income bracket (bracket only - see PII rule), whatever export/photo/paste the user has, and the current date (to place the run inside the fiscal calendar).
- **Outputs:** a stated fiscal profile summary and a stated income year in scope ("this pass covers income year 2025, filed April-June 2026").
- **Failable check:** if the user cannot state which income year they mean, or gives a mix of current-year and prior-year figures without labeling them, STOP and ask for clarification before moving to Plan - mixing income years silently is the single most common error a generic assistant makes in this domain.

### Plan

- **Purpose:** decide which of the 11 Domain playbook categories actually apply to this household, in what order, and what data is still missing before Execute can run.
- **Inputs:** the Research-mode fiscal profile, the category checklist (Domain playbook section 1-9), the global-cap section (section 11).
- **Outputs:** a short applicability list (which categories are in scope, which are explicitly Not applicable and why) and a note of what data is still needed (e.g. "no e-Fatura export yet for health category - ask the user to pull Consultar Faturas").
- **Failable check:** if the household's estimated rendimento coletavel is already comfortably above the global cap ceiling (section 11) with no dependents pushing it back up, STOP category-by-category planning and say so explicitly - do not spend the Execute pass chasing marginal receipts that will be capped out regardless of category-level optimization.

### Execute

- **Purpose:** run the actual category-by-category capture pass against the user's data. This is the v1 Workflow, unchanged in substance, now framed as the Execute mode.
- **Inputs:** everything gathered in Research and scoped in Plan.
- **Outputs:** the two Output format deliverables (category capture table + dated action checklist).
- **Steps:**
  1. Load `assets/deduction-matrix.json` (the moat asset) and use it as the source of truth for every rate, cap, scope, income-year label, and e-Fatura mapping in this pass - place each of the user's expenses in a specific matrix row rather than quoting a remembered figure, and honour any `UNKNOWN` cell by flagging "verify against current AT guidance" instead of guessing.
  1a. **Surface the doutrina.** Whenever the matrix row you placed an expense in carries a `doutrina` list, open `assets/doutrina-index.json` and surface the applicable AT ruling(s) to the user in plain terms - e.g. *"the AT has ruled (proc. 26060) that a university-residence 'contrato de alojamento' still counts as a displaced-student education expense"*, or *"the AT has ruled (proc. 28223) that an electric stairlift is NOT a deductible health expense because the seller's CAE is not a health sector"*. Quote the `ruling_ref` and holding faithfully, attribute honestly (`primary` = AT ficha read vs `secondary` = press/OCC summary), link the `source_url`, and **never invent a processo number** - if a boundary is not covered by an index entry, say so rather than fabricating a ruling.
  2. Walk the category checklist (see Domain playbook) against whatever data the user supplied. For each category: is it present in the data, is it in the right e-Fatura category, is it under/over its cap, does it need manual Anexo H entry.
  3. Flag boundary cases - wrong-category invoices (e.g., a vet bill logged as "general family expenses" instead of health/pets), missing NIF on a receipt, foreign invoices that never reach e-Fatura automatically, rent without an electronic receipt.
  4. Run the household allocation pass - which family member's NIF should be on which expense to maximize the combined household deduction, and whether a dependent's own invoices should route to one parent under a shared-custody split (see Domain playbook section 10).
  5. Produce the Output format deliverable - a per-category capture table plus a dated action checklist.
  6. Time-gate reminders: if run before ~28 Feb, emphasize e-Fatura validation and manual registration of anything missing; if run 16-31 March, emphasize the AT reclamacao window (and its narrow scope - see Domain playbook §12); if run in the April-June filing window, emphasize final Anexo H cross-check against the AT's pre-filled Modelo 3.
  7. Point to the relevant mowei.pt calculators (see Integrations) instead of re-deriving numbers the tools already compute reliably.
- **Failable check:** if any identified expense cannot be placed in a specific CIRS art. 78 category with a stated cap, or is a category this skill explicitly does not cover (Categoria B self-employment, Categoria F rental income as landlord, capital gains), STOP for that item and route it to a contabilista certificado rather than guessing a category to force it into the table.

### Monitor

- **Purpose:** the recurring, seasonal watch duties that keep the household from losing deductions between Execute passes - this is not a one-time analysis, it is a calendar the assistant should keep surfacing across a fiscal year.
- **Inputs:** the current date, the prior Execute-mode capture table (if one exists), any legislative changes flagged since the last run (OE budget law, mid-year AT guidance updates).
- **Outputs:** a dated reminder of which watch duty applies now.
- **Watch duties:**
  - **Mid-year (summer/autumn):** a lightweight "did you give your NIF enough" hygiene check - no formal Anexo H action yet, just habit reinforcement.
  - **Jan-Feb, before ~28 Feb / effective 2 March deadline:** the highest-value pass - e-Fatura validation and manual registration window. [field lesson] The e-Fatura portal itself has a documented history of instability during this exact window - accountants (via the Ordem dos Contabilistas Certificados) have publicly requested deadline extensions after portal outages in prior seasons; if the user reports the portal being unreachable close to the deadline, tell them this is a known recurring pattern, not something wrong on their end, and that a declaracao de substituicao remains available after the deadline as a fallback (see Execute mode boundary case below). (justicatv.com, "IRS: termina prazo para validar faturas, mas contabilistas pedem mais tempo apos problemas no acesso ao portal")
  - **16-31 March:** the reclamacao window opens - but see the Validate-mode failable check below for its narrow scope.
  - **Whenever the OE budget law changes mid-cycle or a new tax year opens:** re-verify every rate, cap, and threshold in the Domain playbook before reusing this file for a new income year - see Limitations & maintenance.
- **Failable check:** if the assistant is about to tell a user "you can still fix this" for a category-a-coleta issue (health, education, housing, lares) discovered after 31 March, STOP and correct course - only despesas gerais familiares and IVA-por-exigencia-de-fatura remain reclamavel via the portal after the 16-31 March window; everything else at that point routes to a declaracao de substituicao, not a reclamacao graciosa (see Domain playbook §12).

### Validate

- **Purpose:** the pre-delivery gate - run before handing the Output format deliverables to the user, on every Execute-mode run.
- **Inputs:** the draft category capture table and action checklist.
- **Outputs:** either a pass (deliverables released as-is) or a blocked deliverable with the specific gap named.
- **Failable check (do NOT deliver unless all of the following hold):**
  - The moat-asset selftest has been run and passed: `python scripts/validate.py --selftest` exits 0. A failing or unrun selftest = do not deliver - it means the matrix, the scanner, or the doutrina index the Execute pass relied on is not in a known-good state. (The selftest's **Doutrina layer** section fails delivery if any ruling entry is incomplete, any `source_url` is missing, or any `matrix_row_ids`/`doutrina` cross-reference dangles.)
  - Any AT ruling surfaced to the user in Execute step 1a was quoted from a real `doutrina-index.json` entry with its `ruling_ref` and `source_url`, and attributed by `confidence` - no processo number was invented and no boundary was asserted as "AT-ruled" without an index entry to back it.
  - Every euro figure in the table carries an explicit income-year label (see Reproducibility & QA rubric).
  - No PII (NIF, full name, exact euro amounts tied to a specific invoice, account numbers) appears in any artifact that will be saved to a persistent note - category labels and rounded/bucketed amounts or counts only.
  - Every deduction row states document-present or document-missing status - a row cannot be marked "Captured" without a stated basis for that status.
  - If a reclamacao-window action item is included, it is scoped to the categories the reclamacao process actually covers (despesas gerais familiares, IVA-por-exigencia-de-fatura only) - see the Monitor-mode field lesson above.
  - If a displaced-student rent item is included, the checklist explicitly separates the landlord's AT-side contract communication step from the student's own registration step - see Domain playbook §3 field lesson; conflating the two is the most common reason this deduction silently fails.

## Domain playbook

All figures below are for **income year 2025** (expenses incurred Jan-Dec 2025, filed April-June 2026, e-Fatura validation deadline late Feb / 2 March 2026) unless marked "income year 2026" for the OE2026 (Lei n.o 73-A/2025) changes that apply to the *next* filing season (income earned 2026, filed 2027). Never apply an income-year-2026 figure to an income-year-2025 return, or vice versa - always state which year a number belongs to.

### 1. Despesas gerais familiares (general family expenses) - CIRS art. 78-B
- Rate: 35% of eligible spend; 45% for single-parent (familia monoparental) households.
- Cap: EUR 250 per taxpayer (EUR 335 for single-parent).
- What counts: everyday household consumption invoices where no other category applies (supermarkets, general retail) as long as an NIF was given at purchase.
- Common rejection: an invoice that actually belongs to a more specific category (health, education) sitting in "general expenses" - AT auto-classifies most of this from e-Fatura sector codes, but manually-entered receipts can land in the wrong bucket.
- e-Fatura mechanics: almost entirely automatic if the NIF was given; nothing to register manually in normal cases.
- **[field lesson]** Vet/pet-related invoices are a recurring miscategorization trap: general-market guidance explicitly warns readers to check that "despesas veterinarias dedutiveis" have not been "erradamente" englobadas into "Despesas Gerais e Familiares" - the pet-vet sub-rule under category 2 (health) has its own 250 EUR sub-cap and a 35% rate for prescribed medication, and it is silently absorbed into the general-expenses bucket if the sector code doesn't route it correctly. Treat any pet-related line item in the general-expenses total as a category-2 candidate to re-check, not a settled classification. (acp.pt "Deduzir despesas de veterinario no IRS"; doutorfinancas.pt "IRS e os animais")

### 2. Saude (health) - CIRS art. 78-C
- Rate: 15% of eligible spend per household.
- Cap: EUR 1,000 (household-level, not per member, unless the household has more members driving a higher combined spend within that single cap - confirm against the current AT guidance page, this is a frequent point of confusion).
- What counts: consultations, exams, medication, health insurance premiums (the health-insurance premium share, not the whole policy if it bundles other cover), dental, optical, and pet-vet expenses under a related sub-rule.
- 23% IVA health items (most medical devices/services) need a doctor's prescription (receita medica) associated with the invoice in e-Fatura, or they won't auto-qualify - a common source of "missing" health deductions in Feb validation.
- e-Fatura mechanics: mostly automatic via the "Saude" sector; prescription linkage step is manual and is the boundary case to check first.
- **[field lesson]** The failure mode here is not "the deduction disappears" - it is worse: an unassociated prescription-required invoice does not stay parked as an unclassified health expense, it gets folded into "Despesas Gerais e Familiares" once the window closes (multiple sources describe the mechanism as "no dia 16 de fevereiro, todas as despesas pendentes passam para a categoria de Despesas Gerais Familiares"). That silently converts a 15%/1,000 EUR-cap health deduction into a 35%/250 EUR-cap general expense - a real-money downgrade the user will not notice unless the capture table flags it explicitly. Always check the health total against what the user expected before the 16 Feb-ish internal AT cutoff, not just the final 2 March deadline. (montepio.org "Despesas de saude: Como associar uma receita medica no e-fatura?"; e-konomista.pt "E-fatura: como associar a receita a fatura de saude")

### 3. Educacao e formacao (education) - CIRS art. 78-D
- Rate: 30% of eligible spend.
- Cap: EUR 800 per household (agregado familiar — not per member); increased by EUR 300 (to EUR 1,100) when the excess over EUR 800 corresponds to a displaced student's housing.
- What counts: tuition, creche/pre-school, school manuals, transport tied to schooling, private tutoring (explicacoes), university propinas.
- **Displaced student (estudante deslocado) rent:** deductible at 30% up to EUR 400/year on top of the education cap, if the student is under 26, enrolled at a recognized institution more than 50km from the household's permanent residence, and the household (a) has a rental/sub-rental contract that states the displaced-student purpose, (b) has an electronic rent receipt or invoice-receipt, and (c) has communicated the displaced-student condition to the AT. Missing step (c) is the most common reason this deduction silently fails to appear pre-filled.
- **[field lesson]** Step (c) is a two-sided sequence, and practitioner guidance is explicit that the sequence order is the trap: the **landlord** must first communicate the rental contract or sub-lease to the AT and issue electronic rent receipts - only once that landlord-side contract exists in the Portal das Financas does the **student** have anything to register against as "displaced." A household that only tries to register displaced-student status on the student's own side, without confirming the landlord actually filed the contract first, will find the registration has nothing to attach to. Ask which side has filed first before assuming the deduction will populate; if the landlord genuinely refuses or is not obligated to issue electronic receipts, the fallback is manual insertion in the IRS declaration with contract/receipt proof kept on hand for a possible AT follow-up call to both parties. (doutorfinancas.pt "Arrendamento a estudante deslocado: IRS e aspetos praticos"; montepio.org "Estudante deslocado: como deduzir as rendas no IRS")
- **Interior/Autonomous Regions majoracao (separate rule, often confused with the displaced-student uplift):** education expenses at establishments located in interior territories or the Regioes Autonomas get a +10 p.p. majoracao (i.e. 40% instead of 30%) with a global limit of EUR 1,000 - distinct from the EUR 1,100 displaced-student ceiling. [Income year 2025 - verify current rule before relying on it.]
- Boundary case: propinas that a court has separately characterized as pensao de alimentos should generally route to category 6 (pensoes de alimentos), not education - check which basis applies before double-claiming. [field lesson] This is not a hypothetical edge case - a 2026 ECO report ("Fisco permite deduzir propinas como pensao de alimentos no IRS") confirms the AT has explicitly ruled on this exact reclassification question, meaning it is an active, currently-relevant boundary, not a theoretical one; flag it whenever a household's education total includes propinas tied to a court-ordered support arrangement.

### 4. Encargos com imoveis / habitacao (housing) - CIRS art. 78-E + transitional regime
- **Rent (permanent residence, arrendamento):** 15% of rent paid, cap EUR 700 for income year 2025. (OE2026 raises this cap to EUR 900 for income year 2026, filed 2027, and a further step to EUR 1,000 is planned for income year 2027 - do not apply either raised figure to a 2025-income return.)
- **Mortgage interest (juros de credito habitacao):** only for loan contracts signed on or before 31 December 2011. Rate 15%, base cap EUR 296/year; increased on a sliding scale up to EUR 450/year for lower rendimento coletavel bands. A mortgage that was refinanced/transferred to a different bank after 2011 loses eligibility even if the original 2011-or-earlier contract still exists in spirit - AT treats a bank transfer as a new contract. Confirm this with the user before assuming eligibility.
- Reported in Anexo H, secção 7.
- e-Fatura mechanics: rent almost never auto-populates - landlords who are not VAT-registered issue paper/manual receipts, so this is one of the highest-value manual-registration checks to run before the deadline.

### 5. Lares e apoio domiciliario (nursing homes / home care) - CIRS art. 84
- Rate: 25%.
- Cap: EUR 403.75/year.
- What counts: fees paid to certified nursing homes, assisted-living residences, day centres, and certified home-care services for the taxpayer, ascendants, or dependents with disability, where the beneficiary's own monthly income is below roughly EUR 920 (the IAS-linked threshold - re-verify the exact multiple each year, it moves with the IAS).
- Boundary case: uncertified/informal home-care arrangements do not qualify - the provider must be an AT/Seguranca Social certified entity.

### 6. Pensoes de alimentos (court-ordered alimony/child support) - CIRS art. 83-A / 78
- Rate: 20% of amounts paid and not reimbursed, set by court sentence or a homologated agreement.
- Cap: none on the deduction itself, but it still counts toward the household's overall global cap (section 11 below).
- Boundary case: a taxpayer who also claims a dependent's education/health expenses for the same child generally cannot simultaneously claim the pensao de alimentos deduction for that child in the same year - the two are mutually exclusive per dependent. Flag this explicitly whenever a shared-custody household is claiming both.

### 7. IVA por exigencia de fatura (invoice-IVA benefit) - CIRS art. 78-F
- Cap: EUR 250/household, shared across all sectors below (not per-sector).
- Sectors and rates (income year 2025):
  - Restaurants, cafes, hotels/alojamento local: 15% of IVA
  - Hairdressers, barbershops, beauty institutes: 15%
  - Vehicle and motorcycle repair (revisions, tyres, mechanics): 15%
  - Veterinary services (consultations, surgery, prescribed medication): 15%
  - Gyms and sports classes (ginasios, mensalidades): 30%
  - Passes de transportes publicos (public transport passes): typically included at a favourable rate - confirm current rate on the AT page each season, this is one of the categories that has moved rates between years
  - New for income year 2025/2026 filings: cultural spend (museums, monuments, concerts, theatre, books) at 15% - this is a recent addition; confirm it is live for the exact income year in scope before promising it to the user.
- Mechanics: purely NIF-driven - if the NIF was given at the point of sale, e-Fatura auto-assigns the sector; nothing to register manually in the normal case. The most common loss here is simply forgetting to give the NIF at low-friction purchases (coffee, haircut).

### 8. PPR (Planos Poupanca Reforma) contributions - CIRS art. 21 / EBF
- Rate: 20% of amounts invested in the year.
- Age-banded caps (age on 1 January of the contribution year):
  - Under 35: cap EUR 400 (implies up to EUR 2,000 contributed)
  - 35-50: cap EUR 350 (implies up to EUR 1,750 contributed)
  - Over 50: cap EUR 300 (implies up to EUR 1,500 contributed)
- Boundary case: contributions made after the taxpayer has already retired/started drawing the PPR are not deductible. Each household member with their own PPR claims their own age-banded cap independently.
- Use `ppr-beneficio-fiscal` (see Integrations) to size the exact contribution that maxes the cap without overshooting it.

### 9. Donativos (donations) and consignacao (IRS assignment) - two separate mechanisms, do not conflate
- **Donativos deduction:** 25% of the donation value, generally capped at 15% of the tax due (coleta); donations to the State, foundations, and religious institutions can be deductible at 25% without that 15%-of-coleta ceiling - confirm the specific recipient's status before assuming the uncapped rate applies.
- **Consignacao (IRS assignment):** a separate mechanism - the taxpayer assigns a percentage of their *already-computed* tax (not an extra out-of-pocket donation) to an eligible IPSS, religious, cultural, or public-utility entity, chosen from the AT's annually published list (searchable by name or NIF). This costs the taxpayer nothing beyond a checkbox in the return and does not reduce other deduction caps - always mention it as a zero-cost add-on distinct from the donativos category above.

### 10. Household allocation strategy
- Deductions generally follow whichever household member's NIF is on the invoice - for maximum-cap categories (health, education) where one spouse is close to a personal or per-member cap, routing new invoices to the other spouse's NIF (or the dependent's own document, where the vendor supports it) can capture more of the combined household ceiling. This is arithmetic optimization, not tax avoidance - flag it as a legitimate allocation choice, not a loophole.
- Dependents' own invoices (e.g., a working student's own health receipt) should generally carry a parent's NIF if the parent wants to claim it - confirm the vendor captured the parent's NIF, not the dependent's, if the dependent has no separate NIF of their own or files jointly under the household.
- **Divorced / shared-custody households:** when custody is split (residencia alternada), each parent typically claims 50% of the dependent's deduction-relevant expenses unless a different split is registered with the AT for that dependent. Confirm which parent has the dependent registered for the tax year before allocating any category - this determines eligibility for the per-dependent caps in categories 3, 5, and 6, and mismatched registration is a common source of AT rejection for both parents simultaneously.

### 11. Global deduction cap (limite global das deducoes a coleta) - CIRS art. 78 n.o 7
- Income year 2025 (this filing season): no overall cap for rendimento coletavel (RC) up to roughly EUR 8,059; a sliding-scale cap between that floor and roughly EUR 83,696; a floor cap of EUR 1,000 above that. Verify the exact interpolation formula and thresholds for the specific return year via the official AT guidance or the `calendario-fiscal` / official simulator before quoting a precise euro figure to the user - these anchors are confirmed, the exact multiplier in the interpolation is not something to compute from memory.
- Income year 2026 (OE2026, Lei n.o 73-A/2025 - next filing season, filed 2027): no cap below RC EUR 8,342; between EUR 8,342 and EUR 80,000 the cap follows `1,000 + 1,500 x (80,000 - RC) / (80,000 - 8,342)`; above EUR 80,000 the cap is EUR 1,000 flat.
- Both years: art. 78 n.o 8 majora o limite em 5% POR DEPENDENTE, em agregados com TRES OU MAIS dependentes. Read it carefully - the 5% multiplies by every dependent, not only those past the second: a household with 3 dependents gets limit x 1.15, not x 1.05. [Corrected 2026-07-24: this line previously read '5% for each dependent beyond the second', which understates the cap for every large family.]
- Practical use: once a household is near this global cap, further category-by-category optimization stops mattering - check this early so time isn't spent chasing marginal receipts that will be capped out anyway.

### 12. Reclamacao window scope (16-31 March) - [field lesson]
- **[field lesson]** Practitioner-facing guidance is explicit that the graciosa reclamacao process available in the 16-31 March window covers only two of the eleven categories above: despesas gerais familiares (category 1) and IVA-por-exigencia-de-fatura (category 7). Health, education, housing, and lares (categories 2-5) are **not** reclamavel through that portal flow in that window - a household that discovers a housing or health-cap shortfall in late March must instead correct it via a declaracao de substituicao during the April-June filing window, not a reclamacao. Get this distinction into every dated action checklist that references the March window, or the user will be pointed at the wrong AT mechanism. (idealista.pt "Erros nas faturas? Fica a saber como reclamar as despesas no IRS"; e-konomista.pt "IRS 2026: prazo para reclamar das deducoes esta a terminar")
- **[field lesson]** Missing the whole validation window is recoverable, not fatal: if the user only realizes after 2 March that invoices were never validated or a category is materially short, the standing fallback across every source consulted is "Entregar Declaracao de Substituicao" in the April-June filing window - correct Anexo H directly and resubmit, rather than treating the missed deadline as a closed door. This should be the default reassurance the Monitor-mode Jan-Feb watch duty gives a user who reports missing the cutoff, paired with the caveat that health/education/housing corrections at that stage need document proof on hand in case AT follow-up asks for it. (doutorfinancas.pt "Esqueci-me de validar as faturas no e-fatura. O que posso fazer?"; alfaseguros.pt "Nao Validou Faturas? Ainda Pode Recuperar Deducoes no IRS!")

### Strategic canon

Adjacent operator wisdom - not tax law, but the operating patterns this skill borrows from outside the fiscal domain.

- **Atomic Habits (James Clear).** Thesis: you don't rise to your goals, you fall to your systems - tiny 1% changes compound, and the real leverage is identity ("become the kind of person who...") rather than willpower. The Four Laws: make it obvious, make it attractive, make it easy, make it satisfying; "never miss twice" once a habit lapses. Applied here: giving the NIF at checkout is a habit-stacked, identity-based habit ("the kind of household that never loses a deduction"), not a one-off effort - the Monitor-mode mid-year hygiene check exists to make the habit obvious, and the monthly pending-invoice triage exists so a missed month never becomes two.
- **Nudge (Richard Thaler & Cass Sunstein).** Thesis: people are predictably biased ("Humans, not Econs"), so the choice architecture - especially the default - quietly determines outcomes; design the environment so the good choice is the easy one, without removing freedom. Applied here: e-Fatura's auto-classification is a default, and defaults do the work whether or not they are correct - this skill treats that default as something the household must audit (the vet-invoice and health-receipt field lessons in the Domain playbook are exactly this default silently mis-sorting spend), not something to trust blindly.
- **The Goal (Eliyahu Goldratt).** Thesis: every system is limited by a small number of constraints, and improving anything other than the constraint is an illusion of progress - identify the bottleneck, exploit it, subordinate everything else to it. Applied here: Plan mode's job is constraint-finding - find the single category where the household is leaking the most (health receipts falling into general expenses, an unregistered displaced-student rent, a missed reclamacao window) and subordinate the Execute-mode effort to closing that one leak first; polishing categories that are already at cap or trivial in size is the "improving a non-bottleneck" trap this framework warns against.

## Adjacent disciplines (vertical & horizontal)

### Upstream (where the inputs come from)

- **SAF-T (PT)** - the AT's Standard Audit File for Tax, the underlying structured-data standard that feeds the e-Fatura Billing file (monthly submission by the 5th of the following month). What it is: Portugal was the first country in the world to mandate SAF-T, and the Billing SAF-T is the actual data pipe that populates the e-Fatura totals this skill reads. Why it matters here: it explains *why* e-Fatura category totals exist at all - they are a byproduct of a business-side compliance filing, not a consumer-designed feature, which is part of why sector-code miscategorization (the vet-invoice, health-receipt field lessons) happens in the first place.
- **ATCUD + QR code (Portaria n.o 195/2020)** - the unique document code and two-dimensional barcode mandatory on Portuguese invoices since 2023, combining a per-series AT validation code with a sequential document number. What it is: a fraud/informal-economy control that makes every fiscally relevant document independently verifiable. Why it matters here: it is the mechanism that lets an invoice reach e-Fatura traceably in the first place - a missing or malformed ATCUD is one more reason a receipt can fail to auto-populate and need the manual-registration check this skill runs.
- **The e-Fatura communication pipeline (DL n.o 198/2012 family)** - the legal basis requiring businesses to communicate invoice data to the AT, which is what makes the "Consultar Faturas" export this skill reads possible at all. Why it matters here: it is the single upstream fact that explains the skill's entire zero-credential design - the data already exists on the AT side because the vendor was legally required to send it, so the household's job is verification and gap-filling, not primary data entry.
- **Bank statement export practices** - the household's own bank CSV/PDF export, used only as a sense-check against e-Fatura totals (see Integrations). Why it matters here: it is the one upstream input this skill uses that is not government-mandated - it is a household-controlled cross-check, and the reason it is never stored with account numbers (PII rule) is that it carries no independent tax-recognition value, only a plausibility-check one.

### Downstream (who consumes the outputs)

- **Contabilistas certificados (OCC professional standards)** - Portugal's certified-accountant profession, governed by the OCC's own Estatuto and Codigo Deontologico (independence, professional competence, confidentiality duties). What it is: the licensed profession this skill explicitly routes a household to whenever an item falls outside its scope (Categoria B, Categoria F, capital gains, disputed AT rulings). Why it matters here: it is the downstream escalation path named throughout Modes and Limitations - this skill's boundary is deliberately drawn short of what an OCC-certified professional does.
- **Modelo 3 filing and the AT validation/divergencias workflow** - the annual income-tax return this skill's capture table feeds into, including the AT's own pre-filled-declaration cross-check and divergencia-resolution process during the April-June window. Why it matters here: the capture-table and action-checklist deliverables exist specifically to be cross-checked against this downstream filing step (Validate mode, Execute-mode step 6) - the skill's output is only useful insofar as it survives contact with the actual Anexo H entry.
- **Records-retention duty (10-year fiscal document retention, Portuguese general tax/accounting rule)** - Portuguese law requires fiscally relevant documents and supporting accounting records to be kept in good order for 10 civil years (dossier fiscal, IRC/IVA supporting documents); transport documents carry a shorter 4-year retention. Why it matters here: it sets the real-world stakes for the PII-hygiene rule in this skill - the household, not this skill, is the party obligated to retain original documents for a decade, so this skill's own artifacts are deliberately not a substitute retention system (bucketed/rounded figures only, never the underlying invoice).
- **ISO 15489 (records management, international frame)** - the international standard for creating, capturing, and managing authentic, reliable records, applicable across formats and sectors. Why it matters here: it is the general discipline underneath the Portuguese 10-year retention rule - a household that treats its e-Fatura exports and invoice photos as a lightweight personal records-management practice (consistent naming, dated capture, no premature deletion) is applying ISO 15489's core principle at home, even without formal certification.

### Horizontal (sibling crafts)

- **Financial-literacy infrastructure - Todos Contam / Plano Nacional de Formacao Financeira** - the joint financial-education initiative run by Banco de Portugal, CMVM, and ASF (the three financial supervisors), offering free simulators and educational content on household budgeting, credit, and savings. Why it matters here: it is the sibling craft of *general* financial literacy that this skill deliberately does not try to replace - this skill is narrow and deduction-specific, and a household wanting broader financial education should be pointed at Todos Contam rather than this skill trying to cover that ground.
- **GDPR data-minimization** - the privacy craft this skill practices operationally, not just cites: category labels and rounded/bucketed amounts only, no NIF/name/account-number persistence (see PII rule, Validate-mode failable check, Reproducibility & QA rubric). Why it matters here: it is the same minimization principle GDPR names as a first-class data-protection obligation, applied here as a design constraint rather than an afterthought - the skill's zero-PII-persistence rule and GDPR's storage-limitation/data-minimization principles are the same discipline stated twice, once as regulation and once as skill design.
- **Open Banking / PSD2 (deliberately rejected adjacent capability)** - the EU directive and Account Information Service Provider (AIS) ecosystem that lets a household aggregate live bank-account data across institutions with authorization (live in Portugal since September 2019 via SIBS API Market and bank-side AIS providers). Why it matters here: this is the nearest capability this skill *could* have built and explicitly did not - PSD2 aggregation would mean live bank-account credentials flowing through a third party, which is precisely the zero-credential, file-level-only boundary this skill exists to hold (see Requirements). The rejection is structural, not a missing feature.

## Value-chain positioning: top-down & bottom-up

### Top-down

The household KPIs this skill moves:
- **Deduction capture rate per category** - claimed amount vs. the category cap, tracked category-by-category in the capture table.
- **Euros left on the table** - the gap between what was captured and what the household was actually eligible for; target zero within each category's cap.
- **Pending invoices at month-end** - the count of unclassified or unregistered items sitting in e-Fatura at any given Monitor-mode check-in.
- **Leak category identified per season** - which single category (per the constraint-thinking canon entry above) is losing the household the most money this cycle.

Sponsor questions a partner/household-CFO would ask, and which mode answers them:
- "Are we going to lose anything before the deadline?" -> **Monitor mode** (the Jan-Feb watch duty).
- "Which categories actually apply to us this year, and what's still missing?" -> **Plan mode**.
- "Did we actually capture everything, and is it correctly categorized?" -> **Execute mode**.
- "Is this ready to hand off / file, or does something still need fixing?" -> **Validate mode**.

Plan mode is the entry point from the top - a household-CFO question about strategy and scope always routes there first, before Execute is allowed to run.

### Bottom-up

Pattern-to-signal escalation rules (real thresholds):
- If an **unmapped/miscategorized income or expense item recurs across 2+ consecutive Monitor-mode check-ins** -> escalate to a full Plan-mode re-scoping pass rather than treating it as a one-off manual fix each time.
- If **estimate-vs-simulator drift** (this skill's category total vs. the mowei.pt `iva-percentagens-descontos` or `ppr-beneficio-fiscal` output) **exceeds the category's own cap threshold in 2 consecutive runs** -> escalate to a contabilista certificado referral (per Execute mode's failable check) rather than re-running the same category analysis a third time.
- If a **single category's pending-invoice count exceeds 3 items still unregistered by the mid-year Monitor check-in** -> escalate that category to an immediate manual e-Fatura registration pass, don't wait for the Jan-Feb high-value window to clear a backlog that size.

Monitor and Validate modes are the sensors that feed these signals - Monitor watches the calendar and pattern recurrence, Validate gates whether a draft deliverable's gaps are severe enough to block delivery.

**Chain:** household member -> this skill -> mowei.pt calculators / official AT simulators -> contabilista certificado (OCC) / AT (Modelo 3, divergencias, reclamacao).

## Integrations

**File-level only.** This skill never connects to an API, OAuth flow, or daemon, and never asks for Portal das Financas credentials. Every row below is something the user exports, downloads, or views in their own browser/app and then pastes, uploads, or screenshots back into this conversation - the skill reads what is handed to it, it does not fetch anything itself.

| Tool / Source | Free or Paid | Format consumed | Format produced |
|---|---|---|---|
| Portal das Financas > e-Fatura > Consultar Faturas | Free (government portal) | CSV export, or on-screen category totals copied/pasted/screenshotted by the user | n/a (read-only source; skill never writes back to the portal) |
| Portal das Financas > IRS pre-filled declaration (Modelo 3 / Anexo H view) | Free (government portal) | Screenshot or pasted text of AT's pre-filled deduction figures, viewed by the user in their own session | n/a (read-only comparison source for the Validate-mode cross-check) |
| Bank statements (household spend cross-check) | Free/Paid depending on bank | CSV or PDF export downloaded by the user | n/a (used only as a sense-check against e-Fatura totals, never stored with account numbers) |
| Invoice/receipt photos | Free | JPEG/PNG/PDF photo supplied by the user | n/a (used to confirm NIF/category/prescription-linkage on a specific document) |
| mowei.pt `calendario-fiscal` | Free | n/a | Dates/deadlines the assistant can cross-check against the Monitor-mode calendar |
| mowei.pt `ppr-beneficio-fiscal` | Free | User-entered age/contribution inputs (manual, in-browser) | Sized contribution recommendation for category 8 |
| mowei.pt `iva-percentagens-descontos` | Free | User-entered spend inputs (manual, in-browser) | IVA-by-sector percentage breakdown, cross-checkable against category 7 |
| This skill's own capture table / action checklist | n/a | n/a | Markdown table + checklist (see Output format) - the only persistent artifact this skill produces |

## Reproducibility & QA rubric

**Named intermediate artifacts** (so two runs on the same household inputs are comparable):
1. `fiscal-profile` — the Research-mode household summary (composition, dependents, income year in scope).
2. `applicability-list` — the Plan-mode scoped-in/scoped-out category list.
3. `capture-table` — the Execute-mode per-category table (see Output format).
4. `action-checklist` — the Execute-mode dated checklist (see Output format).

**Scoring rubric (0-2 per dimension, score every run before delivery):**

| Dimension | 0 | 1 | 2 |
|---|---|---|---|
| Completeness | Categories skipped without a stated reason | All 11 categories addressed but some "Not applicable" calls unexplained | All 11 categories addressed, every "Not applicable" has a one-line reason |
| Correctness of year-labeling | Any euro figure with no income-year label | Most figures labeled, at least one ambiguous | Every euro figure in the capture-table carries an explicit income-year label |
| PII hygiene | Any NIF, full name, exact per-invoice amount, or account number in a persisted artifact | Bucketed amounts used but an NIF or name slipped through once | Zero PII in any persisted artifact - category labels and rounded/bucketed amounts or counts only |
| Actionability | Checklist items are generic ("check your invoices") | Checklist items are dated but not category-specific | Every checklist item is dated, category-specific, and states the exact next action (validate/register/reclamar/cross-check) |

**Hard gate - do NOT deliver unless:**
- Every euro figure carries an income-year label (income year 2025 vs income year 2026 stated explicitly, never implied).
- No PII appears in any persistent artifact (see PII hygiene row above).
- Every deduction row in the capture-table cites a document-present or document-missing status - "Captured" is not a valid status without a stated basis.
- The Validate-mode failable check (see Modes) has been run and passed.

**As-of assumptions:** all rates, caps, and deadlines in the Domain playbook are stated for **income year 2025** (filed April-June 2026) unless explicitly marked income year 2026 (OE2026). These figures were current as of July 2026 research. Fiscal rules change annually (OE budget law, sometimes mid-year updates) - verify every figure against current AT guidance (`portaldasfinancas.gov.pt`) before relying on it for an actual filing, especially for any run more than a few months after this file's last verification date (see Changelog).

## Output format

Produce two deliverables per run:

**1. Category capture table** (one row per CIRS art. 78 category that applies to this household):

| Category | Rate | Cap (income year X) | Amount identified from data | Status | Action needed |
|---|---|---|---|---|---|

Status is one of: Captured / Under cap - room to add / At or near cap / Missing - needs manual e-Fatura registration / Miscategorized - needs correction / Not applicable.

**2. Dated action checklist**, e.g.:
- [ ] Before 2 March: validate/register these N invoices in e-Fatura: <list, categories only, no amounts/NIFs stored>
- [ ] Before 2 March: confirm displaced-student communication filed with AT (category 3) - and confirm the landlord's contract communication happened first (see field lesson §3)
- [ ] 16-31 March: if AT's pre-filled deduction for despesas gerais familiares or IVA-por-exigencia-de-fatura looks lower than expected, file a reclamacao via Portal das Financas (user does this themselves) - other categories are not reclamavel in this window (see §12)
- [ ] Before filing: cross-check final Anexo H entries against this table
- [ ] If the validation deadline was missed entirely: note that a declaracao de substituicao in the April-June window remains available (see §12)

Never include the user's actual NIF, name, exact amounts, or account numbers in either deliverable when it will be saved to a persistent note - use category labels and rounded/bucketed amounts or counts only (see PII rule).

## Handoff dossier contribution

When a handoff dossier folder exists (created by the flagship organizer's
`scripts/dossier.py`) — or the user asks for one — this skill appends its capture results
to **06-outliers-questions-suggestions.md** as part of Execute: outliers (miscategorized
invoices, cap exceedances, post-deadline pending items), questions for the reviewer (each
tied to the deduction decision it unblocks), and suggestions (NIF-allocation moves,
manual-registration to-dos, category corrections) with euro impact where the matrix can
compute it. It also feeds rows into **03-deduction-inventory.md** when the flagship
organizer is not installed. Validate confirms the contribution was written before the run
is logged.

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

- The deduction matrix, doutrina index, and planted-case scanner are bundled, cited, and
  income-year-labeled; category analysis never needs a network. Citation URLs in matrix
  rows and doutrina entries are provenance records to consult when online — not runtime
  dependencies.
- Offline, "verify against current AT guidance" degrades to: the bundled `assets/law/`
  snapshot (sha-hashed, dated) + the sweep's staleness age-gates + honest UNKNOWN cells.
  Record any deferred verification in the dossier's 06/09 files so the reviewer sees it.
- e-Fatura hygiene duties that require the portal (validating pending invoices) are
  calendar duties for the user's next online session — the skill queues them with dates
  rather than skipping them.

## Supported-feature matrix (what this skill will and will not do)

| Status | Scope |
|---|---|
| **SUPPORTED** | All CIRS art. 78 household deduction categories + art. 84 (lares) + art. 83-A (alimony); the two education uplifts as distinct rules; IVA-por-exigencia sectors; global-cap logic; e-Fatura hygiene; NIF-allocation strategy; doutrina layer (25 verified rulings); planted-case scanning |
| **PARTIAL** (honest UNKNOWNs) | Public-transport-pass IVA percentage (moves between years); any matrix cell marked UNKNOWN — the skill says exactly what to verify with the AT instead of guessing |
| **UNSUPPORTED → STOP + route to OCC** | Benefit regimes outside the bundled matrix (special mecenato regimes, EBF corporate benefits); disputed AT positions (the skill surfaces the applicable doutrina and routes — it never argues a contested position) |

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

- **Fiscal rules change annually** (OE budget law each year, sometimes mid-year updates). Every rate, cap, and threshold in this file must be re-verified against the current AT guidance (`portaldasfinancas.gov.pt`) or an equivalently current source before being quoted as authoritative for a filing the user is about to submit - this file's income-year-2025 figures were current as of July 2026 and were already showing a boundary case (rent cap) with a 2026 change already legislated.
- Does not compute Modelo 3 tax liability, escaloes, or refund/acerto amounts - route to the mowei.pt Modelo 3 and IRS settlement tools, or a contabilista certificado, for that.
- Does not touch Portal das Financas, does not automate e-Fatura validation, does not read or write AT sessions - the user always performs the actual portal actions themselves; this skill only tells them what to check and why.
- Does not adjudicate disputed AT rulings or represent the user in a reclamacao - it identifies when a reclamacao window is open and what to look for (including its narrow two-category scope, §12), not how to argue a specific case.
- Global-cap interpolation formula thresholds shift yearly (confirmed a change already legislated between income year 2025 and income year 2026 during this skill's own research) - always re-confirm before quoting an exact capped euro amount.
- Divorced/shared-custody allocation guidance here is a general operating pattern, not a substitute for what is actually registered with the AT for a specific dependent in a specific year.
- **Field-lesson sourcing is thin on forums for this niche.** No Reddit or Hacker News threads surfaced across multiple targeted searches for this domain (Portuguese personal e-Fatura/IRS deduction troubleshooting is essentially undiscussed on English-language forums, and Portuguese-language forum discussion did not surface either); the field lessons in this file are sourced from Portuguese consumer-finance publishers (Doutor Financas, Montepio, e-konomista, idealista, ACP, justicatv.com) rather than practitioner forum threads. This is disclosed rather than papered over - treat these as documented practitioner-facing patterns, not first-person anecdote-verified reports.

## Disclaimer

Outputs produced by this skill are drafts for the user's own review, not a filed tax return. This is not tax advice and does not constitute a professional fiscal opinion. This skill and its output are not affiliated with, endorsed by, or sourced from the Autoridade Tributaria e Aduaneira (AT) or any Portuguese government body. Final figures, category assignments, and any filing decisions should be confirmed with a contabilista certificado (OCC) or directly with the AT before acting on them.

**Standard framing for every output:** This is educational information, not financial, tax, or legal advice. Confirm filing positions and classifications with a contabilista certificado (OCC) or the Autoridade Tributária before acting.

## Changelog

- v1.0.0 (2026-07): wave-1 floor - CIRS art. 78 category playbook, e-Fatura validation/reclamacao calendar, household allocation and global-cap logic for income year 2025 with income-year-2026 OE2026 deltas flagged.
- v2.0.0 (2026-07-10): wave-2 practice depth - restructured into five Modes (Research/Plan/Execute/Monitor/Validate) with a failable check per mode; Workflow section folded into Execute; added six field-lesson entries sourced from targeted web research (vet-invoice miscategorization, health-receipt-to-general-expense downgrade, displaced-student landlord-then-student registration sequence, propinas-as-pensao-de-alimentos AT ruling, reclamacao window's two-category-only scope, missed-deadline declaracao-de-substituicao fallback), new §12 (reclamacao window scope); added Integrations table (file-level only, no credentials); added Reproducibility & QA rubric (named artifacts, 0-2 scoring, hard delivery gate, as-of assumptions); disclosed thin forum-sourcing for this niche rather than padding with unverifiable anecdotes.
- v3.0.0 (2026-07-10): wave-3 context depth - added "Strategic canon" subsection to Domain playbook (Atomic Habits, Nudge, The Goal - adjacent operator wisdom, applied to habit-stacked NIF capture, defaults-as-audit-target, and constraint-thinking on the biggest leak category); added "Adjacent disciplines" section (Upstream: SAF-T (PT), ATCUD/QR code Portaria 195/2020, e-Fatura pipeline DL 198/2012, bank statement exports; Downstream: contabilistas certificados/OCC, Modelo 3 filing and AT divergencias workflow, 10-year fiscal document retention, ISO 15489; Horizontal: Todos Contam financial-literacy infrastructure, GDPR data-minimization, Open Banking/PSD2 as a deliberately rejected capability); added "Value-chain positioning" section (top-down household KPIs and sponsor questions mapped to modes, bottom-up pattern-to-signal escalation rules with real thresholds, household-to-AT chain statement). All standards fresh-confirmed via web search this wave; no other section modified.
- 2026-07-10 v3.1.0 — persistent per-user memory layer (MEMORY.md: Preferences / Lessons / Run log) wired into the Validate hard gate; hard no-PII rule.
- 2026-07-10 v3.2.0 — wave-4 MOAT asset: added `assets/deduction-matrix.json` (27 rows expanding the 9+ CIRS art. 78 categories, per-row income-year labels and as-of dates, per-cell citation-or-UNKNOWN discipline, IVA-por-exigencia-de-fatura sector rows), `assets/planted-cases.json` (9 golden expense-set cases incl. a clean negative control), and `scripts/validate.py` (stdlib-only schema-validator + planted-case scanner; `--selftest` gate exits 0 on the bundled golden set). Wired the asset into Execute (new step 1 consulting the matrix) and Validate (selftest hard gate); added a "The moat asset" section; appended the USP to the frontmatter description. No Domain-playbook figures changed.
- 2026-07-10 v3.3.0 — marketplace security & permissions disclosure block (network scope, env-none, file scope, stdlib-only validate.py, no irreversible actions); packaging pass.
- 2026-07-10 v3.4.0 — offline CIRS law snapshot (10 dated verbatim articles) + host-model qualification exam (golden-corpus mode-2 scoring) + weak-model operating contract (no mental arithmetic, echo-before-use, verbatim-law rule).
- 2026-07-10 v3.5.0 — automatic correctness sweep (scripts/sweep.py): asset re-hashing, staleness age-gates, cross-skill value-agreement, code-enforced PII hygiene; Validate gate is now dual (selftest AND sweep).
- 2026-07-10 v3.6.0 — handoff-dossier contribution contract (writes its files into the flagship's dossier folder; Validate confirms).
- 2026-07-10 v4.0.0 — Doutrina layer: added `assets/doutrina-index.json`, a curated index of 25 real AT binding rulings (informacoes vinculativas / fichas doutrinarias + 1 ofício-circulado; 23 primary AT-ficha reads / 2 secondary press summaries, 100% with source_url), each pinned to the `deduction-matrix.json` row(s) it clarifies; annotated 15 matrix rows with a `doutrina` field (existing cell values untouched); extended `scripts/validate.py --selftest` with a Doutrina-layer integrity section (schema completeness, matrix_row_ids resolve, matrix `doutrina` refs resolve, bars >=25 entries / 100% source_url / >=10 rows annotated) — existing schema checks + 9 planted cases still pass; wired the layer into Execute (new step 1a surfaces the applicable ruling "the AT has ruled: ...") and the Validate gate; appended the USP to the frontmatter description. No Domain-playbook figures or existing matrix cells changed.
- 2026-07-13 v4.1.0 — offline-operation contract, supported-feature matrix, recommendation format, standardized disclaimer.
