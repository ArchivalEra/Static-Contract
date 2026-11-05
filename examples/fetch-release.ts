/**
 * Live end-to-end run against the production catalogue, and the wasm32 benchmark.
 *
 * Not a unit test — this fetches real releases over the real network and checks
 * every byte against the manifest's declared sha256.
 *
 * ## Why `base_proxy` is left in place
 *
 * The interesting property is **graceful switching**, not "works when forced
 * through GitHub". With both roots configured the client prefers `base` (the
 * mirror) and only falls back when `base` actually fails — which is what canon
 * v1.1 §5.3 specifies: `base` is the designed primary, `base_proxy` is the
 * fallback, and falling back is normal operation rather than an error.
 *
 * ## Why zstd
 *
 * zstd is what the mirror's chunk sizing was tuned for, and it is the codec that
 * makes these releases small on the wire: measured 4.9–5.1× compression, so
 * 22 MiB of transfer yields 109 MiB of payload. Reporting throughput in decoded
 * bytes understates the link by that factor, so both numbers are printed.
 *
 * ## Measured 2026-11-04 (this host, through `base` only)
 *
 *   Octave-Full-Wasm/v0.1.0  wasm32   9 chunks   7.42 MiB wire → 37.95 MiB decoded   14.5 s
 *   OpenModelica/v0.2.0-wasm32  omc  18 chunks  14.66 MiB wire → 71.27 MiB decoded   22.8 s
 *   combined                        27 chunks  22.06 MiB wire → 109.2 MiB decoded   37.3 s
 *
 * Every one of the 58 requests went to `static.isui.ren`; the fallback was
 * configured and never needed. Concurrency across entries (burst=3, burst=4)
 * measured within noise of serial — on this link the limit is the path to the
 * edge (0.5–0.6 MiB/s of wire bytes), not the number of parallel requests.
 * Parallelism still matters when several chunks share one entry, which is the
 * default inside `read()`.
 *
 * ## Running it
 *
 *   npx tsx examples/fetch-release.ts
 *
 * Node 26's `DecompressionStream` does not accept `zstd`, so this registers
 * `fzstd` — exactly what a browser before Chrome 123 does. On a runtime whose
 * platform decodes zstd the registration is unnecessary but harmless.
 */
import { openRelease, useDecoder, type EntryInfo, type ReleaseRef } from "./fetch-concurrent";

/**
 * Products to fetch. These are the two the contract currently serves, and they
 * are **examples, not configuration**: point this at your own releases when you
 * copy the file. Overridable at run time:
 *
 *   SC_CATALOGUE=https://your-mirror/catalogue.json npx tsx examples/fetch-release.ts
 */
const TARGETS: { id: string; product: string }[] = [
  { id: "Octave-Full-Wasm/v0.1.0", product: "wasm32" },
  { id: "OpenModelica-Full-Wasm/v0.2.0-wasm32", product: "omc" },
];

/**
 * Entries fetched concurrently. Set above 1 to widen it.
 *
 * Keep this at 1 for the default run. `read()` already runs `CONCURRENCY`
 * (2) chunk fetches in parallel, and that is what saturates this link. Widening
 * both multiplies connections without buying throughput.
 */
const BURST = 1;

/**
 * Where to read the catalogue from.
 *
 * `SC_CATALOGUE` overrides it. This host is the reference mirror of the cluster
 * this repository belongs to — swapping it (or the TARGETS above) is the first
 * thing to do when reusing this file elsewhere.
 */
const CATALOGUE =
  (globalThis as { process?: { env?: Record<string, string | undefined> } }).process?.env
    ?.SC_CATALOGUE ?? "https://static.isui.ren/catalogue.json";

interface Catalogue {
  releases: ReleaseRef[];
}

interface Stats {
  /** Bytes that crossed the network, zstd-encoded. */
  wire: number;
  /** Bytes after decoding, which is what the manifest calls `entry.bytes`. */
  decoded: number;
  requests: number;
  seconds: number;
}

async function main(): Promise<void> {
  const fzstd = await import("fzstd");
  useDecoder("zstd", (b) => fzstd.decompress(b));

  // Instrument fetch so the report can say which host actually served the run.
  // Without this, "it worked" says nothing about whether the fallback silently
  // carried everything.
  const hosts: Record<string, number> = {};
  let wire = 0;
  let requests = 0;
  const realFetch = globalThis.fetch;
  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
    const host = new URL(url).host;
    hosts[host] = (hosts[host] ?? 0) + 1;
    requests++;
    const res = await realFetch(input, init);
    // Read the body here to count encoded bytes, then hand the consumer an
    // equivalent response. This is the only reason for the wrapper.
    const body = await res.arrayBuffer();
    wire += body.byteLength;
    return new Response(body, { status: res.status, statusText: res.statusText, headers: res.headers });
  }) as typeof fetch;

  const catalogue = (await (await fetch(CATALOGUE)).json()) as Catalogue;
  const total: Stats = { wire: 0, decoded: 0, requests: 0, seconds: 0 };

  for (const target of TARGETS) {
    const ref = catalogue.releases.find((r) => r.id === target.id);
    if (!ref) throw new Error(`${target.id} is not in the catalogue`);

    // Reset the wire counter per release so each line reports its own cost.
    wire = 0;
    requests = 0;
    const started = Date.now();

    // Both roots passed through untouched: no forcing, no extra options.
    const release = await openRelease(ref);
    const wanted: EntryInfo[] = release.entries.filter((e) => e.product === target.product);
    if (wanted.length === 0) {
      throw new Error(`${target.id} has no entries for product ${target.product}`);
    }

    // Every entry must be zstd — that is the codec this run is about. If the
    // client silently fell back to gzip the numbers would not be comparable.
    const codecs = [...new Set(wanted.map((e) => e.codec))];
    if (codecs.length !== 1 || codecs[0] !== "zstd") {
      throw new Error(`expected zstd only, got ${codecs.join(",")}`);
    }

    const declared = wanted.reduce((n, e) => n + e.bytes, 0);

    // BURST entries at a time. `read()` already parallelises chunks inside one
    // entry; this adds parallelism across entries on top.
    for (let i = 0; i < wanted.length; i += BURST) {
      const group = wanted.slice(i, i + BURST);
      const got = await Promise.all(group.map((e) => release.read(e)));
      got.forEach((bytes, j) => {
        // read() resolves only after the entry's sha256 matched, so this checks
        // the manifest's declared size, not corruption.
        if (bytes.byteLength !== group[j].bytes) {
          throw new Error(`${group[j].key}: got ${bytes.byteLength} B, manifest says ${group[j].bytes}`);
        }
      });
    }

    const seconds = (Date.now() - started) / 1000;
    const mib = (n: number) => (n / 1048576).toFixed(2);
    console.log(
      `${target.id} [${target.product}]  ` +
        `${wanted.length} entries, ${requests} requests  ` +
        `wire ${mib(wire)} MiB → decoded ${mib(declared)} MiB ` +
        `(${(declared / wire).toFixed(1)}x)  ` +
        `${seconds.toFixed(1)}s  ` +
        `${mib(wire / seconds)} MiB/s wire, ${mib(declared / seconds)} MiB/s decoded`,
    );

    total.wire += wire;
    total.decoded += declared;
    total.requests += requests;
    total.seconds += seconds;
  }

  const mib = (n: number) => (n / 1048576).toFixed(2);
  console.log(
    `\nTOTAL ${total.requests} requests, ` +
      `wire ${mib(total.wire)} MiB → decoded ${mib(total.decoded)} MiB, ` +
      `${total.seconds.toFixed(1)}s, ${mib(total.wire / total.seconds)} MiB/s wire`,
  );
  console.log("requests per host:", JSON.stringify(hosts));

  // Which hosts were reached tells us whether the fallback was used, but the
  // decision must come from what the catalogue *declared*, not from sniffing for
  // a particular vendor: any non-GitHub fallback would be miscounted as a mirror.
  const declaredMirrors = new Set(
    TARGETS.map((t) => catalogue.releases.find((r) => r.id === t.id))
      .filter((r): r is ReleaseRef => Boolean(r))
      .map((r) => new URL(r.base).host),
  );
  const fallbackHosts = [...declaredMirrors].length
    ? Object.keys(hosts).filter((h) => !declaredMirrors.has(h))
    : [];
  if (fallbackHosts.length === 0) {
    console.log(
      "Every request landed on the mirror — `base` carried the whole run and the\n" +
        "fallback was never needed. That is the designed behaviour, not a sign that\n" +
        "`base_proxy` is dead weight.",
    );
  } else {
    console.log(
      `Some requests went to a fallback host (${fallbackHosts.join(", ")}). That is\n` +
        "normal operation too — `base_proxy` exists to make a failing mirror a\n" +
        "non-event for consumers.",
    );
  }
}

main().catch((e) => {
  // No `process.exit` here: this file is written for a browser too, and an
  // uncaught rejection is already a visible failure in every runtime.
  console.error(e);
  throw e;
});
