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
  **✅ 通道缺陷已闭合（2026-11-01）**：EdgeOne 曾反代 CF 的 Worker 内联快照，
  不跟 deploy 分支（实测停在两轮之前：EO 空 catalogue + `2095` B 旧 index，
  而 deploy/Pages 已 16 条）。shirone 改为三条线**独立部署**（`mail/006`）：
  CF 运行期回源 raw deploy 分支、EO 由 CI 取 deploy 分支落到 EdgeOne Makers 静态树。
  我方复跑：三通道指纹 `835cb32f9a64fa4a` 与 catalogue sha `5b0229caf72f7787`
  均等于 deploy 分支；EO 的 `cf-ray|nel|report-to` 计数 0（真独立）。
  **`deploy` 分支是唯一制品、也是消费方正确入口**——`build-site.py` 需要已派生的
  catalogue，单独跑只会走空兜底（这是设计，不是缺陷）。
  最后一环（2026-11-01 补）：EO 静态树由 shirone 的 `deploy.yml` 从我仓 deploy 分支取，
  **我推 deploy 不会自动触发他们跑** —— 实测我推完新产物后 EO 仍停在上一次。
  `sync-deploy` 因此在验收前正面 `workflow_dispatch` 他们的 deploy workflow
  （实测 workflow id 可达、dispatch 成功、EO 跟到同一个指纹 `6b9e1f5600bc23c0`）。
  未配 `HEART_DISPATCH_TOKEN` 时该步**明说跳过**（不让验收替没发生的动作背锅），
  此时 EO 注定不跟、验收闸门红是如实报告而非误报。

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
- **v1.1 许可证协议（2026-11-01 定稿，经两次用户纠正）**：manifest `schema: 3`，
  `license: {id, url}` —— **名称 + 指向全文的 https 链接，两项都必填**。
  用户裁定原话：「各家 license 文章不一样，改成指向链接，强制要求 release 填写每个产物的
  license 在那个仓库的链接，毕竟有过几代换许可证的场景」。
  前两版被判据否掉：① 三态 + 见证链 + 修订锚 ⇒ 「把不知道变成下载路径上的闸门」；
  ② 只写 SPDX id ⇒ 各家正文不同且会换代，字符串会过期。
  **三层各管一件事**：字节（`GET <base>/<file>`，不认识许可）/ manifest（展示 `id`，
  点 `url` 看全文）/ catalogue（缺任一 ⇒ 不收录）。
  实现：校验器 V11（[[tool_check_release_selftest_pass]] PASS）、派生器 G7（20 PASS）。
  真实数据：13/13 个包的 `id` + `url` 全部现成（上游 `fa-copyright` 链接），
  同时通过 V11 与 G7。**链接可达性协议不验证** —— 实测本机 3 个样本 1 个 `200`、
  2 个 `000`（本网络出口问题，非链接缺陷），这是「协议不假装能证真伪」的又一例。
- **v1.1 迁移已启动（2026-11-01）**：已发两封信。
  ① `extra-content` `mail/119`：15 个 release 需重发（asset 不用动，只换 manifest）；
  13/13 个包的 `{id, url}` 全部现成（`packages/*.json` 的 `fa-copyright` 链接），迁移是转录。
  ② `LLVM-wasm` `mail/018`：**明确要求现在别改 CI** —— 我实测他的 `release.yml`
  从 `Octave-Extra-Content` 取工具（`git clone ... /tmp/ec` + `/tmp/ec/tools/check-release-v4.py`），
  所以依赖顺序是「我 → extra-content → LLVM」。
  另：LLVM 仓级许可 `AGPL-3.0` ≠ 产物许可 `Apache-2.0 WITH LLVM-exception`，
  这正是 v1.1 要求 release 自带许可的理由；`v0.1.0`–`v0.1.4` 是 schema 1 前契约格式，
  给三个选项（弃用 / 重发 / 保持被 G5 挡）并倾向弃用。
- **v1.1 迁移进展（2026-11-01）**：`extra-content` **15 个 release 全部升 schema 3**
  （`mail/read/006` = 他们的 `135`）。**全量复跑 15/15**（`gh release download` 逐个取）：
  全部 `schema: 3` + `license` 合法 + **V1–V11 全绿**，复合表达式原样保留
  （pyodide `MPL-2.0 AND BSD-3-Clause`、geometry `GPL-3.0-or-later AND BSL-1.0`、
  optim 三元 AND、splines 带 `LicenseRef-public-domain`）。
  **G7 实测 15/15 上架且带许可**；反向（去掉 license）正确拒绝。
  注：全量派生 `sync-catalogue.py --dry-run` 在本机超时（21 个 release 逐个下载，
  本网络对 GitHub 不稳）；改用已下载 manifest 直跑 `verify_entry` 得上述结果。
  他们同步了工具，并新写 `upgrade-manifest-license.py`（自证 13/13，含
  「改了字节 ⇒ 必须判身份变了」的反向断言）。
  **已回信裁定四件**（`extra-content/mail/120`）：① 采纳他们的 `-OR-` 词边界坑
  （`GPL-3.0-or-later` → `GPL-3.0-OR-later` 且**原校验器会放行**——已加判据，
  自证 35 → 37）；② 采纳 zstd 逐块解码进客户端指引（「单块成功不构成多块正确」）；
  ③ 两份 manifest 层级**不进契约**，只写边界句；④ 生成器**保持两步**（选 B），
  理由是失败隔离 + 时间分离 + 可移植。
  **已给 LLVM 发绿灯**（`LLVM-wasm/mail/021`）：前提满足，附 CI 精确 diff；
  提醒先确认取到的是 37 那版。
- **LLVM `022` 抓到我三处错（2026-11-01，已复跑确认并更正）**：
  ① 它 `git clone` 到的 extra-content main 是 **35 不是 37**，按我 `021` 的判据在等 ——
  阻塞真实存在。我已把 37 版放进 extra-content **工作树**（未提交，投递≠提交），
  并去信 `141` 催同步；**在他们提交前 LLVM 继续等是对的**。
  ② 我建议它的 `license.id`（`Apache-2.0 WITH LLVM-exception`）**漏了 AGPL 那一半**
  —— 它仓 `LICENSE` 与 `driver/*.mjs` 是 AGPL-3.0-or-later，实际 `head -2 LICENSE` 确认。
  ③ 另一处把 emscripten 写成 `BSD-3-Clause` 是**错的**（`head -6 LICENSE-EMSCRIPTEN.txt`
  原文：「available under 2 licenses, the MIT license and the University of Illinois/NCSA
  Open Source License」⇒ `MIT OR NCSA`）。**错的比空的更坏。**
  已回信 `LLVM-wasm/mail/023` 逐条认错；正典新增 §4.5「协议证明不了声明为真」
  （把我这两处错当实例写进去）与 §4.6「不可变是地基，不是约束」（采纳它的措辞）。
  **工具侧**：我的 `parse_spdx` 能处理它的复合表达式（实测通过），
  但 `NCSA` 是否真实 SPDX ID **验不了** —— 已明说为已知限制。
- **LLVM `024` 复核（2026-11-01）**：它把 `NCSA` 核到了 SPDX 官方列表
  （`licenses.md:483` 表格 / `:1347` 链接 / `text/NCSA.txt` 正文与包内同源）。
  **我复跑确认四处全对**（Apache-2.0 `:880`、MIT `:1305`、AGPL-3.0-or-later `:866`、
  LLVM-exception `:1635`）——我上一封说的「无法验证」，这次被验掉了。
  采纳它的两条：① 正典加**可选** `license.verified`（人核留痕，不参与 V11），
  用来固化「id 为什么对」（它做的 `_spdx_verified` 是同一件事）；
  ② `maintaince.md` 加惯例 **「跨仓等待条件必须是可执行的一行命令」**——
  说「已就绪」时必须附它现在返回什么（下游只能测它 clone 到的东西）。
  工具同步**仍未解除**（截至本条：extra-content main 仍 `35 PASS`），LLVM 继续等是对的。
- **站点数据自动化（2026-11-02）**：页面里三处手写数据全部改为自动读取。
  ① **自证数**：构建时跑 `--selftest` 数 PASS 行（生成器 / 校验器 / 构建器 / 派生器四个）；
  **发现真实漂移**——页面上手写的「校验器 26 PASS」早已过时（实为 37），
  自动读取后才暴露。② **通道表**：从 `site/channels.json` 生成（原来手写三个 URL）。
  ③ **收录/排除**：本来就从派生 catalogue 读，未变。页脚加 `© 2026 ArchivalEra`。
  **自证期间不跑自证**（`SC_BUILD_SELFTEST=1`）——否则 `build-site --selftest` 会
  调 `build()` ⇒ 自己调自己 ⇒ 递归爆栈（实测踩到，已修）。构建器自证仍 13 PASS。
- **extra-content 已同步 37（2026-11-02）**：`git clone && --selftest` ⇒ `37 PASS`（复跑确认）。
  LLVM 的阻塞**已解除**。他们信里写 `upgrade-manifest-license.py` 是 13 PASS，
  实测 **25 PASS**（数字又漂了 —— 正好印证本节「站点数据自动化」的必要性）。
  **采纳他们建议写进正典 §4.5**：`license` 过了 V11 **≠** 许可写得对 ——
  V11 只挡机械错形，语义正确性必须逐条核。附三次同一夜的实例
  （我两次推断 + extra-content 一次推断，**三次都过了 V11，三次内容都错**）。
- **站点英文闸门 + 废弃契约标注（2026-11-02）**：用户裁定「html 页面不准出现中文」与
  「之前那些 contract 都标成 deprecated」。
  ① `index.html` 全英文（CJK 实测 `0`）；契约 `.md` 正文保留中文（那是内容，不是门面）。
  ② 废弃标注分级：`v0`/`v1`/`v2`/`v3`/`v3-absorption-audit` 标 **DEPRECATED**；
  **`v4` 标 SUPERSEDED IN PART**（V1–V10 仍有效，只是 `schema: 2` 被 v1.1 的 3 取代）——
  一刀切把 v4 标成废弃会误导读者。
  ③ 页面文档列表按横幅自动渲染 `[DEPRECATED]` / `[PARTLY SUPERSEDED]`。
  新闸门 `zreflect/check_site_lang.py`（commit 相位，实测 **ran 10 / off 6 / failed 0**）：
  H1 HTML 无 CJK / H2 **完全废弃**的文档页面必须标（部分取代不强制，否则判据本身错）/
  H3 非权威文档必须有横幅。**两条阴性验证均正确检出**（塞中文、去横幅）。
- **H1 漏洞已补（2026-11-02，线上实测抓到）**：首版闸门只查 `index.html`，
  而**本地构建用的是空兜底 catalogue**（无 excluded）⇒ 永远查不到那条。
  线上真实页面有 **40 个 CJK 字符**，来源是 `sync-catalogue.py` 的中文诊断消息
  （`G5 schema=1（本客户端只认 2/3）`）被直接渲染进排除表。
  修法：① 派生器给每条排除加 `reasons_en`（按闸号分类的英文摘要，中文 reasons
  保留给维护者）；② 页面优先渲染 `reasons_en`；③ 闸门加 **H4**（catalogue 对外
  字段不得含中文、excluded 必须有 `reasons_en`）；④ CI 把派生件同时写到
  `site/catalogue.live.json` 供闸门读（gitignore），并在构建**前**跑闸门。
  **用线上真实 catalogue 验证**：闸门报 6 个问题（H1 40 个 CJK + 5 条缺 reasons_en），
  修复后重跑应全绿。
- **页面精简与字段清理（2026-11-02，用户三轮纠正）**：用户裁定
  「整个页面以及用户实际拉下来的 catalogue 里仅英语 / 协议不准动 / 三个站都有些坏链接 /
  每个 release 都要标许可证且全自动派生 / proxy 那栏去掉 / 保持风格但字数大幅减少」
  +「不要自己造字段，协议里有的复用到页面上，null 就是 null 不要 not declared」。
  结果：页面 CJK=0、可见文字 `5458`（原 `7063`，-23%）、proxy 0 次、
  17 条 release 全部有许可单元格（schema 3 显示 `{id,url}` 可点链接、schema 2 显示 `null`）、
  许可**全部从 manifest 原样抄**（无手写、无推断）。
  自造字段清除：`summary_en`、`reasons_en`、`source_repo`、`tag`（条目内）、`not declared` 展示态。
  excluded 改用协议的词 `reason`（单数英文串）。
  **code review（两轴）抓到 6 个真 bug 并已修**：① `derive` 排序仍读已删的
  `source_repo` ⇒ 任一 release 通过即 `KeyError`；② `reason` 被无条件覆盖成
  `validation failed`（丢了早退路径的原因）；③ H2 调用被误删 ⇒ 闸门假绿；
  ④ `html.escape("&mdash;")` 二次转义印出字面 `&amp;mdash;`；
  ⑤ H4 缺 catalogue 时静默跳过（「没跑 ≠ 通过」）；⑥ 兜底源 note 仍中文。
  闸门 H5 新增：页面 15 条相对链接逐条核对产物内文件（0 死链）；外链不探测
  （本机网络对 GitHub/Cloudflare 不稳，会误判）。
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
| `catalogue_releases` | **0** | 2026-11-02T08:35:20+0800 | `python3 -c "import json;print(len(json.load(open('site/catalogue.json'))['releases']))"` |
| `mail_unread` | **0** | 2026-11-02T08:35:20+0800 | `find mail -maxdepth 1 -name '[0-9]*.md' | wc -l` |
| `site_build_selftest_pass` | **13** | 2026-11-02T08:35:20+0800 | `python3 scripts/build-site.py --selftest 2>/dev/null | grep -c '^PASS'` |
| `specs_md` | **7** | 2026-11-02T08:35:19+0800 | `ls specs/*.md | wc -l` |
| `tool_check_release_selftest_pass` | **37** | 2026-11-02T08:35:20+0800 | `python3 tools/check-release-v4.py --selftest 2>/dev/null | grep -c '^PASS'` |
| `tool_manifest_selftest_pass` | **43** | 2026-11-02T08:35:20+0800 | `python3 tools/make-manifest-v4.py --selftest 2>/dev/null | grep -c '^PASS'` |

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
