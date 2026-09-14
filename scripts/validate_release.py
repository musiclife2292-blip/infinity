"""Reproducible synthetic DSP evidence, codec verification and bounded stress tests."""
import json
import os
from pathlib import Path
import platform
from datetime import datetime, timezone
try:
    import resource
except ImportError:  # Windows has no resource module.
    resource = None
import shutil
import subprocess
import sys
import tempfile
import time
import importlib.metadata as metadata
import numpy as np

# Allow the evidence script to run directly from a source checkout.  The
# Windows build installs the package in editable mode, but reviewers should
# not need an installation step just to reproduce the deterministic fixtures.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from infinity_audio import dsp,render
from infinity_audio.model import Session,atomic_json
from infinity_audio.audio_io import read_audio,export_audio


def snr(clean,x):
    return float(10*np.log10(np.sum(clean.astype(float)**2)/max(1e-20,np.sum((clean-x).astype(float)**2))))


def main():
    root=Path(sys.argv[1] if len(sys.argv)>1 else "evidence");root.mkdir(exist_ok=True,parents=True)
    samples=root/"audio-samples";samples.mkdir(exist_ok=True)
    sr=24000;t=np.arange(sr*6)/sr;rng=np.random.default_rng(310)
    env=((t%1.2)>.35)*np.sin(np.pi*np.clip((t%1.2-.35)/.8,0,1))**2
    voice=(env*(.28*np.sin(2*np.pi*190*t)+.1*np.sin(2*np.pi*570*t)+.05*np.sin(2*np.pi*950*t)))[:,None].astype(np.float32)
    sine=(.75*np.sin(2*np.pi*440*t))[:,None].astype(np.float32)
    noisy=voice+rng.normal(0,.025,voice.shape).astype(np.float32)
    hum=voice+(.07*np.sin(2*np.pi*50*t)+.04*np.sin(2*np.pi*100*t))[:,None].astype(np.float32)
    clicks=voice.copy();clicks[np.arange(5000,len(t),19000),0]=.95
    clipped=np.clip(sine,-.5,.5)
    event=voice.copy();region=(t>=2)&(t<2.35);event[region,0]+=.2*np.sin(2*np.pi*3000*t[region])
    cases=[("denoise",voice,noisy,{"kind":"denoise","params":{"amount":65}}),
           ("dehum",voice,hum,{"kind":"dehum","params":{}}),
           ("declick",voice,clicks,{"kind":"declick","params":{}}),
           ("declip",sine,clipped,{"kind":"declip","params":{"threshold":.499}}),
           ("spectral",voice,event,{"kind":"spectral","params":{"start":1.98,"end":2.37,"low_hz":2700,"high_hz":3300,"reduction_db":40}})]
    evidence=[]
    for name,clean,before,effect in cases:
        start=time.perf_counter();after=dsp.apply_effect(before,sr,effect);elapsed=time.perf_counter()-start
        for suffix,data in [("reference",clean),("before",before),("after",after)]:
            export_audio(samples/f"{name}-{suffix}.wav",data,sr,output_sr=48000,bit_depth=24,channels=1,overwrite=True)
        evidence.append({"case":name,"duration_s":6,"sample_rate_processing":sr,"effect":effect,
                         "snr_before_db":snr(clean,before),"snr_after_db":snr(clean,after),
                         "elapsed_s":elapsed,"after_meter":dsp.meters(after,sr),
                         "passed_objective":snr(clean,after)>snr(clean,before)})
    codecs=[]
    with tempfile.TemporaryDirectory(prefix="infinity-codecs-") as tmp:
        for bitrate in [96,128,160,192,256,320]:
            out=Path(tmp)/f"mp3-{bitrate}.mp3"
            export_audio(out,voice,sr,output_sr=48000,bitrate=bitrate,channels=2)
            decoded,rate=read_audio(out)
            record={"format":"MP3","requested_kbps":bitrate,"sample_rate":rate,"frames":len(decoded)}
            ffprobe=shutil.which("ffprobe")
            if ffprobe:
                p=subprocess.run([ffprobe,"-v","error","-show_entries","stream=codec_name,sample_rate,channels,bit_rate","-of","json",str(out)],capture_output=True,text=True,check=True)
                info=json.loads(p.stdout)["streams"][0];record["ffprobe"]=info
                record["bitrate_matches"]=int(info["bit_rate"])==bitrate*1000
            codecs.append(record)
    stress=[]
    with tempfile.TemporaryDirectory(prefix="infinity-stress-") as tmp:
        session=Session(Path(tmp)/"multitrack",24000)
        source=np.tile(voice,(5,1))*.01
        for i in range(32):session.add_track(source,f"Track {i+1}")
        start=time.perf_counter();mixed=render.render(session);elapsed=time.perf_counter()-start
        error=float(np.max(abs(mixed[:,0]-source[:,0]*32)))
        stress.append({"case":"32 tracks × 30 seconds, same source at -40 dB","tracks":32,"duration_s":30,"elapsed_render_s":elapsed,"maximum_sample_error":error,"passed":error<1e-6})
        long=Session(Path(tmp)/"long",24000)
        long_source=np.tile(voice,(100,1))
        start=time.perf_counter();long.add_track(long_source,"10 phút");mixed=render.render(long)
        path=Path(tmp)/"long.infinity";long.save(path);opened=Session.load(path,Path(tmp)/"long-reopened")
        out=Path(tmp)/"long.flac";export_audio(out,mixed,24000,output_sr=48000,channels=1)
        data,rate=read_audio(out,24000)
        elapsed=time.perf_counter()-start
        stress.append({"case":"10-minute mono project, 24 kHz; save/reopen/export FLAC","duration_s":600,"elapsed_total_s":elapsed,"frames":len(data),"passed":len(data)==len(long_source) and opened.state==long.state,"note":"Not an hours-long session or Windows benchmark."})
        batch_dir=Path(tmp)/"batch";batch_dir.mkdir()
        start=time.perf_counter();count=0
        for i in range(20):
            data=dsp.chain(voice,24000,[{"kind":"eq","params":{"mid_db":2}},{"kind":"limiter","params":{}}])
            export_audio(batch_dir/f"{i:02}.flac",data,24000,output_sr=48000,channels=1);count+=1
        stress.append({"case":"20 files × 6 seconds, EQ → limiter → FLAC","files":count,"elapsed_total_s":time.perf_counter()-start,"passed":count==20})
    packages=["numpy","scipy","PySide6","soundfile","sounddevice","pedalboard","librosa","pyloudnorm","numba","llvmlite","pytest"]
    result={"date":datetime.now(timezone.utc).isoformat(),"platform":platform.platform(),"python":sys.version,"logical_cpu_count":os.cpu_count(),
            "cpu_model":"Not exposed by environment","ram_total":"Not exposed by environment",
            "peak_process_rss_kib":resource.getrusage(resource.RUSAGE_SELF).ru_maxrss if resource else None,
            "audio_device":"Not tested by this script; no hardware listening performed",
            "windows_install_test":"See separate installer report; not tested by this script", "model_inference_test":"NOT RUN — no bundled runtime/licensed weights",
            "packages":{p:metadata.version(p) for p in packages},"dsp_samples":evidence,"codec_checks":codecs,"stress":stress}
    atomic_json(root/"validation-results.json",result)
    print(json.dumps({"dsp":evidence,"codecs":codecs,"stress":stress,"peak_process_rss_kib":result["peak_process_rss_kib"]},indent=2))
    if not all(v["passed_objective"] for v in evidence) or not all(v["passed"] for v in stress) or any(v.get("bitrate_matches") is False for v in codecs):
        raise SystemExit("Validation found an objective failure; inspect evidence.")


if __name__=="__main__":main()
