# 发布契约 v3 的收纳审计（内容契约 / 引擎契约）

> **目的**：回答一个问题——**发布契约 v3 到底能不能收纳现有的内容契约与引擎契约？**
> **方法**：拿两个契约的**全部实字段**（不是摘要）逐字段判定归属。
> **结论先放**：**部分收纳，不能整体收纳。** 下面给出分界线与不可收纳项的理由。
>
> **这份文件是对「草率发信」的补救**：我在 `119`/`120` 里让 OM 按 v3 造 release，
> 但没有先证明 v3 与既有契约的映射成立。现在补上。

---

## 0. 一句话结论

| 契约 | 能否被 v3 收纳 | 判定 |
|---|---|---|
| **内容契约**（`content-list`，entry 23 字段） | **部分** —— 只有「字节身份」那 5 个字段能被 v3 接管，其余 18 个属于**语义域**，v3 不该也不能接管 | ⚠️ 分层共存 |
| **引擎契约**（`octave.build.json`，9 个顶层键） | **不能** —— 它记的是**构建过程**（declared/measured/verdict/mismatches），v3 只关心**发布产物** | ❌ 完全正交 |

**⇒ v3 的定位必须收窄为「一个 release 内字节对象的身份与取法」，它既不是内容契约的替代，也不是引擎契约的替代。**

---

## 1. 内容契约：23 个 entry 字段逐字段判定

取自宿主产地 `build/extra-content/content-list.schema.json` 的 `$defs.entry`
（`required = [name, version, sha256, url]`）。

### 1.1 ✅ 可被 v3 接管（5 个）—— 字节身份域

| 字段 | v3 里变成什么 | 说明 |
|---|---|---|
| `sha256` | `manifest.assets[].sha256`（原始字节） | 同一语义：fail-closed 唯一依据 |
| `url` | **`chunks[].file`（纯 asset 名）+ 分发方 base URL** | v3 把「一个 url」拆成「N 个纯文件名 + 一个 base」 |
| `size` | `manifest.assets[].bytes` | 同语义，但 v3 是**必填**（原契约是可选，仅进度条用） |
| `files`（`form:"tree"` 专属的下载闭包 map） | `manifest.variants[].chunks[]` 的 `{file,bytes,sha256}` | **语义直接对应**：都是「消费者会下载的文件 → 逐件 bytes+sha」 |
| `upstream_url` | `manifest.assets[].upstreamUrl`（可选，记账） | 同语义：出处，不参与运行期 |

**判据**：这 5 个字段删掉后，v3 会缺信息 ⇒ v3 必须接管它们。

### 1.2 ⚠️ 不该被 v3 接管（15 个）—— 语义域，留在内容契约

| 字段 | 为什么 v3 不该管 |
|---|---|
| `name` | 包的**身份/键**（`deps` 指它）。v3 的 asset 名是**文件名**，不是包名 |
| `version` | **版本语义**（`versions[]` 三不变量）。v3 的 tag 是发布批次，不是包的版本 |
| `form` | 投送形态（pkg/tree/file/oct/octdir/js）—— **内容构成轴**，与字节身份无关 |
| `content` / `kinds` | 包里有什么源（m/src/oct）—— 纯语义 |
| `arch` | 目标架构（dlopen 兼容性）—— 语义，不是字节事实 |
| `deps` | **依赖边**（包→包 / 包→能力层）—— v3 无从得知 |
| `requires` | 平台/版本约束串 —— 语义 |
| `license` | 许可台账 —— 语义（v3 可以带一份副本记账，但**权威在内容契约**） |
| `note` | 人话备注 —— 语义 |
| `description` | 包级描述（UI 卡片首屏）—— 语义 |
| `links` | 文档链接 —— 语义 |
| `consumer` | 消费面（octave/omc 车道轴）—— **引擎车道语义**，v3 无关 |
| `kind` | 条目性质（src/pre/engine）—— 语义 |
| `role` | 消费角色（package/toolchain/language-bridge）—— 语义 |
| `versions[]` | 版本候选集（三不变量）—— 语义 |

**判据（deletion test 反向）**：把这 15 个塞进 v3，会让 v3 的 manifest 变成**第二份内容契约**
⇒ 两处漂移（我们为 `sha256` 两处写漂移打过官司，见 `versions[]` 不变量②）。

### 1.3 ❓ 需要裁定的（3 个）

| 字段 | 问题 | 我的倾向 |
|---|---|---|
| `artifacts` | 预编译 `.oct` 的逐架构发布单位。**它本身就是「一个发布物」**，与 v3 的 release 概念重叠 | **倾向**：`artifacts` 每个条目**指向一个 release**（`releaseRef`），而不是被 v3 吸收。即内容契约记「有哪些 artifact」，v3 记「那个 release 里的字节身份」 |
| `optional_keys` | 协商机制（消费者声明能忽略哪些键） | **倾向**：留在内容契约。v3 的 `variants` 前向兼容靠「未知 codec 跳过」，是**另一套机制**，不需要 `optional_keys` |
| `producer` | 生产者身份（id + pin） | **倾向**：v3 已有 `id`（`<repo>/<tag>`）+ 可选 `producer.commit`，**部分重叠**。需要裁定是否统一 |

---

## 2. 引擎契约：9 个顶层键，**完全不能被 v3 收纳**

`octave.build.json`（宿主 `site/octave.build.json`）实测字段：

```
schema / tool / build / declared / measured / inputs / notes / verdict / mismatches / checked
```

| 键 | 记什么 | 与 v3 的关系 |
|---|---|---|
| `schema` | 该契约自己的版本 | 无关 |
| `tool` | 用什么工具构建（emsdk/clang 版本） | **构建过程事实**，v3 不管 |
| `build` | 构建参数（flags/配置） | 同上 |
| `declared` | **声称**的产物（人写） | 同上 |
| `measured` | **实测**的产物（工具量） | 同上 |
| `inputs` | 输入（源码 commit / 依赖） | 同上 |
| `notes` | 备注 | 同上 |
| **`verdict`** | **对账结论**（ok/mismatch） | 同上 |
| **`mismatches`** | 具体哪些项不符 | 同上 |
| `checked` | 检查时间戳/元数据 | 同上 |

**⇒ 引擎契约的全部内容都是「这个字节是怎么造出来的、造得对不对」，v3 的全部内容是「这个字节发布后是什么身份、怎么取」。两者零重叠。**

**唯一的接触点**：引擎契约的 `measured.files` 里逐件的 `sha256` **就是** v3 `manifest.assets[].sha256` 的**产地**。
所以正确关系是：

```
引擎契约（构建事实 + measured 逐件 sha）
        ↓ 产地（provider，不复制）
发布契约 v3（manifest：发布后的字节身份与分块取法）
        ↓ 消费
分发方（Shirone static 站）/ 消费端（UI/宿主）
```

**v3 不得自己算 sha 当权威**——这与「逐件 sha 唯一产地 = 生产者台账，分发方只核对不另算」
是同一条纪律（`files[]` 五条绑定第③条）。

---

## 3. 结论：v3 的正确位置

```
┌──────────────────────────────────────────────┐
│ 内容契约（content-list）                       │
│   版本语义 / form / content / consumer / deps  │
│   / license / description / versions[]        │
│   —— 回答「有什么、能不能用、给谁用」           │
└────────────────┬─────────────────────────────┘
                 │ 引用（acquisition.releaseRef，**尚未加**）
┌────────────────▼─────────────────────────────┐
│ 发布契约 v3（manifest）                        │
│   一个 release 内：字节身份 + 分块 + 回退链      │
│   —— 回答「这个字节从哪取、分几块、怎么校验」    │
└────────────────▲─────────────────────────────┘
                 │ 产地（提供 measured.files 的 sha，不复制）
┌────────────────┴─────────────────────────────┐
│ 引擎契约（octave.build.json）                  │
│   tool / build / declared / measured / verdict │
│   —— 回答「这个字节是怎么造的、造得对不对」      │
└──────────────────────────────────────────────┘
```

**三层各答一个问题，v3 在中间，只碰字节身份。**

---

## 4. 对已发信件的影响（必须更正的部分）

我在 `119`（给 OM）和 `120`（给 Shirone）里说「契约 v3」时，**没有说清它不替代内容契约**。
这不是致命错误（OM 的试点确实只需要 v3 那部分），但**措辞会让它们误以为 v3 是内容契约的升级版**。

**要补的更正**：
1. **给 OM**：试点 release 只产 v3 的 manifest；**不碰**你现有的 `content-list.json`
   ——两者并存，试点成功后由我出 `acquisition.releaseRef` 把它们连起来（落地顺序第 6 步）；
2. **给 Shirone**：static 站只服务 v3 的 manifest 与分片，**它不解析 content-list**
   ——内容语义在另一边，别混；
3. **给 UI/宿主**：将来消费时是「先读 content-list 选包 → 再看该包的 releaseRef → 读
   v3 manifest 取字节」，**两跳**，不是一跳。

---

## 5. 三个必须裁定的问题（我不擅自定）

| # | 问题 | 我的倾向 | 判据 |
|---|---|---|---|
| **U-A** | `artifacts`（预编译件）与 v3 release 的关系 | 内容契约记「有哪些 artifact 的 releaseRef」，v3 记字节 | 两者都是发布单位，但一个是**语义选择**、一个是**字节身份** |
| **U-B** | `producer` 是否统一（内容契约的 `{id,pin}` vs v3 的 `id` + `producer.commit`） | 统一到 v3 形状 `{repo, commit}`；内容契约的 `pin` 语义（submodule/release）保留在内容契约 | 避免两处各写一份 |
| **U-C** | **一个 release 能否承载多个 asset**？ | **能**（v3 目前只实现单资产；`assets` 应改成 map 而非单对象） | 现实：OM 的 `v0.1.0-wasm32` 已有 **2 个** asset（wasm + MSL zip）；v3 现在只能描述一个 |

**U-C 是个真缺口**：我的生成器只处理「单个主资产」，而 OM 的 release 里有多件。
**试点如果只做 wasm 一件，是可以的**（MSL zip 19.5MB 也可以分片，但不属于第一步）。
**但契约本身应该支持多资产**——这条必须在 OM 动手前定，否则它会造出一个只覆盖一件的 manifest。

---

## 6. 诚实边界

- 本审计基于**两个契约的 schema / 实件**（读 JSON，不是读文档），字段名与数量可复跑；
- 我**没有**验证「内容契约的消费端（UI 包管理器）能否接受两跳读取」——那是 UI 的事，
  且属于落地顺序第 5、6 步；
- 我**没有**验证「引擎契约的 `measured.files` 与 v3 `chunks` 的逐件 sha 是否天然一致」
  ——那需要拿一个真实的 `octave.build.json` 与 v3 manifest 对比，尚未做。

## 7. 复跑方式

```bash
# 内容契约的 entry 全字段（23 个）
python3 -c "
import json
s=json.load(open('/mnt/hdd/zcode-projects/Octave-Full-Wasm/build/extra-content/content-list.schema.json'))
e=s['\$defs']['entry']
print('required:', e.get('required'))
for k in e['properties']: print(' ', k)"

# 引擎契约的全键（9 个）
python3 -c "
import json
d=json.load(open('/mnt/hdd/zcode-projects/Octave-Full-Wasm/site/octave.build.json'))
print(list(d.keys()))"
```
