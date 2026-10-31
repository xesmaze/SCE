# SCE v2.0.0 CLI-first release checklist

The Python CLI and validated APSIM soybean template form the initial **v2.0 release surface**. R Shiny is legacy and **not required** for this release. Do not claim original Shiny feature parity until its CSV → weather → soil → seasonal report workflow is reimplemented in Python.

## Repository and licensing
- [ ] Confirm maintainer access to `CatherineGilbert/SCE` or create an attributable fork; use `release/sce-v2.0.0` branch.
- [ ] Preserve git history, original LICENSE and software citation. Review APSIM redistribution terms (do not bundle binaries).
- [ ] Include the actual locally successful `template_models/Soy_Template_v2.0_APSIM2026.apsimx` in the release branch.
- [ ] Do not publish generated `.db`, large site weather, proprietary assets or local paths as source.

## ReaperMan compatibility
- [ ] Include `scripts/fix_reaperman_apsim2026.py` and its tests.
- [ ] Include the compatibility note and explicit instructions in release notes.
- [ ] Confirm patch check on v2 template returns **ALREADY COMPATIBLE**.
- [ ] Confirm a pristine v1 template can be patched into a distinct v1-compatible copy without changing the original.

## APSIM v2 model
- [ ] `python scripts/validate_sce_v2.py --repo .` passes on 30 cultivar entries.
- [ ] Run native APSIM 2026.10.8138.0 on the packaged v2 model. Check exit code 0 and nonempty `Report` database.
- [ ] Check actual active cultivar, sowing, maturity and harvest fields, and `_Messages` error content.
- [ ] If advertised, verify LAI and biomass report columns exist and contain values; don't claim them from static model inspection.
- [ ] Avoid presenting early-MG calibration as validation of all other MGs.

## Python interface
- [ ] `python -m unittest discover -s tests -v` passes.
- [ ] `python scripts/run_sce_v2.py --help` works without R or Shiny.
- [ ] Run `python scripts/run_sce_v2.py --model ... --apsim ...` on an output-free copy of the template.
- [ ] Test any additional CLI inputs and downloads before documenting them; current runner runs configured APSIMX, not the old Shiny environment retrieval pipeline.
- [ ] Specify installation, APSIM binary path, weather file, site soil and nitrogen expectations.

## Public release
- [ ] Publish `v2.0.0-rc1` to document new functionality and compatibility limits; collect reproducible logs.
- [ ] Publish stable `v2.0.0` only after APSIM execution and Python CLI tests against the exact tagged checkout.
- [ ] Include full command-line examples, release notes, and an archive DOI when ready.

## Scope
No DigitalFields/Isaac Sim feedback coupling in the SCE stable release. Retain separate experimental branch.
