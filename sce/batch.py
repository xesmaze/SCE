"""SCE v2 Phase 5: non-destructive multi-environment characterization and exports.

Runs the validated Phase 4 characterizer on a list of existing APSIM databases,
retaining raw stage segments and separating biological stages from harvest
transition records. This is analysis of supplied simulations, not APSIM fitting.
"""
from __future__ import annotations
import csv
import hashlib
import json
import math
from pathlib import Path
from collections import defaultdict
from .characterization import load_report, build, CharacterizationError, write_csv

class BatchError(ValueError): pass

def _hash(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024), b''):h.update(b)
    return h.hexdigest()

def _real(path, base):
    p=Path(path).expanduser()
    return (base/p).resolve() if not p.is_absolute() else p.resolve()

def _str(v):return '' if v is None else str(v)

def _csv_read(path):
    with path.open(newline='') as f: return list(csv.DictReader(f))

def _load_config(path):
    path=Path(path).resolve()
    d=json.loads(path.read_text())
    if not isinstance(d,dict) or not isinstance(d.get('runs'),list) or not d['runs']:
        raise BatchError('Configuration needs a nonempty runs array')
    runs=[]; seen=set()
    for n,entry in enumerate(d['runs'],1):
        if not isinstance(entry,dict):raise BatchError(f'Run {n} must be an object')
        rid=_str(entry.get('run_id')).strip()
        if not rid or rid in seen:raise BatchError(f'Missing/duplicate run_id: {rid!r}')
        seen.add(rid)
        src=entry.get('database')
        if not src:raise BatchError(f'{rid}: database path missing')
        db=_real(src,path.parent)
        if not db.is_file():raise BatchError(f'{rid}: missing database {db}')
        if not _str(entry.get('site')).strip():raise BatchError(f'{rid}: site missing')
        if not _str(entry.get('cultivar')).strip():raise BatchError(f'{rid}: cultivar/maturity class missing')
        year=entry.get('year')
        if isinstance(year,bool) or not _str(year).isdigit() or not 1900<=int(year)<=2200:
            raise BatchError(f'{rid}: invalid year')
        run=dict(entry);run.update(run_id=rid,database=str(db),year=int(year))
        runs.append(run)
    threshold=d.get('stress_threshold',0.8)
    if not isinstance(threshold,(int,float)) or not math.isfinite(threshold) or not 0<=threshold<=1:
        raise BatchError('stress_threshold must be in [0,1]')
    return runs,float(threshold),path

def _wide(rows):
    # One row per run, distinct contiguous stage segment. Identically named stages
    # can occur more than once, so stage_segment_id remains part of the key.
    return rows

def process_batch(config, output_dir):
    runs, threshold, cfgpath=_load_config(config)
    out=Path(output_dir).resolve()
    targets=('batch_daily.csv','batch_stages.csv','batch_covariates.csv',
             'stage_comparison.csv','run_summary.csv','batch_manifest.json')
    if out.exists() and any((out/t).exists() for t in targets):
        raise BatchError(f'Output exists in {out}; choose a fresh directory')
    # Fail before writing outputs, including invalid APSIM data. No partial batch.
    daily_all=[];stages_all=[];cov_all=[];summaries=[];provenance=[]
    for run in runs:
        rid=run['run_id']; rows=load_report(run['database'],run.get('simulation_id'))
        daily,stages,cov,meta=build(rows, sow_date=run.get('sowing_date'),
            harvest_date=run.get('harvest_date'),stress_threshold=threshold)
        dates={int(d['Date'][:4]) for d in daily}
        if dates!={run['year']}:
            raise BatchError(f'{rid}: report season years {sorted(dates)} do not match year {run["year"]}')
        common={k:run[k] for k in ('run_id','site','year','cultivar')}
        if run.get('maturity_group') is not None:common['maturity_group']=run['maturity_group']
        for record, dest in ((daily,daily_all),(stages,stages_all),(cov,cov_all)):
            dest.extend([{**common,**r} for r in record])
        biologic=[s for s in stages if s['stage_class']=='phenological']
        summaries.append({**common,'sowing_date':meta['sowing_date'],
            'harvest_date':meta['harvest_date'],'season_days':meta['n_season_days'],
            'biological_segments':len(biologic),'harvest_transition_days':meta['n_harvest_transition_days'],
            'rain_season_mm':round(sum(s['Rain_sum'] for s in stages if s['Rain_sum'] is not None),6) if all(s['Rain_sum'] is not None for s in stages) else None,
            'thermal_time_season':round(sum(s['ThermalTime_sum'] for s in stages if s['ThermalTime_sum'] is not None),6) if all(s['ThermalTime_sum'] is not None for s in stages) else None})
        provenance.append({**common,'database':run['database'],'sha256':_hash(run['database']),
                           'simulation_id':run.get('simulation_id'),'source_report_rows':len(rows),
                           'season_days':meta['n_season_days'],'stage_segments':meta['n_stage_segments']})
    # Cross-run stage comparison uses stage names as provided by APSIM, excluding
    # harvest transition; do NOT average repeated intervals or imply stage equivalence.
    comparison=[]
    for s in stages_all:
        if s['stage_class']!='phenological':continue
        keys=('run_id','site','year','cultivar','maturity_group','stage_segment_id','stage_name',
              'start_date','end_date','days','Rain_sum','Radn_sum','ThermalTime_sum',
              'WaterStress_mean','WaterStress_deficit_factor_days',
              'WaterStress_days_below_threshold','WaterStress_max_consecutive_days_below_threshold')
        comparison.append({k:s.get(k) for k in keys})
    out.mkdir(parents=True,exist_ok=True)
    for f,entries in [('batch_daily.csv',daily_all),('batch_stages.csv',stages_all),
                      ('batch_covariates.csv',cov_all),('stage_comparison.csv',comparison),
                      ('run_summary.csv',summaries)]:
        write_csv(out/f,entries)
    manifest={'schema_version':'SCE-batch-1.0','config':str(cfgpath),
              'config_sha256':_hash(cfgpath),'n_runs':len(runs),'stress_threshold':threshold,
              'aggregation':'Phase 4 unmodified; comparison rows are contiguous stage segments, not merged phenophases',
              'stage_classification':'harvest_transition excluded only from stage_comparison, retained in batch_daily/stages/covariates',
              'input_provenance':provenance,
              'outputs':list(targets[:-1])}
    (out/'batch_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest
