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
    ok("V10 schema == 2", str(man.get("schema")), man.get("schema") == 2,
       "旧客户端必须 fail-loud，不许静默少一半")
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
    bad(lambda m: m.update(chunkSize=0), "chunkSize=0", "V6")
    bad(lambda m: m.update(chunkSize=2 ** 26), "chunkSize>2^25", "V6")
    bad(lambda m: m["codecs"].pop(), "codecs 末位非 identity", "V4")
    bad(lambda m: m.update(products={}), "products 空", "V0")
    bad(lambda m: m.update(entries=[]), "entries 空", "V0")
    bad(lambda m: m["entries"][1]["variants"].pop(), "variants 末位非 identity", "V4")
    bad(lambda m: m["entries"][0]["variants"][0]["chunks"][0].update(file="bad name.bin"),
        "file 含空格", "V1")
    bad(lambda m: m["entries"][0]["variants"][0]["chunks"][0].update(file=".dot.bin"),
        "file 前导点", "V1")
    bad(lambda m: m["entries"][0]["variants"][0]["chunks"][0].update(file="a..b"),
        "file 连续点", "V1")
    bad(lambda m: m["entries"][1]["variants"][1]["chunks"][0].update(
        file=m["entries"][1]["variants"][0]["chunks"][0]["file"]), "file 撞车", "V2")
    bad(lambda m: m["entries"][0].update(product="nope"), "悬空 product", "V5")
    bad(lambda m: m["entries"].append(dict(m["entries"][0])), "(product,name) 重复", "V3")
    bad(lambda m: m["entries"][0]["variants"][0]["chunks"][0].update(bytes=999),
        "Σidentity != bytes", "V7")
    bad(lambda m: m["entries"][0].update(sha256="zz"), "sha 非 64hex", "V7")
    bad(lambda m: m["products"]["w"].update(src="nope"), "src 悬空", "V8")
    bad(lambda m: m["products"]["w"].update(src="w"), "src 自指", "V8")
    bad(lambda m: m["products"]["src"].update(src="w"), "无 arch 带 src", "V8")
    bad(lambda m: m["entries"][1]["variants"][0]["chunks"].append(
        {"part": 0, "file": "w__b.oct.zstd.001", "bytes": 1, "sha256": "e" * 64}),
        "part 不连续", "V5")
    bad(lambda m: m["entries"][1]["variants"][1]["chunks"].append(
        {"part": 1, "file": "w__b.oct.gzip.001", "bytes": 1, "sha256": "f" * 64}),
        "codec 块数不一致", "V5")
    bad(lambda m: m["entries"][1]["variants"][0].update(codec="xz"),
        "codec 未在 codecs 声明", "V4")

    # ★ V6 语义：chunkSize 撒谎（声明 1MiB 但 identity 块是 6B 单块 ⇒ 块数应为 1，改 chunkSize 制造不符）
    def lie_chunk(m):
        m["chunkSize"] = 1          # 声明 1 字节 ⇒ 期望 6 块，实际 1 块
    bad(lie_chunk, "chunkSize 撒谎（块数与 ceil(bytes/cs) 不符）", "V6")

    # ★ entry/asset 数**无上限**（2026-10-31 用户裁定「协议无限」）。
    # 反证：条目数远超任何平台容量的 manifest 也必须**合法**（不因数量拒收）。
    m_many = good()
    tmpl = m_many["entries"][0]
    for k in range(1200):
        e = {"product": "src", "name": f"m{k:04d}.bin", "bytes": 6, "sha256": "a" * 64,
             "variants": [{"codec": "identity", "chunks": [
                 {"part": 0, "file": f"src__m{k:04d}.bin.identity.000",
                  "bytes": 6, "sha256": "a" * 64}]}]}
        m_many["entries"].append(e)
    _, P = check(m_many)
    t(f"{len(m_many['entries'])} 条 entry / 1202 个 asset ⇒ 仍合法"
      "（协议不设上限）", not P)
    if P:
        print("      ", P[:3])

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
