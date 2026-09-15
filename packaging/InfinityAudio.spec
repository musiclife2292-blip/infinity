# Run on Windows x64 with .venv\Scripts\python -m PyInstaller packaging\InfinityAudio.spec
from pathlib import Path
from importlib.util import find_spec
from PyInstaller.utils.hooks import collect_all, collect_data_files, copy_metadata

root = Path(SPECPATH).parent
datas = [(str(root / "docs"), "docs"), (str(root / "LICENSE"), "."),
         (str(root / "THIRD_PARTY_NOTICES.md"), "."),
         (str(root / "third_party_licenses"), "third_party_licenses"),
         (str(root / "docs" / "feature_status.json"), "infinity_audio")]
binaries = []
hiddenimports = ["scipy.signal", "scipy.interpolate", "scipy.ndimage", "sounddevice",
                 "soundfile", "pyloudnorm", "pedalboard", "librosa", "numpy"]
for name in ["pedalboard", "librosa", "pyloudnorm", "_soundfile_data", "_sounddevice_data"]:
    if find_spec(name) is not None:
        d, b, h = collect_all(name)
        datas += d
        binaries += b
        hiddenimports += h
for name in ["librosa", "soundfile", "sounddevice", "pedalboard", "pyloudnorm", "numpy", "scipy"]:
    datas += copy_metadata(name)

# librosa loads scikit-learn lazily. Include its native utility explicitly
# so pitch/tempo processing is available in the frozen application.
hiddenimports += ["sklearn._cyutility"]

a = Analysis([str(root / "launch.py")], pathex=[str(root / "src")], binaries=binaries,
             datas=datas, hiddenimports=hiddenimports,
             excludes=["torch", "demucs", "tkinter", "PyQt5", "PyQt6", "matplotlib", "IPython"],
             noarchive=False)
# JIT caches are generated for one compiler/process/CPU environment. They
# must not travel from the build environment into the installed application.
a.datas = [entry for entry in a.datas if not entry[0].lower().endswith((".nbc", ".nbi"))]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="InfinityAudio",
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False, icon=str(root / "assets" / "infinity.ico"))
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="InfinityAudio")
