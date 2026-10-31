# 001 · extra-content → Static-Contract：**静态分发契约正式移交**（定名 v1；从今天起由你维护）

**To:** Static-Contract（静态分发契约维护方）
**From:** Octave-Extra-Content（内容语义产地 / 本契约的临时作者）
**Date:** 2026-10-31
**Re:** 用户裁定：**这套协议自今日起定名 v1，移交你仓维护**。本信是完整移交包：
协议本体 + 工具链 + 四轮演化史（含被否方案）+ 未决项 + 维护边界 + 我第一次给你开的信箱。

---

## 0. 先说三件最要紧的

1. **定名 v1**，不是 v4。理由：**从未真正试点**——只在本地用真产物跑通过，没走完
   「生产者发 release → 分发方建站 → 消费者改链接」那条链。**没试点的东西不配叫 v4**。
   我这里的历史编号 v1–v4 是**四轮 design-it-twice 的迭代**，v4 是那一轮的产物，
   现在是它第一次被命名为**正式的 v1**。
2. **维护权移交给你**。本仓（`Octave-Extra-Content`）退为**上游需求方之一**，
   不再是契约的作者。今后 schema 变更、边界裁定、版本演进都归你。
3. **我这边所有相关文件的处置**：`specs/` 下 v1–v4 五份文档 + `tools/make-manifest-v4.py`
   + `tools/check-release-v4.py` + `questions/05` **全部转为你仓的原始材料**，
   我仓保留副本但**标注"已移交，权威在你"**。

---

## 1. 协议是什么（一句话 + 三句话）

> **一个 release = 一个不可变 tag = 一份 `manifest.json` + N 个扁平 asset。
> 名字只允许 GitHub 不会改写的字符 ⇒ `manifest.file` 与真实 asset 名恒等。
> 客户端只从 manifest 取名字，绝不拼 ⇒ 404 只有一种含义。一切字节走普通 GET。**

**目标（用户原话）**：**apt 的稳健 + HTTP 的简洁**。
- apt 的稳健 = **每条记录自足**（单独拿出来就能用，不靠交叉引用）；
- HTTP 的简洁 = **无 Range、无条件请求、无自定义头**，就是普通 GET。

---

## 2. 契约本体（你接手后这就是 v1 的正典）

### 2.1 名字白名单（**地基，实测得来**）

```regex
^[A-Za-z0-9_-][A-Za-z0-9._-]*$
```
外加：**不含 `..`**、**不以 `.` 结尾**、**≤ 255 字符**（GitHub 硬限）。
名长度**推荐 ≤ 64**（本协议自加预算，超 64 只警告不拦）。

**为什么必须有这条**——我实测了 GitHub 的静默改写面（**长度超限报 422，但改写不报错**）：

| 你写的 | GitHub 实际存成 | 后果 |
|---|---|---|
| `sp ace.bin` | `sp.ace.bin` | 空格→点 |
| `pct%41.bin` | `pct.41.bin` | `%`→点 |
| `paren(1).bin` | `paren.1.bin` | 括号被删 |
| `a中b.bin` | `a.b.bin` | 非 ASCII 删（**7 字符→5**） |
| `.hidden.bin` | `default.hidden.bin` | 前导点加前缀 |
| `dots...many.000` | `dots.many.000` | **连续点折叠** |
| `trailing-dot.` | `default.trailing-dot` | 尾点加前缀 |

**白名单的收益**：`file` 字段**就是** asset 名，**不需要「逻辑路径 ↔ 物理短名」映射表**。
这一条省掉了我前三轮设计里的所有 `slot`/`prefix`/定宽/映射层。

### 2.2 manifest 结构（三层各答一问）

```json
{
  "schema": 2,
  "id": "<repo>/<pkg>@<version>",
  "chunkSize": 5242880,
  "codecs": ["zstd", "gzip", "identity"],
  "products": {
    "src":    {"form": "pkg"},
    "wasm32": {"form": "octdir", "arch": "wasm32", "src": "src"},
    "wasm64": {"form": "octdir", "arch": "wasm64", "src": "src"}
  },
  "entries": [
    {
      "product": "wasm32",
      "name": "__bfgsmin.oct",
      "bytes": 57271,
      "sha256": "f878860d…09d4",
      "variants": [
        {"codec": "zstd", "chunks": [
          {"part": 0, "file": "wasm32____bfgsmin.oct.zstd.000",
           "bytes": 12692, "sha256": "785e172f…8e47"}]},
        {"codec": "gzip",  "chunks": [ … ]},
        {"codec": "identity", "chunks": [ … ]}
      ]
    }
  ]
}
```

| 层 | 答什么 | 为什么必须存在 |
|---|---|---|
| **`products`** | 有哪几个逻辑产物（`form` / `arch` / `src`） | 实测：`optim` 的 wasm32 与 wasm64 的 `.oct` **文件名 5/5 完全相同、字节 5/5 全不同**（`numgradient.oct` 17,025 vs 17,519 B，`cmp` 判 NO）。没有这层就无法区分 |
| **`entries[]`** | 每条载荷的完整字节身份（`bytes`/`sha256`/`variants`） | **apt 的稳健性**：每条记录自足 |
| **`variants[].chunks[]`** | 每个编码的分片 | EdgeOne 20MB+ 掉到 0.93MB/s 且传不完 ⇒ 必须 ≤5MiB |

### 2.3 十条不变量 V1–V10（fail-closed）

见 `specs/…-v4.md` §3。**校验器已全部实现并各有反向用例**（`tools/check-release-v4.py`）。

### 2.4 为什么不做 blob 去重（apt 的判据）

我一度采纳「内容身份层」去重（UI dist 21 路径/10 内容，能省 48.9% 资产）。**撤回了**，
因为实测 apt **明知冗余仍复制**：

```
amd64 索引：221 条 amd64 + 143 条 Architecture: all
i386  索引：146 条 i386  + 143 条 Architecture: all   ← 同一批 143 条复制一遍
```

**这不是懒，是「每条索引自足」**：`amd64` 客户端只下一个文件就得到完整可解集。
去重会引入「删一个 member 影响另一个」的耦合，apt 刻意不要。

⇒ **认下「同一内容多存几份」的代价。**

### 2.5 源码与产物同 release（AGPL 强制）

集群四仓实测全 AGPL。`products[].src` 指向同 release 内的源码 product。
**校验器已 fail-closed**：src 悬空 / 自指 / 指向带 arch 的 product / 无 arch 带 src
——四条全拒。

---

## 3. 工具链（可直接搬走）

| 工具 | 自证 | 说明 |
|---|---|---|
| `tools/make-manifest-v4.py` | **40 PASS / 0 fail** | 生成器：切块 → 每块独立压缩 → 算 sha → 写 manifest。支持递归目录、子目录扁平化、已压格式免压、gzip mtime=0 可复现、失败即清场 |
| `tools/check-release-v4.py` | **25 PASS / 0 fail** | 校验器：V1–V10 + 22 条反向 + 2 条空输入；带 `--base` 时**逐块对盘核 bytes+sha** |

**真数据实测**：OM 的 74,579,404 B wasm → 15 块 × 3 编码，校验 **168 PASS / 0 FAIL**
（含每个 codec 每块的对盘核对）。

**浏览器端到端**（三编码全通，**0 个带 Range/条件头的请求**）：zstd / gzip / identity
各自 15 块并发 → 逐块 sha → 解码 → 拼接 ⇒ sha 逐字一致。

---

## 4. 四轮演化史（**被否方案必须留，否则将来会重开**）

| 轮 | 方案 | 被否的判据 |
|---|---|---|
| 一 | `<asset>.<bytes>.<sha256>.codec.NNN`（111 字符） | **客户端 URL 正确性不可排查**：sha 错 / tag 错 / 名字截断 / 没发 全是同一个 404 |
| 二 A | 纯坐标 `z-000`（5 字符） | codec 靠单字母隐式表，加格式要加字母 = 改文法 |
| 二 B | 自证短名 `aid.codec.NNNN`（`aid=hash(...)`） | **名字里仍有需要计算的身份** = 第一轮的变体；引入两套哈希前映像作新兼容面 |
| 二 C | `slot.i.codec` + 零请求预检 | 骨架被采纳（白名单思想从这里长出来） |
| 三 A | 平铺四类记录（product/member/blob/chunk） | `blob` 去重撤回（见 §2.4）；chunk 平铺不抵复杂度 |
| 三 B | 按 arch 切索引（apt 式） | **实测亏**：optim 客户端 926 vs 923 B gz（亏 3B）却多 1 个串行请求（启动慢 33%） |
| **四（=v1）** | 白名单 + products/entries/variants | **采纳**。用户洞察：「只要强制会在 asset 后变化的名称不允许就行」 |

---

## 5. 未决项（移交给你裁定）

| # | 问题 | 我的倾向 | 结算判据 |
|---|---|---|---|
| **U1** | **zstd vs gzip 谁在前** | 现在是 `[zstd, gzip, identity]`，**但这是推断**（本地 zstd 反而更慢：627 vs 527ms，因本地无带宽差）。EdgeOne 上体积优势 5.5MB ÷ 2.4MB/s ≈ 2.3s 该赢 gzip，**但没测过** | 见 `questions/05`：真站各跑 5 次取中位数；zstd 不赢则顺序改 `[gzip, zstd, identity]` |
| **U2** | `chunkSize` 是否该按件可配 | 现在全局 5 MiB。**若某类内容最优值不同**（如大量小 html），可能要按 product 配 | 需要按内容类型的实测 |
| **U3** | 名字里带 `product__载荷名` 是否违反「只需认出格式和第几块」 | 我认为不违反（product 是必要的判别符，否则跨 arch 撞车），**但这点值得你重新裁**——你说过「只需 codec + index」 | 若你裁"更短"，则 `products` 层要换成数字短号 |
| **U4** | 集群里其余三家何时接入 | 未排期 | 试点链：生产者发 release → 分发方建站 → 消费者改链接 |

---

## 6. 维护边界（我建议，你裁）

**归你**：
- schema 定义与演进（`schema: 2` → 未来版本）
- V1–V10 不变量的增删改
- 名字白名单的收紧/放松（**必须先实测 GitHub 的改写面再改**）
- 各仓接入的验收判据

**不归你**（继续在各自仓）：
- **内容语义**（版本策略 / `form`/`content`/`consumer` 轴 / 许可台账）→ 我仓
- **引擎产物与构建事实**（`octave.build.json`）→ 宿主仓
- **站点装配与路由**（Astro base / 字面量重写）→ UI 仓
- **边缘与反代**（EdgeOne / isui.ren）→ Shirone

**一条硬纪律请你继承**：**数值/行为只认实测，复跑方式写在断言旁边**。
写不出复跑方式的句子只能当历史读，不许写成「现在如此」。
（这是我仓 `AGENTS.md` 的纪律 1，也是这轮踩过最多次的坑。）

---

## 7. 我这边刚修完的一轮（供你知道代码有多"新"）

这套东西刚过两轮双轴代码审查（Standards + Spec），**共 21 项发现全部处理**，其中：
- 6 个真 bug：`chunkSize` 撒谎、跨 product 同名撞车且 manifest **谎报 sha 不报错**、
  `src` 悬空不 fail-closed、gzip 随 mtime 变、CLI 不递归、`codecs[].prefix` 死字段
- 4 个第二轮才抓到的：**`... or True` 恒真假闸门**（自己犯了我在别人身上抓的那类错）、
  长度预算写了没做、失败留半个目录、`--` 分隔符误切

**所以请你先把它当"未试点的 v1"对待**，不要直接宣布稳定。

---

## 8. 信箱（我已给你建好）

```
Static-Contract/
  mail/
    README.md      ← 投递规则（编号递增 / 只追加不删 / read/ 归档 / 投递≠提交）
    001-extra-content-contract-handover.md   ← 本信
    read/
  scripts/
    mail-read.py   ← 零依赖读信工具（自证 9/9）
```

**注意**：你仓 `.gitignore` 是**白名单模式**（`/*` 全忽略，只放行三个文件）。
我已按规矩补了放行规则——**这是本集群踩过的坑：白名单下新增目录不加 `!路径`，
文件不进 git 且"看不见"**。

`mail-read.py` 用法：
```bash
python3 scripts/mail-read.py              # 列未读
python3 scripts/mail-read.py 001          # 读 + 自动归档进 read/
python3 scripts/mail-read.py --selftest   # 自证 9 条
```

---

## 9. 我改了本仓什么（边界凭据）

- **本仓**：`specs/2026-10-30-release-contract-v4.md` 顶部加"已移交，权威在 Static-Contract"标注；
  `STATE.md` 记移交事件；`tools/*-v4.py` 与 `questions/05` 保留副本并标注
- **你仓**：建 `mail/`（含 README + 本信）+ `scripts/mail-read.py` + `.gitignore` 放行
- **未替你提交**（投递 ≠ 提交）

---

## 10. 复跑方式（本信每个数字的出处）

```bash
cd /mnt/hdd/zcode-projects/Octave-Extra-Content
source /mnt/hdd/toolenv/bin/activate

# 生成器自证（40 条）
python3 tools/make-manifest-v4.py --selftest

# 校验器自证（25 条）
python3 tools/check-release-v4.py --selftest

# 真数据（74.5MB wasm → 15 块 × 3 编码 → 168 PASS）
python3 tools/make-manifest-v4.py --out /tmp/v1 --id "OM/omc" \
  --product omc:file:omc:/mnt/hdd/openmodelica-wasm-build/site-omc/omc/OpenModelicaCompiler_bg.wasm
python3 tools/check-release-v4.py /tmp/v1/manifest.json

# 浏览器端到端（三编码，验"全普通 GET"）
cd /tmp/v1 && cp /path/to/fzstd.mjs . && python3 -m http.server 8970 &
node /mnt/hdd/zcode-test/harness/poc-v4.mjs http://127.0.0.1:8970 zstd 8
```
