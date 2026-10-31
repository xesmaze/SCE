"""SCE v2 Phase 3: conservative, auditable cultivar/management staging.

Edits APSIM-native objects only. Does not implement a new crop physiology or
invent the local APSIM sowing-manager API. Inspect first and provide exact
manager command edits verified for the installed APSIM template.
"""
from __future__ import annotations
import copy
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path
import re
import shutil

class ManagementError(ValueError): pass


def walk(x):
    if isinstance(x,dict):
        yield x
        for c in x.get('Children',[]): yield from walk(c)
    elif isinstance(x,list):
        for c in x: yield from walk(c)


def one(root,kind=None,name=None):
    matches=[x for x in walk(root) if (kind is None or x.get('$type','').split(',')[0]==kind) and (name is None or x.get('Name')==name)]
    if len(matches)!=1:raise ManagementError(f'Expected exactly one {kind or name}; got {len(matches)}')
    return matches[0]


def inventory(path):
    model=json.loads(Path(path).read_text())
    sim=one(model,'Models.Core.Simulation')
    clock=one(sim,'Models.Clock')
    managers=[]
    for node in walk(sim):
        if node.get('$type','').split(',')[0]=='Models.Manager':
            managers.append({'name':node.get('Name'), 'code':node.get('CodeArray',[]), 'parameters':node.get('Parameters',[])})
    crop=one(sim,'Models.PMF.Plant',name='Soybean') if any(x.get('Name')=='Soybean' and x.get('$type','').split(',')[0]=='Models.PMF.Plant' for x in walk(sim)) else None
    cultivar_names=[]
    if crop:
        for node in walk(crop):
            if node.get('$type','').split(',')[0]=='Models.PMF.Cultivar': cultivar_names.append(node.get('Name'))
    return {'simulation_name':sim.get('Name'),'clock':{'Start':clock.get('Start'),'End':clock.get('End')},
            'managers':managers,'cultivars':cultivar_names}


def _iso(s,key):
    try:d=date.fromisoformat(s)
    except (TypeError,ValueError):raise ManagementError(f'{key} must be an ISO date YYYY-MM-DD')
    return d


def _edit_manager(model,entry):
    if not isinstance(entry,dict):raise ManagementError('manager_edit must be an object')
    name=entry.get('manager_name')
    node=one(model,'Models.Manager',name)
    changes=entry.get('code_replacements',[])
    if not changes:raise ManagementError(f'{name}: supply code_replacements verified against the template')
    lines=node.get('CodeArray')
    if not isinstance(lines,list) or not all(isinstance(s,str) for s in lines):
        raise ManagementError(f'{name}: expected string CodeArray')
    text='\n'.join(lines)
    for edit in changes:
        old=edit.get('old');new=edit.get('new')
        if not isinstance(old,str) or not old or not isinstance(new,str) or old==new:
            raise ManagementError(f'{name}: invalid replacement')
        n=text.count(old)
        if n!=1:raise ManagementError(f'{name}: expected one occurrence of {old!r}; found {n}')
        text=text.replace(old,new,1)
    node['CodeArray']=text.split('\n')
    return {'manager':name,'replacements':len(changes)}


def stage(env_manifest, config_path, outdir):
    env_manifest=Path(env_manifest).resolve(); config_path=Path(config_path).resolve(); outdir=Path(outdir).resolve()
    env=json.loads(env_manifest.read_text()); config=json.loads(config_path.read_text())
    if env.get('format')!='sce-v2-environment-v1':raise ManagementError('Expected Phase 2 environment_manifest.json')
    settings=config.get('trials')
    if not isinstance(settings,dict):raise ManagementError('Config requires trials mapping')
    trials=env.get('trials',[])
    if not trials:raise ManagementError('Environment manifest has no trials')
    if outdir.exists() and any(outdir.iterdir()):raise ManagementError('Output directory is not empty')
    pending=outdir.with_name(outdir.name+'.staging')
    if pending.exists():raise ManagementError('Previous staging directory exists')
    staged=[];pending.mkdir(parents=True)
    try:
        for trial in trials:
            tid=trial['trial_id']; cfg=settings.get(tid)
            if not isinstance(cfg,dict):raise ManagementError(f'{tid}: missing Phase 3 config')
            cultivar=cfg.get('maturity_class') or trial.get('maturity_class')
            if not isinstance(cultivar,str) or not re.fullmatch(r'(early|mid|late)(000|00|0|I|II|III|IV|V|VI|VII|VIII|IX|X)',cultivar):
                raise ManagementError(f'{tid}: explicit SCE cultivar class required (e.g. midII)')
            # Never change an explicitly resolved Phase 1 maturity class silently.
            if trial.get('maturity_class') and trial['maturity_class']!=cultivar:
                raise ManagementError(f'{tid}: maturity class conflicts with Phase 1: {cultivar} vs {trial["maturity_class"]}')
            source=Path(trial['model_file'])
            if not source.is_absolute():source=(env_manifest.parent/source).resolve()
            if not source.is_file():raise ManagementError(f'{tid}: missing Phase 2 model {source}')
            model=json.loads(source.read_text())
            sim=one(model,'Models.Core.Simulation');clock=one(sim,'Models.Clock')
            template_info=inventory(source)
            if template_info['cultivars'] and cultivar not in template_info['cultivars']:
                raise ManagementError(f'{tid}: cultivar {cultivar} not present in model')
            planting=_iso(cfg.get('planting_date') or trial.get('planting_date'), 'planting_date')
            # Explicit start/end, no arbitrary weather windows.
            start=_iso(cfg.get('simulation_start'),'simulation_start');end=_iso(cfg.get('simulation_end'),'simulation_end')
            if not (start<=planting<end):raise ManagementError(f'{tid}: require simulation_start <= planting_date < simulation_end')
            weather=trial.get('weather',{})
            if weather.get('first_date') and start<_iso(weather['first_date'],'weather.first_date'):
                raise ManagementError(f'{tid}: start precedes weather data')
            if weather.get('last_date') and end>_iso(weather['last_date'],'weather.last_date'):
                raise ManagementError(f'{tid}: end exceeds weather data')
            population=cfg.get('population_plants_m2'); spacing=cfg.get('row_spacing_m'); depth=cfg.get('sowing_depth_mm')
            for key,x,lo,hi in [('population_plants_m2',population,1,150),('row_spacing_m',spacing,.1,2),('sowing_depth_mm',depth,5,100)]:
                if not isinstance(x,(float,int)) or isinstance(x,bool) or not lo<=x<=hi:
                    raise ManagementError(f'{tid}: {key} required in [{lo}, {hi}]')
            clock['Start']=start.strftime('%Y-%m-%dT00:00:00')
            clock['End']=end.strftime('%Y-%m-%dT00:00:00')
            # Every sowing/cultivar change must be an exact-match edit explicitly
            # authored for the locally inspected APSIM template. Reject omissions.
            edits=cfg.get('manager_edits')
            if not isinstance(edits,list) or not edits:raise ManagementError(f'{tid}: explicit manager_edits required')
            receipts=[_edit_manager(model,e) for e in edits]
            # Ensure the requested management values were actually rendered into the model.
            code='\n'.join('\n'.join(x.get('CodeArray',[])) for x in walk(sim) if x.get('$type','').split(',')[0]=='Models.Manager')
            required=cfg.get('required_code_tokens')
            if not isinstance(required,list) or not required:
                raise ManagementError(f'{tid}: required_code_tokens must confirm cultivar, date, population, spacing and depth')
            for token in required:
                if not isinstance(token,str) or not token or token not in code:raise ManagementError(f'{tid}: missing verified code token {token!r}')
            if not all(str(v) in code for v in (cultivar,)):
                raise ManagementError(f'{tid}: selected cultivar not found in final Manager code')
            if len(required)<5:raise ManagementError(f'{tid}: at least 5 verification tokens required')
            sub=pending/tid;sub.mkdir()
            output=sub/f'{tid}_configured.apsimx';output.write_text(json.dumps(model,indent=2)+'\n')
            staged.append({'trial_id':tid,'model_file':str(outdir/tid/output.name),'source_model':str(source),
                           'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
                           'maturity_class':cultivar,'planting_date':planting.isoformat(),
                           'simulation_start':start.isoformat(),'simulation_end':end.isoformat(),
                           'population_plants_m2':population,'row_spacing_m':spacing,'sowing_depth_mm':depth,
                           'edits':receipts,'note':'APSIM manager API must be checked by native execution; no crop physiology was replaced.'})
        (pending/'management_manifest.json').write_text(json.dumps({'format':'sce-v2-management-v1','source_environment_manifest':str(env_manifest),'trial_count':len(staged),'trials':staged},indent=2)+'\n')
        if outdir.exists():outdir.rmdir()
        pending.rename(outdir)
        return outdir/'management_manifest.json'
    except BaseException:
        shutil.rmtree(pending)
        raise
