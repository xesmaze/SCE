#!/usr/bin/env python3
"""Generate one-row-per-run stage covariate matrix from Phase 5 batch stages."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sce.wide import wide_export,WideError

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stages',required=True)
    p.add_argument('--output',required=True)
    args=p.parse_args()
    try:print(json.dumps(wide_export(args.stages,args.output),indent=2))
    except (WideError,OSError,ValueError) as e:p.exit(1,f'ERROR: {e}\n')
if __name__=='__main__':main()
