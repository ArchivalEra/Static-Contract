/**
 * Offline tests for the reference client.
 *
 * Everything here goes through the public interface — `openRelease`, `read`,
 * `readAll`, `close`, `useDecoder` — with a fake `fetch` on `globalThis`. The
 * client exposes no test hooks and none were added: if a case below needed
 * internals, it would be testing the wrong layer.
 *
 * The five silent traps this file exists to catch are the ones that were actually
 * hit while building the client:
 *
 *  1. `new Array(n)` holes making a "gap in chunks" check dead code
 *  2. decoding a concatenation instead of each chunk (truncates multi-chunk data)
 *  3. a timeout being classified as a final failure instead of a retryable one
 *  4. a 404 demoting a healthy mirror in the shared ledger
 *  5. `manifest-unreachable` being unreachable because errors passed through
 *
 * Each test names the trap it covers.
 */
import { test, describe, afterEach } from "node:test";
import assert from "node:assert/strict";

import { openRelease, useDecoder, forgetDecoder, ContractError } from "../fetch-concurrent.ts";
import { buildRelease, installFake, payload, sha256, BASE } from "./fixtures.ts";

// The client is codec-agnostic; Node's DecompressionStream has no zstd, so
// register a real one exactly as a pre-Chrome-123 browser would.
const zlib = await import("node:zlib");
useDecoder("zstd", (b) => new Uint8Array(zlib.zstdDecompressSync(b)));

let restore: (() => void) | undefined;
afterEach(() => {
  restore?.();
  restore = undefined;
});

const REF = { id: "fixture/payload.wasm", base: BASE, base_proxy: null };

describe("happy path", () => {
  test("single-chunk identity entry round-trips and verifies", async () => {
    const fx = buildRelease({ size: 1000, chunkSize: 4096, codecs: ["identity"] });
    const fake = installFake(fx.manifest, fx.files);
    restore = fake.restore;

    const rel = await openRelease(REF);
    const entry = rel.entries[0];
    assert.equal(entry.key, "wasm32/payload.wasm");
    assert.equal(entry.codec, "identity");
    assert.equal(entry.bytes, 1000);

    const bytes = await rel.read(entry);
    assert.equal(bytes.byteLength, 1000);
    assert.equal(sha256(bytes), entry.sha256);
    rel.close();
  });

  test("multi-chunk zstd decodes each chunk separately", async () => {
    // Trap 2: decoding the concatenation instead of each chunk truncates the
    // payload to the first frame. A single-chunk case cannot detect that, which
    // is why this fixture is deliberately multi-chunk.
    const fx = buildRelease({ size: 200_000, chunkSize: 30_000, codecs: ["zstd"] });
    const fake = installFake(fx.manifest, fx.files);
    restore = fake.restore;

    const rel = await openRelease(REF);
    const entry = rel.entries[0];
    assert.ok(entry, "entry exists");

    const bytes = await rel.read(entry);
    assert.equal(bytes.byteLength, 200_000, "full length, not just the first frame");
    assert.equal(sha256(bytes), entry.sha256);
    assert.deepEqual(bytes, payload(200_000), "byte-identical to the original");
    rel.close();
  });

  test("all three codecs produce identical plain bytes", async () => {
    for (const codec of ["zstd", "gzip", "identity"]) {
      const fx = buildRelease({ size: 50_000, chunkSize: 20_000, codecs: [codec] });
      const fake = installFake(fx.manifest, fx.files);
      try {
        const rel = await openRelease({ ...REF, id: `c/${codec}` });
        const bytes = await rel.read(rel.entries[0]);
        assert.equal(sha256(bytes), rel.entries[0].sha256, `${codec} verifies`);
        assert.deepEqual(bytes, payload(50_000), `${codec} matches the original`);
        rel.close();
      } finally {
        fake.restore();
      }
    }
  });

  test("readAll yields every entry in manifest order", async () => {
    const a = buildRelease({ size: 3000, chunkSize: 1000, codecs: ["gzip"], name: "a.bin", seed: 1 });
    const b = buildRelease({ size: 5000, chunkSize: 1000, codecs: ["gzip"], name: "b.bin", seed: 2 });
    const manifest = {
      ...a.manifest,
      entries: [
        ...(a.manifest.entries as unknown[]),
        ...(b.manifest.entries as unknown[]),
      ],
    };
    const files = new Map([...a.files, ...b.files]);
    const fake = installFake(manifest, files);
    restore = fake.restore;

    const rel = await openRelease({ ...REF, id: "two/entries" });
    assert.deepEqual(rel.entries.map((e) => e.key), ["wasm32/a.bin", "wasm32/b.bin"]);

    const seen: string[] = [];
    for await (const { info } of rel.readAll()) seen.push(info.key);
    assert.deepEqual(seen, ["wasm32/a.bin", "wasm32/b.bin"]);
    rel.close();
  });
});

describe("integrity", () => {
  test("a corrupted chunk body is rejected", async () => {
    const fx = buildRelease({ size: 10_000, chunkSize: 4_000, codecs: ["identity"] });
    const target = [...fx.files.keys()].find((k) => k.endsWith(".000"))!;
    const corrupted = new Map(fx.files);
    const bad = new Uint8Array(corrupted.get(target)!);
    bad[0] ^= 0xff;
    corrupted.set(target, bad);

    const fake = installFake(fx.manifest, corrupted);
    restore = fake.restore;

    const rel = await openRelease(REF);
    await assert.rejects(
      () => rel.read(rel.entries[0]),
      (e: unknown) => e instanceof ContractError && e.code === "entry-hash-mismatch",
    );
    rel.close();
  });

  test("a truncated chunk is rejected on length before hashing", async () => {
    const fx = buildRelease({ size: 10_000, chunkSize: 4_000, codecs: ["identity"] });
    const target = [...fx.files.keys()].find((k) => k.endsWith(".000"))!;
    const short = new Map(fx.files);
    short.set(target, short.get(target)!.subarray(0, 10));

    const fake = installFake(fx.manifest, short);
    restore = fake.restore;

    const rel = await openRelease(REF);
    await assert.rejects(() => rel.read(rel.entries[0]), (e: unknown) => {
      assert.ok(e instanceof ContractError);
      assert.equal(e.code, "chunk-unavailable");
      assert.match(e.message, /manifest says/);
      return true;
    });
    rel.close();
  });
});

describe("manifest validation", () => {
  test("unknown schema rejects the whole manifest (V10)", async () => {
    const fx = buildRelease({ size: 1000, chunkSize: 4096, codecs: ["identity"] });
    const fake = installFake({ ...fx.manifest, schema: 99 }, fx.files);
    restore = fake.restore;

    await assert.rejects(() => openRelease(REF), (e: unknown) => {
      assert.ok(e instanceof ContractError);
      assert.equal(e.code, "schema-unsupported");
      return true;
    });
  });

  test("chunk names outside the V1 whitelist are refused", async () => {
    // A name like `//evil.test/x` would resolve to a different host via
    // `new URL(file, root)` — this is a security control, not tidiness.
    const fx = buildRelease({ size: 1000, chunkSize: 4096, codecs: ["identity"] });
    const entry = (fx.manifest.entries as Array<{ variants: Array<{ chunks: Array<{ file: string }> }> }>)[0];
    entry.variants[0].chunks[0].file = "//evil.test/payload";

    const fake = installFake(fx.manifest, fx.files);
    restore = fake.restore;

    await assert.rejects(() => openRelease(REF), (e: unknown) => {
      assert.ok(e instanceof ContractError);
      assert.equal(e.code, "manifest-invalid");
      assert.match(e.message, /whitelist/);
      return true;
    });
  });

  test("codecs disagreeing on chunk count is rejected (V5)", async () => {
    const fx = buildRelease({ size: 9000, chunkSize: 4_000, codecs: ["gzip", "identity"] });
    const entry = (fx.manifest.entries as Array<{ variants: Array<{ chunks: unknown[] }> }>)[0];
    // Slice one chunk off one codec: same entry, mismatched counts.
    entry.variants[1].chunks.pop();

    const fake = installFake(fx.manifest, fx.files);
    restore = fake.restore;

    await assert.rejects(() => openRelease(REF), (e: unknown) => {
      assert.ok(e instanceof ContractError);
      assert.equal(e.code, "manifest-invalid");
      assert.match(e.message, /chunk count/);
      return true;
    });
  });

  test("javascript: license.url is refused (V11)", async () => {
    const fx = buildRelease({ size: 1000, chunkSize: 4096, codecs: ["identity"] });
    const fake = installFake(
      { ...fx.manifest, license: { id: "MIT", url: "javascript:alert(1)" } },
      fx.files,
    );
    restore = fake.restore;

    await assert.rejects(() => openRelease(REF), (e: unknown) => {
      assert.ok(e instanceof ContractError);
      assert.equal(e.code, "manifest-invalid");
      assert.match(e.message, /https:\/\//);
      return true;
    });
  });

  test("an entry with no decodable variant names what was missing", async () => {
    const fx = buildRelease({ size: 1000, chunkSize: 4096, codecs: ["xz"] });
    const fake = installFake(fx.manifest, fx.files);
    restore = fake.restore;

    await assert.rejects(() => openRelease(REF), (e: unknown) => {
      assert.ok(e instanceof ContractError);
      assert.equal(e.code, "no-decodable-variant");
      assert.match(e.message, /xz/);
      return true;
    });
  });
});

describe("fallback and retry", () => {
  test("a dead base falls through to base_proxy", async () => {
    const fx = buildRelease({ size: 20_000, chunkSize: 8_000, codecs: ["gzip"] });
    const files = fx.files;
    const realFetch = globalThis.fetch;

    // base host fails outright; proxy host serves.
    const proxyBase = "https://proxy.test/releases/fixture/";
    globalThis.fetch = (async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      if (url.startsWith(BASE)) throw new TypeError("fetch failed (dead base)");
      const rel = url.startsWith(proxyBase) ? url.slice(proxyBase.length) : null;
      if (rel === "manifest.json") {
        return new Response(new TextEncoder().encode(JSON.stringify(fx.manifest)) as Uint8Array<ArrayBuffer>, { status: 200 });
      }
      const body = rel ? files.get(rel) : undefined;
      return body ? new Response(body as Uint8Array<ArrayBuffer>, { status: 200 }) : new Response("nope", { status: 404 });
    }) as typeof fetch;

    try {
      const rel = await openRelease({ id: "x", base: BASE, base_proxy: proxyBase });
      const bytes = await rel.read(rel.entries[0]);
      assert.deepEqual(bytes, payload(20_000));
      rel.close();
    } finally {
      globalThis.fetch = realFetch;
    }
  });

  test("a transport drop is retried and then succeeds", async () => {
    // Trap 3 (part 1): a drop must be retryable, not final. The fixture fails the
    // first request to one chunk, so only a retry can produce a green result.
    const fx = buildRelease({ size: 20_000, chunkSize: 8_000, codecs: ["gzip"] });
    const victim = [...fx.files.keys()][0];
    let failed = false;

    const fake = installFake(fx.manifest, fx.files, {
      intercept: (url) => {
        if (!failed && url.endsWith(victim)) {
          failed = true;
          throw new TypeError("fetch failed (one-off drop)");
        }
        return undefined;
      },
    });
    restore = fake.restore;

    const rel = await openRelease(REF);
    const bytes = await rel.read(rel.entries[0]);
    assert.equal(bytes.byteLength, 20_000, "retry recovered the chunk");
    assert.ok((fake.stats.counts.get(`${BASE}${victim}`) ?? 0) >= 2, "victim was requested twice");
    rel.close();
  });

  test("a 404 does not demote the mirror for other entries", async () => {
    // Trap 4: previously *any* failure incremented the root's score, so one
    // missing file permanently pushed every later request to the fallback.
    //
    // The asymmetry has to be real for this to be measurable: the missing file
    // must be absent from the **mirror only**, while the proxy has it. Then a
    // demoted mirror is visible — the next good read goes to the proxy instead of
    // the mirror. With both roots missing it, both counters rise together, the
    // order is unchanged, and a demotion is invisible.
    const a = buildRelease({ size: 4000, chunkSize: 2000, codecs: ["gzip"], name: "present.bin" });
    const b = buildRelease({ size: 4000, chunkSize: 2000, codecs: ["gzip"], name: "absent.bin", seed: 7 });
    const manifest = {
      ...a.manifest,
      entries: [...(a.manifest.entries as unknown[]), ...(b.manifest.entries as unknown[])],
    };
    const proxyBase = "https://proxy.test/releases/fixture/";
    const realFetch = globalThis.fetch;
    const hits: Record<string, number> = {};

    // Mirror lacks absent.bin; proxy has everything.
    const mirrorFiles = a.files;
    const proxyFiles = new Map([...a.files, ...b.files]);

    globalThis.fetch = (async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      const host = new URL(url).host;
      hits[host] = (hits[host] ?? 0) + 1;
      const base = url.startsWith(BASE) ? BASE : url.startsWith(proxyBase) ? proxyBase : null;
      if (!base) return new Response("nope", { status: 404 });
      const rel = url.slice(base.length);
      if (rel === "manifest.json") {
        return new Response(new TextEncoder().encode(JSON.stringify(manifest)) as Uint8Array<ArrayBuffer>, { status: 200 });
      }
      const files = base === BASE ? mirrorFiles : proxyFiles;
      const body = files.get(rel);
      return body ? new Response(body as Uint8Array<ArrayBuffer>, { status: 200 }) : new Response("Not Found", { status: 404 });
    }) as typeof fetch;

    try {
      const rel = await openRelease({ id: "two/entries", base: BASE, base_proxy: proxyBase });
      const [present, absent] = rel.entries;

      // absent.bin: mirror 404s, proxy serves it. That read must succeed, and it
      // must have gone through the proxy — proving the fallback works.
      assert.ok((await rel.read(absent)).byteLength === 4000, "proxy supplied the missing file");

      // Now the decisive part: present.bin exists on both. If the 404 had demoted
      // the mirror, this read lands on the proxy; if not, it lands on the mirror.
      const mirrorBefore = hits["mirror.test"] ?? 0;
      const proxyBefore = hits["proxy.test"] ?? 0;
      assert.equal((await rel.read(present)).byteLength, 4000);

      assert.ok(
        (hits["mirror.test"] ?? 0) > mirrorBefore,
        "the mirror still served a good entry after answering 404 for another",
      );
      assert.equal(
        hits["proxy.test"] ?? 0,
        proxyBefore,
        "a 404 must not hand later traffic to the fallback",
      );
      rel.close();
    } finally {
      globalThis.fetch = realFetch;
    }
  });

  test("every root failing produces a typed error naming the last root", async () => {
    const fx = buildRelease({ size: 1000, chunkSize: 4096, codecs: ["identity"] });
    const fake = installFake(fx.manifest, fx.files, { failMatching: "" });
    restore = fake.restore;

    // failMatching: "" matches everything, so every request drops.
    await assert.rejects(() => openRelease(REF), (e: unknown) => {
      assert.ok(e instanceof ContractError);
      assert.match(e.message, /every root failed/);
      assert.match(e.message, /mirror\.test/);
      return true;
    });
  });

  test("manifest-unreachable is actually reachable", async () => {
    // Trap 5: this code path used to be unreachable because the root layer threw
    // `chunk-unavailable` and `wrap()` passed ContractError through unchanged.
    const fx = buildRelease({ size: 1000, chunkSize: 4096, codecs: ["identity"] });
    const fake = installFake(fx.manifest, fx.files, { failMatching: "" });
    restore = fake.restore;

    await assert.rejects(() => openRelease(REF), (e: unknown) => {
      assert.ok(e instanceof ContractError);
      assert.equal(e.code, "manifest-unreachable");
      return true;
    });
  });

  test("an attempt budget aborts a stalled response and retries", async () => {
    // Trap 3 (part 2): a stall is not a status. It must be retried, and the budget
    // must bound the cost — otherwise one dead request eats the whole download.
    const fx = buildRelease({ size: 8000, chunkSize: 4000, codecs: ["gzip"] });
    const victim = [...fx.files.keys()][0];
    let stalled = false;

    const fake = installFake(fx.manifest, fx.files, {
      intercept: async (url) => {
        if (!stalled && url.endsWith(victim)) {
          stalled = true;
          // Never resolves: the client's budget must abort it.
          return new Promise<Response>(() => {});
        }
        return undefined;
      },
    });
    restore = fake.restore;

    const started = Date.now();
    const rel = await openRelease(REF, { attemptBudgetMs: 300 });
    const bytes = await rel.read(rel.entries[0]);
    const elapsed = Date.now() - started;

    assert.equal(bytes.byteLength, 8000, "stall was retried and the entry completed");
    assert.ok(elapsed < 5000, `bounded by the budget, took ${elapsed}ms`);
    rel.close();
  });
});

describe("cancellation and lifecycle", () => {
  test("caller abort surfaces as ContractError('aborted')", async () => {
    const fx = buildRelease({ size: 200_000, chunkSize: 20_000, codecs: ["identity"] });
    const fake = installFake(fx.manifest, fx.files, { delayMs: 5 });
    restore = fake.restore;

    const ac = new AbortController();
    const rel = await openRelease(REF, { signal: ac.signal });
    const p = rel.read(rel.entries[0]);
    ac.abort();

    await assert.rejects(p, (e: unknown) => {
      assert.ok(e instanceof ContractError);
      assert.equal(e.code, "aborted");
      return true;
    });
    rel.close();
  });

  test("a foreign EntryInfo is refused", async () => {
    const fx = buildRelease({ size: 1000, chunkSize: 4096, codecs: ["identity"] });
    const fake = installFake(fx.manifest, fx.files);
    restore = fake.restore;

    const rel = await openRelease(REF);
    await assert.rejects(
      () => rel.read({ ...rel.entries[0], key: "nope/nope" }),
      (e: unknown) => e instanceof ContractError && e.code === "manifest-invalid",
    );
    rel.close();
  });

  test("close() is idempotent and stops later reads", async () => {
    const fx = buildRelease({ size: 1000, chunkSize: 4096, codecs: ["identity"] });
    const fake = installFake(fx.manifest, fx.files);
    restore = fake.restore;

    const rel = await openRelease(REF);
    rel.close();
    rel.close();
    await assert.rejects(
      () => rel.read(rel.entries[0]),
      (e: unknown) => e instanceof ContractError && e.code === "aborted",
    );
  });

  test("onEntry reports progress once per entry", async () => {
    const fx = buildRelease({ size: 3000, chunkSize: 1000, codecs: ["gzip"] });
    const fake = installFake(fx.manifest, fx.files);
    restore = fake.restore;

    const seen: string[] = [];
    const rel = await openRelease(REF, {
      onEntry: (_info, done, total) => seen.push(`${done}/${total}`),
    });
    for await (const _ of rel.readAll()) {
      // consume
    }
    assert.deepEqual(seen, ["1/1"]);
    rel.close();
  });
});

describe("codec registry", () => {
  test("a codec can be unregistered, restoring the platform view", async () => {
    const fx = buildRelease({ size: 4000, chunkSize: 2000, codecs: ["zstd"] });
    const fake = installFake(fx.manifest, fx.files);
    restore = fake.restore;

    assert.equal(forgetDecoder("zstd"), true, "registered codec is removable");
    await assert.rejects(() => openRelease(REF), (e: unknown) => {
      assert.ok(e instanceof ContractError);
      assert.equal(e.code, "no-decodable-variant");
      return true;
    });

    // Put it back for any later test in this file.
    const zlib2 = await import("node:zlib");
    useDecoder("zstd", (b) => new Uint8Array(zlib2.zstdDecompressSync(b)));
    const rel = await openRelease(REF);
    assert.equal(rel.entries[0].codec, "zstd");
    rel.close();
  });

  test("identity cannot be overridden", () => {
    assert.throws(
      () => useDecoder("identity", (b) => b),
      (e: unknown) => e instanceof ContractError && e.code === "manifest-invalid",
    );
  });
});
