# SCE v2.0 — Phase 2: environmental initialization

Phase 2 **prepares** local APSIM environment copies for each trial from the Phase 1 `trials_manifest.json`. It does not run APSIM, fetch weather data, select sowing/cultivar settings, calibrate APSIM, or overwrite the validated SCE template.

## Inputs

1. Phase 1 manifest (`--manifest`), from `scripts/prepare_trials.py`.
2. SCE v2.0 validated base APSIMX (`--template`).
3. A JSON environment configuration (`--config`) mapping **every** trial ID to a local `.met`, a soil-donor `.apsimx`, and an initial-state JSON (see examples).
4. The donor `.apsimx` must contain exactly one `Models.Soils.Soil` with `Physical`, `Water`, `NO3`, and `NH4` children, and matching layer thicknesses. It must represent a **site-appropriate measured or independently characterized physical/hydraulic profile**; an example profile is not a substitute.
5. Initial state must provide arrays, each with exactly as many values as soil layers:
   - `nitrogen_units`: explicitly `"ppm"`.
   - `no3_ppm`, `nh4_ppm`: **concentration per layer** (not kg/ha).
   - `water_units`: explicitly `"mm/mm"`.
   - `water_mm_mm`: volumetric water per soil layer, checked against available `AirDry` / `SAT`.

APSIM 2026 `Models.Soils.Solute.InitialValues` with `InitialValuesUnits = 0` represents the ppm selection in the tested schema. This feature is explicitly limited to the `Soil/Solute` model (other APSIM legacy chemical schemas are not auto-converted). Soil organic carbon and the hydraulic profile are taken from the **complete soil donor** rather than fabricated from trial metadata. APSIM subsequently simulates water and N dynamics; site N is only initialized once.

For `.met` we check a daily APSIM-style `year day radn maxt mint rain` table, `tav` and `amp` constants, numerical range constraints, duplicate/missing days and planting-year presence. Weather spatial match is *not* automatically assumed (check station location separately). The full intended simulation time span is not yet known in Phase 2, so this is not a guarantee that the .met contains sufficient data for a future APSIM run.

## Example on Mac in PyCharm

Your existing Phase 1 example includes three trials. To stage all three, provide an entry for **each trial** with real local environmental data. The supplied `environment_config_example.json` illustrates just one trial and **cannot be used unchanged against the three-trial manifest**. The `site_initial_state_example.json` illustrates a two-layer profile only and must be replaced/extended to match your measured soil profile.

```bash
python3 scripts/prepare_environment.py \
  --manifest phase1_output/trials_manifest.json \
  --template template_models/Soy_Template_v2.0_APSIM2026.apsimx \
  --config examples/environment_config.json \
  --output-dir phase2_output \
  --repo-root .
```

Output includes `phase2_output/environment_manifest.json` and a staged `<trial_id>_environment.apsimx` per trial. Generated APSIMX files use **absolute local weather paths**, which are appropriate for local execution but not for redistribution; record the source paths and recreate staged runs on each computer. The initial APSIMX file and donor profiles remain unchanged. Existing nonempty outputs are never overwritten. If any trial fails validation, no partial final output is published.

**Phase 3 still needs to configure management and the correct maturity class.** The Phase 2 output is not yet a ready-to-run, site-calibrated soybean simulation.

## Tests

```bash
python3 -m unittest discover -s tests -p 'test_environment.py' -v
```

Local package tests exercise a synthetic 2-layer APSIMX structure, not native APSIM. A real Phase 2 staged model must be inspected and run with APSIM 2026 when Phase 3 management is configured. For a strictly reproducible release, capture provenance for measured soil, weather, and initial water/N.
