"""Standalone pilot splitter. Python 3.9+, standard library only."""
import json, random, hashlib
from pathlib import Path
from collections import Counter, defaultdict

NAMES = ('train', 'validation', 'test')
RATIOS = (.70, .15, .15)
CATS = ('politifact_fake', 'politifact_real', 'gossipcop_fake', 'gossipcop_real')

def read(p):
    return json.loads(p.read_text(encoding='utf-8-sig'))

def split(manifest, groups, output):
    manifest, groups, output = map(lambda p: Path(p).expanduser().resolve(), (manifest, groups, output))
    samples, mapping = read(manifest), read(groups)
    if not isinstance(samples, list) or not samples or not isinstance(mapping, dict):
        raise ValueError('Invalid manifest or groups format')
    by = {}
    for s in samples:
        sid = s['sample_id']
        if not isinstance(sid, str) or not sid.strip() or sid in by or s['source']+'_'+s['label'] not in CATS:
            raise ValueError(f'Invalid sample: {sid}')
        by[sid] = s
    if set(mapping) != set(by) or any(not isinstance(g,str) or not g.strip() for g in mapping.values()):
        raise ValueError('groups.json must cover exactly all manifest IDs')
    blocks = defaultdict(list)
    for sid in sorted(by): blocks[mapping[sid]].append(sid)
    if len(blocks) < 3: raise ValueError('Need at least 3 groups; cannot split groups')
    def cat(sid): return by[sid]['source']+'_'+by[sid]['label']
    total = Counter(map(cat, by)); n = len(by)
    units = [(ids, Counter(map(cat,ids))) for _,ids in sorted(blocks.items())]
    def loss(cs, ns):
        return sum((ns[i]-n*r)**2/max(1,n*r) + sum((cs[i][c]-total[c]*r)**2/max(1,total[c]*r) for c in CATS) for i,r in enumerate(RATIOS))
    rng = random.Random(42); best = None
    for _ in range(100):
        order = units.copy(); rng.shuffle(order); order.sort(key=lambda u:-len(u[0]))
        parts=[[],[],[]]; cs=[Counter(),Counter(),Counter()]; ns=[0,0,0]
        for ids,c in order:
            def score(i):
                cs[i].update(c); ns[i]+=len(ids); v=loss(cs,ns); cs[i].subtract(c); ns[i]-=len(ids); return v
            i=min(range(3),key=lambda i:(score(i),i)); parts[i].extend(ids); cs[i].update(c); ns[i]+=len(ids)
        if not all(parts) or {by[s]['label'] for s in parts[0]} != {'fake','real'}: continue
        v=loss(cs,ns)
        if best is None or v<best[0]: best=(v,parts)
    if best is None: raise ValueError('No feasible split found with both labels in Train; groups preserved')
    parts=best[1]; sets=list(map(set,parts)); gs=[{mapping[s] for s in p} for p in parts]
    if set.union(*sets)!=set(by) or any(sets[i]&sets[j] or gs[i]&gs[j] for i in range(3) for j in range(i)):
        raise RuntimeError('Split integrity failure')
    files={}; print('\nPILOT ONLY: image/text/publisher/event leakage not independently verified.')
    for name,ids,r in zip(NAMES,parts,RATIOS):
        rows=[{'sample_id':s,'group_id':mapping[s]} for s in sorted(ids)]
        files[output/(name+'.json')]=(json.dumps(rows,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
        print(f'{name}: {len(ids)} ({len(ids)/n:.2%}), target {r:.0%}, groups={len({mapping[s] for s in ids})}')
        print(dict(Counter(map(cat,ids))))
        missing={'fake','real'}-{by[s]['label'] for s in ids}
        if missing: print('WARNING missing labels:', sorted(missing))
    for p,b in files.items():
        if p in (manifest,groups) or (p.exists() and p.read_bytes()!=b): raise FileExistsError(f'Choose another output directory: {p}')
    output.mkdir(parents=True,exist_ok=True)
    for p,b in files.items():
        p.write_bytes(b); print(p, 'SHA256:',hashlib.sha256(b).hexdigest())
    print('PASS: no overlapping sample_id/group_id. Total:',n)

def ask(label):
    value=input(label).strip().strip('"').strip("'")
    if not value: raise ValueError('Empty path')
    return value

if __name__=='__main__':
    try:
        split(ask('Nhap duong dan manifest.json: '),ask('Nhap duong dan groups.json: '),ask('Nhap thu muc luu ket qua: '))
    except (OSError,ValueError,KeyError,TypeError) as e:
        raise SystemExit(f'ERROR: {e}')
