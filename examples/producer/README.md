# Producer-side release template (contract v4 / v1.1)

This directory is a **template for release producers**, not a runnable workflow.
It is the producer's half of the contract; the consumer's half is
`../fetch-concurrent.ts`.

The source is `LLVM-wasm/.github/workflows/release.yml` (354 lines, the first real
schema 3 release). That file contains a lot of LLVM-specific material — a
14-entry `release/payloads.json`, recovery of payloads from a previous release,
a per-entry `licenses.json`, 105 chunks uploaded in three codec batches. Copying
it verbatim would teach a downstream producer the wrong lesson, so what follows
is the **contract-relevant skeleton** with product-specific parts marked as
placeholders.

## The one rule

> A release = one immutable tag = one `manifest.json` + N flat assets.
> **The release's contents must be exactly the manifest's contents.**

One extra asset breaks it — even a "useful" whole-bundle tarball. The tarball's
bytes are already fully expressed by the identity chunks
(`sum(identity.chunks.bytes) == entry.bytes`), so shipping it is both redundant
and destroys the decidability of "what this release contains".

## Required gates, in order

These are the steps that enforce the contract; their order is not arbitrary.

1. **Generate the manifest and chunks.** Use the canonical generator
   (`Static-Contract/tools/make-manifest-v4.py`). It emits schema 2; that is
   expected, see step 4.
2. **Release contents == manifest contents (no extras, no missing).** Run this
   *before* any upload. Declare the set as
   `{c.file for e in entries for v in e.variants for c in v.chunks} | {"manifest.json"}`
   and compare it to the on-disk file set in both directions.
3. **Contract checker under schema 2.** Run
   `Static-Contract/tools/check-release-v4.py <manifest> --base <dir>` (V1–V10,
   includes per-chunk bytes+sha verification against disk).
4. **Upgrade to schema 3 (v1.1 license).** Use
   `tools/upgrade-manifest-license.py` from the tool repo, feeding it a
   data file of per-entry `{id, url}` — never an inline heredoc, because
   licences differ per entry within one release. Two hard requirements:
   - assert `check_invariants(old, new)` — the upgrade must not change byte
     identity, otherwise "no assets need re-uploading" is a lie;
   - unmapped entries must **not** be silently filled (falling back to the
     top-level licence is honest; a wrong per-entry licence is worse than none).
   - Order: after step 2, before `gh release create`. Licences add no assets, so
     the contents gate is unaffected — but the checker must be re-run under the
     new schema.
5. **Contract checker again, under schema 3.** This is not a duplicate of step 3:
   step 3 validated V1–V10 on schema 2, this one validates V11 too. Assert
   `schema == 3`, top-level `license.id` present, and every entry has its own
   `license.id`.
6. **Verify the identity path.** Reassemble each entry from its identity chunks
   and check `entry.sha256`. Do not upload that reconstruction.
7. **Publish only manifest-declared assets.** Upload the manifest, then the
   chunks grouped by codec. Large releases need batched uploads; a half-finished
   release is worse than no release, so any upload failure must fail the job.
8. **Read the release back.** Download the *serving* bytes from GitHub and repeat
   the contents comparison, the schema 3 / per-entry licence assertions, and the
   contract checker. Check `isDraft` too — a draft is invisible to clients, and
   a failed read-back is not a passed read-back.

## Canonical tool locations

| Tool | Canonical home | Note |
|---|---|---|
| `make-manifest-v4.py` | `Static-Contract/tools/` | schema 2 generator |
| `check-release-v4.py` | `Static-Contract/tools/` | V1–V11 checker, 37 self-tests |
| `upgrade-manifest-license.py` | tool repo (`Octave-Extra-Content/tools/`) | schema 2→3, 25 self-tests; **current, do not delete** |

The LLVM workflow currently clones `Octave-Extra-Content` to `/tmp/ec` and calls
`/tmp/ec/tools/check-release-v4.py`, while its own header says the sole
authority is `Static-Contract/specs/…v4.md`. The two copies are byte-identical
today (sha `ed877ee2…`), so nothing is being mis-judged — but a producer should
fetch its checker from the same repository that owns the canon. A template that
hardcodes `/tmp/ec` invites a future split where the declared authority and the
tool actually disagree.

We have asked `Octave-Extra-Content` (mail `155`) to retire its v1/v2/v3-era
tools: `check-release-contract.py` (`.gz` sidecar / `Accept-Ranges` /
`immutable` HTTP probes), `check-release-v2.py` (single-asset `assets{}` shape),
and `make-release-manifest.py` (v3 pilot generator). Those implement judgements
the current contract no longer makes; a runnable script in a `tools/` directory
gets copied, whereas `Static-Contract/specs/` keeps the same history as
documents explicitly marked deprecated.

## Placeholders a producer must fill

- `release/payloads.json` — the authoritative list of `name/bytes/sha256`
  for the payloads. LLVM's version has 14 entries; yours will differ.
- `release/licenses.json` — top-level `expr` + `url`, plus `by_name` keyed by
  **exact `entry.name`** (no product prefix; `driver/abi.mjs` is flattened to
  `driver__abi.mjs`). Get these right by reading the actual licence files, not
  by guessing one expression for the whole release.
- Chunk upload batching — sized to your release; the contract fixes the shape,
  not the batching.
- Payload recovery from a previous release — only needed if your build artefacts
  are not in git. LLVM's `clang.wasm` takes hours to build, so it reassembles
  from the previous release's identity chunks. If your payloads are in git, skip
  that whole step.

## What this is not

- **Not a consumer client.** Consumers never see chunks; see
  `../fetch-concurrent.ts`.
- **Not a validator.** The contract checker is canonical in
  `Static-Contract/tools/`, not duplicated here.
- **Not runnable CI.** There is no `on:` trigger, no secrets, no repository
  paths. It is a checklist with the reasoning attached, so a producer can build
  their own workflow without re-learning why each gate exists.
