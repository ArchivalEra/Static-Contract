#!/usr/bin/env python3
"""Contract client reference: concurrent chunk fetch with cross-source continuation.

Implements canon v1.1 §3.3 (client algorithm) plus the two properties this
repository actually relies on:

  1. **Concurrent chunk fetch.** Chunks are independent (V5 requires each chunk to
     decode on its own), so they can be fetched in parallel. Order is restored by
     `part`, never by arrival time.

  2. **Cross-source continuation.** A chunk may be fetched from any root that serves
     the same manifest: `base` (cluster mirror), `base_proxy` (GitHub), or a second
     mirror. The sha256 of every chunk is checked before it is accepted, so a wrong
     or truncated response from one root cannot corrupt the result — it just triggers
     a retry on the next root. This is why the catalogue can list two roots with
     different hosts but identical bytes.

Rules that are not negotiable (canon §4, §3.3):

  * Names come from `manifest.chunks[].file` **verbatim**. Never build them.
  * Every chunk is decoded **individually**, then concatenated. Decoding the
    concatenation in one pass silently truncates multi-chunk payloads to the first
    frame (measured: a 9.7 MB payload became 2.5 MB with every chunk sha still green).
  * Plain GET only. No Range, no conditional requests, no custom headers.

Usage:
    python3 fetch-concurrent.py <manifest-url> <outdir> [--jobs N] [--codec C]

    # single root
    python3 fetch-concurrent.py \
        https://static.isui.ren/<owner>/<repo>/releases/download/<tag>/manifest.json out/

    # two roots, cross-source continuation enabled
    python3 fetch-concurrent.py \
        https://static.isui.ren/<owner>/<repo>/releases/download/<tag>/manifest.json out/ \
        --fallback https://github.com/<owner>/<repo>/releases/download/<tag>/manifest.json
"""
import argparse
import gzip
import hashlib
import json
import os
import sys
import threading
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

USER_AGENT = "contract-client/1"

# A root is a base URL ending in "/". Chunks are addressed as root + chunk["file"].
def root_of(manifest_url: str) -> str:
    url = manifest_url.rstrip("/")
    assert url.endswith("/manifest.json"), "manifest URL must end in /manifest.json"
    return url[: -len("manifest.json")]


def fetch(url: str, timeout: float = 120.0) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r:   # plain GET
        return r.read()


def decode(codec: str, blob: bytes) -> bytes:
    if codec == "identity":
        return blob
    if codec == "gzip":
        return gzip.decompress(blob)
    if codec == "zstd":
        import zstandard                                      # optional dependency
        return zstandard.ZstdDecompressor().decompress(blob)
    raise ValueError("unsupported codec %r (the manifest declares it; this client does not)" % codec)


def pick_variant(entry, codecs):
    """First decodable variant in the manifest's codec order."""
    by_codec = {v["codec"]: v for v in entry["variants"]}
    for codec in codecs:
        if codec in by_codec:
            return by_codec[codec]
    raise ValueError("entry %r offers no variant this client can decode" % entry["name"])


class Fetcher:
    """Fetches chunks, failing over across roots. Thread-safe."""

    def __init__(self, roots):
        self.roots = roots
        self.lock = threading.Lock()
        self.failures = {r: 0 for r in roots}

    def chunk(self, name: str, expect_sha: str, expect_bytes: int) -> bytes:
        last = None
        # Round-robin starts at the least-failed root so a dead mirror is not
        # hammered on every chunk.
        with self.lock:
            order = sorted(self.roots, key=lambda r: self.failures[r])
        for root in order:
            try:
                blob = fetch(root + name)
            except (urllib.error.URLError, OSError, TimeoutError) as e:
                last = "%s: %s" % (root, type(e).__name__)
                with self.lock:
                    self.failures[root] += 1
                continue
            # Byte and hash checks are the whole reason cross-source works: a bad
            # response from one root is detected here and simply retried elsewhere.
            if len(blob) != expect_bytes or hashlib.sha256(blob).hexdigest() != expect_sha:
                last = "%s: sha/bytes mismatch" % root
                with self.lock:
                    self.failures[root] += 1
                continue
            return blob
        raise SystemExit("chunk %s unreadable from every root (last: %s)" % (name, last))


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("manifest_url")
    ap.add_argument("outdir")
    ap.add_argument("--fallback", action="append", default=[],
                    help="additional manifest URL; its chunks are used when the primary fails")
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--codec", default=None, help="force one codec (default: manifest order)")
    ap.add_argument("--proxy", default=None, help="http proxy, e.g. http://127.0.0.1:2080")
    args = ap.parse_args(argv)

    if args.proxy:
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": args.proxy, "https": args.proxy}))
        urllib.request.install_opener(opener)

    primary = root_of(args.manifest_url)
    manifests = [json.loads(fetch(u)) for u in [args.manifest_url] + args.fallback]

    # Cross-source continuation requires identical manifests. Two roots serving
    # different tags would produce different chunk lists — refuse rather than mix.
    first = json.dumps(manifests[0], sort_keys=True)
    roots = [primary]
    for url, man in zip(args.fallback, manifests[1:]):
        if json.dumps(man, sort_keys=True) != first:
            raise SystemExit("manifest mismatch between %s and %s — refusing to mix sources"
                             % (args.manifest_url, url))
        roots.append(root_of(url))

    man = manifests[0]
    codecs = [args.codec] if args.codec else man["codecs"]
    print("roots: %d | entries: %d | codecs: %s | jobs: %d"
          % (len(roots), len(man["entries"]), codecs, args.jobs))

    fetcher = Fetcher(roots)
    os.makedirs(args.outdir, exist_ok=True)

    total_chunks = 0
    for entry in man["entries"]:
        variant = pick_variant(entry, codecs)
        chunks = variant["chunks"]

        # Fetch all chunks of this entry concurrently; restore order by `part`.
        parts = [None] * len(chunks)
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            futures = {
                pool.submit(fetcher.chunk, c["file"], c["sha256"], c["bytes"]): c["part"]
                for c in chunks
            }
            for fut in as_completed(futures):
                parts[futures[fut]] = fut.result()
        assert all(p is not None for p in parts), "gap in chunk parts"

        # Decode each chunk separately, then concatenate. Never decode the join.
        blob = b"".join(decode(variant["codec"], p) for p in parts)

        if len(blob) != entry["bytes"] or hashlib.sha256(blob).hexdigest() != entry["sha256"]:
            raise SystemExit("entry %s failed its final hash check" % entry["name"])

        dest = os.path.join(args.outdir, entry["product"], entry["name"])
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as fh:
            fh.write(blob)

        total_chunks += len(chunks)
        print("  ok %-12s %-34s %10d B  %-8s %d chunk(s)"
              % (entry["product"], entry["name"], len(blob), variant["codec"], len(chunks)))

    print("\ndone: %d entries, %d chunks, %d bytes, every hash verified"
          % (len(man["entries"]), total_chunks, sum(e["bytes"] for e in man["entries"])))
    if any(fetcher.failures.values()):
        print("root failures during this run: %s" % fetcher.failures)


if __name__ == "__main__":
    main(sys.argv[1:])
