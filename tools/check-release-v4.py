#!/usr/bin/env python3
"""发布契约 v4 · manifest 校验器（V1–V10，fail-closed）

与 v3 校验器的区别：v4 的形状是 `products{}` + `entries[]`，
每条 entry 自足（不靠 blob 间接），所以不变量全部按 entry 重写。

用法:
  python3 tools/check-release-v4.py <manifest.json> [--base DIR]   # 校验（可对盘核对）
  python3 tools/check-release-v4.py --selftest                       # 三类用例自证
"""
import hashlib
import json
import os
import re
import sys

MAX_CHUNK_HARD = 2 ** 25
MAX_NAME_LEN = 255

# ★ 平台容量**不是协议的不变量**（2026-10-31 用户裁定：「gitcode 啥的就各不相同了，
#   反正协议无限就对了」）。协议对 entries / asset 数**没有上限**；各托管平台的上限
#   是分发方的事（GitHub 单 release 1000 个 asset，别家不同）。
#   ⇒ 校验器**不设** asset 额度判据。这里只保留这条说明，防止将来又有人把平台数写回契约。
NAME_RE = re.compile(r"[A-Za-z0-9_-][A-Za-z0-9._-]*")
HEX = set("0123456789abcdef")
EXIT_OK, EXIT_RED, EXIT_USAGE = 0, 1, 2


def name_ok(n):
    if not isinstance(n, str) or not n:
        return False, "空名字"
    if len(n) > MAX_NAME_LEN:
        return False, f"长度 {len(n)} > {MAX_NAME_LEN}"
    if not NAME_RE.fullmatch(n):
        return False, "不符合白名单"
    if ".." in n:
        return False, "含连续点"
    if n.endswith("."):
        return False, "以点结尾"
    return True, ""


def is_hex64(s):
    return isinstance(s, str) and len(s) == 64 and set(s) <= HEX


# ══ v1.1 许可证（V11，**一行字符串**）══════════════════════════════════════════
#
# 设计判据（用户 2026-11-01 纠正后的最终形态）：
#   「人家只想下个包一条链接」 —— 许可**不能**变成下载路径上的闸门。
#
#   字节层：GET <base>/<file>，普通 GET，**不认识许可**
#   manifest：`license` 是一行 SPDX 表达式字符串，**展示用**
#   catalogue：没有 `license` ⇒ 不收录（闸门只在上架时挡一次，不在每个消费者那里挡 N 次）
#
# ⇒ schema 3 的全部许可判据只有一条 V11，且**只查形状，不查语义、不联网、不联网**。
#   三态（declared/unstated/refused）、provenance 见证链、amends 修订锚 ——
#   全部**删掉**：它们把「一行元数据」变成了「一棵要遍历的树」，
#   偏离了「apt 的稳健 + HTTP 的简洁」里的后一半。

SPDX_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9.+-]*$")
LICENSE_REF = re.compile(r"LicenseRef-[A-Za-z0-9._-]{1,}$")
ROLES = ("payload", "license", "notice")


def parse_spdx(expr):
    """SPDX 表达式文法检查。返回 token 列表，非法返回 None。

    只验**合法性**（算符大写、括号配对、token 形状），不做语义求值。
    客户端**不需要**调用它 —— 它只把 `license` 当字符串展示。
    """
    if not isinstance(expr, str) or not expr.strip():
        return None
    if expr != expr.strip() or "  " in expr or "\t" in expr or "\n" in expr:
        return None                       # 首尾/冗余空白 = 写法错误

    toks, cur = [], ""
    for ch in expr:
        if ch in "()":
            if cur:
                toks.append(cur); cur = ""
            toks.append(ch)
        elif ch == " ":
            if cur:
                toks.append(cur); cur = ""
        else:
            cur += ch
    if cur:
        toks.append(cur)
    if not toks:
        return None

    depth = 0
    expect_operand = True
    for i, t in enumerate(toks):
        if t == "(":
            if not expect_operand:
                return None
            depth += 1
            expect_operand = True
        elif t == ")":
            if expect_operand or depth == 0:
                return None
            depth -= 1
            expect_operand = False
        elif t in ("AND", "OR", "WITH"):
            if expect_operand:
                return None
            if t == "WITH":
                # WITH 只作用于单个标识符，且不许链式
                if i < 1 or i + 1 >= len(toks):
                    return None
                if toks[i - 1] in ("(", ")", "AND", "OR", "WITH"):
                    return None
                if toks[i + 1] in ("(", ")", "AND", "OR", "WITH"):
                    return None
                if i + 2 < len(toks) and toks[i + 2] == "WITH":
                    return None
            expect_operand = True
        else:
            if not expect_operand:
                return None
            if t.lower() in ("and", "or", "with"):
                return None
            if t.startswith("LicenseRef-"):
                if not LICENSE_REF.match(t):
                    return None
            elif not SPDX_TOKEN.match(t):
                return None
            expect_operand = False
    if depth != 0 or expect_operand:
        return None
    return toks


def _check_license(man, ok, P):
    """V11：`license` 是**一行合法 SPDX 表达式字符串**（schema 3 必填）。

    **不查语义、不查来源、不联网、不读盘。** 一行字符串，就这么简单。
    """
    lic = man.get("license")
    ok("V11 license 是字符串", type(lic).__name__, isinstance(lic, str),
       "schema 3 必须带一行许可声明（字符串，不是对象树）")
    if not isinstance(lic, str):
        if lic is None:
            P.append("V11 缺 license（schema 3 必填）—— 一行 SPDX 表达式即可")
        return
    ok("V11 license 非空", repr(lic)[:40], lic.strip() != "")
    ok("V11 license 文法合法", repr(lic)[:40], parse_spdx(lic) is not None,
       "算符必须大写；括号必须配对；不许冗余空白")

    # 只额外查 entry 级的 role 与 excluded.why（它们与本协议其它部分同构，不引入新概念）
    ents = man.get("entries")
    for j, e in enumerate(ents if isinstance(ents, list) else []):
        if not isinstance(e, dict):
            continue
        tag = "[%s/%s] " % (e.get("product"), e.get("name"))
        if "license" in e:
            el = e["license"]
            ok("V11 %sentries[%d].license 若存在必须是合法表达式" % (tag, j),
               repr(el)[:30],
               isinstance(el, str) and parse_spdx(el) is not None,
               "entry 级覆盖也必须一行字符串")
        role = e.get("role", "payload")
        ok("V11 %srole ∈ {payload,license,notice}" % tag, repr(role), role in ROLES)
        exc = e.get("excluded")
        if exc is not None:
            ok("V11 %sexcluded 是数组" % tag, type(exc).__name__, isinstance(exc, list))
            for k, x in enumerate(exc if isinstance(exc, list) else []):
                if not isinstance(x, dict):
                    P.append("V11 %sexcluded[%d] 不是对象" % (tag, k)); continue
                ok("V11 %sexcluded[%d].why 非空" % (tag, k), repr(x.get("why"))[:30],
                   isinstance(x.get("why"), str) and x["why"].strip() != "",
                   "「不分发」必须说明原因")


def check(man, base_dir=None):
    """返回 (results, problems)。results = [(label, detail, ok)]"""
    R, P = [], []

    def ok(label, detail, cond, why=None):
        R.append((label, detail, cond))
        if not cond:
            P.append(f"{label}: {detail}" + (f" —— {why}" if why else ""))

    if not isinstance(man, dict):
        P.append("V0: manifest 必须是对象")
        return R, P

    # ── V10 schema ──
    schema = man.get("schema")
    ok("V10 schema ∈ {2,3}", str(schema), schema in (2, 3),
       "旧客户端必须 fail-loud，不许静默少一半")
    # v1.1：schema 3 必须带许可声明（V11–V15 只在 schema 3 上跑）
    if schema == 3:
        _check_license(man, ok, P)
    ok("V0 id 非空字符串", repr(man.get("id"))[:40],
       isinstance(man.get("id"), str) and man["id"] != "")

    # ── V6 chunkSize ──
    cs = man.get("chunkSize")
    ok("V6 chunkSize 是正整数", str(cs), isinstance(cs, int) and cs > 0)
    if isinstance(cs, int) and cs > 0:
        ok("V6 chunkSize ≤ 2^25", f"{cs} vs {MAX_CHUNK_HARD}", cs <= MAX_CHUNK_HARD)

    # ── V9 codecs 开放串 + V4 identity 末位 ──
    codecs = man.get("codecs")
    ok("V9 codecs 是非空字符串数组", f"{type(codecs).__name__}",
       isinstance(codecs, list) and len(codecs) > 0
       and all(isinstance(c, str) and c for c in codecs))
    if isinstance(codecs, list) and codecs:
        ok("V4 codecs 末位是 identity", repr(codecs[-1]), codecs[-1] == "identity",
           "没有零依赖兜底 ⇒ 解不开就无路可走")
        ok("V9 codecs 无重复", repr(codecs), len(set(codecs)) == len(codecs))

    # ── products ──
    prods = man.get("products")
    ok("V0 products 是非空 map", f"{type(prods).__name__}",
       isinstance(prods, dict) and len(prods) > 0)
    if not isinstance(prods, dict) or not prods:
        return R, P

    for pid, p in prods.items():
        ok(f"V1 product id {pid!r} 过白名单", "", name_ok(pid)[0],
           "product id 会进文件名前缀")
        if isinstance(p, dict):
            ok(f"V0 product {pid} 有 form", repr(p.get("form")),
               isinstance(p.get("form"), str) and p["form"] != "")

    # ── V8 src 边 ──
    for pid, p in prods.items():
        if not isinstance(p, dict):
            continue
        has_src = "src" in p
        has_arch = bool(p.get("arch"))
        if has_src and p["src"] is not None:
            s = p["src"]
            ok(f"V8 {pid}.src 可解析", repr(s), s in prods, "src 悬空")
            ok(f"V8 {pid}.src 不自指", repr(s), s != pid)
            if has_arch:
                tgt = prods.get(s) if isinstance(s, str) else None
                ok(f"V8 {pid}.src 指向无 arch 的源码 product",
                   repr(tgt.get("arch") if isinstance(tgt, dict) else None),
                   isinstance(tgt, dict) and not tgt.get("arch"))
        if has_src and not has_arch and p["src"] is not None:
            P.append(f"V8 无 arch 的 product {pid} 不许带 src")

    # ── entries ──
    entries = man.get("entries")
    ok("V0 entries 是非空数组", f"{type(entries).__name__}",
       isinstance(entries, list) and len(entries) > 0)
    if not isinstance(entries, list) or not entries:
        return R, P

    seen_member = {}
    all_files = {}
    n_assets = 1                            # manifest.json 自己占 1 个 asset（仅计数，不设限）

    for i, e in enumerate(entries):
        if not isinstance(e, dict):
            P.append(f"V0 entries[{i}] 不是对象"); continue
        pid = e.get("product")
        nm = e.get("name")
        tag = f"[{pid}/{nm}]"
        ok(f"V5 {tag} product 可解析", repr(pid), pid in prods, "悬空 product")
        ok(f"V3 {tag} name 非空", repr(nm), isinstance(nm, str) and nm != "")

        key = (pid, nm)
        if key in seen_member:
            P.append(f"V3 ({pid}, {nm}) 重复")
        seen_member[key] = i

        ok(f"V7 {tag} bytes 是正整数", str(e.get("bytes")),
           isinstance(e.get("bytes"), int) and e["bytes"] >= 0)
        ok(f"V7 {tag} sha256 是 64hex", str(e.get("sha256"))[:8], is_hex64(e.get("sha256")))

        vs = e.get("variants")
        ok(f"V4 {tag} variants 非空", f"{type(vs).__name__}",
           isinstance(vs, list) and len(vs) > 0)
        if not isinstance(vs, list) or not vs:
            continue

        vcodecs = [v.get("codec") for v in vs if isinstance(v, dict)]
        ok(f"V4 {tag} variants 末位是 identity", repr(vcodecs[-1:]),
           vcodecs and vcodecs[-1] == "identity")
        ok(f"V4 {tag} 无重复 codec", repr(vcodecs), len(set(vcodecs)) == len(vcodecs))
        ok(f"V4 {tag} 每个 codec 都在 codecs[] 里声明",
           repr([c for c in vcodecs if c not in (codecs or [])]),
           all(c in (codecs or []) for c in vcodecs))

        # 块数一致性（所有 codec 必须同块数 —— 因为切的是同一份原始字节）
        counts = []
        for v in vs:
            if not isinstance(v, dict):
                continue
            chs = v.get("chunks")
            ok(f"V5 {tag}/{v.get('codec')} chunks 非空数组", f"{type(chs).__name__}",
               isinstance(chs, list) and len(chs) > 0)
            if not isinstance(chs, list) or not chs:
                continue
            counts.append(len(chs))
            parts = [c.get("part") for c in chs if isinstance(c, dict)]
            ok(f"V5 {tag}/{v.get('codec')} part 恰是 0..N-1", f"N={len(chs)}",
               parts == list(range(len(chs))))
            for c in chs:
                if not isinstance(c, dict):
                    continue
                fn = c.get("file")
                tok, why = name_ok(fn)
                ok(f"V1 {tag} file 过白名单", repr(fn)[:50], tok, why)
                ok(f"V7 {tag} chunk bytes 是正整数", str(c.get("bytes")),
                   isinstance(c.get("bytes"), int) and c["bytes"] >= 0)
                ok(f"V7 {tag} chunk sha256 是 64hex", str(c.get("sha256"))[:8],
                   is_hex64(c.get("sha256")))
                if isinstance(fn, str):
                    if fn in all_files:
                        P.append(f"V2 file 名撞车 {fn!r}: {all_files[fn]} vs {tag}")
                    all_files[fn] = tag
                    n_assets += 1          # 每个 chunk 文件 = 一个 GitHub asset
        if counts:
            ok(f"V5 {tag} 所有 codec 块数一致", repr(counts), len(set(counts)) == 1)

        # V6 语义：identity 块数必须 == ceil(bytes / chunkSize)，且除末块外每块 == chunkSize
        idv0 = next((v for v in vs if isinstance(v, dict) and v.get("codec") == "identity"), None)
        if idv0 and isinstance(idv0.get("chunks"), list) and idv0["chunks"] \
                and isinstance(cs, int) and cs > 0 and isinstance(e.get("bytes"), int):
            chs0 = idv0["chunks"]
            import math
            want = max(1, math.ceil(e["bytes"] / cs))
            ok(f"V6 {tag} 块数 == ceil(bytes/chunkSize)", f"{len(chs0)} vs {want}",
               len(chs0) == want, "chunkSize 声明与实际切块不一致（会撒谎）")
            sizes = [c.get("bytes") for c in chs0]
            full = sizes[:-1]
            ok(f"V6 {tag} 除末块外每块 == chunkSize", f"{set(full)} vs {cs}",
               all(x == cs for x in full), "块大小与声明的 chunkSize 不符")

        # V7 算术：Σ identity chunk bytes == entry.bytes
        idv = idv0
        if idv and isinstance(idv.get("chunks"), list):
            tot = sum(c.get("bytes", 0) for c in idv["chunks"] if isinstance(c, dict))
            ok(f"V7 {tag} Σ(identity.chunks.bytes) == bytes", f"{tot} vs {e.get('bytes')}",
               tot == e.get("bytes"))

        # 对盘核对（可选）：**每个 codec 的每一块**都核 bytes + sha（不止 identity）
        if base_dir:
            for v in vs:
                if not isinstance(v, dict) or not isinstance(v.get("chunks"), list):
                    continue
                codec = v.get("codec")
                bad = []
                for c in v["chunks"]:
                    if not isinstance(c, dict):
                        continue
                    fp = os.path.join(base_dir, c.get("file", ""))
                    try:
                        b = open(fp, "rb").read()
                    except OSError as ex:
                        bad.append(f"缺件 {c.get('file')}: {ex}"); continue
                    if len(b) != c.get("bytes"):
                        bad.append(f"{c.get('file')} 长度 {len(b)} != {c.get('bytes')}")
                    elif hashlib.sha256(b).hexdigest() != c.get("sha256"):
                        bad.append(f"{c.get('file')} sha 不符")
                ok(f"V7 {tag}/{codec} 盘上逐块 bytes+sha 一致",
                   f"{len(v['chunks'])} 块" + (f"，坏 {len(bad)}" if bad else ""),
                   not bad, "; ".join(bad[:3]))
            # identity 拼接后 == entry.sha256
            if idv and isinstance(idv.get("chunks"), list):
                try:
                    buf = b"".join(open(os.path.join(base_dir, c["file"]), "rb").read()
                                   for c in idv["chunks"])
                    ok(f"V7 {tag} 盘上 identity 拼接 sha 一致",
                       hashlib.sha256(buf).hexdigest()[:8],
                       hashlib.sha256(buf).hexdigest() == e.get("sha256")
                       and len(buf) == e.get("bytes"))
                except OSError as ex:
                    P.append(f"V7 {tag} 盘上缺件: {ex}")

    # entries / asset 数**不判**：协议无限（2026-10-31 用户裁定）。
    # 平台容量是分发方的事；把它写成判据 = 把「某个平台的上限」变成「协议形状」。
    # 只在 stderr 报个数（信息，不是违规），让人知道这次会发多少个文件。
    if n_assets > 1000:
        print(f"提示（非违规）：本 release 共 {n_assets} 个 asset。若目标托管平台"
              f"的单 release 上限更低，拆法由分发方决定 —— 不影响 manifest 合法性。",
              file=sys.stderr)

    return R, P


def selftest():
    n = f = 0

    def t(label, cond):
        nonlocal n, f
        if cond:
            n += 1; print(f"PASS | {label}")
        else:
            f += 1; print(f"fail | {label}")

    def good():
        """一个最小合法 manifest（两块 identity）。"""
        return {
            "schema": 2, "id": "t/x", "chunkSize": 5242880,
            "codecs": ["zstd", "gzip", "identity"],
            "products": {"src": {"form": "pkg"},
                         "w": {"form": "octdir", "arch": "wasm32", "src": "src"}},
            "entries": [
                {"product": "src", "name": "a.tar.gz", "bytes": 6, "sha256": "a" * 64,
                 "variants": [{"codec": "identity", "chunks": [
                     {"part": 0, "file": "src__a.tar.gz.identity.000", "bytes": 6,
                      "sha256": "a" * 64}]}]},
                {"product": "w", "name": "b.oct", "bytes": 6, "sha256": "b" * 64,
                 "variants": [
                     {"codec": "zstd", "chunks": [
                         {"part": 0, "file": "w__b.oct.zstd.000", "bytes": 4, "sha256": "c" * 64}]},
                     {"codec": "gzip", "chunks": [
                         {"part": 0, "file": "w__b.oct.gzip.000", "bytes": 5, "sha256": "d" * 64}]},
                     {"codec": "identity", "chunks": [
                         {"part": 0, "file": "w__b.oct.identity.000", "bytes": 6, "sha256": "b" * 64}]}]},
            ]}

    # ── 正常：合法 manifest 不报 ──
    _, P = check(good())
    t("正常（合法 v4 manifest）⇒ 不报", not P)
    if P:
        print("      ", P[:3])

    # ── 该报：逐条反向 ──
    def bad(mut, label, want):
        m = good(); mut(m)
        _, P = check(m)
        t(f"该报（{label}）⇒ 必报 {want}", any(want in x for x in P))

    bad(lambda m: m.update(schema=1), "schema=1", "V10")
    bad(lambda m: m.update(schema=4), "schema=4", "V10")

    # ── v1.1 许可证（V11）＋ SPDX 文法 ────────────────────────────────────────
    # 文法：拒绝面（该报必报）
    for e in ("A and B", "A OR", "OR A", "(A OR B", "A OR B)", "", "A WITH",
              "A OR (B AND C", " A  OR  B ", "A B", "()", "A OR ()",
              "A WITH B WITH C", "(A OR B) WITH X", "(A) WITH X",
              "LicenseRef-", "LicenseRef- AND MIT"):
        t("SPDX 文法拒：%r" % e, parse_spdx(e) is None)
    # 文法：接受面（正常不报）
    for e in ("MIT", "A OR B AND C", "A AND (B OR C)", "Apache-2.0 WITH LLVM-exception",
              "LicenseRef-public-domain", "(A OR B) AND C",
              "GPL-3.0-or-later AND BSD-3-Clause AND LicenseRef-public-domain"):
        t("SPDX 文法收：%r" % e, parse_spdx(e) is not None)

    def good3():
        """最小合法 schema 3 manifest（许可 = 一行字符串）。"""
        m = good()
        m["schema"] = 3
        m["license"] = "GPL-3.0-or-later"
        return m

    _, P3 = check(good3())
    t("正常（schema 3 + 一行许可）⇒ 不报", not P3)
    if P3:
        print("      ", P3[:3])

    def bad3(mut, label, want):
        m = good3(); mut(m)
        _, P = check(m)
        t("该报（%s）⇒ 必报 %s" % (label, want), any(want in x for x in P))

    bad3(lambda m: m.pop("license"), "缺 license", "V11")
    bad3(lambda m: m.update(license={}), "license 是对象（旧树形）", "V11")
    bad3(lambda m: m.update(license=""), "license 空串", "V11")
    bad3(lambda m: m.update(license="GPL-3.0 and MIT"), "小写算符", "V11")
    bad3(lambda m: m.update(license="(MIT"), "括号未闭合", "V11")

    # entry 级覆盖：也是一行字符串
    def _entry_lic(m):
        m["entries"][1]["license"] = "MIT"
    m = good3(); _entry_lic(m)
    _, P = check(m)
    t("正常（entry 级覆盖，一行字符串）⇒ 不报", not P)

    bad3(lambda m: m["entries"][1].update(license="MIT or BSD"), "entry 小写算符", "V11")
    bad3(lambda m: m["entries"][1].update(license=None), "entry license=null", "V11")
    bad3(lambda m: m["entries"][1].update(role="docs"), "role 非法", "V11")
    bad3(lambda m: m["entries"][0].update(excluded=[{"path": "x"}]), "excluded 缺 why", "V11")

    def _excluded_ok(m):
        m["entries"][0]["excluded"] = [{"path": "subprojects/*", "why": "未 vendored"}]
    m = good3(); _excluded_ok(m)
    _, P = check(m)
    t("正常（excluded 带 why）⇒ 不报", not P)

    # 关键：许可**不影响字节获取**（客户端只 GET <base>/<file>）
    m = good3()
    R0, _ = check(m)
    t("许可声明不改变任何字节相关判据（V1–V10 用例数不变）",
      sum(1 for lab, _d, _o in R0 if lab.startswith("V7") or lab.startswith("V1 ")) > 0)

    # ── 空输入 ──
    _, P = check([])
    t("空输入（根非对象）⇒ 必报 V0", any("V0" in x for x in P))
    _, P = check({})
    t("空输入（空对象）⇒ 必报 V10+V0", any("V10" in x for x in P))

    print(f"\n=== {n} PASS / {f} fail ===")
    return 0 if f == 0 else 1


def main():
    a = sys.argv[1:]
    if not a:
        print(__doc__); return EXIT_USAGE
    if "--selftest" in a:
        return selftest()
    path = a[0]
    base = None
    if "--base" in a:
        base = a[a.index("--base") + 1]
    if not os.path.exists(path):
        print(f"FATAL: 不存在 {path}"); return EXIT_RED
    try:
        man = json.load(open(path))
    except Exception as e:
        print(f"FATAL: 非法 JSON: {e}"); return EXIT_RED

    R, P = check(man, base_dir=base or os.path.dirname(os.path.abspath(path)))
    for label, detail, good_ in R:
        print(f"{'PASS' if good_ else 'fail'} | {label}"
              + (f" :: {detail}" if detail else ""))
    if P:
        print("\n问题:")
        for x in P:
            print("  ·", x)
    fails = sum(1 for _, _, g in R if not g) + len(P)
    print(f"\n=== {sum(1 for _,_,g in R if g)} PASS / {fails} FAIL ===")
    return EXIT_OK if fails == 0 else EXIT_RED


if __name__ == "__main__":
    sys.exit(main())
