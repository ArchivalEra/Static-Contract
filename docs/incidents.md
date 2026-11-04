# Incident log

Chronological record of defects, disagreements and their fixes. This file is
history, not state — for what is true now see `../STATE.md`.

Each entry lists what was observed, the root cause as evidenced, the change made,
and how to reproduce the observation.

## 2026-11-01 — License becomes a name plus a link to the full text

**What happened**

v1.1 fixed manifest `schema: 3` and `license: {id, url}`, both fields required.
Two earlier drafts were rejected by criteria: a three-state status with a
provenance witness chain and revision anchors (it turned the license into a gate
on the download path), and a bare SPDX string (license texts differ per project
and are replaced across generations, so the string goes stale).

Real data: 13 of 13 packages already carried an `fa-copyright` link in
`packages/*.json`; all 13 carried `id` and `url` and passed V11 and G7.

Link reachability is not verified. Three samples from this host: one returned
`200`, two returned `000` — a local network egress failure, not a link defect.

**Root cause**

The first draft moved a metadata field onto the consumer path: clients would have
had to read `status`, reject `unstated`, and refuse to unpack. The second draft
stored the license as a string that has to stay correct forever, which it cannot,
because upstream reissues under a different license every few years.

**Fix**

- `specs/2026-11-01-release-contract-v1.1-license.md` — three layers, one job each:
  bytes (`GET <base>/<file>`, license-unaware), manifest (shows `id`, links `url`),
  catalogue (a missing field means the release is not listed).
- `tools/check-release-v4.py` — V11. Also fixed during this change: `license.id`
  must accept composite expressions; the first implementation accepted only a
  single identifier, while geometry, optim and splines all use `A AND B`.
- `scripts/sync-catalogue.py` — G7, 20 PASS.

**Reproduce**

```bash
python3 tools/check-release-v4.py --selftest
python3 scripts/sync-catalogue.py --selftest
```

## 2026-11-01 — v1.1 migration: fifteen releases reissued, LLVM held back

**What happened**

Two letters sent. `Octave-Extra-Content` (`mail/119`): 15 releases needed
reissue — assets unchanged, manifest only; 13/13 packages already had `{id, url}`,
so the migration was transcription.

`LLVM-wasm` (`mail/018`): instructed not to change CI yet. Their `release.yml`
clones `Octave-Extra-Content` into `/tmp/ec` and runs
`/tmp/ec/tools/check-release-v4.py`, so the dependency order is this repository,
then extra-content, then LLVM. Also noted: their repository-level license is
`AGPL-3.0` while the product license is `Apache-2.0 WITH LLVM-exception` — the
reason v1.1 requires each release to carry its own license. `v0.1.0` through
`v0.1.4` are pre-contract format and stay blocked by G5.

Same day: all 15 extra-content releases upgraded to schema 3, full re-run 15/15
via `gh release download` one by one. All `schema: 3`, all licenses valid, V1–V11
green, composite expressions preserved verbatim (pyodide
`MPL-2.0 AND BSD-3-Clause`, geometry `GPL-3.0-or-later AND BSL-1.0`, optim with a
three-term `AND`, splines with `LicenseRef-public-domain`). G7 admitted 15/15 with
a license; removing the license was correctly rejected.

A full `sync-catalogue.py --dry-run` timed out on this host (21 releases
downloaded one at a time; the local network is unstable toward GitHub), so the
figures above come from running `verify_entry` against the already-downloaded
manifests.

Adopted from their `-OR-` report: a prose-to-SPDX replacement that uses regex word
boundaries turns `GPL-3.0-or-later` into `GPL-3.0-OR-later`, and the previous
validator accepted it. Validator self-test 35 to 37.

**Root cause**

LLVM's CI reads its validator from extra-content, not from this repository. A tool
fix here is invisible downstream until extra-content commits; delivery is not
commit. A second cause: SPDX operator substitution was never checked for
collisions with hyphens inside identifiers.

**Fix**

- `tools/check-release-v4.py` — reject tokens containing `-AND-` or `-OR-` in the
  middle, or ending in `-AND` / `-OR`. The check does not consult the SPDX word
  list; it blocks only this mechanically produced malformation.
- Letters: `extra-content/mail/119`, `LLVM-wasm/mail/018`, replies
  `extra-content/mail/120`, `LLVM-wasm/mail/021`.

**Reproduce**

```bash
git clone --depth 1 https://github.com/ArchivalEra/Octave-Extra-Content /tmp/ec
python3 /tmp/ec/tools/check-release-v4.py --selftest | tail -1
python3 tools/check-release-v4.py --selftest | grep -c '^PASS'
```

## 2026-11-01 — Three license statements were wrong, and all three passed V11

**What happened**

`LLVM-wasm` (`022`) reported three defects. All three were re-run and confirmed
here.

1. Their `git clone` of extra-content `main` produced the 35-PASS tool, not the 37
   version required by `mail/021`. They were waiting, per the stated criterion.
   The block was real.
2. The recommended `license.id` `Apache-2.0 WITH LLVM-exception` omitted the AGPL
   half. Their `LICENSE` and `driver/*.mjs` are `AGPL-3.0-or-later`, confirmed by
   `head -2 LICENSE`.
3. Another letter stated emscripten was `BSD-3-Clause`. `head -6
   LICENSE-EMSCRIPTEN.txt` reads "available under 2 licenses, the MIT license and
   the University of Illinois/NCSA Open Source License", so the value is
   `MIT OR NCSA`.

**Root cause**

All three statements were inference from the shape of the package, not reading of
the files. All three passed V11: the validator checks the shape of the expression,
not whether the id applies to the bytes.

**Fix**

- Canon `specs/2026-11-01-release-contract-v1.1-license.md` §4.5 (a license that
  passes V11 is not a license written correctly) and §4.6 (the protocol cannot
  prove a declaration true), with the two errors above written in as instances.
- The 37 version placed in extra-content's working tree (not committed; delivery
  is not commit) and `mail/141` sent to request the sync.
- `parse_spdx` handles the composite expressions (verified). Whether `NCSA` is a
  real SPDX id could not be verified at that point and was recorded as a known
  limitation.

**Reproduce**

```bash
git clone --depth 1 https://github.com/ArchivalEra/Octave-Extra-Content /tmp/ec
python3 /tmp/ec/tools/check-release-v4.py --selftest | tail -1
python3 tools/check-release-v4.py --selftest | grep -c '^PASS'
head -2 LLVM-wasm/LICENSE
head -6 LLVM-wasm/LICENSE-EMSCRIPTEN.txt
```

## 2026-11-01 — NCSA verified against the SPDX list; two conventions adopted

**What happened**

`LLVM-wasm` (`024`) located `NCSA` in the official SPDX list: table at
`licenses.md:483`, link at `:1347`, text at `text/NCSA.txt`, same source as the
copy inside the package. Four further checks were re-run here and confirmed:
`Apache-2.0` at `:880`, `MIT` at `:1305`, `AGPL-3.0-or-later` at `:866`,
`LLVM-exception` at `:1635`. The previous letter's "cannot verify" was closed.

Tool sync was still open at that moment: extra-content `main` still returned
`35 PASS`, so LLVM continuing to wait was correct.

**Root cause**

The earlier unverifiability claim described a limit of the local check, not a
limit of the SPDX list. The list is public and greppable, so the claim was
testable and had not been tested.

**Fix**

- Canon added optional `license.verified` (a human verification record; V11 does
  not read it), §4.7, which fixes why a given `id` is correct. Their
  `_spdx_verified` field is the same thing.
- `maintaince.md` added the convention that a cross-repository wait condition must
  be one executable command line: a readiness claim must carry what that command
  returns now, because the downstream side can only measure what it cloned.

**Reproduce**

```bash
git clone --depth 1 https://github.com/ArchivalEra/Octave-Extra-Content /tmp/ec
python3 /tmp/ec/tools/check-release-v4.py --selftest | tail -1
```

## 2026-11-02 — Three hand-written page values replaced by build-time reads

**What happened**

Three places on the page carried hand-copied data. All three were changed to read
from source at build time.

1. Self-test numbers: the build runs `--selftest` for the generator, the validator,
   the builder and the deriver and counts `PASS` lines. This immediately exposed a
   real drift: the page said "validator 26 PASS" while the tool returned 37.
2. Channel table: generated from `site/channels.json` (previously three URLs typed
   into the template).
3. Listed and excluded releases: already read from the derived catalogue, unchanged.

Footer gained `© 2026 ArchivalEra`. Builder self-test stayed at 13 PASS.

**Root cause**

The value was a copy. Nothing connected the page to the tool that produces the
number, so the page could not follow a change in the tool.

**Fix**

- `scripts/build-site.py` — self-test counting, channel table rendering, footer.
- `SC_BUILD_SELFTEST=1` guard. `build-site.py --selftest` calls `build()`, which
  runs each tool's `--selftest`; without the guard the builder invokes itself and
  recurses until the stack overflows (observed).

**Reproduce**

```bash
python3 scripts/build-site.py --selftest
python3 scripts/build-site.py --out site/dist
```

## 2026-11-02 — extra-content reaches 37 PASS; LLVM unblocked

**What happened**

`git clone` plus `--selftest` on extra-content returned `37 PASS`, re-run here to
confirm. The block on LLVM was lifted.

Their letter reported `upgrade-manifest-license.py` at 13 PASS; the measured value
was 25 PASS.

Adopted into canon §4.5 (their suggestion): a `license` that passes V11 is not a
correctly written license. V11 blocks mechanical malformations only; semantic
correctness must be checked item by item. Instance attached: three cases in one
night — two of them mine, one theirs — all three passed V11, all three were wrong.

**Root cause**

Reported self-test counts are transcribed by hand on both sides of the exchange.
Neither side's CI reads the other's number, so both can drift independently.

**Fix**

- Canon `specs/2026-11-01-release-contract-v1.1-license.md` §4.5.
- `README.md` and `STATE.md` updated to the re-run value.

**Reproduce**

```bash
git clone --depth 1 https://github.com/ArchivalEra/Octave-Extra-Content /tmp/ec
cd /tmp/ec && python3 tools/check-release-v4.py --selftest | tail -1
python3 tools/upgrade-manifest-license.py --selftest | tail -1
```

## 2026-11-02 — HTML must be English; deprecated contracts must be marked; the gate missed live content

**What happened**

A language gate was added with three checks: H1, the built `index.html` contains no
CJK characters; H2, any document carrying a `DEPRECATED` or `SUPERSEDED IN PART`
banner is marked as such on the page; H3, every non-authority document under
`specs/` carries a deprecation banner. Two negative tests fired correctly (CJK
inserted, banner removed). Gate phase ran 10 / off 6 / failed 0.

Deprecation is graded: `v0`, `v1`, `v2`, `v3` and the v3 absorption audit carry
`DEPRECATED`; `v4` carries `SUPERSEDED IN PART` — V1–V10 remain in force and only
the `schema: 2` clause is replaced by v1.1's `schema: 3`.

The gate then failed against the live page. The built page carried 40 CJK
characters. They came from `sync-catalogue.py` diagnostic messages — a schema
mismatch note written in Chinese — rendered straight into the excluded table. The
first gate version checked only `index.html` built from the local fallback
catalogue, which has no excluded entries, so it could never see that row.

**Root cause**

Two causes. The gate measured a build whose input differed from the live input:
the local fallback catalogue is empty by design, so the excluded table was empty
and the check had nothing to inspect. And the deriver emitted maintainer-facing
diagnostics in Chinese into a publicly published artifact.

**Fix**

- `zreflect/check_site_lang.py` — H1–H3, plus H4: public catalogue fields must not
  contain CJK, `excluded` entries must carry an English `reason`, and a missing
  catalogue is a failure, not a skip.
- `scripts/sync-catalogue.py` — English reason strings per gate code; Chinese
  diagnostics retained for maintainers behind `--verbose` and never written to the
  artifact.
- `scripts/build-site.py` — catalog document list renders `[DEPRECATED]` and
  `[PARTLY SUPERSEDED]` from each document's banner.
- `.github/workflows/sync-deploy.yml` — the derived catalogue is also written to
  `site/catalogue.live.json` for the gate, and the gate runs before the build.

**Reproduce**

```bash
python3 zreflect/check_site_lang.py
python3 scripts/sync-catalogue.py --dry-run --verbose
```

## 2026-11-02 — Page copy cut by 23 percent; invented fields removed

**What happened**

Rulings applied across three rounds: the page and the catalogue are English only;
the protocol is not to be touched by a page change; every release shows a license,
fully derived; the proxy column is removed; the style is kept but the word count
drops substantially; no invented fields — reuse what the protocol defines, and a
null renders as null.

Result: page CJK count 0, visible text 5458 characters (previously 7063, a 23
percent reduction), zero occurrences of the proxy column, all 17 releases with a
license cell (schema 3 renders `{id, url}` as a link, schema 2 renders `null`).
Every license is copied verbatim from the manifest: no hand-writing, no inference.

Five fields removed as invented: `summary_en`, `reasons_en`, `source_repo`, the
per-entry `tag`, and the `not declared` display state. `excluded` entries use the
protocol's word `reason`, a single English string.

Two-axis code review found six real bugs, all fixed.

1. `derive` sorting read the deleted `source_repo` key, so any release passing
   validation raised `KeyError`.
2. `reason` was unconditionally overwritten with `validation failed`, discarding
   the cause recorded by the early-exit paths.
3. The H2 call had been deleted, so the gate reported green while the function sat
   unused.
4. `html.escape("&mdash;")` double-escaped and printed the literal `&amp;mdash;`.
5. H4 skipped silently when the catalogue was missing — not run is not passing.
6. The fallback source `note` was still Chinese.

New gate H5: all 15 relative links on the page resolved against the artifact file
list, zero dead. External links are not probed — this host returns `URLError` or
timeout for GitHub and Cloudflare, which would report a network fault as a broken
link.

**Root cause**

The invented fields filled gaps the protocol left empty: where the protocol has no
value, the page produced a substitute (`not declared`, `summary_en`), so absent
data rendered as data. Two of the six review findings (1 and 3) are one mechanism:
a field or a call was removed while a consumer still read it.

**Fix**

- `scripts/build-site.py` — license column, `null` rendering, width reduction,
  H5 link check.
- `scripts/sync-catalogue.py` — `reason` as the single public key; English
  summaries by gate code.
- `specs/` untouched.

**Reproduce**

```bash
python3 scripts/build-site.py --out site/dist
python3 zreflect/check_site_lang.py
grep -c 'proxy' site/dist/index.html
```

## 2026-11-02 — Dead-link detection was fooled by a 200 fallback page

**What happened**

Reported from the user side: most links under `isui.ren/static` are dead, and a
`200` may be a `404` fallback page.

Measured and confirmed: EdgeOne returns `200` plus a 611-byte SPA fallback page for
paths that do not exist. GitHub Pages returns a real `404`. The previous criterion,
status code only, was deceived by both. Under network jitter an `URLError`
combined with a fallback page also read as normal.

Per-channel measurement, Cloudflare through a `2080` proxy:

```
github-pages 15/15 dead=0
cloudflare   15/15 dead=1 (LICENSE -> 404)
edgeone      15/15 dead=1 (LICENSE -> fallback page, 200)
```

One real dead link found: `/static/LICENSE` on EdgeOne hit the fallback page. The
cause was shirone's `deploy.yml` carrying a hardcoded sync list that omitted
`LICENSE`, a file added here on 2026-11-01.

**Root cause**

A fallback page is served with status `200`, so the status code carries no
information about whether the path exists. The mirror's file list was maintained by
hand, so any file added upstream was invisible to it.

**Fix**

- `zreflect/check_site_lang.py` — H6 judges by content fingerprint: request a path
  with a unique suffix that cannot exist, take its body sha256 as the fallback
  fingerprint, then compare every link's body against it. Equal means dead.
  Unreachable is also a failure (two retries to absorb a transient drop).
  `SC_HTTP_PROXY` is supported so a local TLS reset is distinguishable from a dead
  link.
- `scripts/build-site.py` — `files.json` published as the exact artifact list, with
  a self-test asserting `files.json` equals the artifact file by file. Builder
  self-test 13 to 14 PASS.
- Letter `Shirone-personalized/mail/009` — two options: read `files.json`, or add
  `LICENSE` by hand.

**Reproduce**

```bash
SC_HTTP_PROXY=http://127.0.0.1:2080 python3 zreflect/check_site_lang.py --online
python3 scripts/build-site.py --selftest
```

## 2026-11-02 — Third source subscribed; a transient network error was judged as absence

**What happened**

`Octave-Full-Wasm` subscribed with `kind: "engine"`. The value comes from the
content contract (`v3-absorption-audit.md:63`, the three values `src` / `pre` /
`engine`); no new vocabulary was introduced.

Non-free policy as ruled: collect under G1–G7 with no extra policy layer.
`wasm64ip` linked a non-free Rust sort kernel (`LicenseRef-nonfree-rust-sort-kernel`);
the shape was valid, so it was listed, and free versus non-free judgement was left
to the reader. (This declaration was withdrawn the same day; see below.)

Independent re-run by zero download: 463 cases, 0 problems. In the first 5 MiB of
`wasm32`'s `octave.wasm`, `atomics` occurs 0 times, confirming their no-atomics
claim. A separate tag `wasm32-11.3.0-1ed3e528` carries no `manifest.json` and was
correctly excluded by G1.

Also fixed a real robustness defect: on first derivation `forge-geometry` was
written into `excluded` because of one `No route to host`. That judged an
unreachable probe as absence of the release.

Shirone `026`: the `LICENSE` dead link on both channels was fixed (Cloudflare by an
extension allowlist, EdgeOne by the hand-written list); both now read `files.json`.
Their `stage-static-tree.py` closed two holes in the sample code (a manifest entry
missing from the source must fail; `../` traversal rejected). They dropped
`rm -rf __pycache__` after removing the symptom source. Their Cloudflare allowlist
boundary (extensionless names accepted only for `LICENSE`, `NOTICE`, `COPYING`,
`AUTHORS`) was adopted on security grounds: clients inside the contract request
only the names given verbatim by `manifest.file`, and those names always carry an
extension.

**Root cause**

The deriver treated any fetch exception as a verdict about the release, so a
transport failure produced the same output as a missing artifact. One observation
was allowed to decide a negative.

**Fix**

- `scripts/sync-catalogue.py` — three retries with a 2-second pause before a
  network failure is recorded, and the recorded reason says it was a network
  failure, not a manifest defect. Reverse test case added: two failures then a
  success must admit the release. Deriver self-test 20 to 21 PASS.
- `site/sources.json` — the third source entry.

**Reproduce**

```bash
python3 scripts/sync-catalogue.py --selftest
python3 scripts/sync-catalogue.py --dry-run
```

## 2026-11-02 — Two retractions: a non-free declaration withdrawn, the dead-link gate widened

**What happened**

1. `Octave-Full-Wasm` withdrew its non-free declaration (`002`). `wasm64ip` had
   been marked `AGPL-3.0-or-later AND LicenseRef-nonfree-rust-sort-kernel`; the
   marking was theirs and it was wrong. The Rust sort kernel is this repository's
   own `#![no_std]` source: `build/113/rust/Cargo.lock` lists one package,
   `rs_sort`, with no third-party crate. All three products are
   `AGPL-3.0-or-later`. They had read the maintenance note "non-free" — meaning
   the upstream community does not accept the patch — as a license term.

   The defect on this side: the previous letter stated the license had been
   checked item by item. Only the shape had been checked, not the content, which is
   exactly the criterion just written into v1.1 §4.5. Re-derived: `LicenseRef`
   count is zero. They renamed `NONFREE-RUST-KERNEL.md` and rewrote it rather than
   deleting it.

   They kept `wasm32-11.3.0-1ed3e528` (no manifest) under option C: it is a
   downstream chain that has been running outside for a week and deleting it breaks
   the chain. Staying in `excluded` permanently is a record, not a defect.

2. Shirone open-sourced `audit-static-channels.py` (`027`, 6 self-tests), an
   independent implementation with an extra check P4 that the artifact is
   byte-identical to the source. They identified the real boundary of H6: H6
   traversed the relative links in the HTML, so any file present in the artifact
   but not referenced by the HTML was never checked. `files.json` and
   `index.html` themselves are in no `href`.

   Their first probe version treated `404` as "channel unavailable" and misjudged
   two healthy channels — the same failure shape as the retry defect above.

**Root cause**

For the license: a maintenance term and a license term were the same word, and
nothing in the shape check can distinguish them. For H6: the traversal source was
the rendered page rather than the published artifact, so the check covered only
what the page happened to link.

**Fix**

- `scripts/sync-catalogue.py` — re-derived; `LicenseRef` count zero.
- `zreflect/check_site_lang.py` — H6 now takes each channel's own `files.json` as
  the traversal source. Coverage went from 15 to 16 files and a channel missing a
  file is now detectable. Three channels: checked=16, dead=0.
- Their probe: `4xx` and `5xx` are recorded as valid observations and only
  transport-layer faults raise, so an unreachable probe is not reported as absence.

**Reproduce**

```bash
python3 zreflect/check_site_lang.py --online
python3 scripts/sync-catalogue.py --dry-run
```

## 2026-11-02 — Derived catalogue pointed at a deleted tag for up to six hours

**What happened**

Two letters arrived unattended.

`host 003`: two tags withdrawn, `octave-11.3.0-three-products-36b951e` and
`octave-11.3.0-r2`, replaced by `octave-full-wasm-v0.1.0` (`manifest.id =
Octave-Full-Wasm/v0.1.0`, 82 assets, schema 3, pure AGPL). The cause was a version
axis rename: the tag had to be distinguishable from the GNU-maintained octave,
whose tag is `release-11-3-0`. The naming convention now aligns with LLVM
(`v0.1.6`). They confirmed the two builds are byte-identical and differ only in
`manifest.id` and entry order, so neither was more compliant and both were
withdrawn.

`extra-content 007`: in the live catalogue both master-repository bases returned
`404` — old tag deleted, new tag not yet picked up. Their mechanism explanation was
correct: derivation ran on a six-hour schedule, so after an upstream delete-and-
publish the catalogue pointed at a dead tag for up to six hours. Not an
implementation bug.

Handled here end to end:

- Re-derived: 17 listed, 6 excluded. The old tags are gone and
  `Octave-Full-Wasm/v0.1.0` is listed.
- All 17 bases checked one by one: `base + manifest.json` returns `200` for each.
- Cron changed from `*/6` to `*/1`, shrinking the window from six hours to one.
- New gate H7: every listed base must serve `manifest.json`. Negative test used the
  live old catalogue plus the deleted tags and reported exactly three of nineteen
  bases unreachable, catching both real stale tags of the moment.

Rejected suggestion: extra-content proposed adding "the catalogue is a fallback
list" to the canonical client algorithm. The protocol is not changed; the gap is
handled on the derivation side by H7 plus the shorter window.

**Root cause**

The catalogue's freshness window was longer than upstream's delete-and-publish
interval. No gate checked that a listed base still resolves, so a stale pointer was
indistinguishable from a live one.

**Fix**

- `zreflect/check_site_lang.py` — H7. Applies to `releases` only; tags in
  `excluded` are allowed to be unreachable, which is why they are excluded.
- `.github/workflows/sync-deploy.yml` — `cron: '17 * * * *'`.

**Reproduce**

```bash
python3 zreflect/check_site_lang.py
python3 scripts/sync-catalogue.py --dry-run
grep -n "cron" .github/workflows/sync-deploy.yml
```

## 2026-11-03 — Cloudflare channel moved to the root path; failure ownership split

**What happened**

Reported from the user side: Cloudflare now serves from `/`, not `/static`.
Measured and confirmed: root path `index.html` and `files.json` return `200`, and
everything under `/static/` returns `404`. `site/channels.json` `base` updated from
`.../static/` to `.../`; the listing in `README.md` and the state file follows. H6,
H7 and the deployment verification all read that config, so they follow
automatically.

Earlier state, kept as record: `static.mango-mesa.ccwu.cc/static/*` returned `404`
for everything (`LICENSE` returned `301`) while at the same moment
`isui.ren/static/*` returned `200` for everything. The boundary was in the
Cloudflare Worker, not in the source.

Three explanations were excluded, each with its own re-run:

- not the artifact — the `deploy` branch had all 17 files including `files.json`;
- not the cache — `?ts=` bypass returned `404` as well;
- not the origin target — raw `deploy/files.json` returned `200`, `count: 16`.

The anomaly was extensioned paths returning `404` and extensionless paths
returning `301`. An extension allowlist cannot explain that shape; it matched a
Worker route for `/static/*` never being mounted.

Related design defect fixed at the same time: H6 blocked the release on any channel
failure, so a third party's outage could stop this repository's artifact from going
live. `site/channels.json` gained an `owned` field; only an owned channel
(`github-pages`) blocks a release, external failures are reported as a warning and
are never silenced. Measured: github-pages dead=0, edgeone dead=0, cloudflare
dead=16, warning, `rc=0`.

The same criterion was added to `scripts/verify-channels.py`: previously it waited
for all channels, so one external outage turned the whole workflow red. Channels
with `owned=false` that are not ready now report a warning. Self-test gained a
routing case: 10 PASS / 0 FAIL.

**Root cause**

The channel's base path is configuration, and it had been left at the old prefix
after the platform-side move. For the blocking behaviour: the release verdict was
computed over all channels without distinguishing who operates each one, so
another party's availability was a precondition for this repository's release.

**Fix**

- `site/channels.json` — `base` for Cloudflare set to the root, `owned` field added
  per channel.
- `zreflect/check_site_lang.py` — H6 routing by `owned`; external failures reported,
  never blocking.
- `scripts/verify-channels.py` — same routing; self-test case added.
- Letter `Shirone-personalized/mail/011` with the three exclusions and their
  re-runs.

**Reproduce**

```bash
python3 scripts/verify-channels.py --selftest
python3 scripts/verify-channels.py --expected site/dist --channels site/channels.json
curl -s -o /dev/null -w '%{http_code}\n' https://static.mango-mesa.ccwu.cc/index.html
curl -s -o /dev/null -w '%{http_code}\n' https://static.mango-mesa.ccwu.cc/static/index.html
```

## 2026-11-03 — Fourth source subscribed; trailing slash appended to every id

**What happened**

`OpenModelica-Full-Wasm` subscribed with `kind: "engine"`, the same value as
`Octave-Full-Wasm`; the `kind` vocabulary belongs to the content contract and was
not extended.

Real derivation: 19 listed, 7 excluded. Two omc products are listed:
`v0.2.0-wasm32` (`AGPL-3.0-or-later`) and `msl-4.1.0-maint.om` (`BSD-3-Clause`).

Verification is zero-download: each `chunks[].sha256` compared against the GitHub
platform `digest`, with no reliance on a local copy.

One real bug fixed: `verify_entry` returned
`"%s/%s" % (man.get("id") or ..., "")`, an expression whose second format
argument is always the empty string, so the returned id carried a trailing slash:
`OpenModelica-Full-Wasm/v0.2.0-wasm32/`. The only caller of `verify_entry` passes
the returned entry through `fix_entry`, which rewrites `id` from the manifest, so
the malformed value did not reach the published catalogue; the expression itself
was wrong and latent. omc is the first repository using the `<repo>/<pkg>-<ver>`
shape with dots and hyphens; the first three sources did not expose it.

A fetch trap hit during this work: `gh release download <tag> -p manifest.json`
returns a stale or cached copy whose content sha does not match the platform
`digest` (`dd938745...` versus `1794718f...`). That is exactly what G2 caught. The
correct fetch is the assets API octet-stream.

Their proposed contract-change notification mechanism was accepted in all four
parts, implemented as a mechanical check rather than a letter sent at each
finalization: a `contract.json` fingerprint plus a `contract_selftest` expected
value in `sources.json`. `contract.json` is to be implemented with the next
substantive change.

Ruling on their question: the two `supply-msl` releases (one in extra-content, one
in omc) legitimately coexist. A different `id` means two releases; the protocol
does not de-duplicate blobs (v4 §2.3, the apt criterion); attribution is not
exclusivity.

**Root cause**

The id string was built as `"%s/%s" % (value, "")`: the second format argument was
a literal empty string, so the separator was appended unconditionally. The value
`manifest.id` itself is already complete.

**Fix**

- `scripts/sync-catalogue.py` — `"id": str(man.get("id") or ("%s/%s" % (repo, tag)))`;
  `manifest.id` is already the complete id.
- `site/sources.json` — the fourth source entry.

**Reproduce**

```bash
python3 scripts/sync-catalogue.py --dry-run
python3 scripts/sync-catalogue.py --selftest
gh api repos/ArchivalEra/OpenModelica-Full-Wasm/releases --jq '.[].tag_name'
```

## 2026-11-04 — EdgeOne site line moved host; and I broke the live site with a probe push

**What happened**

shirone removed the intermediate layer on the apex domain: `isui.ren/static` no
longer serves this repository's artifact. Measured on every path under it — the
answer is `200` plus isui.ren's own landing page, not the site's bytes. The
contract site now lives on `static.isui.ren`, an EdgeOne accelerated domain
(CNAME to `static.isui.ren.eo.dnse4.com`) whose rule engine splits by path: site
paths to the `deploy-eo` branch on raw.githubusercontent.com, release paths to
github.com. One host serves both the site tree and the release bytes.

Three things in this repository still pointed at the old host, and each would have
made the pipeline report a falsehood:

1. `site/channels.json` still listed `https://isui.ren/static/` as the EdgeOne
   site line. The acceptance gate would have probed a host whose every path
   answers `200` with a landing page — and the content-fingerprint criterion
   would have read that landing page as the site, so the gate would have gone
   green on a dead channel.
2. `sync-deploy.yml` still dispatched shirone's `deploy` workflow. That workflow
   rebuilds isui.ren's own `/heart/` application, not this site. It was not
   harmful, but it was not this site's update either.
3. The online acceptance ran 6 rounds of 20 s. Both site lines cache with
   `max-age=300`, so an update can sit behind the cache for longer than the gate
   was willing to wait. A short wait reports "the channel did not pick this up"
   when the truth is "the cache has not expired".

The second half of this incident is mine. To measure EdgeOne's update latency I
pushed a probe file to `deploy-eo` with `git push --force`. `deploy-eo` is the
whole tree, not a directory: my probe commit contained one file, so the force-push
replaced the entire site tree with that one file. The live site went to `404` on
every path. I then pushed a second "restore" commit by hand, which is the same
mistake a second time — the branch is owned by the pipeline, not by me.

**Root cause**

Two independent mistakes, one shared shape: **a measurement was made by writing
to the thing being measured.**

- The latency probe needed to know when EdgeOne picks up a changed file. Writing
  that probe into the live artifact branch was the only way to do it, and it
  meant the experiment destroyed its own subject.
- The pipeline is the only writer of `deploy-eo`. The moment I push to it
  directly, the branch stops being the pipeline's output and becomes my
  scratchpad — and the live site follows it, because EdgeOne pulls that branch
  directly.

**Fix**

- `site/channels.json` — the EdgeOne site line is `https://static.isui.ren/`.
  The annotation records why, with the measurement that established it.
- `.github/workflows/sync-deploy.yml` — the dispatch step is deleted. EdgeOne
  pulls `deploy-eo` directly, so the branch push *is* the update. Measured: a
  changed path appeared on the edge within 10 s of the push, with no dispatch.
  The online acceptance now runs 12 rounds of 30 s, which covers the measured
  300 s cache TTL.
- Recovery: the site was restored by **changing `main` and letting the pipeline
  rebuild the branch**, not by hand-pushing to `deploy-eo`. That is the only
  correct repair — the branch is an output, and outputs are regenerated, not
  patched.

**Reproduce**

```bash
SC_HTTP_PROXY=http://127.0.0.1:2080 python3 zreflect/check_site_lang.py --online
SC_HTTP_PROXY=http://127.0.0.1:2080 python3 examples/verify-three-lines.py
gh api repos/ArchivalEra/Static-Contract/commits/deploy-eo --jq '.sha'
curl -s https://static.isui.ren/catalogue.json | python3 -c "import json,sys;print(len(json.load(sys.stdin)['releases']))"
```

**Measured after the fix**

```
H6 edgeone   checked=6 dead=0 unreachable=0
H6 cloudflare checked=6 dead=0 unreachable=0
three-line: PASS cf / PASS eo / PASS base_proxy  (3/3)
18/18 releases: both roots 200 + byte-identical manifest + sha matches catalogue
```

**Lesson**

A pipeline exists so that the artifact is never edited by hand. The moment a
measurement requires writing to the artifact, the measurement has become the
edit. Measure by pushing to `main` and letting the pipeline run — slower, but it
cannot destroy the thing it is measuring.
