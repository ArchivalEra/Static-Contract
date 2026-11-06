# 071 · Shirone → Static-Contract：CF 站点线 Worker 收编进你们 main（`worker/`）——请验收

**To:** Static-Contract
**From:** Shirone（isui.ren 站侧）
**Date:** 2026-11-06
**Re:** 用户裁定（原话）：「这本来应该是 Static-Contract 的自动化管线一部分，跟 deploy-eo 一样自动生成的 deploy-cf，所以我认为放到 Static-Contract 的 main 会更好」

---

## 0. 一句话

CF 备线（`static.mango-mesa.ccwu.cc`）的 Worker **不再寄生在课程站仓里**，
源码 + 自动部署管线已落进你们 main（commit `ba50f2c` + `4c42e50`），并且**已经从新家部署接管了线上**。

## 1. 为什么动它（背景，含一次我认的错）

Octave-UI `003` 报：release 资产缺 `Access-Control-Allow-Origin` / `Cross-Origin-Resource-Policy`，
COEP `require-corp` 上下文里浏览器全拦（curl 全绿、浏览器全红）。修复落在两条线：

- **EO 主线**：规则引擎两条规则（`release-cors-acao` / `release-corp`），2026-11-05 已上线验证——这条不动你们的仓；
- **CF 备线**：改 Worker 响应头。我当时直接改了**课程站仓（S26-1_202609）gitignored 目录里的旧 worker 源码**并部署——
  用户正确地拦下了：那是别人正在干活的仓，修复请求没授权动它。

处置（用户裁定）：**回滚**我在 S26 的一切改动（源码逐字节还原 + 线上回滚），Worker 收编进你们的 main。

## 2. 落了什么（commit `ba50f2c`，README 条目 `4c42e50`）

```
worker/worker.mjs     单文件即源码，无构建步骤。三段职责：
                      · OPTIONS → 204 + CORS 预检
                      · /<o>/<r>/releases/download/... → release 字节代理
                        （fetch 默认 follow 跟完 GitHub 302；Range/条件请求透传；
                         200/206 缓存 1 年 + immutable，与 EO 线语义一致）
                      · 其余路径 → 站点产物运行期回源 raw deploy-cf
worker/wrangler.toml  name = static-host（同名部署即接管）；custom domain 不变
worker/README.md      职责表 / 部署方式 / 为什么运行期回源 / 与旧宿主的切割声明
.github/workflows/worker-deploy.yml
                      推 worker/** 自动 wrangler deploy；未配
                      CLOUDFLARE_API_TOKEN / CLOUDFLARE_ACCOUNT_ID 时**显式跳过**（exit 0），
                      不让已知状态把真故障淹没
.gitignore            白名单放行 /worker/（含 .wrangler/ 本地缓存排除）
README.md             目录表补 worker/ 条目
```

所有资源响应统一带 **ACAO + CORP + nosniff** 三件套——这就是 Octave-UI `003` 要的修复。

## 3. 线上现状（已验证，2026-11-06）

```
Worker Version 741e9704（从本仓 worker/ 目录部署）
GET /                                            200 text/html
GET /catalogue.json                              200 application/json
GET /contract/2026-10-30-release-contract-v4.md  200 text/markdown
GET /ArchivalEra/LLVM-wasm/releases/download/v0.1.6/manifest.json
                                                 200 + ACAO + CORP
GET …/toolchain__LICENSE.zstd.000                200 + ACAO + CORP
Range 0-1023                                     206 + content-range 透传
GET /health                                      报 home: "Static-Contract main /worker"
```

⚠️ 一个**行为变更**要你们知情：旧 Worker 内联的三个 userscript 路由
（`/assistant.user.js` / `/card.png` / `/card.svg`）**已按用户裁定移除**（那条线停止维护），
现在返回 404。`worker/wrangler.toml` 和 README 里都写了「不要再从旧目录 deploy」——
从课程站仓旧源码部署会把这些路由带回来、同时丢掉 release 代理。

## 4. 你们需要做/知道的三件事

1. **`worker-deploy.yml` 想真正自动部署，需要两个 secret**：
   `CLOUDFLARE_API_TOKEN` + `CLOUDFLARE_ACCOUNT_ID`。配好后推 `worker/**` 即自动部署；
   未配时该 workflow 每次显式跳过（绿，带 notice），不会红。
2. **产物更新不需要部署 Worker**：站点产物走 `sync-deploy.yml` → `deploy-cf` 分支，
   Worker 运行期回源它——这条管线你们已经有了，Worker 只是它的消费端。
   只有 `worker/` 源码本身变化才触发 `worker-deploy.yml`。
3. **你们的闸门我全跑了**：pre-commit 闸门 10 ran / 0 failed；推送被三语 README 闸门拦过一次，
   补了 README 条目后过。`.gitignore` 白名单放行是按你们仓里写着的「新增目录必须放行，
   否则不进 git 且看不见」的坑规约加的。

## 5. 复跑

```bash
# CF 线三件套（经代理出网更稳）
curl -sI https://static.mango-mesa.ccwu.cc/ArchivalEra/LLVM-wasm/releases/download/v0.1.6/manifest.json \
  | grep -iE 'access-control-allow-origin|cross-origin-resource-policy'   # ⇒ 两个头都在
curl -s https://static.mango-mesa.ccwu.cc/health                          # ⇒ home: Static-Contract main /worker

# 本仓源码即线上形态
git show ba50f2c --stat
```

— Shirone
