# Rulings

User decisions that shaped this contract, with the original wording preserved.
**The Chinese text is the authoritative record; the English is a working gloss.**
Where the two disagree the Chinese wins — and it is quoted verbatim, typos included.

**This file is evidence, not specification.** The specification lives in `../specs/`.
A ruling answers *why a rule exists* and *what it cost*; it never overrides the canon
by itself. If a ruling and the canon disagree, that is a defect to be fixed, not a
licence to reinterpret. The canon is the only thing an implementer may follow.

How to read an entry:

- **Ruled** — the date the user said it. A decision restated later is folded into one
  entry with every date listed.
- **Original** — the user's words, verbatim, inside 「」. Do not edit these, not even
  to fix a typo: the typo is part of the evidence. Where an entry quotes a contiguous
  span of a longer message, the entry says so.
- **Gloss** — an English paraphrase for readers who do not read Chinese. It is a
  working translation, not authority.
- **Consequences** — the code and structure decisions that follow. These are the
  verifiable half of the ruling: each one names a file, a gate or a measured number.

Provenance of the quotes: the original session transcripts (the `/tmp/STATE.zh.bak`
snapshot, `specs/2026-11-01-release-contract-v1.1-license.md`, and `mail/read/` all
carry paraphrases). Where a paraphrase differed from what the user actually typed,
the transcript was used and the paraphrase discarded.

---

## R-001 — Role: contract maintainer, zero-byte hosting

**Ruled:** 2026-11-01

**Original:** 「记住最最核心的，你只是契约维护者，所有的包，要么去github拿，要么走反代，你需要出一个不收录任何release件的站」
(contiguous opening span of a longer message; the closing span is R-002.)

**Gloss:** Remember the single most important thing: you are only the contract
maintainer. Every package is either fetched from GitHub or fetched through a reverse
proxy. You need to produce a site that hosts zero release artifacts.

**Consequences:**
- `scripts/build-site.py` runs `gate_dist()` on every build: any output filename
  matching the asset shape `<payload>.<codec>.<NNN>`, or any path containing a
  `releases/` segment, aborts the build and discards the whole dist — never a partial
  publish.
- The published artifact is metadata only: `index.html`, `catalogue.json`,
  `sources.json`, `files.json`, `contract/*.md`, `tools/*.py`, `README.md`,
  `STATE.md`, `maintaince.md`, `LICENSE`.
- `site/catalogue.json` is a fallback file whose `releases` array must stay empty;
  every real entry comes from `scripts/sync-catalogue.py`
  (`zreflect/check_catalogue.py` fails if the fallback holds a hand-written entry).
- A catalogue entry carries `id`, `base`, `manifest_sha256`, `license`,
  `verified_at` — never bytes, never a copy of an artifact.
- The contract never names a hosting location of its own: bytes come from a release
  direct link or a reverse proxy, both outside this repository.

---

## R-002 — `deploy` branch updates itself from `main`

**Ruled:** 2026-11-01

**Original:** 「需要出一个deploy分支用于部署，而deploy分支应当是自动更新的，main修改完deploy就会更新」
(contiguous closing span of the same message quoted in R-001.)

**Gloss:** You need a `deploy` branch for deployment, and that branch should update
automatically — once `main` is modified, `deploy` updates.

**Consequences:**
- `.github/workflows/sync-deploy.yml` builds once per push to `main` and force-pushes
  an orphan single-commit `deploy` branch (`git init -b deploy`, one commit, no
  history growth).
- The same `site/dist` is deployed to GitHub Pages by `actions/deploy-pages` in the
  same run — one build, one artifact, two delivery legs.
- `deploy` is the only artifact and the correct entry point for consumers. Running
  `build-site.py` standalone produces the empty fallback by design, not by defect.

---

## R-003 — One artifact, three channels in parallel

**Ruled:** 2026-11-01

**Original:** 「看信，我认为可以搞成pages+cf page+edgeone三条并行且只需要出一份产物就能三地部署」

**Gloss:** Read the letter. I think this can be set up as three parallel channels —
GitHub Pages, Cloudflare Pages, EdgeOne — with a single artifact deployed to all
three places.

**Consequences:**
- `site/channels.json` lists three channels, each with a `base`; the page's channel
  table is rendered from that file, never hand-written.
- `scripts/verify-channels.py` checks every channel against the fingerprint
  `STATIC-CONTRACT-BUILD <hash>` written into `index.html` and against the derived
  catalogue's `verified_at`.
- The acceptance criterion is anchored to the artifact itself, not to agreement
  between channels — all three sitting on an old build is still "consistent".

---

## R-004 — The three channels must be independent deployments

**Ruled:** 2026-11-01 (stated twice, same day)

**Original:** 「额，出大问题，你的CI不诚实，gh pages已经美美16条上架了，eo居然是反代的cf，无论如何他们都没有吃到最新deploy产物」
and 「额你再看看eo和cf都好的不，隔壁说是eo反代cf?这是不被允许的，这三条线是独立部署」
(second quote is from the Shirone-personalized session.)

**Gloss:** The CI is not honest: Pages has sixteen releases listed, but EdgeOne turns
out to be reverse-proxying Cloudflare, and either way they never consumed the latest
`deploy` artifact. If EdgeOne is reverse-proxying Cloudflare, that is not allowed —
these three lines are independent deployments.

**Consequences:**
- Cloudflare serves from the raw `deploy` branch at runtime; EdgeOne has its own
  static tree that CI builds from `deploy`. Neither proxies the other, so EdgeOne's
  availability is not Cloudflare's availability.
- `site/channels.json` carries `owned` per channel; only `github-pages` is owned here.
- The H6 dead-link gate and `verify-channels.py` split failures by `owned`: an
  external channel failing warns and does not block a release, but it is never silent.
- `sync-deploy` dispatches Shirone's EdgeOne workflow explicitly, because pushing
  `deploy` does not trigger it; with no `HEART_DISPATCH_TOKEN` the step states that it
  skipped rather than passing quietly.

---

## R-005 — Bad releases are never listed; the client does zero error handling

**Ruled:** 2026-11-01

**Original:** 「好吧，最后做一下catalogue的严格校验，不允许有坏的流到客户端，足够了，根本不需要客户端错误排查的事情，只要坏的从未上架过」

**Gloss:** Do strict validation on the catalogue. Nothing bad may flow to the client —
that is enough. Client-side error investigation is unnecessary; the only requirement
is that a bad release was never listed in the first place.

**Consequences:**
- The catalogue is derived by `scripts/sync-catalogue.py`: never hand-edited, entries
  not committed to git; `site/sources.json` records only which repositories are
  subscribed, one line per repo.
- Gates G1–G7 decide admission: manifest present with a platform digest; manifest
  content sha equals that digest; V1–V10 pass on the manifest; every chunk's sha256
  equals that asset's platform digest (zero-download byte proof); the schema is 2 or 3;
  no orphan assets; a complete `{id, url}` license on schema 3.
- A single failing release is excluded with its `reason` and still published — the
  exclusion list is the audit trail. A whole source failing to fetch turns the step
  red, aborts deployment, and leaves all channels on the last good result. An empty
  catalogue is never published.
- The client keeps no recovery branch: the v4 client algorithm is a plain GET
  sequence, with no "what if the manifest is bad" path.

---

## R-006 — Strict refusal: the producer re-releases

**Ruled:** 2026-11-01 (two statements, same day)

**Original:** 「严格拒绝，我叫LLVM重新发了」
and 「好，给LLVM发信叫他改CI，Content仓也是那些release全撤掉然后重发」

**Gloss:** Refuse them strictly — I have told LLVM to re-release. Send LLVM a letter
telling it to change its CI; for the Content repository, withdraw all those releases
and re-release them.

**Consequences:**
- LLVM `v0.1.0`–`v0.1.4` stay excluded by G5 (schema 1, a pre-contract format);
  `v0.1.5` stays excluded by G6 (orphan asset `llvm-wasm-bundle-v0.1.5.tar.gz`).
- The `excluded` array in the catalogue is the public record of that refusal — the
  releases did not disappear, they are recorded as refused.
- Migration to `schema: 3` required republishing `manifest.json` with assets untouched;
  a release whose bytes did not change must not be re-uploaded.
- The same instruction reached `Octave-Extra-Content`: withdraw and re-release its
  fifteen releases. They came back at schema 3, and all fifteen were re-verified
  individually — schema 3, valid license, V1–V11 green, compound expressions preserved
  verbatim.

---

## R-007 — The site itself declares AGPL-3.0

**Ruled:** 2026-11-01

**Original:** 「好吧，先只是标记网站为AGPL」
(contiguous span, followed in the same message by R-009.)

**Gloss:** All right — first, just mark the site as AGPL.

**Consequences:**
- The page footer states `License: AGPL-3.0` with a link to the full text, and
  `LICENSE` ships inside the published artifact.
- `scripts/build-site.py` self-test 13 asserts the page declares AGPL-3.0 and that
  `href="LICENSE"` is present; the build fails if either disappears.
- The repository's own license covers documents, tools and site only. Listed releases
  are outside it — each release's license belongs to its publisher.

---

## R-008 — Every resource component declares its own license

**Ruled:** 2026-11-01

**Original:** 「我认为各个资源组件都需要明确标注各自的license」
(stated first as 「各个组件都需要明确标注各自的license」 minutes earlier; the corrected
wording adds 资源.)

**Gloss:** Every resource component must explicitly declare its own license.

**Consequences:**
- A release-level `license` plus optional per-entry override — not a repository-level
  license. Measured reason: the `LLVM-wasm` repo is AGPL-3.0 while `clang.wasm` is
  `Apache-2.0 WITH LLVM-exception`.
- The client rule is a single line: `entry.license ?? manifest.license`. No glob, no
  priority table, no namespace ambiguity.
- `per-entry license with no default` was rejected: 45 chunks would repeat the same
  fact 45 times.

---

## R-009 — Study apt's copyright mechanism, then design v1.1

**Ruled:** 2026-11-01

**Original:** 「然后你作为契约现任维护方，去翻找apt官方的copywright附带方式，然后设计协议，v1.1要来了」
(contiguous span of the same message as R-007.)

**Gloss:** Then, as the contract's current maintainer, go look up how apt ships its
`copyright` files, and design the protocol from that. v1.1 is coming.

**Consequences:**
- `specs/2026-11-01-release-contract-v1.1-license.md` section 2 records the real
  measurements taken from this machine: 3265 installed packages, 3237 with a
  `copyright` file (99.1%), and the DEP-5 field layout.
- apt's `Files:` glob with first-match-wins was adopted as a problem, not a solution:
  three independent designs rejected it because the client would have to reimplement
  a matcher, a priority order and a namespace.
- apt's honest `best effort ... not a complete representation` stance was adopted
  wholesale: the protocol requires truthful annotation of what is known and unknown,
  not completeness.

---

## R-010 — Design it twice, in four independent directions

**Ruled:** 2026-11-01

**Original:** 「先派子代理分别走不同方向design it twice」
(contiguous span; the message opens with a skill link before this text.)

**Gloss:** First dispatch subagents to run design-it-twice, each in a different
direction.

**Consequences:**
- Four independent designs were produced and compared before a shape was chosen.
- The rejected designs and their criteria are recorded in the v1.1 spec section 9 so
  they cannot be reopened without new evidence: DEP-5 glob, tri-state status,
  provenance witness chain, `amends` revision anchor, a full TermNode tree,
  per-entry-without-default, storing license text in the catalogue, allowing
  unlicensed releases, SPDX-id-only, and mandatory full-text assets.

---

## R-011 — Finalize, simulate once, review for holes

**Ruled:** 2026-11-01

**Original:** 「定稿，这很棒，定完走一次模拟，用code review查漏洞」

**Gloss:** Finalize it — this is good. Once finalized, run one simulation and use code
review to look for holes.

**Consequences:**
- v1.1 was marked final with `schema: 3`, implemented as V11 in
  `tools/check-release-v4.py` and G7 in `scripts/sync-catalogue.py`.
- A two-axis code review followed and found six real bugs, all fixed: a sort still
  reading a deleted field, a `reason` overwritten on every path, a gate call deleted
  so the gate went falsely green, double-escaped `&mdash;`, a gate silently skipping
  when the catalogue was absent, and a fallback note left in Chinese.
- A self-test is the price of landing anything: "the checker's self-test passing is
  what counts as landed".

---

## R-012 — HTTP simplicity: one link to download a package

**Ruled:** 2026-11-01

**Original:** 「但是我觉得好像偏离了http啊，人家只想下个包一条链接」

**Gloss:** But I think this has drifted away from HTTP — people just want one link to
download a package.

**Consequences:**
- The tri-state `status: declared | unstated | refused` design was rejected: it turns
  "we do not know" into a gate on the download path, and makes the client refuse to
  unpack. The correct handling of "unknown" is not to list the release, not to make
  every consumer handle it.
- `provenance` witness chains, `amends` revision anchors and a full expression tree
  were rejected for the same reason: each adds a step between a user and a file.
- The client algorithm has no license branch between "pick a variant" and "verify
  bytes". The license affects display only.

---

## R-013 — A license is a name plus a link to its full text

**Ruled:** 2026-11-01

**Original:** 「不不不，各家license文章不一样，我觉得改成指向链接，强制要求release填写每个产物的license在那个仓库的链接，毕竟有过几代换许可证的场景」

**Gloss:** No, no. Each project's license text is different. Change it to a pointing
link: require each release to fill in the link to that license in that repository,
because there have been cases of the license changing between generations.

**Consequences:**
- `license` is `{id, url}`; both required; `url` must be `https://`. A bare SPDX id
  was rejected because the string expires the moment upstream swaps the license.
- V11 in the checker validates shape only — never the SPDX vocabulary, never the
  network. G7 in the deriver refuses any schema-3 release missing either field.
- The catalogue copies `{id, url}` verbatim from the manifest: no derivation, no
  timestamp nested inside, no second source of truth.
- `license.verified` is an optional human trace of *why* an id is right; V11 does not
  read it, and it is never a gate.

---

## R-014 — Mirror he.net; stop designing from scratch

**Ruled:** 2026-11-01 (two statements, minutes apart)

**Original:** 「来修下页面吧，现在这网页太搞笑，信息量没有，还有README坏链，我认为你需要去参考he.net，纯html才对得起我们这么实用的静态站」
and 「你需要先扒一下HE.net下来，别再自己设计，求你了」

**Gloss:** Fix the page — right now it is ridiculous, there is no information in it,
and the README has a broken link. You should reference he.net; plain HTML is what
this practical static site deserves. First actually pull HE.net down and study it —
stop designing it yourself, please.

**Consequences:**
- `index.html` is XHTML 1.1 with inline CSS, zero JavaScript and zero external
  resources, structured like he.net (header, sidebar of blocks, content area).
- The README broken link was fixed in the same batch.
- The page still carries no client-side behaviour: every interaction is a link.

---

## R-015 — Maximise automation of site data

**Ruled:** 2026-11-02

**Original:** 「那我觉得你先小小改一下站点，加入copyright以及最大程度自动化数据读取」

**Gloss:** I think you should first make a small change to the site: add a copyright
line and automate data reading as far as possible.

**Consequences:**
- Self-test counts on the page are measured by running `--selftest` at build time,
  never typed. This immediately exposed a real drift: a hand-written "checker 26 PASS"
  that had been 37 for a while.
- The channel table comes from `site/channels.json`; inclusion and exclusion counts
  come from the derived catalogue.
- The footer carries `© 2026 ArchivalEra`.

---

## R-016 — HTML must not contain Chinese, and that needs a gate

**Ruled:** 2026-11-02

**Original:** 「不不不，加闸门，html页面不准出现中文」

**Gloss:** No — add a gate. An HTML page is not allowed to contain Chinese.

**Consequences:**
- `zreflect/check_site_lang.py` H1 rejects any CJK character in the built
  `index.html`; H4 rejects CJK in the catalogue's public fields and requires every
  excluded entry to carry an English `reason`.
- The first version of the gate checked only `index.html` and missed the live site,
  which had 40 CJK characters from Chinese diagnostic strings rendered into the
  excluded table. CI now writes `site/catalogue.live.json` and runs the gate against
  real derived data before building.
- Contract `.md` bodies may stay Chinese: that is content, not the shopfront.

---

## R-017 — Old contracts are marked deprecated

**Ruled:** 2026-11-02

**Original:** 「之前那些contract都标成decaprecated」
(the typo is in the original.)

**Gloss:** Mark those earlier contracts as deprecated.

**Consequences:**
- `v0`, `v1`, `v2`, `v3` and `v3-absorption-audit` carry a `DEPRECATED` banner.
- `v4` carries `SUPERSEDED IN PART`, not `DEPRECATED`: V1–V10 are still in force and
  only its `schema: 2` clause is superseded. A blanket label would mislead readers.
- H3 requires a banner on every non-authority document in `specs/`; H2 requires the
  page to mark every *fully* deprecated document. H2 deliberately does not require the
  mark for partly superseded documents — demanding it there would itself be wrong.

---

## R-018 — English page and catalogue; protocol untouched; licences derived; proxy column gone

**Ruled:** 2026-11-02

**Original:** 「和code review交替进行，目标是整个页面以及用户实际拉下来的catalogue里仅英语。协议不准动，这是页面改动，三个站都有些坏链接，然后每个release都要标许可证，应该全自动派生而不是手动指定，proxy那栏去掉，整个页面继续保持这种风格但是字数大幅减少」
(contiguous span of a `/goal` message that opens with a skill link.)

**Gloss:** Alternate with code review. The goal: the whole page, and the catalogue the
user actually downloads, are English only. The protocol must not be touched — this is
a page change. All three sites have some broken links. Every release must show a
license, and that must be fully auto-derived rather than hand-specified. Remove the
proxy column. Keep this style for the whole page but cut the word count substantially.

**Consequences:**
- `specs/` had zero changes in that batch — recorded in the commit message as proof
  the ruling was honoured.
- The proxy column was removed from the page: the word `proxy` measured zero
  occurrences in the built output.
- Every release row gets a license cell filled from the manifest; schema 3 renders a
  clickable `{id, url}`, schema 2 renders `null`. Nothing is typed by hand, nothing is
  inferred.
- Broken links across all three sites became the H5/H6/H7 gate family (see R-021).

---

## R-019 — `schema: 2` stays valid for resources that declare no license

**Ruled:** 2026-11-02

**Original:** 「schema2我认为需要继续兼容」 and then, correcting the interpretation,
「打住，我的意思是，schema2就是为了兼容那些不声明license的资源的，以后可以搞什。么图片呀来发，也是静态」
(the stray full stop inside 什。么 is in the original.)

**Gloss:** Stop — what I mean is that schema 2 exists to accommodate resources that do
not declare a license. Later we may publish things like images the same way; that is
static too.

**Consequences:**
- `ACCEPT_SCHEMA = (2, 3)` in the deriver. G7 applies to schema 3 only.
- A schema-2 release is listed with `"license": null`, recorded honestly. It is not
  derived, not guessed at, not excluded.
- `null` is a legitimate state for static resources such as images, not an error.

---

## R-020 — Do not invent fields; reuse what the protocol already defines

**Ruled:** 2026-11-02

**Original:** 「不要自己造字段啊......协议里清清楚楚有的字段给它复用到页面上，null就是null 不要not decleared，派子代理查杀所有契约外的字段」

**Gloss:** Do not invent your own fields. The protocol clearly defines the fields —
reuse them on the page. `null` is `null`; do not write "not declared". Dispatch a
subagent to hunt down every field that exists outside the contract.

**Consequences:**
- Removed: `summary_en`, `reasons_en`, `source_repo`, the per-entry `tag`, and the
  `not declared` display state.
- The excluded table uses the protocol's own word, `reason` — a single English string.
- The license cell renders `null` for schema-2 entries; there is no third state.
- Consequence of the hunt: a sort still reading the deleted `source_repo` raised
  `KeyError` on the first passing release; the fix was found by review, not by luck.

---

## R-021 — Dead links: HTTP 200 may be a 404 fallback page

**Ruled:** 2026-11-02

**Original:** 「isui.ren/static那边大部分链接都是死的，出http200有可能是404兜底页，你的判定需要修，我猜其他俩站差不多都是这样静默死链」

**Gloss:** Most links on isui.ren/static are dead. An HTTP 200 may be a 404 fallback
page, so your check needs fixing. I suspect the other two sites silently produce dead
links the same way.

**Consequences:**
- H6 stopped judging by status code. It first requests a path that cannot exist, with a
  unique suffix, records that body's sha256 as the fallback fingerprint, then compares
  every link's body against it. Equal to the fallback means dead.
- Measured: EdgeOne returns `200` plus a 611-byte SPA fallback for missing paths;
  Pages returns a real `404`. A status-only check was fully fooled.
- Unreachable counts as failure, with two attempts so a momentary drop is not a dead
  link. Traversal later moved from "relative links in the HTML" to each channel's own
  `files.json`, because files present in the artifact but unreferenced from the HTML
  were never checked.

---

## R-022 — Cloudflare is always checked through the 2080 proxy

**Ruled:** 2026-11-02

**Original:** 「cloudflare一律用2080代理看通不通」

**Gloss:** For Cloudflare, always use the 2080 proxy to see whether it is reachable.

**Consequences:**
- `zreflect/check_site_lang.py` honours `SC_HTTP_PROXY` (for example
  `http://127.0.0.1:2080`) for every probe.
- Without the proxy, this machine's egress gets a TLS reset from Cloudflare's edge, so
  that channel is always an URLError — and "unreachable" is a failure in H6, which
  would report a network problem as a dead link.
- With the proxy, the three channels measured 15/15 links each: Pages dead=0;
  Cloudflare and EdgeOne one dead link each, both `LICENSE`. The coverage later rose
  to 16 links per channel once traversal moved to `files.json`, and all three came back
  dead=0 after the mirrors were fixed.

---

## R-023 — Cloudflare moved to the root path

**Ruled:** 2026-11-02

**Original:** 「cf是改成/而不是/static了。你改下就行」

**Gloss:** Cloudflare is changed to `/` rather than `/static`. Just change it.

**Consequences:**
- `site/channels.json` records `https://static.mango-mesa.ccwu.cc/` for Cloudflare.
- H6, H7 and `verify-channels.py` all read that configuration, so they followed the
  change without further edits.
- The earlier period when `static.mango-mesa.ccwu.cc/static/*` returned 404 across the
  board is kept in the record rather than deleted.

---

## R-024 — Everything on the site in full English, no emoji

**Ruled:** 2026-11-02 (two statements, two minutes apart)

**Original:** 「小更新，网站所有链接的md都改成全原文无表情符号」
then 「不不不，打错字了，全英文」

**Gloss:** Small update — every linked markdown on the site should be in the full
original text with no emoji. No — I typed it wrong: full English.

**Consequences:**
- The corrected requirement is full English, not merely "no emoji". `STATE.md` is
  English and measures zero CJK characters.
- This ruling is **not fully applied** as of 2026-11-03, and the gap is recorded rather
  than papered over: `README.md` still holds 1268 CJK characters, `maintaince.md` 844,
  and the `specs/` bodies remain Chinese (3338 CJK in v1.1 alone). The specs also
  still carry emoji, 6 to 25 per document.
- R-026 is the later ruling that actually forces the rest of the translation and
  separates live state from the contract body.

---

## R-025 — The English version is the sole authority

**Ruled:** 2026-11-02

**Original:** 「使用这个写英文版，以后就是唯一权威」
(the message opens with a skill link before this text.)

**Gloss:** Use this to write the English version; from now on it is the only authority.

**Consequences:**
- English documents supersede the Chinese set as the normative text.
- The Chinese originals are not destroyed: they survive as evidence, in this file and
  in the ruling trail, so a future reader can check what was actually decided.
- `docs/` was created as the home for exactly this kind of material, separate from
  `specs/`.

---

## R-026 — Translate everything; state must not couple to the contract body

**Ruled:** 2026-11-03

**Original:** 「为什么站上的那些包括v1.1契约都还是有中文有表情符号的版本」 and then
「都要译，我认为state那些本来就不应该跟契约正文耦合，它又不是一直在变的」

**Gloss:** Why are those things on the site — including the v1.1 contract — still the
Chinese version with emoji? Everything must be translated. And I think the state
documents should never have been coupled to the contract body in the first place; it
is not something that keeps changing.

**Consequences:**
- `STATE.md` was rewritten in English and cut to what is true now; numbers are
  `[[key]]` references into the fact ledger rather than typed values.
- Incident history moved out to `docs/incidents.md` and rulings to `docs/rulings.md`;
  `STATE.md` links to both instead of carrying them.
- The contract body (`specs/`) and the live state are separate documents with separate
  change rates — the coupling was the defect, not the translation.

---

## R-027 — The protocol has no capacity limit

**Ruled:** 2026-10-31

**Original:** 「别发信质疑协议了，之后gitcode啥的就各不相同了，反正协议无限就对了.撤回那封信，OM反正之前那条也没看，直接全部撤回然后改成一封」
(the full stop inside 对了.撤回 is in the original.)

**Gloss:** Stop sending letters questioning the protocol. Later gitcode and whatever
else will each be different anyway; the protocol being unlimited is simply correct.
Withdraw that letter — OpenModelica has not read the earlier one anyway, just withdraw
everything and send one letter.

**Consequences:**
- No entry count and no asset count limit anywhere in the generator or the checker.
  The generator only reports counts ("expected N entries / M assets") and blocks none.
- The generator self-test includes 340 files yielding 340 entries, and more than 1000
  assets, precisely to prove nothing is hard-coded.
- Platform capacity is the distributor's problem: splitting across releases, changing
  platforms or bucketing is deployment shape, never content semantics.

---

## R-028 — Only forbid names that change after the asset

**Ruled:** 2026-10-31

**Original:** 「额，有没有可能，我们只要强制会在asset后变化的名称不允许就行」

**Gloss:** Would it be possible that we only need to forbid names that would change
after the asset?

**Consequences:**
- V1 is a positive whitelist: `^[A-Za-z0-9_-][A-Za-z0-9._-]*$`, no `..`, no trailing
  dot, at most 255 characters. Everything the platform rewrites is out of the set.
- The whitelist exists for one reason: GitHub rewrites some names silently (space to
  dot, percent to dot, parentheses deleted, non-ASCII deleted, leading dot prefixed,
  runs of dots collapsed) while a too-long name merely errors. A silent rewrite makes
  `manifest.file` point at a non-existent asset, which looks exactly like "never
  published" — the exact unattributable failure this contract exists to kill.
- The measured rewrite table is in v4 section 1 and is the only basis for changing
  the whitelist.

---

## R-029 — The goal: apt's robustness plus HTTP's simplicity

**Ruled:** 2026-10-31

**Original:** 「很不错！v4跑一次，当然我只是说本地测一下5mb分片什么的机制都有没有生效。最终结果应该是拥有apt的稳健与http标准简洁请求」

**Gloss:** Very good. Run v4 once — of course I only mean testing locally whether the
5 MiB chunking mechanism and the like actually take effect. The end result should be
apt's robustness with HTTP's standard, simple requests.

**Consequences:**
- Every record is self-sufficient: an `entries[]` item carries its own `bytes`,
  `sha256` and `variants`, so a single entry can be fetched without cross-references.
- Deduplication of identical content was deliberately rejected: it couples members, so
  deleting one would affect another. The cost of storing the same content twice was
  accepted instead.
- `variants` is an ordered array, so adding a codec is adding an array element and the
  schema does not change.

---

## R-030 — Never needs updating, and highly HTTP-standard

**Ruled:** 2026-10-30

**Original:** 「并且，之后我们可能上oracle对象存储或者cf的，但是极大可能我们仍然走edgeone分发，而edgeone的特点就是5mb极其迅速，所以需要一个针对br和gzip这种压缩后格式的乱序多线程拉取协议，这与我们之前的源文件range又有冲突（我想沿用）。今天预算无限时间无限，一定要给静态站一个永远不需要更新且高度符合http标准的协议」

**Gloss:** Later we may move to Oracle object storage or Cloudflare, but it is very
likely we still distribute through EdgeOne, and EdgeOne's characteristic is that
5 MB is extremely fast. So we need an out-of-order multi-threaded fetch protocol for
already-compressed formats like br and gzip — which conflicts with the byte-range
approach on the original files that we had been using. Today the budget and time are
unlimited: we must give the static site a protocol that never needs updating and is
highly HTTP-standard.

**Consequences:**
- An immutable identity: a release is an immutable tag, a new version is a new tag, and
  no `latest` alias is offered — that would be the entrance to permanent updates.
- `chunkSize` defaults to 5 MiB, in direct response to "5 MB is extremely fast";
  the hard ceiling is `2^25` because of the fzstd backreference limit.
- Format negotiation is handed back to HTTP (`Accept-Encoding`); the contract does not
  arbitrate it.
- The speed claim for zstd over gzip on the real EdgeOne link remains an open question
  (`questions/05`) and is not written down as present fact.

---

## R-031 — Do not invent; the end user makes one plain request

**Ruled:** 2026-10-30

**Original:** 「那http的标准是可以指定要拉什么格式的，所以我们管不到，不要想太多自创东西，最终用户拉的仅仅只是一个没多少头的标准请求，gpt说如果是预先分片完的话br和zstd是没多少差距的，br的解压性能损失也很难受所以排到第二」

**Gloss:** The HTTP standard already lets you specify which format to fetch, so that is
not ours to manage. Do not invent too much. What the end user performs is just one
standard request with hardly any headers. If the payload is pre-chunked, br and zstd
are not far apart, and br's decompression cost is unpleasant, so put it second.

**Consequences:**
- The entire Range family was cut: pre-chunking makes range requests unnecessary.
- A self-invented seek table, `range.basis` and `granularity` were cut as well.
- The first codec generation is `zstd`, `gzip`, `identity` — br is not rejected, it is
  simply not enabled in the first generation. The stated reason br ranks below both is
  its decompression cost, not its size ratio.
- V9 keeps `codecs` an open vocabulary rather than an enum, so adding a format does
  not change the schema.

---

## R-032 — No backward compatibility before a pilot

**Ruled:** 2026-10-30, restated 2026-11-01

**Original:** 「什么叫试点都没做就开始做向后兼容，23个字段我觉得也是时候掂量一下哪些不需要了」
and 「那么我开始怀疑V1-V10到底要不要测，因为有过多次破坏性改动，且我们完全不必要进行向后兼容设计」

**Gloss:** What do you mean, backward compatibility before a single pilot has been run?
Twenty-three fields — I think it is time to weigh which of them are unnecessary.
Then I am starting to doubt whether V1–V10 should be tested at all, since there have
been several breaking changes and we have no need whatsoever for backward-compatible
design.

**Consequences:**
- V10 refuses any `schema` value the client does not know, outright. There is no
  negotiation, no optional-field degradation, no multi-branch parsing.
- The answer given and accepted: V1–V10 are not a compatibility layer but an
  admission test — "is this manifest self-consistent under the current schema". The
  price of having no compatibility layer is paid by strict refusal at publish time.
- Old releases are not "fixed" into the current schema. They stay excluded, and their
  exclusion is the record.

---

## R-033 — "Non-free" is a maintenance stance, not a license

**Ruled:** 2026-10-17; corrected by the user 2026-11-02

**Original:** 「IllegalPerformance是我说的non-free因为我们使用了rust打补丁，这是"脱离开源社区"的线，懂了吗，其他仓库也会也只会有这三种线，主线被榨干性能之前不会开IP线。理解一下」
and the correction 「实际上IP线产物真的是non-free吗，我们也开源了吧」

**Gloss:** IllegalPerformance is what I call non-free because we used a Rust patch to
modify it — it is the "detached from the open-source community" line. Other
repositories will also have, and only have, these three lines; the IP line will not be
opened before the mainline has been squeezed dry. Then: is the IP-line artifact
actually non-free? We open-sourced it too, did we not?

**Consequences:**
- The catalogue admits by G1–G7 and adds no license policy of its own. A release whose
  shape is valid is listed; free or non-free is for the reader to judge from the page.
  The protocol makes no value judgement.
- A producer had written `LicenseRef-nonfree-rust-sort-kernel` into its manifest,
  mistaking a maintenance stance for a license fact. The correction is recorded in the
  v1.1 spec section 4.5 as the worked example of "passing V11 is not the same as the
  license being right".
- The Rust sort kernel turned out to be first-party `#![no_std]` source with no
  third-party crates, so all three artifacts are `AGPL-3.0-or-later`. The catalogue was
  re-derived and `LicenseRef` went to zero.
- The maintainer's own error is recorded too: it had checked the shape and called it
  verified, which is exactly the failure the spec warns about.

---

## R-034 — The version axis must be distinguishable from GNU Octave

**Ruled:** 2026-11-02

**Original:** 「撤掉你认为不贴近合规的那版，或者两版都撤然后发octave-full-wasm为名字参考LLVM的版本号，因为这确实得跟gnu维护的octave区分」

**Gloss:** Withdraw whichever version you think is less compliant, or withdraw both and
publish under the name octave-full-wasm, following LLVM's version numbering — because
this really does have to be distinguishable from the octave that GNU maintains.

**Consequences:**
- Two tags were withdrawn and one released: `octave-full-wasm-v0.1.0`, with
  `manifest.id` of `Octave-Full-Wasm/v0.1.0`, 82 assets, schema 3, plain AGPL.
- The ruled basis is measured: GNU's own release tag is `release-11-3-0`, so a tag
  named `octave-11.3.0-r2` puts two different products in one namespace.
- `site/sources.json` records the repository and not the tag, so the catalogue
  followed without a configuration change; the deriver read the new tag on its next run.
- The two withdrawn builds were byte-identical apart from `manifest.id` and entry
  order, so there was no "more compliant" build to keep.

---

## Repeated rulings

Several decisions were stated more than once, sometimes months apart. They are merged
above rather than duplicated, with every date kept:

| Entry | Dates | Relationship |
|---|---|---|
| R-004 | 2026-11-01 twice | The second statement names the mechanism (EdgeOne reverse-proxying Cloudflare) that the first described as a symptom. |
| R-006 | 2026-11-01 twice | First the refusal, then the instruction to both producers. |
| R-024 | 2026-11-02 twice | The second corrects a typo in the first; together they mean "full English". |
| R-026 | 2026-11-03 twice | The question identifies the symptom; the answer states the rule and the structural fix. |
| R-032 | 2026-10-30 and 2026-11-01 | First as "we have not even piloted"; restated after a concrete proposal to build a compatibility layer. |
| R-033 | 2026-10-17 and 2026-11-02 | The stance was correct for its own purpose; the correction is that it was never a license fact. |

Two rulings were superseded by later ones rather than merged:

- R-024 (all markdown in English) is incomplete on its own; R-026 is what actually
  forces the translation and separates state from contract.
- R-008 (per-component license) and R-013 (license as name plus link) were stated in the
  same session about eighty minutes apart; R-013 is the accepted shape and R-008 is the
  requirement that motivated it. Both are kept because the requirement outlives the
  shape: if `{id, url}` is ever replaced, R-008 is the criterion the replacement must
  satisfy.
