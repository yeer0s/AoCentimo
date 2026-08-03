<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/yeer0s/AoCentimo/main/docs/images/aocentimo-wide-dark-1k.svg">
    <img alt="Ao Cêntimo" src="https://raw.githubusercontent.com/yeer0s/AoCentimo/main/docs/images/aocentimo-wide-light-1k.svg" width=55%>
  </picture>
</p>

<p align="center">
  <a href="https://github.com/yeer0s/AoCentimo/actions/workflows/gates.yml"><img src="https://github.com/yeer0s/AoCentimo/actions/workflows/gates.yml/badge.svg" alt="gates"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green.svg" alt="MIT"></a>
  <img src="https://img.shields.io/badge/network-zero%20calls-00a8a8" alt="offline">
  <img src="https://img.shields.io/badge/deps-stdlib%20only-00a8a8" alt="no dependencies">
  <img src="https://img.shields.io/badge/income%20years-2022--2025-orange" alt="income years">
  <a href="https://mowei.pt"><img src="https://img.shields.io/badge/by-mowei.pt-111111" alt="mowei.pt"></a>
  <a href="https://buymeacoffee.com/letsmoweis"><img src="https://img.shields.io/badge/%E2%98%95-buy%20me%20a%20coffee-FFDD00" alt="Buy me a coffee"></a>
  <a href="https://ko-fi.com/letsmowei"><img src="https://img.shields.io/badge/ko--fi-support-FF5E5B" alt="Ko-fi"></a>
</p>

<h3 align="center">
  O seu IRS, ao cêntimo.<br>
  Offline. Determinístico.<br>
  Recusa-se a adivinhar.
</h3>

<p align="center">
  <b>An offline, deterministic Portuguese income-tax engine for AI agents.</b><br>
  Twelve articles of the Código do IRS captured verbatim · two independent engines<br>
  cross-checked to the cent · a test suite built to fail.<br>
  <sub><a href="README.pt.md">🇵🇹 Ler em português</a></sub>
</p>

---

:fire: ***News*** :fire:

- **[Jul 2026]** First public release — nine fiscal defects found and fixed, three of them by an adversarial model
- **[Jul 2026]** Dual-engine architecture: `estimator.py` and `oracle.py` must agree **to the cent** across 1 782 income profiles
- **[Jul 2026]** Mutation testing — every guard must be proven able to *fail* before its green is believed
- **[Jul 2026]** Art. 68.º-A captured, after the global-cap endpoint was found to be taken **from the wrong article** for four income years
- **[Jul 2026]** Income years 2022-2025, each computed against the law as it actually stood that year

---

## Your tax return is none of an API's business

Every "AI tax helper" has the same architecture: you type your salary, your children's
ages, your rent, your health expenses — and it ships all of it to somebody else's server.

**This one has no code path that could.**

<p align="center">
  <img src="docs/images/offline-audit.svg" alt="offline audit passing" width=72%>
</p>

- **Zero network calls.** No API keys, no telemetry. `scripts/offline_audit.py` parses
  every shipped file and fails on any networking, subprocess or `ctypes` import and on any
  builtin `eval`/`exec`. CI additionally re-runs **every gate with the socket layer
  disabled at runtime** — if anything tried to phone home, the build would crash.
- **The law travels with the code.** Twelve CIRS articles in `assets/law/`, each with a
  SHA-256 the suite re-verifies. Pull the ethernet cable; it still computes.
- **Runs on a local model.** Ollama, llama.cpp, LM Studio, an air-gapped box. Your NIF,
  your salary and your medical spending never leave the machine.
- **Structural, not promised.** A privacy policy is a company's intention; this is an
  architecture with no import- or call-level path to a network. Stated precisely: the
  audit is a *static check, not a sandbox* — it catches the accidental and the obvious,
  and it is not a defence against a determined malicious contributor. That risk is
  managed by reading every PR, not by the AST. See [SECURITY.md](SECURITY.md).

## Install

```bash
git clone https://github.com/yeer0s/AoCentimo.git
cp -r AoCentimo ~/.claude/skills/portugal-irs     # Claude Code / Claude Desktop
```

No `pip install`. No `requirements.txt`. Python 3.10+ standard library and nothing else.

## Verify every claim yourself, in 30 seconds

```bash
cd AoCentimo
python scripts/estimator.py --selftest       # 19 golden + 9 retro + refusal guard
python scripts/oracle.py --crosscheck        # two engines, cent-exact, 1782 profiles
python scripts/oracle.py --mutation-test     # prove the guards can fail
python scripts/offline_audit.py --selftest   # prove the privacy audit can fail
python scripts/sweep.py                      # 46 checks
```

All exit `0`. Try it with your Wi-Fi off.


## What it does

| Task | What you get |
|---|---|
| **Estimate** | The full liquidação — rendimento coletável → coleta → deduções → apuramento — for income years 2022-2025, each on its own law |
| **Recover** | Recompute a filed return, quantify what you left behind, and get the correction instrument *and its deadline* — declaração de substituição, reclamação graciosa, the art. 140.º two-year window |
| **Maximise** | [27 deduction rows](assets/deduction-matrix.json) with caps, e-Fatura mechanics, [25 AT rulings](assets/doutrina-index.json), and the boundary cases that decide the awkward ones |
| **Organise** | [61 Modelo 3 field codes](assets/field-codes.json), 8 planted miscodings, the document checklist, and the [divergências](assets/divergence-cases.json) that follow from filing the wrong campo |

Covers escalões, quociente conjugal, conjunta vs separada, IRS Jovem, recibos verdes /
categoria B simplificado, mínimo de existência, adicional de solidariedade, dependentes e
ascendentes with every majoração, PPR, rendas, saúde, educação, despesas gerais familiares,
and the global cap with its large-family majoração.

## Why trust this one

Most tax code is validated against test cases written by the person who wrote the code,
from that person's reading of the law. **That detects changes and is structurally blind to
a shared mistake.**

Ours was blind to one for a year. The 2025 bracket table carried the rates that
**Lei n.º 55-A/2025 superseded — while naming that very law as its legal basis.** All 19
cases agreed with the wrong table. Every gate was green. Every estimate was €48-€401 a
year too high.

<p align="center">
  <img src="docs/images/dual-engine.svg" alt="dual-engine architecture" width=80%>
</p>

| Guarantee | How it is enforced |
|---|---|
| **Two engines, cent-exact** | `estimator.py` walks art. 68.º cumulatively on marginal rates; `oracle.py` uses the taxa-média split the article itself publishes. 1 782 profiles, 30 probes sitting ±1 cent on bracket boundaries |
| **Guards proven able to fail** | `--mutation-test` injects each defect a guard claims to catch. Survivors must be **declared** in a blind-spot register — and a declared entry that later becomes catchable *also* fails the run, so the register can never rot into an alibi |
| **Refuses rather than guesses** | Any unconfirmed constant is the literal string `UNKNOWN` and the engine **raises** instead of computing. Proven by a guard test, not asserted here |
| **Every gap has a direction** | 16 approximations declared, each stating whether it over- or understates tax. The suite fails if any lacks one |

One blind spot is declared and real: the 9th escalão is open-ended, so art. 68.º publishes
no average rate for it and nothing can cross-check the 48% top rate. It is written down in
public rather than hidden.

## ⚠️ Not financial, tax or legal advice

**Estimates produced from public tax law. Not a professional opinion, and no professional
relationship is created. Every figure, recommendation and document produced here must be
verified by a contabilista certificado (OCC) or other qualified professional before you
file, sign, pay, or act on it.**

Full terms: **[DISCLAIMER.md](DISCLAIMER.md)**.

Only the [Autoridade Tributária](https://info.portaldasfinancas.gov.pt) and the Diário da
República are authoritative. The offline law snapshots here decay with every Orçamento do
Estado. A calculator cannot sign your Modelo 3, cannot represent you before the AT, and
carries no professional indemnity insurance — an [OCC](https://www.occ.pt/) does all three.
**This exists to make you a better-prepared client, not an unrepresented one.** No
liability is accepted for tax assessed, penalties incurred, deductions lost, or decisions
taken on this project's output.

## Free, and staying free

MIT licensed. No paid tier, no "pro" version, no email wall, no telemetry.

Built by **[mowei.pt](https://mowei.pt)** — free comparison tools and plain-Portuguese
guides for **energy, telecoms, insurance, banking, credit and grants**. If this found you
money on your IRS, the same household is usually overpaying on a tariff somewhere else too.

<p align="center">
  <a href="https://mowei.pt"><img src="docs/images/mowei-banner.svg" alt="mowei.pt — ferramentas gratuitas" width=80%></a>
</p>

<p align="center">
  <a href="https://mowei.pt"><b>&#127477;&#127481; mowei.pt &mdash; ferramentas gratuitas</b></a>
  &nbsp;&middot;&nbsp;
  <a href="https://buymeacoffee.com/letsmoweis"><img src="https://img.shields.io/badge/%E2%98%95-Buy%20me%20a%20coffee-FFDD00?style=for-the-badge" alt="Buy me a coffee"></a>
  &nbsp;&middot;&nbsp;
  <a href="https://ko-fi.com/letsmowei"><img src="https://img.shields.io/badge/Ko--fi-support-FF5E5B?style=for-the-badge&logo=ko-fi&logoColor=white" alt="Ko-fi"></a>
</p>

Support is entirely optional and always will be — the project is complete without it.

## Contributing

In order of value:

1. **[A wrong number](../../issues/new?template=wrong-number.yml)** — a rate, cap,
   threshold or coefficient contradicting the statute it cites. The most valuable thing
   anyone can send this project.
2. **Extend `oracle.py` to income years 2022-2024** — those retro cases are currently
   single-path and say so.
3. **The art. 70.º n.º 3 taper**, if you can source AT's published simplified formula.
4. **Anexo G / Anexo J** — the two biggest coverage gaps.

Every PR must keep all gates at exit `0`, and every new constant needs its citation.

## License

[MIT](LICENSE) — use it, fork it, ship it commercially. A link back to
[mowei.pt](https://mowei.pt) is appreciated, never required.
