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
  H4 catalogue 的**公开字段**（note / reason / id / license）不得含 CJK；
     且缺 catalogue 时**必须红**（「没跑 ≠ 通过」）
  H5 页面里每个相对链接必须指向产物内真实存在的文件（只查产物内，不探测外链）

权威文档 = `2026-11-01-release-contract-v1.1-license.md`（v1.1）
         + `2026-10-30-release-contract-v4.md`（V1–V10，部分取代）

用法：
  python3 zreflect/check_site_lang.py            # 违规即非零
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request

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


# 发布到站点的 .md 必须全英文、无表情、无圈号（用户裁定 2026-11-03）。
# `docs/rulings.md` 例外：它**不进站点**（保留用户中文原话，那是判据的历史证据）。
# 覆盖面按「实际在文档里出现过的」扩：⭕ ⬜ ⏰ ⌛ ⏩ ™ 都漏过（review 抓到）。
EMOJI = re.compile(r"[\U0001F300-\U0001FAFF\u2600-\u27BF\u2B50\u2714\u2716"
                   r"\u26A1\u2705\u274C\u26A0\uFE0F\u267B\u2611\u2612"
                   r"\u2B55\u2B1C\u23F0\u231B\u23E9\u2122\u2717\u2718"
                   r"\u2764\u2757\u2753\u2755\u203C]")
CIRCLED = re.compile(r"[\u2460-\u24FF\u2776-\u2793]")


# 发布面白名单（用户裁定 2026-11-03）：站点只出货架与契约。
# 维护类文档（STATE / maintaince / README / incidents / rulings / tools / 历史契约）
# 留在仓库里，**不发布** —— 读者不维护这个仓。
EXPECTED_ARTIFACT = {
    "index.html",           # 生成的货架页
    "files.json",           # 生成的产物清单（镜像方照抄）
    "catalogue.json",       # 货架本体
    "sources.json",         # 货架覆盖哪些仓
    "LICENSE",              # 本站自身许可
    "contract/2026-10-30-release-contract-v4.md",
    "contract/2026-11-01-release-contract-v1.1-license.md",
}


def check_publish_surface(dist_dir):
    """H9：产物必须**恰好**等于白名单。

    这是本仓最重要的一条站点判据。用户原话（2026-11-03）：
    「读者需要知道仓库内的事情吗……只需要放出来货架长啥样以及契约啥样就行了」。

    多一个文件 ⇒ 红（发布面在扩散）。少一个 ⇒ 红（货架或缺契约）。
    """
    actual = set()
    for root, _dirs, files in os.walk(dist_dir):
        for f in files:
            actual.add(os.path.relpath(os.path.join(root, f), dist_dir).replace(os.sep, "/"))
    extra = sorted(actual - EXPECTED_ARTIFACT)
    missing = sorted(EXPECTED_ARTIFACT - actual)
    probs = []
    if extra:
        probs.append("H9 发布了不该发布的文件: %s" % ", ".join(extra[:8]))
    if missing:
        probs.append("H9 缺少必需文件: %s" % ", ".join(missing))
    return probs


def check_published_md(dist_dir):
    """H8：产物里的 .md 不得含 CJK / emoji / 圈号。

    来源（用户裁定 2026-11-03）：「站上的那些包括 v1.1 契约都还是有中文有表情符号的版本」。
    H1 只查 index.html，契约正文一路带中文发布到三个站 —— 那是系统性的漏。
    """
    probs = []
    mds = []
    for root, _dirs, files in os.walk(dist_dir):
        for f in files:
            if f.endswith(".md"):
                mds.append(os.path.join(root, f))
    if not mds:
        return ["H8 产物里没有 .md —— 未查不是通过"]
    for p in sorted(mds):
        rel = os.path.relpath(p, dist_dir)
        t = open(p, encoding="utf-8", errors="replace").read()
        # 豁免机器块：AUTO:FACTS / AUTO:GATES 由 vendored 平台渲染（中文模板），
        # 那是**生成物不是散文**。改渲染器等于 fork 上游 Einfacht —— 不做。
        # 判据：只查块外的正文。
        for begin, end in (("<!-- AUTO:FACTS -->", "<!-- /AUTO:FACTS -->"),
                           ("<!-- AUTO:GATES -->", "<!-- /AUTO:GATES -->")):
            while begin in t and end in t:
                a = t.index(begin)
                b = t.index(end, a) + len(end)
                t = t[:a] + t[b:]
        cjk = len(CJK.findall(t))
        em = len(EMOJI.findall(t))
        nu = len(CIRCLED.findall(t))
        if cjk or em or nu:
            probs.append("H8 %s 含 CJK=%d emoji=%d 圈号=%d" % (rel, cjk, em, nu))
    return probs


def check_links(html, dist_dir):
    """H5：页面里每个相对链接必须指向产物内真实存在的文件。

    为什么必须：三个通道都在服务同一份产物，一处死链就是三处死链。
    只查**产物内**（确定性、零网络）；外链（GitHub / gnu.org / 各通道 URL）
    不做在线探测 —— 本机网络对 GitHub 不稳，会把网络问题误判成坏链
    （实测：Cloudflare 通道与 github.com 全部 URLError/Timeout，而链接本身完好）。
    """
    probs = []
    links = sorted({m for m in re.findall(r'href="([^"#]+)"', html)
                    if not m.startswith(("http://", "https://", "mailto:", "#"))})
    for l in links:
        p = os.path.join(dist_dir, l)
        if not os.path.exists(p):
            probs.append("H5 死链: %s（产物里没有这个文件）" % l)
    # 反向：产物里有文件但页面没链到（提示，不算失败）——只在 verbosely 打印
    return probs, len(links)


def _http(url, timeout=20):
    """取 (status, body)。异常返回 (类型名, b"")。

    支持代理：环境变量 `SC_HTTP_PROXY`（如 http://127.0.0.1:2080）。
    为什么需要：某些网络出口对 Cloudflare 做了 SNI reset（实测 TLS reset），
    没有代理时该通道恒 URLError —— 而「不可达」在 H6 里是失败，
    会把「网络问题」误报成「死链」。用代理可区分两者。
    """
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "static-contract-gate/1"})
        proxy = os.environ.get("SC_HTTP_PROXY", "").strip()
        if proxy:
            op = urllib.request.build_opener(
                urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
            with op.open(req, timeout=timeout) as r:
                return r.status, r.read()
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, b""
    except Exception as e:                                   # noqa: BLE001
        return type(e).__name__, b""


def probe_fallback(base):
    """取兜底指纹。两种合法形态：
      · 200 + HTML 兜底页（EdgeOne）⇒ 指纹 = body sha
      · 404 + 空 body（Pages）⇒ 指纹 = "HTTP:<code>"，用于识别死链
    只有**网络不可达**才算「取不到」。
    """
    code, body = _http(base.rstrip("/") + "/zzz-nonexistent-" + str(os.getpid()) + ".md")
    if body:
        return "sha:" + hashlib.sha256(body).hexdigest(), code
    if isinstance(code, int) and code >= 400:
        return "HTTP:%d" % code, code
    return None, code


def check_channels_online(channels, links, attempts=2):
    """H6：逐通道逐链接在线探测。**用内容指纹，不用状态码。**

    返回 (problems, stats)。不可达**算失败**（就算「它没问题」——某通道连不上时
    那句话没有任何证据）。但网络抖动给 attempts 次机会，避免把瞬断当死链。
    """
    probs = []
    stats = {}
    for ch in channels:
        name, base = ch.get("name", "?"), ch.get("base", "")
        if not base:
            probs.append("H6 通道 %s 缺 base" % name)
            continue
        fb_sha, fb_code = probe_fallback(base)
        if fb_sha is None:
            probs.append("H6 %s 兜底页取不到（%s）—— 无法判定死链" % (name, fb_code))
            continue
        dead, unreachable = [], []
        for l in links:
            last = None
            for _ in range(attempts):
                code, body = _http(base.rstrip("/") + "/" + l)
                if body:
                    last = (code, "sha:" + hashlib.sha256(body).hexdigest())
                    if last[1] != fb_sha:
                        break
                elif isinstance(code, int):
                    last = (code, "HTTP:%d" % code)
                    if last[1] != fb_sha:
                        break                 # 404 且指纹不是兜底 ⇒ 也算「不同」（会被下方判死）
                else:
                    last = (code, None)
            if last is None or last[1] is None:
                unreachable.append((l, last[0] if last else "unknown"))
            elif last[1] == fb_sha:
                dead.append(l)
        # ★ 归属判断：**只有我方管线（owned=true）的失败阻塞发布**。
        # 外部通道（CF/EO）挂了不该拦我的产物上线 —— 那是别人的故障，
        # 我发不出去只会让问题叠加（我的新产物上不去，他们的通道还没人修）。
        # 但**必须报告**：静默略过等于把别人的故障藏起来。
        owned = bool(ch.get("owned"))
        tag = "" if owned else "（外通道，不阻塞发布）"
        if dead:
            msg = ("H6 %s 死链 %d 条（返回兜底页/404）: %s"
                   % (name, len(dead), ", ".join(dead[:6])))
            if owned:
                probs.append(msg)
            else:
                print("⚠ %s%s" % (msg, tag))
        if unreachable:
            msg = ("H6 %s 不可达 %d 条（不可达不是「没问题」）: %s"
                   % (name, len(unreachable),
                      ", ".join("%s(%s)" % x for x in unreachable[:6])))
            if owned:
                probs.append(msg)
            else:
                print("⚠ %s%s" % (msg, tag))
        stats[name] = {"checked": len(links), "dead": len(dead),
                       "unreachable": len(unreachable)}
    return probs, stats


def check_catalogue_bases(cat_path, attempts=2):
    """H7：catalogue 里每条 `base + manifest.json` 必须真的可达。

    为什么单列（extra-content mail/007 实测事故）：上游「删旧 tag + 发新 tag」后，
    catalogue 会在一整个派生周期里指向**已删除的 tag** —— 实测两条 base 全 404，
    而当时我所有的闸门都是绿的（它们只查产物，不查 catalogue 指向的活链）。

    ⚠️ 这条**只对 `releases` 生效**；`excluded` 里的 tag 允许不可达
    （那正是它被排除的原因）。
    """
    import json
    probs = []
    if not os.path.exists(cat_path):
        return ["H7 catalogue 不存在"]
    try:
        d = json.load(open(cat_path, encoding="utf-8"))
    except ValueError as e:
        return ["H7 catalogue 非法 JSON: %s" % e]
    rel = d.get("releases") or []
    if not rel:
        return ["H7 catalogue 没有 releases —— 未查不是通过"]
    dead = []
    for r in rel:
        u = (r.get("base") or "") + "manifest.json"
        code = None
        for _ in range(attempts):
            code, body = _http(u)
            if isinstance(code, int) and code == 200 and body:
                break
        else:
            dead.append((r.get("id", "?"), code))
            continue
        if not (isinstance(code, int) and code == 200):
            dead.append((r.get("id", "?"), code))
    if dead:
        probs.append("H7 %d/%d 条 base 取不到 manifest（catalogue 指向已删除的 tag？）: %s"
                     % (len(dead), len(rel),
                        ", ".join("%s(%s)" % x for x in dead[:5])))
    return probs


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
    # ★ 整份 catalogue 的**对外字段**不得含 CJK（note / id / license / excluded）
    #   中文 reasons 是给维护者的内部诊断，**允许**留在 catalogue 里；
    #   但对外可见的部分（note / reasons_en / license / id）必须全英文。
    note = d.get("note")
    if isinstance(note, str) and CJK.search(note):
        probs.append("H4 catalogue.note 含中文（这是公开发布字段）")
    for x in d.get("excluded") or []:
        if not isinstance(x, dict):
            continue
        # 协议 §5.1 G7：excluded 只为「写原因」。键名 `reason`（单数、英文字符串）。
        if not isinstance(x.get("reason"), str) or not x["reason"].strip():
            probs.append("H4 excluded %s/%s 缺 reason" % (x.get("repo"), x.get("tag")))
        elif CJK.search(x["reason"]):
            probs.append("H4 excluded %s/%s 的 reason 含中文" % (x.get("repo"), x.get("tag")))
    for r in d.get("releases") or []:
        if not isinstance(r, dict):
            continue
        if CJK.search(r.get("id") or ""):
            probs.append("H4 release id 含中文: %r" % r.get("id"))
        lic = r.get("license")
        if isinstance(lic, dict):
            for k in ("id", "url"):
                if CJK.search(lic.get(k) or ""):
                    probs.append("H4 %s 的 license.%s 含中文" % (r.get("id"), k))
    return probs


def main():
    import tempfile
    import shutil

    probs = []
    tmp = tempfile.mkdtemp(prefix="sc-site-")
    try:
        dist_dir = os.path.join(tmp, "dist")
        rc, log = _build_to(dist_dir, cat=CAT_ABS)
        if rc != 0:
            probs.append("构建失败（rc=%d）：%s" % (rc, log.strip().splitlines()[-1:]))
            html = ""
        else:
            html = open(os.path.join(dist_dir, "index.html"), encoding="utf-8").read()
            hits = check_html_lang(html)
            if hits:
                probs.append("H1 index.html 含 %d 个 CJK 字符，例：%r"
                             % (len(CJK.findall(html)), hits[:2]))
            # ⚠️ H5 必须在 tmp 还在时跑 —— 曾放到 finally 之后，
            #    产物已删 ⇒ 15 条全部误报"死链"（判据对，时序错）。
            link_probs, n_links = check_links(html, dist_dir)
            probs += link_probs
            print("H5：检查了 %d 个产物内相对链接" % n_links)
            h8 = check_published_md(dist_dir)
            probs += h8
            h9 = check_publish_surface(dist_dir)
            probs += h9
            print("H8 发布 md 语言: %s | H9 发布面: %s"
                  % ("全部英文" if not h8 else "%d 个不合格" % len(h8),
                     "恰好是货架+契约" if not h9 else "越界"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    probs += check_specs_marked(SPECS)
    # ⚠️ 缺 catalogue 必须红，不许静默跳过。
    # 「没跑 ≠ 通过」—— 线上事故就是闸门查不到数据而报绿。
    if CAT_ABS:
        probs += check_catalogue_en(CAT_ABS)
    else:
        # 本地 pre-commit 没有派生件时：查**兜底源**（它也在产物里，必须英文）。
        # CI 里两次都能查（先派生再 gate），所以 CI 不会走到这里。
        # 「没跑 ≠ 通过」：这里查的是兜底源，不是跳过。
        fallback = os.path.join(REPO, "site", "catalogue.json")
        if os.path.exists(fallback):
            probs += check_catalogue_en(fallback)
            print("H4：用兜底源 site/catalogue.json（CI 会用派生件）")
        else:
            probs.append("H4 既无派生件也无兜底源 —— 未查不是通过")
    if html:
        probs += check_page_marks_deprecated(html, SPECS)

    # H6 在线探测（内容指纹判定）。CI 用 --online 显式开启；
    # 本地默认跳过并**明说**（跳过不是通过）。
    if "--online" in sys.argv:
        try:
            cdoc = json.load(open(os.path.join(REPO, "site", "channels.json"),
                                  encoding="utf-8"))
            chans = cdoc.get("channels") or []
        except (OSError, ValueError):
            chans = []
        # ★ 遍历源 = 产物清单（files.json），不是 HTML 里的链接。
        # 真实边界（shirone mail/027 §3 指出）：H6 原判据是「HTML 里的相对链接」，
        # 于是**产物里存在、但 index.html 不引用的文件永远不会被检查**。
        # 实测：`files.json` 与 `index.html` 本身就不在任何 href 里 —— 漏检。
        # 现在两份都查：H5 查 HTML 链接指向的（渲染完整性），
        # H6 查 files.json 列出的全部（分发完整性）。两者各自独立。
        # 从**每个通道**取它自己的 files.json —— 这才能发现"某通道产物清单缺件"。
        # 拿本地清单去查远端会漏掉"通道少发了文件"那一类。
        rel_by_chan = {}
        for ch in chans:
            b = (ch.get("base") or "").rstrip("/")
            code, body = _http(b + "/files.json")
            try:
                doc = json.loads(body.decode("utf-8")) if body else {}
                rel_by_chan[ch.get("name")] = doc.get("files") or []
            except (ValueError, UnicodeDecodeError):
                rel_by_chan[ch.get("name")] = []
        rel = sorted({x for v in rel_by_chan.values() for x in v})
        if not rel and html:
            # 本地无清单时回落到 HTML 链接（并明说覆盖面变窄）
            rel = sorted({m for m in re.findall(r'href="([^"#]+)"', html)
                          if not m.startswith(("http://", "https://", "mailto:", "#"))})
            print("H6：无 files.json 清单，回落到 HTML 链接（覆盖面变窄，不含未引用产物）")
        for k, v in rel_by_chan.items():
            print("H6 %s: files.json 列出 %d 个文件" % (k, len(v)))
        if CAT_ABS:
            h7 = check_catalogue_bases(CAT_ABS)
            probs += h7
            print("H7 catalogue base 可达性: %s" % ("全部可达" if not h7 else h7[0][:80]))
        if chans and rel:
            o_probs, stats = check_channels_online(chans, rel)
            probs += o_probs
            for k, v in stats.items():
                print("H6 %s: checked=%d dead=%d unreachable=%d"
                      % (k, v["checked"], v["dead"], v["unreachable"]))
    else:
        print("H6：未在线探测（需 --online）—— 跳过不是通过")

    for x in probs:
        print("· %s" % x, file=sys.stderr)
    if probs:
        print("站点语言闸门：%d 个问题" % len(probs), file=sys.stderr)
        return 1
    print("站点语言闸门：OK（HTML 全英文 / 废弃契约已标 / catalogue 英文 / 链接完整）")
    return 0


MODULE = module_meta("站点语言闸门",
                     "HTML 全英文 + 废弃契约必有横幅 + 页面同步",
                     selftest=False)


if __name__ == "__main__":
    sys.exit(main())
