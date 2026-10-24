#!/usr/bin/env python3
"""
محول ملفات سريع
- الصور: Pillow  (png / jpg / webp / bmp / gif / tiff / ico)
- الفيديو والصوت: ffmpeg  (mp4 / mkv / webm / avi / mov / gif / mp3 / wav / flac ...)

تشغيل الواجهة:   python converter.py
تشغيل سطر الأوامر: python converter.py -t jpg صورة1.png صورة2.png
                   python converter.py -t mp4 --fast فيديو.mkv
                   python converter.py -t mp3 *.mp4
"""
import argparse
import glob
import os
import queue
import shutil
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image, ImageOps

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

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
FF_LOCK = threading.Lock()  # ffmpeg يستهلك كل الأنوية، فنشغّل واحد بس في نفس الوقت


def ffmpeg_exe():
    """يدور على ffmpeg: داخل الـ exe، أو جنب الملف، أو في PATH."""
    candidates = []
    if getattr(sys, "frozen", False):
        candidates.append(Path(getattr(sys, "_MEIPASS", "")) / "ffmpeg.exe")
        candidates.append(Path(sys.executable).parent / "ffmpeg.exe")
    else:
        candidates.append(Path(__file__).resolve().parent / "ffmpeg.exe")
    for c in candidates:
        if c.is_file():
            return str(c)
    return shutil.which("ffmpeg")


def ext_of(path: Path) -> str:
    return path.suffix.lower().lstrip(".")


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


def unique_dst(src: Path, fmt: str, outdir: Path | None) -> Path:
    ext = "jpg" if fmt == "jpeg" else fmt
    folder = outdir or src.parent
    dst = folder / f"{src.stem}.{ext}"
    n = 1
    while dst.exists() or dst.resolve() == src.resolve():
        tag = "_converted" if n == 1 else f"_converted{n}"
        dst = folder / f"{src.stem}{tag}.{ext}"
        n += 1
    return dst


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


# ---------------------------------------------------------------- ffmpeg
AUDIO_CODECS = {
    "mp3": ["-c:a", "libmp3lame", "-q:a", "2"],
    "wav": ["-c:a", "pcm_s16le"],
    "flac": ["-c:a", "flac"],
    "aac": ["-c:a", "aac", "-b:a", "192k"],
    "m4a": ["-c:a", "aac", "-b:a", "192k"],
    "ogg": ["-c:a", "libvorbis", "-q:a", "5"],
}


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
    if fmt == "webm":
        enc = ["-c:v", "libvpx-vp9", "-crf", "32", "-b:v", "0", "-deadline",
               "realtime", "-cpu-used", "8", "-row-mt", "1", "-c:a", "libopus"]
    else:
        enc = ["-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
               "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k"]
    if fmt in ("mp4", "mov"):
        enc += ["-movflags", "+faststart"]
    full = base + maps + enc + [str(dst)]

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
            r = subprocess.run(cmd, capture_output=True, text=True,
                               encoding="utf-8", errors="replace",
                               stdin=subprocess.DEVNULL,  # ضروري لتطبيقات --windowed
                               creationflags=NO_WINDOW)
            if r.returncode == 0:
                return
            last_err = r.stderr.strip().splitlines()[-1] if r.stderr.strip() else "فشل ffmpeg"
            if dst.exists():
                dst.unlink()
    raise RuntimeError(last_err)


# ---------------------------------------------------------------- الواجهة العامة
def convert(src, fmt: str, outdir=None, fast=False, quality=90) -> Path:
    src = Path(src)
    fmt = fmt.lower().lstrip(".")
    engine = pick_engine(ext_of(src), fmt)
    if engine is None:
        raise ValueError(f"لا يمكن تحويل .{ext_of(src)} إلى {fmt}")
    outdir = Path(outdir) if outdir else None
    if outdir:
        outdir.mkdir(parents=True, exist_ok=True)
    dst = unique_dst(src, fmt, outdir)
    try:
        if engine == "image":
            convert_image(src, dst, fmt, quality)
        else:
            convert_ffmpeg(src, dst, fmt, fast)
    except Exception:
        if dst.exists():
            dst.unlink()
        raise
    return dst


# ---------------------------------------------------------------- الواجهة الرسومية
def run_gui():
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
    root.geometry("760x520")
    root.minsize(640, 420)

    paths: dict[str, Path] = {}
    results: "queue.Queue" = queue.Queue()
    state = {"total": 0, "done": 0, "running": False}

    fmt_var = tk.StringVar(value="jpg")
    fast_var = tk.BooleanVar(value=True)
    quality_var = tk.IntVar(value=90)
    outdir_var = tk.StringVar(value="")

    # قائمة الملفات
    frame = ttk.Frame(root, padding=8)
    frame.pack(fill="both", expand=True)

    tree = ttk.Treeview(frame, columns=("file", "status"), show="headings", selectmode="extended")
    tree.heading("file", text="الملف")
    tree.heading("status", text="الحالة")
    tree.column("file", width=420)
    tree.column("status", width=260)
    sb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=sb.set)
    tree.pack(side="left", fill="both", expand=True)
    sb.pack(side="left", fill="y")

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

    def on_add():
        add_files(filedialog.askopenfilenames(title="اختر الملفات"))

    def on_clear():
        if state["running"]:
            return
        tree.delete(*tree.get_children())
        paths.clear()
        progress["value"] = 0

    def on_remove():
        if state["running"]:
            return
        for iid in tree.selection():
            tree.delete(iid)
            paths.pop(iid, None)

    def on_outdir():
        d = filedialog.askdirectory(title="مجلد الإخراج")
        outdir_var.set(d or "")

    if dnd_flag:
        tree.drop_target_register(dnd_flag)
        tree.dnd_bind("<<Drop>>", lambda e: add_files(root.tk.splitlist(e.data)))

    # شريط التحكم
    bar = ttk.Frame(root, padding=(8, 0))
    bar.pack(fill="x")
    ttk.Button(bar, text="إضافة ملفات", command=on_add).pack(side="left", padx=2)
    ttk.Button(bar, text="حذف المحدد", command=on_remove).pack(side="left", padx=2)
    ttk.Button(bar, text="مسح الكل", command=on_clear).pack(side="left", padx=2)
    hint = "اسحب الملفات هنا" if dnd_flag else "للسحب والإفلات: pip install tkinterdnd2"
    ttk.Label(bar, text=hint, foreground="gray").pack(side="right")

    opts = ttk.Frame(root, padding=8)
    opts.pack(fill="x")
    ttk.Label(opts, text="التحويل إلى:").grid(row=0, column=0, sticky="w")
    ttk.Combobox(opts, textvariable=fmt_var, values=ALL_OUT, width=8, state="readonly").grid(row=0, column=1, padx=6)
    ttk.Label(opts, text="جودة الصور:").grid(row=0, column=2, padx=(16, 0))
    ttk.Spinbox(opts, from_=1, to=100, textvariable=quality_var, width=5).grid(row=0, column=3, padx=6)
    ttk.Checkbutton(opts, text="سريع (بدون إعادة ترميز إن أمكن)", variable=fast_var).grid(row=0, column=4, padx=16)
    ttk.Button(opts, text="مجلد الإخراج", command=on_outdir).grid(row=1, column=0, pady=6, sticky="w")
    ttk.Label(opts, textvariable=outdir_var, foreground="gray").grid(row=1, column=1, columnspan=4, sticky="w")
    ttk.Label(opts, text="(إذا تركته فاضي يحفظ جنب الملف الأصلي)", foreground="gray").grid(row=2, column=0, columnspan=5, sticky="w")

    progress = ttk.Progressbar(root, mode="determinate")
    progress.pack(fill="x", padx=8, pady=(4, 0))
    start_btn = ttk.Button(root, text="ابدأ التحويل")
    start_btn.pack(pady=8)

    def poll():
        try:
            while True:
                iid, status = results.get_nowait()
                if tree.exists(iid):
                    tree.set(iid, "status", status)
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

        items = list(paths.items())
        state.update(total=len(items), done=0, running=True)
        progress["value"] = 0
        start_btn.state(["disabled"])
        for iid, _ in items:
            tree.set(iid, "status", "جاري التحويل...")

        def job(iid, p):
            try:
                dst = convert(p, fmt, outdir, fast, quality)
                results.put((iid, f"تم ✔ {dst.name}"))
            except Exception as e:
                results.put((iid, f"فشل ✘ {str(e)[:90]}"))

        def runner():
            with ThreadPoolExecutor(max_workers=max(2, (os.cpu_count() or 4))) as pool:
                for iid, p in items:
                    pool.submit(job, iid, p)

        threading.Thread(target=runner, daemon=True).start()

    start_btn.configure(command=on_start)
    poll()
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
    ap.add_argument("-q", "--quality", type=int, default=90, help="جودة الصور 1-100")
    ap.add_argument("--fast", action="store_true", help="نسخ مباشر للفيديو بدون إعادة ترميز إن أمكن")
    args = ap.parse_args()

    if not args.files:
        return run_gui()
    if not args.to:
        ap.error("لازم تحدد الصيغة بـ -t مثل: -t jpg")

    files = []
    for pattern in args.files:
        matches = glob.glob(pattern)
        files.extend(matches if matches else [pattern])

    def job(f):
        try:
            dst = convert(f, args.to, args.outdir, args.fast, args.quality)
            print(f"[OK]   {f} -> {dst}")
            return True
        except Exception as e:
            print(f"[FAIL] {f}: {e}")
            return False

    with ThreadPoolExecutor(max_workers=max(2, (os.cpu_count() or 4))) as pool:
        ok = sum(pool.map(job, files))
    print(f"\nتم {ok} من {len(files)}")
    return 0 if ok == len(files) else 1


if __name__ == "__main__":
    sys.exit(main())
