# SCEpy 2.0 — Installation and Usage Guide

**Release:** 2.0.0rc2 (prerelease)  
**Updated:** November 2, 2026  
**Repository:** https://github.com/xesmaze/SCE  
**Package:** https://pypi.org/project/scepy/

## What is SCE, and what is it for?

The **Seasonal Characterization Engine (SCE)** is a framework for describing growing environments in terms of the conditions a crop experiences **as it develops**, rather than relying only on calendar-year or growing-season averages. Two locations can have similar seasonal rainfall or temperature totals but expose plants to very different conditions during emergence, flowering, pod development, and grain filling. SCE translates that time-dependent variation into quantitative **environmental covariates** that can be compared across locations, years, and management scenarios.

**SCEpy** is the Python implementation of SCE. It connects site information, weather, soil properties, and crop-management settings to **APSIM Next Generation**, runs crop simulations, and summarizes APSIM's daily results within biologically meaningful developmental stages. APSIM remains the physiological simulation engine: SCEpy orchestrates the workflow and characterizes its outputs rather than replacing APSIM's crop-growth equations.

### What can SCE be used for?

- **Characterize trial environments:** quantify stage-specific heat, water availability, and stress conditions experienced by a crop in a given site-year.
- **Compare environments:** assemble consistent covariates across years and locations to identify similarities and differences that seasonal averages may obscure.
- **Support genotype-by-environment (G×E) analysis:** supply interpretable environmental descriptors for downstream statistical models of performance and adaptation; SCE does not itself establish genotype responses.
- **Evaluate scenarios:** explore how weather, soil, planting dates, and supported management inputs change the modeled sequence of crop-development conditions.
- **Prepare analysis-ready outputs:** convert daily APSIM simulation outputs into stage-level tables and multi-environment matrices for subsequent analysis.

**Current release scope:** SCEpy `2.0.0rc2` provides a validated soybean-oriented workflow using an APSIM 2026-compatible model template. It can acquire ERA5 weather and USDA soil information for a site, or use prepared inputs. Some site metadata choices, notably previous crop and tillage, are recorded but do not yet produce a fully modeled physical management effect; results should be interpreted as model-based environmental characterization, not direct field observations or independently validated predictions.

This walkthrough covers installing APSIM and SCEpy separately, configuring a site, running a first simulation, and locating the resulting environmental-characterization files.

## 1. Prerequisites

| Component | Requirement |
|---|---|
| Python | 3.10 or newer; 3.12 is suggested for new users |
| SCEpy | 2.0.0rc2 |
| APSIM Next Generation | Validated with 2026.10.8138.0; other releases require compatibility testing |
| .NET / OS libraries | As required by the installed APSIM release |
| Internet | For initial installation and optional ERA5 and USDA input acquisition |

SCEpy 2.0.0rc2 is published as a wheel and source distribution. It is distributed under CC BY-NC-SA 4.0; APSIM licensing and installation are separate.

## 2. Install APSIM Next Generation

Download APSIM **Next Generation** from https://www.apsim.info/download-apsim/downloads/ (not APSIM Classic).

### macOS

Follow https://docs.apsim.info/docs/install/macos . The APSIM instructions describe the required .NET SDK and Homebrew GTK libraries. For the documented macOS installation, APSIM specifies the x64 .NET 8 SDK, including on Apple Silicon; check the instructions for your APSIM release.

Verify your installation:

```bash
dotnet --list-sdks
find /Applications -path '*/Contents/Resources/bin/Models' -type f
```

The validated APSIM binary path for the development test machine is:

```text
/Applications/APSIM2026.10.8138.0.app/Contents/Resources/bin/Models
```

### Windows

Install APSIM Next Generation using the official Windows installer. The executable is typically:

```text
C:\Program Files\APSIM<version>\bin\Models.exe
```

### Linux

Follow https://docs.apsim.info/docs/install/linux . APSIM documents `/usr/local/bin/Models` as a standard executable location. Confirm it is available with `command -v Models`.

APSIM CLI reference: https://docs.apsim.info/docs/usage/commandline/command-line-basics

## 3. Install SCEpy in an isolated Python environment

### macOS / Linux

```bash
python3.12 -m venv scepy-env
source scepy-env/bin/activate
python -m pip install --upgrade pip
python -m pip install 'scepy==2.0.0rc2'
```

### Windows PowerShell

```powershell
py -3.12 -m venv scepy-env
.\scepy-env\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install 'scepy==2.0.0rc2'
```

Confirm installation:

```bash
python -m pip show scepy
scepy --help
scepy run --help
```

If `scepy` is not found, ensure the virtual environment is active. You do not need to clone the repository to use the installed CLI or its packaged soybean template.

## 4. Tell SCEpy where APSIM is

SCEpy searches an explicit `--apsim` path, the `APSIM_MODELS` environment variable, installed APSIM macOS applications, then a `Models` program in PATH.

Optional permanent setting, macOS example:

```bash
export APSIM_MODELS='/Applications/APSIM2026.10.8138.0.app/Contents/Resources/bin/Models'
```

Windows PowerShell example (replace with actual installed version):

```powershell
$env:APSIM_MODELS = 'C:\Program Files\APSIM<version>\bin\Models.exe'
```

Linux example:

```bash
export APSIM_MODELS="$(command -v Models)"
```

You can always override the setting for an individual run using `--apsim /actual/path/to/Models`.

## 5. First complete run: site → ERA5 weather + USDA soil → APSIM → characterization

Work in a new local directory so results stay together:

```bash
mkdir scepy-first-run
cd scepy-first-run
```

### Create an Illinois example site manifest

```bash
scepy site \
  --site-id Illinois_Example \
  --latitude 40.763960462877 \
  --longitude -89.7398359674323 \
  --start-year 2001 \
  --end-year 2001 \
  --weather era5 \
  --soil gnatsgo \
  --previous-crop corn \
  --tillage no_till \
  --planting drill \
  --output-dir site_illinois_2001
```

The site command writes `site_illinois_2001/site_manifest.json`. Note: although its source selector is called `gnatsgo`, the integrated runner's automatic point-based USDA soil acquisition uses **USDA Soil Data Access horizon data**, not a downloaded gNATSGO raster.

### Run the complete integrated simulation

```bash
scepy run \
  --site site_illinois_2001/site_manifest.json \
  --year 2001 \
  --output first_run_2001
```

This command downloads ERA5 weather using Open-Meteo and point-based USDA soil horizons, stages the packaged APSIM soybean template, configures sowing, invokes APSIM Next Generation's `Models` program, and characterizes the APSIM daily reporting database.

The default cultivar is `mid000`. Default management in the runner is an April 12 sowing date, 40 plants/m², 30 mm sowing depth, and drill row spacing of 190 mm, unless overridden. Sowing defaults can be customized:

```bash
scepy run \
  --site site_illinois_2001/site_manifest.json \
  --year 2001 \
  --cultivar mid000 \
  --sowing-date 2001-04-12 \
  --population 40 \
  --spacing-mm 190 \
  --depth-mm 30 \
  --output first_run_custom_2001
```

**Important:** Output directories must be new. Do not reuse `first_run_2001` if it already exists.

### Offline / previously acquired input alternative

Supply an APSIM-formatted weather file and an SCEpy-standardized USDA horizon CSV:

```bash
scepy run \
  --site site_illinois_2001/site_manifest.json \
  --year 2001 \
  --weather /path/to/weather.met \
  --soil-csv /path/to/soil_layers.csv \
  --output first_run_cached_2001
```

The weather file must cover the simulated year; arbitrary weather-station CSV files must first be converted to APSIM `.met`. The soil CSV must match the expected soil-adapter schema; it is not an arbitrary soil-test table.

## 6. Outputs and validation

Successful completion prints JSON with `status: PASS`, an APSIM daily `Report` row count, the configured `.apsimx` path, SQLite database path, and characterization directory.

Expected output layout resembles:

```text
first_run_2001/
  SCE_configured.apsimx
  SCE_configured.db
  soil_staged.apsimx
  apsim_stdout.log
  apsim_stderr.log
  sce_run_manifest.json
  weather/
    weather.met
  soil_cache/
    <cache-key>/soil_layers.csv
  characterization/
    ... characterization outputs ...
```

The manifest captures site and year, selected management choices, input paths and SHA-256 fingerprints. The APSIM SQLite database contains daily `Report` values. Characterization aggregates daily results by growth stage into environmental covariates and stress-factor descriptors.

An example terminal check:

```bash
python - <<'PY'
import json
from pathlib import Path
p = Path('first_run_2001/sce_run_manifest.json')
m = json.loads(p.read_text())
print('Site:', m['site_id'])
print('Year:', m['year'])
print('Report days:', m['reported_days'])
print('Database:', m['db'])
print('Weather:', m['weather'])
print('Soil:', m['soil_csv'])
PY
```

In the validated Illinois 2001 test, APSIM returned **365 daily report rows**. Other years may have 365 or 366 rows. A simulation returning PASS verifies technical completion, not agreement with measured data.

## 7. Other SCEpy CLI commands

| Command | Function |
|---|---|
| `scepy site --help` | Create a site manifest |
| `scepy weather --help` | Download Open-Meteo historical weather as APSIM `.met` |
| `scepy soil --help` | Query/cache USDA soil horizon information |
| `scepy soil-stage --help` | Apply standardized horizon layers to an APSIM template |
| `scepy run --help` | Run the integrated pipeline |
| `scepy characterize --help` | Characterize an existing APSIM simulation database |
| `scepy batch --help` | Process sets of simulations |
| `scepy wide --help` | Produce a wide simulation-by-covariate export |

Use each command's `--help` option for required arguments rather than assuming standalone commands use the same options as `scepy run`.

## 8. Troubleshooting

**`scepy: command not found`:** Activate the virtual environment and retry `scepy --help`.

**Python version incompatible:** Create a new environment with Python 3.10+; Python 3.12 is recommended for a fresh installation.

**`APSIM Models executable not found`:** Inspect `find /Applications ...` on macOS or locate `Models.exe` on Windows. Supply `--apsim` or `APSIM_MODELS` pointing to the actual executable.

**APSIM template not found:** The installed wheel should contain `sce/assets/Soy_Template_v2.0_APSIM2026.apsimx`; reinstall SCEpy or pass `--template` with a compatible local `.apsimx` file.

**Output already exists:** Select a new `--output` directory, preserving the prior run.

**ERA5/USDA acquisition fails:** Check internet service and remote provider availability. Retry with previously acquired `--weather` and `--soil-csv` files to avoid another fetch.

**APSIM simulation failure:** Review `apsim_stdout.log` and `apsim_stderr.log` in the output directory. Check APSIM version compatibility and the template's model/cultivar assumptions.

**macOS APSIM GUI fails to open:** Follow the APSIM .NET/GTK dependency instructions and inspect APSIM's macOS guidance. CLI success does not require the graphical interface to be open.

## 9. Scientific scope and assumptions

- The tested implementation is **soybean-oriented**, centered on the packaged SCE/2026 APSIM template; it is not a general crop model generator.
- APSIM's existing physiology remains active. SCEpy prepares inputs and invokes APSIM rather than replacing physiological equations.
- Open-Meteo ERA5 is a **reanalysis estimate**, not measured local station observations.
- The integrated USDA soil adapter uses point-based survey horizons and assumptions, including provisional soil crop LL from survey LL15, default 100% plant-available water at DUL, extension of the deepest horizon when needed, and KL/XF values inherited from the template. These are not field-calibrated initial conditions.
- Previous crop and tillage settings are currently **metadata**, not implemented residue/tillage physics.
- Stage-level stress-factor deficits are model-derived diagnostics, not observed stress severity or direct yield-loss estimates.
- Other APSIM versions, OS configurations and cultivars have not all been validated as thoroughly as the macOS 2026 soybean example.

## 10. Links

- SCEpy PyPI: https://pypi.org/project/scepy/
- SCE GitHub: https://github.com/xesmaze/SCE
- APSIM downloads: https://www.apsim.info/download-apsim/downloads/
- APSIM macOS setup: https://docs.apsim.info/docs/install/macos
- APSIM Linux setup: https://docs.apsim.info/docs/install/linux
- APSIM CLI reference: https://docs.apsim.info/docs/usage/commandline/command-line-basics

