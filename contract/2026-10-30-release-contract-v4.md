# Release Contract v4 · Final

> ## **SUPERSEDED IN PART** — V1–V10 remain in force; only the "schema: 2" clause has been replaced by v1.1 (schema: 3).
>
> Read V1–V10 in this document. The license field and the schema version are governed by V11 in
> `specs/2026-11-01-release-contract-v1.1-license.md`; the current value is `schema: 3`.

> **Status**: verified locally. **Generator self-test 43/43, validator self-test 26/26, real data 168 PASS / 0 FAIL (including per-chunk verification against disk)**, and all three codecs agree byte-for-byte on the end-to-end sha.
> **The numbers are a snapshot of that run; rerun commands are in §9.** (Repository discipline 2's `[[key]]` ledger covers only `STATE.md`; `specs/` is outside its scan surface — a stated gap, not a claim that it was checked.)
> **Goal**: **apt's robustness plus HTTP's simplicity.** Every kind of content on the static site (wasm / tar / zip / html / fonts / images) uses this one scheme.
> **The convergence point of four rounds of design-it-twice**; the criteria that killed the rejected designs are preserved in §8.

---

## 0. In one sentence

> **One release = one immutable tag = one `manifest.json` plus N flat assets.**
> Names admit only characters GitHub will not rewrite (whitelist), therefore **`manifest.file` is always identical to the real asset name**.
> The client **takes names from the manifest only and never assembles them**, therefore **a 404 has exactly one meaning**.
> All bytes travel over **plain GET**: no Range, no conditional requests, no custom headers.

---

## 1. Name whitelist (the foundation of v4)

```regex
^[A-Za-z0-9_-][A-Za-z0-9._-]*$
```

Plus three constraints: **no `..`**, **no trailing `.`**, **≤ 255 characters** (GitHub hard limit; measured: 256 returns 422).

**Length budget this protocol imposes on itself (tighter than the platform limit, deliberately)**:

| Item | Value | Criterion |
|---|---|---|
| Hard limit | 255 | Measured on GitHub: 255 uploads, 256 returns `name is too long` |
| **Recommended budget** | **≤ 64** | Name = `<product>__<payload>.<codec>.<NNN>`; leaves ~25 characters of headroom for the product and ~25 for the payload name.<br>Largest measured instance `omc__OpenModelicaCompiler_bg.wasm.zstd.014` = 42 characters |
| Over-budget handling | **generator errors out and asks for a shorter name** | Silent truncation is forbidden (truncation = the name changed = the manifest points at an asset that does not exist) |

**Why recommend 64 instead of hugging 255**: all three segments of the name carry real meaning (product / payload / codec+index), and once padded toward 255 nobody can read it; the longer the payload name, the more likely it contains characters that need flattening. The generator **hard-rejects** anything over 255 and does not block between 64 and 255 (it only warns), because that range is the producer's judgement call.

**Why these rules — measured (2026-10-31, real GitHub upload and read-back)**:

| Input | What GitHub actually stores | Verdict |
|---|---|---|
| `a.b_c-D9.zstd.000` | unchanged, byte for byte | pass (inside the whitelist) |
| `UPPER.Mixed.Case.000` | unchanged, byte for byte | pass (uppercase is stable) |
| `-leading-hyphen` | unchanged, byte for byte | pass (leading hyphen is stable) |
| `sp ace.bin` | `sp.ace.bin` | reject (space becomes dot) |
| `pct%41.bin` | `pct.41.bin` | reject (`%` becomes dot) |
| `paren(1).bin` | `paren.1.bin` | reject (parentheses deleted) |
| `a<U+4E2D>b.bin` | `a.b.bin` | reject (non-ASCII deleted; 7 characters to 5) |
| `.hidden.bin` | `default.hidden.bin` | reject (leading dot gains a prefix) |
| `dots...many.000` | `dots.many.000` | reject (runs of dots collapsed) |
| `trailing-dot.` | `default.trailing-dot` | reject (trailing dot gains a prefix) |

**An over-length name errors out (422), but a rewrite does not.** That is the only reason the whitelist exists: **constrain the character set yourself rather than bet on the platform's normalisation rules** — once a rewrite happens, `manifest.file` points at an asset that does not exist, and the symptom is indistinguishable from "never published". That is exactly the unattributable failure we are eliminating.

**The payoff of the whitelist**: the `file` field **is** the asset name, so no map between logical path and physical short name is needed (apt's `Filename` carries directory levels; we do not need that, because the whitelist guarantees "what you write is what is stored" at the source).

**Recommended format (not part of the contract)**: `<arch>__<payload>.<codec>.<NNN>`.
Examples: `omc__OpenModelicaCompiler_bg.wasm.zstd.014` (37 characters), `wasm32__numgradient.oct.gzip.000` (34 characters).

---

## 2. Manifest structure

```json
{
  "schema": 2,
  "id": "Octave-Full-Wasm/optim-1.6.3",
  "chunkSize": 5242880,
  "codecs": [
    "zstd", "gzip", "identity"
  ],
  "products": {
    "src":    {"form": "pkg"},
    "wasm32": {"form": "octdir", "arch": "wasm32", "src": "src"},
    "wasm64": {"form": "octdir", "arch": "wasm64", "src": "src"}
  },
  "entries": [
    {
      "product": "src",
      "name": "optim-1.6.3.tar.gz",
      "bytes": 422679,
      "sha256": "59fb3771…3a14",
      "variants": [
        {"codec": "identity", "chunks": [
          {"part": 0, "file": "src__optim-1.6.3.tar.gz.identity.000",
           "bytes": 422679, "sha256": "59fb3771…3a14"}
        ]}
      ]
    },
    {
      "product": "wasm32",
      "name": "__bfgsmin.oct",
      "bytes": 57271,
      "sha256": "f878860d…09d4",
      "variants": [
        {"codec": "zstd", "chunks": [
          {"part": 0, "file": "wasm32____bfgsmin.oct.zstd.000",
           "bytes": 12692, "sha256": "785e172f…8e47"}
        ]},
        {"codec": "gzip", "chunks": […]},
        {"codec": "identity", "chunks": […]}
      ]
    }
  ]
}
```

### 2.1 Three layers, each answering one question

| Layer | Answers | Why it must exist |
|---|---|---|
| **`products`** | which logical products this release has (with `form`/`arch`/`src`) | **`optim`'s 5 `.oct` files have identical names in wasm32 and wasm64 and entirely different bytes** (measured: 5/5 collide, count of equal shas = 0). Without this layer, entries cannot tell them apart |
| **`entries[]`** | the full byte identity of each payload (`bytes`/`sha256`/`variants`) | **apt's robustness**: each record is self-sufficient; taken alone it still works |
| **`variants[].chunks[]`** | the chunks of each codec | EdgeOne drops to 0.93MB/s above 20MB => chunks must be ≤5MiB |

### 2.2 The `src` edge: where AGPL lands

```json
"wasm32": {"form": "octdir", "arch": "wasm32", "src": "src"}
```

**Source and artifacts must be in the same release** (confirmed by AGPL review across all four repositories). `src` points at a source product inside the same release.

**`form`/`arch` live on the product; names do not need `.src`/`.raw`** — this answers the user's question: format is not binary (src vs raw) but three-dimensional (`form`, 6 values × `arch` × `content`), and each dimension already has a home. Putting the format into the name = **repeating one fact 45 times** (OM's 74.5MB wasm has 45 chunk files), where the manifest needs it once.

### 2.3 No blob deduplication (**apt's choice**)

Across the four rounds I once adopted a "content identity layer" for dedup (UI dist: 21 paths / 10 contents, saving 48.9% of assets). **Withdrawn on apt's criterion**:

Measured: apt knowingly duplicates — 143 `Architecture: all` entries in the `amd64` index and **the same 143 entries** in the `i386` index:

```
amd64: 221 amd64 entries + 143 all
i386 : 146 i386  entries + 143 all   <- copied again
```

**This is not laziness; it is "every index is self-sufficient"**: an `amd64` client downloads a single file and has the complete resolvable set. Dedup would introduce the coupling "deleting one member affects another", and apt deliberately refuses that.

**Cost**: the same content is stored once per product. **Accepted.**

---

## 3. Invariants (fail-closed)

| # | Invariant | Reverse case |
|---|---|---|
| **V1** | Every `chunks[].file` matches the whitelist (`^[A-Za-z0-9_-][A-Za-z0-9._-]*$`, no `..`, no trailing `.`, ≤255) | `sp ace.bin` / `dots...many.000` / `.hidden` / `a<U+4E2D>b.bin` all rejected |
| **V2** | All `file` values are **globally unique** across the whole release | two chunks use the same file |
| **V3** | Within `entries[]`, `(product, name)` is unique; `products{}` ids are unique too (and an id must pass the whitelist — it becomes a filename prefix) | wasm32 and wasm64 may each carry a `numgradient.oct` (different products); a duplicate name inside one product => reject |
| **V4** | Every entry's `variants` is non-empty and contains **exactly one `identity`, in last position** | zstd only (no path forward if the decoder is unavailable) |
| **V5** | Every variant's `chunks[].part` is exactly `0..N-1`, contiguous, no gaps; **all codecs of one entry must have the same chunk count** (they slice the same original bytes) | delete a middle chunk / one codec is a chunk short |
| **V6** | `0 < chunkSize ≤ 2^25` (fzstd backreference limit) | `chunkSize = 2^26` |
| **V7** | `Σ(identity.chunks.bytes) == entry.bytes`; **the sha of the concatenated identity chunks must equal `entry.sha256` byte for byte** (the validator checks against disk when given `--base`) | `bytes` off by one / a file missing on disk / a chunk swapped |
| **V8** | `product.src`, if present, must resolve to a product **without `arch`** in the same release; a product without `arch` must not carry `src` | dangling `src` / self-reference |
| **V9** | `codecs[]` is a non-empty array of strings, an **open vocabulary** (not an enum); every codec an entry uses must already be declared in `codecs[]` | add `br`/`xz` without a schema change; an entry uses an undeclared codec => reject |
| **V10** | `schema` is a value the client understands, otherwise the whole release is rejected | a future `schema:3` force-parsed by an old client |

### No upper bound (**spelled out so nobody mistakes a platform number for protocol shape again**)

**`entries[]` has no count limit, and neither does the asset count.** 3 or 3000, the protocol treats them the same.

On 2026-10-31 we measured that capacity differs by platform (GitHub: 1000 assets per release, error field `file_count`), **but that does not enter the protocol.** The maintainer ruled that no further messages questioning the protocol are needed: hosts such as gitcode differ from one another anyway, so the protocol is simply unbounded.

**Criterion**: platform capacity is the **distributor's** problem. If a host cannot hold the release, that host decides how to split it (multiple releases / another platform / bucketing). That is **deployment shape**, not **content semantics**. Writing it into a contract invariant would freeze "one platform's limit on one particular day" into the protocol's shape, so switching hosts would mean editing the contract — exactly the coupling this contract least wants.

**What the generator and the validator do about it**:
- the generator **reports counts only** ("expected N entries / M assets") and **blocks no quantity**;
- the validator **sets no** asset quota criterion (the self-test includes a 1202-entry manifest that must be **valid**);
- both keep the constraints that are **the protocol's own** — `chunkSize`, the whitelist. Those are the criteria.

---

## 4. Client algorithm (HTTP simplicity, made concrete)

```
1. GET <base>/manifest.json                     <- the only URL the whole flow needs to "know"
2. validate schema / invariants (local, 0 requests)
3. pick a product (by form/arch; the source path reads the src product only)
4. for each entry, in codecs order pick the first decodable branch:
     name = variant.chunks[i].file              <- take it verbatim, never assemble
     GET <base>/<name>                          <- plain GET
     verify byte count + per-chunk sha256
     decode (gzip=native / zstd=fzstd 6.8KB / identity=no-op)
5. concatenate -> verify entry.sha256 -> deliver
```

**Three iron rules**:
1. **Never assemble names** — take the `file` field only (a client that assembles its own returns to "the 404 with four causes and one symptom" the moment it gets one wrong)
2. **Never probe by trial and error** — `variants` is a declaration, not something to discover through 404s
3. **No Range / conditional requests / custom headers** — plain GET throughout

---

## 5. Measured results (2026-10-31, local)

### 5.1 Generator self-test 40/40 (each case maps to a listed criterion)

```
A. Whitelist reverse cases, 9 (measured GitHub rewrites, reproduced verbatim; all must be rejected)
   consecutive dots / leading dot / trailing dot / space / % / parentheses / non-ASCII / slash / trailing newline
B. Whitelist positive cases, 3 (measured: GitHub preserves them verbatim)
   a.b_c-D9.zstd.000 / UPPER.Mixed.Case.000 / -leading-hyphen
C. v4 structure, 10
   3 products / src edge present / same name across arch does not collapse / the two shas differ /
   already-compressed formats get identity only / 11MiB -> 3 chunks / every name passes the whitelist /
   every name unique / each entry.sha matches the on-disk identity concatenation / each chunk decodes standalone
D. Reverse and boundary cases, 16 (must report / parameters actually take effect)
   chunkSize>2^25 / =0 / negative /
   two files with the same name and no arch -> 2 entries with different file names / both shas match disk /
   dangling src / self-referential src / no-arch product carrying src / duplicate product id /
   chunkSize parameter actually takes effect (1MiB -> 3 chunks) / recursive subdirectory collection / subdirectory flattening /
   html goes through all three codecs / css goes through all three codecs / woff2 fonts identity only / gzip output reproducible
E. Empty input, 2: no products / empty directory
```

**Validator `--selftest` 26/26**: 1 valid manifest that reports nothing + 23 that must report (a reverse case for each of V1–V10, including the dedicated "chunkSize lies" case) + 2 empty inputs.

**Real data 168 PASS / 0 FAIL** (74.5MB wasm, 15 chunks × 3 codecs, including **per-codec, per-chunk bytes+sha verification against disk** + the total identity concatenation sha).

### 5.2 The 5MiB chunking mechanism (74.5MB wasm, real artifact)

```
payload 74,579,404 B   chunkSize 5,242,880
zstd     15 chunks  total 15,349,112  largest chunk 1,275,256  <=5MiB OK
gzip     15 chunks  total 20,908,462  largest chunk 1,729,488  <=5MiB OK
identity 15 chunks  total 74,579,404  largest chunk 5,242,880  <=5MiB OK (exactly 5×1024×1024)
expected chunks ceil(74579404/5242880) = 15  OK  all three codecs agree on chunk count
```

### 5.3 Browser end-to-end (all three codecs pass, every request a plain GET)

| Codec | Chunks | Bytes | sha | Requests | With Range/conditional headers | Time (local) |
|---|---|---|---|---|---|---|
| **zstd** | 15 | 74,579,404 | byte-identical | 15+1 | **0** | 595ms (decoder load 7ms) |
| **gzip** | 15 | 74,579,404 | match | 15+1 | **0** | 498ms |
| **identity** | 15 | 74,579,404 | match | 15+1 | **0** | 372ms |

**No network penalty locally => identity is fastest; on real EdgeOne, zstd's 26.6% size advantage will win** (this one is an inference, not a measurement).

### 5.4 Real data: optim 1.6.3

```
products = ['src', 'wasm32', 'wasm64']   entries = 11
src/optim-1.6.3.tar.gz:        422,679 B -> 1 chunk × 1 codec  [already compressed: identity only]
wasm32/__bfgsmin.oct:           57,271 B -> 1 chunk × 3 codecs
wasm32/__disna_optim__.oct:     12,837 B -> 1 chunk × 3 codecs
wasm32/__max_nargin_optim__.oct: 8,311 B -> 1 chunk × 3 codecs
wasm32/numgradient.oct:         17,025 B -> 1 chunk × 3 codecs
wasm32/numhessian.oct:          17,515 B -> 1 chunk × 3 codecs
wasm64/(the same 5 names, all with different bytes)
```

**Same name across arch (`numgradient.oct` ×2) is resolved by `product` grouping; each of the two entries is self-sufficient.**

---

## 6. Coverage: everything a static site serves

**All measured** (not inferred; rerun in §9 item 5).

| Content type | How v4 handles it | Measured |
|---|---|---|
| **wasm** (engine/toolchain) | chunked + three codecs | 74,579,404 B -> 15 chunks × 3 codecs, end-to-end sha byte-identical |
| **tar/zip/whl** (source packages) | **identity only**, still chunked | `optim-1.6.3.tar.gz` 422,679 B -> 1 chunk × **identity only** (recompressing a zip saves 4.6%: wasted work) |
| **oct binaries** | chunked + three codecs | all 10 `.oct` in `optim` are 1 chunk × 3 codecs |
| **HTML** | three codecs (not an already-compressed format) | `index.html` 29 B -> 1 chunk × **3 codecs** confirmed |
| **CSS** | three codecs | `css/app.css` 15 B -> 1 chunk × **3 codecs** confirmed |
| **Fonts** (woff2/woff/ttf/otf/eot) | **identity only** | `fonts/a.woff2` 30,000 B -> 1 chunk × **identity only** confirmed |
| **Images** (png/jpg/webp/avif/gif) | **identity only** | `img/big.avif` 60,000 B -> 1 chunk × **identity only** confirmed |
| **Audio/video** (mp4/webm/mp3/ogg) | **identity only** | already in the `PRECOMPRESSED` list |
| **Oversized images** (>5MiB) | identity, **chunked** | same chunk logic; the consumer reassembles |
| **Nested site tree** | **recursive collection + path flattening** | `site/{css,fonts,img}/x` -> name `site/css__app.css` (`/` -> `__`) confirmed |

**v4's boundary, stated plainly**: it covers **byte distribution of release artifacts**, not **the site's routing and rendering**.
The UI's Astro output (files such as `_astro/App.CUPGshJq.js`, which carry a content hash in the name) keeps being served straight from Pages —
they already satisfy "never updated" (the name contains a hash), so they do not need a manifest layer on top.

---

## 7. Relationship to existing contracts

| Layer | Owner | Relation to v4 |
|---|---|---|
| **Content contract** (`content-list`: version/form/content/consumer/deps) | repo semantics + host schema | **upstream**. Answers "what exists, can it be used, who is it for". v4 does not touch it |
| **Engine contract** (`octave.build.json`) | host | **upstream**. Answers "how the bytes are built". `measured.files[].sha256` is v4's provenance |
| **Release contract v4** (this file) | designed here / produced by each repo | **middle layer**. Touches byte identity + chunking only |
| **Deployment contract** (Astro base/literals) | UI | **downstream** |

**The absorption audit's conclusion stands**: of the content contract's 23 fields, only 5 (`sha256`/`url`/`size`/`files`/`upstream_url`) can be taken over by v4; the other 18 are semantic domain. **v4 replaces neither the content contract nor the engine contract.**

---

## 8. Designs rejected across the four rounds (against reopening)

| Round | Design | Rejection criterion |
|---|---|---|
| Round 1 | `<asset>.<bytes>.<sha256>.codec.NNN` (111 characters) | **Client URL correctness becomes undiagnosable**: wrong sha / wrong tag / truncated name / never published all produce the same 404 |
| Round 2 A | pure coordinate `z-000` (5 characters) | codec encoded in a single-letter implicit table; adding a format means adding a letter, i.e. changing the grammar |
| Round 2 B | self-describing short name `aid.codec.NNNN` (`aid=hash(sha+chunkSize)`) | **the name still contains identity that must be computed**, making it a variant of the round-1 error; introduces a second hash preimage as a new compatibility surface |
| Round 2 C | `slot.i.codec` + zero-request preflight | its skeleton was adopted (v4 later took its whitelist idea) |
| Round 3 A | flat four record types (product/member/blob/chunk) | **`blob` dedup withdrawn** (see the apt criterion in §2.3); flattening chunk records does not repay its complexity, so chunks were nested inside variant instead |
| Round 3 B | index split by arch (apt style) | **measured: splitting loses bytes**: optim client 926 vs 923 B gz (3 B worse) while adding one serial request (33% slower startup) |

---

## 9. How to rerun

```bash
# generator self-test (40 cases)
source /mnt/hdd/toolenv/bin/activate
python3 tools/make-manifest-v4.py --selftest

# real data (optim: 11 payloads + src)
python3 tools/make-manifest-v4.py --out /tmp/v4 --id "Octave-Full-Wasm/optim-1.6.3" \
  --product src:pkg:/mnt/hdd/zcode-projects/Octave-Full-Wasm/site/assets/forge/optim-1.6.3.tar.gz \
  --product wasm32:octdir:wasm32:src:/mnt/hdd/zcode-projects/Octave-Full-Wasm/site/assets/octdir/optim \
  --product wasm64:octdir:wasm64:src:/mnt/hdd/zcode-projects/Octave-Full-Wasm/site/assets/octdir-w64/optim

# chunking mechanism (74.5MB -> 15 chunks)
python3 tools/make-manifest-v4.py --out /tmp/v4big --id "OM/omc" \
  --product omc:file:omc:/mnt/hdd/openmodelica-wasm-build/site-omc/omc/OpenModelicaCompiler_bg.wasm

# end-to-end (three codecs, proving "plain GET throughout")
cd /tmp/v4big && python3 -m http.server 8950 &
node /mnt/hdd/zcode-test/harness/poc-v4.mjs http://127.0.0.1:8950 zstd 8      # => 15 chunks / sha match / 0 conditional headers
node /mnt/hdd/zcode-test/harness/poc-v4.mjs http://127.0.0.1:8950 gzip 8
node /mnt/hdd/zcode-test/harness/poc-v4.mjs http://127.0.0.1:8950 identity 8

# whitelist reverse assertions (the 8 measured GitHub rewrite cases must all be rejected)
# see the first 10 cases in tools/make-manifest-v4.py --selftest
```

**The original measurement of GitHub rewriting** (this is the only reason the whitelist exists; rerunnable):
```bash
RID=$(gh api -X POST repos/<o>/<r>/releases -f tag_name=t -f name=t -F draft=true -q .id)
for nm in 'sp ace.bin' 'dots...many.000' '.hidden.bin' $'a\xe4\xb8\xadb.bin'; do
  gh api --method POST -H 'Content-Type: application/octet-stream' \
    "https://uploads.github.com/repos/<o>/<r>/releases/$RID/assets?name=$(python3 -c "import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1],safe=''))" "$nm")" \
    --input /tmp/p.bin -q '.name'
done
# => sp.ace.bin / dots.many.000 / default.hidden.bin / a.b.bin
```
