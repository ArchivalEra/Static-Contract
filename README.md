# Static-Contract · Static Distribution Contract

The **authoritative repository for the Octave cluster's static distribution contract**: protocol
canon, toolchain, open-questions ledger, and the metadata site all live here.

> **Identity ruling (the core of the whole repository): this repository is a contract maintainer and
> nothing else. The site hosts no release artifacts at all (zero-byte hosting); every package comes
> from GitHub (a release direct link) or through a reverse proxy (the cluster edge).**

**License: this repository — documents, tools, and site — is [AGPL-3.0](LICENSE). Catalogued
releases are not covered by that grant: each release follows the terms of its publisher (see its
`manifest.json`).**

> **One release = one immutable tag = one `manifest.json` plus N flat assets.**
> Names admit only characters GitHub will not rewrite (a whitelist), so `manifest.file` is always
> identical to the real asset name. Clients take names from the manifest and never assemble them,
> so a 404 has exactly one meaning. All bytes travel over plain GET.
>
> **Goal: apt's robustness plus HTTP's simplicity.**

## Canon

**`specs/2026-10-30-release-contract-v4.md`** — the contract is named **v1** (`schema: 2`; the
license protocol v1.1 raises it to `schema: 3` and governs the license field). Four rounds of
design-it-twice converged here; v0–v3 and the absorption audit are evolution history, and **the
criteria that killed rejected designs stay in canon §8 so nobody re-opens them**. Handed over
unpiloted, **not declared stable**.

## Toolchain (measured snapshot 2026-11-03, this repository)

| Tool | Self-test | What it does |
|---|---|---|
| `tools/make-manifest-v4.py` | **43 PASS / 0 fail** | Generator: split into chunks → compress each chunk independently → sha → manifest; reverse-asserts the whitelist and cleans up on failure |
| `tools/check-release-v4.py` | **37 PASS / 0 fail** | Validator: V1–V10 fail-closed; with `--base`, verifies bytes and sha per chunk against disk |

Reproduce: `python3 tools/make-manifest-v4.py --selftest && python3 tools/check-release-v4.py --selftest`

## Directory map

| Directory | Contents |
|---|---|
| `specs/` | Contract canon (v4) + the v0–v3 evolution history + the absorption audit (handed over from Octave-Extra-Content, source material untouched) + **the finalized v1.1 license protocol** (migration in progress: extra-content re-verified 15/15 releases on `schema: 3`; on LLVM-wasm only the newest release carries `schema: 3`, older ones stay excluded until republished) |
| `tools/` | v4 generator and validator (including the v1.1 license invariant V11; self-test 37/37) |
| `questions/` | Open-questions ledger (`05`: zstd vs gzip measured on the real EdgeOne link) |
| `STATE.md` | Live state (Einfacht format: states only what is true now, with the rerun command next to each assertion) |
| `maintaince.md` | Direction and map (maintenance boundary / routine / red lines) |
**Proxy path for release bytes** (ruled 2026-11-03, pending EdgeOne config):
`base_proxy` = `base` with the host swapped to `https://isui.ren/` — same shape as
`base`, filled automatically by the deriver once the reverse-proxy rule is live.

**Published surface is seven files** (shelf plus contract only): `index.html`, `files.json`, `catalogue.json`, `sources.json`, `LICENSE`, and the two current contract documents. Everything else in this repository — live state, maintenance guide, incident log, rulings, tools, superseded drafts — stays in the repo and is never published. Gate H9 enforces the whitelist in both directions; H6 checks each channel against its own file list.

| `site/` | Metadata site source: `sources.json` (subscription list) + `channels.json` (acceptance channels, **also feeds page rendering**) + `catalogue.json` (fallback source, **must stay empty**) + `catalogue.live.json` (derived file written by CI, gitignored, read by gates). Page shape follows he.net: plain XHTML 1.1 + CSS, zero JS, zero external resources. **HTML, public catalogue fields, and published `.md` are English-only** + **deprecated contracts must be marked** + **link integrity** (H5 inside the artifact; H6 an online fingerprint check across every channel's full `files.json`, **with `owned` deciding whether a failure blocks publishing**; H7 catalogue base reachability — `verify-channels.py` applies the same criteria, only warns on external channels, honours `SC_HTTP_PROXY`, and defeats "200 at a fallback page"). **Page data is fully automatic**: self-test counts come from a live `--selftest`, the channel table from `channels.json`, listings from the derived catalogue, and the footer carries `© 2026 ArchivalEra` |
| `zreflect/` | Einfacht fact-system platform (vendored from `vendor/Einfacht` at `6e4e6e8`) + this repository's data-layer collector; ledger `FACTS.json` (**do not hand-edit** — run `zreflect/facts.py`) |
| `reflect-hooks/` | Git hooks and the knob carrier (install: `sh reflect-hooks/install.sh`; pre-commit re-renders machine blocks and runs every gate in the commit phase) |
| `mail/` | Cross-repository mail inbox (rules in `mail/README.md`: append-only, numbers increase, delivery ≠ commit) |
| `docs/` | Incident log and user rulings — repository only, **not published to the site** (rulings keep the original Chinese wording as evidence) |
| `scripts/` | Zero-dependency scripts: `mail-read.py` (read mail), `build-site.py` (build the site, self-test 14/14), `sync-catalogue.py` (strict catalogue derivation G1–G7, self-test 21/21), `verify-channels.py` (online acceptance, self-test 10/10) |
| `vendor/Einfacht` | Anti-hallucination fact-system suite (upstream `6e4e6e8`, vendored snapshot) |

## Where this repository sits in the cluster

| Repository | Relationship |
|---|---|
| `Octave-Extra-Content` | Home of content semantics; the contract's original author, now the upstream requester |
| `Octave-Full-Wasm` | Host: engine artifacts and build facts (`octave.build.json`); site assembly. **Catalogue-integrated (`kind: engine`)** |
| `Octave-UI` | Consumer: package manager, download manager |
| `OpenModelica-Full-Wasm` | Second engine source. **Catalogue-integrated (`kind: engine`)** |
| `Shirone-personalized` | isui.ren side: reverse proxy and edge (EdgeOne) |

## Discipline (inherited from lessons measured in the cluster)

1. **"Cannot measure it" is not "it does not exist"** — before concluding that something is absent,
   you first need a positive control of the same kind proving the probe can detect presence.
2. **Numbers and behaviour come only from measurement; put the rerun command next to the assertion.**
   A sentence with no rerun command can only be read as history.
3. **Machine blocks are maintained by machines** — the block at the end of `STATE.md` is rendered by
   `zreflect/facts.py --render-doc`, and prose may reference numbers only as `[[key]]`. The execution
   surface reads the declaration (`registry --run commit`); `off` is not a pass.
   **Whitelist trap**: a rule that allows `tools/*.py` is defeated by `*.pyc` — `__pycache__/` must
   be ignored explicitly (measured: bytecode once reached a commit).
4. **Push discipline** — `README.md` is updated in the same batch as every push (pre-push and CI
   apply the same criterion, and single-entry mode does not degrade it); `--no-verify` only hides it
   locally, CI is the enforcement point that cannot be skipped.

## Status

**Not yet piloted**: the full chain "producer publishes a release → catalogue lists it → consumer
switches links" has never run end to end.
Open items: U1 codecs order (question 05), U2 per-entry `chunkSize`, U3 asset name product prefix,
U4 rollout schedule for the remaining repositories.

**Deployment (three channels in parallel, one artifact)**: push `main` → the `sync-deploy`
workflow → **the same `site/dist`**:

1. Force-push an orphan `deploy` branch (CF Pages / EdgeOne Pages listen on it);
2. `actions/deploy-pages` deploys GitHub Pages.

Channels: `https://archivalera.github.io/Static-Contract/` ·
`https://static.mango-mesa.ccwu.cc/` (Cloudflare) ·
`https://isui.ren/static/` (EdgeOne, China-facing path). Header semantics (ETag / `304` /
Content-Type) live on the site side.

**Online acceptance**: `scripts/verify-channels.py` checks, after deployment, each channel against
**this build's artifact fingerprint** (`STATIC-CONTRACT-BUILD <hash>` written into `index.html`) and
`catalogue.verified_at`. The criterion anchors to the artifact itself, **not to whether the channels
agree with each other** — when every channel is stuck on an old artifact, agreement holds just as
well (that is exactly how I misjudged it once on 2026-11-01).

> **Fixed (2026-11-01, shirone `mail/006`)**: EdgeOne used to reverse-proxy Cloudflare's Worker
> inline snapshot and did not follow the `deploy` branch (measured: two builds behind). The three
> legs now deploy independently: CF reads the raw `deploy` branch at runtime, and CI drops the
> `deploy` branch into EO's static tree; the count of `cf-ray/nel/report-to` in EO response headers
> is 0. Fingerprints on all three channels and the catalogue sha all equal the `deploy` branch.
> **The `deploy` branch is the only artifact and the correct entry point for consumers** — do not run
> `build-site.py` (it needs an already-derived catalogue; run on its own it only produces the empty
> fallback).
> **EO updates are triggered by our `sync-deploy` dispatching their workflow** (pushing the `deploy`
> branch does not trigger them). This needs `HEART_DISPATCH_TOKEN`; without it the step says so and
> skips, and EO stays on the previous build.

CI: the `gates` workflow runs the same criteria as the local hooks (fact-block reconciliation + the
full gate roster + module self-tests); the environment explicitly installs `zstandard` (the
instrument the generator's self-test needs) and sources `reflect-hooks/Einfacht.env` (the source of
the knobs).

Current state and pilot acceptance criteria: `STATE.md`; direction, boundaries, and routine:
`maintaince.md`.
