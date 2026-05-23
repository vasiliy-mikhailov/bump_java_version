"""Select 24 distinct-owner candidates per cell, smaller-first, from attempt_2 pools.

For Java 8 cells: classified_v2.json filter on java_version_declared==8 + family_evidenced.
For Java 11/17 cells: history_hits.json (already filtered to those versions + family).

Output: attempt_3/dataset_candidates.json with up to 24 entries per cell, smaller-first
(module_count, size_kb). Will need baseline-build verification next.
"""
import json
from collections import defaultdict

HIST = json.load(open('attempt_2/verify/history_hits.json'))
CL   = json.load(open('attempt_2/verify/classified_v2.json'))

size_of = {r['full_name']: r.get('size_kb', 0) or 0 for r in CL}
mc_of   = {r['full_name']: r.get('module_count', 0) for r in CL}

pool = defaultdict(list)

# Java 11/17 from history walk
for h in HIST:
    j = h['java_version']
    for fam in h['families_at_commit']:
        pool[(j, fam)].append({
            'java_version': j, 'family': fam,
            'repo_full_name': h['full_name'], 'owner': h['owner'], 'repo_name': h['repo'],
            'commit_sha': h['commit_sha'],
            'clone_url': f'https://github.com/{h["full_name"]}.git',
            'size_kb': size_of.get(h['full_name'], 0), 'module_count': mc_of.get(h['full_name'], 0),
            'source': 'history_walk',
        })

# Java 8 from current-state classification
for r in CL:
    if r.get('java_version_declared') != 8: continue
    for fam in r.get('families_evidenced', []):
        pool[(8, fam)].append({
            'java_version': 8, 'family': fam,
            'repo_full_name': r['full_name'], 'owner': r['owner'], 'repo_name': r['repo'],
            'commit_sha': 'HEAD',
            'clone_url': f'https://github.com/{r["full_name"]}.git',
            'size_kb': r.get('size_kb', 0) or 0, 'module_count': r.get('module_count', 0),
            'source': 'classified_head',
        })

print('=== Cell pool sizes ===')
print('java | family             | pool | distinct owners')
for (j, fam), cands in sorted(pool.items()):
    owners = set(c['owner'] for c in cands)
    print(f'{j:>4} | {fam:<19} | {len(cands):>4} | {len(owners):>4}')

# Select 24 distinct-owner per cell, smaller-first
SELECTED = []
TARGET = 24
print()
print('=== Selection (target 24/cell) ===')
print('java | family             | chosen | owners')
for (j, fam), cands in sorted(pool.items()):
    cands_sorted = sorted(cands, key=lambda c: (c['module_count'], c['size_kb'] or 999999))
    seen = set(); chosen = []
    for c in cands_sorted:
        if c['owner'] in seen: continue
        seen.add(c['owner'])
        chosen.append(c)
        if len(chosen) >= TARGET: break
    print(f'{j:>4} | {fam:<19} | {len(chosen):>5} | {len(set(c["owner"] for c in chosen))}')
    for i, c in enumerate(chosen, 1):
        SELECTED.append({
            'cell_id': f'{fam}__j{j}__{i:02d}',
            'java_version': j,
            'dep_family': fam,
            'repo_full_name': c['repo_full_name'],
            'owner': c['owner'],
            'repo_name': c['repo_name'],
            'commit_sha': c['commit_sha'],
            'clone_url': c['clone_url'],
            'size_kb': c['size_kb'],
            'module_count': c['module_count'],
            'source': c['source'],
        })

json.dump(SELECTED, open('attempt_3/dataset_candidates.json', 'w'), indent=2)
print(f'\\ntotal selected: {len(SELECTED)}')
