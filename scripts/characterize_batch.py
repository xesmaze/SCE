#!/usr/bin/env python3
"""Aggregate Phase 4 outputs from multiple APSIM SQLite databases."""
import argparse, json, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sce.batch import process_batch, BatchError
from sce.characterization import CharacterizationError

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',required=True,help='JSON manifest with runs array')
    p.add_argument('--output-dir',required=True)
    args=p.parse_args()
    try: print(json.dumps(process_batch(args.config,args.output_dir),indent=2))
    except (BatchError,CharacterizationError,OSError,ValueError) as exc:p.exit(1,f'ERROR: {exc}\n')
if __name__=='__main__':main()
