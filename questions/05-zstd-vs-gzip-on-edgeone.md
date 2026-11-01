# 悬案 05：v4 的 zstd 变体在 EdgeOne 真链路上是否真的比 gzip 快（本地实测反了）

**Status:** needs-triage

**Raised:** 2026-10-31（v4 落地时，两轴审查逮到「推断被写进活状态」）

## 事实

**本地实测（`python -m http.server`，三编码同输入）**：

| 编码 | 传输字节 | 本地总耗时 |
|---|---|---|
| zstd | 15,349,112 | 627ms（含解码器加载 7ms） |
| gzip | 20,908,462 | 527ms |
| identity | 74,579,404 | **392ms** |

**本地 gzip 比 zstd 快 100ms，identity 最快**——因为本地无带宽差，
zstd 的 26.6% 体积优势一分钱也换不到，反而多付解码器加载 + 解码 CPU。

## 为什么这是悬案而不是结论

v4 的 `codecs` 把 `zstd` 排第一，理由是**推断**：
> 真实 EdgeOne 上，zstd 靠 26.6% 体积优势（21.0MB → 15.3MB）会赢。

**这条推断没有实测支撑**：
- 本地无带宽限制 ⇒ 体积优势不可见；
- EdgeOne 实测带宽是 **2.2–2.7 MB/s**（3–10MB 区间），21.0MB vs 15.3MB
  的差是 **5.5MB ÷ 2.4MB/s ≈ 2.3 秒**，远大于解码的 0.1–0.5 秒 ⇒ **理论上 zstd 该赢**；
- 但**没在 EdgeOne 真链路上量过**，所以只是推断。

按本仓纪律 5：「推断写进 `questions/` 并注明哪个实验能结案」，不许写成现状。

**Settling:** `node /mnt/hdd/zcode-test/harness/poc-v4b.mjs <真站>/<release> {zstd,gzip} 8` 各跑 5 次取中位数 —— zstd 中位数快 ≥10% ⇒ rc=0 结案（顺序成立）；zstd 不快或更慢 ⇒ rc=1（顺序应改 `[gzip, zstd, identity]`）；抖动压过差异 ⇒ rc=2（保持现状并明写"未经真链路验证"）。

## 结算判据（能结案的实验）

```bash
# 在 isui.ren 真链路（EdgeOne 反代）上，同一份分片产物分别按 zstd / gzip 拉全套，
# 各跑 5 次，取中位数比总耗时（含解码）。
for codec in zstd gzip; do
  for i in 1 2 3 4 5; do
    node /mnt/hdd/zcode-test/harness/poc-v4b.mjs "https://<真站>/<release>" $codec 8
  done
done
```

- **rc=0（zstd 中位数比 gzip 快 ≥10%）** ⇒ `codecs` 顺序 `[zstd, gzip, identity]` 成立，
  本悬案结案，结论写进 `STATE.md`。
- **rc=1（zstd 不更快，甚至更慢）** ⇒ **顺序要改成 `[gzip, zstd, identity]`**
  （gzip 是浏览器原生，零解码器）——这是本次审查建议的修正，但**不该在没测之前就改**。
- **rc=2（测不出来：EdgeOne 抖动压过差异）** ⇒ 保持现状并在 `STATE.md` 明写
  「顺序未经真链路验证，按体积理论选择」。

## 关联

- 该推断原写在 `STATE.md` 的 v4 条目里（「真实 EdgeOne 上 zstd 靠 26.6% 体积优势会赢，这条是推断」）
  ——**保留原话但指向本悬案**，不算违规（纪律 5 允许推断出现在活状态，条件是挂在悬案上）。
- 一旦结案，`tools/make-manifest-v4.py` 的 `--codecs` 默认值可能要改。
