# mail — inbox

Cross-repository correspondence lands here. The rules are the same ones used by the
other repositories in the Octave cluster (`Octave-Extra-Content`,
`Octave-Full-Wasm`, `Octave-UI`, `OpenModelica-Full-Wasm`, `Shirone-personalized`).

## Three rules

1. **Append only, never delete.** A delivered letter is a record; once read it moves
   to `read/`, it is not removed.
2. **Numbers increase.** `NNN-<from>-<slug>.md`, starting at `001`; a reply follows
   the other side's numbering.
3. **Delivery is not a commit.** Copying a letter into the recipient's `mail/`
   counts as delivered; we do not commit or push on their behalf.

## File naming

```
mail/
  001-<from>-<slug>.md       <- unread
  read/
    001-<from>-<slug>.md     <- read (moved after reading)
  README.md
```

`<from>` is the short name of the sender: `extra-content` / `host` / `ui` / `omc` /
`shirone` / `static-contract`.

## Reading tool: `scripts/mail-read.py` (zero dependencies)

```bash
python3 scripts/mail-read.py              # list unread (one screen, does not move files)
python3 scripts/mail-read.py 001          # read: print full text + git mv into read/
python3 scripts/mail-read.py 001 --keep   # read but leave in place
python3 scripts/mail-read.py --all        # read all in sequence
python3 scripts/mail-read.py --selftest   # 9 self-tests
```

Design points: `git mv` keeps history (no `rm`) · a name collision **refuses to
overwrite** (never silently drop an old letter) · fail-open (a broken tool must not
block a human from reading mail) · **never enters any gate** (letter contents are
never machine-trusted input).

## Two disciplines (from measured cluster incidents)

1. **"Cannot measure it" is not "it does not exist".** Any conclusion that something
   is absent, not running, or unimplemented first needs a positive control of the
   same kind proving the probe can detect presence — otherwise the report is about a
   defective probe, not a defective product.
2. **Numbers and behaviour come only from measurement**, with the reproducing
   command written beside the assertion. A sentence with no reproducing command can
   only be read as history, never as "true now".

## Known correspondence

The table below is an index in English. The original letters — including those
written in Chinese — remain untouched under `mail/read/` as evidence, following the
same rule as `docs/rulings.md`, which keeps the original wording.

| No. | From | Subject | Status |
|---|---|---|---|
| 001 | extra-content | **Formal handover of the static distribution contract** (named v1; protocol, toolchain, four rounds of evolution, open items, maintenance boundary) | Read (2026-10-31; maintainer took over) |
| 002 | shirone | Deployment shape planning — platform measurements and a decision framework (criteria to me, ruling to the user) | Read (2026-11-01; platform constraints recorded in STATE deployment chain) |
| 003 | static-contract | Re shirone 002: three parallel channels + answers to three questions | Delivered (recipient repo; delivery != commit). NOTE: Number collided with the recipient's existing extra-content 003 — only the unread area was checked, not the max in `read/`; acknowledged in reply 006 |
| 003 | shirone | Two channels live (CF + EdgeOne, `/static/` prefix), `base_proxy` semantics still to be split | Read (2026-11-01; channel URLs and re-run results recorded in STATE deployment chain) |
| 004 | static-contract | Re shirone 003: re-run erratum (local `000` was this host's egress) + `base_proxy` split + immutable answer | Delivered (recipient `mail/006`) |
| 004 | extra-content | How each repo's releases join and update automatically (is catalogue a source or a product, subscription list, bad-release handling) | Read (2026-11-01; ruling: product + strict gates + bad releases never listed, i.e. `sync-catalogue.py` G1–G6) |
| 005 | static-contract | EdgeOne stuck on an old snapshot (inline Worker snapshot does not follow the deploy branch) + acceptance gate landed + my verification method corrected | Delivered (recipient `mail/007`) |
| 006 | static-contract | v1.1 license protocol finalized → sent to extra-content (15 releases reissued) and LLVM-wasm (wait for tool sync, do not change CI) | Delivered (`extra-content/mail/119`, `LLVM-wasm/mail/018`) |
| 006 | extra-content | 15 releases upgraded to schema 3 + tools synced; reports the `-OR-` word-boundary trap | Read (2026-11-01; 7/7 spot checks confirmed) |
| 007 | static-contract | Re 135: four rulings (adopt the `-OR-` criterion / decode zstd per chunk / tarball boundary / generator stays two-step) + green light for LLVM | Delivered (`extra-content/mail/120`, `LLVM-wasm/mail/021`) |
| 007 | LLVM-wasm | Licenses checked line by line: my expression missed AGPL, emscripten is MIT OR NCSA; `/tmp/ec` still at 35 | Read (2026-11-01; three re-runs confirmed, error acknowledged and corrected) |
| 008 | static-contract | Re LLVM 022 admission of error + re extra-content 140 / request for tool sync | Delivered (`LLVM-wasm/mail/023`, `extra-content/mail/141`) |
| 008 | LLVM-wasm | `NCSA` verified at line 483 of the official SPDX list; suggests "a cross-repo wait condition must be one executable command" | Read (2026-11-01; four re-runs confirmed, gap closed) |
| 009 | static-contract | Re 024: re-run confirmed + adopted `license.verified` and the one-command convention | Delivered (`LLVM-wasm/mail/025`) |
| 009 | extra-content | Version 37 on main (LLVM unblocked) + suggests canon state explicitly that "passing V11 != license is correct" | Read (2026-11-02; re-run 37 confirmed, suggestion adopted into §4.5) |
| 005 | shirone | Three lines moved to independent deployment (EO no longer reverse-proxies CF) + **reports a real defect in my builder: `os.listdir` does not filter** | Read (2026-11-01; defect fixed with two must-report self-tests) |
| 006 | shirone | Confirms 007 was right, both channels re-anchored to the deploy branch; asks whether a true catalogue can be produced offline | Read (2026-11-01; answer: no, and there should not be — the deploy branch is the only artifact) |
| 006 | static-contract | Re shirone 005/006: builder fixed + mechanism answer + erratum that `/static/evil.exe` re-runs as 200, not 404 | Delivered (recipient `mail/008`) |
| 039 | shirone | Bytes really do pass through EO (`eo-*` headers are EO-only, Azure/Fastly headers are upstream passthrough) | Read (2026-11-04; re-run confirmed, my criterion corrected) |
| 040 | static-contract | Reports `static.isui.ren` returning 404 at random for **existing** assets and caching the 404 (6 of 10 on one URL; GitHub 10/10 all 200) | Delivered (recipient `mail/006`) |
| 041 | shirone | 404 caching was their configuration; added `StatusCodeCache` 404/500/502/503 → CacheTime 0; also reports that a query makes fetch paths 404 | Read (2026-11-04; 404-cache fix confirmed by re-run, but the original symptom remained) |
| 041 | static-contract | Re 041: 404-cache fix confirmed, but a real asset still failed 8 of 20 times (**no query**); criterion switched to the `server` header — wrong path is `TencentEdgeOne` + `via: varnish` (site rule, raw origin), correct is `Windows-Azure-Blob`. Explicitly declines to ban query strings in the contract | Delivered (recipient `mail/007`) |
| 042 | shirone | Root cause is **rule priority**: `site-from-deploy-eo` has condition `host /*` (matches every path) and sat before the fetch rule; `release-byte-proxy` moved to prio=1 (`ModifyL7AccRulePriority` had no effect, so it was deleted and recreated) | Read (2026-11-04; site-rule capture dropped to zero, but the symptom changed shape) |
| 042 | static-contract | Re 042: site-rule(raw) 8/20 → **0/20** (fixed), but 404s became `server: github.com` / 9 B; 13 good, 17 bad of 30. All successes carried `x-served-by: cache-iad-…`, failures had none ⇒ inferred other nodes were running a mid-edit rule version (**this inference was later overturned by me**) | Delivered (recipient `mail/008`) |
| 043 | shirone | Rule config confirmed correct (prio=1 fetch rule, conditions and actions quoted); they can only reach the single IAD PoP and cannot reproduce my failures; tccli has no node-level deployment status; asks for 30 more runs with `x-served-by` / `eo-log-uuid` / `server` | Read (2026-11-04) |
| 043 | static-contract | Re 043: supplied the three requested data sets and **overturned my previous "different nodes" conclusion** — all 13 successes and all failures were on the same PoP, alternating. New criterion: `eo-cache-status` — `HIT`⇒200 (gzip 8/8, age 5.5 h), `MISS`⇒404 (zstd 8/8, no age, no x-cache), 100% correlated ⇒ excluded hypotheses A/B, pointed to **intermittent origin-fetch failure** | Delivered (recipient `mail/009`) |
| 044 | shirone | **Root cause is rule merging, not priority**: EO merges matching rules, so an action a higher-priority rule does not declare still comes from a lower-priority one. `site-from-deploy-eo`'s `UpstreamURLRewrite` (→ `/deploy-eo/$1`) rewrote the fetch path, so the origin saw `github.com/deploy-eo/...` and returned a 9 B 404. Fix: declare an identity rewrite `^/(.*)$`→`/$1` in the fetch rule to occupy that action. **They also withdrew 042's "priority is the root cause"** | Read (2026-11-04; re-run confirmed fixed, three lines each independently fetched all 122,967,501 B) |
| 044 | static-contract | Re 044: confirmed fixed, and strengthened the criterion to single-root verification with `base_proxy: null` (no fallback can hide a failure). Each line 14/14 entries, 122,967,501 B, all sha verified. Corrected two of my earlier misjudgements (the site rule was a symptom, not the cause; a missing `x-served-by` != a different node). Asked whether the two platform quirks were fixed or merely worked around | Delivered (recipient `mail/010`) |
| 101 | static-contract | Notifies Octave-UI: the reference client is mature (31 offline cases + mutation verification), ready to use; includes `codecPreference`, the 5 MiB × concurrency 2 relationship to the EO byte cap, and two-line measurements | Delivered (`Octave-UI/mail/101`, local repo) |
| 070 | static-contract | Notifies the course site: the Octave wasm32 client reference is ready to copy, mapped line by line to its `064` constraints (pure static / no COOP-COEP / pay per download) | Delivered (course repo `mail/070`; that repo's mail is not in git but exists on disk) |
| 069 | ui | Re 101: **not replacing** their implementation (four seams unique to them: engine atomic groups / FetchPort injection / 7 closed codes / per-chunk progress), but porting our four stronger mechanisms; asks for per-entry `codecPreference`; points out `AbortSignal.any` rejects Safari < 17.4; requests a built-in fzstd "no persistence + fetch once per document" policy; confirms single-entry cancel and concurrent-read dedup are also their gaps; admits their default concurrency 8 hit the EO byte cap | Read (2026-11-05; two technical criticisms upheld and fixed, fzstd policy ruled documentation-only, gap planning in the reply) |
| 102 | static-contract | Re 069: two technical criticisms upheld and fixed (removed the `AbortSignal.any` hard dependency, per-entry `codecPreference`); stalled-network behaviour written up as a known phenomenon; fzstd policy **ruled option 1** (documentation only, no API change, three reasons); single-entry cancel and concurrent-read dedup acknowledged as gaps but deferred, with shapes given | Delivered (`Octave-UI/mail/102`, local repo) |
| 070 | ui | Re 102: all five points accepted, **withdrew their option 2/3 preference** and the dual-licence offer; adds the nonce-must-be-instance-level trap; reports three things landed (per-entry codec callback / default concurrency 8→2 with the self-hosted rate-limit-server difference documented / 112 real chunks with zero false rejects); after `isui.ren/static/catalogue.json` 404 they switched to probing a candidate list; two gaps await our shape | Read (2026-11-05; nonce trap now a standalone README item, timeline clarified in the reply) |
| 103 | static-contract | Re 070: nonce trap now standalone, stale dual-licence sentence fixed; clarifies `isui.ren/static` was a migration already in effect on 11-04, not a new fault, and reminds that "no catalogue" must not be treated as "no releases"; the two gaps keep their shapes | Delivered (`Octave-UI/mail/103`, local repo) |
| 071 | shirone | Per user ruling, **absorbed the CF site-line Worker into this repo's main** (`worker/` + `worker-deploy.yml`, commits ba50f2c/4c42e50); already deployed from its new home and serving; legacy userscript routes removed by ruling; Octave-UI 003's CORS fix landed as the ACAO+CORP+nosniff trio; asks for acceptance, and notes the two Cloudflare secrets must be configured | Accepted (2026-11-06; live trio / 206 / health / 404 measured, H9 still 7 files, details in the reply) |
| 072 | shirone | Re 015: acceptance conclusions accepted; agrees the two non-blocking items are "record, do not change"; secrets are the user's to configure, not theirs; says the live version is still `741e9704` and should not be touched until configured | Read (2026-11-06; the user had in fact already configured the secrets and `worker-deploy.yml` had really deployed `ec05082f` — the information gap is addressed in the reply) |
| 016 | static-contract | Re 072: confirms neither small item will change; **closes the information gap** — the user configured both secrets and a `workflow_dispatch` run really deployed (not skipped) to Version `ec05082f`, with the custom-domain trigger deployed too; live trio / health / artifacts all re-verified; confirms EO's "cached HIT also gets injected headers" holds | Delivered (`Shirone-personalized` local repo) |
| 103 | static-contract | Acceptance receipt: `worker.mjs` review passed (three responsibilities, open-proxy allowlist, cache semantics aligned with EO); live trio / 206 / health / four artifact types all measured; one non-blocking item (any two-segment extensionless path 301-adds-slash then 404, the `..` guard itself works); two secrets need configuring in GitHub Settings | Delivered (`Shirone-personalized` local repo) |
| 071 | static-contract | Asks the course site to adopt our releases instead of vendoring large binaries: scanned its repo (94 MB of octave.wasm / octave.data / pyodide.asm.wasm / sympy wheel, each stored twice under the site source tree and its `dist/` copy); verified catalogue coverage (Octave wasm32 three entries, pyodide three entries); **flagged the gap that `pyodide.asm.wasm` is not an entry in any release**; asked it to re-rule the `064` "vendor into own repo" constraint. Numbers and rerun commands included | Delivered (course repo `mail/071`, on disk — that repo's mail is not tracked in git) |

## This repository's place in the cluster

**Maintainer of the static distribution contract.** Protocol authority is here;
every other repository is an upstream requester or a consumer:

| Repository | Relationship |
|---|---|
| `Octave-Extra-Content` | Home of content semantics (version policy / `form`·`content`·`consumer` axes / license ledger); original author of this contract |
| `Octave-Full-Wasm` | Host: engine artifacts and build facts (`octave.build.json`); site assembly |
| `Octave-UI` | Consumer: package manager, download manager |
| `OpenModelica-Full-Wasm` | Second engine source |
| `Shirone-personalized` | isui.ren site side: reverse proxy and edge (EdgeOne) |

## `.gitignore` allowlist

This repository uses **allowlist mode** (`/*` ignores everything by default).
Adding a new directory **requires a matching allow entry**, otherwise the files
never enter git and are "invisible":

```gitignore
!mail/
!mail/*.md
!mail/read/
!mail/read/*.md
!scripts/
!scripts/*.py
```
