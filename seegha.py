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
import json
import locale
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

__version__ = "1.0.0"
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
ESRGAN_BIN = "realesrgan-ncnn-vulkan" + (".exe" if os.name == "nt" else "")
# One heavy job at a time (ffmpeg + GPU). RLock: the AI video pipeline calls ffmpeg from inside.
FF_LOCK = threading.RLock()

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
        "ai_note": "يحتاج كرت شاشة يدعم Vulkan (NVIDIA / AMD / Intel).",
        "ai_note_video": " تنبيه: رفع جودة الفيديو بطيء جداً (كل إطار يمر على النموذج) ويحتاج مساحة فاضية كبيرة على القرص.",
        "ai_note_gif": " الإخراج gif لا يدعم رفع الجودة.",
        "outdir_btn": "مجلد الإخراج", "outdir_dialog": "مجلد الإخراج",
        "outdir_hint": "(إذا تركته فاضي يحفظ جنب الملف الأصلي)",
        "pick_files": "اختر الملفات", "start": "ابدأ التحويل",
        "s_wait": "بانتظار التحويل", "s_queue": "بانتظار الدور...",
        "s_done": "تم ✔ {name}", "s_fail": "فشل ✘ {msg}",
        "p_convert": "جاري التحويل...", "p_save": "جاري الحفظ...",
        "p_upscale_img": "رفع الجودة...", "p_extract": "استخراج الإطارات...",
        "p_upscale": "رفع الجودة {n}/{total}", "p_assemble": "تجميع الفيديو...",
        "err_unsupported": "لا يمكن تحويل .{src} إلى {dst}",
        "err_gif_ai": "رفع الجودة ما يدعم الإخراج gif. اختر mp4 أو mkv أو webm",
        "err_ffmpeg_missing": "ffmpeg غير موجود. ثبّته بالأمر: winget install Gyan.FFmpeg",
        "err_esrgan_missing": "مجلد realesrgan (مع models) غير موجود. نسخة exe الجاهزة تحتويه.",
        "err_esrgan_failed": "{detail} (يحتاج كرت شاشة يدعم Vulkan وتعريف حديث)",
        "err_esrgan_nooutput": "Real-ESRGAN ما أنتج ملف",
        "err_unknown_model": "نموذج غير معروف: {key}",
        "err_too_big": "الناتج كبير جداً ({w}x{h}). استخدم صورة أصغر أو مضاعفة أقل",
        "err_no_frames": "ما لقيت إطارات في الفيديو",
        "err_disk": "المساحة الفاضية ما تكفي (محتاج تقريباً {need} جيجا، المتوفر {free})",
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
        "ai_note": "Needs a Vulkan-capable GPU (NVIDIA / AMD / Intel).",
        "ai_note_video": " Note: video upscaling is very slow (every frame goes through the model) and needs a lot of free disk space.",
        "ai_note_gif": " gif output does not support upscaling.",
        "outdir_btn": "Output folder", "outdir_dialog": "Output folder",
        "outdir_hint": "(leave empty to save next to the original file)",
        "pick_files": "Choose files", "start": "Start conversion",
        "s_wait": "Waiting", "s_queue": "Queued...",
        "s_done": "Done ✔ {name}", "s_fail": "Failed ✘ {msg}",
        "p_convert": "Converting...", "p_save": "Saving...",
        "p_upscale_img": "Upscaling...", "p_extract": "Extracting frames...",
        "p_upscale": "Upscaling {n}/{total}", "p_assemble": "Assembling video...",
        "err_unsupported": "Cannot convert .{src} to {dst}",
        "err_gif_ai": "Upscaling does not support gif output. Choose mp4, mkv or webm",
        "err_ffmpeg_missing": "ffmpeg not found. Install it with: winget install Gyan.FFmpeg",
        "err_esrgan_missing": "The realesrgan folder (with models) is missing. The ready-made exe includes it.",
        "err_esrgan_failed": "{detail} (needs a Vulkan-capable GPU and an up-to-date driver)",
        "err_esrgan_nooutput": "Real-ESRGAN produced no output",
        "err_unknown_model": "Unknown model: {key}",
        "err_too_big": "Output too large ({w}x{h}). Use a smaller image or a lower scale",
        "err_no_frames": "No frames found in the video",
        "err_disk": "Not enough free disk space (need about {need} GB, available {free})",
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
    base = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), ".config")
    return Path(base) / "Seegha" / "config.json"


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


def _bundle_dirs():
    if getattr(sys, "frozen", False):
        return [Path(getattr(sys, "_MEIPASS", "")), Path(sys.executable).parent]
    return [Path(__file__).resolve().parent]


def ffmpeg_exe():
    """ffmpeg inside the exe, next to the script, or on PATH."""
    for d in _bundle_dirs():
        c = d / "ffmpeg.exe"
        if c.is_file():
            return str(c)
    return shutil.which("ffmpeg")


def esrgan_dir():
    for d in _bundle_dirs():
        c = d / "realesrgan"
        if (c / ESRGAN_BIN).is_file() and (c / "models").is_dir():
            return c
    return None


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


def unique_dst(src, fmt, outdir):
    ext = "jpg" if fmt == "jpeg" else fmt
    folder = outdir or src.parent
    dst = folder / "{}.{}".format(src.stem, ext)
    n = 1
    while dst.exists() or dst.resolve() == src.resolve():
        tag = "_converted" if n == 1 else "_converted{}".format(n)
        dst = folder / "{}{}.{}".format(src.stem, tag, ext)
        n += 1
    return dst


def _last_line(text, default):
    lines = [l for l in (text or "").strip().splitlines() if l.strip()]
    return lines[-1] if lines else default


def _noop(key, **kw):
    pass


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


def run_esrgan(src_in, dst_out, model, scale, fmt, progress=None, total=1):
    d = esrgan_dir()
    if d is None:
        raise UserError("err_esrgan_missing")
    cmd = [str(d / ESRGAN_BIN), "-i", str(src_in), "-o", str(dst_out),
           "-n", model, "-s", str(scale), "-m", str(d / "models"), "-f", fmt]
    # stderr goes to a temp file: an unread PIPE can block the tool on long videos
    with tempfile.TemporaryFile("w+", encoding="utf-8", errors="replace") as log:
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=log,
                                stdin=subprocess.DEVNULL, cwd=str(d),
                                creationflags=NO_WINDOW)
        while True:
            try:
                proc.wait(timeout=0.7)
                break
            except subprocess.TimeoutExpired:
                if progress and Path(dst_out).is_dir():
                    n = sum(1 for _ in os.scandir(str(dst_out)))
                    progress("p_upscale", n=min(n, total), total=total)
        log.seek(0)
        err = log.read()
    if proc.returncode != 0:
        raise UserError("err_esrgan_failed", detail=_last_line(err, "Real-ESRGAN failed"))
    if not Path(dst_out).exists():
        raise UserError("err_esrgan_nooutput")


def upscale_image(src, dst_png, model, scale):
    with tempfile.TemporaryDirectory(prefix="fc_") as td:
        tin = Path(td) / "in.png"
        with Image.open(src) as im:
            im = ImageOps.exif_transpose(im)
            w, h = im.size
            if w * h * scale * scale > 150_000_000:
                raise UserError("err_too_big", w=w * scale, h=h * scale)
            has_alpha = "A" in im.getbands() or "transparency" in im.info
            im = im.convert("RGBA" if has_alpha else "RGB")
            im.save(str(tin), "PNG")
        run_esrgan(tin, dst_png, model, scale, "png")


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
    return subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace",
                          stdin=subprocess.DEVNULL,  # required for --windowed apps
                          creationflags=NO_WINDOW)


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
            r = _run_ff(cmd)
            if r.returncode == 0:
                return
            last_err = _last_line(r.stderr, "ffmpeg")
            if dst.exists():
                dst.unlink()
    raise UserError("err_ffmpeg", detail=last_err)


def _probe_fps(exe, src):
    r = _run_ff([exe, "-hide_banner", "-i", str(src)])  # exits with "no output file" but prints stream info
    m = re.search(r"(\d+(?:\.\d+)?)\s*fps", r.stderr or "")
    return m.group(1) if m else "30"


def ai_video(src, dst, fmt, model, scale, progress=None, mute=False):
    """video -> frames -> Real-ESRGAN -> re-assemble with the original audio (unless muted)."""
    say = progress or _noop
    exe = ffmpeg_exe()
    if not exe:
        raise UserError("err_ffmpeg_missing")
    with FF_LOCK, tempfile.TemporaryDirectory(prefix="fc_") as td:
        fin, fout = Path(td) / "in", Path(td) / "out"
        fin.mkdir()
        fout.mkdir()
        fps = _probe_fps(exe, src)

        say("p_extract")
        r = _run_ff([exe, "-y", "-nostdin", "-hide_banner", "-loglevel", "error",
                     "-i", str(src), "-map", "0:v:0", "-vf", "fps={}".format(fps),
                     "-q:v", "2", str(fin / "%08d.jpg")])
        if r.returncode != 0:
            raise UserError("err_extract", detail=_last_line(r.stderr, "ffmpeg"))
        frames = [p for p in fin.iterdir() if p.suffix == ".jpg"]
        total = len(frames)
        if total == 0:
            raise UserError("err_no_frames")

        # disk-space guard: output frames are about scale^2 bigger
        est = sum(p.stat().st_size for p in frames) * scale * scale * 1.3
        free = shutil.disk_usage(td).free
        if free < est:
            raise UserError("err_disk", need="{:.1f}".format(est / 1e9),
                            free="{:.1f}".format(free / 1e9))

        run_esrgan(fin, fout, model, scale, "jpg", progress=say, total=total)
        done = sum(1 for _ in fout.iterdir())
        if done < total:
            raise UserError("err_partial", done=done, total=total)

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
            upscale=None, progress=None, mute=False):
    """
    upscale : None or {"model": "real"|"anime"|"fast"|None, "scale": 2|3|4|None}
    progress: callable(key, **kw) for status updates (optional)
    mute    : drop the audio track from video outputs
    """
    src = Path(src)
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
                with tempfile.TemporaryDirectory(prefix="fc_") as td:
                    up = Path(td) / "up.png"
                    say("p_upscale_img")
                    with FF_LOCK:  # one GPU job at a time
                        upscale_image(src, up, name, scale)
                    say("p_save")
                    convert_image(up, dst, fmt, quality)
            else:
                convert_image(src, dst, fmt, quality)
        elif upscale and fmt in AI_VIDEO_OUT:
            name, scale = _resolve_ai(upscale, "video")
            ai_video(src, dst, fmt, name, scale, progress=say, mute=mute)
        else:  # plain video/audio (upscale is ignored for audio targets)
            say("p_convert")
            convert_ffmpeg(src, dst, fmt, fast, mute)
    except Exception:
        if dst.exists():
            dst.unlink()
        raise
    return dst


# ---------------------------------------------------------------- GUI
def run_gui(_test=False):
    import tkinter as tk
    from tkinter import filedialog, ttk

    set_lang(load_lang())

    dnd_flag = None
    try:  # drag & drop is optional (pip install tkinterdnd2)
        from tkinterdnd2 import DND_FILES, TkinterDnD
        root = TkinterDnD.Tk()
        dnd_flag = DND_FILES
    except Exception:
        root = tk.Tk()

    root.geometry("860x720")
    root.minsize(740, 600)

    paths = {}
    status_data = {}
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
    tree.column("file", width=450)
    tree.column("status", width=300)
    sb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=sb.set)
    tree.pack(side="left", fill="both", expand=True)
    sb.pack(side="left", fill="y")

    # ---- button bar
    bar = ttk.Frame(root, padding=(8, 0))
    bar.pack(fill="x")

    # ---- options
    opts = ttk.Frame(root, padding=8)
    opts.pack(fill="x")

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

    ai_frame = bind(ttk.LabelFrame(opts, padding=6), "ai_group")
    ai_frame.grid(row=2, column=0, columnspan=6, sticky="we", pady=(10, 4))
    bind(ttk.Checkbutton(ai_frame, variable=ai_var), "ai_enable").grid(row=0, column=0, padx=4)
    bind(ttk.Label(ai_frame), "ai_type").grid(row=0, column=1, padx=(10, 2))
    ai_model_cb = ttk.Combobox(ai_frame, state="readonly", width=30)
    ai_model_cb.grid(row=0, column=2, padx=4)
    bind(ttk.Label(ai_frame), "ai_scale").grid(row=0, column=3, padx=(10, 2))
    ai_scale_cb = ttk.Combobox(ai_frame, textvariable=ai_scale_var, state="readonly",
                               width=4, values=["2", "3", "4"])
    ai_scale_cb.grid(row=0, column=4, padx=4)
    ttk.Label(ai_frame, textvariable=ai_note_var, foreground="gray",
              wraplength=790, justify="left").grid(row=1, column=0, columnspan=5, sticky="w", pady=(6, 0))

    bind(ttk.Button(opts, command=lambda: outdir_var.set(
        filedialog.askdirectory(title=tr("outdir_dialog")) or "")), "outdir_btn"
         ).grid(row=3, column=0, pady=6, sticky="w")
    ttk.Label(opts, textvariable=outdir_var, foreground="gray").grid(row=3, column=1, columnspan=5, sticky="w")
    bind(ttk.Label(opts, foreground="gray"), "outdir_hint").grid(row=4, column=0, columnspan=6, sticky="w")

    progress = ttk.Progressbar(root, mode="determinate")
    progress.pack(fill="x", padx=8, pady=(4, 0))

    bottom = ttk.Frame(root)
    bottom.pack(pady=8)
    start_btn = bind(ttk.Button(bottom), "start")
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

    def render_status(key, kw):
        if key == "s_fail":
            return tr("s_fail", msg=err_text(kw["err"])[:140])
        return tr(key, **kw)

    def set_status(iid, key, **kw):
        status_data[iid] = (key, kw)
        if tree.exists(iid):
            tree.set(iid, "status", render_status(key, kw))

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

        note = tr("ai_note")
        if has_vid:
            note += tr("ai_note_video")
        if has_vid and fmt_var.get() == "gif":
            note += tr("ai_note_gif")
        ai_note_var.set(note)

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
        hint_lbl.configure(text=tr("drop_hint") if dnd_flag else tr("nodnd_hint"))
        for iid, (key, kw) in status_data.items():
            if tree.exists(iid):
                tree.set(iid, "status", render_status(key, kw))
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

    # language switch (top-right of the bar)
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
                    state["done"] += 1
                    progress["value"] = 100 * state["done"] / max(1, state["total"])
        except queue.Empty:
            pass
        if state["running"] and state["done"] >= state["total"]:
            state["running"] = False
            start_btn.state(["!disabled"])
        root.after(100, poll)

    def on_start():
        if state["running"] or not paths:
            return
        fmt = fmt_var.get()
        outdir = outdir_var.get() or None
        fast = fast_var.get()
        mute = audio_mode() == "mute"
        try:
            quality = max(1, min(100, int(quality_var.get())))
        except Exception:
            quality = 90
        upscale = None
        if ai_var.get():
            upscale = {"model": ai_key(), "scale": int(ai_scale_var.get())}

        items = list(paths.items())
        state.update(total=len(items), done=0, running=True)
        progress["value"] = 0
        start_btn.state(["disabled"])
        for iid, _ in items:
            set_status(iid, "s_queue")

        def job(iid, p):
            try:
                dst = convert(p, fmt, outdir, fast, quality, upscale,
                              progress=lambda key, **kw: results.put((iid, key, kw, False)),
                              mute=mute)
                results.put((iid, "s_done", {"name": dst.name}, True))
            except Exception as e:
                results.put((iid, "s_fail", {"err": e}, True))

        def runner():
            with ThreadPoolExecutor(max_workers=max(2, (os.cpu_count() or 4))) as pool:
                for iid, p in items:
                    pool.submit(job, iid, p)

        threading.Thread(target=runner, daemon=True).start()

    start_btn.configure(command=on_start)
    audio_cb["values"] = [tr("audio_keep"), tr("audio_mute"), tr("audio_only")]
    audio_cb.current(0)
    ai_model_cb["values"] = [tr("ai_" + k) for k in AI_KEYS]
    ai_model_cb.current(0)
    apply_lang()
    poll()
    if _test:
        return {"root": root, "add_files": add_files, "refresh": refresh, "fmt_cb": fmt_cb,
                "fmt_var": fmt_var, "ai_frame": ai_frame, "fast_chk": fast_chk,
                "audio_cb": audio_cb, "audio_lbl": audio_lbl, "q_spin": q_spin,
                "ai_model_cb": ai_model_cb, "ai_scale_var": ai_scale_var,
                "ai_scale_cb": ai_scale_cb, "ai_var": ai_var, "on_start": on_start,
                "tree": tree, "state": state, "on_clear": on_clear, "start_btn": start_btn,
                "set_language": set_language, "on_model": on_model, "texts": texts,
                "hint_lbl": hint_lbl, "bottom": bottom}
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
    ap.add_argument("--lang", choices=["ar", "en"], help=tr("cli_lang"))
    ap.add_argument("--version", action="version", version="Seegha {}".format(__version__))
    args = ap.parse_args(argv)

    if not args.files:
        return run_gui()
    if not args.to:
        ap.error(tr("cli_need_fmt"))

    files = []
    for pattern in args.files:
        matches = glob.glob(pattern)
        files.extend(matches if matches else [pattern])

    upscale = {"model": args.model, "scale": args.upscale} if (args.upscale or args.model) else None

    def job(f):
        last = [0.0]

        def prog(key, **kw):
            if key in ("p_convert", "p_save"):
                return
            if time.time() - last[0] > 3:
                last[0] = time.time()
                print("[...]  {}: {}".format(f, tr(key, **kw)), flush=True)
        try:
            dst = convert(f, args.to, args.outdir, args.fast, args.quality, upscale, prog, args.mute)
            print("[OK]   {} -> {}".format(f, dst), flush=True)
            return True
        except Exception as e:
            print("[FAIL] {}: {}".format(f, err_text(e)), flush=True)
            return False

    with ThreadPoolExecutor(max_workers=max(2, (os.cpu_count() or 4))) as pool:
        ok = sum(pool.map(job, files))
    print("\n" + tr("cli_done", ok=ok, total=len(files)))
    return 0 if ok == len(files) else 1


if __name__ == "__main__":
    sys.exit(main())
