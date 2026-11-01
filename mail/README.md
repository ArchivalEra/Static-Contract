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
| 005 | static-contract | 待发：EdgeOne 通道停在旧快照（需要 shirone 重新部署 Worker）+ 验收闸门已落地 | 草稿 |

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
