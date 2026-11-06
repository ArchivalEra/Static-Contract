# worker —— CF 站点线 Worker（static.mango-mesa.ccwu.cc）

本 Worker 是两条站点镜像线里 **Cloudflare 线的服务端**，2026-11-06 收编进本仓 main
（此前源码寄生在课程站仓 S26-1_202609 的 gitignored 目录里，用户裁定收回）。

## 职责（三段）

| 路径 | 行为 |
|---|---|
| `OPTIONS` | 204 + CORS 预检头 |
| `/<o>/<r>/releases/download/<tag>/<file>` | GitHub release 字节代理：`fetch` 默认 `redirect: follow`，边缘替客户端跟完 `github.com → 302 → release-assets` 两跳；Range / 条件请求透传；200/206 缓存 1 年 + immutable |
| 其余 | 站点产物**运行期回源** `raw.githubusercontent.com/ArchivalEra/Static-Contract/deploy-cf`；扩展名白名单 + 顶层裸名白名单（防开放代理）；目录缺尾斜杠 301 修正 |

`GET /health` 可查运行形态。

## 响应头三件套（ACAO / CORP / nosniff）

所有资源响应统一携带 `Access-Control-Allow-Origin: *` +
`Cross-Origin-Resource-Policy: cross-origin` + `X-Content-Type-Options: nosniff`。
原因：消费端（Octave-UI）跑在 COEP `require-corp` 上下文里，缺 CORP 时浏览器直接拦掉
——症状是「curl 全 200、浏览器全 ERR_FAILED」（Octave-UI mail/003）。
raw.githubusercontent.com 自带这两头，所以 **EdgeOne 主线**只在 release 路径上用规则
引擎补（`release-cors-acao` / `release-corp` 两条规则）；本 Worker 的响应全部自产，
一律带全。

## 部署

```bash
cd worker && npx wrangler deploy
```

或推 `worker/**` 让 `.github/workflows/worker-deploy.yml` 自动部署（需要仓库 secret
`CLOUDFLARE_API_TOKEN` + `CLOUDFLARE_ACCOUNT_ID`，未配置时该 workflow 静默跳过）。

## 为什么运行期回源而不是内联产物

内联是打包快照——只有重新部署才会变；而产物产地是本仓的 `deploy-cf` 分支
（`sync-deploy.yml` 派生、orphan 单提交强推）。运行期回源让「**deploy-cf 分支 =
唯一产地**」成立：站点发布即刻可见，不需要任何人跨仓重新部署。

## 与旧宿主的关系（不要再从旧目录部署）

Worker 名字沿用 `static-host`，从本目录 deploy 即完成接管。旧源码
（S26-1_202609 `.zcode/userscript/host/`）是 userscript 宿主 + 本 Worker 前身的合体：

- 它的 userscript 三路由（`/assistant.user.js` / `/card.png` / `/card.svg`）**已随收编
  移除**——那条线停止维护（用户裁定 2026-11-06），现在它们在本域 404；
- **不要**再从旧目录 deploy：那会把路由带回来、同时丢掉 release 代理与 CORP。
