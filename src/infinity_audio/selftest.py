"""Exercise the installed application, including lazy native imports.

This diagnostic deliberately uses an in-memory playback sink. It verifies
the playback route without claiming that CI has listened through a device.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import sys
import tempfile
import time
import traceback

import numpy as np
from PySide6.QtCore import QSettings

from . import __version__, dsp, plugins, render
from .audio_io import export_audio, read_audio
from .errors import AudioError
from .model import Session, atomic_json


def run(app, report_path):
    from .app import MainWindow

    report_path = Path(report_path).resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    result = {
        "schema": 1,
        "date_utc": datetime.now(timezone.utc).isoformat(),
        "version": __version__,
        "platform": platform.platform(),
        "python": sys.version,
        "frozen": bool(getattr(sys, "frozen", False)),
        "executable": sys.executable,
        "audio_hardware_verified": False,
        "playback_sink": "memory buffer",
        "checks": [],
        "passed": False,
    }
    window = None
    errors = []

    def check(name, condition, **details):
        result["checks"].append({"name": name, "passed": bool(condition), **details})
        if not condition:
            raise AssertionError(name)

    def settle():
        deadline = time.monotonic() + 120
        while window.jobs.busy and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(.005)
        app.processEvents()
        if window.jobs.busy:
            window.cancel_job()
            raise TimeoutError("Background job did not finish within 120 seconds")
        if errors:
            raise RuntimeError("; ".join(map(str, errors)))

    try:
        with tempfile.TemporaryDirectory(prefix="infinity-selftest-") as tmp:
            base = Path(tmp)
            QSettings.setDefaultFormat(QSettings.Format.IniFormat)
            QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(base / "settings"))
            window = MainWindow(base / "app", recover=False)
            window.confirm_discard = lambda: True
            window.show_error = errors.append
            window.jobs.failed.disconnect()
            window.jobs.failed.connect(errors.append)

            def play_buffer(data, sr, loop=False):
                window.player.transport.set_buffer(data, loop)
                window.player.sr = sr

            window.player.play = play_buffer
            window.show()
            app.processEvents()
            sr = 48000
            t = np.arange(sr * 2) / sr
            audio = (.12 * np.sin(2 * np.pi * 440 * t) + .06 * np.sin(2 * np.pi * 1200 * t))[:, None].astype(np.float32)
            source = base / "Giọng hát nguồn.wav"
            export_audio(source, audio, sr, bit_depth=32, channels=1)
            original_hash = hashlib.sha256(source.read_bytes()).hexdigest()
            window.import_paths([str(source)])
            settle()
            check("ui_import_unicode_path", len(window.session.state["tracks"]) == 1 and window.selected_id is not None)
            cid = window.selected_id
            before = window.session.clip_audio(cid).copy()
            window.effect_combo.setCurrentIndex(window.effect_combo.findData("eq"))
            window.param_fields["mid_db"].setValue(-9)
            window.process_clip(False)
            settle()
            check("ui_preview_ab", window.preview is not None and window.player.transport.playing)
            check("preview_is_non_destructive", np.array_equal(before, window.session.clip_audio(cid)))
            check("preview_changes_audio", float(np.std(window.preview["after"] - window.preview["before"])) > .001)
            window.process_clip(True)
            settle()
            processed = window.session.clip_audio(cid).copy()
            check("ui_apply", not np.array_equal(processed, before))
            window.undo()
            check("ui_undo", np.array_equal(before, window.session.clip_audio(cid)))
            window.redo()
            check("ui_redo", np.array_equal(processed, window.session.clip_audio(cid)))
            window.timeline.cursor = .75
            window.split_clip()
            check("ui_split_clip", len(window.session.state["tracks"][0]["clips"]) == 2)
            window.view_combo.setCurrentIndex(1)
            settle()
            check("ui_spectrogram", bool(window.timeline.images))
            mixed = render.render(window.session)
            project = base / "Dự án kiểm thử.infinity"
            window.session.save(project)
            opened = Session.load(project, base / "reopened")
            check("project_roundtrip", np.array_equal(mixed, render.render(opened)))
            window.session.autosave()
            recovered = Session.recover(window.session.root)
            check("autosave_recovery", recovered.state == window.session.state)
            for suffix, bits in [("wav", 24), ("flac", 24), ("mp3", 24)]:
                out = base / ("Kết quả." + suffix)
                export_audio(out, mixed, sr, bit_depth=bits, channels=2)
                decoded, rate = read_audio(out)
                check("codec_" + suffix, rate == sr and decoded.shape[1] == 2 and abs(len(decoded) - len(mixed)) < 2304 and np.isfinite(decoded).all() and float(np.std(decoded)) > .01)
            shifted = dsp.apply_effect(audio, sr, {"kind": "pitch", "params": {"semitones": 12}})
            peak_hz = np.argmax(np.abs(np.fft.rfft(shifted[2000:-2000, 0]))) * sr / (len(shifted) - 4000)
            check("frozen_librosa_pitch", shifted.shape == audio.shape and abs(peak_hz - 880) < 5, peak_hz=float(peak_hz))
            meter = dsp.meters(mixed, sr)
            check("frozen_loudness", bool(meter) and all(np.isfinite(v) for v in meter.values() if isinstance(v, (float, int))), values=meter)
            malformed = base / "broken.vst3"
            malformed.write_text("invalid plugin", encoding="utf-8")
            rejected = False
            try:
                plugins.run_plugin(malformed, timeout=30)
            except AudioError:
                rejected = True
            check("plugin_failure_isolation", rejected)
            check("source_unchanged", original_hash == hashlib.sha256(source.read_bytes()).hexdigest())
            status = json.loads((Path(__file__).parent / "feature_status.json").read_text(encoding="utf-8"))
            check("bundled_feature_matrix", len(status) == 47)
            window.set_theme(True)
            app.processEvents()
            check("light_theme", window.timeline.light)
            window.set_theme(False)
            app.processEvents()
            check("dark_theme", not window.timeline.light)
            image = window.grab()
            check("ui_screenshot", image.save(str(report_path.with_suffix(".png"))))
            try:
                import sounddevice as sd
                devices = str(sd.query_devices())
                check("portaudio_library_loaded", True, devices=devices)
            except (ImportError, OSError) as exc:
                if sys.platform == "win32":
                    raise
                result["audio_backend_note"] = str(exc)
            window.close()
            app.processEvents()
            window = None
            result["passed"] = True
    except Exception:
        result["error"] = traceback.format_exc()
    finally:
        if window is not None and not window.jobs.busy:
            window.close()
            app.processEvents()
        atomic_json(report_path, result)
    return 0 if result["passed"] else 1
