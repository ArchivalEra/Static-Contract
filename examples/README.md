# examples

Two files, both run against the live catalogue; neither is a sketch.

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
peak memory is the largest single entry rather than the whole release:

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

**Concurrency.** Chunks are independent by construction (V5 requires every chunk to
decode on its own), so they are fetched in parallel and reordered by `part`.

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

## Measured results (2026-11-04)

```
# three-line edge acceptance
PASS cf          server=cloudflare, cf-ray=a551e87a9826ec6d
PASS eo          eo-cache-status, eo-log-uuid, report-to→teo-rum.com
PASS base_proxy  server=Windows-Azure-Blob/1.0, x-ms-* (Azure Blob direct)

# end-to-end, identity codec, LLVM v0.1.6
cf  entries=14 chunks=35 total=122967501B digest=9fe229759cc01fcb
eo  entries=14 chunks=35 total=122967501B digest=9fe229759cc01fcb
gh  entries=14 chunks=35 total=122967501B digest=9fe229759cc01fcb

# catalogue reachability, both roots
18/18 releases: 200 on base and base_proxy, byte-identical manifest,
                sha256 matches the catalogue's manifest_sha256
```
