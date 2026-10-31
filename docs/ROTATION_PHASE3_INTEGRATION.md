# Rotation default → Phase 3 → APSIM integration

This is a **bridge**, not a full automatic soil-residue initialization. It converts user-selected previous crop and tillage into an explicit Phase 3 configuration, stages a model without editing the source, and optionally executes APSIM with the verified binary. The chosen previous crop and tillage are recorded as **provenance only**: no residue mass or mineral-N values are inferred. Existing inherited fertilizer and tillage managers are disabled. Crop physiology is unchanged.

## Run in PyCharm (from SCE root)

After extracting/merging `scripts/` and `docs/`:

```bash
python3 scripts/prepare_rotation_management.py \
  --input examples/rotation_management_example.json \
  --output-dir rotation_config_demo
```

You need a Phase 2 `environment_manifest.json` **whose trial ID matches** `IL_2001_mid000` in the example rotation configuration. Phase 2 environments must be real initialized models, not the generic template. Use the verified `z_12.met` soil as a diagnostic example if appropriate; do not call it geographic calibration.

```bash
python3 scripts/run_rotation_phase3.py \
  --environment-manifest phase2_output/environment_manifest.json \
  --rotation-config examples/rotation_management_example.json \
  --output-dir rotation_phase3_smoketest \
  --apsim '/Applications/APSIM2026.10.8138.0.app/Contents/Resources/bin/Models'
```

This configuration sets `no_till` → `drill`, 0.19 m spacing → APSIM `RowSpacing=190` mm, sowing depth 30 mm, population 40 plants/m², and `mid000` on 12 April 2001. `--apsim` is optional; omit to stage and inspect without executing.

### Key guardrails

- Never overwrite an existing output directory; choose a fresh `--output-dir` on reruns.
- Do not use `--apsim` until the Phase 2 manifest's soil and weather paths are valid.
- The selected `no_till` is currently a **management label** plus a decision to disable the example tillage manager. Physical residue/tillage modeling is not yet implemented.
- No automatic fertilizer; APSIM owns its soil-N dynamics and uses the initial soil pools in the Phase 2 profile.
- The same cultivar and sowing date are only an integration test; outputs are not yield validation.
