/**
 * Reference browser client for the distribution contract (canon v1.1 §3.3).
 *
 * Runs in a browser and in any runtime with `fetch`, `crypto.subtle` and
 * `DecompressionStream` (gzip). zstd needs `fzstd` — 6.8 KB, which is exactly what
 * canon §4 names for the zstd branch. fzstd is MIT-licensed (Arjun Barrett);
 * see NOTICE in the repository root for the full attribution and license text.
 *
 * Two properties this client exists to demonstrate:
 *
 *  1. **Concurrent chunk fetch.** Chunks are independent by construction (V5 requires
 *     each chunk to decode on its own), so they are fetched in parallel and reordered
 *     by `part`, never by arrival time.
 *
 *  2. **Cross-source continuation.** Any chunk may come from any root serving a
 *     byte-identical manifest: `base` (cluster mirror), `base_proxy` (GitHub), or a
 *     second mirror. Every chunk hash is verified before acceptance, so a truncated
 *     or wrong response from one root cannot corrupt the result — it demotes that
 *     root and the chunk is retried elsewhere. A payload started on one root can be
 *     finished on another.
 *
 * ## The trap, stated once
 *
 * Decode **each chunk separately**, then concatenate. Decoding the joined buffer in
 * one pass silently truncates a multi-chunk payload to its first frame: measured on
 * `octave.data`, 9,712,192 B decompressed to 2,541,663 B with every chunk hash still
 * green and every per-chunk check reporting PASS. Only the entry hash caught it.
 *
 * ## Rules that are not negotiable (canon §4, §3.3)
 *
 *  - Names come from `manifest.chunks[].file` verbatim. Never build them.
 *  - Plain GET only: no `Range`, no conditional requests, no custom headers.
 *  - `schema` must be one this client knows, or the whole manifest is rejected (V10).
 */

/** Chunk names are the only thing the manifest promises; nothing is derived here. */
export interface Chunk {
  part: number;
  file: string;
  bytes: number;
  sha256: string;
}

export interface Variant {
  codec: "zstd" | "gzip" | "identity";
  chunks: Chunk[];
}

export interface License {
  id: string;
  url: string;
}

export interface Entry {
  product: string;
  name: string;
  bytes: number;
  sha256: string;
  /** Per-entry override; absent means the release default applies. */
  license?: License;
  role?: "payload" | "license" | "notice";
  excluded?: { path: string; why: string }[];
  variants: Variant[];
}

export interface Manifest {
  schema: 3;
  id: string;
  chunkSize: number;
  codecs: string[];
  license: License;
  products: Record<string, Record<string, unknown>>;
  entries: Entry[];
}

export interface CatalogueEntry {
  id: string;
  /** Cluster mirror. Tried first. */
  base: string;
  /** GitHub origin. The fallback when `base` is unreachable. */
  base_proxy?: string | null;
  manifest_sha256?: string;
  license?: License | null;
}

export interface Catalogue {
  releases: CatalogueEntry[];
  excluded?: { repo: string; tag: string; reason: string }[];
}

export interface FetchOptions {
  /** Parallel chunk fetches per entry. Default 8. */
  jobs?: number;
  /** Force one codec instead of taking the manifest's order. */
  codec?: "zstd" | "gzip" | "identity";
  /** Extra roots (mirror or GitHub) for cross-source continuation. */
  fallbackRoots?: string[];
  /** Called after each entry completes. */
  onProgress?: (done: number, total: number, entry: Entry) => void;
  /** Abort every in-flight request. */
  signal?: AbortSignal;
  /** zstd decoder; required only when a zstd variant is actually used. */
  zstd?: { decompress: (input: Uint8Array) => Uint8Array };
}

const SUPPORTED_SCHEMA = 3;

/** `https://host/a/b/manifest.json` -> `https://host/a/b/` */
export function rootOf(manifestUrl: string): string {
  const url = new URL(manifestUrl);
  if (!url.pathname.endsWith("/manifest.json")) {
    throw new Error(`manifest URL must end in /manifest.json: ${manifestUrl}`);
  }
  return manifestUrl.slice(0, -"manifest.json".length);
}

/** Plain GET. No cache directive, no conditional headers, no Range. */
async function getBytes(url: string, signal?: AbortSignal): Promise<Uint8Array> {
  const res = await fetch(url, { method: "GET", signal });
  if (!res.ok) throw new Error(`GET ${url} -> ${res.status}`);
  return new Uint8Array(await res.arrayBuffer());
}

export async function sha256Hex(bytes: Uint8Array): Promise<string> {
  // Copy into a fresh ArrayBuffer. Two reasons, both real:
  //  - a subarray view would otherwise hash the whole backing buffer;
  //  - `Uint8Array<ArrayBufferLike>` may be backed by SharedArrayBuffer, which
  //    `crypto.subtle.digest` does not accept.
  const copy = new Uint8Array(bytes.byteLength);
  copy.set(bytes);
  const digest = await crypto.subtle.digest("SHA-256", copy.buffer);
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

async function inflateGzip(bytes: Uint8Array): Promise<Uint8Array> {
  const stream = new Blob([new Uint8Array(bytes)]).stream().pipeThrough(new DecompressionStream("gzip"));
  return new Uint8Array(await new Response(stream).arrayBuffer());
}

async function decodeChunk(
  codec: Variant["codec"],
  bytes: Uint8Array,
  zstd?: FetchOptions["zstd"],
): Promise<Uint8Array> {
  if (codec === "identity") return bytes;
  if (codec === "gzip") return inflateGzip(bytes);
  if (!zstd) {
    throw new Error(
      "zstd variant selected but no decoder was supplied; pass { zstd: fzstd } " +
        "(fzstd is 6.8 KB and is what canon §4 names for this branch)",
    );
  }
  return zstd.decompress(bytes);
}

/** First variant this client can actually decode, in the manifest's codec order. */
function pickVariant(entry: Entry, codecs: string[], forced?: string): Variant {
  const order = forced ? [forced] : codecs;
  for (const codec of order) {
    const variant = entry.variants.find((v) => v.codec === codec);
    if (variant) return variant;
  }
  throw new Error(`entry ${entry.name}: no variant this client can decode`);
}

/** Fetches chunks, failing over across roots. Roots are tried least-failed-first. */
class ChunkFetcher {
  private failures: number[];
  private readonly roots: string[];

  constructor(roots: string[]) {
    this.roots = roots;
    this.failures = roots.map(() => 0);
  }

  async chunk(c: Chunk, signal?: AbortSignal): Promise<Uint8Array> {
    const order = this.roots
      .map((root, i) => ({ root, i }))
      .sort((a, b) => this.failures[a.i] - this.failures[b.i]);

    let last = "no roots";
    for (const { root, i } of order) {
      let bytes: Uint8Array;
      try {
        bytes = await getBytes(root + c.file, signal);
      } catch (e) {
        last = `${root}: ${(e as Error).message}`;
        this.failures[i] += 1;
        continue;
      }
      // This check is the whole reason cross-source works: a bad response from one
      // root is caught here and simply retried on the next.
      if (bytes.byteLength !== c.bytes || (await sha256Hex(bytes)) !== c.sha256) {
        last = `${root}: sha/bytes mismatch`;
        this.failures[i] += 1;
        continue;
      }
      return bytes;
    }
    throw new Error(`chunk ${c.file} unreadable from every root (last: ${last})`);
  }

  /** Per-root failure counts, for diagnostics. */
  get stats(): Record<string, number> {
    return Object.fromEntries(this.roots.map((r, i) => [r, this.failures[i]]));
  }
}

/** Fetch one entry: concurrent chunks, per-chunk decode, ordered join, final hash. */
export async function fetchEntry(
  entry: Entry,
  roots: string[],
  codecs: string[],
  opts: FetchOptions = {},
): Promise<Uint8Array> {
  const variant = pickVariant(entry, codecs, opts.codec);
  const fetcher = new ChunkFetcher(roots);
  const jobs = Math.max(1, opts.jobs ?? 8);
  const parts: (Uint8Array | undefined)[] = new Array(variant.chunks.length);

  let next = 0;
  const worker = async () => {
    for (;;) {
      const i = next++;
      if (i >= variant.chunks.length) return;
      const c = variant.chunks[i];
      // Decode here, per chunk. Never decode the concatenation.
      parts[c.part] = await decodeChunk(variant.codec, await fetcher.chunk(c, opts.signal), opts.zstd);
    }
  };
  await Promise.all(Array.from({ length: Math.min(jobs, variant.chunks.length) }, worker));

  if (parts.some((p) => p === undefined)) throw new Error(`entry ${entry.name}: gap in chunk parts`);

  const ordered = parts as Uint8Array[];
  const total = ordered.reduce((n, p) => n + p.byteLength, 0);
  const blob = new Uint8Array(total);
  let offset = 0;
  for (const p of ordered) {
    blob.set(p, offset);
    offset += p.byteLength;
  }

  if (blob.byteLength !== entry.bytes || (await sha256Hex(blob)) !== entry.sha256) {
    throw new Error(`entry ${entry.name}: final hash check failed`);
  }
  return blob;
}

/** Fetch every entry of a release. */
export async function fetchRelease(
  manifestUrl: string,
  opts: FetchOptions = {},
): Promise<Map<string, Uint8Array>> {
  const primaryRoot = rootOf(manifestUrl);
  const roots = [primaryRoot, ...(opts.fallbackRoots ?? [])];

  const man = JSON.parse(new TextDecoder().decode(await getBytes(manifestUrl, opts.signal))) as Manifest;
  if (man.schema !== SUPPORTED_SCHEMA) {
    throw new Error(`unsupported manifest schema ${man.schema} (this client knows ${SUPPORTED_SCHEMA})`);
  }

  const out = new Map<string, Uint8Array>();
  let done = 0;
  for (const entry of man.entries) {
    out.set(`${entry.product}/${entry.name}`, await fetchEntry(entry, roots, man.codecs, opts));
    opts.onProgress?.(++done, man.entries.length, entry);
  }
  return out;
}

/**
 * Resolve a catalogue entry to its manifest URL, preferring the mirror.
 *
 * `base` is the mirror and is tried first; `base_proxy` is the GitHub origin and is
 * the fallback (canon v1.1 §5.3). Both have identical path shapes, so a failed
 * mirror only changes the host — the rest of the URL is the same.
 */
export function rootsFor(entry: CatalogueEntry): string[] {
  const roots: string[] = [];
  for (const base of [entry.base, entry.base_proxy]) {
    if (typeof base === "string" && base) roots.push(base.endsWith("/") ? base : base + "/");
  }
  return roots;
}

/** Whether the client can serve this entry without an optional decoder. */
export function decodableWithoutZstd(entry: Entry): boolean {
  return entry.variants.some((v) => v.codec === "gzip" || v.codec === "identity");
}
