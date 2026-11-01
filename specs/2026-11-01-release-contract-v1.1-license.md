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

**许可就是一行字符串。** 没有对象树、没有三态、没有见证链。

```jsonc
{
  "schema": 3,
  "id": "Octave-Extra-Content/forge-optim-1.6.3",
  "chunkSize": 5242880,
  "codecs": ["zstd", "gzip", "identity"],

  "license": "GPL-3.0-or-later AND BSD-3-Clause AND LicenseRef-public-domain",

  "products": { ... },
  "entries": [ ... ]          // 可选：某条 entry 的 "license": "MIT" 覆盖默认
}
```

### 3.1 三层各管一件事（**这是 v1.1 的全部设计**）

| 层 | 谁看 | 判据 |
|---|---|---|
| **字节** | 下载者 | `GET <base>/<file>` —— **一条链接，普通 GET，不认识许可** |
| **manifest** | 需要完整性 / 发现的人 | `license` 一行字符串，**展示用**。不解析也能下包 |
| **catalogue** | 上架闸 | 没有 `license` ⇒ **不收录** |

**闸门只在上架时挡一次，不在每个消费者那里挡 N 次。**
这是用户 2026-11-01 的纠正：「人家只想下个包一条链接」。

### 3.2 字段

| 字段 | 必需 | 语义 |
|---|---|---|
| `license`（顶层） | ✅ schema 3 必填 | 一行 SPDX 表达式字符串。非空 |
| `entries[].license` | ⭕ 可选 | 覆盖默认。同样是**一行字符串** |
| `entries[].role` | ⭕ 可选 | `payload`（默认）/ `license` / `notice` |
| `entries[].excluded[]` | ⭕ 可选 | `{path, why}` —— 包内「原样有但不分发」（DEP-5 `Files-Excluded` 的对手） |

**没有的东西**（都是我在草案里加过、又删掉的）：`status` 三态、`provenance` 见证链、
`amends` 修订锚、`basis`、`resolver`、`anchor`、`source` 白名单。
判据见 §10。

### 3.3 客户端（**照旧，一行都没变**）

```
1. GET <base>/manifest.json          # 想发现的话
2. 校验 schema / V1–V11（本地，0 请求）
3. 逐字取 variant.chunks[i].file     # 绝不拼
4. GET <base>/<file>                 # 普通 GET —— 与许可证无关
5. 校验 bytes + 逐块 sha256 → 解码 → 拼接
```

**许可不出现在第 3–5 步的任何分支里。** 它只影响第 6 步之后的**展示**：

```
6. 界面显示 manifest.license（有就显示，没有就不显示）
```

**客户端不需要**：解析 SPDX、判断 `status`、联网核实、拒绝解包。
`license` 是**字符串**，不是闸门。

---

## 4. 不变量（V11，唯一一条）

| # | 不变量 | 反向用例（必须拒） |
|---|---|---|
| **V11** | `license` 是非空字符串，且是合法 SPDX 表达式（文法见 §4.1）。`entries[].license` 若存在同理。`role ∈ {payload,license,notice}`；`excluded[].why` 非空 | 缺 `license` / 空串 / `license` 是对象 / 小写算符 / 括号不配对 / `LicenseRef-` 空后缀 |

**零下载、零联网。** V11 只读 manifest 结构。

### 4.1 SPDX 表达式文法

```
expr := term (("AND" | "OR") term)*
term := id ["WITH" exception] | "(" expr ")" | license-ref
id   := ^[A-Za-z0-9][A-Za-z0-9.+-]*$
license-ref := ^LicenseRef-[A-Za-z0-9._-]+$
```

- 算符必须**大写**（`AND` / `OR` / `WITH`）——小写是常见写法错误，直接拒
- `WITH` 只作用于**单个标识符**（`(A OR B) WITH X` 非法），且**不许链式**（`A WITH B WITH C` 非法）
- 优先级 `WITH` > `AND` > `OR`（与 SPDX 一致）；括号只用于显式分组
- **客户端不需要实现这个文法** —— 它把 `license` 当字符串展示

### 4.2 为什么只有一条不变量

因为**协议不负责验证声明是否真实**。它能做的是：
- 要求声明存在且形状合法（V11）
- 要求**没有声明的 release 不上架**（G7）

「这个声明是不是真的」是发布方的责任，靠 `provenance` 之类的东西无法证明 ——
那只会让 manifest 变复杂，同时给客户端增加"必须检查"的假义务。

---

## 5. catalogue（唯一的闸门）

### 5.1 G7

| 闸 | 判据 | 反向用例 |
|---|---|---|
| **G7** | schema 3 且 `license` 是非空字符串 | 缺 `license` / 空串 / 是对象 ⇒ **不进 catalogue**（记入 `excluded` 并写原因） |

**「合法」与「可上架」是两件事**：schema 3 缺 `license` 的 manifest
是**非法**（V11 红），所以 G7 这里其实是双保险；真正的分界在
**schema 2 的迁移期放行**（见 §6）。

### 5.2 catalogue 摘录

```jsonc
"license": "GPL-3.0-or-later AND BSD-3-Clause AND LicenseRef-public-domain"
```

**就是一个字符串。** 不是对象、没有派生字段、没有 `manifest_sha256` 嵌套。

---

## 6. 迁移

| 阶段 | 动作 |
|---|---|
| **M0（现在）** | 校验器接受 schema 2 与 3；schema 3 必须有 `license` |
| **M1** | 生产者重发 manifest（**asset 一个不动**），加一行 `license` |
| **M2** | schema 2 的旧 release 仍进 catalogue，`license` 摘录为 `null` |
| **M3** | 通过 `ACCEPT_SCHEMA = (3,)` 关掉 schema 2 通道（时机由用户裁定） |

**重发 manifest 不需要重传 asset**：v4 的 asset 集合由 manifest 的 `file` 字段定义，
只要 `bytes`/`sha256`/`file` 逐字不变，asset 一个都不用动。

### 6.1 迁移真值（实测，来自 `packages/*.json` 的 `fa-copyright` 链接）

| release | `license` 一行 |
|---|---|
| 10 × forge（cgi 除外） | `GPL-3.0-or-later` |
| `forge-cgi` | `GPL-2.0-or-later` |
| `forge-geometry` | `GPL-3.0-or-later AND BSL-1.0` |
| `forge-matgeom` | `BSD-2-Clause-FreeBSD` |
| `forge-optim` | `GPL-3.0-or-later AND BSD-3-Clause AND LicenseRef-public-domain` |
| `forge-splines` | `GPL-3.0-or-later AND LicenseRef-public-domain` |
| `supply-msl` | `BSD-3-Clause` |
| `supply-pyodide` | `BSD-3-Clause` |
| `LLVM-wasm v0.1.5` | `Apache-2.0 WITH LLVM-exception` |

**13/13 条真实许可全部一行搞定，且全部通过 SPDX 文法**（2026-11-01 实测）。
迁移不是重做调研，是转录。

---

## 7. 复跑方式

```bash
# ① apt copyright 覆盖率（§2.1）
ls -d /usr/share/doc/*/ | wc -l        # ⇒ 3265
ls /usr/share/doc/*/copyright | wc -l  # ⇒ 3237

# ② 迁移真值（§6.1）
cd /mnt/hdd/zcode-projects/Octave-Extra-Content && python3 -c "
import json,glob
for f in sorted(glob.glob('packages/*.json')):
    d=json.load(open(f))
    print(d['name'], [l['label'] for l in d['upstream']['links'] if 'copyright' in l.get('icon','')])"

# ③ 现状：manifest 无许可字段
gh release download forge-optim-1.6.3 -R ArchivalEra/Octave-Extra-Content \
  -p manifest.json -D /tmp/lic && python3 -c \
  "import json;print(sorted(json.load(open('/tmp/lic/manifest.json'))))"

# ④ 校验器（V11 双向用例）
python3 tools/check-release-v4.py --selftest   # ⇒ 42 PASS / 0 fail
```

---

## 8. 实现与自证

| 件 | 增量 | 自证 |
|---|---|---|
| `tools/check-release-v4.py` | V10 接受 2\|3；V11 + `parse_spdx` | 42 PASS / 0 FAIL |
| `scripts/sync-catalogue.py` | G5 收双 schema；G7 | 18 PASS / 0 FAIL |
| `scripts/build-site.py` | 页面已标 AGPL；可加许可列 | 13 PASS / 0 FAIL |

三档自证齐备（正常不报 / 该报必报 / 空输入必报）；失败信息点名 entry。

---

## 9. 被否的方案（防将来重开）

| 方案 | 否决判据 |
|---|---|
| **DEP-5 式 `Files:` glob + first-match-wins** | 客户端要重实现匹配器 + 优先级 + 命名空间；三个独立实现必然分歧。真实数据不支持（8/13 单一许可） |
| **三态 `status: declared/unstated/refused` + `reason`** | **把「不知道」变成下载路径上的闸门**：`unstated` 时客户端要拒绝解包。违反「人家只想下个包一条链接」。而且「不知道」的正确处置是**不上架**，不是让客户端处理 |
| **`provenance` 见证链（anchor + sha256 + source 白名单 + basis）** | 意图是「证明声明真实」，实际只证明了「有份文件在这儿」。manifest 复杂了一个数量级，客户端多了"必须检查"的假义务。**协议证明不了真实性，别假装能。** |
| **`amends` 许可修订锚** | 为「补标许可不动字节」设计的可证伪断言。但重发 manifest 本来就只换 manifest.json、asset 不动 —— `amends` 是给一件**已经成立**的事加证明 |
| **完整 `TermNode` 结构树（8 种 op）** | 对真实数据是过度设计；`render` 文法要写死维护，成为新的漂移面。**结果所有实现都得解析它才能读懂** |
| **每 entry 一个 license（无默认）** | 45 个分片写 45 次同一事实；v4 §2.2 已批判同类错误 |
| **catalogue 存完整许可正文** | 第二个产地，必然漂移 |
| **允许无许可的 release 上架** | 违反「坏的从未上架」 |

---

## 10. 一句话收口

> **许可是一行元数据，不是一个协议层。**
> 字节下载路径不认识它；manifest 展示它；catalogue 用它决定收不收。
> 任何让「下载一个包」多一步的设计，都是偏离。
