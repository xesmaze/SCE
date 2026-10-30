# SCE 2.0 — Python-first soybean seasonal characterization engine

SCE v2.0 extends the originally published Seasonal Characterization Engine with an APSIM 2026-compatible soybean template and early-maturity-group canopy and grain-fill adjustments.

**No R or Shiny required.** The v2 command-line interface runs a prepared APSIM model with the installed APSIM Next Generation executable and verifies the SQLite results.

## Quick start

```bash
python scripts/run_sce_v2.py \
  --model template_models/Soy_Template_v2.0_APSIM2026.apsimx \
  --apsim /Applications/APSIM2026.10.8138.0.app/Contents/Resources/bin/Models
```

This requires APSIM Next Generation 2026.10.8138.0, a configured soybean simulation, and accessible weather file. The `Report` SQLite database is created alongside the input model. R Shiny features (uploading multiple experiments, downloading weather and soil remotely, and seasonal-profile exports) are **not yet implemented** in this CLI; do not treat it as a feature-complete replacement of the upstream app.

## APSIM 2026 ReaperMan repair

Older SCE templates can fail with `CS1503` due to `IPlant` being passed where `INodeModel` is expected during `Crop.FindByPath` calls. The v2 template already incorporates this repair. To patch a legacy template safely:

```bash
python scripts/fix_reaperman_apsim2026.py \
  --input template_models/Soy_Template.apsimx \
  --output template_models/Soy_Template_APSIM2026.apsimx
```

This changes the manager declaration `[Link] IPlant Crop;` to `[Link] Models.PMF.Plant Crop;`, not APSIM's physiological functions. Source remains unchanged. Check a patched model with `--check`.

## Calibration and scope

All 30 maturity-class configurations share provisional `AreaLargestLeaf = 0.008`; only `mid000` and `mid00` have revised grain-fill targets. These values were informed by early maturity-group FIP 2017 trials. SCE v2 does not claim broad multi-MG physiological validation, automatic APSIM calibration, or Isaac Sim coupling.

## Roadmap

- Additional Python-native site weather, soil initialization and experiment CSV interface.
- Reproducible daily LAI, biomass, phenology and seasonal covariate export.
- **Optional Streamlit front end** using the same Python core, if web access is desired. Streamlit requires a Python-running server, not GitHub Pages alone.

See `RELEASE_NOTES_v2.0.0-rc1.md`, `docs/RELEASE_CHECKLIST.md`, and `docs/REPO_MIGRATION.md`.

**Original work:** Gilbert, Mandrini, Ersoz & Martin, *SoftwareX* 33 (2026), 102477. https://doi.org/10.1016/j.softx.2025.102477. Preserve original upstream authorship and license.
