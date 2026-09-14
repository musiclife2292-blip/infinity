"""VST3 probing/rendering in a disposable process; no auto-execution from projects."""
from pathlib import Path
import base64
import multiprocessing as mp
import time
import numpy as np
from .errors import AudioError, check_cancel


def discover(folder):
    root=Path(folder)
    if not root.is_dir():
        raise AudioError("Thư mục plugin không tồn tại.")
    found=[]
    # Windows VST3 may be a bundle directory or a single file.
    import os
    for current,dirs,files in os.walk(root,followlinks=False):
        for name in dirs[:]:
            if name.lower().endswith(".vst3"):
                found.append(str(Path(current)/name))
                dirs.remove(name)
        found.extend(str(Path(current)/n) for n in files if n.lower().endswith(".vst3"))
        if len(found)>500:
            raise AudioError("Thư mục quá nhiều plugin; hãy chọn thư mục hẹp hơn.")
    return sorted(set(found))


def _child(connection,path,params,state,input_path,output_path,sr):
    try:
        import pedalboard
        plugin=pedalboard.load_plugin(path)
        if state:
            plugin.raw_state=base64.b64decode(state,validate=True)
        for k,v in params.items():
            if k not in plugin.parameters:
                raise ValueError("Tham số plugin không tồn tại: "+k)
            setattr(plugin,k,v)
        if input_path:
            x=np.load(input_path,allow_pickle=False)
            y=plugin(np.ascontiguousarray(x.T),sr,reset=True).T
            if y.shape!=x.shape or not np.isfinite(y).all():
                raise ValueError("Plugin trả về dữ liệu không hợp lệ hoặc đổi số mẫu.")
            np.save(output_path,y.astype(np.float32),allow_pickle=False)
        info={"path":path,"parameters":{},"state":base64.b64encode(plugin.raw_state).decode("ascii")}
        for name,param in plugin.parameters.items():
            value=getattr(plugin,name)
            # Pedalboard returns weak-reference wrapper subclasses. They
            # resemble scalars but cannot be pickled across the worker pipe.
            scalar_type=param.type
            value=scalar_type(value) if scalar_type in (bool,int,float,str) else str(value)
            info["parameters"][name]=value
        connection.send({"ok":True,"result":info})
    except BaseException as e:
        connection.send({"ok":False,"error":str(e)})
    finally:
        connection.close()


def run_plugin(path,params=None,state=None,input_path=None,output_path=None,sr=48000,timeout=60,cancel=None):
    if not Path(path).exists() or Path(path).suffix.lower()!=".vst3":
        raise AudioError("Không tìm thấy plugin VST3. Chọn lại plugin trên máy này.")
    context=mp.get_context("spawn")
    receiver,sender=context.Pipe(duplex=False)
    process=context.Process(target=_child,args=(sender,str(path),params or {},state,str(input_path) if input_path else None,str(output_path) if output_path else None,sr),daemon=True)
    process.start()
    sender.close()
    deadline=time.monotonic()+timeout
    try:
        while time.monotonic()<deadline:
            check_cancel(cancel)
            if receiver.poll(.05):
                try:
                    result=receiver.recv()
                except EOFError as e:
                    raise AudioError("Plugin đã crash; dự án được giữ nguyên.") from e
                if not result["ok"]:
                    raise AudioError("Plugin báo lỗi: "+result["error"])
                return result["result"]
            if not process.is_alive():
                raise AudioError(f"Plugin kết thúc bất thường (mã {process.exitcode}).")
        raise AudioError("Plugin quá thời gian cho phép và đã bị dừng.")
    finally:
        if process.is_alive():
            process.terminate()
        process.join(timeout=2)
        if process.is_alive():
            process.kill()
            process.join(timeout=2)
        receiver.close()
