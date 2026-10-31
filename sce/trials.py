"""Validate and standardize trial input for SCE v2.0.

Accepts historical SCE Site,Planting,Latitude,Longitude,Crop,Genetics and
new canonical field names. Does not retrieve environmental data or run APSIM.
"""
from __future__ import annotations
from collections import Counter
import csv
from datetime import date, datetime
import json
from pathlib import Path
import re

ALIASES = {
    'site': ('site','site_id','location','location_id'),
    'planting_date': ('planting_date','planting','sowing_date','sow_date'),
    'latitude': ('latitude','lat'), 'longitude': ('longitude','lon','long'),
    'crop': ('crop','species'),
    'genetics': ('genetics','maturity_group','mg','maturity_class','cultivar'),
    'trial_id': ('trial_id','id_trial','experiment_id'),
    'weather_file': ('weather_file','weather_path'),
    'soil_file': ('soil_file','soil_path'),
    'year': ('year','trial_year'),
}
CANONICAL = ('trial_id','site','planting_date','year','latitude','longitude','crop','genetics','maturity_class','weather_file','soil_file')
REQUIRED = ('site','planting_date','latitude','longitude','crop','genetics')
# 30 SCE maturity classes: early/mid/late x 000,00,0,I,II,III,IV,V,VI,VII,VIII,IX;
# actual template entries are authoritative. Resolve only when value is explicit.
CLASS_RE = re.compile(r'^(early|mid|late)\s*[-_ ]?\s*(000|00|0|I|II|III|IV|V|VI|VII|VIII|IX|X|[1-9])$',re.I)
GROUP_RE = re.compile(r'^(000|00|0|I|II|III|IV|V|VI|VII|VIII|IX|X|[1-9])$',re.I)
ROMAN = {'1':'I','2':'II','3':'III','4':'IV','5':'V','6':'VI','7':'VII','8':'VIII','9':'IX'}

class TrialInputError(ValueError):
    pass

def _columns(headers):
    stripped = [h.strip() for h in headers]
    if len({s.casefold() for s in stripped}) != len(stripped):
        raise TrialInputError('Duplicate input headers after normalization')
    seen={}
    for key,aliases in ALIASES.items():
        candidates=[h for h in stripped if h.casefold() in aliases]
        if len(candidates)>1:
            raise TrialInputError(f'Ambiguous columns for {key}: {candidates}')
        if candidates: seen[key]=candidates[0]
    missing=[k for k in REQUIRED if k not in seen]
    if missing:raise TrialInputError(f'Missing columns: {", ".join(missing)}')
    return seen, [h for h in stripped if h not in seen.values()]

def _date(value):
    for fmt in ('%Y-%m-%d','%m/%d/%Y','%m/%d/%y'):
        try:return datetime.strptime(value,fmt).date()
        except ValueError:continue
    raise ValueError(f'invalid planting date {value!r}; use YYYY-MM-DD or MM/DD/YYYY')

def _maturity(value):
    v=value.strip().replace(' ','')
    match=CLASS_RE.fullmatch(v)
    if match:
        group=ROMAN.get(match.group(2).upper(),match.group(2).upper())
        return match.group(1).lower()+group
    if GROUP_RE.fullmatch(v):
        # Raw maturity group has no early/mid/late assignment. Don't infer a
        # cultivar-specific SCE class without an explicit policy.
        return ''
    raise ValueError(f'unsupported soybean maturity entry {value!r}')

def load_trials(path: Path, *, allow_other_crops=False):
    path=Path(path)
    with path.open(newline='',encoding='utf-8-sig') as f:
        reader=csv.DictReader(f)
        if not reader.fieldnames:raise TrialInputError('CSV is empty or missing a header')
        cols,extras=_columns(reader.fieldnames)
        records=[]; failures=[]
        for line,raw in enumerate(reader,start=2):
            if None in raw:
                failures.append(f'line {line}: extra fields beyond header');continue
            if not any((v or '').strip() for v in raw.values()):continue
            try:
                get=lambda field: (raw.get(cols.get(field,'')) or '').strip()
                planting=_date(get('planting_date'))
                lat=float(get('latitude'));lon=float(get('longitude'))
                if not (-90<=lat<=90 and -180<=lon<=180):raise ValueError('latitude/longitude out of range')
                import math
                if not (math.isfinite(lat) and math.isfinite(lon)):raise ValueError('nonfinite coordinate')
                crop=get('crop').lower()
                if crop not in ('soybean','soybeans') and not allow_other_crops:
                    raise ValueError('Phase 1 APSIM v2.0 supports soybean only')
                if crop=='soybeans':crop='soybean'
                genetics=get('genetics')
                if not genetics:raise ValueError('genetics/maturity group is blank')
                maturity=_maturity(genetics) if crop=='soybean' else ''
                site=get('site')
                if not site:raise ValueError('site is blank')
                year=get('year')
                if year and (not year.isdigit() or int(year)!=planting.year):
                    raise ValueError('year must match planting date year')
                ident=get('trial_id') or f'{site}_{planting.isoformat()}_{line-1:04d}'
                if not re.fullmatch(r'[A-Za-z0-9_.-]+',ident):
                    raise ValueError('trial_id must use only letters, numbers, _, . or -')
                rec=dict(trial_id=ident,site=site,planting_date=planting.isoformat(),year=planting.year,
                         latitude=lat,longitude=lon,crop=crop,genetics=genetics,
                         maturity_class=maturity,weather_file=get('weather_file'),soil_file=get('soil_file'))
                rec['_extras']={k:raw[k] for k in extras}
                records.append(rec)
            except (ValueError, TypeError) as e:
                failures.append(f'line {line}: {e}')
    ids=Counter(row['trial_id'] for row in records)
    failures.extend(f'duplicate trial_id: {t}' for t,n in ids.items() if n>1)
    if not records and not failures:failures.append('No trial records found')
    if failures:raise TrialInputError('\n'.join(failures))
    return records

def export_trials(records, destination:Path, *, source:Path):
    destination=Path(destination)
    destination.mkdir(parents=True,exist_ok=True)
    output=destination/'trials_normalized.csv'
    if output.exists() or (destination/'trials_manifest.json').exists():
        raise FileExistsError(f'Output directory already contains trial outputs: {destination}')
    with output.open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=CANONICAL)
        writer.writeheader()
        for record in records:writer.writerow({k:record[k] for k in CANONICAL})
    manifest={'format':'sce-v2-trials-v1','source_file':str(Path(source).resolve()),
              'trial_count':len(records),
              'resolved_maturity_class_count':sum(bool(r['maturity_class']) for r in records),
              'maturity_class_policy':'Only explicit early/mid/late maturity classes resolve; raw maturity groups remain unresolved.',
              'trials':[dict(r) for r in records]}
    (destination/'trials_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    return output,destination/'trials_manifest.json'
