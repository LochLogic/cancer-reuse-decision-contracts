import copy,importlib.util,json,subprocess,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import contracts as dc
import build_examples as ex
class ContractTests(unittest.TestCase):
 def base(self):return ex.cohort()
 def altered(self,change):
  c=self.base();change(c);return dc.evaluate(c)
 def test_public_aliquot(self):self.assertEqual(dc.evaluate(self.base())['status'],'consistent')
 def test_public_sample(self):self.assertEqual(dc.evaluate(ex.cohort('sample'))['checks']['cohort']['units_over_limit'],160)
 def test_primary_marrow(self):self.assertEqual(dc.evaluate(ex.cohort('sample',1,'target-primary-marrow'))['checks']['cohort']['units_over_limit'],102)
 def test_replicate_policy_preserved(self):self.assertEqual(dc.evaluate(ex.cohort('sample',3))['status'],'consistent')
 def test_boolean_count_rejected(self):self.assertEqual(self.altered(lambda c:c['selection']['observation'].update(files=True))['status'],'invalid')
 def test_truthy_complete_rejected(self):self.assertEqual(self.altered(lambda c:c['selection'].update(complete='true'))['status'],'invalid')
 def test_negative_count(self):self.assertEqual(self.altered(lambda c:c['selection']['observation'].update(files=-1))['status'],'invalid')
 def test_impossible_histogram(self):self.assertEqual(self.altered(lambda c:c['selection']['observation']['units']['aliquot']['histogram'].update({'1':3226}))['status'],'invalid')
 def test_count_histogram_reconcile(self):self.assertEqual(self.altered(lambda c:c['selection']['observation']['units']['aliquot'].update(count=1))['status'],'invalid')
 def test_missing_mapping_no_pass(self):
  c=self.base();u=c['selection']['observation']['units']['aliquot'];u.update(files_without_unit=1,count=3226,histogram={'1':3226})
  self.assertEqual(dc.evaluate(c)['status'],'unknown')
 def test_ambiguous_mapping_no_pass(self):
  c=self.base();u=c['selection']['observation']['units']['aliquot'];u.update(files_with_multiple_units=1,count=3228,histogram={'1':3228})
  self.assertEqual(dc.evaluate(c)['status'],'unknown')
 def test_incomplete_no_pass(self):self.assertEqual(self.altered(lambda c:c['selection'].update(complete=False))['status'],'unknown')
 def test_wrong_total(self):self.assertEqual(self.altered(lambda c:c['selection']['pagination'].update(total=4000))['status'],'invalid')
 def test_query_tamper(self):self.assertEqual(self.altered(lambda c:c['selection']['query'].update(size=999))['status'],'invalid')
 def test_missing_unit_unknown(self):self.assertEqual(self.altered(lambda c:c['selection']['observation']['units'].pop('aliquot'))['status'],'unknown')
 def test_boolean_policy_limit(self):self.assertEqual(self.altered(lambda c:c['cohort'].update(max_files_per_unit=True))['status'],'invalid')
 def test_unsupported_policy_field(self):self.assertEqual(self.altered(lambda c:c['cohort'].update(clinically_valid=True))['status'],'invalid')
 def test_endpoint_nonreconstruction(self):
  r=dc.evaluate(ex.endpoint());self.assertEqual(r['status'],'violated');w=r['checks']['endpoint']['witness']
  a=ex.endpoint()['endpoint']['source_profile'];b=ex.endpoint()['endpoint']['target_profile']
  self.assertEqual(dc.derive(w['history_a'],a),dc.derive(w['history_b'],a));self.assertNotEqual(dc.derive(w['history_a'],b),dc.derive(w['history_b'],b))
 def test_raw_components_supported(self):self.assertEqual(dc.evaluate(ex.endpoint(True))['status'],'consistent')
 def test_equivalent_rules(self):
  c=ex.endpoint();c['endpoint']['target_profile']=copy.deepcopy(c['endpoint']['source_profile']);self.assertEqual(dc.evaluate(c)['status'],'consistent')
 def test_unknown_spec(self):
  c=ex.endpoint();del c['endpoint']['target_profile']['cutoff'];self.assertEqual(dc.evaluate(c)['status'],'unknown')
 def test_no_source_summary_unknown(self):
  c=ex.endpoint();c['endpoint']['available_components']=[];self.assertEqual(dc.evaluate(c)['status'],'unknown')
 def test_month_unit_unsupported(self):
  c=ex.endpoint();c['endpoint']['target_profile']['unit']='months';self.assertEqual(dc.evaluate(c)['status'],'invalid')
 def test_unknown_component_rejected(self):
  c=ex.endpoint();c['endpoint']['available_components'].append('magic');self.assertEqual(dc.evaluate(c)['status'],'invalid')
 def test_no_witness_stays_unknown(self):
  c=ex.endpoint();a=c['endpoint']['source_profile'];b=c['endpoint']['target_profile'];b['origin']='diagnosis';b['events']=list(reversed(a['events']))
  self.assertEqual(dc.evaluate(c)['status'],'unknown')
 def test_all_missing_no_derivation(self):
  h={'diagnosis':0,'randomization':0,'progression':None,'death':None,'death_with_tumor':False,'last_contact':None,'new_therapy':None,'last_pretherapy_assessment':None}
  self.assertIsNone(dc.derive(h,ex.ep_profile()))
 def test_event_classification(self):
  h={'diagnosis':0,'randomization':0,'progression':None,'death':100,'death_with_tumor':False,'last_contact':90,'new_therapy':None,'last_pretherapy_assessment':None}
  p=ex.ep_profile(events=['progression','death_with_tumor'],censor=['last_contact','death_without_tumor']);self.assertFalse(dc.derive(h,p)['event'])
  h['death_with_tumor']=True;self.assertTrue(dc.derive(h,p)['event'])
 def test_source_profile_cannot_be_guessed(self):
  c=ex.endpoint();c['endpoint'].pop('source_profile');self.assertEqual(dc.evaluate(c)['status'],'invalid')
 def test_current_decision(self):self.assertEqual(dc.evaluate(ex.examples()['aliquot'])['decision']['state'],'current')
 def test_policy_change_stale_even_if_valid(self):
  c=ex.examples()['labeled-replicates'];c['cohort']['unit']='aliquot';r=dc.evaluate(c);self.assertEqual(r['status'],'consistent');self.assertEqual(r['decision']['state'],'stale')
 def test_relationship_change_stale(self):
  c=ex.examples()['aliquot'];c['selection']['observation']['relationship_sha256']='a'*64;self.assertEqual(dc.evaluate(c)['decision']['state'],'stale')
 def test_capture_time_not_semantic_change(self):
  c=ex.examples()['aliquot'];c['selection']['captured_at_utc']='2030-01-01T00:00:00Z';self.assertEqual(dc.evaluate(c)['decision']['state'],'current')
 def test_evaluator_change_stale(self):
  c=ex.examples()['aliquot'];c['decision']['evaluator_sha256']='b'*64;self.assertEqual(dc.evaluate(c)['decision']['state'],'stale')
 def test_contradictory_proceed_rejected(self):
  with self.assertRaises(dc.Invalid):dc.decide(ex.cohort('sample'),'Example','proceed_under_declared_conditions','Ignore multiplicity')
 def test_duplicate_json_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'c.json';p.write_text('{"a":1,"a":2}')
   with self.assertRaises(dc.Invalid):dc.load(p)
 def test_nan_json_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'c.json';p.write_text('{"a":NaN}')
   with self.assertRaises(dc.Invalid):dc.load(p)
 def test_portable_export_and_replay(self):
  c=ex.examples()['aliquot']
  with tempfile.TemporaryDirectory() as d:
   dc.export_crate(c,d);r=dc.evaluate(dc.load(Path(d)/'contract.json'));self.assertEqual(r['decision']['state'],'current')
   self.assertEqual(r,dc.evaluate(c));self.assertEqual(len(json.loads((Path(d)/'ro-crate-metadata.json').read_text())['@graph']),5)
 def test_html_escapes_user_text(self):
  c=self.base();c['purpose']='<script>alert(1)</script>';self.assertNotIn('<script>',dc.report(c))
 def test_cli_invalid_structured(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'bad.json';p.write_text('[]');r=subprocess.run([sys.executable,str(ROOT/'contracts.py'),str(p)],capture_output=True,text=True)
   self.assertEqual(r.returncode,2);self.assertEqual(json.loads(r.stdout)['status'],'invalid');self.assertNotIn('Traceback',r.stderr)
 def test_input_unknown_field(self):self.assertEqual(self.altered(lambda c:c.update(trusted=True))['status'],'invalid')
 def test_combined_one_pass_is_not_overall_pass(self):
  r=dc.evaluate(ex.examples()['combined']);self.assertEqual(r['checks']['cohort']['status'],'consistent');self.assertEqual(r['checks']['endpoint']['status'],'violated');self.assertEqual(r['status'],'violated')
 def test_combined_missing_information_is_unknown(self):
  c=ex.examples()['combined'];del c['endpoint']['target_profile']['cutoff'];r=dc.evaluate(c)
  self.assertEqual(r['status'],'unknown');self.assertEqual(r['decision']['state'],'stale')
if __name__=='__main__':unittest.main()
