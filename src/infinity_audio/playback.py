"""Buffer transport is device-independent and directly testable."""
import numpy as np
from .errors import AudioError


class BufferTransport:
    def __init__(self):
        self.data=np.zeros((0,2),dtype=np.float32)
        self.position=0
        self.loop=False
        self.playing=False
        self.gain=1.
        self.mono=False

    def set_buffer(self,data,loop=False):
        x=np.asarray(data,dtype=np.float32)
        if x.ndim==1:
            x=x[:,None]
        if x.shape[1]==1:
            x=np.repeat(x,2,axis=1)
        if not len(x) or not np.isfinite(x).all():
            raise AudioError("Buffer nghe thử không hợp lệ.")
        # Playback protection is local to monitor; exports are never silently clipped.
        self.data=np.clip(x,-1,1)
        self.position=0
        self.loop=loop
        self.playing=True

    def read_into(self,out):
        out.fill(0)
        if not self.playing or not len(self.data):
            return
        written=0
        while written<len(out):
            n=min(len(out)-written,len(self.data)-self.position)
            out[written:written+n]=self.data[self.position:self.position+n]
            written+=n
            self.position+=n
            if self.position>=len(self.data):
                if self.loop:
                    self.position=0
                else:
                    self.playing=False
                    break
        out*=self.gain
        if self.mono:
            out[:]=out.mean(axis=1,keepdims=True)


class Player:
    def __init__(self):
        self.transport=BufferTransport()
        self.stream=None
        self.sr=48000
        self.last_status=""

    def play(self,data,sr,loop=False):
        self.stop()
        try:
            import sounddevice as sd
            sd.check_output_settings(samplerate=sr,channels=2,dtype="float32")
            self.transport.set_buffer(data,loop)
            self.sr=sr
            def callback(out,frames,time,status):
                if status:
                    self.last_status=str(status)
                self.transport.read_into(out)
            self.stream=sd.OutputStream(samplerate=sr,channels=2,dtype="float32",callback=callback,latency="high")
            self.stream.start()
        except Exception as e:
            self.stop()
            raise AudioError(f"Không mở được thiết bị phát âm thanh. Kiểm tra đầu ra mặc định của Windows. Chi tiết: {e}") from e

    def stop(self):
        self.transport.playing=False
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream=None
