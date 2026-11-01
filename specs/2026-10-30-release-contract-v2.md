# 发布契约 v2 · 初代

> **状态**：初代协议草案，供用户审。**未投递、未进 schema、未推广。**
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

| 编码 | 解码器 | minified | gzip 后 |
|---|---|---|---|
| gzip | 浏览器原生 | 0 | **0** |
| zstd | `fzstd@0.1.1` | 8,394 B | **3,860 B** ← 官方标 3.8kB，我实测 3860 ✅ |
| br | 需 wasm（如 `brotli-wasm`） | ~100KB+ | 未测（初代不开） |

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

## 2. 目录形状

```
<repo>/<tag>/                         ← 不可变。新版本 = 新 tag = 新目录
  manifest.json                       ← 唯一元数据入口
  chunks/zstd/000.zst … NNN.zst       ← 预分片（每块一个普通 URL）
  chunks/gzip/000.gz  … NNN.gz
```

**不提供 `latest` 别名**——那是「永续更新」的入口。「永不更新」的强制就在目录名含 tag。

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
  "bytes": 74579404,
  "sha256": "8287589e…b001",
  "variants": [
    {
      "codec": "zstd",
      "decoder": "fzstd@0.1.1",          // 可选：提示消费端要什么解码器
      "decoderBytes": 3860,               // 可选：提示代价
      "totalBytes": 15349112,
      "chunked": true,
      "chunkSize": 5242880,
      "chunks": [
        { "i": 0, "file": "chunks/zstd/000.zst", "bytes": 1275256, "sha256": "…" }
      ]
    },
    {
      "codec": "gzip",
      "totalBytes": 20908462,
      "chunked": true,
      "chunkSize": 5242880,
      "chunks": [ { "i": 0, "file": "chunks/gzip/000.gz", "bytes": 1395000, "sha256": "…" } ]
    },
    {
      "codec": "identity",                // 最后兜底：单文件
      "totalBytes": 74579404,
      "chunked": false,
      "file": "OpenModelicaCompiler_bg.wasm"
    }
  ]
}
```

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
| **I1** | 顶层 `bytes`/`sha256` = **全部块解码拼接后**的字节与哈希 | 写成"某编码层"的 sha |
| **I2** | `chunks[].sha256` 是**该编码块的字节** sha | 写原始 sha |
| **I3** | 每个 `chunks[].bytes` 之和 == `variants[].totalBytes` | 声明与实际不符 |
| **I4** | `variants` 非空，且**恰有一个** `codec:"identity"` 作为末位兜底 | 全是压缩格式（解不了就无路可走） |
| **I5** | `chunked:true` ⇒ `chunkSize` 必填且 `chunks` 非空；`chunked:false` ⇒ 有 `file` 无 `chunks` | 半截状态 |
| **I6** | ★`chunked:true` ⇒ `chunkSize ≤ 2^25`（fzstd 安全边界）+ 块必须**独立压缩** | 块 > 32MiB 且 level≥20 ⇒ fzstd 可能解不出 |
| **I7** | `codec` 是**开放字符串**（不是枚举） | 加 br/xz/lz4 时要改 schema |

---

## 4. 消费端算法（初代，伪码）

```
man = GET <dir>/manifest.json                       // 1 个请求，可永久缓存
for v of man.variants:                              // 按声明顺序（回退链）
    dec = {
      "gzip":  () => nativeGzip,                     // 零成本
      "zstd":  () => import(fzstd),                  // 3.8KB
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
1. 用户审定本 v2                       ← 现在
2. manifest 生成器 + 校验器（I1–I7 自证）    ← 先有工具
3. 单仓试点（建议 OM：已有 release + 两 asset）
4. 站侧接入（immutable + 索引引用 manifest）
5. UI/宿主 消费端（variants 遍历 + 并发 + 两道校验）
6. 内容契约加 acquisition               ← 最后动语义
```

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
