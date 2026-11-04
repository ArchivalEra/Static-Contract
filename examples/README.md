# examples

Reference clients for the distribution contract. Both are executable and were run
against the live catalogue; neither is a sketch.

## `fetch-concurrent.py` — concurrent chunk fetch with cross-source continuation

Implements canon v1.1 §3.3 and the two properties this repository depends on.

**Concurrency.** Chunks are independent by construction (V5 requires every chunk to
decode on its own), so they are fetched in parallel and reordered by `part`, never by
arrival time.

**Cross-source continuation.** Every chunk may come from any root serving the same
manifest: `base` (cluster mirror), `base_proxy` (GitHub), or a second mirror. The
chunk `sha256` is verified before the chunk is accepted, so a truncated or wrong
response from one root cannot corrupt the result — it just demotes that root and the
chunk is retried elsewhere. Roots are tried least-failed-first so a dead mirror is not
hammered once per chunk.

**Why mixing is safe.** Both roots must serve a byte-identical `manifest.json`; the
client compares them and refuses to mix otherwise. Because chunk names, sizes and
hashes then agree, a payload started on one root and finished on another reassembles
correctly.

**The trap this example exists to document.** Decode each chunk **separately**, then
concatenate. Decoding the joined buffer in one pass silently truncates a multi-chunk
payload to its first frame: measured on `octave.data`, a 9,712,192 B payload
decompressed to 2,541,663 B with every chunk hash still green and the per-chunk
checks all reporting PASS. Only the final entry hash caught it.

```bash
# single root
python3 fetch-concurrent.py \
  https://static.isui.ren/<owner>/<repo>/releases/download/<tag>/manifest.json out/

# two roots, cross-source continuation
python3 fetch-concurrent.py \
  https://static.isui.ren/<owner>/<repo>/releases/download/<tag>/manifest.json out/ \
  --fallback https://github.com/<owner>/<repo>/releases/download/<tag>/manifest.json \
  --jobs 8
```

Options: `--jobs N` (default 8), `--codec zstd|gzip|identity` (default: manifest order),
`--proxy http://host:port`.

## `verify-three-lines.py` — whose edge did the bytes cross?

Answers a different question from "does it fetch". All three roots fetch fine; the
question is whether the bytes actually transited the platform each URL claims to use.

The criterion is platform fingerprints in the response headers:

| Line | Fingerprint |
|---|---|
| Cloudflare | `server: cloudflare` + `cf-ray` |
| EdgeOne | `eo-log-uuid`, `eo-cache-status`, `report-to: nel.teo-rum.com` |
| GitHub | `server: github.com`, or the Azure Blob `x-ms-*` headers |

A false negative worth remembering: EdgeOne **passes upstream headers through**, so a
response served by EdgeOne can still say `server: Windows-Azure-Blob` and carry
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
PASS cf          server=cloudflare, cf-ray=a55111fb1af77a17
PASS eo          eo-cache-status, eo-log-uuid, report-to→teo-rum.com
PASS base_proxy  server=Windows-Azure-Blob/1.0, x-ms-* (Azure Blob direct)

# end-to-end, identity codec, LLVM v0.1.6
cf  entries=14 chunks=35 total=122967501B digest=9fe229759cc01fcb
eo  entries=14 chunks=35 total=122967501B digest=9fe229759cc01fcb
gh  entries=14 chunks=35 total=122967501B digest=9fe229759cc01fcb

# codec independence: gzip and zstd decode to byte-identical trees
# failover: dead primary root, 10 chunks of clang.wasm all served by the fallback,
#           primary demoted after a single failure, entry sha verified
```
