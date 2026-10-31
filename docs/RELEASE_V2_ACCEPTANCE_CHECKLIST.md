# SCE v2.0.0-rc1 — acceptance checklist

- [ ] `develop/sce-v2.0` correctly tracks original history; no commits to upstream repository.
- [ ] Branch contains the Phase 1–5 `sce/`, `scripts/`, `tests/` code and vetted APSIMX template.
- [ ] `python3 scripts/check_sce_release.py --run-tests` passes.
- [ ] `python3 scripts/validate_sce_v2.py --v2 ...` passes all 30 cultivar and manager checks.
- [ ] Native APSIM 2026 completes three example seasons and creates populated Report tables.
- [ ] Phase 5 creates 3 run summaries and stage comparison with no accidental harvest-stage insertion.
- [ ] Wide matrix has one row per run, unique column names, finite numeric data, and source-to-wide agreement for selected stages.
- [ ] `z_12.met` availability documented; ensure no unintentionally proprietary or unpublished datasets are included.
- [ ] `.gitignore` excludes `*.db`, `*.runlog.txt`, `multiyear_*/`, `phase*_output*/`, `sce_runs/`, `.venv/`, `__pycache__/`.
- [ ] `README.md` updated to make CLI-first instructions primary (legacy R Shiny clearly marked).
- [ ] Release notes include `ReaperMan` exact declaration change, invocation of compatibility script, verified APSIM version and scientific limitations.
- [ ] APSIM binary not bundled; original authors attributed; inherited CC BY-NC-SA 4.0 conditions preserved/reviewed.
- [ ] GitHub Actions job passes for Python source tests; native APSIM integration requirements clearly identified if not tested in CI.
- [ ] PR reviewed and merged into your fork's `main`, then candidate tag created; **do not tag until this checklist is reviewed**.
