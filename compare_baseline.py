"""Actual JSON Schema baseline and independent RO-Crate reader.

This compares selected workflow features, not speed, human outcomes, or a claim
that generic tools cannot implement the domain profile we propose.
"""
import copy,importlib.metadata,json,sys
from pathlib import Path
import jsonschema
import contracts as dc
import build_examples as ex
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'work/deps'))
from rocrate.rocrate import ROCrate
def conventional_check(c):
 if 'selection' not in c:return {'data_valid':None,'reason':'No selection table in this synthetic endpoint fixture.'}
 s=c['selection'];u=s['observation']['units'][c['cohort']['unit']];limit=c['cohort']['max_files_per_unit']
 schema={'type':'object','required':['histogram','count','files_without_unit','files_with_multiple_units'],
  'properties':{'histogram':{'type':'object','properties':{str(k):{'type':'integer','minimum':1} for k in range(1,limit+1)},'additionalProperties':False},
   'count':{'type':'integer','minimum':0},'files_without_unit':{'const':0},'files_with_multiple_units':{'const':0}}}
 try:
  jsonschema.validate(u,schema);jsonschema.validate(s['observation']['files'],{'type':'integer','minimum':1})
  count=sum(u['histogram'].values());links=sum(int(k)*v for k,v in u['histogram'].items())
  valid=s['complete'] is True and count==u['count'] and links==s['observation']['files']==s['pagination']['total']
  return {'data_valid':valid,'reason':'Schema and independently programmed cardinality reconciliation.'}
 except jsonschema.ValidationError:return {'data_valid':False,'reason':'Declared histogram/mapping condition failed.'}
def reference_alignment():
 # The reference was actually executed in admiral 1.4.2, independently of this core.
 ref=json.loads((ROOT/'evidence/reference/admiral-results.json').read_text())
 rows=ref['outputs'];actual={(x['history'],x['profile']):x for x in rows}
 profiles={'DIAG_ANY_DEATH':ex.ep_profile(),'RAND_ANY_DEATH':ex.ep_profile(origin='randomization'),
 'DIAG_DEATH_WITH_TUMOR':ex.ep_profile(events=['progression','death_with_tumor'],censor=['last_contact','death_without_tumor']),
 'RAND_THERAPY_CUTOFF':ex.ep_profile(origin='randomization',censor=['last_contact','last_pretherapy_assessment'],cutoff='new_therapy')}
 histories=[]
 for i,(o,p,d,l,t,pre) in enumerate([(0,100,None,180,None,None),(30,100,None,180,None,None),(0,None,100,90,None,None),
   (0,120,None,180,80,60),(0,None,None,180,None,None),(0,None,None,None,None,None),(0,None,150,120,None,None)],1):
  histories.append({'diagnosis':0,'randomization':o,'progression':p,'death':d,'death_with_tumor':i==7,'last_contact':l,'new_therapy':t,'last_pretherapy_assessment':pre})
 comparisons=[]
 for i,h in enumerate(histories,1):
  for n,p in profiles.items():
   x=actual.get(('H'+str(i),n));got=dc.derive(h,p)
   expected=None if x is None else {'elapsed_days':x['elapsed_days'],'event':x['censored']==0}
   assert got==expected,(i,n,got,expected)
   comparisons.append({'history':'H'+str(i),'profile':n,'result':got,'admiral_match':True})
 return {'runtime':ref['runtime'],'comparisons':comparisons,'scope':'Seven synthetic histories, four mechanism profiles; not full clinical endpoint implementations.'}
def main():
 examples=ex.examples();results=[];crates=[]
 for n,c in examples.items():
  jsonschema.validate(c,json.loads((ROOT/'contract.schema.json').read_text()))
  base=conventional_check(c);ours=dc.evaluate(c)
  results.append({'example':n,'baseline':base,'contract':{'status':ours['status'],'decision':ours['decision']['state']}})
  crate=ROCrate(str(ROOT/'demo'/n));assert crate.root_dataset.id=='./'
  parts=crate.root_dataset.get('hasPart');assert len(parts)==3
  for part in parts:
   p=ROOT/'demo'/n/part.id;assert p.is_file()
  crates.append({'example':n,'rocrate_python_reader_loaded':True,'files':len(parts),
    'scope':'Reader structure and local parts only; not an independent SHACL conformance certification.'})
 # Exactly matched competence: baseline detects the same cardinality failures.
 assert next(x for x in results if x['example']=='sample')['baseline']['data_valid'] is False
 for n in ['aliquot','labeled-replicates','primary-marrow','stale-decision']:
  assert next(x for x in results if x['example']==n)['baseline']['data_valid'] is True
 r={'jsonschema_version':importlib.metadata.version('jsonschema'),'rocrate_version':importlib.metadata.version('rocrate'),
  'cases':results,'crate_reader_checks':crates,'reference_alignment':reference_alignment(),
  'conclusion':'Cardinality checking is not new. Proposed addition is an application profile preserving target/use, bounded reconstruction explanation, recorded choice and its validity conditions. RO-Crate and validation tools can host this extension; no algorithmic superiority, tool incapability, user efficiency or universal clinical validity claim.'}
 (ROOT/'evidence/baseline-results.json').write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({'baseline_cases':len(results),'crates_read':len(crates),'admiral_matches':len(r['reference_alignment']['comparisons']),
   'jsonschema_version':r['jsonschema_version'],'rocrate_version':r['rocrate_version'],'conclusion':r['conclusion']},indent=2))
if __name__=='__main__':main()
