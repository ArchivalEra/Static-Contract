# 建站方案 · 分发站（2026-11-01 用户裁定版）

> 状态：**裁定已落**。本文是部署形态设计，**不是契约**——契约正典
> `specs/2026-10-30-release-contract-v4.md` 不因本文件改动。

## 0. 核心身份（用户裁定，最最核心）

> **本仓只是契约维护者。本站不收录任何 release 件（0 字节托管）。**
>
> 所有的包，只有两条获取路径：
> **① 去 GitHub 拿（release 直链）；② 走反代（集群边缘）。**

站点是**元数据站**：catalogue（收录了哪些 release、字节从哪个 base 拿）+
契约正典文档 + 工具。**任何包字节出现在产物里 ⇒ 构建失败**（这不是纪律，是闸门，
`scripts/build-site.py` 构建时逐文件检查）。

## 1. 站点内容（全部由 `scripts/build-site.py` 产出）

```
index.html        ← 落地页：身份声明 + catalogue/正典/工具导航
catalogue.json    ← 站点索引：release 元数据（id / base / base_proxy）
contract/*.md     ← 契约正典与演化史（specs/ 逐字拷贝）
tools/*.py        ← 生成器与校验器（tools/ 逐字拷贝）
README.md         ← 仓库地图
```

`catalogue.json` 站方语义（不属契约），条目形状：

```json
{
  "id": "Octave-Full-Wasm/optim-1.6.3",
  "base": "https://github.com/ArchivalEra/Octave-Full-Wasm/releases/download/optim-1.6.3/",
  "base_proxy": null,
  "note": ""
}
```

客户端按契约 §4：`GET <base|base_proxy>manifest.json` → 逐字取 `file` → 普通 GET。
`base` / `base_proxy` 必须 `https://` 且以 `/` 结尾（客户端直接拼 `file`，不带斜杠会拼坏）。

## 2. 部署链（CF + EdgeOne，deploy 分支）

```
main 修改 → sync-deploy workflow（GitHub Actions）
         → 自证 + 构建 site/dist
         → orphan 单提交强推 deploy 分支
         → CF Pages / EdgeOne Pages 监听 deploy → 自动重新部署
```

- **deploy 分支 = 纯站点产物**（根即站点根），每次更新一个无父提交，无历史膨胀。
- 触发：任意 push 到 main（含 workflow_dispatch 手动）。
- 谁改 main 谁触发，部署侧零手工。

## 3. 硬约束（每条带出处）

| 约束 | 出处 |
|---|---|
| **产物禁含 release 件**（asset 名形状 / `releases/` 路径 ⇒ 构建失败） | 本文 §0 裁定；`build-site.py` 闸门 |
| catalogue 的 `base`/`base_proxy` 仅 https 且以 `/` 结尾 | 本文 §1（拼 `file` 的前提） |
| 一切字节走普通 GET：无 Range、无条件请求、无自定义头 | 正典 §4；poc-v4.mjs 实测 0 条件头 |
| 分片 ≤5MiB | 正典 §3 V6；EdgeOne 20MB+ 掉速实测 |
| entry / asset 数无上限 | 正典 §3「无上限」 |

## 4. 试点链验收判据（U4 落地，可勾选）

1. ☐ 生产者（宿主 / extra-content）对真包（候选 `optim 1.6.3`）**发 GitHub release**（manifest + 资产随 release）
2. ☐ 本站 `catalogue.json` 收录该 release（**只记 id + base**，不收字节）
3. ☐ 消费者（Octave-UI）从 base（GitHub 直链，或反代 `base_proxy`）拉 manifest + 资产，全程普通 GET，sha 逐字一致
4. ☐ 复跑记录落本仓（纪律 2：数字旁边写复跑方式）

## 5. 下一步

1. 部署侧：CF Pages / EdgeOne Pages 接 deploy 分支（等安排）；反代 base（`base_proxy`）随部署裁定
2. 试点链第 1 环：宿主仓对 `optim 1.6.3` 发 release → 本站 catalogue 收录 → 消费者改链接
3. 悬案 05（zstd vs gzip）在反代真链路上结案：各跑 5 次取中位数
