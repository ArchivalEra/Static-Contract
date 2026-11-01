# 活状态（Static-Contract）

这个文件是**活状态文档**（Einfacht 生态格式）：正文只写「现在是什么」，
数字一律引用台账键（`[[键名]]`，不手抄），每条「现在如此」的断言**旁边带复跑方式**
（纪律 2 —— 写不出复跑方式的句子只能当历史读）。
台账自动化**已接线**（2026-11-01）：平台 `zreflect/`（自 `vendor/Einfacht` `6e4e6e8`），
数据层 `zreflect/measure_static_contract.py`，旋钮载体 `reflect-hooks/Einfacht.env`；
文末机器块由 `python3 zreflect/facts.py --render-doc` 渲染，**不要手改**。
线上事实（deploy 分支状态等）不进台账——要引用就在正文写命令，不写数。

## 角色（用户裁定 2026-11-01）

**本仓只是契约维护者；站点不收录任何 release 件（0 字节托管）。
所有的包，要么去 GitHub 拿（release 直链），要么走反代。**
（用户原话：「记住最最核心的，你只是契约维护者，所有的包，要么去github拿，要么走反代，
你需要出一个不收录任何release件的站」。）

这条裁定**已做成构建闸门而非纪律**：`scripts/build-site.py` 产物扫描命中 asset 形状
（`*.<codec>.<NNN>`）或 `releases/` 路径 ⇒ 构建失败清场，并挂进 commit 相位
（`zreflect/check_site_build.py`，pre-commit / CI 每次真跑）。
复跑：`python3 scripts/build-site.py --selftest` ⇒ [[site_build_selftest_pass]] PASS / 0 fail。

## 现在是什么

- **正典**：`specs/2026-10-30-release-contract-v4.md`（契约名 v1，manifest `schema: 2`）。
  自 `Octave-Extra-Content` HEAD `9186463` 逐字落库（2026-11-01；拷贝前验过来源三目录 git 干净）。
  v0–v3 与收纳审计是演化史，被否方案判据在正典 §8。**未试点，不宣布稳定。**
- **工具链在库**（落库即实测，2026-11-01。复跑：
  `python3 tools/make-manifest-v4.py --selftest && python3 tools/check-release-v4.py --selftest`）：
  生成器 [[tool_manifest_selftest_pass]] PASS / 0 fail，
  校验器 [[tool_check_release_selftest_pass]] PASS / 0 fail（V1–V10 fail-closed）。
  （移交信所载 `40/25` 是信写完后的旧数字，以本仓实测为准——工具在移交后更新过一轮。）
- **站点**：元数据站。产物 = `index.html` + `catalogue.json` + `contract/*.md` +
  `tools/*.py` + `README.md` + `STATE.md` + `maintaince.md`，**无任何 release 件**。
  数据源 `site/catalogue.json`，当前收录 [[catalogue_releases]] 条（试点链第 1 环未跑）。
  构建复跑：`python3 scripts/build-site.py --out site/dist`（确定性构建，两次逐字节一致，自证覆盖）。
- **部署链**：push main → `sync-deploy` workflow（自证 + 构建 + 0 字节闸门）→
  orphan 单提交强推 `deploy` 分支 → CF Pages / EdgeOne Pages 监听 deploy 自动重建。
  实测：run `41263566662` success（9s，2026-11-01）；deploy 树 11 文件、无父提交、
  提交信息带 main 源 SHA。复跑：`gh run list --workflow sync-deploy --repo ArchivalEra/Static-Contract`
  及 `git fetch origin deploy && git log --oneline origin/deploy`。
  **CF / EdgeOne 尚未接入**（等安排）；反代 `base_proxy` 字段已预留未填。
- **事实系统**（2026-11-01 接线）：pre-commit 重渲染机器块 + 跑 commit 相位全部闸门
  （实测 ran 8 / off 6 / failed 0；复跑 `sh reflect-hooks/pre-commit`）。off 态明说未启用、
  不算通过（ab / instruments / invariants / locks / pins / world —— 各自的旋钮文件未配，
  配了即自动收编）。CI 同判据：`gates` workflow。阴性实测：正文裸数字会被事实闸门打红
  （`999999` 试探已验证），恢复即绿。
- **邮件**：001（契约移交）已读归档，当前未读 [[mail_unread]] 封；往来表见 `mail/README.md`。
- **悬案**：`questions/05`（zstd vs gzip 在 EdgeOne 真链路，各 5 次取中位数）未结。
- **未决项**：U1 codecs 顺序（= 悬案 05）、U2 chunkSize 按件可配、U3 asset 名 product 前缀、
  U4 接入排期——裁定权在本仓（移交信 §5）。

## 试点链验收判据（U4 落地，可勾选）

1. ☐ 生产者（宿主 / extra-content）对真包（候选 `optim 1.6.3`，实测数据现成）**发 GitHub release**
2. ☐ 本站 `catalogue.json` 收录该 release（只记 id + base，不收字节）
3. ☐ 消费者（Octave-UI）从 base（GitHub 直链或反代）拉 manifest + 资产：
   全程普通 GET，逐块 sha + 总 sha 逐字一致
4. ☐ 复跑记录落本仓（数字旁边写复跑方式）

<!-- AUTO:FACTS -->
> 本区块由 `zreflect/facts.py --render-doc` 从 `FACTS.json` 渲染，**不要手改**（pre-commit 会重算并 `git add`）。
> 正文里的「测出来的数字」只在这里生产：要引用就写 `[[键名]]`，不要手抄数字。

| 键 | 值 | 测于 | 复跑命令 |
|---|---|---|---|
| `catalogue_releases` | **0** | 2026-11-01T10:39:17+0800 | `python3 -c "import json;print(len(json.load(open('site/catalogue.json'))['releases']))"` |
| `mail_unread` | **0** | 2026-11-01T10:39:17+0800 | `find mail -maxdepth 1 -name '[0-9]*.md' | wc -l` |
| `site_build_selftest_pass` | **10** | 2026-11-01T10:39:17+0800 | `python3 scripts/build-site.py --selftest 2>/dev/null | grep -c '^PASS'` |
| `specs_md` | **6** | 2026-11-01T10:39:16+0800 | `ls specs/*.md | wc -l` |
| `tool_check_release_selftest_pass` | **26** | 2026-11-01T10:39:17+0800 | `python3 tools/check-release-v4.py --selftest 2>/dev/null | grep -c '^PASS'` |
| `tool_manifest_selftest_pass` | **43** | 2026-11-01T10:39:17+0800 | `python3 tools/make-manifest-v4.py --selftest 2>/dev/null | grep -c '^PASS'` |

6 条事实。
<!-- /AUTO:FACTS -->

<!-- AUTO:GATES -->
> 本区块由 `zreflect/facts.py --render-doc` 从发现式名录（zreflect/registry.py 的声明行）渲染，**不要手改**。
> 执行面（hooks / CI）读 `registry --run <相位>` —— 相位是声明字段（`runs_at`），不是文件名。

| 闸门 | 相位 | 它挡住什么 | 消费的旋钮 |
|---|---|---|---|
| `check_ab.py`（A/B 闸门） | commit | A/B 同旗标不变式（非 allow 轴差异 = 混淆变量，A/B 作废） | `REFLECT_AB` |
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
| `check_stale.py`（陈旧断言检测） | commit | sha 出处 / 退役名 / 测龄 | `REFLECT_DOCS`, `REFLECT_FACTS`, `REFLECT_HISTORY_SECS`, `REFLECT_RETIRED`, `REFLECT_STALE_DAYS` |
| `check_world.py`（world 闸门） | commit | 声明式验证对象：多线仓库共享验证环境的世界对账 | `REFLECT_WORLD`, `REFLECT_WORLD_LINE` |
| `doctor.py`（开工预检 doctor） | start-of-work | 进程 / 端口活性（查会死的东西 ⇒ runs_at=start-of-work，不进 pre-commit） | `REFLECT_DOCTOR`, `REFLECT_DOCTOR_TIMEOUT` |

15 道闸门（发现式名录派生 —— 手写清单会漂，加闸门 = 落一个声明行，这里自动长出来）。
<!-- /AUTO:GATES -->
