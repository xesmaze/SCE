#!/usr/bin/env python3
"""Make original SCE Shiny soybean example select the SCE v2 APSIM template.

Conservative text replacement: if the upstream code has changed, refuse to edit.
R runtime compatibility still requires an independent end-to-end test.
"""
from pathlib import Path
import argparse
import sys


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo', type=Path, required=True)
    p.add_argument('--apply', action='store_true', help='Actually edit app.R. Omit for diff preview.')
    a=p.parse_args()
    repo=a.repo.resolve()
    file=repo/'app.R'
    target=repo/'template_models'/'Soy_Template_v2.0_APSIM2026.apsimx'
    if not file.is_file() or not target.is_file():
        p.error(f'Missing {file} or new v2 soybean template {target}')
    source=file.read_text(encoding='utf-8')
    old='/template_models/Soy_Template.apsimx'
    new='/template_models/Soy_Template_v2.0_APSIM2026.apsimx'
    if new in source:
        print('app.R already points to SCE v2 model. Review application tests before release.')
        return 0
    if source.count(old) != 1:
        p.error(f'Expected one legacy example soybean source path, found {source.count(old)}; examine app.R manually')
    # Also replace the example bundle path, which uses a different relative prefix.
    bundle_old='template_models/Soy_Template.apsimx'
    bundle_new='template_models/Soy_Template_v2.0_APSIM2026.apsimx'
    patched=source.replace(old,new)
    if bundle_old in patched:
        patched=patched.replace(bundle_old,bundle_new)
    if not a.apply:
        print('Dry run: would update soybean example path in app.R. To apply pass --apply.')
        for line in patched.splitlines():
            if 'Soy_Template_v2.0_APSIM2026.apsimx' in line: print('  ',line.strip())
        return 0
    file.write_text(patched, encoding='utf-8')
    print('Updated app.R. Next run R Shiny end-to-end; this does not repair R package incompatibilities.')
    return 0

if __name__=='__main__':
    raise SystemExit(main())
