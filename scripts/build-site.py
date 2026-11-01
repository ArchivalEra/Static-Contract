#!/usr/bin/env python3
# build-site.py —— 静态契约站构建（零依赖，确定性输出）
#
# 站点纪律（用户裁定 2026-11-01，最最核心）：**本站不收录任何 release 件（0 字节托管）**。
# 站点只产出：index.html + catalogue.json + 契约文档（specs/*.md）+ 工具（tools/*.py）+ README。
# 包字节一律从 catalogue 条目的 base（GitHub release 直链）或 base_proxy（集群反代）获取。
#
# 构建闸门（fail-closed）：产物中出现 release 件形状 ⇒ 构建失败、清场不留半个目录。
#   · 文件名匹配契约 asset 形状 `<载荷>.<codec>.<NNN>`（codec 取开放词表超集）
#   · 路径含 releases/ 段
#
# 用法：
#   python3 scripts/build-site.py --out site/dist   # 构建到指定目录（先建临时目录，成功才替换）
#   python3 scripts/build-site.py --selftest        # 自证（不碰 site/dist）
import hashlib
import html
import json
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPECS = os.path.join(HERE, "specs")
TOOLS = os.path.join(HERE, "tools")
CATALOGUE_SRC = os.path.join(HERE, "site", "catalogue.json")
SOURCES_SRC = os.path.join(HERE, "site", "sources.json")
README = os.path.join(HERE, "README.md")

# 开放词表超集：正典 V9 codecs 是开放词表，闸门按超集匹配宁可误拒不漏放
ASSET_SHAPE = re.compile(r"\.(zstd|gzip|identity|br|xz|deflate|compress)\.\d{1,4}$")
HTTPS = "https://"


# ── catalogue 校验 ────────────────────────────────────────────────────────────
def validate_release(e, seen_ids):
    """单条 release 校验，违规抛 ValueError（fail-closed）。"""
    if not isinstance(e, dict):
        raise ValueError("release 条目必须是对象: %r" % (e,))
    rid = e.get("id")
    if not isinstance(rid, str) or not rid.strip() or any(c.isspace() for c in rid):
        raise ValueError("id 必须是非空且无空白的字符串，got %r" % (rid,))
    if rid in seen_ids:
        raise ValueError("id 重复: %r" % rid)
    seen_ids.add(rid)
    for key in ("base", "base_proxy"):
        v = e.get(key)
        if v is None and key == "base_proxy":
            continue
        if not isinstance(v, str) or not v.startswith(HTTPS) or not v.endswith("/"):
            raise ValueError("%s 必须 https:// 开头且以 / 结尾（客户端直接拼 file），got %r" % (key, v))


def load_catalogue(path):
    with open(path, encoding="utf-8") as f:
        cat = json.load(f)
    if not isinstance(cat, dict) or cat.get("schema") != 1:
        raise ValueError("catalogue schema 必须是 1")
    releases = cat.get("releases")
    if not isinstance(releases, list):
        raise ValueError("releases 必须是数组")
    seen = set()
    for i, e in enumerate(releases):
        try:
            validate_release(e, seen)
        except ValueError as ex:
            raise ValueError("releases[%d]: %s" % (i, ex)) from None
    return cat


# ── 闸门 ─────────────────────────────────────────────────────────────────────
def gate_dist(dist):
    """产物禁含 release 件；违例收集后一次性报全（fail-closed）。"""
    bad = []
    for root, _dirs, files in os.walk(dist):
        for name in files:
            rel = os.path.relpath(os.path.join(root, name), dist)
            parts = rel.split(os.sep)
            if ASSET_SHAPE.search(name) or "releases" in parts:
                bad.append(rel)
    if bad:
        raise SystemExit("构建闸门：产物含 release 件形状（0 字节托管裁定）⇒ 拒绝发布：\n  "
                         + "\n  ".join(sorted(bad)))


# ── 构建 ─────────────────────────────────────────────────────────────────────
def build(out):
    # catalogue 是**派生产物**（scripts/sync-catalogue.py 从各仓 release 严格派生）。
    # 源文件 site/catalogue.json 只作兜底：派生件不在时用它，并**明说**是兜底，
    # 不许静默把「没派生」伪装成「派生结果为空」。
    derived = os.environ.get("CATALOGUE_DERIVED", "").strip()
    src = derived if derived and os.path.exists(derived) else CATALOGUE_SRC
    cat = load_catalogue(src)
    if os.path.abspath(src) == os.path.abspath(CATALOGUE_SRC):
        print("⚠ catalogue 用的是源文件兜底（未派生）—— 发布前应先跑 "
              "scripts/sync-catalogue.py", file=sys.stderr)
    # 构建指纹：线上验收闸门（verify-channels.py）靠它在各通道的 index.html 里
    # 认出「这是本次产物」。没有它，验收只能比通道之间是否一致 —— 而在所有通道
    # 都停在旧产物时，一致性同样成立（2026-11-01 真实事故）。
    fp_input = (cat.get("verified_at") or "no-verified-at") + "|" + str(len(cat.get("releases") or []))
    fingerprint = "STATIC-CONTRACT-BUILD " + hashlib.sha256(fp_input.encode()).hexdigest()[:16]
    tmp = tempfile.mkdtemp(prefix="build-site-")
    try:
        d = os.path.join(tmp, "dist")
        os.makedirs(os.path.join(d, "contract"))
        os.makedirs(os.path.join(d, "tools"))
        for src_dir, dst in ((SPECS, os.path.join(d, "contract")),
                             (TOOLS, os.path.join(d, "tools"))):
            for name in sorted(os.listdir(src_dir)):
                if name.endswith((".md", ".py")):
                    shutil.copy2(os.path.join(src_dir, name), os.path.join(dst, name))
        shutil.copy2(src, os.path.join(d, "catalogue.json"))
        # 订阅清单随站一起发布：**可审计**（谁决定收哪些仓）
        shutil.copy2(SOURCES_SRC, os.path.join(d, "sources.json"))
        for fname in ("README.md", "STATE.md", "maintaince.md"):
            shutil.copy2(os.path.join(HERE, fname), os.path.join(d, fname))
        with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as f:
            f.write(render_index(cat, fingerprint))
        gate_dist(d)
        if os.path.exists(out):
            shutil.rmtree(out)
        shutil.move(d, out)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return out


def render_index(cat, fingerprint=""):
    releases = cat["releases"]
    rows = "\n".join(
        '    <tr><td><code>{id}</code></td><td><a href="{base}manifest.json">GitHub 直链</a></td>'
        "<td>{proxy}</td></tr>".format(
            id=html.escape(e["id"]),
            base=html.escape(e["base"]),
            proxy=('<a href="%smanifest.json">反代</a>' % html.escape(e["base_proxy"])
                   if e.get("base_proxy") else "—"))
        for e in releases) or "    <tr><td colspan=3>（暂无收录 —— 试点链第 1 环待跑）</td></tr>"
    specs = sorted(os.listdir(SPECS))
    tools = sorted(os.listdir(TOOLS))
    spec_links = "\n".join(
        "    <li><a href=\"contract/%s\">%s</a></li>" % (n, html.escape(n)) for n in specs)
    tool_links = "\n".join(
        "    <li><a href=\"tools/%s\"><code>%s</code></a></li>" % (n, n) for n in tools)
    return """<!doctype html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Static-Contract · 静态分发契约</title>
<style>
body{font:16px/1.7 system-ui,sans-serif;max-width:52em;margin:2rem auto;padding:0 1rem;color:#1a1a1a}
h1{font-size:1.5rem} code{background:#f4f4f4;padding:.1em .35em;border-radius:4px;font-size:.9em}
.rule{border-left:4px solid #b45309;padding:.5rem 1rem;background:#fffbeb;margin:1rem 0}
table{border-collapse:collapse}td,th{border:1px solid #ddd;padding:.4em .8em;text-align:left}
a{color:#1d4ed8}
</style>
</head>
<body>
<h1>Static-Contract · 静态分发契约</h1>
<div class="rule">
<strong>本站不收录任何 release 件（0 字节托管）。</strong><br>
所有的包，要么去 GitHub 拿（release 直链），要么走反代。本站只收录元数据与契约文档。<br>
客户端按契约 §4：从 <code>catalogue.json</code> 拿 <code>base</code>，<code>GET base + manifest.json</code>，
其余文件名<strong>逐字</strong>取自 manifest，一切字节走普通 GET。
</div>
<h2>catalogue（<a href="catalogue.json">catalogue.json</a>）</h2>
<table>
  <tr><th>id</th><th>字节来源</th><th>反代</th></tr>
@@ROWS@@
</table>
<h2>契约文档（正典：2026-10-30-release-contract-v4.md）</h2>
<ul>
@@SPECS@@
</ul>
<h2>工具链</h2>
<ul>
@@TOOLS@@
</ul>
<p>完整地图见 <a href="README.md">README.md</a>。apt 的稳健 + HTTP 的简洁。</p>
<p style="color:#888;font-size:.8em">@@FP@@</p>
</body>
</html>
""".replace("@@ROWS@@", rows).replace("@@SPECS@@", spec_links).replace("@@TOOLS@@", tool_links).replace("@@FP@@", html.escape(fingerprint))


# ── 自证 ─────────────────────────────────────────────────────────────────────
def selftest():
    cases = []
    seen = set()

    def ok(label, fn):
        try:
            cases.append((label, bool(fn()), None))
        except SystemExit as e:
            cases.append((label, False, str(e)))
        except Exception as e:                                    # noqa: BLE001
            cases.append((label, False, repr(e)))

    def must_raise(label, fn, exc=ValueError):
        try:
            fn()
            cases.append((label, False, "未抛异常"))
        except exc:
            cases.append((label, True, None))
        except Exception as e:                                    # noqa: BLE001
            cases.append((label, False, "抛错类型不符 %r" % (e,)))

    # 1. catalogue 校验：正例
    ok("校验：合法条目通过", lambda: (validate_release(
        {"id": "a/b@1.0", "base": HTTPS + "x/y/releases/download/t/"}, seen), True)[1])
    # 2. 反例：base 非 https
    must_raise("校验：http base 拒", lambda: validate_release(
        {"id": "a/c@1.0", "base": "http://x/"}, set()))
    # 3. 反例：base 不以 / 结尾（拼 file 会坏）
    must_raise("校验：base 无尾斜杠拒", lambda: validate_release(
        {"id": "a/d@1.0", "base": HTTPS + "x/y"}, set()))
    # 4. 反例：id 重复
    must_raise("校验：id 重复拒", lambda: validate_release(
        {"id": "a/b@1.0", "base": HTTPS + "x/"}, seen))
    # 5. 反例：id 带空白
    must_raise("校验：id 带空白拒", lambda: validate_release(
        {"id": "a b", "base": HTTPS + "x/"}, set()))
    # 6. 闸门：asset 形状文件名
    must_raise("闸门：asset 形状文件名拒", lambda: _gate_flag("x.oct.zstd.000"), SystemExit)
    # 7. 闸门：releases/ 路径
    must_raise("闸门：releases/ 路径拒", lambda: _gate_flag("sub/x.md", subdir="releases"), SystemExit)
    # 8. 闸门：普通文档放行
    ok("闸门：普通文档放行", lambda: (_gate_flag("contract/v4.md"), True)[1])
    # 9. 真构建：产物齐全且无 release 件
    def real_build():
        d = tempfile.mkdtemp()
        try:
            build(os.path.join(d, "dist"))
            names = set()
            for root, _dirs, files in os.walk(os.path.join(d, "dist")):
                for n in files:
                    names.add(os.path.relpath(os.path.join(root, n), os.path.join(d, "dist")))
            need = {"index.html", "catalogue.json", "README.md",
                    "STATE.md", "maintaince.md",
                    "contract/2026-10-30-release-contract-v4.md",
                    "tools/make-manifest-v4.py", "tools/check-release-v4.py"}
            return need <= names and all(not ASSET_SHAPE.search(n) for n in names)
        finally:
            shutil.rmtree(d, ignore_errors=True)
    ok("真构建：产物齐全 + 无 asset 形状", real_build)
    # 10. 确定性：两次构建逐字节一致
    def deterministic():

        def h(root):
            items = []
            for dp, _dn, fs in os.walk(root):
                for f in fs:
                    p = os.path.join(dp, f)
                    items.append((os.path.relpath(p, root),
                                  hashlib.sha256(open(p, "rb").read()).hexdigest()))
            return hashlib.sha256(repr(sorted(items)).encode()).hexdigest()

        d1 = tempfile.mkdtemp()
        d2 = tempfile.mkdtemp()
        try:
            build(os.path.join(d1, "a"))
            build(os.path.join(d2, "b"))
            return h(os.path.join(d1, "a")) == h(os.path.join(d2, "b"))
        finally:
            shutil.rmtree(d1, ignore_errors=True)
            shutil.rmtree(d2, ignore_errors=True)
    ok("确定性：两次构建逐字节一致", deterministic)

    bad = 0
    for label, passed, err in cases:
        print("%s | %s%s" % ("PASS" if passed else "fail", label,
                             "（%s）" % err.splitlines()[0] if err else ""))
        bad += 0 if passed else 1
    print("=== %d PASS / %d FAIL ===" % (len(cases) - bad, bad))
    return 1 if bad else 0


def _gate_flag(name, subdir="."):
    """在临时目录里造一个文件，跑闸门；闸门放行返回 False，拒绝抛 SystemExit。"""
    d = tempfile.mkdtemp()
    try:
        p = os.path.join(d, subdir, name)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "w").close()
        gate_dist(d)
        return False
    finally:
        shutil.rmtree(d, ignore_errors=True)


def main(argv):
    if "--selftest" in argv:
        return selftest()
    if "--out" not in argv:
        print("用法：build-site.py --out <dir> | --selftest", file=sys.stderr)
        return 2
    out = argv[argv.index("--out") + 1]
    build(out)
    print("built → %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
