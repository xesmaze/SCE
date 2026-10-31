# SCE v2 integrated local test

This is a **candidate integration update**, not a stable release. Run on macOS with APSIM 2026 installed. The original template is not overwritten. This uses **USDA SDA point horizons**, not a nationwide gNATSGO raster. ERA5 is reanalysis, not site-measured weather.

## One year, reusing the known-good acquired inputs (offline)

```bash
python3 scripts/run_sce_integrated.py \
  --site site_illinois_v1/site_manifest.json \
  --year 2001 \
  --weather openmeteo_era5_illinois_2001_2010/weather.met \
  --soil-csv data/soil_cache/dfc3c56f88cdddcc/soil_layers.csv \
  --output sce_integrated_test_2001
```

## Online acquisition test (prompts have already been handled by site configuration)

```bash
python3 scripts/run_sce_integrated.py \
  --site site_illinois_v1/site_manifest.json --year 2001 \
  --output sce_integrated_online_2001
```

These commands create unique output directories. `--year` runs that year only. Native APSIM is invoked using the default macOS path; override with `--apsim` if needed. Outputs include staged APSIM model and DB, stdout/stderr logs, characterization CSVs, and `sce_run_manifest.json`.

## Assumptions

- Site metadata for previous crop/tillage are retained; residue and tillage effects not modeled.
- Profile extended at most 300 mm using last observed horizon when necessary (Fayette: 280 mm).
- SAT derived from bulk density assuming particle density 2.65 g/cm³.
- Organic carbon estimated as 0.58 × organic matter.
- AirDry and soybean LL estimated from LL15. KL/XF inherited; 100% PAWC initialization at DUL.
- The source's soil survey profile is not a field soil measurement; no independent soil nitrogen calibration is implied.
- APSIM physiological equations are never modified.
- POLARIS and station-weather CSV ingestion are **not yet implemented**.

Before release, confirm `_Messages` and simulated sow/maturity/harvest dates, and compare outputs with previous manual Fayette-ERA5 run. This archive was tested with Python only; native APSIM execution must occur locally.
