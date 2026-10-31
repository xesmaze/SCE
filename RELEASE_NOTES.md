# SCE v2.0.0-rc1 — Python-Based Seasonal Characterization Engine

**Release type:** Release Candidate (Pre-release)

## Overview

SCE v2.0 modernizes the Seasonal Characterization Engine by introducing a Python-based workflow for environmental characterization using APSIM Next Generation.

This release replaces the original R Shiny-dependent workflow with Python scripts and command-line interfaces, supporting reproducible simulation, environmental data acquisition, phenology-aligned characterization, and multi-environment comparisons.

The original SCE framework and its scientific objectives are preserved while improving compatibility with modern APSIM versions and enabling integration into computational research pipelines.

## Major Features

### 1. APSIM Next Generation 2026 Compatibility

- Updated soybean simulation template for APSIM Next Generation 2026.
- Preserved the existing APSIM physiological and crop-development models.
- Implemented compatibility corrections for the `ReaperMan` manager.
- Supports configurable soybean cultivar maturity groups, sowing dates, planting density, row spacing, and sowing depth.
- Supports native APSIM execution and SQLite report extraction.

### 2. Automated Weather Acquisition

- Integrated Open-Meteo's Historical Weather API.
- Uses ERA5 reanalysis as the default historical weather source.
- Automatically generates APSIM-compatible `.met` files.
- Retrieves daily solar radiation, maximum and minimum temperatures, and precipitation.
- Includes input validation, source metadata, and provenance records.

**Weather data disclaimer:** ERA5 provides spatially consistent historical weather estimates but may differ from conditions observed at individual field sites. These differences can affect simulated crop development, environmental stress, and seasonal characterization. Researchers conducting site-specific studies are encouraged to use reliable local weather observations when available.

Existing APSIM `.met` files can be used directly. Automated weather-station CSV conversion is planned for a later release.

### 3. Automated USDA Soil Data Acquisition

- Retrieves soil survey information using USDA-NRCS Soil Data Access.
- Uses site latitude and longitude to identify soil map units.
- Downloads soil component and horizon properties without requiring large national raster datasets.
- Selects a representative soil component based on reported component prevalence and available horizon information.
- Preserves source identifiers, soil attributes, and provenance.

The soil acquisition workflow retrieves site-specific survey profiles. It does not claim that survey horizons represent direct measurements from the experimental field.

### 4. APSIM Soil Profile Initialization

- Converts soil horizons into APSIM-compatible layered soil properties.
- Supports depth-weighted mapping onto the existing APSIM soil-layer structure.
- Validates hydraulic limits and layer consistency.
- Initializes soil water using documented assumptions.
- Preserves APSIM's existing soil-water, carbon, nitrogen, and crop-process equations.

Where required, the workflow records assumptions such as extension of the deepest soil horizon, estimated saturation, crop-specific lower-limit initialization, and initial plant-available water.

### 5. Rotation and Planting Management

Supports configurable management selections, including:

- Previous crop in rotation.
- Conventional tillage, no-till, or strip-till.
- Drilled or planter-based soybean establishment.
- Plant population, row spacing, and sowing depth.

Previous crop and tillage selections are currently retained as management scenario metadata. Their detailed effects on residue and soil processes are reserved for future versions.

### 6. Seasonal Environmental Characterization

Provides phenology-aligned environmental characterization using APSIM simulation outputs.

Includes:

- Daily environmental covariates.
- Developmental-stage summaries.
- Accumulated rainfall and thermal time.
- Temperature, nutrient, and water-stress factors.
- Stress-duration and cumulative-deficit metrics.
- Harvest-transition handling.
- Simulation metadata and provenance.

Environmental characterization follows APSIM-derived developmental stages rather than fixed calendar periods.

### 7. Multi-Environment Analysis

- Batch characterization of multiple APSIM simulations.
- Cross-environment developmental-stage comparisons.
- Wide-format environmental covariate matrices for downstream statistical analysis.
- Reproducible exports supporting genotype-by-environment research.

### 8. Unified Python Execution

Introduces an integrated runner connecting site configuration, weather and soil inputs, APSIM model preparation, native simulation, and seasonal characterization.

The validated workflow supports one site-year simulation per execution.

## Validation

The release candidate was tested using an Illinois soybean simulation with Open-Meteo ERA5 weather and a USDA-derived Fayette soil profile.

**Integration results:**

| Validation | Result |
|---|---|
| ERA5 historical weather acquisition | 3,652 daily records (2001–2010) |
| USDA soil survey retrieval | Fayette component, four horizons |
| Soil profile conversion | Seven APSIM soil layers |
| Native APSIM simulation | Successful |
| APSIM daily report | 365 records |
| Unified simulation workflow | PASS |
| Python regression suite | 42 tests passed in release preparation |

The implementation was also evaluated using three historical weather years (2001, 2005, and 2010), demonstrating multi-environment characterization and wide-matrix exports.

These tests establish software functionality for the demonstrated configurations; they do not constitute independent agronomic calibration or validation of the underlying environmental datasets.

## Installation and Requirements

- Python 3
- APSIM Next Generation (2026-compatible installation)
- Python dependencies specified by the repository
- Internet access for automatic ERA5 and USDA soil-data retrieval

See the repository README and example configurations for execution instructions.

## Known Limitations

- ERA5 historical weather is reanalysis data, not field-station observation.
- USDA soil horizons are representative survey descriptions, not field-measured profiles.
- Soil hydraulic and initial-water assumptions require evaluation for site-specific applications.
- Automatic POLARIS acquisition is not included.
- Automatic weather-station CSV conversion is not included.
- Rotation-dependent residue and tillage effects are not yet implemented.
- Automated nationwide field-scale soil raster extraction is not included.
- The unified runner has been validated for single site-year execution; broader batch orchestration remains a separate workflow.

## Planned Enhancements

Future updates will focus on additional environmental data providers, user-supplied weather conversion, improved soil-initialization options, spatial soil variability, and streamlined multi-site execution.

## Attribution

SCE v2.0 builds upon the original Seasonal Characterization Engine and retains its scientific foundations and original repository attribution and licensing.

The Python modernization extends SCE's accessibility and reproducibility while using APSIM Next Generation as the underlying crop simulation framework.

---

**Release status:** `v2.0.0-rc1` — Pre-release

**Repository:** https://github.com/xesmaze/SCE