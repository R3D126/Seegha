# -*- mode: python ; coding: utf-8 -*-
# Build with:  pyinstaller seegha.spec
# Lite build (default): ffmpeg is bundled LZMA-compressed (ffmpeg.exe.xz); the AI pack downloads on demand.
# Full build: if a "realesrgan" folder exists next to this file, it is bundled (works offline).
import os
from PyInstaller.utils.hooks import collect_all

EXE_NAME = os.environ.get("SEEGHA_EXE_NAME", "Seegha")

datas, binaries, hiddenimports = collect_all("tkinterdnd2")
for f in ("ffmpeg.exe.xz", "ffmpeg.exe.xz.json"):
    if os.path.exists(f):
        datas.append((f, "."))
if os.path.isdir("realesrgan"):
    datas.append(("realesrgan", "realesrgan"))

# Things Seegha never uses (keeps the exe small). Verified by converting every format afterwards.
EXCLUDES = [
    "unittest", "doctest", "pydoc", "pdb", "test", "tests", "distutils", "setuptools",
    "pkg_resources", "pip", "wheel", "lib2to3", "curses", "sqlite3", "xmlrpc", "xml", "pyexpat",
    "turtle", "idlelib", "tkinter.tix", "tkinter.dnd", "numpy",
    "PIL._imagingft", "PIL._imagingcms", "PIL._imagingtk", "PIL._imagingmorph",
    "PIL.ImageFont", "PIL.ImageCms", "PIL.ImageTk", "PIL.ImageQt", "PIL.ImageDraw",
]

a = Analysis(
    ["seegha.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=EXCLUDES,
    noarchive=False,
)


def _keep(entry):
    # Tcl/Tk extras we do not need: time-zone data, translations, demos
    dest = entry[0].replace("\\", "/").lower()
    return not dest.startswith(("tcl/tzdata/", "tcl/msgs/", "tk/msgs/", "tk/demos/", "tcl8/"))


a.datas = [d for d in a.datas if _keep(d)]
pyz = PYZ(a.pure, a.zipped_data)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name=EXE_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,          # UPX-packed exes trigger antivirus false positives
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
)
