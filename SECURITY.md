# Security & privacy

## The threat this project is designed against

Tax data is among the most sensitive material a person holds: income, household
composition, children's ages, medical spending, address. The design assumption here is
that **it should never leave the user's machine**, including to us.

## Guarantees, and how they are enforced

| Guarantee | Enforcement |
|---|---|
| No network calls | `scripts/offline_audit.py` parses every shipped file and fails on any networking/`subprocess`/`ctypes` import. Wired into `sweep.py` and CI |
| No dynamic code execution | Same audit fails on builtin `eval`/`exec`/`__import__` |
| Provably offline at runtime | CI re-runs **every gate with the socket layer disabled**. If any path attempted a connection the build would crash rather than pass |
| No dependencies | Python standard library only. No supply chain to compromise |
| No telemetry | There is no analytics, no phone-home, no usage reporting, and no code that could add one without failing the audit |

Verify all of it yourself:

```bash
python scripts/offline_audit.py --selftest   # prove the audit can fail
python scripts/offline_audit.py              # then trust that it doesn't
```

## Your own data

`scripts/estimator.py <candidate.json>` reads a file you create containing real income
figures. `.gitignore` excludes `candidate*.json`, `*.local.json` and `scratch/` so an
absent-minded `git add -A` cannot publish your tax return. **Check before you commit
anyway.**

Never paste a real NIF, IBAN, address or full name into an issue. The engine needs none
of them — income figures and household structure are enough to reproduce any bug.

## Reporting a vulnerability

Anything that would let this project transmit user data, execute arbitrary code, or read
outside its own folder: please open a **private security advisory** via the Security tab
rather than a public issue.

Fiscal errors are not security issues — those go in the
[wrong number](../../issues/new?template=wrong-number.yml) template, in public, where
they can be discussed.
