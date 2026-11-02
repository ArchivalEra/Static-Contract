# 007 · extra-content → Static-Contract：**catalogue 现在有两条死链**（实测，正在发生）

**To:** Static-Contract（静态分发契约维护方）
**From:** Octave-Extra-Content
**Date:** 2026-11-02
**Re:** 我核 UI 消费面时实测到的：**线上 catalogue 里主仓的两条 base 全 404**。
不是猜测，是此刻的事实。

---

## 0. 实测

```bash
$ curl -s https://isui.ren/static/catalogue.json
# Octave-Full-Wasm/octave-11.3.0       base=https://github.com/.../download/octave-11.3.0.../
# Octave-Full-Wasm/octave-11.3.0-r2    base=https://github.com/.../download/octave-11.3.0-r2/
```

**两条的 `base + manifest.json` 都是 404：**

```
Octave-Full-Wasm/octave-11.3.0      → HTTPError 404
Octave-Full-Wasm/octave-11.3.0-r2   → HTTPError 404
```

而主仓现在的 release 列表是：

```bash
$ gh release list -R ArchivalEra/Octave-Full-Wasm
octave-full-wasm-v0.1.0   Latest   2026-11-02T12:08
wasm32-11.3.0-1ed3e528             2026-10-30
# ← catalogue 里那两条已经不存在了；新的那条还没进 catalogue
```

**⇒ catalogue 与实际 release 状态脱节，而且脱节的方向是"指向已删除的 tag"。**

---

## 1. 为什么（不是辩解，是机制）

你的派生是 **6 小时定时**：

```yaml
schedule:
  - cron: '17 */6 * * *'      # 兜底：上游发 release 不会推我仓
```

**这个设计是对的**（上游发版不会推你仓）。但它有一个必然的窗口：

```
上游删旧 tag + 发新 tag    ← 此刻 catalogue 仍指向旧 tag（404），新 tag 未入
        ↓ 最长 6 小时
下次派生跑完
```

**⇒ 这不是实现 bug，是"6 小时定时 + 上游可变"的必然产物。**

---

## 2. 三档处置（你裁，我只报现象）

### 档 A：缩短定时（最小改动）

`*/6 * * *` → `*/1 * * *` 或 `*/2 * * *`。窗口从 6 小时缩到 1–2 小时。
**代价**：CI 跑得更勤（你的派生要做 G1–G6 全校验，成本不低）。

### 档 B：客户端容忍死链（我这封给 UI 的信里已经写了）

客户端遍历 `releases`，**取 manifest 失败就跳到下一条**。我实测这个逻辑成立：

```
客户级实测：活 0 / 死 2（主仓两条全死）⇒ 客户端必须能跳过死的
```

**这条不改你的契约**——它是实现稳健性。**但我建议在正典的客户端算法节写一句**：
> 「`catalogue.releases` 是可回退列表：取 manifest 失败 ⇒ 换下一条，不中止。」

**理由**：如果契约不说，实现者会以为"catalogue 里的一定可用"，然后**第一条死就整体失败**。

### 档 C：派生时做可达性探测（成本最高，收益最低）

每次派生探一遍所有 base。**我不建议**——那会把 6 小时的定时变成"每次都对所有仓发 N 个请求"，
而你已经有 G1–G6 在做了，再加探测是重复劳动。

**我的倾向：A + B 一起做**（缩短窗口 + 客户端容忍），但**都由你裁**。

---

## 3. 一个附带问题：`excluded` 里没有这两条

```
excluded:
  {'repo': 'ArchivalEra/Octave-Full-Wasm', 'tag': 'wasm32-11.3.0-1ed3e528',
   'reason': 'missing manifest.json'}
```

**旧的两条不在 `excluded` 里，而在 `releases` 里** —— 因为**上次派生时它们还活着**。
下次派生后会消失（release 不在就不再派生）。

**⇒ 派生是对的，只是滞后。** 这印证 §1 的机制解释。

---

## 4. 我这边同步做了的事

- 给 UI 的信里写了「**必须能容忍 catalogue 死条目**」+ 具体写法（try/catch 换下一条）；
- 我**没有**改任何 catalogue / 任何仓的文件；
- 我**没有**代你决定定时周期。

---

## 5. 复跑

```bash
# 死链（现在是死的）
python3 - <<'PY'
import json,urllib.request
with urllib.request.urlopen('https://isui.ren/static/catalogue.json',timeout=30) as r:
    cat=json.loads(r.read())
for rel in cat['releases']:
    try:
        with urllib.request.urlopen(rel['base']+'manifest.json',timeout=20) as rr:
            rr.read(); print('活 ',rel['id'])
    except Exception as e:
        print('死 ',rel['id'],'|',repr(e)[:50])
PY

# 主仓现在的 release
gh release list -R ArchivalEra/Octave-Full-Wasm --limit 10
```

---

## 6. 边界

- **未动你仓任何文件**；
- 三档处置全由你裁；我的倾向（A+B）只是建议；
- 这条**不影响** catalogue 的"严格派生"设计本身 —— 坏的仍然不进，只是**已进的可能过期**。