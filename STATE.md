# Live State (Static-Contract)

This file answers one question: **what is true now**. Not what happened, not why.
Incident history and user rulings are kept in the repository under `docs/` and are not
published to the site. Numbers are never typed here — they are `[[...]]` references into the fact ledger.

## Role

**This repository maintains the contract. It hosts zero bytes of any release.**
Every package comes either from GitHub (release direct link) or through a reverse
proxy. The site publishes metadata and contract documents only.

Ruling text: `docs/rulings.md` R-001 (repository only, not published).

## Canon

| Document | Covers | Status |
|---|---|---|
| `specs/2026-10-30-release-contract-v4.md` | V1–V10, manifest structure | Authority for invariants; `schema: 2` clause superseded |
| `specs/2026-11-01-release-contract-v1.1-license.md` | V11, `schema: 3` | Authority for license |

v0, v1, v2, v3 and the v3 absorption audit are `DEPRECATED` — kept only so rejected
designs and their criteria are not re-opened. **Not yet piloted end to end; not
declared stable.**

## Tools

| Tool | Self-test |
|---|---|
| `tools/make-manifest-v4.py` | `[[tool_manifest_selftest_pass]]` PASS |
| `tools/check-release-v4.py` | `[[tool_check_release_selftest_pass]]` PASS |
| `scripts/sync-catalogue.py` | derivation: G1–G7 |
| `scripts/build-site.py` | `[[site_build_selftest_pass]]` PASS |
| `scripts/verify-channels.py` | deployment verification |

Reproduce: `python3 tools/check-release-v4.py --selftest`.

## Catalogue

**Derived, never hand-written.** `site/sources.json` lists which repositories are
subscribed; every tag is read from their releases at derivation time.

- Four sources: `Octave-Extra-Content` (forge), `LLVM-wasm` (toolchain),
  `Octave-Full-Wasm` (engine), `OpenModelica-Full-Wasm` (engine).
- Gates G1–G7 decide admission. Anything that fails is excluded **with its reason
  listed** — a bad release never goes live, and never disappears silently.
- A release with no license declaration reads `"license": null`. That is a
  legitimate state for static resources such as images, not an error.
- Derivation runs on every push and hourly (`cron: '17 * * * *'`).

Reproduce: `python3 scripts/sync-catalogue.py --dry-run`.

## Site

Built by `scripts/build-site.py` into `site/dist`. The page is plain XHTML 1.1 with
zero JavaScript and zero external resources. Numbers on the page are measured by the
builder at build time, never copied by hand.

`files.json` is published alongside the artifact. It is the exact file list; mirrors
copy it rather than maintaining their own list.

## Deployment

One build, **one deploy branch per mirror** (ruled 2026-11-04): `deploy-eo` and
`deploy-cf`. Each carries a catalogue whose `base` points at that mirror, so each site
line fetches from its nearest mirror. Adding a mirror means one matrix entry and one
branch — no code change.

| Branch | Mirror (`base` host) | Site line | Owned |
|---|---|---|---|
| `deploy-eo` | `https://static.isui.ren/` | `https://isui.ren/static/` | **yes** |
| `deploy-cf` | `https://static.mango-mesa.ccwu.cc/` | `https://static.mango-mesa.ccwu.cc/` | **yes** |

`base_proxy` is `https://github.com/...` in both — the fallback when a mirror fails.
The two catalogues are **not byte-identical** (different `base` host); each is
self-consistent. Cross-mirror range continuation was measured working, so a client may
start on one mirror and finish on another or on `base_proxy`.

GitHub Pages was removed on 2026-11-04: a Pages site is inert static hosting and can
never proxy or redirect release bytes, so as a fetch channel it was pure false signal.
The site itself is deleted rather than left serving a stale artifact.

Each matrix job verifies **only its own branch and mirror** (`SC_CHANNELS_ONLY`), so
`deploy-eo` never waits on `deploy-cf`. `site/channels.json` carries `owned`. **Only a failure on an owned channel blocks a
release.** External channels report a warning and never silently disappear. A channel
list with no `owned` entry is a fatal configuration error, not a pass.

Pipeline: push `main` → for each matrix entry: derive its catalogue → gates → build →
force-push orphan branch → verify. Only the EO entry dispatches the EdgeOne rebuild.

## Gates

The roster is rendered from declaration lines at the bottom of this file.
Execution reads the roster (`registry --run commit`), never a filename glob.
**An `off` gate is not a passing gate** — it is reported separately.

## base_proxy ruling (2026-11-03)

Canon v1.1 §5.3 defines both fields: **`base` = cluster mirror, tried first;
`base_proxy` = GitHub origin, the fallback.** Same path shape, host only.

`base_proxy` is `base` with the host swapped: `https://isui.ren/<owner>/<repo>/releases/download/<tag>/`.
Same shape as `base` — clients need zero changes, and the proxy provider's path
layout never leaks into the contract (same criterion that rejected platform
capacity limits in canon §3).

Both are filled by `scripts/sync-catalogue.py` at derivation time. Live as of
2026-11-04: mirrors verified byte-passing, 18/18 releases reachable on **both**
roots (36/36 HEAD checks against `manifest.json`).

## License URL content check (2026-11-04)

`V11` checks only the shape of `license.url` (https, non-empty), so a page that
answers `200` with no license text passes silently. The deriver now also fetches each
`license.url` and emits a **warning** to stderr when the body is under `200` characters
or contains no known license token. It never fails a release: splitting the license
across file headers is a legitimate upstream layout, and failing would push producers
to invent a URL. **It proves only that something is there, not that it is the right
license.**

## Open

- `questions/05` — zstd vs gzip on the real EdgeOne link (5 runs, median). Unresolved.
- U1 codec order (= question 05), U2 per-entry `chunkSize`, U3 asset name prefix,
  U4 rollout schedule for remaining repositories.
- `contract.json` fingerprint file (machine-checkable contract version for downstream
  CI) — proposed, not implemented.

## Pilot chain acceptance

1. [ ] Producer publishes a real GitHub release (candidate: `optim 1.6.3`).
2. [ ] This catalogue lists it (id + base only, no bytes).
3. [ ] Consumer pulls manifest and assets from base: plain GET throughout, per-chunk
   and total sha match byte for byte.
4. [ ] Reproduction recorded here, next to the number.

<!-- AUTO:FACTS -->
> 本区块由 `zreflect/facts.py --render-doc` 从 `FACTS.json` 渲染，**不要手改**（pre-commit 会重算并 `git add`）。
> 正文里的「测出来的数字」只在这里生产：要引用就写 `[[键名]]`，不要手抄数字。

| 键 | 值 | 测于 | 复跑命令 |
|---|---|---|---|
| `catalogue_releases` | **0** | 2026-11-02T13:28:11+0800 | `python3 -c "import json;print(len(json.load(open('site/catalogue.json'))['releases']))"` |
| `mail_unread` | **0** | 2026-11-02T13:28:11+0800 | `find mail -maxdepth 1 -name '[0-9]*.md' | wc -l` |
| `site_build_selftest_pass` | **14** | 2026-11-02T13:28:11+0800 | `python3 scripts/build-site.py --selftest 2>/dev/null | grep -c '^PASS'` |
| `specs_md` | **7** | 2026-11-02T13:28:09+0800 | `ls specs/*.md | wc -l` |
| `tool_check_release_selftest_pass` | **37** | 2026-11-02T13:28:11+0800 | `python3 tools/check-release-v4.py --selftest 2>/dev/null | grep -c '^PASS'` |
| `tool_manifest_selftest_pass` | **43** | 2026-11-02T13:28:11+0800 | `python3 tools/make-manifest-v4.py --selftest 2>/dev/null | grep -c '^PASS'` |

6 条事实。
<!-- /AUTO:FACTS -->

<!-- AUTO:GATES -->
> 本区块由 `zreflect/facts.py --render-doc` 从发现式名录（zreflect/registry.py 的声明行）渲染，**不要手改**。
> 执行面（hooks / CI）读 `registry --run <相位>` —— 相位是声明字段（`runs_at`），不是文件名。

| 闸门 | 相位 | 它挡住什么 | 消费的旋钮 |
|---|---|---|---|
| `check_ab.py`（A/B 闸门） | commit | A/B 同旗标不变式（非 allow 轴差异 = 混淆变量，A/B 作废） | `REFLECT_AB` |
| `check_catalogue.py`（catalogue 派生闸门） | commit | 派生器自证全绿 + 兜底源文件不得含手写条目（条目只由派生产出） | — |
| `check_envfile.py`（env 文件闸门） | commit | 守钩子的 REFLECT_* 载体（旋钮 typo / 指向缺失 / 空值） | `REFLECT_ENV_FILE` |
| `check_facts.py`（事实闸门） | commit | 块一致性 / 裸数字 / 坏引用 | `REFLECT_FACTS`, `REFLECT_DOC`, `REFLECT_NAKED_MIN` |
| `check_facts_replay.py`（复跑闸门） | commit | 台账 cmd 逐字复跑（裸值契约：stdout 必须等于值） | `REFLECT_FACTS`, `REFLECT_REPLAY`, `REFLECT_REPLAY_TIMEOUT` |
| `check_instruments.py`（仪器生命周期闸门） | commit | 恒常检测（first_seen）+ 被证伪量法登记 | `REFLECT_INSTRUMENTS`, `REFLECT_INSTRUMENT_DAYS`, `REFLECT_FACTS` |
| `check_invariants.py`（不变量闸门） | commit | 声明式不变量：仓库文件必须/不得含某片段（grep 级） | `REFLECT_INVARIANTS` |
| `check_locks.py`（锁定源闸门） | commit | 锁定源清单（URL + 文件 + sha256 的内容指纹） | `REFLECT_LOCKS` |
| `check_pins.py`（pin 闸门） | commit | 派生树 pin 一致性（stamp commit / dirty / 版本串对读） | `REFLECT_PINS` |
| `check_questions.py`（悬案闸门） | commit | 未结案的问题必须挂一个能跑的结算件 | `REFLECT_QUESTIONS` |
| `check_readme_sync.py`（三语 README 闸门） | commit | 语言版本是同一条断言的三份拷贝：结构互链 + 每次推送同批 | `REFLECT_READMES` |
| `check_retractions.py`（翻案重现检测） | commit | 被推翻的断言不许悄悄回来当现状 | `REFLECT_RETRACTIONS`, `REFLECT_DOCS`, `REFLECT_HISTORY_SECS` |
| `check_site_build.py`（站点构建自证） | commit | build-site.py 自证 10 条（catalogue 校验 + 0 字节闸门 + 确定性） | — |
| `check_site_lang.py`（站点语言闸门） | commit | HTML 产物必须全英文；废弃契约必须在页面与文档里被标出 | — |
| `check_stale.py`（陈旧断言检测） | commit | sha 出处 / 退役名 / 测龄 | `REFLECT_DOCS`, `REFLECT_FACTS`, `REFLECT_HISTORY_SECS`, `REFLECT_RETIRED`, `REFLECT_STALE_DAYS` |
| `check_world.py`（world 闸门） | commit | 声明式验证对象：多线仓库共享验证环境的世界对账 | `REFLECT_WORLD`, `REFLECT_WORLD_LINE` |
| `doctor.py`（开工预检 doctor） | start-of-work | 进程 / 端口活性（查会死的东西 ⇒ runs_at=start-of-work，不进 pre-commit） | `REFLECT_DOCTOR`, `REFLECT_DOCTOR_TIMEOUT` |

17 道闸门（发现式名录派生 —— 手写清单会漂，加闸门 = 落一个声明行，这里自动长出来）。
<!-- /AUTO:GATES -->
