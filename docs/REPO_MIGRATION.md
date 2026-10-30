# SCE v2: migration from Shiny to a Python-first release

The original repository contains a legacy R Shiny interface (`app.R`, `apsimx.R`, `renv.lock`, `Dockerfile`). **Do not attempt to repair these as part of the initial v2 release.** Keep their history, and state explicitly that v2.0 supports the native APSIM model and Python CLI instead. A separate optional Streamlit front end can be developed later.

## Git branch preparation

```bash
git clone https://github.com/CatherineGilbert/SCE.git SCE-v2
cd SCE-v2
git switch -c release/sce-v2.0.0
```

Use a fork or repository with actual contributor permission, never publish to the original without authorization. Copy `scripts/`, `tests/`, `docs/`, `.github/workflows/`, the README and release notes from the included package.

## Stage the already-validated APSIM v2 template

```bash
python scripts/stage_v2_template.py \
  --source /Users/elhan/PycharmProjects/DigitalFields/external/SCE-main/template_models/Soy_Template_v2.0_APSIM2026.apsimx \
  --checkout .
python scripts/validate_sce_v2.py --repo .
python scripts/fix_reaperman_apsim2026.py \
  --input template_models/Soy_Template_v2.0_APSIM2026.apsimx --check
```

The original SCE v1 template is preserved. If you need to repair v1 separately, run:

```bash
python scripts/fix_reaperman_apsim2026.py \
  --input template_models/Soy_Template.apsimx \
  --output template_models/Soy_Template_APSIM2026.apsimx
```

This only repairs ReaperMan; it does not add the v2 cultivar overrides.

## Native APSIM command line (no R or Shiny)

```bash
python scripts/run_sce_v2.py \
  --model template_models/Soy_Template_v2.0_APSIM2026.apsimx \
  --apsim /Applications/APSIM2026.10.8138.0.app/Contents/Resources/bin/Models
```

The model must already reference valid local weather and management. `run_sce_v2.py` intentionally refuses overwriting an existing database; rename or remove the old report only if you intentionally want to rerun. No remote weather, soil or maturity-group calibration API is claimed yet.

## Push for review (do not automatically publish)

```bash
python -m unittest discover -s tests -v
git add scripts/ tests/ docs/ .github/workflows/ RELEASE_NOTES_v2.0.0-rc1.md README_v2.md template_models/Soy_Template_v2.0_APSIM2026.apsimx
git commit -m "Prepare SCE v2 CLI and APSIM 2026 compatibility release"
git push -u origin release/sce-v2.0.0
```

Only tag after completing the release checklist. The optional browser UI is a separate planned component, not a v2 prerequisite.
