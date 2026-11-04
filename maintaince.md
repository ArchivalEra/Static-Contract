# maintaince.md · Direction and Map (Static-Contract)

This file **points at direction and boundaries only**. It copies no numbers and no procedures.
Measured current state lives in `STATE.md` (live state, every assertion paired with its rerun
command); usage lives in `README.md`. Anything copied here would drift: the tools speak for
themselves (build gates turn red, self-tests count, git keeps the books), and listening to them
beats trusting any detail written below. (Einfacht ecosystem format: the fact ledger and the gate
roster maintain themselves — read `STATE.md` for what is true now.)

## What this project is

The **authoritative repository for the Octave cluster's static distribution contract**: protocol
canon + toolchain + metadata site + open-questions ledger. **apt's robustness plus HTTP's
simplicity.** This repository is a contract maintainer and nothing else — the site hosts zero bytes;
package bytes come only from GitHub direct links or through a reverse proxy (the ruling's own wording
and its gates are in `STATE.md`).

## Map (where the truths are)

| To find out | Go to |
|---|---|
| What is true now | `STATE.md` (live state) |
| Where the numbers come from | `FACTS.json` (measured by `zreflect/facts.py`; prose may only cite `[[key]]`) |
| The gate roster | the machine block at the end of `STATE.md` (discovery-derived, never hand-written) |
| How to use the protocol | `README.md`; canon `specs/2026-10-30-release-contract-v4.md` (§4, client algorithm) |
| What may not change | canon §3 invariants V1–V10 + §8, the criteria that killed rejected designs |
| What the site lists | `site/catalogue.json` (the only data source; the builder reads nothing else) |
| What the site looks like | `scripts/build-site.py` (artifact list and gates both live in its declaration) |
| Incident log | `docs/incidents.md` — what broke, root cause, fix (repository only, not published) |
| User rulings | `docs/rulings.md` — original wording preserved (repository only, not published) |
| Open questions | `questions/` (each carries a settling criterion; 05 is unresolved) |
| Cross-repository mail | `mail/` (rules: append-only, numbers increase, delivery ≠ commit) |
| The anti-hallucination system itself | `vendor/Einfacht/` (upstream `6e4e6e8`, vendored snapshot) |

## Maintenance boundary

**Ours**:
- schema definition and evolution (`schema: 2` → future versions)
- adding, removing, or changing invariants V1–V10
- tightening or loosening the asset-name whitelist (**measure the platform's rewrite surface
  first** — the measurement table in canon §1 is the only basis)
- catalogue admission criteria and the zero-byte gate
- acceptance criteria for repositories joining the contract

**Not ours** (each belongs to its owner; do not cross the line):
- content semantics (`form` / `content` / `consumer` axes, version policy, license ledger) →
  `Octave-Extra-Content`
- engine artifacts and build facts (`octave.build.json`) → the host, `Octave-Full-Wasm`
- site assembly and routing (Astro base, literal rewriting) → `Octave-UI`
- edge and reverse proxy (EdgeOne / isui.ren) → `Shirone-personalized`

## Routine

- **Committing**: the hooks are installed (`core.hooksPath=reflect-hooks`) — they re-render the
  machine block and run every gate in the commit phase (`off` is not a pass; it is listed separately
  in the output). If you changed a measurement or a value, re-measure first with
  `python3 zreflect/facts.py` (accept changed values one by one with `--accept-changes=k1,k2`, drops
  with `--allow-drop`); CI (the `gates` workflow) applies the same criterion remotely, and
  `--no-verify` does not get past it.

- **Cross-repository communication**: **A cross-repository wait condition must be one executable
  command.** When reporting "ready", include what that command returns right now. (Proposed by
  LLVM-wasm in `mail/024` §5; adopted.)

  ```bash
  # tool sync
  git clone --depth 1 <repo> /tmp/x && python3 /tmp/x/tools/check-release-v4.py --selftest | tail -1
  # channel content
  for u in <ch1> <ch2> <ch3>; do curl -s "$u/index.html" | grep -o 'BUILD [0-9a-f]*'; done
  ```

  The reason: downstream can only measure what it managed to `git clone`;
  "I have put it in place" is invisible to them.

- **Pushing**: `REFLECT_READMES` (= `README.md`) is updated **in the same batch as every push** —
  the "same batch" criterion does not degrade in single-entry mode (it is self-proved in
  `check_readme_sync`), and pre-push and CI apply the same criterion. Documentation follows the
  code; this is not a ritual: change behaviour without updating the docs and the docs have been lying
  since that moment.

- **Cataloguing a release**: **no longer a manual edit**. Once a publisher publishes a GitHub
  release it is onboarded (provided the repository is in the subscription list); `sync-deploy`
  derives the catalogue on every push and on a timer, and only releases that pass G1–G7 go live.
  Adding a repository = adding one line to `site/sources.json` (an explicit decision). A bad release
  never enters the catalogue, and the reason is written into the catalogue's `excluded` (public,
  auditable).

- **Deploy exit**: one branch per mirror — `deploy-eo` and `deploy-cf`. Each is the pure site
  artifact (a single orphan commit) written only by the workflow, and each carries a catalogue
  whose `base` points at that mirror. The two are **not** byte-identical: only `catalogue.json`
  differs. Adding a mirror is one matrix row plus one branch.

- **Amending the canon**: open a `questions/` entry first (with an executable settling criterion) →
  rule → amend the canon, and record the ruling's wording and date in `STATE.md`.
  **The criteria for rejected designs must stay in canon §8 so nobody re-opens them.**

- **Red line**: no release artifact (tar / zip / wasm / whl / chunks) enters `main`, and none enters
  any `deploy-*` branch — a build gate turns red (`scripts/build-site.py` artifact scan).
