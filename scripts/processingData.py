#!/usr/bin/env python3
"""Tiền xử lý FakeNewsNet offline; plan/process, không chia tập hoặc enhancement.

Đặt cạnh analyzeData.py (afn-analyze-v1). Báo cáo Before phải đầy đủ và còn hiệu lực.
"""
from __future__ import annotations

import argparse
import csv
import io
import html
import json
import logging
import re
import shutil
import unicodedata as ud
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from itertools import combinations
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from PIL import Image, ImageOps
import analyzeData as A

VERSION = 'afn-processing-v1'
LOG = logging.getLogger('afn.processing')
REVIEW_FIELDS = ('sample_id','sample_id_b','component','issue','decision','reason','target_sha256')
REQUIRED = ('sample_inventory.csv','text_metrics.csv','image_metrics.csv','duplicate_candidates.csv','metadata_statistics.json','errors.csv')
GROUPS = A.GROUPS
ArticleSample = A.ArticleSample

@dataclass(frozen=True)
class ProcessingConfig:
    """Cấu hình cố định; không học tham số từ dataset."""
    resize_mode: str = 'none'
    target_size: int | None = None
    max_pixels: int = 40_000_000
    max_image_bytes: int = 100 * 1024 * 1024
    # Chỉ là mốc khảo sát, không tự loại bài dài.
    review_long_words: float | None = None

    def validate(self) -> None:
        if self.resize_mode not in ('none','longest_side','letterbox'):
            raise ValueError('INVALID_CONFIG: resize_mode')
        if self.resize_mode != 'none' and (not self.target_size or self.target_size <= 0 or self.target_size**2 > self.max_pixels):
            raise ValueError('INVALID_CONFIG: target_size')
        if self.resize_mode == 'none' and self.target_size is not None:
            raise ValueError('INVALID_CONFIG: target_size chỉ dùng khi resize')
        if min(self.max_pixels,self.max_image_bytes) <= 0:
            raise ValueError('INVALID_CONFIG: giới hạn giải mã')


def truth(value: Any) -> bool:
    return value is True or str(value).lower() == 'true'


def val(row: dict, key: str) -> str:
    return str(row.get(key) or '')


def num(row: dict, key: str) -> float | None:
    v = val(row,key)
    return float(v) if v else None


def index(rows: list[dict]) -> dict[str,dict]:
    result = {}
    for row in rows:
        sid = row['sample_id']
        if sid in result:
            raise ValueError(f'DUPLICATE_SAMPLE_ID trong Before: {sid}')
        result[sid] = row
    return result


def load_before_statistics(directory: Path) -> tuple[dict,dict,dict,dict,list[dict]]:
    """Không sử dụng báo cáo dang dở hoặc đã bị sửa ngoài pipeline."""
    stats = A.read_json(directory/'statistics.json')
    if stats.get('stage') != 'before' or not stats.get('analysis_complete') or stats.get('methods') != A.METHODS:
        raise ValueError('STALE_BEFORE_STATISTICS: sai stage, version hoặc báo cáo chưa hoàn tất')
    checks = stats.get('report_checksums',{})
    for name in REQUIRED:
        if not checks.get(name) or A.file_sha(directory/name) != checks[name]:
            raise ValueError(f'STALE_BEFORE_STATISTICS: checksum {name}')
    inv, text, image = (index(A.read_csv(directory/name)) for name in REQUIRED[:3])
    if set(inv) != set(text) or set(inv) != set(image) or len(inv) != stats['dataset_summary']['row_count']:
        raise ValueError('STALE_BEFORE_STATISTICS: tập ID không khớp')
    return stats, inv, text, image, A.read_csv(directory/'duplicate_candidates.csv')


class DatasetLoader(A.DatasetLoader):
    """Tái dùng loader CSV/path; đọc JSON một lần và giữ metadata cần cho event."""
    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.event_data: dict[str,dict] = {}

    def read_article(self, s: ArticleSample) -> None:
        # Tái dùng hàm extract/profile/hash của analyzer, tránh mở JSON lần thứ hai.
        if not s.json_path or not s.json_path.is_file():
            s.json_status='missing'; s.issue('json','MISSING_JSON','Không tìm thấy JSON',s.json_path); return
        try:
            raw=s.json_path.read_bytes(); s.json_sha256=A.sha(raw)
            data=json.loads(raw.decode('utf-8-sig')); json.dumps(data,allow_nan=False)
            if not isinstance(data,dict):
                s.json_status='invalid_structure'; s.issue('json','INVALID_JSON_STRUCTURE','JSON không phải object'); return
            s.json_status='valid'; s.metadata=A.metadata_profile(data)
            s.title,s.title_source_key,s.title_whitespace_only=A.extract(data,A.TITLE_KEYS)
            s.text,s.text_source_key,s.text_whitespace_only=A.extract(data,A.TEXT_KEYS)
            self.event_data[s.row_id]={k:data[k] for k in ('event','event_id','url','canonical_link','publish_date','authors','keywords','meta_keywords','tags','meta_data') if k in data}
        except (OSError,UnicodeError,ValueError,RecursionError) as exc:
            s.json_status='decode_error'; s.issue('json','INVALID_JSON',str(exc),s.json_path)


def verify_inputs(samples: list[ArticleSample], loader: DatasetLoader, stats: dict, inv: dict, text: dict, image: dict) -> None:
    """Hash byte hiện tại, không tính lại IQA. Dừng khi Before không còn đáng tin."""
    if Counter(loader.input_hashes.values()) != Counter(stats.get('input_file_checksums',{}).values()):
        raise ValueError('STALE_BEFORE_STATISTICS: bốn CSV đã thay đổi; chạy lại Before')
    if len({s.sample_id for s in samples}) != len(samples):
        raise ValueError('DUPLICATE_SAMPLE_ID: không thể nối Before theo ID; sửa nguồn rồi chạy lại Before')
    if {s.sample_id for s in samples} != set(inv):
        raise ValueError('STALE_BEFORE_STATISTICS: tập ID thay đổi')
    for s in samples:
        i=s.sample_id; old=inv[i]; t=text[i]; im=image[i]
        for key in ('row_id','source','label','collection_status','original_json_path','original_image_path'):
            if val(old,key) != str(getattr(s,key)):
                raise ValueError(f'STALE_BEFORE_STATISTICS: {i}: {key}')
        for key in ('row_id','source','label','collection_status','assessed_status'):
            if val(t,key)!=val(old,key) or val(im,key)!=val(old,key):
                raise ValueError(f'STALE_BEFORE_STATISTICS: {i}: bảng metric không khớp {key}')
        image_hash=A.file_sha(s.image_path) if s.image_path and s.image_path.is_file() else None
        current=dict(sample_id=i,source=s.source,label=s.label,collection_status=s.collection_status,
                     original_json_path=s.original_json_path,original_image_path=s.original_image_path,
                     json_sha256=s.json_sha256,image_sha256=image_hash,
                     title_sha256=A.digest_text(s.title) if A.present(s.title) else None,
                     text_sha256=A.digest_text(s.text) if A.present(s.text) else None,group_event=s.group_event)
        if any(val(old,k)!=str(v or '') for k,v in current.items()) or val(old,'input_fingerprint')!=A.sha(json.dumps(current,sort_keys=True,ensure_ascii=True).encode()):
            raise ValueError(f'STALE_BEFORE_STATISTICS: {i}: fingerprint thay đổi; chạy lại Before')
        if val(t,'text_sha256')!=val(old,'text_sha256') or val(t,'title_sha256')!=val(old,'title_sha256') or val(im,'image_sha256')!=val(old,'image_sha256'):
            raise ValueError(f'STALE_BEFORE_STATISTICS: {i}: hash metric không khớp')


class Reviews:
    """Review phải có lý do; không tự duyệt. Cặp ID được sắp xếp ổn định."""
    def __init__(self, path: Path | None, ids: set[str]):
        self.rows: dict[tuple,dict] = {}
        self.used: set[tuple] = set()
        if path is None: return
        with path.open(encoding='utf-8-sig',newline='') as f:
            reader=csv.DictReader(f)
            if not {'sample_id','component','issue','decision','reason'} <= set(reader.fieldnames or ()):
                raise ValueError('INVALID_CONFIG: review thiếu cột')
            for r in reader:
                a,b=val(r,'sample_id'),val(r,'sample_id_b')
                if a not in ids or (b and (b not in ids or a==b)):
                    raise ValueError(f'Review có ID không hợp lệ: {a}, {b}')
                if b: a,b=sorted((a,b))
                key=(a,b,val(r,'component'),val(r,'issue'),val(r,'target_sha256'))
                if val(r,'decision') not in ('approved','rejected','pending_review') or not val(r,'reason').strip() or (val(r,'decision')!='pending_review' and val(r,'reason')=='Chưa có quyết định review') or key in self.rows:
                    raise ValueError(f'Review không hợp lệ hoặc trùng: {key}')
                self.rows[key]=dict(zip(REVIEW_FIELDS,(a,b,key[2],key[3],r['decision'],r['reason'],key[4])))

    def get(self,a: str,component: str,issue: str,b: str='',target: str='') -> str:
        if b: a,b=sorted((a,b))
        key=(a,b,component,issue,target)
        if key in self.rows:
            self.used.add(key)
            return self.rows[key]['decision']
        return 'pending_review'

    def reason(self,a: str,component: str,issue: str,b: str='',target: str='') -> str:
        if b: a,b=sorted((a,b))
        return self.rows.get((a,b,component,issue,target),{}).get('reason','Chưa có quyết định review')


def logop(log: list[dict],s: ArticleSample,component: str,operation: str,status: str='applied',reason: str='',**extra: Any) -> None:
    log.append(dict(sample_id=s.sample_id,source=s.source,label=s.label,component=component,operation=operation,status=status,reason=reason,**extra))


class TextProcessor:
    """NFC và whitespace có kiểm soát; chỉ xóa đoạn đúng hash đã duyệt."""
    @staticmethod
    def normalize(value: str | None, s: ArticleSample, field: str, log: list[dict]) -> str | None:
        if value is None: return None
        steps=(('unicode_normalization',lambda x:ud.normalize('NFC',x)),
               ('control_character_removal',lambda x:''.join(c if ud.category(c) not in ('Cc','Cs') or c in '\t\r\n' else ' ' for c in x)),
               ('whitespace_normalization',lambda x:re.sub(r'\n{3,}','\n\n','\n'.join(re.sub(r'[^\S\n]+',' ',line).strip() for line in x.replace('\r\n','\n').replace('\r','\n').split('\n'))).strip()))
        for name,fn in steps:
            new=fn(value)
            if new!=value:
                logop(log,s,'text',name,field=field,before_sha256=A.digest_text(value),after_sha256=A.digest_text(new),char_delta=len(new)-len(value))
            value=new
        return value or None

    @staticmethod
    def paragraphs(body: str | None) -> list[str]:
        return re.split(r'\n\n+',body) if body else []

    def process(self,s: ArticleSample,review: Reviews,log: list[dict],candidates: list[dict]) -> tuple[str|None,str|None]:
        title=self.normalize(s.title,s,'title',log)
        body=self.normalize(s.text,s,'text',log)
        if s.text_source_key=='description' and body:
            if review.get(s.sample_id,'text','description_only')!='approved':
                logop(log,s,'text','description_not_confirmed','held','Không coi description là article body')
                body=None
        # Chỉ xóa đoạn có định danh chính xác (hash NFC + whitespace); không xóa câu lặp tự động.
        if body:
            before=body; seen=set(); kept=[]; removed=Counter()
            for p in self.paragraphs(body):
                key=A.digest_text(p); norm=A.normalized(p)
                repeated=bool(norm) and norm in seen
                seen.add(norm)
                issues=[]
                if repeated: issues.append('duplicate_paragraph_removal')
                if re.search(r'\b(subscribe|newsletter|sign up|advertisement|cookies|all rights reserved|click here|sponsored content)\b',p,re.I):
                    issues.append('boilerplate_removal')
                discard=False
                for issue in issues:
                    d=review.get(s.sample_id,'text',issue,target=key)
                    candidates.append(dict(sample_id=s.sample_id,component='text',issue=issue,target_sha256=key,decision=d,reason='Đoạn cần kiểm tra; hash của đoạn sau NFC/whitespace',paragraph_chars=len(p)))
                    if d=='approved': discard=True; removed[issue]+=1; break
                if not discard: kept.append(p)
            body='\n\n'.join(kept).strip() or None
            for issue,count in removed.items():
                logop(log,s,'text',issue,reason='Review đã phê duyệt theo hash đoạn',paragraph_count=count,before_sha256=A.digest_text(before),after_sha256=A.digest_text(body) if body else None,char_delta=len(body or '')-len(before))
        # Chỉ xử lý tập tag HTML trình bày đã xác nhận, không xóa tag lạ hay nội dung bên trong.
        if body and review.get(s.sample_id,'text','html_tag_count')=='approved':
            before=body
            body=re.sub(r'</?(?:p|br|div|span|b|strong|i|em|u|ul|ol|li|h[1-6])(?:\s+[^<>]*|\s*/?)>',lambda m:'\n' if re.match(r'</?(?:p|br|div|li|h[1-6])\b',m.group(),re.I) else '',body,flags=re.I)
            body=self.normalize(body,s,'text',log)
            if body!=before: logop(log,s,'text','html_markup_removal',reason='Markup trình bày đã duyệt',before_sha256=A.digest_text(before),after_sha256=A.digest_text(body) if body else None,char_delta=len(body or '')-len(before))
        if body and review.get(s.sample_id,'text','html_entity_count')=='approved':
            before=body; body=self.normalize(html.unescape(body),s,'text',log)
            if body!=before: logop(log,s,'text','html_entity_decode',before_sha256=A.digest_text(before),after_sha256=A.digest_text(body) if body else None)
        return title,body


class ImageProcessor:
    """Chuẩn hóa frame đầu, EXIF, alpha trắng, RGB, PNG; không enhancement."""
    def __init__(self,config: ProcessingConfig): self.config=config

    def process(self,s: ArticleSample,path: Path,expected_hash: str,log: list[dict]) -> str:
        if s.image_path is None: raise ValueError('MISSING_IMAGE')
        if s.image_path.stat().st_size>self.config.max_image_bytes: raise ValueError('IMAGE_DECODE_LIMIT')
        raw=s.image_path.read_bytes()
        if A.sha(raw)!=expected_hash: raise RuntimeError('STALE_BEFORE_STATISTICS: ảnh thay đổi trong khi xử lý')
        with Image.open(io.BytesIO(raw)) as img:
            if img.width*img.height>self.config.max_pixels: raise ValueError('IMAGE_DECODE_LIMIT')
            if img.width*img.height<=1: raise ValueError('IMAGE_TOO_SMALL')
            n=int(getattr(img,'n_frames',1)); orientation=img.getexif().get(274,1)
            trans='A' in img.getbands() or 'transparency' in img.info
            old_mode=img.mode; fmt=img.format; img.seek(0); img.load()
            upright=ImageOps.exif_transpose(img)
            if n>1: logop(log,s,'image','frame_selection',frame_count=n,selected_frame=0)
            if orientation in range(2,9): logop(log,s,'image','exif_transpose',orientation=orientation)
            if trans:
                rgba=upright.convert('RGBA'); rgb=Image.alpha_composite(Image.new('RGBA',rgba.size,'white'),rgba).convert('RGB')
                logop(log,s,'image','alpha_composite',background='white')
            else: rgb=upright.convert('RGB')
            if old_mode!='RGB': logop(log,s,'image','rgb_conversion',original_mode=old_mode)
            if self.config.resize_mode!='none':
                size=rgb.size; target=self.config.target_size
                if self.config.resize_mode=='longest_side': rgb.thumbnail((target,target),Image.Resampling.LANCZOS)
                else:
                    rgb.thumbnail((target,target),Image.Resampling.LANCZOS)
                    canvas=Image.new('RGB',(target,target),'white'); canvas.paste(rgb,((target-rgb.width)//2,(target-rgb.height)//2)); rgb=canvas
                if rgb.size!=size: logop(log,s,'image','resize',original_size=size,output_size=rgb.size,resize_mode=self.config.resize_mode)
            # Bỏ metadata container; raw được giữ nguyên cho forensic.
            rgb.info.clear(); path.parent.mkdir(parents=True,exist_ok=True)
            temp=path.with_suffix('.png.tmp')
            try:
                rgb.save(temp,format='PNG');
                with Image.open(temp) as check:
                    check.load()
                    if check.format!='PNG' or check.mode!='RGB': raise ValueError('OUTPUT_VALIDATION_FAILED')
                temp.replace(path)
            finally: temp.unlink(missing_ok=True)
            logop(log,s,'image','png_conversion' if fmt!='PNG' else 'png_save',original_format=fmt,output_size=rgb.size)
        return A.file_sha(path)


class UnionFind:
    def __init__(self,ids: set[str]): self.parent={i:i for i in ids}
    def find(self,x: str) -> str:
        while self.parent[x]!=x:
            self.parent[x]=self.parent[self.parent[x]]; x=self.parent[x]
        return x
    def union(self,a: str,b: str) -> None:
        a,b=self.find(a),self.find(b)
        self.parent[max(a,b)]=min(a,b)
    def groups(self,prefix: str,singletons: bool=True) -> dict[str,list[str]]:
        groups=defaultdict(list)
        for i in sorted(self.parent): groups[self.find(i)].append(i)
        return {prefix+'_'+A.sha(json.dumps(v,ensure_ascii=True).encode())[:20]:v for v in groups.values() if singletons or len(v)>1}


def canonical(value: Any) -> str:
    """Chỉ chuẩn hóa URL thận trọng; không network, giữ query/path."""
    if not isinstance(value,str): return ''
    try:
        p=urlsplit(value.strip())
        if p.scheme.lower() not in ('https','http') or not p.hostname or p.username or p.password: return ''
        return urlunsplit((p.scheme.lower(),p.netloc.lower(),p.path or '/',p.query,''))
    except ValueError: return ''


class DuplicateAuditor:
    """Gộp bằng chứng một cặp; hash gần không tự coi là trùng."""
    @staticmethod
    def collect(rows: list[dict],ids: set[str]) -> dict[tuple[str,str],dict]:
        pairs={}
        for r in rows:
            a,b=sorted((r['sample_id_a'],r['sample_id_b']))
            if a not in ids or b not in ids or a==b: raise ValueError('STALE_BEFORE_STATISTICS: duplicate mapping sai')
            pair=pairs.setdefault((a,b),dict(sample_id=a,sample_id_b=b,exact=[],near={},post_exact=[]))
            kind=r['duplicate_type']
            if kind in ('text_fingerprint','image_phash'):
                pair['near'][kind]={'distance':int(r['distance']),'similarity':float(r['similarity_score']),'candidate':truth(r['candidate']) if val(r,'candidate') else None}
            elif truth(r['candidate']) and kind not in pair['exact']: pair['exact'].append(kind)
        return pairs

    @staticmethod
    def add_exact(pairs: dict,records: dict,audit: dict) -> None:
        # Sau chuẩn hóa có thể phát sinh exact duplicate mới; không tính lại IQA.
        for kind,values in [('processed_text_sha256',{i:audit[i]['processed_text_sha256'] for i in records}),('processed_image_sha256',{i:audit[i]['processed_image_sha256'] for i in records})]:
            buckets=defaultdict(list)
            for i,h in values.items():
                if h: buckets[h].append(i)
            for group in buckets.values():
                for a,b in combinations(sorted(group),2):
                    p=pairs.setdefault((a,b),dict(sample_id=a,sample_id_b=b,exact=[],near={},post_exact=[]))
                    p['post_exact'].append(kind)


class EventGrouper:
    """Chỉ gom event khi review cặp approved; không sử dụng label."""
    def candidates(self,samples: dict,metadata: dict,pairs: dict,review: Reviews) -> tuple[list[dict],dict,dict]:
        uf=UnionFind(set(samples)); rows=[]
        titles={i:set(A.WORD.findall(A.normalized(s.title or ''))) for i,s in samples.items()}
        for a,b in combinations(sorted(samples),2):
            ma,mb=metadata.get(samples[a].row_id,{}),metadata.get(samples[b].row_id,{})
            ua=canonical(ma.get('canonical_link')) or canonical(ma.get('url')); ub=canonical(mb.get('canonical_link')) or canonical(mb.get('url'))
            union=titles[a]|titles[b]; overlap=len(titles[a]&titles[b])/len(union) if union else 0
            explicit=[k for k in ('event_id','event') if isinstance(ma.get(k),(str,int)) and ma.get(k) not in ('',None) and ma.get(k)==mb.get(k)]
            near=pairs.get((a,b),{}).get('near',{}).get('text_fingerprint',{})
            decision=review.get(a,'event','same_event',b)
            if decision=='approved': uf.union(a,b)
            # Xuất điểm khảo sát, không áp ngưỡng tự gán event.
            if overlap or (ua and ua==ub) or explicit or near or decision!='pending_review':
                rows.append(dict(sample_id=a,sample_id_b=b,component='event',issue='same_event',decision=decision,reason=review.reason(a,'event','same_event',b),title_jaccard=overlap,text_simhash_similarity=near.get('similarity'),canonical_url_equal=bool(ua and ua==ub),matching_direct_event_keys=explicit,publish_date_a=ma.get('publish_date'),publish_date_b=mb.get('publish_date')))
        events=uf.groups('event',False); mapping={i:g for g,ids in events.items() for i in ids}
        return rows,events,mapping


def safe_id(s: str) -> bool:
    return bool(re.fullmatch(r'[A-Za-z0-9_-]+',s)) and s.upper() not in {'CON','PRN','AUX','NUL',*(f'COM{i}' for i in range(1,10)),*(f'LPT{i}' for i in range(1,10))}


def sample_type(title: str|None,text: str|None,image: str|None) -> str:
    return ('full' if text and image else 'notext' if image else 'noimg' if text else 'error') if title else 'error'


def validate_manifest(records: list[dict],root: Path,eligibility: dict,events: dict,groups: dict,rejected: list[dict],input_ids: set[str]) -> None:
    """Schema tương thích analyzer After; error được đối soát ngoài manifest."""
    ids={r['sample_id'] for r in records}
    if len(ids)!=len(records) or ids & {r['sample_id'] for r in rejected} or ids|{r['sample_id'] for r in rejected} != input_ids:
        raise ValueError('MANIFEST_VALIDATION_FAILED: đối soát ID')
    paths=set()
    for r in records:
        i=r['sample_id']; p=r['pathIMG']
        if set(r)!=A.MANIFEST_KEYS or not safe_id(i) or (r['source'],r['label']) not in GROUPS or r['type'] not in A.TYPES[:3] or r['type']!=sample_type(r['title'],r['text'],p) or not A.present(r['title']):
            raise ValueError(f'MANIFEST_VALIDATION_FAILED: {i}')
        if any(x is not None and not A.present(x) for x in (r['text'],r['group_event'],p)): raise ValueError(f'MANIFEST_VALIDATION_FAILED: null/string {i}')
        if p:
            expected=f"images/{r['source']}_{r['label']}/{i}.png"
            target=(root/p).resolve()
            if p!=expected or not target.is_relative_to(root.resolve()) or not target.is_file(): raise ValueError(f'MANIFEST_VALIDATION_FAILED: path {i}')
            paths.add(target)
            # Đã decode ngay sau save; xác minh lại format/mode ở điểm publish.
            with Image.open(target) as img:
                if img.format!='PNG' or img.mode!='RGB': raise ValueError(f'MANIFEST_VALIDATION_FAILED: PNG/RGB {i}')
        if r['group_event'] is not None and i not in events.get(r['group_event'],[]): raise ValueError('MANIFEST_VALIDATION_FAILED: event mapping')
    actual={p.resolve() for p in (root/'images').rglob('*') if p.is_file()}
    if actual!=paths: raise ValueError('MANIFEST_VALIDATION_FAILED: orphan/missing image')
    event_members=[i for group in events.values() for i in group]
    if len(event_members)!=len(set(event_members)) or not set(event_members)<=ids or set(event_members)!={r['sample_id'] for r in records if r['group_event'] is not None}:
        raise ValueError('MANIFEST_VALIDATION_FAILED: event members')
    members=[i for group in groups.values() for i in group]
    if set(members)!=ids or len(members)!=len(ids): raise ValueError('MANIFEST_VALIDATION_FAILED: leakage mapping')
    blocked=set(eligibility['pending_review'])|set(eligibility['quarantined'])
    for key,allowed in [('multimodal_eligible',{'full'}),('text_only_eligible',{'full','noimg'}),('image_only_eligible',{'full','notext'})]:
        chosen=set(eligibility[key])
        if chosen & blocked or not chosen<=ids or any(r['sample_id'] in chosen and r['type'] not in allowed for r in records): raise ValueError('MANIFEST_VALIDATION_FAILED: eligibility')


def flag_issues(s: ArticleSample,t: dict,im: dict,long_words: float|None) -> list[tuple[str,str]]:
    issues=[]
    if s.text_source_key=='description' and A.present(s.text): issues.append(('text','description_only'))
    for k in ('suspected_boilerplate','suspected_error_page','suspected_login','suspected_blocked','suspected_advertising','suspected_non_article','short_text_warning'):
        if truth(t.get(k)): issues.append(('text',k))
    for k in ('replacement_char_count','repeated_paragraph_count','repeated_sentence_count','html_tag_count','html_entity_count'):
        if (num(t,k) or 0)>0: issues.append(('text',k))
    if A.present(s.text) and val(t,'language')!='en': issues.append(('text','language_review'))
    if long_words is not None and (num(t,'text_word_count') or 0)>long_words: issues.append(('text','long_text_review'))
    if truth(im.get('image_valid')):
        for k in ('suspected_placeholder','suspected_uniform','low_resolution_warning'):
            if truth(im.get(k)): issues.append(('image',k))
        if not truth(im.get('filename_matches_sampleid')): issues.append(('image','filename_mismatch'))
        if not truth(im.get('extension_matches_format')): issues.append(('image','extension_mismatch'))
    return issues


def ensure_replaceable(output: Path,cleanup: bool) -> list[str]:
    """Chỉ thay dataset theo schema quản lý, không xóa file ngoài phạm vi."""
    if not output.exists() or (output.is_dir() and not any(output.iterdir())): return []
    manifest=output/'manifest.json'
    if not manifest.is_file() or manifest.is_symlink() or any(p.name not in ('manifest.json','images') or p.is_symlink() for p in output.iterdir()):
        raise ValueError('Output không phải dataset quản lý; chọn --output-dir khác')
    data=A.read_json(manifest)
    if not isinstance(data,list) or any(not isinstance(r,dict) or set(r)!=A.MANIFEST_KEYS for r in data): raise ValueError('Manifest cũ không hợp lệ')
    refs={r['pathIMG'] for r in data if r.get('pathIMG')}; files=set(); folders={f'{a}_{b}' for a,b in GROUPS}
    for p in (output/'images').rglob('*'):
        rel=p.relative_to(output).as_posix(); parts=Path(rel).parts
        if p.is_symlink() or (p.is_dir() and (len(parts)!=2 or parts[1] not in folders)) or (p.is_file() and (len(parts)!=3 or parts[1] not in folders or p.suffix!='.png' or not safe_id(p.stem))):
            raise ValueError(f'File ngoài phạm vi quản lý: {rel}')
        if p.is_file(): files.add(rel)
    orphans=sorted(files-refs)
    if orphans and not cleanup: raise ValueError(f'Có {len(orphans)} ảnh mồ côi; dùng --cleanup-orphans nếu xác nhận')
    return orphans


def run_processing(repo: Path|str,mode: str='plan',csv_dir: Path|None=None,before_dir: Path|None=None,output_dir: Path|None=None,review_file: Path|None=None,config: ProcessingConfig=ProcessingConfig(),old_root: str|None=None,new_root: Path|None=None,cleanup_orphans: bool=False) -> dict:
    """Chạy pipeline offline, không gọi analyzer toàn bộ; plan không tạo ảnh/manifest."""
    config.validate()
    if mode not in ('plan','process') or bool(old_root)!=bool(new_root): raise ValueError('INVALID_CONFIG: mode hoặc path mapping')
    repo=Path(repo).expanduser().resolve(); csv_dir=Path(csv_dir or repo/'validation_reports').resolve(); before=Path(before_dir or repo/'reports/before').resolve(); output=Path(output_dir or repo/'processed_data').resolve()
    report=(repo/'reports/processing').resolve(); dest=(report/'plan').resolve() if mode=='plan' else report
    if not dest.is_relative_to(report): raise ValueError('INVALID_CONFIG: report plan thoát thư mục quản lý')
    stats,inv,tm,im,dup=load_before_statistics(before)
    loader=DatasetLoader(repo,old_root,new_root); samples=sorted(loader.load_raw_dataset(csv_dir),key=lambda s:s.sample_id)
    verify_inputs(samples,loader,stats,inv,tm,im)
    protected=[repo/'fakenewsnet_raw_output',csv_dir,before,*(p for s in samples for p in (s.json_path,s.image_path) if p)]
    for dst in (output,report):
        if any(dst.is_relative_to(p.resolve()) or p.resolve().is_relative_to(dst) for p in protected): raise ValueError(f'INVALID_CONFIG: output chồng lấn nguồn {dst}')
    if output.is_relative_to(report) or report.is_relative_to(output): raise ValueError('Output và report chồng lấn')
    ids={s.sample_id for s in samples}; sm={s.sample_id:s for s in samples}
    review=Reviews(Path(review_file).resolve() if review_file else None,ids)
    if review_file and Path(review_file).resolve().parent==dest: raise ValueError('Đặt review input ngoài thư mục output báo cáo')
    n=stats['text_summary']['numeric']['text_word_count']; long_words=config.review_long_words
    if long_words is None and n.get('p75') is not None and n.get('iqr') is not None: long_words=n['p75']+1.5*n['iqr']
    ar=stats['image_summary']['numeric']['aspect_ratio']; lower=upper=None
    if ar.get('p25') is not None and ar.get('iqr') is not None: lower=max(0,ar['p25']-1.5*ar['iqr']); upper=ar['p75']+1.5*ar['iqr']
    pairs=DuplicateAuditor.collect(dup,ids); candidates=[]; logs=[]; rejected=[]; records={}; audit={}; pending=defaultdict(set); quarantine=defaultdict(set); excluded_image=set(); image_pending=set()
    tp=TextProcessor(); ip=ImageProcessor(config); case_ids=Counter(i.casefold() for i in ids)
    if mode=='process': output.parent.mkdir(parents=True,exist_ok=True)
    else: report.mkdir(parents=True,exist_ok=True)
    orphans=ensure_replaceable(output,cleanup_orphans) if mode=='process' else []
    with TemporaryDirectory(prefix='.afn-processing-',dir=output.parent if mode=='process' else report) as temp:
        tmp=Path(temp); root=tmp/'dataset'; rdir=tmp/'reports'; rdir.mkdir()
        if mode=='process':
            for a,b in GROUPS: (root/'images'/f'{a}_{b}').mkdir(parents=True)
        for s in samples:
            i=s.sample_id; t,m=tm[i],im[i]; old=inv[i]; issues=flag_issues(s,t,m,long_words)
            ratio=num(m,'aspect_ratio')
            if truth(m.get('image_valid')) and ratio is not None and lower is not None and not lower<=ratio<=upper: issues.append(('image','aspect_ratio_outlier'))
            flags=[]; local=[]; local_candidates=[]; text_reject=False
            for component,issue in sorted(set(issues)):
                d=review.get(i,component,issue); flags.append(f'{component}:{issue}:{d}')
                candidates.append(dict(sample_id=i,component=component,issue=issue,decision=d,reason=review.reason(i,component,issue)))
                if d=='pending_review':
                    pending[i].add(f'{component}:{issue}')
                    if component=='image': image_pending.add(i)
                elif d=='rejected':
                    if component=='image': excluded_image.add(i)
                    else: text_reject=True; quarantine[i].add(f'text:{issue}')
            if review.get(i,'sample','training_eligibility')=='rejected': quarantine[i].add('sample:review_rejected')
            title,body=tp.process(s,review,local,local_candidates)
            if text_reject: body=None; logop(local,s,'text','text_quarantine','held','Review xác nhận không phù hợp')
            for c in local_candidates:
                if c['decision']=='pending_review': pending[i].add('text:'+c['issue'])
            candidates.extend(local_candidates)
            img_ok=truth(m.get('image_valid')) and bool(s.image_path); image_sha=None; path=None; pixels=num(m,'pixel_count')
            if not img_ok and s.image_path: logop(local,s,'image','image_quarantine','held','Ảnh thiếu/không giải mã theo Before')
            if img_ok and pixels is not None and pixels<=1:
                excluded_image.add(i); logop(local,s,'image','image_quarantine','held','IMAGE_TOO_SMALL: 1 pixel')
            if i in excluded_image:
                img_ok=False; logop(local,s,'image','image_quarantine','held','Ảnh không đủ điều kiện hoặc review rejected')
                # Ảnh đã bỏ khỏi manifest không còn chặn text-only do cờ chất lượng ảnh đó.
                pending[i]={x for x in pending[i] if not x.startswith('image:')}
                image_pending.discard(i)
            if not safe_id(i) or case_ids[i.casefold()]>1: quarantine[i].add('invalid_or_case_colliding_sample_id'); title=None
            if img_ok and title:
                rel=f'images/{s.source}_{s.label}/{i}.png'
                if mode=='plan': path=rel
                else:
                    try: image_sha=ip.process(s,root/rel,val(old,'image_sha256'),local); path=rel
                    except (OSError,ValueError,EOFError,SyntaxError,Image.DecompressionBombError,MemoryError) as exc:
                        logop(local,s,'image','IMAGE_PROCESSING_FAILED','error',str(exc)); pending[i].add('image:processing_failed'); (root/rel).unlink(missing_ok=True)
            typ=sample_type(title,body,path)
            if typ=='error':
                quarantine[i].add('invalid_manifest_modalities'); rejected.append(dict(sample_id=i,source=s.source,label=s.label,collection_status=s.collection_status,reason='Thiếu title, thiếu cả hai modality hoặc ID không an toàn'))
            else: records[i]=dict(sample_id=i,source=s.source,label=s.label,title=title,text=body,pathIMG=path,group_event=None,type=typ)
            for e in s.errors: logop(local,s,e['component'],e['error_code'],e['severity'],e['error_message'])
            logs.extend(local)
            audit[i]=dict(sample_id=i,source=s.source,label=s.label,raw_json_path=str(s.json_path) if s.json_path else None,raw_image_path=str(s.image_path) if s.image_path else None,processed_image_path=path,raw_title_sha256=val(old,'title_sha256') or None,processed_title_sha256=A.digest_text(title) if title else None,raw_text_sha256=val(old,'text_sha256') or None,processed_text_sha256=A.digest_text(body) if body else None,raw_image_sha256=val(old,'image_sha256') or None,processed_image_sha256=image_sha,input_fingerprint=old['input_fingerprint'],collection_status=s.collection_status,assessed_status=old['assessed_status'],processed_type=typ,quality_flags=flags,pipeline_version=VERSION)
        DuplicateAuditor.add_exact(pairs,records,audit)
        urls=defaultdict(list)
        for i,s in sm.items():
            md=loader.event_data.get(s.row_id,{}); u=canonical(md.get('canonical_link')) or canonical(md.get('url'))
            if u: urls[u].append(i)
        for members in urls.values():
            for a,b in combinations(sorted(members),2): pairs.setdefault((a,b),dict(sample_id=a,sample_id_b=b,exact=[],near={},post_exact=[]))['exact'].append('canonical_url')
        # Cho phép xác nhận near-duplicate thủ công kể cả khi cặp chưa có điểm hash.
        for a,b,component,issue,target in review.rows:
            if b and component=='duplicate' and issue=='same_content' and not target:
                pairs.setdefault((a,b),dict(sample_id=a,sample_id_b=b,exact=[],near={},post_exact=[]))
        event_rows,events_all,_=EventGrouper().candidates(sm,loader.event_data,pairs,review)
        events={g:[i for i in v if i in records] for g,v in events_all.items()}; events={g:v for g,v in events.items() if len(v)>1}
        for members in events.values():
            for a,b in combinations(members,2):
                if review.get(a,'event','same_event',b)=='rejected': raise ValueError(f'Event review mâu thuẫn bắc cầu: {a}, {b}')
        eventmap={i:g for g,v in events.items() for i in v}; uf=UnionFind(set(records)); duplicate_rows=[]; conflicts=[]
        for members in events.values():
            for i in members[1:]: uf.union(members[0],i)
        for (a,b),p in sorted(pairs.items()):
            exact=set(p['exact'])|set(p['post_exact']); near=p['near']; cross=sm[a].label!=sm[b].label
            text_exact=bool(exact & {'text_sha256','normalized_text_sha256','processed_text_sha256'}) and all(bool(records.get(i,{}).get('text')) for i in (a,b))
            image_exact=bool(exact & {'image_sha256','resolved_image_path','processed_image_sha256'}) and all(records.get(i,{}).get('pathIMG') and i not in image_pending for i in (a,b))
            d=review.get(a,'duplicate','same_content',b)
            edge=a in records and b in records and (text_exact or image_exact or d=='approved')
            if edge: uf.union(a,b)  # exact đáng tin không được tách chỉ bằng nút reject
            conflict=(bool(exact) or (d=='approved' and bool(near))) and cross; unresolved=False
            if conflict:
                cd=review.get(a,'duplicate','label_conflict',b)
                removed=any(i not in records or 'sample:review_rejected' in quarantine[i] or any(x.startswith('text:') for x in quarantine[i]) for i in (a,b))
                unresolved=not removed and (text_exact or (d=='approved' and 'text_fingerprint' in near) or cd!='approved')
                if unresolved:
                    for i in (a,b): quarantine[i].add('unresolved_label_conflict')
                    conflicts.append([a,b])
                candidates.append(dict(sample_id=a,sample_id_b=b,component='duplicate',issue='label_conflict',decision=cd,reason=review.reason(a,'duplicate','label_conflict',b)))
            near_review=any(x.get('candidate') is True or x.get('distance')==0 for x in near.values())
            if near_review and not edge and d=='pending_review':
                for i in (a,b): pending[i].add('duplicate:near_hash_review')
            if exact or near_review or d!='pending_review': candidates.append(dict(sample_id=a,sample_id_b=b,component='duplicate',issue='same_content',decision=d,reason=review.reason(a,'duplicate','same_content',b)))
            duplicate_rows.append(dict(sample_id=a,sample_id_b=b,source_a=sm[a].source,source_b=sm[b].source,label_a=sm[a].label,label_b=sm[b].label,exact_evidence=sorted(p['exact']),post_exact_evidence=sorted(p['post_exact']),near_evidence=near,label_conflict=conflict,unresolved_label_conflict=unresolved,review_decision=d,leakage_edge=edge))
        groups=uf.groups('leakage'); groupmap={i:g for g,v in groups.items() for i in v}
        eligibility={k:[] for k in ('multimodal_eligible','text_only_eligible','image_only_eligible','pending_review','quarantined')}
        for i in sorted(ids):
            r=records.get(i); a=audit[i]
            if r: r['group_event']=eventmap.get(i)
            if quarantine[i]: eligibility['quarantined'].append(i); status='quarantined'
            elif pending[i]: eligibility['pending_review'].append(i); status='pending_review'
            else:
                status='eligible'
                if r:
                    if r['type']=='full': eligibility['multimodal_eligible'].append(i)
                    if r['type'] in ('full','noimg'): eligibility['text_only_eligible'].append(i)
                    if r['type'] in ('full','notext'): eligibility['image_only_eligible'].append(i)
            a.update(review_status=status,training_eligibility=status,reason=sorted(quarantine[i]|pending[i]),group_event=eventmap.get(i),leakage_group_id=groupmap.get(i))
            if i in eventmap: logop(logs,sm[i],'event','event_assignment',group_event=eventmap[i])
            if 'unresolved_label_conflict' in quarantine[i]: logop(logs,sm[i],'duplicate','label_conflict_detected','held','Xung đột nhãn chưa giải quyết')
        manifest=list(records.values())
        if mode=='process':
            validate_manifest(manifest,root,eligibility,events,groups,rejected,ids)
            A.json_dump(root/'manifest.json',manifest)
            loaded=A.load_processed_dataset(root/'manifest.json')
            if any(s.manifest_valid is not True for s in loaded): raise ValueError('MANIFEST_VALIDATION_FAILED: analyzeData After loader')
        unused=[review.rows[k] for k in sorted(set(review.rows)-review.used)]
        if unused: LOG.warning('%s review không khớp ứng viên',len(unused))
        counts=Counter(a['processed_type'] for a in audit.values())
        before_counts=Counter(a['assessed_status'] for a in audit.values())
        # Baseline tham khảo chỉ dùng để thông báo chênh lệch, không dùng làm kết quả.
        reference={'input_count':358,'full':283,'notext':12,'noimg':57,'error':6}
        current_before={'input_count':len(ids),**{k:before_counts[k] for k in A.TYPES}}
        baseline_delta={k:current_before[k]-v for k,v in reference.items()}
        summary=dict(pipeline_version=VERSION,mode=mode,processing_complete=mode=='process',input_count=len(ids),manifest_count=len(manifest) if mode=='process' else None,projected_manifest_count=len(manifest) if mode=='plan' else None,rejected_count=len(rejected),quarantined_count=len(eligibility['quarantined']),pending_review_count=len(eligibility['pending_review']),processed_text_count=sum(bool(r['text']) for r in manifest) if mode=='process' else 0,processed_image_count=sum(bool(r['pathIMG']) for r in manifest) if mode=='process' else 0,projected_image_count=sum(bool(r['pathIMG']) for r in manifest) if mode=='plan' else None,text_changed_count=sum(a['raw_text_sha256']!=a['processed_text_sha256'] for a in audit.values()),image_converted_count=sum(l['operation']=='png_conversion' for l in logs) if mode=='process' else 0,event_assigned_count=len(eventmap),event_unassigned_count=len(records)-len(eventmap),event_group_count=len(events),duplicate_candidate_count=sum(bool(r['exact_evidence'] or r['post_exact_evidence'] or any(x.get('candidate') is True for x in r['near_evidence'].values())) for r in duplicate_rows),duplicate_scored_pair_count=len(duplicate_rows),unresolved_label_conflict_count=len(conflicts),unresolved_label_conflict_ids=sorted({i for p in conflicts for i in p}),status_distribution=dict(counts),group_statistics={f'{a}_{b}':dict(Counter(x['processed_type'] for x in audit.values() if (x['source'],x['label'])==(a,b))) for a,b in GROUPS},eligibility_counts={k:len(v) for k,v in eligibility.items()},processing_config=asdict(config),review_long_words=long_words,review_aspect_ratio_bounds=[lower,upper],before_config=stats['analysis_config'],before_analysis_warnings=stats.get('analysis_warnings',[]),before_statistics_sha256=A.file_sha(before/'statistics.json'),library_versions=A.versions(),unused_review_count=len(unused),removed_orphans=orphans,notes=['Plan chỉ dự kiến, chưa tạo ảnh' if mode=='plan' else 'Đã kiểm tra manifest nội bộ','Chưa xác minh semantic image-title alignment, quyền sử dụng, split hoặc label truth'])
        summary.update(before_counts=current_before,reference_baseline=reference,baseline_delta=baseline_delta,review_file_sha256=A.file_sha(Path(review_file)) if review_file else None,manifest_sha256=A.file_sha(root/'manifest.json') if mode=='process' else None)
        for name,value in [('processing_summary.json',summary),('rejected_samples.json',rejected),('events.json',{'groups':events,'mapping':eventmap}),('groups.json',{'groups':groups,'mapping':groupmap}),('eligibility.json',eligibility),('unused_review_decisions.json',unused)]: A.json_dump(rdir/name,value)
        if mode=='plan':
            for l in logs:
                if l['status']=='applied': l['status']='projected'
        A.write_csv(rdir/'processing_log.csv',logs,('sample_id','source','label','component','operation','status','reason'))
        A.write_csv(rdir/'sample_audit.csv',list(audit.values()),('sample_id','source','label','processed_type'))
        # Một dòng review cho mỗi khóa, dù đoạn lặp nhiều lần.
        unique={(val(c,'sample_id'),val(c,'sample_id_b'),val(c,'component'),val(c,'issue'),val(c,'target_sha256')):c for c in candidates}
        A.write_csv(rdir/'review_candidates.csv',[unique[k] for k in sorted(unique)],REVIEW_FIELDS)
        A.write_csv(rdir/'review_decisions.csv',list(review.rows.values()),REVIEW_FIELDS)
        A.write_csv(rdir/'duplicate_audit.csv',duplicate_rows,('sample_id','sample_id_b','label_conflict','unresolved_label_conflict'))
        A.write_csv(rdir/'event_candidates.csv',event_rows,REVIEW_FIELDS)
        A.write_csv(rdir/'event_review.csv',[r for r in event_rows if r['decision']!='pending_review'],REVIEW_FIELDS)
        (rdir/'processing.log').write_text(f'{VERSION} mode={mode}\ninput={len(ids)}\n'+ '\n'.join(f"{l['sample_id']} {l['component']} {l['operation']} {l['status']}: {l['reason']}" for l in logs)+'\n',encoding='utf-8',errors='backslashreplace')
        dest.mkdir(parents=True,exist_ok=True)
        # Marker xuất cuối. Copy staging report bằng file tạm cùng filesystem đích.
        (dest/'processing_summary.json').unlink(missing_ok=True)
        old=tmp/'previous_dataset'
        if mode=='process':
            if output.exists(): output.replace(old)
            try: root.replace(output)
            except OSError:
                if old.exists(): old.replace(output)
                raise
        try:
            with TemporaryDirectory(prefix='.publish-',dir=dest) as d:
                stage=Path(d)
                for f in sorted(rdir.iterdir()): shutil.copyfile(f,stage/f.name)
                for f in sorted(stage.iterdir()):
                    if f.name!='processing_summary.json': f.replace(dest/f.name)
                (stage/'processing_summary.json').replace(dest/'processing_summary.json')
        except OSError:
            if mode=='process':
                output.replace(tmp/'failed_dataset')
                if old.exists(): old.replace(output)
            raise
        LOG.info('%s: %s mẫu, %s rejected; báo cáo %s',mode,len(ids),len(rejected),dest)
        return summary


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',type=Path,default=Path.cwd())
    parser.add_argument('--mode',choices=('plan','process'),default='plan')
    for name in ('csv-dir','before-dir','output-dir','review-file','new-root'): parser.add_argument('--'+name,type=Path)
    parser.add_argument('--old-root'); parser.add_argument('--resize-mode',choices=('none','longest_side','letterbox'),default='none'); parser.add_argument('--target-size',type=int); parser.add_argument('--review-long-words',type=float); parser.add_argument('--cleanup-orphans',action='store_true')
    args=parser.parse_args(); logging.basicConfig(level=logging.INFO,format='%(levelname)s %(message)s')
    try:
        summary=run_processing(args.repo,args.mode,args.csv_dir,args.before_dir,args.output_dir,args.review_file,ProcessingConfig(resize_mode=args.resize_mode,target_size=args.target_size,review_long_words=args.review_long_words),args.old_root,args.new_root,args.cleanup_orphans)
        print(json.dumps({k:summary[k] for k in ('mode','input_count','manifest_count','projected_manifest_count','rejected_count','pending_review_count','quarantined_count','eligibility_counts')},indent=2,ensure_ascii=False))
    except (OSError,ValueError,RuntimeError,KeyError,TypeError) as exc:
        LOG.error('Pipeline thất bại: %s',exc); raise SystemExit(1) from exc

if __name__=='__main__': main()
