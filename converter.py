#!/usr/bin/env python3
"""
محول ملفات سريع
- الصور: Pillow  (png / jpg / webp / bmp / gif / tiff / ico)
- الفيديو والصوت: ffmpeg
- رفع الجودة بالذكاء الاصطناعي: Real-ESRGAN (ncnn-vulkan) للصور والفيديو

تشغيل الواجهة:     python converter.py
سطر الأوامر:        python converter.py -t jpg صورة1.png صورة2.png
                    python converter.py -t mp4 --fast فيديو.mkv
                    python converter.py -t png --upscale 4 صورة_صغيرة.jpg
                    python converter.py -t mp4 --upscale 2 --model fast فيديو.mp4
"""
import argparse
import glob
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

Image.MAX_IMAGE_PIXELS = 300_000_000

# ---------------------------------------------------------------- الصيغ
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
AI_VIDEO_OUT = ("mp4", "mkv", "webm", "avi", "mov")  # صيغ يدعمها رفع جودة الفيديو

# نماذج Real-ESRGAN: المفتاح -> (اسم النموذج, المضاعفات المدعومة فعلياً)
# ملاحظة: نماذج x4plus تدعم ×4 فقط، و animevideov3 يدعم ×2 و×3 و×4.
AI_MODELS = {
    "real": ("realesrgan-x4plus", (4,)),
    "anime": ("realesrgan-x4plus-anime", (4,)),
    "fast": ("realesr-animevideov3", (2, 3, 4)),
}
AI_LABELS = {
    "real": "واقعي (صور فوتوغرافية) ×4",
    "anime": "رسوم / أنمي ×4",
    "fast": "سريع (يصلح للفيديو) ×2 ×3 ×4",
}

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
ESRGAN_BIN = "realesrgan-ncnn-vulkan" + (".exe" if os.name == "nt" else "")
# قفل واحد للأعمال الثقيلة (ffmpeg + كرت الشاشة). RLock لأن خط معالجة الفيديو ينادي ffmpeg من داخله.
FF_LOCK = threading.RLock()


# ---------------------------------------------------------------- أدوات مساعدة
def ext_of(path) -> str:
    return Path(path).suffix.lower().lstrip(".")


def kind_of_ext(ext: str):
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
    """يدور على ffmpeg: داخل الـ exe، أو جنب الملف، أو في PATH."""
    for d in _bundle_dirs():
        c = d / "ffmpeg.exe"
        if c.is_file():
            return str(c)
    return shutil.which("ffmpeg")


def esrgan_dir():
    """مجلد realesrgan (فيه الـ exe ومجلد models)، أو None."""
    for d in _bundle_dirs():
        c = d / "realesrgan"
        if (c / ESRGAN_BIN).is_file() and (c / "models").is_dir():
            return c
    return None


def pick_engine(src_ext: str, target: str):
    """يرجع 'image' أو 'ffmpeg' أو None إذا التحويل غير مدعوم."""
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


def _primary_targets(ext: str):
    """الصيغ اللي تظهر في القائمة لملف بهذا الامتداد."""
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
    """الصيغ المناسبة لقائمة الملفات: فيديو -> صيغ فيديو فقط، صور -> صيغ صور فقط..."""
    kinds = {kind_of_ext(ext_of(f)) for f in files} - {None}
    if not kinds:
        return list(ALL_OUT)
    if audio_only and "video" in kinds:
        return list(AUDIO_OUT)
    if len(kinds) > 1:
        return list(ALL_OUT)
    known = [f for f in files if kind_of_ext(ext_of(f))]
    sets = [set(_primary_targets(ext_of(f))) for f in known]
    # الترتيب حسب أول ملف (فيديو: mp4 أولاً، صور: jpg أولاً)
    common = [t for t in _primary_targets(ext_of(known[0])) if all(t in s for s in sets)]
    return common or list(ALL_OUT)


def unique_dst(src: Path, fmt: str, outdir) -> Path:
    ext = "jpg" if fmt == "jpeg" else fmt
    folder = outdir or src.parent
    dst = folder / f"{src.stem}.{ext}"
    n = 1
    while dst.exists() or dst.resolve() == src.resolve():
        tag = "_converted" if n == 1 else f"_converted{n}"
        dst = folder / f"{src.stem}{tag}.{ext}"
        n += 1
    return dst


def _last_line(text, default):
    lines = [l for l in (text or "").strip().splitlines() if l.strip()]
    return lines[-1] if lines else default


# ---------------------------------------------------------------- الصور
def convert_image(src: Path, dst: Path, fmt: str, quality: int):
    pil_fmt = IMAGE_PIL[fmt]
    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im)  # يصلّح اتجاه صور الجوال
        if pil_fmt in ("JPEG", "BMP") and (
            im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info)
        ):
            rgba = im.convert("RGBA")
            bg = Image.new("RGB", rgba.size, (255, 255, 255))  # الشفافية -> خلفية بيضاء
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


# ---------------------------------------------------------------- رفع الجودة (Real-ESRGAN)
def _resolve_ai(upscale: dict, kind: str):
    """يرجع (اسم النموذج, المضاعفة الفعلية) مع تصحيح القيم غير المدعومة."""
    key = upscale.get("model") or ("real" if kind == "image" else "fast")
    if key not in AI_MODELS:
        raise ValueError(f"نموذج غير معروف: {key}")
    name, scales = AI_MODELS[key]
    scale = upscale.get("scale") or (scales[0] if key == "fast" else scales[-1])
    if scale not in scales:
        scale = scales[-1]  # x4plus يدعم ×4 فقط
    return name, scale


def run_esrgan(src_in, dst_out, model, scale, fmt, progress=None, total=1):
    d = esrgan_dir()
    if d is None:
        raise RuntimeError("مجلد realesrgan (مع models) غير موجود. الـ exe الجاهز يحتويه.")
    cmd = [str(d / ESRGAN_BIN), "-i", str(src_in), "-o", str(dst_out),
           "-n", model, "-s", str(scale), "-m", str(d / "models"), "-f", fmt]
    # stderr يروح لملف مؤقت: لو تركناه PIPE بدون قراءة ممكن يتعلق البرنامج مع آلاف الإطارات
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
                    n = sum(1 for _ in os.scandir(dst_out))
                    progress(f"رفع الجودة {min(n, total)}/{total}")
        log.seek(0)
        err = log.read()
    if proc.returncode != 0:
        raise RuntimeError(_last_line(err, "فشل Real-ESRGAN") +
                           " (يحتاج كرت شاشة يدعم Vulkan وتعريف حديث)")
    if not Path(dst_out).exists():
        raise RuntimeError("Real-ESRGAN ما أنتج ملف")


def upscale_image(src: Path, dst_png: Path, model: str, scale: int):
    """يرفع دقة صورة بالذكاء الاصطناعي ويحفظ النتيجة PNG مؤقتة."""
    with tempfile.TemporaryDirectory(prefix="fc_") as td:
        tin = Path(td) / "in.png"
        with Image.open(src) as im:
            im = ImageOps.exif_transpose(im)
            w, h = im.size
            if w * h * scale * scale > 150_000_000:
                raise ValueError(f"الناتج كبير جداً ({w * scale}x{h * scale}). "
                                 "استخدم صورة أصغر أو مضاعفة أقل")
            has_alpha = "A" in im.getbands() or "transparency" in im.info
            im = im.convert("RGBA" if has_alpha else "RGB")
            im.save(tin, "PNG")
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
                          stdin=subprocess.DEVNULL,  # ضروري لتطبيقات --windowed
                          creationflags=NO_WINDOW)


def _video_enc(fmt: str, hq: bool = False):
    if fmt == "webm":
        enc = ["-c:v", "libvpx-vp9", "-crf", "26" if hq else "32", "-b:v", "0",
               "-deadline", "realtime", "-cpu-used", "8", "-row-mt", "1", "-c:a", "libopus"]
    else:
        enc = ["-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
               "-c:v", "libx264", "-preset", "veryfast" if not hq else "fast",
               "-crf", "18" if hq else "23",
               "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k"]
    if fmt in ("mp4", "mov"):
        enc += ["-movflags", "+faststart"]
    return enc


def _ffmpeg_cmds(exe: str, src: Path, dst: Path, fmt: str, fast: bool):
    """يرجع قائمة محاولات (الأولى الأسرع، والباقي احتياط)."""
    base = [exe, "-y", "-nostdin", "-hide_banner", "-loglevel", "error", "-i", str(src)]

    if fmt in AUDIO_OUT:
        return [base + ["-vn"] + AUDIO_CODECS[fmt] + [str(dst)]]

    if fmt == "gif":
        vf = ("fps=12,scale='min(480,iw)':-1:flags=lanczos,"
              "split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse")
        return [base + ["-vf", vf, "-loop", "0", str(dst)]]

    maps = ["-map", "0:v:0", "-map", "0:a:0?"]
    full = base + maps + _video_enc(fmt) + [str(dst)]

    if fast and ext_of(src) in {"mp4", "mkv", "mov", "m4v"} and fmt in {"mp4", "mkv", "mov"}:
        copy = base + maps + ["-c", "copy"]
        if fmt in ("mp4", "mov"):
            copy += ["-movflags", "+faststart"]
        return [copy + [str(dst)], full]  # لو فشل النسخ المباشر نعيد الترميز
    return [full]


def convert_ffmpeg(src: Path, dst: Path, fmt: str, fast: bool):
    exe = ffmpeg_exe()
    if not exe:
        raise RuntimeError("ffmpeg غير موجود. ثبّته بالأمر: winget install Gyan.FFmpeg")
    last_err = ""
    with FF_LOCK:
        for cmd in _ffmpeg_cmds(exe, src, dst, fmt, fast):
            r = _run_ff(cmd)
            if r.returncode == 0:
                return
            last_err = _last_line(r.stderr, "فشل ffmpeg")
            if dst.exists():
                dst.unlink()
    raise RuntimeError(last_err)


def _probe_fps(exe: str, src: Path) -> str:
    r = _run_ff([exe, "-hide_banner", "-i", str(src)])  # يطلع خطأ "no output" لكن المعلومات في stderr
    m = re.search(r"(\d+(?:\.\d+)?)\s*fps", r.stderr or "")
    return m.group(1) if m else "30"


def ai_video(src: Path, dst: Path, fmt: str, model: str, scale: int, progress=None):
    """فيديو -> إطارات -> Real-ESRGAN -> تجميع مع صوت الفيديو الأصلي."""
    say = progress or (lambda t: None)
    exe = ffmpeg_exe()
    if not exe:
        raise RuntimeError("ffmpeg غير موجود")
    with FF_LOCK, tempfile.TemporaryDirectory(prefix="fc_") as td:
        fin, fout = Path(td) / "in", Path(td) / "out"
        fin.mkdir()
        fout.mkdir()
        fps = _probe_fps(exe, src)

        say("استخراج الإطارات...")
        r = _run_ff([exe, "-y", "-nostdin", "-hide_banner", "-loglevel", "error",
                     "-i", str(src), "-map", "0:v:0", "-vf", f"fps={fps}",
                     "-q:v", "2", str(fin / "%08d.jpg")])
        if r.returncode != 0:
            raise RuntimeError(_last_line(r.stderr, "فشل استخراج الإطارات"))
        frames = [p for p in fin.iterdir() if p.suffix == ".jpg"]
        total = len(frames)
        if total == 0:
            raise RuntimeError("ما لقيت إطارات في الفيديو")

        # حماية من امتلاء القرص: الإطارات الناتجة أكبر بحوالي scale^2
        est = sum(p.stat().st_size for p in frames) * scale * scale * 1.3
        free = shutil.disk_usage(td).free
        if free < est:
            raise RuntimeError(f"المساحة الفاضية ما تكفي (محتاج تقريباً {est / 1e9:.1f} جيجا، "
                               f"المتوفر {free / 1e9:.1f})")

        run_esrgan(fin, fout, model, scale, "jpg", progress=say, total=total)
        done = sum(1 for _ in fout.iterdir())
        if done < total:
            raise RuntimeError(f"Real-ESRGAN عالج {done} من {total} إطار فقط")

        say("تجميع الفيديو...")
        cmd = [exe, "-y", "-nostdin", "-hide_banner", "-loglevel", "error",
               "-framerate", fps, "-i", str(fout / "%08d.jpg"), "-i", str(src),
               "-map", "0:v:0", "-map", "1:a:0?"] + _video_enc(fmt, hq=True) + \
              ["-shortest", str(dst)]
        r = _run_ff(cmd)
        if r.returncode != 0:
            raise RuntimeError(_last_line(r.stderr, "فشل تجميع الفيديو"))


# ---------------------------------------------------------------- الواجهة العامة
def convert(src, fmt: str, outdir=None, fast=False, quality=90,
            upscale=None, progress=None) -> Path:
    """
    upscale: None أو dict مثل {"model": "real"|"anime"|"fast"|None, "scale": 2|3|4|None}
    progress: دالة تستقبل نص الحالة (اختياري)
    """
    src = Path(src)
    fmt = fmt.lower().lstrip(".")
    engine = pick_engine(ext_of(src), fmt)
    if engine is None:
        raise ValueError(f"لا يمكن تحويل .{ext_of(src)} إلى {fmt}")
    say = progress or (lambda t: None)
    if upscale and engine == "ffmpeg" and fmt == "gif":
        raise ValueError("رفع الجودة ما يدعم الإخراج gif. اختر mp4 أو mkv أو webm")

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
                    say("رفع الجودة...")
                    with FF_LOCK:  # كرت الشاشة واحد، فنرتب الطلبات
                        upscale_image(src, up, name, scale)
                    say("حفظ...")
                    convert_image(up, dst, fmt, quality)
            else:
                convert_image(src, dst, fmt, quality)
        elif upscale and fmt in AI_VIDEO_OUT:
            name, scale = _resolve_ai(upscale, "video")
            ai_video(src, dst, fmt, name, scale, progress=say)
        else:  # فيديو/صوت عادي (رفع الجودة لا يؤثر على الصوت)
            say("تحويل...")
            convert_ffmpeg(src, dst, fmt, fast)
    except Exception:
        if dst.exists():
            dst.unlink()
        raise
    return dst


# ---------------------------------------------------------------- الواجهة الرسومية
def run_gui(_test=False):
    import tkinter as tk
    from tkinter import filedialog, ttk

    dnd_flag = None
    try:  # السحب والإفلات اختياري: pip install tkinterdnd2
        from tkinterdnd2 import DND_FILES, TkinterDnD
        root = TkinterDnD.Tk()
        dnd_flag = DND_FILES
    except Exception:
        root = tk.Tk()

    root.title("محول الملفات")
    root.geometry("820x660")
    root.minsize(700, 560)

    paths: dict = {}
    results: "queue.Queue" = queue.Queue()
    state = {"total": 0, "done": 0, "running": False, "kinds": None}

    fmt_var = tk.StringVar(value="jpg")
    fast_var = tk.BooleanVar(value=True)
    audio_only_var = tk.BooleanVar(value=False)
    quality_var = tk.IntVar(value=90)
    outdir_var = tk.StringVar(value="")
    ai_var = tk.BooleanVar(value=False)
    ai_model_var = tk.StringVar(value=AI_LABELS["real"])
    ai_scale_var = tk.StringVar(value="4")
    ai_note_var = tk.StringVar(value="")
    label_to_key = {v: k for k, v in AI_LABELS.items()}

    # قائمة الملفات
    frame = ttk.Frame(root, padding=8)
    frame.pack(fill="both", expand=True)
    tree = ttk.Treeview(frame, columns=("file", "status"), show="headings", selectmode="extended")
    tree.heading("file", text="الملف")
    tree.heading("status", text="الحالة")
    tree.column("file", width=440)
    tree.column("status", width=280)
    sb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=sb.set)
    tree.pack(side="left", fill="both", expand=True)
    sb.pack(side="left", fill="y")

    # شريط الأزرار
    bar = ttk.Frame(root, padding=(8, 0))
    bar.pack(fill="x")

    # خيارات
    opts = ttk.Frame(root, padding=8)
    opts.pack(fill="x")

    ttk.Label(opts, text="التحويل إلى:").grid(row=0, column=0, sticky="w")
    fmt_cb = ttk.Combobox(opts, textvariable=fmt_var, values=ALL_OUT, width=8, state="readonly")
    fmt_cb.grid(row=0, column=1, padx=6)

    q_lbl = ttk.Label(opts, text="جودة الحفظ:")
    q_spin = ttk.Spinbox(opts, from_=1, to=100, textvariable=quality_var, width=5)
    q_lbl.grid(row=0, column=2, padx=(16, 0))
    q_spin.grid(row=0, column=3, padx=6)

    fast_chk = ttk.Checkbutton(opts, text="سريع (بدون إعادة ترميز إن أمكن)", variable=fast_var)
    fast_chk.grid(row=0, column=4, padx=12)
    audio_chk = ttk.Checkbutton(opts, text="استخراج الصوت فقط", variable=audio_only_var)
    audio_chk.grid(row=0, column=5, padx=4)

    # رفع الجودة
    ai_frame = ttk.LabelFrame(opts, text="رفع الجودة بالذكاء الاصطناعي (Real-ESRGAN)", padding=6)
    ai_frame.grid(row=1, column=0, columnspan=6, sticky="we", pady=(10, 4))
    ttk.Checkbutton(ai_frame, text="تفعيل", variable=ai_var).grid(row=0, column=0, padx=4)
    ttk.Label(ai_frame, text="النوع:").grid(row=0, column=1, padx=(10, 2))
    ai_model_cb = ttk.Combobox(ai_frame, textvariable=ai_model_var, state="readonly", width=30,
                               values=[AI_LABELS[k] for k in ("real", "anime", "fast")])
    ai_model_cb.grid(row=0, column=2, padx=4)
    ttk.Label(ai_frame, text="المضاعفة:").grid(row=0, column=3, padx=(10, 2))
    ai_scale_cb = ttk.Combobox(ai_frame, textvariable=ai_scale_var, state="readonly",
                               width=4, values=["2", "3", "4"])
    ai_scale_cb.grid(row=0, column=4, padx=4)
    ttk.Label(ai_frame, textvariable=ai_note_var, foreground="gray",
              wraplength=760, justify="right").grid(row=1, column=0, columnspan=5, sticky="w", pady=(6, 0))

    ttk.Button(opts, text="مجلد الإخراج",
               command=lambda: outdir_var.set(filedialog.askdirectory(title="مجلد الإخراج") or "")
               ).grid(row=2, column=0, pady=6, sticky="w")
    ttk.Label(opts, textvariable=outdir_var, foreground="gray").grid(row=2, column=1, columnspan=5, sticky="w")
    ttk.Label(opts, text="(إذا تركته فاضي يحفظ جنب الملف الأصلي)",
              foreground="gray").grid(row=3, column=0, columnspan=6, sticky="w")

    progress = ttk.Progressbar(root, mode="determinate")
    progress.pack(fill="x", padx=8, pady=(4, 0))
    start_btn = ttk.Button(root, text="ابدأ التحويل")
    start_btn.pack(pady=8)

    def toggle(widgets, show):
        for w in widgets:
            if show:
                w.grid()
            else:
                w.grid_remove()

    def refresh(*_):
        """يقرأ نوع الملفات ويعرض الخيارات المناسبة فقط."""
        files = list(paths.values())
        kinds = {kind_of_ext(ext_of(p)) for p in files} - {None}
        has_img, has_vid = "image" in kinds, "video" in kinds
        empty = not kinds

        toggle([audio_chk, fast_chk], has_vid)
        toggle([q_lbl, q_spin], has_img or empty)

        audio_only = audio_only_var.get() and has_vid
        values = targets_for_files(files, audio_only)
        fmt_cb["values"] = values
        if fmt_var.get() not in values:
            pref = {"image": "jpg", "video": "mp4", "audio": "mp3"}
            first = next(iter(sorted(kinds)), None)
            fmt_var.set(pref.get(first) if pref.get(first) in values else values[0])

        # رفع الجودة: للصور والفيديو فقط (مو للصوت)
        toggle([ai_frame], empty or has_img or (has_vid and not audio_only))

        # النوع الافتراضي يتغير فقط لما يتغير نوع الملفات (عشان ما نمسح اختيار المستخدم)
        if state["kinds"] != kinds:
            state["kinds"] = kinds
            if has_vid and not has_img:
                ai_model_var.set(AI_LABELS["fast"])
            elif has_img:
                ai_model_var.set(AI_LABELS["real"])
        on_model()

        note = "يحتاج كرت شاشة يدعم Vulkan (NVIDIA / AMD / Intel)."
        if has_vid:
            note += " تنبيه: رفع جودة الفيديو بطيء جداً (كل إطار يمر على النموذج) ويحتاج مساحة فاضية كبيرة على القرص."
        if has_vid and fmt_var.get() == "gif":
            note += " الإخراج gif لا يدعم رفع الجودة."
        ai_note_var.set(note)

    def on_model(*_):
        key = label_to_key.get(ai_model_var.get(), "real")
        if key == state.get("model_key"):
            return
        state["model_key"] = key
        if key == "fast":
            ai_scale_cb.configure(state="readonly")
            ai_scale_var.set("2")
        else:
            ai_scale_var.set("4")
            ai_scale_cb.configure(state="disabled")  # هذي النماذج تدعم ×4 فقط

    def add_files(files):
        for f in files:
            p = Path(f)
            if p.is_dir():
                add_files([str(x) for x in p.iterdir() if x.is_file()])
                continue
            if not p.is_file() or p in paths.values():
                continue
            iid = tree.insert("", "end", values=(str(p), "بانتظار التحويل"))
            paths[iid] = p
        refresh()

    def on_clear():
        if state["running"]:
            return
        tree.delete(*tree.get_children())
        paths.clear()
        progress["value"] = 0
        refresh()

    def on_remove():
        if state["running"]:
            return
        for iid in tree.selection():
            tree.delete(iid)
            paths.pop(iid, None)
        refresh()

    ttk.Button(bar, text="إضافة ملفات",
               command=lambda: add_files(filedialog.askopenfilenames(title="اختر الملفات"))
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="حذف المحدد", command=on_remove).pack(side="left", padx=2)
    ttk.Button(bar, text="مسح الكل", command=on_clear).pack(side="left", padx=2)
    hint = "اسحب الملفات هنا" if dnd_flag else "للسحب والإفلات: pip install tkinterdnd2"
    ttk.Label(bar, text=hint, foreground="gray").pack(side="right")

    if dnd_flag:
        tree.drop_target_register(dnd_flag)
        tree.dnd_bind("<<Drop>>", lambda e: add_files(root.tk.splitlist(e.data)))

    audio_only_var.trace_add("write", refresh)
    fmt_var.trace_add("write", lambda *_: refresh() if not state["running"] else None)
    ai_model_var.trace_add("write", on_model)

    def poll():
        try:
            while True:
                iid, status, final = results.get_nowait()
                if tree.exists(iid):
                    tree.set(iid, "status", status)
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
        try:
            quality = max(1, min(100, int(quality_var.get())))
        except Exception:
            quality = 90
        upscale = None
        if ai_var.get():
            upscale = {"model": label_to_key.get(ai_model_var.get()),
                       "scale": int(ai_scale_var.get())}

        items = list(paths.items())
        state.update(total=len(items), done=0, running=True)
        progress["value"] = 0
        start_btn.state(["disabled"])
        for iid, _ in items:
            tree.set(iid, "status", "بانتظار الدور...")

        def job(iid, p):
            try:
                dst = convert(p, fmt, outdir, fast, quality, upscale,
                              progress=lambda t: results.put((iid, t, False)))
                results.put((iid, f"تم ✔ {dst.name}", True))
            except Exception as e:
                results.put((iid, f"فشل ✘ {str(e)[:110]}", True))

        def runner():
            with ThreadPoolExecutor(max_workers=max(2, (os.cpu_count() or 4))) as pool:
                for iid, p in items:
                    pool.submit(job, iid, p)

        threading.Thread(target=runner, daemon=True).start()

    start_btn.configure(command=on_start)
    refresh()
    poll()
    if _test:
        return {"root": root, "add_files": add_files, "refresh": refresh, "fmt_cb": fmt_cb,
                "fmt_var": fmt_var, "ai_frame": ai_frame, "fast_chk": fast_chk,
                "audio_chk": audio_chk, "audio_only_var": audio_only_var, "q_spin": q_spin,
                "ai_model_var": ai_model_var, "ai_scale_var": ai_scale_var,
                "ai_scale_cb": ai_scale_cb, "ai_var": ai_var, "on_start": on_start,
                "tree": tree, "state": state, "on_clear": on_clear}
    root.mainloop()


# ---------------------------------------------------------------- سطر الأوامر
def main():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description="محول ملفات: صور وفيديو وصوت")
    ap.add_argument("files", nargs="*", help="الملفات (يدعم *.png)")
    ap.add_argument("-t", "--to", help="الصيغة المطلوبة مثل jpg أو mp4 أو mp3")
    ap.add_argument("-o", "--outdir", help="مجلد الإخراج")
    ap.add_argument("-q", "--quality", type=int, default=90, help="جودة حفظ الصور 1-100")
    ap.add_argument("--fast", action="store_true", help="نسخ مباشر للفيديو بدون إعادة ترميز إن أمكن")
    ap.add_argument("--upscale", type=int, choices=[2, 3, 4],
                    help="رفع الجودة بالذكاء الاصطناعي (Real-ESRGAN) بهذي المضاعفة")
    ap.add_argument("--model", choices=list(AI_MODELS),
                    help="real=صور واقعية ×4 | anime=رسوم ×4 | fast=سريع ×2/×3/×4 (الافتراضي: real للصور، fast للفيديو)")
    args = ap.parse_args()

    if not args.files:
        return run_gui()
    if not args.to:
        ap.error("لازم تحدد الصيغة بـ -t مثل: -t jpg")

    files = []
    for pattern in args.files:
        matches = glob.glob(pattern)
        files.extend(matches if matches else [pattern])

    upscale = {"model": args.model, "scale": args.upscale} if (args.upscale or args.model) else None

    def job(f):
        last = [0.0]

        def prog(t):
            if t in ("تحويل...", "حفظ..."):
                return
            if time.time() - last[0] > 3:
                last[0] = time.time()
                print(f"[...]  {f}: {t}", flush=True)
        try:
            dst = convert(f, args.to, args.outdir, args.fast, args.quality, upscale, prog)
            print(f"[OK]   {f} -> {dst}", flush=True)
            return True
        except Exception as e:
            print(f"[FAIL] {f}: {e}", flush=True)
            return False

    with ThreadPoolExecutor(max_workers=max(2, (os.cpu_count() or 4))) as pool:
        ok = sum(pool.map(job, files))
    print(f"\nتم {ok} من {len(files)}")
    return 0 if ok == len(files) else 1


if __name__ == "__main__":
    sys.exit(main())
