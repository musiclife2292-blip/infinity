"""Deterministic offline timeline summing. Source assets are always read-only."""
import copy
import numpy as np
from . import dsp
from .errors import AudioError, check_cancel

MAX_RENDER_BYTES = 128 * 1024**2


def duration(state):
    return max((c["start"] + c["length"] for t in state["tracks"] for c in t["clips"]), default=0.)


def render_track(session, t, state, frames, cancel=None, bypass=False):
    sr = state["sr"]
    y = np.zeros((frames,2),dtype=np.float32)
    for c in t["clips"]:
        check_cancel(cancel)
        at,offset,n = round(c["start"]*sr),round(c["offset"]*sr),round(c["length"]*sr)
        if at>=frames:
            continue
        n=min(n,frames-at)
        src=session.audio(c["asset"])
        x=np.array(src[offset:offset+n],dtype=np.float32,copy=True)
        if len(x)!=n:
            raise AudioError("Clip tham chiếu vượt quá độ dài nguồn.")
        fi,fo=min(n,round(c["fade_in"]*sr)),min(n,round(c["fade_out"]*sr))
        if not bypass:
            if fi:
                x[:fi] *= np.linspace(0,1,fi,dtype=np.float32)[:,None]
            if fo:
                x[-fo:] *= np.linspace(1,0,fo,dtype=np.float32)[:,None]
        if x.shape[1]==1:
            x=np.repeat(x,2,axis=1)
        y[at:at+n]+=x
    if bypass:
        return y
    if t["effects"]:
        for effect in t["effects"]:
            if effect["kind"] in {"tempo","trim_silence"}:
                raise AudioError("Hiệu ứng đổi thời lượng phải áp dụng lên clip, không dùng trên rack track.")
        y=dsp.chain(y,sr,t["effects"],cancel)
    time=np.arange(frames)/sr
    automation=t.get("automation",{})
    gain=t["gain_db"]
    pan=t["pan"]
    if automation.get("gain_db"):
        a=np.asarray(automation["gain_db"])
        gain=np.interp(time,a[:,0],a[:,1])
    if automation.get("pan"):
        a=np.asarray(automation["pan"])
        pan=np.interp(time,a[:,0],a[:,1])
    y=dsp.pan_width(y,pan,t["width"])
    y*=np.asarray(dsp.amp(gain)).reshape(-1,1) if np.ndim(gain) else dsp.amp(gain)
    return y.astype(np.float32)


def render(session, state=None, start=0, end=None, cancel=None, progress=None, bypass=False, only_track=None):
    state=copy.deepcopy(state or session.state)
    sr=state["sr"]
    total=duration(state)
    if not total:
        raise AudioError("Dự án chưa có âm thanh.")
    frames=round(total*sr)
    if frames*2*4 > MAX_RENDER_BYTES:
        raise AudioError("Dự án vượt ngân sách kết xuất 128 MiB stereo. Hãy chia thành dự án ngắn hơn.")
    if not 0 <= start < total or (end is not None and end<=start):
        raise AudioError("Vùng kết xuất không hợp lệ.")
    solos=any(t["solo"] for t in state["tracks"])
    active=[t for t in state["tracks"] if t["id"]==only_track] if only_track else [t for t in state["tracks"] if not t["mute"] and (not solos or t["solo"])]
    mix=np.zeros((frames,2),dtype=np.float32)
    for i,t in enumerate(active):
        check_cancel(cancel)
        y=render_track(session,t,state,frames,cancel,bypass)
        if not bypass and t.get("sidechain"):
            cfg=t["sidechain"]
            source=next((v for v in state["tracks"] if v["id"]==cfg["track_id"]),None)
            if source is None or source["id"]==t["id"]:
                raise AudioError("Nguồn sidechain không còn hợp lệ.")
            # Detector uses raw clip sum, independent of reference mute/solo/FX and avoids cycles.
            ref=render_track(session,source,state,frames,cancel,True)
            y=dsp.duck(y,ref,sr,cfg.get("threshold_db",-35),cfg.get("depth_db",12))
        mix+=y
        if progress:
            progress((i+1)/max(1,len(active)),"Đang phối "+t["name"])
    if not bypass:
        mix*=dsp.amp(state["master_db"])
        if state["mono"]:
            mix[:]=mix.mean(axis=1,keepdims=True)
    check_cancel(cancel)
    if not np.isfinite(mix).all():
        raise AudioError("Kết xuất không hữu hạn; không xuất file.")
    return mix[round(start*sr):min(frames,round((end or total)*sr))].copy()
