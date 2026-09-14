import copy
import time
from pathlib import Path
import numpy as np
import pytest
import soundfile as sf
from PySide6.QtCore import Qt,QPoint,QTimer
from PySide6.QtTest import QTest
from infinity_audio.app import MainWindow
from infinity_audio.model import Session
from infinity_audio.audio_io import export_audio,read_audio
from infinity_audio import render

pytestmark=pytest.mark.gui


def settle(qapp,window,timeout=30):
    until=time.monotonic()+timeout
    while window.jobs.busy and time.monotonic()<until:
        qapp.processEvents();QTest.qWait(10)
    qapp.processEvents()
    assert not window.jobs.busy,"Background job failed to finish in time"


def test_desktop_import_edit_preview_save_reopen_export(qapp,tmp_path,tone,sr):
    w=MainWindow(tmp_path/"app",recover=False);errors=[];w.show_error=lambda e:errors.append(e)
    w.jobs.failed.disconnect();w.jobs.failed.connect(w.show_error)
    w.confirm_discard=lambda:True
    # Exercise UI playback dispatch without pretending there is an audio device.
    def mock_play(x,rate,loop=False):
        w.player.transport.set_buffer(x,loop);w.player.sr=rate
    w.player.play=mock_play
    w.show();qapp.processEvents()
    source=tmp_path/"Giọng hát.wav";sf.write(source,tone,sr,subtype="FLOAT");source_bytes=source.read_bytes()
    w.import_paths([str(source)]);settle(qapp,w)
    assert len(w.session.state["tracks"])==1 and w.file_list.count()==1
    cid=w.selected_id;assert cid
    c=w.selected()[1]
    rect=w.timeline.clip_rect(0,c)
    QTest.mouseDClick(w.timeline,Qt.MouseButton.LeftButton,pos=QPoint(int(rect.center().x()),int(rect.center().y())))
    assert w.timeline.region[1]>1.9
    w.effect_combo.setCurrentIndex(w.effect_combo.findData("eq"));w.param_fields["mid_db"].setValue(-6)
    w.process_clip(False);settle(qapp,w)
    assert w.preview and w.player.transport.playing
    before=w.session.clip_audio(cid).copy()
    assert np.std(w.preview["after"]-w.preview["before"])>.005
    w.process_clip(True);settle(qapp,w)
    processed=w.session.clip_audio(cid).copy();assert not np.array_equal(processed,before)
    w.undo();np.testing.assert_array_equal(w.session.clip_audio(cid),before)
    w.redo();np.testing.assert_array_equal(w.session.clip_audio(cid),processed)
    w.timeline.cursor=.75;w.split_clip();assert len(w.selected()[0]["clips"])==2
    w.timeline.region=(0,0);w.play();settle(qapp,w);assert w.player.transport.playing
    w.stop()
    path=tmp_path/"Dự án.infinity";w.session.save(path)
    loaded=Session.load(path,tmp_path/"opened")
    np.testing.assert_array_equal(render.render(loaded),render.render(w.session))
    out=tmp_path/"mix.flac";export_audio(out,render.render(loaded),48000)
    decoded,rate=read_audio(out);assert rate==48000 and len(decoded)==96000
    assert source.read_bytes()==source_bytes
    w.set_theme(True);qapp.processEvents();assert w.timeline.light
    w.set_theme(False);qapp.processEvents();assert not w.timeline.light
    assert not errors,errors
    w.close()


def test_gui_thread_progress_cancellation_keeps_model(qapp,tmp_path):
    w=MainWindow(tmp_path/"app",recover=False);w.confirm_discard=lambda:True
    w.show();qapp.processEvents();before=copy.deepcopy(w.session.state);committed=[];beats=[]
    heartbeat=QTimer();heartbeat.timeout.connect(lambda:beats.append(time.monotonic()));heartbeat.start(5)
    def heavy(cancel,progress):
        for i in range(200):
            if cancel.is_set():return "cancelled"
            progress(i/200,"test work");time.sleep(.005)
        return "done"
    w.run_task("Test",heavy,lambda result:committed.append(result))
    QTest.qWait(70);w.cancel_job();settle(qapp,w)
    assert len(beats)>2 and not committed and w.session.state==before
    assert w.splitter.isEnabled() and not w.cancel_btn.isEnabled()
    heartbeat.stop();w.close()


def test_gui_spectrogram_and_direct_spectral_selection(qapp,tmp_path,tone):
    w=MainWindow(tmp_path/"app",recover=False);w.confirm_discard=lambda:True
    w.session.add_track(tone,"Vocal");w.refresh();w.show();qapp.processEvents()
    w.view_combo.setCurrentIndex(1);settle(qapp,w)
    assert w.selected_id in w.timeline.images
    w.spectral_region(.2,.6,1000,3000)
    assert w.effect()["kind"]=="spectral"
    assert w.param_fields["end"].value()==pytest.approx(.4)
    assert w.param_fields["low_hz"].value()==1000
    w.close()


def test_gui_comping_and_copy_paste(qapp,tmp_path,tone):
    w=MainWindow(tmp_path/"app",recover=False);w.confirm_discard=lambda:True
    w.session.add_track(tone,"Take 1");w.refresh()
    w.copy_clip();w.timeline.cursor=1.5;w.paste_clip();assert len(w.session.state["tracks"][0]["clips"])==2
    w.timeline.region=(.1,.5);w.comp_selection();assert w.session.state["tracks"][-1]["name"]=="Comp vocal"
    assert w.session.state["tracks"][-1]["clips"][0]["length"]==pytest.approx(.4)
    w.close()


def test_gui_save_and_export_actions(qapp,tmp_path,tone,monkeypatch):
    from PySide6.QtWidgets import QFileDialog,QDialog
    import infinity_audio.app as module
    w=MainWindow(tmp_path/"app",recover=False);w.confirm_discard=lambda:True
    errors=[];w.jobs.failed.disconnect();w.jobs.failed.connect(errors.append)
    w.session.add_track(tone,"Vocal");w.refresh()
    project=tmp_path/"ui-saved.infinity"
    monkeypatch.setattr(QFileDialog,"getSaveFileName",lambda *args,**kwargs:(str(project),""))
    w.save_dialog();settle(qapp,w);assert project.exists() and w._saved_revision==w.session.revision
    class FakeExport:
        def __init__(self,*args):self.format=type("Format",(),{"currentText":lambda s:"FLAC"})()
        def exec(self):return QDialog.DialogCode.Accepted
        def options(self):return {"output_sr":48000,"bit_depth":24,"bitrate":192,"channels":2}
    monkeypatch.setattr(module,"ExportDialog",FakeExport)
    output=tmp_path/"ui-export.flac"
    monkeypatch.setattr(QFileDialog,"getSaveFileName",lambda *args,**kwargs:(str(output),""))
    w.export_dialog();settle(qapp,w);assert output.exists()
    w.open_path(project);settle(qapp,w);assert w.session.state["tracks"][0]["name"]=="Vocal"
    assert not errors,errors
    w.close()
