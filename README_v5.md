# SCE v2.0 Phase 5 — multi-environment characterization and release exports

This **additive** package includes the Phase 4 implementation and new Phase 5 batch tools. It does not replace `run_sce_v2.py`, change APSIM, or run crop simulations. It processes **already executed** APSIM SQLite `Report` databases. Environmental simulation across multiple sites/years requires the Phase 1–3 pipeline to create those databases first.

## Install in PyCharm

Extract ZIP into the repository, merge directories (never replace the entire `sce/`, `scripts/`, `tests/` folders). The new files are `sce/batch.py`, `scripts/characterize_batch.py`, `tests/test_batch.py`, `examples/batch_config_example.json`. `sce/characterization.py` is included only for standalone compatibility; if your Phase 4 file already matches the latest harvest-transition update, do not overwrite it.

## Test

```bash
python3 -m unittest discover -s tests -p 'test_batch.py' -v
```

## Run on verified Phase 3 SQLite file

From SCE repo root:

```bash
python3 scripts/characterize_batch.py \
  --config examples/batch_config_example.json \
  --output-dir phase5_output_2001_mid000
```

**Note:** The sample database must exist in `phase3_native_test/`. The database path is relative to the **JSON config file directory**, not the current working directory.

To compare years/sites/maturity groups, add records to the `runs` array. Every record needs a distinct `run_id`, `site`, `year`, `cultivar`, and `database`. Optional `simulation_id`, `maturity_group`, `sowing_date`, and `harvest_date`. Each APSIM database is processed independently. The example input weather/soil is for demonstration, not a site-calibrated environmental profile.

## Outputs

- `batch_daily.csv`: per-day source APSIM measurements and factor diagnostics, keyed by run/site/year/cultivar.
- `batch_stages.csv`: each **contiguous** stage segment including harvest transition; no silent merging of repeated stage names.
- `batch_covariates.csv`: long-format per-stage covariates, including observation coverage.
- `stage_comparison.csv`: cross-run comparable stage-segment rows, omitting harvest transitions while retaining them in the full exports.
- `run_summary.csv`: season-level overview.
- `batch_manifest.json`: config and SQLite SHA-256 fingerprints, source paths, aggregation rules and counts.

## Scientific constraints

- Comparisons are descriptive; APSIM stage labels have not been independently harmonized across different crop models or cultivar definitions.
- Rainfall/radiation/thermal-time are sums; stress deficits are factor-days and assume source factors constrained to [0,1].
- Missing daily measurements are **not** silently interpreted as zeros.
- Source model files and databases are never modified.
- Existing output files are never replaced.
- Results only include supplied simulations; no extrapolation, geographic calibration or cross-validation is performed.

## Status

Phase 5 batch exports and tests are implemented, but your locally installed APSIM Phase 3 database is needed to validate the first real run. Do not tag the full SCE v2.0 release until tests and complete workflows are documented and confirmed.
