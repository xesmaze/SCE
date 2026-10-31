"""Stage-aligned wide covariates, without averaging repeated stage segments.

Missing values remain blank; stage labels are APSIM-native; output is one row/run.
"""
import csv
import json
import re
from collections import Counter
from pathlib import Path

class WideError(ValueError):pass

def wide_export(batch_stages, output_file):
    source=Path(batch_stages).resolve();target=Path(output_file).resolve()
    if target.exists():raise WideError(f'Refusing overwrite: {target}')
    with source.open(newline='') as f: rows=list(csv.DictReader(f))
    if not rows:raise WideError('No stage data')
    base=('run_id','site','year','cultivar','maturity_group')
    excluded=set(base)|{'stage_segment_id','stage_name','stage_class','start_date','end_date','observed_stage_values'}
    metrics=[k for k in rows[0] if k not in excluded]
    by_run={}; seen=set(); all_columns=set(); occurrence=Counter()
    for r in rows:
        rid=r['run_id'];by_run.setdefault(rid,dict((k,r.get(k,'')) for k in base))
        if r.get('stage_class')!='phenological':continue
        stage=r.get('stage_name','')
        if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*',stage):raise WideError(f'Invalid stage label: {stage!r}')
        # Retain repeated intervals separately; comparison will never merge or average them.
        segment=r.get('stage_segment_id','')
        key=(rid,stage,segment)
        if key in seen:raise WideError(f'Duplicate run/stage segment {key}')
        seen.add(key)
        occurrence[(rid,stage)]+=1
        occurrence_index=occurrence[(rid,stage)]
        for m in metrics:
            col=f'{stage}__occurrence{occurrence_index:02d}__{m}'
            by_run[rid][col]=r.get(m,'');all_columns.add(col)
    headers=list(base)+sorted(all_columns)
    target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=headers,extrasaction='ignore');w.writeheader()
        for rid in sorted(by_run):w.writerow(by_run[rid])
    return {'runs':len(by_run),'columns':len(headers),'stage_metric_columns':len(all_columns),
            'source':str(source),'output':str(target),'alignment':'APSIM StageName plus within-run stage occurrence (in source row order); no pooling'}
