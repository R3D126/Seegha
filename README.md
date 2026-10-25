<div align="center">

# ✨ Seegha (صيغة)
### 🚀 by R3D

**🎞️ Convert · 🪄 Enhance · ⚡ Enjoy**  
**حوّل ملفاتك · حسّن جودتها · واستمتع بالسرعة**

A free, lightweight, and fast media converter for Windows — with optional AI-powered upscaling.

برنامج مجاني وخفيف وسريع لتحويل الصور والفيديو والصوت، مع إمكانية تحسين الجودة بالذكاء الاصطناعي.

🌐 **English | العربية**  
[⬇️ Download Seegha](https://github.com/R3D126/Seegha/releases/latest)

</div>

---

## 🌟 Highlights | أبرز المميزات

- 🖼️ **Image conversion | تحويل الصور**
- 🎬 **Video conversion | تحويل الفيديو**
- 🎵 **Audio conversion & extraction | تحويل الصوت واستخراجه**
- 🤖 **AI upscaling with Real-ESRGAN | تحسين الجودة بالذكاء الاصطناعي**
- 🌙 **Dark mode & ☀️ Light mode | الوضع الداكن والفاتح**
- ⚡ **Fast mode, batch conversion, and drag & drop | وضع سريع وتحويل جماعي وسحب وإفلات**
- 📦 **Portable — no installation required | نسخة محمولة بدون تثبيت**
- 🌍 **English and Arabic interface | واجهة باللغتين العربية والإنجليزية**

---

# 🇬🇧 English

## 📖 About Seegha

**Seegha** is a free, lightweight, and fast media converter for Windows. It helps you convert **images, videos, and audio** between supported formats, with optional **AI-powered upscaling using Real-ESRGAN**.

The app is portable, so there is no traditional installation process. Switch between English and Arabic directly from the interface.

## 📥 Which version should I download?

| File | Approx. size | AI upscaling |
|---|---:|---|
| **Seegha.exe** ⭐ Recommended | ~35 MB | Downloads an ~45 MB AI pack the first time you use it |
| **Seegha-Full.exe** | ~80 MB | AI pack included; designed to work offline |

➡️ **[Download the latest release](https://github.com/R3D126/Seegha/releases/latest)**

Download the `.exe` that suits your needs from the **Releases** page.

## 🧰 Features

- 🖼️ **Images:** PNG, JPG, WebP, BMP, GIF, TIFF, ICO.
- 🎬 **Video:** MP4, MKV, WebM, AVI, MOV, GIF.
- 🎵 **Audio:** MP3, WAV, FLAC, AAC, OGG, M4A.
- 🎯 **Smart format list:** options adapt to the selected media type.
- 🔊 **Video audio options:** keep audio, mute the output, or extract audio only.
- ⚡ **Fast mode:** changes the container (for example, MKV → MP4) without re-encoding when possible.
- 🤖 **AI upscaling:** enhance images and videos with Real-ESRGAN models.
- 🎨 **Personalized appearance:** light and dark themes; follows the Windows theme on first launch.
- 🛑 **Stop button:** stop a conversion when needed.
- 📂 **Batch conversion & drag and drop:** work with multiple files more conveniently.
- ⌨️ **Command-line support:** run supported conversion tasks from a terminal.
- 🛡️ **Protects originals:** Seegha does not overwrite your original files.

## 🤖 AI upscaling — what to expect

- 🖥️ **GPU required:** AI upscaling needs a Vulkan-capable GPU (NVIDIA, AMD, or Intel). CPU-only AI mode is not available.
- 🎚️ **GPU usage modes:** **Light** prioritizes responsiveness, **Balanced** offers a middle ground, and **Maximum** prioritizes speed but may make the PC less responsive.
- 🔄 **Recovery handling:** processing runs at low priority in batches of 100 frames and can retry with smaller tiles if a GPU driver reset occurs.
- 📺 **Video output limit:** output is capped at **4K (3840 × 2160)**. If the requested scale would exceed this limit, Seegha reduces the scale automatically and notifies you. For example, 1080p video is scaled up to ×2 rather than ×4.
- 🧠 **Model options:** Realistic and Anime models support ×4; the Fast model supports ×2, ×3, and ×4.
- ⏳ **Video processing takes time:** every frame must be processed, and substantial free disk space may be needed. Available space is checked before processing.
- 💡 **A realistic expectation:** AI reconstructs plausible details; results can look sharper than ordinary resizing, but they cannot restore the exact information from a genuine high-resolution original.

## 🪟 Windows compatibility

| Operating system | Status |
|---|---|
| Windows 10 / 11 (64-bit) | ✅ Supported |
| Windows 8 / 8.1 (64-bit) | ✅ Supported |
| Windows 7 SP1 (64-bit) | ⚠️ Targeted — see notes below |
| 32-bit Windows | ❌ Not supported |

**Windows 7 notes:** Install Service Pack 1 (SP1) and the Universal C Runtime update (**KB2999226**), or run Windows Update. Seegha is built with Python 3.8 and an FFmpeg build documented as Windows-7-compatible. AI upscaling also requires a suitable Vulkan driver.

If FFmpeg does not start on your system, try placing your own `ffmpeg.exe` next to `Seegha.exe`; Seegha checks for it first.

## 📁 Files created by Seegha

Seegha stores its application data in:

`%LOCALAPPDATA%\Seegha\`

- `config.json` — settings such as the interface language.
- `bin\` — FFmpeg files unpacked from the executable when needed.
- `realesrgan\` — AI pack used by the Lite build.
- `seegha_*` temporary folders — temporary video frames used during AI upscaling.

Temporary frames are removed after processing, when a task is stopped, or at the next launch.

## ⌨️ Command line

```bash
Seegha.exe -t jpg *.png
Seegha.exe -t mp4 --mute video.mkv
Seegha.exe -t mp3 video.mp4
Seegha.exe -t png --upscale 4 small.jpg
Seegha.exe -t mp4 --upscale 2 --model fast --gpu balanced clip.mp4
Seegha.exe --install-ai
```

Examples:
- Convert PNG images to JPG.
- Convert a video to MP4 without audio using `--mute`.
- Extract audio from a video to MP3.
- Upscale an image with AI.
- Upscale a video using the Fast model and Balanced GPU mode.
- Download the AI pack without starting a conversion.

The packaged executable is a windowed application and may not show console output. To see console messages, run `python seegha.py ...` from source.

## 🛠️ Build Seegha yourself

1. Push your changes to GitHub.
2. Open **Actions** and select **Build Seegha**.
3. Download the `Seegha` and `Seegha-Full` build artifacts.
4. Push a tag such as `v1.0.0` to publish both builds to Releases.

To run from source:

```bash
pip install -r requirements.txt
python seegha.py
```

FFmpeg must be available on `PATH` or placed next to the script as `ffmpeg.exe`.

## 🔐 Security, antivirus & VirusTotal

Seegha's source code and build workflow are available in this repository. As with any executable, review the source and scan downloads if you have concerns.

- 🧾 Compare the downloaded file with `SHA256SUMS.txt` on the Releases page, if provided.
- 🛡️ If a build attestation is available, verify it with GitHub CLI:
  ```bash
  gh attestation verify Seegha.exe --repo <owner>/<repo>
  ```
- 🔎 You can scan the executable using [VirusTotal](https://www.virustotal.com/).

**Antivirus detections:** Applications packaged with PyInstaller, and executables that unpack bundled tools, can sometimes receive false-positive detections. However, a detection should not automatically be assumed harmless. Check the detection details, verify the file's source and hash, and report suspected false positives to the relevant vendor.

Seegha is designed to process the files you select, store its app data in `%LOCALAPPDATA%\Seegha` and temporary files in a temporary folder, and use the internet to download the optional AI pack from GitHub when needed.

## 📄 License

- **Seegha source code:** MIT — see [`LICENSE`](LICENSE).
- **Bundled components:** the executable includes FFmpeg (GPLv3) and other third-party components. See [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

---

<a id="العربية"></a>

# 🇸🇦 العربية

## 📖 عن صيغة Seegha

**صيغة (Seegha)** برنامج مجاني وخفيف وسريع لنظام ويندوز، يساعدك على تحويل **الصور والفيديوهات والملفات الصوتية** بين الصيغ المدعومة، مع إمكانية **تحسين الجودة بالذكاء الاصطناعي باستخدام Real-ESRGAN**.

البرنامج محمول ولا يحتاج إلى تثبيت بالطريقة التقليدية، وتقدر تبدّل بين الواجهة العربية والإنجليزية مباشرةً من داخل البرنامج.

## 📥 أي نسخة أحمّل؟

| الملف | الحجم التقريبي | تحسين الجودة بالذكاء الاصطناعي |
|---|---:|---|
| **Seegha.exe** ⭐ الموصى به | حوالي 35 ميجابايت | يحمّل حزمة ذكاء اصطناعي بحجم 45 ميجابايت تقريبًا عند أول استخدام |
| **Seegha-Full.exe** | حوالي 80 ميجابايت | حزمة الذكاء الاصطناعي مدمجة، ومصمم للعمل دون إنترنت |

➡️ **[تحميل أحدث إصدار من Seegha](https://github.com/R3D126/Seegha/releases/latest)**

اختر ملف `.exe` المناسب لك من صفحة **Releases**.

## 🧰 المميزات

- 🖼️ **الصور:** PNG وJPG وWebP وBMP وGIF وTIFF وICO.
- 🎬 **الفيديو:** MP4 وMKV وWebM وAVI وMOV وGIF.
- 🎵 **الصوت:** MP3 وWAV وFLAC وAAC وOGG وM4A.
- 🎯 **قائمة صيغ ذكية:** تتغير الخيارات حسب نوع الملف المحدد.
- 🔊 **خيارات صوت الفيديو:** الاحتفاظ بالصوت، أو إخراج الفيديو بدون صوت، أو استخراج الصوت فقط.
- ⚡ **الوضع السريع:** تغيير حاوية الملف، مثل MKV إلى MP4، دون إعادة ترميز متى ما أمكن.
- 🤖 **تحسين الجودة بالذكاء الاصطناعي:** تحسين الصور والفيديو باستخدام نماذج Real-ESRGAN.
- 🎨 **مظهر يناسبك:** وضع داكن ووضع فاتح، مع اتباع مظهر ويندوز عند أول تشغيل.
- 🛑 **زر إيقاف:** لإيقاف عملية التحويل عند الحاجة.
- 📂 **تحويل جماعي وسحب وإفلات:** لمعالجة عدة ملفات بسهولة.
- ⌨️ **دعم سطر الأوامر:** تنفيذ عمليات التحويل المدعومة من الطرفية.
- 🛡️ **الحفاظ على ملفاتك الأصلية:** لا يستبدل Seegha الملفات الأصلية التي اخترتها.

## 🤖 تحسين الجودة بالذكاء الاصطناعي — وش تتوقع؟

- 🖥️ **يحتاج كرت شاشة:** يتطلب كرتًا يدعم Vulkan من NVIDIA أو AMD أو Intel. لا يتوفر وضع ذكاء اصطناعي يعمل على المعالج فقط.
- 🎚️ **مستويات استخدام الكرت:** وضع **خفيف** للمحافظة على استجابة الجهاز، و**متوازن** للموازنة بين السرعة والاستجابة، و**أقصى سرعة** لأولوية الأداء، وقد يجعل الجهاز أقل استجابة.
- 🔄 **التعامل مع تعطل التعريف:** تتم المعالجة بأولوية منخفضة وعلى دفعات من 100 إطار، وقد يعيد البرنامج المحاولة بمقاطع أصغر إذا أعاد تعريف كرت الشاشة التشغيل.
- 📺 **الحد الأقصى للفيديو:** دقة الإخراج محدودة بـ **4K (3840 × 2160)**. إذا كانت المضاعفة المطلوبة تتجاوز هذا الحد، يخفض Seegha المضاعفة تلقائيًا ويبلغك. مثلًا، فيديو 1080p تتم مضاعفته إلى ×2 بدلًا من ×4.
- 🧠 **النماذج:** نموذجا الواقعي والأنمي يدعمان ×4، بينما النموذج السريع يدعم ×2 و×3 و×4.
- ⏳ **معالجة الفيديو تستغرق وقتًا:** لأن كل إطار يحتاج إلى معالجة، وقد تحتاج العملية إلى مساحة كبيرة فارغة على القرص. يفحص البرنامج المساحة المتاحة قبل البدء.
- 💡 **توقعات واقعية:** الذكاء الاصطناعي يعيد بناء تفاصيل محتملة؛ وقد تكون النتيجة أوضح من التكبير العادي، لكنها لا تستعيد المعلومات الأصلية نفسها الموجودة في مصدر حقيقي عالي الدقة.

## 🪟 توافق ويندوز

| نظام التشغيل | الحالة |
|---|---|
| Windows 10 / 11 (64 بت) | ✅ مدعوم |
| Windows 8 / 8.1 (64 بت) | ✅ مدعوم |
| Windows 7 SP1 (64 بت) | ⚠️ مستهدف — راجع الملاحظات |
| ويندوز 32 بت | ❌ غير مدعوم |

**ملاحظات ويندوز 7:** ثبّت Service Pack 1 (SP1) وتحديث Universal C Runtime (**KB2999226**) أو شغّل Windows Update. بُني Seegha باستخدام Python 3.8 ونسخة FFmpeg موثّق توافقها مع ويندوز 7. كما يتطلب تحسين الجودة تعريفًا مناسبًا يدعم Vulkan.

إذا لم يعمل FFmpeg على جهازك، جرّب وضع نسخة `ffmpeg.exe` الخاصة بك بجانب `Seegha.exe`؛ إذ يتحقق البرنامج منها أولًا.

## 📁 الملفات التي ينشئها البرنامج

يحفظ Seegha بياناته في:

`%LOCALAPPDATA%\Seegha\`

- `config.json` — إعدادات مثل لغة الواجهة.
- `bin\` — ملفات FFmpeg التي تُفك من داخل البرنامج عند الحاجة.
- `realesrgan\` — حزمة الذكاء الاصطناعي المستخدمة في النسخة الخفيفة.
- مجلدات مؤقتة باسم `seegha_*` — لحفظ إطارات الفيديو أثناء تحسينها بالذكاء الاصطناعي.

تُحذف الإطارات المؤقتة بعد انتهاء المعالجة، أو عند إيقاف المهمة، أو عند تشغيل البرنامج مرة أخرى.

## ⌨️ أمثلة سطر الأوامر

```bash
Seegha.exe -t jpg *.png
Seegha.exe -t mp4 --mute video.mkv
Seegha.exe -t mp3 video.mp4
Seegha.exe -t png --upscale 4 small.jpg
Seegha.exe -t mp4 --upscale 2 --model fast --gpu balanced clip.mp4
Seegha.exe --install-ai
```

أمثلة على الاستخدام:
- تحويل صور PNG إلى JPG.
- تحويل فيديو إلى MP4 بدون صوت باستخدام `--mute`.
- استخراج الصوت من فيديو إلى MP3.
- تحسين صورة بالذكاء الاصطناعي.
- تحسين فيديو باستخدام النموذج السريع ووضع الكرت المتوازن.
- تحميل حزمة الذكاء الاصطناعي فقط دون بدء التحويل.

نسخة EXE تعمل بواجهة رسومية، لذلك قد لا تعرض رسائل في نافذة الأوامر. لمشاهدة الرسائل، شغّل `python seegha.py ...` من السورس.

## 🛠️ بناء البرنامج بنفسك

1. ارفع التغييرات إلى GitHub.
2. افتح **Actions** واختر **Build Seegha**.
3. نزّل ملفات البناء `Seegha` و`Seegha-Full` من Artifacts.
4. ارفع Tag مثل `v1.0.0` لنشر النسختين في Releases.

لتشغيل البرنامج من السورس:

```bash
pip install -r requirements.txt
python seegha.py
```

يجب أن يكون FFmpeg متاحًا في `PATH` أو موجودًا بجانب السكربت باسم `ffmpeg.exe`.

## 🔐 الأمان ومضادات الفيروسات وVirusTotal

السورس البرمجي وسير عمل البناء متاحان في هذا المستودع. وكما هو الحال مع أي ملف تنفيذي، يمكنك مراجعة السورس وفحص الملف إذا كانت لديك مخاوف.

- 🧾 قارن الملف الذي حمّلته مع `SHA256SUMS.txt` في صفحة Releases، إذا كان الملف متوفرًا.
- 🛡️ إذا كانت شهادة البناء متاحة، تحقّق منها باستخدام GitHub CLI:
  ```bash
  gh attestation verify Seegha.exe --repo <owner>/<repo>
  ```
- 🔎 يمكنك فحص الملف باستخدام [VirusTotal](https://www.virustotal.com/).

**تنبيهات مضادات الفيروسات:** قد تحصل البرامج المجمعة باستخدام PyInstaller، أو التي تفك أدوات مرفقة عند التشغيل، على إنذارات كاذبة أحيانًا. لكن لا تفترض تلقائيًا أن كل إنذار غير صحيح؛ راجع تفاصيل الكشف، وتحقق من مصدر الملف وبصمته، وأبلغ الشركة المطوّرة لمضاد الفيروسات إذا كنت تعتقد أن الكشف خاطئ.

صُمم Seegha لمعالجة الملفات التي تختارها، وحفظ بياناته في `%LOCALAPPDATA%\Seegha` والملفات المؤقتة في مجلد Temp، والاتصال بالإنترنت لتنزيل حزمة الذكاء الاصطناعي الاختيارية من GitHub عند الحاجة.

## 📄 الترخيص

- **كود Seegha:** ترخيص MIT — راجع [`LICENSE`](LICENSE).
- **المكونات المرفقة:** يتضمن البرنامج FFmpeg (GPLv3) ومكونات أخرى من جهات خارجية. راجع [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

---

<div align="center">

### 💚 Seegha (صيغة) — by R3D

**حوّل. حسّن. استمتع.**  
**Convert. Enhance. Enjoy.**

</div>
