"""Exercise the installed application, including lazy native imports.

This diagnostic deliberately uses an in-memory playback sink. It verifies
the playback route without claiming that CI has listened through a device.
"""
from datetime import datetime, timezone
import hashlib
import json
import os
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
            detuned=(.2*np.sin(2*np.pi*452*np.arange(sr*2)/sr))[:,None].astype(np.float32)
            corrected=dsp.apply_effect(detuned,sr,{"kind":"autotune","params":{"amount":100,"tolerance":0}})
            stable=corrected[sr//2:,0]
            corrected_hz=float(np.argmax(np.abs(np.fft.rfft(stable*np.hanning(len(stable)))))*sr/len(stable))
            check("frozen_monophonic_pitch", corrected.shape==detuned.shape and
                  np.isfinite(corrected).all() and abs(corrected_hz-440)<3,
                  input_hz=452,output_hz=corrected_hz)
            meter = dsp.meters(mixed, sr)
            check("frozen_loudness", bool(meter) and all(np.isfinite(v) for v in meter.values() if isinstance(v, (float, int))), values=meter)
            steps=np.concatenate([np.full(sr,.001),np.full(sr,.2),np.full(sr,.001)])[:,None].astype(np.float32)
            expanded=dsp.apply_effect(steps,sr,{"kind":"expander","params":{
                "threshold_db":-35,"ratio":4,"floor_db":-36,"attack_ms":2,"release_ms":500}})
            check("expander_attack_release", float(expanded[0,0]/steps[0,0])<.02 and
                  float(expanded[round(1.02*sr),0]/steps[round(1.02*sr),0])>.98 and
                  float(expanded[round(2.1*sr),0]/steps[round(2.1*sr),0])>.75)
            malformed = base / "broken.vst3"
            malformed.write_text("invalid plugin", encoding="utf-8")
            rejected = False
            try:
                plugins.run_plugin(malformed, timeout=30)
            except AudioError:
                rejected = True
            check("plugin_failure_isolation", rejected)
            fixture = os.environ.get("INFINITY_TEST_VST3")
            if fixture:
                # CI supplies an explicitly selected, pinned CHOWTapeModel
                # fixture. It is never installed with the application.
                fixture = Path(fixture).resolve()
                discovered = {Path(value).resolve() for value in plugins.discover(fixture.parent)}
                check("vst3_discovery", fixture in discovered,
                      discovered_plugins=[str(value) for value in sorted(discovered)])
                info = plugins.run_plugin(fixture, timeout=45)
                # The pinned Windows fixture labels this parameter "Output
                # Gain [dB]", while the Linux fixture uses "Output Gain".
                # Keep the actual host key for editing and project recall.
                gain_keys = [key for key in ("output_gain", "output_gain_db")
                             if key in info["parameters"]]
                check("vst3_load", len(gain_keys) == 1 and bool(info["state"]),
                      parameter_names=sorted(info["parameters"]),
                      state_bytes_base64=len(info["state"]))
                gain_key = gain_keys[0]
                params = {k: False for k in info["parameters"] if k.endswith("on_off")}
                params[gain_key] = -9.0
                plugin_input = np.repeat(audio, 2, axis=1)
                in_path, out_path = base / "plugin-input.npy", base / "plugin-output.npy"
                np.save(in_path, plugin_input, allow_pickle=False)
                info = plugins.run_plugin(fixture, params=params, input_path=in_path,
                                          output_path=out_path, sr=sr, timeout=60)
                effected = np.load(out_path, allow_pickle=False)
                check("vst3_render", effected.shape == plugin_input.shape and
                      np.isfinite(effected).all() and float(np.std(effected)) > .001 and
                      float(np.std(effected - plugin_input)) > .01)
                plugin_session = Session(base / "plugin-session", sr)
                _, plugin_cid = plugin_session.add_track(effected, "VST3 fixture")
                plugin_session.commit("Lưu trạng thái VST3", lambda state:
                    plugin_session.find_clip(plugin_cid, state)[1].update(plugin_state=info))
                plugin_project = base / "Plugin.infinity"
                plugin_session.save(plugin_project)
                recalled = Session.load(plugin_project, base / "plugin-reopened")
                state = recalled.find_clip(plugin_cid)[1]["plugin_state"]
                check("vst3_project_state", state == info)
                from .dialogs import PluginDialog
                saved_params=dict(state["parameters"])
                dialog=PluginDialog(previous=state)
                edited_params=dict(saved_params)
                edited_params[gain_key]=-12.0
                dialog.params.setPlainText(json.dumps(edited_params))
                dialog.apply()
                check("vst3_dialog_preserves_project", state["parameters"]==saved_params and
                      dialog.info["parameters"][gain_key]==-12.0)
                dialog.close()
                recall_path = base / "plugin-recalled.npy"
                recalled_info = plugins.run_plugin(fixture, params=state["parameters"], state=state["state"],
                    input_path=in_path, output_path=recall_path, sr=sr, timeout=60)
                recalled_audio = np.load(recall_path, allow_pickle=False)
                # The plugin smooths a freshly changed gain at startup. Raw
                # state restores parameters, not the transient delay buffers.
                steady_error = float(np.max(np.abs(effected[sr:] - recalled_audio[sr:])))
                check("vst3_state_and_parameters_recall", steady_error < 1e-5 and
                      abs(recalled_info["parameters"][gain_key] + 9) < .01,
                      steady_state_max_error=steady_error,
                      recalled_gain=recalled_info["parameters"][gain_key])
                result["vst3_fixture"] = {"path": str(fixture), "name": "CHOWTapeModel",
                    "gain_parameter": gain_key,
                    "state_bytes_base64": len(info["state"]),
                    "sha256": hashlib.sha256(fixture.read_bytes()).hexdigest() if fixture.is_file() else None}
            check("source_unchanged", original_hash == hashlib.sha256(source.read_bytes()).hexdigest())
            status = json.loads((Path(__file__).parent / "feature_status.json").read_text(encoding="utf-8"))
            check("bundled_feature_matrix", len(status) == 47)
            window.set_theme(True)
            app.processEvents()
            check("light_theme", window.timeline.light)
            window.set_theme(False)
            app.processEvents()
            check("dark_theme", not window.timeline.light)
            window.resize(1180,760)
            parameter_layouts=[]
            for effect in ("eq","expander","spectral","compressor"):
                window.effect_combo.setCurrentIndex(window.effect_combo.findData(effect))
                app.processEvents()
                visible=True
                for field in window.param_fields.values():
                    window.effect_scroll.ensureWidgetVisible(field,0,0)
                    app.processEvents()
                    center=field.mapTo(window.effect_scroll.viewport(),field.rect().center())
                    visible=visible and field.height()>=field.minimumSizeHint().height() and \
                        window.param_widget.rect().contains(field.geometry()) and \
                        window.effect_scroll.viewport().rect().contains(center)
                parameter_layouts.append({"effect":effect,"accessible":bool(visible),"fields":len(window.param_fields)})
            check("effect_controls_accessible", all(x["accessible"] for x in parameter_layouts),
                  layouts=parameter_layouts,window_size=[window.width(),window.height()])
            window.effect_combo.setCurrentIndex(window.effect_combo.findData("eq"))
            app.processEvents()
            window.effect_scroll.verticalScrollBar().setValue(0)
            app.processEvents()
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
