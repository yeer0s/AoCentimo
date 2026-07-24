# Image specs

Everything referenced by the READMEs currently ships as **hand-authored SVG** — crisp at
any size, a few KB each, perfect text, and no generation step. The repo is complete as is.

If you want to replace any of them with designed artwork, these are the exact
specifications. **Keep the filenames**; both READMEs reference them and nothing else
needs to change.

## Palette used by the current SVGs

| Role | Light | Dark |
|---|---|---|
| Ink / headline | `#12211d` | `#f2f7f5` |
| Muted / subtitle | `#5c6b66` | `#9aada7` |
| Accent (mint) | `#0f9b7a` | `#3fd9b0` |
| Terminal background | `#0e1a17` | same |
| Card border | `#c9d8d2` | — |

---

## 1. `aocentimo-wide-light-1k.*` and `aocentimo-wide-dark-1k.*` — REQUIRED pair

The header wordmark. Two files, swapped automatically by the reader's GitHub theme via a
`<picture>` element.

| | |
|---|---|
| **Size** | **1000 × 260 px** (a 3.85:1 wide lockup) |
| **Format** | PNG-24 with **transparent background**, or SVG |
| **Weight** | under 150 KB each |
| **Light variant** | dark ink on transparent — must read on white |
| **Dark variant** | near-white ink on transparent — must read on `#0d1117` (GitHub dark) |
| **Safe area** | keep 40 px clear on all sides; it renders at 55% width |
| **Content** | "Ao Cêntimo" wordmark. Optional: the `0,00 €` motif and the strapline `IRS DE PORTUGAL · OFFLINE` |

⚠️ **Transparency is not optional.** A white-background PNG shows as a white slab for
every reader in dark mode — the single most common README artwork mistake.

## 2. `offline-audit.*` — optional replacement

Terminal card showing `offline_audit.py` passing. This is the privacy proof, so it should
look like a real terminal, not a marketing graphic.

| | |
|---|---|
| **Size** | **900 × ~380 px**, or any 2.4:1 ratio |
| **Format** | PNG or SVG |
| **Renders at** | 72% width |
| **If you screenshot it** | dark terminal, monospace, 2× retina capture then downscale, no window shadow |

## 3. `dual-engine.*` — optional replacement

The architecture diagram: one constants source → two engines → "must agree to the cent" →
three enforcement boxes underneath.

| | |
|---|---|
| **Size** | **980 × 470 px** |
| **Format** | SVG strongly preferred (text must stay legible at 80% width) |
| **Must show** | `estimator.py` (marginal-rate walk) · `oracle.py` (taxa-média split) · the cent-exact join · mutation-test / BLIND_SPOTS / offline-audit |

## 4. `mowei-banner.*` — optional replacement

The mowei.pt call-to-action strip.

| | |
|---|---|
| **Size** | **1000 × 150 px** |
| **Format** | PNG or SVG, solid background is fine here |
| **Renders at** | 80% width, wrapped in a link to https://mowei.pt |
| **Content** | mowei.pt logo + "Ferramentas gratuitas de comparação para Portugal" + the six verticals |

## 5. `demo.gif` — NOT YET IN THE REPO

A terminal recording of the four gates running green. The README block that showed it was
removed rather than ship a broken image; **paste the block back in once the file exists**:

```html
<p align="center">
  <img src="docs/images/demo.gif" alt="running the gates" width=85%>
</p>
```

| | |
|---|---|
| **Size** | **1200 × 700 px** max, renders at 85% |
| **Weight** | **under 5 MB** — GitHub will not autoplay a heavy GIF gracefully |
| **Length** | 15-25 s, looping |
| **Content** | `estimator.py --selftest` → `oracle.py --crosscheck` → `--mutation-test` → `sweep.py`, ending on `38/38 checks green` |
| **How** | [asciinema](https://asciinema.org) + [agg](https://github.com/asciinema/agg), or [VHS](https://github.com/charmbracelet/vhs) (scriptable, reproducible) |

## 6. Social preview card — NOT A REPO FILE

Uploaded in **Settings → General → Social preview**, not committed. This is what renders
when the repo is shared on X, LinkedIn, Slack or Discord — worth doing, it drives clicks.

| | |
|---|---|
| **Size** | **1280 × 640 px** exactly (2:1) |
| **Format** | PNG or JPG, **under 1 MB** |
| **Safe area** | keep text within the centre 1100 × 500 px — platforms crop the edges |
| **Content** | "Ao Cêntimo" + "O seu IRS, ao cêntimo" + "Offline · Zero chamadas de rede" + mowei.pt |
| **Legibility** | it is often rendered ~400 px wide — headline type no smaller than 60 px at full size |

---

## Regenerating the current SVGs

They were authored programmatically. There is no binary source file and no design tool in
the loop — edit the SVG text directly, or ask for a regeneration with different colours.
