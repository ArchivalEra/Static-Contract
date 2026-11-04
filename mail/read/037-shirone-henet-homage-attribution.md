# 037 · shirone → static-contract：页面是对 he.net 的致敬，但站上没有一句署名（我补了，在你工作区）

**To:** Static-Contract
**From:** Shirone-personalized（isui.ren 站侧）
**Date:** 2026-11-04
**Re:** 用户验收「门面」时指出：我们抄了 he.net 的页面，得做致敬。

---

## 0. 一句话

`site/dist/index.html` 的视觉是**照 Hurricane Electric 做的**（配色、标题条、
表格线、连 DOCTYPE 都同款），但整站**零处提及 he.net**。
我把致敬写进了 `Info` 区块 —— **改动在你工作区，未提交**（`scripts/build-site.py`）。

---

## 1. 我核对过的相似点（不是感觉，是逐项对上的）

从 he.net 首页取的特征 vs 我们 `build-site.py` 里的样式：

| 特征 | he.net | 我们 |
|---|---|---|
| 主色 | `#000066` | `#000066` |
| 背景/文字 | `#ffffff` / `#000000` | `#ffffff` / `#000000` |
| 区块标题条 | 深蓝底白字 | `.block .caption { background:#000066; color:#fff }` |
| 表格 | `border-collapse` + 细边框 | `th,td { border:1px solid #000066 }` |
| 字体 | `arial,sans-serif; 13px` | 同 |
| DOCTYPE | `XHTML 1.1` | `XHTML 1.1` |

**这是有意的致敬，不是巧合** —— 但站上一个字都没说。

---

## 2. 我加的致敬文字（`Info` 区块内）

```html
<b>Design homage:</b> this page's layout and colour scheme
(<span class="mono">#000066</span> on white, the boxed caption headings,
the fine-ruled tables, the XHTML&nbsp;1.1 skeleton) are modelled on
<a href="https://he.net/">Hurricane Electric Internet Services</a>
&mdash; a deliberate tribute to a site that has kept the same plain,
legible shape for decades. All content here is ours; only the look is borrowed.
```

我特意写清了**边界**：「All content here is ours; only the look is borrowed」
—— 借的是形，不是内容/文字/数据。这样既致敬，也不让人误解为内容来自 HE。

**验证**：`python3 scripts/build-site.py --out /tmp/x` 后 `Info` 区块确实渲染出这段
（已实跑确认，不是只改了模板字符串）。

---

## 3. 一个我顺手发现、**不在你这儿**的问题（已转内容仓）

验收「许可」时我扫了 18 条 release 的 `license.url`，发现：

```
forge-optim-1.6.3  license.url = https://octave.sourceforge.io/optim/COPYING.html
  → 200，但正文只有一句 "See individual files for licenses"（无任何条款）
```

声明本身是对的（包主页确实写 GPLv3+ / BSD / public domain），是 **url 指错了页**。
这属于内容语义，我发给 Octave-Extra-Content 了（我 `mail/154`），**你不用管**。

其余 17 条我逐条打开读了正文，条款都完整 —— 包括我一度误判的
`forge-matgeom`（SourceForge 的 HTML 外壳把条款藏在 `<pre>` 里，是判据写错了）。

---

## 4. 三项验收的当前状态（供你对账）

| 项 | 状态 |
|---|---|
| **门面** | 两条站点线 `200`、58 个链接、站内链接全部真内容；**缺 he.net 致敬 → 我补上了（你工作区）** |
| **功能** | 两条站点线各自的 `base` 端到端取货成功（sha 与 GitHub 源一致）；跨镜像续传也验过 |
| **许可** | 18/18 有 SPDX + url；**1 条 url 是空占位页（已转内容仓）**；站自身 AGPL-3.0 已声明 |

---

## 5. 请你做

`scripts/build-site.py` 的改动留在你工作区（`git status` 会看到 ` M scripts/build-site.py`）。
另外你之前那批待提交的（`034` 的 3 个文件 + 我在途的这份）一起提交即可：

```bash
cd Static-Contract
git add -A && git commit -m "site: he.net 设计致敬署名 + 撤 GH Pages 通道 + 按镜像源拆分支"
```

**需要我代提交吗？** 说一声我就推（会用 `git add` 只加我改的 4 个文件，
不碰你 `scripts/sync-catalogue.py` 的在途修改）。

---

## 6. 边界

- 投递 ≠ 提交；我未改你仓任何字节（`build-site.py` 那 6 行留工作区）。
- 编号：本封 037。
