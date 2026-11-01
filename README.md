# Static-Contract · 静态分发契约

Octave 集群的**静态分发契约权威仓**：协议正典、工具链、悬案台账、分发站（在建）都在这里。

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
| `site/` | 分发站（在建；方案见 `site/PLAN.md`） |
| `mail/` | 跨仓邮件收件箱（规矩见 `mail/README.md`：只追加不删 / 编号递增 / 投递≠提交） |
| `scripts/` | 读信工具等零依赖脚本 |
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

## 状态

**未试点**：没走完「生产者发 release → 分发方建站 → 消费者改链接」全链。
未决项：U1 codecs 顺序（悬案 05）、U2 chunkSize 按件可配、U3 asset 名 product 前缀、U4 其余仓接入排期。
建站方案与试点验收判据：`site/PLAN.md`。
