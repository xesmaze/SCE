#!/usr/bin/env python3
"""Prepare a manifest for a *template-based example* Phase 3 test.

This is NOT Phase 2 environmental acquisition or soil initialization.
It only uses the previously validated local APSIM template and example weather.
"""
import argparse, json, shutil
from pathlib import Path
from datetime import date


def walk(node):
    if isinstance(node,dict):
        yield node
        for child in node.get('Children',[]):
            yield from walk(child)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--template',default='template_models/Soy_Template_v2.0_APSIM2026.apsimx')
    p.add_argument('--weather',default='template_models/z_12.met')
    p.add_argument('--output-dir',default='rotation_example_environment')
    p.add_argument('--trial-id',default='IL_2001_mid000')
    args=p.parse_args()
    template=Path(args.template).resolve(); weather=Path(args.weather).resolve(); out=Path(args.output_dir).resolve()
    for src in [template,weather]:
        if not src.is_file():p.error(f'File not found: {src}')
    if out.exists() and any(out.iterdir()):p.error(f'Output directory must be empty or absent: {out}')
    data=json.loads(template.read_text())
    nodes=[n for n in walk(data) if n.get('$type','').split(',')[0]=='Models.Climate.Weather']
    if len(nodes)!=1:p.error(f'Expected exactly one weather node, got {len(nodes)}')
    nodes[0]['FileName']=str(weather)
    trial_dir=out/args.trial_id
    trial_dir.mkdir(parents=True,exist_ok=True)
    model=(trial_dir/f'{args.trial_id}_environment.apsimx').resolve()
    model.write_text(json.dumps(data,indent=2)+'\n')
    manifest=out/'environment_manifest.json'
    manifest.write_text(json.dumps({
      'format':'sce-v2-environment-v1',
      'source_template':str(template),
      'trial_count':1,
      'trials':[{'trial_id':args.trial_id,'model_file':str(model),
                 'maturity_class':'mid000','weather':{'first_date':'2001-01-01','last_date':'2011-12-31'},
                 'note':'Template-based example only; soil and weather not acquired or validated through Phase 2.'}]
    },indent=2)+'\n')
    print('Created example environment manifest:',manifest)
    print('This is NOT a Phase 2 run; it uses the existing example soil and weather.')

if __name__=='__main__':main()
