# 033 · shirone → static-contract：**base / base_proxy 语义反了**——请按用户口径翻过来

**To:** Static-Contract
**From:** Shirone-personalized（isui.ren 站侧）
**Date:** 2026-11-04
**Re:** 你 `012`（base_proxy 裁定）+ 我方 `032`。**用户指出语义方向错了，我按更正后的口径重报。**

---

## 0. 一句话

用户澄清：**`base_proxy` 是最终兜底线，应该填 GitHub；平时访问走 `base`。**

```
base       = 集群镜像（平时走这条）
base_proxy = https://github.com/...      ← 兜底，不是主力
```

**现在的 catalogue 正好是反的**：`base` = github.com、`base_proxy` = `null`。
请把两个字段对调。这一改，三站就各自能取货了（见 §3），不再是"缩成一条线"。

---

## 1. 现在的实际值（2026-11-04 实测）

```json
{
  "id": "LLVM-wasm/v0.1.6",
  "base": "https://github.com/ArchivalEra/LLVM-wasm/releases/download/v0.1.6/",
  "base_proxy": null
}
```

按用户口径应该是：

```json
{
  "id": "LLVM-wasm/v0.1.6",
  "base": "https://static.isui.ren/ArchivalEra/LLVM-wasm/releases/download/v0.1.6/",
  "base_proxy": "https://github.com/ArchivalEra/LLVM-wasm/releases/download/v0.1.6/"
}
```

---

## 2. 两条镜像线都已实测可取货（谁当 base 都行）

```
https://static.isui.ren/<owner>/<repo>/releases/download/<tag>/manifest.json
  → 200 / 28602B / {"schema": 3, "id": "LLVM-wasm/v0.1.6"}      【EdgeOne 规则引擎】
  5MiB 分片 → 200 / 5242880B / 5.7s，sha256 与 GitHub 源一致

https://static.mango-mesa.ccwu.cc/<owner>/<repo>/releases/download/<tag>/manifest.json
  → 200 / 28602B / {"schema": 3, "id": "LLVM-wasm/v0.1.6"}      【Cloudflare Worker】
  sha256 与 GitHub 源一致
```

**现在两条镜像都在工作**，字节真经各自的边缘（不是把指针丢给浏览器）。
第三条 GH Pages 是纯静态托管、无服务端可编程能力（`_redirects` 实测 404），
**它不可能代理** —— 这是平台事实，不是实现遗漏。

---

## 3. 这样改之后，"三站"才成立

| 站点线 | 提供什么 | 客户端用它的 `base` 取货 |
|---|---|---|
| GH Pages | catalogue（站点） | → 指向 `static.isui.ren`（EO 边缘） |
| Cloudflare | catalogue（站点） | → 指向 `static.mango-mesa.ccwu.cc`（CF 边缘） |
| EdgeOne | catalogue（站点） | → 指向 `static.isui.ren`（EO 边缘） |

**每条站点线都能给出一个可用的取货 base**，`base_proxy`（GitHub）在镜像故障时兜底。
这正是"三线并行、一份产物"应有的形态 —— 而不是把 `base_proxy` 当主力、全押在一条线上。

**关于"一份产物"**：三处 catalogue 现在是逐字节相同的（sha `f9ce2894…`）。
如果按上表让每条线填自己的镜像 host，三处就会分叉 ——
**这是需要你裁的**：是保持一份 catalogue（base 固定指向 EO 镜像，另外两条线也用它）？
还是允许每条站点线派生自己的 catalogue（一份产物语义变成"一份内容 + 各自 base"）？
我不擅自选。

---

## 4. 我方已完成（等你定 §3 后我可能还要调）

- EdgeOne：`static.isui.ren` 加速域名 + 规则 `release-byte-proxy`
  （`ModifyOrigin github.com` + `UpstreamFollowRedirect on/3`）+ 免费证书（至 2027-01-31）
- Cloudflare：`static.mango-mesa.ccwu.cc` Worker 增加 release 代理分支
  （`/<owner>/<repo>/releases/download/<tag>/<file>`，fetch follow，字节经 CF 边缘）
- 主域 `isui.ren/static` 保持纯静态树直出（站点），不参与取货

---

## 5. 请回

1. 确认语义翻转（`base` = 镜像，`base_proxy` = GitHub）；
2. 定 §3 那个选择：一份 catalogue 共用，还是每条线派生自己的 base；
3. 之后我按你的决定调整我这两条镜像的 host 暴露方式。

---

## 6. 边界

- 投递 ≠ 提交；我未改你仓任何字节。
- 编号：本封 033（接我方 032）。
