#!/usr/bin/env python3
"""站点闸门：HTML 产物必须全英文，且废弃契约必须被标出来。

用户裁定（2026-11-02）：
  ① 「html页面不准出现中文」
  ② 「之前那些 contract 都标成 deprecated」

这两条都不是建议，是判据。为什么值得一道闸门：

  · **中文散布在 HTML 里**会让非中文读者放弃，也让 `Content-Language` 语义变浑；
    站点的读者是跨仓的开发者，代码与契约文档可以是中文，**但门面必须是英文**。
  · **废弃契约若不带标记**，读者会照 v0/v1/v2 的旧形态实现 ——
    本仓已有三次「推断输给逐条核」的教训（正典 §4.5），文档层不能再来一次。

## 判据

  H1 构建产物的 `index.html` **不含任何 CJK 字符**（U+4E00–U+9FFF 等）
  H2 页面里每个 `contract/*.md` 链接，若该文档带 DEPRECATED / SUPERSEDED 横幅，
     则页面上该项**必须**同时出现同样的标记（不能静默列出）
  H3 `specs/` 下除权威文档外，全部必须带废弃横幅（防新加文档时忘标）

权威文档 = `2026-11-01-release-contract-v1.1-license.md`（v1.1）
         + `2026-10-30-release-contract-v4.md`（V1–V10，部分取代）

用法：
  python3 zreflect/check_site_lang.py            # 违规即非零
"""
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gate import meta, module_meta, repo                   # noqa: E402

GATE = meta("站点语言闸门",
            "HTML 产物必须全英文；废弃契约必须在页面与文档里被标出",
            runs_at="commit")

REPO = repo("")
SPECS = os.path.join(REPO, "specs")
# 真实派生 catalogue（CI 会写到这里；本地有则用之）
CAT_ABS = os.path.join(REPO, "site", "catalogue.live.json")
if not os.path.exists(CAT_ABS):
    CAT_ABS = os.environ.get("SC_CATALOGUE", "")

# CJK 区间：中日韩统一表意文字 + 扩展 A + 兼容表意 + 全角标点/符号
CJK = re.compile(r"[\u3000-\u303f\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff"
                 r"\uf900-\ufaff\uff00-\uffef]")

# 权威（不要求废弃横幅）
AUTHORITY = {
    "2026-11-01-release-contract-v1.1-license.md",
    "2026-10-30-release-contract-v4.md",
}
DEPRECATED_MARK = re.compile(r"(DEPRECATED|SUPERSEDED IN PART)")


def _build_to(tmp, cat=None):
    """构建一次站点。**优先用真实派生 catalogue**（否则 excluded 是空的，
    H2/H4 会漏检 —— 线上就因此出现过 40 个 CJK 字符）。"""
    env = dict(os.environ)
    if cat and os.path.exists(cat):
        env["CATALOGUE_DERIVED"] = cat
    else:
        env.pop("CATALOGUE_DERIVED", None)
    r = subprocess.run([sys.executable, os.path.join(REPO, "scripts", "build-site.py"),
                        "--out", tmp], capture_output=True, text=True, env=env, cwd=REPO)
    return r.returncode, r.stdout + r.stderr


def check_html_lang(html):
    """H1：返回违规的 CJK 片段（空 = 通过）。"""
    hits = CJK.findall(html)
    if not hits:
        return []
    # 给出上下文，便于定位
    out = []
    for m in CJK.finditer(html):
        a = max(0, m.start() - 20)
        b = min(len(html), m.end() + 20)
        out.append(html[a:b].replace("\n", " "))
        if len(out) >= 5:
            break
    return out


def check_specs_marked(specs_dir):
    """H3：非权威文档必须有废弃横幅。"""
    probs = []
    for name in sorted(os.listdir(specs_dir)):
        if not name.endswith(".md"):
            continue
        if name in AUTHORITY:
            continue
        head = open(os.path.join(specs_dir, name), encoding="utf-8").read(800)
        if not DEPRECATED_MARK.search(head):
            probs.append("%s 未标 DEPRECATED（非权威文档必须有横幅）" % name)
    return probs


def check_page_marks_deprecated(html, specs_dir):
    """H2：**完全废弃**的文档，页面上每个链接都必须带标记。

    「部分取代」（v4：V1–V10 仍有效）**不在此列** —— 强求给它标 DEPRECATED
    反而是错的：它确实是现行契约的一半。只在文档列表处标 [PARTLY SUPERSEDED] 即可，
    正文引用它时不必标。
    """
    probs = []
    for m in re.finditer(r'<a href="contract/([^"]+)">([^<]*)</a>', html):
        name = m.group(1)
        path = os.path.join(specs_dir, name)
        if not os.path.exists(path):
            probs.append("页面链接的 contract/%s 不存在" % name)
            continue
        head = open(path, encoding="utf-8").read(800)
        if "DEPRECATED" not in head:
            continue                      # 部分取代 / 权威：不要求在正文引用处标记
        # 完全废弃：**必须**在同一条目行里带标记
        line_end = html.find("</li>", m.start())
        line = html[m.start():line_end if line_end > 0 else len(html)]
        if "DEPRECATED" not in line:
            probs.append("contract/%s 已完全废弃，但页面上没标出来" % name)
    return probs


def check_catalogue_en(cat_path):
    """H4：catalogue 对外字段不得含中文（它是**公开发布的产物**，不是内部日志）。

    为什么单列：页面渲染的排除原因来自 catalogue；闸门若只查 index.html，
    而本地构建用的是空兜底源（无 excluded），**这条永远查不到** ——
    实际线上就因为 `reasons` 里带中文，页面出现了 40 个 CJK 字符。
    """
    import json
    probs = []
    if not os.path.exists(cat_path):
        return ["H4 catalogue 不存在：%s" % cat_path]
    try:
        d = json.load(open(cat_path, encoding="utf-8"))
    except ValueError as e:
        return ["H4 catalogue 非法 JSON: %s" % e]
    for x in d.get("excluded") or []:
        if not isinstance(x, dict):
            continue
        # reasons_en 是给读者的；reasons 是内部诊断
        if not x.get("reasons_en"):
            probs.append("H4 excluded %s/%s 缺 reasons_en（页面会退化成中文原因）"
                         % (x.get("repo"), x.get("tag")))
        for r in x.get("reasons_en") or []:
            if CJK.search(r):
                probs.append("H4 excluded %s/%s 的 reasons_en 含中文"
                             % (x.get("repo"), x.get("tag")))
    return probs


def main():
    import tempfile
    import shutil

    probs = []
    tmp = tempfile.mkdtemp(prefix="sc-site-")
    try:
        rc, log = _build_to(os.path.join(tmp, "dist"), cat=CAT_ABS)
        if rc != 0:
            probs.append("构建失败（rc=%d）：%s" % (rc, log.strip().splitlines()[-1:]))
            html = ""
        else:
            html = open(os.path.join(tmp, "dist", "index.html"), encoding="utf-8").read()
            hits = check_html_lang(html)
            if hits:
                probs.append("H1 index.html 含 %d 个 CJK 字符，例：%r"
                             % (len(CJK.findall(html)), hits[:2]))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    probs += check_specs_marked(SPECS)
    if CAT_ABS:
        probs += check_catalogue_en(CAT_ABS)
    if html:
        probs += check_page_marks_deprecated(html, SPECS)

    for x in probs:
        print("· %s" % x, file=sys.stderr)
    if probs:
        print("站点语言闸门：%d 个问题" % len(probs), file=sys.stderr)
        return 1
    print("站点语言闸门：OK（HTML 全英文 / 废弃契约已标 / 页面同步标记）")
    return 0


MODULE = module_meta("站点语言闸门",
                     "HTML 全英文 + 废弃契约必有横幅 + 页面同步",
                     selftest=False)


if __name__ == "__main__":
    sys.exit(main())
