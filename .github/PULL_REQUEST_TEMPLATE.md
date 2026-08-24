## What changed

<!-- One or two sentences. What does this do? -->

## Why

<!-- The failure mode this prevents, or the requirement it satisfies.
     If it comes from a CBDT/ITD rule, cite it. -->

## Checklist

- [ ] Branched from and targeting **`main`** (not `master` — that branch is stale)
- [ ] Any new third-party import is declared in `requirements.txt` / `package.json`
- [ ] `cd frontend && npm run build` passes (`tsc -b` included)
- [ ] No secrets committed — `.env`, `app.db`, `*.pem`, keystores, DSC certificates

## Tax-critical changes

Tick if this touches any of these, and explain the impact:

- [ ] ERI credential resolution or the `(ERI_MODE, ERI_ENV)` selection
- [ ] CBDT JSON generation or the `Digest` computation
- [ ] Calculator logic, slabs, surcharge, rebate, or cess
- [ ] Anything affecting an already-filed return

<!-- These can change the content of returns filed with the Income Tax
     Department. Describe what you verified and how. -->

## Testing

<!-- What did you run? Note that the suite is not green - a known baseline is
     177 failures / 13 collection errors. Confirm your area is not NEWLY broken. -->
