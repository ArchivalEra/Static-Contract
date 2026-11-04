/**
 * Reference client for the distribution contract (canon v1.1 §3.3).
 *
 * Two consumers, both in a browser: Octave-UI's package manager and in-site
 * downloads. So this is TypeScript, and it uses only browser primitives.
 *
 * The interface is one function and one handle:
 *
 *   const rel = await openRelease(catalogueEntry);
 *   const bytes = await rel.read(rel.entries[0]);        // verified
 *
 * Roots, manifests, chunks, codecs, retries, timeouts, concurrency and per-chunk
 * hashes all stay behind that line. A caller never sees a chunk, so it cannot
 * assemble a name, decode a concatenation, or skip a hash.
 *
 * ## Why `read` returns verified bytes rather than a stream
 *
 * Canon §3.3 step 5 is "verify bytes + per-chunk sha256 → decode → concatenate",
 * and the entry hash is the last gate. A streaming interface hands bytes out
 * before that gate closes, so a consumer can persist 122 MB and only then learn
 * it is corrupt. Canon §4.3 records exactly that failure: every chunk hash was
 * green and only the final entry hash caught the truncation. So `read` resolves
 * only after the entry hash matches, and `readAll` exists for callers that need
 * to bound peak memory without giving up that guarantee.
 *
 * ## Codec capability belongs to the runtime, not to the call
 *
 * Canon V9 makes `codecs[]` an **open vocabulary**: "add `br`/`xz` without a
 * schema change". A producer adding a codec must not break existing clients, and
 * a client must not need a code change to gain one.
 *
 * So decodability is discovered, never configured per call:
 *
 *  - `identity` is always decodable (a no-op).
 *  - Anything the platform's `DecompressionStream` accepts is decodable —
 *    `gzip`, `deflate`, and on newer engines `zstd` and `br`, because
 *    `new DecompressionStream(name)` throws exactly when the platform lacks it.
 *  - Anything else is added once, for the whole process, with `useDecoder`.
 *    zstd before Chrome 123 / Node 22 is the case that matters:
 *
 *      import { useDecoder } from "./fetch-concurrent";
 *      import * as fzstd from "fzstd";
 *      useDecoder("zstd", (b) => fzstd.decompress(b));
 *
 * A manifest declaring a codec this runtime cannot decode does not fail: the
 * client falls through to the next declared codec, per §3.3's "in codecs order
 * pick the first decodable branch". Only an entry with no decodable variant at
 * all is an error, and the message names what was offered and what is missing.
 *
 * ## The trap this file exists to document
 *
 * Decode **each chunk separately**, then concatenate. Decoding the joined buffer
 * in one pass silently truncates a multi-chunk payload to its first frame:
 * measured on `octave.data`, 9,712,192 B decompressed to 2,541,663 B with every
 * chunk hash still green and every per-chunk check reporting PASS.
 *
 * ## Rules that are not negotiable (canon §4, §3.3)
 *
 *  - Names come from `chunks[].file` verbatim. Never build them.
 *  - Plain GET only: no `Range`, no conditional requests, no custom headers.
 *  - A `schema` this client does not know means the whole manifest is rejected.
 */

/** A catalogue entry, structurally. `verified_at` and friends are not our business. */
export interface ReleaseRef {
  id: string;
  /** Cluster mirror, tried first (canon §5.3). */
  base: string;
  /** GitHub origin, the fallback when `base` is unreachable (canon §5.3). */
  base_proxy?: string | null;
  /** When present, the manifest bytes must hash to this before anything is used. */
  manifest_sha256?: string;
}

export interface LicenseRef {
  id: string;
  url: string;
}

/** One entry, resolved: which variant this client will fetch, under which license. */
export interface EntryInfo {
  /** `<product>/<name>` — unique within a release (V3). */
  readonly key: string;
  readonly product: string;
  readonly name: string;
  /** Decoded size. `read()` returns exactly this many bytes. */
  readonly bytes: number;
  /** sha256 of the decoded bytes. `read()` does not resolve until it matches. */
  readonly sha256: string;
  readonly role: "payload" | "license" | "notice";
  /** The codec this client will use for this entry. A fact, not a prediction. */
  readonly codec: string;
  /** `entries[].license` when present, else the release default, else null. */
  readonly license: LicenseRef | null;
}

/** A release, opened. Holds no bytes; `read` fetches and verifies on demand. */
export interface ReleaseHandle {
  readonly id: string;
  /** Release-level license, before per-entry overrides. */
  readonly license: LicenseRef | null;
  /** Metadata only — zero bytes, zero chunk requests. */
  readonly entries: readonly EntryInfo[];
  /**
   * One entry, verified.
   *
   * Takes an `EntryInfo` from `entries` rather than a key: a key that does not
   * exist is then a type error rather than a runtime error mode.
   *
   * Resolves only when the entry hash matches. Concurrent calls share one root
   * health ledger.
   */
  read(entry: EntryInfo): Promise<Bytes>;
  /**
   * Every entry in manifest order, one at a time.
   *
   * Serial on purpose: one entry's bytes are released before the next is
   * fetched, so peak memory is the largest single entry rather than the whole
   * release. Fetches inside an entry still run `CONCURRENCY`-wide.
   */
  readAll(): AsyncIterable<{ info: EntryInfo; bytes: Bytes }>;
}

export interface OpenOptions {
  /** Cancels every request this handle owns. */
  signal?: AbortSignal;
}

export type ContractErrorCode =
  | "manifest-unreachable"
  | "manifest-invalid"
  | "schema-unsupported"
  | "manifest-pin-mismatch"
  | "no-decodable-variant"
  | "chunk-unavailable"
  | "entry-hash-mismatch"
  | "aborted"
  | "unsupported-environment";

export class ContractError extends Error {
  readonly code: ContractErrorCode;
  readonly entry?: string;
  readonly file?: string;
  override readonly cause?: unknown;

  constructor(
    code: ContractErrorCode,
    message: string,
    detail: { entry?: string; file?: string; cause?: unknown } = {},
  ) {
    super(message);
    this.name = "ContractError";
    this.code = code;
    this.entry = detail.entry;
    this.file = detail.file;
    this.cause = detail.cause;
  }
}

// ── codec registry ────────────────────────────────────────────────────────────

/** A decoder turns one chunk's encoded bytes into that chunk's plain bytes. */
export type Decoder = (encoded: Uint8Array) => Uint8Array | Promise<Uint8Array>;

/**
 * Bytes this module owns.
 *
 * Every buffer here came from `res.arrayBuffer()` or `DecompressionStream`, so it
 * is backed by a plain `ArrayBuffer`, never a `SharedArrayBuffer`. Saying so in
 * the type keeps the guarantee checkable instead of a comment: it is what lets
 * `crypto.subtle.digest` and `new Blob` take the view directly, with no copy.
 */
type Bytes = Uint8Array<ArrayBuffer>;

/** Codecs this process can decode beyond what the platform offers. */
const extraDecoders = new Map<string, Decoder>();

/**
 * Teach this process one more codec. Call once, at module load.
 *
 * Registration is process-wide because codec capability is: a browser either can
 * decompress zstd or it cannot, and that fact does not vary per release, per
 * call, or per consumer. Making it an option on `openRelease` would put the same
 * argument on every call site to express a property none of them control.
 *
 * Registering a codec the platform already handles is harmless — the registered
 * function wins, which is also how you override a platform decoder.
 */
export function useDecoder(codec: string, decode: Decoder): void {
  if (codec === "identity") {
    throw new ContractError("manifest-invalid", "identity is a no-op and cannot be overridden");
  }
  extraDecoders.set(codec, decode);
}

/** Whether this runtime can decode `codec`, asked at open time. */
function canDecode(codec: string): boolean {
  if (codec === "identity") return true;
  if (extraDecoders.has(codec)) return true;
  try {
    // The constructor is the probe: it throws exactly when the platform lacks it.
    new DecompressionStream(codec as CompressionFormat);
    return true;
  } catch {
    return false;
  }
}

// ── constants ─────────────────────────────────────────────────────────────────

/** Schemas this client understands. Canon v4 is 2; v1.1 is 3. */
const SUPPORTED_SCHEMAS = new Set([2, 3]);

/** V6: a chunk above this cannot be decoded independently by the named decoders. */
const MAX_CHUNK_BYTES = 2 ** 25;

/**
 * Asset names, per canon V1: `^[A-Za-z0-9_-][A-Za-z0-9._-]*$`.
 *
 * This is a security control, not tidiness. Chunk URLs are built with
 * `new URL(chunk.file, root)`, and a name like `//evil.example/x` resolves to a
 * different host — the manifest would redirect the client off the mirror.
 */
const ASSET_NAME = /^[A-Za-z0-9_-][A-Za-z0-9._-]*$/;

/** `fetch` has no timeout of its own; a server that goes quiet hangs forever. */
const TIMEOUT_MS = 120_000;

/** Parallel chunk fetches per entry. */
const CONCURRENCY = 8;

// ── internal shapes ───────────────────────────────────────────────────────────

interface RawChunk {
  part: number;
  file: string;
  bytes: number;
  sha256: string;
}

interface RawVariant {
  codec: string;
  chunks: RawChunk[];
}

interface RawEntry {
  product: string;
  name: string;
  bytes: number;
  sha256: string;
  variants: RawVariant[];
  license?: LicenseRef | null;
  role?: "payload" | "license" | "notice";
}

interface RawManifest {
  schema: number;
  id: string;
  codecs: string[];
  license?: LicenseRef | null;
  entries: RawEntry[];
}

/** An entry paired with the variant this client will actually fetch. */
interface Planned {
  info: EntryInfo;
  variant: RawVariant;
}

// ── the entry point ───────────────────────────────────────────────────────────

/**
 * Open a release: fetch and validate its manifest, resolve every entry to a
 * variant this runtime can decode. No chunk bytes are fetched here.
 */
export async function openRelease(
  ref: ReleaseRef,
  options: OpenOptions = {},
): Promise<ReleaseHandle> {
  const subtle = globalThis.crypto?.subtle;
  if (!subtle) {
    throw new ContractError(
      "unsupported-environment",
      "crypto.subtle is unavailable — this client needs a secure context (https, localhost)",
    );
  }

  const roots = rootsOf(ref);
  if (roots.length === 0) {
    throw new ContractError("manifest-invalid", `release ${ref.id}: no fetch root`);
  }

  const session = new AbortController();
  const relay = () => session.abort();
  options.signal?.addEventListener("abort", relay, { once: true });

  const health = new RootHealth(roots);

  // ── manifest ────────────────────────────────────────────────────────────────
  let raw: Bytes;
  let rawText: string;
  try {
    raw = await health.fetchAcrossRoots((root) =>
      httpGet(joinUrl(root, "manifest.json"), session.signal),
    );
    rawText = new TextDecoder().decode(raw);
  } catch (e) {
    throw wrap(e, "manifest-unreachable", `release ${ref.id}: manifest unreadable from every root`);
  }

  if (ref.manifest_sha256) {
    const got = await sha256Hex(raw, subtle);
    if (got !== ref.manifest_sha256.toLowerCase()) {
      throw new ContractError(
        "manifest-pin-mismatch",
        `release ${ref.id}: manifest sha256 ${got} does not match catalogue pin ${ref.manifest_sha256}`,
      );
    }
  }

  let manifest: RawManifest;
  try {
    manifest = JSON.parse(rawText) as RawManifest;
  } catch (e) {
    throw new ContractError("manifest-invalid", `release ${ref.id}: manifest is not JSON`, {
      cause: e,
    });
  }

  const plan = validate(manifest, ref.id);

  const read = async (entry: EntryInfo): Promise<Bytes> => {
    const planned = plan.get(entry.key);
    if (!planned || planned.info !== entry) {
      throw new ContractError(
        "manifest-invalid",
        `entry ${entry.key} does not belong to release ${ref.id}`,
        { entry: entry.key },
      );
    }
    // `fetchEntry` rethrows a caller abort unchanged so the root ledger is not
    // penalised; the public surface translates it into this module's error type.
    return translate(fetchEntry(planned, health, subtle, session.signal), entry.key);
  };

  return {
    id: ref.id,
    license: manifest.license ?? null,
    entries: [...plan.values()].map((p) => p.info),
    read,
    async *readAll() {
      for (const planned of plan.values()) {
        const bytes = await translate(
          fetchEntry(planned, health, subtle, session.signal),
          planned.info.key,
        );
        yield { info: planned.info, bytes };
      }
    },
  };
}

// ── manifest validation (zero requests) ───────────────────────────────────────

/**
 * Turn a raw manifest into a plan, or reject the whole thing.
 *
 * Canon V10: an unknown `schema` rejects the manifest. Validation is all-or-
 * nothing — a manifest that half-passes is not used, because acting on the
 * valid subset would mean silently dropping entries the producer published.
 */
function validate(m: RawManifest, id: string): Map<string, Planned> {
  if (typeof m.schema !== "number" || !SUPPORTED_SCHEMAS.has(m.schema)) {
    throw new ContractError(
      "schema-unsupported",
      `release ${id}: schema ${String(m.schema)} is not one this client knows ` +
        `(${[...SUPPORTED_SCHEMAS].join(", ")})`,
    );
  }
  if (!Array.isArray(m.entries)) {
    throw new ContractError("manifest-invalid", `release ${id}: entries is not an array`);
  }
  const declared = Array.isArray(m.codecs) ? m.codecs : [];

  const plan = new Map<string, Planned>();
  for (const e of m.entries) {
    const key = `${e.product}/${e.name}`;
    if (plan.has(key)) {
      throw new ContractError("manifest-invalid", `release ${id}: duplicate entry ${key}`);
    }
    const variant = pickVariant(e, declared, id);
    plan.set(key, {
      variant,
      info: {
        key,
        product: e.product,
        name: e.name,
        bytes: e.bytes,
        sha256: e.sha256,
        role: e.role ?? "payload",
        codec: variant.codec,
        license: e.license ?? m.license ?? null,
      },
    });
  }
  return plan;
}

/**
 * First variant this runtime can decode, in the manifest's declared order.
 *
 * Canon §3.3: "for each entry, in codecs order pick the first decodable branch".
 * An unknown codec is skipped, never fatal — V9 makes the vocabulary open, so a
 * producer adding one must not break clients that predate it.
 */
function pickVariant(e: RawEntry, declared: string[], id: string): RawVariant {
  const available = Array.isArray(e.variants) ? e.variants : [];

  for (const codec of declared) {
    if (!canDecode(codec)) continue;
    const v = available.find((candidate) => candidate.codec === codec);
    if (v) return checkChunks(v, `${e.product}/${e.name}`, id);
  }

  const offered = available.map((v) => v.codec).join(", ") || "none";
  const missing = available
    .map((v) => v.codec)
    .filter((codec) => !canDecode(codec))
    .join(", ");
  throw new ContractError(
    "no-decodable-variant",
    `release ${id} entry ${e.product}/${e.name}: offered codecs (${offered}), ` +
      `none of which this runtime can decode` +
      (missing ? ` — missing: ${missing}. Register one with useDecoder(), e.g. ` +
        `useDecoder("zstd", (b) => fzstd.decompress(b)).` : ""),
    { entry: `${e.product}/${e.name}` },
  );
}

/**
 * V1 names, V5 contiguous parts, V6 chunk size. Checked once, here, so the fetch
 * path can index chunks by `part` without re-validating anything.
 */
function checkChunks(v: RawVariant, entryKey: string, id: string): RawVariant {
  if (!Array.isArray(v.chunks) || v.chunks.length === 0) {
    throw new ContractError(
      "manifest-invalid",
      `release ${id} ${entryKey}: ${v.codec} has no chunks`,
      { entry: entryKey },
    );
  }
  const chunks = [...v.chunks].sort((a, b) => a.part - b.part);
  for (let i = 0; i < chunks.length; i++) {
    const c = chunks[i];
    if (c.part !== i) {
      throw new ContractError(
        "manifest-invalid",
        `release ${id} ${entryKey}: chunk parts are not 0..${chunks.length - 1} ` +
          `(part ${c.part} at index ${i})`,
        { entry: entryKey },
      );
    }
    if (!ASSET_NAME.test(c.file)) {
      throw new ContractError(
        "manifest-invalid",
        `release ${id} ${entryKey}: chunk name ${JSON.stringify(c.file)} is outside the ` +
          `asset-name whitelist (canon V1) — refusing to build a URL from it`,
        { entry: entryKey, file: c.file },
      );
    }
    if (c.bytes > MAX_CHUNK_BYTES) {
      throw new ContractError(
        "manifest-invalid",
        `release ${id} ${entryKey}: chunk ${c.file} is ${c.bytes} B, above the ` +
          `${MAX_CHUNK_BYTES} B limit (canon V6 — chunks must decode independently)`,
        { entry: entryKey, file: c.file },
      );
    }
  }
  return { codec: v.codec, chunks };
}

// ── fetching ──────────────────────────────────────────────────────────────────

/**
 * Fetch and verify one entry.
 *
 * A dense array, built by `new Array` plus an explicit index write per chunk, so
 * every slot is either filled or the whole promise rejects. (The previous
 * version checked `some(p => p === undefined)`, but `some` skips holes — the gap
 * check was dead code.)
 */
async function fetchEntry(
  planned: Planned,
  health: RootHealth,
  subtle: Pick<SubtleCrypto, "digest">,
  session: AbortSignal,
): Promise<Bytes> {
  const { info, variant } = planned;
  const chunks = variant.chunks;

  // Entry-scoped cancellation: the first failure aborts this entry's siblings.
  // Without it, one bad chunk leaves CONCURRENCY-1 downloads running for a
  // result nobody will use.
  const scope = new AbortController();
  const relay = () => scope.abort();
  session.addEventListener("abort", relay, { once: true });

  const decoded = new Array<Bytes>(chunks.length);
  let next = 0;

  const worker = async (): Promise<void> => {
    for (;;) {
      const i = next++;
      if (i >= chunks.length) return;
      const c = chunks[i];
      const encoded = await health.fetchAcrossRoots((root) =>
        httpGet(joinUrl(root, c.file), scope.signal),
      );
      // Byte length before hash: a truncated response is rejected without hashing.
      if (encoded.byteLength !== c.bytes) {
        throw new ContractError(
          "chunk-unavailable",
          `entry ${info.key} chunk ${c.file}: ${encoded.byteLength} B, manifest says ${c.bytes}`,
          { entry: info.key, file: c.file },
        );
      }
      const got = await sha256Hex(encoded, subtle);
      if (got !== c.sha256) {
        throw new ContractError(
          "entry-hash-mismatch",
          `entry ${info.key} chunk ${c.file}: sha256 ${got} != ${c.sha256}`,
          { entry: info.key, file: c.file },
        );
      }
      // Decode here, per chunk. Never decode the concatenation — canon §4.3.
      decoded[i] = await decodeChunk(variant.codec, encoded, info.key);
    }
  };

  try {
    const workers = Math.max(1, Math.min(CONCURRENCY, chunks.length));
    await Promise.all(Array.from({ length: workers }, worker));

    const total = decoded.reduce((n, part) => n + part.byteLength, 0);
    const blob = new Uint8Array(total);
    let offset = 0;
    for (let i = 0; i < decoded.length; i++) {
      blob.set(decoded[i], offset);
      offset += decoded[i].byteLength;
      decoded[i] = EMPTY; // release each part as it is copied
    }

    if (blob.byteLength !== info.bytes) {
      throw new ContractError(
        "entry-hash-mismatch",
        `entry ${info.key}: decoded to ${blob.byteLength} B, manifest says ${info.bytes}`,
        { entry: info.key },
      );
    }
    const got = await sha256Hex(blob, subtle);
    if (got !== info.sha256) {
      throw new ContractError(
        "entry-hash-mismatch",
        `entry ${info.key}: sha256 ${got} != ${info.sha256}`,
        { entry: info.key },
      );
    }
    return blob;
  } catch (e) {
    scope.abort(); // stop the siblings; their results are now pointless
    throw e;
  } finally {
    session.removeEventListener("abort", relay);
  }
}

const EMPTY: Bytes = new Uint8Array(0);

/**
 * Root selection with a shared failure ledger.
 *
 * The ledger lives on the handle, not on each entry: with a per-entry ledger a
 * dead mirror is retried once per entry (14 entries ⇒ 14 wasted round trips
 * before every chunk goes to the fallback).
 */
class RootHealth {
  private readonly roots: string[];
  private readonly failures: number[];

  constructor(roots: string[]) {
    this.roots = roots;
    this.failures = roots.map(() => 0);
  }

  /** Tries each root in least-failed-first order; returns the first response. */
  async fetchAcrossRoots(attempt: (root: string) => Promise<Bytes>): Promise<Bytes> {
    const order = this.roots
      .map((root, i) => ({ root, i }))
      .sort((a, b) => this.failures[a.i] - this.failures[b.i]);

    let last: unknown;
    for (const { root, i } of order) {
      try {
        return await attempt(root);
      } catch (e) {
        // A caller-driven abort is not this root's fault: rethrow instead of
        // burning the ledger and trying the next root, which would keep fetching
        // after the consumer asked to stop.
        if (isAbort(e)) throw e;
        // Network failure and wrong bytes are both "this root did not deliver".
        // Counting them the same keeps a mirror that serves corrupt data from
        // being preferred over one that merely timed out.
        this.failures[i] += 1;
        last = e;
      }
    }
    throw last instanceof Error ? last : new ContractError("chunk-unavailable", "no root answered");
  }
}

/**
 * The only place bytes enter the client. A deadline is composed in
 * unconditionally — `fetch` has no default timeout.
 *
 * The deadline is disposed as soon as the body is read, not left to fire later:
 * `AbortSignal.timeout` keeps a timer alive for its full duration, and with a
 * 120 s deadline across many sequential chunks those timers outlive the work they
 * guard. Once a request is done its deadline has no meaning.
 */
async function httpGet(url: string, session: AbortSignal): Promise<Bytes> {
  const doFetch = globalThis.fetch;
  if (!doFetch) {
    throw new ContractError("unsupported-environment", "no fetch implementation available");
  }
  const deadline = new AbortController();
  const timer = setTimeout(() => deadline.abort(), TIMEOUT_MS);
  try {
    const signal = AbortSignal.any([session, deadline.signal]);
    const res = await doFetch(url, { method: "GET", signal });
    if (!res.ok) {
      throw new ContractError("chunk-unavailable", `GET ${url} -> ${res.status}`, { file: url });
    }
    return new Uint8Array(await res.arrayBuffer());
  } finally {
    clearTimeout(timer);
  }
}

// ── codecs ────────────────────────────────────────────────────────────────────

async function decodeChunk(
  codec: string,
  bytes: Bytes,
  entryKey: string,
): Promise<Bytes> {
  if (codec === "identity") return bytes;

  const registered = extraDecoders.get(codec);
  if (registered) {
    // A registered decoder is third-party code: its output may be backed by a
    // SharedArrayBuffer, or be a view into a larger buffer. Copy once, here, so
    // everything downstream can rely on `Bytes` and hash without copying again.
    return adopt(await registered(bytes));
  }

  try {
    const stream = new Blob([bytes]).stream().pipeThrough(
      new DecompressionStream(codec as CompressionFormat),
    );
    return new Uint8Array(await new Response(stream).arrayBuffer());
  } catch (e) {
    throw new ContractError(
      "no-decodable-variant",
      `entry ${entryKey}: codec ${codec} was selected but this runtime cannot decode it`,
      { entry: entryKey, cause: e },
    );
  }
}

/**
 * Take ownership of bytes whose provenance we do not control.
 *
 * Copies only when needed: already an `ArrayBuffer`-backed, full-range view ⇒
 * returned as is; anything else (SharedArrayBuffer, a slice of a bigger buffer)
 * ⇒ copied into a fresh one. This is the single place the module pays for a copy
 * of decoded output, and it exists because a registered decoder is third-party.
 */
function adopt(bytes: Uint8Array): Bytes {
  if (
    bytes.buffer instanceof ArrayBuffer &&
    bytes.byteOffset === 0 &&
    bytes.byteLength === bytes.buffer.byteLength
  ) {
    return bytes as Bytes;
  }
  const copy = new Uint8Array(bytes.byteLength);
  copy.set(bytes);
  return copy;
}

// ── helpers ───────────────────────────────────────────────────────────────────

/**
 * Fetch roots for a catalogue entry, normalised to end in `/`.
 *
 * Built from the parsed `URL`, never by slicing the input: the previous version
 * checked `pathname.endsWith("/manifest.json")` but then sliced 13 characters off
 * the *original string*, so `.../manifest.json?v=3` became `.../mani`.
 */
function rootsOf(ref: ReleaseRef): string[] {
  const out: string[] = [];
  for (const raw of [ref.base, ref.base_proxy]) {
    if (typeof raw !== "string" || !raw) continue;
    const url = new URL(raw);
    if (url.protocol !== "https:") {
      throw new ContractError("manifest-invalid", `fetch root must be https: ${raw}`);
    }
    url.search = "";
    url.hash = "";
    if (!url.pathname.endsWith("/")) url.pathname += "/";
    out.push(url.toString());
  }
  return out;
}

/** `new URL` handles the join; a root always ends in `/` by the time it gets here. */
function joinUrl(root: string, file: string): string {
  return new URL(file, root).toString();
}

/**
 * sha256 as lowercase hex.
 *
 * Every `Uint8Array` this module hashes came from `res.arrayBuffer()` or from
 * `DecompressionStream`, so it is backed by a plain `ArrayBuffer` — WebCrypto
 * accepts it directly and honours `byteOffset`/`byteLength`, so there is nothing
 * to copy. (An earlier version copied unconditionally "in case" of a
 * SharedArrayBuffer, which cannot occur here and doubled peak memory.)
 */
async function sha256Hex(
  bytes: Uint8Array<ArrayBuffer>,
  subtle: Pick<SubtleCrypto, "digest">,
): Promise<string> {
  const digest = await subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

function wrap(e: unknown, code: ContractErrorCode, message: string): ContractError {
  if (e instanceof ContractError) return e;
  if (isAbort(e)) return new ContractError("aborted", message, { cause: e });
  return new ContractError(code, message, { cause: e });
}

/**
 * Translate a raw cancellation into `ContractError("aborted")` at the public
 * boundary.
 *
 * Internally an abort is rethrown unchanged — `fetchAcrossRoots` must not read it
 * as a root failure, and `fetchEntry` must not swallow it. But a caller should
 * never receive a bare `DOMException` from a module whose every other error is
 * typed.
 */
async function translate<T>(work: Promise<T>, entryKey: string): Promise<T> {
  try {
    return await work;
  } catch (e) {
    if (e instanceof ContractError) throw e;
    if (isAbort(e)) {
      throw new ContractError("aborted", `entry ${entryKey}: cancelled`, {
        entry: entryKey,
        cause: e,
      });
    }
    throw new ContractError("chunk-unavailable", `entry ${entryKey}: ${String(e)}`, {
      entry: entryKey,
      cause: e,
    });
  }
}

/** A cancellation, not a failure: the consumer asked to stop. */
function isAbort(e: unknown): boolean {
  return e instanceof DOMException && (e.name === "AbortError" || e.name === "TimeoutError");
}
