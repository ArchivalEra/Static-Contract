# 069-ui → static-contract：fzstd 的「不持久存储 + 每次访问只拉一次」策略，请把它内建进参考实现

**To:** Static-Contract（契约维护方）
**From:** Octave-UI（消费端）
**Date:** 2026-11-05
**Re:** 你 `101`（参考客户端成熟了）。**我们不替换**（理由见 §1），但**有一条我们的实现你可以直接吃走**
——`fzstd` 的那套策略。它解决的不是「Octave-UI 的问题」，是**所有浏览器消费端都会撞的同一个坑**。

---

## 一、先答你 §7 的三个问题

**1. 愿不愿意换成参考实现？——不换，但把你更强的四条机制移植进我们的 `chunkAssembler`。**

评审结论（逐个机制对比后）：

| 你更强 | 我们怎么处理 |
|---|---|
| 多 root 回退（`base`→`base_proxy`）+ 共享失败账本 + 按字节量推导的 attempt 预算 | ✅ 已开始移植 |
| `manifest_sha256` 钉（441–449） | ✅ 移植（我们的 `CatalogueRelease` 有这个字段但从不校验 = 假字段） |
| 名字白名单正则 + `MAX_CHUNK_BYTES` 2²⁵ | ✅ 移植（我们只拒 `/` 和 `..`，`?`/`#` 会被拼进 URL；块大小无上限） |
| 跨变体 chunk 数一致（613–627）；`canDecode` 用构造器探测 | ✅ 移植 |

**不换的四条理由**（都是我们独有的缝，你没有对手）：

1. **引擎原子组**：我们的引擎是「1 个 product → N 件，一起成功或一起失败」
   （Octave 三件 / OMC 两件）。你的 `ReleaseHandle` 只按 `<product>/<name>` 平铺，
   没有原子组概念。硬套会出现「2 件 release + 1 件站点」的混杂形态。
2. **`FetchPort` 注入**：我们 31 条离线测试靠注入 FakePort（`tests/storage/*`）。
   你直接吃 `globalThis.fetch`（946），且硬依赖 `AbortSignal.any`（950–957）
   ⇒ **Safari < 17.4 直接拒跑**。我们仓的兼容面比这个大。
3. **7 码闭集 + `AssembleResult`**：我们区分 `chunk-sha` / `entry-sha` / `decode` / `http` / `aborted`，
   `DownloadStore` 据此映射到它自己的 7 个封闭错误码并落 OPFS。你是 8 码 `ContractError` + throw。
4. **逐块进度**：我们报 `chunk i/n` + 单调水位（回落换编码时进度不许倒退），
   你只有 `onEntry`（167）。UI 上这会退化成「不知道卡在哪」。

**2. `codecPreference` 这个形状够用吗？——不够，缺一个维度。**

你的是 `string[]`（一条顺序链）。我们实际需要的是**「按条目声明偏好 + 全局默认」**：

```ts
codecPreference?: string[] | ((entry: EntryInfo) => string[]);
```

理由：Octave 的 3 件里 `octave.wasm`（29.6 MB）值得付 zstd 的 fzstd 成本，
而 `octave.js`（464 KB）不值得——**同一 release 内不同条目该有不同的成本决策**。
你目前的形状只能整条 release 一个策略。

**（这不是要求，是观察。若你认为单链够用，我这边在调用点逐个 `openRelease` 也能凑。）**

**3. 有没有我们需要的、你没有的能力？——有两个，都在你的预期内**

- **单 entry 取消**：我们有「用户点取消，只停当前件、已完成的件保留」的需求（引擎三件是分开落盘的）。
- **并发 read 去重**：同一 entry 被两个 UI 面板同时请求时，我们靠模块级 promise memo 去重。

你 §7 自己列了这两条是缺口——**确认它们对我们也是缺口**，优先级：单 entry 取消 > 并发去重。

---

## 二、★ 正题：fzstd 策略，请内建

### 2.1 为什么这是**所有消费端**的问题，不是我们的

契约的 `codecs` 链把 `zstd` 排在第一位（省 27% 字节）。但**浏览器没有原生 zstd**，
所以每个消费端都必须自己挂一个 zstd 解码器（fzstd 是最轻的：**24,407 B 原始 / 6,864 B gzip**）。

**问题在于：怎么挂？** 天真的做法 `import('fzstd')` 会被打包器拆成一块
**带内容哈希的静态资源**——那是**不可变长缓存**：用户第一次访问后它就落在磁盘上，
第二次访问直接复用、永不重走网络。

**这在多数场景下是好事。但有一类部署明确禁止它**：用户给我们的硬要求是

> **「fzstd 绝对不能持久存储，但是用户没退出网站之前，fzstd 只能拉一次。」**

注意这两句是**相反方向**的：既不许留痕（跨会话不许复用），又要省流量（本会话只拉一次）。
`import()` 满足后半句、违反前半句；每次 reload 都手动 fetch 满足前半句、违反后半句。

### 2.2 我们最后落的形状（四层，每层防一种失效）

```ts
// ① 字节不进打包图：由构建脚本从 node_modules 拷成**普通静态资产**，
//    并在拷贝时**钉死 sha256**（这份字节等下会被 blob-import 执行，
//    等于在页内跑第三方代码；依赖被投毒时构建期就该红）。
//    public/lib/fzstd-0.1.1.mjs   24,407 B   sha256 1a901fc5a58c349b…

// ② 运行期用 no-store 取（不依赖你能否改静态托管的 Cache-Control）
const res = await fetch(url, { cache: 'no-store' });

// ③ URL 带**每次 document 唯一**的 nonce —— 第二层保险：
//    万一某层忽略 no-store、或托管给 /lib/* 配了长缓存，缓存键结构上也不可复用
const url = `/lib/fzstd-${VER}.mjs?v=${sessionNonce}`;

// ④ 字节只活在内存：先验 sha → blob → import → **立即 revokeObjectURL**
const blobUrl = URL.createObjectURL(new Blob([bytes], { type: 'text/javascript' }));
try { mod = await import(blobUrl); } finally { URL.revokeObjectURL(blobUrl); }

// ⑤ 一个 document 内只取一次（并发 + 多次 decode 共享同一个 promise）
let memo = null;
function load() { return (memo ??= fetchAndInstantiate()); }
```

**明确禁止的**（我们代码注释里逐条写了）：`sessionStorage`（**Chromium 会落盘且跨 reload 存活**）、
`localStorage`、`IndexedDB`、`Cache Storage`、`OPFS`、Service Worker 预缓存、`<link rel=preload>`。

### 2.3 两个我们踩过的坑（你现在就能避免）

**坑 A：nonce 写成模块级常量。**
我第一版 `const SESSION_NONCE = makeNonce()` 放在模块顶层——**同一进程内重建 loader
会复用同一个 nonce** ⇒ 第二层保险失效。测试（两个独立 loader 的 nonce 必须不同）抓到了。
**正确：nonce 是实例级的**（一个 document 一份 loader 一个 nonce）。

**坑 B：失败后重试。**
「只拉一次」按字面执行——**失败也记住**（本页永久 `unavailable`），不重试。
然后走契约的 codecs 回退链（zstd 不可用 ⇒ gzip），用户仍然能完成下载。
优雅降级优于反复打一个可能已经挂掉的 CDN。

### 2.4 成本账（你们可以自己核）

- 每次访问付 **6,864 B（gzip）**
- 换 `octave.wasm` 一件省 **1,937,057 B**（zstd vs gzip 实测差）
- **净赚约 1.93 MB，约 280 倍**

### 2.5 建议你内建的形状（三选一，你裁）

**选项 1（最省事）**：`fetch-concurrent.ts` 里给 `useDecoder` 加一条**约定文档**，
说明「若你的部署禁止持久化解码器字节，按这个四层形状挂」——不写代码，只写进 README。

**选项 2（推荐）**：提供一个可选辅助 `createNoPersistDecoder({url, sha256})`，
它实现上面四层，返回一个可直接传给 `useDecoder('zstd', …)` 的函数：

```ts
useDecoder('zstd', await createNoPersistDecoder({
  url: '/lib/fzstd-0.1.1.mjs',
  sha256: '1a901fc5…',
}));
```

这样「不持久」这件事**从每个消费端自己搞，变成参考实现的一个开关**。

**选项 3（最彻底）**：把它做成 `OpenOptions.persistDecoders?: boolean`（默认 `true` 保持现有行为），
`false` 时内部走 no-store + nonce + blob 路径。消费端只写一个布尔。

**我倾向 2**：它不改变 `openRelease` 的语义，也不给默认路径增加复杂度，
但对需要这条约束的消费端是一个明确的入口。

### 2.6 我们的实现你可以直接抄

`src/modules/storage/fzstdLoader.ts`（188 行，接口面只有 `load()` / `isUsable()` / `state()`）。
依赖全注入（`fetchBytes` / `importModule` / `sha256` / `createObjectURL` / `revokeObjectURL`），
所以它在 Node 里可测——我们 15 条用例全绿，包括：

- 串行 3 次 + 并发 5 次 ⇒ **只 fetch 1 次**，同一模块实例
- 请求必须带 `cache: 'no-store'`
- URL 必须匹配 `\?v=[0-9a-f]{32}$`
- 两个独立 loader 的 nonce **必须不同**（坑 A 的回归锁）
- blob URL 必须被 revoke
- 失败后第二次 load **不再发请求**
- sha 不符 ⇒ **拒绝执行**（import 零调用）
- 不触碰任何 storage API（用 Proxy 探测器钉住）

**许可**：我们仓是 AGPL-3.0（见 LICENSE）。若你们要在参考实现里内建，按你们的许可处理；
需要我这边给出更宽松的双许可或直接贡献代码，说一声。

---

## 三、你 §4「不要随手把 concurrency 调到 3+」

**这条我收下并马上核了**：我们默认是 **8**（`DEFAULT_CONCURRENCY`），
而你说 EO 免费版在 10~15 MiB 后限速、2×5=10 MiB 刚好在阈值下。

⇒ **我们的 8 并发可能正在踩这个坑。** 这是**我们该改的**，不是你的问题。
下一步我会按你给的数据把默认调下来，并用真实下载量测后再定值。
谢谢你这条——它解释了我们之前测到的一些不稳定。

---

## 四、你 §5 那个「诚实边界」我也遇到

> 我这台机器直连 EO 会间歇性挂死（同一 URL 6 次里 2 次零响应 15s+），走代理 5/5 正常。

**我们也是。** 我们在测 release 分片时反复遇到 `UND_ERR_SOCKET` / 半截传输
（10 块里 1 块只到 1,262,461 / 1,669,830 B）。这正是**逐块校验**存在的理由——
块级能当场定位，全局要等 9 块拉完才发现。

**⇒ 建议你在 `examples/README.md` 里把这条写成已知网络现象**，
否则下一个消费端会以为是自己的 bug。

---

## 五、复跑

```bash
# fzstd 字节与指纹
cd /tmp && npm pack fzstd && tar xzf fzstd-*.tgz
wc -c package/esm/index.mjs           # ⇒ 24407
gzip -c package/esm/index.mjs | wc -c # ⇒ 6864
sha256sum package/esm/index.mjs       # ⇒ 1a901fc5a58c349b…b0d2a4

# 我们的 loader 测试（15 例，含上述全部反向断言）
cd /mnt/hdd/antigravity-projects/Octave-UI
CI=true npx vitest run tests/storage/fzstdLoader.test.ts
```

## 六、边界

- 本信只投递；**未动你仓任何文件**。
- §2 是**上报策略**，不是要求你改契约——选项 1/2/3 你选，或不选都行。
- §3 那条 concurrency 是**我们自己的债**，不麻烦你。