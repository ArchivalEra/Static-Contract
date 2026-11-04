"""Acceptance: do the bytes actually pass through each line's own edge?

The criterion is not "can it be fetched" -- all three can. The criterion is
**whose edge the bytes crossed**, read from platform fingerprints in the response:

  CF  -> server: cloudflare + cf-ray
  EO  -> eo-log-uuid / eo-cache-status / report-to -> nel.teo-rum.com
         (EO passes upstream headers through, so server may still say
          Windows-Azure-Blob; the eo-* headers are what prove EO handled it)
  GH  -> server: github.com, or the Azure Blob x-ms-* headers that release
         assets are actually served from
"""
import hashlib, os, sys, urllib.error, urllib.request

# Proxy is optional; set SC_HTTP_PROXY to route through one (some networks reset
# TLS to Cloudflare or GitHub directly, which reads as "unreachable" without it).
PROXY = os.environ.get("SC_HTTP_PROXY", "").strip()
if PROXY:
    OP = urllib.request.build_opener(urllib.request.ProxyHandler({"http": PROXY, "https": PROXY}))
else:
    OP = urllib.request.build_opener()

TARGET = (sys.argv[1] if len(sys.argv) > 1
          else "ArchivalEra/LLVM-wasm/releases/download/v0.1.6/manifest.json")
LINES = {
    "cf":         "https://static.mango-mesa.ccwu.cc/" + TARGET,
    "eo":         "https://static.isui.ren/" + TARGET,
    "base_proxy": "https://github.com/" + TARGET,
}

def head(url):
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "verify/1"})
    try:
        with OP.open(req, timeout=30) as r:
            return r.status, dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers)

def classify(name, h):
    """Return (verdict, evidence)."""
    low = {k.lower(): v for k, v in h.items()}
    if name == "cf":
        if "cf-ray" in low and "cloudflare" in low.get("server", "").lower():
            return "PASS", "server=cloudflare, cf-ray=%s" % low["cf-ray"][:16]
        return "FAIL", "no CF edge fingerprint (server=%r)" % low.get("server")
    if name == "eo":
        # EO exposes two header families; I got this wrong once:
        #   the old apex site line isui.ren/static -> Server: edgeone makers /
        #     X-NWS-LOG-UUID (that layer was removed on 2026-11-04)
        #   the current host static.isui.ren -> eo-log-uuid / eo-cache-status /
        #     nel -> eo-nel. It serves the site tree AND the release bytes
        #     (the rule engine splits by path), so both kinds of response
        #     carry the same eo-* headers.
        #   The latter coexists with upstream Azure/Fastly headers, so judging by
        #   `server` alone reports a false negative.
        eo = [k for k in low if k.startswith(("x-eo", "x-nws", "eo-"))]
        if "edgeone" in low.get("server", "").lower():
            eo.append("server=edgeone")
        if "eo-nel" in (low.get("report-to", "") + low.get("nel", "")):
            eo.append("report-to→teo-rum.com")
        if eo:
            return "PASS", ", ".join(sorted(set(eo))[:4])
        return "FAIL", "no EO edge fingerprint (server=%r, x-served-by=%r)" % (
            low.get("server"), low.get("x-served-by"))
    if name == "base_proxy":
        s = low.get("server", "").lower()
        if "github" in s or "x-ms-request-id" in low:
            return "PASS", "server=%s%s" % (low.get("server"),
                     ", x-ms-* (Azure Blob direct)" if "x-ms-request-id" in low else "")
        return "FAIL", "not served by GitHub (server=%r)" % low.get("server")
    return "?", ""

print("Three-line acceptance: whose edge did the bytes cross?\n")
ok = 0
for name, url in LINES.items():
    code, h = head(url)
    verdict, why = classify(name, h)
    if verdict == "PASS":
        ok += 1
    print(f"  {'PASS' if verdict=='PASS' else 'FAIL'}  {name:11} HTTP {code}  {why}")
print(f"\n{ok}/3 lines: bytes crossed their own edge")
