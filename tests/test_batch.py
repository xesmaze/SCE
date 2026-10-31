import json,sqlite3,sys,tempfile,unittest,csv
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sce.batch import process_batch,BatchError

class TestBatch(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.db=self.root/'data.db'
        with sqlite3.connect(self.db) as c:
            c.execute('CREATE TABLE Report (SimulationID INTEGER, Zone TEXT, Date TEXT, StageName TEXT, Stage REAL, SimSowDate TEXT, SimHarvestDate TEXT, Rain REAL, Radn REAL, MaxT REAL, MinT REAL, ThermalTime REAL, AccEmTT REAL, WaterStress REAL)')
            c.executemany('INSERT INTO Report VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',[
                (1,'Field','2001-04-12','Germinating',1,'2001-04-12','NA',0,10,20,10,5,5,1),
                (1,'Field','2001-04-13','Vegetative',3,'NA','NA',1,11,21,11,7,12,.6),
                (1,'Field','2001-04-14',None,11,'NA','2001-04-14',0,12,22,12,0,12,1)])
        self.cfg=self.root/'config.json'
        self.runs=[dict(run_id='IL_2001_mid000',site='IL',year=2001,cultivar='mid000',database='data.db')]
        self._config()
    def _config(self):self.cfg.write_text(json.dumps({'runs':self.runs,'stress_threshold':.8}))
    def test_export_preserves_transition_and_provenance(self):
        man=process_batch(self.cfg,self.root/'out')
        self.assertEqual(man['n_runs'],1)
        self.assertEqual(len(man['input_provenance'][0]['sha256']),64)
        with (self.root/'out'/'stage_comparison.csv').open() as f:rows=list(csv.DictReader(f))
        self.assertEqual(len(rows),2)
        self.assertEqual([r['stage_name'] for r in rows],['Germinating','Vegetative'])
        with (self.root/'out'/'batch_stages.csv').open() as f:all_stages=list(csv.DictReader(f))
        self.assertEqual(all_stages[-1]['stage_class'],'harvest_transition')
        self.assertEqual(all_stages[1]['WaterStress_days_below_threshold'],'1')
        with (self.root/'out'/'batch_daily.csv').open() as f:daily=list(csv.DictReader(f))
        self.assertEqual(len(daily),3)
        self.assertEqual(daily[1]['run_id'],'IL_2001_mid000')
    def test_multiple_runs_and_no_overwrite(self):
        self.runs.append(dict(run_id='IL_2001_mid00',site='IL',year=2001,cultivar='mid00',database='data.db'))
        self._config()
        m=process_batch(self.cfg,self.root/'out')
        self.assertEqual(m['n_runs'],2)
        with self.assertRaisesRegex(BatchError,'Output exists'):process_batch(self.cfg,self.root/'out')
    def test_duplicate_and_missing_file(self):
        self.runs.append(dict(self.runs[0]));self._config()
        with self.assertRaisesRegex(BatchError,'duplicate'):process_batch(self.cfg,self.root/'o')
        self.runs[1]['run_id']='different';self.runs[1]['database']='missing.db';self._config()
        with self.assertRaisesRegex(BatchError,'missing database'):process_batch(self.cfg,self.root/'o')
    def test_year_mismatch_rejected_before_write(self):
        self.runs[0]['year']=2002;self._config()
        with self.assertRaisesRegex(BatchError,'do not match'):process_batch(self.cfg,self.root/'o')
        self.assertFalse((self.root/'o').exists())
    def test_invalid_threshold(self):
        self.cfg.write_text(json.dumps({'runs':self.runs,'stress_threshold':1.5}))
        with self.assertRaisesRegex(BatchError,'stress_threshold'):process_batch(self.cfg,self.root/'o')

if __name__=='__main__':unittest.main()
