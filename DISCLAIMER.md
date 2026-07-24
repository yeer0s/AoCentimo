# Not professional advice

**Ao Cêntimo produces ESTIMATES of Portuguese personal income tax (IRS) from publicly
available tax law. It is not tax, legal, accounting or financial advice, and it does not
create a professional relationship of any kind.**

## Before you act on anything this produces

**Every figure, recommendation and document produced by this software must be verified by
a contabilista certificado (OCC) or another appropriately qualified professional before
you file, sign, pay, or act on it.**

That is not a formality. A calculator cannot:

- sign your Modelo 3
- represent you before the Autoridade Tributária
- carry professional indemnity insurance for getting it wrong

An [OCC](https://www.occ.pt/) does all three. This project exists to make you a
**better-prepared client**, not an unrepresented one.

## What is authoritative, and what is not

| | |
|---|---|
| **Authoritative** | [Portal das Finanças](https://info.portaldasfinancas.gov.pt) · [Diário da República](https://diariodarepublica.pt) · the AT's own simulator |
| **Not authoritative** | This repository. Its offline snapshots of the law decay with every Orçamento do Estado |

The engine deliberately refuses to compute paths that depend on values it could not
confirm, and declares — with a direction of error — every rule it models only partially.
Read `assets/constants.json → documented_approximations` before relying on a figure.

Known gaps at the time of writing include Anexo G (mais-valias), Anexo J (foreign income
and treaty relief), contabilidade organizada, RNH/IFICI, categoria H, deficiência, and the
art. 70.º n.º 3 taper. Any of these means: **route the case to an OCC.**

## Liability

No liability is accepted for any tax assessed, penalty incurred, deduction lost, or
decision taken on the basis of this software's output. See [LICENSE](LICENSE) — the
software is provided "as is", without warranty of any kind.

---

*Free tools and plain-Portuguese guides: [mowei.pt](https://mowei.pt)*
