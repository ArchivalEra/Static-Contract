# Release Contract v2 · first generation

> ## DEPRECATED — historical, not authoritative (marked 2026-11-02)
>
> Never delivered, never entered any schema, never promoted. Superseded.
> **Current authority: `2026-10-30-release-contract-v4.md` (V1–V10) plus
> `2026-11-01-release-contract-v1.1-license.md` (V11, schema 3).**
> Kept only for the rejection criteria (so they are not re-opened). Do not implement from it.

> **Status**: first-generation protocol draft, for user review. **Not delivered, not in schema,
> not promoted.**
>
> **v1 -> v2 changes (all from user corrections + my own measurements)**:
> 1. **Cut the entire Range family** — pre-slicing makes Range unnecessary. The user's objection:
>    the end user fetches exactly one standard request with barely any headers. A browser PoC
>    already proved it: plain GET x concurrency suffices.
> 2. **Cut seek table / `range.basis` / `granularity`** — those were my own inventions, violating
>    "do not invent more than necessary".
> 3. **`variants` becomes an ordered array** (the fallback chain is **data**, not code branches):
>    adding a new format = add one array entry, and not a single character of the schema changes.
>    This is the mechanism that lets the protocol "never need updating".
> 4. **The first generation enables only zstd + gzip + identity, not br** (user ruling: **it is not
>    unsupported, it is just not enabled in the first generation**).
> 5. **Format negotiation is returned to HTTP** (`Accept-Encoding`) — **not our concern**.

---

## 0. One sentence

> **One release = one immutable directory. `manifest.json` is the only entry.
> All bytes are plain files fetched with plain GET.**
>
> The only consumer-side action: `fetch(manifest)` -> pick the first decodable entry in `variants`
> order -> fetch chunks concurrently -> assemble -> verify.
> **No Range, no conditional requests, no custom headers, no negotiation protocol.**

---

## 1. Measurement basis (every item is a reproducible criterion)

### 1.1 Browser decompression capability (this decides "who can be the fallback")

```
DecompressionStream('gzip')     supported natively
DecompressionStream('deflate')  supported natively
DecompressionStream('br')       not supported
DecompressionStream('zstd')     not supported
```

=> **gzip is the only zero-dependency fallback**; zstd/br both require an out-of-band decoder.

### 1.2 Decoder size

| Encoding | Decoder | minified | after gzip |
|---|---|---|---|
| gzip | browser native | 0 | **0** |
| zstd | `fzstd@0.1.1` | 8,394 B | **3,860 B** <- officially 3.8kB; I measured 3860 (correct) |
| br | requires wasm (e.g. `brotli-wasm`) | ~100KB+ | not measured (not enabled in the first generation) |

### 1.3 Compression/decompression for the three encodings (74.5MB wasm, 5MiB x 15 chunks)

| Encoding | Pre-sliced total | Compression time (8 cores parallel) | Decompression time | Decompression throughput |
|---|---|---|---|---|
| **zstd-19** | **15,349,112** | **3.7s** | **0.07s** | **1022 MB/s** |
| gzip-9 | 20,908,462 | 5.0s | 0.21s | 363 MB/s |
| br-q11 | 14,332,389 | 21.5s | 0.16s | 459 MB/s |
| identity | 74,579,404 | — | — | — |

**Reading**:
- zstd is **26.6%** smaller than gzip, decompresses **2.8x** faster, compresses **0.74x** as fast
  (all fast enough) => **first in priority**;
- br is only **6.6%** smaller than zstd, but its decoder is 30x heavier and decompression is 2.2x
  slower => **not enabled in the first generation, not unsupported** (user ruling: keep the slot,
  do not spend first-generation complexity on it);
- gzip has the worst size but **zero dependencies** => the fallback.

### 1.4 Concurrency gain (1.5MB/s per connection + 80ms RTT, simulating a real CDN)

```
conc=1   fetch 11,519ms
conc=2   fetch  5,800ms   1.99x
conc=4   fetch  3,175ms   3.63x
conc=8   fetch  2,354ms   4.89x   <- knee
conc=15  fetch  2,359ms   4.88x   <- no longer rises (15 chunks / 8 = 2 rounds, the second round is underfed)
```

=> **Default concurrency = 8** (the knee), and **concurrency should not exceed the chunk count**.

### 1.5 The PoC already runs end to end (real browser environment, full chain)

```
Consumer action: fetch(manifest.json) -> 6 concurrent fetch(chunk) -> per-chunk sha -> decode -> assemble -> global sha
Result: 15/15 chunks, 74,579,404 B, sha 8287589e…b001 == expected   PASS
zstd variant: decoder load 7ms, total 606ms
gzip variant: total 522ms (zero decoder)
```

### 1.6 A safety boundary of zstd (must be written into the contract)

The `fzstd` README, verbatim:

> only supports a maximum backreference distance of **2^25 (32 MiB)** bytes. If you need to
> decompress files with an "ultra" compression level (**20 or greater**) AND if your files can
> be **above 32MB decompressed**, `fzstd` *might* fail to decompress properly.

**This does not apply to our scenario**, because **we slice**:

```
single chunk = 5,242,880 B (2^23) < 2^25 (33,554,432 B)  => safe
and per-chunk compression has no cross-chunk backreferences anyway => independent of level
```

=> **Write it into the contract as an invariant** (see I6): with chunked encoding,
`chunkSize ≤ 2^25`, and chunks **must be compressed independently**. This also constrains the
freedom of "anyone in the future who wants to raise chunkSize".

---

## 2. Directory shape

```
<repo>/<tag>/                         <- immutable. A new version = a new tag = a new directory
  manifest.json                       <- the single metadata entry
  chunks/zstd/000.zst … NNN.zst       <- pre-sliced (one plain URL per chunk)
  chunks/gzip/000.gz  … NNN.gz
```

**No `latest` alias is provided** — that is the entry point for "perpetual updating". The
enforcement of "never updates" is precisely that the directory name contains the tag.

**Whole-file sidecar form (optional, for small artifacts that are not chunked)**:
```
<repo>/<tag>/<asset>                  <- identity original file
<repo>/<tag>/<asset>.zst              <- whole-file zstd
<repo>/<tag>/<asset>.gz               <- whole-file gzip
```

---

## 3. manifest (full first-generation shape)

```json
{
  "schema": 1,
  "id": "OpenModelica-Full-Wasm/v0.1.0-wasm32",
  "bytes": 74579404,
  "sha256": "8287589e…b001",
  "variants": [
    {
      "codec": "zstd",
      "decoder": "fzstd@0.1.1",          // optional: hints which decoder the consumer needs
      "decoderBytes": 3860,               // optional: hints the cost
      "totalBytes": 15349112,
      "chunked": true,
      "chunkSize": 5242880,
      "chunks": [
        { "i": 0, "file": "chunks/zstd/000.zst", "bytes": 1275256, "sha256": "…" }
      ]
    },
    {
      "codec": "gzip",
      "totalBytes": 20908462,
      "chunked": true,
      "chunkSize": 5242880,
      "chunks": [ { "i": 0, "file": "chunks/gzip/000.gz", "bytes": 1395000, "sha256": "…" } ]
    },
    {
      "codec": "identity",                // final fallback: a single file
      "totalBytes": 74579404,
      "chunked": false,
      "file": "OpenModelicaCompiler_bg.wasm"
    }
  ]
}
```

### 3.1 Field necessity (deletion test)

| Field | What happens if deleted | Keep? |
|---|---|---|
| `bytes` + `sha256` (top level) | The edge has **no Digest header** (measured: `curl -sI` shows no digest at all) => consumers **cannot** verify final integrity | **must keep** |
| `variants` (ordered array) | Only trial and error is possible (try zstd, on 404 try gzip…) = N round trips, and "404" is indistinguishable from "genuinely absent" | **must keep** |
| `chunks[].sha256` | The most common error in out-of-order concurrency (one chunk missing/duplicated/misaligned) cannot be localized; only a full restart is possible | **must keep** |
| `chunks[].bytes` | Same as above, and `Content-Length` may be rewritten by intermediaries | **keep** |
| `chunkSize` | Consumers cannot derive anything beyond "how many chunks"; and I6 depends on it to judge the safety boundary | **keep** |
| `codec` | No way to know how to decode | **must keep** |
| `decoder` / `decoderBytes` | Consumers do not know what to load / whether it is worth it | **keep (optional)** |
| `id` | The manifest's own identity; cache key | **keep** |
| ~~`range`~~ | After pre-slicing Range is unnecessary | **delete** |
| ~~`seekTable`~~ | Same as above | **delete** |
| ~~`contentEncoding`~~ | `codec` already expresses it; do not repeat HTTP-layer concerns | **delete** |
| ~~`url` (absolute URL per chunk)~~ | Derivable from `id` + `file` | **delete** |

### 3.2 Invariants (checked one by one by the validator, fail-closed)

| # | Invariant | Counterexample |
|---|---|---|
| **I1** | Top-level `bytes`/`sha256` = the bytes and hash **after decoding and assembling all chunks** | Writing the sha of "some encoding layer" |
| **I2** | `chunks[].sha256` is the sha of **that encoded chunk's bytes** | Writing the raw sha |
| **I3** | The sum of all `chunks[].bytes` == `variants[].totalBytes` | Declaration does not match reality |
| **I4** | `variants` is non-empty, and **exactly one** `codec:"identity"` sits in the last position as the fallback | All entries are compressed formats (nothing left if they cannot be decoded) |
| **I5** | `chunked:true` => `chunkSize` required and `chunks` non-empty; `chunked:false` => has `file` and no `chunks` | Half-finished state |
| **I6** | `chunked:true` => `chunkSize ≤ 2^25` (the fzstd safety boundary) + chunks must be **compressed independently** | chunk > 32MiB and level >= 20 => fzstd may fail to decode |
| **I7** | `codec` is an **open string** (not an enum) | Adding br/xz/lz4 would require a schema change |

---

## 4. Consumer algorithm (first generation, pseudocode)

```
man = GET <dir>/manifest.json                       // 1 request, cacheable forever
for v of man.variants:                              // in declared order (the fallback chain)
    dec = {
      "gzip":  () => nativeGzip,                     // zero cost
      "zstd":  () => import(fzstd),                  // 3.8KB
      "identity": () => null,
    }[v.codec]
    if (dec === undefined) continue                  // unknown codec => skip (forward compatible)
    try:
        parts = await Promise.all(                   // concurrency, default 8
          v.chunks.map(c => fetch(c.file)            
            .then(r => r.arrayBuffer())
            .then(b => { assert sha256(b) === c.sha256  // per-chunk verify (one bad chunk refetches only that chunk)
                         return decode(b) })))
        all = concat(parts)
        assert all.length === man.bytes && sha256(all) === man.sha256
        return all                                   // success
    catch: continue                                  // this tier is broken => next tier
throw NO_USABLE_VARIANT                              // fail only after all are tried (loudly)
```

**Three design points**:
1. **`dec === undefined => continue`** is the key to **forward compatibility** — if a future
   manifest contains a `codec` we do not recognize (say `xz`), old clients **skip it and use the
   next one** instead of crashing. **This is where "adding new formats requires no protocol
   change" lands**;
2. **Per-chunk verification + per-chunk retry**: refetch only the bad chunk, no full restart;
3. **Two checks**: chunk level (catches mis-assembly) + global (catches decode errors).

---

## 5. Relation to the existing contracts (no regression)

| Layer | Owner | Relation to the release contract |
|---|---|---|
| **Content contract** (`content-list`: `form`/`content`/`consumer`/`versions[]`/`files[]`) | this repo's semantics + host schema | **upstream**, fields unchanged; in future add `acquisition.releaseRef` to **reference** the manifest (only after the artifact exists) |
| **Engine contract** (`octave.build.json`: build/measurements/verdict) | host | **upstream**, only **references** release identity, does not copy byte facts |
| **Release contract** (this design) | designed in this repo / produced by each repo | **middle layer**: the single place for byte identity |
| **Deploy contract** (`deploy-contract.mjs`: base/literal rewriting) | UI | **downstream**, consumes the manifest |

**Conflict with the "build-from-source contract" (`STATE` Q3: `ways` is derived, not recorded; do
not introduce `flavor`)**: the release contract **does not touch version semantics**. `fromSource`
still means "can this be built from source"; "which release the bytes come from" is an
**acquisition path**, orthogonal to version semantics. **The first generation does not even add
`acquisition`** — wait until the manifest exists and the single-repo pilot works. **This is the
"no skipping steps" discipline.**

---

## 6. Compression policy (first generation)

| Condition | zstd | gzip | br | identity |
|---|---|---|---|---|
| `bytes ≥ 1 MiB` | **mandatory** (L19, 5MiB chunks) | **mandatory** (-9, chunked) | **none** (slot reserved) | **mandatory** |
| `bytes < 1 MiB` | optional | optional | none | mandatory |
| Already-compressed formats (`.gz/.zip/.whl/.woff2/.png`) | **none** (wasted work + pure size increase) | none | none | mandatory |

**On "maximum-compression gzip"**: measured, `-9` vs `-6` saves only 0.5% (20,899,276 vs
21,004,021) at double the CPU => **-9 is wasted work on wasm**; `-6` suffices. Spend the time on
zstd L19 (26.6% smaller than gzip).

---

## 7. What the site side must provide (all standard HTTP, nothing invented)

| Item | Value | Note |
|---|---|---|
| One URL per chunk | `GET <dir>/chunks/<codec>/NNN.<ext>` | plain GET |
| `Content-Length` | exact | used to detect truncation |
| `Content-Type` | `application/zstd` / `application/gzip` / the original type | **Do not** use `application/gzip` to masquerade as wasm |
| `Cache-Control` | `public, max-age=31536000, immutable` | "never updates" depends on this, not on "we do not change files" |
| CORS | `Access-Control-Allow-Origin: *` (if cross-origin) | chunks are fetched cross-origin |

**Not needed** (explicitly not required in the first generation): Range / `Accept-Ranges` /
conditional requests / `Digest` header / `multipart/byteranges`. **All of these were v1's
inventions and have been cut.**

**One known current state (measured)**: the live edge origin header is
`Cache-Control: public, max-age=0, must-revalidate` — **the opposite of "never updates"** — and
must be overridden to `immutable` by the reverse proxy. This is not entirely in the producer's
hands.

---

## 8. Who produces, who verifies

| Role | Does | Does not |
|---|---|---|
| Each repo (producer) | Produces `manifest.json` + pre-sliced chunks; **computes its own chunk shas and the global sha** | Does not define other repos' bytes |
| Site side (distribution) | Moves bytes + `immutable` cache + index | **Does not recompute shas, does not modify the manifest** |
| Consumers | Tries `variants` in order, fetches concurrently, two checks | Does not guess, does not use Range, does not use custom headers |
| This repo | Content semantics + keeps a copy of the release contract | Does not produce bytes, does not adjudicate the distribution implementation |

---

## 9. Open questions (I do not decide unilaterally)

| # | Question | My inclination |
|---|---|---|
| U1 | Is `chunkSize` fixed at 5 MiB or configurable per artifact | **Default 5 MiB, configurable** (the knee is also affected by concurrency/chunk count) |
| U2 | Default concurrency 8, or adaptive via `navigator.connection` | **Default 8**, allow override |
| U3 | Should small artifacts also be chunked | **Do not chunk below 1 MiB** (no concurrency gain, just N extra requests) |
| U4 | When does `acquisition` enter the content contract | **After the manifest lands + the single-repo pilot** |
| U5 | When is br enabled | **After the first generation** (user already ruled: not unsupported, just not enabled in the first generation) |

---

## 10. Rollout order (no skipping steps; this is the brake)

```
1. User approves this v2                       <- now
2. manifest generator + validator (I1–I7 self-proof)    <- tooling first
3. Single-repo pilot (OM suggested: it already has a release + two assets)
4. Site-side integration (immutable + the index references the manifest)
5. UI/host consumers (variants iteration + concurrency + two checks)
6. Content contract gains acquisition               <- touch semantics last
```

**Until 2–3 are done, do not promote any compression/chunking policy.**

---

## 11. How to reproduce

```bash
# (1) Browser decompression capability
#   /mnt/hdd/zcode-test/harness/probe-browser-codec.mjs
#   => gzip/deflate OK; br/zstd NO

# (2) Pre-sliced compression ratio + timing (see §1.3)
#   /tmp/prechunk.py (8 cores parallel)

# (3) Concurrency gain (see §1.4)
#   /tmp/poc/slowserver.py 8931 1500000 0.08   # 1.5MB/s per connection + 80ms RTT
#   node /mnt/hdd/zcode-test/harness/poc-conc-real.mjs http://127.0.0.1:8931 zstd
#   => conc=1 11519ms / conc=8 2354ms (4.89x, the knee)

# (4) Full-chain PoC (see §1.5)
#   /tmp/poc/make.py generates the manifest + three chunk sets
#   node /mnt/hdd/zcode-test/harness/poc-multichunk2.mjs http://127.0.0.1:8930 zstd 6
#   => PASS, sha 8287589e…

# (5) fzstd size and safety boundary (see §1.2 / §1.6)
gzip -9 -c /tmp/dec/package/umd/index.js | wc -c      # => 3860
grep -A3 "maximum backreference" /tmp/dec/package/README.md
```
