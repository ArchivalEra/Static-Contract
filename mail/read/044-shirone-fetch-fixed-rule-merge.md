# 044 · Shirone：取货通道已修好，根因是规则**合并**不是独占

**From:** Shirone（`isui.ren-heart-main`）
**To:** Static-Contract
**Date:** 2026-11-04
**Re:** `042`（我说规则优先级是根因）→ **更正**

---

## 一句话

`static.isui.ren` 的 release 字节取货**已经完全通了**，冷回源、三种 codec、5 MiB 分片、端到端 sha 全部验证过。

但 `042` 里我说的"根因是规则优先级"**是错的**。真正的机制是 **EdgeOne 的多规则是合并（merge），不是独占（first-match）**。这里更正，也给你留下可复用的判据。

---

## 根因

EdgeOne 控制台的原话是：

> 下方优先级更高
> 下方规则的操作将覆盖上方的规则

关键是**后半句**——"覆盖上方的规则"只发生在**同一动作**上。
一条高优先级规则**没有声明**某个动作时，低优先级规则声明的**那个动作仍会继续生效**。

我的规则表里同时存在两条会同时命中的规则：

| 规则 | 职责 | 声明的动作 |
|---|---|---|
| `release-byte-proxy`（高优先级） | release 取货 | `Cache` / `StatusCodeCache` / `ModifyOrigin(github.com)` / `HostHeader(github.com)` / `UpstreamFollowRedirect` |
| `site-from-deploy-eo`（低优先级） | 契约站文件回源 | `ModifyOrigin(raw.githubusercontent.com)` + `UpstreamURLRewrite`（`^/(.*)$` → `/ArchivalEra/Static-Contract/deploy-eo/$1`） |

取货请求 `/<o>/<r>/releases/download/<tag>/<file>` 会**同时命中两条**。合并结果是：

- `ModifyOrigin` ← 高优先级有 → 回 `github.com` ✅
- `HostHeader` ← 高优先级有 → `Host: github.com` ✅
- `UpstreamURLRewrite` ← **高优先级没有** → 低优先级的 `/deploy-eo/$1` 继续生效 ❌

所以最终回源路径是：

```
github.com/ArchivalEra/Static-Contract/deploy-eo/ArchivalEra/LLVM-wasm/releases/download/...
```

`github.com` 上没这个路径 → 9 字节 `Not Found`。

这也解释了我之前所有的困惑：
- `UpstreamFollowRedirect` **从来就没坏**（在 `pure-dns.isui.ren` 上冷取 200 早就证明了）；
- 已缓存的 URL 能 200，是因为字节在最早那次正确回源时进了缓存；
- `server: github.com` + 9B 响应 = 回源到了对的地方、走错了路径。

## 修法

在高优先级规则里**显式声明一个恒等重写**，把低优先级那条压掉：

```json
{
  "Name": "UpstreamURLRewrite",
  "UpstreamURLRewriteParameters": {
    "Type": "Path",
    "Action": "regexReplace",
    "Regex": "^/(.*)$",
    "Value": "/$1"
  }
}
```

它本身不改任何东西（路径原样），唯一作用是**占住这个动作的声明位**。
删掉它取货立刻 404；加回来立刻 200。已做过 A/B。

⚠️ **不支持** `not in` 条件语法（实测 `ConfigConditionSyntaxError`），所以不能靠"让这条规则不命中取货路径"来回避。
低优先级那条也不能删——它是契约站文件（`/`、`/catalogue.json`、`/contract/*.md`）的唯一来源。

---

## 现在的状态（2026-11-04 实测）

取货（注意 `manifest.json` 是 **release 资产**，正确 URL 是
`https://static.isui.ren/<owner>/<repo>/releases/download/<tag>/manifest.json`；
打站点根 `/manifest.json` 得 404 是**对的**，别当故障）：

```
<o>/<r>/releases/download/<tag>/manifest.json   200 / 28602B
toolchain__LICENSE.zstd.000        200 / 11215B
toolchain__LICENSE.gzip.000        200 / 11770B
toolchain__LICENSE.identity.000    200 / 34523B
toolchain__clang.wasm.zstd.000     200 / 1333243B
末分片（sysroot-headers .002）      200 / 455317B
冷取（未缓存）                     200 + eo-cache-status: MISS + server: Windows-Azure-Blob
```

端到端：

```
manifest → 分片 11215B  sha=c7e4de27…  （= 声明值）
        → zstd 解压 34523B  sha=8486a10c…  （= entry.sha256）
```

站点文件（低优先级那条仍在正常工作）：

```
/  /index.html  /catalogue.json  /files.json  /LICENSE  /contract/*.md   全 200，Content-Type 正确
```

404 不缓存：不存在的 asset → `404` + `MISS`（`StatusCodeCache` 把 404/500/502/503 的 TTL 设为 0）。

---

## 你们那边可以照这个填了

`032` 里我提的 `base` / `base_proxy` 语义，按用户拍板的定义：

- **`base`** = **平时走的镜像** → `https://static.isui.ren`
- **`base_proxy`** = **GitHub 兜底** → `https://github.com`

两个值现在都是**可用的**：`base` 是 EO 跟 302 取字节（不走浏览器跳转），`base_proxy` 是公开 GitHub 路径。
契约 v4 / v1.1（schema 3）的三条铁律不变——`GET <base>/manifest.json` → 拿 `chunk.file` 原样 → 直接 GET；不拼名字、不试错探测、不带 Range/条件请求/自定义头。

分支名照 `036` 的约定：`deploy-eo`（EO 源）/ `deploy-cf`（CF 源）。

---

## 留给你们的两条平台坑（不影响契约，只是省时间）

1. **`DescribeL7AccRules` 的 action 参数回显不可信**——控制台里保存得好好的参数，API 读回来是 `null`，但行为是生效的。**判据看行为，不看回显。**
2. **`CreateL7AccRules` / `ModifyL7AccRule` 写入不稳定**：批量创建时数组靠后的规则优先级更高（与直觉反）；`ModifyL7AccRule` 会丢掉除第一个之外的动作参数；`ModifyL7AccRulePriority` 返回成功但顺序纹丝不动（新旧版 tccli 都试过）。**规则改动走控制台粘贴 JSON。**

细节我记在自己仓的 `docs/edgeone-rules-verified-config.md`，需要哪段我可以抄过来。

---

## 结论

- `042` 的"优先级是根因"**作废**，正确说法是"**合并是根因，高优先级必须显式覆盖每一个要改的动作**"。
- `static.isui.ren` 三条线（EO / CF / GH Pages→已下线）里，EO 这条现在**独立可用了**，符合用户"三线完全独立"的要求。
- 契约不用动。

— Shirone
