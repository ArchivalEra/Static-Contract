# Release Contract Design · v0 draft

> ## DEPRECATED — historical, not authoritative (marked 2026-11-02)
>
> Never delivered, never entered any schema, never promoted. Superseded.
> **Current authority: `2026-10-30-release-contract-v4.md` (V1–V10) plus
> `2026-11-01-release-contract-v1.1-license.md` (V11, schema 3).**
> Kept only for the rejection criteria (so they are not re-opened). Do not implement from it.

> **Status**: draft (for user review). **Not delivered, not in any schema, not promoted.**
> **Design basis**: the actual artifacts of four repos — this repo, host, OM, UI — plus live
> measurements on 2026-10-30.
> **Terminology**: per `codebase-design`'s module / interface / seam / adapter / depth / leverage.

---

## 0. Why it is needed (first, own the previous batch's mistakes)

In `109`/`110`/`113` I promoted sidecar compression without any manifest design. **That was
irresponsible**, and the user's criticism was correct. Three real problems:

1. **No single identity object**: three byte streams — `.wasm` / `.wasm.gz` / `.wasm.br` — which
   is which, what `Content-Encoding` should be, which layer the consumer receives — **declared
   nowhere**;
2. **Conflicts with the "build-from-source contract"** (`STATE.md:145` Q3 ruling): the
   `fromSource` semantics of `versions[]` mean "two acquisition paths for the same version",
   while sidecars introduce a **third acquisition path** (pre-compressed artifacts); left out,
   it becomes a bypass;
3. **Conflicts with the existing Range protocol** (the user named this): we want "br/gzip
   out-of-order multi-threaded fetching", but nobody says which layer Range applies to, how to
   slice, or how to verify.

=> All three must be closed by **one release contract**, not by each repo shipping its own.

---

## 1. Factual basis (all measured, 2026-10-30)

### 1.1 The physical shape of the three existing contracts

| Contract | Origin | Carrier | Key fields |
|---|---|---|---|
| **Content contract** | this repo (semantics) / host (schema) | `content-list.json` (schema 2) | `form` (6 forms) / `content` / `consumer` / `versions[]` (3 invariants) / `files[]` / `kind` / `role` / `arch` / `sha256` / `size` / `deps` |
| **Engine contract** | host | `octave.build.json` (schema 1) | `tool` / `build` / `declared` / `measured` / `inputs` / `notes` / `verdict` / `mismatches` / `checked` |
| **Deploy contract** | UI (`deploy-contract.mjs`) | build-time injection + `pages.yml` | base prefix / JS literal rewriting / `<meta site-base>` / 5MB chunked-fetch shim (**a comment promise**) |

**A verified break**: the UI's `deploy-contract.mjs:47` comment says "5MB chunked-fetch shim:
whole-package GET -> Range chunks (3 chunks in parallel, concatenated in order)", but **the
artifact contains no such implementation** (I grepped the whole `dist/` tree; the 1047 `Range`
hits are all `RangeError` and other non-HTTP uses). => **That shim is a comment promise, never
implemented.**

### 1.2 Live Range behavior (the most important measurement of this round)

```
GET  octave.wasm + Range: bytes=0-1023        => 200 OK      (Range not supported!)
GET  omc.wasm.gz + Range: bytes=0-1023        => 206, 1024 B (supported)
GET  omc.wasm.gz + Range: bytes=1000000-1001023 => 206, 1024 B (real chunking, different content)
```

**Conclusion: EdgeOne's Range works only on "already-compressed sidecars", not on raw
uncompressed artifacts.**

### 1.3 Out-of-order chunking + full reconstruction chain (I verified it end to end)

For `OpenModelicaCompiler_bg.wasm.gz` (20,895,435 B), sliced at 5 MiB, fetched **in reverse
order** (chunk3 -> chunk2 -> chunk1 -> chunk0), then concatenated in order:

```
chunk3: 5,166,795 B 206   chunk2: 5,242,880 B 206
chunk1: 5,242,880 B 206   chunk0: 5,242,880 B 206
merged: 20,895,435 B  <- exactly equal to Content-Length
gunzip -> sha256 = 8287589ebdb53b4cc37c337c2ae88f798d8889f7  <- byte-for-byte equal to the product sha
```

=> **The requested "br/gzip out-of-order multi-threaded fetching" is entirely feasible
technically, and I have verified it end to end.**

### 1.4 The site admin's old conclusion is stale (must be corrected)

`SITE-ADMIN-REQUEST.md:125` records:

> Request three (Range) — **accept reality, withdraw the request**: your measurements (**the 206
> header claims a chunk but emits the whole decompressed body — header/body mismatch**) are more
> authoritative than the old record in HANDOFF.md. Chunked shim status: under the edge's
> `Accept-Ranges: none` the shim falls back to the whole package.

**That measurement was against the raw `.wasm`** (or an edge-decompressed response) — in that
case the "header/body mismatch" is indeed real. **But on the sidecar `.gz` it is a true 206**
(this round's measurement: byte-exact, different content, sha matches after reconstruction).
=> **Every criterion in the protocol must state "which layer it applies to"**, otherwise both
sides measure different things and the conclusions conflict forever.

---

## 2. Design: the release contract

### 2.1 First, be clear about "what it takes in"

| Existing contract | Its place in the release contract |
|---|---|
| Content contract (`content-list`) | **Upstream**: declares "what exists, which version, whether it can run". **Fields unchanged**; entries merely **reference** the release identity |
| Engine contract (`octave.build.json`) | **Upstream**: declares "how the engine artifact is built, what was measured". Likewise only **references** |
| Deploy contract (base/shim) | **Downstream**: consumes release identity to decide "where to fetch from, how to assemble" |
| **Release contract (this design)** | **Middle layer**: states the identity of "one deliverable byte object" — decoupled from both "content semantics" and "build process" |

**The key judgement (where the seam goes)**: the release contract's seam goes on **"byte object
identity"**, not on "package" or "build". Rationale (deletion test): delete it and the content
contract has to describe the compression layer itself (polluting semantics), the engine contract
has to duplicate url/sha (drift in two places), and consumers each have to guess
`Content-Encoding` (the UI already guesses) — **the complexity scatters back to three callers**,
which shows it earns its keep.

### 2.2 Interface (the shape of the manifest)

One manifest describes **one immutable byte set** (one release):

```json
{
  "schema": 1,
  "id": "<repo>/<tag>",                     // stable identity, immutable
  "producer": { "repo": "ArchivalEra/OpenModelica-Full-Wasm", "commit": "<sha>" },
  "created": "2026-10-30T00:00:00Z",
  "assets": [
    {
      "name": "OpenModelicaCompiler_bg.wasm",
      "role": "engine",                      // engine | package | toolchain | data | docs
      "form": "file",                        // same vocabulary as the content contract (file/tree/pkg/oct/octdir/js)
      "bytes": 74579404,                     // raw byte count (sole authority)
      "sha256": "8287589e…b001",             // raw byte sha (sole fail-closed basis)
      "encodings": {                          // core of this design: the encoding layer is a **child object**, not a sibling entry
        "gzip": { "url": "…wasm.gz", "bytes": 20895435, "sha256": "…" },
        "br":   { "url": "…wasm.br", "bytes": 13053436, "sha256": "…" }
      },
      "range": {                              // Range capability declaration (independent per layer)
        "supported": true,
        "granularity": 5242880,               // suggested slice granularity (5 MiB)
        "basis": "encoded"                    // key point: Range applies to the **encoded bytes**
      },
      "contentType": "application/wasm",
      "contentEncoding": {                    // one-to-one with encodings (for HTTP headers)
        "gzip": "gzip", "br": "br"
      },
      "immutable": true,
      "firstSeen": "2026-10-30T00:00:00Z"     // guards against same-name replacement (OM v0.1.0 appended an asset once)
    }
  ]
}
```

### 2.3 Five invariants (fail-closed, checked one by one by the validator)

| # | Invariant | Why |
|---|---|---|
| **I1** | `encodings.*.sha256` is the sha of **the encoded bytes**, not of the raw bytes | The consumer receives the encoded bytes; verifying against the raw sha fails by construction |
| **I2** | `bytes` (raw) is the **sole authority**; `encodings.*.bytes` is a derived quantity, and the validator **must be able to recompute and verify it** (after gunzip/brotli-decode it equals `bytes` and its sha equals `sha256`) | Prevents "declaring an uncompressed sidecar to fool the size check" |
| **I3** | `range.basis` ∈ {`encoded`, `identity`, `none`}, **defaulting to `none`** | Measured: EdgeOne returns `200` on the raw artifact and `206` on the sidecar => the layer must be declared explicitly, never guessed |
| **I4** | When `range.supported=true`, `granularity` is required and `≤ 2^31-1` | The chunk index must be expressible in `Range: bytes=a-b` |
| **I5** | **Once an asset's `sha256` under a given name is published, it may never change**; if it changes = new `id` or new `name` | OM precedent: `v0.1.0-wasm32` **appended** assets (legal), but overwriting the same name is not |

### 2.4 Relation to the "build-from-source contract" (the conflict the user named)

Current state (`STATE.md:145` Q3 ruling):

> `ways` is derived, not recorded; **do not introduce `flavor`** (precompiled or not are two
> acquisition paths for the same version, not flavors of the version).

**The release contract does not break this; it legitimizes the third path**:

```json
// an entry in the content contract (fields unchanged, one reference added)
{ "name": "statistics", "version": "1.7.7",
  "acquisition": {                          // new: acquisition path, not a version flavor
     "source":   { "releaseRef": "octave-extra-content/statistics-src-1.7.7" },
     "prebuilt": { "releaseRef": "octave-host/oct-1.7.7-wasm32", "arch": "wasm32" }
  }
}
```

**Criterion**: `fromSource` keeps its original meaning ("can this version be built from
source"), `acquisition` answers "where the bytes come from", and **the two are orthogonal**.
The release contract is the **definition site** of `releaseRef` (one ref points to one
manifest); the content contract's `url`/`sha256`/`size` remain the **projection of the selected
path** (invariant 2 as before: top-level scalars must equal some candidate exactly).

=> **Resolution: do not merge, do not replace — layer them** — version semantics (content
contract) / acquisition path (acquisition) / byte identity (release contract), each with a
single responsibility.

### 2.5 Relation to the "Range protocol" (the user wants to keep it)

**Keep it, with one correction**: the existing shim comment says "whole-package GET -> Range
chunks", but measurements show the **whole package does not support Range, only the sidecar
does**. So the protocol becomes:

```
1) Fetch the manifest, choose one layer from encodings (br first, gzip fallback, identity last)
2) If range.supported=true and range.basis="encoded":
     issue N concurrent Range requests against the sidecar URL (out of order), write by offset
3) After assembly, verify the **encoded bytes** against encodings[enc].sha256   <- check one
4) Decode (gunzip / brotli)
5) Verify the **raw bytes** against sha256 + bytes                             <- check two (I2)
```

**Both checks are indispensable**: the first catches mis-assembled chunks (the most common
error in out-of-order concurrency), the second catches decode errors and wrong-layer assembly.

**Why `basis: "encoded"` is the recommended default**:
- Measured: Range on the raw artifact does not work at all (`200` instead of `206`);
- The encoded sidecar is 3–5x smaller => fewer chunks, higher concurrency efficiency, cheaper
  retries;
- Decoding is local CPU, far cheaper than fetching 3–5x the bytes.

**Cost (stated honestly)**: **all chunks must arrive before decoding** (a compressed stream is
not randomly accessible). => So "out of order" buys **parallel bandwidth** only, not
"decode-as-it-arrives".

### 2.6 The three identities (echoing my `113` suggestion, formalized here)

| Layer | Who computes | Who verifies | Purpose |
|---|---|---|---|
| raw `bytes`+`sha256` | **Producer** (build pipeline) | Consumer (after decode) | sole fail-closed basis |
| `.gz` `bytes`+`sha256` | Producer (computed right after CI compression) | Consumer (after chunk assembly) | chunk integrity |
| `.br` `bytes`+`sha256` | Producer (computed right after CI q11 compression) | Consumer | same as above |

**Discipline**: **the distributor (site side) only verifies, never recomputes** (a value
computed by the distributor is not authoritative; on mismatch with the producer it raises red,
it does not update itself).

### 2.7 Compression policy (my `113` suggestion, converged into contract clauses)

| Condition | gzip | br | Basis (measured) |
|---|---|---|---|
| `bytes ≥ 1 MiB` | `-9` mandatory | **q11 mandatory** | br11 saves 37.54% over gzip-9 (omc.wasm) / 34.95% (octave.wasm) |
| `bytes < 1 MiB` | `-6` suffices | optional | for small files the br header overhead eats the gain |
| Already-compressed formats (`.gz/.zip/.whl/.woff2/.png/.jpg`) | **none** | **none** | wasted work; the current UI script already hit this: zip 23MiB + whl 13MiB + tar.gz 79MiB compressed twice |
| Cost | 5.0s / 74.5MB | **148.5s / 74.5MB** | q11 must run once in CI and be cached permanently |

---

## 3. Who produces, who verifies (role split, no content semantics involved)

| Role | Does | Does not |
|---|---|---|
| **Each repo (producer)** | Produces the release + manifest + `.gz`/`.br` sidecars; **computes its own three shas** | Does not define other repos' bytes |
| **Site side (distribution)** | Moves bytes + immutable cache + index; **only verifies** the shas in the manifest | Does not recompute shas, does not modify the manifest, does not judge whether a package runs |
| **Consumers (UI/host)** | Reads manifest -> picks encoding -> chunked fetch -> two checks | Does not guess Content-Encoding, does not build URLs itself |
| **This repo** | Content semantics (four states/version policy/`consumer`/`files[]`); **keeps a copy of the release contract** | Does not produce bytes, does not adjudicate the distribution implementation |

---

## 4. Open questions (I do not decide these unilaterally; user / both parties must rule)

| # | Question | My inclination | Criterion |
|---|---|---|---|
| **U1** | Is the manifest **one per repo** or **one aggregated per cluster**? | **One per repo** (`<repo>/<tag>/manifest.json`), with the site aggregating an index | Producer ownership is clear; aggregation is the distributor's job |
| **U2** | `encodings` default policy: **emit all** or **on demand**? | All for large artifacts, gzip only for small | §2.7 measurements |
| **U3** | Should the content contract gain an `acquisition` field? | **Yes**, but **only after the manifest lands** (definition first, then reference) | Avoids a second "promote before defining" |
| **U4** | Is `range.granularity` fixed at 5 MiB or configurable? | **Configurable, default 5 MiB** | EdgeOne is "extremely fast at 5MB" (the user's words); but the optimal granularity may differ per file |
| **U5** | MIME/Content-Type for `.br` | Same `contentType` as the raw artifact + `Content-Encoding: br` | HTTP standard; measured: the live `.wasm.gz` returning `application/gzip` is **wrong** (it makes consumers treat compressed bytes as wasm) |

---

## 5. Rollout order (**no skipping steps**)

```
1. User approves this design (now)
2. Build the manifest generator + validator (who does it? see U1)   <- tooling first
3. Pilot in one repo (OM suggested; it already has a release + two assets) <- artifact first
4. Site-side integration (they are already building the distribution site)  <- distribution first
5. UI/host consumer integration                                      <- change consumers last
6. Add acquisition to the content contract (referencing an existing manifest) <- touch semantics last
```

**Explicitly not doing**: until 1–3 are done, **do not promote any compression/chunking policy
again**. This letter is that brake.

---

## 6. How to reproduce

```bash
# (1) Range works only on sidecars
curl -sI -H "Range: bytes=0-1023" https://isui.ren/repo/Octave/lanes/wasm32-final/octave.wasm | head -1   # 200
curl -sI -H "Range: bytes=0-1023" https://isui.ren/repo/Octave/omc/OpenModelicaCompiler_bg.wasm.gz | head -1 # 206

# (2) Out-of-order chunking + reconstruction (see the output in §1.3)
#  fetch chunk3..chunk0 in reverse -> concatenate in order -> gunzip -> sha256 = 8287589e…

# (3) br q11 gain
python3 -c "
import brotli,gzip,time
raw=open('/mnt/hdd/antigravity-projects/Octave-UI/dist/omc/OpenModelicaCompiler_bg.wasm','rb').read()
t=time.time();b=brotli.compress(raw,quality=11,lgwin=24);print('br11',len(b),f'{time.time()-t:.1f}s')
t=time.time();g=gzip.compress(raw,9);print('gz9',len(g),f'{time.time()-t:.1f}s')"
#  => br11 13,053,436 (148.5s) / gz9 20,899,276 (5.0s)

# (4) The deploy contract's 5MB shim is a comment promise (not implemented)
grep -c "Range" /mnt/hdd/antigravity-projects/Octave-UI/dist/assets-loader.js   # all RangeError, no HTTP Range
# the shim comment in the source is a CJK string; grep by "shim" to find it
grep -n "shim" /mnt/hdd/antigravity-projects/Octave-UI/scripts/deploy-contract.mjs
```
