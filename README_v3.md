# SCE v2.0 Phase 3 — Cultivar and management configuration

Phase 3 uses **Phase 2's `environment_manifest.json`** and an explicit per-trial management configuration to produce non-destructive APSIM model copies. It does **not** run APSIM or modify the validated v2.0 template.

## Why an inspection step is required

The original SCE APSIM template uses C# manager code for sowing. The exact C# source and API contracts of your local APSIM 2026 model are not bundled in this package. Therefore we **must not guess** the manager name or search-and-replace arbitrary numeric values. The CLI supports an *inspection pass* to reveal manager source and an exact-match mutation pass, where every requested edit must match **exactly one** occurrence.

### 1. Install

Copy/merge `sce/management.py`, `scripts/prepare_management.py`, `tests/test_management.py`, and `examples/management_config_example.json` into the corresponding directories of the SCE project. Do not overwrite Phase 1/2 or other files. Stay on `develop/sce-v2.0`.

### 2. Run tests

```bash
python3 -m unittest discover -s tests -p 'test_management.py' -v
```

Four synthetic regression tests cover isolation of source models, explicit controls, missing cultivar classification, ambiguous manager edits, and weather-window bounds. **No native APSIM run is claimed.**

### 3. Inspect your local Phase 2 model

```bash
python3 scripts/prepare_management.py --inspect phase2_output/Trial_A_2017/Trial_A_2017_environment.apsimx > phase3_manager_inventory.json
```

If the Phase 2 manifest has not yet been created from real weather/soil and initial-state inputs, complete the Phase 2 integration first. The original v2 template can be inspected instead:

```bash
python3 scripts/prepare_management.py --inspect template_models/Soy_Template_v2.0_APSIM2026.apsimx > phase3_manager_inventory.json
```

Look at `managers[].name`, `managers[].code` and `managers[].parameters` to locate the **actual sowing manager** and confirm existing variable types. Its code may use fixed dates, sowing windows or external manager parameters; select only a compatible exact substitution.

### 4. Define trial management (verified edit mapping)

Copy `examples/management_config_example.json` to `examples/management_config.json` and replace all `EXACT_...` placeholders with **actual C# source substrings** observed in the inventory. Explicitly set cultivar (`early/mid/late` + MG), planting date, simulation start/end, population (plants/m²), row spacing (m) and sowing depth (mm). Ensure the required tokens correspond to changed manager expressions, not merely comments.

**The example file is a schema illustration and cannot be executed unchanged.** Cultivar classes such as `II` without an early/mid/late subdivision deliberately fail. The software does not claim to infer class from latitude or genotype name.

For a valid trial, the config must include `manager_edits` with a manager name and `code_replacements`, plus `required_code_tokens` confirming the configured cultivar/date/population/spacing/depth. Existing C# physiology and all cultivar commands remain untouched except for the explicitly approved manager edits.

### 5. Stage

```bash
python3 scripts/prepare_management.py \
  --environment-manifest phase2_output/environment_manifest.json \
  --config examples/management_config.json \
  --output-dir phase3_output
```

This creates `phase3_output/management_manifest.json` and `phase3_output/<trial_id>/<trial_id>_configured.apsimx`. Output directories are never overwritten. All edits are tracked against source model SHA-256. No APSIM run occurs until the user invokes `scripts/run_sce_v2.py` against a generated model. **Verify native sowing dates, cultivar, population and physiological stage reporting on your installed APSIM 2026 before treating models as operational.**

## Remaining for a fully automatic Phase 3

An adapter specific to the verified sowing manager in your SCE v2.0 template can automatically generate the `manager_edits` for common input fields. The exact C# manager source needs to be inspected first. This release is the conservative structural and validation foundation, **not** an automatically inferred manager replacement.
