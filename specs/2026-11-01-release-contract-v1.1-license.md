# 发布契约 v1.1 · 许可证协议（草案，待裁）

> **状态**：**草案**（2026-11-01）。尚未进 manifest schema、未实现校验器。
> **依据**：用户裁定「各个资源组件都需要明确标注各自的 license」，以及
> 「去翻找 apt 官方的 copyright 附带方式，然后设计协议」。
> **本文所有 apt 侧事实均取自本机 `/usr/share/doc/*/copyright` 实物 + DEP-5 规范**，
> 复跑方式见 §7。**未经实测的推断在文中显式标注为「待验」。**

---

## 0. 为什么需要 v1.1（问题陈述）

当前 `schema: 2` 的 manifest **没有任何许可字段**（实测：`chunkSize` / `codecs` /
`entries` / `id` / `products` / `schema` 六个键，无 `license`）。后果：

| 现状 | 问题 |
|---|---|
| 站点只标本站 AGPL | **收录的 release 许可不明** —— 读者无法知道 `forge-optim-1.6.3` 能不能商用 |
| 字节来自第三方（Octave-Forge） | `Octave-Extra-Content` 的 LICENSE 明写「Package bytes ... governed by each package's own license (see COPYING inside its tarball)」，**那份 COPYING 在 tarball 里，不在任何元数据里** |
| 客户端只拉字节 | 用户拿到 tarball 才知道许可 —— **太晚**，且很多包根本没有 COPYING |

**这不只是「标注」问题，是分发合规缺口。** apt 早就遇到过，它的答案是 `copyright` 文件。

---

## 1. apt 的官方做法（实物调研）

### 1.1 机制

Debian 每个包在 `/usr/share/doc/<pkg>/copyright` 附带一份**机器可读版权文件**
（DEP-5，全称 *Machine-readable debian/copyright file*）：

```
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: <名称>
Upstream-Contact: <联系>
Source: <上游地址>

Files: *
Copyright: <年份 作者>
License: <SPDX 短名>

Files: <具体路径>
Copyright: ...
License: ...
```

**实测覆盖率**（本机，2026-11-01）：

```bash
ls -d /usr/share/doc/*/ | wc -l      # ⇒ 3265
ls /usr/share/doc/*/copyright | wc -l # ⇒ 3237   （99.1%）
```

⇒ `copyright` 在 apt 生态里是**近乎强制**的约定，不是可选装饰。

### 1.2 从实物里提取到的四条关键规则

| 规则 | 实物证据 |
|---|---|
| **`Files:` 用 glob，`*` 兜底** | `/usr/share/doc/accountsservice/copyright`：`Files: *` 给默认，后续 `Files: src/user.c ...` 覆盖特例 |
| **`License:` 是短名（SPDX 风格），全文单独成段** | 同上文件：正文引用 `GPL-3+`，文末 `License: GPL-3+` 段落给全文或指向 `/usr/share/common-licenses/` |
| **多许可用 `or` / `and`** | `/usr/share/doc/aha/copyright`：`License: MPL-1.1 or LGPL-3+`；`apt/copyright`：`License: GPL-2+ and curl` |
| **`Files-Excluded:` 声明「原样有但不分发」** | `/usr/share/doc/7zip/copyright`：`Files-Excluded: CPP/7zip/Compress/Rar*`（RAR 代码是非自由许可，删掉了） |

**`apt/copyright` 的 `Comment:` 段还写了句诚实的话**（我直接抄它的态度）：

> "This file is a best effort to document the statements of copyright and licenses
> as stated in the file, but is not a complete representation of all copyright"

⇒ **协议不要求「完美」，要求「如实标注已知的与未知的」**。空白 ≠ 未知。

---

## 2. 设计目标与不变量

**目标（与 v4 同源）**：apt 的稳健 + HTTP 的简洁。
**核心判据（用户原话精神）**：坏的从未上架 —— 许可缺失的 release **不该进 catalogue**。

新增不变量（延续 V1–V10 编号）：

| # | 不变量 | 反向用例（必须拒） |
|---|---|---|
| **V11** | 每个 release 必须有 `license` 对象，且**至少一条** `Files:` 覆盖 `*` | 缺 `license` 键 |
| **V12** | `license.files[]` 的 `license` 字段必须是**非空字符串**；`custom` 许可必须附 `text` 或 `url` | `license: ""` |
| **V13** | `license` 里的 SPDX 标识必须在**开放词表**内（或显式 `custom`） | `license: "Proprietary-Please-Read"` 而未标 custom |
| **V14** | 若 `products[].src` 存在，`license` 必须覆盖源码产物（不能只标二进制） | 只有 `.oct` 有许可，`src` 裸奔 |
| **V15** | `license` 不得与 `id` 里的仓名矛盾（如声明 MIT 但仓 LICENSE 是 AGPL）—— **这条只在能读到上游时校验，读不到就明说跳过** | 待实现时细化 |

**V15 是软判据**，因为它依赖网络。按本仓纪律：**读不到就明说不查**，不假装通过。

---

## 3. 协议形态（manifest 增量）

**向后兼容性：不做。** `schema` 升到 `3`，旧客户端（只认 2）按 V10 整体拒收 ——
这正是 V10 存在的意义（用户裁定：「我们完全不必要进行向后兼容设计」）。

```json
{
  "schema": 3,
  "id": "Octave-Extra-Content/forge-optim-1.6.3",
  "license": {
    "files": [
      {
        "files": "*",
        "copyright": "2008-2023 The Octave-Forge developers",
        "license": "GPL-3.0-or-later",
        "url": "https://github.com/ArchivalEra/Octave-Extra-Content/blob/main/packages/optim.json"
      },
      {
        "files": "src/optim-1.6.3.tar.gz",
        "copyright": "2008-2023 The Octave-Forge developers",
        "license": "GPL-3.0-or-later"
      }
    ],
    "comment": "上游 COPYING 在 tarball 内；本条目如实转录，未逐文件核对。"
  },
  "products": { ... },
  "entries": [ ... ]
}
```

### 3.1 字段定义

| 字段 | 必需 | 语义 |
|---|---|---|
| `license.files[]` | ✅ 至少 1 条 | 与 DEP-5 的 `Files:` 段一一对应 |
| `files[]` 里的 `files` | ✅ | glob，`*` 表示兜底默认。**匹配的是 `entries[].name` 或 product id**（见 §3.2） |
| `files[]` 里的 `license` | ✅ | SPDX 标识（开放词表）；非 SPDX 用 `custom` + `text`/`url` |
| `files[]` 里的 `copyright` | ⭕ 建议 | 版权人/年份。**缺失不拒**（很多人不知道），但要有 `comment` 说明 |
| `files[]` 里的 `url` | ⭕ | 许可全文或声明出处 |
| `license.comment` | ⭕ | 诚实说明（「未逐文件核对」「上游无 LICENSE 文件」等） |

### 3.2 匹配语义（关键设计决定）

DEP-5 的 `Files:` 匹配**文件路径**。我们的 `entries[]` 有 `product` + `name`，
所以 glob 匹配 `<product>/<name>`（与 DEP-5 的路径观感一致）。

**解析顺序**：从最具体到最宽泛，**第一个匹配生效**（与 DEP-5 一致）。

**为什么不用「每个 entry 一个 license 字段」**（更简单的方案）：

- 一个 release 里 90% 的文件同许可 ⇒ 逐条写 = 45 次重复同一事实（v4 §2.2 已经批判过这个错误）；
- 但**确实需要逐 product 区分**（如 wasm 引擎 AGPL、示例代码 MIT）；
- `Files: *` 兜底 + 特例覆盖 = **两者兼得，且与 apt 心智模型一致**。

### 3.3 客户端义务

```
1. GET manifest.json
2. 校验 schema == 3（否则整体拒收 —— V10）
3. 校验 V11–V14（本地，0 请求）
4. 消费字节时，把 license 信息一并呈现（至少：许可名 + 出处 url）
```

**客户端不需要**联网取许可全文 —— `license.files[].url` 是给人看的，
`license.files[].license` 短名是给程序判断的。

---

## 4. 与 catalogue / 站点 的关系

| 层 | 承载什么 |
|---|---|
| **manifest（v1.1）** | 逐 release 的许可真相（**唯一产地**） |
| **catalogue** | 只加一个 `license_summary` 摘录（如 `["GPL-3.0-or-later"]`），**供列表页显示**；完整信息仍在 manifest |
| **站点页** | 每条 release 显示许可短名 + 链到 manifest；本站自身 AGPL-3.0 单独声明 |

**为什么不把完整 license 复制进 catalogue**：那就是第二个产地，必然漂移
（与 catalogue 从 release 派生的原则一致）。

---

## 5. 迁移与门槛

| 阶段 | 动作 |
|---|---|
| **1（现在）** | 站点标 AGPL；catalogue 允许无许可字段（现状） |
| **2（v1.1 落地）** | manifest 支持 `schema: 3` + `license`；校验器加 V11–V14（带反向用例）；**catalogue 默认仍收 schema 2，但在页面上标「许可未声明」** |
| **3（收紧）** | 只收 `schema: 3`；无许可的 release **不进 catalogue**（与「坏的从未上架」一致） |
| **4（自愿）** | 生产者提供 `copyright` 全文文件（DEP-5 形态）作为 release 的额外 asset |

**关键：阶段 3 的切换是破坏性的**，会让现有 16 条全部下架。所以必须先让生产者补齐
（extra-content 15 条 + LLVM 1 条），**然后再切**。切换时机由维护方裁定。

---

## 6. 未决项（待你裁）

| # | 问题 | 我的倾向 |
|---|---|---|
| **L1** | `Files:` glob 匹配 `<product>/<name>` 还是只匹配 `name`？ | `<product>/<name>`（能区分同名的 wasm32/wasm64） |
| **L2** | 缺 `copyright` 字段该不该拒？ | **不拒**（很多包不知道版权人），但要 `comment` 说明；与 apt 的「best effort」态度一致 |
| **L3** | 是否要求给 `copyright` 全文文件（DEP-5 完整版）？ | 阶段 4 才要求，v1.1 只要 `license` 短名 |
| **L4** | 阶段 3 何时切（会下架 16 条） | 等生产者补齐后，由你裁定日期 |
| **L5** | `license_summary` 放 catalogue 会不会成为第二产地？ | 只放**从 manifest 派生的摘录**（派生器读 manifest 时顺手取），不手写 |

---

## 7. 复跑方式（本文所有 apt 事实的出处）

```bash
# ① copyright 覆盖率（本文 §1.1 的 3265 / 3237）
ls -d /usr/share/doc/*/ | wc -l
ls /usr/share/doc/*/copyright | wc -l

# ② DEP-5 结构（Files: * 兜底 + 特例覆盖）
head -40 /usr/share/doc/accountsservice/copyright

# ③ 多许可写法（or / and）
grep -hE '^License: .* (or|and) ' /usr/share/doc/*/copyright | head -5

# ④ Files-Excluded（声明「原样有但不分发」）
grep -hE '^Files-Excluded' /usr/share/doc/*/copyright | head -5

# ⑤ 最佳努力声明（apt 自己的态度）
grep -A4 '^Comment:' /usr/share/doc/apt/copyright | head -8

# ⑥ 当前 manifest 无许可字段（问题陈述的依据）
gh release download forge-optim-1.6.3 -R ArchivalEra/Octave-Extra-Content \
  -p manifest.json -D /tmp/lic && python3 -c \
  "import json;print(sorted(json.load(open('/tmp/lic/manifest.json'))))"
#   ⇒ ['chunkSize', 'codecs', 'entries', 'id', 'products', 'schema']
```

---

## 8. 被否的方案（防将来重开）

| 方案 | 为什么否 |
|---|---|
| **每个 entry 一个 `license` 字段** | 45 个分片 → 45 次重复同一事实；v4 §2.2 已批判过同类错误 |
| **catalogue 里存完整 license 文本** | 第二个产地，必然与 manifest 漂移 |
| **只在站点页脚标一个总许可** | 正是当前的问题：读者无法区分 `forge-optim` 与 `LLVM-wasm` 的许可 |
| **强制每个 release 附 DEP-5 全文** | 门槛太高会逼人造假；apt 自己都写「best effort」 |
| **不做许可、只标本站 AGPL** | 合规缺口：字节来自第三方，本站声明管不到它们 |
