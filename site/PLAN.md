# 建站方案 · 分发站（准备稿）

> 状态：**准备**（2026-11-01）。本文是部署形态设计，**不是契约**——契约正典
> `specs/2026-10-30-release-contract-v4.md` 不因本文件改动。带「提案」标的部分待用户裁定。

## 0. 站点是什么（一句话）

**一份 release 目录本身就是一个可托管的站点子树。** 契约 §4 里客户端唯一需要"知道"的
URL 是 `<base>/manifest.json`，其余全部逐字取自 manifest —— 所以分发站没有路由、没有
后端、没有动态逻辑，**任何能应答普通 GET 的静态托管都合格**。

## 1. 站点树 = release 树

生成器产物直接就是站点子树（`python3 tools/make-manifest-v4.py --out <dir> …`）：

```
<dir>/
  manifest.json                              ← 唯一入口
  src__optim-1.6.3.tar.gz.identity.000       ← 全部扁平 asset
  wasm32____bfgsmin.oct.zstd.000
  …
```

分发站 = N 个 release 子树 + 一份站点自己的目录索引（见 §2，站方语义，不属契约）。

## 2. URL 布局（**提案，待裁**）

```
/catalogue.json                        ← 站点索引：id / 版本 / base URL 清单（站方语义）
/r/<id>/<version>/manifest.json        ← release 入口
/r/<id>/<version>/<asset>…             ← 扁平 asset（名字 = manifest.file 逐字）
```

- manifest 的 `id` 形如 `Octave-Full-Wasm/optim-1.6.3`（`<repo>/<pkg>@<version>`）；
  URL 里 `@` 与 `/` 不进 asset 名（白名单只约束 asset），目录层级是站方的自由度。
- 布局变更**不碰契约**：客户端拿到的 base URL 由 catalogue 或上游链接给，站方随时可改。

## 3. 硬约束（每条带出处）

| 约束 | 出处 |
|---|---|
| 一切字节走**普通 GET**：无 Range、无条件请求、无自定义头 | 正典 §4；实测 poc-v4.mjs 三编码 0 条件头（正典 §5.3） |
| 分片 ≤5MiB（`chunkSize ≤ 2^25`） | 正典 §3 V6；EdgeOne 20MB+ 掉到 0.93MB/s 且传不完（正典 §2.1） |
| asset 名过白名单，`manifest.file` 与盘上名字逐字恒等 | 正典 §1；GitHub 改写面实测表 |
| entry / asset 数**无上限**（平台容量是分发方的事，不进协议） | 正典 §3「无上限」，用户裁定原话在案 |

## 4. 边界（如实）

- **管**：发布产物的字节分发（manifest + 分片 asset 的静态托管）。
- **不管**：站点路由与渲染；UI 的 Astro 产物（自带内容哈希，Pages 直出）；内容语义
  （`form`/`content`/`consumer` 轴，归 extra-content）；引擎构建事实（归宿主）。

## 5. 部署目标（**开放裁定**）

| 选项 | 判据 |
|---|---|
| GitHub Pages（本仓直接托管 release 树） | 零基建、push 即上线；代价：大二进制进 git 历史仓膨胀 |
| EdgeOne Pages（isui.ren 同款边缘） | 集群已有部署链（Shirone/UI）；5MiB 分片正是按它的实测掉速设计的 |
| 对象存储 / 其它 | 换平台不改契约（正典 §3：部署形态与内容语义解耦） |

**试点路径建议**：先本地 `http.server` + `poc-v4.mjs` 验全链（零部署），真站再上边缘。

## 6. 试点链验收判据（U4 的落地，可勾选）

1. ☐ 生产者（宿主 / extra-content）对一个真包（候选：`optim 1.6.3`，实测数据现成）产出 release
2. ☐ 分发站托管该 release，`catalogue.json` 可拉
3. ☐ 消费者（Octave-UI）改链接：从 `manifest.json` 起，全程普通 GET，逐块 sha + 总 sha 逐字一致
4. ☐ 复跑记录落本仓（纪律 2：数字旁边写复跑方式）

## 7. 下一步

1. 用户裁 §2 布局与 §5 部署目标 → 写 `tools/make-catalogue.py`（release 目录 → catalogue.json）
2. 接 `optim 1.6.3` 真 release 跑通本地全链
3. 上边缘部署，顺手结悬案 05（zstd vs gzip 真链路 5 次取中位数）
