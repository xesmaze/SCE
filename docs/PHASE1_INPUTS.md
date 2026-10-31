# SCE v2.0 — Phase 1 trial input

Phase 1 accepts the *original* SCE `Site, Planting, Latitude, Longitude, Crop, Genetics` CSV format (historical `Planting` dates `MM/DD/YYYY`), as well as `planting_date`, `maturity_group`, etc. Use `YYYY-MM-DD` or `MM/DD/YYYY`. The output is a standardized CSV and JSON manifest; **there is no APSIM execution, weather download, or soil processing yet**.

Run from the root of your PyCharm SCE checkout:

```bash
python3 scripts/prepare_trials.py --input examples/trials_example.csv --output-dir phase1_output
python3 -m unittest discover -s tests -p 'test_trials.py' -v
```

`--output-dir` can be created automatically but existing output files are never overwritten. The generated files are `trials_normalized.csv` and `trials_manifest.json`. Place `phase1_output/` in `.gitignore` if keeping results under your repository.

## Required fields

| Canonical | Original SCE | Validation |
|---|---|---|
| `site` | `Site` | Nonempty |
| `planting_date` | `Planting` | ISO or US month/day/year |
| `latitude`, `longitude` | `Latitude`, `Longitude` | Numeric, geographic bounds |
| `crop` | `Crop` | Soybean only in this release |
| `genetics` | `Genetics` | Explicit `early/mid/late` + MG or a raw maturity group |

Additional optional input fields: `trial_id` (otherwise generated), `year` (must match planting year), `weather_file`, `soil_file`. Unknown columns are preserved as per-record `_extras` in JSON, not as columns in the normalized CSV. Locations outside the US are allowed; Phase 1 never assumes SSURGO or Daymet availability.

**Maturity distinction:** raw genetics `II` or `2` is a maturity *group*, not a uniquely determined early/mid/late class. The program intentionally leaves `maturity_class` blank in that case; it does not silently assume `midII`. Existing model cultivar labels should be checked against the released APSIM template before Phase 3.

## Scope and release preparation

Do not commit runtime `phase1_output/` or experimental data. Phase 1 is independent of the existing verified `scripts/run_sce_v2.py`. Copy only `sce/__init__.py`, `sce/trials.py`, `scripts/prepare_trials.py`, `tests/test_trials.py`, `examples/trials_example.csv`, and `docs/PHASE1_INPUTS.md` into your SCE development branch. It is additive; no changes to original R files, current APSIM v2.0 template, or working runner.
