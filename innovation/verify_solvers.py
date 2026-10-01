"""Replay every distinct saved SMT obligation using a second solver engine.

Agreement checks the same encoding in two engines, not independent model validity.
"""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'work/solver-deps'))
import cvc5

def solve(text):
 s=cvc5.Solver();s.setOption('tlimit-per','5000');s.setLogic('ALL')
 p=cvc5.InputParser(s);p.setStringInput(cvc5.InputLanguage.SMT_LIB_2_6,text,'saved-obligation');sm=p.getSymbolManager();answers=[]
 while True:
  c=p.nextCommand()
  if c.isNull():break
  r=c.invoke(s,sm).strip()
  if r:answers.append(r)
 assert len(answers)==1,answers
 return answers[0]

def main():
 data=json.loads((ROOT/'innovation/results.json').read_text());expected={}
 for r in data['requests']:
  for o in r['obligations']:expected[o['smt_sha256']]=o['status']
 for r in data['producer_release_matrix']:
  for o in r['questions'].values():expected[o['smt_sha256']]=o['status']
 records=[]
 for sha,status in sorted(expected.items()):
  p=ROOT/'innovation/obligations'/f'{sha}.smt2';raw=p.read_bytes();assert hashlib.sha256(raw).hexdigest()==sha
  actual=solve(raw.decode());want={'ambiguous':'sat','determined_in_model':'unsat','unknown':'unknown'}[status]
  assert actual==want,(sha,actual,want)
  records.append({'smt_sha256':sha,'z3':want,'cvc5':actual,'agreement':True})
 out={'cvc5':cvc5.__version__,'z3':data['solver'],'distinct_obligations':len(records),'all_agree':True,'scope':'Two solver engines on one symbolic encoding; not independent clinical verification.','records':records}
 (ROOT/'innovation/solver-verification.json').write_text(json.dumps(out,indent=2)+'\n')
 print(json.dumps({k:v for k,v in out.items() if k!='records'}))
if __name__=='__main__':main()
