# 发布契约 v3 · 初代（定稿候选）

> ## ⛔ DEPRECATED — 历史文档，不是权威（2026-11-02 标注）
>
> 本文**从未投递、从未进任何 schema、从未推广**，已被后续版本取代。
> **现行权威 = `specs/2026-10-30-release-contract-v4.md`（V1–V10 基础条款）
> + `specs/2026-11-01-release-contract-v1.1-license.md`（V11 许可，schema 3）**。
> 保留本文的唯一理由是**被否方案的判据**（防止将来重开）——不要照它实现。

> ## ⚠️ 历史文档 —— 已被取代，不是权威（2026-11-01 标注）
>
> **现行权威 = v1**（本仓副本 `specs/2026-10-30-release-contract-v4.md`，权威文本在
> `ArchivalEra/Static-Contract`）。v3 是**四轮 design-it-twice 中的第三轮**，保留了当时的
> 结构与判据，**不要按它实现**。
>
> **特别提醒：R1–R4（§4.1）没有进入 v1。** 现行 v1 契约里查不到任何对冲/并发判据
> （`grep -c "对冲|hedge|R2|R3"` ⇒ 0）。R1–R4 今日的地位是**实现建议与实测数据**，
> 不是契约不变量——并发与对冲属于消费端实现策略，v1 管的是「manifest 长什么样、怎么取字节」。
>
> **其中 R3（「禁止在 EdgeOne 中间件内对冲」）已于 2026-10-31 被 Shirone 本人翻案**：
> 复测 20/20 有效（最慢 4.75s，兜底上限 17.5s 一次未触发）。见其 `118` 勘误与本仓 `131` 回信。
> **一次测量配不上「禁止」级结论**——这正是本仓纪律 5（断言有生命周期）的实例。

---

> **状态（当时）**：v3 = v2 定稿 + Shirone `117` 确认的 R1–R4 + 一条体积口径勘误（我错了，已改）。
> **两仓共识已达成**（我 `116` / Shirone `117`）：R1–R4 逐字定稿、初代只出
> zstd+gzip+identity、`chunkSize` 默认 5 MiB 可配且上限 ≤10 MiB。
> **仍待用户批准开始试点**（§10 第 3 步）。
>
> **v1 → v2 的改动（全部来自用户纠正 + 我实测）**：
> 1. **砍掉 Range 全族**——预分片让 Range 不必要。用户点破：「最终用户拉的仅仅只是一个
>    没多少头的标准请求」。实测浏览器 PoC 已证明：普通 GET × 并发即可。
> 2. **砍掉 seek table / `range.basis` / `granularity`**——那是我自创的，违反
>    「不要想太多自创东西」。
> 3. **`variants` 改为有序数组**（回退链是**数据**不是代码分支）：加新格式 = 数组加一项，
>    schema 一个字不改。这是让协议「永远不需要更新」的机制。
> 4. **初代只开 zstd + gzip + identity，不开 br**（用户裁定：**不是不支持，是初代不开**）。
> 5. **格式协商交还给 HTTP**（`Accept-Encoding`）——**我们不管**。

---

## 0. 一句话

> **一个 release = 一个不可变目录。`manifest.json` 是唯一入口。
> 所有字节都是普通文件、普通 GET。**
>
> 用户侧的唯一动作：`fetch(manifest)` → 按 `variants` 顺序挑一个能解的 → 并发拉块 → 拼 → 校验。
> **没有 Range、没有条件请求、没有自定义头、没有协商协议。**

---

## 1. 实测依据（每条都是可复跑的判据）

### 1.1 浏览器解压能力（这决定「谁能当兜底」）

```
DecompressionStream('gzip')     ✅ 原生
DecompressionStream('deflate')  ✅ 原生
DecompressionStream('br')       ❌ 不支持
DecompressionStream('zstd')     ❌ 不支持
```

⇒ **gzip 是唯一零依赖的兜底**；zstd/br 都必须带外挂解码器。

### 1.2 解码器体积

| 编码 | 解码器 | 分发音 | 原始 | gzip -9 | 形态判据 |
|---|---|---|---|---|---|
| gzip | 浏览器原生 | — | 0 | **0** | `DecompressionStream('gzip')` ✅ |
| **zstd** | `fzstd@0.1.1` | **ESM** | 24,407 | **6,840** | `exports.import=esm/index.mjs`；esm 零 `import`、`dependencies` 空 |
| zstd | 同上 | UMD | 8,394 | 3,860 | 仅当消费端用 UMD 时 |
| br | 需 wasm（如 `brotli-wasm`） | — | ~100KB+ | 未测 | 初代不开 |

**★ 体积口径勘误（2026-10-30，Shirone `117` 纠我、我复验确认）**：
官方 README 的「8kB minified and 3.8kB after gzipping」指的是 **UMD** 产物。
**走 ESM 的消费端实际负担是 6,840 B（gzip 后），不是 3,860 B——差 77%。**
我此前把 UMD 的数字当成 ESM 的，错了。本契约一律按 **ESM = 6.8KB** 计。

复跑：
```bash
npm pack fzstd && tar xzf fzstd-0.1.1.tgz
for f in esm/index.mjs lib/index.js umd/index.js; do
  printf '%-16s raw=%-7s gz9=%s\n' "$f" "$(stat -c%s package/$f)" "$(gzip -9 -c package/$f | wc -c)"
done
# ⇒ esm 24407/6840 · lib 24454/6857 · umd 8394/3860
```

### 1.3 三种编码的压缩/解压（74.5MB wasm，5MiB × 15 块）

| 编码 | 预分片总计 | 压缩耗时(8 核并行) | 解压耗时 | 解压吞吐 |
|---|---|---|---|---|
| **zstd-19** | **15,349,112** | **3.7s** | **0.07s** | **1022 MB/s** |
| gzip-9 | 20,908,462 | 5.0s | 0.21s | 363 MB/s |
| br-q11 | 14,332,389 | 21.5s | 0.16s | 459 MB/s |
| identity | 74,579,404 | — | — | — |

**判读**：
- zstd 比 gzip 小 **26.6%**，解压快 **2.8×**，压缩快 **0.74×**（都够快）⇒ **当第一顺位**；
- br 只比 zstd 小 **6.6%**，但解码器重 30 倍、解压慢 2.2× ⇒ **初代不开，不是不支持**
  （用户裁定：留位，不占初代复杂度）；
- gzip 体积最差但**零依赖** ⇒ 兜底。

### 1.4 并发收益（每连接 1.5MB/s + 80ms RTT，模拟真实 CDN）

```
conc=1   拉取 11,519ms
conc=2   拉取  5,800ms   1.99×
conc=4   拉取  3,175ms   3.63×
conc=8   拉取  2,354ms   4.89×   ← 拐点
conc=15  拉取  2,359ms   4.88×   ← 不再涨（15 块 ÷ 8 = 2 轮，第二轮吃不饱）
```

⇒ **默认并发 = 8**（拐点），且**并发数不应超过块数**。

### 1.5 PoC 已跑通（浏览器真环境，全链路）

```
用户动作：fetch(manifest.json) → 6 并发 fetch(chunk) → 逐块 sha → 解码 → 拼接 → 全局 sha
结果：15/15 块，74,579,404 B，sha 8287589e…b001 == 期望   ✅ PASS
zstd 变体：解码器加载 7ms，全程 606ms
gzip 变体：全程 522ms（零解码器）
```

### 1.6 ★ zstd 的一个安全边界（必须写进契约）

`fzstd` README 原话：

> only supports a maximum backreference distance of **2^25 (32 MiB)** bytes. If you need to
> decompress files with an "ultra" compression level (**20 or greater**) AND if your files can
> be **above 32MB decompressed**, `fzstd` *might* fail to decompress properly.

**对我们的场景不适用**，因为**我们分片**：

```
单块 = 5,242,880 B (2^23) < 2^25 (33,554,432 B)  ⇒ 安全
且分块压缩本就没有跨块 backreference ⇒ 与 level 无关
```

⇒ **契约里写成不变量**（见 I6）：分块编码时 `chunkSize ≤ 2^25`，且**必须按块独立压缩**。
这条同时约束了「未来谁想改 chunkSize 调大」的自由。

---

## 2. 产物形状（**Release assets，扁平命名**）

> ★ **硬约束（2026-10-30 实测）**：GitHub Release 的 asset 名**会被拍平**——
> `gh release upload .../chunks/zstd/000.zst` 落成的 asset 名是 **`000.zst`**（路径丢失）。
> 所以**不能**用 `chunks/zstd/NNN.zst` 这种带斜杠的路径作为 asset 名。
> **分片身份改由「asset 名的命名约定」承载**（下表）。

```
Release <repo>@<tag> 的 assets（全部扁平，同层）：
  manifest.json                      ← 唯一元数据入口
  <asset>.zstd.000 … <asset>.zstd.NNN   ← zstd 分片（命名约定：<资产名>.zstd.<序号>）
  <asset>.gzip.000 … <asset>.gzip.NNN   ← gzip 分片
  <asset>                            ← identity 原文件（兜底）
```

**为什么能这么命名**：asset 名允许 `[a-zA-Z0-9._-]`，点号是合法分隔符。
`OpenModelicaCompiler_bg.wasm.zstd.000` 既扁平又可解析（`<name>.<codec>.<i>`）。

**解析规则（消费端）**：manifest 里的 `chunks[].file` 就是**asset 名**（纯文件名，无路径），
消费端把它拼到 base URL 后面即可。**base URL 由分发方（static 站/反代）提供，
不是我们定义**——这样同一份 release 可以被任意反代挂到任意路径前缀下。

**不提供 `latest` 别名**——那是「永续更新」的入口。「永不更新」的强制就在 tag 上。

**sidecar 整文件形态（可选，给不并发的小件用）**：
```
<repo>/<tag>/<asset>                  ← identity 原文件
<repo>/<tag>/<asset>.zst              ← 整块 zstd
<repo>/<tag>/<asset>.gz               ← 整块 gzip
```

---

## 3. manifest（初代全形状）

```json
{
  "schema": 1,
  "id": "OpenModelica-Full-Wasm/v0.1.0-wasm32",
  "assets": {
    "OpenModelicaCompiler_bg.wasm": {
      "role": "engine",
      "contentType": "application/wasm",
      "bytes": 74579404,
      "sha256": "8287589e…b001",
      "variants": [
        { "codec": "zstd", "decoder": "fzstd@0.1.1", "decoderBytes": 6840,
          "decoderForm": "esm", "totalBytes": 15349112,
          "chunked": true, "chunkSize": 5242880,
          "chunks": [ { "i": 0,
                        "file": "OpenModelicaCompiler_bg.wasm.zstd.000",
                        "bytes": 1275256, "sha256": "…" }, … ] },
        { "codec": "gzip", "totalBytes": 20908462, "chunked": true, "chunkSize": 5242880,
          "chunks": [ … ] },
        { "codec": "identity", "totalBytes": 74579404, "chunked": false,
          "file": "OpenModelicaCompiler_bg.wasm" }
      ]
    },
    "msl-4.1.0-maint.om.zip": {
      "role": "package", "contentType": "application/zip",
      "bytes": 19482938, "sha256": "a97d8d94…8535",
      "variants": [ … ]
    }
  }
}
```

### ★ 多资产（2026-10-30 补：v3 初稿只能描述**一个**资产，而 OM 的 release 实测有 **2 个**）

**`assets` 是 map（资产名 → 该资产的身份与变体）**，不是单个对象。
理由（deletion test）：删掉这一层，一个含 2 个资产的 release 就只能描述一件 ⇒
消费端要么拿不到另一件、要么得猜它的名字。**OM 的 `v0.1.0-wasm32` 现有 2 个 asset
（wasm + MSL zip）、UI `dist` 有 21 个 wasm**——单资产形状覆盖不了现实。

**资产名 = Release asset 的基线名**（分片 asset 名在此基础上加 `.<codec>.<i>` 后缀）。
消费端先读 manifest 的 `assets`（知道有哪些资产），再按需取某个资产的 `variants`。

### 3.1 字段必要性（deletion test）

| 字段 | 删了会怎样 | 留？ |
|---|---|---|
| `bytes` + `sha256`（顶层） | 边缘**无 Digest 头**（实测 `curl -sI` 无任何 digest）⇒ 消费端**无法**验证最终完整性 | **必留** |
| `variants`（有序数组） | 只能靠试错（先试 zstd 404 再试 gzip…）= N 次往返，且「404」与「真没有」分不开 | **必留** |
| `chunks[].sha256` | 乱序并发最常见的错（少一片/重复/错位）无法定位，只能整体重来 | **必留** |
| `chunks[].bytes` | 同上，且 `Content-Length` 可能被中转改写 | **留** |
| `chunkSize` | 消费端无法推导「一共有几块」以外的东西；且 I6 要靠它判安全边界 | **留** |
| `codec` | 不知道用什么解 | **必留** |
| `decoder` / `decoderBytes` | 消费端不知道要加载什么/值不值 | **留（可选）** |
| `id` | manifest 自身身份；缓存键 | **留** |
| ~~`range`~~ | 预分片后不需要 Range | **删** |
| ~~`seekTable`~~ | 同上 | **删** |
| ~~`contentEncoding`~~ | `codec` 已表达；HTTP 层的事不重复 | **删** |
| ~~`url`（每块绝对 URL）~~ | 可由 `id` + `file` 推导 | **删** |

### 3.2 不变量（校验器逐条判，fail-closed）

| # | 不变量 | 反例 |
|---|---|---|
| **I1** | **每个资产**的 `bytes`/`sha256` = 该资产**全部块解码拼接后**的字节与哈希 | 写成"某编码层"的 sha；或把两个资产混成一个 |
| **I2** | `chunks[].sha256` 是**该编码块的字节** sha | 写原始 sha |
| **I3** | 每个 `chunks[].bytes` 之和 == `variants[].totalBytes` | 声明与实际不符 |
| **I4** | **每个资产**的 `variants` 非空，且**恰有一个** `codec:"identity"` 作为末位兜底 | 全是压缩格式（解不了就无路可走） |
| **I5** | `chunked:true` ⇒ `chunkSize` 必填且 `chunks` 非空；`chunked:false` ⇒ 有 `file` 无 `chunks` | 半截状态 |
| **I6** | ★`chunked:true` ⇒ `chunkSize ≤ 2^25`（fzstd 安全边界）**且建议 ≤ 10 MiB**（实测降速点在 10–20MB 之间；默认 5 MiB）+ 块必须**独立压缩** | 块 > 32MiB 且 level≥20 ⇒ fzstd 可能解不出；块 > 10MiB ⇒ 落进降速区 |
| **I7** | `codec` 是**开放字符串**（不是枚举） | 加 br/xz/lz4 时要改 schema |

---

## 4. 消费端算法（初代，伪码）

```
man = GET <dir>/manifest.json                       // 1 个请求，可永久缓存
for v of man.variants:                              // 按声明顺序（回退链）
    dec = {
      "gzip":  () => nativeGzip,                     // 零成本
      "zstd":  () => import(fzstd),                  // 6.8KB (ESM, gzip 后；不是 3.8KB)
      "identity": () => null,
    }[v.codec]
    if (dec === undefined) continue                  // 不认识的编码 ⇒ 跳过（前向兼容）
    try:
        parts = await Promise.all(                   // ★ 并发，默认 8
          v.chunks.map(c => fetch(c.file)            
            .then(r => r.arrayBuffer())
            .then(b => { assert sha256(b) === c.sha256  // 逐块校验（错一块只重拉一块）
                         return decode(b) })))
        all = concat(parts)
        assert all.length === man.bytes && sha256(all) === man.sha256
        return all                                   // ✅
    catch: continue                                  // 这一档坏了 ⇒ 下一档
throw NO_USABLE_VARIANT                              // 全试完才失败（响亮）
```

**三条设计要点**：
1. **`dec === undefined ⇒ continue`** 是**前向兼容**的关键——未来 manifest 里出现
   我们不认识的 `codec`（比如 `xz`），旧客户端会**跳过它、用后面的**，而不是崩。
   **这就是"加新格式不需要改协议"的落地点**；
2. **逐块校验 + 逐块重试**：只重拉坏的那块，不整体重来；
3. **两道校验**：块级（防拼错）+ 全局（防解错）。

### 4.1 ★ 并发与对冲条款 R1–R4（**两仓逐字定稿，2026-10-30**）

> 出处：本仓 `mail/116` 提出草案 → Shirone `mail/117` 回「一个字都不用改，照单定稿」。

```
R1（块级并发）：不同块并发拉取（默认 8；实测拐点 8 = 4.89×）
R2（单片对冲）：同一块若 1.5s 内未拿到响应头 ⇒ 并发第二发，首个成功者胜；
                失败不 settle，继续等另一发；理论 p → p²
R3（对冲位置）：R2 只许在**消费端**实现。EdgeOne middleware/worker 内**禁止**
                （实测 AbortController 无法中断已发 fetch：8s 超时返 200 跑满 40s）
R4（两条正交）：R1 抗带宽/并发，R2 抗单请求随机失败。两者都要，不能互替。
```

**R2 的判据出处（两方独立复现，各自实测）**：

```
Shirone（首次观测）：并发 10 路同 URL ⇒ 9 路 0.6–1.3s、1–2 路卡到 25s
我（独立复跑，2026-10-30，用当前真实 bundle）：
  e7 0.32s e9 0.36s e3 0.37s e10 0.43s e4 0.54s
  e2 0.87s e6 1.12s e8 1.71s e1 2.04s      ← 9 路正常
  e5 **25.001561s**                        ← 1 路卡满 25s 上限
⇒ 「劣化是单请求级随机失败，不是整条路径死」——**两方独立验证成立**
```

**R3 为什么是负面判据**：Shirone 在 EdgeOne middleware 里实现过对冲，**没生效**
——边缘运行时的 `AbortController` 无法中断已发起的 fetch（8s 超时该返 502 却返 200
跑满 40s）。写成「禁止」而不是「不建议」，是为了让后来人不必再踩一遍。

**R1 的并发默认值 8 的依据**（每连接独立限速 1.5MB/s + 80ms RTT）：

```
conc=1 11,519ms | conc=2 1.99× | conc=4 3.63× | conc=8 **4.89×（拐点）** | conc=15 4.88×
```

⚠️ **测并发必须用「每连接独立限速」**。我最初用 CDP 的
`Network.emulateNetworkConditions`，1/2/4/8/15 并发**完全无差异**——因为
**CDP 限速是全局共享带宽**，并发分不到更多。这个坑已告知 Shirone。

---

## 5. 与既有契约的关系（不回退）

| 层 | 归谁 | 与发布契约的关系 |
|---|---|---|
| **内容契约**（`content-list`：`form`/`content`/`consumer`/`versions[]`/`files[]`） | 本仓语义 + 宿主 schema | **上游**，不改字段；未来加 `acquisition.releaseRef` **引用** manifest（先有实物再加） |
| **引擎契约**（`octave.build.json`：构建/实测/verdict） | 宿主 | **上游**，只**引用**发布身份，不复制字节事实 |
| **发布契约**（本设计） | 本仓设计 / 各仓产出 | **中间层**：字节身份的唯一处 |
| **部署契约**（`deploy-contract.mjs`：base/字面量重写） | UI | **下游**，消费 manifest |

**与「从源码构建契约」的冲突（`STATE` Q3：`ways` 是派生不是记录、不引入 `flavor`）**：
发布契约**不动版本语义**。`fromSource` 仍是"能不能从源码构建"；
"从哪个 release 取字节"是**取得路径**，与版本语义正交。**初代连 `acquisition` 都不加**
——等 manifest 有实物、单仓试点通了再说。**这是"不跳步"的纪律。**

---

## 6. 压缩策略（初代）

| 条件 | zstd | gzip | br | identity |
|---|---|---|---|---|
| `bytes ≥ 1 MiB` | **必出**（L19，分片 5MiB） | **必出**（-9，分片） | **不出**（留位） | **必出** |
| `bytes < 1 MiB` | 可选 | 可选 | 不出 | 必出 |
| 已压格式（`.gz/.zip/.whl/.woff2/.png`） | **不出**（白工 + 纯增体积） | 不出 | 不出 | 必出 |

**关于「极限压 gzip」**：实测 `-9` vs `-6` 只省 0.5%（20,899,276 vs 21,004,021），
CPU 翻倍 ⇒ **-9 在 wasm 上是白工**，用 -6 即可。时间该花在 zstd L19（比 gzip 小 26.6%）。

---

## 7. 站侧要提供的（全是标准 HTTP，无自创）

| 项 | 值 | 说明 |
|---|---|---|
| 每块独立 URL | `GET <dir>/chunks/<codec>/NNN.<ext>` | 普通 GET |
| `Content-Length` | 精确 | 用来判截断 |
| `Content-Type` | `application/zstd` / `application/gzip` / 原始类型 | **不要**再用 `application/gzip` 冒充 wasm |
| `Cache-Control` | `public, max-age=31536000, immutable` | ★「永不更新」靠这个，不靠"我们不改文件" |
| CORS | `Access-Control-Allow-Origin: *`（若跨源） | 分片会被跨源拉 |

**不需要的**（初代明确不要求）：Range / `Accept-Ranges` / 条件请求 /
`Digest` 头 / `multipart/byteranges`。**这些都是 v1 的自创，已砍。**

**一条已知现状（实测）**：当前边缘源站头是 `Cache-Control: public, max-age=0, must-revalidate`
——**与「永不更新」相反**，必须由反代层覆盖成 `immutable`。这条不完全在生产者手里。

---

## 8. 谁产谁核

| 角色 | 做什么 | 不做什么 |
|---|---|---|
| 各仓（生产者） | 产 `manifest.json` + 预分片；**自己算块 sha 与全局 sha** | 不定义别家字节 |
| 站侧（分发） | 搬运 + `immutable` 缓存 + 索引 | **不另算 sha、不改 manifest** |
| 消费端 | 按 `variants` 顺序试、并发拉、两道校验 | 不猜、不 Range、不自定义头 |
| 本仓 | 内容语义 + 发布契约存副本 | 不产字节、不裁决分发实现 |

---

## 9. 未决（我不擅定）

| # | 问题 | 我的倾向 |
|---|---|---|
| U1 | `chunkSize` 固定 5 MiB 还是按件可配 | **默认 5 MiB 可配**（拐点也受并发/块数影响） |
| U2 | 并发默认值 8 还是按 `navigator.connection` 自适应 | **默认 8**，允许覆盖 |
| U3 | 小件是否也分片 | **< 1 MiB 不分片**（并发无收益，反而多 N 个请求） |
| U4 | `acquisition` 何时进内容契约 | **manifest 落地 + 单仓试点之后** |
| U5 | br 何时开 | **初代之后**（用户已裁：不是不支持，是初代不开） |

---

## 10. 落地顺序（不跳步，这是刹车）

```
1. ✅ 用户审定 v3（R1–R4 两仓定稿；体积口径已纠；5MiB 表述已改为「上限+实测区间」）
2. ✅ manifest 校验器（check-release-v2.py，7/7 自证）+ **生成器已落地**
   （`tools/make-release-manifest.py`，自证 11/11：正常/该报超界/空输入三类齐）
3. ✅ **单仓试点已完成**（OM 真实产物）：见 §10.1
4. 站侧接入（immutable + 索引引用 manifest）    ← Shirone 已确认配合
5. UI/宿主 消费端（variants 遍历 + 并发 + 两道校验 + R2 对冲）
6. 内容契约加 acquisition                      ← 最后动语义
```

**试点前的两个硬前提（都已满足）**：
- ✅ 契约 v3 定稿（两仓共识）
- ✅ 校验器可机判（`tools/check-release-v2.py --selftest` 7/7，对 PoC 真件 31/0）
- ⬜ **manifest 生成器**——把「压缩→切块→算 sha→写 manifest」固化成脚本，
  否则试点要手工拼 manifest（易错且不可复现）

**试点的最小形态**（建议 OM 仓的 `v0.1.0-wasm32`）：
```
在 OM 仓加一个 `make-release-manifest.py`（或用宿主已有的 build 脚本扩展）：
  输入：产物文件（omc.wasm 74.5MB、js 56KB、msl zip 19.5MB）
  处理：按 5 MiB 切块 → zstd-19 每块独立压 → gzip-9 每块独立压
        → 算块 sha + 全局 sha → 写 manifest.json
  输出：<release 目录>/manifest.json + chunks/{zstd,gzip}/*
验收：tools/check-release-v2.py <manifest> ⇒ 全绿
```
**这一步不动任何现有消费端**——纯新增产物，可随时废弃。

### 10.1 ✅ 试点实跑结果（2026-10-30，OM 真实产物）

用 `tools/make-release-manifest.py` 对 `OpenModelicaCompiler_bg.wasm`（74,579,404 B）跑：

```
生成：24.2s（15 块 × 2 编码）
  zstd      15,349,112  (20.6% of raw)
  gzip      20,908,462  (28.0%)
  identity  74,579,404  (100%)
校验：check-release-v2.py ⇒ **24 PASS / 0 FAIL**
浏览器端到端：8 并发拉 15 块 → 逐块 sha → zstd 解码 → 拼接
  ⇒ 74,579,404 B，全局 sha 与 manifest 顶层**逐字一致**；total 583ms（fetch 76 + decode 442）
  ⇒ 解码器加载 6ms（fzstd ESM）
```

**⇒ 生成器 → 校验器 → 浏览器消费，三环闭合。** 这是「试点可以开始」的实测凭据。

**在 2–3 完成前，不推广任何压缩/分片策略。**

---

## 11. 复跑方式

```bash
# ① 浏览器解压能力
#   /mnt/hdd/zcode-test/harness/probe-browser-codec.mjs
#   ⇒ gzip/deflate OK；br/zstd NO

# ② 预分片压缩率 + 耗时（见 §1.3）
#   /tmp/prechunk.py（8 核并行）

# ③ 并发收益（见 §1.4）
#   /tmp/poc/slowserver.py 8931 1500000 0.08   # 每连接 1.5MB/s + 80ms RTT
#   node /mnt/hdd/zcode-test/harness/poc-conc-real.mjs http://127.0.0.1:8931 zstd
#   ⇒ conc=1 11519ms / conc=8 2354ms（4.89×拐点）

# ④ 全链路 PoC（见 §1.5）
#   /tmp/poc/make.py 生成 manifest + 三套分片
#   node /mnt/hdd/zcode-test/harness/poc-multichunk2.mjs http://127.0.0.1:8930 zstd 6
#   ⇒ PASS，sha 8287589e…

# ⑤ fzstd 体积与安全边界（见 §1.2 / §1.6）
gzip -9 -c /tmp/dec/package/umd/index.js | wc -c      # ⇒ 3860
grep -A3 "maximum backreference" /tmp/dec/package/README.md
```
