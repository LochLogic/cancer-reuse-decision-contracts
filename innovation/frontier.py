"""Optional symbolic analysis of information retained by an endpoint release.

Uses Z3 only for this extension. Core contracts.py remains standard-library-only.
Results concern all nonnegative integer-day histories in the explicit model,
not all clinically valid endpoints, permissions, privacy, or observed patients.
"""
import hashlib,itertools,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'work/solver-deps'))
import z3
import contracts as dc
MODEL_VERSION='integer-day-history-v1'
FIELDS=('randomization','progression','death','last_contact','new_therapy','last_pretherapy_assessment')
ASSUMPTIONS=['Diagnosis is the common day-zero reference; randomization is a nonnegative offset.',
 'Optional event/observation days are absent (-1) or nonnegative integers, with no upper date bound.',
 'Known progression, contact, therapy and randomization do not follow a known death.',
 'A pretherapy assessment, when present, requires a therapy date and does not follow it.',
 'Death-with-tumor is false when death is absent; it is not cause of death.',
 'Both compared histories have a defined source summary; target absence is a distinct outcome.',
 'Derivation follows the encoded event priority, censor maximum and origin clamp; clinical eligibility is outside the model.']
def history(prefix):
 h={k:z3.Int(prefix+'_'+k) for k in FIELDS};h['diagnosis']=z3.IntVal(0);h['death_with_tumor']=z3.Bool(prefix+'_tumor')
 rules=[h['randomization']>=0]+[h[k]>=-1 for k in FIELDS if k!='randomization']
 rules += [z3.Implies(h['death']<0,z3.Not(h['death_with_tumor']))]
 for k in ['randomization','progression','last_contact','new_therapy','last_pretherapy_assessment']:
  rules.append(z3.Implies(z3.And(h['death']>=0,h[k]>=0),h[k]<=h['death']))
 rules.append(z3.Implies(h['last_pretherapy_assessment']>=0,z3.And(h['new_therapy']>=0,h['last_pretherapy_assessment']<=h['new_therapy'])))
 return h,rules
def symbolic_derive(h,p):
 dc.profile(p,'symbolic_profile')
 if set(dc.PROFILE_KEYS)-set(p):raise dc.Invalid('Symbolic analysis requires complete profiles')
 cutoff=h['new_therapy'] if p['cutoff'] else z3.IntVal(-1)
 def eligible(v):return z3.And(v>=0,z3.Or(cutoff<0,v<=cutoff))
 ev=z3.IntVal(-1);cs=z3.IntVal(-1)
 for name in p['events']:
  v=h['progression'] if name=='progression' else h['death'];ok=eligible(v)
  if name=='death_with_tumor':ok=z3.And(ok,h['death_with_tumor'])
  ev=z3.If(z3.And(ok,z3.Or(ev<0,v<ev)),v,ev)
 for name in p['censor_at']:
  v=h['death'] if name=='death_without_tumor' else h[name];ok=eligible(v)
  if name=='death_without_tumor':ok=z3.And(ok,z3.Not(h['death_with_tumor']))
  cs=z3.If(z3.And(ok,v>cs),v,cs)
 exists=z3.Or(ev>=0,cs>=0);event=ev>=0;date=z3.If(event,ev,cs)
 elapsed=z3.If(exists,z3.If(date>=h[p['origin']],date-h[p['origin']],0),-1)
 return {'defined':exists,'elapsed_days':elapsed,'event':event}
def observations(h,source):
 return {**h,'source_elapsed_days':source['elapsed_days'],'source_event':source['event'],
  'source_30day_bin':source['elapsed_days']/30,'within_bin_day':source['elapsed_days']%30,
  'origin_offset':h['randomization']-h['diagnosis']}
def different(a,b):return z3.Or(a['defined']!=b['defined'],z3.And(a['defined'],b['defined'],z3.Or(a['elapsed_days']!=b['elapsed_days'],a['event']!=b['event'])))
def concrete(m,h):
 return {k:(z3.is_true(m.eval(v,model_completion=True)) if k=='death_with_tumor' else (None if m.eval(v,model_completion=True).as_long()<0 else m.eval(v,model_completion=True).as_long())) for k,v in h.items()}
def plain_observations(h,p):
 x=dc.derive(h,p);assert x is not None
 return {**h,'source_elapsed_days':x['elapsed_days'],'source_event':x['event'],'source_30day_bin':x['elapsed_days']//30,'within_bin_day':x['elapsed_days']%30,'origin_offset':h['randomization']-h['diagnosis']}
def binding():
 return {'model':MODEL_VERSION,'model_assumptions':ASSUMPTIONS,'solver':z3.get_version_string(),'implementation_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),ROOT/'contracts.py']}}
class Analyzer:
 def __init__(self,source,target,timeout_ms=5000,artifact_dir=None):
  self.source=source;self.target=target;self.a,ra=history('a');self.b,rb=history('b')
  sa=symbolic_derive(self.a,source);sb=symbolic_derive(self.b,source)
  self.oa=observations(self.a,sa);self.ob=observations(self.b,sb)
  self.ta=symbolic_derive(self.a,target);self.tb=symbolic_derive(self.b,target)
  self.base=ra+rb+[sa['defined'],sb['defined'],different(self.ta,self.tb)]
  self.timeout=timeout_ms;self.cache={};self.artifact_dir=Path(artifact_dir) if artifact_dir else None
 def check(self,available,artifact=None):
  available=tuple(sorted(set(available)))
  if set(available)-set(self.oa):raise dc.Invalid('Unsupported information component')
  if available in self.cache and artifact is None:return self.cache[available]
  solver=z3.Solver();solver.set(timeout=self.timeout);solver.add(*self.base)
  solver.add(*[self.oa[k]==self.ob[k] for k in available]);smt=solver.to_smt2();answer=solver.check()
  result={'available':list(available),'status':'determined_in_model' if answer==z3.unsat else 'ambiguous' if answer==z3.sat else 'unknown','smt_sha256':hashlib.sha256(smt.encode()).hexdigest()}
  if self.artifact_dir:
   self.artifact_dir.mkdir(parents=True,exist_ok=True)
   (self.artifact_dir/(result['smt_sha256']+'.smt2')).write_text(smt,encoding='utf-8',newline='\n')
  if answer==z3.sat:
   m=solver.model();a=concrete(m,self.a);b=concrete(m,self.b);oa=plain_observations(a,self.source);ob=plain_observations(b,self.source)
   assert all(oa[k]==ob[k] for k in available)
   ta=dc.derive(a,self.target);tb=dc.derive(b,self.target);assert ta!=tb
   result['witness']={'history_a':a,'history_b':b,'shared_information':{k:oa[k] for k in available},'target_a':ta,'target_b':tb,'synthetic':True}
  elif answer==z3.unknown:result['reason']=solver.reason_unknown()
  if artifact:
   artifact=Path(artifact);artifact.parent.mkdir(parents=True,exist_ok=True);artifact.write_text(smt,encoding='utf-8',newline='\n')
  self.cache[available]=result;return result
 def frontier(self,available,candidates):
  if not isinstance(available,(list,set,tuple)) or not isinstance(candidates,(list,set,tuple)) or not all(isinstance(k,str) for k in list(available)+list(candidates)):raise dc.Invalid('Components must be collections of names')
  if (set(available)|set(candidates))-set(self.oa):raise dc.Invalid('Unsupported information component')
  available=set(available);candidates=sorted(set(candidates)-available)
  if len(candidates)>10:raise dc.Invalid('At most ten candidate supplements per request')
  minima=[];unknown=[];checks=0
  for size in range(len(candidates)+1):
   for extra in itertools.combinations(candidates,size):
    extra=set(extra)
    if any(set(x)<=extra for x in minima):continue
    r=self.check(available|extra);checks+=1
    if r['status']=='determined_in_model':minima.append(sorted(extra))
    elif r['status']=='unknown':unknown.append(sorted(extra))
  # A minimum requires a counterexample for removing each proposed component.
  verified=[]
  for m in minima:
   witnesses={k:self.check(available|set(m)-{k}) for k in m}
   verified.append({'additional_components':m,'sufficiency':'determined_in_model','minimality_established':all(x['status']=='ambiguous' for x in witnesses.values()),'removal_checks':witnesses})
  return {'minimal_supplements':verified,'status':'complete_in_model' if not unknown else 'incomplete_due_to_solver_unknown','unknown_subsets':unknown,'solver_calls':checks,'candidate_universe':candidates,'scope':'Inclusion-minimal among the declared candidate components, within the stated integer-day model. Field count is not a privacy measure.'}
def main():
 import argparse
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('request');p.add_argument('--out');args=p.parse_args()
 q=dc.load(args.request);a=Analyzer(q['source_profile'],q['target_profile'])
 result={'request_id':q['id'],'request':q,**binding(),'input_sha256':dc.digest(q),'baseline':a.check(q['available_components']),'frontier':a.frontier(q['available_components'],q['candidate_components']),'decision_scope':'Planning evidence only. Review source binding and model assumptions before acting; no automatic proceed decision.'}
 s=json.dumps(result,indent=2)+'\n'
 if args.out:Path(args.out).write_text(s,encoding='utf-8')
 else:print(s)
if __name__=='__main__':main()
