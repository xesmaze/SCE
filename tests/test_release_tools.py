"""Release-tool regression tests, requiring only Python standard library."""
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import textwrap
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]

def load_module(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / 'scripts' / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

fix = load_module('fix_reaperman_apsim2026', 'fix_reaperman_apsim2026.py')
runner = load_module('run_sce_v2', 'run_sce_v2.py')


def template(lines=None):
    return {'Children': [{'Name': 'Simulation', 'Children': [
        {'Name': 'ReaperMan', 'CodeArray': lines or [
            'using Models.Core;', '[Link] IPlant Crop;',
            'var p = Crop.FindByPath("Phenology.Stage");',
            'var a = Crop.FindByPath("Leaf.LAI");']},
        {'Name': 'Unchanged', 'SomeData': [1, 2, 3]}
    ]}]}


class ReaperManTests(unittest.TestCase):
    def test_only_field_type_changes_and_second_call_untouched(self):
        original = template()
        modified = json.loads(json.dumps(original))
        updated, line = fix.patch_model(modified)
        self.assertTrue(updated)
        self.assertEqual(line, 2)
        self.assertEqual(modified['Children'][0]['Children'][0]['CodeArray'][1], '[Link] Models.PMF.Plant Crop;')
        self.assertEqual(modified['Children'][0]['Children'][0]['CodeArray'][2:],
                         original['Children'][0]['Children'][0]['CodeArray'][2:])
        self.assertEqual(original['Children'][0]['Children'][0]['CodeArray'][1], '[Link] IPlant Crop;')
        again, _ = fix.patch_model(modified)
        self.assertFalse(again)

    def test_rejects_ambiguous_and_missing_managers(self):
        with self.assertRaises(ValueError):
            fix.patch_model({'Children': []})
        with self.assertRaises(ValueError):
            fix.patch_model({'Children': [{'Name': 'ReaperMan', 'CodeArray': ['[Link] IPlant Crop;']},
                                               {'Name': 'ReaperMan', 'CodeArray': ['[Link] IPlant Crop;']}]})
        with self.assertRaises(ValueError):
            fix.patch_model(template(['[Link] IPlant Crop;', '[Link] IPlant Crop;']))

    def test_cli_non_destructive_idempotent_and_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp)/'original.apsimx'
            out = Path(tmp)/'patched.apsimx'
            source = json.dumps(template())
            src.write_text(source)
            self.assertEqual(fix.main(['--input', str(src), '--output', str(out)]), 0)
            self.assertEqual(src.read_text(), source)
            self.assertEqual(fix.main(['--input', str(src), '--output', str(out)]), 0)
            self.assertEqual(fix.main(['--input', str(out), '--check']), 0)
            self.assertEqual(fix.main(['--input', str(src), '--check']), 1)
            with self.assertRaises(SystemExit):
                fix.main(['--input', str(src), '--output', str(src)])


class CLIRunnerTests(unittest.TestCase):
    def test_runner_stages_weather_and_preserves_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            model = root/'test.apsimx'
            weather = root/'z_12.met'
            weather.write_text('test weather')
            model.write_text(json.dumps({'Children': [{'$type':'Models.Climate.Weather, Models', 'FileName':'z_12.met'}]}))
            original = model.read_text()
            old_db = root/'test.db'
            old_db.write_text('preserve existing DB')
            fake = root/'Models'
            fake.write_text('#!/usr/bin/env python3\n'
                            'import sqlite3, sys\n'
                            'from pathlib import Path\n'
                            'p=Path(sys.argv[1]).with_suffix(".db")\n'
                            'con=sqlite3.connect(p)\n'
                            'con.execute("CREATE TABLE Report (Date TEXT, Stage REAL)")\n'
                            'con.execute("INSERT INTO Report VALUES (?, ?)", ("2017-04-12", 1.0))\n'
                            'con.commit(); con.close()\n')
            fake.chmod(0o755)
            out = runner.run(model, fake, 30)
            self.assertEqual(out['report_rows'], 1)
            self.assertIn('Stage', out['report_columns'])
            self.assertEqual(original, model.read_text())
            self.assertEqual(old_db.read_text(), 'preserve existing DB')
            staged = json.loads(Path(out['staged_model']).read_text())
            self.assertEqual(staged['Children'][0]['FileName'], str(weather.resolve()))
            next_out = runner.run(model, fake, 30)
            self.assertNotEqual(out['run_directory'], next_out['run_directory'])
            self.assertTrue(Path(next_out['database']).is_file())

    def test_missing_weather_fails_without_touching_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            model=Path(tmp)/'test.apsimx'
            model.write_text(json.dumps({'Children':[{'$type':'Models.Climate.Weather, Models', 'FileName':'missing.met'}]}))
            fake=Path(tmp)/'Models'
            fake.touch()
            with self.assertRaises(FileNotFoundError):
                runner.run(model, fake, 30)
            self.assertFalse((Path(tmp)/'sce_runs').exists())


if __name__ == '__main__':
    unittest.main()
