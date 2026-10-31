# Seasonal Characterization Engine (SCE) v2.0.0-rc1

**Release candidate — CLI-first APSIM Next Generation 2026 compatibility**

SCE originally described crop environments by growth stage, using APSIM simulations through an R Shiny interface. This release candidate makes the validated **soybean APSIM template** directly accessible through a Python command-line workflow. **The R Shiny interface is legacy and is NOT required or supported by this release candidate.** It is retained in upstream history, not represented as fixed.

## New in v2.0.0-rc1

- APSIM Next Generation **2026.10.8138.0** compatible soybean template, including the `ReaperMan` compatibility repair documented below.
- Preserve the **30 existing SCE soybean maturity-class configurations**, with `Leaf.AreaLargestLeaf.FixedValue = 0.008` provisionally shared across classes.
- FIP-informed grain-fill adjustments for **two configurations only**: `mid000` 590 → 531 and `mid00` 600 → 480; other grain-fill targets unchanged.
- Pure-Python `scripts/run_sce_v2.py` to execute an **already configured** APSIMX simulation and verify its populated SQLite Report table; no R or Shiny dependency.
- `scripts/fix_reaperman_apsim2026.py`, a safe, idempotent repair utility for older `.apsimx` templates.
- Static model and regression tests, provenance and staging guidance for GitHub release.

## Important migration fix: ReaperMan and APSIM 2026

The original SCE soybean manager `ReaperMan` declares its crop reference as:

```csharp
[Link] IPlant Crop;
```

On APSIM Next Generation 2026.10.8138.0, the manager's calls to `Crop.FindByPath("Phenology.Stage")` and `Crop.FindByPath("Leaf.LAI")` failed to compile with `CS1503`: **cannot convert from `Models.Core.IPlant` to `APSIM.Core.INodeModel`**. The repaired field declaration is:

```csharp
[Link] Models.PMF.Plant Crop;
```

**Only this manager field type changes.** The fix does not replace physiology, modify crop calculations, or alter cultivar calibration parameters. The working SCE v2 template generated on the user's APSIM 2026 installation already contains the fix.

For any legacy template that still contains `IPlant Crop;`, run the included standalone script:

```bash
python scripts/fix_reaperman_apsim2026.py \
  --input template_models/Soy_Template.apsimx \
  --output template_models/Soy_Template_APSIM2026.apsimx
```

This deliberately **does not overwrite** the input. Re-running with identical output is a no-op. Check compatibility without writing:

```bash
python scripts/fix_reaperman_apsim2026.py \
  --input template_models/Soy_Template_v2.0_APSIM2026.apsimx --check
```

**A ReaperMan patch alone does not create SCE 2.0.** It only repairs one original manager for APSIM 2026. Use the staged, separately calibrated v2.0 template for the new leaf-area and GrainFill parameters.

## Running the new release without Shiny

With APSIM Next Generation installed and its `.met` weather file available:

```bash
python scripts/run_sce_v2.py \
  --model template_models/Soy_Template_v2.0_APSIM2026.apsimx \
  --apsim /Applications/APSIM2026.10.8138.0.app/Contents/Resources/bin/Models
```

The CLI requires an **already configured** model. Output is an APSIM SQLite `.db` next to the `.apsimx`. To avoid accidental data loss, the runner refuses to overwrite an existing `.db`. The upstream Shiny workflow's CSV import, remote weather/soil acquisition, and seasonal profile exports are **not yet fully reimplemented** in Python; those features must be developed and tested before claiming full application replacement.

## Evidence and limitations

- The working v2 soybean template and `ReaperMan` fix were executed with APSIM 2026.10.8138.0 on macOS, yielding a populated SQLite database.
- The exact v2.0 GitHub checkout still needs repository-level integration and release smoke testing.
- All 30 configurations have provisional leaf-area settings, but only `mid000`/`mid00` have FIP-informed grain-fill revisions. These do not imply 30 independent calibrations.
- R Shiny application remains unmaintained in this release. APSIM must be installed separately. This release does not bundle APSIM binaries.
- DigitalFields/Isaac Sim runtime feedback is experimental and not included in the stable SCE model release.

## Citation and license

Gilbert, C., Mandrini, G., Ersoz, E., & Martin, N. F. (2026). *The seasonal characterization engine, an application for describing environment from the perspective of crop development*. SoftwareX 33, 102477. https://doi.org/10.1016/j.softx.2025.102477

Original repository: https://github.com/CatherineGilbert/SCE

Preserve existing attribution and license in the upstream repository. Do not bundle APSIM binaries without reviewing their redistribution terms.
