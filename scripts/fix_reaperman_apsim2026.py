#!/usr/bin/env python3
"""Patch legacy SCE ReaperMan IPlant link for APSIM Next Generation 2026.

Legacy ReaperMan declares `[Link] IPlant Crop;`. APSIM 2026's model-tree
FindByPath call requires a concrete Models.PMF.Plant with INodeModel support.
Only this declaration is changed. Original .apsimx is untouched by default.

Examples:
  python scripts/fix_reaperman_apsim2026.py \
    --input template_models/Soy_Template.apsimx \
    --output template_models/Soy_Template_APSIM2026.apsimx
  python scripts/fix_reaperman_apsim2026.py --input mymodel.apsimx --check
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

OLD = 'IPlant Crop;'
NEW = 'Models.PMF.Plant Crop;'


def walk(node):
    if isinstance(node, dict):
        yield node
        for child in node.get('Children', []):
            yield from walk(child)


def patch_model(data):
    managers = [n for n in walk(data) if n.get('Name') == 'ReaperMan']
    if len(managers) != 1:
        raise ValueError(f'Expected exactly one ReaperMan, found {len(managers)}')
    code = managers[0].get('CodeArray')
    if not isinstance(code, list) or any(not isinstance(s, str) for s in code):
        raise ValueError('ReaperMan.CodeArray must be a list of C# source lines')
    old_lines = [i for i, s in enumerate(code) if OLD in s and NEW not in s]
    new_lines = [i for i, s in enumerate(code) if NEW in s]
    if len(new_lines) == 1 and not old_lines:
        return False, new_lines[0] + 1
    if len(old_lines) != 1 or new_lines:
        raise ValueError(f'Unexpected ReaperMan declaration: {len(old_lines)} legacy and {len(new_lines)} patched references')
    line = old_lines[0]
    code[line] = code[line].replace(OLD, NEW)
    if code[line].count(NEW) != 1:
        raise ValueError('Replacement did not produce exactly one concrete Plant declaration')
    return True, line + 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True, help='Existing SCE .apsimx template')
    parser.add_argument('--output', type=Path, help='New patched template (default: <input stem>_APSIM2026.apsimx)')
    parser.add_argument('--check', action='store_true', help='Check whether template already contains compatibility fix; do not write')
    parser.add_argument('--force', action='store_true', help='Overwrite a DIFFERENT existing output; source remains protected')
    args = parser.parse_args(argv)
    src = args.input.expanduser().resolve()
    if not src.is_file():
        parser.error(f'Input does not exist: {src}')
    try:
        data = json.loads(src.read_text(encoding='utf-8'))
        changed, line = patch_model(data)
    except (ValueError, json.JSONDecodeError) as err:
        parser.error(str(err))
    if args.check:
        print(f'{"NEEDS PATCH" if changed else "ALREADY COMPATIBLE"}: {src}, ReaperMan source line {line}')
        return 1 if changed else 0
    output = (args.output or src.with_name(src.stem + '_APSIM2026.apsimx')).expanduser().resolve()
    if output == src:
        parser.error('Refusing to overwrite source template; supply a distinct --output')
    serialized = json.dumps(data, indent=2, ensure_ascii=False) + '\n'
    if output.exists():
        if output.read_text(encoding='utf-8') == serialized:
            print(f'ALREADY GENERATED: {output}; no changes')
            return 0
        if not args.force:
            parser.error(f'Output already exists and differs: {output}. Use --force only after inspection')
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = output.with_name(output.name + '.tmp')
    try:
        tmp.write_text(serialized, encoding='utf-8')
        # Verify persisted JSON has the intended declaration before replacement.
        reloaded = json.loads(tmp.read_text(encoding='utf-8'))
        is_changed, _ = patch_model(reloaded)
        if is_changed:
            raise ValueError('Serialized model still has a legacy declaration')
        tmp.replace(output)
    finally:
        if tmp.exists():
            tmp.unlink()
    print(f'{"PATCHED" if changed else "COPIED COMPATIBLE TEMPLATE"}: {output}')
    print(f'Changed only ReaperMan declaration, source line {line}: {OLD} -> {NEW}')
    print('Next step: execute this model with the installed APSIM Models binary and check its SQLite report.')
    return 0

if __name__ == '__main__':
    sys.exit(main())
