# Release Contract · v1

> ## DEPRECATED — historical, not authoritative (marked 2026-11-02)
>
> Never delivered, never entered any schema, never promoted. Superseded.
> **Current authority: `2026-10-30-release-contract-v4.md` (V1–V10) plus
> `2026-11-01-release-contract-v1.1-license.md` (V11, schema 3).**
> Kept only for the rejection criteria (so they are not re-opened). Do not implement from it.

> **Status**: draft, for user review. **Not delivered, not in any schema, not promoted.**
> **Why v0 -> v1 changed**: v0 was hand-rolling manifest fields, but this class of semantics
> **is already standardized by HTTP**. v1's principle: **anything expressible by an HTTP header
> never goes into the manifest; the manifest only fills the small gap the standard cannot
> express.**
>
> **The user's goal**: "give the static site a protocol that **never needs updating** and
> **conforms closely to HTTP standards**". Every design point below is checked against those two
> words: **never updates** = immutable identity + self-description + no version negotiation;
> **conforms to standards** = use mechanisms the RFCs already have, invent nothing.

---

## 0. Own the previous batch's mistakes first (this is where the design starts)

I promoted sidecar compression in `109`/`110`/`113` without a manifest. Three real problems:

1. **No single identity object**: three byte streams `.wasm` / `.wasm.gz` / `.wasm.br` — which is
   which, what `Content-Encoding` should be, which layer the consumer gets — nowhere declared;
2. **Conflicts with the "build-from-source contract"** (`STATE.md:145` Q3: `ways` is derived, not
   recorded; do not introduce `flavor`): a sidecar is a third acquisition path; left out, it is a
   bypass;
3. **Conflicts with the existing Range protocol**: we want out-of-order multi-threaded fetching of
   br/gzip, but nobody says which layer Range applies to, how to slice, or how to verify.

=> There must first be **one** release contract to close this.

---

## 1. Measured facts (2026-10-30, full edge probe)

### 1.1 Range works only on "already-compressed sidecars"

| Request | Result |
|---|---|
| `octave.wasm` + `Range: bytes=0-1023` | **200 OK** (`Accept-Ranges: none`, unsupported) |
| `….wasm.gz` + `Range: bytes=0-1023` | **206**, 1024 B, `Content-Range: bytes 0-1023/20895435` |
| `….wasm.gz` + `Range: bytes=1000000-1001023` | **206**, 1024 B (different content = real chunking) |
| `….wasm.gz` + `Range: bytes=-1024` (suffix) | **206**, 1024 B (correct) |
| `….wasm.gz` + `Range: bytes=20893000-` (open) | **206**, 2435 B (correct) |
| `….wasm.gz` + `Range: bytes=0-99,200-299` (multi-range) | **200 whole body** (fails) — multipart unsupported |
| `….wasm.gz` + `Range: bytes=99999999-…` (out of bounds) | **416** (correct) |
| `….wasm.gz` + `Range: bytes=20895435-` (start = end) | **416** (correct) |

**=> Range support surface = single-range (including suffix and open forms), with correct
`Content-Range` and `416`. Multi-range (`multipart/byteranges`) unsupported. This directly
dictates "chunks must be fetched one at a time, not in batches".**

### 1.2 Conditional requests **cannot be relied on** (the key counterintuitive finding)

| Request | Expected (RFC) | Measured |
|---|---|---|
| `Range` + `If-Range: <correct ETag>` | 206 | **206** (correct) |
| `Range` + `If-Range: <wrong ETag>` | **200 whole body** (RFC 9110 §13.1.5) | **206** (does not follow the standard) — fails |
| `If-None-Match: <correct ETag>` | **304** | **200** — fails |

**=> You cannot use `If-Range` as a guard for "chunk and whole-package version consistency";
you cannot use `If-None-Match` to save traffic. Both must be written into the contract as "known
boundaries", otherwise consumers will write retry logic that looks correct but protects
nothing.**

### 1.3 Availability of ETag / Last-Modified

```
ETag: "6ae2ff51-13ed6cb"        <- constant across requests (identical 3/3 times)
  prefix 6ae2ff51 = 1793261393     <- mtime epoch (= Last-Modified)
  suffix 13ed6cb  = 20895435       <- exactly equal to Content-Length
Last-Modified: Thu, 29 Oct 2026 08:09:53 GMT
Accept-Ranges: bytes            <- only on the sidecar; the raw artifact says none
```

**=> The ETag is a weak validator derived from "mtime + size"** (`W/"<mtime>-<size>"` is the
GitHub/Fastly family convention), **not a content hash**. It **can** be used for a **weak**
judgement of "do two chunks of the same URL come from the same version" (both size and mtime are
stable), but **cannot** replace sha256's fail-closed guarantee.
=> In the contract: **ETag is for diagnostics/logs only, never a security criterion.**

### 1.4 What is absent (recorded honestly)

- **No `Digest` / `Content-Digest` header at all** (RFC 9530) => the standard content-integrity
  header is unavailable, so the manifest must carry sha256. **This is the first reason the
  manifest exists**;
- **zstd unsupported**: `Accept-Encoding: zstd` returns 200 + the raw artifact (74,579,404 B),
  and a `.wasm.zst` sidecar 404s => the current encoding surface = `identity` / `gzip` / `br`.
- **`Content-Type: application/gzip` on a `:status` 200** (when fetching the sidecar directly) —
  **this is a trap**: a consumer that does `fetch('x.wasm.gz')` directly gets compressed bytes
  while thinking it got wasm.

### 1.5 Out-of-order chunking + reconstruction verified end to end

For `….wasm.gz` (20,895,435 B), sliced at 5 MiB, fetched **in reverse order**, then concatenated
in order:

```
chunk3 5,166,795 B / chunk2 5,242,880 B / chunk1 5,242,880 B / chunk0 5,242,880 B  (all 206)
merged = 20,895,435 B          <- exactly equal to Content-Length
gunzip -> sha256 = 8287589ebdb53b4cc37c337c2ae88f798d8889f7  <- byte-for-byte equal to the product sha
```

=> **The protocol is feasible, verified end to end.** But note §1.1: multi-range is unsupported,
so this is **N independent requests**, not one multipart.

### 1.6 The site admin's old conclusion is stale (must be corrected, or the two sides measure different things forever)

`SITE-ADMIN-REQUEST.md:125`:

> Request three (Range) — **accept reality, withdraw the request**: measured "the 206 header
> claims a chunk but emits the whole decompressed body — header/body mismatch".

**That measurement was presumably against the raw `.wasm`** (the edge is inconsistent in headers
on the decompression path). **On the sidecar `.gz` it is a true 206** (this round: byte-exact,
correct `Content-Range`, sha matches after reconstruction).

=> **The contract must state the "measurement surface of Range"**: a different
`(URL, identity or not, Content-Encoding present or not)` triple gives a completely different
conclusion. **This is the biggest methodological gain of this round** — and another instance of
the "unmeasurable ≠ nonexistent" discipline I imposed on the UI: two teams each measure half,
each write a conclusion, and conflict forever.

### 1.7 Cache status: "never updates" is **backwards** on the origin (the release contract must correct it)

Measuring three consecutive requests to the same sidecar:

```
Age: 565   X-Served-By: cache-bur-kbur8200088-BUR  X-Cache: HIT
Age: 0     X-Served-By: cache-hkg-vhhh8650073-HKG  X-Cache: HIT   <- different node = counter restarts
Age: 566   X-Served-By: cache-bur-kbur8200114-BUR  X-Cache: HIT
```

**Two facts**:

1. **Multiple nodes cache independently** (LAX/HKG/BUR each keep their own counter) => the hit
   rate depends on which node the request lands on. This matches exactly what letter `080`
   recorded: "EdgeOne caches per node (Age sequences differ from each other)";
2. **The origin header is `Cache-Control: public, max-age=0, must-revalidate`** => the origin is
   actively **demanding revalidation on every request**. That is the exact opposite of "never
   updates".

**=> "Never updates" cannot be achieved by "we do not change files"; it must be achieved by
headers**: the release directory (`<repo>/<tag>/`) must be set by the producer to
`Cache-Control: public, max-age=31536000, immutable`.
**But this is not entirely in the producer's hands** — measured: the `.gz` `Cache-Control` comes
from the origin (GitHub Pages' default policy), whereas the `.wasm` (uncompressed) gets
`max-age=3600, s-maxage=86400`.
=> **The cache policy differs between the two byte layers in the same directory**; this is the
first thing the release contract must correct.

**The minimal requirement on the site side** (doable without touching the origin): the reverse
proxy **overrides** `Cache-Control: public, max-age=31536000, immutable` for `/<repo>/<tag>/`.
Criterion:

```bash
curl -sI https://<static-host>/<repo>/<tag>/x.wasm.gz | grep -i cache-control
# => public, max-age=31536000, immutable
```

### 1.8 How multi-node caching affects chunking (this decides the concurrency policy)

Since `Age` differs across nodes, **N chunk requests for the same file may land on N different
nodes**:

- **The good side**: when different nodes each hold the full body, concurrent chunking =
  concurrent hits on different caches, throughput adds up;
- **The bad side**: if a node does **not** have the file cached, its first request goes to the
  origin (measured: on `X-Cache: MISS`, `X-Timer ... VE3845` = **3.8 seconds to origin**) => that
  chunk is 3.8s slower and becomes the straggler for the whole concurrent set.

=> **Requirement on consumers**: chunks **must tolerate a single slow point** — set timeouts +
retries (a retry gets stuck to another node, a dividend of EdgeOne's topology). **Do not** restart
everything because one chunk is slow.

---

## 2. Design principles (checked against the user's two words)

| Principle | How | Why |
|---|---|---|
| **Never updates** (P1) | Identity = `sha256`; a URL is immutable once published; **no version negotiation, no capability discovery** | Any "negotiation" requires both sides to evolve together = requires updating |
| **Pure standard** (P2) | Slicing uses RFC 9110 `Range`/`Content-Range`/`416`; encoding uses RFC 9110 `Content-Encoding`; caching uses `Cache-Control: immutable` | Browsers/proxies/CDNs all understand it; nothing to teach |
| **The manifest only fills gaps the standard does not express** (P3) | HTTP has `Content-Encoding`, `Content-Length`, `Accept-Ranges` — **these do not go into the manifest**; HTTP **lacks** sha256, "which encoding these bytes belong to", and "which layer Range applies to" — **only these go in** | The smaller the manifest, the less it can become a second truth |
| **Failures must be loud** (P4) | Two sha checks (encoding layer / raw layer); `416`/`404`/sha mismatch are all hard errors | Precedent: success reported as failure (D12), assembly defects disguised as degradation (D11) |
| **Degradable but observable** (P5) | br -> gzip -> identity step down, **with a readable reason for the fallback** | Old browsers and broken proxies exist; but silent degradation makes "why is it slow" unanswerable forever |

---

## 3. The protocol itself

### 3.1 One sentence

> **One release = one immutable directory + one manifest.json.**
> The manifest records only "the few things HTTP cannot express": sha256, the byte identity of
> each encoding layer, and the measurement surface of Range.
> Everything else (type, length, Range capability, cache policy) **is self-described by HTTP
> headers**.

### 3.2 Directory shape (static site, never updates)

```
<repo>/<tag>/
  manifest.json                 <- the single metadata entry (immutable)
  <asset>                       <- identity raw artifact
  <asset>.gz                    <- gzip sidecar (5.0s/74.5MB)
  <asset>.br                    <- brotli q11 sidecar (148.5s/74.5MB)
```

**Enforcing "never updates"**: the directory name contains `tag`, and `tag` never changes once
published. A new version = a new `tag` (new directory). **No `latest` alias is provided** — that
is the entry point for perpetual updating.

### 3.3 manifest (minimal shape)

```json
{
  "schema": 1,
  "id": "OpenModelica-Full-Wasm/v0.1.0-wasm32",
  "producer": { "repo": "ArchivalEra/OpenModelica-Full-Wasm", "commit": "<sha>" },
  "assets": {
    "OpenModelicaCompiler_bg.wasm": {
      "role": "engine",
      "contentType": "application/wasm",
      "bytes": 74579404,
      "sha256": "8287589e…b001",
      "encodings": {
        "gzip": { "bytes": 20895435, "sha256": "<sha of the gz bytes>" },
        "br":   { "bytes": 13053436, "sha256": "<sha of the br bytes>" }
      },
      "range": { "basis": "encoded", "granularity": 5242880 }
    }
  }
}
```

**Necessity argument per field (deletion test: delete it, who is hurt?)**

| Field | What happens if deleted | Verdict |
|---|---|---|
| `bytes` + `sha256` | The edge has **no Digest header** (§1.4) => consumers have **no way** to verify integrity | **must stay** |
| `encodings.*.{bytes,sha256}` | After chunk assembly there is no way to verify it was assembled correctly (`Content-Range` gives the range, not the content identity) | **must stay** |
| `encodings` (its existence) | Consumers can only **try** (try br, on 404 try gzip…) = N round trips, and "404" is indistinguishable from "genuinely absent" | **must stay** |
| `range.basis` | Measured: the raw artifact does not support Range, the sidecar does (§1.1) => without it, consumers may send Range at the raw artifact, get a 200 whole body, and think it was chunked | **must stay** |
| `range.granularity` | 5 MiB is the empirical "extremely fast at the edge" value; without it every client guesses | **stay (default 5 MiB)** |
| `contentType` | When the sidecar is fetched directly, `Content-Type: application/gzip` (§1.4) => consumers misjudge | **stay** |
| ~~`url`~~ | **delete**: URL = `<dir>/<asset>` or `<dir>/<asset>.<enc>`, **derivable from id+name** | **delete (derived, not recorded)** |
| ~~`contentEncoding`~~ | **delete**: `gzip`/`br` are just HTTP encoding names; repeating them = a second truth | **delete** |
| ~~`range.supported`~~ | **delete**: the `Accept-Ranges` header already says it; `basis` already implies "supported" | **delete** |
| ~~`immutable`~~ | **delete**: `Cache-Control: immutable` is HTTP's business | **delete** |
| ~~`firstSeen`~~ | **delete**: see P3; diagnosing with `Last-Modified`/`ETag` is enough | **delete** |
| ~~`form`~~ | **delete**: `form` (pkg/tree/file…) is an axis of the **content contract**, not of byte identity | **delete (belongs to the content contract)** |

**=> Cut from 14 fields in v0 to 6.** Every cut is either "HTTP already says it" or "wrong place".

### 3.4 Five invariants (checked one by one by the validator, fail-closed)

| # | Invariant | Counterexample (must go red) |
|---|---|---|
| **I1** | `encodings.<enc>.sha256` is the sha of **that encoding's bytes**, not of the raw bytes | Writing the raw sha => consumer verification always fails |
| **I2** | The compressed layer is **recomputable**: `gunzip(enc bytes)` / `brotli_decode(enc bytes)` must yield the length `bytes` and sha = `sha256` | Declaring an uncompressed sidecar to fool the size check |
| **I3** | `range.basis ∈ {encoded, identity}`, **and declaring `encoded` requires `encodings` to be non-empty** | Declaring encoded with no encoding layer at all = a dangling reference |
| **I4** | `granularity ≤ 2^31-1` and `> 0` | The chunk index must fit in `Range: bytes=a-b` |
| **I5** | **Under the same `id`, an asset's `sha256` never changes**; if it changes = must change `id` (new tag) | OM precedent: `v0.1.0-wasm32` **appending** an asset is legal (new name), **overwriting** the same name is not |

### 3.5 Consumer algorithm (using HTTP to the fullest)

```
1. GET <dir>/manifest.json           (Cache-Control: immutable => cache forever)
2. Choose encoding: br -> gzip -> identity   (by presence in encodings, not by trial and error)
   Note: if an encoding 404s (the manifest says it exists but the site lacks it) => report ENCODING_MISSING, do not silently fall back
3. Fetch bytes:
   if range.basis == "encoded" and enc != identity:
       N = ceil(encBytes / granularity)
       issue K concurrent single-range requests (RFC 9110 single range; **no multipart**, §1.1)
       write to disk by the offset in Content-Range (out-of-order safe)
   else:
       plain GET (the raw artifact has Accept-Ranges: none, do not bother with Range)
4. Check one: sha256 of the assembled encoded bytes == encodings[enc].sha256   (catches mis-assembly)
5. Decode (gunzip / brotli)
6. Check two: decoded bytes == bytes and sha256 == sha256        (catches decode errors / wrong layer)
```

**Why both checks are indispensable**: the most common error in out-of-order concurrency is
"one chunk missing / one chunk duplicated / misaligned" — the first check catches it. Errors at
the decode layer (wrong codec, truncated stream) can only be caught by the second check.

**Concurrency K**: the contract only says "K is decided by the consumer", but **it must be ≤ the
number of connections the site allows** (do not DDoS yourself).

### 3.6 Relation to the "build-from-source contract" (the conflict the user named)

Current state (`STATE.md:145` Q3 ruling):

> `ways` is derived, not recorded; **do not introduce `flavor`** (precompiled or not are two
> acquisition paths for the same version, not flavors of the version).

**The release contract does not touch this; it only adds a third layer**:

```
version semantics (content contract)      : what this version is, whether it can be built from source (fromSource)
acquisition path (content contract, new)  : which release to fetch from (two refs: source / prebuilt)
byte identity (release contract)          : the three shas of every byte object in that release
```

**Criterion**: `fromSource` keeps its original meaning; `acquisition` holds **only releaseRef
references**, not byte facts; the release contract is the **definition site** of `releaseRef`.
The content contract's `url/sha256/size` remain "the projection of the selected path" (invariant 2
as before: top-level scalars must equal some candidate exactly).

**=> Do not merge, do not replace; layer them.** And the `acquisition` field **must wait until the
manifest exists physically** — definition first, then reference, otherwise it is a second
"promote before defining".

### 3.7 Compression policy (backed by measurements, converged into contract clauses)

| Condition | gzip | br | Basis |
|---|---|---|---|
| `bytes ≥ 1 MiB` | `-9` mandatory | **q11 mandatory** | br11 saves **37.54%** over gzip-9 (omc.wasm) / **34.95%** (octave.wasm) |
| `bytes < 1 MiB` | `-6` suffices | optional | for small files the br header overhead eats the gain |
| Already-compressed formats (`.gz/.zip/.whl/.woff2/.png/.jpg`) | **none** | **none** | wasted work; the current UI script already hit this: zip 23 MiB + whl 13 MiB + tar.gz 79 MiB compressed twice |
| Cost | 5.0s / 74.5MB | **148.5s / 74.5MB** | q11 must run once in CI and be cached permanently |

**On "maximum-compression gzip"**: measured, `-9` saves only **0.5%** over `-6` (20,899,276 vs
21,004,021) at double the CPU. => Spend the time on br q11 (saves 37.5%), not on gzip -9 (saves
0.5%). The phrase "maximum compression" only holds for br on wasm.

### 3.8 What the site side must obey (HTTP headers, not the manifest)

| Header | Value | Why |
|---|---|---|
| `Accept-Ranges` | `bytes` (sidecar) / `none` (identity) | Let consumers **decide from the header**, no trial and error |
| `Content-Type` | **the raw artifact's real type** (`application/wasm` etc.); the sidecar carries the **same type** | The current `application/gzip` is a trap (§1.4) |
| `Content-Encoding` | `gzip` / `br` (only when serving directly after `Accept-Encoding` negotiation) | RFC 9110 |
| `Cache-Control` | `public, max-age=31536000, immutable` | never updates |
| `Content-Range` | mandatory on 206, and the total in `*/<total>` must **equal the byte count of that encoding layer** | measured correct today; keep it |
| `416` | Range out of bounds / start = end | measured correct today; keep it |
| ~~`If-Range`~~ | **not relied upon** (measured: does not follow the standard, §1.2) | the contract states "unusable" |

**One site-side trap to note**: currently `Cache-Control: public, max-age=0, must-revalidate`
(`.gz`) — this is the opposite of "never updates". The release directory should be switched to
`immutable` (releases and the site's branch artifacts must be treated separately).

---

## 4. Who produces, who verifies

| Role | Does | Does not |
|---|---|---|
| **Each repo (producer)** | Produces the release + `manifest.json` + `.gz`/`.br`; **computes its own three shas** | Does not define other repos' bytes |
| **Site side (distribution)** | Moves bytes + immutable cache + index; **only verifies** the manifest's shas | **Does not recompute shas, does not modify the manifest, does not judge whether a package runs** |
| **Consumers (UI/host)** | Reads manifest -> picks encoding -> chunks -> two checks | Does not guess `Content-Encoding`, does not probe by trial and error |
| **This repo** | Content semantics; **keeps a copy of the release contract** | Does not produce bytes, does not adjudicate the distribution implementation |

**Known tension (recorded honestly)**: the site side's `111` wants "one static index
(repo->tag->assets+sha256)" — that **is exactly the aggregate view of the manifests**. **This is
not duplication; the index should reference the manifests rather than copy the shas.** Suggestion:
the site index = a `{repo, tag, manifestUrl}` triple + optional caching; **sha exists in exactly
one place, the manifest**.

---

## 5. Open questions (user / both parties must rule; I do not decide unilaterally)

| # | Question | My inclination | Reason |
|---|---|---|---|
| **U1** | One manifest per repo vs one aggregate per cluster | **One per repo** (`<repo>/<tag>/manifest.json`) | Producer ownership is clear; aggregation is the distributor's index, referencing rather than copying |
| **U2** | Is `range.granularity` fixed or configurable | **Configurable, default 5 MiB** | The user's words: "5MB extremely fast"; but the optimal granularity may differ per file size |
| **U3** | When does the content contract gain `acquisition` | **After the manifest exists physically** | define first, reference after |
| **U4** | Should br be mandatory by default (or on demand) | mandatory for large artifacts, optional for small | §3.7 measurements |
| **U5** | Should the site index be fully delegated to the manifests | **Yes** | avoids sha in two places |

---

## 6. Rollout order (**no skipping steps; this is the brake**)

```
1. User approves this design                       <- now
2. manifest generator + validator (with I1–I5 self-proof)   <- tooling first
3. Pilot in one repo (OM suggested: it already has a release + two assets) <- artifact first
4. Site-side integration (the index references the manifests)              <- distribution next
5. UI/host consumer integration (two checks)              <- change consumers last
6. Content contract gains acquisition (referencing an existing manifest) <- touch semantics last
```

**Explicitly not doing**: until 1–3 are done, **do not promote any compression/chunking policy
again**. This letter is the brake.

---

## 7. How to reproduce (the source of every conclusion)

```bash
B=https://isui.ren/repo/Octave/omc/OpenModelicaCompiler_bg.wasm
G=$B.gz

# (1) Range works only on sidecars
curl -sI -H "Range: bytes=0-1023" $B | head -1                 # 200 (Accept-Ranges: none)
curl -sI -H "Range: bytes=0-1023" $G | head -1                 # 206 + Content-Range

# (2) single-range variants
curl -s -o /dev/null -w "%{http_code} %{size_download}\n" -H "Range: bytes=-1024" $G      # 206 1024
curl -s -o /dev/null -w "%{http_code} %{size_download}\n" -H "Range: bytes=20893000-" $G  # 206 2435
curl -s -o /dev/null -w "%{http_code}\n" -H "Range: bytes=0-99,200-299" $G               # 200 (multi-range unsupported)
curl -s -o /dev/null -w "%{http_code}\n" -H "Range: bytes=99999999-100000000" $G         # 416

# (3) conditional requests do not follow the standard
curl -s -o /dev/null -w "%{http_code}\n" -H "Range: bytes=0-1023" \
  -H 'If-Range: "deadbeef-1"' $G        # 206 (RFC says 200) => If-Range unreliable
curl -s -o /dev/null -w "%{http_code}\n" -H 'If-None-Match: "6ae2ff51-13ed6cb"' $G   # 200 (should be 304)

# (4) ETag = mtime-size (not a content hash)
curl -sI $G | grep -i '^etag'          # "6ae2ff51-13ed6cb"; suffix hex = Content-Length

# (5) out-of-order chunking + reconstruction (§1.5)
#  fetch chunk3..chunk0 in reverse -> concatenate in order -> gunzip -> sha256 = 8287589e…

# (6) no Digest header / no zstd
curl -sI $G | grep -i digest           # empty
curl -s -o /dev/null -w "%{size_download}\n" -H "Accept-Encoding: zstd" $B   # 74579404 (uncompressed)
```
