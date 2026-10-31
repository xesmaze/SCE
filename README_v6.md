# SCE v2.0 — Multi-year APSIM integration + wide covariate matrix

A small additive update for `develop/sce-v2.0`. **This package does not replace** the earlier Phase 4 `sce/characterization.py` or Phase 5 `sce/batch.py` and does not alter the validated SCE soybean template.

## Install in PyCharm

Merge only these files into the existing SCE repository:

- `sce/multiyear.py`
- `sce/wide.py`
- `scripts/run_multiyear.py`
- `scripts/export_wide.py`
- `tests/test_multiyear_wide.py`

Keep your existing `scripts/characterize_batch.py`, `sce/batch.py`, and Phase 4 source.

## Step 1. Tests

```bash
python3 -m unittest discover -s tests -p 'test_multiyear_wide.py' -v
```

## Step 2. Simulate 2001, 2005 and 2010

```bash
python3 scripts/run_multiyear.py \
  --template template_models/Soy_Template_v2.0_APSIM2026.apsimx \
  --apsim '/Applications/APSIM2026.10.8138.0.app/Contents/Resources/bin/Models' \
  --output-dir multiyear_2001_2005_2010
```

The command creates **three independent run directories** with separately named `.apsimx` and `.db` files and a top-level `multiyear_manifest.json`. It explicitly sets the model clock to Jan 1–Dec 31 for each year, sets the sowing manager's fixed `SowDate` to `12-apr`, chooses `mid000`, population 40 plants/m², row spacing 500 mm, depth 30 mm, and **disables inherited fertilizer/tillage manager nodes**. The source model's relative weather filename `z_12.met` is resolved against its directory and converted to an absolute path in *staged copies only*. Full-year daily weather coverage is checked before runs. APSIM must report a sowing event on April 12 of each year, or the command exits with an error. It never overwrites a previous run directory.

**This is a controlled example, not geographically anchored calibration**. The source SCE example soil and initial soil nitrogen are inherited. For measured site conditions use the Phase 2 initializer instead.

For a non-executing dry run (e.g. to inspect configuration):

```bash
python3 scripts/run_multiyear.py --dry-run --output-dir multiyear_preview
```

## Step 3. Batch characterization using validated Phase 4/5

The previous command creates `multiyear_2001_2005_2010/batch_config.json` with absolute paths to the 3 SQLite databases. Now run:

```bash
python3 scripts/characterize_batch.py \
  --config multiyear_2001_2005_2010/batch_config.json \
  --output-dir multiyear_2001_2005_2010/characterization
```

You should see `n_runs: 3` in the manifest. Data include stages, daily trajectories, stage comparisons, stress factors, and hashes.

## Step 4. Create one-row-per-run wide stage covariates

```bash
python3 scripts/export_wide.py \
  --stages multiyear_2001_2005_2010/characterization/batch_stages.csv \
  --output multiyear_2001_2005_2010/characterization/environment_matrix_wide.csv
```

This creates one row per simulation. The column names use `StageName__occurrenceNN__covariate`, e.g., `EarlyPodDevelopment__occurrence01__WaterStress_deficit_factor_days`. This intentionally preserves *repeated* stage occurrences rather than averaging them. Missing stages remain blank. `harvest_transition` records are not treated as developmental stages.

For multivariate models with strictly shared column sets, select columns with complete coverage across runs after inspecting the matrix (do not silently fill missing stage values with zeros).

## Verify

In PyCharm:

```python
import pandas as pd
folder='multiyear_2001_2005_2010/characterization'
print(pd.read_csv(f'{folder}/run_summary.csv').to_string(index=False))
wide=pd.read_csv(f'{folder}/environment_matrix_wide.csv')
print('wide dimensions:', wide.shape)
print(wide[['run_id','year','cultivar']].to_string(index=False))
```

## Notes

- This integration runner uses your **verified SCE Sowing Manager parameters** and leaves `CodeArray` unchanged.
- The three simulations are not cross-validation and do not re-calibrate APSIM.
- The included tests use generated fixtures; native APSIM runs must be performed on your Mac.
- Do not commit `multiyear_2001_2005_2010/` output databases to Git; add `multiyear_*/` to `.gitignore`.
- Once this passes, the remaining stable-release work is a combined Phase 1–5 entry point, explicit environment provenance and versioned install documentation.
