"""Documented management presets for SCE v2.0 Phase 3.

Presets describe target geometry and management choice, NOT calibrated seed
placement distributions or measured soil N/residue initialization. The
existing APSIM sowing manager receives scalar parameter values. No soil state
or physiological function is changed here.
"""
from __future__ import annotations
import json
from copy import deepcopy
from pathlib import Path

CROPS = {'corn', 'soybean', 'wheat', 'small_grain', 'cover_crop', 'fallow', 'other'}
TILLAGE = {'conventional', 'no_till', 'strip_till'}
METHODS = {'drill', 'planter'}
# Example establishment targets; users should override using observed practices.
# No-till -> drill is a workflow preference, not a universal agronomic rule.
PRESETS = {
    'conventional': {'planting_method': 'planter', 'row_spacing_m': 0.50, 'sowing_depth_mm': 30.0},
    'no_till': {'planting_method': 'drill', 'row_spacing_m': 0.19, 'sowing_depth_mm': 30.0},
    'strip_till': {'planting_method': 'planter', 'row_spacing_m': 0.50, 'sowing_depth_mm': 30.0},
}

class PresetError(ValueError):
    pass


def make_preset(previous_crop: str, tillage_system: str, *, planting_method=None,
                row_spacing_m=None, sowing_depth_mm=None, population_plants_m2=40.0):
    if previous_crop not in CROPS:
        raise PresetError(f'Unknown previous crop: {previous_crop!r}')
    if tillage_system not in TILLAGE:
        raise PresetError(f'Unknown tillage system: {tillage_system!r}')
    result = deepcopy(PRESETS[tillage_system])
    if planting_method is not None:
        if planting_method not in METHODS:
            raise PresetError(f'Unknown planting method: {planting_method!r}')
        result['planting_method'] = planting_method
    for key, val, lower, upper in (
        ('row_spacing_m', row_spacing_m, 0.1, 2.0),
        ('sowing_depth_mm', sowing_depth_mm, 5.0, 100.0),
        ('population_plants_m2', population_plants_m2, 1.0, 150.0),
    ):
        if val is None:
            continue
        if isinstance(val, bool) or not isinstance(val, (int, float)) or not lower <= val <= upper:
            raise PresetError(f'{key} must be between {lower} and {upper}')
        result[key] = float(val)
    result.update({'previous_crop': previous_crop, 'tillage_system': tillage_system,
                   'fertilise_at_sowing': False,
                   # Disabling inherited 20-mar tillage manager avoids claiming a
                   # specific implement, incorporation depth or strip fraction.
                   'tillage': False,
                   'tillage_implementation': 'unconfigured',
                   'soil_state_policy': 'use_existing_APSIM_profile',
                   'initial_N_policy': 'use_existing_APSIM_profile',
                   'depth_variability': 'not_modeled',
                   'residue_initialization': 'not_inferred_from_previous_crop',
                   'assumptions': [
                       'Planting geometry values are example targets, not field observations.',
                       'Previous crop is provenance only: does not assign residue mass or nitrogen pools.',
                       'Tillage choice is provenance only until a supported APSIM management operation is configured.',
                       'No-till/drill pairing is a configurable default, not a universal rule.',
                       'APSIM SowingDepth is one target value, not a seed-depth distribution.',
                   ]})
    return result


def build_phase3_config(input_config: dict):
    """Convert explicit crop+tillage inputs to existing Phase3 adapter keys.

    Requires dates and cultivar from user; never infer those from a default.
    Returns (management_config, scenario_manifest); input is unchanged.
    """
    trials = input_config.get('trials')
    if not isinstance(trials, dict) or not trials:
        raise PresetError('Expected a nonempty trials object')
    out, scenario = {}, {}
    for tid, entry in trials.items():
        if not isinstance(entry, dict):
            raise PresetError(f'{tid}: must be an object')
        for required in ('previous_crop', 'tillage_system', 'maturity_class', 'planting_date',
                         'simulation_start', 'simulation_end'):
            if not entry.get(required):
                raise PresetError(f'{tid}: missing {required}')
        if 'fertilise_at_sowing' in entry and entry['fertilise_at_sowing'] is not False:
            raise PresetError(f'{tid}: fertilizer requires explicit separate management configuration')
        if 'tillage' in entry and entry['tillage'] is not False:
            raise PresetError(f'{tid}: tillage operation requires separately verified APSIM parameters')
        preset = make_preset(entry['previous_crop'], entry['tillage_system'],
                             planting_method=entry.get('planting_method'),
                             row_spacing_m=entry.get('row_spacing_m'),
                             sowing_depth_mm=entry.get('sowing_depth_mm'),
                             population_plants_m2=entry.get('population_plants_m2', 40))
        out[tid] = {key: entry[key] for key in ('maturity_class', 'planting_date',
                                               'simulation_start', 'simulation_end')}
        for key in ('row_spacing_m', 'sowing_depth_mm', 'population_plants_m2',
                    'fertilise_at_sowing', 'tillage'):
            out[tid][key] = preset[key]
        scenario[tid] = preset
    return {'trials': out}, {'format': 'sce-v2-rotation-presets-v1', 'trials': scenario}


def write_configs(input_path, output_dir):
    """Write configuration with no overwrite and preserve input file."""
    source = Path(input_path)
    output = Path(output_dir)
    if output.exists() and any(output.iterdir()):
        raise PresetError(f'Output directory not empty: {output}')
    data = json.loads(source.read_text())
    config, manifest = build_phase3_config(data)
    output.mkdir(parents=True, exist_ok=True)
    a, b = output / 'management_config.json', output / 'management_scenarios.json'
    a.write_text(json.dumps(config, indent=2) + '\n')
    b.write_text(json.dumps(manifest, indent=2) + '\n')
    return a, b
