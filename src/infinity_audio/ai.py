"""Experimental local-only Demucs bridge. Weights and runtime are NOT bundled.

This adapter is not counted as tested source separation. A licensed model,
Windows packaging, performance testing, and representative fixtures remain gates.
"""
from pathlib import Path
import importlib.util
import multiprocessing as mp
import time
import numpy as np
from .errors import AudioError,check_cancel

STEMS={"htdemucs":["drums","bass","other","vocals"],
       "htdemucs_6s":["drums","bass","other","vocals","guitar","piano"]}


def available():
    return importlib.util.find_spec("demucs") is not None and importlib.util.find_spec("torch") is not None


def _separate_child(pipe,input_path,output_dir,sr,repo,name,device):
    try:
        import torch
        from demucs.pretrained import get_model
        from demucs.apply import apply_model
        from demucs.audio import convert_audio
        model=get_model(name,repo=Path(repo))  # LocalRepo, never auto-download.
        if list(model.sources)!=STEMS[name]:
            raise ValueError("Danh sách stem trong model không khớp manifest.")
        x=torch.from_numpy(np.load(input_path,allow_pickle=False).T.copy())
        x=convert_audio(x,sr,model.samplerate,model.audio_channels)
        ref=x.mean(0);mean=ref.mean();std=ref.std().clamp_min(1e-8)
        with torch.inference_mode():
            y=apply_model(model,(x-mean)[None]/std,device=device,shifts=0,split=True,overlap=.25)[0]
        y=y*std+mean
        outputs={}
        for stem,values in zip(model.sources,y):
            values=convert_audio(values.cpu(),model.samplerate,sr,2).numpy().T
            path=Path(output_dir)/(stem+".npy")
            np.save(path,values.astype(np.float32),allow_pickle=False)
            outputs[stem]=str(path)
        pipe.send({"ok":True,"outputs":outputs})
    except BaseException as e:
        pipe.send({"ok":False,"error":str(e)})
    finally:
        pipe.close()


def separate(input_path,output_dir,sr,repo,name="htdemucs",device="cpu",cancel=None,progress=None):
    if name not in STEMS or not Path(repo).is_dir():
        raise AudioError("Chọn repository model local hợp lệ và model 4/6 stem đã công bố.")
    if not available():
        raise AudioError("Bản cơ bản chưa đóng gói Demucs/PyTorch. Tách stem chưa khả dụng trong bản này; xem phần AI trong tài liệu build.")
    x=np.load(input_path,allow_pickle=False,mmap_mode="r")
    if len(x)>sr*120:
        raise AudioError("Bộ nối AI thử nghiệm giới hạn 2 phút/lần.")
    Path(output_dir).mkdir(parents=True,exist_ok=True)
    ctx=mp.get_context("spawn");receive,send=ctx.Pipe(duplex=False)
    process=ctx.Process(target=_separate_child,args=(send,str(input_path),str(output_dir),sr,str(repo),name,device))
    process.start();send.close()
    deadline=time.monotonic()+1800
    try:
        if progress:
            progress(0,"AI đang xử lý; tiến độ chi tiết chưa có. Có thể hủy.")
        while time.monotonic()<deadline:
            check_cancel(cancel)
            if receive.poll(.1):
                try:
                    result=receive.recv()
                except EOFError as e:
                    raise AudioError("Tiến trình AI kết thúc bất thường.") from e
                if not result["ok"]:
                    raise AudioError("Không tách được stem: "+result["error"])
                return result["outputs"]
            if not process.is_alive():
                raise AudioError("Tiến trình AI đã dừng mà không trả kết quả.")
        raise AudioError("AI vượt thời gian cho phép 30 phút.")
    finally:
        if process.is_alive():
            process.terminate()
        process.join(timeout=2)
        if process.is_alive():
            process.kill();process.join(timeout=2)
        receive.close()
