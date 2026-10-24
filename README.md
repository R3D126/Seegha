# Seegha (صيغة) — by R3D

**English** | [العربية](#العربية)

Free, fast file converter for Windows: **images, video and audio**, with optional **AI upscaling** (Real-ESRGAN).
One portable `Seegha.exe` — nothing to install. UI in **English and Arabic** (switch live from the top-right corner).

## Features
- Images: png, jpg, webp, bmp, gif, tiff, ico. Video: mp4, mkv, webm, avi, mov, gif. Audio: mp3, wav, flac, aac, ogg, m4a.
- The format list adapts to your files: add a video → only video formats; add images → only image formats.
- **Audio options for video:** keep audio · **no audio (video only)** · audio only.
- **Fast mode:** change the container (e.g. mkv → mp4) without re-encoding when possible.
- **AI upscaling** for images and videos (real detail reconstruction with Real-ESRGAN, not plain resizing).
- Drag & drop, batch conversion, command-line mode, never overwrites your originals.

## Download
Grab `Seegha.exe` from the **Releases** page (or the latest **Actions** run → Artifacts).

## Windows support
| System | Status |
|---|---|
| Windows 10 / 11 (64-bit) | Supported |
| Windows 8 / 8.1 (64-bit) | Supported |
| Windows 7 SP1 (64-bit) | Targeted — see notes below |
| 32-bit Windows | **Not supported** (ffmpeg and Real-ESRGAN builds are 64-bit only) |

Windows 7 notes: install Service Pack 1 and the Universal C Runtime update (**KB2999226**) or run Windows Update.
Seegha is built with Python 3.8 (the last Python that supports Windows 7) and a Windows-7-compatible ffmpeg build.
AI upscaling needs a GPU + driver with **Vulkan** support; if your Windows 7 GPU driver has none, the rest of the program still works.

## AI upscaling — what to expect
- Needs a Vulkan-capable GPU (NVIDIA / AMD / Intel). There is no CPU mode.
- Realistic and anime models are ×4 only; the fast model supports ×2, ×3, ×4.
- **Video is very slow**: every frame goes through the model, and it needs lots of free disk space (Seegha stops with a message if there is not enough).
- The AI *guesses* plausible detail. The result is far better than normal resizing, but it is not the original high-resolution source.

## Command line
```
Seegha.exe -t jpg *.png
Seegha.exe -t mp4 --mute video.mkv            # video without audio
Seegha.exe -t mp3 video.mp4                   # extract audio
Seegha.exe -t png --upscale 4 small.jpg       # AI upscale
Seegha.exe -t mp4 --upscale 2 --model fast clip.mp4 --lang en
```
The exe is a windowed app, so it prints nothing in the console. To see messages run `python seegha.py ...` from source.

## Build it yourself
1. Push this repo to GitHub. 2. Open the **Actions** tab, run **Build Seegha**. 3. Download `Seegha` from the run's Artifacts.
Push a tag like `v1.0.0` to publish `Seegha.exe` on the Releases page automatically.

Run from source: `pip install -r requirements.txt` then `python seegha.py` (needs ffmpeg on PATH or `ffmpeg.exe` next to the script; put the `realesrgan` folder there for AI upscaling).

## Licence
Seegha's code: MIT (`LICENSE`). The exe bundles FFmpeg (GPLv3), Real-ESRGAN and others — see `THIRD_PARTY_NOTICES.md`.

---

<a id="العربية"></a>
# صيغة (Seegha) — by R3D

محوّل ملفات مجاني وسريع لويندوز: **صور وفيديو وصوت**، مع **رفع جودة بالذكاء الاصطناعي** (Real-ESRGAN).
ملف واحد `Seegha.exe` بدون تثبيت. الواجهة **عربي وإنجليزي** وتغيّرها فوراً من أعلى اليمين.

## المميزات
- صور: png, jpg, webp, bmp, gif, tiff, ico. فيديو: mp4, mkv, webm, avi, mov, gif. صوت: mp3, wav, flac, aac, ogg, m4a.
- قائمة الصيغ تتغير حسب ملفاتك: أضفت فيديو تظهر صيغ الفيديو فقط، وأضفت صور تظهر صيغ الصور فقط.
- **خيارات الصوت للفيديو:** مع الصوت · **بدون صوت (فيديو فقط)** · صوت فقط.
- **الوضع السريع:** يغيّر الحاوية (مثل mkv إلى mp4) بدون إعادة ترميز إذا أمكن.
- **رفع الجودة بالذكاء الاصطناعي** للصور والفيديو (يعيد بناء التفاصيل فعلياً بـ Real-ESRGAN، مو تكبير عادي).
- سحب وإفلات، تحويل جماعي، وضع سطر أوامر، ولا يكتب فوق الملفات الأصلية.

## التحميل
نزّل `Seegha.exe` من صفحة **Releases** (أو من آخر تشغيل في **Actions** ثم Artifacts).

## الأنظمة المدعومة
| النظام | الحالة |
|---|---|
| ويندوز 10 / 11 (64 بت) | مدعوم |
| ويندوز 8 / 8.1 (64 بت) | مدعوم |
| ويندوز 7 SP1 (64 بت) | مستهدف — شوف الملاحظات تحت |
| ويندوز 32 بت | **غير مدعوم** (نسخ ffmpeg وReal-ESRGAN 64 بت فقط) |

ملاحظات ويندوز 7: ثبّت Service Pack 1 وتحديث Universal C Runtime (**KB2999226**) أو شغّل Windows Update.
البرنامج مبني ببايثون 3.8 (آخر إصدار يدعم ويندوز 7) ونسخة ffmpeg متوافقة مع ويندوز 7.
رفع الجودة يحتاج كرت شاشة وتعريف يدعم **Vulkan**؛ لو تعريفك على ويندوز 7 ما يدعمه، باقي البرنامج يشتغل عادي.

## رفع الجودة — وش تتوقع
- يحتاج كرت شاشة يدعم Vulkan (NVIDIA / AMD / Intel). ما فيه وضع معالج.
- النموذج الواقعي والأنمي ×4 فقط، والسريع يدعم ×2 و×3 و×4.
- **الفيديو بطيء جداً**: كل إطار يمر على النموذج، ويحتاج مساحة فاضية كبيرة (البرنامج يوقف مع رسالة لو المساحة ما تكفي).
- الذكاء الاصطناعي **يخمّن تفاصيل معقولة**. النتيجة أحسن بكثير من التكبير العادي، لكنها مو المصدر الأصلي عالي الدقة.

## سطر الأوامر
```
Seegha.exe -t jpg *.png
Seegha.exe -t mp4 --mute video.mkv            # فيديو بدون صوت
Seegha.exe -t mp3 video.mp4                   # استخراج الصوت
Seegha.exe -t png --upscale 4 small.jpg       # رفع جودة
```
الـ exe تطبيق نوافذ فلا يطبع في الكونسول. لرؤية الرسائل شغّل `python seegha.py ...` من الكود.

## البناء بنفسك
1. ارفع المستودع على GitHub. 2. افتح تبويب **Actions** وشغّل **Build Seegha**. 3. نزّل `Seegha` من Artifacts.
أنشئ tag مثل `v1.0.0` وينرفع `Seegha.exe` تلقائياً في Releases.

## الترخيص
كود Seegha: MIT (`LICENSE`). الـ exe يحتوي FFmpeg (GPLv3) وReal-ESRGAN وغيرها — شوف `THIRD_PARTY_NOTICES.md`.
