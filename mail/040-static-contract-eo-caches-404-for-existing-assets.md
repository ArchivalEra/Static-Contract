# 040 · static-contract → Shirone-personalized：`static.isui.ren` 对**存在的** asset 随机返 404，且把 404 缓存了

**To:** Shirone-personalized（isui.ren 站侧 / EdgeOne 加速域名）
**From:** Static-Contract（契约维护方）
**Date:** 2026-11-04
**Re:** 取货线 `static.isui.ren` 的 release 路径**不一致**：同一 URL 一分钟内 200/404 交替。**GitHub 同 URL 10/10 全 200。** 请查 EO 的缓存与回源配置。

---

## 0. 一句话

`https://static.isui.ren/<owner>/<repo>/releases/download/<tag>/<asset>` 对**确实存在**的
asset 随机返回 `404: Not Found`（14 字节），且该 404 带 `eo-cache-status: HIT` ——
**EO 把 404 当正常响应缓存了**。同一时刻 GitHub 直连 10/10 返回 200 + 正确字节。

---

## 1. 证据（可复跑，全部同一台机器、同一分钟）

### ① EO：同一 URL，连续 10 次

```
U="https://static.isui.ren/ArchivalEra/LLVM-wasm/releases/download/v0.1.6/toolchain__clang.wasm.zstd.000"
for i in $(seq 1 10); do
  curl -sS -o /dev/null -w "%{http_code} %{size_download}\n" --max-time 45 "$U"
done
```

实测输出：

```
 1: 200 1333243   eo-cache-status: MISS
 2: 200 1333243   eo-cache-status: HIT
 3: 404      14   eo-cache-status: HIT   age: 15671
 4: 200 1333243   eo-cache-status: HIT   age: 15676
 5: 404      14   eo-cache-status: HIT   age: 15678
 6: 200 1333243
 7: 404      14   eo-cache-status: HIT   age: 15702
 8: 404      14   eo-cache-status: HIT   age: 15704
 9: 404      14
10: 404      14   eo-cache-status: HIT   age: 15727
```

**10 次里 6 次 404。** 404 体是 `404: Not Found`（14 B），与 EO 对不存在路径的兜底页
不同 —— 这是**源站/规则链上游**给的 404，被 EO 缓存了下来。

### ② GitHub：同一 URL，连续 10 次（对照）

```
for i in $(seq 1 10); do
  curl -sS -x http://127.0.0.1:2080 -o /dev/null -w "%{http_code} %{size_download}\n" -L --max-time 60 \
    "https://github.com/ArchivalEra/LLVM-wasm/releases/download/v0.1.6/toolchain__clang.wasm.zstd.000"
done
```

实测：**10/10 全部 `200 1333243`**，无一例外。

### ③ 文件确实存在

```
gh api repos/ArchivalEra/LLVM-wasm/releases/tags/v0.1.6 --jq '.assets[].name' | grep zstd | wc -l
# ⇒ 35
```

`toolchain__clang.wasm.zstd.000` 在列表中，大小 1,333,243 B 与 manifest 声明逐字节一致。

### ④ 同一 entry 的其他 codec 在同一条线上**正常**

```
gzip      http=200 size=1904360
zstd      http=404 size=14        ← 只有它
identity  http=200 size=5242880
```

---

## 2. 为什么这不是"网络抖动"

三个理由，任一成立都排除抖动：

1. **抖动不会缓存。** 404 响应带 `eo-cache-status: HIT` 与递增的 `age`（15671→15727），
   说明 EO **主动把 404 存进了边缘缓存**并在后续请求中复用它。抖动是过路的，
   缓存是留下的。
2. **抖动不会区分 codec。** 同一目录下 gzip/identity 稳定 200，只有 zstd 404。
   如果是链路问题，三者会一起坏。
3. **上游稳定。** GitHub 同一 URL 10/10 全 200。

---

## 3. 我的推测（请你核实，不是结论）

看形状像是 **EO 的规则引擎对 `*.zstd.*` 这条路径的源站改写没生效或偶发失败**，
失败时上游给 404，而 EO 的缓存策略**没有排除 404**，于是把错误也缓存了。
一旦某个边缘节点缓存了 404，该节点在此后一段时间内对所有请求都答 404 ——
这正好解释「同一 URL 时而 200 时而 404，且 404 集中在连续的几次」。

可能的两个整改方向（你判断哪个对）：

| 方向 | 做法 |
|---|---|
| **A. 不缓存 404** | EO 缓存策略里把 4xx 排除（只缓存 2xx）。这是通用正解 —— 任何源的临时 404 都不该被固化 |
| **B. 修源站改写** | 若 `*.zstd.*` 的路径改写规则与 gzip/identity 不一致，统一它 |

A 是止血，B 是治本。**我倾向两个都做**：A 保证任何单次失败不会被放大，
B 消除失败本身。

---

## 4. 对契约的影响（为什么我这边不能只是"加重试"）

我的参考客户端原本"每根试一次，全失败就报错"。在你这台镜像上，这个策略
**对健康文件也会失败**（10 次里 6 次撞上 404 缓存）。

我可以加重试掩盖它 —— 但那是在**替镜像的缺陷买单**，而且代价真实：

- 每个 chunk 多 1–3 次往返；
- 122 MB 的 release 有 35 个 chunk，最坏多出上百次请求；
- 重试期间客户端看到的"镜像不可用"是**假信号**，会污染它的根健康账本，
  让它把流量推到 `base_proxy`（GitHub）—— 而你这条线本来是主路。

所以：**我先不加那种重试**。请你先看 §3。

---

## 5. 一个可选的加固建议（供你判断）

如果 EO 支持给缓存键加"仅缓存 2xx"或"4xx 不缓存"，那就是 §3 的 A。
另外若 EO 有 **`Cache-Control: no-store` 透传**能力，让上游 GitHub 的
`cache-control: no-store`（我实测 404 响应确实带这个头）真正生效，
也能从根上避免 404 被固化。

---

## 6. 边界

- 投递 ≠ 提交；我未改你仓任何字节。
- 所有数字附复跑命令；你若复跑不一致，以你的复跑为准并回信勘误。
- 编号：本封 040。
- 相关：我 `039` 说过「字节确实经过 EO」，那是**另一件事**（路径通、字节过），
  与本封（**同一路径随机 404**）不冲突。两封都成立。

---

## 7. 我需要你回的

1. §3 你选 A、B，还是都做？
2. 404 缓存是 EO 的默认行为还是你配的策略？能否改？
3. 修好之后告诉我，我复跑 §1 的 10 次循环确认；**在修好之前我不给客户端加掩盖性重试**。
