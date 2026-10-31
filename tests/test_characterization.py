import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import csv,sqlite3,tempfile,unittest
from sce.characterization import characterize,load_report,build,CharacterizationError

class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.db=self.root/'season.db'
        with sqlite3.connect(self.db) as c:
            c.execute('CREATE TABLE Report (SimulationID INTEGER, Zone TEXT, Date TEXT, StageName TEXT, Stage REAL, SimSowDate TEXT, SimHarvestDate TEXT, Rain REAL, Radn REAL, MaxT REAL, MinT REAL, ThermalTime REAL, AccEmTT REAL, WaterStress REAL, NO3 REAL)')
            rows=[(1,'Field','2001-04-11','PreSowing',0,'NA','NA',3,10,20,5,0,0,1,20),
                  (1,'Field','2001-04-12','Sowing',1,'2001-04-12','NA',0,11,21,6,5,5,.8,19),
                  (1,'Field','2001-04-13','Vegetative',3,'NA','NA',0,12,22,7,7,12,.7,18),
                  (1,'Field','2001-04-14','Vegetative',3,'NA','NA',4,13,23,8,9,21,.9,17),
                  (1,'Field','2001-04-15','Mature',10,'NA','2001-04-15',0,14,24,9,6,27,.5,16)]
            c.executemany('INSERT INTO Report VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',rows)
    def test_stage_and_cumulative(self):
        r=load_report(self.db);d,st,cov,man=build(r)
        self.assertEqual(len(d),4);self.assertEqual(len(st),3)
        self.assertEqual(st[1]['stage_name'],'Vegetative')
        self.assertEqual(st[1]['Rain_sum'],4)
        self.assertEqual(st[1]['Radn_sum'],25)
        self.assertAlmostEqual(st[1]['WaterStress_mean'],.8)
        self.assertEqual(st[1]['longest_consecutive_dry_days'],1)
        self.assertEqual(man['sowing_date'],'2001-04-12')
    def test_real_outputs_and_nonoverwrite(self):
        output=self.root/'out';m=characterize(self.db,output)
        self.assertEqual(m['n_season_days'],4)
        for f in ['daily_phenology.csv','stage_summary.csv','stage_covariates.csv','characterization_manifest.json']:
            self.assertTrue((output/f).exists())
        with self.assertRaises(CharacterizationError): characterize(self.db,output)
    def test_missing_gaps_or_mixed_simulation(self):
        with sqlite3.connect(self.db) as c:
            c.execute("DELETE FROM Report WHERE Date='2001-04-14'")
        with self.assertRaisesRegex(CharacterizationError,'not contiguous'):load_report(self.db)
        with sqlite3.connect(self.db) as c:
            c.execute("INSERT INTO Report SELECT 2,Zone,'2002-04-11',StageName,Stage,SimSowDate,SimHarvestDate,Rain,Radn,MaxT,MinT,ThermalTime,AccEmTT,WaterStress,NO3 FROM Report WHERE Date='2001-04-11'")
        with self.assertRaisesRegex(CharacterizationError,'Multiple SimulationID'):load_report(self.db)
    def test_repeated_stage_forms_distinct_segments(self):
        r=load_report(self.db)
        r[3]['StageName']='Sowing'
        _,s,_,_=build(r)
        self.assertEqual([x['stage_name'] for x in s],['Sowing','Vegetative','Sowing','Mature'])
    def test_stress_deficit_and_threshold(self):
        _,st,_,meta=build(load_report(self.db),stress_threshold=0.8)
        veg=st[1]
        self.assertAlmostEqual(veg['WaterStress_deficit_factor_days'],0.4)
        self.assertEqual(veg['WaterStress_days_below_threshold'],1)
        self.assertEqual(veg['WaterStress_max_consecutive_days_below_threshold'],1)
        self.assertEqual(veg['WaterStress_stress_observed_days'],2)
        self.assertEqual(meta['stress_threshold'],0.8)
    def test_harvest_transition_preserves_raw_data(self):
        with sqlite3.connect(self.db) as c:
            c.execute("UPDATE Report SET StageName=NULL WHERE Date='2001-04-15'")
        daily,st,_,meta=build(load_report(self.db))
        self.assertEqual(len(daily),4)
        self.assertEqual(st[-1]['stage_name'],'Unreported')
        self.assertEqual(st[-1]['stage_class'],'harvest_transition')
        self.assertFalse(st[-1]['include_in_biological_stage_summary'])
        self.assertEqual(daily[-1]['stage_class'],'harvest_transition')
        self.assertEqual(meta['n_harvest_transition_days'],1)
    def test_missing_stress_requires_coverage(self):
        with sqlite3.connect(self.db) as c:
            c.execute("UPDATE Report SET WaterStress=NULL WHERE Date='2001-04-14'")
        _,st,_,_=build(load_report(self.db))
        self.assertIsNone(st[1]['WaterStress_deficit_factor_days'])
        self.assertEqual(st[1]['WaterStress_stress_missing_days'],1)
        self.assertEqual(st[1]['WaterStress_days_below_threshold'],1)
    def test_invalid_stress_factor_rejected(self):
        with sqlite3.connect(self.db) as c:
            c.execute("UPDATE Report SET WaterStress=1.4 WHERE Date='2001-04-14'")
        with self.assertRaisesRegex(CharacterizationError,'outside'):
            build(load_report(self.db))
    def test_missing_data_not_zero(self):
        with sqlite3.connect(self.db) as c:c.execute("UPDATE Report SET Rain=NULL WHERE Date='2001-04-14'")
        _,s,_,_=build(load_report(self.db))
        self.assertIsNone(s[1]['Rain_sum'])
        self.assertEqual(s[1]['Rain_observed_days'],1)
if __name__=='__main__':unittest.main()
