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
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPECS = os.path.join(HERE, "specs")
TOOLS = os.path.join(HERE, "tools")
CATALOGUE_SRC = os.path.join(HERE, "site", "catalogue.json")
SOURCES_SRC = os.path.join(HERE, "site", "sources.json")
CHANNELS_SRC = os.path.join(HERE, "site", "channels.json")
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
def _selftest_count(script):
    """跑某个工具的自证，数 PASS 行。**失败返回 None，不编数字**。"""
    try:
        r = subprocess.run([sys.executable, os.path.join(HERE, script), "--selftest"],
                           capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    return sum(1 for ln in r.stdout.splitlines() if ln.startswith("PASS"))


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
        for fname in ("README.md", "STATE.md", "maintaince.md", "LICENSE"):
            shutil.copy2(os.path.join(HERE, fname), os.path.join(d, fname))
        # 自证数实测（不手抄）；工具不在就明说未知。
        # ⚠️ 自证模式下不跑自证（build-site --selftest 会调 build() ⇒ 递归爆栈）
        if os.environ.get("SC_BUILD_SELFTEST") == "1":
            counts, chans = {}, []
        else:
            counts = {k: _selftest_count(v) for k, v in (
                ("gen", "tools/make-manifest-v4.py"),
                ("chk", "tools/check-release-v4.py"),
                ("build", "scripts/build-site.py"),
                ("cat", "scripts/sync-catalogue.py"))}
            try:
                cdoc = json.load(open(CHANNELS_SRC, encoding="utf-8"))
                chans = cdoc.get("channels") or []
            except (OSError, ValueError):
                chans = []
        with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as f:
            f.write(render_index(cat, fingerprint, counts, chans))
        gate_dist(d)
        if os.path.exists(out):
            shutil.rmtree(out)
        shutil.move(d, out)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return out


def render_index(cat, fingerprint="", counts=None, channels=None):
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
    verified = (cat.get("verified_at") or "not derived (source fallback)")
    counts = counts or {}
    channels = channels or []

    def _cnt(k):
        v = counts.get(k)
        return ("%d PASS" % v) if isinstance(v, int) else "not measured"

    # 通道表：从 site/channels.json 生成（**不手写**）
    if channels:
        # note 是实现细节（长），表格只放英文摘要；note 不进 HTML（闸门要求全英文）
        ch_rows = "\n".join(
            '<tr><td>%s</td><td class="mono"><a href="%s">%s</a></td>'
            '<td class="m">%s</td></tr>'
            % (html.escape(c.get("name", "?")), html.escape(c.get("base", "#")),
               html.escape(c.get("base", "?").rstrip("/").split("//")[-1]),
               html.escape(c.get("summary_en") or ""))
            for c in channels)
    else:
        ch_rows = '<tr><td colspan="3">(channels.json not configured)</td></tr>'

    rows = "\n".join(
        "<tr><td><a href=\"%smanifest.json\"><code>%s</code></a></td>"
        "<td class=\"mono\">%s</td><td class=\"mono\">%s</td><td>%s</td></tr>"
        % (html.escape(e["base"]), html.escape(e["id"]),
           html.escape(str((e.get("manifest_sha256") or "")[:12])),
           html.escape(((e.get("verified_at") or "").replace("T", " ")[:16])),
           ('<a href="%smanifest.json">反代</a>' % html.escape(e["base_proxy"])
            if e.get("base_proxy") else "&mdash;"))
        for e in releases) or \
        '<tr><td colspan="4">(no entries yet &mdash; pilot chain step 1 not started)</td></tr>'

    ex_rows = "\n".join(
        '<tr><td><code>%s</code></td><td><code>%s</code></td><td class="mono">%s</td></tr>'
        % (html.escape(x.get("repo", "?")), html.escape(x.get("tag", "?")),
           html.escape("; ".join(x.get("reasons") or [])[:150]))
        for x in excluded) or '<tr><td colspan="3">(none)</td></tr>'

    specs = _publishable(SPECS, (".md",))
    tools = _publishable(TOOLS, (".py",))

    def _links(names, prefix):
        """文档列表。**废弃文档必须带标记** —— 否则读者会照旧形态实现（闸门 H2 查这条）。"""
        if not names:
            return "<li>(none)</li>"
        out = []
        for n in names:
            mark = ""
            try:
                head = open(os.path.join(SPECS, n), encoding="utf-8").read(800)
                if "DEPRECATED" in head:
                    mark = ' <span class="dep">[DEPRECATED]</span>'
                elif "SUPERSEDED IN PART" in head:
                    mark = ' <span class="dep">[PARTLY SUPERSEDED]</span>'
            except OSError:
                pass
            out.append('<li><a href="%s/%s">%s</a>%s</li>'
                       % (prefix, html.escape(n), html.escape(n), mark))
        return "\n".join(out)

    return """<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en">
<head>
<meta http-equiv="content-type" content="application/xhtml+xml; charset=utf-8" />
<meta name="viewport" content="initial-scale=1" />
<title>Static-Contract &mdash; Static Distribution Contract</title>
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
.dep { color:#8b0000; font-weight:bold; font-size:90%; margin-left:.4em; }
ul.doclist { padding-left:1.4em; margin:.2em 0; }
ul.doclist li { font-family:monospace; font-size:112%; }
address { font-style:normal; font-size:95%; color:#333; }
.copy { font-size:110%; }
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
    <h2>Octave cluster &middot; static distribution contract &middot; metadata site (zero-byte hosting)</h2>
    <div style="font-size:95%;margin-top:.2em">
      License: <a href="https://www.gnu.org/licenses/agpl-3.0.html">AGPL-3.0</a>
      &middot; <a href="LICENSE">full text</a>
    </div>
  </div>

  <div class="sidebar" id="navigation">
    <div class="block">
      <div class="caption">Site</div>
      <div class="content">
        <ul class="menu">
          <li><a href="#what">What this is</a></li>
          <li><a href="#catalogue">Catalogue</a>
            <ul class="submenu">
              <li><a href="#excluded">Excluded</a></li>
            </ul>
          </li>
          <li><a href="#consume">How to consume</a></li>
          <li><a href="#channels">Channels</a></li>
        </ul>
      </div>
    </div>
    <div class="block">
      <div class="caption">Contract</div>
      <div class="content">
        <ul class="menu">
          <li><a href="#docs">All @@NSPECS@@ documents</a>
            <ul class="submenu">
              <li><a href="contract/2026-10-30-release-contract-v4.md">v4 &mdash; V1&ndash;V10</a></li>
              <li><a href="contract/2026-11-01-release-contract-v1.1-license.md">v1.1 &mdash; V11</a></li>
            </ul>
          </li>
          <li><a href="#tools">Tools @@NTOOLS@@</a></li>
        </ul>
      </div>
    </div>
    <div class="block">
      <div class="caption">Repository</div>
      <div class="content">
        <ul class="menu">
          <li><a href="README.md">README.md</a></li>
          <li><a href="STATE.md">STATE.md</a></li>
          <li><a href="maintaince.md">maintaince.md</a></li>
          <li><a href="sources.json">sources.json</a></li>
          <li><a href="catalogue.json">catalogue.json</a></li>
          <li><a href="LICENSE">LICENSE (AGPL-3.0)</a></li>
        </ul>
      </div>
    </div>
    <div class="block">
      <div class="caption">Source</div>
      <div class="content">
        <ul class="menu">
          <li><a href="https://github.com/ArchivalEra/Static-Contract">GitHub repository</a></li>
          <li><a href="https://github.com/ArchivalEra/Static-Contract/tree/deploy">deploy branch</a></li>
        </ul>
      </div>
    </div>
  </div>

  <div id="content">

    <div class="block">
      <div class="caption"><a name="what" style="color:#fff">What this is</a></div>
      <div class="content">
        <p><b>One release = one immutable tag = one <code>manifest.json</code> + N flat assets.</b></p>
        <ul>
          <li>Names use only characters GitHub will not rewrite (whitelist) &rArr;
              <code>manifest.file</code> is <b>identical</b> to the real asset name.</li>
          <li>Clients take names <b>only</b> from the manifest, never concatenate &rArr;
              404 has exactly one meaning.</li>
          <li>All bytes travel by <b>plain GET</b> &mdash; no Range, no conditional
              requests, no custom headers.</li>
        </ul>
        <p><b>Goal: the robustness of apt + the simplicity of HTTP.</b></p>
        <div class="notice">
          <b>This site hosts zero bytes of any release.</b>
          Every package comes either from GitHub (release direct link) or through a
          reverse proxy. This site publishes <b>metadata</b> and <b>contract documents</b> only.
          <br />
          <b>Bad releases never go live</b>: every release passes G1&ndash;G7 (including
          platform-digest verification with zero download). Anything that fails stays
          out of the catalogue, with the reason listed.
        </div>
      </div>
    </div>

    <div class="block">
      <div class="caption"><a name="catalogue" style="color:#fff">Catalogue (@@NREL@@ releases)</a></div>
      <div class="content">
        <p>Every id is clickable &mdash; it opens that release's <code>manifest.json</code>
           directly. The verification time and manifest sha are the values
           <b>measured at derivation time</b>.</p>
        <table>
          <tr><th>id</th><th>manifest sha</th><th>verified (UTC)</th><th>proxy</th></tr>
@@ROWS@@
        </table>
        <p><a href="catalogue.json">catalogue.json</a> &mdash; machine-readable full record
           (including <code>excluded</code> reasons and per-release <code>license</code>)</p>
      </div>
    </div>

    <div class="block">
      <div class="caption"><a name="excluded" style="color:#fff">Excluded (@@NEXC@@ releases)</a></div>
      <div class="content">
        <p>These releases <b>failed strict validation and are not in the catalogue</b>.
           They are listed so publishers can see <b>why they are not live</b> &mdash;
           silent disappearance is the hardest failure to debug.</p>
        <table>
          <tr><th>repo</th><th>tag</th><th>reason</th></tr>
@@EXROWS@@
        </table>
      </div>
    </div>

    <div class="block">
      <div class="caption"><a name="docs" style="color:#fff">Contract documents</a></div>
      <div class="content">
        <p><b>Current authority:</b>
           <a href="contract/2026-10-30-release-contract-v4.md">v4 &mdash; V1&ndash;V10</a>
           (base invariants) plus
           <a href="contract/2026-11-01-release-contract-v1.1-license.md">v1.1 &mdash; V11</a>
           (per-release license, manifest <code>schema: 3</code>).</p>
        <p>Everything else is <b>history</b>. Rejected designs and their criteria are kept
           in v4 &sect;8 and v1.1 &sect;9 so they are not re-opened by accident.
           <b>Not yet piloted end-to-end; not declared stable.</b></p>
        <ul class="doclist">
@@SPECS@@
        </ul>
      </div>
    </div>

    <div class="block">
      <div class="caption"><a name="tools" style="color:#fff">Tools</a></div>
      <div class="content">
        <p>manifest generator <code>@@CNT_GEN@@</code> &middot;
           contract checker <code>@@CNT_CHK@@</code> &middot;
           site builder <code>@@CNT_BUILD@@</code> &middot;
           catalogue deriver <code>@@CNT_CAT@@</code>.<br />
           <small>(These counts are <b>measured by the builder itself</b>, never
           hand-copied &mdash; a copied number starts rotting the moment it is written.)</small><br />
           Reproduce: <code>python3 tools/make-manifest-v4.py --selftest</code> &middot;
           <code>python3 tools/check-release-v4.py --selftest</code></p>
        <ul class="doclist">
@@TOOLS@@
        </ul>
      </div>
    </div>

    <div class="block">
      <div class="caption"><a name="consume" style="color:#fff">How to consume</a></div>
      <div class="content">
<pre>1. GET &lt;base&gt;/manifest.json         # the only URL you need to know
2. validate schema / invariants (local, 0 requests)
3. pick a product (by form/arch; source path reads the src product only)
4. for each entry, take the first decodable variant per codecs order:
     name = variant.chunks[i].file    # verbatim, never concatenate
     GET &lt;base&gt;/&lt;name&gt;               # plain GET
     check bytes + per-chunk sha256 &rarr; decode &rarr; concat &rarr; check entry.sha256</pre>
        <p>Three rules: <b>never build names</b>, <b>never probe by trial</b>,
           <b>never use Range / conditional requests / custom headers</b>.</p>
      </div>
    </div>

    <div class="block">
      <div class="caption"><a name="channels" style="color:#fff">Channels (same artifact)</a></div>
      <div class="content">
        <table>
          <tr><th>channel</th><th>URL</th><th>form</th></tr>
@@CHANNELS@@
        </table>
        <p>All channels serve the same bytes, verifiable by the build fingerprint in the
           footer. Release bytes always live on GitHub releases or a proxy, never here.</p>
      </div>
    </div>

    <div class="block">
      <div class="caption">Site information</div>
      <div class="content">
        <address>
          <b class="copy">&copy; 2026 ArchivalEra. All rights reserved.</b><br />
          This site (pages, contract documents, tools) is licensed under
          <a href="https://www.gnu.org/licenses/agpl-3.0.html">AGPL-3.0</a> &mdash;
          full text: <a href="LICENSE">LICENSE</a> &middot;
          source: <a href="https://github.com/ArchivalEra/Static-Contract">GitHub</a><br />
          <b>Catalogued releases are NOT covered by this licence</b> &mdash; each release
          is governed by its publisher's terms, listed per release in
          <a href="catalogue.json">catalogue.json</a> (<code>license.id</code> +
          <code>license.url</code>) and in its own <code>manifest.json</code>.
          This site hosts <b>metadata only</b>, never bytes.<br /><br />
          catalogue verified_at: <span class="mono">@@VERIFIED@@</span><br />
          @@FP@@<br />
          Zero JS, zero external resources &mdash; plain XHTML 1.1 + CSS, readable in
          a text browser.<br />
          Maintainer: <a href="https://github.com/ArchivalEra">ArchivalEra</a> &middot;
          contract: <a href="contract/2026-10-30-release-contract-v4.md">contract/</a>
        </address>
      </div>
    </div>

  </div>
</div>
</body>
</html>
'''""".replace("@@ROWS@@", rows).replace("@@EXROWS@@", ex_rows) \
   .replace("@@SPECS@@", _links(specs, "contract")) \
   .replace("@@TOOLS@@", _links(tools, "tools")) \
   .replace("@@NREL@@", str(n_rel)).replace("@@NEXC@@", str(n_exc)) \
   .replace("@@NSPECS@@", str(len(specs))).replace("@@NTOOLS@@", str(len(tools))) \
   .replace("@@CNT_GEN@@", _cnt("gen")) \
   .replace("@@CNT_CHK@@", _cnt("chk")) \
   .replace("@@CNT_BUILD@@", _cnt("build")) \
   .replace("@@CNT_CAT@@", _cnt("cat")) \
   .replace("@@CHANNELS@@", ch_rows) \
   .replace("@@VERIFIED@@", html.escape(verified)) \
   .replace("@@FP@@", html.escape(fingerprint))

# ── 自证 ─────────────────────────────────────────────────────────────────────
def selftest():
    os.environ["SC_BUILD_SELFTEST"] = "1"
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
                    "STATE.md", "maintaince.md", "LICENSE", "sources.json",
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

    # 13. 许可证标记：页面必须声明 AGPL 且 LICENSE 随站发布
    def license_marked():
        d = tempfile.mkdtemp()
        try:
            build(os.path.join(d, "dist"))
            idx = open(os.path.join(d, "dist", "index.html"), encoding="utf-8").read()
            has_lic = os.path.exists(os.path.join(d, "dist", "LICENSE"))
            return has_lic and "AGPL-3.0" in idx and 'href="LICENSE"' in idx
        finally:
            shutil.rmtree(d, ignore_errors=True)
    ok("★ 许可证：页面声明 AGPL-3.0 且 LICENSE 随站发布", license_marked)

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
