# Contributing to Taxify

Internal guide. Taxify is proprietary — see [LICENSE](LICENSE).

## Before anything else

**The default branch on GitHub is `master`, but all work happens on `main`.**
`master` is a stale line of work. A bare `git clone` gets the wrong code.

```bash
git clone -b main https://github.com/DevanshGoyanka/Taxify
```

## Local setup

Requires **Python 3.10** and **Node 20**.

```bash
python3.10 -m venv .venv
./.venv/bin/pip install -r requirements.txt      # Windows: .venv\Scripts\pip
cd frontend && npm ci
```

Copy the credentials into `.env` at the repo root — ask a maintainer, never commit it.

Run:

```bash
python run.py                    # backend :8000  (NOT `uvicorn app.main:app`, see below)
cd frontend && npm run dev       # frontend :3000
```

### Why `run.py` and not `uvicorn` directly

On Windows, uvicorn's `asyncio_setup()` switches to `WindowsSelectorEventLoopPolicy`, which
cannot spawn subprocesses. Playwright then fails with `NotImplementedError` the moment any
portal automation runs. `run.py` sets the Proactor policy *before* importing uvicorn and
passes `loop="none"` so uvicorn cannot override it.

On Linux the default loop already supports subprocesses, which is why the deployed systemd
unit calls uvicorn directly.

## Code style

`.editorconfig` is authoritative — 4 spaces for Python, 2 for TS/JS/JSON/CSS, LF endings.

Match the surrounding code. This codebase favours explanatory comments that state *why*,
particularly around CBDT rules — keep that up. When a rule comes from a CBDT/ITD document,
cite it.

## Dependencies

**Every third-party import must be declared in `requirements.txt` or `package.json`.**

Most Python imports here are lazy (inside functions), so a missing package doesn't fail at
startup — it fails when a user hits the feature, in production. Nine packages were missing
this way and only surfaced when portal automation broke on the live host.

To check before you push:

```bash
./.venv/bin/python - <<'PY'
import ast, pathlib, sys
mods = set()
for root in (pathlib.Path("app"), pathlib.Path("ais_extractor")):
    for f in root.rglob("*.py"):
        try: tree = ast.parse(f.read_text(encoding="utf-8", errors="ignore"))
        except SyntaxError: continue
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                for a in n.names: mods.add(a.name.split(".")[0])
            elif isinstance(n, ast.ImportFrom) and n.level == 0 and n.module:
                mods.add(n.module.split(".")[0])
for m in sorted(mods - set(sys.stdlib_module_names) - {"app","ais_extractor","tests","scripts"}):
    try: __import__(m)
    except Exception: print("MISSING:", m)
PY
```

## Tests

```bash
pytest                                  # full suite
pytest tests/test_itr1_calculator.py -v # one file
```

**The suite is not green** — a measured baseline is 177 failures and 13 collection errors,
predating the deployment work. Do not treat a red run as your fault; do check that *your*
area is not newly broken. If you fix a suite, say so in the PR.

`conftest.py` at the repo root loads `.env` before any test imports app code — ERI credential
resolution fails without it.

## Secrets

Never commit `.env`, `app.db`, DSC certificates, keystores, or `*.pem`.
See [SECURITY.md](SECURITY.md). If you commit one by accident, rotating it is mandatory —
deleting the file does not remove it from git history.

## Commit messages

Explain **why**, not just what. State the failure mode a change prevents.

```
Enable SQLite WAL so the automation worker cannot lock out the API

The engine set only check_same_thread=False, leaving SQLite in its default
delete journal mode where a writer blocks every reader...
```

## Pull requests

1. Branch from `main`
2. Keep the change focused — one concern per PR
3. Confirm the frontend builds: `cd frontend && npm run build` (`tsc -b` must pass)
4. Note any new dependency and why it's needed
5. Flag anything touching ERI credentials, CBDT JSON generation, or the digest computation —
   those affect filed returns

## Deployment

Not automatic on merge unless the CI/CD workflow is enabled. See
[`Docs/AWS_FREE_TIER_DEPLOYMENT.md`](Docs/AWS_FREE_TIER_DEPLOYMENT.md) and
[`docs/runbook.md`](docs/runbook.md).
