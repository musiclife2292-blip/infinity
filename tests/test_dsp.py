import threading
import numpy as np
import pytest
from infinity_audio import dsp
from infinity_audio.errors import AudioError,Cancelled


def tone_at(hz,sr,n,level=.2):return (level*np.sin(2*np.pi*hz*np.arange(n)/sr))[:,None].astype(np.float32)


def power_at(x,sr,hz):
    x=np.asarray(x).reshape(-1)
    return abs(np.dot(x,np.exp(-2j*np.pi*hz*np.arange(len(x))/sr)))*2/len(x)


def peak_hz(x,sr):
    y=x[:,0]*np.hanning(len(x))
    return np.argmax(abs(np.fft.rfft(y)))*sr/len(x)


@pytest.mark.parametrize("kind",list(dsp.EFFECTS))
def test_processors_return_audio_without_mutating_input(kind,tone,sr):
    original=tone.copy()
    result=dsp.apply_effect(tone,sr,{"kind":kind,"params":{}})
    assert np.array_equal(tone,original)
    assert result.dtype==np.float32 and result.shape[1]==1 and np.isfinite(result).all()
    assert len(result)==len(tone)


def test_dehum_attenuates_50_and_harmonics_preserves_voice(sr):
    x=tone_at(50,sr,3*sr,.1)+tone_at(100,sr,3*sr,.08)+tone_at(997,sr,3*sr,.2)
    y=dsp.apply_effect(x,sr,{"kind":"dehum"})[sr:]
    assert power_at(y,sr,50)<.01
    assert power_at(y,sr,100)<.008
    assert power_at(y,sr,997)>.18


def test_declick_reduces_impulse_error(sr):
    clean=tone_at(300,sr,sr,.2);damaged=clean.copy();damaged[4000]=.9;damaged[11001]=-.9
    repaired=dsp.apply_effect(damaged,sr,{"kind":"declick"})
    assert np.mean((repaired-clean)**2)<np.mean((damaged-clean)**2)*.2


def test_declip_reduces_clipped_sine_mse(sr):
    clean=tone_at(440,sr,sr,1.1);damaged=np.clip(clean,-.8,.8)
    repaired=dsp.apply_effect(damaged,sr,{"kind":"declip","params":{"threshold":.799}})
    assert np.mean((repaired-clean)**2)<np.mean((damaged-clean)**2)*.5


def test_noise_reduction_improves_snr_on_gated_harmonics(sr):
    rng=np.random.default_rng(3);t=np.arange(sr*4)/sr
    gate=((t%1)>.35)*np.sin(np.pi*np.clip((t%1-.35)/.65,0,1))**2
    clean=(gate*(.2*np.sin(2*np.pi*190*t)+.08*np.sin(2*np.pi*570*t)))[:,None].astype(np.float32)
    noisy=clean+rng.normal(0,.03,clean.shape).astype(np.float32)
    out=dsp.apply_effect(noisy,sr,{"kind":"denoise","params":{"amount":65}})
    assert np.mean((out-clean)**2)<np.mean((noisy-clean)**2)*.8


def test_spectral_selected_frequency_and_time(sr):
    a=tone_at(500,sr,3*sr,.2);b=tone_at(3000,sr,3*sr,.15);x=a+b
    y=dsp.apply_effect(x,sr,{"kind":"spectral","params":{"start":1,"end":2,"low_hz":2800,"high_hz":3200,"reduction_db":40}})
    mid=y[int(1.1*sr):int(1.9*sr)]
    assert power_at(mid,sr,3000)<.02
    assert power_at(mid,sr,500)>.18
    assert np.mean((y[:sr//2]-x[:sr//2])**2)<1e-6


def test_bass_increases_low_relative_to_mid(sr):
    x=tone_at(60,sr,3*sr,.05)+tone_at(1500,sr,3*sr,.05)
    y=dsp.apply_effect(x,sr,{"kind":"bass","params":{"gain_db":9}})[sr:]
    assert power_at(y,sr,60)/power_at(y,sr,1500)>2
    assert abs(y).max()<=dsp.amp(-1)+1e-6


def test_eq_mid_adjustment(sr):
    x=tone_at(1000,sr,sr,.1)
    y=dsp.apply_effect(x,sr,{"kind":"eq","params":{"mid_db":6,"mid_hz":1000}})
    assert 1.85 < np.std(y[sr//4:])/np.std(x[sr//4:]) < 2.15


def test_compressor_reduces_dynamic_range(sr):
    x=np.concatenate([tone_at(440,sr,sr,.05),tone_at(440,sr,sr,.8)])
    y=dsp.apply_effect(x,sr,{"kind":"compressor","params":{"threshold_db":-20,"ratio":5}})
    before=np.std(x[int(sr*1.5):])/np.std(x[sr//2:sr])
    after=np.std(y[int(sr*1.5):])/np.std(y[sr//2:sr])
    assert after<before*.6


def test_gate_quiet_floor(sr):
    x=tone_at(400,sr,2*sr,.001)
    y=dsp.apply_effect(x,sr,{"kind":"gate","params":{"threshold_db":-35}})
    assert np.std(y[sr:])<np.std(x[sr:])*.1


@pytest.mark.parametrize("kind",["reverb","delay","chorus","saturation"])
def test_effects_audibly_alter_signal(kind,sr):
    x=tone_at(330,sr,2*sr,.2);x[sr:]=0
    y=dsp.apply_effect(x,sr,{"kind":kind})
    assert np.mean((y-x)**2)>1e-5


def test_limiter_ceiling_and_normalize(sr):
    x=tone_at(1000,sr,sr,2.0)
    y=dsp.apply_effect(x,sr,{"kind":"limiter","params":{"ceiling_db":-3}})
    assert abs(y).max()<=dsp.amp(-3)+1e-6
    z=dsp.apply_effect(x*.01,sr,{"kind":"normalize","params":{"target_db":-18}})
    assert abs(dsp.db(np.sqrt(np.mean(z*z)))+18)<.05


def test_pitch_shift_preserves_duration(tone,sr):
    y=dsp.apply_effect(tone,sr,{"kind":"pitch","params":{"semitones":12}})
    assert len(y)==len(tone)
    assert abs(peak_hz(y[sr//2:],sr)-880)<3


def test_tempo_preserves_pitch(tone,sr):
    y=dsp.apply_effect(tone,sr,{"kind":"tempo","params":{"rate":1.25}})
    assert abs(len(y)-len(tone)/1.25)<=1
    assert abs(peak_hz(y,sr)-440)<2


def test_harmony_adds_requested_interval(tone,sr):
    y=dsp.apply_effect(tone,sr,{"kind":"harmonize","params":{"semitones":12,"mix":50,"delay_ms":0}})
    assert power_at(y[sr//2:],sr,440)>.15
    assert power_at(y[sr//2:],sr,880)>.03


def test_silence_detection_and_shorten(tone,sr):
    x=np.concatenate([tone[:sr],np.zeros((sr,1),np.float32),tone[:sr]])
    assert dsp.silence_regions(x,sr)==[(1.,2.)]
    y=dsp.apply_effect(x,sr,{"kind":"trim_silence","params":{"keep_s":.1}})
    assert abs(len(y)/sr-2.1)<.02


def test_ducking_follows_reference(sr):
    x=tone_at(330,sr,3*sr,.2);ref=np.zeros_like(x);ref[sr:2*sr]=tone_at(500,sr,sr,.3)
    y=dsp.duck(x,ref,sr)
    assert np.std(y[int(1.2*sr):int(1.8*sr)])<np.std(x[int(1.2*sr):int(1.8*sr)])*.4
    assert np.allclose(y[:sr//2],x[:sr//2])


def test_pan_width_mono_and_phase(tone,sr):
    stereo=np.column_stack([tone[:,0],-tone[:,0]])
    assert dsp.meters(stereo,sr)["phase_correlation"]<-.999
    assert np.max(abs(dsp.pan_width(stereo,width=0)))<1e-7
    left=dsp.pan_width(tone,pan=-1)
    assert np.max(abs(left[:,1]))==0 and np.std(left[:,0])>.1


def test_rms_ab_matching(tone):
    result=dsp.match_rms(tone,tone*2)
    assert abs(np.std(result)/np.std(tone)-1)<.001


def test_alignment_known_delay(sr):
    rng=np.random.default_rng(33);ref=rng.normal(0,.1,(sr*2,1)).astype(np.float32)
    ref[:sr//2]=0;ref[sr:]=0
    delay=int(sr*.25);target=np.pad(ref,((delay,0),(0,0)))[:len(ref)]
    assert abs(dsp.alignment_offset(ref,target,sr)+.25)<.011


def test_issue_detection_positions(sr):
    x=np.zeros((sr,1),dtype=np.float32);x[sr//2:sr//2+20]=1
    result=dsp.issues(x,sr)
    clips=[r for r in result if r["kind"]=="clip"]
    assert clips and clips[0]["start"]<=.5<clips[0]["end"]


def test_invalid_effects_and_cancel(tone,sr):
    with pytest.raises(AudioError):dsp.apply_effect(tone,sr,{"kind":"imaginary"})
    with pytest.raises(AudioError):dsp.apply_effect(tone,sr,{"kind":"bass","params":{"gain_db":1000}})
    token=threading.Event();token.set()
    with pytest.raises(Cancelled):dsp.chain(tone,sr,[{"kind":"eq"}],token)
    bad=tone.copy();bad[2]=np.nan
    with pytest.raises(AudioError):dsp.apply_effect(bad,sr,{"kind":"eq"})


def test_loudness_normalization_and_channel_sum(tone,sr):
    mono=dsp.integrated_lufs(tone,sr)
    stereo=dsp.integrated_lufs(np.repeat(tone,2,axis=1),sr)
    assert abs((stereo-mono)-3.0103)<.03
    y=dsp.apply_effect(tone,sr,{"kind":"loudness","params":{"target_lufs":-23}})
    assert abs(dsp.integrated_lufs(y,sr)+23)<.1


def test_monophonic_correction_reduces_detuning(sr):
    x=tone_at(452,sr,3*sr,.2)
    y=dsp.apply_effect(x,sr,{"kind":"autotune","params":{"amount":100,"tolerance":0}})
    assert abs(peak_hz(y[sr//2:-sr//2],sr)-440)<3


def test_formant_changes_envelope_preserves_fundamental(sr):
    n=sr*2;t=np.arange(n)/sr
    x=sum(np.sin(2*np.pi*180*h*t)*np.exp(-((180*h-800)/500)**2)/h for h in range(1,20))[:,None].astype(np.float32)*.3
    y=dsp.apply_effect(x,sr,{"kind":"formant","params":{"semitones":4,"amount":80}})
    assert np.std(y-x)>.001
    assert len(y)==len(x)
    # Fundamental bin remains on the original harmonic grid.
    assert power_at(y[sr//2:],sr,180)>1e-4


def test_deess_reduces_sibilant_band(sr):
    x=tone_at(8000,sr,2*sr,.3)+tone_at(440,sr,2*sr,.1)
    y=dsp.apply_effect(x,sr,{"kind":"deess","params":{"threshold_db":-30}})[sr:]
    assert power_at(y,sr,8000)<.15
    assert power_at(y,sr,440)>.075


def test_bpm_key_chords_on_synthetic_c_major(sr):
    t=np.arange(sr*12)/sr
    envelope=np.exp(-((t%.5)/.1))
    harmonic=sum(.06*np.sin(2*np.pi*f*t) for f in [261.6256,329.6276,391.9954])
    beat=.25*np.sin(2*np.pi*120*t)*envelope
    x=(harmonic*(.4+.6*envelope)+beat)[:,None].astype(np.float32)
    result=dsp.analyze_music(x,sr)
    assert abs(result["bpm"]-120)<5
    assert result["key"]=="C major"
    assert result["chords"] and len(result["beats"])>12
