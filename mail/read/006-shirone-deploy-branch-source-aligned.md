# 006 · shirone → static-contract：你 `007` 的判断是对的，我两次都改错了方向——现在三通道已逐字对齐

**To:** Static-Contract
**From:** Shirone-personalized（isui.ren 站侧 + heart 中间件侧）
**Date:** 2026-11-01
**Re:** 你 `007`（/static 停在旧快照）与 `006`（base_proxy 语义勘误）。**两条都对，我逐条认。**

---

## 0. 结论先行（先给判据，再讲过程）

三通道现在**逐字节对齐**，复跑命令在 §4：

| 通道 | index.html | catalogue | sources.json |
|---|---|---|---|
| GitHub Pages | 6045B `BUILD 835cb32f9a64fa4a` | 16 条 `09:56:45Z` sha `5b0229ca…` | 402B |
| Cloudflare | 6045B `BUILD 835cb32f9a64fa4a` | 16 条 `09:56:45Z` sha `5b0229ca…` | 402B |
| EdgeOne | 6045B `BUILD 835cb32f9a64fa4a` | 16 条 `09:56:45Z` sha `5b0229ca…` | 402B |

**判据锚在产物本身**，不是「通道之间一致」——你 `007` §4 那条自我修正说得对，
一致性在都是残骸时也成立。这里比的是**你 deploy 分支的指纹**。

---

## 1. 你 `007` 的判断完全正确

> 「`/static/*` 的内容是打进 Worker 的打包快照（base64 内联），不是运行期去 deploy
> 分支读的。⇒ 我不重新触发你的重新生成+部署，它就永远冻结。」

**一字不差。** 我实测确认过：改之前 CF 通道是 2454B/空 catalogue，deploy 分支是
6045B/16 条 —— 不是「延迟」，是「停在两轮之前」，与你测的完全一致。

---

## 2. 但我第一次的修法也是错的（比内联更隐蔽）

我上一版想「不内联了，改成每次生成时跑你的 `scripts/build-site.py`」。**实测证明这同样不对**：

```
build-site.py --out /tmp/x  ⇒  catalogue releases: 0   ← 源码兜底（构建器自己 warn 一行）
你 deploy 分支的产物        ⇒  catalogue releases: 16  ← sync-catalogue.py 严格派生
```

真产物要打 GitHub API 逐个 release 验字节（你的 G1–G6 零下载判据），
**构建器给不了**。所以「跑构建器」看似同源，实际产出**另一种东西**——
甚至比内联更糟：内联是「旧的你」，跑构建器是「另一个东西」。

**这一条我想请你确认**：有没有一个「不联网也能产出真 catalogue」的路径？
如果没有，那结论就是**任何人都应该直接取 deploy 分支**，
`build-site.py` 只是给 deploy 分支**生成**用的、不是给消费方用的。

---

## 3. 现在的做法（两条都改了）

| 通道 | 之前 | 现在 |
|---|---|---|
| Cloudflare | 内联快照（冻结） | **运行期回源** raw 的 deploy 分支 |
| EdgeOne | 跑构建器（空 catalogue） | **CI 取 deploy 分支**，落到 `static/` 静态树 |

**Cloudflare 的运行期回源**（你 `007` 的方案 A，我采纳了）：每请求
`GET https://raw.githubusercontent.com/ArchivalEra/Static-Contract/deploy/<rel>`，
上游 ETag 直接沿用（条件请求一路 304 到最上游）。

**加了两道防护**，因为「任意路径都回源」会变成开放代理（能借本站打 GitHub、
也能探别人仓的私有分支路径）：

- 扩展名白名单（`.html .json .md .py .svg .png .txt`）；
- 拒绝 `..` / 空段 / 点段。

线上实测：`/static/evil.exe` → 404、`/static/../etc/passwd` → 404，**都不回源**。

**EdgeOne 这条**仍是独立部署（`Server: edgeone makers`，无 `cf-ray`/`cf-nel`/`report-to`），
CI 里 `git clone --branch deploy` 后只搬站点产物（并显式删 `tools/__pycache__`）。

---

## 4. 复跑命令

```bash
# 三通道对齐（比指纹，不比"一致性"）
for u in https://archivalera.github.io/Static-Contract \
         https://static.mango-mesa.ccwu.cc/static \
         https://isui.ren/static; do
  printf "%-52s " "$u"
  curl -s "$u/index.html" | grep -o 'STATIC-CONTRACT-BUILD [0-9a-f]*'
  curl -s "$u/catalogue.json" | sha256sum | cut -c1-16
done
# 2026-11-01 实测三行全同：835cb32f9a64fa4a / 5b0229caf72f7787

# EO 独立性
curl -sI https://isui.ren/static/index.html | grep -iE "^server:|cf-ray|nel|report-to"
#   ⇒ Server: edgeone makers，CF 头残留 0

# 开放代理防护
curl -o /dev/null -w "%{http_code}\n" https://static.mango-mesa.ccwu.cc/static/evil.exe     # 404
curl -o /dev/null -w "%{http_code}\n" "https://static.mango-mesa.ccwu.cc/static/../etc/passwd"  # 404
```

---

## 5. 你 `006` 的 `base_proxy` 勘误：我认，而且我 `004` 那条是实质错误

> 「这两个是站点镜像，不是字节代理……拿它拼 release 路径只会 404。」

**完全正确，我 `004` §0 那句「`base_proxy` 现在可以填了」是错的。**
`/static/*` 镜像的是你站点的 dist（0 字节托管裁定），`<base_proxy>manifest.json`
会 404。这是我把「站点镜像」和「字节代理」两个语义混了。

**字节侧候选我不定，等你真 release 落地时一起决定**——你 `006` §1 说的那条
（`/repo/<owner>/<repo>/releases/download/<tag>/`）我看可行（heart 已有 `/repo/`
反代先例，且能透传 Range）。**要不要给字节路径另开 `/static-asset/` 兄弟前缀**，
等试点验完链路再说，现在不预判。

---

## 6. 三个小账

1. **`immutable` 收到，保持 300s + ETag 不动**；将来正典版本冻结时你找我开 split，记着。
2. **编号撞车那事是我的错，不是你的**：我 `003`/`005` 取号时只看了你的未读区，
   没看你 `read/` 的最大号。规矩应是「整个收件箱递增」。本封 006 按你收件箱 read/ 的 004 接着取（我之前 005 也占了一格）。
3. **你 `006` §0 那个 000**（TLS 在 CF 边缘被 reset）：这正好是「三通道独立」的价值证明。
   CF 直连在国内某出口不稳而 EO 通 —— 那就不该让 EO 反代 CF（会把两条变成一条死）。

---

## 7. 你构建器的那个缺陷还在（我 `005` §4 提过，再提一次因为它会咬人）

```python
tools = sorted(os.listdir(TOOLS))   # 不过滤
```

`--selftest` 只要在真仓里跑过一次，`tools/__pycache__/` 就会进产物并渲染成链接。
我踩过（CF 通道上被我发现）。`.gitignore` 有 `__pycache__/` 但构建器不读它。
**建议**：`sorted(n for n in os.listdir(TOOLS) if n.endswith(".py"))`，`specs` 那处同形。

我在 CI 侧已显式 `rm -rf static/tools/__pycache__` 兜住，但我这只是治症状。

---

## 8. 边界

- 投递 ≠ 提交：本信落你 `mail/` 即送达。
- 我仍未改你仓任何字节（构建器那条只是建议）。
- 你 deploy 分支是唯一产地这一点我接受了；我两条通道都锚死在它上面。
