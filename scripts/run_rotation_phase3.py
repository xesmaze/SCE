#!/usr/bin/env python3
"""Bridge rotation presets to Phase 3 and optionally execute the staged APSIM models.

Run from the root of the SCE repository. Writes new outputs only.
"""
import argparse
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from sce.rotation_defaults import write_configs
from sce.management import stage


def run(manifest, scenario, out, apsim=None):
    out=Path(out).resolve()
    if out.exists() and any(out.iterdir()):
        raise ValueError(f'Output folder already contains data: {out}')
    # Make all outputs in one new directory; the existing Phase 2 manifest is read-only.
    out.mkdir(parents=True, exist_ok=True)
    configdir=out/'configs'
    cfg,scenarios=write_configs(scenario,configdir)
    result_manifest=stage(manifest,cfg,out/'models')
    results=[]
    for t in json.loads(result_manifest.read_text())['trials']:
        model=Path(t['model_file'])
        obj=json.loads(model.read_text())
        def walk(n):
            if isinstance(n,dict):
                yield n
                for c in n.get('Children',[]):yield from walk(c)
        sow=[n for n in walk(obj) if n.get('$type','').startswith('Models.Manager,') and n.get('Name')=='Sowing']
        if len(sow)!=1: raise RuntimeError('Expected one Sowing manager')
        params={p['Key']:p['Value'] for p in sow[0]['Parameters']}
        verify={'CultivarName':t['maturity_class'], 'Population':str(t['population_plants_m2']),
                'RowSpacing':str(1000*t['row_spacing_m']), 'SowingDepth':str(t['sowing_depth_mm'])}
        for k,v in verify.items():
            if k=='CultivarName': assert params[k]==v
            else: assert abs(float(params[k])-float(v))<1e-7, (k,params[k],v)
        for mgr_name in ('Fertilise at sowing','Tillage on a fixed date'):
            managers=[n for n in walk(obj) if n.get('Name')==mgr_name]
            if len(managers)!=1 or managers[0].get('Enabled') is not False:
                raise RuntimeError(f'{mgr_name} not safely disabled')
        item={'trial_id':t['trial_id'],'model':str(model),'sowing_parameters':params,
              'previous_crop':json.loads(scenarios.read_text())['trials'][t['trial_id']]['previous_crop'],
              'tillage_system':json.loads(scenarios.read_text())['trials'][t['trial_id']]['tillage_system']}
        if apsim:
            exe=Path(apsim).expanduser().resolve()
            if not exe.is_file(): raise FileNotFoundError(exe)
            proc=subprocess.run([str(exe),str(model)],capture_output=True,text=True)
            (model.parent/'apsim_execution.log').write_text(proc.stdout+'\n'+proc.stderr)
            if proc.returncode:raise RuntimeError(f'{t["trial_id"]}: APSIM returned {proc.returncode}: {proc.stderr[-1100:]}')
            db=model.with_suffix('.db')
            if not db.is_file(): raise RuntimeError(f'Missing APSIM database {db}')
            with sqlite3.connect(db) as con:
                count=con.execute('SELECT COUNT(*) FROM Report').fetchone()[0]
                sowdates=[r[0] for r in con.execute("SELECT DISTINCT SimSowDate FROM Report WHERE SimSowDate IS NOT NULL AND SimSowDate!='NA'")]
            if count<=0:raise RuntimeError('Report empty')
            if t['planting_date'] not in sowdates:raise RuntimeError(f'{t["trial_id"]}: sowing date not reported: {sowdates}')
            item.update({'database':str(db),'report_rows':count,'sowing_dates':sowdates})
        results.append(item)
    path=out/'rotation_integration_results.json';path.write_text(json.dumps({'executed':bool(apsim),'trials':results},indent=2)+'\n')
    return path

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--environment-manifest',required=True)
    p.add_argument('--rotation-config',required=True)
    p.add_argument('--output-dir',required=True)
    p.add_argument('--apsim',help='Optional APSIM Models binary; omit to stage/verify only')
    a=p.parse_args()
    try:print('Result:',run(a.environment_manifest,a.rotation_config,a.output_dir,a.apsim))
    except Exception as e: print('ERROR:',e,file=sys.stderr);sys.exit(1)
