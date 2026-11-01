# 发布契约（Release Contract）设计 · v0 草案

> **状态**：草案（供用户审）。**未投递、未进任何 schema、未推广**。
> **设计依据**：本仓、宿主、OM、UI 四个仓的产物实物 + 2026-10-30 线上实测。
> **术语**：按 `codebase-design` 的 module / interface / seam / adapter / depth / leverage。

---

## 0. 为什么需要它（先认前一批的错）

我 `109`/`110`/`113` 在没有 manifest 设计的情况下推广了 sidecar 压缩。**这是不负责的**，
用户批评正确。三个真问题：

1. **没有单一身份对象**：`.wasm` / `.wasm.gz` / `.wasm.br` 三个字节，谁是谁、
   `Content-Encoding` 该是什么、消费端拿到的是哪一层——**没有任何地方声明**；
2. **与「从源码构建契约」冲突**（`STATE.md:145` Q3 裁决）：`versions[]` 的
   `fromSource` 语义是「同一版的两种取得路径」，而 sidecar 引入了**第三种取得路径**
   （预压缩件），不纳入就会变成旁路；
3. **与现有 Range 协议冲突**（用户点名）：想用「br/gzip 乱序多线程拉取」，
   但没人说清 Range 打在哪一层、按什么切、怎么校验。

⇒ 这三件事都必须由**一个发布契约**收口，而不是各仓各发一套。

---

## 1. 事实基础（全部实测，2026-10-30）

### 1.1 三个现有契约的实物形态

| 契约 | 产地 | 载体 | 关键字段 |
|---|---|---|---|
| **内容契约** | 本仓（语义）/ 宿主（schema） | `content-list.json`（schema 2） | `form`(6 形态) / `content` / `consumer` / `versions[]`(3 不变量) / `files[]` / `kind` / `role` / `arch` / `sha256` / `size` / `deps` |
| **引擎契约** | 宿主 | `octave.build.json`（schema 1） | `tool` / `build` / `declared` / `measured` / `inputs` / `notes` / `verdict` / `mismatches` / `checked` |
| **部署契约** | UI（`deploy-contract.mjs`） | 构建期注入 + `pages.yml` | base 前缀 / JS 字面量重写 / `<meta site-base>` / 5MB 分片 shim（**注释承诺**） |

**已验证的断点**：UI `deploy-contract.mjs:47` 注释写「5MB 分片取数 shim：整包 GET →
Range 分片（3 片并行、按序拼接）」，但**产物里没有该实现**（我 grep `dist/` 全树，
`Range` 命中 1047 次全是 `RangeError` 等非 HTTP 语义）。⇒ **这个 shim 是注释承诺，未实装**。

### 1.2 ★ 线上 Range 的真实行为（本次最关键实测）

```
GET  octave.wasm + Range: bytes=0-1023        ⇒ 200 OK      （不支持 Range！）
GET  omc.wasm.gz + Range: bytes=0-1023        ⇒ 206, 1024 B （支持）
GET  omc.wasm.gz + Range: bytes=1000000-1001023 ⇒ 206, 1024 B（真分片，内容不同）
```

**结论：EdgeOne 的 Range 只在「已压缩的 sidecar」上工作，在原始未压缩件上不支持。**

### 1.3 ★ 乱序分片 + 还原全链路验证（我实测通过）

对 `OpenModelicaCompiler_bg.wasm.gz`（20,895,435 B）按 5 MiB 切片，
**逆序**（chunk3 → chunk2 → chunk1 → chunk0）拉取，然后按序拼接：

```
chunk3: 5,166,795 B 206   chunk2: 5,242,880 B 206
chunk1: 5,242,880 B 206   chunk0: 5,242,880 B 206
merged: 20,895,435 B  ← 与 Content-Length 精确相等
gunzip → sha256 = 8287589ebdb53b4cc37c337c2ae88f798d8889f7  ← 与产品 sha 逐字一致
```

⇒ **你要的「br/gzip 乱序多线程拉取」在技术上完全可行，且我已端到端验证。**

### 1.4 站管的旧结论已过期（必须更正）

`SITE-ADMIN-REQUEST.md:125` 记着：

> 申请三（Range）——**接受现实，撤回申请**：你们的实测（**206 头声称分片却吐解压全体，
> 头体不一致**）比 HANDOFF.md 的旧记录权威。分片 shim 现状：边缘 `Accept-Ranges: none`
> 下 shim 走整包回落。

**那次测的是原始 `.wasm`**（或经边缘解压的响应）——在那种情况下确实「头体不一致」。
**但 sidecar `.gz` 上是真 206**（本次实测，字节精确、内容不同、拼接还原后 sha 一致）。
⇒ **协议的每条判据都必须指明「打在哪一层」**，否则两方各测各的、结论永久冲突。

---

## 2. 设计：发布契约

### 2.1 先说清「收谁」

| 现有契约 | 在发布契约里的位置 |
|---|---|
| 内容契约（`content-list`） | **上游**：声明"有什么、什么版本、能不能跑"。**不改字段**，只在条目上**引用**发布身份 |
| 引擎契约（`octave.build.json`） | **上游**：声明"引擎产物怎么构建的、实测什么"。同样只**引用** |
| 部署契约（base/shim） | **下游**：消费发布身份来定"从哪取、怎么拼" |
| **发布契约（本设计）** | **中间层**：把「一个可交付字节对象」的身份说清 —— 与"内容语义"和"构建过程"都解耦 |

**关键判断（seam 的位置）**：发布契约的 seam 放在 **「字节对象身份」** 上，不放在
「包」或「构建」上。理由（用 deletion test）：删掉它，内容契约就得自己描述压缩层
（污染语义）、引擎契约就得重复描述 url/sha（两处漂移）、消费端就得各自猜
`Content-Encoding`（UI 已经在猜）——**复杂度会散回三个调用方**，说明它挣到了自己。

### 2.2 接口（manifest 的形状）

一个 manifest 描述**一个不可变字节集**（一个 release）：

```json
{
  "schema": 1,
  "id": "<repo>/<tag>",                     // 稳定身份，不可变
  "producer": { "repo": "ArchivalEra/OpenModelica-Full-Wasm", "commit": "<sha>" },
  "created": "2026-10-30T00:00:00Z",
  "assets": [
    {
      "name": "OpenModelicaCompiler_bg.wasm",
      "role": "engine",                      // engine | package | toolchain | data | docs
      "form": "file",                        // 与内容契约同词表（file/tree/pkg/oct/octdir/js）
      "bytes": 74579404,                     // 原始字节数（唯一权威）
      "sha256": "8287589e…b001",             // 原始字节 sha（唯一 fail-closed 依据）
      "encodings": {                          // ★ 本设计的核心：编码层是**子对象**，不是兄弟条目
        "gzip": { "url": "…wasm.gz", "bytes": 20895435, "sha256": "…" },
        "br":   { "url": "…wasm.br", "bytes": 13053436, "sha256": "…" }
      },
      "range": {                              // ★ Range 能力声明（每层各自独立）
        "supported": true,
        "granularity": 5242880,               // 建议切片粒度（5 MiB）
        "basis": "encoded"                    // ★ 关键：Range 打在「编码后的字节」上
      },
      "contentType": "application/wasm",
      "contentEncoding": {                    // 与 encodings 一一对应（HTTP 头用）
        "gzip": "gzip", "br": "br"
      },
      "immutable": true,
      "firstSeen": "2026-10-30T00:00:00Z"     // 防同名替换（OM v0.1.0 追加过 asset 的先例）
    }
  ]
}
```

### 2.3 五条不变量（fail-closed，校验器逐条判）

| # | 不变量 | 为什么 |
|---|---|---|
| **I1** | `encodings.*.sha256` 是**该编码字节的 sha**，不是原始字节的 | 消费端拿到的就是编码字节；用原始 sha 校验必然失败 |
| **I2** | `bytes`（原始）是**唯一权威**；`encodings.*.bytes` 是派生量，且校验器**必须能复算验证**（gunzip/解 br 后等于 `bytes` 且 sha 等于 `sha256`） | 防"声明一个没压过的 sidecar 骗过体积检查" |
| **I3** | `range.basis` ∈ {`encoded`, `identity`, `none`}，**缺省 `none`** | 实测：EdgeOne 在原始件上 `200`、在 sidecar 上 `206` ⇒ 必须显式声明打哪层，不许猜 |
| **I4** | `range.supported=true` 时，`granularity` 必填且 `≤ 2^31-1` | 分片号要被 `Range: bytes=a-b` 表达 |
| **I5** | **同名 asset 的 `sha256` 一旦见报，永不许变**；变了 = 新 `id` 或新 `name` | OM 的先例：`v0.1.0-wasm32` **追加**过 asset（合法），但覆盖同名不合法 |

### 2.4 与「从源码构建契约」的关系（用户点名的冲突）

现状（`STATE.md:145` Q3 裁决）：

> `ways` 是派生不是记录；**不引入 `flavor`**（预编译与否是同一版的两种取得路径，
> 不是版本的味道）。

**发布契约不破坏这条，而是补上第三条路径的正名**：

```json
// 内容契约的条目（不改字段，只加一个引用）
{ "name": "statistics", "version": "1.7.7",
  "acquisition": {                          // ★ 新增：取得路径，不是版本味道
     "source":   { "releaseRef": "octave-extra-content/statistics-src-1.7.7" },
     "prebuilt": { "releaseRef": "octave-host/oct-1.7.7-wasm32", "arch": "wasm32" }
  }
}
```

**判据**：`fromSource` 保持原义（"这一版能不能从源码构建"），`acquisition` 回答
"从哪取字节"，**两者正交**。发布契约是 `releaseRef` 的**定义处**（一个 ref 指向一个
manifest），内容契约的 `url`/`sha256`/`size` 仍是**选中路径的投影**（不变量②照旧：
顶层标量必须逐字等于某候选）。

⇒ **冲突解决方式：不合并、不替代，而是分层** —— 版本语义（内容契约）/
取得路径（acquisition）/ 字节身份（发布契约）三层，各自单一职责。

### 2.5 与「Range 协议」的关系（用户点名想沿用）

**沿用，但要加一条修正**：现有 shim 注释说「整包 GET → Range 分片」，
实测**整包不支持 Range、sidecar 才支持**。所以协议改成：

```
1) 取 manifest，选 encodings 里的一层（优先 br，回落 gzip，最后 identity）
2) 若 range.supported=true 且 range.basis="encoded"：
     对 sidecar URL 发 N 个并发 Range 请求（乱序），按 offset 落盘
3) 拼完对「编码字节」核 encodings[enc].sha256   ← 第一道
4) 解码（gunzip / brotli）
5) 对「原始字节」核 sha256 + bytes                ← 第二道（I2）
```

**两道校验缺一不可**：第一道防分片拼错（乱序并发最常见的错），第二道防解码错/装错层。

**为什么 `basis: "encoded"` 是默认建议**：
- 实测原始件 Range 根本不工作（`200` 而非 `206`）；
- 编码后的 sidecar 体积小 3–5 倍 ⇒ 分片数少、并发效率高、失败重试代价低；
- 解码是本地 CPU，比多拉 3–5 倍字节便宜得多。

**代价（如实）**：必须**全部分片到齐才能解码**（压缩流不可随机访问）。
⇒ 所以「乱序」只买到**并行带宽**，买不到「先解压先可用」。

### 2.6 三份身份（呼应我 `113` 的建议，此处正式化）

| 层 | 谁算 | 谁核 | 用途 |
|---|---|---|---|
| 原始 `bytes`+`sha256` | **生产者**（构建产线） | 消费端（解码后） | fail-closed 唯一依据 |
| `.gz` `bytes`+`sha256` | 生产者（CI 压完立刻算） | 消费端（分片拼完后） | 分片完整性 |
| `.br` `bytes`+`sha256` | 生产者（CI q11 压完立刻算） | 消费端 | 同上 |

**纪律**：**分发方（站侧）只核对，不另算**（分发方算出来的值不是权威，
与生产者不一致时报 red，不是自己更新）。

### 2.7 压缩策略（我 `113` 的建议，此处收敛为契约条款）

| 条件 | gzip | br | 依据（实测） |
|---|---|---|---|
| `bytes ≥ 1 MiB` | 必出 `-9` | **必出 q11** | br11 省 gzip-9 的 37.54%（omc.wasm）/ 34.95%（octave.wasm） |
| `bytes < 1 MiB` | 出 `-6` 即可 | 可选 | 小件 br header 开销吃掉收益 |
| 已压格式（`.gz/.zip/.whl/.woff2/.png/.jpg`） | **不出** | **不出** | 白工；UI 现脚本踩坑：zip 23MiB + whl 13MiB + tar.gz 79MiB 被重复压 |
| 成本 | 5.0s / 74.5MB | **148.5s / 74.5MB** | q11 必须 CI 一次 + 永久缓存 |

---

## 3. 谁产谁核（角色分工，不涉及内容语义）

| 角色 | 做什么 | 不做什么 |
|---|---|---|
| **各仓（生产者）** | 产出 release + manifest + `.gz`/`.br` sidecar；**自己算三份 sha** | 不定义别家的字节 |
| **站侧（分发）** | 搬运 + 不可变缓存 + 索引；**只核对** manifest 里的 sha | 不另算 sha、不改 manifest、不判断包能不能跑 |
| **消费端（UI/宿主）** | 读 manifest → 选编码 → 分片拉 → 两道校验 | 不猜 Content-Encoding、不自己拼 URL |
| **本仓** | 内容语义（四态/版本策略/`consumer`/`files[]`）；**发布契约存副本** | 不产字节、不裁决分发实现 |

---

## 4. 未决问题（我不擅自定，需用户/两家裁）

| # | 问题 | 我的倾向 | 判据 |
|---|---|---|---|
| **U1** | manifest 是**每仓一份**还是**集群一份聚合**？ | **每仓一份**（`<repo>/<tag>/manifest.json`），站侧聚合索引 | 生产者产权清晰；聚合是分发方的活 |
| **U2** | `encodings` 缺省策略：**全出**还是**按需**？ | 大件全出、小件只 gzip | §2.7 实测 |
| **U3** | 内容契约要不要加 `acquisition` 字段？ | **要**，但**等 manifest 落地后再加**（先有定义才有引用） | 避免第二次"无定义先推广" |
| **U4** | `range.granularity` 固定 5 MiB 还是可配？ | **可配，默认 5 MiB** | EdgeOne "5MB 极其迅速"（用户原话）；但不同文件最优粒度可能不同 |
| **U5** | `.br` 的 MIME/Content-Type | 与原始件同 `contentType` + `Content-Encoding: br` | HTTP 标准；实测线上 `.wasm.gz` 返 `application/gzip` 是**错的**（会让消费端拿到压缩字节当 wasm） |

---

## 5. 落地顺序（**不跳步**）

```
1. 用户审定本设计（现在）
2. 生产 manifest 生成器 + 校验器（谁做？见 U1）      ← 先有工具
3. 一个仓试点（建议 OM，它已有 release + 两个 asset）  ← 先有实物
4. 站侧接入（它已经在建分发站，正好）                  ← 先有分发
5. UI/宿主 消费端接入                                  ← 最后改消费端
6. 内容契约加 acquisition 字段（引用已存在的 manifest）  ← 最后动语义层
```

**明确不做**：在 1–3 完成前，**不再推广任何压缩/分片策略**。这封信就是那个刹车。

---

## 6. 复跑方式

```bash
# ① Range 只在 sidecar 上工作
curl -sI -H "Range: bytes=0-1023" https://isui.ren/repo/Octave/lanes/wasm32-final/octave.wasm | head -1   # 200
curl -sI -H "Range: bytes=0-1023" https://isui.ren/repo/Octave/omc/OpenModelicaCompiler_bg.wasm.gz | head -1 # 206

# ② 乱序分片 + 还原全链路（见 §1.3 的输出）
#  chunk3..chunk0 逆序拉 → 按序拼接 → gunzip → sha256 = 8287589e…

# ③ br q11 收益
python3 -c "
import brotli,gzip,time
raw=open('/mnt/hdd/antigravity-projects/Octave-UI/dist/omc/OpenModelicaCompiler_bg.wasm','rb').read()
t=time.time();b=brotli.compress(raw,quality=11,lgwin=24);print('br11',len(b),f'{time.time()-t:.1f}s')
t=time.time();g=gzip.compress(raw,9);print('gz9',len(g),f'{time.time()-t:.1f}s')"
#  ⇒ br11 13,053,436 (148.5s) / gz9 20,899,276 (5.0s)

# ④ 部署契约的 5MB shim 是注释承诺（未实装）
grep -c "Range" /mnt/hdd/antigravity-projects/Octave-UI/dist/assets-loader.js   # 全是 RangeError，无 HTTP Range
grep -n "5MB 分片取数 shim" /mnt/hdd/antigravity-projects/Octave-UI/scripts/deploy-contract.mjs
```
