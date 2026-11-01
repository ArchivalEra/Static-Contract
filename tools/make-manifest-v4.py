#!/usr/bin/env python3
"""发布契约 v4 · manifest 生成器

v4 相对 v3 的核心变化：
  1. 名字字符白名单（实测 GitHub 静默改写面 → 只允许不会被改写的字符）
  2. products{} 分组解决「跨 arch 同名不同字节」（optim 5/5 撞车，实测）
  3. 每条 entry 自足（apt 稳健性：不靠 blob 间接，重复写 sha 换"单条可用"）
  4. file 字段 == asset 名（白名单保证 GitHub 逐字保留 ⇒ 不需要映射表）

用法:
  python3 tools/make-manifest-v4.py --out DIR --id ID \
      --product src:pkg::/path/to/src.tar.gz \
      --product wasm32:octdir:wasm32:src:/path/to/octdir \
      [--chunk-size 5242880]
  python3 tools/make-manifest-v4.py --selftest

--product 语法（冒号分隔，从右往左剥）:
  pid:form[:arch][:src]:path
  · path 若含 ':'，用 `--`（双横线）代替分隔符：`pid:form:arch:src--/a:b/c`
  · path 是目录时**递归**收集（v4 支持站点树）
  · 两个无 arch 的 product 可以各有同名文件 —— 名字带 product 前缀，不撞车
"""
import argparse
import gzip
import hashlib
import json
import os
import re
import sys
import tempfile

DEFAULT_CHUNK = 5 * 1024 * 1024
MAX_CHUNK_HARD = 2 ** 25          # fzstd backreference 上限
MAX_NAME_LEN = 255                # GitHub asset 名硬上限（实测：256 报 422）
NAME_BUDGET = 64                  # 本协议推荐预算（spec §1；超了只提示不拦）

# ★ 平台容量**不是协议的一部分**（2026-10-31 用户裁定：「gitcode 啥的就各不相同了，
#   反正协议无限就对了」）。协议对 entry 数 / asset 数**没有任何上限**。
#   实测记录（只为将来有人问「为什么发不上去」时有个线索，**不构成判据**）：
#   GitHub 单 release 上限 1000 个 asset，错误字段 `file_count`。
#   ⇒ 换平台（GitCode / 对象存储 / …）这个数不同，所以**不许写进 manifest 不变量**。

# ★ 实测得到的白名单（GitHub 逐字保留）：
#   OK:      a.b_c-D9.zstd.000 / UPPER.Mixed.Case.000 / under_score / hy-phen / -leading
#   CHANGED: dots...many.000 → dots.many.000（连续点折叠）
#            .leading-dot    → default.leading-dot
#            trailing-dot.   → default.trailing-dot
#            空格/%(/)/非 ASCII 全部被改写或删除
#   判据：`re.fullmatch`（不是 match）——避免 '$' 前置换行被放过
NAME_RE = re.compile(r"[A-Za-z0-9_-][A-Za-z0-9._-]*")

PRECOMPRESSED = (".zip", ".gz", ".br", ".zst", ".xz", ".whl", ".7z", ".rar", ".tgz",
                 ".png", ".jpg", ".jpeg", ".gif", ".webp", ".avif", ".mp4", ".webm",
                 ".woff2", ".woff", ".ttf", ".otf", ".eot", ".mp3", ".ogg")


def sha256(b):
    return hashlib.sha256(b).hexdigest()


def name_ok(n):
    """名字能否通过 GitHub 逐字保留。返回 (ok, reason)。"""
    if not isinstance(n, str) or not n:
        return False, "空名字"
    if len(n) > MAX_NAME_LEN:
        return False, f"长度 {len(n)} > {MAX_NAME_LEN}"
    # fullmatch：防 'a\\n' 因为 '$' 前置换行而被 match 放过
    if not NAME_RE.fullmatch(n):
        return False, "不符合白名单 ^[A-Za-z0-9_-][A-Za-z0-9._-]*$（含会被改写的字符）"
    if ".." in n:
        return False, "含连续点（GitHub 会折叠成单点）"
    if n.endswith("."):
        return False, "以点结尾（GitHub 会加 default. 前缀）"
    return True, ""


def compress_blocks(blocks, codec):
    """每块**独立**压缩（V6：块必须独立，跨块 backreference 会让 fzstd 解不出）。

    gzip 固定 mtime=0 ⇒ 同输入必得同字节（可复现；否则 manifest 的 sha 每次变）。
    """
    if codec == "gzip":
        out = []
        for b in blocks:
            buf = gzip.compress(b, compresslevel=9, mtime=0)
            out.append(buf)
        return out
    if codec == "zstd":
        import zstandard as zstd
        c = zstd.ZstdCompressor(level=19)
        return [c.compress(b) for b in blocks]
    if codec == "identity":
        return list(blocks)
    raise ValueError(codec)


def build_variants(raw, codecs, outdir, name_ctx, chunk, written=None):
    """为一个载荷产出 variants[]（每块独立压缩，按 chunk 切）。

    name_ctx = 名字前缀（含 product 前缀，不含 codec/序号）
    """
    if chunk <= 0:
        raise SystemExit(f"FATAL: chunkSize={chunk} 必须 > 0")
    if chunk > MAX_CHUNK_HARD:
        raise SystemExit(f"FATAL: chunkSize={chunk} > 2^25（fzstd 边界）")
    blocks = [raw[i:i + chunk] for i in range(0, len(raw), chunk)]
    if not blocks:                      # 空文件：仍然要有 identity 兜底
        blocks = [b""]
    variants = []
    for codec in codecs:
        parts = compress_blocks(blocks, codec)
        chunks = []
        for i, p in enumerate(parts):
            fn = f"{name_ctx}.{codec}.{i:03d}"
            ok, why = name_ok(fn)
            if not ok:
                raise SystemExit(f"FATAL: 名字不合法 {fn!r}: {why}")
            with open(os.path.join(outdir, fn), "wb") as f:
                f.write(p)
            if written is not None:
                written.append(fn)
            chunks.append({"part": i, "file": fn, "bytes": len(p), "sha256": sha256(p)})
        variants.append({"codec": codec, "chunks": chunks})
    return variants, len(blocks)


def _collect(path):
    """文件 → [path]；目录 → 递归收集所有文件（保留相对路径用于去重判据）。"""
    if os.path.isfile(path):
        return [(os.path.basename(path), path)]
    if os.path.isdir(path):
        out = []
        for root, _dirs, files in os.walk(path):
            for fn in sorted(files):
                full = os.path.join(root, fn)
                rel = os.path.relpath(full, path)
                out.append((rel, full))
        if not out:
            raise SystemExit(f"FATAL: 目录为空 {path!r}")
        return out
    raise SystemExit(f"FATAL: 路径不存在 {path!r}")


def _flatten(rel):
    """相对路径 → 白名单扁平名（'/' 与多余 '.' 都换掉）。"""
    return rel.replace(os.sep, "__").replace("/", "__")


def make(spec, outdir, relid, codecs=("zstd", "gzip", "identity"), chunk=DEFAULT_CHUNK):
    """spec = [ {product, form, arch?, src?, files:[path,...]} ]"""
    if not spec:
        raise SystemExit("FATAL: 没有 product")
    if chunk <= 0:
        raise SystemExit(f"FATAL: chunkSize={chunk} 必须 > 0")
    if chunk > MAX_CHUNK_HARD:
        raise SystemExit(f"FATAL: chunkSize={chunk} > 2^25（fzstd 边界）")

    # ── 先验证 spec 自身（V3/V8 的 fail-closed）──────────────────────────
    pids = [p["product"] for p in spec]
    dup = {x for x in pids if pids.count(x) > 1}
    if dup:
        raise SystemExit(f"FATAL: product id 重复 {sorted(dup)}（V5）")
    for p in spec:
        pid = p["product"]
        ok, why = name_ok(pid)
        if not ok:
            raise SystemExit(f"FATAL: product id {pid!r} 不能进文件名: {why}")
        if "src" in p and p["src"] is not None:
            if p["src"] not in pids:
                raise SystemExit(f"FATAL: {pid}.src={p['src']!r} 悬空（V8：同 release 内无此 product）")
            if p["src"] == pid:
                raise SystemExit(f"FATAL: {pid}.src 自指（V8）")
            if "arch" not in p or not p.get("arch"):
                raise SystemExit(f"FATAL: 无 arch 的 product {pid} 不许带 src（V8）")
            # src 必须指向**无 arch** 的 product
            tgt = next(x for x in spec if x["product"] == p["src"])
            if tgt.get("arch"):
                raise SystemExit(f"FATAL: {pid}.src 指向带 arch 的 {p['src']}（V8：src 必须是源码 product）")

    os.makedirs(outdir, exist_ok=True)

    # 记已写文件，失败时清掉（不留半个 release 目录）
    written = []

    products = {}
    entries = []
    seen_files = {}                      # file 名 → (product, name)，用于 V2 全局唯一
    seen_member = set()                  # (product, name)，用于 V3

    try:
        return _make_inner(spec, outdir, relid, codecs, chunk, written)
    except BaseException:
        for fn in written:                     # 失败即清理，不留半个 release
            try:
                os.remove(os.path.join(outdir, fn))
            except OSError:
                pass
        mf = os.path.join(outdir, "manifest.json")
        if os.path.exists(mf):
            try:
                os.remove(mf)
            except OSError:
                pass
        raise


def _count_assets(spec, codecs, chunk):
    """算出本 release 会产出多少个 asset（= 分片总数 + 1 manifest）。

    **只报数、不设限**。协议对 entry 数 / asset 数没有上限（2026-10-31 用户裁定）；
    各托管平台各有各的容量，那是**分发方的事**，不是协议的事。
    块数只取决于文件大小（`ceil(size/chunk)`，下限 1），不读字节就能算。
    """
    n = 1                                     # manifest.json 自己占 1 个 asset
    n_entries = 0
    for p in spec:
        for rel, fp in _collect_many(p["files"]):
            base = _flatten(rel)
            is_pre = base.lower().endswith(PRECOMPRESSED)
            n_codecs = 1 if is_pre else len(codecs)
            size = os.path.getsize(fp)
            n += max(1, -(-size // chunk)) * n_codecs   # ceil，与 build_variants 同口径
            n_entries += 1
    return n, n_entries


def _make_inner(spec, outdir, relid, codecs, chunk, written):
    """真正干活的部分；失败由外层清场。"""
    products = {}
    entries = []
    seen_files = {}
    seen_member = set()

    # 报数（不设限）：让生产者事先知道这次会产出多少个 asset。
    n_assets, n_entries = _count_assets(spec, codecs, chunk)
    print(f"  预计 {n_entries} 条 entry / {n_assets} 个 asset（分片 + 1 manifest）",
          file=sys.stderr)

    for p in spec:
        pid = p["product"]
        products[pid] = {"form": p["form"]}
        if p.get("arch"):
            products[pid]["arch"] = p["arch"]
        if "src" in p:
            products[pid]["src"] = p["src"]

        for rel, fp in _collect_many(p["files"]):
            raw = open(fp, "rb").read()
            base = _flatten(rel)
            is_pre = base.lower().endswith(PRECOMPRESSED)
            use = ("identity",) if is_pre else tuple(codecs)

            # ★ 名字前缀含 product id —— 修「跨 product 同名撞车」
            name_ctx = f"{pid}__{base}"
            probe = f"{name_ctx}.x.000"
            ok, why = name_ok(probe)
            if not ok:
                raise SystemExit(f"FATAL: {pid}/{base} 派生名不合法: {why}"
                                 f"（载荷名太长或含禁用字符，请缩短）")
            if len(probe) > NAME_BUDGET:
                print(f"  ⚠️  名字 {probe!r} = {len(probe)} 字符 > 推荐预算 {NAME_BUDGET}"
                      f"（不拦，但贴 255 上限时人已读不懂；建议缩短 {pid} 或载荷名）",
                      file=sys.stderr)

            variants, nchunks = build_variants(raw, use, outdir, name_ctx, chunk, written)

            key = (pid, base)
            if key in seen_member:
                raise SystemExit(f"FATAL: ({pid}, {base}) 重复（V3）")
            seen_member.add(key)

            for v in variants:
                for c in v["chunks"]:
                    if c["file"] in seen_files:
                        raise SystemExit(
                            f"FATAL: file 名撞车 {c['file']!r}："
                            f"{seen_files[c['file']]} vs {(pid, base)}（V2）")
                    seen_files[c["file"]] = (pid, base)

            entries.append({
                "product": pid, "name": base,
                "bytes": len(raw), "sha256": sha256(raw),
                "variants": variants,
            })
            print(f"  {pid}/{base}: {len(raw):,} B → {nchunks} 块 × {len(variants)} 编码"
                  + ("  [已压格式只出 identity]" if is_pre else ""))

    if not entries:
        raise SystemExit("FATAL: 没有条目")

    man = {"schema": 2, "id": relid, "chunkSize": chunk,
           "codecs": list(codecs),
           "products": products, "entries": entries}
    with open(os.path.join(outdir, "manifest.json"), "w") as f:
        json.dump(man, f, indent=1)
    return man


def _collect_many(paths):
    """把 product 的 files 列表展开成 [(rel, fullpath)]；跨多个根时用序号前缀防重名。"""
    out = []
    for k, p in enumerate(paths):
        got = _collect(p)
        if len(paths) > 1:
            out.extend((f"{k:02d}__{rel}", full) for rel, full in got)
        else:
            out.extend(got)
    return out


# ────────────────────────────── selftest ──────────────────────────────
def selftest():
    n = f = 0

    def t(label, cond):
        nonlocal n, f
        if cond:
            n += 1; print(f"PASS | {label}")
        else:
            f += 1; print(f"fail | {label}")

    def must_fail(label, fn):
        try:
            fn()
            t(label, False)
        except SystemExit:
            t(label, True)

    # ── A. 白名单：实测 GitHub 改写案例必须全拒（7 条反向）──
    for nm, why in [
        ("dots...many.000", "连续点→折叠"),
        (".leading-dot", "前导点→加 default."),
        ("trailing-dot.", "尾点→加 default."),
        ("sp ace.bin", "空格→点"),
        ("pct%41.bin", "%→点"),
        ("paren(1).bin", "括号删"),
        ("a中b.bin", "非 ASCII 删"),
    ]:
        t(f"★ 白名单拒（{why}）{nm}", not name_ok(nm)[0])
    t("★ 白名单拒（斜杠）a/b.bin", not name_ok("a/b.bin")[0])
    t("★ 白名单拒（换行尾）'a\\n'", not name_ok("a\n")[0])

    # ── B. 白名单：实测 OK 的必须全过（3 条正例）──
    for nm in ("a.b_c-D9.zstd.000", "UPPER.Mixed.Case.000", "-leading-hyphen"):
        t(f"白名单过 {nm}", name_ok(nm)[0])

    with tempfile.TemporaryDirectory() as d:
        # ── C. 正常路径：跨 arch 同名不同字节（复刻 optim 真形状）──
        for arch, size in (("wasm32", 11 * 1024 * 1024), ("wasm64", 12 * 1024 * 1024)):
            sub = os.path.join(d, arch); os.makedirs(sub)
            open(os.path.join(sub, "numgradient.oct"), "wb").write(os.urandom(size))
        src = os.path.join(d, "optim-1.6.3.tar.gz")
        open(src, "wb").write(os.urandom(300 * 1024))

        out = os.path.join(d, "out")
        man = make([
            {"product": "src", "form": "pkg", "files": [src]},
            {"product": "wasm32", "form": "octdir", "arch": "wasm32", "src": "src",
             "files": [os.path.join(d, "wasm32", "numgradient.oct")]},
            {"product": "wasm64", "form": "octdir", "arch": "wasm64", "src": "src",
             "files": [os.path.join(d, "wasm64", "numgradient.oct")]},
        ], out, "test/optim-1.6.3", codecs=("gzip", "identity"), chunk=5 * 1024 * 1024)

        t("v4：products 3 个", len(man["products"]) == 3)
        t("v4：src 边存在", man["products"]["wasm32"].get("src") == "src")
        t("★ 跨 arch 同名 = 2 条独立 entry（不塌陷）",
          sum(1 for e in man["entries"] if e["name"] == "numgradient.oct") == 2)
        t("★ 两条 entry sha 不同", len({e["sha256"] for e in man["entries"]
                                        if e["name"] == "numgradient.oct"}) == 2)
        t("v4：已压格式只 identity",
          [v["codec"] for v in next(e for e in man["entries"]
                                    if e["name"].endswith(".tar.gz"))["variants"]] == ["identity"])
        t("★ 11MiB → 3 块", len(man["entries"][1]["variants"][0]["chunks"]) == 3)
        t("★ 所有 file 名过白名单",
          all(name_ok(c["file"])[0] for e in man["entries"]
              for v in e["variants"] for c in v["chunks"]))
        allf = [c["file"] for e in man["entries"] for v in e["variants"] for c in v["chunks"]]
        t("★ 所有 file 名全局唯一", len(set(allf)) == len(allf))
        # ★ entry.sha 必须等于盘上字节（修「manifest 撒谎」）
        disk_ok = True
        for e in man["entries"]:
            idv = next(v for v in e["variants"] if v["codec"] == "identity")
            buf = b"".join(open(os.path.join(out, c["file"]), "rb").read()
                           for c in idv["chunks"])
            if sha256(buf) != e["sha256"] or len(buf) != e["bytes"]:
                disk_ok = False
        t("★ 每条 entry.sha 与盘上 identity 拼接逐字一致", disk_ok)
        # 块能独立解
        import gzip as gz
        c0 = man["entries"][1]["variants"][0]["chunks"][0]
        t("★ 块能独立解压（gzip，每块独立）",
          gz.decompress(open(os.path.join(out, c0["file"]), "rb").read())
          == open(os.path.join(d, "wasm32", "numgradient.oct"), "rb").read()[:5 * 1024 * 1024])

        # ── D. 该报的必须报（每条一个反向用例）──
        must_fail("★ chunkSize > 2^25 必拒",
                  lambda: make([{"product": "x", "form": "file", "files": [src]}],
                               os.path.join(d, "b1"), "t/x", chunk=2 ** 26))
        must_fail("★ chunkSize = 0 必拒",
                  lambda: make([{"product": "x", "form": "file", "files": [src]}],
                               os.path.join(d, "b2"), "t/x", chunk=0))
        must_fail("★ chunkSize 负数必拒",
                  lambda: make([{"product": "x", "form": "file", "files": [src]}],
                               os.path.join(d, "b3"), "t/x", chunk=-5))

        # ★ 两个无 arch product 同名文件：不许静默覆盖
        for k, sz in (("p1", 1000), ("p2", 2000)):
            sub = os.path.join(d, k); os.makedirs(sub, exist_ok=True)
            open(os.path.join(sub, "data.bin"), "wb").write(bytes([65 + int(k[1])]) * sz)
        m2 = make([
            {"product": "p1", "form": "file", "files": [os.path.join(d, "p1", "data.bin")]},
            {"product": "p2", "form": "file", "files": [os.path.join(d, "p2", "data.bin")]},
        ], os.path.join(d, "o-dup"), "t/dup", codecs=("identity",), chunk=1024 * 1024)
        t("★ 两个无 arch 的同名文件 → 2 条 entry 且 file 名不同",
          len(m2["entries"]) == 2
          and m2["entries"][0]["variants"][0]["chunks"][0]["file"]
          != m2["entries"][1]["variants"][0]["chunks"][0]["file"])
        t("★ 两条 entry 的 sha 与各自盘上字节一致",
          all(sha256(open(os.path.join(d, "o-dup",
                                       e["variants"][0]["chunks"][0]["file"]),
                          "rb").read()) == e["sha256"]
              for e in m2["entries"]))

        # ★ src 悬空 / src 自指 / src 指向带 arch 的 / 无 arch 带 src —— 四条必拒
        must_fail("★ src 悬空必拒（AGPL 强制）",
                  lambda: make([{"product": "w", "form": "octdir", "arch": "wasm32",
                                 "src": "nope", "files": [src]}],
                               os.path.join(d, "b4"), "t/x"))
        must_fail("★ src 自指必拒",
                  lambda: make([{"product": "w", "form": "octdir", "arch": "wasm32",
                                 "src": "w", "files": [src]}],
                               os.path.join(d, "b5"), "t/x"))
        must_fail("★ 无 arch 的 product 带 src 必拒",
                  lambda: make([{"product": "s", "form": "pkg", "src": "s2",
                                 "files": [src]},
                                {"product": "s2", "form": "pkg", "files": [src]}],
                               os.path.join(d, "b6"), "t/x"))
        must_fail("★ product id 重复必拒",
                  lambda: make([{"product": "p", "form": "file", "files": [src]},
                                {"product": "p", "form": "file", "files": [src]}],
                               os.path.join(d, "b7"), "t/x"))

        # ── E. chunkSize 不再撒谎（参数必须真的生效）──
        big = os.path.join(d, "big.bin")
        open(big, "wb").write(os.urandom(3 * 1024 * 1024))
        m3 = make([{"product": "b", "form": "file", "files": [big]}],
                  os.path.join(d, "o-chunk"), "t/chunk",
                  codecs=("identity",), chunk=1024 * 1024)
        cs = m3["entries"][0]["variants"][0]["chunks"]
        t("★ chunkSize 参数真生效（1MiB → 3 块，每块 ≤1MiB）",
          m3["chunkSize"] == 1024 * 1024 and len(cs) == 3
          and max(c["bytes"] for c in cs) <= 1024 * 1024)

        # ── F. 递归目录（覆盖站点树）──
        tree = os.path.join(d, "site")
        os.makedirs(os.path.join(tree, "a", "b"))
        open(os.path.join(tree, "index.html"), "wb").write(b"<html></html>")
        open(os.path.join(tree, "a", "b", "deep.css"), "wb").write(b"body{}")
        # 用**默认三编码**（不是 identity-only）才验得出「html/css 不被误判成已压格式」
        m4 = make([{"product": "site", "form": "tree", "files": [tree]}],
                  os.path.join(d, "o-tree"), "t/tree")
        names = {e["name"] for e in m4["entries"]}
        t("★ 递归收集子目录文件（2 条 entry）", len(m4["entries"]) == 2)
        t("★ 子目录路径被扁平化（含 __ 且无 /）",
          any("a__b__deep.css" in n for n in names) and not any("/" in n for n in names))
        # ★ 真断言（原为 `or True` 恒真 = 假闸门）：html/css 必须出 3 编码
        idx = next(e for e in m4["entries"] if e["name"] == "index.html")
        t("★ html 走全三编码（未被误当已压格式）",
          [v["codec"] for v in idx["variants"]] == list(m4["codecs"]))
        css = next(e for e in m4["entries"] if e["name"].endswith(".css"))
        t("★ css 走全三编码", [v["codec"] for v in css["variants"]] == list(m4["codecs"]))
        # ★ 已压格式（woff2/avif）必须只出 identity
        woff = os.path.join(tree, "f.woff2")
        open(woff, "wb").write(os.urandom(2000))
        m5 = make([{"product": "f", "form": "file", "files": [woff]}],
                  os.path.join(d, "o-font"), "t/f")
        t("★ 字体 woff2 只出 identity（已压格式免压）",
          [v["codec"] for v in m5["entries"][0]["variants"]] == ["identity"])

        # ── G. 可复现：同输入两次生成，字节逐字相同（gzip mtime=0）──
        try:
            import subprocess
        except Exception:
            subprocess = None
        o1 = os.path.join(d, "r1"); o2 = os.path.join(d, "r2")
        mk = lambda o: make([{"product": "r", "form": "file", "files": [big]}],
                            o, "t/r", codecs=("gzip",), chunk=1024 * 1024)
        m_r1 = mk(o1); m_r2 = mk(o2)
        t("★ gzip 可复现（两次同输入 → 同 sha 序列）",
          [c["sha256"] for v in m_r1["entries"][0]["variants"] for c in v["chunks"]]
          == [c["sha256"] for v in m_r2["entries"][0]["variants"] for c in v["chunks"]])

        # ── H. 空输入必拒 ──
        must_fail("★ 空输入（无 product）必拒",
                  lambda: make([], os.path.join(d, "b8"), "t/e"))
        must_fail("★ 目录为空必拒",
                  lambda: make([{"product": "z", "form": "tree",
                                 "files": [os.path.join(d, "emptydir")]}],
                               os.path.join(d, "b9"), "t/e")
                  if os.makedirs(os.path.join(d, "emptydir"), exist_ok=True) is None else None)

        # ── I. entry 数无上限（协议层；平台容量是分发方的事）──
        # 用户 2026-10-31 裁定「反正协议无限就对了」：这里证的是**不硬编码**，
        # 不是「装得下」。大目录照样生成，不设任何 entry/asset 上限。
        many = os.path.join(d, "many"); os.makedirs(many, exist_ok=True)
        for i in range(340):
            open(os.path.join(many, f"f{i:03d}.txt"), "wb").write(b"x" * 64)
        m_big = make([{"product": "m", "form": "tree", "files": [many]}],
                     os.path.join(d, "bigout"), "t/big")
        t(f"★ 340 个文件 ⇒ 340 条 entry（不硬编码、不设上限）",
          len(m_big["entries"]) == 340)
        t("★ 340 条 entry 的 asset 数 > 1000 也照常生成（平台容量不是协议约束）",
          len(os.listdir(os.path.join(d, "bigout"))) > 1000)

        # 报数口径必须与真实产出一致（否则「预计 N 个 asset」会说谎）
        ok_spec = [{"product": "m", "form": "tree",
                    "files": [os.path.join(d, "small")]}]
        os.makedirs(os.path.join(d, "small"), exist_ok=True)
        for i in range(3):
            open(os.path.join(d, "small", f"s{i}.txt"), "wb").write(b"y" * (2 * DEFAULT_CHUNK))
        est, est_e = _count_assets(ok_spec, ("zstd", "gzip", "identity"), DEFAULT_CHUNK)
        man_ok = make(ok_spec, os.path.join(d, "ok"), "t/ok",
                      codecs=("zstd", "gzip", "identity"))
        real = 1 + sum(len(v["chunks"]) for e in man_ok["entries"] for v in e["variants"])
        t(f"★ 预计 asset 数 == 实际（{est} vs {real}）", est == real and est_e == 3)

    print(f"\n=== {n} PASS / {f} fail ===")
    return 0 if f == 0 else 1


def _parse_product(ps):
    """pid:form[:arch][:src]:path —— 冒号分隔；若 path 含 ':'，用 '--' 分隔。"""
    # `--` 作路径分隔符：仅当左侧像 meta（含 >=2 个 ':'）时才启用，
    # 避免路径本身含 '--'（如 /tmp/a--b/c）被误切。
    if "--" in ps and ps.split("--", 1)[0].count(":") >= 2:
        meta_s, path = ps.split("--", 1)
        meta = meta_s.rstrip(":").split(":")
    else:
        parts = ps.split(":")
        if len(parts) < 3:
            raise SystemExit(f"FATAL: --product 需要 pid:form:path，得到 {ps!r}")
        path = parts[-1]
        meta = parts[:-1]
    pid = meta[0]
    form = meta[1]
    rest = meta[2:]
    arch = None
    srcp = None
    # rest 形如 [] / [arch] / [arch, src] / ["", src]
    if len(rest) == 1:
        if rest[0]:
            arch = rest[0]
    elif len(rest) >= 2:
        arch = rest[0] or None
        srcp = rest[1] or None
    d = {"product": pid, "form": form, "files": [path]}
    if arch:
        d["arch"] = arch
    if srcp:
        d["src"] = srcp
    return d


def main():
    ap = argparse.ArgumentParser(description="发布契约 v4 manifest 生成器")
    ap.add_argument("--out", help="输出目录")
    ap.add_argument("--id", dest="relid", help="release 身份，如 Octave-Full-Wasm/optim-1.6.3")
    ap.add_argument("--product", action="append", default=[],
                    help="pid:form[:arch][:src]:path（path 含 ':' 时用 '--' 分隔）")
    ap.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK,
                    help=f"块大小字节，默认 {DEFAULT_CHUNK}（5 MiB）")
    ap.add_argument("--codecs", default="zstd,gzip,identity",
                    help="逗号分隔的回退链，默认 zstd,gzip,identity")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if not (a.out and a.relid and a.product):
        ap.print_help(); return 2

    codecs = tuple(x.strip() for x in a.codecs.split(",") if x.strip())
    if "identity" not in codecs:
        raise SystemExit("FATAL: codecs 必须含 identity（V4：零依赖兜底）")
    if codecs[-1] != "identity":
        raise SystemExit("FATAL: identity 必须在 codecs 末位（V4）")

    spec = [_parse_product(ps) for ps in a.product]
    man = make(spec, a.out, a.relid, codecs=codecs, chunk=a.chunk_size)
    print(f"\n✅ {os.path.join(a.out, 'manifest.json')}")
    print(f"   id={man['id']}  products={list(man['products'])}  "
          f"entries={len(man['entries'])}  chunkSize={man['chunkSize']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
