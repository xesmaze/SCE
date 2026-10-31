import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sce.rotation_defaults import make_preset, build_phase3_config, write_configs, PresetError

class Tests(unittest.TestCase):
    def test_no_till_default_and_override(self):
        x = make_preset('corn', 'no_till')
        self.assertEqual((x['planting_method'], x['row_spacing_m']), ('drill', .19))
        y = make_preset('corn','no_till', planting_method='planter', row_spacing_m=.76)
        self.assertEqual((y['planting_method'], y['row_spacing_m']), ('planter', .76))
        self.assertFalse(y['fertilise_at_sowing'])
        self.assertFalse(y['tillage'])

    def test_conventional_and_strip_metadata_not_fake_tillage(self):
        for till in ('conventional', 'strip_till'):
            x = make_preset('wheat',till)
            self.assertFalse(x['tillage'])
            self.assertEqual(x['tillage_implementation'],'unconfigured')
            self.assertEqual(x['residue_initialization'],'not_inferred_from_previous_crop')

    def test_invalid_values_and_fail_closed(self):
        for kwargs in ({'previous_crop':'bad', 'tillage_system':'no_till'},
                       {'previous_crop':'corn', 'tillage_system':'bad'},
                       {'previous_crop':'corn', 'tillage_system':'no_till', 'sowing_depth_mm':150},
                       {'previous_crop':'corn', 'tillage_system':'no_till', 'population_plants_m2':True}):
            with self.assertRaises(PresetError):make_preset(**kwargs)
        with self.assertRaises(PresetError):build_phase3_config({'trials': {'a': {'previous_crop':'corn'}}})

    def test_phase3_adapter_contract(self):
        inp = json.loads((Path(__file__).resolve().parents[1]/'examples/rotation_management_example.json').read_text())
        cfg, meta = build_phase3_config(inp)
        x = cfg['trials']['IL_2001_mid000']
        for k in ('maturity_class','planting_date','simulation_start','simulation_end',
                  'row_spacing_m','sowing_depth_mm','population_plants_m2',
                  'fertilise_at_sowing','tillage'):
            self.assertIn(k, x)
        self.assertEqual(meta['trials']['IL_2001_mid000']['previous_crop'],'corn')
        self.assertNotIn('previous_crop',x)

    def test_outputs_no_overwrite(self):
        source = Path(__file__).resolve().parents[1]/'examples/rotation_management_example.json'
        with tempfile.TemporaryDirectory() as tmp:
            a, b = write_configs(source, Path(tmp)/'out')
            self.assertTrue(a.exists() and b.exists())
            with self.assertRaises(PresetError):write_configs(source,Path(tmp)/'out')

if __name__=='__main__':unittest.main()
