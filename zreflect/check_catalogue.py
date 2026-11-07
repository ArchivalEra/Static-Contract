#!/usr/bin/env python3
"""catalogue 派生闸门：确认派生器自证全绿 + 源文件没被手改歪。

为什么要有这道闸（而不是只靠 sync-catalogue 在工作流里跑）：
  · 派生只在 CI 跑 ⇒ 本地提交前**没人**验证派生器还能不能过，
    坏了要等部署红才发现（那时三通道已停在旧版本）。
  · `site/catalogue.json` 是**兜底源文件**，但它极易被误当数据源手改
    （「第二个产地」正是本仓反复要消灭的坏法）。本闸门对它做形状校验，
    并要求它**自证为空**（真正的条目由派生器产出，不落 git）。

用法：
  python3 zreflect/check_catalogue.py           # 违规即非零
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gate import meta, module_meta, repo                   # noqa: E402
from i18n import M                                         # noqa: E402

GATE = meta("catalogue 派生闸门",
            "派生器自证全绿 + 兜底源文件不得含手写条目（条目只由派生产出）",
            runs_at="commit")

# `snapshot.derived_copy`（新版平台）：`repo("")` 的返回值在别处可能被重赋值，
# 在模块顶层把「含可变全局的表达式」存成常量会冻住 import 那一刻的值。
# 改为调用点即时求值 —— `repo()` 本身是纯函数，开销可忽略。
def SRC():                       # 调用点即时求值（新版 snapshot 闸门同款理由）
    return os.path.join(repo(""), "site", "catalogue.json")


def main():
    probs = []

    # ① 派生器自证必须全绿（纯逻辑，不联网 —— 探针本身坏掉要先知道）
    p = subprocess.run([sys.executable, "scripts/sync-catalogue.py", "--selftest"], encoding="utf-8",
                       cwd=repo(""), capture_output=True, text=True)
    if p.returncode != 0:
        tail = (p.stdout or "").strip().splitlines()[-1:] or \
               [M("catalogue.selftest_no_output")]
        probs.append(M("catalogue.selftest_red", tail=tail[0]))

    # ② 兜底源文件必须是合法 shape 且 **releases 为空**
    if not os.path.exists(SRC()):
        probs.append(M("catalogue.missing_fallback"))
    else:
        try:
            doc = json.load(open(SRC(), encoding="utf-8"))
        except ValueError as e:
            probs.append(M("catalogue.fallback_bad_json", error=e))
            doc = None
        if isinstance(doc, dict):
            if doc.get("schema") != 1:
                probs.append(M("catalogue.fallback_schema", actual=doc.get("schema")))
            rels = doc.get("releases")
            if not isinstance(rels, list):
                probs.append(M("catalogue.fallback_releases_not_list"))
            elif rels:
                probs.append(M("catalogue.fallback_handwritten", count=len(rels)))

    # ③ 订阅清单存在且非空（零源不是「没有坏条目」，是「什么都没查」）
    sj = os.path.join(repo(""), "site", "sources.json")
    if not os.path.exists(sj):
        probs.append(M("catalogue.missing_sources"))
    else:
        try:
            sdoc = json.load(open(sj, encoding="utf-8"))
            srcs = sdoc.get("sources")
            if not isinstance(srcs, list) or not srcs:
                probs.append(M("catalogue.sources_not_list"))
            else:
                for s in srcs:
                    if not isinstance(s, dict) or not isinstance(s.get("repo"), str) \
                            or "/" not in s.get("repo", ""):
                        probs.append(M("catalogue.sources_bad_shape", item=repr(s)))
        except ValueError as e:
            probs.append(M("catalogue.sources_bad_json", error=e))

    for x in probs:
        print("· %s" % x, file=sys.stderr)
    if probs:
        print(M("catalogue.problems", count=len(probs)), file=sys.stderr)
        return 1
    print(M("catalogue.ok"))
    return 0


MODULE = module_meta(
    "catalogue 派生闸门",
    "派生器自证 + 兜底源必须空 + 订阅清单非空（selftest=False：逻辑自证"
    "住在 registry._cases）",
    selftest=False)


if __name__ == "__main__":
    from gate import activate_or_fatal
    _rc = activate_or_fatal()
    sys.exit(_rc or main())
