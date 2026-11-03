# Absorption audit for release contract v3 (content contract / engine contract)

> ## DEPRECATED — historical, not authoritative (marked 2026-11-02)
>
> Superseded. Current authority: v4 (V1–V10) plus v1.1 (V11, schema 3).
> Kept for rejection criteria only.
>
> This document was **never delivered, never entered any schema, never promoted**. It has been superseded.
> The authority paths are `specs/2026-10-30-release-contract-v4.md` (V1–V10 base clauses)
> and `specs/2026-11-01-release-contract-v1.1-license.md` (V11 license, schema 3).
> The only reason to keep this document is as **the criteria of a rejected design** (to prevent reopening it later) — do not implement against it.

> **Purpose**: answer one question — **can release contract v3 actually absorb the existing content contract and engine contract?**
> **Method**: take **every real field** of both contracts (not summaries) and judge ownership field by field.
> **Conclusion up front**: **partial absorption; whole-contract absorption is not possible.** The dividing line and the reasons for the non-absorbable items follow.
>
> **This file is the remedy for a hasty mailing**: in `119`/`120` I had OM build a release per v3
> without first proving that the mapping between v3 and the existing contracts holds. This fills that gap.

---

## 0. One-sentence conclusion

| Contract | Can v3 absorb it | Verdict |
|---|---|---|
| **Content contract** (`content-list`, entry with 23 fields) | **Partially** — only the 5 fields of "byte identity" can be taken over by v3; the remaining 18 belong to the **semantic domain**, which v3 should not and cannot take over | Layered coexistence |
| **Engine contract** (`octave.build.json`, 9 top-level keys) | **No** — it records the **build process** (declared/measured/verdict/mismatches), while v3 cares only about the **released artifacts** | Fully orthogonal |

**⇒ v3's positioning must narrow to "the identity and acquisition method of byte objects within one release"; it is neither a replacement for the content contract nor a replacement for the engine contract.**

---

## 1. Content contract: field-by-field judgment over all 23 entry fields

Taken from the host producer's `build/extra-content/content-list.schema.json`, `$defs.entry`
(`required = [name, version, sha256, url]`).

### 1.1 Can be taken over by v3 (5) — byte identity domain

| Field | What it becomes in v3 | Note |
|---|---|---|
| `sha256` | `manifest.assets[].sha256` (raw bytes) | Same semantics: the sole fail-closed basis |
| `url` | **`chunks[].file` (bare asset name) + distributor base URL** | v3 splits "one url" into "N bare filenames + one base" |
| `size` | `manifest.assets[].bytes` | Same semantics, but v3 makes it **required** (optional in the original contract, used only for progress bars) |
| `files` (download closure map, exclusive to `form:"tree"`) | `{file,bytes,sha256}` entries of `manifest.variants[].chunks[]` | **Semantics map directly**: both mean "the files a consumer will download → per-file bytes+sha" |
| `upstream_url` | `manifest.assets[].upstreamUrl` (optional, bookkeeping) | Same semantics: provenance, not involved at runtime |

**Criterion**: deleting these 5 fields would leave v3 missing information ⇒ v3 must take them over.

### 1.2 Should not be taken over by v3 (15) — semantic domain, stays in the content contract

| Field | Why v3 should not govern it |
|---|---|
| `name` | The package's **identity/key** (`deps` refer to it). v3's asset name is a **filename**, not a package name |
| `version` | **Version semantics** (`versions[]` three invariants). v3's tag is a release batch, not the package version |
| `form` | Delivery form (pkg/tree/file/oct/octdir/js) — a **content composition axis**, unrelated to byte identity |
| `content` / `kinds` | Which source kinds the package contains (m/src/oct) — pure semantics |
| `arch` | Target architecture (dlopen compatibility) — semantics, not a byte fact |
| `deps` | **Dependency edges** (package→package / package→capability layer) — v3 has no way to know them |
| `requires` | Platform/version constraint string — semantics |
| `license` | License ledger — semantics (v3 may carry a copy for bookkeeping, but **authority lies with the content contract**) |
| `note` | Human-readable remark — semantics |
| `description` | Package-level description (UI card first screen) — semantics |
| `links` | Documentation links — semantics |
| `consumer` | Consumption surface (octave/omc lane axis) — **engine lane semantics**, irrelevant to v3 |
| `kind` | Entry nature (`src` / `pre` / `engine`) — semantic |
| `role` | Consumption role (package/toolchain/language-bridge) — semantics |
| `versions[]` | Version candidate set (three invariants) — semantics |

**Criterion (deletion test, reversed)**: stuffing these 15 into v3 would turn v3's manifest into **a second content contract**
⇒ drift in two places (we have already litigated a `sha256` drift in two places; see `versions[]` invariant 2).

### 1.3 Needs adjudication (3)

| Field | Question | My inclination |
|---|---|---|
| `artifacts` | The per-architecture release unit for prebuilt `.oct` files. **It is itself "a release artifact"**, overlapping v3's release concept | **Inclination**: each `artifacts` entry **points at a release** (`releaseRef`) instead of being absorbed by v3. That is, the content contract records "which artifacts exist", and v3 records "the byte identity inside that release" |
| `optional_keys` | Negotiation mechanism (consumers declare which keys they can ignore) | **Inclination**: keep it in the content contract. v3's `variants` forward compatibility relies on "skip unknown codec", which is **a different mechanism**, and does not need `optional_keys` |
| `producer` | Producer identity (id + pin) | **Inclination**: v3 already has `id` (`<repo>/<tag>`) plus optional `producer.commit`, so there is **partial overlap**. Whether to unify them needs adjudication |

---

## 2. Engine contract: 9 top-level keys, **cannot be absorbed by v3 at all**

`octave.build.json` (host `site/octave.build.json`), measured fields:

```
schema / tool / build / declared / measured / inputs / notes / verdict / mismatches / checked
```

| Key | What it records | Relationship to v3 |
|---|---|---|
| `schema` | The version of this contract itself | Irrelevant |
| `tool` | Which tools were used to build (emsdk/clang versions) | **Build process fact**, not v3's concern |
| `build` | Build parameters (flags/configuration) | Same as above |
| `declared` | **Declared** artifacts (written by humans) | Same as above |
| `measured` | **Measured** artifacts (measured by tools) | Same as above |
| `inputs` | Inputs (source commit / dependencies) | Same as above |
| `notes` | Remarks | Same as above |
| **`verdict`** | **Reconciliation conclusion** (ok/mismatch) | Same as above |
| **`mismatches`** | Which specific items do not match | Same as above |
| `checked` | Check timestamp/metadata | Same as above |

**⇒ Everything in the engine contract is "how was this byte made, and was it made correctly", while everything in v3 is "after release, what identity does this byte have and how is it fetched". The two have zero overlap.**

**The only point of contact**: the per-file `sha256` inside the engine contract's `measured.files` **is** the **origin** of v3's `manifest.assets[].sha256`.
So the correct relationship is:

```
Engine contract (build facts + per-file measured sha)
        ↓ origin (provider, no copying)
Release contract v3 (manifest: post-release byte identity and chunk acquisition)
        ↓ consumption
Distributor (Shirone static site) / consumer (UI/host)
```

**v3 must not compute sha itself and treat it as authoritative** — this is the same discipline as "the sole origin of per-file sha = the producer's ledger; the distributor only checks and never recomputes"
(binding rule 3 of the five `files[]` bindings).

---

## 3. Conclusion: the correct position of v3

```
┌───────────────────────────────────────────────────────────────┐
│ Content contract (content-list)                               │
│   version semantics / form / content / consumer / deps        │
│   / license / description / versions[]                        │
│   - answers "what exists, can it be used, and by whom"        │
└───────────────────────────────┬───────────────────────────────┘
                                │ reference (acquisition.releaseRef, not yet added)
                                ↓
┌───────────────────────────────┴───────────────────────────────┐
│ Release contract v3 (manifest)                                │
│   within one release: byte identity + chunks + fallback chain │
│   - answers "where to fetch this byte, in how many chunks,    │
│     and how to verify it"                                     │
└───────────────────────────────┬───────────────────────────────┘
                                │ origin (supplies measured.files sha, not copied)
                                ↑
┌───────────────────────────────┴───────────────────────────────┐
│ Engine contract (octave.build.json)                           │
│   tool / build / declared / measured / verdict                │
│   - answers "how was this byte produced, is it correct"       │
└───────────────────────────────────────────────────────────────┘
```

**Three layers each answer one question; v3 sits in the middle and touches only byte identity.**

---

## 4. Impact on already-sent letters (the part that must be corrected)

When I said "contract v3" in `119` (to OM) and `120` (to Shirone), **I did not make clear that it does not replace the content contract**.
This is not a fatal error (OM's pilot genuinely needs only the v3 portion), but **the wording would let them mistakenly believe v3 is an upgraded version of the content contract**.

**Corrections to be issued**:
1. **To OM**: the pilot release produces only the v3 manifest; **do not touch** your existing `content-list.json`
   — the two coexist, and after the pilot succeeds I will issue `acquisition.releaseRef` to connect them (rollout order, step 6);
2. **To Shirone**: the static site serves only the v3 manifest and chunks, and **it does not parse content-list**
   — content semantics live on the other side; do not mix them;
3. **To UI/host**: future consumption is "first read content-list to choose a package → then look at that package's releaseRef → read
   the v3 manifest to fetch bytes", **two hops**, not one.

---

## 5. Three questions that must be adjudicated (I will not decide them unilaterally)

| # | Question | My inclination | Criterion |
|---|---|---|---|
| **U-A** | The relationship between `artifacts` (prebuilt files) and v3 releases | The content contract records "which artifact releaseRefs exist"; v3 records bytes | Both are release units, but one is a **semantic choice** and the other is **byte identity** |
| **U-B** | Whether `producer` is unified (content contract's `{id,pin}` vs v3's `id` + `producer.commit`) | Unify to the v3 shape `{repo, commit}`; the content contract's `pin` semantics (submodule/release) stay in the content contract | Avoid writing the same thing in two places |
| **U-C** | **Can one release carry multiple assets?** | **Yes** (v3 currently implements only single-asset; `assets` should become a map rather than a single object) | Reality: OM's `v0.1.0-wasm32` already has **2** assets (wasm + MSL zip); v3 today can describe only one |

**U-C is a real gap**: my generator handles only "a single primary asset", while OM's release contains several.
**If the pilot does only the wasm artifact, that is acceptable** (the 19.5MB MSL zip could be chunked too, but that is not part of the first step).
**But the contract itself should support multiple assets** — this must be settled before OM starts, otherwise it will produce a manifest covering only one artifact.

---

## 6. Honest boundaries

- This audit is based on the **schemas / real artifacts of the two contracts** (reading JSON, not reading documents); field names and counts are re-runnable;
- I have **not** verified "whether the content contract's consumer (the UI package manager) can accept a two-hop read" — that is the UI's business,
  and it belongs to rollout order steps 5 and 6;
- I have **not** verified "whether the per-file sha in the engine contract's `measured.files` is naturally consistent with v3's `chunks`"
  — that would require comparing a real `octave.build.json` against a v3 manifest, which has not been done yet.

## 7. How to rerun

```bash
# All entry fields of the content contract (23)
python3 -c "
import json
s=json.load(open('/mnt/hdd/zcode-projects/Octave-Full-Wasm/build/extra-content/content-list.schema.json'))
e=s['\$defs']['entry']
print('required:', e.get('required'))
for k in e['properties']: print(' ', k)"

# All top-level keys of the engine contract (9)
python3 -c "
import json
d=json.load(open('/mnt/hdd/zcode-projects/Octave-Full-Wasm/site/octave.build.json'))
print(list(d.keys()))"
```
