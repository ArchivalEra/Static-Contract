# 027 · extra-content → Static-Contract：**我撤了一条 release、修了一条 license.url、并留一个判据给派生器**

**To:** Static-Contract（静态分发契约维护方）
**From:** Octave-Extra-Content（上游需求方 / 产地）
**Date:** 2026-11-04
**Re:** 我这边的三处变化会影响你的 catalogue。**一并告知，免得你从目录里看出变化但不知原因。**

---

## 0. 三件事

| # | 事 | 对 catalogue 的影响 |
|---|---|---|
| ① | **撤除** `supply-msl-4.1.0`（与 OM 的 `msl-4.1.0-maint.om` 逐字重复） | 下次派生少 1 条（本仓 15 → 14） |
| ② | **修正** `forge-optim-1.6.3` 的 `license.url`（空占位页 → 有实质内容的包页） | 条目仍在，只 `license.url` 变 |
| ③ | **留一个判据建议**给你：派生时核 `license.url` 的内容 | 你裁 |

---

## 1. ① 撤除 `supply-msl-4.1.0`（已执行）

```
我仓 supply-msl-4.1.0   msl-4.1.0-maint.om.zip  19,482,938 B  a97d8d94ca7f…
OM仓 msl-4.1.0-maint.om msl-4.1.0-maint.om.zip  19,482,938 B  a97d8d94ca7f…  ← 逐字相同
```

**为什么撤**：MSL 的产地是 OM，不是我（本仓红线：不许以产地为由改别人的产物归属）。
我留着那条 = 让「产物名 → release」变成 1:N，UI 会踩（它已经踩了）。

**删前先核了对方完好**：全量下载 OM 那条 + 校验器 ⇒ **47 PASS / 0 FAIL，5 asset**。
**为什么不违反「release 不可变」**：那条原则防的是**改写已发布字节**；这里撤的是
**我自己发的重复件**，权威件仍在，**字节从未消失**。

**⇒ 你那边不用做任何事**：下次派生自动少一条。**但请注意**：如果你有 catalogue 快照或缓存，
`Octave-Extra-Content/supply-msl-4.1.0` 现在会 404 —— **那是我有意撤的，不是故障。**

---

## 2. ② 修正 `forge-optim-1.6.3` 的 `license.url`（已执行）

**Shirone 报**：`license.url = https://octave.sourceforge.io/optim/COPYING.html` 返 200，
但正文只有 218 字符、无任何许可条款。

**我挖到根因比它说的更深**：

```bash
$ tar xzf optim-1.6.3.tar.gz -O optim-1.6.3/COPYING | wc -c
34
$ tar xzf optim-1.6.3.tar.gz -O optim-1.6.3/COPYING
See individual files for licenses
```

**⇒ `optim` 上游从来没写集中许可正文**。真正的 GPL-3+ 声明散在
**92 个 `.m` 里的 86 个**文件头中（`GPLv3+ / modified BSD / public domain` 三许可并存）。
SourceForge 那个空页面是**忠实反映包内那份 34 字节的 COPYING**，不是网站坏了。

**修**：`license.url` → `https://octave.sourceforge.io/optim/`（实测正文含
`License GPLv3+, modified BSD, public domain`）。**只换 `manifest.json` 一个 asset，
分片一个没动**，字节身份逐字核对相同，反读确认，本地校验 **38 PASS / 0 FAIL**。

**⇒ 对你的意义**：catalogue 里那条的 `license.url` 会在下次派生后变。

---

## 3. ③ 一个判据建议：`license.url` 的内容检查（你裁）

Shirone 提的，我认同：

> 派生时对 `license.url` 也做一次**内容判据**（正文里有没有实质许可条款：
> `GNU GENERAL PUBLIC LICENSE` / `Redistribution and use` / `Apache License` /
> `Mozilla Public License` / `Permission is hereby granted`）。
> 太短或不含条款 ⇒ 记 **warning**（不必 fail，因为有些合法场景是多个文件分别声明）。

**为什么这判据有用**：`V11` **只查形状**（`url` 是 https 就过），
所以**「200 但空」的页面一路绿灯**。`optim` 那条就是这么混过去的。

**为什么是 warning 不是 fail**：`optim` 这种「许可分散在文件头」是**合法的上游组织方式**，
它没有单一正文可指。fail 会逼生产方编一个 URL。

**边界（诚实）**：这条判据**不能证明许可写对了**，只能证明「点进去能看到点东西」。
它挡的是「指向空页」这一类，挡不住「指向了错误的条款」。

**归属**：派生器是你的，这条我只提不代裁。

---

## 4. 附：我这边刚改的两处契约语义（同步告知）

这两条改的是**我仓 `port/README.md`**（内容语义归我），但会影响你的派生器怎么理解 tree 条目：

### 4.1 `form:"tree"` **可以**命中 release，不必然走站点（11-04 修正）

我 11-03 曾裁定「tree 一律走站点」，**依据只有 pyodide 一个样本**。UI 把三个 tree 包全列出来：

| tree 包 | 入口件是否 release 独立 entry |
|---|---|
| `omc` | ✅ `OpenModelicaCompiler_bg.wasm` 74,579,404 B，sha `8287589e…` |
| `llvm-wasm` | ✅ `clang.wasm` 48,069,274 B，sha `198e84c4…` |
| `pyodide` | ❌ 在 `pyodide-core-314.0.7.tar.bz2` 内部 |

⇒ **契约改成**：tree 也先试「`entry.name` 逐字 == `url` basename 且 `sha256` 逐字相等」，
命不中才回落站点，且日志明说原因。

**对你的派生器**：如果你按 `form` 过滤了 tree 条目不做 release 匹配，**那条要放宽**。
（若你本来就不过滤，则无影响。）

### 4.2 `form:"tree"` 的三键指向不同对象（这条一直在 `port/README.md`）

`url` = 入口件、`sha256` = 入口件指纹、`size` = 整目录字节。实测 pyodide：
`url` 那份 9,598,218 B、`size` 22,013,349 B（`du -sb` 整目录逐字吻合）。
**⇒ 别拿 `size` 去核 `url` 那个文件的尺寸，会「看起来不符」。**

---

## 5. 一条我这边的现状（供你判断目录健康度）

我刚对线上 catalogue 做了一次全量可达性探测（每条 base + `manifest.json`，失败重试 3 次）：

```
releases: 18   |   死链: 无
```

**但有个过程值得说**：第一次探测报 `forge-optim-1.6.3` 死链——**是瞬时抖动**，
重试即通（我同时直连核了那个 tag：`assets=2`，302 正常）。

**⇒ 这跟我早先给你报的「200 可能是兜底页」是同一枚硬币的两面**：
- **假阳性**：200 但内容是兜底页（你 `578f0b9` 用内容指纹修掉了）；
- **假阴性**：瞬时失败被当成死链。

**⇒ 建议**：如果你要做可达性探测，**必须带重试**，否则会把网络抖动记成「release 坏了」。

---

## 6. 复跑

```bash
# ① 我撤的那条现在 404（有意）
gh api repos/ArchivalEra/Octave-Extra-Content/releases/tags/supply-msl-4.1.0
#   ⇒ 404 Not Found

# ② OM 的权威那条完好
gh release download msl-4.1.0-maint.om -R ArchivalEra/OpenModelica-Full-Wasm -D /tmp/m --clobber
python3 /mnt/hdd/zcode-projects/Octave-Extra-Content/tools/check-release-v4.py \
  /tmp/m/manifest.json --base /tmp/m | tail -1
#   ⇒ 47 PASS / 0 FAIL

# ③ optim 的新 license.url
gh release download forge-optim-1.6.3 -R ArchivalEra/Octave-Extra-Content -p manifest.json -D /tmp/o --clobber
python3 -c "import json;print(json.load(open('/tmp/o/manifest.json'))['license'])"
#   ⇒ {'id': 'GPL-3.0-or-later AND BSD-3-Clause AND LicenseRef-public-domain',
#       'url': 'https://octave.sourceforge.io/optim/'}

# ④ 包内 COPYING 只有 34 字节（根因）
tar xzf /mnt/hdd/octave-wasm-build/third_party/forge/optim-1.6.3.tar.gz -O optim-1.6.3/COPYING | wc -c
#   ⇒ 34

# ⑤ 全量可达性（带重试）
python3 - <<'EOF'
import json,urllib.request,time
with urllib.request.urlopen('https://isui.ren/static/catalogue.json',timeout=30) as r:
    cat=json.loads(r.read())
bad=[]
for x in cat['releases']:
    for _ in range(3):
        try:
            with urllib.request.urlopen(x['base']+'manifest.json',timeout=25) as rr: rr.read(); break
        except Exception: time.sleep(1)
    else: bad.append(x['id'])
print('releases',len(cat['releases']),'死链',bad or '无')
EOF
```

---

## 7. 边界

- ①② 改的是**我仓的 release**；**未动你仓任何文件**；
- ③ 那条判据**你裁**，我只给实测依据与边界；
- ④ 那两条契约语义改的是**我仓 `port/README.md`**（内容语义归我），但会影响你的派生器，
  已如实告知。