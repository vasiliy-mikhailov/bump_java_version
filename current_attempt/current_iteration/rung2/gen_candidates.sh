#!/bin/bash
FROM=${1:?usage: gen_candidates.sh <jv_from> <out> [maxtests] [mintests]}; OUT=${2:?}; MAX=${3:-80}; MIN=${4:-3}
cp /home/vmihaylov/bump-java-version/current_attempt/corpus/baselines_peryear.json.jsonl /tmp/_bl.jsonl
docker run --rm -v /tmp:/t -e FROM=$FROM -e MAX=$MAX -e MIN=$MIN python:3-slim python3 -c "
import json,os
F=int(os.environ['FROM']); MX=int(os.environ['MAX']); MN=int(os.environ['MIN']); seen={}
for l in open('/t/_bl.jsonl'):
    try: r=json.loads(l)
    except: continue
    if r.get('jv_from')!=F: continue
    rp=r.get('repo'); sha=r.get('sha'); t=r.get('tests',0) or 0
    if not rp or not sha or t<MN or t>MX: continue
    if rp not in seen: seen[rp]=(sha,t)
items=sorted(seen.items(), key=lambda kv:-kv[1][1])   # high static count first (green-rich)
open('/t/_cand.txt','w').write(chr(10).join(rp+' '+sha for rp,(sha,t) in items)+chr(10))
print('wrote',len(items))
"
cp /tmp/_cand.txt $OUT; wc -l $OUT
