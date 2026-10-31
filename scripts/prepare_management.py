#!/usr/bin/env python3
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sce.management import inventory,stage,ManagementError
p=argparse.ArgumentParser(description='SCE v2 Phase 3: inspect managers and stage explicit crop configurations')
p.add_argument('--inspect',help='Inspect one Phase 2 model and print manager code and cultivar names')
p.add_argument('--environment-manifest')
p.add_argument('--config')
p.add_argument('--output-dir')
a=p.parse_args()
try:
    if a.inspect:print(json.dumps(inventory(a.inspect),indent=2))
    else:
        if not all((a.environment_manifest,a.config,a.output_dir)):p.error('supply --environment-manifest, --config, --output-dir')
        print('Prepared:',stage(a.environment_manifest,a.config,a.output_dir))
except (ManagementError,ValueError,KeyError,OSError) as e:
    p.exit(1,'ERROR: '+str(e)+'\n')
