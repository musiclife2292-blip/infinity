import copy,json,threading,zipfile
from pathlib import Path
import numpy as np
import pytest
from infinity_audio.model import Session,checksum,track,clip
from infinity_audio import render
from infinity_audio.errors import AudioError,Cancelled


def test_edit_save_reopen_export_equivalent(session,tone,tmp_path):
    tid,cid=session.add_track(tone,"Giọng hát tiếng Việt")
    session.split(cid,.7)
    second=session.state["tracks"][0]["clips"][1]
    session.move(second["id"],1.)
    session.duplicate(cid,2.5)
    session.fade(cid,.05,.1)
    session.set_track(tid,gain_db=-6,pan=-.25)
    expected=render.render(session)
    path=tmp_path/"âm-thanh.infinity";session.save(path)
    reopened=Session.load(path,tmp_path/"reopened")
    np.testing.assert_array_equal(render.render(reopened),expected)
    assert reopened.state==session.state
    assert len(reopened.history)==len(session.history)
    assert reopened.undo() and reopened.redo()
    np.testing.assert_array_equal(render.render(reopened),expected)


def test_undo_redo_branch_and_assets_immutable(session,tone):
    _,cid=session.add_track(tone,"Take 1");source=session.find_clip(cid)[1]["asset"];before=checksum(session.assets/source)
    session.replace_audio(cid,tone*.5,"Giảm âm")
    assert session.undo();np.testing.assert_array_equal(session.clip_audio(cid),tone)
    assert session.redo();np.testing.assert_array_equal(session.clip_audio(cid),tone*.5)
    session.undo();session.move(cid,.2)
    assert not session.redo()
    assert checksum(session.assets/source)==before


def test_recovery_after_unclean_exit_and_saved_history(session,tone):
    _,cid=session.add_track(tone,"Thu âm")
    session.split(cid,.5)
    recovered=Session.recover(session.root)
    assert recovered.state==session.state
    assert recovered.undo() and len(recovered.state["tracks"][0]["clips"])==1


def test_atomic_save_failure_keeps_previous_file(session,tone,tmp_path,monkeypatch):
    import infinity_audio.model as model
    _,cid=session.add_track(tone,"A")
    path=tmp_path/"test.infinity";session.save(path);before=checksum(path)
    session.move(cid,1)
    real=model.os.replace
    def fail(src,dst):
        if Path(dst)==path:raise OSError("disk failure")
        return real(src,dst)
    monkeypatch.setattr(model.os,"replace",fail)
    with pytest.raises(OSError):session.save(path)
    assert checksum(path)==before
    assert not list(tmp_path.glob("*.tmp"))


def test_cancelled_save_keeps_previous_file(session,tone,tmp_path):
    session.add_track(tone,"A");path=tmp_path/"test.infinity";session.save(path);before=checksum(path)
    token=threading.Event();token.set()
    with pytest.raises(Cancelled):session.save(path,token)
    assert checksum(path)==before


def test_failed_autosave_rolls_back_model(session,tone,monkeypatch):
    _,cid=session.add_track(tone,"A");before=copy.deepcopy(session.state)
    def fail(*args,**kwargs):raise OSError("out of space")
    monkeypatch.setattr(session,"autosave",fail)
    with pytest.raises(OSError):session.move(cid,1)
    assert session.state==before


@pytest.mark.parametrize("name",["../outside.npy","/tmp/escape.npy","assets/../../../escape","assets/not-a-hash.npy"])
def test_archive_path_validation(tmp_path,name):
    path=tmp_path/"attack.infinity"
    with zipfile.ZipFile(path,"w") as z:
        z.writestr("project.json","{}");z.writestr(name,b"fake")
    with pytest.raises(AudioError):Session.load(path,tmp_path/"dest")
    assert not (tmp_path/"outside.npy").exists()


def test_asset_tampering_detected(session,tone,tmp_path):
    session.add_track(tone,"A");path=tmp_path/"test.infinity";session.save(path)
    corrupted=tmp_path/"bad.infinity"
    with zipfile.ZipFile(path) as src,zipfile.ZipFile(corrupted,"w") as dst:
        for name in src.namelist():
            data=src.read(name)
            if name.startswith("assets/"):data=data[:-1]+bytes([data[-1]^1])
            dst.writestr(name,data)
    with pytest.raises(AudioError,match="Checksum"):Session.load(corrupted,tmp_path/"dest")


def test_invalid_state_rejected_without_edit(session,tone):
    tid,_=session.add_track(tone,"A");before=copy.deepcopy(session.state)
    with pytest.raises(AudioError):session.set_track(tid,pan=float("nan"))
    assert session.state==before


def test_solo_mute_pan_gain_automation(session,tone):
    a,_=session.add_track(tone,"A");b,_=session.add_track(tone,"B")
    session.set_track(a,solo=True,pan=-1,gain_db=-6)
    y=render.render(session)
    np.testing.assert_allclose(y[:,0],tone[:,0]*10**(-6/20),atol=1e-6)
    assert np.max(abs(y[:,1]))==0
    session.set_track(a,automation={"gain_db":[[0,-20],[2,0]],"pan":[[0,-1],[2,1]]})
    z=render.render(session)
    assert np.std(z[:2400,0])>np.std(z[:2400,1])
    assert np.std(z[-2400:,1])>np.std(z[-2400:,0])
    session.set_track(a,mute=True)
    assert np.max(abs(render.render(session)))==0


def test_fade_split_and_trim_samples(session,tone):
    _,cid=session.add_track(tone,"A");session.split(cid,.5)
    # Adjacent splits reconstruct the original sample sequence.
    np.testing.assert_array_equal(render.render(session)[:,0],tone[:,0])
    session.fade(cid,.1,.1);y=render.render(session)
    assert np.std(y[:1200,0])<np.std(tone[:1200,0])*.5
    session.trim(cid,.1,.3)
    assert session.find_clip(cid)[1]["offset"]==.1


def test_render_range_equals_full_slice(session,tone):
    tid,_=session.add_track(tone,"A")
    session.set_track(tid,effects=[{"kind":"delay","params":{}}])
    full=render.render(session);part=render.render(session,start=.5,end=1.2)
    np.testing.assert_array_equal(part,full[12000:28800])


def test_track_count_guard_and_automation_order(session,tone):
    tid,_=session.add_track(tone,"A")
    with pytest.raises(AudioError):session.set_track(tid,automation={"pan":[[1,0],[1,.5]]})
    with pytest.raises(AudioError):session.set_track(tid,automation={"unknown":[[1,0]]})


def test_render_resource_guard(session,tone):
    _,cid=session.add_track(tone,"A");session.move(cid,20000)
    with pytest.raises(AudioError,match="ngân sách"):render.render(session)


@pytest.mark.slow
def test_32_track_deterministic_sum(session,tone):
    for i in range(32):session.add_track(tone*.01,f"Track {i+1}")
    y=render.render(session)
    np.testing.assert_allclose(y[:,0],tone[:,0]*.32,atol=2e-7)
    assert len(session.all_assets())==1


def test_recovery_after_process_abrupt_exit(tmp_path):
    import os,sys,subprocess
    root=Path(__file__).resolve().parents[1]
    code="""import sys,os,numpy as np
from infinity_audio.model import Session
s=Session(sys.argv[1],24000)
_,c=s.add_track(np.full((2400,1),.2,np.float32),'Take trước crash')
s.move(c,.75)
os._exit(7)
"""
    env=os.environ.copy();env["PYTHONPATH"]=str(root/"src")
    process=subprocess.run([sys.executable,"-c",code,str(tmp_path/"crash")],env=env,capture_output=True)
    assert process.returncode==7
    recovered=Session.recover(tmp_path/"crash")
    assert recovered.state["tracks"][0]["clips"][0]["start"]==.75
    assert recovered.undo()
    assert recovered.state["tracks"][0]["clips"][0]["start"]==0


def test_marker_structure_survives_roundtrip(session,tone,tmp_path):
    session.add_track(tone,"A")
    session.commit("Sections",lambda s:s["markers"].extend([{"time":0,"name":"Intro"},{"time":1,"name":"Verse"},{"time":1.5,"name":"Chorus"}]))
    p=tmp_path/"sections.infinity";session.save(p)
    restored=Session.load(p,tmp_path/"restored")
    assert restored.state["markers"]==session.state["markers"]
