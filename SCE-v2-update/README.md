# SCE v2 Integration Update — Local Test Overlay

This is an overlay for your existing `SCE-main` repository, **not a replacement of the whole repository**. It contains the revised `scripts/apply_usda_soil.py`, a standalone one-year end-to-end runner, one regression test, instructions and a small Fayette CSV fixture. No large data, .db files, or original model is included.

## Install safely on Mac

From SCE-main, extract archive to a temporary location first. Back up your current adapter, then copy only the new files:

```bash
cp scripts/apply_usda_soil.py scripts/apply_usda_soil.py.before_update
cp /path/to/SCE-v2-update/scripts/apply_usda_soil.py scripts/
cp /path/to/SCE-v2-update/scripts/run_sce_integrated.py scripts/
cp /path/to/SCE-v2-update/tests/test_soil_integration_update.py tests/
```

Run existing tests:

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

See `docs/INTEGRATED_RC_TEST.md` for the native APSIM/ERA5/Fayette command. Run with a new output directory. This update still relies on existing `sce.characterization`, `scripts/run_rotation_native.py`, and `scripts/acquire_usda_horizons.py` from your checkout.

## Verification

Python tests: 42 passed in the assembly environment. Soil adapter staging on the Fayette fixture passed, 263.02 mm initial PAWC; native APSIM must be tested on your Mac. USDA acquisition in the runner uses SDA point horizons, **not** a gNATSGO 10 m spatial raster. POLARIS and station CSV adapters are future work.
