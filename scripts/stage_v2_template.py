#!/usr/bin/env python3
"""Stage already-built, locally validated SCE v2 APSIM template in a Git checkout.

Does not edit the original v1 template or publish to GitHub.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import shutil
import subprocess
import sys


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True, help='Local SCE_v2 APSIM2026 model that ran successfully')
    p.add_argument('--checkout', type=Path, required=True, help='Git checkout of CatherineGilbert/SCE or its fork')
    p.add_argument('--overwrite', action='store_true', help='Allow overwriting an existing staged v2 copy')
    args = p.parse_args()
    src = args.source.resolve(); repo = args.checkout.resolve()
    dst = repo / 'template_models' / 'Soy_Template_v2.0_APSIM2026.apsimx'
    if not src.is_file():
        p.error(f'No source model: {src}')
    if not (repo / 'template_models' / 'Soy_Template.apsimx').is_file():
        p.error('Target checkout lacks the original soybean APSIM template')
    result = subprocess.run(['git', '-C', str(repo), 'rev-parse', '--is-inside-work-tree'], text=True, capture_output=True)
    if result.returncode != 0 or result.stdout.strip() != 'true':
        p.error('Target must be a git checkout, not an extracted SCE-main ZIP')
    if dst.exists() and src != dst and not args.overwrite:
        p.error(f'v2 file already exists: {dst} (use --overwrite only after inspecting)')
    if src == dst:
        print('Already staged:', dst)
    else:
        shutil.copy2(src, dst)
        print('Staged:', dst)
    # Only after copy, import validator from sibling script.
    import validate_sce_v2
    errors = validate_sce_v2.validate(repo/'template_models'/'Soy_Template.apsimx', dst)
    if errors:
        for e in errors: print('FAIL:', e, file=sys.stderr)
        print('Do NOT tag/release until validated.', file=sys.stderr)
        return 1
    print('PASS structure checks. Next: run native APSIM and Python CLI verification.')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
