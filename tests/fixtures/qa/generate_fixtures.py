"""Sinh fixture tổng hợp AFN-014. Không tải dữ liệu mạng, không tạo Test nghiên cứu."""

import argparse
import json
from pathlib import Path
import struct
import tempfile
import zlib


def make_png(width=2, height=2, *, compression_level=-1):
    """Tệp PNG RGB tự sinh hoàn toàn từ thư viện chuẩn."""
    def chunk(kind, payload):
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(
            ">I", zlib.crc32(kind + payload) & 0xFFFFFFFF
        )

    pixels = b"".join(b"\x00" + b"\x20\x80\xe0" * width for _ in range(height))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(pixels, compression_level))
        + chunk(b"IEND", b"")
    )


def generate(destination, with_exif=False):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "long-text.txt").write_text("a" * 50001, encoding="utf-8")
    (destination / "long-title.txt").write_text("a" * 501, encoding="utf-8")
    (destination / "valid.png").write_bytes(make_png())
    (destination / "corrupt.png").write_bytes(b"not-an-image")
    (destination / "wrong-mime.txt").write_bytes(make_png())
    # PNG hợp lệ, 4.2 MP; dữ liệu không nén để vượt 10 MiB.
    (destination / "oversized.png").write_bytes(make_png(2048, 2048, compression_level=0))
    files = ["long-text.txt", "long-title.txt", "valid.png", "corrupt.png", "wrong-mime.txt", "oversized.png"]

    if with_exif:
        try:
            from PIL import Image
        except ImportError as exc:
            raise RuntimeError("Muốn tạo JPEG EXIF, cài Pillow riêng trong môi trường kiểm thử.") from exc
        im = Image.new("RGB", (3, 2), color=(32, 128, 224))
        exif = Image.Exif()
        exif[274] = 6  # Orientation: rotate 90 degrees clockwise for display.
        im.save(destination / "orientation-6.jpg", exif=exif)
        files.append("orientation-6.jpg")

    return files


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", help="Thư mục sinh tệp; mặc định là thư mục tạm mới.")
    parser.add_argument("--with-exif", action="store_true", help="Cần Pillow đã cài riêng.")
    args = parser.parse_args()
    output = Path(args.output) if args.output else Path(tempfile.mkdtemp(prefix="afn-qa-fixtures-"))
    files = generate(output, with_exif=args.with_exif)
    print(json.dumps({"output": str(output), "created": files}, ensure_ascii=False))
