#!/usr/bin/env python3
from pathlib import Path
import argparse,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from sce.environment import prepare,EnvironmentError
p=argparse.ArgumentParser(description='SCE v2 Phase 2: stage trial weather and soil in APSIM, without simulation')
p.add_argument('--manifest',required=True);p.add_argument('--template',required=True)
p.add_argument('--config',required=True);p.add_argument('--output-dir',required=True)
p.add_argument('--repo-root',default=None)
a=p.parse_args()
try:
    result=prepare(a.manifest,a.template,a.config,a.output_dir,a.repo_root)
    print('Prepared APSIM environmental inputs:',result)
except (OSError,ValueError,KeyError) as ex:
    p.exit(1,'ERROR: '+str(ex)+'\n')
