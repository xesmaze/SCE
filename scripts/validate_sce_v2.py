#!/usr/bin/env python3
"""Validate SCE 2.0 soybean APSIM template against original v1 template.

Run from any directory:
  python scripts/validate_sce_v2.py --repo /path/to/SCE

Checks full 30-class cultivar differences, ReaperMan compatibility, numerical
values, and preservation of the original source model. No APSIM execution is
implied by successful static checks.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
import sys

LEAF = '[Leaf].AreaLargestLeaf.FixedValue'
GRAIN = '[Phenology].LateGrainFilling.Target.EntireGrainfillPeriod.FixedValue'


def walk(v):
    if isinstance(v, dict):
        yield v
        for x in v.get('Children', []):
            yield from walk(x)


def cultivar_map(root):
    entries = [x for x in walk(root) if 'Models.PMF.Cultivar' in x.get('$type', '')]
    matches = {}
    for e in entries:
        n = e.get('Name')
        if n in matches:
            raise ValueError(f'Duplicate cultivar {n}')
        matches[n] = e
    return matches


def find_override(node, key):
    cmds = node.get('Command', [])
    c = [x for x in cmds if isinstance(x, str) and x.split('=', 1)[0].strip() == key]
    if len(c) > 1:
        raise ValueError(f"Duplicate {key} in {node.get('Name')}")
    if not c:
        return None
    if '=' not in c[0]:
        raise ValueError(f'Malformed {c[0]}')
    v = float(c[0].split('=', 1)[1].strip())
    if not math.isfinite(v):
        raise ValueError('Nonfinite override')
    return v


def omitted(cmds):
    return [x for x in cmds if x.split('=', 1)[0].strip() not in (LEAF, GRAIN)]


def close(a, b):
    return math.isclose(a, b, rel_tol=0, abs_tol=1e-6)


def validate(original: Path, updated: Path):
    issues = []
    old = json.loads(original.read_text(encoding='utf8'))
    new = json.loads(updated.read_text(encoding='utf8'))
    orig_map, new_map = cultivar_map(old), cultivar_map(new)
    if orig_map.keys() != new_map.keys():
        issues.append('Cultivar names differ from original template')
    if len(orig_map) != 30 or len(new_map) != 30:
        issues.append(f'Expected 30 SCE cultivar classes; found original={len(orig_map)}, v2={len(new_map)}')
    for name in sorted(orig_map.keys() & new_map.keys()):
        a, b = orig_map[name], new_map[name]
        for key in set(a) | set(b):
            if key == 'Command':
                continue
            if a.get(key) != b.get(key):
                issues.append(f'{name}: changed non-command field {key}')
        if omitted(a.get('Command', [])) != omitted(b.get('Command', [])):
            issues.append(f'{name}: unrelated cultivar command changed')
        area = find_override(b, LEAF)
        if area is None or not close(area, .008):
            issues.append(f'{name}: expected AreaLargestLeaf=0.008; found {area}')
        g_old, g_new = find_override(a, GRAIN), find_override(b, GRAIN)
        if g_old is None or g_new is None:
            issues.append(f'{name}: missing GrainFill override')
        elif name == 'mid000':
            if not (close(g_old, 590) and close(g_new, 531)):
                issues.append(f'{name}: expected 590 -> 531, found {g_old} -> {g_new}')
        elif name == 'mid00':
            if not (close(g_old, 600) and close(g_new, 480)):
                issues.append(f'{name}: expected 600 -> 480, found {g_old} -> {g_new}')
        elif not close(g_old, g_new):
            issues.append(f'{name}: GrainFill modified without calibration')
    old_man = [x for x in walk(old) if x.get('Name') == 'ReaperMan']
    new_man = [x for x in walk(new) if x.get('Name') == 'ReaperMan']
    if len(old_man) != 1 or len(new_man) != 1:
        issues.append(f'Expected one ReaperMan each, found {len(old_man)}, {len(new_man)}')
    else:
        a, b = old_man[0], new_man[0]
        original_lines, modified_lines = a.get('CodeArray', []), b.get('CodeArray', [])
        expected = [x.replace('IPlant Crop;', 'Models.PMF.Plant Crop;') for x in original_lines]
        if expected != modified_lines:
            issues.append('ReaperMan modifications differ from the narrowly tested Plant compatibility patch')
        if sum('Models.PMF.Plant Crop;' in x for x in modified_lines) != 1:
            issues.append('ReaperMan missing unique concrete Plant declaration')
    # No unrelated modifications to the entire APSIM JSON tree. Compare after normalizing permitted changes.
    if orig_map.keys() == new_map.keys() and len(old_man) == len(new_man) == 1:
        import copy
        norm = copy.deepcopy(new)
        norm_map = cultivar_map(norm)
        for n, target in norm_map.items():
            target['Command'] = orig_map[n]['Command']
        norm_man = next(x for x in walk(norm) if x.get('Name') == 'ReaperMan')
        norm_man['CodeArray'] = old_man[0]['CodeArray']
        if norm != old:
            issues.append('Other APSIM model fields/nodes differ from original; review changes explicitly')
    return issues


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo', type=Path, default=Path.cwd())
    p.add_argument('--original', type=Path)
    p.add_argument('--v2', type=Path)
    a = p.parse_args()
    repo = a.repo.resolve()
    original = a.original or repo / 'template_models' / 'Soy_Template.apsimx'
    v2 = a.v2 or repo / 'template_models' / 'Soy_Template_v2.0_APSIM2026.apsimx'
    if not original.is_file() or not v2.is_file():
        print(f'FAIL missing original or v2 APSIM file:\n - {original}\n - {v2}', file=sys.stderr)
        return 1
    try:
        issues = validate(original, v2)
    except Exception as e:
        print('FAIL:', e, file=sys.stderr)
        return 1
    for msg in issues:
        print('FAIL:', msg, file=sys.stderr)
    if issues:
        print(f'FAILED: {len(issues)} validation findings', file=sys.stderr)
        return 1
    print('PASS: 30 cultivar definitions, leaf area 0.008, grain-fill changes only in mid000/mid00,')
    print('      original other cultivar commands and structure unchanged, ReaperMan APSIM2026 patch confirmed.')
    print('NOTE: This does NOT verify native APSIM execution or the Python CLI.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
