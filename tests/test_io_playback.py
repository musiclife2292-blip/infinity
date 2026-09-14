import threading
import numpy as np
import pytest
import soundfile as sf
from infinity_audio.audio_io import read_audio,export_audio,resample
from infinity_audio.playback import BufferTransport
from infinity_audio.errors import AudioError,Cancelled


@pytest.mark.parametrize("extension,bits",[("wav",16),("wav",24),("wav",32),("flac",16),("flac",24),("mp3",24)])
def test_audio_roundtrip(tmp_path,tone,sr,extension,bits):
    path=tmp_path/("âm-thanh."+extension)
    export_audio(path,tone,sr,output_sr=48000,channels=2,bit_depth=bits,bitrate=192)
    y,out_sr=read_audio(path)
    assert out_sr==48000 and y.shape[1]==2
    assert abs(len(y)-len(tone)*2)<2304
    assert np.isfinite(y).all() and np.std(y)>.05
    info=sf.info(path)
    if extension!="mp3":
        expected=resample(tone,sr,48000)[:,0]
        assert np.max(abs(y[:,0]-expected))<(4e-5 if bits==16 else 3e-7)


def test_export_mono_and_rate(tmp_path,tone,sr):
    path=tmp_path/"mono.flac";export_audio(path,tone,sr,output_sr=44100,channels=1)
    x,rate=read_audio(path)
    assert rate==44100 and x.shape==(88200,1)


def test_error_corrupt_format_and_nonfinite(tmp_path):
    bad=tmp_path/"corrupt.wav";bad.write_bytes(b"corrupt audio")
    with pytest.raises(AudioError):read_audio(bad)
    with pytest.raises(AudioError):read_audio(tmp_path/"unknown.xyz")
    nan=tmp_path/"nan.wav";sf.write(nan,np.array([0,np.nan,.1]),48000,subtype="FLOAT")
    with pytest.raises(AudioError):read_audio(nan)


def test_export_refuses_overrange_and_collision(tmp_path,tone,sr):
    path=tmp_path/"a.wav"
    with pytest.raises(AudioError,match="vượt"):export_audio(path,tone*10,sr,output_sr=48000)
    assert not path.exists()
    export_audio(path,tone,sr,output_sr=48000)
    before=path.read_bytes()
    with pytest.raises(AudioError,match="tồn tại"):export_audio(path,tone,sr,output_sr=48000)
    assert path.read_bytes()==before


def test_export_cancel_atomic(tmp_path,tone,sr):
    path=tmp_path/"a.wav";export_audio(path,tone,sr,output_sr=48000);before=path.read_bytes()
    token=threading.Event();token.set()
    with pytest.raises(Cancelled):export_audio(path,tone,sr,output_sr=48000,cancel=token,overwrite=True)
    assert path.read_bytes()==before


def test_transport_eof_loop_and_mono():
    t=BufferTransport();data=np.arange(10,dtype=np.float32)[:,None]/20;t.set_buffer(data)
    out=np.empty((16,2),np.float32);t.read_into(out)
    np.testing.assert_array_equal(out[:10,0],data[:,0]);assert np.max(out[10:])==0 and not t.playing
    t.set_buffer(data,loop=True);t.read_into(out)
    np.testing.assert_array_equal(out[10:,0],data[:6,0]);assert t.playing and t.position==6
    stereo=np.column_stack([data[:,0],-data[:,0]]);t.set_buffer(stereo);t.mono=True;t.read_into(out)
    assert np.max(abs(out))==0


def test_playback_buffer_not_modify_or_nan(tone):
    t=BufferTransport();x=tone*20;before=x.copy();t.set_buffer(x)
    np.testing.assert_array_equal(x,before);assert abs(t.data).max()<=1
    with pytest.raises(AudioError):t.set_buffer(np.array([[np.nan]],np.float32))


def test_ai_missing_and_plugin_invalid_file(tmp_path):
    from infinity_audio import ai,plugins
    assert ai.STEMS["htdemucs"]==["drums","bass","other","vocals"]
    assert len(ai.STEMS["htdemucs_6s"])==6
    with pytest.raises(AudioError):plugins.run_plugin(tmp_path/"missing.vst3")
    with pytest.raises(AudioError):ai.separate("missing.npy",tmp_path,48000,tmp_path,name="unknown")


def test_scan_vst_bundles_and_fault_isolation(tmp_path):
    from infinity_audio import plugins
    (tmp_path/"broken.vst3").write_text("not a binary")
    bundle=tmp_path/"Bundle.vst3";bundle.mkdir();(bundle/"nested.vst3").write_text("internal")
    found=plugins.discover(tmp_path)
    assert len(found)==2
    with pytest.raises(AudioError):plugins.run_plugin(tmp_path/"broken.vst3",timeout=20)
