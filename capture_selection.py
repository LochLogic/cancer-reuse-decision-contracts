"""Fetch public metadata, verify JSON against TSV, persist aggregate evidence only."""
import collections,csv,datetime,hashlib,io,json,urllib.parse,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parent
FIELDS='file_id,analysis.workflow_type,cases.submitter_id,cases.samples.submitter_id,cases.samples.portions.analytes.aliquots.submitter_id'
LOG=[]
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def get(url,payload=None):
 req=urllib.request.Request(url,data=None if payload is None else json.dumps(payload).encode(),headers={'User-Agent':'Cancer-Reuse-Decision-Contracts/0.1','Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=60) as r:raw=r.read(25_000_001)
 if len(raw)>25_000_000:raise ValueError('Capture bound exceeded')
 LOG.append({'url':url,'payload':payload,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
 return raw
def counts(rows):
 ids=[r['file_id'] for r in rows];assert len(ids)==len(set(ids))
 units={n:collections.Counter() for n in ('case','sample','aliquot')};missing=collections.Counter();ambig=collections.Counter();relations=[]
 for r in rows:
  case=set();sample=set();aliquot=set()
  for c in r.get('cases',[]):
   if c.get('submitter_id'):case.add(c['submitter_id'])
   for s in c.get('samples',[]):
    if s.get('submitter_id'):sample.add(s['submitter_id'])
    for p in s.get('portions',[]):
     for a in p.get('analytes',[]):
      for al in a.get('aliquots',[]):
       if al.get('submitter_id'):aliquot.add(al['submitter_id'])
  for n,vs in [('case',case),('sample',sample),('aliquot',aliquot)]:
   if not vs:missing[n]+=1
   if len(vs)>1:ambig[n]+=1
   units[n].update(vs)
  relations.append([r['file_id'],sorted(case),sorted(sample),sorted(aliquot)])
 return {'files':len(rows),'file_set_sha256':hashlib.sha256('\n'.join(sorted(ids)).encode()).hexdigest(),
  'relationship_sha256':digest(sorted(relations)),
  'units':{n:{'histogram':{str(k):v for k,v in sorted(collections.Counter(c.values()).items())},
              'count':len(c),'files_without_unit':missing[n],'files_with_multiple_units':ambig[n]} for n,c in units.items()}}
def tsv_counts(raw):
 rows=list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig')),delimiter='\t'))
 cols={'case':'cases.0.submitter_id','sample':'cases.0.samples.0.submitter_id',
       'aliquot':'cases.0.samples.0.portions.0.analytes.0.aliquots.0.submitter_id'}
 # TSV flattens arrays into indexed columns. Recover every observed relationship.
 import re
 patterns={'case':r'^cases\.\d+\.submitter_id$', 'sample':r'^cases\.\d+\.samples\.\d+\.submitter_id$',
  'aliquot':r'^cases\.\d+\.samples\.\d+\.portions\.\d+\.analytes\.\d+\.aliquots\.\d+\.submitter_id$'}
 assert rows and 'file_id' in rows[0]
 columns={n:[k for k in rows[0] if re.match(pat,k)] for n,pat in patterns.items()}
 if not all(columns.values()):raise ValueError('Unrecognized TSV relationship columns')
 ids=[r['file_id'] for r in rows];assert len(ids)==len(set(ids))
 units={};relations=[]
 for r in rows:relations.append([r['file_id']]+[sorted({r[k] for k in columns[n] if r.get(k) not in ('',None,'null','[]')}) for n in ('case','sample','aliquot')])
 for n,ks in columns.items():
  counter=collections.Counter();missing=0;ambig=0
  for r in rows:
   vs={r[k] for k in ks if r.get(k) not in ('',None,'null','[]')}
   missing+=not vs;ambig+=len(vs)>1;counter.update(vs)
  units[n]={'histogram':{str(k):v for k,v in sorted(collections.Counter(counter.values()).items())},'count':len(counter),
    'files_without_unit':missing,'files_with_multiple_units':ambig}
 return {'files':len(rows),'file_set_sha256':hashlib.sha256('\n'.join(sorted(ids)).encode()).hexdigest(),'relationship_sha256':digest(sorted(relations)),'units':units}
def capture(name,extra=None):
 start=len(LOG);before=json.loads(get('https://api.gdc.cancer.gov/status'))
 filters={'op':'and','content':[{'op':'=','content':{'field':'cases.project.project_id','value':'TARGET-AML'}},
  {'op':'=','content':{'field':'data_type','value':'Gene Expression Quantification'}},{'op':'=','content':{'field':'access','value':'open'}}]}
 if extra:filters['content'].append(extra)
 query={'filters':filters,'fields':FIELDS,'size':1000,'sort':'file_id:asc'}
 rows=[];totals=[];offset=0
 while True:
  p=dict(query,**{'from':offset});data=json.loads(get('https://api.gdc.cancer.gov/files',p))['data']
  rows+=data['hits'];totals.append(data['pagination']['total']);offset+=len(data['hits'])
  if offset>=totals[-1]:break
  if not data['hits']:raise ValueError('Empty page before total')
 assert rows and len(set(totals))==1 and len(rows)==totals[0]
 aggregate=counts(rows)
 tsvquery=dict(query,size=10000,format='TSV')
 tsv=tsv_counts(get('https://api.gdc.cancer.gov/files?'+urllib.parse.urlencode({k:json.dumps(v) if isinstance(v,dict) else v for k,v in tsvquery.items()})))
 assert aggregate==tsv,'Independent TSV aggregate/file-set disagreement'
 after=json.loads(get('https://api.gdc.cancer.gov/status'));assert before==after
 snapshot={'source':'https://api.gdc.cancer.gov/files','project':'TARGET-AML','data_type':'Gene Expression Quantification',
  'captured_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'release':str(before['data_release_version']['major'])+'.'+str(before['data_release_version']['minor']),
  'query':query,'query_sha256':digest(query),'complete':True,'pagination':{'pages':len(totals),'total':totals[0]},
  'status_before':before,'status_after':after,'observation':aggregate,'independent_tsv_agrees':True,
  'visibility':'aggregate_only','replay_limit':'An exact current selection can be refetched and compared with the hash; historical source availability is not guaranteed.',
  'requests':LOG[start:]}
 (ROOT/'evidence').mkdir(exist_ok=True);(ROOT/'evidence'/f'{name}.json').write_text(json.dumps(snapshot,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({'name':name,'release':snapshot['release'],'observation':aggregate,'independent_tsv_agrees':True},indent=2))
if __name__=='__main__':
 capture('target-all')
 capture('target-primary-marrow',{'op':'=','content':{'field':'cases.samples.sample_type','value':'Primary Blood Derived Cancer - Bone Marrow'}})
