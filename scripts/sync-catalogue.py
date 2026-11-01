#!/usr/bin/env python3
"""catalogue 严格派生：坏 release **从未上架**（客户端零错误处理）。

裁定（用户 2026-11-01）：
    「最后做一下 catalogue 的严格校验，不允许有坏的流到客户端，足够了，
      根本不需要客户端错误排查的事情，只要坏的从未上架过」

⇒ 校验点前移到**发布端**。catalogue 不是手写清单，是从各仓 release **派生**的产物；
派生时逐条过严格闸门，通过的才进 array，不通过的不进并**记录原因**。
客户端因此永远不需要处理「坏条目」——它在 array 里不存在。

## 严格闸门（每条 release 都要过）

  G1 有 manifest.json asset，且平台给了 digest
  G2 manifest.json 的**平台 digest == 内容 sha256**（证明「我读到的 manifest 就是平台存的」）
  G3 manifest 过 `check-release-v4.py` 全套 V1–V10（零下载：纯 manifest 判据）
  G4 **V7 的字节身份用平台 digest 对**（零下载）：manifest 里每个 chunk 的
     sha256 == 平台该 asset 的 digest ⇒ 证明「manifest 说的块 == 平台上真有且是这份」
  G5 schema 必须是 2（V10 已含，这里明写一遍便于审计）
  G6 没有孤儿 asset（asset 不在任何 chunk 里 ⇒ 平台上有 manifest 不认识的文件）

## 失败即拒绝发布（不是跳过）

任一条 source 拉取失败（网络 / 权限 / 仓库消失）⇒ **整次同步失败**，保留上次
catalogue 不动。理由：静默产出空目录 = 所有 release 一起「消失」且无闸门红。

## 用法

    python3 scripts/sync-catalogue.py --out site/catalogue.json   # 派生并写盘
    python3 scripts/sync-catalogue.py --dry-run                   # 只算不写
    python3 scripts/sync-catalogue.py --selftest                  # 自证（不联网）
"""
import hashlib
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCES = os.path.join(HERE, "site", "sources.json")
CHECKER = os.path.join(HERE, "tools", "check-release-v4.py")
GITHUB_API = "https://api.github.com"
ACCEPT_SCHEMA = 2


# ── GitHub 取数（可注入 —— 自证用假 fetcher，绝不联网）────────────────────────
def _token():
    """取 token：**环境变量优先**（CI 里没有 `gh auth`），其次 gh CLI，最后匿名。

    CI 用 `GITHUB_TOKEN` 环境变量 —— 不设它会在 API 上限流（60/h），
    而限流会被误读成「没有 release」，正是本脚本最要防的静默失败。
    """
    for k in ("GITHUB_TOKEN", "GH_TOKEN"):
        v = os.environ.get(k, "").strip()
        if v:
            return v
    try:
        return subprocess.run(["gh", "auth", "token"], capture_output=True,
                              text=True, timeout=15).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def http_get(url, token=None, timeout=60):
    """GET 一个 URL，返回 bytes。失败抛异常（调用方决定怎么报）。"""
    req = urllib.request.Request(url)
    if token:
        req.add_header("Authorization", "token " + token)
    req.add_header("Accept", "application/vnd.github+json")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def gh_json(url, token, timeout=60):
    return json.loads(http_get(url, token, timeout).decode("utf-8"))


# ── 严格闸门的纯逻辑（自证的主战场）──────────────────────────────────────────
def _chunk_files(man):
    """manifest 里被引用的全部 asset 名。"""
    out = set()
    for e in man.get("entries") or []:
        for v in e.get("variants") or []:
            for c in v.get("chunks") or []:
                n = c.get("file")
                if isinstance(n, str):
                    out.add(n)
    return out


def _chunk_sha_map(man):
    """{asset 名: sha256} —— 同一个文件在多个 codec/variant 里出现时取唯一值。"""
    out = {}
    for e in man.get("entries") or []:
        for v in e.get("variants") or []:
            for c in v.get("chunks") or []:
                n, s = c.get("file"), c.get("sha256")
                if isinstance(n, str) and isinstance(s, str):
                    prev = out.get(n)
                    if prev is not None and prev != s:
                        # 同一个文件两个 sha ⇒ manifest 自相矛盾（V2 的加强版，
                        # check-release-v4 若不查这条，这里兜住）
                        out[n] = None
                    else:
                        out[n] = s
    return out


def verify_entry(repo, rel, manifest_bytes, assets_by_name, check_runner):
    """验一条 release。返回 (entry or None, reasons)。

    `assets_by_name` = {name: {"digest": "sha256:...", "size": n}}
    `check_runner(man)` = 跑 V1–V10，返回问题列表（空 = 通过）
    """
    reasons = []
    tag = rel.get("tag_name") or "?"
    base = ("https://github.com/%s/releases/download/%s/" % (repo, tag))

    # G1 有 manifest 且平台给了 digest
    mas = assets_by_name.get("manifest.json")
    if not mas:
        return None, ["G1 缺 manifest.json"]
    if not mas.get("digest"):
        reasons.append("G1 平台未给 manifest digest（无法证明读到的是平台那份）")

    # G2 平台 digest == 内容 sha256
    got = hashlib.sha256(manifest_bytes).hexdigest()
    pd = (mas.get("digest") or "").split(":", 1)[-1]
    if mas.get("digest") and pd != got:
        reasons.append("G2 manifest 内容 sha=%s != 平台 digest=%s" % (got[:12], pd[:12]))

    try:
        man = json.loads(manifest_bytes.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as e:
        return None, reasons + ["G1 manifest 不是合法 JSON: %s" % e]

    # G5 schema
    if man.get("schema") != ACCEPT_SCHEMA:
        return None, reasons + ["G5 schema=%r（本客户端只认 %d）"
                                % (man.get("schema"), ACCEPT_SCHEMA)]

    # G3 V1–V10
    problems = check_runner(man)
    if problems:
        return None, reasons + ["G3 " + p for p in problems]

    # G4 每个 chunk 的 sha256 == 平台 digest
    shas = _chunk_sha_map(man)
    for name, want in sorted(shas.items()):
        if want is None:
            reasons.append("G4 %s 在 manifest 里有冲突的 sha256" % name)
            continue
        a = assets_by_name.get(name)
        if not a:
            reasons.append("G4 %s 在平台上不存在" % name)
            continue
        have = (a.get("digest") or "").split(":", 1)[-1]
        if not have:
            reasons.append("G4 %s 平台未给 digest（无法零下载验字节）" % name)
        elif have != want:
            reasons.append("G4 %s manifest sha=%s != 平台 %s" % (name, want[:12], have[:12]))

    # G6 无孤儿 asset
    orphans = sorted(set(assets_by_name) - _chunk_files(man) - {"manifest.json"})
    if orphans:
        reasons.append("G6 孤儿 asset（manifest 不认识）: %s" % ", ".join(orphans[:5]))

    if reasons:
        return None, reasons

    # 通过：条目**不含任何可变内容**（tag 固定的 base + 派生时刻 + manifest 身份）
    return {
        "id": "%s/%s" % (man.get("id") or "%s/%s" % (repo, tag), ""),
        "base": base,
        "base_proxy": None,
        "manifest_sha256": got,
        "verified_at": None,          # 由调用方填（保持纯函数）
        "source_repo": repo,
        "tag": tag,
    }, []


def fix_entry(entry, man_id, now):
    """把 manifest 自称的 id 归一（manifest.id 形如 `<repo>/<pkg>@<ver>`）。"""
    entry["id"] = man_id
    entry["verified_at"] = now
    return entry


# ── 派生主流程 ───────────────────────────────────────────────────────────────
def derive(sources, fetch_releases, fetch_bytes, check_runner, now):
    """派生 catalogue。`releases` = 通过列表；`excluded` = 坏的原因为什么没上架。

    **任何 source 取数失败 ⇒ 抛异常**（fail-closed：不许静默产出空目录）。
    """
    releases, excluded = [], []
    for src in sources:
        repo = src["repo"]
        rels = fetch_releases(repo)                 # 失败让异常冒上去
        for rel in rels:
            if rel.get("draft") or rel.get("prerelease"):
                continue
            assets = {a["name"]: a for a in rel.get("assets") or []}
            tag = rel.get("tag_name") or "?"
            try:
                body = fetch_bytes(assets["manifest.json"]["browser_download_url"])
            except KeyError:
                excluded.append({"repo": repo, "tag": tag, "reasons": ["G1 缺 manifest.json"]})
                continue
            except (urllib.error.URLError, OSError, TimeoutError) as e:
                excluded.append({"repo": repo, "tag": tag,
                                 "reasons": ["G1 manifest 取不到: %s" % e]})
                continue
            entry, reasons = verify_entry(repo, rel, body, assets, check_runner)
            if entry is None:
                excluded.append({"repo": repo, "tag": tag, "reasons": reasons})
            else:
                try:
                    man = json.loads(body.decode("utf-8"))
                    mid = man.get("id") or "%s/%s" % (repo, tag)
                except (ValueError, UnicodeDecodeError):
                    mid = "%s/%s" % (repo, tag)
                releases.append(fix_entry(entry, mid, now))
    ids = [r["id"] for r in releases]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        raise SystemExit("FATAL: catalogue 里 id 重复（不同 release 自称同一 id）: %s"
                         % ", ".join(dup))
    releases.sort(key=lambda r: (r["source_repo"], r["tag"]))
    excluded.sort(key=lambda r: (r["repo"], r["tag"]))
    return releases, excluded


# ── 自证（纯逻辑，不联网）────────────────────────────────────────────────────
def _selftest():
    import tempfile

    def good_man():
        body = json.dumps({"schema": 2, "id": "R/p@1", "chunkSize": 5242880,
                           "codecs": ["identity"], "products": {"p": {"form": "file"}},
                           "entries": [{"product": "p", "name": "a.bin", "bytes": 3,
                                        "sha256": "a" * 64,
                                        "variants": [{"codec": "identity", "chunks": [
                                            {"part": 0, "file": "p__a.bin.identity.000",
                                             "bytes": 3, "sha256": "b" * 64}]}]}]}).encode()
        return body, {"manifest.json": {"digest": "sha256:" + hashlib.sha256(body).hexdigest()},
                      "p__a.bin.identity.000": {"digest": "sha256:" + "b" * 64}}

    def run(rel, body, assets, checker=lambda m: []):
        return verify_entry("R", rel, body, assets, checker)

    cases = []

    def case(label, fn):
        try:
            cases.append((label, bool(fn()), None))
        except Exception as e:                                  # noqa: BLE001
            cases.append((label, False, repr(e)))

    # ① 正常不报
    case("合法 release ⇒ 通过、条目无坏字段", lambda: (lambda r: r[0] is not None and not r[1])(run({"tag_name": "t"}, *good_man())))
    case("条目带 base（tag 固定）与 manifest_sha256",
         lambda: (lambda r: r[0]["base"].endswith("/t/") and len(r[0]["manifest_sha256"]) == 64)(run({"tag_name": "t"}, *good_man())))
    # ② 该报必报
    def miss_manifest():
        b, a = good_man(); a.pop("manifest.json")
        return run({"tag_name": "t"}, b, a)[0] is None
    case("★ G1 缺 manifest ⇒ 拒", miss_manifest)

    def bad_g2():
        b, a = good_man(); a["manifest.json"]["digest"] = "sha256:" + "0" * 64
        return any("G2" in x for x in run({"tag_name": "t"}, b, a)[1])
    case("★ G2 平台 digest ≠ 内容 sha ⇒ 拒", bad_g2)

    def bad_schema():
        b, a = good_man(); a["manifest.json"]["digest"] = "sha256:" + hashlib.sha256(b).hexdigest()
        i = b.index(b'"schema": 2'); b2 = b[:i] + b'"schema": 1' + b[i + 11:]
        a["manifest.json"]["digest"] = "sha256:" + hashlib.sha256(b2).hexdigest()
        return any("G5" in x for x in run({"tag_name": "t"}, b2, a)[1])
    case("★ G5 schema≠2 ⇒ 拒（旧 manifest 结构在此挡下）", bad_schema)

    def bad_g3():
        return any("G3" in x for x in run({"tag_name": "t"}, *good_man(),
                                          checker=lambda m: ["V1 名字非法"])[1])
    case("★ G3 V1–V10 任一不过 ⇒ 拒", bad_g3)

    def bad_g4():
        b, a = good_man(); a["p__a.bin.identity.000"]["digest"] = "sha256:" + "c" * 64
        return any("G4" in x for x in run({"tag_name": "t"}, b, a)[1])
    case("★ G4 manifest 块 sha ≠ 平台 digest ⇒ 拒（零下载验字节）", bad_g4)

    def bad_g4_missing():
        b, a = good_man(); a.pop("p__a.bin.identity.000")
        return any("G4" in x for x in run({"tag_name": "t"}, b, a)[1])
    case("★ G4 manifest 引用的块平台没有 ⇒ 拒", bad_g4_missing)

    def bad_g6():
        b, a = good_man(); a["extra.bin"] = {"digest": "sha256:" + "d" * 64}
        return any("G6" in x for x in run({"tag_name": "t"}, b, a)[1])
    case("★ G6 孤儿 asset ⇒ 拒（平台上有 manifest 不认的文件）", bad_g6)

    # ③ 空输入 / 失败即拒绝
    case("★ 空 releases 列表 ⇒ 派生结果为空但**不抛**（真空 ≠ 故障）",
         lambda: derive([{"repo": "R"}], lambda r: [], lambda u: b"", lambda m: [], "now")[0] == [])

    def fetch_fail_propagates():
        def boom(_): raise urllib.error.URLError("network down")
        try:
            derive([{"repo": "R"}], boom, lambda u: b"", lambda m: [], "now")
            return False
        except urllib.error.URLError:
            return True
    case("★ source 取数失败 ⇒ **抛异常**（不许静默产出空目录）", fetch_fail_propagates)

    case("★ 重复 id ⇒ SystemExit（两个 release 自称同一 id）",
         lambda: _dup_probe())

    bad = 0
    for label, ok, err in cases:
        print("%s | %s%s" % ("PASS" if ok else "fail", label,
                             "（%s）" % err if err else ""))
        bad += 0 if ok else 1
    print("=== %d PASS / %d FAIL ===" % (len(cases) - bad, bad))
    return 1 if bad else 0


def _dup_probe():
    body = json.dumps({"schema": 2, "id": "SAME", "chunkSize": 5242880,
                       "codecs": ["identity"], "products": {"p": {"form": "file"}},
                       "entries": []}).encode()
    dg = "sha256:" + hashlib.sha256(body).hexdigest()

    def fetch_releases(_):
        return [{"tag_name": "a", "assets": [{"name": "manifest.json", "digest": dg,
                                              "browser_download_url": "u"}]},
                {"tag_name": "b", "assets": [{"name": "manifest.json", "digest": dg,
                                              "browser_download_url": "u"}]}]
    try:
        derive([{"repo": "R"}], fetch_releases, lambda u: body, lambda m: [], "now")
        return False
    except SystemExit:
        return True


def main(argv):
    if "--selftest" in argv:
        return _selftest()
    dry = "--dry-run" in argv
    out = os.path.join(HERE, "site", "catalogue.json")
    if "--out" in argv:
        out = argv[argv.index("--out") + 1]

    src_doc = json.load(open(SOURCES, encoding="utf-8"))
    sources = src_doc.get("sources") or []
    if not sources:
        print("FATAL: sources.json 为空 —— 零源不是「没有坏条目」，是「什么都没查」",
              file=sys.stderr)
        return 2

    token = _token()
    import importlib.util

    def check_runner(man):
        spec = importlib.util.spec_from_file_location("chk", CHECKER)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _R, P = mod.check(man, base_dir=None)          # 零下载：纯 manifest 判据
        return P

    now = subprocess.run(["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"],
                         capture_output=True, text=True).stdout.strip()
    releases, excluded = derive(
        sources,
        lambda repo: gh_json("%s/repos/%s/releases?per_page=100" % (GITHUB_API, repo), token),
        lambda url: http_get(url, token),
        check_runner, now)

    doc = {"schema": 1,
           "note": ("本站不收录任何 release 件（0 字节托管）。**本文件由 "
                    "scripts/sync-catalogue.py 从各仓 release 严格派生，不要手改**。"
                    "每条都过了 G1–G6（含 V1–V10 全套 + 平台 digest 零下载验字节）；"
                    "客户端不需要处理坏条目 —— 坏条目从未上架。"),
           "verified_at": now,
           "releases": releases,
           "excluded": excluded}
    text = json.dumps(doc, ensure_ascii=False, indent=1) + "\n"
    print("派生：%d 条上架 / %d 条排除" % (len(releases), len(excluded)))
    for e in excluded:
        print("  ✗ %s %s: %s" % (e["repo"], e["tag"], e["reasons"][0]))
    if dry:
        print("--dry-run：未写盘")
        return 0
    open(out, "w", encoding="utf-8").write(text)
    print("已写出 %s" % os.path.relpath(out, HERE))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
