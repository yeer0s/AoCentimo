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

## What the audit does NOT prove

`offline_audit.py` is a **static check, not a sandbox.** It is honest about its own limits
because a security claim that overreaches is worse than none:

- It catches networking/`subprocess`/`ctypes` imports, shell-outs (`os.system`, `os.popen`,
  `os.exec*`), dynamic imports (`importlib.import_module`) and builtin `eval`/`exec`.
- It cannot catch every conceivable exfiltration path. `os` itself cannot be forbidden —
  the project needs `os.path` — so the dangerous *members* are enumerated, and an
  enumeration is never complete.
- The CI job that disables sockets patches **this interpreter's** socket layer. A shelled-out
  network client would run in a separate process and evade it.

**Neither mechanism is a defence against a determined malicious contributor.** That risk is
managed the ordinary way: this is a small project where every pull request is read by a
human. The audit exists to make an *accidental* regression impossible to merge quietly, and
to let a stranger verify the offline claim without reading all 900 lines themselves.

This scoping was added after an adversarial review demonstrated that
`os.system("curl ... http://host")` passed the original audit with zero findings. The audit
now catches that specific case; the honest generalisation is the paragraph above.

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
