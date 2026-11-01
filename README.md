# Static-Contract · 静态分发契约

Octave 集群的**静态分发契约权威仓**：协议正典、工具链、悬案台账、元数据站都在这里。

> **身份裁定（最最核心）：本仓只是契约维护者。站点不收录任何 release 件（0 字节托管）；
> 所有的包，要么去 GitHub 拿（release 直链），要么走反代（集群边缘）。**

> **一个 release = 一个不可变 tag = 一份 `manifest.json` + N 个扁平 asset。**
> 名字只允许 GitHub 不会改写的字符（白名单）⇒ `manifest.file` 与真实 asset 名恒等。
> 客户端只从 manifest 取名字，绝不拼 ⇒ 404 只有一种含义。一切字节走普通 GET。
>
> **目标：apt 的稳健 + HTTP 的简洁。**

## 正典

**`specs/2026-10-30-release-contract-v4.md`** —— 契约定名 **v1**（manifest `schema: 2`）。
四轮 design-it-twice 的收敛结果；v0–v3 与收纳审计是演化史，**被否方案的判据留在正典 §8，
防止将来重开**。移交给本仓时正典从未试点，**不宣布稳定**。

## 工具链（实测快照 2026-11-01，本仓实测）

| 工具 | 自证 | 说明 |
|---|---|---|
| `tools/make-manifest-v4.py` | **43 PASS / 0 fail** | 生成器：切块 → 每块独立压缩 → sha → manifest；白名单反向断言、失败即清场 |
| `tools/check-release-v4.py` | **26 PASS / 0 fail** | 校验器：V1–V10 fail-closed；带 `--base` 时逐块对盘核 bytes+sha |

复跑：`python3 tools/make-manifest-v4.py --selftest && python3 tools/check-release-v4.py --selftest`

## 目录地图

| 目录 | 内容 |
|---|---|
| `specs/` | 契约正典（v4）+ v0–v3 演化史 + 收纳审计（自 Octave-Extra-Content 移交，原始材料未改） |
| `tools/` | v4 生成器与校验器（同上） |
| `questions/` | 悬案台账（`05`：zstd vs gzip 在 EdgeOne 真链路的实测裁决） |
| `STATE.md` | 活状态（Einfacht 生态格式：只写「现在是什么」，断言旁带复跑方式） |
| `maintaince.md` | 方向与地图（维护边界 / 例行 / 红线） |
| `site/` | 元数据站数据源（`catalogue.json`；**不收录任何 release 件**） |
| `zreflect/` | Einfacht 事实系统平台（自 `vendor/Einfacht` `6e4e6e8`）+ 本仓数据层收集器；台账 `FACTS.json`（**别手改**，跑 `zreflect/facts.py`） |
| `reflect-hooks/` | git 钩子与旋钮载体（装：`sh reflect-hooks/install.sh`；pre-commit 重渲染机器块 + commit 相位全部闸门） |
| `mail/` | 跨仓邮件收件箱（规矩见 `mail/README.md`：只追加不删 / 编号递增 / 投递≠提交） |
| `scripts/` | 零依赖脚本：`mail-read.py`（读信）、`build-site.py`（建站，构建器自证 10/10） |
| `vendor/Einfacht` | 反幻觉事实系统套件（上游 `6e4e6e8`，快照 vendor） |

## 本仓在集群里的位置

| 仓 | 关系 |
|---|---|
| `Octave-Extra-Content` | 内容语义产地；本契约的前作者，现退为上游需求方 |
| `Octave-Full-Wasm` | 宿主：引擎产物与构建事实（`octave.build.json`）；站点装配 |
| `Octave-UI` | 消费端：包管理器、下载管理 |
| `OpenModelica-Full-Wasm` | 第二引擎产地 |
| `Shirone-personalized` | isui.ren 站侧：反代与边缘（EdgeOne） |

## 纪律（继承自集群实测教训）

1. **「测不到」≠「不存在」**——任何「不存在」的结论，必须先有同类肯定用例证明探针有效。
2. **数值/行为只认实测，复跑方式写在断言旁边**。写不出复跑方式的句子只能当历史读。
3. **机器块是机器维护的**——`STATE.md` 文末块由 `zreflect/facts.py --render-doc` 渲染，
   正文数字只许 `[[键名]]` 引用；闸门执行面读声明（`registry --run commit`），off 不是通过。
4. **推送纪律**——`README.md` 随每批推送同批更新（pre-push 与 CI 同判据，单条目不退化）；
   `--no-verify` 只能躲过本地，CI 是正面落点。

## 状态

**未试点**：没走完「生产者发 release → catalogue 收录 → 消费者改链接」全链。
未决项：U1 codecs 顺序（悬案 05）、U2 chunkSize 按件可配、U3 asset 名 product 前缀、U4 其余仓接入排期。

**部署**：deploy 分支 = 纯站点产物，CF Pages / EdgeOne Pages 的部署出口。
自动更新链：push main → `sync-deploy` workflow（构建器自证 + 构建 + 0 字节闸门）→ orphan 强推 deploy → 托管方自动重建。
CI：`gates` workflow 跑与本地钩子同一判据（事实块对账 + 名录全闸门 + 模块自证），
环境侧显式装 `zstandard`（生成器自证的仪器）并加载 `reflect-hooks/einfacht-env.sh`（旋钮来源）。

现状与试点验收判据：`STATE.md`；方向、边界与例行：`maintaince.md`。
