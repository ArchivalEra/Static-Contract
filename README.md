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
| `worker/` | Cloudflare site-line Worker (`static.mango-mesa.ccwu.cc`) — absorbed into this repository from the course repo on 2026-11-06: site artifacts are fetched at runtime from `deploy-cf`, release bytes are proxied (fetch follows the GitHub 302, with Range passthrough), and every asset response carries ACAO + CORP + nosniff. Deploy with `cd worker && npx wrangler deploy`, or push `worker/**` to run `worker-deploy.yml` (skips when the secrets are absent). The three legacy userscript routes were removed by ruling |
| `questions/` | Open-questions ledger (`05`: zstd vs gzip measured on the real EdgeOne link) |
| `STATE.md` | Live state (Einfacht format: states only what is true now, with the rerun command next to each assertion) |
| `maintaince.md` | Direction and map (maintenance boundary / routine / red lines) |
**Fetch roots** (canon v1.1 §5.3, ruled 2026-11-04): `base` = cluster mirror,
tried first; `base_proxy` = GitHub origin (`https://github.com/...`), the fallback when
`base` is unreachable. Same path shape, host only.

**One deploy branch per mirror** (ruled 2026-11-04): `deploy-eo` (base →
`static.isui.ren`) and `deploy-cf` (base → `static.mango-mesa.ccwu.cc`). Each site line
fetches from its nearest mirror. The two catalogues differ only in the `base` host.
Adding a mirror is one matrix row plus one branch. Each matrix job verifies only its own branch and mirror, so a branch never blocks on a sibling. `channels.json` lists the site lines a reader
can reach; deploy branches are artifacts kept by the matrix in `sync-deploy.yml`, not
channels.

**Published surface is seven files** (shelf plus contract only): `index.html`, `files.json`, `catalogue.json`, `sources.json`, `LICENSE`, and the two current contract documents. Everything else in this repository — live state, maintenance guide, incident log, rulings, tools, superseded drafts — stays in the repo and is never published. Gate H9 enforces the whitelist in both directions; H6 checks each channel against its own file list.

| `site/` | Metadata site source: `sources.json` (subscription list) + `channels.json` (acceptance channels, **also feeds page rendering**) + `catalogue.json` (fallback source, **must stay empty**) + `catalogue.live.json` (derived file written by CI, gitignored, read by gates). Page shape follows he.net: plain XHTML 1.1 + CSS, zero JS, zero external resources. **HTML, public catalogue fields, and published `.md` are English-only** + **deprecated contracts must be marked** + **link integrity** (H5 inside the artifact; H6 an online fingerprint check across every channel's full `files.json`, **with `owned` deciding whether a failure blocks publishing**; H7 catalogue base reachability — `verify-channels.py` applies the same criteria, only warns on external channels, honours `SC_HTTP_PROXY`, and defeats "200 at a fallback page"). **Page data is fully automatic**: self-test counts come from a live `--selftest`, the channel table from `channels.json`, listings from the derived catalogue, and the footer carries `© 2026 ArchivalEra` |
| `zreflect/` | Einfacht fact-system platform (vendored from `vendor/Einfacht` at `6e4e6e8`) + this repository's data-layer collector; ledger `FACTS.json` (**do not hand-edit** — run `zreflect/facts.py`) |
| `reflect-hooks/` | Git hooks and the knob carrier (install: `sh reflect-hooks/install.sh`; pre-commit re-renders machine blocks and runs every gate in the commit phase) |
| `mail/` | Cross-repository mail **inbox** (rules in `mail/README.md`: append-only, numbers increase, delivery ≠ commit). Incoming letters live here; an outgoing letter is delivered into the recipient's `mail/` and is recorded here only as one index row — this repository's `mail/` is not an outbox. |
| `examples/` | Reference client, **TypeScript** (`fetch-concurrent.ts` — both consumers run in a browser): one entry point, `openRelease`, returning a handle with `read(entry)` / `readAll()`. Concurrency, cross-source continuation, per-chunk verification and per-chunk decoding are all behind that line; the caller never sees a chunk. **Retry policy is per-root: 3 attempts of 5 s each by default, `base` first and `base_proxy` only after that budget is spent** — measured, the mirror's failure mode is a request that stops answering, so a long deadline is the wrong tool. All three link-dependent values (`concurrency`, `attemptsPerRoot`, `attemptBudgetMs`) are overridable through `OpenOptions`, and the budget is derived per chunk when not given: a flat budget encodes one link's speed into every consumer. **`concurrency` defaults to 2 because the reference mirror throttles above roughly 10–15 MiB in flight**, and `chunkSize` is 5 MiB — 2 x 5 = 10 stays under, 3 x 5 = 15 does not. That ceiling is the mirror's, not the contract's; a release with smaller chunks can run wider. A status and a stall are classified apart (`ContractError.status`) — a 404 will not change on a retry, and it must not demote a healthy mirror in the shared ledger. `close()` releases the abort listener and in-flight work; `onEntry` reports progress. Codecs are an **open vocabulary** (canon V9): anything `DecompressionStream` accepts works, anything else is registered once with `useDecoder` (and can be unregistered with `forgetDecoder`, so tests can observe the no-decoder path). **The consumer picks the chain** via `codecPreference`, tried before the manifest's order and falling back to it — a preference, not a requirement, so asking for a codec a release does not ship still succeeds. That is a cost decision the contract deliberately leaves to the client: measured, forcing `identity` over the default zstd path moves the same payload from 22.09 MiB to 109.23 MiB on the wire. The manifest is validated once at the only entry point: schema, V1 names, V5 contiguous parts **and equal chunk counts across an entry's codecs**, V6 chunk size, and **V11 license shape** — the last one is a safety property, since `license.url` becomes an `href` and a `javascript:` value would be injected into every trusting consumer. Plus `test/` (**34 offline cases**, fake `fetch`, no network — the client exposes no test hooks and none were added; every case goes through the public interface) covering the five traps that were hit for real while building this client, and `verify-three-lines.py` (whose edge the bytes crossed). **`codecPreference` accepts a per-entry callback** (a 29 MB wasm and a 464 KB js in one release can make different cost decisions), and signal composition no longer depends on `AbortSignal.any`, so older Safari works. **The CF line's Worker lives in `worker/` in this repository** (single-file `worker.mjs`: OPTIONS preflight, release-byte proxy that follows GitHub's 302 with Range passthrough and 1-year immutable caching, and runtime origin-pull of site artifacts from `deploy-cf`; every response carries ACAO + CORP + nosniff, which is what Octave-UI's COEP context required). `worker-deploy.yml` deploys it on `worker/**` pushes (verified: a real `wrangler deploy` with the Cloudflare secrets, not the skip path) and skips explicitly only when they are absent. **No benchmark script ships**: `fetch-concurrent.ts` is the client, so a measurement is the client plus a stopwatch, and wire bytes are a sum over `chunks[].bytes` in the manifest rather than something to intercept — measured, the declared total and an intercepted `fetch` agreed to within 0.03 MiB. **A consumer whose decoder bytes may not persist should follow the `examples/README.md` recipe** (build-time sha pin, `no-store` plus a per-document instance-level nonce, verify before blob-import, one promise per document, remember failures). **The suite is verified by mutation, not by passing**: breaking the client seven ways (skip decode, no retry, ignore the ledger distinction, drop the name whitelist, let `close()` not stop reads, ignore the consumer's codec chain, ignore the per-entry callback) turns it red each time. CI runs `tsc --noEmit` and the suite on every push. Repository only, not published. |
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

**Deployment (one build, one branch per mirror)**: push `main` → the `sync-deploy` workflow
runs a matrix → each entry force-pushes its own orphan branch (`deploy-eo`, `deploy-cf`) →
the matching mirror reads it (the Cloudflare Worker fetches `deploy-cf` at runtime; EdgeOne's
CI takes `deploy-eo` as a static tree). The two branches differ only in `catalogue.json`'s
`base` host.

Channels: `https://static.mango-mesa.ccwu.cc/` (Cloudflare) ·
`https://static.isui.ren/` (EdgeOne, China-facing host). Header semantics (ETag / `304` /
Content-Type) live on the site side.

**The EdgeOne site line moved host on 2026-11-04**: it was `https://isui.ren/static/`
and is now `https://static.isui.ren/`. The apex-domain intermediate layer was removed
upstream — every path under `isui.ren/static/` now answers `200` with isui.ren's own
611 B landing page, not this repository's artifact. `static.isui.ren` is an EdgeOne
accelerated domain whose rule engine splits by path: site paths → the `deploy-eo` branch
on raw.githubusercontent.com, release paths → github.com. So one host serves both the
site tree and the release bytes, and pushing `deploy-eo` *is* the update — no dispatch
step is needed (measured: a new path appeared on the edge within 10 s of the push).

**GitHub Pages was removed from the channel list on 2026-11-04.** It is a pure static host
with no server-side programmability, so it cannot proxy or 302 release bytes: `fetch` does not
execute HTML/JS redirects, and `_redirects` is not supported (measured 404). Keeping it listed
made the acceptance gate report a permanent, unfixable red — the honest thing is to remove it
rather than let a channel look available while it can never carry bytes. The Pages site itself
was **deleted**, not merely unlisted: a mirror that stops updating still answers `200` with a
stale catalogue, which is worse than a `404`.

**The EdgeOne fetch defect is closed (2026-11-04).** It took three rounds to characterise, and
the record is kept because the *way* it was misdiagnosed twice is the reusable part. Same
existing asset, plain GET, no query string, throughout.

- *Round 1* — 20 GETs produced 8 failures: `server: TencentEdgeOne`, `via: 1.1 varnish`, body
  `404: Not Found` (14 B). The site rule `site-from-deploy-eo` (condition `host /*`, matching
  every path) sat *before* the release-byte rule, so fetch requests were captured by the site
  rule and sent to `raw.githubusercontent.com`.
- *Round 2* — after the provider moved the release rule to priority 1, that mode dropped to
  0/20 but 17/30 still failed, now `server: github.com` with a 9-byte `Not Found`. My reading at
  this point — "other edge nodes are on a mid-edit rule version" — **was wrong**: every success
  and every failure came from the same PoP, and `x-served-by` is merely absent when a request
  never reaches the blob layer. Absence of that header is not evidence of a different node.
- *Round 3* — `eo-cache-status` separated the cases perfectly: `HIT` ⇒ 200, `MISS` ⇒ 404. That
  pointed at the origin fetch, and the real cause was **rule merging, not rule order**: EdgeOne
  merges matching rules, and a lower-priority rule's action still applies unless a
  higher-priority rule declares that same action. `site-from-deploy-eo` declares
  `UpstreamURLRewrite` to `/ArchivalEra/Static-Contract/deploy-eo/$1`; the release rule did not
  declare it, so release requests were rewritten onto the deploy branch path and github.com
  answered 404. The fix is an explicit identity rewrite (`^/(.*)$` → `/$1`) in the release rule.
  Confirmed by A/B: remove it and fetch 404s; restore it and fetch 200s.

**Verified after the fix** — each root fetches the whole release on its own, with no fallback:

```
EO  (static.isui.ren)            14/14 entries, 122,967,501 B, every entry sha verified,  97.8 s
CF  (static.mango-mesa.ccwu.cc)  14/14 entries, 122,967,501 B, every entry sha verified,  63.1 s
base_proxy (github.com)          14/14 entries, 122,967,501 B, every entry sha verified
```

Three-line edge acceptance: 3/3 PASS (`cf-ray` / `eo-*` / Azure `x-ms-*`). The residual
failures seen while probing are `curl` exit 28 (connect timeout) with no response at all — a
transport drop on this host's egress, distinct from the 404s, which always carried headers.

Judgement rule worth keeping: identify a line by its **`server` header plus cache state**, never
by status code. `Windows-Azure-Blob` is the release rule working; `TencentEdgeOne` was the site
rule; `github.com` was the release rule reaching the wrong upstream path. Letters
`mail/read/041`–`044` and the outgoing replies (provider `mail/007`–`010`) carry the measurements.

**Three roots, each independently sufficient** (measured 2026-11-04). The verification that
matters sets `base_proxy` to `null`: with a fallback configured, a broken `base` is invisible
because the client silently succeeds through GitHub. With no fallback, each root above fetched
all 14 entries of `LLVM-wasm/v0.1.6` and matched every entry's declared sha256 — EO 97.8 s,
Cloudflare 63.1 s, GitHub likewise. That is what "three independent lines" means here: any one
of them can serve a release alone.

**License URL content**: the deriver fetches each `license.url` and warns (stderr, never fatal) when the body is under 200 characters or names no known license. V11 checks shape only, so `200 but empty` would otherwise pass.

**Online acceptance**: `scripts/verify-channels.py` checks, after deployment, each channel against
**this build's artifact fingerprint** (`STATIC-CONTRACT-BUILD <hash>` written into `index.html`) and
`catalogue.verified_at`. The criterion anchors to the artifact itself, **not to whether the channels
agree with each other** — when every channel is stuck on an old artifact, agreement holds just as
well (that is exactly how I misjudged it once on 2026-11-01).

> **Fixed (2026-11-01, shirone `mail/006`)**: EdgeOne used to reverse-proxy Cloudflare's Worker
> inline snapshot and did not follow the deploy branch (measured: two builds behind). Each leg now
> deploys independently: CF reads `deploy-cf` at runtime, and EO's rule engine reads `deploy-eo`
> from raw.githubusercontent.com; the count of `cf-ray/nel/report-to` in EO response headers is 0.
> **`deploy-eo` / `deploy-cf` are the artifacts and the correct entry point for consumers** — do not
> run `build-site.py` (it needs an already-derived catalogue; run on its own it only produces the
> empty fallback).
> **EO updates need no dispatch** (2026-11-04): EO pulls the `deploy-eo` branch directly, so the
> branch push *is* the update. The old dispatch step (and `HEART_DISPATCH_TOKEN`) is gone; it
> rebuilt isui.ren's own `/heart/` application, which is not this site.
> The original single `deploy` branch was **deleted** on 2026-11-04 once both mirrors had switched.
>
> **Never push to `deploy-eo` or `deploy-cf` by hand.** They are pipeline *outputs*: a force-push
> from a terminal replaces the entire tree, and the live site follows the branch immediately. On
> 2026-11-04 I broke the live site exactly that way — a latency probe force-pushed as a commit
> containing one file, so the whole site tree became that file and every path went to `404`.
> The repair is to change `main` and let the pipeline rebuild the branch, not to push a
> "restore" commit: the branch is regenerated, never patched. Full account in `docs/incidents.md`.
> If you need to measure edge behaviour, measure it through `main` — never by writing into the
> artifact.

CI: the `gates` workflow runs the same criteria as the local hooks (fact-block reconciliation + the
full gate roster + module self-tests); the environment explicitly installs `zstandard` (the
instrument the generator's self-test needs) and sources `reflect-hooks/Einfacht.env` (the source of
the knobs).

Current state and pilot acceptance criteria: `STATE.md`; direction, boundaries, and routine:
`maintaince.md`.
