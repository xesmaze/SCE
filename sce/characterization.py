"""SCE v2 Phase 4: phenology-aligned characterization of APSIM SQLite Report.

Standard-library only; observation/stage semantics are inherited from APSIM.
Not crop-model calibration, not site/soil retrieval. One row per reported day.
"""
from __future__ import annotations
import csv
from datetime import date, datetime
import json
import math
from pathlib import Path
import sqlite3
from collections import Counter

class CharacterizationError(ValueError): pass

REQUIRED={'Date','StageName','Rain','Radn','MaxT','MinT','ThermalTime','AccEmTT'}
MEAN_COLUMNS=('MaxT','MeanT','MinT','SoilTemp','PAWmm','NH4','NO3','Urea','OrganicC','FracGrowthRate','NutrientStress','TempStress','WaterStress')
SUM_COLUMNS=('Rain','Radn','ThermalTime')
STRESS_COLUMNS=('WaterStress','TempStress','NutrientStress')
DEFAULT_STRESS_THRESHOLD=0.8

def number(x):
    if x is None or str(x).strip().lower() in ('','na','nan','null','none'):return None
    try:
        z=float(x)
        return z if math.isfinite(z) else None
    except (ValueError, TypeError): return None

def parse_date(value):
    if value is None: raise CharacterizationError('Date is null')
    s=str(value).strip()
    try: return date.fromisoformat(s[:10])
    except ValueError as exc: raise CharacterizationError(f'Bad Date: {s!r}') from exc

def load_report(database, simulation_id=None):
    db=Path(database)
    if not db.is_file():raise CharacterizationError(f'Database not found: {db}')
    with sqlite3.connect(f'file:{db.resolve()}?mode=ro',uri=True) as conn:
        info=conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='Report'").fetchone()
        if not info:raise CharacterizationError('Missing Report table')
        columns=[r[1] for r in conn.execute('PRAGMA table_info("Report")')]
        missing=REQUIRED-set(columns)
        if missing:raise CharacterizationError(f'Missing required Report columns: {sorted(missing)}')
        if 'SimulationID' in columns:
            ids=[r[0] for r in conn.execute('SELECT DISTINCT SimulationID FROM "Report"')]
            if simulation_id is None:
                if len(ids)!=1:raise CharacterizationError(f'Multiple SimulationID values {ids}; specify --simulation-id')
                simulation_id=ids[0]
            if simulation_id not in ids:raise CharacterizationError(f'SimulationID {simulation_id} not found: {ids}')
            cur=conn.execute('SELECT * FROM "Report" WHERE SimulationID=? ORDER BY Date',(simulation_id,))
        else:
            if simulation_id is not None:raise CharacterizationError('SimulationID column not present')
            cur=conn.execute('SELECT * FROM "Report" ORDER BY Date')
        keys=[d[0] for d in cur.description]
        rows=[dict(zip(keys,r)) for r in cur.fetchall()]
    if not rows:raise CharacterizationError('Report contains no rows')
    # One zone per run: prevents contaminating each-day measurements with distinct paddocks.
    zones={str(r.get('Zone')) for r in rows if r.get('Zone') is not None}
    if len(zones)>1:raise CharacterizationError(f'Multiple Zone values {sorted(zones)}; provide a one-zone Report')
    dates=[parse_date(r['Date']) for r in rows]
    if len(dates)!=len(set(dates)):raise CharacterizationError('Duplicate Date values in Report')
    if any((b-a).days!=1 for a,b in zip(dates,dates[1:])):raise CharacterizationError('Daily Report dates are not contiguous')
    for row,d in zip(rows,dates):
        row['Date']=d.isoformat()
        for k in SUM_COLUMNS+MEAN_COLUMNS+('AccEmTT','Stage'):
            if k in row:row[k]=number(row[k])
        if row['Rain'] is not None and row['Rain'] <0:raise CharacterizationError('Negative daily rain')
        if row['Radn'] is not None and row['Radn'] <0:raise CharacterizationError('Negative daily radiation')
        if row['ThermalTime'] is not None and row['ThermalTime'] <0:raise CharacterizationError('Negative daily thermal time')
    return rows

def first_event(rows,key):
    events=[]
    for r in rows:
        val=r.get(key)
        if val is not None and str(val).strip().lower() not in ('','na','nan','none','null'):
            events.append(str(val)[:10])
    events=list(dict.fromkeys(events))
    if len(events)>1:raise CharacterizationError(f'Multiple {key} events: {events}')
    return events[0] if events else None

def build(rows, *, sow_date=None, harvest_date=None, include_pre_sowing=False, stress_threshold=DEFAULT_STRESS_THRESHOLD):
    """Segment into *contiguous* StageName intervals; don't merge repeats.

    StageName values are APSIM-provided, not inferred developmental thresholds.
    Harvest/sow event date fields are used only for season boundaries; they are
    event markers and may be NA on other days.
    """
    if not rows:raise CharacterizationError('No Report rows')
    if not (0.0 <= stress_threshold <= 1.0) or not math.isfinite(stress_threshold):
        raise CharacterizationError('Stress threshold must be finite and between 0 and 1')
    sow=sow_date or first_event(rows,'SimSowDate')
    harvest=harvest_date or first_event(rows,'SimHarvestDate')
    if sow is None and not include_pre_sowing:
        raise CharacterizationError('No SimSowDate event: supply --sow-date or --include-pre-sowing')
    if sow is not None: sow=parse_date(sow).isoformat()
    if harvest is not None: harvest=parse_date(harvest).isoformat()
    if sow and harvest and harvest<sow:raise CharacterizationError('Harvest date precedes sowing')
    subset=[dict(r) for r in rows if (include_pre_sowing or sow is None or r['Date']>=sow) and (harvest is None or r['Date']<=harvest)]
    if not subset:raise CharacterizationError('No dates in selected season')
    daily=[]; segments=[]; segment_id=0; last=None
    for r in subset:
        name=str(r.get('StageName') or 'Unreported').strip() or 'Unreported'
        if name!=last:
            segment_id+=1
            segments.append([])
        d=dict(r)
        d['StageName']=name
        # APSIM may end the crop before Report writes the harvest-day stage.
        # Preserve raw StageName, while classifying missing-stage harvest day as transition.
        is_harvest_transition=(harvest is not None and d['Date']==harvest and name=='Unreported')
        d['stage_class']='harvest_transition' if is_harvest_transition else ('unreported' if name=='Unreported' else 'phenological')
        d['include_in_biological_stage_summary']=not is_harvest_transition
        for factor in STRESS_COLUMNS:
            val=d.get(factor)
            d[f'{factor}_deficit']=round(1.0-val,8) if val is not None and 0.0<=val<=1.0 else None
            d[f'{factor}_below_threshold']=(int(val<stress_threshold) if val is not None and 0.0<=val<=1.0 else None)
        d['stage_segment_id']=segment_id
        d['days_since_sowing']=(parse_date(d['Date'])-parse_date(sow)).days if sow else None
        daily.append(d);segments[-1].append(d);last=name
    stage=[]
    for seg in segments:
        stage.append(summarize(seg,seg[0]['stage_segment_id'],stress_threshold=stress_threshold))
    cov=[]
    for s in stage:
        base={'stage_segment_id':s['stage_segment_id'],'stage_name':s['stage_name'],
              'start_date':s['start_date'],'end_date':s['end_date'],'days':s['days']}
        for key,val in s.items():
            if key not in base and key not in ('observed_stage_values','stage_name','start_date','end_date','days','stage_segment_id'):
                cov.append({**base,'covariate':key,'value':val})
    metadata={'n_report_days':len(rows),'n_season_days':len(daily),'n_stage_segments':len(stage),
              'sowing_date':sow,'harvest_date':harvest,'stage_definition':'contiguous daily APSIM StageName intervals',
              'stress_interpretation':'raw APSIM-reported stress-factor values; no assumed stress severity conversion',
              'aggregation':'Rain/Radn/ThermalTime sums; other columns means (non-null observations); daily values preserved',
              'pre_sowing_included':include_pre_sowing,
              'harvest_transition_rule':'harvest-day Unreported retained in daily output, excluded from biological-stage summary flag only',
              'stress_threshold':stress_threshold,
              'stress_deficit_definition':'sum(1-factor) for observed factors in [0,1]; null if missing or invalid; threshold counts only observed factors < threshold',
              'stress_factor_domain':'0 to 1; no assumed causal stress mechanism or validation of source variable',
              'n_harvest_transition_days':sum(r['stage_class']=='harvest_transition' for r in daily)}
    return daily,stage,cov,metadata

def summarize(seg,index,stress_threshold=DEFAULT_STRESS_THRESHOLD):
    n=len(seg)
    out={'stage_segment_id':index,'stage_name':seg[0]['StageName'],
         'start_date':seg[0]['Date'],'end_date':seg[-1]['Date'],'days':n,
         'observed_stage_values':','.join(sorted({str(r['Stage']) for r in seg if r.get('Stage') is not None})),
         'stage_class':seg[0]['stage_class'],
         'include_in_biological_stage_summary':seg[0]['stage_class']!='harvest_transition'}
    for col in SUM_COLUMNS:
        vals=[r[col] for r in seg if r.get(col) is not None]
        out[f'{col}_sum']=round(sum(vals),8) if len(vals)==n else None
        out[f'{col}_observed_days']=len(vals)
    for col in MEAN_COLUMNS:
        if col not in seg[0]:continue
        vals=[r[col] for r in seg if r.get(col) is not None]
        out[f'{col}_mean']=round(sum(vals)/len(vals),8) if vals else None
        out[f'{col}_observed_days']=len(vals)
    for factor in STRESS_COLUMNS:
        if factor not in seg[0]:
            continue
        vals=[r[factor] for r in seg if r.get(factor) is not None]
        invalid=[x for x in vals if not (0.0<=x<=1.0)]
        if invalid:
            raise CharacterizationError(f'{factor} outside [0,1]: {invalid[:3]}')
        out[f'{factor}_deficit_factor_days']=round(sum(1.0-v for v in vals),8) if len(vals)==n else None
        out[f'{factor}_days_below_threshold']=sum(v<stress_threshold for v in vals)
        out[f'{factor}_max_consecutive_days_below_threshold']=longest_run([r.get(factor) is not None and r[factor]<stress_threshold for r in seg])
        out[f'{factor}_stress_observed_days']=len(vals)
        out[f'{factor}_stress_missing_days']=n-len(vals)
    a=seg[0].get('AccEmTT'); b=seg[-1].get('AccEmTT')
    out['AccEmTT_start']=a;out['AccEmTT_end']=b
    out['rainy_days']=sum(r.get('Rain') is not None and r['Rain']>0 for r in seg)
    out['dry_days']=sum(r.get('Rain')==0 for r in seg)
    longest=cur=0
    for r in seg:
        cur=cur+1 if r.get('Rain')==0 else 0;longest=max(longest,cur)
    out['longest_consecutive_dry_days']=longest
    return out

def longest_run(flags):
    longest=cur=0
    for flag in flags:
        cur=cur+1 if flag else 0
        longest=max(longest,cur)
    return longest

def write_csv(path,records):
    if not records:raise CharacterizationError('No output records')
    keys=list(dict.fromkeys(k for r in records for k in r))
    with Path(path).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(records)

def characterize(db,outdir,simulation_id=None,sow_date=None,harvest_date=None,include_pre_sowing=False,stress_threshold=DEFAULT_STRESS_THRESHOLD):
    db=Path(db).resolve();dst=Path(outdir)
    if dst.exists() and any((dst/x).exists() for x in ('daily_phenology.csv','stage_summary.csv','stage_covariates.csv','characterization_manifest.json')):
        raise CharacterizationError(f'Existing Phase 4 outputs in {dst}; choose a fresh output directory')
    rows=load_report(db,simulation_id)
    daily,stage,cov,meta=build(rows,sow_date=sow_date,harvest_date=harvest_date,include_pre_sowing=include_pre_sowing,stress_threshold=stress_threshold)
    dst.mkdir(parents=True,exist_ok=True)
    write_csv(dst/'daily_phenology.csv',daily)
    write_csv(dst/'stage_summary.csv',stage)
    write_csv(dst/'stage_covariates.csv',cov)
    meta.update({'source_database':str(db),'outputs':{'daily':'daily_phenology.csv','stages':'stage_summary.csv','covariates':'stage_covariates.csv'}})
    (dst/'characterization_manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    return meta
