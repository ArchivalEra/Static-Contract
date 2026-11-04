# Release Contract v1.1 · License Protocol (Final)

> **Status**: **Final** (2026-11-01), manifest `schema` raised to **3**.
> Implementation: `tools/check-release-v4.py` adds V11–V15; `scripts/sync-catalogue.py` adds G7;
> `scripts/build-site.py` renders the license column. **Nothing counts as landed until the validator self-proves** (see §8).
>
> **Source**: the user's rulings — that every resource component must explicitly declare its own
> license; that the apt copyright convention should be dug out first and the protocol designed
> from it, because v1.1 was coming; and, after a four-direction design-it-twice, that the result
> should be finalized.
> **Every apt-side fact is taken from real objects on this machine** (`/usr/share/doc/*/copyright`); re-run in §7.

---

## 0. One sentence

> **The license declaration is a first-class field of a release: by default one expression covers
> the whole release, and when components differ it is overridden on that entry. The declaration
> must be traceable to bytes inside the release.**
> **"Not known" is a legal terminal state, but "not known" does not get into the catalogue.**

Three design criteria, in order of importance:

1. **The client knows exactly one rule** — `entry.license ?? manifest.license.expr`.
   No glob, no precedence table, no namespace ambiguity. Two independent implementations will not disagree.
2. **Not known is not the same as absent** — `status: "unstated" | "refused"` is a legal manifest,
   but the catalogue excludes it without exception. **Being wrong is worse than being empty** —
   forcing a false answer is worse than leaving the field blank.
3. **The declaration must anchor to bytes** — `provenance.sources[].anchor` points at an entry inside the release,
   and `anchor_sha256` must equal that entry's sha256. ⇒ **zero downloads to validate** (the G4 technique),
   and a declaration that does not match the truth becomes structurally discoverable.

---

## 1. Problem statement (why v1.1 is needed)

A `schema: 2` manifest **has no license field at all** (measured keys:
`chunkSize` / `codecs` / `entries` / `id` / `products` / `schema`). Consequences:

| Situation | Problem |
|---|---|
| The site marks only its own AGPL | The listed releases **have unknown license** — a reader cannot tell whether `forge-optim-1.6.3` may be used commercially |
| The bytes come from a third party (Octave-Forge) | The `Octave-Extra-Content` LICENSE states verbatim: "Package bytes ... governed by each package's own license (see COPYING inside its tarball)", and **that COPYING lives inside the tarball, not in any metadata** |
| The client only pulls bytes | You learn the license only after fetching the tarball — **too late**, and many packages have no COPYING at all |
| The repository-level `license` field is not trustworthy | Two measured cases: the `LLVM-wasm` repo is `AGPL-3.0` but `clang.wasm` is `Apache-2.0 WITH LLVM-exception`; `Octave-Extra-Content` is `NOASSERTION` (its text says each package carries its own license) |

**This is a distribution-compliance gap, not a presentation problem.** apt ran into it long ago, and its answer is the `copyright` file.

---

## 2. What apt does (study of real objects, measured on this machine)

### 2.1 Mechanism and coverage

Debian ships a **machine-readable copyright file** (DEP-5) at `/usr/share/doc/<pkg>/copyright` for every package:

```
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: <name>
Source: <upstream URL>

Files: *
Copyright: <year author>
License: <SPDX short name>

Files: <specific path>
Copyright: ...
License: ...
```

**Measured coverage** (2026-11-01, this machine): `3265` packages contain `3237` copyright files ⇒ **99.1%**.
⇒ `copyright` is a **near-mandatory** convention in the apt ecosystem.

### 2.2 Four rules extracted (and what we adopt, and what we do not)

| What apt does | Evidence in the real objects | v1.1 |
|---|---|---|
| `Files:` glob, `*` fallback plus specific overrides | accountsservice | **not adopted** — no glob (the client would have to reimplement the matcher + precedence + namespaces; entry-level override instead) |
| `License:` short name plus the full text in a separate paragraph | apt, 7zip | adopted (`expr` short name + `provenance` pointer) |
| `or` / `and` multiple licenses | aha `MPL-1.1 or LGPL-3+`; apt `GPL-2+ and curl` | adopted (SPDX expression grammar) |
| `Files-Excluded:` declaring "present as-is but not distributed" | 7zip's RAR code | adopted (`excluded[]`, see §4.4) |
| **the honest "best effort" stance** | the `Comment:` paragraph of `apt/copyright`, verbatim: *"This file is a best effort to document the statements of copyright and licenses as stated in the file, but is not a complete representation of all copyright"* | **adopted wholesale** — the protocol does not demand perfection, it demands honest labelling of what is known and what is not |

### 2.3 The criterion for **not adopting** the `Files:` glob (agreed by all four review directions)

The draft once used a `Files: *` fallback plus specific overrides (copying DEP-5). **Three independent designs all rejected it**, for the same reasons:

- the client must implement a glob matcher (does `*` cross `/`? what about case?)
- it must implement a **precedence order** (first match wins)
- it must implement **namespace disambiguation** (`<product>/<name>` or bare `name`?)
- all three implementations will inevitably diverge at the edges ⇒ **one manifest, two clients reading two different licenses**

And the real data does not support that complexity: of 13 forge packages, **8 carry a single license**, and the most complex,
`optim`, is only `GPL-3.0-or-later and BSD-3-Clause and public domain` (one AND chain).

---

## 3. Protocol shape (`schema: 3`)

**A license is a name plus a link to the full text.** A one-line string is not enough.
As ruled on 2026-11-01: the license text differs between projects, and projects change
licenses across generations. A release must therefore point at the license text that
applies to it, per component, rather than assert a short identifier that will go stale.

```jsonc
{
  "schema": 3,
  "id": "Octave-Extra-Content/forge-optim-1.6.3",
  "chunkSize": 5242880,
  "codecs": ["zstd", "gzip", "identity"],

  "license": {
    "id":  "GPL-3.0-or-later AND BSD-3-Clause AND LicenseRef-public-domain",
    "url": "https://octave.sourceforge.io/optim/COPYING.html"
  },

  "products": { ... },
  "entries": [
    {
      "product": "forge", "name": "optim-1.6.3.tar.gz",
      // an individual artifact may also point at its own link
      // (in the real data FONT-RFN / NOTICE entries often differ)
      "license": {"id": "MIT", "url": "https://opensource.org/license/mit"},
      ...
    }
  ]
}
```

### 3.1 Three layers, one job each (**the whole of the v1.1 design**)

| Layer | Who reads it | Criterion |
|---|---|---|
| **bytes** | downloaders | `GET <base>/<file>` — **one link, a plain GET, license-unaware** |
| **manifest** | anyone who needs integrity / discovery / compliance | `license: {id, url}` — **display, plus click-through to the full text** |
| **catalogue** | the listing gate | missing either `id` or `url` ⇒ **not listed** |

**The gate blocks once, at listing time, not N times at every consumer.**
This is the user's 2026-11-01 correction: someone who wants a package wants one link to download it, and nothing more.

### 3.2 Fields

| Field | Required | Meaning |
|---|---|---|
| `license.id` | yes | SPDX expression (may be compound: `A AND B`). **Not checked against the SPDX vocabulary** |
| `license.url` | yes | **must be `https://`**. Points at the license text for that release |
| `entries[].license` | optional | overrides the default; likewise two items, `{id, url}` |
| `entries[].role` | optional | `payload` (default) / `license` / `notice` |
| `entries[].excluded[]` | optional | `{path, why}` — "present inside the package but not distributed" |

**Why `url` is required rather than optional:**

1. **Each project's text differs** — `optim`'s `COPYING.html` is not standard GPL text; it carries additional terms;
2. **They are replaced across generations** — upstream changes license every few years, so the `id` string expires while the **current text** that `url` points at does not;
3. **GPL-family licenses require the full text to accompany distribution** — pointing at an authoritative external text is cheaper than storing 16 copies of the GPL, one per release;
4. **13/13 real packages already have a ready link** (the `url` field of the `fa-copyright` link in `packages/*.json`),
   so migration is transcription, not research.

### 3.3 The client (**unchanged, not one line different**)

```
1. GET <base>/manifest.json          # if you want discovery
2. validate schema / V1–V11 (local, 0 requests)
3. take variant.chunks[i].file verbatim   # never assemble the name
4. GET <base>/<file>                 # a plain GET — unrelated to the license
5. verify bytes + per-chunk sha256 → decode → concatenate
6. in the UI show license.id and make it a link to license.url
```

**The license appears in none of the branches of steps 3–5.** It affects the display in step 6 only.

**The client does not need to**: parse SPDX, verify over the network, or refuse to unpack.
`license` is **two lines of metadata**, not a gate. Clicking the link shows the full text — that is the correct answer to "the texts differ per project".

---

## 4. Invariant (V11, the only one)

| # | Invariant | Counter-case (must reject) |
|---|---|---|
| **V11** | `license` is a `{id, url}` object; `id` is a non-empty string that passes the SPDX grammar (may be compound); `url` starts with `https://` and is non-empty. `entries[].license`, when present, the same. `role ∈ {payload,license,notice}`; `excluded[].why` non-empty | missing `license` / missing `id` / missing `url` / `url` is `http://` / `id` empty string / `license` is a string (the old form without a link) |

**Zero downloads, zero network.** V11 reads manifest structure only.

### 4.1 SPDX expression grammar (for `id`)

```
expr := term (("AND" | "OR") term)*
term := id ["WITH" exception] | "(" expr ")" | license-ref
id   := ^[A-Za-z0-9][A-Za-z0-9.+-]*$
license-ref := ^LicenseRef-[A-Za-z0-9._-]+$
```

- operators must be **uppercase**; `WITH` applies to a single identifier and does not chain
- **no check against the SPDX vocabulary** (the vocabulary drifts; the same criterion as v4 §3, "platform capacity does not enter the protocol")
- **the client does not need to implement it** — it only displays the `id` string

### 4.2 Prose → SPDX conversion (producers must read this; measured, and it bit us)

License values in upstream metadata are **prose** (`GPL-3.0-or-later and BSD-3-Clause and public domain`).
When converting to SPDX you **must tokenize first, then replace whole tokens**:

```python
# correct
toks = label.split()
out = ["AND" if t.lower() == "and" else
       "OR"  if t.lower() == "or"  else
       t for t in toks]
```

```python
# wrong: a regex word boundary lands inside hyphens
re.sub(r"\band\b", "AND", label)
re.sub(r"\bor\b",  "OR",  label)
#   GPL-3.0-or-later  →  GPL-3.0-OR-later   ← invalid, and all 13 artifacts are hit at once
```

**Why this must be guarded**: the **shape** of `GPL-3.0-OR-later` is legal (`^[A-Za-z0-9][A-Za-z0-9.+-]*$`),
so the criterion "do not check the SPDX vocabulary" would let it through. ⇒ V11 additionally blocks one mechanical malformation:

```
an identifier must not contain `-AND-` / `-OR-` (uppercase) in the middle, nor end with `-AND` / `-OR`
```

This does **not** check the SPDX vocabulary (it drifts, see below); it blocks only the class where the string replacement looks right
and the boundary conditions are all wrong.

(Source: `Octave-Extra-Content` `mail/135` §3, measured: among the 13 packages, the batch carrying `-or-later` would collectively become invalid. After reproducing it I added the criterion, and the self-proof went from 35 → 37.)

### 4.3 Implementers beware: zstd chunks must be **decoded chunk by chunk**

```
Decode each chunk.file separately and then concatenate; do not treat several chunks as one multi-frame stream and decode it in one pass.
```

A `decompress()`-style API usually **decodes only the first frame** ⇒ a multi-chunk payload is silently truncated.
V6's 2^25 limit exists so that each chunk decodes independently, and this is extremely easy to get wrong.

**Criterion: a passing single-chunk case does not prove the multi-chunk path.** Verification must use a **multi-chunk** payload
(LLVM's first version, measured: 10 single-chunk cases passed, 4 multi-chunk cases blew up).

(Source: `LLVM-wasm` measurement + `extra-content` `mail/135` §4.1 review.)

### 4.4 Boundary: tarballs inside a release are not governed by the contract

The contract governs **the one `manifest.json` at the top level of a release**. A tarball may contain any structure
(including another manifest, such as the one a host provision hard-codes) —
that is an internal arrangement between producer and consumer, **not part of the distribution contract**.

The sentence is here so that nobody later asks where exactly the manifest is: **there is only one place.**

### 4.5 Known limit: passing V11 does not mean the license is correct

> Passing the shape check for `license` is **not** the same as writing the license correctly. V11 blocks mechanical malformations only;
> semantic correctness is the producer's responsibility, checked **item by item**.

**This one is a lesson paid in blood** (2026-11-01, three times in the same night):

| Who | The error | How it was caught |
|---|---|---|
| me | recommended LLVM write `Apache-2.0 WITH LLVM-exception` | omitted the AGPL in `driver/*.mjs` and `LICENSE` — **found when LLVM checked item by item** |
| me | another letter wrote emscripten as `BSD-3-Clause` | it is actually `MIT OR NCSA` — **found when LLVM read the first paragraph of the text** |
| extra-content | **inferred** the whole package's license from "this is an LLVM toolchain package" | the same two places — rejected by LLVM |

**All three times, inference lost to item-by-item checking.** All three passed V11 (legal shape), and all three contents were wrong.

⇒ **V11's value is blocking mechanical malformations (missing fields, plain http, `-OR-` mixed into hyphens),
not proving semantic correctness.** Do not mistake the former for the latter.

**Recommended practice** (not required): after checking item by item, write `license.verified` (see §4.7),
leaving a trace of why this id is right. `LLVM-wasm` traced `NCSA` to the official SPDX list
at `licenses.md:483` + `text/NCSA.txt`, same source — that is the correct shape.

### 4.6 Known limit: the contract cannot prove a declaration is true (**say it plainly, do not pretend**)

V11 checks **shape** only (legal SPDX + https url). What it can catch and what it cannot:

| Can catch | Cannot catch |
|---|---|
| missing field / empty string / plain http | **whether `id` really applies to these bytes** |
| SPDX grammar errors (lowercase operator, unbalanced parentheses) | whether the `id` is spelled right (`NCSA` vs `UoI-NCSA`) |
| mechanical malformation when converting prose to SPDX (`GPL-3.0-OR-later`) | whether the text `url` points at is the one `id` names |
| `url` points at a 404 (**not verified either, see below**) | whether the publisher is honest |

**`url` reachability is not verified either**: on this machine 3 samples measured, 1 returned `200` and 2 returned `000`
(a local network egress problem, not a link defect). The protocol cannot distinguish a broken link from a network that is unreachable from here.

⇒ **A human read is still the last line.** This is not a defect; it is the price of the criterion that the protocol does not pretend it can prove truth.

**Instance (2026-11-01, actually hit)**:
I recommended `Apache-2.0 WITH LLVM-exception` to `LLVM-wasm` and omitted the `AGPL-3.0-or-later` of `driver/*.mjs` and `LICENSE` in its repo; another letter wrote emscripten as `BSD-3-Clause` when it is actually `MIT OR NCSA`. **Both were found by a human reading the text, not by a validator.**

### 4.7 Optional: `license.verified` (a human-check trace, **not a criterion**)

The protocol does not check the SPDX vocabulary (it drifts). But why a given id is right can be left on record:

```jsonc
"license": {
  "id": "MIT OR NCSA",
  "url": "https://github.com/emscripten-core/emscripten/blob/main/LICENSE",
  "verified": {                       // optional
    "by": "LLVM-wasm",
    "at": "2026-11-01",
    "how": "spdx/license-list-data licenses.md:483 + text/NCSA.txt, same source as the text in the package"
  }
}
```

**It does not take part in V11, does not affect the download path, and requires no machine criterion.** It has exactly one purpose:
so the next person does not have to re-check.

**Why this is not the `provenance` witness chain coming back**: the witness chain required evidence to be anchored to the entry's sha256
and took part in invariant validation; `verified` is a sentence a human can check plus a citation — **the protocol does not read it**.
(Source: `LLVM-wasm` `mail/024` §1 — it traced `NCSA` to line 483 of the official list, and I re-ran and confirmed. This field fixes the shape of that check.)

### 4.8 Immutability is the foundation, not a constraint

Historical releases (the pre-contract format, `schema: 1`) **are not retrofitted** — republishing as schema 3 would mean re-arranging
`products` / `entries` / `variants` wholesale, and **the bytes must not move**.

> "Release immutability is the foundation of this whole thing; 'retrofitting a historical release' is itself a violation of it."
> — `LLVM-wasm` `mail/022` §4

⇒ Their correct destination is **to be kept out of the catalogue by G5**, not to be "fixed".

### 4.9 Why only one invariant

The protocol **is not responsible for verifying that a declaration is true**, only for guaranteeing:
- the declaration exists and its shape is legal (V11)
- **a release with no declaration is not listed** (G7)
- **there is a link to click** (`url` is required) — this is the only checkable means, and a human does the checking, not the protocol

---

## 5. catalogue (the only gate)

### 5.1 G7

| Gate | Criterion | Counter-case |
|---|---|---|
| **G7** | schema 3 and `license` has a non-empty `id` and an `https://` `url` | missing either / `url` not https ⇒ **not listed** (recorded in `excluded` with a reason) |

**"Legal" and "listable" are two different things**: a schema-3 manifest missing `license` is **illegal** (V11 red), so G7 is really a second lock here; the real dividing line is **the migration-period allowance for schema 2** (see §6).

### 5.2 catalogue excerpt

```jsonc
"license": {
  "id":  "GPL-3.0-or-later AND BSD-3-Clause AND LicenseRef-public-domain",
  "url": "https://octave.sourceforge.io/optim/COPYING.html"
}
```

**Exactly those two items from the manifest, copied verbatim.** No derivation, no timestamp added, no nested sha.

### 5.3 `base` and `base_proxy`

Each catalogue entry carries two fetch roots, both with the same shape
(`<host>/<owner>/<repo>/releases/download/<tag>/`, trailing slash included):

| Field | Meaning | Current value |
|---|---|---|
| `base` | The cluster mirror. **The client tries this first.** | `https://static.isui.ren/<owner>/<repo>/releases/download/<tag>/` (EdgeOne rule engine proxying GitHub) |
| `base_proxy` | **The fallback**, used when `base` cannot be reached. Points at the origin itself. | `https://github.com/<owner>/<repo>/releases/download/<tag>/` |

Ruled 2026-11-04: `base_proxy` is the fallback path, not the primary one. Earlier
revisions of this field (and of the whole catalogue) had the two flipped or left it
`null` — the field predates this canon section and was never defined here until now.

Rules the client and the mirror provider can rely on:

1. Both fields have the **same path shape**, differing only in host. The client runs
   the identical algorithm against either root; swapping hosts changes nothing else.
2. **The proxy provider's path layout never enters the contract.** A mirror is free to
   implement `/releases/download/...` behind any internal routing it likes, as long as
   the public path matches the shape above. This is the same criterion that rejected
   encoding platform capacity limits into the contract.
3. `base` failure is **not** a protocol error. Falling back to `base_proxy` is the
   designed behaviour, and mirrors may rate-limit (a mirror with a request quota is a
   valid `base`; the fallback exists precisely because mirrors can be imperfect).
4. The derivation fills both fields as a deterministic function of the release
   (`<owner>/<repo>/<tag>` come from the release itself); neither field is hand-written.

Historical note: the mirror hosts currently are `static.isui.ren` (EdgeOne rule engine
proxying GitHub, byte-passing) and `static.mango-mesa.ccwu.cc` (Cloudflare Worker,
byte-passing with a request quota). The earlier idea of the site mirroring bytes itself
was dropped: the site hosts zero bytes, and the mirrors proxy bytes from the origin.

---

## 6. Migration

| Stage | Action |
|---|---|
| **M0 (now)** | the validator accepts schema 2 and 3; schema 3 must have `license` |
| **M1** | producers reissue the manifest (**not one asset touched**), adding one `license` line |
| **M2** | old schema-2 releases still enter the catalogue, with `license` excerpted as `null` |
| **M3** | close the schema-2 channel via `ACCEPT_SCHEMA = (3,)` (timing is the user's call) |

**Reissuing a manifest does not require re-uploading assets**: v4's asset set is defined by the manifest's `file` fields,
so as long as `bytes`/`sha256`/`file` are verbatim identical, not one asset needs to move.

### 6.1 Migration ground truth (measured, from the `fa-copyright` links in `packages/*.json`)

| release | `license.id` | `license.url` |
|---|---|---|
| 13 × forge | see below | the `url` of the upstream `fa-copyright` link (**all already exist**) |
| `forge-cgi` | `GPL-2.0-or-later` | `https://sourceforge.net/p/octave/cgi/ci/master/tree/COPYING` |
| `forge-datatypes` | `GPL-3.0-or-later` | `https://github.com/pr0m1th3as/datatypes/blob/master/COPYING` |
| `forge-geometry` | `GPL-3.0-or-later AND BSL-1.0` | `https://sourceforge.net/p/octave/geometry/ci/default/tree/COPYING` |
| `forge-matgeom` | `BSD-2-Clause-FreeBSD` | `https://sourceforge.net/p/octave/matgeom/ci/master/tree/LICENSE.txt` |
| `forge-optim` | `GPL-3.0-or-later AND BSD-3-Clause AND LicenseRef-public-domain` | `https://octave.sourceforge.io/optim/COPYING.html` |
| `forge-splines` | `GPL-3.0-or-later AND LicenseRef-public-domain` | `https://sourceforge.net/p/octave/splines/ci/default/tree/COPYING` |
| the other 8 × forge | `GPL-3.0-or-later` | each upstream COPYING link |
| `supply-msl` | `BSD-3-Clause` | MSL upstream |
| `supply-pyodide` | `BSD-3-Clause` | PyPI upstream |
| `LLVM-wasm v0.1.5` | `Apache-2.0 WITH LLVM-exception` | LLVM upstream |

**13/13 real licenses all have a ready `id` + `url`, and all pass V11** (measured 2026-11-01).
Migration is not redoing research; it is transcription.

---

## 7. How to re-run

```bash
# 1. apt copyright coverage (§2.1)
ls -d /usr/share/doc/*/ | wc -l        # ⇒ 3265
ls /usr/share/doc/*/copyright | wc -l  # ⇒ 3237

# 2. migration ground truth (§6.1)
cd /mnt/hdd/zcode-projects/Octave-Extra-Content && python3 -c "
import json,glob
for f in sorted(glob.glob('packages/*.json')):
    d=json.load(open(f))
    print(d['name'], [l['label'] for l in d['upstream']['links'] if 'copyright' in l.get('icon','')])"

# 3. current state: the manifest has no license field
gh release download forge-optim-1.6.3 -R ArchivalEra/Octave-Extra-Content \
  -p manifest.json -D /tmp/lic && python3 -c \
  "import json;print(sorted(json.load(open('/tmp/lic/manifest.json'))))"

# 4. the validator (V11 cases in both directions)
python3 tools/check-release-v4.py --selftest   # ⇒ 42 PASS / 0 fail
```

---

## 8. Implementation and self-proof

| Artifact | Delta | Self-proof |
|---|---|---|
| `tools/check-release-v4.py` | V10 accepts 2\|3; V11 + `parse_spdx` | 42 PASS / 0 FAIL |
| `scripts/sync-catalogue.py` | G5 takes both schemas; G7 | 18 PASS / 0 FAIL |
| `scripts/build-site.py` | the page already declares AGPL; a license column can be added | 13 PASS / 0 FAIL |

All three self-proof tiers are in place (passes when it should / fails when it should / fails on empty input); failure messages name the entry.

---

## 9. Rejected designs (to prevent them being reopened)

| Design | Rejection criterion |
|---|---|
| **DEP-5 style `Files:` glob + first-match-wins** | the client would have to reimplement the matcher + precedence + namespaces; three independent implementations would inevitably diverge. The real data does not support it (8/13 single license) |
| **three-state `status: declared/unstated/refused` + `reason`** | **it turns "not known" into a gate on the download path**: on `unstated` the client would have to refuse to unpack. Violates the rule that someone who wants a package wants one link to download it. And the correct handling of "not known" is **not listing**, not making the client deal with it |
| **`provenance` witness chain (anchor + sha256 + source allowlist + basis)** | the intent was to prove the declaration true; in practice it only proved that there is a file here. The manifest grew by an order of magnitude and the client acquired a false obligation to check. **The contract cannot prove truth; do not pretend it can.** |
| **`amends` license revision anchor** | a falsifiable assertion designed for adding the license without touching bytes. But reissuing a manifest already only swaps manifest.json, assets untouched — `amends` adds proof to something that **already holds** |
| **a full `TermNode` structure tree (8 ops)** | over-design for the real data; the `render` grammar would have to be frozen and maintained, becoming a new drift surface. **And every implementation would have to parse it to understand anything** |
| **one license per entry (no default)** | 45 chunks would write the same fact 45 times; v4 §2.2 already criticised the same class of error |
| **catalogue stores the full license text** | a second place where it lives, and it will inevitably drift |
| **allow releases without a license to be listed** | violates the rule that the bad ones never get listed |
| **require only the SPDX id, not the url** | each project's text differs (`optim`'s COPYING carries additional terms) and is replaced across generations; an id alone replaces the current text with a string that will expire. The user's ruling: point at a link instead |
| **ship the full license text as a mandatory release asset** | 16 copies of the GPL, one per release; and `url` can already point back at the authoritative text. The full text may be an optional `role:"license"` entry, but is not mandatory |

---

## 10. One-sentence close

> **A license is one line of metadata, not a protocol layer.**
> The byte download path does not know it; the manifest displays it; the catalogue uses it to decide whether to list.
> Any design that adds a step to downloading one package is a deviation.
