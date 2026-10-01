"""Build inspectable examples. Decisions are demonstrations, not user outcomes."""
import copy,json,sys
from pathlib import Path
import contracts as dc
ROOT=Path(__file__).resolve().parent
def selection(name):return json.loads((ROOT/'evidence'/f'{name}.json').read_text())
def cohort(unit='aliquot',limit=1,name='target-all'):
 return {'schema_version':'0.1','id':f'{name}-{unit}-{limit}','purpose':f'Illustrative {unit}-level file-cardinality decision for a public expression selection.',
  'selection':selection(name),'cohort':{'unit':unit,'max_files_per_unit':limit,
    'policy':'Retain labeled aliquot files; interpret repeated units within the declared structure.' if limit>1 else 'Require at most one selected file per declared unit; do not choose files automatically.',
    'evidence_binding':'Aggregate metadata independently reconciled against TSV; cardinality only.'}}
def ep_profile(origin='diagnosis',events=None,censor=None,cutoff=None):
 return {'origin':origin,'events':events or ['progression','death_any'],'censor_at':censor or ['last_contact'],
  'cutoff':cutoff,'unit':'days','definition_source':'https://pharmaverse.github.io/admiral/cran-release/reference/derive_param_tte.html',
  'definition_scope':'Synthetic mechanism fixture, not a full clinical or regulatory endpoint definition.'}
def endpoint(raw=False):
 return {'schema_version':'0.1','id':'synthetic-clock-'+('raw' if raw else 'summary'),'purpose':'Synthetic illustration: can a diagnosis-based endpoint summary support a randomization-based elapsed-time target?',
  'endpoint':{'source_profile':ep_profile(),'target_profile':ep_profile(origin='randomization'),
    'available_components':['source_elapsed_days','source_event']+(['randomization','progression','death','last_contact'] if raw else []),
    'component_evidence':'Declared components of an invented fixture. No patient data supplied.',
    'binding':'Synthetic rule binding; source citations explain mechanisms, not clinical approval.'}}
def examples():
 out={}
 out['aliquot']=dc.decide(cohort(),'Demonstration author','proceed_under_declared_conditions','Retain aliquots as labeled rows under the cardinality condition; make no patient-independence claim.')
 out['sample']=dc.decide(cohort('sample'),'Demonstration author','revise_analysis','The one-file-per-sample condition is violated; specify a selection or repeated-unit policy before this intended construction.')
 out['labeled-replicates']=dc.decide(cohort('sample',3),'Demonstration author','proceed_under_declared_conditions','Keep labeled within-sample multiplicity under the declared maximum; this does not establish independent observations.')
 out['primary-marrow']=dc.decide(cohort(name='target-primary-marrow'),'Demonstration author','proceed_under_declared_conditions','Use the exact primary-marrow selection at aliquot level under the stated cardinality condition.')
 out['endpoint-summary']=dc.decide(endpoint(),'Demonstration author','seek_information','Request the missing origin/source components or retain the original endpoint; do not transform an unidentified target.')
 out['endpoint-components']=dc.decide(endpoint(True),'Demonstration author','proceed_under_declared_conditions','Declared components support rederivation with an existing package; a clinical analysis still requires its own review.')
 u=endpoint();del u['endpoint']['target_profile']['cutoff'];u['id']='synthetic-missing-specification'
 out['endpoint-unknown']=dc.decide(u,'Demonstration author','seek_information','Clarify the incomplete target specification.')
 stale=copy.deepcopy(out['labeled-replicates']);stale['cohort']['unit']='aliquot';stale['id']='changed-unit-stale-decision';out['stale-decision']=stale
 combined=endpoint();combined['id']='synthetic-combined-contract'
 combined['purpose']='Synthetic seven-participant demonstration: check both one-file-per-participant structure and endpoint reconstruction before recording one reuse decision.'
 s=copy.deepcopy(selection('target-all'));s['source']='Invented fixture';s['project']='SYNTHETIC';s['release']='fixture-1';s['query']={'fixture':'seven-invented-participants'};s['query_sha256']=dc.digest(s['query']);s['pagination']={'total':7}
 s['status_before']={'fixture':'synthetic'};s['observation']={'files':7,'file_set_sha256':dc.digest('synthetic-seven-files'),'relationship_sha256':dc.digest('synthetic-seven-relationships'),'units':{'case':{'count':7,'histogram':{'1':7},'files_without_unit':0,'files_with_multiple_units':0}}}
 for k in ('requests','independent_tsv','status_after'):s.pop(k,None)
 combined['selection']=s;combined['cohort']={'unit':'case','max_files_per_unit':1,'policy':'One invented record per participant.','evidence_binding':'Synthetic aggregate fixture, not GDC observations.'}
 out['combined']=dc.decide(combined,'Demonstration author','seek_information','Structure is consistent, but endpoint reconstruction is not identified. One passing check cannot authorize the whole reuse decision.')
 return out
def main():
 ex=examples();(ROOT/'examples').mkdir(exist_ok=True);results={}
 for n,c in ex.items():
  (ROOT/'examples'/f'{n}.json').write_text(json.dumps(c,indent=2)+'\n',encoding='utf-8')
  dc.export_crate(c,ROOT/'demo'/n);results[n]=dc.evaluate(c)
 (ROOT/'evidence/demo-results.json').write_text(json.dumps(results,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({n:{'status':r['status'],'decision':r['decision']['state']} for n,r in results.items()},indent=2))
if __name__=='__main__':main()
