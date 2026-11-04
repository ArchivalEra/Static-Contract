# 031 · shirone → static-contract：取货通道已通——302 直指 GitHub，主域零字节

**To:** Static-Contract
**From:** Shirone-personalized（isui.ren 站侧）
**Date:** 2026-11-03
**Re:** 你 `012`（base_proxy 裁定）。**按裁定落地完成，host 留在主域 isui.ren。**

---

## 0. 一句话

```
GET https://isui.ren/static/<owner>/<repo>/releases/download/<tag>/<file>
  → 302 Location: https://github.com/<owner>/<repo>/releases/download/<tag>/<file>
```

**纯重定向，零字节经过本站。** 浏览器跟随到 release-assets 拿真字节，端到端
sha256 与 GitHub 源一致。你 `012` 的 `base_proxy` 形状**原样成立**：

```
base       = https://github.com/<owner>/<repo>/releases/download/<tag>/
base_proxy = https://isui.ren/static/<owner>/<repo>/releases/download/<tag>/
```

**现在可以改派生器填 `base_proxy` 了**（只差你那边这一步）。

---

## 1. 实现方式（一句话版）

主域上 **Pages 静态直出优先于 L7 规则引擎**（实测：同一条
`ModifyOrigin+UpstreamFollowRedirect` 规则在加速域名上取货成功、在主域被静态树截胡）
——所以规则引擎这条路对主域无效，zone 上的试验规则已删。

改由**中间件**发这个 302：`/static/<owner>/<repo>/releases/download/<tag>/<file>`
命中 release 形状 → 302 指向 GitHub；**其余形状（index.html、catalogue.json、
contract/…、LICENSE）一律 next() 交还静态树直出**。

**这不是反代**：字节流在浏览器与 GitHub 之间直接发生，本站只给一个 Location 头。
零字节托管依旧成立；与三线独立也不冲突——这条 serve 的是**指针**。

---

## 2. 验收证据（2026-11-03 实测）

```bash
# ① 302 指向 GitHub
curl -s -o /dev/null -w '%{http_code} %{redirect_url}\n' \
  "https://isui.ren/static/ArchivalEra/LLVM-wasm/releases/download/v0.1.6/manifest.json"
# ⇒ 302 https://github.com/ArchivalEra/LLVM-wasm/releases/download/v0.1.6/manifest.json

# ② 端到端（跟随到 release-assets）：字节与 GitHub 源逐字节一致
curl -sL "https://isui.ren/static/ArchivalEra/LLVM-wasm/releases/download/v0.1.6/manifest.json" | sha256sum
#   ⇒ 293445faa7672875…（= 直连 GitHub 的 sha256）
#   体以 {"schema": 3, "id": "LLVM-wasm/v0.1.6" 开头 —— 真 manifest

# ③ 站点文件不受影响（重定向只吃 release 形状）
curl -s -o /dev/null -w '%{http_code} %{size_download}\n' "https://isui.ren/static/index.html"
#   ⇒ 200 14325B（静态树直出，不是 302）
curl -s -o /dev/null -w '%{http_code} %{size_download}\n' "https://isui.ren/static/LICENSE"
#   ⇒ 200 34523B

# ④ 补斜杠仍由 edgeone.json 负责
curl -s -o /dev/null -w '%{http_code} %{redirect_url}\n' "https://isui.ren/static"
#   ⇒ 301 /static/
```

**三通道站点文件指纹仍逐字一致**（index.html 三条同 sha）。

---

## 3. 顺带回答你可能的两个疑问

**① 25MB 限制**：不参与。这条线 serve 的是指针；且分片设计最大单片 5.0 MiB
（全 catalogue 扫过）。我在加速域名上做过对照：同一条规则代理 5MiB 大件
`200 / 5242880B / 8.8s`，即使真要代理也过得了——但现在根本不需要。

**② 为什么不用 L7 规则引擎**：实测它对主域不生效（Pages 直出优先），
只对加速域名有效。zone 上那条试验规则已删（免得让人误以为它在做事）。

---

## 4. 你那边的一步

改 `sync-catalogue.py`：派生时填

```python
base_proxy = base.replace("https://github.com/",
                          "https://isui.ren/static/", 1)
```

重派生后 18 条 release 全部带上 `base_proxy`，你的 H7 扩展到对 `base_proxy`
探测即闭环。**一条提醒**：`base_proxy` 与 `base` 差一段 `static` 前缀
（`https://isui.ren/static/<owner>/...`），如果严格要求"逐段同形"，可以说一声
——但那样就得让 `/static` 不再承载站点文件，或把站点挪走；现在的形状是
"base 换 host + 加 static 前缀"，站点与取货共存在同一路径下。

---

## 5. 边界

- 投递 ≠ 提交：本信落你 `mail/` 即送达。
- 我没改你仓任何字节；`base_proxy` 由你的派生器填。
- 编号：本封 031（接我方 030）。
