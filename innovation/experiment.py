"""Predeclared mechanisms and reproducible producer release comparison."""
import itertools,json,random,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(Path(__file__).parent))
import build_examples as ex,contracts as dc
from frontier import Analyzer,ASSUMPTIONS,MODEL_VERSION,symbolic_derive,history,plain_observations,z3,binding
def requests():
 p=ex.ep_profile();r=ex.ep_profile(origin='randomization');t=ex.ep_profile(events=['progression','death_with_tumor'],censor=['last_contact','death_without_tumor']);cut=ex.ep_profile(censor=['last_contact','last_pretherapy_assessment'],cutoff='new_therapy')
 base=['source_elapsed_days','source_event']
 return [
 {'id':'forward-origin','source_profile':p,'target_profile':r,'available_components':base,'candidate_components':['origin_offset','progression','death','last_contact'],'expert_baseline':'One origin offset suffices: target elapsed = max(source elapsed - offset, 0); preserve event flag.'},
 {'id':'reverse-origin-clamp','source_profile':r,'target_profile':p,'available_components':base+['origin_offset'],'candidate_components':['progression','death','last_contact'],'expert_baseline':'Adding an offset cannot invert a zero-clamped source endpoint in general.'},
 {'id':'death-classification','source_profile':p,'target_profile':t,'available_components':base,'candidate_components':['progression','death','death_with_tumor','last_contact'],'expert_baseline':'A death-with-tumor flag alone does not locate an earlier or later progression or the relevant censoring time.'},
 {'id':'therapy-cutoff','source_profile':p,'target_profile':cut,'available_components':base,'candidate_components':['new_therapy','last_pretherapy_assessment','progression','death','last_contact'],'expert_baseline':'Complete target-input collection is sufficient; compare which additional fields are necessary after accounting for an existing summary.'},
 {'id':'same-definition','source_profile':p,'target_profile':p,'available_components':base,'candidate_components':['origin_offset','progression','death','last_contact'],'expert_baseline':'Identical declared rules require no supplement.'},
 {'id':'unavailable-repair','source_profile':p,'target_profile':t,'available_components':base,'candidate_components':['origin_offset','last_contact'],'expert_baseline':'These candidate fields omit information that distinguishes relevant event histories.'},
 {'id':'coarsened-time','source_profile':p,'target_profile':p,'available_components':['source_30day_bin','source_event'],'candidate_components':['within_bin_day','progression','death','last_contact'],'expert_baseline':'Quotient plus remainder reconstructs elapsed days; a 30-day bin alone does not.'}]
def equivalence_checks():
 # Cross-check the separately encoded symbolic derivation against existing Python
 # on held-out synthetic times, including large values outside the old finite grid.
 rng=random.Random(731904);hs=[]
 for i in range(160):
  death=rng.choice([None,0,1,31,127,10000]);bound=death if death is not None else 20000
  h={'diagnosis':0,'randomization':rng.randint(0,bound),'death':death,'death_with_tumor':False if death is None else bool(rng.getrandbits(1))}
  for k in ['progression','last_contact','new_therapy']:h[k]=None if rng.random()<.3 else rng.randint(0,bound)
  h['last_pretherapy_assessment']=None if h['new_therapy'] is None or rng.random()<.3 else rng.randint(0,h['new_therapy'])
  hs.append(h)
 profiles=[ex.ep_profile(),ex.ep_profile(origin='randomization'),ex.ep_profile(events=['progression','death_with_tumor'],censor=['last_contact','death_without_tumor']),ex.ep_profile(origin='randomization',censor=['last_contact','last_pretherapy_assessment'],cutoff='new_therapy')]
 count=0
 for h in hs:
  sh={k:z3.BoolVal(v) if type(v) is bool else z3.IntVal(-1 if v is None else v) for k,v in h.items()}
  for p in profiles:
   x=symbolic_derive(sh,p);exists=z3.is_true(z3.simplify(x['defined']));actual=None if not exists else {'elapsed_days':z3.simplify(x['elapsed_days']).as_long(),'event':z3.is_true(z3.simplify(x['event']))}
   assert actual==dc.derive(h,p),(h,p,actual,dc.derive(h,p));count+=1
 return {'histories':len(hs),'profiles':len(profiles),'matched':count,'seed':731904,'scope':'Two code encodings, synthetic held-out times; not independent clinical validation. Existing 28 admiral reference comparisons remain separate.'}
def main():
 out=ROOT/'innovation';(out/'requests').mkdir(exist_ok=True);records=[]
 for q in requests():
  (out/'requests'/f"{q['id']}.json").write_text(json.dumps(q,indent=2)+'\n')
  a=Analyzer(q['source_profile'],q['target_profile'],artifact_dir=out/'obligations');r={'request':q,'request_sha256':dc.digest(q),'baseline':a.check(q['available_components'],out/'smt'/f"{q['id']}-baseline.smt2"),'frontier':a.frontier(q['available_components'],q['candidate_components'])}
  for i,m in enumerate(r['frontier']['minimal_supplements']):
   a.check(q['available_components']+m['additional_components'],out/'smt'/f"{q['id']}-sufficient-{i}.smt2")
  r['obligations']=list(a.cache.values())
  records.append(r)
 releases=[('Summary',['source_elapsed_days','source_event']),('Summary + origin offset',['source_elapsed_days','source_event','origin_offset']),('Summary + cutoff support',['source_elapsed_days','source_event','new_therapy','last_contact','last_pretherapy_assessment']),('30-day bins',['source_30day_bin','source_event'])]
 target_names=['same-definition','forward-origin','death-classification','therapy-cutoff'];matrix=[]
 for label,fields in releases:
  cells={}
  for n in target_names:
   q=next(x for x in requests() if x['id']==n);a=Analyzer(q['source_profile'],q['target_profile'],artifact_dir=out/'obligations');cells[n]=a.check(fields)
  matrix.append({'release':label,'shared_components':fields,'questions':cells})
 result={**binding(),'scope':'Synthetic specification experiment, no real patient records, no release permission or privacy certification.','requests':records,'producer_release_matrix':matrix,'encoding_crosscheck':equivalence_checks()}
 (out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({'results':[{ 'id':x['request']['id'],'baseline':x['baseline']['status'],'minimal_supplements':[m['additional_components'] for m in x['frontier']['minimal_supplements']],'complete':x['frontier']['status']} for x in records],'crosscheck':result['encoding_crosscheck']},indent=2))
if __name__=='__main__':main()
