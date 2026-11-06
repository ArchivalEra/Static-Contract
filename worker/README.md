# worker — Cloudflare site-line Worker (`static.mango-mesa.ccwu.cc`)

This Worker is the server side of the **Cloudflare line**, one of the two site
mirrors. It was absorbed into this repository's `main` on 2026-11-06; before that
its source lived in a gitignored directory of the course repository
(`S26-1_202609`) and was recalled by user ruling.

## Responsibilities (three parts)

| Path | Behaviour |
|---|---|
| `OPTIONS` | 204 + CORS preflight headers |
| `/<o>/<r>/releases/download/<tag>/<file>` | GitHub release byte proxy: `fetch` uses `redirect: follow`, so the edge follows `github.com -> 302 -> release-assets` on the client's behalf; Range and conditional requests are passed through; 200/206 responses get a 1-year `immutable` cache |
| everything else | Site artifacts are **fetched at runtime** from `raw.githubusercontent.com/ArchivalEra/Static-Contract/deploy-cf`; an extension allowlist plus a top-level bare-name allowlist prevents an open proxy; directories missing a trailing slash get a 301 |

`GET /health` reports the running shape.

## The three response headers (ACAO / CORP / nosniff)

Every asset response carries `Access-Control-Allow-Origin: *`,
`Cross-Origin-Resource-Policy: cross-origin` and `X-Content-Type-Options: nosniff`.

Reason: the consumer (Octave-UI) runs in a COEP `require-corp` context, where a
missing CORP header makes the browser block the response outright — the symptom is
"curl returns 200 for everything, the browser returns `ERR_FAILED` for everything"
(Octave-UI `mail/003`). `raw.githubusercontent.com` supplies those two headers
itself, so the **EdgeOne line** only needs them injected on release paths (the
`release-cors-acao` / `release-corp` rules). This Worker produces every response
itself, so all of them carry the full set.

## Deployment

```bash
cd worker && npx wrangler deploy
```

Or push `worker/**` and let `.github/workflows/worker-deploy.yml` deploy it
automatically (needs the repository secrets `CLOUDFLARE_API_TOKEN` and
`CLOUDFLARE_ACCOUNT_ID`; the workflow skips explicitly when they are absent).

This workflow was verified end to end: with the secrets configured, a
`workflow_dispatch` run performed a real `wrangler deploy`, uploaded `static-host`
and deployed the `static.mango-mesa.ccwu.cc` custom-domain trigger.

## Why runtime origin-pull rather than inlining artifacts

An inline copy is a build-time snapshot: it changes only when someone redeploys.
The artifacts' single source is this repository's `deploy-cf` branch (derived by
`sync-deploy.yml`, force-pushed as one orphan commit). Runtime origin-pull is what
makes "**the `deploy-cf` branch is the only source**" true: a site publish is
visible immediately, with no cross-repository redeploy by anyone.

## Relationship to the old host (do not deploy from the old directory again)

The Worker keeps the name `static-host`; deploying from this directory takes over.
The old source (`S26-1_202609` `.zcode/userscript/host/`) was a combination of a
userscript host and this Worker's predecessor:

- Its three userscript routes (`/assistant.user.js`, `/card.png`, `/card.svg`)
  were **removed with the absorption** — that line is no longer maintained (user
  ruling, 2026-11-06), and they now 404 on this domain.
- **Do not** deploy from the old directory again: it would bring those routes
  back while dropping the release proxy and CORP.
