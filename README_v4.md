# SCE v2.0 — Phase 4: Seasonal environmental characterization

A Python-only, non-destructive postprocessor of APSIM's **daily `Report`** SQLite table. The CLI does **not** run APSIM or adjust its crop physiology. It consumes a completed Phase 3 database and outputs:

1. `daily_phenology.csv`: every daily APSIM Report variable plus `stage_segment_id` and `days_since_sowing`.
2. `stage_summary.csv`: contiguous `StageName` interval characteristics (days; sums of rainfall, radiation and thermal time; mean temperature, soil-water, soil nutrient and reported stress factors; dry-spell metrics).
3. `stage_covariates.csv`: tidy stage-by-covariate table for comparison across trials/seasons.
4. `characterization_manifest.json`: source DB, date selection, observational semantics and output inventory.

### Install in PyCharm

Merge `sce/`, `scripts/`, `tests/`, `examples/`, `docs/` into the SCE development-branch project. Do not replace Phase 1–3 source files. No extra third-party Python packages required for the CLI and tests.

### Unit tests

```bash
python3 -m unittest discover -s tests -p 'test_characterization.py' -v
```

### Native Phase 3 integration (run from the SCE repository root)

```bash
python3 scripts/characterize_season.py \
  --db phase3_native_test/SCE_Phase3_2001_mid000.db \
  --output-dir phase4_output_2001_mid000
```

Expect `n_report_days: 365`, with `n_season_days` based on actual sow/harvest events. Inspect `stage_summary.csv` in PyCharm. If the model did not emit a `SimSowDate` event, `--sow-date 2001-04-12` can specify an external known planting date; this is explicitly recorded in the manifest.

### Scientific/interpretation limits

- **No guessed stage boundaries.** Each *contiguous* interval of the APSIM `StageName` string is one segment. These reflect the model's internal developmental naming, and should not be equated with externally observed R1, R5, R7 etc without a documented mapping. Repeated labels create new segments.
- The default analysis window starts on the **actual simulated sowing event** and stops at the simulated harvest event if present, otherwise at the final reported day. Use `--include-pre-sowing` to include the entire year.
- `Rain_sum` = mm, `Radn_sum` = MJ/m², `ThermalTime_sum` = APSIM-reported °C-day (assuming the column's usual units); the others are **unweighted daily arithmetic means**, not flux sums. NO₃/NH₄ values are stocks, not crop nitrogen uptake. `AccEmTT` is retained as stage start/end points rather than summed.
- `WaterStress`, `TempStress`, and `NutrientStress` are kept as *raw APSIM-reported factors*; we do not invert these or label them as stress severity without verifying their model-specific scale and interpretation.
- If any daily input for a sum is missing, the stage sum is **null**, not an undercount presented as a full sum. Mean variables show observation coverage. Empty/NA/invalid numeric values are not substituted by zero.
- The tool rejects missing dates, duplicate dates, a missing Report, and multiple simulations/zones that could silently be mixed.
- Records after the last observed harvest event are excluded by default. If harvest was not recorded, the full remainder of the simulation window is retained and may include post-maturity periods; interpret accordingly.
- These outputs are **modeled environmental characterization** for the supplied weather, soil and management, not observed field environmental truth. Phase 2 must use actual site inputs for geographical inference.
- Existing output directories are allowed **only if the four target files do not exist**; files are not overwritten.

### Next extension

A multi-trial orchestration CLI can combine Phase 1–3 environment manifests with the Phase 4 stage tables. Stage alignment across trials should use documented developmental-stage definitions, not naive string comparisons.
