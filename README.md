# محول الملفات (File Converter)

يحوّل الصور (png / jpg / webp / bmp / gif / tiff / ico) والفيديو (mp4 / mkv / webm / avi / mov / gif) والصوت (mp3 / wav / flac / aac / ogg / m4a).
واجهة رسومية مع سحب وإفلات، ويشتغل كذلك من سطر الأوامر.

## الحصول على الـ exe
1. ارفع هذي الملفات على مستودع GitHub.
2. روح تبويب **Actions** وانتظر يخلص البناء (دقيقتين تقريباً).
3. افتح آخر تشغيل ونزّل **FileConverter** من قسم Artifacts، فيه `FileConverter.exe`.

لإصدار رسمي في تبويب Releases: سوّ tag يبدأ بـ `v`، مثل `v1.0`، والـ exe ينرفع تلقائياً.

## التشغيل بدون exe
```
pip install pillow tkinterdnd2
python converter.py
python converter.py -t jpg *.png
```
ملاحظة: الفيديو والصوت يحتاجون ffmpeg (`winget install Gyan.FFmpeg`) أو حط `ffmpeg.exe` جنب `converter.py`.
الـ exe الجاهز يحتوي ffmpeg داخله.
