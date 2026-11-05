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
  /**
   * Release everything this handle holds: abort in-flight requests and detach the
   * caller's abort listener.
   *
   * Without this the listener registered on `options.signal` lives as long as the
   * caller's signal does — for an app-level signal that is the process lifetime,
   * and it keeps this handle reachable, so every `openRelease` leaks one. Idempotent.
   */
  close(): void;
}

export interface OpenOptions {
  /** Cancels every request this handle owns. */
  signal?: AbortSignal;
  /**
   * Parallel chunk fetches per entry. Default 2.
   *
   * **2 is not arbitrary and not a property of this protocol.** The reference
   * mirror throttles once a client pulls roughly 10–15 MiB concurrently. With
   * `chunkSize` at 5 MiB, three in flight is 15 MiB — across the line — while two
   * is 10 MiB, which is the margin the chunk size was chosen to leave. So the
   * safe ceiling for a 5 MiB chunk size is two, and that is where the default
   * comes from.
   *
   * Raising this is legal (`chunks` are independent by construction, canon V5)
   * but on a mirror with a byte cap it makes things slower, not faster: the
   * throttle applies to the whole transfer. If a producer ships a smaller
   * `chunkSize`, more parallelism fits under the same cap and this can go up.
   */
  concurrency?: number;
  /** Attempts per root before moving to the next root. Default 3. */
  attemptsPerRoot?: number;
  /**
   * Timeout for one attempt. Default 5000 ms, but **derived per request**: a
   * chunk whose declared size cannot plausibly transfer within the default gets
   * proportionally more.
   *
   * A flat budget is wrong in both directions. Measured on the reference mirror,
   * the average zstd chunk is 865 KB — about 1.5 s at 0.55 MiB/s, so 5 s is
   * comfortable. But a 5 MiB `identity` chunk needs 8.3–9.1 s on the same link,
   * so a flat 5 s would abort a healthy transfer and mark a good root dead.
   * Supplying this overrides the derivation for every request.
   */
  attemptBudgetMs?: number;
  /** Called after each entry resolves, for UI progress on large releases. */
  onEntry?: (info: EntryInfo, done: number, total: number) => void;
  /**
   * This client's preferred codec chain, highest priority first.
   *
   * Canon V9 makes `codecs[]` an **open vocabulary**: a release may offer any
   * number of codecs, in any order, and `identity` need not exist at all. The
   * manifest's order is a *producer's* suggestion, not a rule — which branch to
   * fetch belongs to the consumer.
   *
   * So this list is the consumer speaking. It is tried first, verbatim and in
   * order; whatever it does not cover falls through to the manifest's declared
   * order. That is what makes it a preference rather than a requirement: asking
   * for `["br", "zstd"]` from a release that ships only `["identity", "gzip"]`
   * still succeeds, and asking for `["identity"]` against a release that ships
   * everything will use `identity` and nothing else.
   *
   * Names are arbitrary strings — `["identity", "xz", "gzip"]` is as valid as
   * `["zstd"]`. A preferred codec that is absent or undecodable is not an error;
   * the chain moves on. Only an entry with **no** decodable variant at all fails,
   * and the message then lists what was offered.
   *
   * Default: the manifest's own order (canon §3.3's "in codecs order").
   */
  codecPreference?: string[];
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
  /**
   * HTTP status, when the failure was a response rather than a transport
   * problem. Absent means "the request never produced an answer" — a stall or a
   * dropped connection — which is retryable in a way a status is not.
   */
  readonly status?: number;
  override readonly cause?: unknown;

  constructor(
    code: ContractErrorCode,
    message: string,
    detail: { entry?: string; file?: string; status?: number; cause?: unknown } = {},
  ) {
    super(message);
    this.name = "ContractError";
    this.code = code;
    this.entry = detail.entry;
    this.file = detail.file;
    this.status = detail.status;
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

/**
 * Forget a registered decoder, restoring whatever the platform provides.
 *
 * Exists so tests can isolate: without it, a test that registers a fake zstd
 * leaves the process unable to observe "no zstd decoder", and the next test in
 * the same module instance cannot assert the fallback path. Also the escape
 * hatch for a long-lived server process serving tenants that must not share
 * decoder implementations.
 */
export function forgetDecoder(codec: string): boolean {
  return extraDecoders.delete(codec);
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

/**
 * Attempts per root before moving on, and the budget for each.
 *
 * The mirror intermittently accepts a request and then never delivers it.
 * Measured on the production EdgeOne line: the same 5 MiB chunk, six tries —
 * two timed out past 40 s, four succeeded in 0.39–1.99 s. Success was fast when
 * it came; failure was not a slow transfer but a request that simply stopped
 * answering.
 *
 * So the useful unit is a **short, capped attempt repeated a few times**, not
 * one long wait. Three attempts × 5 s bounds the cost of a dead request to 15 s
 * per root, which is what makes falling through to the next root viable. A
 * single 120 s deadline spent the whole budget on one stall and then reported a
 * failure that a second try would have avoided.
 *
 * These are **defaults, not protocol facts** — all three are overridable through
 * `OpenOptions`. The reference mirror is one link; a consumer on a slower or
 * faster one must be able to adjust without forking this file.
 */
const DEFAULT_ATTEMPTS_PER_ROOT = 3;
const DEFAULT_ATTEMPT_BUDGET_MS = 5_000;

/**
 * Assumed transfer rate used to scale an attempt budget to a chunk's size.
 *
 * 0.5 MiB/s is the measured floor of the reference link. Dividing a chunk's
 * declared encoded size by this gives the time it plausibly needs, which is then
 * given two times headroom. A 865 KB zstd chunk lands at ~3.5 s (the flat 5 s
 * default still governs); a 5 MiB identity chunk gets ~20 s instead of being
 * killed at 5 s.
 *
 * Without this, the retry budget quietly encodes one link's speed into every
 * consumer: on a half-speed link, healthy transfers get aborted, the root gets
 * marked dead, and the fallback carries everything.
 */
const ASSUMED_BYTES_PER_SECOND = 512 * 1024;
const BUDGET_HEADROOM = 2;

/**
 * Parallel chunk fetches per entry. Overridable; see `OpenOptions.concurrency`.
 *
 * Two, because the reference mirror throttles above ~10–15 MiB of concurrent
 * transfer and `chunkSize` is 5 MiB: 2 x 5 = 10 stays under, 3 x 5 = 15 does not.
 * Tied to the chunk size, not to the protocol — a release with 1 MiB chunks could
 * safely run more.
 */
const DEFAULT_CONCURRENCY = 2;

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

  const concurrency = Math.max(1, options.concurrency ?? DEFAULT_CONCURRENCY);
  const health = new RootHealth(roots, options.attemptsPerRoot, options.attemptBudgetMs);

  // ── manifest ────────────────────────────────────────────────────────────────
  let raw: Bytes;
  let rawText: string;
  try {
    raw = await health.fetchAcrossRoots(
      (root, budget) =>
        httpGet(joinUrl(root, "manifest.json"), AbortSignal.any([session.signal, budget])),
      undefined,
      "manifest-unreachable",
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

  const plan = validate(manifest, ref.id, options.codecPreference);

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
    return translate(
      fetchEntry(planned, health, subtle, session.signal, concurrency),
      entry.key,
    );
  };

  const close = () => {
    session.abort();
    options.signal?.removeEventListener("abort", relay);
  };

  const entries = [...plan.values()].map((p) => p.info);

  return {
    id: ref.id,
    license: manifest.license ?? null,
    entries,
    close,
    read,
    async *readAll() {
      let done = 0;
      for (const planned of plan.values()) {
        const bytes = await translate(
          fetchEntry(planned, health, subtle, session.signal, concurrency),
          planned.info.key,
        );
        done++;
        options.onEntry?.(planned.info, done, entries.length);
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
function validate(m: RawManifest, id: string, preference?: string[]): Map<string, Planned> {
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

  // V11 applies only to schema 3; schema 2 predates the license field, so a
  // release without one there is legitimate rather than malformed.
  const releaseLicense = m.schema === 3 ? checkLicense(m.license, `${id} (release)`) : null;

  const plan = new Map<string, Planned>();
  for (const e of m.entries) {
    const key = `${e.product}/${e.name}`;
    if (plan.has(key)) {
      throw new ContractError("manifest-invalid", `release ${id}: duplicate entry ${key}`);
    }
    const variant = pickVariant(e, declared, preference, id);
    const own = e.license === undefined ? undefined : checkLicense(e.license, `${id} ${key}`);
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
        license: own ?? releaseLicense,
      },
    });
  }
  return plan;
}

/**
 * V11: `license` is `{id, url}`, `id` non-empty, `url` starting with `https://`.
 *
 * The `https://` requirement is a safety property, not pedantry: this value is
 * rendered by a UI as `href`, so a manifest that said `javascript:...` would be
 * injecting script into every consumer that trusted it. The check runs here, at
 * the only place a manifest enters the process.
 */
function checkLicense(value: unknown, where: string): LicenseRef | null {
  if (value === null || value === undefined) return null;
  if (typeof value !== "object") {
    throw new ContractError(
      "manifest-invalid",
      `${where}: license must be an object {id, url}, got ${typeof value} (canon V11)`,
    );
  }
  const { id, url } = value as { id?: unknown; url?: unknown };
  if (typeof id !== "string" || id === "") {
    throw new ContractError("manifest-invalid", `${where}: license.id must be a non-empty string (canon V11)`);
  }
  if (typeof url !== "string" || !url.startsWith("https://")) {
    throw new ContractError(
      "manifest-invalid",
      `${where}: license.url must start with https:// (canon V11) — got ${JSON.stringify(url)}`,
    );
  }
  return { id, url };
}

/**
 * First variant this runtime can decode.
 *
 * Two orders are consulted, in sequence:
 *
 *  1. the **consumer's** chain (`OpenOptions.codecPreference`), if given;
 *  2. the **manifest's** declared order, which is canon §3.3's default
 *     ("for each entry, in codecs order pick the first decodable branch").
 *
 * Trying the consumer's chain first is what makes codec choice a client decision
 * rather than a producer's. Falling back to the manifest order is what keeps it a
 * *preference*: a consumer that wants `br` still gets served by a release that
 * only offers gzip, instead of failing because its first choice was absent.
 *
 * An unknown codec is skipped, never fatal — V9 makes the vocabulary open, so a
 * producer adding one must not break clients that predate it, and a consumer
 * asking for one it cannot decode must not break on releases that lack it.
 */
function pickVariant(
  e: RawEntry,
  declared: string[],
  preference: string[] | undefined,
  id: string,
): RawVariant {
  const available = Array.isArray(e.variants) ? e.variants : [];

  // V5, second half: "all codecs of one entry must have the same chunk count
  // (they slice the same original bytes)". Checked for every variant, not just
  // the one this runtime picks — otherwise the same manifest would be valid for
  // a zstd client and invalid for a gzip client, and a client that cannot decode
  // zstd would never learn the manifest was broken.
  const counts = new Set(available.map((v) => (Array.isArray(v.chunks) ? v.chunks.length : -1)));
  if (counts.size > 1) {
    const detail = available.map((v) => `${v.codec}=${Array.isArray(v.chunks) ? v.chunks.length : "?"}`).join(", ");
    throw new ContractError(
      "manifest-invalid",
      `release ${id} entry ${e.product}/${e.name}: codecs disagree on chunk count (${detail}); ` +
        `canon V5 requires them to slice the same bytes the same way`,
      { entry: `${e.product}/${e.name}` },
    );
  }

  // Consumer's chain first, then the manifest's — de-duplicated so a codec named
  // in both is not probed twice.
  const order = [...new Set([...(preference ?? []), ...declared])];
  for (const codec of order) {
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
  concurrency: number,
): Promise<Bytes> {
  const { info, variant } = planned;
  const chunks = variant.chunks;

  // Entry-scoped cancellation: the first failure aborts this entry's siblings.
  // Without it, one bad chunk leaves `concurrency`-1 downloads running for a
  // result nobody will use.
  const scope = new AbortController();
  const relay = () => scope.abort();
  // `addEventListener` does not replay a past abort, so a handle closed before
  // `read()` was called would otherwise run to completion against a dead session.
  // Checking `session.aborted` covers that case; the listener covers abort-while-
  // reading. `close()` is documented as stopping later reads, and this is the
  // line that makes it true.
  if (session.aborted) scope.abort();
  else session.addEventListener("abort", relay, { once: true });

  const decoded = new Array<Bytes>(chunks.length);
  let next = 0;

  const worker = async (): Promise<void> => {
    for (;;) {
      const i = next++;
      if (i >= chunks.length) return;
      const c = chunks[i];
      const encoded = await health.fetchAcrossRoots(
        (root, budget) => httpGet(joinUrl(root, c.file), AbortSignal.any([scope.signal, budget])),
        c.bytes,
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
    const workers = Math.max(1, Math.min(concurrency, chunks.length));
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
 *
 * The retry budget is **per root, not global**: `ATTEMPTS_PER_ROOT` tries of
 * `ATTEMPT_BUDGET_MS` each on `base`, and only after those are exhausted does
 * `base_proxy` get its own budget. That is what makes the fallback meaningful —
 * a root that is briefly stalling gets a few fast retries, while a root that is
 * genuinely down costs a bounded 3 x 5 s rather than the whole request.
 *
 * A root that fails stays demoted: penalties decay only when the root itself
 * succeeds again, never because some *other* root succeeded.
 */
class RootHealth {
  private readonly roots: string[];
  private readonly failures: number[];
  private readonly attemptsPerRoot: number;
  private readonly fixedBudgetMs: number | undefined;

  constructor(
    roots: string[],
    attemptsPerRoot = DEFAULT_ATTEMPTS_PER_ROOT,
    fixedBudgetMs?: number,
  ) {
    this.roots = roots;
    this.failures = roots.map(() => 0);
    this.attemptsPerRoot = Math.max(1, attemptsPerRoot);
    this.fixedBudgetMs = fixedBudgetMs;
  }

  /**
   * Budget for one attempt at a body of `expectBytes`.
   *
   * An explicit `attemptBudgetMs` wins. Otherwise scale by size: a fixed budget
   * derived from one link's speed aborts healthy transfers on any slower link,
   * and a 5 MiB identity chunk needs eight times the time of an 865 KB zstd one.
   * `expectedBytes === undefined` (the manifest, whose size is unknown until it
   * arrives) uses the flat default.
   */
  private budgetFor(expectedBytes?: number): number {
    if (this.fixedBudgetMs !== undefined) return this.fixedBudgetMs;
    if (expectedBytes === undefined) return DEFAULT_ATTEMPT_BUDGET_MS;
    const plausible = (expectedBytes / ASSUMED_BYTES_PER_SECOND) * 1000 * BUDGET_HEADROOM;
    return Math.max(DEFAULT_ATTEMPT_BUDGET_MS, Math.ceil(plausible));
  }

  /** Tries each root in least-failed-first order, each with its own attempt budget. */
  async fetchAcrossRoots(
    attempt: (root: string, signal: AbortSignal) => Promise<Bytes>,
    expectBytes?: number,
    failCode: ContractErrorCode = "chunk-unavailable",
  ): Promise<Bytes> {
    const order = this.roots
      .map((root, i) => ({ root, i }))
      .sort((a, b) => this.failures[a.i] - this.failures[b.i]);

    let last: unknown;
    let lastRoot = "";

    for (const { root, i } of order) {
      let delivered = false;
      let answeredWithStatus = false;

      const budgetMs = this.budgetFor(expectBytes);
      for (let tryNo = 1; tryNo <= this.attemptsPerRoot; tryNo++) {
        const budget = new AbortController();
        const timer = setTimeout(() => budget.abort(), budgetMs);
        try {
          const bytes = await attempt(root, budget.signal);
          delivered = true;
          // Only this root's own success pays down its debt.
          this.failures[i] = Math.max(0, this.failures[i] - 1);
          return bytes;
        } catch (e) {
          // A caller-driven abort is not this root's fault: rethrow instead of
          // burning the ledger and trying the next root, which would keep
          // fetching after the consumer asked to stop.
          if (isAbort(e) && !budget.signal.aborted) throw e;
          last = e;
          lastRoot = root;
          // A status is an answer from this root: a 404 will still be a 404 on
          // a retry, so skip the rest of this root's budget and move on.
          if (isStatus(e)) {
            answeredWithStatus = true;
            break;
          }
          // Otherwise a stall or transport failure — spend another attempt.
        } finally {
          clearTimeout(timer);
        }
      }

      if (!delivered && !answeredWithStatus) {
        // Only transport failures count against a root. A 404 (or any status) is
        // the root answering correctly about a file it does not have — one bad
        // chunk must not permanently demote a healthy mirror for every other
        // file in the release.
        this.failures[i] += 1;
      }
    }

    // The code is the caller's, not a constant: "no root served the manifest" and
    // "no root served this chunk" are different failures, and a consumer that
    // cannot tell them apart cannot decide whether to retry the whole release or
    // skip one file. Passing a fixed "chunk-unavailable" here made
    // `manifest-unreachable` unreachable, because `wrap()` passes a
    // ContractError through unchanged.
    const reason = last instanceof Error ? `${last.name}: ${last.message}` : String(last);
    throw new ContractError(failCode, `every root failed (last: ${lastRoot || "none"} — ${reason})`, {
      cause: last,
    });
  }
}

/**
 * A response the root actually sent (any status), as opposed to a stall or a drop.
 *
 * A status is a final answer for that root: repeating the request cannot change
 * it, so the budget should move to the next root instead of being spent on the
 * same unreachable file.
 */
function isStatus(e: unknown): boolean {
  return e instanceof ContractError && typeof e.status === "number";
}

/**
 * The only place bytes enter the client: one GET, under the caller's signal.
 *
 * The attempt budget lives in `RootHealth`, not here. This function performs
 * exactly one request and reports honestly what happened — a status (the root
 * answered), a stall (it stopped answering), or a transport drop. Deciding how
 * many times to try and when to switch roots is the caller's job, and putting
 * that decision one level up keeps a single attempt's failure classification
 * unambiguous.
 *
 * The body is read as a stream rather than via `res.arrayBuffer()` so that the
 * abort signal can interrupt a transfer that has already started. `arrayBuffer()`
 * resolves once at the end, so a body that dies mid-flight is only noticed when
 * the budget expires — with a plain whole-body read there is no way to tell "slow"
 * from "dead" until it is too late to try again.
 */
async function httpGet(url: string, signal: AbortSignal): Promise<Bytes> {
  const doFetch = globalThis.fetch;
  if (!doFetch) {
    throw new ContractError("unsupported-environment", "no fetch implementation available");
  }
  if (typeof AbortSignal.any !== "function") {
    // Safari < 17.4. Reported here rather than as "every mirror is down", which
    // is what a TypeError thrown per root would look like.
    throw new ContractError(
      "unsupported-environment",
      "AbortSignal.any is unavailable — this client needs a browser from 2024 or later",
    );
  }

  const res = await doFetch(url, { method: "GET", signal });
  if (!res.ok) {
    // A status is an answer, not a transport failure.
    throw new ContractError("chunk-unavailable", `GET ${url} -> ${res.status}`, {
      file: url,
      status: res.status,
    });
  }

  if (!res.body) {
    // No streaming support in this runtime: the signal still aborts the read.
    return new Uint8Array(await res.arrayBuffer());
  }

  const reader = res.body.getReader();
  const parts: Uint8Array[] = [];
  let received = 0;
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      if (value) {
        parts.push(value);
        received += value.byteLength;
      }
    }
  } finally {
    // Release the lock even on abort, so the connection can be torn down.
    reader.releaseLock();
  }

  const out = new Uint8Array(received);
  let at = 0;
  for (const p of parts) {
    out.set(p, at);
    at += p.byteLength;
  }
  return out;
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
 * Built from the parsed `URL`, never by slicing the input: an earlier version
 * checked `pathname.endsWith("/manifest.json")` but then sliced 13 characters off
 * the *original string*, so `.../manifest.json?v=3` became `.../mani`.
 *
 * A catalogue `base` is a **directory** (canon §5.3: "`<host>/<owner>/<repo>/
 * releases/download/<tag>/`, trailing slash included"). Passing a manifest URL
 * here is a caller mistake and is rejected rather than silently reinterpreted as
 * a directory — appending `/` to `.../manifest.json` would yield
 * `.../manifest.json/manifest.json`, and every chunk would 404 with a message
 * that pointed at the mirror instead of at the caller.
 */
function rootsOf(ref: ReleaseRef): string[] {
  const out: string[] = [];
  for (const raw of [ref.base, ref.base_proxy]) {
    if (typeof raw !== "string" || !raw) continue;

    let url: URL;
    try {
      url = new URL(raw);
    } catch (e) {
      throw new ContractError("manifest-invalid", `fetch root is not a URL: ${raw}`, { cause: e });
    }
    if (url.protocol !== "https:") {
      throw new ContractError("manifest-invalid", `fetch root must be https: ${raw}`);
    }
    if (url.pathname.endsWith("/manifest.json")) {
      throw new ContractError(
        "manifest-invalid",
        `fetch root must be a directory, not a manifest URL: ${raw} ` +
          `(drop the trailing "manifest.json")`,
      );
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
