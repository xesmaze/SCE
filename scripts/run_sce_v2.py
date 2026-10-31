#!/usr/bin/env python3
"""Run a prepared SCE v2.0 APSIMX model in an isolated output directory.

Resolves relative APSIM Weather.FileName paths against the SOURCE model's folder,
then writes a staged copy and runs APSIM there. Never modifies the source model or
its existing .db. Each invocation creates a fresh uniquely named run directory.

This is an APSIM execution/report runner, not an end-to-end SCE calibration tool.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import uuid

DEFAULT_MAC_APSIM = '/Applications/APSIM2026.10.8138.0.app/Contents/Resources/bin/Models'


def _resolve_weather(tree: object, source_dir: Path) -> list[str]:
    """Update only Weather.FileName fields in the staged *in-memory* model."""
    paths = []
    def visit(node):
        if isinstance(node, dict):
            typ = node.get('$type', '')
            if typ.split(',')[0] == 'Models.Climate.Weather':
                name = node.get('FileName')
                if not isinstance(name, str) or not name.strip():
                    raise ValueError('APSIM Weather node has no FileName')
                p = Path(name).expanduser()
                if not p.is_absolute():
                    p = source_dir / p
                p = p.resolve()
                if not p.is_file():
                    raise FileNotFoundError(f'Weather file not found: {p} (source model directory: {source_dir})')
                node['FileName'] = str(p)
                paths.append(str(p))
            for v in node.values():
                visit(v)
        elif isinstance(node, list):
            for v in node:
                visit(v)
    visit(tree)
    return paths


def run(model: Path, apsim: Path, timeout: int, output_dir: Path | None = None):
    model = Path(model).expanduser().resolve()
    apsim = Path(apsim).expanduser().resolve()
    if not model.is_file():
        raise FileNotFoundError(f'APSIM model missing: {model}')
    if not apsim.is_file():
        raise FileNotFoundError(f'APSIM executable missing: {apsim}')
    # Parsing before allocating a directory prevents creating junk output on invalid input.
    tree = json.loads(model.read_text())
    weather_files = _resolve_weather(tree, model.parent)
    output_root = Path(output_dir).expanduser().resolve() if output_dir else model.parent / 'sce_runs'
    output_root.mkdir(parents=True, exist_ok=True)
    # Unique and non-destructive even for repeated runs and concurrent launches.
    workdir = output_root / f'{model.stem}_{uuid.uuid4().hex[:12]}'
    workdir.mkdir(exist_ok=False)
    staged = workdir / model.name
    staged.write_text(json.dumps(tree, indent=2, ensure_ascii=False) + '\n')
    db = staged.with_suffix('.db')
    result = subprocess.run([str(apsim), str(staged)], cwd=str(workdir),
                            capture_output=True, text=True, timeout=timeout)
    log = workdir / 'apsim_run.log'
    log.write_text(f'exit_code={result.returncode}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}\n')
    if result.returncode:
        raise RuntimeError(f'APSIM returned {result.returncode}. Log: {log}\n'
                           f'{result.stdout[-800:]}\n{result.stderr[-1600:]}')
    if not db.is_file():
        raise RuntimeError(f'APSIM returned success but no SQLite DB was found at {db}. Log: {log}')
    with sqlite3.connect(db) as connection:
        table = connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='Report'").fetchone()
        if not table:
            raise RuntimeError(f'No Report table in {db}')
        rows = connection.execute('SELECT COUNT(*) FROM "Report"').fetchone()[0]
        columns = [item[1] for item in connection.execute('PRAGMA table_info("Report")')]
    if rows < 1:
        raise RuntimeError(f'Report table is empty in {db}')
    return {'database': str(db), 'report_rows': rows, 'report_columns': columns,
            'model': str(model), 'staged_model': str(staged), 'weather_files': weather_files,
            'run_directory': str(workdir), 'apsim': str(apsim)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--apsim', type=Path, default=Path(DEFAULT_MAC_APSIM))
    parser.add_argument('--output-dir', type=Path, default=None,
                        help='Base directory for isolated runs (default: <model parent>/sce_runs)')
    parser.add_argument('--timeout', type=int, default=240)
    args = parser.parse_args(argv)
    try:
        summary = run(args.model, args.apsim, args.timeout, args.output_dir)
    except (RuntimeError, ValueError, FileNotFoundError, FileExistsError, subprocess.TimeoutExpired) as err:
        print(f'FAILED: {err}', file=sys.stderr)
        return 1
    print(json.dumps(summary, indent=2))
    return 0

if __name__ == '__main__':
    sys.exit(main())
