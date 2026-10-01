"""Cancer Reuse Decision Contracts: bounded, local, aggregate-only reference.

No clinical certification, automatic specimen selection, network access, or
arbitrary user-supplied code. Standard-library runtime. Version 0.1.0.
"""
import argparse,copy,hashlib,html,itertools,json,math,re,sys
from pathlib import Path
VERSION='0.1.0'
IMPLEMENTATION_SHA256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
class Invalid(ValueError):pass
def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)
def digest(x):return hashlib.sha256(canonical(x).encode()).hexdigest()
def integer(x,name,minimum=0):
 if type(x) is not int or x<minimum:raise Invalid(name+' must be an integer >= '+str(minimum))
 return x
def mapping(x,name):
 if type(x) is not dict:raise Invalid(name+' must be an object')
 return x
def text(x,name):
 if type(x) is not str or not x.strip():raise Invalid(name+' must be a nonempty string')
 return x
def sha(x,name):
 if type(x) is not str or not re.fullmatch('[0-9a-f]{64}',x):raise Invalid(name+' must be a SHA-256 hex digest')
def exact_keys(x,allowed,name):
 if set(x)-set(allowed):raise Invalid(name+' contains unsupported fields')
def load(path):
 def pairs(items):
  d={}
  for k,v in items:
   if k in d:raise Invalid('Duplicate JSON key: '+k)
   d[k]=v
  return d
 p=Path(path)
 if p.stat().st_size>5_000_000:raise Invalid('Contract exceeds input size bound')
 return json.loads(p.read_text(encoding='utf-8'),object_pairs_hook=pairs,parse_constant=lambda s:(_ for _ in ()).throw(Invalid('Non-finite JSON number')))
def context(contract):
 c={k:contract.get(k) for k in ('schema_version','purpose','cohort','endpoint')}
 if 'selection' in contract:
  s=contract['selection'];c['selection']={k:s.get(k) for k in ('source','project','release','visibility','query','query_sha256','complete','observation')}
  c['selection']['source_status']=s.get('status_before')
 return c
def observe(selection):
 mapping(selection,'selection')
 for k in ('source','project','release','captured_at_utc','visibility'):text(selection.get(k),'selection.'+k)
 if selection['visibility']!='aggregate_only':raise Invalid('Reference supports aggregate-only observations')
 query=mapping(selection.get('query'),'query');sha(selection.get('query_sha256'),'query_sha256')
 if digest(query)!=selection['query_sha256']:raise Invalid('Query content does not match its digest')
 complete=selection.get('complete')
 if type(complete) is not bool:raise Invalid('complete must be a Boolean')
 obs=mapping(selection.get('observation'),'observation');n=integer(obs.get('files'),'files')
 sha(obs.get('file_set_sha256'),'file_set_sha256')
 sha(obs.get('relationship_sha256'),'relationship_sha256')
 total=integer(mapping(selection.get('pagination'),'pagination').get('total'),'pagination.total')
 if complete and n!=total:raise Invalid('Complete capture file count differs from pagination total')
 if n>total:raise Invalid('Captured count exceeds source total')
 units=mapping(obs.get('units'),'units')
 for name,u in units.items():
  if name not in ('case','sample','aliquot'):raise Invalid('Unsupported unit')
  mapping(u,name);count=integer(u.get('count'),name+'.count')
  missing=integer(u.get('files_without_unit'),name+'.missing');ambig=integer(u.get('files_with_multiple_units'),name+'.ambiguous')
  if missing+ambig>n:raise Invalid('Mapping categories exceed file count')
  hist=mapping(u.get('histogram'),name+'.histogram')
  for k,v in hist.items():
   if not re.fullmatch('[1-9][0-9]*',k):raise Invalid('Histogram keys must be positive integer multiplicities')
   integer(v,'histogram frequency',1)
   if int(k)>n:raise Invalid('A unit cannot have more distinct files than the selection')
  if sum(hist.values())!=count:raise Invalid('Histogram does not sum to distinct unit count')
  links=sum(int(k)*v for k,v in hist.items())
  if not ambig and links!=n-missing:raise Invalid('Unambiguous relationship counts do not reconcile with files')
  if ambig and links<n-missing+ambig:raise Invalid('Ambiguous relationship counts are impossible')
 return obs
def cohort_check(c,s,obs):
 mapping(c,'cohort');exact_keys(c,('unit','max_files_per_unit','policy','evidence_binding'),'cohort')
 unit=text(c.get('unit'),'cohort.unit');limit=integer(c.get('max_files_per_unit'),'max_files_per_unit',1)
 text(c.get('policy'),'cohort.policy');text(c.get('evidence_binding'),'cohort.evidence_binding')
 if not s['complete'] or not obs['files']:return {'status':'unknown','reason':'Selection incomplete or empty.'}
 if unit not in obs['units']:return {'status':'unknown','reason':'Declared unit relationship is unavailable.'}
 u=obs['units'][unit]
 if u['files_without_unit'] or u['files_with_multiple_units']:
  return {'status':'unknown','reason':'Missing or ambiguous relationships prevent this cardinality decision.'}
 violating=sum(v for k,v in u['histogram'].items() if int(k)>limit)
 return {'status':'violated' if violating else 'consistent','reason':f'{violating} {unit} units exceed the declared maximum of {limit} files.',
  'unit':unit,'distinct_units':u['count'],'files':obs['files'],'units_over_limit':violating,
  'policy':c['policy'],'scope':'Cardinality consistency only; no independence, eligibility or specimen-quality inference.'}
PROFILE_KEYS=('origin','events','censor_at','cutoff','unit','definition_source','definition_scope')
def profile(p,name):
 mapping(p,name);exact_keys(p,PROFILE_KEYS,name)
 missing=[k for k in PROFILE_KEYS if k not in p]
 if missing:return {'unknown':missing}
 for k in ('definition_source','definition_scope'):text(p[k],name+'.'+k)
 if p['origin'] not in ('diagnosis','randomization'):raise Invalid('Unsupported time origin')
 if p['unit']!='days':raise Invalid('Reference supports explicitly declared elapsed days only')
 if p['cutoff'] not in (None,'new_therapy'):raise Invalid('Unsupported observation cutoff')
 allowed={'events':{'progression','death_any','death_with_tumor'},'censor_at':{'last_contact','death_without_tumor','last_pretherapy_assessment'}}
 for k,options in allowed.items():
  if type(p[k]) is not list or not p[k] or any(type(x) is not str for x in p[k]) or set(p[k])-options or len(set(p[k]))!=len(p[k]):raise Invalid('Invalid '+k)
 if 'death_any' in p['events'] and 'death_with_tumor' in p['events']:raise Invalid('Redundant death-event definitions')
 return p
def required(p):
 fields={p['origin']}
 for e in p['events']:
  fields.add('progression' if e=='progression' else 'death')
  if e=='death_with_tumor':fields.add('death_with_tumor')
 for c in p['censor_at']:
  fields.add('death' if c=='death_without_tumor' else c)
  if c=='death_without_tumor':fields.add('death_with_tumor')
 if p['cutoff']:fields.add(p['cutoff'])
 return fields
def derive(h,p):
 events=[];censors=[];cutoff=h['new_therapy'] if p['cutoff'] else None
 for e in p['events']:
  v=h['progression'] if e=='progression' else h['death']
  if e=='death_with_tumor' and not h['death_with_tumor']:continue
  if v is not None and (cutoff is None or v<=cutoff):events.append(v)
 for c in p['censor_at']:
  if c=='death_without_tumor':
   if h['death_with_tumor']:continue
   v=h['death']
  else:v=h[c]
  if v is not None and (cutoff is None or v<=cutoff):censors.append(v)
 if events:date=min(events);event=True
 elif censors:date=max(censors);event=False
 else:return None
 return {'elapsed_days':max(date,h[p['origin']])-h[p['origin']],'event':event}
def histories():
 # Fixed finite domain. A witness is conclusive within the encoded mechanism;
 # no witness is never promoted to universal equivalence.
 for rand,prog,death,tumor,last,new in itertools.product([0,30],[None,60,100,120],[None,90,100,150],[False,True],[None,60,90,180],[None,80]):
  if death is None and tumor:continue
  if death is not None and any(x is not None and x>death for x in (prog,last,new)):continue
  yield {'diagnosis':0,'randomization':rand,'progression':prog,'death':death,'death_with_tumor':tumor,
    'last_contact':last,'new_therapy':new,'last_pretherapy_assessment':60 if new is not None else None}
def endpoint_check(e):
 mapping(e,'endpoint');exact_keys(e,('source_profile','target_profile','available_components','component_evidence','binding'),'endpoint')
 text(e.get('binding'),'endpoint.binding');text(e.get('component_evidence'),'endpoint.component_evidence')
 a=profile(e.get('source_profile'),'source_profile');b=profile(e.get('target_profile'),'target_profile')
 if 'unknown' in a or 'unknown' in b:return {'status':'unknown','reason':'Endpoint specification is incomplete.'}
 avail=e.get('available_components')
 allowed={'source_elapsed_days','source_event','diagnosis','randomization','progression','death','death_with_tumor','last_contact','new_therapy','last_pretherapy_assessment'}
 if type(avail) is not list or any(type(x) is not str for x in avail) or len(avail)!=len(set(avail)) or set(avail)-allowed:raise Invalid('Invalid available endpoint components')
 sem=lambda p:{k:p[k] for k in ('origin','events','censor_at','cutoff','unit')}
 if sem(a)==sem(b) and {'source_elapsed_days','source_event'}<=set(avail):
  return {'status':'consistent','reason':'Declared derivation rules agree within the supported language.',
          'scope':'Author-bound specification agreement, not clinical pooling approval or observation validation.'}
 need=sorted(required(b)-set(avail))
 if not need:return {'status':'consistent','reason':'Declared components support target rederivation with an existing derivation tool.',
  'scope':'Component availability is supplied evidence; no raw-data derivation or clinical appropriateness is certified.'}
 if not {'source_elapsed_days','source_event'}<=set(avail):return {'status':'unknown','reason':'Even the source summary components are unspecified.','missing_target_components':need}
 seen={};tested=0
 for h in histories():
  src=derive(h,a);tgt=derive(h,b)
  if src is None:continue
  exposed={'source_elapsed_days':src['elapsed_days'],'source_event':src['event'],**h}
  key=canonical({k:exposed[k] for k in sorted(avail)});tested+=1
  if key in seen and seen[key][1]!=tgt:
   old,old_tgt=seen[key]
   return {'status':'violated','reason':'Target is not uniquely reconstructible from the declared available components.',
     'missing_target_components':need,'witness':{'observed_components':json.loads(key),'history_a':old,'history_b':h,'target_a':old_tgt,'target_b':tgt,'synthetic':True},
     'scope':'Constructive witness in restricted source/target rules; not a clinical incompatibility certificate.','histories_compared':tested}
  seen[key]=(h,tgt)
 return {'status':'unknown','reason':'Rules differ; no counterexample was found in the finite domain.','missing_target_components':need,'histories_compared':tested}
def evaluate(c):
 try:
  mapping(c,'contract');exact_keys(c,('schema_version','id','purpose','selection','cohort','endpoint','decision'),'contract')
  if c.get('schema_version')!='0.1':raise Invalid('Unsupported schema version')
  text(c.get('id'),'id');text(c.get('purpose'),'purpose')
  if 'cohort' not in c and 'endpoint' not in c:raise Invalid('At least one decision mechanism is required')
  results={}
  if 'cohort' in c:
   obs=observe(c.get('selection'));results['cohort']=cohort_check(c['cohort'],c['selection'],obs)
  elif 'selection' in c:observe(c['selection'])
  if 'endpoint' in c:results['endpoint']=endpoint_check(c['endpoint'])
  states=[v['status'] for v in results.values()]
  overall='violated' if 'violated' in states else ('unknown' if 'unknown' in states else 'consistent')
  ctx=digest(context(c));decision={'state':'unrecorded'}
  if 'decision' in c:
   d=mapping(c['decision'],'decision');exact_keys(d,('actor','action','reason','context_sha256','evaluator_version','evaluator_sha256'),'decision')
   for k in ('actor','action','reason'):text(d.get(k),'decision.'+k)
   sha(d.get('context_sha256'),'decision.context_sha256')
   sha(d.get('evaluator_sha256'),'decision.evaluator_sha256')
   if d.get('evaluator_version')!=VERSION or d['evaluator_sha256']!=IMPLEMENTATION_SHA256 or d['context_sha256']!=ctx:decision={'state':'stale','reason':'Decision inputs or evaluator implementation changed; record a new decision.'}
   elif d['action'] not in ('proceed_under_declared_conditions','revise_analysis','seek_information'):raise Invalid('Unsupported recorded action')
   elif d['action']=='proceed_under_declared_conditions' and overall!='consistent':raise Invalid('Proceed decision contradicts the checked conditions')
   else:decision={'state':'current','actor':d['actor'],'action':d['action'],'reason':d['reason']}
  return {'evaluator_version':VERSION,'evaluator_sha256':IMPLEMENTATION_SHA256,'contract_id':c['id'],'status':overall,'context_sha256':ctx,'checks':results,'decision':decision,
   'interpretation':'Limited consistency/reconstruction checks. Source binding is supplied evidence. Scientific suitability and record authenticity require separate review.'}
 except (Invalid,ValueError,TypeError,KeyError) as exc:
  return {'evaluator_version':VERSION,'status':'invalid','errors':[str(exc)],'decision':{'state':'unavailable'}}
def decide(c,actor,action,reason):
 r=evaluate(c)
 if r['status']=='invalid':raise Invalid('; '.join(r['errors']))
 out=copy.deepcopy(c);out['decision']={'actor':text(actor,'actor'),'action':text(action,'action'),'reason':text(reason,'reason'),
    'context_sha256':r['context_sha256'],'evaluator_version':VERSION,'evaluator_sha256':IMPLEMENTATION_SHA256}
 if evaluate(out)['status']=='invalid':raise Invalid('Decision does not match the checked conditions')
 return out
def report(c):
 r=evaluate(c);esc=lambda s:html.escape(str(s));blocks=[]
 action={'proceed_under_declared_conditions':'Proceed under the declared conditions','revise_analysis':'Revise the analysis','seek_information':'Seek missing information'}
 choice=r['decision'];choice_html=''
 if choice['state']=='current':choice_html='<p><b>Recorded action: '+esc(action[choice['action']])+'</b><br>Recorded by: '+esc(choice['actor'])+'</p>'
 for name,v in r.get('checks',{}).items():
  explanation=''
  if name=='cohort' and 'units_over_limit' in v:explanation='<p>'+esc(str(v['files'])+' selected files; '+str(v['distinct_units'])+' distinct '+v['unit']+' units. Policy: '+v['policy'])+'</p>'
  if 'witness' in v:
   w=v['witness'];summary=w['observed_components'];show=lambda x:'No derived outcome' if x is None else str(x['elapsed_days'])+' elapsed days, '+('event' if x['event'] else 'censored')
   explanation='<p><b>Two invented histories, the same available information.</b> The shared summary is '+esc(str(summary.get('source_elapsed_days')))+' days, '+('event' if summary.get('source_event') else 'censored')+'. All other declared available components also agree.</p><p>Requested target in history A: <b>'+esc(show(w['target_a']))+'</b>.<br>Requested target in history B: <b>'+esc(show(w['target_b']))+'</b>.</p><p>These different targets demonstrate why additional information is needed under the specified rules.</p>'
  blocks.append('<section><h2>'+esc(name.title())+' / '+esc(v['status'])+'</h2><p>'+esc(v['reason'])+'</p>'+explanation+'<details><summary>Evidence and scope</summary><pre>'+esc(json.dumps(v,indent=2))+'</pre></details></section>')
 return '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Cancer Reuse Decision Contract</title><style>body{max-width:950px;margin:40px auto;padding:0 24px;background:#f4f7f6;color:#16343d;font:17px/1.5 system-ui}h1{font-size:34px}section{background:white;border:1px solid #ccdeda;border-radius:12px;padding:22px;margin:18px 0}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px}summary{cursor:pointer;color:#006966}small{color:#52686d}</style><h1>Cancer Reuse Decision Contract</h1><p>'+esc(c.get('purpose','Input could not be read'))+'</p><section><h2>Checked conditions: '+esc(r['status'])+'</h2><p>Recorded decision: '+esc(r['decision']['state'])+'</p>'+choice_html+'<p>'+esc(r['decision'].get('reason','No decision has been recorded.'))+'</p><small>Each result applies to its stated scope. It does not approve a scientific design.</small></section>'+''.join(blocks)+'<details><summary>Complete portable contract</summary><pre>'+esc(json.dumps(c,indent=2))+'</pre></details><p><small>Local report. Replay with the reference evaluator to recompute checks and decision validity; this HTML is a captured view.</small></p></html>'
def export_crate(c,out):
 out=Path(out);out.mkdir(parents=True,exist_ok=True);r=evaluate(c)
 if r['status']=='invalid':raise Invalid('Cannot export invalid contract')
 files={'contract.json':json.dumps(c,indent=2)+'\n','evaluation.json':json.dumps(r,indent=2)+'\n','report.html':report(c)}
 for n,s in files.items():(out/n).write_text(s,encoding='utf-8',newline='\n')
 graph=[{'@id':'ro-crate-metadata.json','@type':'CreativeWork','conformsTo':{'@id':'https://w3id.org/ro/crate/1.1'},'about':{'@id':'./'}},
  {'@id':'./','@type':'Dataset','name':c['id'],'description':c['purpose'],'datePublished':'2026-09-30',
   'license':{'@id':'https://spdx.org/licenses/MIT'},'hasPart':[{'@id':n} for n in files]}]
 for n,s in files.items():graph.append({'@id':n,'@type':'File','name':n,'encodingFormat':'text/html' if n.endswith('html') else 'application/json','sha256':hashlib.sha256(s.encode()).hexdigest()})
 (out/'ro-crate-metadata.json').write_text(json.dumps({'@context':'https://w3id.org/ro/crate/1.1/context','@graph':graph},indent=2)+'\n',encoding='utf-8')
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('contract');p.add_argument('--export');p.add_argument('--actor');p.add_argument('--action');p.add_argument('--reason');p.add_argument('--write')
 args=p.parse_args()
 try:
  c=load(args.contract)
  if any((args.actor,args.action,args.reason)):
   if not all((args.actor,args.action,args.reason,args.write)):raise Invalid('Recording requires actor, action, reason and --write')
   c=decide(c,args.actor,args.action,args.reason);Path(args.write).write_text(json.dumps(c,indent=2)+'\n',encoding='utf-8')
  if args.export:export_crate(c,args.export)
  r=evaluate(c)
 except (OSError,Invalid,json.JSONDecodeError) as exc:r={'status':'invalid','errors':[str(exc)],'decision':{'state':'unavailable'}}
 print(json.dumps(r,indent=2));return 0 if r['status']=='consistent' and r['decision']['state']!='stale' else 2
if __name__=='__main__':sys.exit(main())
