# 发布契约 v4 · 定稿

> **状态**：本地实测通过。**生成器自证 43/43、校验器自证 26/26、真数据 168 PASS / 0 FAIL（含逐块盘核对）**、
> 三编码端到端 sha 逐字一致。**数字是当次实测快照，复跑命令见 §9**（本仓纪律 2 的
> `[[键名]]` 台账只覆盖 `STATE.md`，`specs/` 不在扫描面内 —— 这是写明的缺口，不是"查过"）。
> **目标**：**apt 的稳健 + HTTP 的简洁**。静态站上所有内容（wasm / tar / zip / html / 字体 / 图片）都用这一套。
> **四轮 design-it-twice 的收敛结果**，被否方案的判据都留在 §8。

---

## 0. 一句话

> **一个 release = 一个不可变 tag = 一份 `manifest.json` + N 个扁平 asset。**
> 名字只允许 GitHub 不会改写的字符（白名单）⇒ **`manifest.file` 与真实 asset 名恒等**。
> 客户端**只从 manifest 取名字，绝不拼** ⇒ **404 只有一种含义**。
> 一切字节走**普通 GET**，无 Range / 无条件请求 / 无自定义头。

---

## 1. 名字白名单（v4 的地基）

```regex
^[A-Za-z0-9_-][A-Za-z0-9._-]*$
```

外加两条：**不含 `..`**、**不以 `.` 结尾**、**≤ 255 字符**（GitHub 硬限，实测 256 报 422）。

**本协议自加的长度预算（比平台上限紧，有意为之）**：

| 项 | 值 | 判据 |
|---|---|---|
| 硬上限 | 255 | 实测 GitHub：255 传成功、256 报 `name is too long` |
| **推荐预算** | **≤ 64** | 名字 = `<product>__<载荷名>.<codec>.<NNN>`；product 与载荷名各留 ~25 字符余量。<br>实测最大实例 `omc__OpenModelicaCompiler_bg.wasm.zstd.014` = 42 字符 |
| 超预算处置 | **生成器报错并提示缩短** | 不许静默截断（截断 = 名字变了 = manifest 指向不存在的 asset） |

**为什么推荐 64 而不是贴 255**：名字里三段都有实际含义（product / 载荷 / codec+序号），
真按 255 撑满时人已经读不懂；而且载荷名越长越可能含需要扁平化的字符。
生成器对超 255 **硬拒**，对 64–255 之间不拦（只提示），因为那是生产者的判断空间。

**为什么是这几条——实测（2026-10-31，真 GitHub 上传回读）**：

| 输入 | GitHub 实际存成 | 判定 |
|---|---|---|
| `a.b_c-D9.zstd.000` | 逐字不变 | ✅ 白名单内 |
| `UPPER.Mixed.Case.000` | 逐字不变 | ✅ 大写稳 |
| `-leading-hyphen` | 逐字不变 | ✅ 前导连字符稳 |
| `sp ace.bin` | `sp.ace.bin` | ❌ 空格→点 |
| `pct%41.bin` | `pct.41.bin` | ❌ `%`→点 |
| `paren(1).bin` | `paren.1.bin` | ❌ 括号删 |
| `a中b.bin` | `a.b.bin` | ❌ 非 ASCII 删（7 字符→5） |
| `.hidden.bin` | `default.hidden.bin` | ❌ 前导点加前缀 |
| `dots...many.000` | `dots.many.000` | ❌ 连续点折叠 |
| `trailing-dot.` | `default.trailing-dot` | ❌ 尾点加前缀 |

**长度超限会报错（422），但改写不报错。** 这是白名单存在的唯一理由：
**宁可自己约束字符集，不赌平台的规范化规则**——改写一旦发生，`manifest.file` 就指向一个不存在的 asset，
表现和「没发」一模一样，正是我们要消灭的不可归因。

**白名单的收益**：`file` 字段**就是** asset 名，不需要「逻辑路径 ↔ 物理短名」映射表
（apt 的 `Filename` 带目录层级，我们不需要，因为白名单从源头保证「写什么存什么」）。

**推荐格式（非契约）**：`<arch>__<载荷名>.<codec>.<NNN>`
例：`omc__OpenModelicaCompiler_bg.wasm.zstd.014`（37 字符）、`wasm32__numgradient.oct.gzip.000`（34 字符）。

---

## 2. manifest 结构

```json
{
  "schema": 2,
  "id": "Octave-Full-Wasm/optim-1.6.3",
  "chunkSize": 5242880,
  "codecs": [
    "zstd", "gzip", "identity"
  ],
  "products": {
    "src":    {"form": "pkg"},
    "wasm32": {"form": "octdir", "arch": "wasm32", "src": "src"},
    "wasm64": {"form": "octdir", "arch": "wasm64", "src": "src"}
  },
  "entries": [
    {
      "product": "src",
      "name": "optim-1.6.3.tar.gz",
      "bytes": 422679,
      "sha256": "59fb3771…3a14",
      "variants": [
        {"codec": "identity", "chunks": [
          {"part": 0, "file": "src__optim-1.6.3.tar.gz.identity.000",
           "bytes": 422679, "sha256": "59fb3771…3a14"}
        ]}
      ]
    },
    {
      "product": "wasm32",
      "name": "__bfgsmin.oct",
      "bytes": 57271,
      "sha256": "f878860d…09d4",
      "variants": [
        {"codec": "zstd", "chunks": [
          {"part": 0, "file": "wasm32____bfgsmin.oct.zstd.000",
           "bytes": 12692, "sha256": "785e172f…8e47"}
        ]},
        {"codec": "gzip", "chunks": […]},
        {"codec": "identity", "chunks": […]}
      ]
    }
  ]
}
```

### 2.1 三层各答一问

| 层 | 答什么 | 为什么必须存在 |
|---|---|---|
| **`products`** | 这个 release 有哪几个逻辑产物（含 `form`/`arch`/`src`） | **`optim` 的 5 个 `.oct` 在 wasm32/wasm64 里文件名全同、字节全不同**（实测 5/5 撞车，同 sha = 0）。没有这一层，entries 无法区分 |
| **`entries[]`** | 每个载荷的完整字节身份（`bytes`/`sha256`/`variants`） | **apt 的稳健性**：每条记录自足，单独拿出来就能用 |
| **`variants[].chunks[]`** | 每个编码的分片 | EdgeOne 20MB+ 掉 0.93MB/s ⇒ 必须 ≤5MiB 分片 |

### 2.2 `src` 边：AGPL 落点

```json
"wasm32": {"form": "octdir", "arch": "wasm32", "src": "src"}
```

**源码与产物必须在同一 release**（四仓全 AGPL 实测确认）。`src` 指向同 release 内的源码 product。

**`form`/`arch` 留在 product 上，名字里不需要 `.src`/`.raw`**——这是用户问题的答案：
格式不是二元（src vs raw），是三维（`form` 6 种 × `arch` × `content`），且每维已有归属。
名字里塞格式 = **一个事实重复 45 次**（OM 的 74.5MB wasm 有 45 个分片文件），而 manifest 里只需写 1 次。

### 2.3 不做 blob 去重（**apt 的选择**）

四轮里我曾采纳「内容身份层」去重（UI dist 21 路径/10 内容，省 48.9% 资产）。**按 apt 的判据撤回**：

实测 apt 明知冗余仍复制——`amd64` 索引里 143 条 `Architecture: all`，`i386` 索引里**同样 143 条**：

```
amd64: 221 条 amd64 + 143 条 all
i386 : 146 条 i386  + 143 条 all   ← 复制一遍
```

**这不是懒，是「每条索引自足」**：`amd64` 客户端只下一个文件就得到完整可解集。
去重会引入「删一个 member 影响另一个」的耦合，而 apt 刻意不要这个。

**代价**：同一份内容在多个 product 里存多份。**认。**

---

## 3. 不变量（fail-closed）

| # | 不变量 | 反向用例 |
|---|---|---|
| **V1** | 每个 `chunks[].file` 匹配白名单（`^[A-Za-z0-9_-][A-Za-z0-9._-]*$`、无 `..`、不以 `.` 结尾、≤255） | `sp ace.bin` / `dots...many.000` / `.hidden` / `a中b.bin` 全拒 |
| **V2** | 所有 `file` 在整个 release 内**全局唯一** | 两条 chunk 用同一 file |
| **V3** | `entries[]` 内 `(product, name)` 唯一；`products{}` 的 id 也唯一（且 id 必须过白名单——它进文件名前缀） | wasm32 和 wasm64 可以有同名 `numgradient.oct`（不同 product）；同一 product 内重名 ⇒ 拒 |
| **V4** | 每个 entry 的 `variants` 非空，且**恰有一个 `identity` 在末位** | 只有 zstd（解不了就无路可走） |
| **V5** | 每个 variant 的 `chunks[].part` 恰是 `0..N-1` 连续无缺；**同一 entry 的所有 codec 块数必须相同**（切的是同一份原始字节） | 删中间一块 / 某 codec 少一块 |
| **V6** | `0 < chunkSize ≤ 2^25`（fzstd backreference 上限） | `chunkSize = 2^26` |
| **V7** | `Σ(identity.chunks.bytes) == entry.bytes`；**identity 各块拼接后的 sha 必须逐字等于 `entry.sha256`**（校验器带 `--base` 时对盘核对） | `bytes` 多写 1 / 盘上缺件 / 块被换 |
| **V8** | `product.src` 若存在必须解析到同 release 内**无 `arch`** 的 product；无 `arch` 的 product 不许带 `src` | `src` 悬空 / 自指 |
| **V9** | `codecs[]` 是非空字符串数组，**开放词表**（不是枚举）；每个 entry 用到的 codec 必须已在 `codecs[]` 声明 | 加 `br`/`xz` 不改 schema；entry 用了未声明的 codec ⇒ 拒 |
| **V10** | `schema` 是客户端认识的值，否则整体拒收 | 未来 `schema:3` 被旧客户端硬解 |

### 无上限（**明文写出来，免得又有人把平台数当协议形状**）

**`entries[]` 没有数量上限，asset 数也没有上限。** 3 条也好、3000 条也好，协议一视同仁。

2026-10-31 实测过各平台容量不一（GitHub 单 release 1000 个 asset，错误字段 `file_count`），
**但那不进协议**——用户裁定原话：

> **「别发信质疑协议了，之后 gitcode 啥的就各不相同了，反正协议无限就对了。」**

**判据**：平台容量是**分发方**的事。托管方放不下，由它决定怎么拆（多 release / 换平台 / 分桶），
那是**部署形态**，不是**内容语义**。写进契约不变量会把「某个平台某天的上限」固化成协议形状，
换平台就得改契约——正是本契约最不想要的那种耦合。

**生成器与校验器对此的态度**：
- 生成器**只报数**（"预计 N 条 entry / M 个 asset"），**不拦任何数量**；
- 校验器**不设** asset 额度判据（自证里有一条 1202 条 entry 的 manifest 必须**合法**）；
- 两者都保留 `chunkSize`、白名单这些**协议自己的**硬约束——那些才是判据。

---

## 4. 客户端算法（HTTP 简洁的落地）

```
1. GET <base>/manifest.json                     ← 全流程唯一需要"知道"的 URL
2. 校验 schema / 不变量（本地，0 请求）
3. 选 product（按 form/arch；源码路径只读 src product）
4. 对每条 entry，按 codecs 顺序选第一个能解的分支：
     名字 = variant.chunks[i].file              ← ★ 逐字取，绝不拼
     GET <base>/<名字>                            ← 普通 GET
     校验字节数 + 逐块 sha256
     解码（gzip=原生 / zstd=fzstd 6.8KB / identity=no-op）
5. 拼接 → 校验 entry.sha256 → 交付
```

**三条铁律**：
1. **不拼名字**——只取 `file` 字段（客户端若自己拼，拼错就回到「四因一果的 404」）
2. **不试错探测**——`variants` 是声明，不是靠 404 试探
3. **不用 Range / 条件请求 / 自定义头**——全是普通 GET

---

## 5. 实测结果（2026-10-31，本地）

### 5.1 生成器自证 40/40（构成与用例逐条对应）

```
A. 白名单反向 9 条（实测 GitHub 改写原样，必须全拒）
   连续点 / 前导点 / 尾点 / 空格 / % / 括号 / 非 ASCII / 斜杠 / 换行尾
B. 白名单正例 3 条（实测 GitHub 逐字保留）
   a.b_c-D9.zstd.000 / UPPER.Mixed.Case.000 / -leading-hyphen
C. v4 结构 10 条
   products 3 个 / src 边存在 / 跨 arch 同名不塌陷 / 两条 sha 不同 /
   已压格式只 identity / 11MiB→3 块 / 全名过白名单 / 全名唯一 /
   每条 entry.sha 与盘上 identity 拼接一致 / 块能独立解压
D. 反向与边界 16 条（该报必报 / 参数真生效）
   chunkSize>2^25 / =0 / 负数 /
   两个无 arch 同名文件→2 条 entry 且 file 名不同 / 两条 sha 各自与盘上一致 /
   src 悬空 / src 自指 / 无 arch 带 src / product id 重复 /
   chunkSize 参数真生效（1MiB→3 块）/ 递归收集子目录 / 子目录扁平化 /
   html 走全三编码 / css 走全三编码 / 字体 woff2 只 identity / gzip 可复现
E. 空输入 2 条：无 product / 目录为空
```

**校验器 `--selftest` 26/26**：1 条正常不报 + 23 条该报必报（V1–V10 逐条反向，
含「chunkSize 撒谎」这条专测）+ 2 条空输入。

**真数据 168 PASS / 0 FAIL**（74.5MB wasm，15 块 × 3 编码，含**每个 codec 每块
bytes+sha 对盘核对** + identity 拼接总 sha）。

### 5.2 5MiB 分片机制（74.5MB wasm，真件）

```
载荷 74,579,404 B   chunkSize 5,242,880
zstd     15 块  总 15,349,112  最大块  1,275,256  ≤5MiB ✅
gzip     15 块  总 20,908,462  最大块  1,729,488  ≤5MiB ✅
identity 15 块  总 74,579,404  最大块  5,242,880  ≤5MiB ✅（精确 5×1024×1024）
期望块数 ceil(74579404/5242880) = 15  ✅ 三种编码块数一致
```

### 5.3 浏览器端到端（三种编码全通，全部普通 GET）

| 编码 | 块数 | 字节 | sha | 请求数 | 带 Range/条件头 | 耗时(本地) |
|---|---|---|---|---|---|---|
| **zstd** | 15 | 74,579,404 | ✅ 逐字一致 | 15+1 | **0** | 595ms（解码器加载 7ms） |
| **gzip** | 15 | 74,579,404 | ✅ | 15+1 | **0** | 498ms |
| **identity** | 15 | 74,579,404 | ✅ | 15+1 | **0** | 372ms |

**本地无网络差 ⇒ identity 最快；真实 EdgeOne 上 zstd 靠 26.6% 体积优势会赢**（这条是推断，不是实测）。

### 5.4 真数据：optim 1.6.3

```
products = ['src', 'wasm32', 'wasm64']   entries = 11
src/optim-1.6.3.tar.gz:        422,679 B → 1 块 × 1 编码  [已压格式只出 identity]
wasm32/__bfgsmin.oct:           57,271 B → 1 块 × 3 编码
wasm32/__disna_optim__.oct:     12,837 B → 1 块 × 3 编码
wasm32/__max_nargin_optim__.oct: 8,311 B → 1 块 × 3 编码
wasm32/numgradient.oct:         17,025 B → 1 块 × 3 编码
wasm32/numhessian.oct:          17,515 B → 1 块 × 3 编码
wasm64/（同名 5 件，字节全不同）
```

**跨 arch 同名（`numgradient.oct` ×2）由 `product` 分组解决，两条 entry 各自自足。**

---

## 6. 覆盖性：静态站的所有内容

**全部实测**（不是推断；复跑见 §9 第 5 条）。

| 内容类型 | v4 怎么走 | 实测 |
|---|---|---|
| **wasm**（引擎/工具链） | 分片 + 三编码 | 74,579,404 B → 15 块 × 3 编码，端到端 sha 逐字一致 |
| **tar/zip/whl**（源码包） | **只出 identity**，仍分片 | `optim-1.6.3.tar.gz` 422,679 B → 1 块 × **identity only**（zip 再压只省 4.6%，白工） |
| **oct 二进制** | 分片 + 三编码 | `optim` 的 10 个 `.oct` 全部 1 块 × 3 编码 |
| **HTML** | 三编码（不是已压格式） | `index.html` 29 B → 1 块 × **3 编码** ✅ |
| **CSS** | 三编码 | `css/app.css` 15 B → 1 块 × **3 编码** ✅ |
| **字体**（woff2/woff/ttf/otf/eot） | **只出 identity** | `fonts/a.woff2` 30,000 B → 1 块 × **identity only** ✅ |
| **图片**（png/jpg/webp/avif/gif） | **只出 identity** | `img/big.avif` 60,000 B → 1 块 × **identity only** ✅ |
| **音视频**（mp4/webm/mp3/ogg） | **只出 identity** | 已进 `PRECOMPRESSED` 清单 |
| **超大图片**（>5MiB） | identity **分片** | 走同一套 chunk 逻辑，消费者拼回 |
| **嵌套站点树** | **递归收集 + 路径扁平化** | `site/{css,fonts,img}/x` → 名字 `site/css__app.css`（`/` → `__`）✅ |

**v4 的边界（如实）**：它管**发布产物的字节分发**，不管**站点的路由与渲染**。
UI 的 Astro 产物（`_astro/App.CUPGshJq.js` 这类自带内容哈希的文件）继续 Pages 直出——
它们已经满足「永不更新」（名字含 hash），不需要再套一层 manifest。

**v4 的边界（如实）**：它管**发布产物的字节分发**，不管**站点的路由与渲染**。
UI 的 Astro 产物（`_astro/App.CUPGshJq.js` 这类自带内容哈希的文件）继续用 Pages 直出——
它们已经满足「永不更新」（名字含 hash），不需要再套一层 manifest。

---

## 7. 与既有契约

| 层 | 归谁 | 与 v4 关系 |
|---|---|---|
| **内容契约**（`content-list`：version/form/content/consumer/deps） | 本仓语义 + 宿主 schema | **上游**。回答"有什么、能不能用、给谁用"。v4 不碰 |
| **引擎契约**（`octave.build.json`） | 宿主 | **上游**。回答"字节怎么造的"。`measured.files[].sha256` 是 v4 的产地 |
| **发布契约 v4**（本文件） | 本仓设计 / 各仓产出 | **中间层**。只碰字节身份 + 分片 |
| **部署契约**（Astro base/字面量） | UI | **下游** |

**收纳审计的结论不变**：内容契约 23 字段里只有 5 个（`sha256`/`url`/`size`/`files`/`upstream_url`）能被 v4 接管，
其余 18 个是语义域。**v4 不替代内容契约，也不替代引擎契约。**

---

## 8. 四轮被否的方案（防将来重开）

| 轮 | 方案 | 被否理由（判据） |
|---|---|---|
| 第一轮 | `<asset>.<bytes>.<sha256>.codec.NNN`（111 字符） | **客户端 URL 正确性不可排查**：sha 错/tag 错/名字截断/没发 全是一个 404 |
| 第二轮 A | 纯坐标 `z-000`（5 字符） | codec 靠单字母隐式表，加格式要加字母 = 改文法 |
| 第二轮 B | 自证短名 `aid.codec.NNNN`（`aid=hash(sha+chunkSize)`） | **名字里仍有需要计算的身份**，是第一轮错误的变体；引入两套哈希前映像作新兼容面 |
| 第二轮 C | `slot.i.codec` + 零请求预检 | 采纳其骨架（后来的 v4 用了它的白名单思想） |
| 第三轮 A | 平铺四类记录（product/member/blob/chunk） | **`blob` 去重撤回**（见 §2.3 apt 判据）；chunk 平铺收益不抵复杂度，改为嵌进 variant |
| 第三轮 B | 按 arch 切索引（apt 式） | **实测切分亏字节**：optim 客户端 926 vs 923 B gz（亏 3B）却多 1 个串行请求（启动慢 33%） |

---

## 9. 复跑方式

```bash
# 生成器自证（40 条）
source /mnt/hdd/toolenv/bin/activate
python3 tools/make-manifest-v4.py --selftest

# 真数据（optim 11 载荷 + src）
python3 tools/make-manifest-v4.py --out /tmp/v4 --id "Octave-Full-Wasm/optim-1.6.3" \
  --product src:pkg:/mnt/hdd/zcode-projects/Octave-Full-Wasm/site/assets/forge/optim-1.6.3.tar.gz \
  --product wasm32:octdir:wasm32:src:/mnt/hdd/zcode-projects/Octave-Full-Wasm/site/assets/octdir/optim \
  --product wasm64:octdir:wasm64:src:/mnt/hdd/zcode-projects/Octave-Full-Wasm/site/assets/octdir-w64/optim

# 分片机制（74.5MB → 15 块）
python3 tools/make-manifest-v4.py --out /tmp/v4big --id "OM/omc" \
  --product omc:file:omc:/mnt/hdd/openmodelica-wasm-build/site-omc/omc/OpenModelicaCompiler_bg.wasm

# 端到端（三编码，验"全普通 GET"）
cd /tmp/v4big && python3 -m http.server 8950 &
node /mnt/hdd/zcode-test/harness/poc-v4.mjs http://127.0.0.1:8950 zstd 8      # ⇒ 15 块 / sha 一致 / 0 条件头
node /mnt/hdd/zcode-test/harness/poc-v4.mjs http://127.0.0.1:8950 gzip 8
node /mnt/hdd/zcode-test/harness/poc-v4.mjs http://127.0.0.1:8950 identity 8

# 白名单反向断言（8 个实测 GitHub 改写案例必须全拒）
# 见 tools/make-manifest-v4.py --selftest 的前 10 条
```

**GitHub 改写的原始实测**（本条是白名单存在的唯一理由，可复跑）：
```bash
RID=$(gh api -X POST repos/<o>/<r>/releases -f tag_name=t -f name=t -F draft=true -q .id)
for nm in 'sp ace.bin' 'dots...many.000' '.hidden.bin' 'a中b.bin'; do
  gh api --method POST -H 'Content-Type: application/octet-stream' \
    "https://uploads.github.com/repos/<o>/<r>/releases/$RID/assets?name=$(python3 -c "import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1],safe=''))" "$nm")" \
    --input /tmp/p.bin -q '.name'
done
# ⇒ sp.ace.bin / dots.many.000 / default.hidden.bin / a.b.bin
```
