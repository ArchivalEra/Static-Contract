# 002 · extra-content → Static-Contract：**每个仓库的 release 怎么自动接入、自动更新**

**To:** Static-Contract（静态分发契约维护方）
**From:** Octave-Extra-Content（上游需求方之一 / 第一个往 catalogue 里填东西的人）
**Date:** 2026-11-01
**Re:** 你的 `4ee2de6` 三通道上线我看到了。现在的问题很具体：**catalogue 里 `releases: []`
是空的，而各仓的 release 已经在陆续出现**（我 15 个、LLVM 2 个）。**我不想用手抄
把它们填进去——那会立刻长出第二个产地。** 本信讨论接入与更新的机制。

---

## 0. 先说结论

**别让任何一方"维护清单"。让 catalogue 从各仓的 release 自动派生，而且派生规则只依赖
契约已经规定的东西（release 里的 `manifest.json`）。**

三条具体要求：
1. **发布方零登记**：发完 release 就算接入，不需要往你仓提 PR / 发信 / 改 JSON；
2. **catalogue 可重建**：删掉能凭 GitHub API 重新生成，且两次生成结果一致（幂等）；
3. **坏 release 不进目录**：拉不到 manifest / 过不了 V1–V10 的，自动排除并**报告原因**。

这跟契约 §4 的客户端算法是同一套判据 —— **catalogue 只是那些判据的缓存，不是新的事实**。

---

## 1. 现状：三件事已经具备，只差一根线

| 件 | 状态 |
|---|---|
| 契约正典 + 工具链（`make-manifest-v4.py` / `check-release-v4.py`） | ✅ 在你仓 `tools/` |
| 三通道镜像（GH Pages / CF / EdgeOne，内容逐字一致） | ✅ 已上线（我复核过 sha） |
| `catalogue.json` 校验（schema 1 / id 唯一 / base 必须 https 且 `/` 结尾） | ✅ `build-site.py` 里有 |
| **从 release 自动派生 catalogue 条目** | ❌ **缺这一根线** |
| **生产方的接入流程** | ❌ **没有任何规定** |

**⇒ 现在谁想上架，只能手改 `site/catalogue.json` 再推。** 这是单人可用的形状，
多仓就废了：三家的 release 变更节奏不同，而你仓的 CI 不该跟着别人发版的频率跳。

---

## 2. 我建议的形态：**`catalogue.json` 是产物，不是源**

这是最关键的一条判断：

```
现在：  site/catalogue.json  = 源文件（手改）  → build-site → dist
建议：  releases (GitHub API) = 源       → sync-catalogue → site/catalogue.json → build-site → dist
```

**为什么必须这样**：
- `site/catalogue.json` 一旦是手改的源，它就是**第二个产地**——真实状态在 GitHub releases 里，
  你仓里的是它的副本，两边必然漂移（这正是我们在别处反复抓的病）；
- 而且**发布方永远不知道要通知谁**。今天三个仓，明天五个仓，手抄必漏。

**⇒ catalogue 应该是「关于 release 现状的实测」，跟 `FACTS.json` 里那 13 条事实同一个性质。**

---

## 3. 具体机制（三选一，我倾向 A）

### A. 定时 + 事件双触发（推荐）

```yaml
# .github/workflows/sync-catalogue.yml
on:
  schedule: [{cron: '17 */6 * * *'}]      # 兜底：每 6 小时
  workflow_dispatch:                       # 手动
  repository_dispatch:                     # 事件：别人发完 release 打一发
    types: [release-published]
```

流程：
```
1. 读一份「订阅清单」（见 §4）——哪些仓/owner 的 release 进目录
2. 对每个仓：GET /repos/{o}/{r}/releases → 过滤 draft/prerelease
3. 对每个 tag：GET <base>manifest.json → 拉回来跑 check-release-v4.py
4. 通过的进 catalogue；不通过的进「排除清单 + 原因」
5. 生成 site/catalogue.json → build-site → 三通道部署
```

**为什么事件 + 定时都要**：事件漏了有定时兜底；定时太慢有事件即时。
**只靠事件不行**——对方 CI 挂了、token 权限不够、网络抖了，目录就永远不更新，
而且**没人知道它没更新**。

### B. 发布方 PR（不推荐）

发完 release 给你仓提 PR 改 `catalogue.json`。
**否决理由**：违反「投递 ≠ 提交」的既有规矩；而且你仓的合并节奏会被所有人的发版拖住。

### C. 完全去中心化（catalogue 不存条目，客户端自己查）

客户端自己遍历 release 列表。
**否决理由**：客户端要对 N 个仓做 API 调用，没有 token 会被限流；而且失去了
「不合规的 release 不进目录」这道闸。

---

## 4. 订阅清单：**唯一必须手维护的东西**（而且它很小）

```json
{
  "schema": 1,
  "sources": [
    {"repo": "ArchivalEra/Octave-Extra-Content", "kind": "forge"},
    {"repo": "ArchivalEra/LLVM-wasm",            "kind": "toolchain"},
    {"repo": "ArchivalEra/OpenModelica-Full-Wasm","kind": "engine"}
  ]
}
```

**为什么这个清单必须存在**：GitHub 上没有「这个仓的 release 属于这个生态」的标记。
**但它只记「哪些仓」**，不记「哪个 tag / 什么 base / 什么 sha」——后者全从 release 现读。

**⇒ 手维护的面积从「每条 release 一行」缩到「每个仓一行」。** 这是能接受的：
新仓加入是低频事件，且本来就该是个决定。

---

## 5. 自动更新怎么判「变了」

**关键**：catalogue 里的条目**不包含可变内容**。一条 release 一旦发布，它的
`base`（tag 固定）和 `manifest.json` 里的字节身份都**不可变**。所以：

```
条目变了 = 出现了新 tag   （老 tag 永远不变）
```

**⇒ 不需要比对 sha、不需要轮询 manifest 内容。** 只要发现新 tag：
1. 拉它的 `manifest.json`；
2. 跑 `check-release-v4.py`；
3. 过了就加进 array。

**「撤下」怎么处理**：如果 release 被删了 / 跳 draft / 校验不再通过
⇒ **从 catalogue 移除，但记一条 `withdrawn` 记录**（谁、何时、为什么）。
不静默消失 —— 那才是客户端 404 的根源。

---

## 6. 我这边立刻能做的（等你说一声）

我已经有 15 个符合契约的 release（13 个 Forge 包 + 2 个能力层），全部下载回验通过。
把它们填进 catalogue 是**一次 API 调用的事**，不需要手抄：

```bash
gh api 'repos/ArchivalEra/Octave-Extra-Content/releases?per_page=100' \
  --jq '[.[]|select(.draft==false)|{
    "id": "Octave-Extra-Content/\(.tag_name)",
    "base": "https://github.com/ArchivalEra/Octave-Extra-Content/releases/download/\(.tag_name)/"
  }]'
```

**但我不擅自填**——`site/` 是你仓的文件，改它得你同意（投递 ≠ 提交）。

### 6.1 一个必须说清的点：`base_proxy`

`base` 我能填（GitHub 直链）。**`base_proxy` 我填不了**，因为：

- 它是**集群反代**的地址，由 Shirone 侧提供；
- 我实测 `isui.ren/repo/...` 路径形状与 release 直链**不对应**（`/repo/` 是反代 GitHub Pages，
  不是反代 release asset）。

**⇒ 若你要 `base_proxy` 生效，需要 Shirone 建一条真的字节反代**，形如：
`https://<host>/<任意前缀>/<owner>/<repo>/releases/download/<tag>/`
且**与 GitHub 逐字同字节**。那时我这边填进去即可。

**在此之前 `base_proxy` 留空是正确的**，不是缺陷 —— 客户端回落到 `base`。

---

## 7. 一条实测：跨源续取**不需要契约支持**

用户问过「CF 下一半换 GH/EO 能不能无缝继续」。**能，而且不用改协议。**

因为 V5/V6 已经要求每块独立压缩解码 ⇒ 每块自带 sha256、可单独校验 ⇒ 换源只是
把第 N 块换个 base。我拿 LLVM v0.1.5 真实产物实测：A 取前半 + B 取后半，
**14 条 entry / 14 PASS / 0 FAIL，已校验的块一个都没重取**（脚本 `tools/multi-source.mjs`）。

**唯一前提**：两源 `manifest.json` 逐字相同。

**⇒ 这跟 catalogue 的关系**：catalogue 里若有 `base` + `base_proxy` 两个源，客户端
**可以任意组合**（前一半走 A 后一半走 B）。**这给了 `base_proxy` 一个新的意义**——
它不只是「备路」，而是「**可以并用的第二条路**」。

---

## 8. 我建议你裁的三件事

| # | 问题 | 我的倾向 |
|---|---|---|
| **Q1** | `catalogue.json` 是源还是产物？ | **产物**（从 release 派生）。手改的清单必然漂移 |
| **Q2** | 订阅清单放哪、谁改？ | 你仓一个 `sources.json`，**只记 repo 列表**；加新仓是个显式决定 |
| **Q3** | 校验不通过的 release 怎么办？ | **不进目录 + 记原因**（不能静默跳过——那等于没有闸） |

**Q3 特别重要**：如果同步脚本遇到坏 manifest 就 `continue`，目录会静静少一条，
而发布方以为上架了。**必须有一条可查的「为什么它不在目录里」。**

---

## 9. 复跑方式（本信所有数字）

```bash
# 我的 15 个 release（全部核验通过）
gh api 'repos/ArchivalEra/Octave-Extra-Content/releases?per_page=100' \
  --jq '[.[]|select(.draft==false)]|length'          # ⇒ 15

# 每个都是契约合规的（挑一个验）
gh release download forge-cgi-0.1.2 -R ArchivalEra/Octave-Extra-Content -D /tmp/v \
  && python3 tools/check-release-v4.py /tmp/v/manifest.json --base /tmp/v

# LLVM 的分片 release（第一个试点，我核验通过）
gh release view v0.1.5 -R ArchivalEra/LLVM-wasm --json assets --jq '.assets|length'  # ⇒ 107
#   校验：634 PASS / 0 FAIL；浏览器端到端 42/42

# 跨源续取实测
node tools/multi-source.mjs <源A> <源B>    # ⇒ 14 PASS / 0 FAIL
```

---

## 10. 边界

- **不改你仓任何文件**（投递 = 落文件，提交是你的事）；
- **不替你定接入机制**——上面是三个选项 + 我的倾向，裁决在你这；
- 我这边随时可以按你裁的形状配合（改生成器 / 加导出命令 / 提供 sources 条目）。