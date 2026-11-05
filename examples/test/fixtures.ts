/**
 * Test fixtures: build a real release out of real bytes.
 *
 * Deliberately self-contained. The client under test exposes no injection point
 * for tests — no `_internal`, no exported helpers, no seam added for the sake of
 * testing. The only boundary a test can cross is `globalThis.fetch`, which the
 * client reads at call time. So the fixtures below do all the work: compress real
 * bytes, hash them, lay out a manifest, and serve the whole thing from an
 * in-memory map.
 *
 * If this file needs to reach inside the client for anything, the test is
 * measuring the wrong thing.
 */
import { createHash } from "node:crypto";
import { gzipSync, zstdCompressSync } from "node:zlib";

// `zstdCompressSync` only exists from Node 22.15. If it is missing the fixtures
// can still build gzip/identity releases, but every zstd case must fail loudly
// rather than quietly testing nothing — a skipped test that looks green is worse
// than no test.
if (typeof zstdCompressSync !== "function") {
  throw new Error(
    `node:zlib.zstdCompressSync is unavailable (node ${process.version}) — ` +
      "the fixtures need Node 22.15+ to build zstd releases",
  );
}

export interface FixtureChunk {
  part: number;
  file: string;
  bytes: number;
  sha256: string;
}

export interface FixtureVariant {
  codec: string;
  chunks: FixtureChunk[];
}

export interface FixtureEntry {
  product: string;
  name: string;
  bytes: number;
  sha256: string;
  variants: FixtureVariant[];
  role?: "payload" | "license" | "notice";
  license?: { id: string; url: string } | null;
}

export interface Fixture {
  /** The manifest JSON, as it would be published. */
  manifest: Record<string, unknown>;
  /** url -> response, served by the fake fetch. */
  files: Map<string, Uint8Array>;
}

export interface BuildOptions {
  /** Pseudo-random payload size in bytes. */
  size: number;
  /** Slice size for the identity variant, which also sets the chunk count. */
  chunkSize: number;
  /** Codecs to provide, in manifest order. Default ["zstd", "gzip", "identity"]. */
  codecs?: string[];
  /** Seed, so runs are reproducible. */
  seed?: number;
  /** Override the product/name. */
  product?: string;
  name?: string;
}

/** Deterministic bytes — no crypto randomness, so a failing case reproduces. */
export function payload(size: number, seed = 1): Uint8Array {
  const out = new Uint8Array(size);
  let x = seed >>> 0 || 1;
  for (let i = 0; i < size; i++) {
    // xorshift32, then fold so the bytes compress somewhat (as real data does)
    x ^= x << 13;
    x >>>= 0;
    x ^= x >>> 17;
    x ^= x << 5;
    x >>>= 0;
    out[i] = (x >>> 24) & 0xff;
  }
  return out;
}

export function sha256(bytes: Uint8Array): string {
  return createHash("sha256").update(bytes).digest("hex");
}

const COMPRESSORS: Record<string, (b: Uint8Array) => Uint8Array> = {
  identity: (b) => b,
  gzip: (b) => new Uint8Array(gzipSync(b)),
  zstd: (b) => new Uint8Array(zstdCompressSync(b)),
};

/**
 * Build one release with the given codecs.
 *
 * Every variant slices the same plain bytes into the same number of chunks, which
 * is what canon V5 requires ("all codecs of one entry must have the same chunk
 * count"). Getting that wrong would make the fixture — not the client — the
 * thing under test.
 */
export function buildRelease(opts: BuildOptions): Fixture {
  const {
    size,
    chunkSize,
    codecs = ["zstd", "gzip", "identity"],
    seed = 1,
    product = "wasm32",
    name = "payload.wasm",
  } = opts;

  const plain = payload(size, seed);
  const slices: Uint8Array[] = [];
  for (let at = 0; at < plain.byteLength; at += chunkSize) {
    slices.push(plain.subarray(at, Math.min(at + chunkSize, plain.byteLength)));
  }

  const files = new Map<string, Uint8Array>();
  const variants: FixtureVariant[] = [];

  for (const codec of codecs) {
    // An unknown codec is legitimate: the point of V9's open vocabulary is that a
    // producer may ship one this client cannot decode. The fixture stores raw
    // bytes under such a codec so tests can exercise the fallback and the
    // "nothing decodable" error without inventing a real encoder.
    const compress = COMPRESSORS[codec] ?? ((b: Uint8Array) => b);
    const chunks: FixtureChunk[] = slices.map((slice, part) => {
      const encoded = compress(slice);
      // Name shape matters: the client enforces canon V1's whitelist on chunk
      // names, so the fixture must produce legal ones.
      const file = `${product}__${name}.${codec}.${String(part).padStart(3, "0")}`;
      files.set(file, encoded);
      return { part, file, bytes: encoded.byteLength, sha256: sha256(encoded) };
    });
    variants.push({ codec, chunks });
  }

  const manifest: Record<string, unknown> = {
    schema: 3,
    id: `fixture/${name}`,
    chunkSize,
    codecs,
    license: { id: "MIT", url: "https://example.test/LICENSE" },
    entries: [
      {
        product,
        name,
        bytes: plain.byteLength,
        sha256: sha256(plain),
        variants,
        role: "payload",
      } satisfies FixtureEntry,
    ],
  };

  return { manifest, files };
}

/** Wrap a fixture so it can be merged into a multi-entry release. */
export function entryOf(fixture: Fixture): FixtureEntry {
  return (fixture.manifest.entries as FixtureEntry[])[0];
}

export interface FakeOptions {
  /** Base URL the client will be told to use. */
  base?: string;
  /** How each request should behave. Return a Response to serve, or throw to simulate a drop. */
  intercept?: (url: string, attempt: number) => Response | undefined | Promise<Response | undefined>;
  /** Fail the first N requests with a transport error. */
  failFirst?: number;
  /** Fail only requests whose URL contains this substring. */
  failMatching?: string;
  /** Delay each response by this many ms (to exercise budgets). */
  delayMs?: number;
}

export interface FakeStats {
  /** Every URL requested, in order. */
  urls: string[];
  /** Requests per URL. */
  counts: Map<string, number>;
}

export const BASE = "https://mirror.test/releases/fixture/";

/**
 * Install a fake `fetch` and return its bookkeeping.
 *
 * The client reads `globalThis.fetch` on every call, so this is the whole
 * seam — no other integration is needed or wanted.
 */
export function installFake(
  manifest: Record<string, unknown>,
  files: Map<string, Uint8Array>,
  opts: FakeOptions = {},
): { stats: FakeStats; restore: () => void } {
  const base = opts.base ?? BASE;
  const stats: FakeStats = { urls: [], counts: new Map() };
  const real = globalThis.fetch;
  let served = 0;

  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
    stats.urls.push(url);
    stats.counts.set(url, (stats.counts.get(url) ?? 0) + 1);
    const attempt = stats.counts.get(url) ?? 1;

    // Race whatever the intercept does against the caller's abort signal, the way
    // a real fetch does. Without this, an intercept that never resolves would
    // hang the test forever instead of exercising the client's budget.
    const aborted = new Promise<never>((_, reject) => {
      const onAbort = () => reject(new DOMException("The operation was aborted.", "AbortError"));
      if (init?.signal?.aborted) return onAbort();
      init?.signal?.addEventListener("abort", onAbort, { once: true });
    });

    if (opts.delayMs) {
      await Promise.race([new Promise((r) => setTimeout(r, opts.delayMs)), aborted]);
    }

    const custom = await Promise.race([
      Promise.resolve(opts.intercept?.(url, attempt)),
      aborted,
    ]);
    if (custom) return custom;

    // `!== undefined`, not truthiness: an empty string is a legitimate matcher
    // meaning "every URL", which is exactly how a total-outage case is written.
    if (opts.failMatching !== undefined && url.includes(opts.failMatching)) {
      // A transport-level failure: fetch rejects, no Response at all.
      throw new TypeError("fetch failed (simulated drop)");
    }
    if (opts.failFirst && served < opts.failFirst) {
      served++;
      throw new TypeError("fetch failed (simulated drop)");
    }
    // Honour the caller's abort signal, like a real fetch.
    if (init?.signal?.aborted) {
      throw new DOMException("The operation was aborted.", "AbortError");
    }

    const rel = url.startsWith(base) ? url.slice(base.length) : null;
    if (rel === "manifest.json") {
      return new Response(new TextEncoder().encode(JSON.stringify(manifest)) as Uint8Array<ArrayBuffer>, {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    }
    const body = rel !== null ? files.get(rel) : undefined;
    if (!body) {
      return new Response("Not Found", { status: 404 });
    }
    return new Response(body as Uint8Array<ArrayBuffer>, {
      status: 200,
      headers: { "content-type": "application/octet-stream" },
    });
  }) as typeof fetch;

  return {
    stats,
    restore: () => {
      globalThis.fetch = real;
    },
  };
}
