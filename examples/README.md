# examples

Three files, all run against the live catalogue; none is a sketch.

- **`fetch-concurrent.ts`** — the reference client. Both consumers of this contract
  (Octave-UI's package manager and in-site downloads) run in a browser, so the
  reference implementation is TypeScript.
- **`verify-three-lines.py`** — acceptance for a different question: not "does it
  fetch" but "whose edge did the bytes cross".

## `fetch-concurrent.ts` — the browser client

TypeScript, strict, no runtime dependencies. Uses only browser primitives:
`fetch`, `crypto.subtle.digest`, `DecompressionStream`, `AbortSignal`.

The interface is one function and one handle:

```ts
import { openRelease } from "./fetch-concurrent";

const rel = await openRelease(catalogue.releases.find((r) => r.id === "LLVM-wasm/v0.1.6")!);
const entry = rel.entries.find((e) => e.key === "toolchain/clang.wasm")!;
const bytes = await rel.read(entry);        // verified: length + sha256
```

Roots, manifests, chunks, codecs, retries, timeouts, concurrency and per-chunk
hashes stay behind that line. A caller never sees a chunk, so it cannot assemble a
name, decode a concatenation, or skip a hash.

For a whole release, `readAll()` yields entries one at a time in manifest order, so
peak memory is bounded by one entry rather than the whole release (the entry
itself peaks at roughly 2x its size, because the decoded chunks and the joined
buffer coexist while assembling):

```ts
for await (const { info, bytes } of rel.readAll()) {
  await writeToDisk(info.key, bytes);        // previous bytes are collectable here
}
```

### Codecs are an open vocabulary

Canon V9 makes `codecs[]` "an open vocabulary (not an enum)" — adding `br` or `xz`
must not require a schema change or a client change. So decodability is
**discovered, never configured per call**:

- `identity` always works (a no-op).
- Anything the platform's `DecompressionStream` accepts works — `gzip`, `deflate`,
  and on newer engines `zstd` and `br`. `new DecompressionStream(name)` throws
  exactly when the platform lacks the codec, so the constructor is the probe.
- Anything else is registered once for the process:

```ts
import { useDecoder } from "./fetch-concurrent";
import * as fzstd from "fzstd";              // MIT, Arjun Barrett — see NOTICE

useDecoder("zstd", (b) => fzstd.decompress(b));
```

Registration is process-wide because codec capability is: a runtime either can
decompress zstd or it cannot, and that does not vary per release or per call. An
option on `openRelease` would put the same argument on every call site to express
a property none of them control.

A manifest declaring a codec this runtime cannot decode is **not** an error: the
client falls through to the next declared codec, per canon §3.3 ("in codecs order
pick the first decodable branch"). Only an entry with no decodable variant at all
fails, and the message names what was offered and what is missing.

### What it demonstrates

**Concurrency, with a ceiling that is not the protocol's.** Chunks are independent
by construction (V5 requires every chunk to decode on its own), so they are
fetched in parallel and reordered by `part`.

The default is **2**, and the reason is the mirror, not the contract: the
reference mirror throttles once roughly 10–15 MiB are in flight at once. With
`chunkSize` at 5 MiB, two chunks is 10 MiB — under the line — and three is 15 MiB,
over it. The chunk size is chosen with that margin in mind, so the concurrency
default follows from it. Raise `concurrency` only with a smaller `chunkSize`, or
against a mirror without a byte cap.

**Cross-source continuation.** Every chunk may come from any root serving the same
manifest: `base` (cluster mirror) or `base_proxy` (GitHub). The chunk `sha256` is
verified before acceptance, so a truncated or wrong response from one root cannot
corrupt the result — it demotes that root and the chunk is retried elsewhere. The
failure ledger is shared across all entries of a release, so a dead mirror is not
retried once per entry.

**Why mixing is safe.** Both roots must serve a byte-identical `manifest.json`;
chunk names, sizes and hashes then agree, so a payload started on one root and
finished on another reassembles correctly.

### The trap this example exists to document

Decode each chunk **separately**, then concatenate. Decoding the joined buffer in
one pass silently truncates a multi-chunk payload to its first frame: measured on
`octave.data`, a 9,712,192 B payload decompressed to 2,541,663 B with every chunk
hash still green and the per-chunk checks all reporting PASS. Only the final entry
hash caught it. This is canon §4.3.

Because of that, `read()` returns bytes only **after** the entry hash matches. A
streaming interface would hand bytes out before that gate closes, letting a consumer
persist a corrupt payload and only then learn about it.

### Verified

`tsc --strict` clean (no unused locals or parameters). Executed on Node 26 against
the live catalogue:

```
opening LLVM-wasm/v0.1.6 -> 14 entries
reading toolchain/clang.wasm (48,069,274 B, codec=zstd) -> length + sha verified
readAll() -> 14 entries, 122,967,501 B, every entry sha verified
```

Edge cases exercised against the live service:

| Case | Result |
|---|---|
| no zstd decoder registered | falls through to gzip; 48 MB entry still verifies |
| dead `base_proxy` | primary still serves; no error |
| both roots dead | `manifest-unreachable` in 39 ms, no hang |
| abort mid-flight | `aborted`, not a bare `DOMException` |
| foreign `EntryInfo` | `manifest-invalid` |
| bad catalogue pin | `manifest-pin-mismatch` |
| arbitrary codec name | accepted by `useDecoder` (open vocabulary) |
| `useDecoder("identity", …)` | refused |

## Choosing your own codec chain

The contract does not fix which branch a release is fetched from. Canon V9 calls
`codecs[]` an **open vocabulary** — a producer may offer any number of codecs, in
any order, and `identity` need not exist. The manifest's order is a suggestion;
the choice belongs to the consumer.

```ts
// Highest priority first. Falls through to the manifest's order for anything
// this list does not cover.
const release = await openRelease(ref, {
  codecPreference: ["identity", "xz", "gzip"],
});
```

Three properties make this a preference rather than a requirement:

- **The chain wins when it can.** `["gzip"]` against a release declaring
  `["zstd","gzip","identity"]` fetches gzip, not zstd.
- **It falls back when it cannot.** `["br","xz"]` against that same release still
  succeeds, using the manifest's first decodable codec. Asking for a codec the
  release does not ship is not an error.
- **Undecodable names are skipped.** A chain naming `xz` when no decoder is
  registered moves past it instead of failing.

Names are arbitrary strings, so `["identity", "avi", "iso"]` is a legal chain — it
just falls through to whatever the release actually offers.

**This is a cost decision, not a correctness one.** Measured on the reference
mirror, the same two releases:

| codec chain | wire bytes | wall clock |
|---|---|---|
| default (manifest order → `zstd`) | **22.12 MiB** | ~30 s |
| `["identity", "gzip"]` | **109.26 MiB** | 180.8 s |

Identical payload after decoding — 109.23 MiB both ways — but 4.9x the transfer
and 6x the time, because `identity` sends the raw bytes. A consumer on a fast
local link may prefer that (no decompression cost); a consumer on a metered or
slow link will not. The contract deliberately leaves that call to the client.

## `test/` — offline tests

```bash
cd examples && npm install && npm test        # 31 cases, ~0.5 s, no network
```

Every case goes through the **public interface** — `openRelease`, `read`,
`readAll`, `close`, `useDecoder` — with a fake `fetch` on `globalThis`. The client
exposes no test hooks and none were added for these tests: if a case needed
internals, it would be measuring the wrong layer. The only seam is the global
`fetch`, which the client reads at call time.

`test/fixtures.ts` builds real releases: it compresses real bytes with Node's
`zlib` (zstd and gzip), slices them into real chunks, names them per canon V1, and
hashes them. Nothing is mocked at the data level — a passing test means the client
decoded actual compressed bytes.

The suite exists to catch five traps that were each hit for real while building
this client. They are named in the file and each has a dedicated case:

| Trap | What goes wrong | Covered by |
|---|---|---|
| Decoding the concatenation | Multi-chunk payload silently truncates to its first frame; every chunk hash stays green | `multi-chunk zstd decodes each chunk separately` |
| A hole check that skips holes | `some(p => p === undefined)` never fires on `new Array(n)`, so the gap check is dead code | `readAll` / multi-chunk cases |
| A stall classified as final | One stalled request burns the whole budget and reports a failure a retry would have fixed | `an attempt budget aborts a stalled response and retries` |
| A 404 demoting a healthy mirror | One missing file pushes every later request to the fallback | `a 404 does not demote the mirror for other entries` |
| `manifest-unreachable` unreachable | Errors passed through unchanged, so the code could never surface | `manifest-unreachable is actually reachable` |

A second group covers the **codec chain**: the consumer's order wins over the manifest's, an absent or undecodable preference falls through instead of failing, duplicates are harmless, and the no-chain default still follows canon §3.3.

**These tests were verified by mutation, not by passing.** Breaking the client in
five separate ways — skipping decode, treating every failure as final, ignoring
the ledger distinction, dropping the asset-name whitelist, letting `close()` not
stop later reads — turns the suite red in each case (1, 2, 8, 1 and 1 failures
respectively). A test that cannot fail is not evidence, so this was checked
rather than assumed. One of the five cases was originally written badly enough
that it did *not* catch its mutation; it was rewritten with a real asymmetry
between the two roots, which is the only shape where a demoted mirror is
observable.

CI runs `tsc --noEmit` and the suite on every push, so the examples cannot rot
silently.

## `verify-three-lines.py` — whose edge did the bytes cross?



All three roots fetch fine; the question is whether the bytes actually transited the
platform each URL claims to use.

The criterion is platform fingerprints in the response headers:

| Line | Fingerprint |
|---|---|
| Cloudflare | `server: cloudflare` + `cf-ray` |
| EdgeOne | `eo-log-uuid`, `eo-cache-status`, `report-to: nel.teo-rum.com` |
| GitHub | `server: github.com`, or the Azure Blob `x-ms-*` headers |

A false negative worth remembering: EdgeOne **passes upstream headers through**, so
a response served by EdgeOne can still say `server: Windows-Azure-Blob` and carry
`x-served-by: cache-iad-…`. Judging by `server` alone reports "not EdgeOne" when it
plainly is. The `eo-*` headers are what prove it.

```bash
SC_HTTP_PROXY=http://127.0.0.1:2080 python3 verify-three-lines.py \
  ArchivalEra/LLVM-wasm/releases/download/v0.1.6/manifest.json
```

Exit code is non-zero if any line does not show its own edge.

## Measuring it yourself

There is no benchmark script. `fetch-concurrent.ts` is the client, so a
measurement is just the client plus a stopwatch — anything that wraps `fetch`
would be measuring the wrapper, not the path a consumer takes.

**Wall clock.** Time the read loop:

```ts
const t0 = Date.now();
const rel = await openRelease(ref);            // both roots configured, unforced
for await (const { info, bytes } of rel.readAll()) { /* consume */ }
console.log(`${((Date.now() - t0) / 1000).toFixed(1)}s`);   // read() resolves only after the sha checks
rel.close();
```

**Wire bytes.** Don't count them — read them off the manifest. Every chunk
declares its encoded size, so the transfer for a release under a given codec is a
sum, not a measurement:

```ts
const wire = entry.variants
  .find((v) => v.codec === codec)!
  .chunks.reduce((n, c) => n + c.bytes, 0);
```

Measured against the reference mirror, the declared total and an intercepted
`fetch` agreed to within 0.03 MiB (22.09 vs 22.12) — the difference is
`manifest.json` itself. That is why no wrapper is needed: the number is already in
the data.

**Which host served it.** `EntryInfo` does not expose it on purpose — a consumer
should not depend on which mirror answered. Use `verify-three-lines.py` when that
is the question.

### Recorded results (2026-11-05)

```
Octave-Full-Wasm/v0.1.0 [wasm32] + OpenModelica/v0.2.0-wasm32 [omc]
  7 files, 114,533,242 B decoded, 22.09 MiB declared wire

EO  (static.isui.ren)            3 runs: 25.2s / 26.9s / 27.4s
CF  (static.mango-mesa.ccwu.cc)  3 runs: 31.2s / 33.3s / 33.6s

Same payload, same verified sha256 on every run. EO ~20% faster on this egress.

Codec chain, same releases, measured on the same link:
  default (manifest order -> zstd)   22.09 MiB wire   ~30s
  ["identity","gzip"]               109.23 MiB wire   180.8s
```

**Caveat, measured:** direct connections from the test host to EO intermittently
stall (2 of 6 plain GETs of one cached chunk returned nothing for 15 s+). The same
URLs through a proxy were 5/5 clean, and CF direct was 6/6 clean. Both lines above
were therefore measured over the same proxy so the comparison isolates the mirror,
not the egress. A consumer whose network stalls this way will see the client spend
its retry budget and, if all roots fail, report `chunk-unavailable` — which is the
correct outcome, but `attemptBudgetMs` is the knob to raise.

### Edge acceptance

```
# three-line edge acceptance
PASS cf          server=cloudflare, cf-ray=a551e87a9826ec6d
PASS eo          eo-cache-status, eo-log-uuid, report-to->teo-rum.com
PASS base_proxy  server=Windows-Azure-Blob/1.0, x-ms-* (Azure Blob direct)

# each root fetches the whole release alone (base_proxy=null, no fallback possible)
EO  (static.isui.ren)             14/14 entries, 122,967,501 B, every sha verified,  97.8 s
CF  (static.mango-mesa.ccwu.cc)   14/14 entries, 122,967,501 B, every sha verified,  63.1 s
base_proxy (github.com)           14/14 entries, 122,967,501 B, every sha verified

# catalogue reachability, both roots
18/18 releases: 200 on base and base_proxy, byte-identical manifest,
                sha256 matches the catalogue's manifest_sha256
```
