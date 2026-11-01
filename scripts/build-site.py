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
def _publishable(src_dir, suffixes):
    """该目录里**可以发布**的文件名（排序）。目录一律不收。

    缺陷（2026-11-01，shirone `mail/005` §4 / `mail/006` §7 两次报告）：
    此前是裸 `sorted(os.listdir(...))` —— `--selftest` 在真仓里跑过一次后，
    Python 生成的 `tools/__pycache__/` 目录会被当成条目渲染成链接并发出去。
    `.gitignore` 有 `__pycache__/`，但**构建器不读 gitignore**。
    ⇒ 判据：只收**普通文件**且后缀在白名单内；点开头的一律排除。
    """
    out = []
    for name in sorted(os.listdir(src_dir)):
        if name.startswith(".") or name == "__pycache__":
            continue
        p = os.path.join(src_dir, name)
        if os.path.isfile(p) and name.endswith(suffixes):
            out.append(name)
    return out


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
            for name in _publishable(src_dir, (".md", ".py")):
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
    """页面形态照 **he.net**（2026-11-01 用户裁定：「去参考 he.net，纯 html 才对得起
    我们这么实用的静态站」）。

    抄的是**结构与信息密度**，不是抄它的营销内容：
      · 深蓝标题条（`#000066` 底 + 白字）分节，块边同色 1px —— he.net 的 block/caption；
      · 左侧边栏导航（170px）+ 右侧内容区（620px），窄屏堆叠；
      · Arial 13px、链接深蓝加粗带下划线；表格细黑边、无圆角无阴影；
      · 零 JS、零外链资源（he.net 有 gtag，我们一个都不要）；
      · 链接只给相对路径 ⇒ 三通道（Pages / CF / EdgeOne）通用。
    """
    releases = cat.get("releases") or []
    excluded = cat.get("excluded") or []
    n_rel, n_exc = len(releases), len(excluded)
    verified = (cat.get("verified_at") or "未派生（源文件兜底）")

    rows = "\n".join(
        "<tr><td><a href=\"%smanifest.json\"><code>%s</code></a></td>"
        "<td class=\"mono\">%s</td><td class=\"mono\">%s</td><td>%s</td></tr>"
        % (html.escape(e["base"]), html.escape(e["id"]),
           html.escape(str((e.get("manifest_sha256") or "")[:12])),
           html.escape(((e.get("verified_at") or "").replace("T", " ")[:16])),
           ('<a href="%smanifest.json">反代</a>' % html.escape(e["base_proxy"])
            if e.get("base_proxy") else "&mdash;"))
        for e in releases) or \
        '<tr><td colspan="4">（暂无收录 &mdash; 试点链第 1 环待跑）</td></tr>'

    ex_rows = "\n".join(
        '<tr><td><code>%s</code></td><td><code>%s</code></td><td class="mono">%s</td></tr>'
        % (html.escape(x.get("repo", "?")), html.escape(x.get("tag", "?")),
           html.escape("; ".join(x.get("reasons") or [])[:150]))
        for x in excluded) or '<tr><td colspan="3">（无排除项）</td></tr>'

    specs = _publishable(SPECS, (".md",))
    tools = _publishable(TOOLS, (".py",))

    def _links(names, prefix):
        if not names:
            return "<li>（无）</li>"
        return "\n".join('<li><a href="%s/%s">%s</a></li>'
                         % (prefix, html.escape(n), html.escape(n)) for n in names)

    return """<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="zh">
<head>
<meta http-equiv="content-type" content="application/xhtml+xml; charset=utf-8" />
<meta name="viewport" content="initial-scale=1" />
<title>Static-Contract &mdash; 静态分发契约</title>
<style>
body { background-color:#fff; color:#000; font-family:arial,sans-serif;
       font-size:13px; padding:0; margin:0; }
a { color:#000066; text-decoration:underline; font-weight:bold; }
code { font-family:monospace; font-size:100%; }
td code { font-size:92%; word-break:break-all; }
.mono { font-family:monospace; white-space:nowrap; }
h2 { font-size:100%; margin:0; padding:0; }
hr { height:1px; margin-bottom:1em; border:0; border-bottom:1px solid #000; }

#page_center { max-width:1240px; margin:0 auto; padding:0 8px; }
#header { width:100%; text-align:center; margin-bottom:13px; padding-top:8px; }
#header span { font-size:160%; font-weight:bold; }
#header h2 { font-weight:normal; font-size:100%; margin-top:.2em; }

.sidebar { display:inline; float:left; width:170px; margin-top:1px; }
#content { display:inline; float:left; width:1000px; margin:1px 10px 0 10px;
           padding-bottom:1px; }

.block { width:100%; margin-bottom:9px; padding-bottom:2px; text-align:left;
         border:1px solid #000066; }
.block .caption { width:100%; padding:.2em 0; font-size:130%; font-weight:bold;
                  text-align:center; background-color:#000066; color:#fff; }
.block .content { font-size:110%; padding:4px 12px 4px 12px; }

.menu { padding:0; margin:0; }
.menu li { list-style-type:none; margin-left:12px; }
.submenu { padding:0; margin:0; }
.submenu li { list-style-type:none; margin-left:8px; font-size:95%; }
.menu a, .submenu a { text-decoration:none; }
.menu a:hover, .submenu a:hover { text-decoration:underline; }

table { border-collapse:collapse; width:100%; margin:.3em 0; }
th, td { border:1px solid #000066; padding:.2em .4em; text-align:left;
         vertical-align:top; font-size:92%; }
th { background-color:#e8e8f0; }
.notice { border:1px solid #000066; background-color:#f4f4f8; padding:.4em .8em;
          margin:.3em 0; }
ul.doclist { padding-left:1.4em; margin:.2em 0; }
ul.doclist li { font-family:monospace; font-size:112%; }
address { font-style:normal; font-size:95%; color:#333; }
pre { font-family:monospace; font-size:100%; background-color:#f4f4f8;
      border:1px solid #999; padding:.5em; overflow-x:auto; margin:.4em 0; }

@media (max-width:1180px) {
  .sidebar, #content { float:none; width:auto; max-width:100%; }
  .sidebar { margin:0 10px; }
  #content { margin:10px; }
}
</style>
</head>
<body>
<div id="page_center">
  <div id="header">
    <span>Static-Contract</span><br />
    <h2>Octave 集群 &middot; 静态分发契约 &middot; 元数据站（0 字节托管）</h2>
  </div>

  <div class="sidebar" id="navigation">
    <div class="block">
      <div class="caption">本站</div>
      <div class="content">
        <ul class="menu">
          <li><a href="#what">这是什么</a></li>
          <li><a href="#catalogue">收录目录</a>
            <ul class="submenu">
              <li><a href="#excluded">排除项</a></li>
            </ul>
          </li>
          <li><a href="#consume">怎么消费</a></li>
          <li><a href="#channels">三条通道</a></li>
        </ul>
      </div>
    </div>
    <div class="block">
      <div class="caption">契约文档</div>
      <div class="content">
        <ul class="menu">
          <li><a href="#docs">全部 @@NSPECS@@ 份</a>
            <ul class="submenu">
              <li><a href="contract/2026-10-30-release-contract-v4.md">正典 v4</a></li>
            </ul>
          </li>
          <li><a href="#tools">工具链 @@NTOOLS@@ 件</a></li>
        </ul>
      </div>
    </div>
    <div class="block">
      <div class="caption">仓库</div>
      <div class="content">
        <ul class="menu">
          <li><a href="README.md">README.md</a></li>
          <li><a href="STATE.md">STATE.md</a></li>
          <li><a href="maintaince.md">maintaince.md</a></li>
          <li><a href="sources.json">sources.json</a></li>
          <li><a href="catalogue.json">catalogue.json</a></li>
        </ul>
      </div>
    </div>
    <div class="block">
      <div class="caption">源码</div>
      <div class="content">
        <ul class="menu">
          <li><a href="https://github.com/ArchivalEra/Static-Contract">GitHub 仓库</a></li>
          <li><a href="https://github.com/ArchivalEra/Static-Contract/tree/deploy">deploy 分支</a></li>
        </ul>
      </div>
    </div>
  </div>

  <div id="content">

    <div class="block">
      <div class="caption"><a name="what" style="color:#fff">这是什么</a></div>
      <div class="content">
        <p><b>一个 release = 一个不可变 tag = 一份 <code>manifest.json</code> + N 个扁平 asset。</b></p>
        <ul>
          <li>名字只允许 GitHub 不会改写的字符（白名单）&rArr;
              <code>manifest.file</code> 与真实 asset 名<b>恒等</b>。</li>
          <li>客户端只从 manifest 取名字、<b>绝不拼</b> &rArr; 404 只有一种含义。</li>
          <li>一切字节走<b>普通 GET</b> &mdash; 无 Range、无条件请求、无自定义头。</li>
        </ul>
        <p><b>目标：apt 的稳健 + HTTP 的简洁。</b></p>
        <div class="notice">
          <b>本站不收录任何 release 件（0 字节托管）。</b>
          所有的包要么去 GitHub 拿（release 直链），要么走反代。
          本站只收录<b>元数据</b>与<b>契约文档</b>。<br />
          <b>坏的从未上架</b>：每条 release 过 G1&ndash;G6（含平台 digest 零下载验字节），
          不过的不进目录、原因照列。
        </div>
      </div>
    </div>

    <div class="block">
      <div class="caption"><a name="catalogue" style="color:#fff">收录目录（@@NREL@@ 条）</a></div>
      <div class="content">
        <p>每条的 id 都可点 &mdash; 直接打开该 release 的 <code>manifest.json</code>。
           验证时刻与 manifest sha 是<b>派生当时</b>的实测值。</p>
        <table>
          <tr><th>id</th><th>manifest sha</th><th>验证时刻 (UTC)</th><th>反代</th></tr>
@@ROWS@@
        </table>
        <p><a href="catalogue.json">catalogue.json</a> &mdash; 机器可读全量（含 <code>excluded</code> 原因）</p>
      </div>
    </div>

    <div class="block">
      <div class="caption"><a name="excluded" style="color:#fff">排除项（@@NEXC@@ 条）</a></div>
      <div class="content">
        <p>以下 release <b>未通过严格校验，不在目录里</b>。列出来是为了让发布方知道
           <b>为什么它没上架</b> &mdash; 静默消失才是最难查的坏法。</p>
        <table>
          <tr><th>仓</th><th>tag</th><th>原因</th></tr>
@@EXROWS@@
        </table>
      </div>
    </div>

    <div class="block">
      <div class="caption"><a name="docs" style="color:#fff">契约文档</a></div>
      <div class="content">
        <p><b>正典：<a href="contract/2026-10-30-release-contract-v4.md">
           2026-10-30-release-contract-v4.md</a></b> &mdash;
           契约定名 <b>v1</b>，manifest <code>schema: 2</code>。
           v0&ndash;v3 与收纳审计是演化史，<b>被否方案的判据留在正典 &sect;8</b>，防将来重开。
           移交给本仓时正典<b>从未试点，不宣布稳定</b>。</p>
        <ul class="doclist">
@@SPECS@@
        </ul>
      </div>
    </div>

    <div class="block">
      <div class="caption"><a name="tools" style="color:#fff">工具链</a></div>
      <div class="content">
        <p>生成器自证 <code>43 PASS / 0 fail</code>；校验器 <code>26 PASS / 0 fail</code>
           （V1&ndash;V10 逐条反向）。复跑：<br />
           <code>python3 tools/make-manifest-v4.py --selftest</code><br />
           <code>python3 tools/check-release-v4.py --selftest</code></p>
        <ul class="doclist">
@@TOOLS@@
        </ul>
      </div>
    </div>

    <div class="block">
      <div class="caption"><a name="consume" style="color:#fff">怎么消费</a></div>
      <div class="content">
<pre>1. GET &lt;base&gt;/manifest.json         # 全流程唯一需要"知道"的 URL
2. 校验 schema / 不变量（本地，0 请求）
3. 选 product（按 form/arch；源码路径只读 src product）
4. 对每条 entry 按 codecs 顺序选第一个能解的分支：
     name = variant.chunks[i].file    # 逐字取，绝不拼
     GET &lt;base&gt;/&lt;name&gt;               # 普通 GET
     校验 bytes + 逐块 sha256 &rarr; 解码 &rarr; 拼接 &rarr; 校验 entry.sha256</pre>
        <p>三条铁律：<b>不拼名字</b>、<b>不试错探测</b>、
           <b>不用 Range / 条件请求 / 自定义头</b>。</p>
      </div>
    </div>

    <div class="block">
      <div class="caption"><a name="channels" style="color:#fff">三条通道（同一份产物）</a></div>
      <div class="content">
        <table>
          <tr><th>通道</th><th>URL</th><th>形态</th></tr>
          <tr><td>GitHub Pages</td>
              <td class="mono"><a href="https://archivalera.github.io/Static-Contract/">archivalera.github.io/Static-Contract/</a></td>
              <td>本仓 workflow 直发</td></tr>
          <tr><td>Cloudflare</td>
              <td class="mono"><a href="https://static.mango-mesa.ccwu.cc/static/">static.mango-mesa.ccwu.cc/static/</a></td>
              <td>运行期回源 deploy 分支</td></tr>
          <tr><td>EdgeOne</td>
              <td class="mono"><a href="https://isui.ren/static/">isui.ren/static/</a></td>
              <td>独立静态树（国内路径）</td></tr>
        </table>
        <p>三通道逐字同源，页脚指纹可核对。字节始终在 GitHub release / 反代，
           不在本站。</p>
      </div>
    </div>

    <div class="block">
      <div class="caption">站点信息</div>
      <div class="content">
        <address>
          catalogue verified_at: <span class="mono">@@VERIFIED@@</span><br />
          @@FP@@<br />
          本站零 JS、零外链资源 &mdash; 纯 XHTML 1.1 + CSS，文本浏览器可读。<br />
          维护方：<a href="https://github.com/ArchivalEra">ArchivalEra</a> &middot;
          契约正典 <a href="contract/2026-10-30-release-contract-v4.md">contract/</a>
        </address>
      </div>
    </div>

  </div>
</div>
</body>
</html>
""".replace("@@ROWS@@", rows).replace("@@EXROWS@@", ex_rows) \
   .replace("@@SPECS@@", _links(specs, "contract")) \
   .replace("@@TOOLS@@", _links(tools, "tools")) \
   .replace("@@NREL@@", str(n_rel)).replace("@@NEXC@@", str(n_exc)) \
   .replace("@@NSPECS@@", str(len(specs))).replace("@@NTOOLS@@", str(len(tools))) \
   .replace("@@VERIFIED@@", html.escape(verified)) \
   .replace("@@FP@@", html.escape(fingerprint))

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
    # 11. 发布过滤：目录 / 点开头 / 非白名单后缀 都不许进产物
    #     （shirone mail/005 §4 报告的缺陷：__pycache__ 曾被渲染成链接）
    def publishable_filter():
        d = tempfile.mkdtemp()
        try:
            open(os.path.join(d, "good.py"), "w").close()
            open(os.path.join(d, ".hidden.py"), "w").close()
            open(os.path.join(d, "note.txt"), "w").close()
            os.makedirs(os.path.join(d, "__pycache__"))
            os.makedirs(os.path.join(d, "subdir"))
            return _publishable(d, (".py",)) == ["good.py"]
        finally:
            shutil.rmtree(d, ignore_errors=True)
    ok("★ 发布过滤：目录 / 点开头 / 非白名单后缀一律不收（__pycache__ 缺陷）",
       publishable_filter)

    # 12. 真构建里不得出现 __pycache__（端到端复现那条缺陷）
    def no_pycache_in_dist():
        d = tempfile.mkdtemp()
        try:
            os.makedirs(os.path.join(TOOLS, "__pycache__"), exist_ok=True)
            build(os.path.join(d, "dist"))
            idx = open(os.path.join(d, "dist", "index.html"), encoding="utf-8").read()
            bad = [n for dp, dn, fn in os.walk(os.path.join(d, "dist"))
                   for n in dn + fn if n == "__pycache__"]
            return "__pycache__" not in idx and not bad
        finally:
            shutil.rmtree(d, ignore_errors=True)
            shutil.rmtree(os.path.join(TOOLS, "__pycache__"), ignore_errors=True)
    ok("★ 真构建：tools/__pycache__ 存在时产物也不含它（端到端）", no_pycache_in_dist)

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
