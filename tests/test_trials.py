import csv
from pathlib import Path
import sys,tempfile,unittest,json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sce.trials import load_trials,export_trials,TrialInputError
class Tests(unittest.TestCase):
 def write(self,base,data):
  path=base/'data.csv';path.write_text(data);return path
 def test_legacy_and_output(self):
  with tempfile.TemporaryDirectory() as x:
   base=Path(x);p=self.write(base,'Site,Planting,Latitude,Longitude,Crop,Genetics\nA,04/12/2017,47.449,8.682,soybean,mid000\nB,2017-05-04,40,-88,soybean,II\n')
   rows=load_trials(p);self.assertEqual(len(rows),2);self.assertEqual(rows[0]['maturity_class'],'mid000');self.assertEqual(rows[1]['maturity_class'],'')
   c,j=export_trials(rows,base/'out',source=p);self.assertTrue(c.exists());self.assertEqual(json.loads(j.read_text())['trial_count'],2)
   with self.assertRaises(FileExistsError):export_trials(rows,base/'out',source=p)
 def test_bad_coordinate_and_date(self):
  for value,dt in [('95','2017-04-12'),('nan','2017-04-12'),('47','2017-19-12')]:
   with self.subTest(value=value,dt=dt),tempfile.TemporaryDirectory() as x:
    p=self.write(Path(x),f'Site,Planting,Latitude,Longitude,Crop,Genetics\nA,{dt},{value},8,soybean,mid000\n')
    with self.assertRaises(TrialInputError):load_trials(p)
 def test_duplicate_ids(self):
  with tempfile.TemporaryDirectory() as x:
   p=self.write(Path(x),'Site,Planting,Latitude,Longitude,Crop,Genetics,trial_id\nA,2017-04-12,47,8,soybean,mid000,A\nA,2017-04-13,47,8,soybean,mid000,A\n')
   with self.assertRaisesRegex(TrialInputError,'duplicate'):load_trials(p)
 def test_invalid_crop_and_alias_collision(self):
  with tempfile.TemporaryDirectory() as x:
   p=self.write(Path(x),'Site,Planting,Latitude,Longitude,Crop,Genetics\nA,2017-04-12,47,8,maize,mid000\n')
   with self.assertRaisesRegex(TrialInputError,'soybean'):load_trials(p)
   p=self.write(Path(x),'Site,site_id,Planting,Latitude,Longitude,Crop,Genetics\nA,A,2017-04-12,47,8,soybean,mid000\n')
   with self.assertRaisesRegex(TrialInputError,'Ambiguous'):load_trials(p)
if __name__=='__main__':unittest.main()
