import json,sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parent))
from frontier import Analyzer,z3,dc,binding,history,symbolic_derive,observations,different
from experiment import requests

def query(name):return next(q for q in requests() if q['id']==name)
def analyzer(q):return Analyzer(q['source_profile'],q['target_profile'])
class FrontierTests(unittest.TestCase):
 def test_forward_matches_expert_algebra(self):
  q=query('forward-origin');a=analyzer(q)
  self.assertEqual(a.check(q['available_components']+['origin_offset'])['status'],'determined_in_model')
  h,r=history('expert');src=symbolic_derive(h,q['source_profile']);tar=symbolic_derive(h,q['target_profile'])
  s=z3.Solver();s.add(*r,src['defined']);s.add(z3.Or(tar['event']!=src['event'],tar['elapsed_days']!=z3.If(src['elapsed_days']>=h['randomization'],src['elapsed_days']-h['randomization'],0)))
  self.assertEqual(s.check(),z3.unsat)
 def test_reverse_offset_is_not_inverse(self):
  q=query('reverse-origin-clamp');r=analyzer(q).check(q['available_components']);self.assertEqual(r['status'],'ambiguous');self.assertNotEqual(r['witness']['target_a'],r['witness']['target_b'])
 def test_death_flag_alone_fails(self):
  q=query('death-classification');self.assertEqual(analyzer(q).check(q['available_components']+['death_with_tumor'])['status'],'ambiguous')
 def test_no_repair_in_universe(self):
  q=query('unavailable-repair');self.assertEqual(analyzer(q).frontier(q['available_components'],q['candidate_components'])['minimal_supplements'],[])
 def test_multiple_inclusion_minima(self):
  q=query('coarsened-time');r=analyzer(q).frontier(q['available_components'],q['candidate_components'])
  self.assertEqual([x['additional_components'] for x in r['minimal_supplements']],[['within_bin_day'],['death','last_contact','progression']]);self.assertTrue(all(x['minimality_established'] for x in r['minimal_supplements']))
 def test_unknown_never_claims_sufficiency(self):
  q=query('forward-origin');a=analyzer(q)
  with patch.object(a,'check',return_value={'status':'unknown'}):r=a.frontier(q['available_components'],q['candidate_components'])
  self.assertEqual(r['minimal_supplements'],[]);self.assertEqual(r['status'],'incomplete_due_to_solver_unknown')
 def test_unknown_removal_never_claims_minimality(self):
  q=query('forward-origin');a=analyzer(q)
  with patch.object(a,'check',side_effect=lambda available:{'status':'determined_in_model' if 'origin_offset' in available else 'unknown'}):r=a.frontier(q['available_components'],['origin_offset'])
  self.assertFalse(r['minimal_supplements'][0]['minimality_established']);self.assertEqual(r['status'],'incomplete_due_to_solver_unknown')
 def test_unknown_field_rejected(self):
  with self.assertRaises(dc.Invalid):analyzer(query('forward-origin')).check(['bogus'])
 def test_large_universe_rejected(self):
  with self.assertRaises(dc.Invalid):analyzer(query('forward-origin')).frontier([],list(map(str,range(11))))
 def test_unsupported_candidate_not_hidden_by_empty_repair(self):
  q=query('same-definition')
  with self.assertRaises(dc.Invalid):analyzer(q).frontier(q['available_components'],['invented_field'])
 def test_string_is_not_a_component_list(self):
  with self.assertRaises(dc.Invalid):analyzer(query('same-definition')).frontier('source_event',[])
 def test_incomplete_profile_rejected(self):
  q=query('forward-origin');q['target_profile'].pop('origin')
  with self.assertRaises(dc.Invalid):analyzer(q)
 def test_assumption_dependency(self):
  # Relax only chronology. Old reverse-origin supplement is insufficient if a
  # death can precede randomization. This is an adversarial model mutation,
  # not a proposed clinical model.
  q=query('reverse-origin-clamp');a=analyzer(q);old=q['available_components']+['last_contact','progression']
  self.assertEqual(a.check(old)['status'],'determined_in_model')
  s=z3.Solver()
  for h in [a.a,a.b]:
   s.add(h['randomization']>=0,*[h[k]>=-1 for k in ['progression','death','last_contact','new_therapy','last_pretherapy_assessment']],z3.Implies(h['death']<0,z3.Not(h['death_with_tumor'])))
   s.add(symbolic_derive(h,q['source_profile'])['defined'])
  s.add(different(a.ta,a.tb),*[a.oa[k]==a.ob[k] for k in old]);self.assertEqual(s.check(),z3.sat)
 def test_bound_to_both_implementations(self):
  b=binding();self.assertEqual(set(b['implementation_sha256']),{'frontier.py','contracts.py'});self.assertTrue(b['model_assumptions'])
if __name__=='__main__':unittest.main()
