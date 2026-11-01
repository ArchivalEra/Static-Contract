# 发布契约 v1.1 · 许可证协议（定稿）

> **状态**：**定稿**（2026-11-01），manifest `schema` 升至 **3**。
> 实现：`tools/check-release-v4.py` 加 V11–V15；`scripts/sync-catalogue.py` 加 G7；
> `scripts/build-site.py` 渲染许可列。**校验器自证通过后才算落地**（见 §9）。
>
> **来源**：用户裁定「各个资源组件都需要明确标注各自的 license」，
> 「去翻找 apt 官方的 copyright 附带方式，然后设计协议，v1.1 要来了」，
> 以及四方向 design-it-twice 后的裁定「定稿，这很棒」。
> **apt 侧事实全部取自本机实物**（`/usr/share/doc/*/copyright`），复跑见 §8。

---

## 0. 一句话

> **许可声明是 release 的一等字段：默认一条表达式管整个 release，
> 逐组件差异时在该 entry 上覆盖。声明必须可追溯到 release 内的字节。
> 「不知道」是合法终态，但「不知道」进不了 catalogue。**

三条设计判据（按重要性）：

1. **客户端只认一条规则** —— `entry.license ?? manifest.license.expr`。
   没有 glob、没有优先级表、没有命名空间歧义。两个独立实现不会分歧。
2. **不知道 ≠ 没有** —— `status: "unstated" | "refused"` 是合法 manifest，
   但 catalogue 一律排除。**逼人给假答案比留白更坏。**
3. **声明必须锚到字节** —— `provenance.sources[].anchor` 指向 release 内的 entry，
   `anchor_sha256` 必须等于该 entry 的 sha256。⇒ **校验零下载**（沿用 G4 手法），
   且「声明与真相不符」在结构上可被发现。

---

## 1. 问题陈述（为什么需要 v1.1）

`schema: 2` 的 manifest **没有任何许可字段**（实测键：
`chunkSize` / `codecs` / `entries` / `id` / `products` / `schema`）。后果：

| 现状 | 问题 |
|---|---|
| 站点只标本站 AGPL | 收录的 release **许可不明** —— 读者无法知道 `forge-optim-1.6.3` 能不能商用 |
| 字节来自第三方（Octave-Forge） | `Octave-Extra-Content` 的 LICENSE 明写「Package bytes ... governed by each package's own license (see COPYING inside its tarball)」，**那份 COPYING 在 tarball 里，不在任何元数据里** |
| 客户端只拉字节 | 拿到 tarball 才知道许可 —— **太晚**，且很多包根本没有 COPYING |
| 仓级 `license` 字段不可信 | 实测两例：`LLVM-wasm` 仓是 `AGPL-3.0` 但 `clang.wasm` 是 `Apache-2.0 WITH LLVM-exception`；`Octave-Extra-Content` 是 `NOASSERTION`（其正文说「各包自有许可」） |

**这是分发合规缺口，不是展示问题。** apt 早遇到过，它的答案是 `copyright` 文件。

---

## 2. apt 的做法（实物调研，本机实测）

### 2.1 机制与覆盖率

Debian 每个包在 `/usr/share/doc/<pkg>/copyright` 附一份**机器可读版权文件**（DEP-5）：

```
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: <名称>
Source: <上游地址>

Files: *
Copyright: <年份 作者>
License: <SPDX 短名>

Files: <具体路径>
Copyright: ...
License: ...
```

**实测覆盖率**（2026-11-01 本机）：`3265` 个包含 `3237` 份 copyright ⇒ **99.1%**。
⇒ `copyright` 在 apt 生态里是**近乎强制**的约定。

### 2.2 提取到的四条规则（以及我们采纳/不采纳什么）

| apt 的做法 | 实物证据 | v1.1 采纳 |
|---|---|---|
| `Files:` glob，`*` 兜底 + 特例覆盖 | accountsservice | ❌ **不采纳 glob**（客户端要重实现匹配器 + 优先级 + 命名空间；改用 entry 级覆盖） |
| `License:` 短名 + 全文单独成段 | apt、7zip | ✅ 采纳（`expr` 短名 + `provenance` 指路） |
| `or` / `and` 多许可 | aha `MPL-1.1 or LGPL-3+`；apt `GPL-2+ and curl` | ✅ 采纳（SPDX 表达式文法） |
| `Files-Excluded:` 声明「原样有但不分发」 | 7zip 的 RAR 代码 | ✅ 采纳（`excluded[]`，见 §4.4） |
| **「best effort」的诚实态度** | `apt/copyright` 的 `Comment:` 段原文：*"This file is a best effort to document the statements of copyright and licenses as stated in the file, but is not a complete representation of all copyright"* | ✅ **全盘采纳** —— 协议不要求完美，要求如实标注已知与未知 |

### 2.3 我们**不采纳** `Files:` glob 的判据（四方向评审一致结论）

草案曾用 `Files: *` 兜底 + 特例覆盖（照抄 DEP-5）。**三份独立设计都否掉了它**，理由一致：

- 客户端必须实现 glob 匹配器（`*` 跨不跨 `/`？大小写？）
- 必须实现**优先级顺序**（第一匹配生效）
- 必须实现**命名空间歧义**（`<product>/<name>` 还是裸 `name`？）
- 三个实现都必然在边界上分歧 ⇒ **「同一份 manifest，两个客户端读出两个许可」**

而真实数据不支持这个复杂度：13 个 forge 包里 **8 个是单一许可**，最复杂的
`optim` 也只是 `GPL-3.0-or-later and BSD-3-Clause and public domain`（一个 AND 串）。

---

## 3. 协议形态（`schema: 3`）

```jsonc
{
  "schema": 3,
  "id": "Octave-Extra-Content/forge-optim-1.6.3",
  "chunkSize": 5242880,
  "codecs": ["zstd", "gzip", "identity"],

  "license": {                          // ← 整个 release 的默认声明
    "expr": "GPL-3.0-or-later AND BSD-3-Clause AND LicenseRef-public-domain",
    "status": "declared",               // declared | unstated | refused
    "provenance": {
      "resolver": "spdx-norm@1",        // 归一化规则版本（可追溯）
      "sources": [
        {
          "source": "producer-registry",   // 见 §4.2 白名单
          "anchor": {"product": "meta", "name": "meta__optim.json"},
          "anchor_sha256": "<该 entry 的 sha256>",
          "basis": "extracted",         // extracted | inherited | declared | upstream
          "copyright": "2008-2023 The Octave-Forge developers"
        }
      ]
    }
  },

  "products": { ... },
  "entries": [
    {
      "product": "meta", "name": "meta__optim.json",
      "bytes": 3120, "sha256": "...",
      "role": "license",                // payload | license | notice（可选，默认 payload）
      "variants": [ ... ]
    },
    {
      "product": "wasm32", "name": "numgradient.oct",
      "bytes": 17025, "sha256": "...",
      "license": "MIT",                 // ← 仅需要时覆盖；缺省继承 manifest.license.expr
      "variants": [ ... ]
    }
  ]
}
```

### 3.1 字段定义

| 字段 | 必需 | 语义 |
|---|---|---|
| `license` (顶层) | ✅ | 默认许可声明对象 |
| `license.expr` | `status=="declared"` 时必需 | SPDX 表达式（文法见 §4.1）。非空字符串 |
| `license.status` | ✅ | `declared`（有明确许可）/ `unstated`（查不到，未声明）/ `refused`（上游明确拒绝声明） |
| `license.reason` | `status != "declared"` 时必需 | 非空字符串，说明为什么不知道。**空白 ≠ 未知** |
| `license.provenance.sources[]` | `status=="declared"` 时 ≥1 条 | 声明依据，见 §4.2 |
| `license.provenance.resolver` | ✅ 建议 | 归一化规则版本（如 `spdx-norm@1`），用于复现 |
| `entries[].license` | ⭕ 可选 | 覆盖默认表达式（字符串）。**只有真需要时写** |
| `entries[].role` | ⭕ 可选 | `payload`（默认）/ `license` / `notice` |
| `entries[].excluded[]` | ⭕ 可选 | `{path, why}` —— 包内「原样有但不分发」（DEP-5 `Files-Excluded` 的对手） |

### 3.2 解析规则（客户端唯一需要知道的一条）

```
license_of(entry) = entry["license"] if "license" in entry else manifest["license"]["expr"]
```

**没有第二跳，没有优先级，没有 glob。** 这就是全部。

`manifest.license.status != "declared"` 时，所有 entry 解析为同一状态
（`unstated` / `refused`），客户端按策略处理（默认拒绝解包，见 §5）。

---

## 4. 不变量（V11–V14，全部零下载）

延续 v4 的 V1–V10 编号。**全部是纯 manifest 判据，不需要网络、不需要磁盘。**

| # | 不变量 | 反向用例（必须拒） |
|---|---|---|
| **V11** | `license` 必须存在且为对象；`status ∈ {declared, unstated, refused}`；`declared` ⇔ `expr` 是非空字符串且能解析为合法 SPDX 表达式；非 `declared` ⇒ **必须**有非空 `reason`，且**不得**有 `expr` | 缺 `license` / `status` 不在闭集 / `unstated` 带 `expr`（自相矛盾）/ `unstated` 无 `reason` |
| **V12** | **白名单与 basis 无条件生效**（与 `status` 无关）；`declared` 时额外要求 `sources[]` 非空。`explicit-unknown` 的 `basis` 只许缺席或 `declared` | `source: "http-body"` / `basis: "guessed"`，**即使 `status: "unstated"` 也拒** |
| **V13** | `provenance.sources[].anchor` 必须解析到**同 release 内**的 entry，且 `anchor_sha256` 逐字等于该 entry 的 `sha256`；无 `anchor` 的 source 必须是 `manifest-embedded` | anchor 指向不存在的 entry / sha 不符 / 无锚却声称 `explicit-unknown` 之外的来源 |
| **V14** | `entries[].license` 若存在必须是非空字符串且文法合法；`role ∈ {payload, license, notice}`；`excluded[].why` 非空 | `license: ""` / `role: "docs"` / `excluded: [{path:"x"}]` 缺 `why` |

### 4.1 SPDX 表达式文法（客户端**不需要**实现）

```
expr := term (("AND" | "OR") term)*
term := id ["WITH" exception] | "(" expr ")" | license-ref
id   := SPDX 标识符形状  ^[A-Za-z0-9][A-Za-z0-9.+-]*$
exception := SPDX 标识符形状
license-ref := ^LicenseRef-[A-Za-z0-9._-]+$
```

**算符必须大写**（`AND` / `OR` / `WITH`）—— 小写是写法错误的常见形态，直接拒。
`WITH` 只能作用在**单个标识符**上（`(A OR B) WITH X` 非法），且**不许链式**（`A WITH B WITH C` 非法）。
优先级：`WITH` > `AND` > `OR`（与 SPDX 一致）。**括号只用于显式分组，不改变优先级。**

**客户端不需要解析**：它只展示 `expr` 字符串。需要判断"能不能用"的客户端才需要 tokenizer
（约 35 行），而那是消费端可选能力。

### 4.2 `source` 白名单（谁有资格当证据）

| source | 含义 | 需要 anchor |
|---|---|---|
| `manifest-embedded` | 生产者直接写在 manifest 里（无外部依据） | ❌ 不需要 |
| `archive-license-files` | 从 release 内的许可正文 entry 读到 | ✅ |
| `producer-registry` | 生产者注册表（如 `packages/*.json` 的 `fa-copyright` 链接） | ✅ |
| `upstream-api` | 上游 API（GitHub `/license`、SPDX 列表） | ✅ **需要**（无锚不可复核） |
| `explicit-unknown` | 生产者明确声明「查不到」 | ❌ 不需要 |

**为什么只这五种**：每一种都能说清"证据长在哪"。`http-body` 之类不可复核的来源直接排除 ——
它是"我说我看到了"，不是证据。

### 4.3 `basis`（声明的性质，给人看也给审计用）

| basis | 含义 |
|---|---|
| `extracted` | 从 release 内的字节直接读到（最强） |
| `inherited` | 从 `src` product 继承（产物与源码同许可） |
| `declared` | 生产者人工声明 |
| `upstream` | 从上游元数据转录（未经字节核对） |

**协议不强制 `extracted`**，但 catalogue 可以按 basis 排序/过滤 —— 这是**给人判断的**，
不是协议判据（避免"逼人造假"）。

### 4.4 `excluded[]`（包内不分发的东西）

```jsonc
"excluded": [
  {"path": "subprojects/*", "why": "git submodule 未 vendored，不在本 release"},
  {"path": "tests/runtests", "why": "上游以未知许可分发，已从 tarball 删除"}
]
```

至少有一条时，`why` 必须非空。**这不是判据面**（协议不能验证"你真的删了"），
它是**留痕**：`Files-Excluded` 的对手，让"我们知道包里有东西不能分发"这件事可查。

---

## 5. 客户端义务（`schema: 3`）

```
1. GET manifest.json
2. schema != 3 ⇒ 拒收（V10 整体拒收，不做向后兼容）
3. 校验 V1–V15（本地，0 请求）
4. 对每条要消费的 entry：
     expr = entry.license ?? manifest.license.expr
     manifest.license.status == "declared" ⇒ 展示 expr，交付字节
     status == "unstated" / "refused"      ⇒ 默认拒绝解包；
        错误文案必须带 manifest.license.reason（客户端知道为什么，不是 404）
```

**客户端不联网核实、不解析正文、不合并来源。** 它消费一个**已经裁决好**的表达式。

若生产者给了 `LicenseRef-<x>`，客户端**照原样展示**，不去追定义 ——
需要理解自定义许可的客户端才去读 `provenance` 指的那条 entry。

---

## 6. 与 catalogue / 站点的关系

| 层 | 承载什么 |
|---|---|
| **manifest（v1.1）** | 逐 release 的许可真相（**唯一产地**） |
| **catalogue** | 只加派生摘录（见下），**不放正文、不放 `provenance` 全量** |
| **站点页** | 每条 release 显示 `status` + `expr`；本站自身 AGPL-3.0 单独声明 |

catalogue 条目的增量（**派生，不手写**）：

```jsonc
"license": {
  "status": "declared",
  "expr": "GPL-3.0-or-later AND BSD-3-Clause AND LicenseRef-public-domain",
  "basis": "extracted",              // provenance.sources[0].basis
  "resolver": "spdx-norm@1",
  "manifest_sha256": "..."           // 与顶层同名——可复核"这份摘录来自哪份 manifest"
}
```

**为什么不复制完整 `provenance`**：那是第二个产地，必然漂移。
摘录只保留**能复核来源**的最小集。

### 6.1 catalogue 闸门 G7（新增）

| 闸 | 判据 | 反向用例 |
|---|---|---|
| **G7** | `license.status == "declared"` 且 `expr` 非空 | `unstated` / `refused` / 缺 `license` ⇒ **不进 catalogue**（记入 `excluded` 并写原因） |

**「合法」与「可上架」是两件事**：`unstated` 的 manifest 是合法 schema 3
（校验器全绿），但它进不了 catalogue。这条分界正是「坏的从未上架」。

---

## 7. 迁移（16 条现有 release）

| 阶段 | 动作 | 谁 |
|---|---|---|
| **M0（现在）** | 校验器仍只认 `schema: 2`；v1.1 实现完成后同时认 3 | 本仓 |
| **M1** | 生产者重发 manifest（**asset 一个不动**，只换 `manifest.json`），加 `license` 与 `amends` | extra-content / LLVM |
| **M2** | 派生器开 G7；schema 2 的旧 release 仍进 catalogue 但标 `license.status: "absent"` | 本仓 |
| **M3** | 全部有 schema 3 ⇒ 关 schema 2 通道；`ACCEPT_SCHEMA` 改 3 | 本仓，由用户裁定时机 |

**`amends`（许可修订锚）**—— 让"只改许可、不动字节"可证伪：

```jsonc
"license": {
  "amends": {
    "prior": {"bytes_digest": "<旧 manifest 算出的字节投影>", "manifest_sha256": "<旧 manifest>"},
    "at": "2026-11-02T10:00:00Z",
    "why": "补标许可；字节未动"
  },
  ...
}
```

**V15**：`amends.prior.bytes_digest` 必须等于**本** manifest 算出的 `bytes_digest`
（`bytes_digest` = 对所有 entry 的 `(product,name,bytes,sha256)` 排序后取 sha256）。

理由：现有 16 条 release 字节一个都不会变，但 manifest 从 schema 2 变 3。
没有 `amends`，这次补发在协议看来与"重新发布"不可区分。

### 7.1 迁移真值（实测，来自 `packages/*.json` 的 `fa-copyright` 链接）

| release | 表达式 | 档位 |
|---|---|---|
| 10 × forge（cgi 除外） | `GPL-3.0-or-later` | 短档 |
| `forge-cgi` | `GPL-2.0-or-later` | 短档 |
| `forge-geometry` | `GPL-3.0-or-later AND BSL-1.0` | 短档 |
| `forge-matgeom` | `BSD-2-Clause-FreeBSD` | 短档 |
| `forge-optim` | `GPL-3.0-or-later AND BSD-3-Clause AND LicenseRef-public-domain` | 短档 |
| `forge-splines` | `GPL-3.0-or-later AND LicenseRef-public-domain` | 短档 |
| `supply-msl` | `BSD-3-Clause` | 短档 |
| `supply-pyodide` | `BSD-3-Clause`（+ `MPL-2.0` 的 core 走 entry 覆盖） | 长档 |
| `LLVM-wasm v0.1.5` | `Apache-2.0 WITH LLVM-exception`（部分 entry 不同） | 长档 |

**14/16 条只需要一个字段。** 迁移不是重做调研，是转录
（`upstream.links[icon="far fa-copyright"].label`）。

---

## 8. 复跑方式（本文所有事实的出处）

```bash
# ① apt copyright 覆盖率（§2.1 的 3265 / 3237）
ls -d /usr/share/doc/*/ | wc -l
ls /usr/share/doc/*/copyright | wc -l

# ② 四条规则（§2.2）
head -40 /usr/share/doc/accountsservice/copyright          # Files: * + 特例
grep -hE '^License: .* (or|and) ' /usr/share/doc/*/copyright | head -5
grep -hE '^Files-Excluded' /usr/share/doc/*/copyright | head -3
grep -A4 '^Comment:' /usr/share/doc/apt/copyright | head -8  # best-effort 态度

# ③ 现状：manifest 无许可字段（§1）
gh release download forge-optim-1.6.3 -R ArchivalEra/Octave-Extra-Content \
  -p manifest.json -D /tmp/lic && python3 -c \
  "import json;print(sorted(json.load(open('/tmp/lic/manifest.json'))))"
#   ⇒ ['chunkSize','codecs','entries','id','products','schema']

# ④ 迁移真值（§7.1）—— 许可在 upstream.links 的 fa-copyright 里
cd /mnt/hdd/zcode-projects/Octave-Extra-Content && python3 -c "
import json,glob
for f in sorted(glob.glob('packages/*.json')):
    d=json.load(open(f))
    print(d['name'], [l['label'] for l in d['upstream']['links'] if 'copyright' in l.get('icon','')])"

# ⑤ 仓级 license 不可信（§1）
gh api repos/ArchivalEra/LLVM-wasm --jq .license.spdx_id          # ⇒ AGPL-3.0
gh api repos/ArchivalEra/Octave-Extra-Content --jq .license.spdx_id  # ⇒ NOASSERTION
```

---

## 9. 实现与自证（落地判据）

| 件 | 增量 | 自证 |
|---|---|---|
| `tools/check-release-v4.py` | V11–V15 | 每条不变量 **≥2 条反向用例**；正向用例必须真绿 |
| `scripts/sync-catalogue.py` | G7 + catalogue 摘录 | `unstated` 必须被排除；`declared` 必须进 |
| `scripts/build-site.py` | 许可列 + AGPL 页脚 | 已有（13 PASS） |
| **零下载** | V11–V15 全部不碰盘/网 | 自证里不得出现网络调用 |

**三档自证**（本仓纪律）：正常不报 / 该报必报 / 空输入必报。
**每条失败信息必须点名 entry**（`[wasm32/numgradient.oct] V14 …`），否则多条报红时无从定位。

---

## 10. 被否的方案（防将来重开）

| 方案 | 判据 |
|---|---|
| **DEP-5 式 `Files:` glob + first-match-wins** | 客户端要重实现匹配器 + 优先级 + 命名空间；三个独立实现必然分歧。真实数据不支持（8/13 单一许可） |
| **每 entry 一个 license（无默认值）** | 45 个分片写 45 次同一事实；v4 §2.2 已批判同类错误 |
| **三跳继承（entry → product → src product）** | 对真实数据过度优化；两级（entry → manifest）已够，且少一跳就少一处歧义 |
| **完整 `TermNode` 结构树（8 种 op）** | 对 16 条真实数据是过度设计；`render` 文法要写死维护，成为新的漂移面 |
| **catalogue 存完整许可正文** | 第二个产地，必然与 manifest 漂移 |
| **强制 `basis: "extracted"`** | 逼生产者造假（很多包没有可读的 COPYING）；apt 自己写 "best effort" |
| **只在站点页脚标总许可** | 正是当前的问题：读者无法区分 `forge-optim` 与 `LLVM-wasm` |
| **允许 `unstated` 进 catalogue** | 违反「坏的从未上架」——不知道就是不知道，不能上架 |
| **`Files-Excluded` 做成硬判据** | 协议无法验证"你真的删了"；只能留痕（`excluded[]` + `why`） |

---

## 11. 未决项（不阻塞定稿）

| # | 问题 | 当前处置 |
|---|---|---|
| **L1** | `public domain` 该用 `LicenseRef-public-domain` 还是单列布尔 | 用 `LicenseRef-` + `provenance` 指路（SPDX 自带逃逸舱） |
| **L2** | `amends` 是否要求保留上一份 manifest 的 sha | 可选。给了就核，没给不拒 |
| **L3** | 阶段 M3 的切换日期（会下架旧 schema） | 等生产者补齐后由用户裁定 |
| **L4** | 是否需要 DEP-5 全文文件作为 release asset | 可选。作为 `role:"license"` 的普通 entry 即可，不新增 asset 种类 |
