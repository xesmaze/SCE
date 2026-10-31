import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class SoilIntegrationTest(unittest.TestCase):
    def test_fayette_initialization(self):
        soil=ROOT/'data/soil_cache/dfc3c56f88cdddcc/soil_layers.csv'
        template=ROOT/'template_models/Soy_Template_v2.0_APSIM2026.apsimx'
        if not soil.exists() or not template.exists():
            self.skipTest('Optional Fayette integration fixture not installed')
        with tempfile.TemporaryDirectory() as td:
            model_file=Path(td)/'model.apsimx'
            result=subprocess.run([sys.executable,str(ROOT/'scripts/apply_usda_soil.py'),'--template',str(template),'--soil-csv',str(soil),'--output',str(model_file)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            model=json.loads(model_file.read_text())
            def walk(x):
                if isinstance(x,dict):
                    yield x
                    for v in x.values(): yield from walk(v)
                elif isinstance(x,list):
                    for v in x:yield from walk(v)
            ns=list(walk(model))
            find=lambda t: next(n for n in ns if n.get('$type','').split(',')[0]==t)
            physical=find('Models.Soils.Physical');water=find('Models.Soils.Water')
            self.assertEqual(water['InitialValues'],physical['DUL'])
            self.assertAlmostEqual(water['InitialPAWmm'],263.02,places=2)
            self.assertTrue(all(a<=l<=d<s for a,l,d,s in zip(physical['AirDry'],physical['LL15'],physical['DUL'],physical['SAT'])))

if __name__=='__main__':unittest.main()
