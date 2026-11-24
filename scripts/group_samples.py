"""Offline grouping; Python >=3.10. pip install scikit-learn pillow scipy."""
import argparse, csv, hashlib, json, re, unicodedata
from collections import Counter, defaultdict
from pathlib import Path, PureWindowsPath
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from itertools import combinations
from sklearn.feature_extraction.text import TfidfVectorizer
from PIL import Image, ImageOps
import numpy as np
from scipy.fft import dctn
def phash(im):
    a=dctn(np.asarray(im.convert("L").resize((32,32),Image.Resampling.LANCZOS),dtype=float))[:8,:8]
    return int("".join("1" if v else "0" for v in (a>np.median(a)).ravel()),2)

VERSION = 'afn-group-v1-pilot'
RULES = dict(title_candidate=.30, title_only=.85, title_text=.72, text_support=.35, text_near=.90, phash_distance=4, title_weight=.70)
GROUPS = ('politifact_fake','politifact_real','gossipcop_fake','gossipcop_real')
def norm(s):
    return ' '.join(unicodedata.normalize('NFC', s or '').casefold().split())
def sha(b): return hashlib.sha256(b).hexdigest()
def read(p): return json.loads(p.read_text(encoding='utf-8-sig'))
def canonical(u):
    try:
        p=urlsplit(u); host=(p.hostname or '').lower().removeprefix('www.')
        if p.scheme not in ('http','https') or not host: return None,None
        q=sorted((k,v) for k,v in parse_qsl(p.query,keep_blank_values=True) if not k.lower().startswith('utm_') and k.lower() not in ('fbclid','gclid'))
        port=p.port; authority=host + (f':{port}' if port and port != (443 if p.scheme=='https' else 80) else '')
        return urlunsplit(('https',authority,p.path.rstrip('/') or '/',urlencode(q),'')),host
    except (ValueError,TypeError,AttributeError): return None,None

def local_path(value, root):
    if not value: return None
    p=Path(value)
    if p.is_file(): return p
    parts=PureWindowsPath(value).parts
    for i,part in enumerate(parts):
        if part.lower()=='fakenewsnet_raw_output':
            return root.joinpath(*parts[i+1:])
    return None

def matrix(values):
    try:
        x=TfidfVectorizer(ngram_range=(1,2),sublinear_tf=True,stop_words='english').fit_transform(values)
        return (x@x.T).toarray()
    except ValueError as e:
        if 'empty vocabulary' not in str(e): raise
        import numpy as np
        return np.zeros((len(values),len(values)))

class UnionFind:
    def __init__(self, ids): self.parent={i:i for i in ids}
    def root(self,i):
        while self.parent[i]!=i:
            self.parent[i]=self.parent[self.parent[i]]; i=self.parent[i]
        return i
    def union(self,a,b):
        a,b=self.root(a),self.root(b)
        if a!=b: self.parent[max(a,b)]=min(a,b)

def run(args):
    samples=read(args.manifest); ids=[s['sample_id'] for s in samples]
    if not samples or len(set(ids))!=len(ids) or any(not isinstance(i,str) or not i.strip() for i in ids): raise ValueError('Invalid manifest IDs')
    samples=sorted(samples,key=lambda s:s['sample_id']); ids=[s['sample_id'] for s in samples]; by_id=dict(zip(ids,samples))
    rows={}; counts={}
    for group in GROUPS:
        with (args.csv_dir/f'{group}.csv').open(encoding='utf-8-sig',newline='') as f:
            data=list(csv.DictReader(f)); counts[group]=len(data)
        for r in data:
            sid=r['sampleid']
            if sid in rows: raise ValueError(f'Duplicate CSV ID: {sid}')
            rows[sid]=(group,r)
    uf=UnionFind(ids); edges=[]; seen={}; missing=defaultdict(list); hashes={}; titles=[]; texts=[]
    def edge(a,b,kind,evidence):
        uf.union(a,b); edges.append((a,b,kind,str(evidence)))
    def key(sid,kind,value):
        if not value: return
        k=(kind,value)
        if k in seen: edge(seen[k],sid,kind,value)
        else: seen[k]=sid
    for s in samples:
        sid=s['sample_id']; group=f"{s['source']}_{s['label']}"
        if group not in GROUPS: raise ValueError(f'Invalid source/label: {sid}')
        title,text=norm(s.get('title')),norm(s.get('text')); titles.append(title); texts.append(text)
        if not title: missing['title'].append(sid)
        if not text: missing['text'].append(sid)
        if not s.get('group_event'): missing['event_metadata'].append(sid)
        key(sid,'existing_event',s.get('group_event')); key(sid,'text_sha256',sha(text.encode()) if text else None)
        raw={}; r={}
        if sid in rows:
            g,r=rows[sid]
            if g!=group: raise ValueError(f'CSV group mismatch: {sid}')
            p=local_path(r['pathjson'],args.raw_root)
            try:
                raw=read(p) if p else {}; assert isinstance(raw,dict)
                if not raw: raise ValueError('empty metadata')
            except (OSError,ValueError,AssertionError): raw={}; missing['raw_json'].append(sid)
        else: missing['csv_row'].append(sid)
        url,publisher=canonical(raw.get('url')); cu,cp=canonical(raw.get('canonical_link'))
        if not url and not cu: missing['url'].append(sid)
        if not publisher and not cp: missing['publisher'].append(sid)
        for u in sorted({v for v in (url,cu) if v}): key(sid,'url',u)
        for host in sorted({v for v in (publisher,cp) if v}): key(sid,'publisher_host',host)
        image=s.get('pathIMG'); paths=[]
        if image:
            p=(args.manifest.parent/image).resolve()
            if not p.is_relative_to(args.manifest.parent.resolve()): raise ValueError(f'Unsafe image path: {sid}')
            paths.append(p)
            raw_image=local_path(r.get('path_anh'),args.raw_root)
            if raw_image and raw_image not in paths: paths.append(raw_image)
        else: missing['image_absent'].append(sid)
        ph=[]; processed_ok=False
        for j,p in enumerate(paths):
            try:
                with Image.open(p) as im:
                    im=ImageOps.exif_transpose(im); im.load(); h=phash(im.convert('RGB'))
                key(sid,'image_sha256',sha(p.read_bytes())); ph.append(h)
                if j==0: processed_ok=True
            except (OSError,ValueError): pass
        if image and not processed_ok: missing['processed_image_unreadable'].append(sid)
        if ph: hashes[sid]=ph
    tm,xm=matrix(titles),matrix(texts); candidates=[]
    for i,j in combinations(range(len(ids)),2):
        a,b=ids[i],ids[j]; t,x=float(tm[i,j]),float(xm[i,j]); both=bool(texts[i] and texts[j]); score=.7*t+.3*x if both else t
        if both and x>=RULES['text_near']: edge(a,b,'text_near',f'{x:.4f}')
        if t>=RULES['title_candidate']:
            accepted=(both and score>=RULES['title_text'] and x>=RULES['text_support']) or (not both and t>=RULES['title_only'])
            candidates.append((a,b,t,x if both else None,score,accepted))
            if accepted: edge(a,b,'event_candidate',f'title={t:.4f}; text={x:.4f}' if both else f'title={t:.4f}; text missing')
        if a in hashes and b in hashes:
            d=min((h^k).bit_count() for h in hashes[a] for k in hashes[b])
            if d<=RULES['phash_distance']: edge(a,b,'image_near',d)
    blocks=defaultdict(list)
    for sid in ids: blocks[uf.root(sid)].append(sid)
    mapping={sid:f'group_{n:04d}' for n,members in enumerate(sorted(blocks.values(),key=lambda v:v[0]),1) for sid in members}
    assert set(mapping)==set(ids) and all(mapping[a]==mapping[b] for a,b,_,_ in edges)
    # Explicit transitivity test independent of dataset.
    test=UnionFind(['A','B','C']); test.union('A','B'); test.union('B','C'); assert test.root('A')==test.root('C')
    args.groups.parent.mkdir(parents=True,exist_ok=True); args.audit.parent.mkdir(parents=True,exist_ok=True)
    args.groups.write_text(json.dumps(dict(sorted(mapping.items())),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    def cell(s): return str(s).replace('|','\\|').replace('\n',' ')
    lines=['# Grouping audit — PILOT / NOT APPROVED','',f'- Version: `{VERSION}`',f'- Manifest SHA-256: `{sha(args.manifest.read_bytes())}`',f'- Mapping SHA-256: `{sha(args.groups.read_bytes())}`',f'- Samples: {len(ids)}; CSV rows: {len(rows)}; CSV-only IDs: {len(set(rows)-set(ids))}',f'- Groups: {len(blocks)}; largest: {max(map(len,blocks.values()))}; singleton groups: {sum(len(v)==1 for v in blocks.values())}',f'- Pair comparisons: {len(ids)*(len(ids)-1)//2}', '- Coverage, edge consistency and synthetic A–B–C test: PASS.', '- No group was split; no labels used for similarity.', '- Thresholds are fixed pilot proposals, not calibrated or manually approved. Do not use this mapping for research splits.', '- Publisher proxy is normalized URL hostname, not verified corporate ownership. Missing metadata is not treated as a shared key.', '- TF-IDF is fitted only for grouping, not exported as a training feature. Event candidates are not verified event IDs.', '', '## Rules', '',f'`{json.dumps(RULES)}`','', 'NFC/casefold/whitespace normalization; word unigram/bigram TF-IDF cosine; SHA-256 normalized text and image bytes; 64-bit pHash Hamming; URL removes tracking parameters, fragment and www; connected components over all accepted edges.', '', '## Input coverage','', '| Group | CSV | Manifest |','|---|---:|---:|']
    for g in GROUPS: lines.append(f'| {g} | {counts[g]} | {sum(s["source"]+"_"+s["label"]==g for s in samples)} |')
    lines+=['','## Missing data','', '| Field | Count |','|---|---:|']
    for k in ('csv_row','raw_json','url','publisher','event_metadata','title','text','image_absent','processed_image_unreadable'): lines.append(f'| {k} | {len(missing[k])} |')
    lines+=['','## Edge counts','']+[f'- {k}: {v}' for k,v in sorted(Counter(e[2] for e in edges).items())]
    lines+=['','## Largest groups (review priority)','', '| Group | Size | Fake | Real |','|---|---:|---:|---:|']
    for v in sorted(blocks.values(),key=lambda v:(-len(v),v[0]))[:10]: lines.append(f'| {mapping[v[0]]} | {len(v)} | {sum(by_id[i]["label"]=="fake" for i in v)} | {sum(by_id[i]["label"]=="real" for i in v)} |')
    lines+=['','## Accepted edge evidence (automatic, not human review)','','| A | B | Relation | Evidence |','|---|---|---|---|']+[f'| {cell(a)} | {cell(b)} | {k} | {cell(e)} |' for a,b,k,e in edges]
    lines+=['','## Event candidates for manual review','','| A | B | Title cosine | Text cosine | Score | Accepted |','|---|---|---:|---:|---:|---|']+[f'| {a} | {b} | {t:.4f} | {x if x is not None else "NA"} | {s:.4f} | {ok} |' for a,b,t,x,s,ok in sorted(candidates,key=lambda v:(-v[4],v[0],v[1]))]
    lines+=['','## Member table','','| Sample ID | Group ID |','|---|---|']+[f'| {i} | {mapping[i]} |' for i in ids]
    lines+=['','## Release blockers','','Review accepted/rejected event candidates, cross-label exact text, publisher aliases and large components. Re-run with accessible raw JSON and processed images; record human approval and freeze rules before official split. A missing event relation cannot be ruled out by low lexical similarity.']
    args.audit.write_text('\n'.join(lines)+'\n',encoding='utf-8'); print(f'PILOT: {len(ids)} samples, {len(blocks)} groups; see {args.audit}')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--manifest',type=Path,required=True); p.add_argument('--csv-dir',type=Path,required=True); p.add_argument('--raw-root',type=Path,required=True,help='Path to fakenewsnet_raw_output'); p.add_argument('--groups',type=Path,default=Path('data/processed/groups.json')); p.add_argument('--audit',type=Path,default=Path('reports/grouping-audit.md')); run(p.parse_args())
