#!/usr/bin/env python3
"""Non-destructive SCE v2 release preflight and optional existing-results audit."""
import argparse, csv, json, math, subprocess, sys
from pathlib import Path

TEST_PATTERNS = ('test_release_tools.py','test_trials.py','test_environment.py',
                 'test_management.py','test_characterization.py','test_batch.py',
                 'test_multiyear_wide.py')
REQUIRED = ('sce/trials.py','sce/environment.py','sce/management.py',
            'sce/characterization.py','sce/batch.py','sce/wide.py','sce/multiyear.py',
            'scripts/run_sce_v2.py','scripts/prepare_trials.py',
            'scripts/prepare_environment.py','scripts/prepare_management.py',
            'scripts/characterize_season.py','scripts/characterize_batch.py',
            'scripts/run_multiyear.py','scripts/export_wide.py',
            'scripts/fix_reaperman_apsim2026.py',
            'template_models/Soy_Template_v2.0_APSIM2026.apsimx')

def fail(message):
    print('FAIL:',message,file=sys.stderr); return False

def audit_wide(root, target):
    p=root/target
    if not p.is_file(): return fail(f'Wide matrix not found: {p}')
    with p.open(newline='') as f:
        reader=csv.DictReader(f); cols=reader.fieldnames; rows=list(reader)
    if not cols or len(cols)!=len(set(cols)):return fail('Duplicate or missing CSV headers')
    if 'run_id' not in cols:return fail('No run_id column')
    ids=[r['run_id'] for r in rows]
    if not ids or len(ids)!=len(set(ids)):return fail('No runs or repeated run_id')
    non_numeric={'run_id','site','year','cultivar','simulation_id','maturity_group','sowing_date','harvest_date'}
    numeric=0;missing=0
    for col in cols:
        if col in non_numeric:continue
        values=[r[col].strip() for r in rows]
        nonempty=[v for v in values if v]
        if not nonempty:
            missing+=len(values);continue
        try:
            converted=[float(x) for x in nonempty]
        except ValueError:
            continue
        numeric+=1
        if any(not math.isfinite(x) for x in converted):return fail(f'Nonfinite value in {col}')
        missing+=len(values)-len(nonempty)
    print(f'PASS: wide matrix rows={len(rows)}, numeric_columns={numeric}, missing_numeric_cells={missing}, duplicate_headers=0')
    print('run_ids:', ', '.join(ids))
    return True

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',type=Path,default=Path('.'))
    p.add_argument('--run-tests',action='store_true',help='Execute all available SCE v2 test files')
    p.add_argument('--wide',type=Path,help='Optional path to existing wide matrix, relative to repo')
    a=p.parse_args();root=a.repo.resolve()
    missing=[str(v) for v in REQUIRED if not (root/v).is_file()]
    if missing:
        fail('Missing required Phase 1–5 release files: '+', '.join(missing));return 1
    print('PASS: required Python modules, scripts and APSIM template present')
    try:
        model=json.loads((root/'template_models/Soy_Template_v2.0_APSIM2026.apsimx').read_text())
        assert isinstance(model,dict)
    except (OSError,ValueError,AssertionError) as exc:
        fail(f'Invalid APSIMX JSON: {exc}');return 1
    print('PASS: APSIMX JSON parses (not a replacement for native model validation)')
    if a.run_tests:
        for test in TEST_PATTERNS:
            if not (root/'tests'/test).is_file():
                fail(f'Test file not found: {test}');return 1
            print('Running', test,flush=True)
            cmd=[sys.executable,'-m','unittest','discover','-s','tests','-p',test,'-v']
            code=subprocess.run(cmd,cwd=root,check=False).returncode
            if code:return fail(f'Regression test failed: {test}') or 1
        print('PASS: all seven named regression test suites')
    if a.wide and not audit_wide(root,a.wide):return 1
    print('Release preflight passed; native macOS APSIM and site-data validation remain separate checks.')
    return 0

if __name__=='__main__':raise SystemExit(main())
