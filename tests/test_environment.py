import json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sce.environment import prepare,weather_validate,apply_initial_state,EnvironmentError

class EnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.d=tempfile.TemporaryDirectory();self.root=Path(self.d.name)
        soil={'$type':'Models.Soils.Soil, Models','Name':'Soil','Children':[
            {'Name':'Physical','Thickness':[150,150],'AirDry':[.04,.06],'SAT':[.45,.42],'Children':[]},
            {'Name':'Water','Thickness':[150,150],'InitialValues':[.2,.2],'Children':[]},
            {'Name':'NO3','Thickness':[150,150],'InitialValues':[1,1],'InitialValuesUnits':0,'Children':[]},
            {'Name':'NH4','Thickness':[150,150],'InitialValues':[1,1],'InitialValuesUnits':0,'Children':[]}]}
        self.soil=soil
        self.base={'Name':'Simulations','Children':[{'$type':'Models.Core.Simulation, Models','Name':'Sim','Children':[
            {'$type':'Models.Core.Zone, Models','Name':'Field','Children':[soil]},
            {'$type':'Models.Climate.Weather, Models','Name':'Weather','FileName':'z_12.met','Children':[]}]}]}
        (self.root/'template.apsimx').write_text(json.dumps(self.base))
        (self.root/'donor.apsimx').write_text(json.dumps({'Children':[soil]}))
        (self.root/'n.json').write_text(json.dumps({'nitrogen_units':'ppm','water_units':'mm/mm',
            'no3_ppm':[10,5],'nh4_ppm':[2,1], 'water_mm_mm':[.22,.23]}))
        (self.root/'sample.met').write_text('! weather\nlatitude = 40.1\ntav = 12\namp = 20\nyear day radn maxt mint rain\n() () (MJ/m2) (oC) (oC) (mm)\n2017 1 12 22 8 0\n2017 2 15 24 7 2\n')
        (self.root/'manifest.json').write_text(json.dumps({'format':'sce-v2-trials-v1','trials':[
            {'trial_id':'A','year':2017,'maturity_class':'mid000'}]}))
        (self.root/'config.json').write_text(json.dumps({'trials':{'A':{
            'weather_file':'sample.met','soil_file':'donor.apsimx','initial_state_file':'n.json'}}}))
    def tearDown(self):self.d.cleanup()
    def execute(self):return prepare(self.root/'manifest.json',self.root/'template.apsimx',
        self.root/'config.json',self.root/'result',self.root)
    def test_stages_non_destructive_and_initial_state(self):
        original=(self.root/'template.apsimx').read_bytes();path=self.execute()
        output=json.loads((self.root/'result/A/A_environment.apsimx').read_text())
        weather=output['Children'][0]['Children'][1]
        soil=output['Children'][0]['Children'][0]['Children'][0]
        # self.assertEqual(weather['FileName'], str(self.root / 'sample.met'))
        self.assertEqual(
            Path(weather['FileName']).resolve(),
            (self.root / 'sample.met').resolve()
        )
        # self.assertEqual(weather['FileName'],str(self.root/'sample.met'))
        self.assertEqual(soil['Children'][2]['InitialValues'],[10.,5.])
        self.assertEqual(soil['Children'][3]['InitialValues'],[2.,1.])
        self.assertEqual(soil['Children'][1]['InitialValues'],[.22,.23])
        self.assertEqual((self.root/'template.apsimx').read_bytes(),original)
        self.assertTrue(path.exists())
        self.assertTrue(json.loads(path.read_text())['trials'][0]['ready_for_phase3'])
        with self.assertRaises(EnvironmentError):self.execute()
    def test_reject_invalid_units_and_water(self):
        state=json.loads((self.root/'n.json').read_text());state['nitrogen_units']='kg/ha'
        with self.assertRaisesRegex(EnvironmentError,'nitrogen_units'):apply_initial_state(self.soil,state)
        state['nitrogen_units']='ppm';state['water_mm_mm']=[.5,.1]
        with self.assertRaisesRegex(EnvironmentError,'AirDry'):apply_initial_state(self.soil,state)
    def test_reject_bad_weather_and_missing_days(self):
        self.assertEqual(weather_validate(self.root/'sample.met',2017)['n_days'],2)
        text=(self.root/'sample.met').read_text().replace('2017 2','2017 3')
        (self.root/'sample.met').write_text(text)
        with self.assertRaisesRegex(EnvironmentError,'missing days'):self.execute()
        self.assertFalse((self.root/'result').exists())
    def test_missing_required_trial_env_fails_closed(self):
        config=json.loads((self.root/'config.json').read_text());del config['trials']['A']['soil_file']
        (self.root/'config.json').write_text(json.dumps(config))
        with self.assertRaisesRegex(EnvironmentError,'require weather_file'):self.execute()
        self.assertFalse((self.root/'result').exists())

if __name__=='__main__':unittest.main()
