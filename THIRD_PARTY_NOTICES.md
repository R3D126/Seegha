# Third-party software bundled in Seegha.exe

Seegha's own code (`seegha.py`) is MIT licensed (see `LICENSE`). The released
`Seegha.exe` additionally contains the programs below, each under its own licence.
FFmpeg is started as a separate command-line program; it is not linked into Seegha's code.

| Component | Version | Licence | Source / info |
|---|---|---|---|
| **FFmpeg** (Gyan.dev "essentials" Windows build, includes x264, libvpx, libopus, libmp3lame, libvorbis, libwebp, libaom) | 6.1.1 | **GPL v3** | Source: https://ffmpeg.org/releases/ffmpeg-6.1.1.tar.xz — build info: https://www.gyan.dev/ffmpeg/builds/ — release: https://github.com/GyanD/codexffmpeg/releases/tag/6.1.1 |
| **Real-ESRGAN ncnn Vulkan** (executable + models) | 20220424 | MIT (ncnn-vulkan), BSD-3-Clause (Real-ESRGAN models) | https://github.com/xinntao/Real-ESRGAN-ncnn-vulkan , https://github.com/xinntao/Real-ESRGAN |
| ncnn (inside the Real-ESRGAN executable) | — | BSD-3-Clause | https://github.com/Tencent/ncnn |
| Pillow | 10.4.0 | HPND | https://python-pillow.org |
| tkinterdnd2 / tkdnd | 0.6.4 | MIT / BSD-style | https://github.com/Eliav2/tkinterdnd2 |
| Python | 3.8.10 | PSF License | https://www.python.org |
| PyInstaller (bootloader) | 5.13.2 | GPLv2+ with an exception that allows distributing the built program under any licence | https://pyinstaller.org |

## FFmpeg (GPL v3) — your rights
The FFmpeg binary inside `Seegha.exe` is licensed under the GNU General Public
License v3. You may obtain the complete corresponding source code of that exact
version from the link above, and you may replace the bundled `ffmpeg.exe` with your own build.
The full licence text: https://www.gnu.org/licenses/gpl-3.0.html

## Real-ESRGAN
Models and executable are used unmodified. Please keep the original copyright
notices if you redistribute them.

*This file is informational and is not legal advice.*
