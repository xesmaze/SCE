"""SCE v2 APSIM multi-year staging and execution; no cultivar physiological edits.

Supports the inspected SCE v2 Sowing Manager's exposed Parameters. All
simulations use the source soil and weather (a diagnostic, NOT site calibration).
"""
from __future__ import annotations
import hashlib
import json
import re
import sqlite3
import subprocess
from datetime import date
from pathlib import Path

class MultiYearError(ValueError): pass

def walk(node):
    if isinstance(node, dict):
        yield node
        for child in node.get('Children', []):
            yield from walk(child)

def unique(root, kind, name=None):
    found=[n for n in walk(root) if n.get('$type','').split(',')[0]==kind and (name is None or n.get('Name')==name)]
    if len(found)!=1:raise MultiYearError(f'Expected exactly one {kind} {name or ""}; found {len(found)}')
    return found[0]

def param_set(manager, key, value):
    found=[p for p in manager.get('Parameters',[]) if p.get('Key')==key]
    if len(found)!=1: raise MultiYearError(f'{manager.get("Name")}: expected exactly one {key}; found {len(found)}')
    found[0]['Value']=str(value)

def met_years(path):
    # Check daily year/day completeness for requested simulation years;
    # this is a weather availability check, NOT a weather-quality assessment.
    from collections import defaultdict
    import calendar
    counts=defaultdict(set)
    with Path(path).open() as f:
        for raw in f:
            parts=raw.split()
            if len(parts)<2:continue
            try:y=int(parts[0]);day=int(parts[1])
            except ValueError:continue
            if 1900<=y<=2200 and 1<=day<=366:
                if day in counts[y]:raise MultiYearError(f'Duplicate weather year/day {y}/{day}')
                counts[y].add(day)
    return {y:(len(ds)==(366 if calendar.isleap(y) else 365) and ds==set(range(1,(366 if calendar.isleap(y) else 365)+1))) for y,ds in counts.items()}

def _digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def configure(source, year, weather_path, *, cultivar='mid000', sow_month=4,sow_day=12,
              population=40.,row_spacing_mm=500.,sowing_depth_mm=30.,
              fertilise=False,tillage=False):
    source=Path(source)
    model=json.loads(source.read_text())
    sim=unique(model,'Models.Core.Simulation')
    clock=unique(sim,'Models.Clock')
    clock['Start']=f'{year}-01-01T00:00:00'
    clock['End']=f'{year}-12-31T00:00:00'
    date(year,sow_month,sow_day)
    wx=unique(sim,'Models.Climate.Weather')
    wx['FileName']=str(Path(weather_path).resolve())
    soy=unique(sim,'Models.PMF.Plant','Soybean')
    cultivars={n.get('Name') for n in walk(soy) if n.get('$type','').split(',')[0]=='Models.PMF.Cultivar'}
    if cultivar not in cultivars:raise MultiYearError(f'Unknown cultivar {cultivar!r}, available: {sorted(cultivars)}')
    sow=unique(sim,'Models.Manager','Sowing')
    for key,value in {'SowDate':f'{sow_day}-{date(year,sow_month,sow_day).strftime("%b").lower()}',
                      'CultivarName':cultivar,'Population':f'{population:g}',
                      'RowSpacing':f'{row_spacing_mm:g}', 'SowingDepth':f'{sowing_depth_mm:g}'}.items():
        param_set(sow,key,value)
    for name,enabled in [('Fertilise at sowing',fertilise),('Tillage on a fixed date',tillage)]:
        unique(sim,'Models.Manager',name)['Enabled']=bool(enabled)
    # Managers' CodeArray and crop functions were not touched.
    return model

def run_multiyear(*, template, apsim, weather=None, output_dir, years=(2001,2005,2010),
                  cultivar='mid000', sow_month=4, sow_day=12, population=40.,
                  row_spacing_mm=500., sowing_depth_mm=30., dry_run=False):
    template=Path(template).resolve(); apsim=Path(apsim).expanduser().resolve()
    output_dir=Path(output_dir).resolve()
    if not template.is_file():raise MultiYearError(f'Missing model: {template}')
    if not dry_run and not apsim.is_file():raise MultiYearError(f'Missing APSIM Models executable: {apsim}')
    src=json.loads(template.read_text()); sim=unique(src,'Models.Core.Simulation')
    wx=unique(sim,'Models.Climate.Weather'); original_weather=Path(wx.get('FileName',''))
    weather=Path(weather).resolve() if weather else ((template.parent/original_weather).resolve() if not original_weather.is_absolute() else original_weather.resolve())
    if not weather.is_file():raise MultiYearError(f'Missing weather: {weather}')
    coverage=met_years(weather)
    years=list(years)
    if not years or len(years)!=len(set(years)) or any(type(y)!=int or y<1900 or y>2200 for y in years):
        raise MultiYearError('years must be unique valid integers')
    missing=[y for y in years if not coverage.get(y,False)]
    if missing:raise MultiYearError(f'Incomplete/missing full-year weather: {missing}')
    if not 1<=population<=150 or not 100<=row_spacing_mm<=2000 or not 5<=sowing_depth_mm<=100:
        raise MultiYearError('Invalid management parameters')
    # Validate all generated models BEFORE creating output folder.
    models={y:configure(template,y,weather,cultivar=cultivar,sow_month=sow_month,sow_day=sow_day,
        population=population,row_spacing_mm=row_spacing_mm,sowing_depth_mm=sowing_depth_mm) for y in years}
    if output_dir.exists() and any(output_dir.iterdir()):raise MultiYearError(f'Output directory not empty: {output_dir}')
    output_dir.mkdir(parents=True,exist_ok=True)
    runs=[]
    for year in years:
        rid=f'IL_{year}_{cultivar}'
        rd=output_dir/rid; rd.mkdir()
        mf=rd/f'{rid}.apsimx';mf.write_text(json.dumps(models[year],indent=2)+'\n')
        db=mf.with_suffix('.db')
        report_rows=None
        if not dry_run:
            proc=subprocess.run([str(apsim),str(mf)],capture_output=True,text=True)
            (rd/'apsim.log').write_text(proc.stdout+'\n--- STDERR ---\n'+proc.stderr)
            if proc.returncode!=0 or not db.is_file():
                raise MultiYearError(f'APSIM failed for {year}: {proc.stderr[-1000:]}; inspect {rd/"apsim.log"}')
            with sqlite3.connect(db) as con:
                try:
                    report_rows=con.execute('SELECT COUNT(*) FROM Report').fetchone()[0]
                    dates=[r[0] for r in con.execute("SELECT DISTINCT SimSowDate FROM Report WHERE SimSowDate IS NOT NULL AND SimSowDate!='NA'")]
                except sqlite3.Error as exc:raise MultiYearError(f'{year}: invalid APSIM Report: {exc}') from exc
            expected=f'{year}-{sow_month:02d}-{sow_day:02d}'
            if not report_rows or dates!=[expected]:
                raise MultiYearError(f'{year}: report has {report_rows} rows and sow events {dates}, expected {[expected]}')
        runs.append({'run_id':rid,'site':'Illinois example','year':year,'cultivar':cultivar,
                     'maturity_group':'000','database':str(db),'model':str(mf),'report_rows':report_rows})
    batch={'stress_threshold':0.8,'runs':[{k:r[k] for k in ('run_id','site','year','cultivar','maturity_group','database')} for r in runs]}
    config=output_dir/'batch_config.json'; config.write_text(json.dumps(batch,indent=2)+'\n')
    manifest={'template':str(template),'template_sha256':_digest(template),'weather':str(weather),
              'weather_sha256':_digest(weather),'years':years,'cultivar':cultivar,
              'sowing_month':sow_month,'sowing_day':sow_day,
              'population_plants_m2':population,'row_spacing_mm':row_spacing_mm,
              'sowing_depth_mm':sowing_depth_mm,'fertiliser_enabled':False,'tillage_enabled':False,
              'apsim_executable':str(apsim),'dry_run':dry_run,
              'diagnostic_only':'Inherited SCE example soil and 2001–2011 Illinois weather; not site-calibrated',
              'runs':runs,'batch_config':str(config)}
    (output_dir/'multiyear_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest
