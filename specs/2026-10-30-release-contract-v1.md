# 发布契约（Release Contract）· v1

> **状态**：草案，供用户审。**未投递、未进 schema、未推广。**
> **v0 → v1 的改动原因**：v0 在手搓 manifest 字段，而这类语义 **HTTP 已经标准化**。
> v1 的原则是：**能由 HTTP 头表达的，绝不进 manifest；manifest 只补标准表达不了的那一小块。**
>
> **用户给的目标**：「给静态站一个**永远不需要更新**且**高度符合 HTTP 标准**的协议」。
> 本文每条设计都对着这两个词验：**永不更新** = 身份不可变 + 自描述 + 无版本协商；
> **符合标准** = 用 RFC 已有的机制，不自创。

---

## 0. 先认前一批的错（这是本设计的起点）

我 `109`/`110`/`113` 在没有 manifest 的情况下推广了 sidecar 压缩。三个真问题：

1. **没有单一身份对象**：`.wasm` / `.wasm.gz` / `.wasm.br` 三份字节，谁是谁、`Content-Encoding`
   该是什么、消费端拿到哪一层——无处声明；
2. **与「从源码构建契约」冲突**（`STATE.md:145` Q3：`ways` 是派生不是记录，不引入 `flavor`）：
   sidecar 是第三种取得路径，不纳入就是旁路；
3. **与现有 Range 协议冲突**：想乱序多线程拉 br/gzip，但没说清 Range 打哪层、怎么切、怎么校验。

⇒ 必须先有**一个**发布契约收口。

---

## 1. 实测事实（2026-10-30，edge 全量探测）

### 1.1 Range 只在「已压缩 sidecar」上工作

| 请求 | 结果 |
|---|---|
| `octave.wasm` + `Range: bytes=0-1023` | **200 OK**（`Accept-Ranges: none`，不支持） |
| `….wasm.gz` + `Range: bytes=0-1023` | **206**，1024 B，`Content-Range: bytes 0-1023/20895435` |
| `….wasm.gz` + `Range: bytes=1000000-1001023` | **206**，1024 B（内容不同 = 真分片） |
| `….wasm.gz` + `Range: bytes=-1024`（后缀） | **206**，1024 B ✅ |
| `….wasm.gz` + `Range: bytes=20893000-`（开放） | **206**，2435 B ✅ |
| `….wasm.gz` + `Range: bytes=0-99,200-299`（多段） | **200 全体** ❌ 不支持 multipart |
| `….wasm.gz` + `Range: bytes=99999999-…`（越界） | **416** ✅ |
| `….wasm.gz` + `Range: bytes=20895435-`（起始=尾） | **416** ✅ |

**⇒ Range 支持面 = 单段 Range（含后缀与开放形式），含正确的 `Content-Range` 与 `416`。
不支持多段（`multipart/byteranges`）。这条直接决定「分片必须一个一个拉、不能批量」**。

### 1.2 条件请求**不可依赖**（关键反直觉）

| 请求 | 期望（RFC） | 实测 |
|---|---|---|
| `Range` + `If-Range: <正确 ETag>` | 206 | **206** ✅ |
| `Range` + `If-Range: <错误 ETag>` | **200 全体**（RFC 9110 §13.1.5） | **206**（**不守标准**）❌ |
| `If-None-Match: <正确 ETag>` | **304** | **200** ❌ |

**⇒ 不能用 `If-Range` 做「分片与整包版本一致性」的守卫；不能用 `If-None-Match` 省流量。
这两条必须写进契约当「已知边界」，否则消费端会写出看似正确、实际无保护的重试逻辑。**

### 1.3 ETag / Last-Modified 的可用性

```
ETag: "6ae2ff51-13ed6cb"        ← 跨请求恒定（3/3 次相同）
  前缀 6ae2ff51 = 1793261393     ← mtime epoch（= Last-Modified）
  后缀 13ed6cb  = 20895435       ← ★ 精确等于 Content-Length
Last-Modified: Thu, 29 Oct 2026 08:09:53 GMT
Accept-Ranges: bytes            ← 仅 sidecar 有；原始件是 none
```

**⇒ ETag 是「mtime + size」派生的弱校验器**（`W/"<mtime>-<size>"` 是 GitHub/Fastly 家族约定），
**不是内容哈希**。它**能**用于「同一 URL 的两片是否来自同一版本」的**弱**判定
（size 与 mtime 都稳定），但**不能**替代 sha256 的 fail-closed。
⇒ 契约里：**ETag 只作诊断/日志，不作安全判据。**

### 1.4 没有的（如实记）

- **无任何 `Digest` / `Content-Digest` 头**（RFC 9530）⇒ 标准的内容完整性头不可用，
  必须由 manifest 携带 sha256。**这是 manifest 存在的第一理由**；
- **zstd 不支持**：`Accept-Encoding: zstd` 返回 200 + 原始件（74,579,404 B），
  `.wasm.zst` sidecar 404 ⇒ 当前编码面 = `identity` / `gzip` / `br` 三种。
- **`:status` 200 时 `Content-Type: application/gzip`**（sidecar 直接取时）——
  **这是坑**：消费端若直接 `fetch('x.wasm.gz')` 会拿到压缩字节却以为拿到 wasm。

### 1.5 乱序分片 + 还原全链路已验证

对 `….wasm.gz`（20,895,435 B）按 5 MiB 切片，**逆序**拉取后按序拼接：

```
chunk3 5,166,795 B / chunk2 5,242,880 B / chunk1 5,242,880 B / chunk0 5,242,880 B  (全 206)
merged = 20,895,435 B          ← 与 Content-Length 精确相等
gunzip → sha256 = 8287589ebdb53b4cc37c337c2ae88f798d8889f7  ← 与产品 sha 逐字一致
```

⇒ **协议可行，已端到端验证。** 但注意 §1.1：多段 Range 不支持，所以这是 **N 个独立请求**，
不是一次 multipart。

### 1.6 站管旧结论已过期（必须更正，否则两方永久各测各的）

`SITE-ADMIN-REQUEST.md:125`：

> 申请三（Range）——**接受现实，撤回申请**：实测「206 头声称分片却吐解压全体，头体不一致」。

**那次测的应是原始 `.wasm`**（边缘在解压路径上头体不一致）。**在 sidecar `.gz` 上是真 206**
（本次实测：字节精确、`Content-Range` 正确、拼接还原后 sha 一致）。

⇒ **契约必须写明「Range 的测量面」**：`(URL, 是否 identity, 是否有 Content-Encoding)` 三元组
不同，结论完全不同。**这是本次最大的方法论收获**——也是我给 UI 立的「测不到 ≠ 不存在」
纪律的又一个实例：两个团队各测一半、各写结论、永久冲突。

### 1.7 ★ 缓存现状：「永不更新」在源站头上**是反的**（必须由发布契约纠正）

实测三次连续请求同一 sidecar：

```
Age: 565   X-Served-By: cache-bur-kbur8200088-BUR  X-Cache: HIT
Age: 0     X-Served-By: cache-hkg-vhhh8650073-HKG  X-Cache: HIT   ← 换节点 = 重新计数
Age: 566   X-Served-By: cache-bur-kbur8200114-BUR  X-Cache: HIT
```

**两条事实**：

1. **多节点独立缓存**（LAX/HKG/BUR 各自计数）⇒ 命中率取决于请求落在哪个节点。
   这与 `080` 信记录的「EdgeOne 多节点各自缓存（Age 序列互异）」完全一致；
2. **源站头是 `Cache-Control: public, max-age=0, must-revalidate`** ⇒ 源站在主动
   **要求每次回源验证**。这和「永不更新」正相反。

**⇒ 「永不更新」不能靠"我们不改文件"实现，必须靠头**：
发布目录（`<repo>/<tag>/`）必须由产出方设成
`Cache-Control: public, max-age=31536000, immutable`。
**但这条不完全在生产者手里**——实测 `.gz` 的 `Cache-Control` 来自源站（GitHub Pages
的默认策略），而 `.wasm`（未压）却是 `max-age=3600, s-maxage=86400`。
⇒ **同一个目录下两层字节的缓存策略不一致**，这是发布契约必须纠正的第一件事。

**给站侧的最小要求**（不改源站也能做）：反代层对 `/<repo>/<tag>/` **覆盖**
`Cache-Control: public, max-age=31536000, immutable`。判据：

```bash
curl -sI https://<static-host>/<repo>/<tag>/x.wasm.gz | grep -i cache-control
# ⇒ public, max-age=31536000, immutable
```

### 1.8 多节点缓存对分片的影响（这条决定并发策略）

既然 `Age` 跨节点互异，**同一个文件的 N 个分片请求可能落到 N 个不同节点**：

- **好的一面**：不同节点各自有全量体时，并发分片 = 并发命中不同缓存，吞吐叠加；
- **坏的一面**：若某节点**没有**该文件缓存，它的首次请求要回源（实测 `X-Cache: MISS`
  时 `X-Timer ... VE3845` = **回源 3.8 秒**）⇒ 该分片慢 3.8s，成为整个并发的短板。

⇒ **契约对消费端的要求**：分片**必须容忍单点慢**——设超时 + 重试（重试会被粘到
另一个节点，这是 EdgeOne 拓扑给的红利）。**不要**因为一个分片慢就整体重来。

---

## 2. 设计原则（对着用户那两个词）

| 原则 | 怎么做 | 为什么 |
|---|---|---|
| **永不更新**（P1） | 身份 = `sha256`；URL 一旦发布不可变；**无版本协商、无能力发现** | 任何"协商"都要双方同步演进 = 要更新 |
| **纯标准**（P2） | 分片用 RFC 9110 `Range`/`Content-Range`/`416`；编码用 RFC 9110 `Content-Encoding`；缓存用 `Cache-Control: immutable` | 浏览器/代理/CDN 全都懂，不用教 |
| **manifest 只补标准不表达的**（P3） | HTTP 有 `Content-Encoding`、`Content-Length`、`Accept-Ranges` —— **这些不进 manifest**；HTTP **没有** sha256、没有"这层是哪个编码的字节"、没有"Range 打哪层" —— **只有这些进** | manifest 越小，越不会变成第二真相 |
| **失败要响**（P4） | 两道 sha 校验（编码层 / 原始层）；`416`/`404`/sha 不符都当硬错 | 有前科：装成功报失败（D12）、装配缺陷伪装降级（D11） |
| **可降级但可观测**（P5） | br → gzip → identity 逐级回落，**回落原因必须可读** | 老浏览器/坏代理存在；但静默降级会让"为什么慢"永远查不出 |

---

## 3. 协议本体

### 3.1 一句话

> **一个 release = 一个不可变目录 + 一份 manifest.json。**
> manifest 只写「HTTP 表达不了的那几件」：sha256、编码层的字节身份、Range 的测量面。
> 其余一切（类型、长度、Range 能力、缓存策略）**都由 HTTP 头自描述**。

### 3.2 目录形状（静态站，永不更新）

```
<repo>/<tag>/
  manifest.json                 ← 唯一元数据入口（不可变）
  <asset>                       ← identity 原始件
  <asset>.gz                    ← gzip sidecar（5.0s/74.5MB）
  <asset>.br                    ← brotli q11 sidecar（148.5s/74.5MB）
```

**"永不更新"的强制**：目录名含 `tag`，`tag` 一旦发布不再变。
新版本 = 新 `tag`（新目录）。**不提供 `latest` 别名** —— 那是永续更新的入口。

### 3.3 manifest（最小形状）

```json
{
  "schema": 1,
  "id": "OpenModelica-Full-Wasm/v0.1.0-wasm32",
  "producer": { "repo": "ArchivalEra/OpenModelica-Full-Wasm", "commit": "<sha>" },
  "assets": {
    "OpenModelicaCompiler_bg.wasm": {
      "role": "engine",
      "contentType": "application/wasm",
      "bytes": 74579404,
      "sha256": "8287589e…b001",
      "encodings": {
        "gzip": { "bytes": 20895435, "sha256": "<gz 字节的 sha>" },
        "br":   { "bytes": 13053436, "sha256": "<br 字节的 sha>" }
      },
      "range": { "basis": "encoded", "granularity": 5242880 }
    }
  }
}
```

**逐字段的必要性论证（deletion test：删了它，谁受损？）**

| 字段 | 删了会怎样 | 判定 |
|---|---|---|
| `bytes` + `sha256` | 边缘**无 Digest 头**（§1.4）⇒ 消费端**没有任何办法**验证完整性 | **必须留** |
| `encodings.*.{bytes,sha256}` | 分片拼完后无法验证拼对了（`Content-Range` 只给范围，不给内容身份） | **必须留** |
| `encodings`（存在性本身） | 消费端只能靠**试**（先试 br，404 再试 gzip…）= N 次往返、且"404"与"真没有"分不开 | **必须留** |
| `range.basis` | 实测原始件不支持 Range、sidecar 支持（§1.1）⇒ 不写就可能对着原始件发 Range，得 200 全体还以为是分片 | **必须留** |
| `range.granularity` | 5 MiB 是"边缘极其迅速"的经验值；不写就得各端各猜 | **留（可缺省 5 MiB）** |
| `contentType` | 侧车直接取时 `Content-Type: application/gzip`（§1.4）⇒ 消费端会误判 | **留** |
| ~~`url`~~ | **删**：URL = `<dir>/<asset>` 与 `<dir>/<asset>.<enc>`，**可由 id+name 推导** | **删（派生而非记录）** |
| ~~`contentEncoding`~~ | **删**：`gzip`/`br` 就是 HTTP 的编码名，重复写 = 第二真相 | **删** |
| ~~`range.supported`~~ | **删**：`Accept-Ranges` 头已经在说；`basis` 已隐含"支持" | **删** |
| ~~`immutable`~~ | **删**：`Cache-Control: immutable` 是 HTTP 的事 | **删** |
| ~~`firstSeen`~~ | **删**：见 P3；用 `Last-Modified`/`ETag` 诊断即可 | **删** |
| ~~`form`~~ | **删**：`form`（pkg/tree/file…）是**内容契约**的轴，不属于字节身份 | **删（归内容契约）** |

**⇒ 从 v0 的 14 个字段砍到 6 个。** 砍掉的每一个都是「HTTP 已经说了」或「位置放错了」。

### 3.4 五条不变量（校验器逐条判，fail-closed）

| # | 不变量 | 反例（必须报红） |
|---|---|---|
| **I1** | `encodings.<enc>.sha256` 是**该编码字节**的 sha，不是原始字节的 | 写了原始 sha ⇒ 消费端校验必失败 |
| **I2** | 压缩层**可复算**：`gunzip(enc bytes)` / `brotli_decode(enc bytes)` 必须得到 `bytes` 长度且 sha = `sha256` | 声明一个没真压的 sidecar 骗体积检查 |
| **I3** | `range.basis ∈ {encoded, identity}`，**且声明 `encoded` 时 `encodings` 必须非空** | 声明 encoded 但没有任何编码层 = 空指 |
| **I4** | `granularity ≤ 2^31-1` 且 `> 0` | 分片号要能写进 `Range: bytes=a-b` |
| **I5** | **同一 `id` 下同名 asset 的 `sha256` 永不变**；变了 = 必须换 `id`（新 tag） | OM 先例：`v0.1.0-wasm32` **追加** asset 合法（新名字），**覆盖**同名非法 |

### 3.5 消费端算法（把 HTTP 用到极致）

```
1. GET <dir>/manifest.json           （Cache-Control: immutable ⇒ 永久缓存）
2. 选编码：br → gzip → identity       （按 encodings 存在性，不靠试错）
   ⚠ 若某编码 404（manifest 说有但站上没有）⇒ 报 ENCODING_MISSING，不静默回落
3. 取字节：
   if range.basis == "encoded" and enc != identity:
       N = ceil(encBytes / granularity)
       并发 K 个单段 Range（RFC 9110 单段；**不用 multipart**，§1.1）
       按 Content-Range 的 offset 落盘（乱序安全）
   else:
       普通 GET（原始件 Accept-Ranges: none，别试 Range）
4. 校验①：拼好的编码字节 sha256 == encodings[enc].sha256   （防拼错）
5. 解码（gunzip / brotli）
6. 校验②：解码后 bytes == bytes 且 sha256 == sha256        （防解错/装错层）
```

**为什么两道校验缺一不可**：乱序并发最常见的错是「少一片/重复一片/错位」——
第一道抓这个。解码层的错（用了错的编码器、流被截断）只有第二道能抓。

**并发数 K**：契约只规定"K 由消费端定"，但**必须 ≤ 站侧允许的连接数**（避免自己把自己 DDoS）。

### 3.6 与「从源码构建契约」的关系（用户点名的冲突）

现状（`STATE.md:145` Q3 裁决）：

> `ways` 是派生不是记录；**不引入 `flavor`**（预编译与否是同一版的两种取得路径，不是版本的味道）。

**发布契约不动这条，只补第三层**：

```
版本语义（内容契约）      ：这一版是什么、能不能从源码构建（fromSource）
取得路径（内容契约·新增）  ：从哪个 release 取（source / prebuilt 两个 ref）
字节身份（发布契约）      ：那个 release 里每个字节对象的三份 sha
```

**判据**：`fromSource` 保持原义；`acquisition` 只放 **releaseRef 引用**，不放字节事实；
发布契约是 `releaseRef` 的**定义处**。内容契约的 `url/sha256/size` 仍是"选中路径的投影"
（不变量②照旧：顶层标量必须逐字等于某候选）。

**⇒ 不合并、不替代，分层。** 而 `acquisition` 字段**必须等 manifest 有实物之后再加**
——先有定义才有引用，否则就是第二次"无定义先推广"。

### 3.7 压缩策略（实测数据支撑，收敛为契约条款）

| 条件 | gzip | br | 依据 |
|---|---|---|---|
| `bytes ≥ 1 MiB` | 必出 `-9` | **必出 q11** | br11 省 gzip-9 的 **37.54%**（omc.wasm）/ **34.95%**（octave.wasm） |
| `bytes < 1 MiB` | `-6` 即可 | 可选 | 小件 br 头开销吃掉收益 |
| 已压格式（`.gz/.zip/.whl/.woff2/.png/.jpg`） | **不出** | **不出** | 白工；UI 现脚本踩坑：zip 23 MiB + whl 13 MiB + tar.gz 79 MiB 被重复压 |
| 成本 | 5.0s / 74.5MB | **148.5s / 74.5MB** | q11 必须 CI 一次 + 永久缓存 |

**关于「极限压的 gzip」**：实测 `-9` 相对 `-6` **只省 0.5%**（20,899,276 vs 21,004,021），
CPU 翻倍。⇒ 时间该花在 br q11（省 37.5%），不是 gzip -9（省 0.5%）。
「极限压」这个词在 wasm 上只对 br 成立。

### 3.8 站侧要遵守的（HTTP 头，不是 manifest）

| 头 | 值 | 为什么 |
|---|---|---|
| `Accept-Ranges` | `bytes`（sidecar）/ `none`（identity） | 让消费端**看头决定**，不用试 |
| `Content-Type` | **原始件真实类型**（`application/wasm` 等），sidecar 也是**同一类型** | 现在的 `application/gzip` 是坑（§1.4） |
| `Content-Encoding` | `gzip` / `br`（仅当按 `Accept-Encoding` 协商直出时） | RFC 9110 |
| `Cache-Control` | `public, max-age=31536000, immutable` | 永不更新 |
| `Content-Range` | 206 必带，且 `*/<total>` 的 total 必须**等于该编码层字节数** | 实测现在正确，要保 |
| `416` | Range 越界/起始=尾 | 实测现在正确，要保 |
| ~~`If-Range`~~ | **不依赖**（实测不守标准 §1.2） | 契约写明"不可用" |

**注意一个站侧坑**：现在 `Cache-Control: public, max-age=0, must-revalidate`（`.gz`）
—— 这与"永不更新"相反。发布目录应改成 `immutable`（releases 与站点的分支产物要分开对待）。

---

## 4. 谁产谁核

| 角色 | 做什么 | 不做什么 |
|---|---|---|
| **各仓（生产者）** | 产 release + `manifest.json` + `.gz`/`.br`；**自己算三份 sha** | 不定义别家字节 |
| **站侧（分发）** | 搬运 + 不可变缓存 + 索引；**只核对** manifest 的 sha | **不另算 sha、不改 manifest、不判断包能不能跑** |
| **消费端（UI/宿主）** | 读 manifest → 选编码 → 分片 → 两道校验 | 不猜 `Content-Encoding`、不试错探测 |
| **本仓** | 内容语义；**发布契约存副本** | 不产字节、不裁决分发实现 |

**已知张力（如实记）**：站侧 `111` 想「一份静态索引（repo→tag→assets+sha256）」
—— 那**正是 manifest 的聚合视图**。**这不是重复，是索引应引用 manifest 而非重抄 sha**。
建议：站侧索引 = `{repo, tag, manifestUrl}` 三元组 + 可选缓存；**sha 只在 manifest 里有一份**。

---

## 5. 未决（需用户/两家裁，我不擅定）

| # | 问题 | 我的倾向 | 理由 |
|---|---|---|---|
| **U1** | manifest 每仓一份 vs 集群一份聚合 | **每仓一份**（`<repo>/<tag>/manifest.json`） | 生产者产权清晰；聚合是分发方的索引，引用而非复制 |
| **U2** | `range.granularity` 固定还是可配 | **可配，缺省 5 MiB** | 用户原话「5MB 极其迅速」；但不同尺寸件最优粒度可能不同 |
| **U3** | 内容契约何时加 `acquisition` | **manifest 有实物之后** | 先定义后引用 |
| **U4** | br 是否默认必出（还是按需） | 大件必出、小件可选 | §3.7 实测 |
| **U5** | 站侧索引是否完全委托 manifest | **是** | 避免 sha 两处 |

---

## 6. 落地顺序（**不跳步，这是刹车**）

```
1. 用户审定本设计                       ← 现在
2. manifest 生成器 + 校验器（含 I1–I5 自证）   ← 先有工具
3. 一个仓试点（建议 OM：已有 release + 两 asset）← 先有实物
4. 站侧接入（索引引用 manifest）              ← 再分发
5. UI/宿主 消费端接入（两道校验）              ← 最后改消费
6. 内容契约加 acquisition（引用已存在的 manifest）← 最后动语义
```

**明确不做**：在 1–3 完成前，**不再推广任何压缩/分片策略**。这封信是刹车。

---

## 7. 复跑方式（每条结论的出处）

```bash
B=https://isui.ren/repo/Octave/omc/OpenModelicaCompiler_bg.wasm
G=$B.gz

# ① Range 只在 sidecar 上工作
curl -sI -H "Range: bytes=0-1023" $B | head -1                 # 200（Accept-Ranges: none）
curl -sI -H "Range: bytes=0-1023" $G | head -1                 # 206 + Content-Range

# ② 单段多种形式
curl -s -o /dev/null -w "%{http_code} %{size_download}\n" -H "Range: bytes=-1024" $G      # 206 1024
curl -s -o /dev/null -w "%{http_code} %{size_download}\n" -H "Range: bytes=20893000-" $G  # 206 2435
curl -s -o /dev/null -w "%{http_code}\n" -H "Range: bytes=0-99,200-299" $G               # 200（不支持多段）
curl -s -o /dev/null -w "%{http_code}\n" -H "Range: bytes=99999999-100000000" $G         # 416

# ③ 条件请求不守标准
curl -s -o /dev/null -w "%{http_code}\n" -H "Range: bytes=0-1023" \
  -H 'If-Range: "deadbeef-1"' $G        # 206（RFC 应 200）⇒ If-Range 不可依赖
curl -s -o /dev/null -w "%{http_code}\n" -H 'If-None-Match: "6ae2ff51-13ed6cb"' $G   # 200（应 304）

# ④ ETag = mtime-size（不是内容哈希）
curl -sI $G | grep -i '^etag'          # "6ae2ff51-13ed6cb"；后缀 hex = Content-Length

# ⑤ 乱序分片 + 还原（§1.5）
#  chunk3..chunk0 逆序拉 → 按序拼 → gunzip → sha256 = 8287589e…

# ⑥ 无 Digest 头 / 无 zstd
curl -sI $G | grep -i digest           # 空
curl -s -o /dev/null -w "%{size_download}\n" -H "Accept-Encoding: zstd" $B   # 74579404（未压）
```
