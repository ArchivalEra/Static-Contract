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
- **站点**：元数据站。产物 = `index.html` + `catalogue.json` + `sources.json` +
  `contract/*.md` + `tools/*.py` + `README.md` + `STATE.md` + `maintaince.md`，
  **无任何 release 件**。
  构建复跑：`python3 scripts/build-site.py --out site/dist`（确定性构建，两次逐字节一致，自证覆盖）。
- **catalogue（严格派生，2026-11-01 裁定）**——用户裁定原话：「最后做一下 catalogue 的
  严格校验，不允许有坏的流到客户端，足够了，根本不需要客户端错误排查的事情，
  只要坏的从未上架过」+「严格拒绝，我叫LLVM重新发了」。
  ⇒ catalogue 是**派生产物**（`scripts/sync-catalogue.py`）：不手改、条目不落 git；
  订阅清单 `site/sources.json` 只记仓名（加仓是显式决定）。
  六道闸 G1–G6：有 manifest 且平台给 digest / manifest 内容 sha == 平台 digest /
  V1–V10 全过 / **每个 chunk 的 sha256 == 该 asset 的平台 digest**（零下载验字节 ——
  GitHub asset API 实测 `107/107` 带 digest）/ schema 必须 2 / **无孤儿 asset**。
  失败处置：单条不过 ⇒ 不进 array 并记 `excluded`（照样发布，可审计）；
  **source 取数失败 ⇒ 整步红、部署中止、三通道停在上次好结果**（绝不发空目录）。
  实测（2026-11-01 dry-run）：15 条上架 / 6 条排除 —— LLVM `v0.1.0`–`v0.1.4` 被 G5
  （schema 1）挡、`v0.1.5` 被 G6（孤儿 `llvm-wasm-bundle-v0.1.5.tar.gz`）挡；
  用户裁定**硬拒**并令 LLVM 重发。复跑：`python3 scripts/sync-catalogue.py --dry-run`、
  `--selftest`（12 PASS / 0 FAIL）。
  闸门入册：`zreflect/check_catalogue.py`（派生器自证 + 兜底源必须空 + 订阅清单非空）。
- **部署链（三通道并行，一份产物）**——用户裁定 2026-11-01：「pages + cf pages + edgeone
  三条并行且只需要出一份产物就能三地部署」。push main → `sync-deploy` workflow
  （构建器自证 + 构建 + 0 字节闸门）→ **同一份 `site/dist`** 走两条腿：
  ① orphan 单提交强推 `deploy` 分支（CF Pages / EdgeOne Pages 监听，**待接入**）；
  ② `actions/deploy-pages` 正面部署 GitHub Pages（2026-11-01 实测启用，
  `https://archivalera.github.io/Static-Contract/`，`build_type=workflow`，复跑：
  `gh api repos/ArchivalEra/Static-Contract/pages --jq .html_url`）。
  站点全相对链接，子路径托管无害。实测：run `41263566662` success（首跑，2026-11-01），
  复跑 `gh run list --workflow sync-deploy --repo ArchivalEra/Static-Contract`。
  **三通道现状（2026-11-01 全部上线，shirone `mail/read/003` 侧建 + 我复跑）**：
  GitHub Pages `https://archivalera.github.io/Static-Contract/`；
  Cloudflare `https://static.mango-mesa.ccwu.cc/static/`（Worker `/static/*` 前缀路由）；
  EdgeOne `https://isui.ren/static/`（heart 中间件反代 CF Worker，国内路径）。
  我侧复跑（2026-11-01）：EdgeOne 通道 catalogue 哈希 `3fffe32ee34975a441aee0a357f10e9d`
  与 Pages 一致、ETag 条件请求 `304` ✓；CF 通道**从本机 000**（TLS 在 CF 边缘被重置，
  本网络出口问题，连既有路由 `/assistant.user.js` 同样 000 —— 非部署缺陷；
  shirone 侧三通道同哈希实测在原信 §3.1，复跑见原信）。
  头语义（shirone 侧配置，见原信 §2）：精确 Content-Type / ETag=sha256 前 32 位 /
  条件请求 `304` / `Cache-Control: max-age=300`（刻意不用 immutable —— 站内文档原地更新）。
  **⚠️ 已知缺陷（2026-11-01 用户当场发现，未修复）**：EdgeOne 通道**不跟 deploy 分支**——
  它读的是 shirone 侧 Worker 内联的打包快照（`worker.gen.mjs`，base64 内联），
  对方不重新生成并部署 Worker，那条通道就停在旧快照。实测：deploy 分支与 Pages
  都是 `verified_at=2026-11-01T09:51:56Z` / 16 条，EdgeOne 的 catalogue 是**空体**、
  index.html 是 `2095` 字节的加 catalogue 段之前的旧构建。
  **这条与「三通道并行，一份产物三地部署」的裁定不符** —— 真正的自动更新需要
  shirone 侧把 Worker 改成读 deploy 分支（或每次我方推送后触发他们的重新部署）。
- **线上验收闸门**（`scripts/verify-channels.py`，自证 9/9）：部署后逐通道核对
  **本次产物指纹**（`STATIC-CONTRACT-BUILD <hash>` 写进 index.html）与
  `catalogue.verified_at`。判据锚在产物本身，**不是通道之间是否一致** ——
  全都停在旧产物时一致性同样成立（这正是我第一次误判的原因）。
  实测（2026-11-01）：`sync-deploy` 在该步**红**并如实列出 EdgeOne 三项全败，
  GitHub Pages 通过。复跑：`python3 scripts/verify-channels.py --expected site/dist
  --channels site/channels.json`。
  **`base_proxy` 仍未填**——语义切分：catalogue 的 `base_proxy` 是**字节侧**逐 release
  反代（代理 release asset），`/static/` 两 URL 是**站点镜像**，两者不是一回事；
  字节侧候选（`isui.ren/repo/<owner>/<repo>/releases/download/<tag>/`，heart 反代 GitHub）
  待试点真 release 落地时验链再填（shirone 003 §5.2 同意此序）。
  卫生：本地 `site/dist` 已重建（它是 gitignore 的构建物；三通道读的 deploy 分支由 CI
  每推重建，本地落后不影响通道，但按 shirone 003 §4 提醒保持新鲜）。
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
| `catalogue_releases` | **0** | 2026-11-01T14:44:32+0800 | `python3 -c "import json;print(len(json.load(open('site/catalogue.json'))['releases']))"` |
| `mail_unread` | **0** | 2026-11-01T14:44:32+0800 | `find mail -maxdepth 1 -name '[0-9]*.md' | wc -l` |
| `site_build_selftest_pass` | **10** | 2026-11-01T14:44:31+0800 | `python3 scripts/build-site.py --selftest 2>/dev/null | grep -c '^PASS'` |
| `specs_md` | **6** | 2026-11-01T14:44:30+0800 | `ls specs/*.md | wc -l` |
| `tool_check_release_selftest_pass` | **26** | 2026-11-01T14:44:31+0800 | `python3 tools/check-release-v4.py --selftest 2>/dev/null | grep -c '^PASS'` |
| `tool_manifest_selftest_pass` | **43** | 2026-11-01T14:44:31+0800 | `python3 tools/make-manifest-v4.py --selftest 2>/dev/null | grep -c '^PASS'` |

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
| `check_stale.py`（陈旧断言检测） | commit | sha 出处 / 退役名 / 测龄 | `REFLECT_DOCS`, `REFLECT_FACTS`, `REFLECT_HISTORY_SECS`, `REFLECT_RETIRED`, `REFLECT_STALE_DAYS` |
| `check_world.py`（world 闸门） | commit | 声明式验证对象：多线仓库共享验证环境的世界对账 | `REFLECT_WORLD`, `REFLECT_WORLD_LINE` |
| `doctor.py`（开工预检 doctor） | start-of-work | 进程 / 端口活性（查会死的东西 ⇒ runs_at=start-of-work，不进 pre-commit） | `REFLECT_DOCTOR`, `REFLECT_DOCTOR_TIMEOUT` |

16 道闸门（发现式名录派生 —— 手写清单会漂，加闸门 = 落一个声明行，这里自动长出来）。
<!-- /AUTO:GATES -->
