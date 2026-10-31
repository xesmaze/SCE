#!/usr/bin/env python3
"""SCE v2 integrated one-site/one-year ERA5 + USDA soil -> APSIM -> Phase 4.

No modification of the checked-in template; no residue/tillage effect simulation.
Uses existing cached inputs when supplied; no need to download large spatial grids.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
from datetime import date

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
from sce.characterization import characterize
from apply_usda_soil import get_node, nodes
from run_rotation_native import get_node as named_node, set_parameters


def execute(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(f"Command failed ({result.returncode}): {' '.join(map(str, cmd))}\n{result.stdout[-3000:]}\n{result.stderr[-3000:]}")
    return result


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(args):
    source = json.loads(args.site.read_text())
    site = source['site']
    management = source.get('management', {})
    weather_settings = source.get('environment', {}).get('weather', {})
    soil_settings = source.get('environment', {}).get('soil', {})
    if not (-90 <= float(site['latitude']) <= 90 and -180 <= float(site['longitude']) <= 180):
        raise ValueError('Invalid coordinates')
    if args.year < int(source['simulation']['start_year']) or args.year > int(source['simulation']['end_year']):
        raise ValueError('Year outside site manifest period')
    if args.output.exists():
        raise FileExistsError(f'Output exists: {args.output}')
    if not args.template.is_file() or not args.apsim.is_file():
        raise FileNotFoundError('APSIM template or executable not found')
    args.output.mkdir(parents=True)
    weather = args.weather
    if weather is None:
        if weather_settings.get('source') != 'era5':
            raise ValueError('Use --weather for station/met sources; automatic acquisition supports ERA5 only')
        acquire = HERE / 'acquire_openmeteo_weather.py'
        execute([sys.executable, str(acquire), '--latitude', str(site['latitude']), '--longitude', str(site['longitude']), '--start-year', str(args.year), '--end-year', str(args.year), '--model', 'era5', '--output-dir', str(args.output/'weather')])
        weather = args.output/'weather'/'weather.met'
    weather = weather.resolve()
    if not weather.is_file():
        raise FileNotFoundError(weather)
    soil = args.soil_csv
    if soil is None:
        if soil_settings.get('source') not in ('gnatsgo', 'usda', 'sda'):
            raise ValueError('Use --soil-csv for other soil providers')
        # Site-level USDA SDA query, not the 10 m gNATSGO raster.
        acquire = HERE/'acquire_usda_horizons.py'
        execute([sys.executable,str(acquire),'--site-manifest',str(args.site),'--cache-dir',str(args.output/'soil_cache'),'--yes'])
        candidates = list((args.output/'soil_cache').glob('*/soil_layers.csv'))
        if len(candidates)!=1:
            raise RuntimeError('USDA acquisition did not create one soil_layers.csv')
        soil = candidates[0]
    soil = soil.resolve()
    if not soil.is_file():
        raise FileNotFoundError(soil)
    staged = args.output/'soil_staged.apsimx'
    execute([sys.executable,str(HERE/'apply_usda_soil.py'),'--template',str(args.template.resolve()),'--soil-csv',str(soil),'--output',str(staged)])
    model=json.loads(staged.read_text())
    clock=named_node(model,'Clock','Models.Clock')
    for k, v in [('Start',f'{args.year}-01-01'),('End',f'{args.year}-12-31')]:
        old=str(clock[k]); clock[k]=v+('T00:00:00' if 'T' in old else '')
    weather_nodes=[n for n in nodes(model) if 'Models.Climate.Weather' in str(n.get('$type','')) and 'FileName' in n]
    if not weather_nodes: raise ValueError('Weather node missing')
    for n in weather_nodes: n['FileName']=str(weather)
    sow=date.fromisoformat(args.sowing_date or f'{args.year}-04-12')
    if sow.year!=args.year: raise ValueError('Sowing year must match simulation year')
    method=management.get('planting_method','drill')
    spacing=args.spacing_mm if args.spacing_mm is not None else (190 if method=='drill' else 500)
    sowing=named_node(model,'Sowing','Models.Manager')
    set_parameters(sowing,{'SowDate':f'{sow.day}-{sow.strftime("%b").lower()}', 'CultivarName':args.cultivar,'Population':str(args.population),'RowSpacing':str(spacing),'SowingDepth':str(args.depth_mm)})
    for name in ('Fertilise at sowing','Tillage on a fixed date'):
        named_node(model,name,'Models.Manager')['Enabled']=False
    model_file=args.output/'SCE_configured.apsimx'
    model_file.write_text(json.dumps(model,indent=2)+'\n')
    proc=subprocess.run([str(args.apsim.resolve()),str(model_file.resolve())],cwd=str(args.output),capture_output=True,text=True)
    (args.output/'apsim_stdout.log').write_text(proc.stdout)
    (args.output/'apsim_stderr.log').write_text(proc.stderr)
    if proc.returncode:
        raise RuntimeError(f'APSIM returned {proc.returncode}. See {args.output}/apsim_stdout.log and apsim_stderr.log: {proc.stdout[-2500:]}')
    db=model_file.with_suffix('.db')
    if not db.is_file(): raise RuntimeError(f'No APSIM database: {db}')
    with sqlite3.connect(db) as conn:
        n=conn.execute('SELECT COUNT(*) FROM "Report"').fetchone()[0]
    if n < 365 or n > 366: raise RuntimeError(f'Unexpected Report row count {n}')
    characterization=characterize(db,args.output/'characterization')
    summary={'status':'PASS','site_id':site['site_id'],'year':args.year,'reported_days':n,'model':str(model_file),'db':str(db),'weather':str(weather),'soil_csv':str(soil),'weather_sha256':sha(weather),'soil_sha256':sha(soil),'template_sha256':sha(args.template),'sowing_requested':sow.isoformat(),'planting_method':method,'spacing_mm':spacing,'depth_mm':args.depth_mm,'soil_initial_water':'100% PAWC at DUL (assumed)','soil_depth_extension':'max 300 mm deepest horizon (assumed)','soil_crop_LL':'survey LL15 (assumed)','KL_XF':'inherited from SCE template','previous_crop':management.get('previous_crop'),'tillage':management.get('tillage'),'tillage_residue_physics_implemented':False,'characterization':characterization}
    (args.output/'sce_run_manifest.json').write_text(json.dumps(summary,indent=2,default=str)+'\n')
    print(json.dumps({'status':'PASS','report_rows':n,'model':str(model_file),'database':str(db),'characterization_dir':str(args.output/'characterization')},indent=2))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--site',type=Path,required=True)
    p.add_argument('--year',type=int,required=True)
    p.add_argument('--template',type=Path,default=ROOT/'template_models/Soy_Template_v2.0_APSIM2026.apsimx')
    p.add_argument('--apsim',type=Path,default=Path('/Applications/APSIM2026.10.8138.0.app/Contents/Resources/bin/Models'))
    p.add_argument('--weather',type=Path,help='Existing .met (omit to acquire ERA5)')
    p.add_argument('--soil-csv',type=Path,help='Existing standardized soil CSV (omit to fetch USDA)')
    p.add_argument('--cultivar',default='mid000')
    p.add_argument('--sowing-date')
    p.add_argument('--population',type=float,default=40)
    p.add_argument('--spacing-mm',type=float)
    p.add_argument('--depth-mm',type=float,default=30)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    try: run(a)
    except Exception as e: p.exit(1,f'ERROR: {e}\n')
if __name__=='__main__': main()
