# maintaince.md · 方向与地图（Static-Contract）

本文件**只指明方向与边界**，不抄数字、不抄流程 —— 测出来的现状由
`STATE.md`（活状态，断言旁带复跑方式）承载，使用方法由 `README.md` 承载。
抄了就会漂：工具自己会说话（构建闸门会红、自证会数、git 会记账），听它们
比读本文件的任何细节都可靠。（Einfacht 生态格式；台账自动化未接线，
见 `STATE.md` 顶部的缺口声明。）

## 这个项目是什么

Octave 集群的**静态分发契约权威仓**：协议正典 + 工具链 + 元数据站 + 悬案台账。
**apt 的稳健 + HTTP 的简洁。** 本仓只是契约维护者——站点 0 字节托管，
包字节只走 GitHub 直链或反代（裁定原话与闸门见 `STATE.md`）。

## 地图（真值在哪里）

| 想知道 | 去哪 |
|---|---|
| 现在是什么 | `STATE.md`（活状态） |
| 协议怎么用 | `README.md`；正典 `specs/2026-10-30-release-contract-v4.md`（§4 客户端算法） |
| 协议什么改不得 | 正典 §3 不变量 V1–V10 + §8 被否方案判据 |
| 站点收录了什么 | `site/catalogue.json`（唯一数据源，构建器只读它） |
| 站点长什么样 | `scripts/build-site.py`（产物清单与闸门都在声明里） |
| 悬案 | `questions/`（每条挂结算判据；05 未结） |
| 跨仓通信 | `mail/`（规矩：只追加不删 / 编号递增 / 投递≠提交） |
| 反幻觉系统本体 | `vendor/Einfacht/`（上游 `6e4e6e8`，快照 vendor） |

## 维护边界

**归本仓**：
- schema 定义与演进（`schema: 2` → 未来版本）
- V1–V10 不变量的增删改
- asset 名白名单收紧/放松（**必须先实测平台改写面再改**——正典 §1 的实测表是唯一依据）
- catalogue 收录判据与 0 字节闸门
- 各仓接入的验收判据

**不归本仓**（各归其主，勿越界）：
- 内容语义（`form`/`content`/`consumer` 轴、版本策略、许可台账）→ `Octave-Extra-Content`
- 引擎产物与构建事实（`octave.build.json`）→ 宿主 `Octave-Full-Wasm`
- 站点装配与路由（Astro base / 字面量重写）→ `Octave-UI`
- 边缘与反代（EdgeOne / isui.ren）→ `Shirone-personalized`

## 例行

- **收录一个 release**：向 `site/catalogue.json` 加条目
  （`id` 唯一无空白；`base` / `base_proxy` 必须 `https://` 且以 `/` 结尾）
  → push main。`sync-deploy` 自动重建 deploy，部署侧零手工。
- **改正典**：先开 `questions/` 悬案（挂可执行结算判据）→ 裁定 → 改正典，
  并在 `STATE.md` 记裁定原话与日期。**被否方案判据必须留在正典 §8，防将来重开。**
- **红线**：任何 release 件（tar/zip/wasm/whl/分片）不进 main，也不进 deploy——
  构建闸门会红（`scripts/build-site.py` 产物扫描）。
- **部署出口**：deploy 分支 = 纯站点产物（orphan 单提交），只由 workflow 写，
  任何人不手工碰它。
