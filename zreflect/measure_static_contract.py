#!/usr/bin/env python3
"""Static-Contract —— **本仓的数据层**（Einfacht 机制层之上的"你的部分"）。

形状照 `Octave-Extra-Content/zreflect/measure_extra_content.py` 的先例：
Einfacht 的 `zreflect/facts.py` 只提供**机制**（守卫 / 渲染 / 收尾），
这里放本仓真正要量的东西：**契约正典规模**、**三套自证的通过数**、
**catalogue 收录数**、**邮件未读数**。全部照旧：每条带复跑命令 + 出处。

⚠️ 本模块**自包含**：不 import 宿主仓的任何东西（那是另一棵仓）。
⚠️ 采集器纪律（`zreflect/collect.py` 五条原则）逐条遵守：
   · 只读**持久盘**产物，不跑服务、不碰网络（pre-commit 里不该依赖"某个东西正在跑"）；
     —— deploy 分支状态是在线事实，**故意不进台账**（要引用就在正文写命令）；
   · 不引入会自己在变的输入：HEAD sha / 墙上时钟不进台账（原则 2）；
   · 读不到就明说：条目不在 ⇒ 那条事实**不写**，不许用 0 冒充"已量"
     （catalogue_releases 例外：catalogue 文件本身在库，`0 条收录`是
     合法实测值而非「读不到」—— 读不到的形状是文件不存在，那才不写）；
   · 本仓事实都是廉价磁盘读 + 亚秒级自证，无缓存需要。
"""
import glob
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ledger import fact                                    # noqa: E402
from gate import module_meta                               # noqa: E402

# ★ C5：本仓数据层也必须在平台名册里声明自己，否则 registry 报 undeclared。
#   selftest=False：它是**数据**（量什么、怎么量），机制的自证在 zreflect/ 那批。
MODULE = module_meta("本仓数据层", "量正典规模 / 三套自证 / catalogue / 邮件（数据 vs 机制分离）",
                     selftest=False)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _one(cmd):
    """跑一条裸值命令，返回 stdout.strip()（读不到 ⇒ None，调用方决定写不写）。"""
    try:
        p = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                           cwd=REPO, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    if p.returncode != 0:
        return None
    return p.stdout.strip()


def measure():
    """量一遍全部事实（本仓的策略/数据）。守卫与写盘由 zreflect/facts.py 的平台负责。"""
    facts = {}

    # ── 契约正典规模（**目录侧**事实，从磁盘量，不猜）────────────────────────────
    n_specs = len(glob.glob(os.path.join(REPO, "specs", "*.md")))
    if n_specs:
        facts["specs_md"] = fact(n_specs, "ls specs/*.md | wc -l", "specs/",
                                 "契约正典 + 演化史文档数（正典 = v4）")

    # ── 三套自证的通过数（本仓判据强度）────────────────────────────────────────
    #   PASS 行计数与各工具自证的「=== N PASS / 0 FAIL ===」同源；哪套红了，
    #   pre-commit 的 check_site_build / CI 会先红，这里只是把数值入账供引用。
    for key, tool, what in (
            ("tool_manifest_selftest_pass", "tools/make-manifest-v4.py",
             "manifest 生成器自证通过数（白名单反向 + v4 结构 + 边界）"),
            ("tool_check_release_selftest_pass", "tools/check-release-v4.py",
             "release 校验器自证通过数（V1–V10 逐条反向）"),
            ("site_build_selftest_pass", "scripts/build-site.py",
             "站点构建器自证通过数（catalogue 校验 + 0 字节闸门双向 + 确定性）")):
        n = _one("python3 %s --selftest 2>/dev/null | grep -c '^PASS'" % tool)
        if n is not None and n.strip().isdigit():
            facts[key] = fact(int(n),
                              "python3 %s --selftest 2>/dev/null | grep -c '^PASS'" % tool,
                              tool, what)

    # ── catalogue 收录数（站点数据源；0 条是合法实测值 —— 试点链第 1 环未跑）──────
    if os.path.isfile(os.path.join(REPO, "site", "catalogue.json")):
        n_rel = _one("python3 -c \"import json;print(len(json.load(open("
                     "'site/catalogue.json'))['releases']))\"")
        if n_rel is not None and n_rel.strip().isdigit():
            facts["catalogue_releases"] = fact(
                int(n_rel),
                "python3 -c \"import json;print(len(json.load(open("
                "'site/catalogue.json'))['releases']))\"",
                "site/catalogue.json", "catalogue 收录的 release 条目数（0 字节托管，只记 id + base）")

    # ── 邮件未读数（收件箱状态；read/ 里的 = 已读，不列）────────────────────────
    n_unread = _one("find mail -maxdepth 1 -name '[0-9]*.md' | wc -l")
    if n_unread is not None and n_unread.strip().isdigit():
        facts["mail_unread"] = fact(int(n_unread),
                                    "find mail -maxdepth 1 -name '[0-9]*.md' | wc -l",
                                    "mail/", "未读信件数（读过的在 mail/read/）")

    return facts


if __name__ == "__main__":
    print(json.dumps(measure(), ensure_ascii=False, indent=1))
