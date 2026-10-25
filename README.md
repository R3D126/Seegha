# Seegha (صيغة) — by R3D

**English** | [العربية](#العربية)

Free, fast file converter for Windows: **images, video and audio**, with optional **AI upscaling** (Real-ESRGAN).
One portable exe — nothing to install. UI in **English and Arabic** (switch live, top-right corner).

## Which file do I download?
| File | Size | AI upscaling |
|---|---|---|
| **Seegha.exe** (lite, recommended) | ~35 MB | downloads a 45 MB pack once, the first time you use it |
| **Seegha-Full.exe** | ~80 MB | built in, works fully offline |

Get them from the **Releases** page (or the latest **Actions** run → Artifacts).

## Features
- Images: png, jpg, webp, bmp, gif, tiff, ico. Video: mp4, mkv, webm, avi, mov, gif. Audio: mp3, wav, flac, aac, ogg, m4a.
- The format list adapts to your files (video → video formats only, images → image formats only).
- **Audio options for video:** keep audio · **no audio (video only)** · audio only.
- **Fast mode:** change the container (e.g. mkv → mp4) without re-encoding when possible.
- **AI upscaling** for images and video (real detail reconstruction, not plain resizing).
- **Stop** button, drag & drop, batch conversion, command line, never overwrites your originals.

## AI upscaling — what to expect
- Needs a Vulkan-capable GPU (NVIDIA / AMD / Intel). There is no CPU mode.
- **GPU usage** (default *Light*): *Light* keeps the PC responsive, *Balanced* is faster, *Maximum* is fastest but may slow the whole PC.
  Seegha runs the AI at low priority, in chunks of 100 frames, and **retries automatically with smaller tiles** if the GPU driver resets.
- **Video output is capped at 4K (3840×2160).** A 1080p video at ×4 would be 8K, which exhausts RAM/VRAM/disk and freezes the PC,
  so Seegha lowers the scale automatically (1080p → ×2) and tells you. Realistic/anime models are ×4 only; the fast model supports ×2/×3/×4.
- **Video is slow**: every frame goes through the model, and it needs lots of free disk space (checked before starting).
- The AI *guesses* plausible detail. The result is far better than normal resizing, but it is not the original high-resolution source.

## Windows support
| System | Status |
|---|---|
| Windows 10 / 11 (64-bit) | Supported |
| Windows 8 / 8.1 (64-bit) | Supported |
| Windows 7 SP1 (64-bit) | Targeted — see notes |
| 32-bit Windows | **Not supported** (ffmpeg and Real-ESRGAN builds are 64-bit only) |

Windows 7: install SP1 and the Universal C Runtime update (**KB2999226**) or run Windows Update. Seegha is built with Python 3.8
(the last Python for Windows 7) and an ffmpeg build documented as Windows-7-compatible. AI upscaling needs a Vulkan driver.
If ffmpeg refuses to start on your system, put your own `ffmpeg.exe` next to `Seegha.exe` — it is used first.

## Files Seegha creates
`%LOCALAPPDATA%\Seegha\` — `config.json` (language), `bin\` (ffmpeg, unpacked once from inside the exe), `realesrgan\` (AI pack, lite build only).
Temporary frames for video upscaling live in a `seegha_*` temp folder and are removed when finished, stopped, or at the next start.

## Command line
```
Seegha.exe -t jpg *.png
Seegha.exe -t mp4 --mute video.mkv            # video without audio
Seegha.exe -t mp3 video.mp4                   # extract audio
Seegha.exe -t png --upscale 4 small.jpg       # AI upscale (downloads the pack if needed)
Seegha.exe -t mp4 --upscale 2 --model fast --gpu balanced clip.mp4
Seegha.exe --install-ai                       # only download the AI pack
```
The exe is a windowed app, so it prints nothing in a console; run `python seegha.py ...` from source to see messages.

## Build it yourself
Push to GitHub → **Actions** → *Build Seegha* → download `Seegha` and `Seegha-Full` from Artifacts. Push a tag like `v1.1.0` to publish both on Releases.
From source: `pip install -r requirements.txt` then `python seegha.py` (ffmpeg on PATH or `ffmpeg.exe` next to the script).

## Licence
Seegha's code: MIT (`LICENSE`). The exe bundles FFmpeg (GPLv3) and others — see `THIRD_PARTY_NOTICES.md`.

---

<a id="العربية"></a>
# صيغة (Seegha) — by R3D

محوّل ملفات مجاني وسريع لويندوز: **صور وفيديو وصوت**، مع **رفع جودة بالذكاء الاصطناعي** (Real-ESRGAN).
ملف واحد بدون تثبيت. الواجهة **عربي وإنجليزي** وتغيّرها فوراً من أعلى اليمين.

## أي ملف أنزّل؟
| الملف | الحجم | رفع الجودة |
|---|---|---|
| **Seegha.exe** (الخفيف، الموصى به) | حوالي 35 ميجا | يحمّل حزمة 45 ميجا مرة وحدة أول ما تستخدمه |
| **Seegha-Full.exe** | حوالي 80 ميجا | مدمج، يشتغل بدون إنترنت |

نزّلهم من صفحة **Releases** (أو من آخر تشغيل في **Actions** ثم Artifacts).

## المميزات
- صور: png, jpg, webp, bmp, gif, tiff, ico. فيديو: mp4, mkv, webm, avi, mov, gif. صوت: mp3, wav, flac, aac, ogg, m4a.
- قائمة الصيغ تتغير حسب ملفاتك (فيديو ← صيغ فيديو فقط، صور ← صيغ صور فقط).
- **خيارات الصوت للفيديو:** مع الصوت · **بدون صوت (فيديو فقط)** · صوت فقط.
- **الوضع السريع:** يغيّر الحاوية (مثل mkv إلى mp4) بدون إعادة ترميز إذا أمكن.
- **رفع الجودة بالذكاء الاصطناعي** للصور والفيديو (يعيد بناء التفاصيل فعلياً، مو تكبير عادي).
- زر **إيقاف**، سحب وإفلات، تحويل جماعي، سطر أوامر، ولا يكتب فوق الملفات الأصلية.

## رفع الجودة — وش تتوقع
- يحتاج كرت شاشة يدعم Vulkan (NVIDIA / AMD / Intel). ما فيه وضع معالج.
- **الحمل على كرت الشاشة** (الافتراضي *خفيف*): *خفيف* يبقي الجهاز مرتاح، *متوازن* أسرع، *أقصى سرعة* الأسرع لكنه قد يبطّئ الجهاز كله.
  Seegha يشغّل الذكاء الاصطناعي بأولوية منخفضة وعلى دفعات من 100 إطار، و**يعيد المحاولة تلقائياً بمقاطع أصغر** لو تعريف الكرت أعاد تشغيل نفسه.
- **ناتج الفيديو محدود بدقة 4K (3840×2160).** فيديو 1080p بمضاعفة ×4 يصير 8K، وهذا يستهلك الرام والفيديو رام والقرص ويعلّق الجهاز،
  فيخفض Seegha المضاعفة تلقائياً (1080p ← ×2) ويخبرك. النموذج الواقعي والأنمي ×4 فقط، والسريع يدعم ×2 و×3 و×4.
- **الفيديو بطيء**: كل إطار يمر على النموذج، ويحتاج مساحة فاضية كبيرة على القرص (تُفحص قبل البدء).
- الذكاء الاصطناعي **يخمّن تفاصيل معقولة**. النتيجة أحسن بكثير من التكبير العادي لكنها مو المصدر الأصلي عالي الدقة.

## الأنظمة المدعومة
| النظام | الحالة |
|---|---|
| ويندوز 10 / 11 (64 بت) | مدعوم |
| ويندوز 8 / 8.1 (64 بت) | مدعوم |
| ويندوز 7 SP1 (64 بت) | مستهدف — شوف الملاحظات |
| ويندوز 32 بت | **غير مدعوم** (نسخ ffmpeg وReal-ESRGAN 64 بت فقط) |

ويندوز 7: ثبّت SP1 وتحديث Universal C Runtime (**KB2999226**) أو شغّل Windows Update. البرنامج مبني ببايثون 3.8
(آخر إصدار لويندوز 7) ونسخة ffmpeg الموثّق أنها متوافقة مع ويندوز 7. رفع الجودة يحتاج تعريف Vulkan.
لو ffmpeg ما اشتغل عندك، ضع `ffmpeg.exe` الخاص بك جنب `Seegha.exe` وبيُستخدم أولاً.

## الملفات اللي ينشئها البرنامج
`%LOCALAPPDATA%\Seegha\` — `config.json` (اللغة)، `bin\` (ffmpeg يُفك مرة وحدة من داخل الـ exe)، `realesrgan\` (حزمة الذكاء الاصطناعي، النسخة الخفيفة فقط).
إطارات رفع جودة الفيديو المؤقتة تكون في مجلد `seegha_*` داخل Temp وتنحذف عند الانتهاء أو الإيقاف أو عند التشغيل التالي.

## سطر الأوامر
```
Seegha.exe -t jpg *.png
Seegha.exe -t mp4 --mute video.mkv            # فيديو بدون صوت
Seegha.exe -t mp3 video.mp4                   # استخراج الصوت
Seegha.exe -t png --upscale 4 small.jpg       # رفع جودة (يحمّل الحزمة لو لزم)
Seegha.exe --install-ai                       # تحميل حزمة الذكاء الاصطناعي فقط
```

## البناء بنفسك
ارفع على GitHub ← **Actions** ← *Build Seegha* ← نزّل `Seegha` و`Seegha-Full` من Artifacts. أنشئ tag مثل `v1.1.0` وينرفعون في Releases.

## الترخيص
كود Seegha: MIT (`LICENSE`). الـ exe يحتوي FFmpeg (GPLv3) وغيره — شوف `THIRD_PARTY_NOTICES.md`.
