# Third-party inventory and distribution gates

Application source prepared under GPL-3.0-only. Full GPL text is in `LICENSE`. Synthetic fixtures and original application code were created for this project. This archive does not include a Windows installer, licensed model weights, external VST3 plugins or vendor certificates.

| Component | Pinned direct version | Upstream terms / role | Current distribution review |
|---|---|---|---|
| Python | 3.12 | PSF license; packaged only by a future Windows freeze | Bundle license and verify Windows runtime |
| PySide6 / Qt / Shiboken | 6.8.3 | LGPLv3/GPL alternatives/commercial; only Qt Core/Gui/Widgets used | Wheel metadata lacked notice files in this inventory; module/third-party notices and obligations remain release gate |
| NumPy | 2.2.4 | BSD-3-Clause; vendored BLAS libraries carry additional notices | Collected wheel notices; audit Windows binary closure |
| SciPy | 1.15.2 | BSD-3-Clause plus bundled library notices | Collected wheel notices; audit Windows binary closure |
| Pedalboard | 0.9.17 | GPLv3; includes JUCE and bundled code with its own notices | LICENSE/NOTICE included; provide corresponding source for redistributed GPL binaries |
| SoundFile | 0.13.1 | BSD-3-Clause wrapper; libsndfile LGPL | Wrapper/library notices collected; Windows codec binary provenance still requires review |
| sounddevice | 0.5.1 | MIT wrapper; PortAudio MIT-style | Windows PortAudio DLL not tested in this environment |
| librosa | 0.11.0 | ISC | Collected notices; dependencies inventoried |
| pyloudnorm | 0.1.1 | MIT | Collected notices; not a meter certification |
| PyInstaller | 6.12.0 | GPL with bundling exception | Build tool; no Windows binary produced in this session |
| NSIS | 3.x target | zlib/libpng, with other terms for optional compression; script selects zlib | Not installed/executed here |
| Demucs | optional future runtime | MIT source does not establish model-weight redistribution rights | No runtime/weights redistributed; model license and compatibility unresolved |
| VST3 plugins | none bundled | Each plugin vendor's terms apply | Scan/render adapter only; no vendor plugin redistributed |

`third_party_licenses/inventory.json` records the **resolved Linux dependency closure**, including transitive packages and their distributed notice files. It is not a Windows SBOM or a complete legal clearance. Package metadata can contain multiple licenses for vendored libraries. Do not strip those notices from a future binary release.

No FFmpeg binary is bundled or required by the application. The local validation script optionally used system `ffprobe` to inspect MP3 bitrates; runtime import/export uses libsndfile. Sample rate, PCM subtype and MP3 bitrate were verified on the tested libsndfile build; codecs must be rechecked in the Windows wheel.

If a closed-source product is required, the current GPL dependency choice needs to change or appropriate commercial permissions must be obtained. Merely hiding the Python source with PyInstaller does not change the license obligations.

Primary references checked 2026-09-14:

- [Qt for Python](https://doc.qt.io/qtforpython-6/), [Qt 6.8 licensing](https://doc.qt.io/qt-6.8/licensing.html)
- [Pedalboard source and notices](https://github.com/spotify/pedalboard)
- [SoundFile and libsndfile](https://python-soundfile.readthedocs.io/en/latest/)
- [sounddevice source](https://github.com/spatialaudio/python-sounddevice)
- [librosa source](https://github.com/librosa/librosa)
- [pyloudnorm source/license](https://github.com/csteinmetz1/pyloudnorm)
- [PyInstaller exception](https://pyinstaller.org/en/stable/license.html)
- [NSIS license](https://nsis.sourceforge.io/License)
- [Demucs source](https://github.com/facebookresearch/demucs), [upstream author discussion of weight rights](https://github.com/facebookresearch/demucs/issues/327)

Before release: archive exact Windows dependency hashes, all notices, GPL corresponding source/build information, approved AI model manifest/licenses, installer signing evidence and acceptance results. This file describes actual inventory and remaining work; it does not certify redistribution of unreviewed future components.
