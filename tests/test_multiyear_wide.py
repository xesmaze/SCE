import csv,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sce.multiyear import met_years, configure, run_multiyear, MultiYearError
from sce.wide import wide_export, WideError

class Tests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);self.p=Path(t.name)
        crop={'$type':'Models.PMF.Plant, Models','Name':'Soybean','Children':[{'$type':'Models.PMF.Cultivar, Models','Name':'mid000'}]}
        manager=lambda name,keys: {'$type':'Models.Manager, Models','Name':name,'Enabled':True,'CodeArray':['unchanged'], 'Parameters':[{'Key':k,'Value':'old'} for k in keys]}
        self.model={'Children':[{'$type':'Models.Core.Simulation, Models','Name':'Simulation','Children':[
            {'$type':'Models.Clock, Models','Name':'Clock','Start':'2001-01-01','End':'2001-12-31'},
            {'$type':'Models.Climate.Weather, Models','Name':'Weather','FileName':'wx.met'},crop,
            manager('Sowing',['SowDate','CultivarName','Population','RowSpacing','SowingDepth']),
            manager('Fertilise at sowing',[]),manager('Tillage on a fixed date',[])]}]}
        self.template=self.p/'test.apsimx';self.template.write_text(json.dumps(self.model))
        self.weather=self.p/'wx.met';self.weather.write_text('year day radn maxt mint rain\n'+'\n'.join(f'2001 {d} 12 25 10 0' for d in range(1,366)))
    def test_weather_coverage(self):
        self.assertTrue(met_years(self.weather)[2001])
        self.weather.write_text(self.weather.read_text().replace('2001 365 12 25 10 0',''))
        self.assertFalse(met_years(self.weather)[2001])
    def test_non_destructive_manager_settings(self):
        x=configure(self.template,2001,self.weather)
        sim=x['Children'][0]['Children'];sow=next(n for n in sim if n['Name']=='Sowing')
        self.assertEqual(dict((p['Key'],p['Value']) for p in sow['Parameters'])['CultivarName'],'mid000')
        self.assertEqual(sow['CodeArray'],['unchanged'])
        self.assertEqual(json.loads(self.template.read_text()),self.model)
        self.assertFalse(next(n for n in sim if n['Name']=='Fertilise at sowing')['Enabled'])
    def test_dry_run_and_preserve_results(self):
        m=run_multiyear(template=self.template,apsim=self.p/'absent',output_dir=self.p/'out',years=[2001],dry_run=True)
        self.assertEqual(m['years'],[2001]);self.assertTrue(Path(m['runs'][0]['model']).is_file())
        with self.assertRaisesRegex(MultiYearError,'not empty'):
            run_multiyear(template=self.template,apsim=self.p/'absent',output_dir=self.p/'out',years=[2001],dry_run=True)
    def test_invalid_weather_fail_closed(self):
        with self.assertRaisesRegex(MultiYearError,'Incomplete'):
            run_multiyear(template=self.template,apsim=self.p/'absent',output_dir=self.p/'out',years=[2005],dry_run=True)
        self.assertFalse((self.p/'out').exists())
    def test_wide_occurrence_alignment_and_exclusion(self):
        src=self.p/'stages.csv'
        rows=[dict(run_id='a',site='IL',year=2001,cultivar='mid000',maturity_group='000',stage_segment_id=i,stage_name=n,stage_class=c,Rain_sum=rain) for i,n,c,rain in [(1,'Emerging','phenological',10),(2,'Emerging','phenological',20),(3,'Unreported','harvest_transition',4)]]
        rows+= [dict(run_id='b',site='IL',year=2005,cultivar='mid000',maturity_group='000',stage_segment_id=1,stage_name='Emerging',stage_class='phenological',Rain_sum=8)]
        with src.open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
        out=self.p/'wide.csv';meta=wide_export(src,out)
        with out.open() as f:result={r['run_id']:r for r in csv.DictReader(f)}
        self.assertEqual(meta['runs'],2)
        self.assertEqual(result['a']['Emerging__occurrence02__Rain_sum'],'20')
        self.assertEqual(result['b']['Emerging__occurrence01__Rain_sum'],'8')
        self.assertFalse(any('Unreported' in c for c in result['a']))
        with self.assertRaisesRegex(WideError,'overwrite'):wide_export(src,out)
if __name__=='__main__':unittest.main()
