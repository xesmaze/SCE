# SCE v2.0.0-rc1 — install and reproduce the three-year example

## Scope

The release candidate is **Python CLI-first**. The original R Shiny application is retained in repository history but **not used** by the supported Python workflow. SCE runs against a separately installed **APSIM Next Generation 2026.10.8138.0** executable; no APSIM binary is distributed here.

Verified in the user's macOS APSIM installation: `mid000` at the example Illinois site with `z_12.met` (2001, 2005, 2010). Same management: fixed April 12 sowing, 40 plants/m², 500 mm row spacing, 30 mm sowing depth. Example fertilizer/tillage managers disabled. This is *not* a measured, geographically calibrated soil/N experiment, nor a cross-validation exercise.

## Prerequisites

- Python 3.10+ and the standard library for the CLI and basic tests; `pandas` for notebook analysis.
- APSIM Next Generation installed separately. The verified binary is `/Applications/APSIM2026.10.8138.0.app/Contents/Resources/bin/Models` on macOS; substitute your actual installed binary.
- A cloned repository containing `template_models/Soy_Template_v2.0_APSIM2026.apsimx` **and** `template_models/z_12.met`.
- Sufficient local disk space for three SQLite databases and per-day outputs.

## Validate release files

```bash
python3 scripts/check_sce_release.py --run-tests
python3 scripts/validate_sce_v2.py --v2 template_models/Soy_Template_v2.0_APSIM2026.apsimx
```

`check_sce_release.py` performs a non-destructive file check and runs seven test files. `validate_sce_v2.py` validates the v2 cultivar definitions, limited GrainFill revisions and the ReaperMan repair. Neither substitutes for running APSIM.

## ReaperMan compatibility

The v1 manager declared `[Link] IPlant Crop;`; this breaks `FindByPath` usage with the targeted APSIM 2026 API. The v2 model includes `[Link] Models.PMF.Plant Crop;` and the standalone idempotent repair tool is included for existing copies:

```bash
python3 scripts/fix_reaperman_apsim2026.py \
  --input template_models/Soy_Template.apsimx \
  --output template_models/Soy_Template_APSIM2026.apsimx
```

This repair does **not** perform v2 cultivar calibration. It should not overwrite source files.

## Run the three-year diagnostic (separate outputs)

```bash
python3 scripts/run_multiyear.py \
  --template template_models/Soy_Template_v2.0_APSIM2026.apsimx \
  --apsim '/Applications/APSIM2026.10.8138.0.app/Contents/Resources/bin/Models' \
  --output-dir multiyear_2001_2005_2010
```

The runner validates weather-year coverage, stages separate APSIMX files, and generates the configuration for batch processing. It will refuse to replace existing outputs: choose a new output directory on subsequent runs.

```bash
python3 scripts/characterize_batch.py \
  --config multiyear_2001_2005_2010/batch_config.json \
  --output-dir multiyear_2001_2005_2010/characterization

python3 scripts/export_wide.py \
  --stages multiyear_2001_2005_2010/characterization/batch_stages.csv \
  --output multiyear_2001_2005_2010/characterization/environment_matrix_wide.csv

python3 scripts/check_sce_release.py \
  --wide multiyear_2001_2005_2010/characterization/environment_matrix_wide.csv
```

### Reference outcomes, diagnostic dataset only

| Year | Sowing | Harvest | Season days | Phenological stages | Harvest transitions | Rain (mm) | Thermal time (°C·d) |
|---|---|---|---:|---:|---:|---:|---:|
| 2001 | Apr 12 | Aug 28 | 139 | 11 | 1 | 307 | 1215.564205 |
| 2005 | Apr 12 | Aug 12 | 123 | 11 | 1 | 375 | 1216.702806 |
| 2010 | Apr 12 | Aug 27 | 138 | 11 | 1 | 537 | 1226.648420 |

For this example the wide output had **3 distinct simulations, 595 numeric covariates, zero missing entries, no infinite values**. The early-pod `WaterStress_deficit_factor_days` values matched the long stage summaries: 2.462758 (2001), 0.142725 (2005), and 0 (2010) to displayed precision. These outcomes were user-executed, not independently re-run in this packaging environment.

## Outputs and interpretation

- **Daily**: complete observed daily APSIM reporting fields and stress-factor trajectories for crop-active periods.
- **Stage**: contiguous stage episodes, including repeated episodes as separate occurrences.
- **Covariates**: per-stage radiation/rainfall/thermal-time sums, state/stress factor means, coverage counts, and duration-aware factor deficit descriptors.
- **Wide**: one row per run, with `StageName__occurrenceNN__covariate` columns; missing stages are missing, not zero.
- **Provenance**: per-source filenames and SHA-256 fingerprints in the batch manifest.

The current implementation treats reported `WaterStress`, `TempStress`, and `NutrientStress` as model-supplied factors. The derived `sum(1-factor)` has **factor-day** units *provided* the source factor is a [0,1] growth multiplier where 1 means unconstrained. It is a diagnostic descriptor, **not observed stress severity, water use, N uptake, or predicted yield loss**. The exact APSIM report-variable expressions and their physiological roles require a version-specific audit before stronger statements can be made.

## Known limitations

1. The **fully general** Phase 1 trial CSV → measured site soil/weather → Phase 2 APSIMX → Phase 3 management → native run → Phase 4/5 command is not yet one integrated general-purpose CLI. Modules and tests exist but per-site orchestration and real input data validation still require user configuration.
2. The 2001/2005/2010 diagnostic inherits an **example** soil and initial nitrogen; it does not establish site-specific calibration.
3. Data acquisition from remote NASA POWER, Daymet, CHIRPS or soil APIs is **not implemented** in the Python CLI; supply local files.
4. The 30 named maturity classes have not been independently calibrated across environments. Leaf area 0.008 is provisional across them; revised grain fill is limited to `mid000`/`mid00`.
5. The runtime geometry feedback work for DigitalFields/Isaac Sim is separate and **not part of SCE v2.0.0-rc1**.
6. Only one environment/cultivar combination has been tested across three weather years here. Reproducibility on other APSIM versions, OSs, sites or crops remains to be evaluated.

## GitHub release sequence

Work on `develop/sce-v2.0`. Run the tests and verify release files are committed without simulation databases. Open a PR targeting **your fork's** `main`; do not merge into the original `CatherineGilbert/SCE` upstream. After review and CI, tag `v2.0.0-rc1` in your fork. Reserve `v2.0.0` for a stable release after the documented acceptance criteria are met.
