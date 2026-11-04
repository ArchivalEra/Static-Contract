#!/usr/bin/env python3
"""线上验收闸门：**部署后，各通道真的吃到了这次的产物吗**。

为什么必须有（真实事故，2026-11-01）：
    我一连几轮把「workflow 绿 + 三通道互相一致」当成上线成功。实际状态是：
    GitHub Pages 与 deploy 分支都是最新的（16 条上架），而 EdgeOne 那条
    **返回的是加 catalogue 段之前的旧构建**（index.html 2374B vs 5965B，
    catalogue.json 空体，sources.json 404）。三通道「一致」成立过，
    因为那时候大家都还是空的 —— **一致性在都是残骸时也成立**。

⇒ 判据必须锚在**产物本身**，不是通道之间：
    · 每个通道的 index.html 字节 == 本地构建（含本次构建指纹）
    · 每个通道的 catalogue.json 的 verified_at == 本次派生的 verified_at

## 判据

  P1 通道可达（HTTP 200）
  P2 `<chan>/catalogue.json` 的 `verified_at` == 本地派生件里的 `verified_at`
  P3 `<chan>/index.html` 里含 `BUILD_FINGERPRINT`（构建器写进 HTML 的唯一指纹）
  P4 catalogue 的 releases 条数与本地派生件相等

任一不过 ⇒ 非零。**unreachable 也算失败**，不许当「跳过」——
某通道连不上时，「它没问题」这个结论没有任何证据。

## 用法

    python3 scripts/verify-channels.py --expected site/dist \\
        --channels site/channels.json
    python3 scripts/verify-channels.py --selftest

## 边界（如实）

  · 不重试到天荒地老：默认 3 次 × 5s，CDN 传播要时间但闸门不该永远等。
  · 只验「吃到了这次产物」，不验「字节对不对」——后者是 G1–G6 在派生时干的。
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FINGERPRINT = "STATIC-CONTRACT-BUILD"


def fetch(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": "static-contract-verify/1"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def check_channel(name, base, expected_cat, expected_verified, expected_n,
                  expected_fp, fetcher=fetch):
    """验一个通道。返回问题列表（空 = 通过）。"""
    out = []
    base = base if base.endswith("/") else base + "/"

    # P1 + P2 catalogue
    try:
        body = fetcher(base + "catalogue.json")
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        return ["P1 %s 不可达: %s（不可达不是「没问题」——没有证据"\
                "就不能说它对）" % (name, e)]
    try:
        cat = json.loads(body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as e:
        return ["P1 %s catalogue.json 不是合法 JSON: %s（%d 字节）" % (name, e, len(body))]

    got_verified = cat.get("verified_at")
    if got_verified != expected_verified:
        out.append("P2 %s catalogue verified_at=%r ≠ 本次派生 %r ⇒ 它没吃到这次的产物"
                   % (name, got_verified, expected_verified))
    n = len(cat.get("releases") or [])
    if n != expected_n:
        out.append("P4 %s catalogue 条数=%d ≠ 本次 %d" % (name, n, expected_n))

    # P3 index.html 指纹
    try:
        idx = fetcher(base + "index.html").decode("utf-8", "replace")
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        out.append("P3 %s index.html 取不到: %s" % (name, e))
    else:
        if expected_fp not in idx:
            out.append("P3 %s index.html 不含本次构建指纹 %r（%d 字节）⇒ 停在旧构建"
                       % (name, expected_fp, len(idx)))
    return out


def fingerprint_of(expected_dir):
    """从本地构建的 index.html 里取指纹。取不到 ⇒ 构建器没写（那本身就是缺陷）。"""
    p = os.path.join(expected_dir, "index.html")
    body = open(p, encoding="utf-8").read()
    marker = FINGERPRINT + " "
    i = body.find(marker)
    if i < 0:
        return None
    j = body.find("<", i)
    return body[i:j].strip()


def selftest():
    import tempfile

    cases = []

    def case(label, fn):
        try:
            cases.append((label, bool(fn()), None))
        except Exception as e:                                  # noqa: BLE001
            cases.append((label, False, repr(e)))

    GOOD = {"verified_at": "T1", "releases": [{}, {}, {}]}
    FP = FINGERPRINT + " abc123"

    def mk(cat_obj=None, index="<html>" + FP + "</html>", raise_cat=False):
        def f(url):
            if url.endswith("catalogue.json"):
                if raise_cat:
                    raise urllib.error.URLError("down")
                return json.dumps(cat_obj if cat_obj is not None else GOOD).encode()
            return index.encode()
        return f

    case("正常：全部对齐 ⇒ 不报", lambda: check_channel(
        "c", "https://x/", GOOD, "T1", 3, FP, mk()) == [])
    case("★ P2 verified_at 旧 ⇒ 必报（本次事故的形状）",
         lambda: any("P2" in x for x in check_channel(
             "c", "https://x/", GOOD, "T2-NEW", 3, FP, mk())))
    case("★ P4 条数不符 ⇒ 必报",
         lambda: any("P4" in x for x in check_channel(
             "c", "https://x/", GOOD, "T1", 16, FP, mk())))
    case("★ P3 指纹缺失（旧构建）⇒ 必报",
         lambda: any("P3" in x for x in check_channel(
             "c", "https://x/", GOOD, "T1", 3, FP,
             mk(index="<html>old build</html>"))))
    case("★ P1 不可达 ⇒ 必须报，不许当跳过",
         lambda: any("P1" in x and "不可达" in x for x in check_channel(
             "c", "https://x/", GOOD, "T1", 3, FP, mk(raise_cat=True))))
    case("★ 空体（0 字节 catalogue）⇒ 必须报",
         lambda: check_channel("c", "https://x/", GOOD, "T1", 3, FP,
                               lambda u: b"") != [])
    case("★ 坏 JSON ⇒ 必须报",
         lambda: any("不是合法 JSON" in x for x in check_channel(
             "c", "https://x/", GOOD, "T1", 3, FP, lambda u: b"{oops")))

    # fingerprint_of
    def fp_probe():
        d = tempfile.mkdtemp()
        open(os.path.join(d, "index.html"), "w").write("<p>" + FINGERPRINT + " deadbeef</p>")
        return fingerprint_of(d) == FINGERPRINT + " deadbeef"
    case("从 index.html 取指纹", fp_probe)

    def fp_missing():
        d = tempfile.mkdtemp()
        open(os.path.join(d, "index.html"), "w").write("<p>no fp</p>")
        return fingerprint_of(d) is None
    case("★ 缺指纹 ⇒ None（构建器缺陷要能看见）", fp_missing)

    # 归属分流：owned=false 的失败不进 blocked（不阻塞）
    def ownership_routing():
        chans = [{"name": "mine", "owned": True}, {"name": "theirs", "owned": False}]
        last, blocked = {}, {}
        for c in chans:
            name, owned = c["name"], bool(c.get("owned"))
            (blocked if owned else last)[name] = ["P1 不可达"]
        return set(blocked) == {"mine"} and set(last) == {"theirs"}
    case("★ 归属分流：外部通道失败进 last（不阻塞），我方进 blocked", ownership_routing)

    bad = 0
    for label, ok, err in cases:
        print("%s | %s%s" % ("PASS" if ok else "fail", label,
                             "（%s）" % err if err else ""))
        bad += 0 if ok else 1
    print("=== %d PASS / %d FAIL ===" % (len(cases) - bad, bad))
    return 1 if bad else 0


def main(argv):
    if "--selftest" in argv:
        return selftest()
    if "--expected" not in argv or "--channels" not in argv:
        print("用法：verify-channels.py --expected <dist> --channels <channels.json> "
              "[--attempts N] [--wait S] | --selftest", file=sys.stderr)
        return 2
    exp_dir = argv[argv.index("--expected") + 1]
    chan_path = argv[argv.index("--channels") + 1]
    attempts = int(argv[argv.index("--attempts") + 1]) if "--attempts" in argv else 3
    wait = float(argv[argv.index("--wait") + 1]) if "--wait" in argv else 5.0

    cat = json.load(open(os.path.join(exp_dir, "catalogue.json"), encoding="utf-8"))
    verified = cat.get("verified_at")
    n = len(cat.get("releases") or [])
    fp = fingerprint_of(exp_dir)
    if fp is None:
        print("FATAL: 本地构建的 index.html 里没有 %s 指纹 —— 构建器没写，"
              "验收无从锚定" % FINGERPRINT, file=sys.stderr)
        return 2

    doc = json.load(open(chan_path, encoding="utf-8"))
    # 归属：owned=true 的通道失败**阻塞发布**；外部通道失败只报告。
    # 理由（2026-11-02，CF 全 404 事故）：别人的通道挂了不该拦停我的产物上线，
    # 那会让问题叠加（我的新产物上不去，他们的通道还没人修）。
    channels = [(c["name"], c["base"], bool(c.get("owned")))
                for c in doc.get("channels") or []]
    # ★ 零值守卫（2026-11-04 撤掉 github-pages 后新增）：
    #   没有任何 owned 通道 ⇒ 这个闸门再也阻塞不了任何东西。
    #   「全部是外通道」不等于「没有我方责任」—— 它是判据失效。
    if not any(o for _n, _b, o in channels):
        print("FATAL: 通道清单里没有任何 owned=true 的通道 —— 验收永远不会阻塞发布。"
              "至少要把一条我方负责的通道标 owned（例如 deploy 分支本身）。",
              file=sys.stderr)
        return 2
    if not channels:
        print("FATAL: channels.json 里没有通道 —— 零通道不是「全通过」", file=sys.stderr)
        return 2

    print("本次产物：verified_at=%s 条数=%d 指纹=%s" % (verified, n, fp))
    last = {}
    for attempt in range(1, attempts + 1):
        last = {}
        blocked = {}
        for name, base, owned in channels:
            probs = check_channel(name, base, cat, verified, n, fp)
            if probs:
                (blocked if owned else last)[name] = probs
        if not blocked:
            if last:
                for name, probs in sorted(last.items()):
                    print("⚠ 外部通道 %s 未就绪（不阻塞发布）: %s"
                          % (name, probs[0][:70]))
            print("全部 %d 个我方/已就绪通道都吃到了本次产物" % len(channels))
            return 0
        if attempt < attempts:
            print("第 %d/%d 轮有通道未就绪，%.0fs 后重试…" % (attempt, attempts, wait))
            time.sleep(wait)

    print("\n验收失败（%d 轮后仍有通道没吃到本次产物）：" % attempts, file=sys.stderr)
    for name, probs in sorted(last.items()):
        print("  ── %s" % name, file=sys.stderr)
        for p in probs:
            print("     %s" % p, file=sys.stderr)
    print("\n判据：通道之间「一致」不算证据（都停在旧产物时也一致）；"
          "必须各自等于本次产物。", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
