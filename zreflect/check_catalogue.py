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

GATE = meta("catalogue 派生闸门",
            "派生器自证全绿 + 兜底源文件不得含手写条目（条目只由派生产出）",
            runs_at="commit")

REPO = repo("")
SRC = os.path.join(REPO, "site", "catalogue.json")


def main():
    probs = []

    # ① 派生器自证必须全绿（纯逻辑，不联网 —— 探针本身坏掉要先知道）
    p = subprocess.run([sys.executable, "scripts/sync-catalogue.py", "--selftest"],
                       cwd=REPO, capture_output=True, text=True)
    if p.returncode != 0:
        tail = (p.stdout or "").strip().splitlines()[-1:] or ["(无输出)"]
        probs.append("派生器自证红（%s）" % tail[0])

    # ② 兜底源文件必须是合法 shape 且 **releases 为空**
    if not os.path.exists(SRC):
        probs.append("缺 site/catalogue.json 兜底源")
    else:
        try:
            doc = json.load(open(SRC, encoding="utf-8"))
        except ValueError as e:
            probs.append("site/catalogue.json 非法 JSON: %s" % e)
            doc = None
        if isinstance(doc, dict):
            if doc.get("schema") != 1:
                probs.append("兜底源 schema 必须是 1，got %r" % doc.get("schema"))
            rels = doc.get("releases")
            if not isinstance(rels, list):
                probs.append("兜底源 releases 必须是数组")
            elif rels:
                probs.append(
                    "兜底源里有 %d 条手写 release —— 条目只由 sync-catalogue 从 "
                    "release 派生（手改 = 第二个产地）；删掉它们" % len(rels))

    # ③ 订阅清单存在且非空（零源不是「没有坏条目」，是「什么都没查」）
    sj = os.path.join(REPO, "site", "sources.json")
    if not os.path.exists(sj):
        probs.append("缺 site/sources.json（订阅清单）")
    else:
        try:
            sdoc = json.load(open(sj, encoding="utf-8"))
            srcs = sdoc.get("sources")
            if not isinstance(srcs, list) or not srcs:
                probs.append("sources.json 的 sources 必须是非空数组")
            else:
                for s in srcs:
                    if not isinstance(s, dict) or not isinstance(s.get("repo"), str) \
                            or "/" not in s.get("repo", ""):
                        probs.append("sources.json 条目形状坏: %r" % (s,))
        except ValueError as e:
            probs.append("sources.json 非法 JSON: %s" % e)

    for x in probs:
        print("· %s" % x, file=sys.stderr)
    if probs:
        print("catalogue 派生闸门：%d 个问题" % len(probs), file=sys.stderr)
        return 1
    print("catalogue 派生闸门：OK（派生器自证绿 / 兜底源空 / 订阅清单非空）")
    return 0


MODULE = module_meta("catalogue 派生闸门", "派生器自证 + 兜底源必须空 + 订阅清单非空",
                     selftest=False)


if __name__ == "__main__":
    sys.exit(main())
