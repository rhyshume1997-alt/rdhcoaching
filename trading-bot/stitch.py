#!/usr/bin/env python3
"""Stitch YouTube caption chunks captured via get_page_text into one transcript.
Usage: stitch.py OUT.md "Session N (videoId)" chunk1.json chunk2.json ...
Chunks may overlap; blocks are deduped by timestamp and sorted."""
import json,re,sys

def load(p):
    d=json.load(open(p))
    if isinstance(d,list):
        cand=[e['text'] for e in d if isinstance(e,dict) and '---' in e.get('text','')]
        t=cand[0] if cand else d[0]['text']
    else: t=d['text']
    t=t.split('---',1)[1]
    i=t.find('[output truncated at')
    return t[:i] if i!=-1 else t

def blocks(t):
    out={}
    for p in re.split(r'(?m)^(?=\[(?:\d\d:\d\d:\d\d|end)\])', t):
        m=re.match(r'^\[(\d\d:\d\d:\d\d|end)\]\s*(.*)$', p.strip(), re.S)
        if m:
            k=m.group(1); v=' '.join(m.group(2).split())
            if k not in out or len(v)>len(out[k]): out[k]=v
    return out

out_path, title = sys.argv[1], sys.argv[2]
acc={}
for f in sys.argv[3:]:
    for k,v in blocks(load(f)).items():
        if k not in acc or len(v)>len(acc[k]): acc[k]=v
keys=sorted(k for k in acc if k!='end')
lines=['['+k+'] '+acc[k] for k in keys]
if 'end' in acc: lines.append('[end] '+acc['end'])
txt='\n'.join(lines)
open(out_path,'w').write('# '+title+' — auto transcript\n\n'+txt+'\n')
gaps=[]
for a,b in zip(keys, keys[1:]):
    ta=sum(int(x)*60**i for i,x in enumerate(reversed(a.split(':'))))
    tb=sum(int(x)*60**i for i,x in enumerate(reversed(b.split(':'))))
    if tb-ta > 90: gaps.append(a+' -> '+b)
print(json.dumps({'file':out_path,'blocks':len(lines),'chars':len(txt),
                  'first':keys[0] if keys else None,'last':keys[-1] if keys else None,
                  'suspicious_gaps':gaps}))
