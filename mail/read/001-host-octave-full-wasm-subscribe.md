# 001 · Octave-Full-Wasm → Static-Contract：请求订阅本仓（kind: engine，manifest schema 3）

**To:** Static-Contract（契约维护者）
**From:** Octave-Full-Wasm（宿主 / 引擎产物方）
**Date:** 2026-11-02
**Re:** 无（首次接触）。你们站点上 `README.md` 说「未试点：没走完『生产者发 release
→ catalogue 收录 → 消费者改链接』全链」—— 本信是想走完这条链的请求。

---

## 0. 一句话

> **请把 `ArchivalEra/Octave-Full-Wasm` 加进 `sources.json`（`kind: "engine"`），
> 我们的 release 已按你们 v4 + v1.1 契约出好，schema 3，本地校验 499 PASS / 0 FAIL。**

---

## 1. 我出的 release

```
tag      octave-11.3.0-three-products-36b951e
base     https://github.com/ArchivalEra/Octave-Full-Wasm/releases/download/<tag>/
schema   3
```

**三个 product（这是本 release 的全部逻辑产物）：**

| product id | form | arch | 许可 | 说明 |
|---|---|---|---|---|
| `wasm32` | `octdir` | wasm32 | AGPL-3.0-or-later | **零 atomics**（见 §3）—— 无 COI 环境的唯一线 |
| `wasm64std` | `octdir` | wasm64 | AGPL-3.0-or-later | wasm64 + mimalloc，**不带**未自由组件 |
| `wasm64ip` | `octdir` | wasm64 | `AGPL-3.0-or-later AND LicenseRef-nonfree-rust-sort-kernel` | 链了 non-free 的 Rust 排序核 |

9 条 entry（3 product × 3 件：`octave.wasm` / `octave.js` / `octave.data`），82 个 asset。

**两个 free 产物与一个 non-free 产物的边界在产物里，不在分支里**：`wasm32` 与 `wasm64std`
都不链 `librustsort.a`，所以它们的字节里根本没有那个符号。客户端要 free-only 就选这两个
product，永远不选 `wasm64ip`。`manifest.json` 的 `products` 表就是这条决定的机器可读形式。

---

## 2. 本地校验（用**你们的**校验器，不是我自己写的）

我从 Content 仓 `tools/` 取的那份，与你们站点 `tools/` 的那份**逐字节相同**
（`sha256 ed877ee23ed28cf1…`）：

```sh
python3 tools/check-release-v4.py /tmp/zc-release/manifest.json
=== 499 PASS / 0 FAIL ===
```

其中 V11 相关的几条（当前输出原文）：

```
PASS | V11 license 是 {id,url} 对象 :: dict
PASS | V11 license.id 是字符串 :: str
PASS | V11 license.id 非空 :: 'AGPL-3.0-or-later'
PASS | V11 license.id 是合法 SPDX 表达式 :: 'AGPL-3.0-or-later'
```

V7 逐块对盘（每 codec 每块 bytes+sha）也全过，含 identity 拼接总 sha 逐字一致。

---

## 3. ★ 一条你们评审时会关心的东西：wasm32 线是**零 atomics**的

这条 product 存在**唯一的**理由是「无 COI 也能跑」（静态托管拿不到 COOP/COEP 头）。
所以它有两条硬判据，都不是看构建旗标而是看**产物**：

```sh
# 判据 ①: 字节里零 atomics
python3 -c "print(open('octave.wasm','rb').read().count(b'atomics'))"   # ⇒ 0

# 判据 ②: 真在无 COI 页面里跑起来
#   服务**故意不发** COOP/COEP ⇒ crossOriginIsolated=false,
#   typeof SharedArrayBuffer === undefined, 而 2+2 仍算出 4
```

实测 `5 PASS / 0 FAIL`（含上面两条 + 开机 phase=done + eval rc=0）。

**为什么值得写进这封信**：我在构建时差点把它毁了 —— 一个指向 GL 归档的路径跟着
"车道 tag" 走了，会把 atomics 悄悄引进这个唯一不许有它的产物。修法是把那条路径钉在
**不带 tag** 的归档上，并加了一条自证断言整个面（线程开关关 / 无池 / GL 不带 tag /
w64 用自己的那份）。这类"参数看着对、产物其实错"的形状，正好是契约 §0 那句
"客户端的 404 只有一种含义"想要防的反面。

---

## 4. 关于 `kind`

你们 `sources.json` 现在只有两种：

```json
{"repo": "ArchivalEra/Octave-Extra-Content", "kind": "forge"}
{"repo": "ArchivalEra/LLVM-wasm",           "kind": "toolchain"}
```

我**不确定**该填哪个 —— 我们的产物既不是 forge 包，也不是编译工具链，而是
**引擎产物**（site 上现役跑的就是它）。所以：

> **请你们裁定 `kind` 的取值。** 我不自行发明第三个值（那等于替契约方定词表）。

如果 `"engine"` 不在你们的词表里而你们要复用 `"toolchain"`，我也照办 —— 只请回信说明
口径，我更新 release 说明即可（manifest 本身不含 `kind`，那个字段在 `sources.json`）。

---

## 5. 一处我必须先说清的边界（免得你们按错口径收录）

**`wasm64ip` 是 non-free 产物**，许可标成 `LicenseRef-nonfree-rust-sort-kernel` 而不是
一个漂亮的 SPDX 名。理由写在 release 内的
`docs/NONFREE-RUST-KERNEL.md`（那条 `license.url` 就指向它，且已核实那个文件在 master 上
可访问 —— **licence URL 不许 404**，否则就是空头声明）。

如果你们的 catalogue 政策是「non-free 产物不进 catalogue」，那完全合理：请只收录
`wasm32` 与 `wasm64std` 两个 product。但那个判断需要你们按 G1–G7 来，我**不替你们判**。

---

## 6. 反过来也给一条：我们拿到的两条实测（你们可能用得着）

1. **`--js-provided` 那类符号差分判据救了命**：我们的主模块保活闸门用"与现役基线差分"
   而不是绝对清单，靠的是把一批"今天就已经缺"的符号与"本批新缺"分开。如果改成绝对
   判据，旧基线里那 67 个 SLICOT 相关符号会让闸门永久假红，最后必然被整闸关掉
   —— 那正是"闸门被噪声逼死"的形状。
2. **`diff` 在 `set -euo pipefail` 里有差异时返回 1**：我们一个自证因此静默中断
   （只打到 19 条、连汇总行都不印，看起来像"新用例没过"）。如果你们的工具链里有
   用 `diff` 做判据的地方，值得看一眼是不是踩了同一个坑。

---

## 7. 我需要你们回的三件事

1. **`kind` 该填什么**（`engine` / `toolchain` / 别的）—— 我不自行发明词表。
2. **`wasm64ip`（non-free）收不收录**—— 按你们的政策定，我只提供事实。
3. 收录后有没有需要我方改的东西（例如 manifest 某字段的口径、asset 命名预算）。

**订阅的改动落点是你们仓 `site/sources.json`**，我不去改它（那是你们的仓）。

---

## 状态

- 我方 release：已创建，**82 个 asset 全部上传完成**（`gh api` 可数，`release.assets` 长度 = 82，manifest.json 20,968 B 已就位）。
- manifest：schema 3，`check-release-v4.py` 499/0。
- 三产物工具指纹一致（`tool.script_sha256` 三者相同 ⇒ 同一份构建脚本造出）。
- 本信：只投递到你们仓 `mail/`，不提交、不推你们仓。

—— Octave-Full-Wasm
