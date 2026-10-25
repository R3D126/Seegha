#!/usr/bin/env python3
"""
Seegha (صيغة) - by R3D
Fast file converter: images (Pillow), video/audio (ffmpeg) and optional AI upscaling (Real-ESRGAN).
محوّل ملفات سريع: صور وفيديو وصوت، مع رفع جودة بالذكاء الاصطناعي.

GUI:  python seegha.py
CLI:  python seegha.py -t jpg a.png b.png
      python seegha.py -t mp4 --mute video.mkv          (video without audio)
      python seegha.py -t png --upscale 4 small.jpg     (AI upscale)
      python seegha.py --lang ar -t mp3 video.mp4

Targets Python 3.8 so the same code runs from Windows 7 to Windows 11.
"""
import argparse
import glob
import hashlib
import json
import locale
import lzma
import os
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image, ImageOps

__version__ = "1.1.0"
Image.MAX_IMAGE_PIXELS = 300_000_000

# ---------------------------------------------------------------- formats
IMAGE_PIL = {"jpg": "JPEG", "jpeg": "JPEG", "png": "PNG", "webp": "WEBP",
             "bmp": "BMP", "gif": "GIF", "tiff": "TIFF", "ico": "ICO"}
IMAGE_IN = set(IMAGE_PIL) | {"tif", "jfif"}
VIDEO_IN = {"mp4", "mkv", "webm", "avi", "mov", "flv", "wmv", "m4v", "ts",
            "3gp", "mpg", "mpeg"}
AUDIO_IN = {"mp3", "wav", "flac", "aac", "ogg", "m4a", "opus", "wma"}

IMAGE_OUT = ["jpg", "png", "webp", "bmp", "gif", "tiff", "ico"]
VIDEO_OUT = ["mp4", "mkv", "webm", "avi", "mov", "gif"]
AUDIO_OUT = ["mp3", "wav", "flac", "aac", "ogg", "m4a"]
ALL_OUT = IMAGE_OUT + [f for f in VIDEO_OUT if f not in IMAGE_OUT] + AUDIO_OUT
AI_VIDEO_OUT = ("mp4", "mkv", "webm", "avi", "mov")

# Real-ESRGAN models: key -> (model name, scales it really supports)
# x4plus models are x4-only; animevideov3 ships x2/x3/x4 model files.
AI_MODELS = {
    "real": ("realesrgan-x4plus", (4,)),
    "anime": ("realesrgan-x4plus-anime", (4,)),
    "fast": ("realesr-animevideov3", (2, 3, 4)),
}
AI_KEYS = ["real", "anime", "fast"]
AUDIO_MODES = ["keep", "mute", "only"]

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
LOW_PRIO = 0x00004000 if os.name == "nt" else 0       # BELOW_NORMAL_PRIORITY_CLASS: keeps the PC responsive
PROC_FLAGS = NO_WINDOW | LOW_PRIO
ESRGAN_ZIP_EXE = "realesrgan-ncnn-vulkan.exe"
ESRGAN_BIN = "realesrgan-ncnn-vulkan" + (".exe" if os.name == "nt" else "")
WORK_PREFIX = "seegha_"
# One heavy job at a time (ffmpeg + GPU). RLock: the AI video pipeline calls ffmpeg from inside.
FF_LOCK = threading.RLock()

# AI pack (downloaded once when needed, unless the "Full" build already contains it)
AI_PACK_URL = ("https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/"
               "realesrgan-ncnn-vulkan-20220424-windows.zip")
AI_PACK_SHA256 = "abc02804e17982a3be33675e4d471e91ea374e65b70167abc09e31acb412802d"
AI_PACK_SIZE = 45474481

# Video upscaling is capped to a 4K box: 8K frames are what froze the PC (RAM, VRAM, disk, x264).
MAX_VIDEO_W, MAX_VIDEO_H = 3840, 2160
MAX_IMAGE_OUT_PIXELS = 100_000_000
CHUNK_FRAMES = 100          # frames per Real-ESRGAN run (resume point if the GPU driver resets)
GPU_KEYS = ["light", "balanced", "max"]
# (tile size, "load:proc:save" threads) tried in order; smaller tiles = shorter GPU bursts
GPU_ATTEMPTS = {
    "light": [(100, "1:1:1"), (64, "1:1:1"), (32, "1:1:1")],
    "balanced": [(200, "1:2:2"), (100, "1:1:1"), (64, "1:1:1"), (32, "1:1:1")],
    "max": [(0, "1:2:2"), (200, "1:2:2"), (100, "1:1:1"), (64, "1:1:1"), (32, "1:1:1")],
}
NO_RETRY = ("invalid gpu", "invalid tilesize", "invalid thread", "invalid output",
            "invalid format", "unknown model", "decode image", "encode image")
MODEL_SCALES = {name: scales for name, scales in AI_MODELS.values()}

# ---------------------------------------------------------------- cancel + child process registry
CANCEL = threading.Event()
_ACTIVE = set()
_ACTIVE_LOCK = threading.Lock()


def kill_active():
    with _ACTIVE_LOCK:
        procs = list(_ACTIVE)
    for p in procs:
        try:
            p.kill()
        except Exception:
            pass


def check_cancel():
    if CANCEL.is_set():
        raise UserError("err_cancel")


def _popen(cmd, **kw):
    kw.setdefault("creationflags", PROC_FLAGS)
    p = subprocess.Popen(cmd, **kw)
    with _ACTIVE_LOCK:
        _ACTIVE.add(p)
    return p


def _release(p):
    with _ACTIVE_LOCK:
        _ACTIVE.discard(p)


# ---------------------------------------------------------------- i18n (Arabic / English)
STR = {
    "ar": {
        "title": "Seegha | صيغة — محوّل الملفات",
        "add_files": "إضافة ملفات", "remove_sel": "حذف المحدد", "clear_all": "مسح الكل",
        "drop_hint": "اسحب الملفات هنا", "nodnd_hint": "السحب والإفلات غير متوفر، استخدم زر الإضافة",
        "col_file": "الملف", "col_status": "الحالة",
        "language": "اللغة:",
        "convert_to": "التحويل إلى:", "save_quality": "جودة الحفظ:",
        "fast_copy": "سريع (بدون إعادة ترميز إن أمكن)",
        "audio": "الصوت:", "audio_keep": "مع الصوت", "audio_mute": "بدون صوت (فيديو فقط)",
        "audio_only": "صوت فقط",
        "ai_group": "رفع الجودة بالذكاء الاصطناعي (Real-ESRGAN)",
        "ai_enable": "تفعيل", "ai_type": "النوع:", "ai_scale": "المضاعفة:",
        "ai_real": "واقعي (صور فوتوغرافية) ×4", "ai_anime": "رسوم / أنمي ×4",
        "ai_fast": "سريع (يصلح للفيديو) ×2 ×3 ×4",
        "gpu": "الحمل على كرت الشاشة:",
        "gpu_light": "خفيف (يبقي الجهاز مرتاح) - موصى به", "gpu_balanced": "متوازن",
        "gpu_max": "أقصى سرعة (قد يبطّئ الجهاز)",
        "ai_note": "يحتاج كرت شاشة يدعم تقنية Vulkan من كروت NVIDIA أو AMD أو Intel الحديثة",
        "ai_note_video": "رفع جودة الفيديو بطيء جداً لأن كل إطار يمر على النموذج، ويحتاج مساحة فاضية كبيرة على القرص، والحد الأقصى للناتج دقة 4K",
        "ai_note_gif": "الإخراج gif لا يدعم رفع الجودة",
        "ai_note_dl": "أول استخدام يحمّل حزمة رفع الجودة (حوالي 45 ميجا) مرة وحدة من الإنترنت",
        "outdir_btn": "مجلد الإخراج", "outdir_dialog": "مجلد الإخراج",
        "outdir_hint": "(إذا تركته فاضي يحفظ جنب الملف الأصلي)",
        "pick_files": "اختر الملفات", "start": "ابدأ التحويل",
        "s_wait": "بانتظار التحويل", "s_queue": "بانتظار الدور...",
        "s_done": "تم ✔ {name}", "s_fail": "فشل ✘ {msg}",
        "p_convert": "جاري التحويل...", "p_save": "جاري الحفظ...",
        "p_upscale_img": "رفع الجودة...", "p_extract": "استخراج الإطارات...",
        "p_upscale": "رفع الجودة {n}/{total} (×{scale}) متبقي {eta}",
        "p_upscale_lim": "رفع الجودة {n}/{total} (×{scale} بسبب حد 4K) متبقي {eta}",
        "p_assemble": "تجميع الفيديو...", "p_download": "تحميل حزمة رفع الجودة {done}/{total} ميجا",
        "s_cancel": "أُلغي", "stop": "إيقاف",
        "dl_title": "تحميل حزمة رفع الجودة",
        "dl_ask": "رفع الجودة يحتاج حزمة النماذج (حوالي {size} ميجا) وتتحمّل مرة وحدة من GitHub. تحمّلها الحين؟",
        "err_cancel": "تم الإلغاء",
        "err_ai_download": "تعذّر تحميل حزمة رفع الجودة: {detail}. تقدر تستخدم نسخة Seegha-Full اللي تحتويها",
        "err_ai_checksum": "الحزمة المحمّلة تالفة (فشل التحقق). جرّب مرة ثانية",
        "err_model_missing": "ملف النموذج غير موجود: {model}",
        "err_ffmpeg_start": "تعذّر تشغيل ffmpeg: {detail}. على ويندوز 7 ثبّت التحديثات (KB2999226) أو ضع ffmpeg.exe متوافق جنب Seegha.exe",
        "err_video_big": "ناتج الفيديو سيكون {ow}x{oh} وهو أكبر من الحد المسموح {maxw}x{maxh}. استخدم النموذج السريع بمضاعفة أقل أو فيديو أصغر",
        "cli_gpu": "الحمل على كرت الشاشة: light أو balanced أو max (الافتراضي light)",
        "cli_install_ai": "تحميل حزمة رفع الجودة ثم الخروج",
        "cli_ai_installed": "تم تثبيت حزمة رفع الجودة في: {path}",
        "err_unsupported": "لا يمكن تحويل .{src} إلى {dst}",
        "err_gif_ai": "رفع الجودة ما يدعم الإخراج gif. اختر mp4 أو mkv أو webm",
        "err_ffmpeg_missing": "ffmpeg غير موجود. ثبّته بالأمر: winget install Gyan.FFmpeg",
        "err_esrgan_missing": "مجلد realesrgan (مع models) غير موجود. نسخة exe الجاهزة تحتويه.",
        "err_esrgan_failed": "{detail} (يحتاج كرت شاشة يدعم Vulkan وتعريف حديث)",
        "err_esrgan_nooutput": "Real-ESRGAN ما أنتج ملف",
        "err_unknown_model": "نموذج غير معروف: {key}",
        "err_too_big": "الناتج كبير جداً ({w}x{h}). استخدم صورة أصغر أو مضاعفة أقل",
        "err_no_frames": "ما لقيت إطارات في الفيديو",
        "err_disk": "المساحة الفاضية ما تكفي (محتاج تقريباً {need} جيجا، المتوفر {free} جيجا)",
        "err_partial": "Real-ESRGAN عالج {done} من {total} إطار فقط",
        "err_extract": "فشل استخراج الإطارات: {detail}",
        "err_assemble": "فشل تجميع الفيديو: {detail}",
        "err_ffmpeg": "فشل ffmpeg: {detail}",
        "cli_done": "تم {ok} من {total}",
        "cli_need_fmt": "لازم تحدد الصيغة بـ -t مثل: -t jpg",
        "cli_desc": "Seegha (صيغة) — محوّل صور وفيديو وصوت",
        "cli_files": "الملفات (يدعم *.png)", "cli_to": "الصيغة المطلوبة مثل jpg أو mp4 أو mp3",
        "cli_outdir": "مجلد الإخراج", "cli_quality": "جودة حفظ الصور 1-100",
        "cli_fast": "نسخ مباشر للفيديو بدون إعادة ترميز إن أمكن",
        "cli_mute": "إخراج الفيديو بدون صوت",
        "cli_upscale": "رفع الجودة بالذكاء الاصطناعي بهذي المضاعفة",
        "cli_model": "real=صور واقعية ×4 | anime=رسوم ×4 | fast=سريع ×2/×3/×4 (الافتراضي: real للصور، fast للفيديو)",
        "cli_lang": "لغة الرسائل: ar أو en",
    },
    "en": {
        "title": "Seegha — File Converter",
        "add_files": "Add files", "remove_sel": "Remove selected", "clear_all": "Clear all",
        "drop_hint": "Drag files here", "nodnd_hint": "Drag & drop unavailable, use the Add button",
        "col_file": "File", "col_status": "Status",
        "language": "Language:",
        "convert_to": "Convert to:", "save_quality": "Save quality:",
        "fast_copy": "Fast (no re-encode when possible)",
        "audio": "Audio:", "audio_keep": "Keep audio", "audio_mute": "No audio (video only)",
        "audio_only": "Audio only",
        "ai_group": "AI quality upscaling (Real-ESRGAN)",
        "ai_enable": "Enable", "ai_type": "Model:", "ai_scale": "Scale:",
        "ai_real": "Realistic (photos) ×4", "ai_anime": "Illustration / anime ×4",
        "ai_fast": "Fast (good for video) ×2 ×3 ×4",
        "gpu": "GPU usage:",
        "gpu_light": "Light (keeps the PC responsive) - recommended", "gpu_balanced": "Balanced",
        "gpu_max": "Maximum speed (may slow the PC)",
        "ai_note": "Needs a Vulkan-capable GPU (modern NVIDIA, AMD or Intel)",
        "ai_note_video": "Video upscaling is very slow (every frame goes through the model), needs a lot of free disk space, and the output is capped at 4K",
        "ai_note_gif": "gif output does not support upscaling",
        "ai_note_dl": "First use downloads the AI pack (about 45 MB) once from the internet",
        "outdir_btn": "Output folder", "outdir_dialog": "Output folder",
        "outdir_hint": "(leave empty to save next to the original file)",
        "pick_files": "Choose files", "start": "Start conversion",
        "s_wait": "Waiting", "s_queue": "Queued...",
        "s_done": "Done ✔ {name}", "s_fail": "Failed ✘ {msg}",
        "p_convert": "Converting...", "p_save": "Saving...",
        "p_upscale_img": "Upscaling...", "p_extract": "Extracting frames...",
        "p_upscale": "Upscaling {n}/{total} (x{scale}) ETA {eta}",
        "p_upscale_lim": "Upscaling {n}/{total} (x{scale}, 4K limit) ETA {eta}",
        "p_assemble": "Assembling video...", "p_download": "Downloading AI pack {done}/{total} MB",
        "s_cancel": "Cancelled", "stop": "Stop",
        "dl_title": "Download AI pack",
        "dl_ask": "AI upscaling needs the model pack (about {size} MB), downloaded once from GitHub. Download it now?",
        "err_cancel": "Cancelled",
        "err_ai_download": "Could not download the AI pack: {detail}. You can use the Seegha-Full build, which includes it",
        "err_ai_checksum": "The downloaded pack is corrupt (checksum failed). Please try again",
        "err_model_missing": "Model file not found: {model}",
        "err_ffmpeg_start": "Could not start ffmpeg: {detail}. On Windows 7 install the updates (KB2999226) or put a compatible ffmpeg.exe next to Seegha.exe",
        "err_video_big": "The video output would be {ow}x{oh}, above the allowed {maxw}x{maxh}. Use the fast model with a lower scale or a smaller video",
        "cli_gpu": "GPU usage: light, balanced or max (default light)",
        "cli_install_ai": "Download the AI pack and exit",
        "cli_ai_installed": "AI pack installed in: {path}",
        "err_unsupported": "Cannot convert .{src} to {dst}",
        "err_gif_ai": "Upscaling does not support gif output. Choose mp4, mkv or webm",
        "err_ffmpeg_missing": "ffmpeg not found. Install it with: winget install Gyan.FFmpeg",
        "err_esrgan_missing": "The realesrgan folder (with models) is missing. The ready-made exe includes it.",
        "err_esrgan_failed": "{detail} (needs a Vulkan-capable GPU and an up-to-date driver)",
        "err_esrgan_nooutput": "Real-ESRGAN produced no output",
        "err_unknown_model": "Unknown model: {key}",
        "err_too_big": "Output too large ({w}x{h}). Use a smaller image or a lower scale",
        "err_no_frames": "No frames found in the video",
        "err_disk": "Not enough free disk space (need about {need} GB, available {free} GB)",
        "err_partial": "Real-ESRGAN processed only {done} of {total} frames",
        "err_extract": "Failed to extract frames: {detail}",
        "err_assemble": "Failed to assemble the video: {detail}",
        "err_ffmpeg": "ffmpeg failed: {detail}",
        "cli_done": "Done {ok} of {total}",
        "cli_need_fmt": "You must give the target format with -t, e.g. -t jpg",
        "cli_desc": "Seegha — convert images, video and audio",
        "cli_files": "Files (wildcards like *.png work)", "cli_to": "Target format, e.g. jpg, mp4, mp3",
        "cli_outdir": "Output folder", "cli_quality": "Image save quality 1-100",
        "cli_fast": "Copy streams without re-encoding when possible (video)",
        "cli_mute": "Remove audio from the output video",
        "cli_upscale": "AI-upscale with this scale factor",
        "cli_model": "real=realistic x4 | anime=illustration x4 | fast=fast x2/x3/x4 (default: real for images, fast for video)",
        "cli_lang": "Message language: ar or en",
    },
}
_LANG = "en"


def set_lang(lang):
    global _LANG
    _LANG = lang if lang in STR else "en"


def get_lang():
    return _LANG


def tr(key, **kw):
    s = STR[_LANG].get(key) or STR["en"][key]
    return s.format(**kw) if kw else s


class UserError(Exception):
    """Error with a translatable message (rendered when displayed, so language can change)."""

    def __init__(self, key, **kw):
        super().__init__(key)
        self.key, self.kw = key, kw

    def message(self):
        return tr(self.key, **self.kw)


def err_text(e):
    return e.message() if isinstance(e, UserError) else str(e)


def _config_path():
    return data_dir() / "config.json"


def detect_lang():
    try:  # Windows UI language (works on Windows 7 → 11)
        import ctypes
        lid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        return "ar" if (lid & 0x3FF) == 0x01 else "en"
    except Exception:
        pass
    try:
        loc = (locale.getdefaultlocale()[0] or "").lower()
        return "ar" if loc.startswith("ar") else "en"
    except Exception:
        return "en"


def load_lang():
    try:
        data = json.loads(_config_path().read_text(encoding="utf-8"))
        if data.get("lang") in STR:
            return data["lang"]
    except Exception:
        pass
    return detect_lang()


def save_lang(lang):
    try:
        p = _config_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"lang": lang}), encoding="utf-8")
    except Exception:
        pass


# ---------------------------------------------------------------- helpers
def ext_of(path):
    return Path(path).suffix.lower().lstrip(".")


def kind_of_ext(ext):
    if ext in IMAGE_IN:
        return "image"
    if ext in VIDEO_IN:
        return "video"
    if ext in AUDIO_IN:
        return "audio"
    return None


def data_dir():
    base = (os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
            or os.path.join(os.path.expanduser("~"), ".local", "share"))
    return Path(base) / "Seegha"


def _bundle_dirs():
    if getattr(sys, "frozen", False):
        return [Path(getattr(sys, "_MEIPASS", "")), Path(sys.executable).parent]
    return [Path(__file__).resolve().parent]


_FF_PATH = [None]
_FF_LOCK_X = threading.Lock()


def _unpack_xz(stem):
    """The exe ships ffmpeg LZMA-compressed (much smaller). Unpack it once into a cache folder."""
    for d in _bundle_dirs():
        xz, meta = d / (stem + ".exe.xz"), d / (stem + ".exe.xz.json")
        if not (xz.is_file() and meta.is_file()):
            continue
        try:
            m = json.loads(meta.read_text(encoding="utf-8"))
        except Exception:
            continue
        for base in (data_dir() / "bin", Path(tempfile.gettempdir()) / "seegha-bin"):
            target = base / "{}-{}.exe".format(stem, m["sha256"][:12])
            try:
                if target.is_file() and target.stat().st_size == m["size"]:
                    return str(target)
                base.mkdir(parents=True, exist_ok=True)
                tmp = target.with_name(target.name + ".tmp{}".format(os.getpid()))
                with lzma.open(str(xz), "rb") as src, open(str(tmp), "wb") as out:
                    shutil.copyfileobj(src, out, 1 << 20)
                if tmp.stat().st_size != m["size"]:
                    tmp.unlink()
                    continue
                os.replace(str(tmp), str(target))
                return str(target)
            except Exception:
                continue
    return None


def ffmpeg_exe():
    """ffmpeg: plain ffmpeg.exe next to us, the bundled LZMA copy (cached), or PATH."""
    with _FF_LOCK_X:
        if _FF_PATH[0] and os.path.isfile(_FF_PATH[0]):
            return _FF_PATH[0]
        for d in _bundle_dirs():
            c = d / "ffmpeg.exe"
            if c.is_file():
                _FF_PATH[0] = str(c)
                return _FF_PATH[0]
        _FF_PATH[0] = _unpack_xz("ffmpeg") or shutil.which("ffmpeg")
        return _FF_PATH[0]


def user_ai_dir():
    return data_dir() / "realesrgan"


def esrgan_dir():
    """Folder holding Real-ESRGAN (bundled in the Full build, or the downloaded pack)."""
    for c in [d / "realesrgan" for d in _bundle_dirs()] + [user_ai_dir()]:
        if (c / ESRGAN_BIN).is_file() and (c / "models").is_dir():
            return c
    return None


def install_ai_pack(progress=None):
    """Download the Real-ESRGAN pack once (checksum verified) into the user's data folder."""
    import ssl
    import urllib.request
    import zipfile
    # System store first (works behind antivirus/corporate HTTPS inspection),
    # plus certifi's bundle (old Windows 7 stores lack newer root certificates).
    ctx = ssl.create_default_context()
    try:
        import certifi
        ctx.load_verify_locations(cafile=certifi.where())
    except Exception:
        pass
    dest = user_ai_dir()
    with _workdir(dest.parent) as td:
        zpath = Path(td) / "pack.zip"
        req = urllib.request.Request(AI_PACK_URL, headers={"User-Agent": "Seegha/" + __version__})
        h = hashlib.sha256()
        got = 0
        try:
            with urllib.request.urlopen(req, timeout=30, context=ctx) as r, open(str(zpath), "wb") as f:
                total = int(r.headers.get("Content-Length") or AI_PACK_SIZE)
                while True:
                    check_cancel()
                    chunk = r.read(1 << 18)
                    if not chunk:
                        break
                    f.write(chunk)
                    h.update(chunk)
                    got += len(chunk)
                    if progress:
                        progress("p_download", done=got // 10 ** 6, total=max(1, total // 10 ** 6))
        except UserError:
            raise
        except Exception as e:
            raise UserError("err_ai_download", detail=str(e))
        if h.hexdigest() != AI_PACK_SHA256:
            raise UserError("err_ai_checksum")
        staging = Path(td) / "pack"
        with zipfile.ZipFile(str(zpath)) as z:
            for n in z.namelist():
                if n in (ESRGAN_ZIP_EXE, "vcomp140.dll") or n.startswith("models/"):
                    z.extract(n, str(staging))
        if not (staging / ESRGAN_ZIP_EXE).is_file() or not (staging / "models").is_dir():
            raise UserError("err_ai_checksum")
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            shutil.rmtree(str(dest), ignore_errors=True)
        shutil.move(str(staging), str(dest))
    return dest


def _free(path):
    try:
        return shutil.disk_usage(str(path)).free
    except Exception:
        return 0


def _workdir(prefer=None):
    """Temp dir on the drive with more free space (frames can reach many GB)."""
    base = None
    try:
        if prefer is not None and Path(prefer).is_dir() and \
                _free(prefer) > _free(tempfile.gettempdir()) * 1.5:
            base = str(prefer)
    except Exception:
        base = None
    try:
        return tempfile.TemporaryDirectory(prefix=WORK_PREFIX, dir=base)
    except OSError:
        return tempfile.TemporaryDirectory(prefix=WORK_PREFIX)


def sweep_stale_workdirs(max_age_hours=6):
    """Remove work folders left behind by a crash/kill (only old ones, so running jobs are safe)."""
    cutoff = time.time() - max_age_hours * 3600
    for d in glob.glob(os.path.join(tempfile.gettempdir(), WORK_PREFIX + "*")):
        try:
            if not os.path.isdir(d):
                continue
            newest = os.path.getmtime(d)
            for sub in os.scandir(d):
                newest = max(newest, sub.stat().st_mtime)
            if newest < cutoff:
                shutil.rmtree(d, ignore_errors=True)
        except Exception:
            pass


def pick_engine(src_ext, target):
    """'image', 'ffmpeg', or None when the conversion is unsupported."""
    if src_ext in IMAGE_IN:
        if target in IMAGE_OUT:
            return "image"
        if src_ext == "gif" and target in VIDEO_OUT:
            return "ffmpeg"
        return None
    if src_ext in VIDEO_IN:
        return "ffmpeg" if (target in VIDEO_OUT or target in AUDIO_OUT) else None
    if src_ext in AUDIO_IN:
        return "ffmpeg" if target in AUDIO_OUT else None
    return None


def _primary_targets(ext):
    kind = kind_of_ext(ext)
    if kind == "image":
        extra = [v for v in VIDEO_OUT if v != "gif"] if ext == "gif" else []
        return IMAGE_OUT + extra
    if kind == "video":
        return VIDEO_OUT
    if kind == "audio":
        return AUDIO_OUT
    return []


def targets_for_files(files, audio_only=False):
    """Formats that fit the files: video -> video formats only, images -> image formats only..."""
    kinds = {kind_of_ext(ext_of(f)) for f in files} - {None}
    if not kinds:
        return list(ALL_OUT)
    if audio_only and "video" in kinds:
        return list(AUDIO_OUT)
    if len(kinds) > 1:
        return list(ALL_OUT)
    known = [f for f in files if kind_of_ext(ext_of(f))]
    sets = [set(_primary_targets(ext_of(f))) for f in known]
    common = [t for t in _primary_targets(ext_of(known[0])) if all(t in s for s in sets)]
    return common or list(ALL_OUT)


_DST_LOCK = threading.Lock()
_RESERVED = set()


def unique_dst(src, fmt, outdir):
    """Pick a free output name; reserved under a lock so parallel jobs never collide."""
    ext = "jpg" if fmt == "jpeg" else fmt
    folder = outdir or src.parent
    with _DST_LOCK:
        dst = folder / "{}.{}".format(src.stem, ext)
        n = 1
        while dst.exists() or dst.resolve() == src.resolve() or str(dst).lower() in _RESERVED:
            tag = "_converted" if n == 1 else "_converted{}".format(n)
            dst = folder / "{}{}.{}".format(src.stem, tag, ext)
            n += 1
        _RESERVED.add(str(dst).lower())
    return dst


def _release_dst(dst):
    with _DST_LOCK:
        _RESERVED.discard(str(dst).lower())


def _last_line(text, default):
    lines = [l for l in (text or "").strip().splitlines() if l.strip()]
    return lines[-1] if lines else default


def _noop(key, **kw):
    pass


def _fmt_eta(sec):
    sec = int(max(0, sec))
    h, r = divmod(sec, 3600)
    m, s = divmod(r, 60)
    return "{}:{:02d}:{:02d}".format(h, m, s) if h else "{}:{:02d}".format(m, s)


def _count_files(path):
    try:
        return sum(1 for _ in os.scandir(str(path)))
    except OSError:
        return 0


# ---------------------------------------------------------------- images
def convert_image(src, dst, fmt, quality):
    pil_fmt = IMAGE_PIL[fmt]
    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im)  # fix phone-photo orientation
        if pil_fmt in ("JPEG", "BMP") and (
            im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info)
        ):
            rgba = im.convert("RGBA")
            bg = Image.new("RGB", rgba.size, (255, 255, 255))  # transparency -> white
            bg.paste(rgba, mask=rgba.getchannel("A"))
            im = bg
        elif pil_fmt == "JPEG" and im.mode != "RGB":
            im = im.convert("RGB")
        elif pil_fmt != "TIFF" and im.mode in ("CMYK", "YCbCr", "LAB", "HSV"):
            im = im.convert("RGB")  # these modes cannot be written to png/webp/...

        kwargs = {}
        if pil_fmt in ("JPEG", "WEBP"):
            kwargs["quality"] = quality
        if pil_fmt == "JPEG":
            kwargs["optimize"] = True
        if pil_fmt == "ICO":
            im.thumbnail((256, 256))
            sizes = [(s, s) for s in (16, 32, 48, 64, 128, 256) if s <= max(im.size)]
            kwargs["sizes"] = sizes or [im.size]
        im.save(dst, pil_fmt, **kwargs)


# ---------------------------------------------------------------- AI upscaling (Real-ESRGAN)
def _resolve_ai(upscale, kind):
    """(model name, effective scale), correcting unsupported combinations."""
    key = upscale.get("model") or ("real" if kind == "image" else "fast")
    if key not in AI_MODELS:
        raise UserError("err_unknown_model", key=key)
    name, scales = AI_MODELS[key]
    scale = upscale.get("scale") or (scales[0] if key == "fast" else scales[-1])
    if scale not in scales:
        scale = scales[-1]  # x4plus models only exist at x4
    return name, scale


def _fits_video(w, h, s):
    return max(w, h) * s <= MAX_VIDEO_W and min(w, h) * s <= MAX_VIDEO_H


def fit_video_scale(model, w, h, requested):
    """Largest scale <= requested (supported by the model) whose output stays inside 4K."""
    cands = [s for s in sorted(MODEL_SCALES[model], reverse=True)
             if s <= requested and _fits_video(w, h, s)]
    if not cands:
        raise UserError("err_video_big", ow=w * requested, oh=h * requested,
                        maxw=MAX_VIDEO_W, maxh=MAX_VIDEO_H)
    return cands[0]


def _attempt_esrgan(cmd, cwd, on_poll=None):
    # stderr goes to a temp file: an unread PIPE can block the tool on long videos
    with tempfile.TemporaryFile("w+", encoding="utf-8", errors="replace") as log:
        try:
            p = _popen(cmd, stdout=subprocess.DEVNULL, stderr=log, stdin=subprocess.DEVNULL, cwd=cwd)
        except OSError as e:
            return -1, "invalid gpu device: {}".format(e)  # not retryable
        try:
            while True:
                try:
                    p.wait(timeout=0.7)
                    break
                except subprocess.TimeoutExpired:
                    if CANCEL.is_set():
                        p.kill()
                        p.wait()
                        raise UserError("err_cancel")
                    if on_poll:
                        on_poll()
        finally:
            _release(p)
        log.seek(0)
        return p.returncode, log.read()


def _drop_finished(in_dir, out_dir, fmt):
    """Resume support: forget frames that already have an output (re-do the last two to be safe)."""
    outs = sorted((p for p in Path(out_dir).iterdir()), key=lambda p: p.stat().st_mtime)
    for p in outs[-2:]:
        try:
            p.unlink()
        except OSError:
            pass
    for f in list(Path(in_dir).iterdir()):
        if (Path(out_dir) / (f.stem + "." + fmt)).exists():
            f.unlink()


def run_esrgan(src_in, dst_out, model, scale, fmt, gpu="light", on_poll=None):
    """Run Real-ESRGAN with automatic retries (smaller tiles) if the GPU/driver gives up."""
    d = esrgan_dir()
    if d is None:
        raise UserError("err_esrgan_missing")
    stem = "{}-x{}".format(model, scale) if model == "realesr-animevideov3" else model
    for ext in ("param", "bin"):
        if not (d / "models" / "{}.{}".format(stem, ext)).is_file():
            raise UserError("err_model_missing", model=stem)
    is_dir = Path(src_in).is_dir()
    last = ""
    for i, (tile, jobs) in enumerate(GPU_ATTEMPTS.get(gpu, GPU_ATTEMPTS["light"])):
        check_cancel()
        if i > 0:
            if is_dir:
                _drop_finished(src_in, dst_out, fmt)
                if not any(Path(src_in).iterdir()):
                    return
            for _ in range(6):  # let the display driver recover
                check_cancel()
                time.sleep(0.5)
        cmd = [str(d / ESRGAN_BIN), "-i", str(src_in), "-o", str(dst_out), "-n", model,
               "-s", str(scale), "-m", str(d / "models"), "-f", fmt,
               "-t", str(tile), "-j", jobs]
        rc, err = _attempt_esrgan(cmd, str(d), on_poll)
        if rc != 0:
            check_cancel()
        if rc == 0:
            if not is_dir and not Path(dst_out).exists():
                raise UserError("err_esrgan_nooutput")
            return
        last = _last_line(err, "Real-ESRGAN failed")
        if any(m in err.lower() for m in NO_RETRY):
            break
    raise UserError("err_esrgan_failed", detail=last)


def upscale_image(src, dst_png, model, scale, gpu="light"):
    with _workdir(Path(dst_png).parent) as td:
        tin = Path(td) / "in.png"
        with Image.open(src) as im:
            im = ImageOps.exif_transpose(im)
            w, h = im.size
            if w * h * scale * scale > MAX_IMAGE_OUT_PIXELS:
                raise UserError("err_too_big", w=w * scale, h=h * scale)
            has_alpha = "A" in im.getbands() or "transparency" in im.info
            im = im.convert("RGBA" if has_alpha else "RGB")
            im.save(str(tin), "PNG")
        run_esrgan(tin, dst_png, model, scale, "png", gpu)


# ---------------------------------------------------------------- ffmpeg
AUDIO_CODECS = {
    "mp3": ["-c:a", "libmp3lame", "-q:a", "2"],
    "wav": ["-c:a", "pcm_s16le"],
    "flac": ["-c:a", "flac"],
    "aac": ["-c:a", "aac", "-b:a", "192k"],
    "m4a": ["-c:a", "aac", "-b:a", "192k"],
    "ogg": ["-c:a", "libvorbis", "-q:a", "5"],
}


def _run_ff(cmd):
    """Run ffmpeg at low priority, killable by Stop / window close."""
    try:
        p = _popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,
                   universal_newlines=True, encoding="utf-8", errors="replace")
    except OSError as e:
        raise UserError("err_ffmpeg_start", detail=str(e))
    try:
        while True:
            try:
                out, err = p.communicate(timeout=0.5)
                break
            except subprocess.TimeoutExpired:
                if CANCEL.is_set():
                    p.kill()
                    p.communicate()
                    raise UserError("err_cancel")
    finally:
        _release(p)
    if p.returncode != 0:
        check_cancel()  # killed by Stop / window close
    return subprocess.CompletedProcess(cmd, p.returncode, out, err)


def _video_enc(fmt, hq=False):
    if fmt == "webm":
        enc = ["-c:v", "libvpx-vp9", "-crf", "26" if hq else "32", "-b:v", "0",
               "-deadline", "realtime", "-cpu-used", "8", "-row-mt", "1", "-c:a", "libopus"]
    else:
        enc = ["-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
               "-c:v", "libx264", "-preset", "fast" if hq else "veryfast",
               "-crf", "18" if hq else "23",
               "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k"]
    if fmt in ("mp4", "mov"):
        enc += ["-movflags", "+faststart"]
    return enc


def _ffmpeg_cmds(exe, src, dst, fmt, fast, mute=False):
    """List of attempts (first = fastest, the rest = fallbacks)."""
    base = [exe, "-y", "-nostdin", "-hide_banner", "-loglevel", "error", "-i", str(src)]

    if fmt in AUDIO_OUT:
        return [base + ["-vn"] + AUDIO_CODECS[fmt] + [str(dst)]]

    if fmt == "gif":
        vf = ("fps=12,scale='min(480,iw)':-1:flags=lanczos,"
              "split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse")
        return [base + ["-vf", vf, "-loop", "0", str(dst)]]

    maps = ["-map", "0:v:0"] if mute else ["-map", "0:v:0", "-map", "0:a:0?"]
    tail = ["-an"] if mute else []
    full = base + maps + tail + _video_enc(fmt) + [str(dst)]

    if fast and ext_of(src) in {"mp4", "mkv", "mov", "m4v"} and fmt in {"mp4", "mkv", "mov"}:
        copy = base + maps + tail + ["-c", "copy"]
        if fmt in ("mp4", "mov"):
            copy += ["-movflags", "+faststart"]
        return [copy + [str(dst)], full]  # if stream copy fails, re-encode
    return [full]


def convert_ffmpeg(src, dst, fmt, fast, mute=False):
    exe = ffmpeg_exe()
    if not exe:
        raise UserError("err_ffmpeg_missing")
    last_err = ""
    with FF_LOCK:
        for cmd in _ffmpeg_cmds(exe, src, dst, fmt, fast, mute):
            check_cancel()
            r = _run_ff(cmd)
            if r.returncode == 0:
                return
            last_err = _last_line(r.stderr, "ffmpeg")
            if dst.exists():
                dst.unlink()
    raise UserError("err_ffmpeg", detail=last_err)


def _probe_video(exe, src):
    """fps / duration (seconds) / width / height from `ffmpeg -i` (best effort)."""
    r = _run_ff([exe, "-hide_banner", "-i", str(src)])  # exits "no output file" but prints stream info
    txt = r.stderr or ""
    m = re.search(r"(\d+(?:\.\d+)?)\s*fps", txt)
    fps = m.group(1) if m else "30"
    dur = None
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", txt)
    if m:
        dur = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    m = re.search(r",\s*(\d{2,5})x(\d{2,5})", txt)
    w, h = (int(m.group(1)), int(m.group(2))) if m else (None, None)
    return fps, dur, w, h


def ai_video(src, dst, fmt, model, req_scale, progress=None, mute=False, gpu="light"):
    """video -> frames -> Real-ESRGAN (in chunks, with retries) -> re-assemble (+ original audio)."""
    say = progress or _noop
    exe = ffmpeg_exe()
    if not exe:
        raise UserError("err_ffmpeg_missing")
    with FF_LOCK, _workdir(Path(dst).parent) as td:
        td = Path(td)
        fin, fout, fchunk = td / "in", td / "out", td / "chunk"
        fin.mkdir()
        fout.mkdir()
        fps, dur, pw, ph = _probe_video(exe, src)

        # early disk check (before the frames are written)
        if dur and pw and ph:
            s0 = min(req_scale, 2)
            frames_est = dur * float(fps)
            need = frames_est * (pw * ph * 0.25 + pw * ph * s0 * s0 * 0.8)
            free = _free(td)
            if free < need:
                raise UserError("err_disk", need="{:.1f}".format(need / 1e9),
                                free="{:.1f}".format(free / 1e9))

        say("p_extract")
        r = _run_ff([exe, "-y", "-nostdin", "-hide_banner", "-loglevel", "error",
                     "-i", str(src), "-map", "0:v:0", "-vf", "fps={}".format(fps),
                     "-q:v", "2", str(fin / "%08d.jpg")])
        if r.returncode != 0:
            raise UserError("err_extract", detail=_last_line(r.stderr, "ffmpeg"))
        names = sorted(p.name for p in fin.iterdir() if p.suffix == ".jpg")
        total = len(names)
        if total == 0:
            raise UserError("err_no_frames")

        with Image.open(str(fin / names[0])) as im0:  # real frame size (handles rotation metadata)
            fw, fh = im0.size
        scale = fit_video_scale(model, fw, fh, req_scale)
        limited = scale < req_scale

        in_bytes = sum((fin / n).stat().st_size for n in names)
        need = in_bytes * scale * scale * 3.0  # q100 output frames are ~3x denser than the q:v 2 inputs
        if _free(td) < need:
            raise UserError("err_disk", need="{:.1f}".format(need / 1e9),
                            free="{:.1f}".format(_free(td) / 1e9))

        t0 = time.time()
        key = "p_upscale_lim" if limited else "p_upscale"

        def poll():
            n = min(total, _count_files(fout))
            el = time.time() - t0
            eta = _fmt_eta((total - n) * el / n) if (n >= 3 and el > 5) else "--"
            say(key, n=n, total=total, scale=scale, eta=eta)

        for i in range(0, total, CHUNK_FRAMES):
            check_cancel()
            if fchunk.exists():
                shutil.rmtree(str(fchunk))
            fchunk.mkdir()
            for n in names[i:i + CHUNK_FRAMES]:
                os.replace(str(fin / n), str(fchunk / n))
            poll()
            run_esrgan(fchunk, fout, model, scale, "jpg", gpu, on_poll=poll)
        poll()
        done = _count_files(fout)
        if done < total:
            raise UserError("err_partial", done=done, total=total)

        check_cancel()
        say("p_assemble")
        head = [exe, "-y", "-nostdin", "-hide_banner", "-loglevel", "error",
                "-framerate", fps, "-i", str(fout / "%08d.jpg")]
        if mute:
            cmd = head + ["-map", "0:v:0", "-an"] + _video_enc(fmt, hq=True) + [str(dst)]
        else:
            cmd = head + ["-i", str(src), "-map", "0:v:0", "-map", "1:a:0?"] + \
                  _video_enc(fmt, hq=True) + ["-shortest", str(dst)]
        r = _run_ff(cmd)
        if r.returncode != 0:
            raise UserError("err_assemble", detail=_last_line(r.stderr, "ffmpeg"))


# ---------------------------------------------------------------- public API
def convert(src, fmt, outdir=None, fast=False, quality=90,
            upscale=None, progress=None, mute=False, gpu="light"):
    """
    upscale : None or {"model": "real"|"anime"|"fast"|None, "scale": 2|3|4|None}
    progress: callable(key, **kw) for status updates (optional)
    mute    : drop the audio track from video outputs
    gpu     : "light" | "balanced" | "max"  (AI upscaling load)
    """
    check_cancel()
    src = Path(src).resolve()
    fmt = fmt.lower().lstrip(".")
    engine = pick_engine(ext_of(src), fmt)
    if engine is None:
        raise UserError("err_unsupported", src=ext_of(src), dst=fmt)
    say = progress or _noop
    if upscale and engine == "ffmpeg" and fmt == "gif":
        raise UserError("err_gif_ai")
    mute = bool(mute) and engine == "ffmpeg" and fmt not in AUDIO_OUT

    outdir = Path(outdir) if outdir else None
    if outdir:
        outdir.mkdir(parents=True, exist_ok=True)
    dst = unique_dst(src, fmt, outdir)
    try:
        if engine == "image":
            if upscale:
                name, scale = _resolve_ai(upscale, "image")
                with _workdir(dst.parent) as td:
                    up = Path(td) / "up.png"
                    say("p_upscale_img")
                    with FF_LOCK:  # one GPU job at a time
                        upscale_image(src, up, name, scale, gpu)
                    say("p_save")
                    convert_image(up, dst, fmt, quality)
            else:
                convert_image(src, dst, fmt, quality)
        elif upscale and fmt in AI_VIDEO_OUT:
            name, scale = _resolve_ai(upscale, "video")
            ai_video(src, dst, fmt, name, scale, progress=say, mute=mute, gpu=gpu)
        else:  # plain video/audio (upscale is ignored for audio targets)
            say("p_convert")
            convert_ffmpeg(src, dst, fmt, fast, mute)
    except BaseException:
        if dst.exists():
            try:
                dst.unlink()
            except OSError:
                pass
        raise
    finally:
        _release_dst(dst)
    return dst


# ---------------------------------------------------------------- GUI
def run_gui(_test=False):
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    set_lang(load_lang())
    threading.Thread(target=sweep_stale_workdirs, daemon=True).start()

    dnd_flag = None
    try:  # drag & drop is optional (pip install tkinterdnd2)
        from tkinterdnd2 import DND_FILES, TkinterDnD
        root = TkinterDnD.Tk()
        dnd_flag = DND_FILES
    except Exception:
        root = tk.Tk()

    root.geometry("900x780")
    root.minsize(780, 640)

    paths = {}
    status_data = {}
    partial = {}
    results = queue.Queue()
    state = {"total": 0, "done": 0, "running": False, "kinds": None, "model_key": None}
    texts = []  # (widget, option, key) for live language switching

    def bind(widget, key, option="text"):
        texts.append((widget, option, key))
        widget.configure(**{option: tr(key)})
        return widget

    fmt_var = tk.StringVar(value="jpg")
    fast_var = tk.BooleanVar(value=True)
    quality_var = tk.IntVar(value=90)
    outdir_var = tk.StringVar(value="")
    ai_var = tk.BooleanVar(value=False)
    ai_scale_var = tk.StringVar(value="4")
    ai_note_var = tk.StringVar(value="")

    # ---- file list
    frame = ttk.Frame(root, padding=8)
    frame.pack(fill="both", expand=True)
    tree = ttk.Treeview(frame, columns=("file", "status"), show="headings", selectmode="extended")
    tree.column("file", width=420)
    tree.column("status", width=380)
    sb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=sb.set)
    tree.pack(side="left", fill="both", expand=True)
    sb.pack(side="left", fill="y")

    bar = ttk.Frame(root, padding=(8, 0))
    bar.pack(fill="x")
    opts = ttk.Frame(root, padding=8)
    opts.pack(fill="x")
    opts.columnconfigure(5, weight=1)

    bind(ttk.Label(opts), "convert_to").grid(row=0, column=0, sticky="w")
    fmt_cb = ttk.Combobox(opts, textvariable=fmt_var, values=ALL_OUT, width=8, state="readonly")
    fmt_cb.grid(row=0, column=1, padx=6)

    q_lbl = bind(ttk.Label(opts), "save_quality")
    q_spin = ttk.Spinbox(opts, from_=1, to=100, textvariable=quality_var, width=5)
    q_lbl.grid(row=0, column=2, padx=(16, 0))
    q_spin.grid(row=0, column=3, padx=6)

    fast_chk = bind(ttk.Checkbutton(opts, variable=fast_var), "fast_copy")
    fast_chk.grid(row=0, column=4, padx=12)

    audio_lbl = bind(ttk.Label(opts), "audio")
    audio_cb = ttk.Combobox(opts, state="readonly", width=26)
    audio_lbl.grid(row=1, column=0, sticky="w", pady=(6, 0))
    audio_cb.grid(row=1, column=1, columnspan=3, sticky="w", padx=6, pady=(6, 0))

    # ---- AI upscaling group
    ai_frame = bind(ttk.LabelFrame(opts, padding=6), "ai_group")
    ai_frame.grid(row=2, column=0, columnspan=6, sticky="we", pady=(10, 4))
    ai_frame.columnconfigure(5, weight=1)
    bind(ttk.Checkbutton(ai_frame, variable=ai_var), "ai_enable").grid(row=0, column=0, padx=4, sticky="w")
    bind(ttk.Label(ai_frame), "ai_type").grid(row=0, column=1, padx=(10, 2))
    ai_model_cb = ttk.Combobox(ai_frame, state="readonly", width=32)
    ai_model_cb.grid(row=0, column=2, padx=4)
    bind(ttk.Label(ai_frame), "ai_scale").grid(row=0, column=3, padx=(10, 2))
    ai_scale_cb = ttk.Combobox(ai_frame, textvariable=ai_scale_var, state="readonly",
                               width=4, values=["2", "3", "4"])
    ai_scale_cb.grid(row=0, column=4, padx=4)
    bind(ttk.Label(ai_frame), "gpu").grid(row=1, column=1, padx=(10, 2), pady=(6, 0), sticky="e")
    gpu_cb = ttk.Combobox(ai_frame, state="readonly", width=44)
    gpu_cb.grid(row=1, column=2, columnspan=3, padx=4, pady=(6, 0), sticky="w")
    note_lbl = ttk.Label(ai_frame, textvariable=ai_note_var, foreground="gray")
    note_lbl.grid(row=2, column=0, columnspan=6, sticky="we", pady=(8, 0))
    ai_frame.bind("<Configure>", lambda e: note_lbl.configure(wraplength=max(200, e.width - 40)))

    bind(ttk.Button(opts, command=lambda: outdir_var.set(
        filedialog.askdirectory(title=tr("outdir_dialog")) or "")), "outdir_btn"
         ).grid(row=3, column=0, pady=6, sticky="w")
    ttk.Label(opts, textvariable=outdir_var, foreground="gray").grid(row=3, column=1, columnspan=5, sticky="w")
    bind(ttk.Label(opts, foreground="gray"), "outdir_hint").grid(row=4, column=0, columnspan=6, sticky="w")

    progress = ttk.Progressbar(root, mode="determinate")
    progress.pack(fill="x", padx=8, pady=(4, 0))

    bottom = ttk.Frame(root)
    bottom.pack(pady=8)
    start_btn = ttk.Button(bottom)
    start_btn.pack(side="left")
    ttk.Label(bottom, text="by R3D", foreground="#666666").pack(side="left", padx=(12, 0))

    # ---- helpers
    def toggle(widgets, show):
        for w in widgets:
            if show:
                w.grid()
            else:
                w.grid_remove()

    def audio_mode():
        i = audio_cb.current()
        return AUDIO_MODES[i if i >= 0 else 0]

    def ai_key():
        i = ai_model_cb.current()
        return AI_KEYS[i if i >= 0 else 0]

    def gpu_key():
        i = gpu_cb.current()
        return GPU_KEYS[i if i >= 0 else 0]

    def render_status(key, kw):
        if key == "s_fail":
            return tr("s_fail", msg=err_text(kw["err"])[:160])
        return tr(key, **kw)

    def set_status(iid, key, **kw):
        status_data[iid] = (key, kw)
        if tree.exists(iid):
            tree.set(iid, "status", render_status(key, kw))

    def update_start_btn():
        if state["running"]:
            start_btn.configure(text=tr("stop"), command=on_stop)
        else:
            start_btn.configure(text=tr("start"), command=on_start)

    def on_model(*_):
        key = ai_key()
        if key == state["model_key"]:
            return
        state["model_key"] = key
        if key == "fast":
            ai_scale_cb.configure(state="readonly")
            ai_scale_var.set("2")
        else:
            ai_scale_var.set("4")
            ai_scale_cb.configure(state="disabled")  # these models only exist at x4

    def refresh(*_):
        """Read the file types and show only the relevant options."""
        files = list(paths.values())
        kinds = {kind_of_ext(ext_of(p)) for p in files} - {None}
        has_img, has_vid = "image" in kinds, "video" in kinds
        empty = not kinds
        mode = audio_mode()
        audio_only = has_vid and mode == "only"

        toggle([audio_lbl, audio_cb], has_vid)
        toggle([fast_chk], has_vid and not audio_only)
        toggle([q_lbl, q_spin], has_img or empty)

        values = targets_for_files(files, audio_only)
        fmt_cb["values"] = values
        if fmt_var.get() not in values:
            pref = {"image": "jpg", "video": "mp4", "audio": "mp3"}
            first = next(iter(sorted(kinds)), None)
            fmt_var.set(pref.get(first) if pref.get(first) in values else values[0])

        toggle([ai_frame], empty or has_img or (has_vid and not audio_only))

        # default model follows the file type (only when the type set changes)
        if state["kinds"] != kinds:
            state["kinds"] = kinds
            if has_vid and not has_img:
                ai_model_cb.current(AI_KEYS.index("fast"))
            elif has_img:
                ai_model_cb.current(AI_KEYS.index("real"))
        on_model()

        lines = [tr("ai_note")]
        if has_vid:
            lines.append(tr("ai_note_video"))
        if has_vid and fmt_var.get() == "gif":
            lines.append(tr("ai_note_gif"))
        if esrgan_dir() is None:
            lines.append(tr("ai_note_dl"))
        ai_note_var.set("\n".join(lines))

    def apply_lang():
        root.title(tr("title"))
        for w, opt, key in texts:
            w.configure(**{opt: tr(key)})
        tree.heading("file", text=tr("col_file"))
        tree.heading("status", text=tr("col_status"))
        i = audio_cb.current()
        audio_cb["values"] = [tr("audio_keep"), tr("audio_mute"), tr("audio_only")]
        audio_cb.current(i if i >= 0 else 0)
        i = ai_model_cb.current()
        ai_model_cb["values"] = [tr("ai_" + k) for k in AI_KEYS]
        ai_model_cb.current(i if i >= 0 else 0)
        i = gpu_cb.current()
        gpu_cb["values"] = [tr("gpu_" + k) for k in GPU_KEYS]
        gpu_cb.current(i if i >= 0 else 0)
        hint_lbl.configure(text=tr("drop_hint") if dnd_flag else tr("nodnd_hint"))
        rtl = get_lang() == "ar"
        note_lbl.configure(anchor="e" if rtl else "w", justify="right" if rtl else "left")
        for iid, (key, kw) in status_data.items():
            if tree.exists(iid):
                tree.set(iid, "status", render_status(key, kw))
        update_start_btn()
        refresh()

    def add_files(files):
        for f in files:
            p = Path(f)
            if p.is_dir():
                add_files([str(x) for x in p.iterdir() if x.is_file()])
                continue
            if not p.is_file() or p in paths.values():
                continue
            iid = tree.insert("", "end", values=(str(p), ""))
            paths[iid] = p
            set_status(iid, "s_wait")
        refresh()

    def on_clear():
        if state["running"]:
            return
        tree.delete(*tree.get_children())
        paths.clear()
        status_data.clear()
        partial.clear()
        progress["value"] = 0
        refresh()

    def on_remove():
        if state["running"]:
            return
        for iid in tree.selection():
            tree.delete(iid)
            paths.pop(iid, None)
            status_data.pop(iid, None)
        refresh()

    bind(ttk.Button(bar, command=lambda: add_files(
        filedialog.askopenfilenames(title=tr("pick_files")))), "add_files").pack(side="left", padx=2)
    bind(ttk.Button(bar, command=on_remove), "remove_sel").pack(side="left", padx=2)
    bind(ttk.Button(bar, command=on_clear), "clear_all").pack(side="left", padx=2)

    lang_names = ["العربية", "English"]
    lang_codes = ["ar", "en"]
    lang_cb = ttk.Combobox(bar, values=lang_names, state="readonly", width=9)
    lang_cb.current(lang_codes.index(get_lang()))
    lang_cb.pack(side="right", padx=(2, 0))
    bind(ttk.Label(bar), "language").pack(side="right", padx=(10, 2))
    hint_lbl = ttk.Label(bar, foreground="gray")
    hint_lbl.pack(side="right", padx=6)

    def set_language(code):
        set_lang(code)
        save_lang(code)
        lang_cb.current(lang_codes.index(code))
        apply_lang()

    lang_cb.bind("<<ComboboxSelected>>", lambda e: set_language(lang_codes[lang_cb.current()]))

    if dnd_flag:
        tree.drop_target_register(dnd_flag)
        tree.dnd_bind("<<Drop>>", lambda e: add_files(root.tk.splitlist(e.data)))

    audio_cb.bind("<<ComboboxSelected>>", refresh)
    ai_model_cb.bind("<<ComboboxSelected>>", on_model)
    fmt_var.trace_add("write", lambda *_: refresh() if not state["running"] else None)

    def poll():
        try:
            while True:
                iid, key, kw, final = results.get_nowait()
                set_status(iid, key, **kw)
                if final:
                    partial.pop(iid, None)
                    state["done"] += 1
                elif "n" in kw and kw.get("total"):
                    partial[iid] = kw["n"] / kw["total"]
                elif "done" in kw and kw.get("total"):
                    partial[iid] = kw["done"] / kw["total"]
                elif key == "p_assemble":
                    partial[iid] = 0.98
                else:
                    partial[iid] = 0
                progress["value"] = 100 * (state["done"] + sum(partial.values())) / max(1, state["total"])
        except queue.Empty:
            pass
        if state["running"] and state["done"] >= state["total"]:
            state["running"] = False
            update_start_btn()
        root.after(100, poll)

    def fail_result(e):
        if isinstance(e, UserError) and e.key == "err_cancel":
            return "s_cancel", {}
        return "s_fail", {"err": e}

    def on_stop():
        CANCEL.set()
        kill_active()

    def on_start():
        if state["running"] or not paths:
            return
        fmt = fmt_var.get()
        outdir = outdir_var.get() or None
        fast = fast_var.get()
        mute = audio_mode() == "mute"
        gpu = gpu_key()
        try:
            quality = max(1, min(100, int(quality_var.get())))
        except Exception:
            quality = 90
        upscale = None
        if ai_var.get():
            upscale = {"model": ai_key(), "scale": int(ai_scale_var.get())}
            if esrgan_dir() is None and not messagebox.askyesno(
                    tr("dl_title"), tr("dl_ask", size=AI_PACK_SIZE // 10 ** 6)):
                return

        CANCEL.clear()
        items = list(paths.items())
        partial.clear()
        state.update(total=len(items), done=0, running=True)
        progress["value"] = 0
        update_start_btn()
        for iid, _ in items:
            set_status(iid, "s_queue")

        def job(iid, p):
            try:
                dst = convert(p, fmt, outdir, fast, quality, upscale,
                              progress=lambda key, **kw: results.put((iid, key, kw, False)),
                              mute=mute, gpu=gpu)
                results.put((iid, "s_done", {"name": dst.name}, True))
            except BaseException as e:
                k, kw = fail_result(e)
                results.put((iid, k, kw, True))

        def runner():
            if upscale and esrgan_dir() is None:
                try:
                    install_ai_pack(lambda key, **kw: [results.put((i, key, kw, False)) for i, _ in items])
                except BaseException as e:
                    k, kw = fail_result(e)
                    for i, _ in items:
                        results.put((i, k, kw, True))
                    return
            with ThreadPoolExecutor(max_workers=max(2, (os.cpu_count() or 4))) as pool:
                for iid, p in items:
                    pool.submit(job, iid, p)

        threading.Thread(target=runner, daemon=True).start()

    def on_close():
        if state["running"]:
            CANCEL.set()
            kill_active()
            t0 = time.time()
            while state["running"] and time.time() - t0 < 4:  # let workers clean their temp folders
                root.update()
                time.sleep(0.05)
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    audio_cb["values"] = [tr("audio_keep"), tr("audio_mute"), tr("audio_only")]
    audio_cb.current(0)
    ai_model_cb["values"] = [tr("ai_" + k) for k in AI_KEYS]
    ai_model_cb.current(0)
    gpu_cb["values"] = [tr("gpu_" + k) for k in GPU_KEYS]
    gpu_cb.current(0)
    apply_lang()
    poll()
    if _test:
        return {"root": root, "add_files": add_files, "refresh": refresh, "fmt_cb": fmt_cb,
                "fmt_var": fmt_var, "ai_frame": ai_frame, "fast_chk": fast_chk,
                "audio_cb": audio_cb, "audio_lbl": audio_lbl, "q_spin": q_spin,
                "ai_model_cb": ai_model_cb, "ai_scale_var": ai_scale_var,
                "ai_scale_cb": ai_scale_cb, "ai_var": ai_var, "on_start": on_start,
                "on_stop": on_stop, "gpu_cb": gpu_cb, "note_lbl": note_lbl, "ai_note_var": ai_note_var,
                "tree": tree, "state": state, "on_clear": on_clear, "start_btn": start_btn,
                "set_language": set_language, "on_model": on_model, "texts": texts,
                "hint_lbl": hint_lbl, "bottom": bottom, "progress": progress, "on_close": on_close}
    root.mainloop()


# ---------------------------------------------------------------- CLI
def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--lang", choices=["ar", "en"])
    known, _ = pre.parse_known_args(argv)
    set_lang(known.lang or load_lang())

    ap = argparse.ArgumentParser(description=tr("cli_desc"))
    ap.add_argument("files", nargs="*", help=tr("cli_files"))
    ap.add_argument("-t", "--to", help=tr("cli_to"))
    ap.add_argument("-o", "--outdir", help=tr("cli_outdir"))
    ap.add_argument("-q", "--quality", type=int, default=90, help=tr("cli_quality"))
    ap.add_argument("--fast", action="store_true", help=tr("cli_fast"))
    ap.add_argument("--mute", action="store_true", help=tr("cli_mute"))
    ap.add_argument("--upscale", type=int, choices=[2, 3, 4], help=tr("cli_upscale"))
    ap.add_argument("--model", choices=list(AI_MODELS), help=tr("cli_model"))
    ap.add_argument("--gpu", choices=GPU_KEYS, default="light", help=tr("cli_gpu"))
    ap.add_argument("--install-ai", action="store_true", help=tr("cli_install_ai"))
    ap.add_argument("--lang", choices=["ar", "en"], help=tr("cli_lang"))
    ap.add_argument("--version", action="version", version="Seegha {}".format(__version__))
    args = ap.parse_args(argv)

    def dl_progress(key, **kw):
        if time.time() - dl_progress.last > 2:
            dl_progress.last = time.time()
            print("[...]  {}".format(tr(key, **kw)), flush=True)
    dl_progress.last = 0.0

    if args.install_ai:
        try:
            path = install_ai_pack(dl_progress)
        except Exception as e:
            print("[FAIL] {}".format(err_text(e)), flush=True)
            return 1
        print(tr("cli_ai_installed", path=path))
        return 0

    if not args.files:
        return run_gui()
    if not args.to:
        ap.error(tr("cli_need_fmt"))

    files = []
    for pattern in args.files:
        matches = glob.glob(pattern)
        files.extend(matches if matches else [pattern])

    upscale = {"model": args.model, "scale": args.upscale} if (args.upscale or args.model) else None
    if upscale and esrgan_dir() is None:  # asking for --upscale is consent to the one-time download
        try:
            install_ai_pack(dl_progress)
        except Exception as e:
            print("[FAIL] {}".format(err_text(e)), flush=True)
            return 1

    def job(f):
        last = [0.0]

        def prog(key, **kw):
            if key in ("p_convert", "p_save"):
                return
            if time.time() - last[0] > 3:
                last[0] = time.time()
                print("[...]  {}: {}".format(f, tr(key, **kw)), flush=True)
        try:
            dst = convert(f, args.to, args.outdir, args.fast, args.quality, upscale, prog,
                          args.mute, args.gpu)
            print("[OK]   {} -> {}".format(f, dst), flush=True)
            return True
        except Exception as e:
            print("[FAIL] {}: {}".format(f, err_text(e)), flush=True)
            return False

    try:
        with ThreadPoolExecutor(max_workers=max(2, (os.cpu_count() or 4))) as pool:
            ok = sum(pool.map(job, files))
    except KeyboardInterrupt:
        CANCEL.set()
        kill_active()
        return 130
    print("\n" + tr("cli_done", ok=ok, total=len(files)))
    return 0 if ok == len(files) else 1


if __name__ == "__main__":
    sys.exit(main())
