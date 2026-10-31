"""SCE v2 Phase 2: validation and non-destructive APSIM environment staging.

No weather acquisition, parameter fitting, or APSIM execution is performed.
Every trial must provide a local .met file and soil donor .apsimx; site initial
water and layer N values must be explicitly supplied in an initial-state JSON.
"""
from __future__ import annotations
import csv
from datetime import date, datetime, timedelta
import json
import math
from pathlib import Path
import re
import shutil

class EnvironmentError(ValueError): pass

def nodes(x):
    if isinstance(x, dict):
        yield x
        for ch in x.get('Children', []): yield from nodes(ch)
    elif isinstance(x, list):
        for ch in x: yield from nodes(ch)

def one(root, *, name=None, kind=None):
    hits=[n for n in nodes(root) if (name is None or n.get('Name')==name) and (kind is None or n.get('$type','').split(',')[0]==kind)]
    if len(hits)!=1: raise EnvironmentError(f'Expected exactly one {name or kind}, found {len(hits)}')
    return hits[0]

def children(node): return node.get('Children', [])

def child(parent, name):
    hits=[n for n in children(parent) if n.get('Name')==name]
    if len(hits)!=1:raise EnvironmentError(f'Expected one child {name!r} under {parent.get("Name")}, found {len(hits)}')
    return hits[0]

def resolve_reference(ref, manifest_dir, repo_root):
    p=Path(ref).expanduser()
    if p.is_absolute():return p.resolve()
    # Phase 1 exported paths were entered relative to the CSV or project; prefer source CSV.
    for root in (manifest_dir, repo_root):
        candidate=(root/p).resolve()
        if candidate.is_file():return candidate
    raise EnvironmentError(f'Missing input file {ref!r}: searched {manifest_dir}, {repo_root}')

def weather_validate(path, planting_year):
    """Validate standard APSIM .met headers and essential daily observations.

    APSIM may support additional valid formats; unsupported forms fail closed.
    """
    text=path.read_text(encoding='utf-8-sig',errors='replace').splitlines()
    lat=None; lon=None; tav=None; amp=None; header=None; records=[]
    for index,line in enumerate(text):
        s=line.strip()
        if not s or s.startswith(('!','#')):continue
        mm=re.match(r'^(latitude|longitude|lat|lon|tav|amp)\s*=\s*([^!#]+)',s,re.I)
        if mm:
            key=mm.group(1).lower(); val=mm.group(2).strip().split()[0]
            try:v=float(val)
            except ValueError:raise EnvironmentError(f'Invalid .met {key}: {val}')
            if not math.isfinite(v):raise EnvironmentError(f'Nonfinite .met {key}')
            if key in ('latitude','lat'):lat=v
            elif key in ('longitude','lon'):lon=v
            elif key=='tav':tav=v
            elif key=='amp':amp=v
            continue
        fields=s.split()
        low=[x.lower() for x in fields]
        if header is None and 'year' in low and ('day' in low or 'doy' in low):
            header=low;continue
        if header is None:continue
        # Units row or descriptor text is allowed; data rows begin with year/doy.
        try:
            vals=dict(zip(header,fields,strict=True))
            y=int(vals['year']); doy=int(vals.get('day',vals.get('doy')))
        except (ValueError,KeyError):continue
        except TypeError:continue
        except Exception as exc:
            if len(fields)!=len(header):raise EnvironmentError(f'Malformed weather data row: {s[:90]}') from exc
            raise
        if not (1<=doy<=(366 if y%4==0 and (y%100!=0 or y%400==0) else 365)):
            raise EnvironmentError(f'Invalid weather DOY {y}:{doy}')
        if len(fields)!=len(header):raise EnvironmentError(f'Column mismatch on weather day {y}:{doy}')
        required=['radn','maxt','mint','rain']
        if not all(k in vals for k in required):raise EnvironmentError(f'Missing required .met columns: {required}')
        for key in required:
            try: z=float(vals[key])
            except ValueError:raise EnvironmentError(f'Non-numeric weather value {key} at {y}:{doy}')
            if not math.isfinite(z) or z==-999 or z==-9999:raise EnvironmentError(f'Missing/nonfinite weather value {key} at {y}:{doy}')
            if key in ('radn','rain') and z<0:raise EnvironmentError(f'Negative {key} at {y}:{doy}')
        if float(vals['maxt'])<float(vals['mint']):raise EnvironmentError(f'MaxT below MinT at {y}:{doy}')
        records.append((y,doy))
    if not records:raise EnvironmentError(f'No readable daily APSIM weather observations: {path}')
    if len(records)!=len(set(records)):raise EnvironmentError('Duplicate dates in weather file')
    dates=[date(y,1,1)+timedelta(days=d-1) for y,d in records]
    if dates!=sorted(dates):raise EnvironmentError('Weather file dates are not strictly increasing')
    if any((b-a).days!=1 for a,b in zip(dates,dates[1:])):raise EnvironmentError('Weather file has missing days')
    if not any(y==planting_year for y,d in records):raise EnvironmentError(f'Weather file has no records for planting year {planting_year}')
    if lat is not None and not (-90<=lat<=90):raise EnvironmentError('Weather latitude out of range')
    if lon is not None and not (-180<=lon<=180):raise EnvironmentError('Weather longitude out of range')
    if tav is None or amp is None:raise EnvironmentError('APSIM .met requires tav and amp values')
    return {'path':str(path),'first_date':str(dates[0]),'last_date':str(dates[-1]),'n_days':len(dates),'latitude':lat,'longitude':lon,'tav':tav,'amp':amp}

def numeric_vec(data,key,n,*,positive=False):
    vals=data.get(key)
    if not isinstance(vals,list) or len(vals)!=n:raise EnvironmentError(f'{key} must contain {n} layer values')
    try: out=[float(x) for x in vals]
    except (TypeError,ValueError):raise EnvironmentError(f'{key}: nonnumeric layer value')
    if not all(math.isfinite(x) and (x>0 if positive else x>=0) for x in out):raise EnvironmentError(f'{key}: invalid layer value')
    return out

def validate_soil(soil):
    p=child(soil,'Physical'); thickness=p.get('Thickness')
    if not isinstance(thickness,list) or not thickness:raise EnvironmentError('Soil.Physical.Thickness missing')
    thick=numeric_vec(p,'Thickness',len(thickness),positive=True)
    n=len(thick)
    for nm in ('Water','NO3','NH4'):
        ch=child(soil,nm)
        if nm=='Water': numeric_vec(ch,'InitialValues',n)
        else: numeric_vec(ch,'InitialValues',n)
        if ch.get('Thickness') is not None:
            t=numeric_vec(ch,'Thickness',n,positive=True)
            if any(abs(a-b)>0.01 for a,b in zip(t,thick)):
                raise EnvironmentError(f'{nm} layers do not align with Physical.Thickness')
    for key in ('AirDry','LL15','DUL','SAT'):
        if key in p and p[key] is not None:numeric_vec(p,key,n)
    return thick

def apply_initial_state(soil,state):
    """Supply explicit volumetric initial water and N in ppm; no implicit units."""
    thick=validate_soil(soil); n=len(thick)
    if state.get('nitrogen_units')!='ppm':
        raise EnvironmentError('nitrogen_units must explicitly be "ppm" (no unit guessing)')
    if state.get('water_units')!='mm/mm':
        raise EnvironmentError('water_units must explicitly be "mm/mm" (volumetric fraction)')
    no3=numeric_vec(state,'no3_ppm',n)
    nh4=numeric_vec(state,'nh4_ppm',n)
    water=numeric_vec(state,'water_mm_mm',n)
    phys=child(soil,'Physical')
    for i,w in enumerate(water):
        for low,high in (('AirDry','SAT'),):
            if low in phys and high in phys and phys[low] and phys[high]:
                if w<float(phys[low][i])-1e-8 or w>float(phys[high][i])+1e-8:
                    raise EnvironmentError(f'Initial water outside AirDry..SAT in layer {i+1}')
    child(soil,'Water')['InitialValues']=water
    for name,vals in (('NO3',no3),('NH4',nh4)):
        sol=child(soil,name)
        # Check the source uses the current APSIM solute representation.
        if 'InitialValuesUnits' not in sol:raise EnvironmentError(f'{name} solute lacks InitialValuesUnits')
        sol['InitialValues']=vals
        sol['InitialValuesUnits']=0  # APSIM Next Gen ppm enumeration; verified against APSIM example.
    return {'layers':n,'thickness_mm':thick,'nitrogen_units':'ppm','water_units':'mm/mm',
            'no3_ppm':no3,'nh4_ppm':nh4,'water_mm_mm':water}

def prepare(manifest_path,template_path,configuration_path,outdir,repo_root=None):
    manifest_path=Path(manifest_path).resolve(); template_path=Path(template_path).resolve()
    configuration_path=Path(configuration_path).resolve();outdir=Path(outdir).resolve()
    repo_root=Path(repo_root).resolve() if repo_root else manifest_path.parent.parent
    manifest=json.loads(manifest_path.read_text()); config=json.loads(configuration_path.read_text())
    if manifest.get('format')!='sce-v2-trials-v1':raise EnvironmentError('Expected Phase 1 trial manifest')
    if not isinstance(config.get('trials'),dict):raise EnvironmentError('Config must contain trials object')
    trials=manifest.get('trials',[])
    if not trials: raise EnvironmentError('No Phase 1 trials')
    template=json.loads(template_path.read_text())
    zone=one(template,kind='Models.Core.Zone')
    old_soil=child(zone,'Soil')
    one(template,kind='Models.Climate.Weather')
    for trial in trials:
        if not all(k in config['trials'].get(trial['trial_id'],{}) for k in ('weather_file','soil_file','initial_state_file')):
            raise EnvironmentError(f'Trial {trial["trial_id"]}: require weather_file, soil_file, initial_state_file')
    if outdir.exists() and any(outdir.iterdir()):raise EnvironmentError(f'Output directory not empty: {outdir}')
    # Validate and stage all in a temporary sibling directory; only publish if all pass.
    staging=outdir.with_name(outdir.name+'.staging')
    if staging.exists():raise EnvironmentError(f'Staging directory already exists: {staging}')
    staging.mkdir(parents=True)
    results=[]
    try:
        for trial in trials:
            tid=trial['trial_id'];spec=config['trials'][tid]
            weather=resolve_reference(spec['weather_file'],configuration_path.parent,repo_root)
            donor=resolve_reference(spec['soil_file'],configuration_path.parent,repo_root)
            initial=resolve_reference(spec['initial_state_file'],configuration_path.parent,repo_root)
            if weather.suffix.lower()!='.met' or donor.suffix.lower()!='.apsimx':
                raise EnvironmentError(f'Trial {tid}: expected .met weather and .apsimx donor')
            weather_info=weather_validate(weather,int(trial['year']))
            donor_json=json.loads(donor.read_text())
            donor_soil=one(donor_json,kind='Models.Soils.Soil')
            # JSON copies are safely isolated from originals.
            soil=json.loads(json.dumps(donor_soil))
            soilinfo=apply_initial_state(soil,json.loads(initial.read_text()))
            model=json.loads(json.dumps(template))
            model_zone=one(model,kind='Models.Core.Zone')
            old=child(model_zone,'Soil');pos=model_zone['Children'].index(old)
            model_zone['Children'][pos]=soil
            weather_node=one(model,kind='Models.Climate.Weather')
            weather_node['FileName']=str(weather)
            # Do not set cultivar, sowing management, dates or model physiology here.
            # These are Phase 3 responsibilities and must not be inferred.
            sub=staging/tid;sub.mkdir()
            model_file=sub/f'{tid}_environment.apsimx'
            model_file.write_text(json.dumps(model,indent=2)+'\n')
            results.append({'trial_id':tid,'model_file':str(outdir/tid/model_file.name),
                            'weather':weather_info,'soil_donor':str(donor),'initial_state':str(initial),
                            'soil':soilinfo,'maturity_class':trial.get('maturity_class',''),
                            'ready_for_phase3':bool(trial.get('maturity_class')),
                            'note':'Environment staged only; no sowing or maturity configuration applied.'})
        (staging/'environment_manifest.json').write_text(json.dumps({'format':'sce-v2-environment-v1',
            'source_manifest':str(manifest_path),'source_template':str(template_path),
            'trial_count':len(results),'trials':results},indent=2)+'\n')
        if outdir.exists():outdir.rmdir()
        staging.rename(outdir)
        return outdir/'environment_manifest.json'
    except Exception:
        shutil.rmtree(staging)
        raise
