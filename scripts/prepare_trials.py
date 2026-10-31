#!/usr/bin/env python3
"""Standardize original SCE input.csv files into a Phase 1 trial manifest."""
from pathlib import Path
import argparse
import sys

# Works directly from a source checkout without pip installation.
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sce.trials import load_trials,export_trials,TrialInputError

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',required=True,type=Path,help='CSV, including original SCE Site/Planting/Latitude/Longitude/Crop/Genetics format')
    parser.add_argument('--output-dir',required=True,type=Path,help='New or empty output directory')
    args=parser.parse_args()
    try:
        records=load_trials(args.input)
        csv_path,manifest=export_trials(records,args.output_dir,source=args.input)
    except (OSError,TrialInputError) as exc:
        parser.exit(1,f'ERROR: {exc}\n')
    print(f'Validated {len(records)} soybean trials')
    print('Normalized CSV:',csv_path.resolve())
    print('JSON manifest:',manifest.resolve())
    unresolved=sum(not r['maturity_class'] for r in records)
    if unresolved:print(f'NOTE: {unresolved} trial(s) require an explicit early/mid/late maturity class before cultivar-specific simulation')
if __name__=='__main__':main()
