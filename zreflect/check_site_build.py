#!/usr/bin/env python3
"""站点构建自证闸门：把 `scripts/build-site.py --selftest` 挂进 commit 相位。

为什么是壳：自证主体（catalogue 校验双向 + 0 字节闸门双向 + 真构建 + 确定性，
10 条三档用例）住在 `scripts/build-site.py`，**改它不改这里** —— 本模块只负责
把它声明进发现式名录（`GATE = gate.meta(…, runs_at="commit")`），让
`registry --run commit`（pre-commit / CI）每次真跑。壳没有自己的判据，
因此 `selftest=False` 正面声明（不装自证）。

用法：
  python3 zreflect/check_site_build.py            # 违规即非零（pre-commit / CI 用）
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gate import meta, module_meta, repo                  # noqa: E402
from i18n import M                                        # noqa: E402

GATE = meta("站点构建自证",
            "build-site.py 自证 10 条（catalogue 校验 + 0 字节闸门 + 确定性）",
            runs_at="commit")

# `repo()` 在调用点即时求值（新版 snapshot 闸门：模块顶层冻结含可变
# 全局的表达式是派生快照 —— 而它本就是纯函数，开销可忽略）。
CMD = [sys.executable, os.path.join("scripts", "build-site.py"), "--selftest"]


def main():
    p = subprocess.run(CMD, cwd=repo(""), capture_output=True, text=True, encoding="utf-8")
    sys.stdout.write(p.stdout)
    sys.stderr.write(p.stderr)
    if p.returncode != 0:
        print("FATAL: " + M("sitebuild.selftest_red", rc=p.returncode), file=sys.stderr)
        return 1
    return 0


MODULE = module_meta("站点构建自证闸门", "壳：把 scripts/build-site.py --selftest 挂进 commit 相位",
                     selftest=False)


if __name__ == "__main__":
    from gate import activate_or_fatal
    _rc = activate_or_fatal()
    sys.exit(_rc or main())
