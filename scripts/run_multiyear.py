#!/usr/bin/env python3
"""Run 2001/2005/2010 mid000 diagnostic seasons using SCE v2 and native APSIM."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sce.multiyear import run_multiyear,MultiYearError

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--template',default='template_models/Soy_Template_v2.0_APSIM2026.apsimx')
    p.add_argument('--apsim',default='/Applications/APSIM2026.10.8138.0.app/Contents/Resources/bin/Models')
    p.add_argument('--weather',default=None)
    p.add_argument('--output-dir',default='multiyear_2001_2005_2010')
    p.add_argument('--years',type=int,nargs='+',default=[2001,2005,2010])
    p.add_argument('--cultivar',default='mid000')
    p.add_argument('--dry-run',action='store_true',help='Stage models but do not execute APSIM')
    a=p.parse_args()
    try:print(json.dumps(run_multiyear(template=a.template,apsim=a.apsim,weather=a.weather,output_dir=a.output_dir,years=a.years,cultivar=a.cultivar,dry_run=a.dry_run),indent=2))
    except (MultiYearError,OSError,ValueError) as e:p.exit(1,f'ERROR: {e}\n')
if __name__=='__main__':main()
