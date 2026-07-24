# Contributing

Thank you. This project handles numbers that cost real people real money, so the bar is
"prove it", not "looks right".

## The one rule

**Every PR keeps all gates at exit `0`:**

```bash
python scripts/estimator.py --selftest
python scripts/oracle.py --crosscheck
python scripts/oracle.py --mutation-test
python scripts/offline_audit.py --selftest && python scripts/offline_audit.py
python scripts/sweep.py
```

No dependencies to install. If a gate is red, the PR is not ready — including if it went
red for a reason you believe is unrelated.

## Changing a fiscal constant

This is the highest-risk change in the repo and has a fixed procedure.

1. **Cite it.** Article and diploma, in the constant's own `source` field. "I checked
   online" is not a citation. A secondary source is acceptable only when it names the
   diploma.
2. **Never edit an expected value to make a test pass.** If the corpus goes red after a
   constant change, that is the corpus doing its job. Regenerate with
   `python scripts/oracle.py --derive`, which only writes values **both** engines agree
   on and reports the ones they don't.
3. **Bump `_meta.law_version`** in `assets/golden-cases.json`.
4. `oracle.py --crosscheck` re-derives the taxa-média column from your new rates. If it
   goes red, your rate and the published average disagree — resolve that before merging.

## Adding something the engine does not model

Either implement it **or** declare it — never leave it silent.

Every entry in `constants.json → documented_approximations` carries a **direction of
error**: does omitting this overstate or understate tax? `sweep.py` fails if any entry
lacks one. If you cannot state the direction, you do not yet understand the gap well
enough to ship the change.

Partial implementations must raise a **flag** on the result so no caller mistakes a
partial answer for a whole one.

## Adding a guard

A guard that has only ever been observed green is not evidence. If you add one, add the
mutation that proves it can go red — and if your guard structurally cannot catch
something, put it in `oracle.BLIND_SPOTS` with an explanation. An undeclared survivor
fails the run; so does a declared entry that has since become catchable.

## What will get a PR rejected

- A networking, `subprocess` or `ctypes` import, or a builtin `eval`/`exec`. The offline
  guarantee is the reason this project is trustworthy with tax data. There is no
  exception, not even for a "quick fetch" of a rate.
- A dependency. Standard library only, deliberately.
- A constant without a citation.
- Real personal data in a fixture. Invent the numbers.
- Weakening or removing the disclaimer.

## Reporting a wrong number

Open an issue with the [wrong number](../../issues/new?template=wrong-number.yml)
template. It is the most valuable contribution to this project and you do not need to
write any code to make it.
