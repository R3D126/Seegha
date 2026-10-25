"""Compress ffmpeg.exe with LZMA (about 28% smaller than PyInstaller's zlib) and write its metadata.

usage: python tools/pack_ffmpeg.py [path/to/ffmpeg.exe]
creates ffmpeg.exe.xz and ffmpeg.exe.xz.json next to the script's working directory.
Seegha unpacks it once into %LOCALAPPDATA%\\Seegha\\bin on first run.
"""
import hashlib
import json
import lzma
import sys
from pathlib import Path

src = Path(sys.argv[1] if len(sys.argv) > 1 else "ffmpeg.exe")
data = src.read_bytes()
out = Path("ffmpeg.exe.xz")
with lzma.open(str(out), "wb", preset=9 | lzma.PRESET_EXTREME) as f:
    f.write(data)
meta = {"name": "ffmpeg.exe", "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
Path("ffmpeg.exe.xz.json").write_text(json.dumps(meta), encoding="utf-8")
print("{} -> {}  ({:.1f} MB -> {:.1f} MB)".format(src, out, len(data) / 2 ** 20, out.stat().st_size / 2 ** 20))
