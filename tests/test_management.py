import json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sce.management import inventory,stage,ManagementError

class ManagementTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.code=['// example synthetic manager', 'string cultivar = "midII";', 'string plant = "2017-05-04";', 'double pop = 50;', 'double rows = 0.60;', 'double depth = 40;']
        self.model={'Children':[{'$type':'Models.Core.Simulation, Models','Name':'Sim','Children':[
            {'$type':'Models.Clock, Models','Name':'Clock','Start':'2017-03-01T00:00:00','End':'2017-11-01T00:00:00'},
            {'$type':'Models.Core.Zone, Models','Name':'Field','Children':[
                {'$type':'Models.PMF.Plant, Models','Name':'Soybean','Children':[
                    {'$type':'Models.PMF.Cultivar, Models','Name':'midII'}]} ,
                {'$type':'Models.Manager, Models','Name':'SowMgr','CodeArray':self.code,'Children':[]}
            ]}]}]}
        sub=self.root/'env'/'A';sub.mkdir(parents=True)
        (sub/'A_environment.apsimx').write_text(json.dumps(self.model))
        self.source=sub/'A_environment.apsimx'
        (self.root/'env'/'environment_manifest.json').write_text(json.dumps({'format':'sce-v2-environment-v1','trials':[{'trial_id':'A','model_file':str(self.source),'weather':{'first_date':'2017-01-01','last_date':'2017-12-31'},'maturity_class':'midII','planting_date':'2017-05-04'}]}))
        self.cfg={'trials':{'A':{'maturity_class':'midII','planting_date':'2017-05-04','simulation_start':'2017-03-01','simulation_end':'2017-10-31','population_plants_m2':45,'row_spacing_m':.55,'sowing_depth_mm':35,
            'manager_edits':[{'manager_name':'SowMgr','code_replacements':[
                {'old':'double pop = 50;','new':'double pop = 45;'},
                {'old':'double rows = 0.60;','new':'double rows = 0.55;'},
                {'old':'double depth = 40;','new':'double depth = 35;'}]}],
            'required_code_tokens':['midII','2017-05-04','45','0.55','35']}}}
        (self.root/'cfg.json').write_text(json.dumps(self.cfg))
    def tearDown(self):self.temp.cleanup()
    def runstage(self):return stage(self.root/'env'/'environment_manifest.json',self.root/'cfg.json',self.root/'out')
    def test_stage_with_exact_verified_edits_non_destructively(self):
        source_bytes=self.source.read_bytes();p=self.runstage();self.assertTrue(p.is_file())
        self.assertEqual(source_bytes,self.source.read_bytes())
        model=json.loads((self.root/'out/A/A_configured.apsimx').read_text());it=inventory(self.root/'out/A/A_configured.apsimx')
        self.assertIn('double pop = 45;','\n'.join(it['managers'][0]['code']))
        self.assertTrue(it['clock']['End'].startswith('2017-10-31'))
        with self.assertRaisesRegex(ManagementError,'not empty'):self.runstage()
    def test_unresolved_maturity_fails_closed(self):
        self.cfg['trials']['A']['maturity_class']='II';(self.root/'cfg.json').write_text(json.dumps(self.cfg))
        with self.assertRaisesRegex(ManagementError,'explicit SCE'):self.runstage()
        self.assertFalse((self.root/'out').exists())
    def test_ambiguous_code_replacement_rejected(self):
        self.cfg['trials']['A']['manager_edits'][0]['code_replacements'][0]['old']='double';(self.root/'cfg.json').write_text(json.dumps(self.cfg))
        with self.assertRaisesRegex(ManagementError,'one occurrence'):self.runstage()
        self.assertFalse((self.root/'out').exists())
    def test_weather_window_and_missing_manager_rejected(self):
        self.cfg['trials']['A']['simulation_end']='2018-01-01';(self.root/'cfg.json').write_text(json.dumps(self.cfg))
        with self.assertRaisesRegex(ManagementError,'weather data'):self.runstage()
        self.cfg['trials']['A']['simulation_end']='2017-10-31'
        self.cfg['trials']['A']['manager_edits'][0]['manager_name']='NoManager'
        (self.root/'cfg.json').write_text(json.dumps(self.cfg))
        with self.assertRaisesRegex(ManagementError,'exactly one'):self.runstage()
        self.assertFalse((self.root/'out').exists())

if __name__=='__main__':unittest.main()
