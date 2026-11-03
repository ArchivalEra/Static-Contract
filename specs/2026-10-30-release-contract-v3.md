# Release Contract v3 · First Generation (finalization candidate)

> ## DEPRECATED — historical, not authoritative (marked 2026-11-02)
>
> Superseded. Current authority: v4 (V1–V10) plus v1.1 (V11, schema 3).
> Kept for rejection criteria only.
>
> This document was **never delivered, never entered any schema, never promoted**.
> Authority paths: `specs/2026-10-30-release-contract-v4.md` (V1–V10 base clauses)
> and `specs/2026-11-01-release-contract-v1.1-license.md` (V11 license, schema 3).
> Do not implement against this document.

> ## Historical document — superseded, not authoritative (marked 2026-11-01)
>
> **Current authority = v1** (repo copy `specs/2026-10-30-release-contract-v4.md`; the authoritative text lives in
> `ArchivalEra/Static-Contract`). v3 is the **third of four design-it-twice rounds**; it preserves the structure and
> criteria of that time. **Do not implement against it.**
>
> **Special note: R1–R4 (§4.1) did not make it into v1.** No hedging or concurrency criterion can be found anywhere
> in the current v1 contract (`grep -c "hedge|R2|R3"` ⇒ 0). Today R1–R4 stand as **implementation advice and measured
> data**, not as contract invariants — concurrency and hedging are consumer-side implementation strategies; what v1
> governs is "what the manifest looks like and how bytes are fetched".
>
> **Among them, R3 ("no hedging inside EdgeOne middleware") was overturned by Shirone himself on 2026-10-31**:
> a retest was valid 20/20 (slowest 4.75s; the 17.5s fallback ceiling was never triggered even once). See his `118`
> erratum and this repo's `131` reply.
> **A single measurement does not deserve a "prohibition"-level conclusion** — this is exactly an instance of this repo's discipline 5 (assertions have a lifecycle).

---

> **Status (at the time)**: v3 = the v2 final draft + R1–R4 as confirmed by Shirone in `117` + one size-metric erratum (I was wrong; corrected).
> **Two-repo consensus reached** (my `116` / Shirone `117`): R1–R4 finalized verbatim, the first generation ships only
> zstd+gzip+identity, `chunkSize` defaults to 5 MiB and is configurable with an upper bound of ≤10 MiB.
> **Still awaiting user approval to begin the pilot** (§10, step 3).
>
> **v1 → v2 changes (all from user corrections plus my own measurements)**:
> 1. **Cut the entire Range family** — pre-chunking makes Range unnecessary. The user pointed out that the end user
>    only issues one standard request with very few headers. The measured browser PoC already proved that plain
>    GET × concurrency suffices.
> 2. **Cut the seek table / `range.basis` / `granularity`** — those were my own inventions, violating the rule
>    against inventing too much of one's own machinery.
> 3. **`variants` became an ordered array** (the fallback chain is **data**, not a code branch): adding a new format
>    = adding one array item, with not a single character of the schema changed. This is the mechanism that lets the
>    protocol "never need updating".
> 4. **The first generation enables only zstd + gzip + identity, not br** (user ruling: it is **not that br is
>    unsupported, but that the first generation does not enable it**).
> 5. **Format negotiation handed back to HTTP** (`Accept-Encoding`) — **not our concern**.

---

## 0. In one sentence

> **One release = one immutable directory. `manifest.json` is the only entry point.
> All bytes are plain files fetched with plain GET.**
>
> The consumer's only action sequence: `fetch(manifest)` → pick one it can decode in `variants` order → fetch chunks concurrently → concatenate → verify.
> **No Range, no conditional requests, no custom headers, no negotiation protocol.**

---

## 1. Measured evidence (every item is a re-runnable criterion)

### 1.1 Browser decompression capability (this decides who can be the fallback)

```
DecompressionStream('gzip')     # native
DecompressionStream('deflate')  # native
DecompressionStream('br')       # unsupported
DecompressionStream('zstd')     # unsupported
```

Therefore **gzip is the only zero-dependency fallback**; both zstd and br require an external decoder.

### 1.2 Decoder size

| Codec | Decoder | Distribution flavor | Raw | gzip -9 | Form criterion |
|---|---|---|---|---|---|
| gzip | browser native | — | 0 | **0** | `DecompressionStream('gzip')` supported |
| **zstd** | `fzstd@0.1.1` | **ESM** | 24,407 | **6,840** | `exports.import=esm/index.mjs`; the esm build has zero `import`s and empty `dependencies` |
| zstd | same as above | UMD | 8,394 | 3,860 | Only when the consumer uses UMD |
| br | needs wasm (e.g. `brotli-wasm`) | — | ~100KB+ | not measured | Not enabled in the first generation |

**Size-metric erratum (2026-10-30; Shirone corrected me in `117`, I re-verified and confirmed)**:
The official README's "8kB minified and 3.8kB after gzipping" refers to the **UMD** build.
**The actual burden for ESM consumers is 6,840 B (after gzip), not 3,860 B — a 77% difference.**
I had previously taken the UMD number for the ESM number; that was wrong. This contract consistently counts **ESM = 6.8KB**.

Rerun:
```bash
npm pack fzstd && tar xzf fzstd-0.1.1.tgz
for f in esm/index.mjs lib/index.js umd/index.js; do
  printf '%-16s raw=%-7s gz9=%s\n' "$f" "$(stat -c%s package/$f)" "$(gzip -9 -c package/$f | wc -c)"
done
# => esm 24407/6840 · lib 24454/6857 · umd 8394/3860
```

### 1.3 Compression/decompression for the three codecs (74.5MB wasm, 5MiB × 15 chunks)

| Codec | Pre-chunked total | Compression time (8 cores parallel) | Decompression time | Decompression throughput |
|---|---|---|---|---|
| **zstd-19** | **15,349,112** | **3.7s** | **0.07s** | **1022 MB/s** |
| gzip-9 | 20,908,462 | 5.0s | 0.21s | 363 MB/s |
| br-q11 | 14,332,389 | 21.5s | 0.16s | 459 MB/s |
| identity | 74,579,404 | — | — | — |

**Reading**:
- zstd is **26.6%** smaller than gzip, **2.8×** faster to decompress, and **0.74×** the compression speed (both are fast enough) ⇒ **first in line**;
- br is only **6.6%** smaller than zstd, but its decoder is 30× heavier and decompression is 2.2× slower ⇒ **not enabled in the first generation, not unsupported**
  (user ruling: reserve the slot, but do not spend first-generation complexity on it);
- gzip has the worst size but **zero dependencies** ⇒ fallback.

### 1.4 Concurrency gain (1.5MB/s per connection + 80ms RTT, simulating a real CDN)

```
conc=1   fetch 11,519ms
conc=2   fetch  5,800ms   1.99×
conc=4   fetch  3,175ms   3.63×
conc=8   fetch  2,354ms   4.89×   ← knee
conc=15  fetch  2,359ms   4.88×   ← no longer rising (15 chunks ÷ 8 = 2 rounds; the second round is not saturated)
```

Therefore **default concurrency = 8** (the knee), and **the concurrency count should not exceed the chunk count**.

### 1.5 PoC passed (real browser environment, full chain)

```
User actions: fetch(manifest.json) → 6 concurrent fetch(chunk) → per-chunk sha → decode → concatenate → global sha
Result: 15/15 chunks, 74,579,404 B, sha 8287589e…b001 == expected   PASS
zstd variant: decoder load 7ms, 606ms end-to-end
gzip variant: 522ms end-to-end (zero decoder)
```

### 1.6 A safety boundary of zstd (must be written into the contract)

Verbatim from the `fzstd` README:

> only supports a maximum backreference distance of **2^25 (32 MiB)** bytes. If you need to
> decompress files with an "ultra" compression level (**20 or greater**) AND if your files can
> be **above 32MB decompressed**, `fzstd` *might* fail to decompress properly.

**Not applicable to our scenario**, because **we chunk**:

```
single chunk = 5,242,880 B (2^23) < 2^25 (33,554,432 B)  ⇒ safe
and per-chunk compression has no cross-chunk backreference anyway ⇒ independent of level
```

Therefore **write it into the contract as an invariant** (see I6): when encoding chunks, `chunkSize ≤ 2^25`, and each chunk **must be compressed independently**.
This simultaneously constrains the freedom of anyone in future who wants to raise `chunkSize`.

---

## 2. Artifact shape (**Release assets, flat naming**)

> **Hard constraint (measured 2026-10-30)**: GitHub Release asset names **get flattened** —
> `gh release upload .../chunks/zstd/000.zst` lands as the asset name **`000.zst`** (the path is lost).
> Therefore you **must not** use slash-bearing paths such as `chunks/zstd/NNN.zst` as asset names.
> **Chunk identity is instead carried by the "asset naming convention"** (table below).

```
Assets of release <repo>@<tag> (all flat, same level):
  manifest.json                        ← the only metadata entry point
  <asset>.zstd.000 … <asset>.zstd.NNN  ← zstd chunks (naming convention: <asset-name>.zstd.<index>)
  <asset>.gzip.000 … <asset>.gzip.NNN  ← gzip chunks
  <asset>                              ← identity original file (fallback)
```

**Why this naming works**: asset names allow `[a-zA-Z0-9._-]`, and the dot is a legal separator.
`OpenModelicaCompiler_bg.wasm.zstd.000` is both flat and parseable (`<name>.<codec>.<i>`).

**Parse rule (consumer)**: `chunks[].file` in the manifest is the **asset name** (a bare filename, no path);
the consumer simply appends it to the base URL. **The base URL is supplied by the distributor (static site / reverse proxy),
not defined by us** — this way the same release can be mounted by any reverse proxy under any path prefix.

**No `latest` alias is provided** — that is an entry point for "perpetual updates". The enforcement of "never update" lives precisely in the tag.

**Whole-file sidecar form (optional, for small artifacts that are not fetched concurrently)**:
```
<repo>/<tag>/<asset>                  ← identity original file
<repo>/<tag>/<asset>.zst              ← whole-file zstd
<repo>/<tag>/<asset>.gz               ← whole-file gzip
```

---

## 3. manifest (full shape, first generation)

```json
{
  "schema": 1,
  "id": "OpenModelica-Full-Wasm/v0.1.0-wasm32",
  "assets": {
    "OpenModelicaCompiler_bg.wasm": {
      "role": "engine",
      "contentType": "application/wasm",
      "bytes": 74579404,
      "sha256": "8287589e…b001",
      "variants": [
        { "codec": "zstd", "decoder": "fzstd@0.1.1", "decoderBytes": 6840,
          "decoderForm": "esm", "totalBytes": 15349112,
          "chunked": true, "chunkSize": 5242880,
          "chunks": [ { "i": 0,
                        "file": "OpenModelicaCompiler_bg.wasm.zstd.000",
                        "bytes": 1275256, "sha256": "…" }, … ] },
        { "codec": "gzip", "totalBytes": 20908462, "chunked": true, "chunkSize": 5242880,
          "chunks": [ … ] },
        { "codec": "identity", "totalBytes": 74579404, "chunked": false,
          "file": "OpenModelicaCompiler_bg.wasm" }
      ]
    },
    "msl-4.1.0-maint.om.zip": {
      "role": "package", "contentType": "application/zip",
      "bytes": 19482938, "sha256": "a97d8d94…8535",
      "variants": [ … ]
    }
  }
}
```

### Multiple assets (added 2026-10-30: the v3 first draft could describe only **one** asset, while OM's release actually has **2**)

**`assets` is a map (asset name → the identity and variants of that asset)**, not a single object.
Rationale (deletion test): delete this layer, and a release containing 2 assets can describe only one ⇒
the consumer either cannot get the other one or has to guess its name. **OM's `v0.1.0-wasm32` currently has 2 assets
(wasm + MSL zip), and the UI `dist` has 21 wasm files** — a single-asset shape cannot cover reality.

**Asset name = baseline name of the Release asset** (chunk asset names add a `.<codec>.<i>` suffix on top of it).
The consumer first reads `assets` in the manifest (to learn which assets exist), then fetches the `variants` of a given asset on demand.

### 3.1 Field necessity (deletion test)

| Field | What breaks if deleted | Keep? |
|---|---|---|
| `bytes` + `sha256` (top level) | The edge has **no Digest header** (measured: `curl -sI` shows no digest at all) ⇒ the consumer **cannot** verify final integrity | **Must keep** |
| `variants` (ordered array) | Only trial and error remains (try zstd, get 404, then try gzip…) = N round trips, and "404" cannot be distinguished from "genuinely absent" | **Must keep** |
| `chunks[].sha256` | The most common error in out-of-order concurrency (a missing chunk, a duplicate, a misplacement) cannot be localized, so the whole thing must be redone | **Must keep** |
| `chunks[].bytes` | Same as above, plus `Content-Length` may be rewritten by an intermediary | **Keep** |
| `chunkSize` | The consumer cannot derive anything beyond "how many chunks in total"; I6 also needs it to judge the safety boundary | **Keep** |
| `codec` | No idea what to decode with | **Must keep** |
| `decoder` / `decoderBytes` | The consumer does not know what to load, or whether it is worth it | **Keep (optional)** |
| `id` | The manifest's own identity; cache key | **Keep** |
| ~~`range`~~ | Range is unnecessary after pre-chunking | **Delete** |
| ~~`seekTable`~~ | Same as above | **Delete** |
| ~~`contentEncoding`~~ | Already expressed by `codec`; HTTP-layer concerns are not duplicated | **Delete** |
| ~~`url` (absolute URL per chunk)~~ | Derivable from `id` + `file` | **Delete** |

### 3.2 Invariants (the validator judges each one; fail-closed)

| # | Invariant | Counterexample |
|---|---|---|
| **I1** | **For each asset**, `bytes`/`sha256` = the bytes and hash of that asset **after all its chunks are decoded and concatenated** | Writing the sha of "some encoding layer"; or mixing two assets into one |
| **I2** | `chunks[].sha256` is the sha of **that encoded chunk's bytes** | Writing the raw sha |
| **I3** | The sum of every `chunks[].bytes` == `variants[].totalBytes` | Declaration does not match reality |
| **I4** | **Each asset's** `variants` is non-empty and contains **exactly one** `codec:"identity"` as the last-resort fallback | All compressed formats (no way out if they cannot be decoded) |
| **I5** | `chunked:true` ⇒ `chunkSize` required and `chunks` non-empty; `chunked:false` ⇒ has `file`, no `chunks` | Half-finished state |
| **I6** | `chunked:true` ⇒ `chunkSize ≤ 2^25` (fzstd safety boundary) **and recommended ≤ 10 MiB** (measured slowdown point lies between 10–20MB; default 5 MiB) + chunks must be **compressed independently** | Chunk > 32MiB with level≥20 ⇒ fzstd may fail to decode; chunk > 10MiB ⇒ falls into the slowdown zone |
| **I7** | `codec` is an **open string** (not an enum) | Adding br/xz/lz4 would require a schema change |

---

## 4. Consumer algorithm (first generation, pseudocode)

```
man = GET <dir>/manifest.json                       // 1 request, cacheable forever
for v of man.variants:                              // in declared order (fallback chain)
    dec = {
      "gzip":  () => nativeGzip,                     // zero cost
      "zstd":  () => import(fzstd),                  // 6.8KB (ESM, after gzip; not 3.8KB)
      "identity": () => null,
    }[v.codec]
    if (dec === undefined) continue                  // unknown codec ⇒ skip (forward compatible)
    try:
        parts = await Promise.all(                   // concurrent, default 8
          v.chunks.map(c => fetch(c.file)            
            .then(r => r.arrayBuffer())
            .then(b => { assert sha256(b) === c.sha256  // per-chunk verify (one bad chunk = refetch only that chunk)
                         return decode(b) })))
        all = concat(parts)
        assert all.length === man.bytes && sha256(all) === man.sha256
        return all                                   // success
    catch: continue                                  // this tier is broken ⇒ next tier
throw NO_USABLE_VARIANT                              // fail only after all tiers are tried (loudly)
```

**Three design points**:
1. **`dec === undefined ⇒ continue`** is the key to **forward compatibility** — when a future manifest contains
   a `codec` we do not recognize (say `xz`), an old client will **skip it and use the next one** instead of crashing.
   **This is where "adding a new format requires no protocol change" actually lands**;
2. **Per-chunk verification + per-chunk retry**: refetch only the bad chunk, not the whole thing;
3. **Two verification layers**: chunk level (against mis-concatenation) + global (against mis-decoding).

### 4.1 Concurrency and hedging clauses R1–R4 (**finalized verbatim by both repos, 2026-10-30**)

> Provenance: a draft proposed in this repo's `mail/116` → Shirone replied in `mail/117` that not a single word needed changing and it was finalized as submitted.

```
R1 (chunk-level concurrency): fetch different chunks concurrently (default 8; measured knee at 8 = 4.89×)
R2 (single-chunk hedging): if a response header for a chunk does not arrive within 1.5s ⇒ fire a second concurrent
                request, first success wins; failure does not settle, keep waiting for the other request;
                theoretically p → p²
R3 (hedging location): R2 may be implemented **only in the consumer**. **Forbidden** inside EdgeOne middleware/worker
                (measured: AbortController cannot abort an already-issued fetch: an 8s timeout returned 200 and ran the full 40s)
R4 (two orthogonal axes): R1 resists bandwidth/concurrency, R2 resists random single-request failure. Both are needed; neither substitutes for the other.
```

**Where R2's criterion comes from (independently reproduced by both parties, each with their own measurements)**:

```
Shirone (first observation): 10 concurrent requests to the same URL ⇒ 9 finished in 0.6–1.3s, 1–2 stuck until 25s
Me (independent rerun, 2026-10-30, using the current real bundle):
  e7 0.32s e9 0.36s e3 0.37s e10 0.43s e4 0.54s
  e2 0.87s e6 1.12s e8 1.71s e1 2.04s      ← 9 normal
  e5 **25.001561s**                        ← 1 request pinned at the 25s ceiling
⇒ "degradation is per-request random failure, not the whole path dying" — **independently verified by both parties**
```

**Why R3 is a negative criterion**: Shirone implemented hedging inside EdgeOne middleware and **it did not work**
— the edge runtime's `AbortController` cannot abort an already-initiated fetch (the 8s timeout should have returned 502
but returned 200 and ran the full 40s). It is written as "forbidden" rather than "not recommended" so that later people
do not have to step on it again.

**Basis for R1's default concurrency of 8** (per-connection independent rate limit of 1.5MB/s + 80ms RTT):

```
conc=1 11,519ms | conc=2 1.99× | conc=4 3.63× | conc=8 **4.89× (knee)** | conc=15 4.88×
```

**Measuring concurrency requires a per-connection independent rate limit**. I initially used CDP's
`Network.emulateNetworkConditions` and saw **no difference at all** across 1/2/4/8/15 concurrent requests — because
**CDP throttling is a globally shared bandwidth pool**, so concurrency cannot get more. I have told Shirone about this trap.

---

## 5. Relationship to existing contracts (no regression)

| Layer | Owner | Relationship to the release contract |
|---|---|---|
| **Content contract** (`content-list`: `form`/`content`/`consumer`/`versions[]`/`files[]`) | This repo's semantics + host schema | **Upstream**; fields unchanged; a future `acquisition.releaseRef` **references** the manifest (add it only once there is a real artifact) |
| **Engine contract** (`octave.build.json`: build/measured/verdict) | Host | **Upstream**; only **references** release identity, never copies byte facts |
| **Release contract** (this design) | Designed in this repo / produced by each repo | **Middle layer**: the single home of byte identity |
| **Deploy contract** (`deploy-contract.mjs`: base/literal rewriting) | UI | **Downstream**, consumes the manifest |

**Conflict with the "build from source" contract (`STATE` Q3: `ways` are derived not recorded; `flavor` is not introduced)**:
The release contract **does not touch version semantics**. `fromSource` remains "can this be built from source";
"which release to take bytes from" is an **acquisition path**, orthogonal to version semantics. **The first generation does not even add `acquisition`**
— wait until the manifest has a real artifact and a single-repo pilot has passed. **This is the discipline of "no skipped steps".**

---

## 6. Compression policy (first generation)

| Condition | zstd | gzip | br | identity |
|---|---|---|---|---|
| `bytes ≥ 1 MiB` | **Required** (L19, 5MiB chunks) | **Required** (-9, chunked) | **Not produced** (slot reserved) | **Required** |
| `bytes < 1 MiB` | Optional | Optional | Not produced | Required |
| Already-compressed formats (`.gz/.zip/.whl/.woff2/.png`) | **Not produced** (wasted work + pure size increase) | Not produced | Not produced | Required |

**On "maximum gzip compression"**: measured, `-9` vs `-6` saves only 0.5% (20,899,276 vs 21,004,021) at double the
CPU ⇒ **-9 is wasted work on wasm**; -6 is enough. Time is better spent on zstd L19 (26.6% smaller than gzip).

---

## 7. What the station side must provide (all standard HTTP, nothing invented)

| Item | Value | Note |
|---|---|---|
| Independent URL per chunk | `GET <dir>/chunks/<codec>/NNN.<ext>` | Plain GET |
| `Content-Length` | Exact | Used to detect truncation |
| `Content-Type` | `application/zstd` / `application/gzip` / the original type | **Do not** use `application/gzip` to masquerade as wasm |
| `Cache-Control` | `public, max-age=31536000, immutable` | "Never update" relies on this, not on "we won't change the files" |
| CORS | `Access-Control-Allow-Origin: *` (if cross-origin) | Chunks will be fetched cross-origin |

**Not needed** (explicitly not required in the first generation): Range / `Accept-Ranges` / conditional requests /
`Digest` header / `multipart/byteranges`. **All of these were v1 inventions and have been cut.**

**One known current state (measured)**: the current edge origin headers are `Cache-Control: public, max-age=0, must-revalidate`
— **the opposite of "never update"**, and must be overridden to `immutable` at the reverse-proxy layer. This is not entirely in the producer's hands.

---

## 8. Who produces, who verifies

| Role | Does | Does not do |
|---|---|---|
| Each repo (producer) | Produce `manifest.json` + pre-chunked files; **compute chunk sha and global sha itself** | Does not define another party's bytes |
| Station side (distribution) | Transport + `immutable` caching + index | **Does not recompute sha, does not modify the manifest** |
| Consumer | Try `variants` in order, fetch concurrently, two verification layers | Does not guess, does not Range, does not use custom headers |
| This repo | Content semantics + keeps a copy of the release contract | Does not produce bytes, does not arbitrate distribution implementations |

---

## 9. Open questions (I do not decide these unilaterally)

| # | Question | My inclination |
|---|---|---|
| U1 | Whether `chunkSize` is fixed at 5 MiB or configurable per artifact | **Default 5 MiB, configurable** (the knee also depends on concurrency / chunk count) |
| U2 | Whether concurrency defaults to 8 or adapts via `navigator.connection` | **Default 8**, overridable |
| U3 | Whether small artifacts are also chunked | **< 1 MiB is not chunked** (no concurrency gain, only N extra requests) |
| U4 | When `acquisition` enters the content contract | **After the manifest lands + the single-repo pilot** |
| U5 | When br is enabled | **After the first generation** (user already ruled: not unsupported, but not enabled in the first generation) |

---

## 10. Rollout order (no skipped steps; this is the brake)

```
1. [done] User approved v3 (R1–R4 finalized by both repos; the size metric is corrected; the 5MiB wording has been
   changed to "upper bound + measured range")
2. [done] manifest validator (check-release-v2.py, 7/7 self-test) + **generator landed**
   (`tools/make-release-manifest.py`, 11/11 self-test: normal / should-report-out-of-bounds / empty-input cases all covered)
3. [done] **Single-repo pilot completed** (real OM artifacts): see §10.1
4. Station-side integration (immutable + index referencing the manifest)    ← Shirone has confirmed cooperation
5. UI/host consumer (variants traversal + concurrency + two verification layers + R2 hedging)
6. Add acquisition to the content contract                      ← touch semantics last
```

**Two hard preconditions for the pilot (both already satisfied)**:
- [done] Contract v3 finalized (two-repo consensus)
- [done] Validator is machine-checkable (`tools/check-release-v2.py --selftest` 7/7, against the real PoC artifacts 31/0)
- [pending] **manifest generator** — freeze "compress → chunk → compute sha → write manifest" into a script,
  otherwise the pilot has to assemble the manifest by hand (error-prone and irreproducible)

**Minimal pilot shape** (suggested: `v0.1.0-wasm32` in the OM repo):
```
Add a `make-release-manifest.py` to the OM repo (or extend the host's existing build script):
  Input: artifact files (omc.wasm 74.5MB, js 56KB, msl zip 19.5MB)
  Process: chunk at 5 MiB → zstd-19 compress each chunk independently → gzip-9 compress each chunk independently
        → compute chunk sha + global sha → write manifest.json
  Output: <release dir>/manifest.json + chunks/{zstd,gzip}/*
Acceptance: tools/check-release-v2.py <manifest> ⇒ all green
```
**This step touches no existing consumer** — purely additive artifacts, disposable at any time.

### 10.1 Pilot run results (2026-10-30, real OM artifacts)

Running `tools/make-release-manifest.py` against `OpenModelicaCompiler_bg.wasm` (74,579,404 B):

```
Generation: 24.2s (15 chunks × 2 codecs)
  zstd      15,349,112  (20.6% of raw)
  gzip      20,908,462  (28.0%)
  identity  74,579,404  (100%)
Validation: check-release-v2.py ⇒ **24 PASS / 0 FAIL**
Browser end-to-end: 8 concurrent fetches of 15 chunks → per-chunk sha → zstd decode → concatenate
  ⇒ 74,579,404 B, global sha **byte-for-byte identical** to the manifest top level; total 583ms (fetch 76 + decode 442)
  ⇒ decoder load 6ms (fzstd ESM)
```

**Generator → validator → browser consumption: three links closed.** This is the measured evidence that "the pilot can begin".

**Until steps 2–3 are complete, no compression/chunking policy is promoted.**

---

## 11. How to rerun

```bash
# 1) browser decompression capability
#   /mnt/hdd/zcode-test/harness/probe-browser-codec.mjs
#   => gzip/deflate OK; br/zstd NO

# 2) pre-chunked compression ratio + timing (see §1.3)
#   /tmp/prechunk.py (8-core parallel)

# 3) concurrency gain (see §1.4)
#   /tmp/poc/slowserver.py 8931 1500000 0.08   # 1.5MB/s per connection + 80ms RTT
#   node /mnt/hdd/zcode-test/harness/poc-conc-real.mjs http://127.0.0.1:8931 zstd
#   => conc=1 11519ms / conc=8 2354ms (4.89× knee)

# 4) full-chain PoC (see §1.5)
#   /tmp/poc/make.py generates manifest + three chunk sets
#   node /mnt/hdd/zcode-test/harness/poc-multichunk2.mjs http://127.0.0.1:8930 zstd 6
#   => PASS, sha 8287589e…

# 5) fzstd size and safety boundary (see §1.2 / §1.6)
gzip -9 -c /tmp/dec/package/umd/index.js | wc -c      # => 3860
grep -A3 "maximum backreference" /tmp/dec/package/README.md
```
