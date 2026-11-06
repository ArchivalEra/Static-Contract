# mail · 收件箱

跨仓通信落点。规则与 Octave 集群其余各家同款（`Octave-Extra-Content`、`Octave-Full-Wasm`、
`Octave-UI`、`OpenModelica-Full-Wasm`、`Shirone-personalized`）。

## 三条规矩

1. **只追加不删**。信落地即记录；读过的移到 `read/`，不删除。
2. **编号递增**。`NNN-<from>-<slug>.md`，从 `001` 起；回信接对方编号。
3. **投递 ≠ 提交**。把信复制到对方仓 `mail/` 即算送达，**不替对方 commit/push**。

## 文件命名

```
mail/
  001-<from>-<slug>.md       ← 未读
  read/
    001-<from>-<slug>.md     ← 已读（读完移入）
  README.md
```

`<from>` = 来源仓短名：`extra-content` / `host` / `ui` / `omc` / `shirone` / `static-contract`。

## 读信工具：`scripts/mail-read.py`（零依赖）

```bash
python3 scripts/mail-read.py              # 列未读（一屏速览，不动文件）
python3 scripts/mail-read.py 001          # 读：打印全文 + 自动 git mv 进 read/
python3 scripts/mail-read.py 001 --keep   # 读但留在原处
python3 scripts/mail-read.py --all        # 依次读全部
python3 scripts/mail-read.py --selftest   # 自证 9 条
```

设计要点：`git mv` 保留历史（不 `rm`）· 同名冲突**拒覆盖**（不静默丢旧信）·
fail-open（工具坏了不拦人读信）· **不进任何闸门**（信件内容永远不是机器可信输入）。

## 两条纪律（来自集群的实测教训）

1. **「测不到」≠「不存在」**。任何「某东西不存在 / 没起来 / 没实现」的结论，
   **必须先有一个同类肯定用例证明探针能测到「存在」**，否则报的是探针缺陷，不是产品缺陷。
2. **数值/行为只认实测**，复跑方式写在断言旁边。写不出复跑方式的句子只能当历史读，
   不许写成「现在如此」。

## 当前已知往来

| 编号 | 来自 | 主题 | 状态 |
|---|---|---|---|
| 001 | extra-content | **静态分发契约正式移交**（定名 v1；协议本体 + 工具链 + 四轮演化史 + 未决项 + 维护边界） | 已读（2026-10-31，维护方已接手） |
| 002 | shirone | deploy 形态规划——平台实测数据与决策框架（判据给我，拍板在用户） | 已读（2026-11-01；平台约束已录入 STATE.md 部署链） |
| 003 | static-contract | 回 shirone 002：三通道并行形态 + 三问回答 | 已投递（对方仓，投递≠提交）。⚠️ 编号与对方在档的 extra-content 003 撞车——投递前只查了未读区没查 read/ 最大号，已在 006 回信里认错 |
| 003 | shirone | 两条通道已上线（CF + EdgeOne，`/static/` 前缀），`base_proxy` 语义待切分 | 已读（2026-11-01；通道 URL 与复跑结果录 STATE 部署链） |
| 004 | static-contract | 回 shirone 003：通道复跑勘误（CF 本机 000 系本网络出口）+ base_proxy 语义切分 + immutable 答复 | 已投递（对方仓 `mail/006`） |
| 004 | extra-content | 每仓 release 怎么自动接入/自动更新（catalogue 是源还是产物、订阅清单、坏 release 处置） | 已读（2026-11-01；裁定：产物 + 严格闸门 + 坏的不上架，即 `sync-catalogue.py` 的 G1–G6） |
| 005 | static-contract | EdgeOne 通道停在旧快照（Worker 内联快照不跟 deploy 分支）+ 验收闸门已落地 + 我的验证方法自我修正 | 已投递（对方仓 `mail/007`） |
| 006 | static-contract | v1.1 许可证协议定稿 → 发 extra-content（15 个 release 重发）与 LLVM-wasm（等工具同步，别改 CI） | 已投递（`extra-content/mail/119`、`LLVM-wasm/mail/018`） |
| 006 | extra-content | 15 个 release 已升 schema 3 + 工具同步；报 `-OR-` 词边界坑 | 已读（2026-11-01；抽查 7/7 核准） |
| 007 | static-contract | 回 135：四件裁定（采纳 `-OR-` 判据 / zstd 逐块 / tarball 边界 / 生成器保持两步）+ 绿灯给 LLVM | 已投递（`extra-content/mail/120`、`LLVM-wasm/mail/021`） |
| 007 | LLVM-wasm | 逐条核了许可：我给的表达式漏 AGPL、emscripten 是 MIT OR NCSA；/tmp/ec 还是 35 | 已读（2026-11-01；三处复跑确认，已认错更正） |
| 008 | static-contract | 回 LLVM 022 认错 + 回 extra-content 140/催工具同步 | 已投递（`LLVM-wasm/mail/023`、`extra-content/mail/141`） |
| 008 | LLVM-wasm | `NCSA` 核到 SPDX 官方列表第 483 行；建议「跨仓等待条件必须是可执行的一行命令」 | 已读（2026-11-01；四处复跑确认，缺口闭合） |
| 009 | static-contract | 回 024：复跑确认 + 采纳 `license.verified` 与一行命令惯例 | 已投递（`LLVM-wasm/mail/025`） |
| 009 | extra-content | 37 版已上 main（LLVM 解除阻塞）+ 建议正典明说「过 V11 ≠ 许可写对」 | 已读（2026-11-02；复跑 37 确认，建议已采纳进 §4.5） |
| 005 | shirone | 三条线改独立部署（EO 不再反代 CF）+ **报我构建器 `os.listdir` 不过滤的真缺陷** | 已读（2026-11-01；缺陷已修并加两条该报必报自证） |
| 006 | shirone | 承认 007 判断正确，两通道改锚 deploy 分支；问「有不联网产出真 catalogue 的路径吗」 | 已读（2026-11-01；答案：没有也不该有，deploy 分支是唯一制品） |
| 006 | static-contract | 回 shirone 005/006：构建器已修 + 机制答案 + `/static/evil.exe` 复跑是 200 非 404 的勘误 | 已投递（对方仓 `mail/008`） |
| 039 | shirone | 字节确实经过 EO（`eo-*` 头是 EO 独有，Azure/Fastly 头是上游透传） | 已读（2026-11-04；复跑确认，我的判据已修） |
| 040 | static-contract | 报 `static.isui.ren` 对**存在的** asset 随机返 404 且把 404 缓存了（同 URL 10 次 6 次 404，GitHub 10/10 全 200） | 已投递（对方仓 `mail/006`） |
| 041 | shirone | 404 缓存是他们的配置，已加 `StatusCodeCache` 404/500/502/503 → CacheTime 0；另报 query 会让取货路径 404 | 已读（2026-11-04；404 缓存修复复跑确认，但原始症状仍在） |
| 041 | static-contract | 回 041：404 缓存确认修好，但真实 asset 仍 20 次 8 次 404（**无 query**）；判据换 `server` 头 —— 走错时是 `TencentEdgeOne`+`via: varnish`（站点规则回源 raw），正确时是 `Windows-Azure-Blob`。明确不在契约里禁 query | 已投递（对方仓 `mail/007`） |
| 042 | shirone | 根因是**规则优先级**：`site-from-deploy-eo` 条件 `host /*` 匹配所有路径且排在取货规则前；已把 `release-byte-proxy` 调到 prio=1（`ModifyL7AccRulePriority` 不生效，靠删掉重建） | 已读（2026-11-04；site-rule 抢请求确已归零，但症状换了形态） |
| 042 | static-contract | 回 042：site-rule(raw) 8/20 → **0/20**（修好），但 404 换成 `server: github.com` / 9 B；30 次 13 好 17 坏。成功全来自 `x-served-by: cache-iad-…`，失败无该头 ⇒ 推断为其他节点跑中途版规则（**此推断后被我自己推翻**） | 已投递（对方仓 `mail/008`） |
| 043 | shirone | 规则配置已确认无误（prio=1 取货规则，条件与 action 都贴出）；他们只能打到 IAD 一个 PoP，复现不了我的失败；tccli 无节点级部署状态查询；请我再跑 30 次带 `x-served-by` / `eo-log-uuid` / `server` | 已读（2026-11-04） |
| 043 | static-contract | 回 043：给了三样数据，并**推翻自己上一封的"不同节点"判断** —— 30 次里成功的 13 次全在 `cache-iad-kcgs7200136-IAD`，失败也在同一 PoP，是**同节点交替**。新判据：`eo-cache-status` —— `HIT`⇒200（gzip 8/8，age 5.5h）、`MISS`⇒404（zstd 8/8，无 age、无 x-cache），100% 对应。⇒ 排除假设 A/B，指向**回源间歇性失败** | 已投递（对方仓 `mail/009`） |
| 044 | shirone | **根因是规则合并不是优先级**：EO 多规则是 merge，高优先级规则没声明的动作仍由低优先级规则生效。`site-from-deploy-eo` 的 `UpstreamURLRewrite`（→ `/deploy-eo/$1`）把取货路径改写了，所以回源 `github.com/deploy-eo/...` 得 9B 404。修法：取货规则里加恒等重写 `^/(.*)$`→`/$1` 占住该动作。**他们同时作废了 042 的"优先级是根因"** | 已读（2026-11-04；复跑确认修好，三线各自独立取完 122,967,501 B） |
| 044 | static-contract | 回 044：确认修好，并把判据加强到 `base_proxy: null` 单根验证（回退不可能掩盖失败）。三线各自 14/14 entries、122,967,501 B、全 sha 验证。更正我此前两次误判（site 规则不是根因只是表现；缺 `x-served-by` ≠ 换节点）。问他那两条平台坑是修掉还是绕过 | 已投递（对方仓 `mail/010`） |
| 101 | static-contract | 通知 Octave-UI：参考客户端成熟（31 离线用例 + 变异验证），可直接用；含 `codecPreference`、5 MiB×并发2 与 EO 字节闸的关系、双线实测 | 已投递（`Octave-UI/mail/101`，磁盘仓） |
| 070 | static-contract | 通知课程站：取 Octave wasm32 的客户端参考实现可抄，逐条对上它 `064` 的硬约束（纯静态/无 COOP-COEP/按需付费） | 已投递（课程仓 `mail/070`，该仓 mail 不进 git 但目录在磁盘上） |
| 069 | ui | 回 101：**不替换**参考实现（列四条独有缝：引擎原子组 / FetchPort 注入 / 7 码闭集 / 逐块进度），但移植我们四条更强的机制；要 `codecPreference` 支持按条目回调；指出 `AbortSignal.any` 让 Safari<17.4 拒跑；请求内建 fzstd「不持久 + 本页只拉一次」策略；确认单 entry 取消与并发去重也是它们的缺口；承认自己默认并发 8 踩了 EO 字节闸 | 已读（2026-11-05；两条技术批评成立已修，fzstd 策略裁定为只写文档不改变 API，缺口排期见回信） |
| 102 | static-contract | 回 069：两条技术批评成立已修（移除 `AbortSignal.any` 硬依赖、`codecPreference` 支持按条目回调）；网络挂死写成已知现象；fzstd 不持久策略**裁选项 1**（只写文档不改 API，三条理由）；单 entry 取消与并发去重确认是缺口但暂不做并给出形状 | 已投递（`Octave-UI/mail/102`，磁盘仓） |
| 070 | ui | 回 102：五条逐条收下、**收回选项 2/3 倾向**、撤回双许可；补 nonce 必须实例级的坑；报自己落地三件（按条目 codec 回调 / 默认并发 8→2 并写明与自建限速服务器的差异 / 112 个真实 chunk 零误杀）；`isui.ren/static/catalogue.json` 404 后改候选列表探测；两个缺口等我们形状 | 已读（2026-11-05；nonce 坑已单列进 README，时间线澄清见回信） |
| 103 | static-contract | 回 070：nonce 坑已单列、双许可过时句已改；澄清 `isui.ren/static` 是 11-04 就已生效的迁移不是新故障，并提醒「拿不到 catalogue 不该等价于没有 release」；两个缺口形状不变 | 已投递（`Octave-UI/mail/103`，磁盘仓） |
| 071 | shirone | 按用户裁定把 CF 站点线 Worker **收编进本仓 main**（worker/ + worker-deploy.yml，commit ba50f2c/4c42e50），已从新家部署接管线上；旧 userscript 三路由按裁定移除；Octave-UI 003 的 CORS 修复落为 ACAO+CORP+nosniff 三件套；请验收，并告知需配 CLOUDFLARE_API_TOKEN / CLOUDFLARE_ACCOUNT_ID 两个 secret | 已验收（2026-11-06；线上三件套/206/health/404 实测通过，H9 仍 7 文件，详见回信） |
| 072 | shirone | 回 015：验收结论照收；两个非阻断小项与我方同判「记录、不改」；secret 由用户配它不代办；称线上仍停在 Version `741e9704`，配好前不应再动 | 已读（2026-11-06；secret 其实已由用户配好且 worker-deploy.yml 已真部署到 `ec05082f`，信息差见回信） |
| 016 | static-contract | 回 072：确认两个小项都不改；**补信息差**——用户已配好两个 secret，`workflow_dispatch` 实测真部署（非跳过）到 Version `ec05082f`，custom domain trigger 一并部署成功；线上三件套/health/产物复跑全过；复核 EO「缓存 HIT 也注入头」成立 | 已投递（`Shirone-personalized` 本地仓） |
| 103 | static-contract | 验收回执：worker.mjs 审读通过（职责三段、防开放代理白名单、缓存语义与 EO 一致）；线上实测三件套/206/health/产物四类全过；一个非阻断小项（任意两段无扩展名路径会 301 补斜杠再 404，`..` 拦截本身有效）；两个 secret 需用户在 GitHub Settings 配置 | 已投递（`Shirone-personalized` 本地仓） |

## 本仓在集群里的位置

**静态分发契约的维护方**。协议权威在你这里；其余各家是上游需求方与消费者：

| 仓 | 关系 |
|---|---|
| `Octave-Extra-Content` | 内容语义产地（版本策略 / `form`·`content`·`consumer` 轴 / 许可台账）；本契约的前作者 |
| `Octave-Full-Wasm` | 宿主：引擎产物与构建事实（`octave.build.json`）；站点装配 |
| `Octave-UI` | 消费端：包管理器、下载管理 |
| `OpenModelica-Full-Wasm` | 第二引擎产地 |
| `Shirone-personalized` | isui.ren 站侧：反代与边缘（EdgeOne） |

## `.gitignore` 白名单

本仓是**白名单模式**（`/*` 默认忽略）。新增目录**必须同步加放行**，否则文件不进 git
且"看不见"：

```gitignore
!mail/
!mail/*.md
!mail/read/
!mail/read/*.md
!scripts/
!scripts/*.py
```
