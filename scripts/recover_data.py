#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Thu thập JSON, tải một ảnh/bài và xuất CSV phân loại cho FakeNewsNet.

Chạy trong Google Colab (sau khi đã có repository FakeNewsNet)::

    !python /content/recover_data.py --dataset-dir /content/FakeNewsNet/dataset
    !python /content/recover_data.py --dataset-dir /content/FakeNewsNet/pilot_dataset

Đầu vào là MỘT thư mục chứa bốn file CSV:
    politifact_fake.csv, politifact_real.csv,
    gossipcop_fake.csv, gossipcop_real.csv

Kết quả gồm bốn CSV riêng theo nhóm, đặt tại validation_reports:
    politifact_fake.csv, politifact_real.csv,
    gossipcop_fake.csv, gossipcop_real.csv

Mỗi CSV có bốn cột: sampleid, pathjson, path_anh, phan_loai.
Hai cột đường dẫn là đường dẫn tuyệt đối của file trên ổ đĩa,
KHÔNG phải URL từ nội dung JSON. Báo cáo recovery-attempts.jsonl ghi trạng thái
của từng mẫu nguồn. Chạy lại cùng bốn CSV tái sử dụng các JSON và ảnh đã lưu.

Quy tắc phân loại (phải có title mới thuộc ba nhóm đầu):
    full   : có title, text và ảnh đã tải trên đĩa
    notext : có title và ảnh, thiếu text
    noimg  : có title và text, thiếu ảnh
    error  : mọi trường hợp còn lại, kể cả thiếu title/JSON lỗi

Lưu ý: file này KHÔNG giải nén ZIP/TAR và KHÔNG tạo báo cáo tải ảnh riêng.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sqlite3
import subprocess
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import closing
from datetime import datetime, timezone
from io import BytesIO
from tempfile import TemporaryDirectory
from pathlib import Path
from urllib.parse import urlparse

import requests


# ============================================================
# 1. CẤU HÌNH CHUNG
# ============================================================
REPO = None
CODE_DIR = None
DATASET_DIR = None
OUTPUT_DIR = None
REPORT_DIR = None
TWEET_KEYS_PATH = None

def config_path(repo):
    # Chuẩn hóa đường dẫn thư mục gốc
    repo = Path(repo).expanduser().resolve()

    # Khởi tạo các đường dẫn cần thiết
    code_dir = repo / "code"
    dataset_dir = repo / "dataset"
    # dataset_dir = repo / "pilot"
    output_dir = repo / "fakenewsnet_raw_output"
    report_dir = repo / "validation_reports"
    tweet_keys_file = code_dir / "resources" / "tweet_keys_file.json"

    return (
        code_dir,
        dataset_dir,
        output_dir,
        report_dir,
        tweet_keys_file
    )

REQUIRED_CSV = (
    'politifact_fake.csv', 'politifact_real.csv',
    'gossipcop_fake.csv', 'gossipcop_real.csv',
)

TITLE_KEYS = ('title', 'headline')
TEXT_KEYS = ('text', 'article_text', 'content', 'description')
TOP_IMAGE_KEYS = ('top_img', 'top_images', 'img_top_url', 'top_image', 'image_url')
IMAGE_LIST_KEYS = ('images', 'img', 'image_list', 'image_urls', 'image')

MAX_WORKERS = 8
REQUEST_TIMEOUT = 20
MAX_IMAGE_PIXELS = 20_000_000
MAX_IMAGE_BYTES = 20 * 1024 * 1024  # Tối đa 20 MB/ảnh.
HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; FakeNewsNetRecovery/1.0)'}
CSV_FIELDS = ('sampleid', 'pathjson', 'path_anh', 'phan_loai')

GROUPS = [
    ("politifact", "fake"),
    ("politifact", "real"),
    ("gossipcop", "fake"),
    ("gossipcop", "real"),
]


# ============================================================
# 2. KIỂM TRA ĐẦU VÀO VÀ CHẠY MAIN.PY CỦA TÁC GIẢ
# ============================================================

def validate_dataset_dir(dataset_dir: Path) -> Path:
    """Nhận đúng một đường dẫn; dùng chung cho dataset gốc và pilot."""
    dataset_dir = dataset_dir.expanduser().resolve()
    if not dataset_dir.is_dir():
        raise FileNotFoundError(f'Không tìm thấy thư mục dataset: {dataset_dir}')

    missing = [filename for filename in REQUIRED_CSV if not (dataset_dir / filename).is_file()]
    if missing:
        raise FileNotFoundError(
            f'Thư mục {dataset_dir} thiếu CSV: {", ".join(missing)}'
        )
    return dataset_dir


def dataset_checksum(dataset_dir: Path) -> str:
    hashes = [hashlib.sha256((dataset_dir / name).read_bytes()).digest() for name in REQUIRED_CSV]
    return hashlib.sha256(b"".join(hashes)).hexdigest()


def is_article_url(url: str) -> bool:
    if not url or any(char.isspace() for char in url):
        return False
    try:
        parsed = urlparse(url if "://" in url else f"https://{url}")
        return parsed.scheme in ("http", "https") and bool(parsed.hostname) and parsed.port != 0
    except ValueError:
        return False


def prepare_pending_inputs(
    dataset_dir: Path, pending_dir: Path, output_dir: Path
) -> tuple[list[dict], int]:
    attempts = []
    pending_count = 0
    pending_dir.mkdir(parents=True, exist_ok=True)
    for source, label in GROUPS:
        filename = f"{source}_{label}.csv"
        seen = set()
        with (
            (dataset_dir / filename).open(encoding="utf-8-sig", newline="") as source_file,
            (pending_dir / filename).open("w", encoding="utf-8", newline="") as target_file,
        ):
            reader = csv.DictReader(source_file)
            if not {"id", "news_url", "title"}.issubset(reader.fieldnames or []):
                raise ValueError(f"{filename}: thiếu cột id, news_url hoặc title")
            writer = csv.DictWriter(target_file, fieldnames=reader.fieldnames)
            writer.writeheader()
            for row in reader:
                source_id = (row.get("id") or "").strip()
                if not re.fullmatch(r"[A-Za-z0-9_-]+", source_id) or source_id in seen:
                    raise ValueError(f"{filename}: ID không hợp lệ hoặc bị trùng tại dòng {reader.line_num}")
                seen.add(source_id)
                source_url = (row.get("news_url") or "").strip()
                article_path = output_dir / source / label / source_id / "news content.json"
                attempts.append({
                    "source": source,
                    "label": label,
                    "source_id": source_id,
                    "sample_id": f"{source}:{label}:{source_id}",
                    "source_url": source_url,
                    "article_path": article_path,
                })
                if is_article_url(source_url) and not read_json(article_path):
                    row["id"] = source_id
                    row["news_url"] = source_url
                    writer.writerow(row)
                    pending_count += 1
    return attempts, pending_count


def saved_at(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()


def export_attempts(attempts: list[dict], image_paths: dict[Path, str], completed: bool) -> None:
    """Write a local audit record for every input ID, including missing JSON."""
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    target = REPORT_DIR / "recovery-attempts.jsonl"
    recorded_at = datetime.now(timezone.utc).isoformat()
    with TemporaryDirectory(dir=REPORT_DIR) as temporary_dir:
        temporary = Path(temporary_dir) / target.name
        with temporary.open("w", encoding="utf-8", newline="\n") as file:
            for attempt in attempts:
                article = attempt["article_path"]
                image_path = image_paths.get(article, "")
                data = read_json(article)
                status = "excluded"
                if not attempt["source_url"]:
                    reason = "missing_url"
                elif not is_article_url(attempt["source_url"]):
                    reason = "invalid_url"
                elif not completed:
                    status, reason = "pending", "interrupted"
                elif not data:
                    reason = "article_not_recovered"
                elif not has_text_field(data, TITLE_KEYS):
                    reason = "missing_title"
                elif classify_article(article, image_path) == "error":
                    reason = "neither_recovered"
                else:
                    status, reason = "recovered", None
                record = {key: value for key, value in attempt.items() if key != "article_path"}
                record.update({
                    "status": status,
                    "exclusion_reason": reason,
                    "article_url": data.get("url") if data else None,
                    "article_saved_at": saved_at(article) if data else None,
                    "image_saved_at": saved_at(Path(image_path)) if image_path else None,
                    "recorded_at": recorded_at,
                })
                file.write(json.dumps(record, ensure_ascii=False) + "\n")
        temporary.replace(target)


def write_config(dataset_dir: Path) -> None:
    """Ghi config.json đúng cấu trúc main.py FakeNewsNet cần đọc."""
    if not (CODE_DIR / 'main.py').is_file():
        raise FileNotFoundError(f'Không tìm thấy main.py trong {CODE_DIR}')
    if not TWEET_KEYS_PATH.is_file():
        raise FileNotFoundError(f'Không tìm thấy file credentials: {TWEET_KEYS_PATH}')

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    config = {
        'dump_location': str(OUTPUT_DIR),
        'dataset_dir': str(dataset_dir),
        'tweet_keys_file': str(TWEET_KEYS_PATH),
        'num_process': 2,
        'num_twitter_keys': 1,
        'data_collection_choice': [
            {'news_source': source, 'label': label}
            for source in ('politifact', 'gossipcop')
            for label in ('fake', 'real')
        ],
        'data_features_to_collect': ['news_articles'],
    }
    (dataset_dir / "config.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2), encoding='utf-8'
    )
    print(f'[CẤU HÌNH] Dataset đầu vào: {dataset_dir}')
    print(f'[CẤU HÌNH] JSON đầu ra: {OUTPUT_DIR}')


def run_fakenewsnet(dataset_dir: Path) -> None:
    """
    Cài đặt các thư viện cần thiết và chạy FakeNewsNet main.py.
    Giữ nguyên logic thu thập dữ liệu của tác giả.
    Không chỉnh sửa file main.py.
    """

    # ========================================================
    # 1. CÀI ĐẶT CÁC THƯ VIỆN CẦN THIẾT
    # ========================================================

    print("\n[BƯỚC 1/3] Cài đặt thư viện...")

    packages = [
        "newspaper3k==0.2.8",
        "twython",
        "tqdm",
        "lxml_html_clean",
        "pillow",
        "requests"
    ]

    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "-q",
            *packages
        ],
        check=True
    )

    # ========================================================
    # 2. KIỂM TRA FILE MAIN.PY
    # ========================================================

    print("\n[BƯỚC 2/3] Kiểm tra FakeNewsNet...")

    main_path = CODE_DIR / "main.py"

    if not main_path.is_file():
        raise FileNotFoundError(
            f"Không tìm thấy main.py: {main_path}"
        )

    # ========================================================
    # 3. CHẠY MAIN.PY CỦA TÁC GIẢ
    # ========================================================

    print("\n[BƯỚC 3/3] Thu thập dữ liệu JSON...")

    subprocess.run(
        [sys.executable, str(main_path)],
        cwd=dataset_dir,
        check=True
    )

    print("\n[THÀNH CÔNG] Đã chạy xong FakeNewsNet main.py.")

# ============================================================
# 3. ĐỌC JSON VÀ LẤY CÁC TRƯỜNG CẦN THIẾT
# ============================================================

def read_json(path: Path) -> dict | None:
    """JSON không đọc được sẽ được xếp loại error ở bước cuối."""
    try:
        with path.open('r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError, UnicodeError):
        return None


def has_text_field(data: dict, keys: tuple[str, ...]) -> bool:
    """Chỉ kiểm tra giá trị văn bản không rỗng, không kiểm tra URL."""
    return any(
        isinstance(data.get(key), str) and bool(data[key].strip())
        for key in keys
    )


def extract_urls(value) -> list[str]:
    """Đọc URL từ chuỗi/danh sách/dict; KHÔNG phải hàm giải nén file."""
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, list):
        return [url for item in value for url in extract_urls(item)]
    if isinstance(value, dict):
        results = []
        for key in ('url', 'src', 'original', 'image_url', 'img_url'):
            if key in value:
                results.extend(extract_urls(value[key]))
        return results
    return []


def get_image_urls(data: dict) -> list[str]:
    """Ưu tiên top image; nếu lỗi thì thử từng ảnh trong danh sách."""
    results, seen = [], set()
    for key in TOP_IMAGE_KEYS + IMAGE_LIST_KEYS:
        for url in extract_urls(data.get(key)):
            if url not in seen:
                seen.add(url)
                results.append(url)
    return results


def find_article_jsons() -> dict[str, list[Path]]:
    """Tìm JSON theo bốn nhóm, giữ nguyên đường dẫn thực tế của từng file."""
    grouped_files = {}
    for source, label in GROUPS:
        group_name = f'{source}_{label}'
        folder = OUTPUT_DIR / source / label
        grouped_files[group_name] = sorted(
            path.resolve() for path in folder.rglob('*.json') if path.is_file()
        ) if folder.is_dir() else []
    return grouped_files


# ============================================================
# 4. TẢI TỐI ĐA MỘT ẢNH HỢP LỆ VÀO THƯ MỤC CHỨA JSON
# ============================================================

def detect_image_format(content: bytes) -> str | None:
    """Nhận diện định dạng từ bytes, không tin hoàn toàn vào đuôi URL."""
    if content.startswith(b'\xff\xd8\xff'):
        return 'jpg'
    if content.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'png'
    if content.startswith((b'GIF87a', b'GIF89a')):
        return 'gif'
    if content[:4] == b'RIFF' and content[8:12] == b'WEBP':
        return 'webp'
    if content.startswith(b'BM'):
        return 'bmp'
    if content.startswith((b'II*\x00', b'MM\x00*')):
        return 'tiff'
    if len(content) >= 12 and content[4:8] == b'ftyp':
        if content[8:12] in (b'avif', b'avis'):
            return 'avif'
        if content[8:12] in (b'heic', b'heix', b'mif1'):
            return 'heic'
    return None


def is_decodable_image(source) -> bool:
    from PIL import Image

    try:
        with Image.open(source) as image:
            width, height = image.size
            if width * height > MAX_IMAGE_PIXELS:
                return False
            image.load()
            return True
    except (OSError, ValueError, Image.DecompressionBombError):
        return False


def download_image(url: str, image_base_path: Path) -> Path | None:
    """Tải ảnh có giới hạn kích thước; thất bại không để lại file dở."""
    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https') or not parsed.netloc:
        return None

    temporary_file = image_base_path.with_suffix('.tmp')
    try:
        with requests.get(
            url, headers=HEADERS, timeout=REQUEST_TIMEOUT,
            allow_redirects=True, stream=True,
        ) as response:
            if response.status_code != 200:
                return None
            content_type = response.headers.get('Content-Type', '').lower()
            if content_type and not (
                content_type.startswith('image/') or 'octet-stream' in content_type
            ):
                return None
            data = bytearray()
            for chunk in response.iter_content(chunk_size=64 * 1024):
                if chunk:
                    data.extend(chunk)
                    if len(data) > MAX_IMAGE_BYTES:
                        return None

        image_format = detect_image_format(bytes(data))
        if image_format is None or not is_decodable_image(BytesIO(data)):
            return None
        target_path = image_base_path.with_suffix('.' + image_format)
        temporary_file.write_bytes(data)
        temporary_file.replace(target_path)
        return target_path
    except (requests.RequestException, OSError, ValueError):
        return None
    finally:
        temporary_file.unlink(missing_ok=True)


def recover_article_image(json_path: Path) -> str:
    """Trả về đường dẫn tuyệt đối của ảnh nằm cùng thư mục với JSON.

    URL chỉ dùng để tải ảnh; tuyệt đối không ghi URL vào cột path_anh.
    Khi chạy lại, ưu tiên ảnh đã tải trước đó theo URL tương ứng.
    """
    data = read_json(json_path)
    if data is None:
        return ''

    for url in get_image_urls(data):
        url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()[:12]
        image_base = json_path.parent / f'image_{url_hash}'

        # Chỉ chấp nhận file ảnh đã tồn tại trong chính thư mục chứa JSON.
        for extension in ('jpg', 'png', 'gif', 'webp', 'bmp', 'tiff', 'avif', 'heic'):
            existing_file = image_base.with_suffix('.' + extension)
            if (
                existing_file.is_file()
                and 0 < existing_file.stat().st_size <= MAX_IMAGE_BYTES
                and is_decodable_image(existing_file)
            ):
                return str(existing_file.resolve())

        downloaded_file = download_image(url, image_base)
        if downloaded_file is not None and downloaded_file.is_file():
            return str(downloaded_file.resolve())
    return ''


def recover_all_images(json_files: list[Path]) -> dict[Path, str]:
    """Chỉ tải ảnh và trả kết quả trong bộ nhớ; KHÔNG xuất báo cáo."""
    print(f'\n[BƯỚC 2/3] Tải ảnh cho {len(json_files)} JSON...')
    results = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(recover_article_image, p): p for p in json_files}
        for completed in as_completed(futures):
            p = futures[completed]
            try:
                results[p] = completed.result()
            except Exception as exc:
                print(f'[CẢNH BÁO] Không xử lý được ảnh của {p}: {exc}')
                results[p] = ''
    print(f'  Có ảnh: {sum(bool(p) for p in results.values())}/{len(json_files)}')
    return results


# ============================================================
# 5. VALIDATE VÀ XUẤT BỐN CSV THEO NHÓM
# ============================================================

def classify_article(json_path: Path, image_path: str) -> str:
    """Phân loại theo title, text và file ảnh thực sự tồn tại trên đĩa."""
    data = read_json(json_path)
    if data is None:
        return 'error'

    has_title = has_text_field(data, TITLE_KEYS)
    has_text = has_text_field(data, TEXT_KEYS)
    has_image = bool(image_path and Path(image_path).is_file())

    # Thiếu title luôn là error vì ba nhóm hợp lệ đều cần title.
    if not has_title:
        return 'error'
    if has_text and has_image:
        return 'full'
    if not has_text and has_image:
        return 'notext'
    if has_text and not has_image:
        return 'noimg'
    return 'error'


def export_group_csvs(
    grouped_jsons: dict[str, list[Path]], image_paths: dict[Path, str]
) -> dict[str, Path]:
    """Xuất bốn CSV, mỗi nhóm một file; mỗi JSON đúng một dòng.

    pathjson: đường dẫn tuyệt đối tới file JSON đã đọc.
    path_anh: đường dẫn tuyệt đối tới file ảnh thực sự tồn tại cùng thư mục.
    Nếu không có ảnh, path_anh để trống. Không ghi URL vào CSV.
    """
    print('\n[BƯỚC 3/3] Validate và xuất bốn CSV theo nhóm...')
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    output_files = {}

    for group_name, json_files in grouped_jsons.items():
        csv_path = REPORT_DIR / f'{group_name}.csv'
        temp_path = csv_path.with_suffix('.csv.tmp')
        counts = Counter()
        try:
            with temp_path.open('w', newline='', encoding='utf-8-sig') as file:
                writer = csv.DictWriter(file, fieldnames=CSV_FIELDS)
                writer.writeheader()
                for json_path in json_files:
                    json_path = json_path.resolve()
                    image_path = image_paths.get(json_path, '')
                    image_file = Path(image_path) if image_path else None
                    # Chỉ ghi đường dẫn ảnh nếu file tồn tại và nằm cùng JSON.
                    valid_image_path = (
                        str(image_file.resolve())
                        if image_file is not None
                        and image_file.is_file()
                        and image_file.resolve().parent == json_path.parent
                        else ''
                    )
                    category = classify_article(json_path, valid_image_path)
                    counts[category] += 1
                    writer.writerow({
                        'sampleid': json_path.parent.name,
                        'pathjson': str(json_path),
                        'path_anh': valid_image_path,
                        'phan_loai': category,
                    })
            temp_path.replace(csv_path)
        finally:
            temp_path.unlink(missing_ok=True)

        output_files[group_name] = csv_path
        summary = ', '.join(f'{name}={counts[name]}' for name in
                            ('full', 'notext', 'noimg', 'error'))
        print(f'  {group_name}: {len(json_files)} JSON | {summary}')
        print(f'    CSV: {csv_path}')
    return output_files


# ============================================================
# 6. ĐIỂM BẮT ĐẦU CHƯƠNG TRÌNH
# ============================================================

def main() -> None:
    global REPO, CODE_DIR, DATASET_DIR
    global OUTPUT_DIR, REPORT_DIR, TWEET_KEYS_PATH

    # ========================================================
    # 1. NHẬP ĐƯỜNG DẪN REPO
    # ========================================================

    parser = argparse.ArgumentParser(
        description="Thu thập FakeNewsNet từ dataset hoặc pilot_dataset.",
    )
    parser.add_argument("--repo", type=Path, help="Thư mục checkout FakeNewsNet")
    parser.add_argument("--dataset-dir", type=Path, help="Thư mục chứa 4 file CSV đầu vào")
    args = parser.parse_args()

    repo_input = args.repo or Path(input("Nhập đường dẫn đến REPO: ").strip())
    REPO = repo_input.expanduser().resolve()
    if not REPO.is_dir():
        raise FileNotFoundError(f"Không tìm thấy thư mục REPO: {REPO}")

    CODE_DIR, DATASET_DIR, OUTPUT_DIR, REPORT_DIR, TWEET_KEYS_PATH = config_path(REPO)
    DATASET_DIR = validate_dataset_dir(args.dataset_dir or DATASET_DIR)
    OUTPUT_DIR = OUTPUT_DIR / dataset_checksum(DATASET_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[DATASET] {DATASET_DIR}")
    print(f"[OUTPUT] {OUTPUT_DIR}")
    print(f"[REPORT] {REPORT_DIR}")

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(REPORT_DIR / ".recovery-lock.sqlite", timeout=0)) as reservation:
        reservation.execute("BEGIN IMMEDIATE")
        recover_dataset()

    print("\n[HOÀN THÀNH] Pipeline đã chạy xong.")
    print(f"Thư mục báo cáo: {REPORT_DIR}")


def recover_dataset() -> None:
    with TemporaryDirectory(dir=OUTPUT_DIR) as temporary_dir:
        pending_dir = Path(temporary_dir)
        attempts, pending_count = prepare_pending_inputs(DATASET_DIR, pending_dir, OUTPUT_DIR)
        image_paths = {}
        completed = False
        try:
            if pending_count:
                write_config(pending_dir)
                run_fakenewsnet(pending_dir)

            grouped_jsons = find_article_jsons()
            json_files = [path for paths in grouped_jsons.values() for path in paths]
            image_paths = recover_all_images(json_files)
            export_group_csvs(grouped_jsons, image_paths)
            completed = True
        finally:
            export_attempts(attempts, image_paths, completed)


if __name__ == "__main__":
    main()
