#!/usr/bin/env python3
import argparse
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from sce.rotation_defaults import write_configs, PresetError


def main():
    parser = argparse.ArgumentParser(description='Prepare Phase3 management configuration from rotation and tillage choices')
    parser.add_argument('--input', required=True)
    parser.add_argument('--output-dir', required=True)
    a = parser.parse_args()
    try:
        config, scenario = write_configs(a.input, a.output_dir)
    except (PresetError, ValueError, OSError) as exc:
        parser.exit(2, f'ERROR: {exc}\n')
    print(f'Phase 3 config: {config}\nProvenance: {scenario}')

if __name__ == '__main__':
    main()
