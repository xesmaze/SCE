#!/usr/bin/env python3
"""Create daily and phenological-stage SCE covariates from an APSIM Report DB."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sce.characterization import characterize,CharacterizationError

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--db',required=True,help='APSIM sqlite Report database')
    p.add_argument('--output-dir',required=True)
    p.add_argument('--simulation-id',type=int)
    p.add_argument('--sow-date',help='Override event date YYYY-MM-DD if required')
    p.add_argument('--harvest-date',help='Override event date YYYY-MM-DD if required')
    p.add_argument('--include-pre-sowing',action='store_true',help='Include all days before sowing')
    p.add_argument('--stress-threshold',type=float,default=0.8,help='Count observed stress-factor days strictly below this threshold (0..1)')
    args=p.parse_args()
    try:
        manifest=characterize(args.db,args.output_dir,args.simulation_id,args.sow_date,args.harvest_date,args.include_pre_sowing,args.stress_threshold)
        print(json.dumps(manifest,indent=2))
    except (CharacterizationError,ValueError,OSError) as exc:
        p.exit(1,f'ERROR: {exc}\n')
if __name__=='__main__':main()
