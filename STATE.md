# 活状态（Static-Contract）

这个文件是**活状态文档**（Einfacht 生态格式）：正文只写「现在是什么」，
每条「现在如此」的断言**旁边带复跑方式**（纪律 2 —— 写不出复跑方式的句子只能当历史读）。

> ⚠️ 缺口声明：Einfacht 的台账自动化（`FACTS.json` + `[[键名]]` 引用 + 机器块渲染）
> **尚未对本仓接线**——`zreflect/` 在 `vendor/Einfacht/`，收集器未适配本仓。
> 这是写明的缺口，不是「查过」。接线前本文件按同款纪律人工维护：数字必须在行内可复跑。

## 角色（用户裁定 2026-11-01）

**本仓只是契约维护者；站点不收录任何 release 件（0 字节托管）。
所有的包，要么去 GitHub 拿（release 直链），要么走反代。**
（用户原话：「记住最最核心的，你只是契约维护者，所有的包，要么去github拿，要么走反代，
你需要出一个不收录任何release件的站」。）

这条裁定**已做成构建闸门而非纪律**：`scripts/build-site.py` 产物扫描命中 asset 形状
（`*.<codec>.<NNN>`）或 `releases/` 路径 ⇒ 构建失败清场。
复跑：`python3 scripts/build-site.py --selftest` ⇒ `10 PASS / 0 FAIL`（2026-11-01 本仓实测）。

## 现在是什么

- **正典**：`specs/2026-10-30-release-contract-v4.md`（契约名 v1，manifest `schema: 2`）。
  自 `Octave-Extra-Content` HEAD `9186463` 逐字落库（2026-11-01；拷贝前验过来源三目录 git 干净）。
  v0–v3 与收纳审计是演化史，被否方案判据在正典 §8。**未试点，不宣布稳定。**
- **工具链在库**（落库即实测，2026-11-01。复跑：
  `python3 tools/make-manifest-v4.py --selftest && python3 tools/check-release-v4.py --selftest`）：
  生成器 `43 PASS / 0 fail`，校验器 `26 PASS / 0 fail`（V1–V10 fail-closed）。
  （移交信所载 `40/25` 是信写完后的旧数字，以本仓实测为准——工具在移交后更新过一轮。）
- **站点**：元数据站。产物 = `index.html` + `catalogue.json` + `contract/*.md` +
  `tools/*.py` + `README.md` + `STATE.md` + `maintaince.md`，**无任何 release 件**。
  数据源 `site/catalogue.json`，**当前收录 0 条**（试点链第 1 环未跑）。
  构建复跑：`python3 scripts/build-site.py --out site/dist`（确定性构建，两次逐字节一致，自证覆盖）。
- **部署链**：push main → `sync-deploy` workflow（自证 + 构建 + 0 字节闸门）→
  orphan 单提交强推 `deploy` 分支 → CF Pages / EdgeOne Pages 监听 deploy 自动重建。
  实测：run `41263566662` success（9s，2026-11-01）；deploy 树 11 文件、无父提交、
  提交信息带 main 源 SHA。复跑：`gh run list --workflow sync-deploy --repo ArchivalEra/Static-Contract`
  及 `git fetch origin deploy && git log --oneline origin/deploy`。
  **CF / EdgeOne 尚未接入**（等安排）；反代 `base_proxy` 字段已预留未填。
- **邮件**：001（契约移交）已读归档；往来表见 `mail/README.md`。
- **悬案**：`questions/05`（zstd vs gzip 在 EdgeOne 真链路，各 5 次取中位数）未结。
- **未决项**：U1 codecs 顺序（= 悬案 05）、U2 chunkSize 按件可配、U3 asset 名 product 前缀、
  U4 接入排期——裁定权在本仓（移交信 §5）。

## 试点链验收判据（U4 落地，可勾选）

1. ☐ 生产者（宿主 / extra-content）对真包（候选 `optim 1.6.3`，实测数据现成）**发 GitHub release**
2. ☐ 本站 `catalogue.json` 收录该 release（只记 id + base，不收字节）
3. ☐ 消费者（Octave-UI）从 base（GitHub 直链或反代）拉 manifest + 资产：
   全程普通 GET，逐块 sha + 总 sha 逐字一致
4. ☐ 复跑记录落本仓（数字旁边写复跑方式）
