"""Qt worker lifecycle; no UI work or model commit in background tasks."""
import threading
import traceback
from PySide6.QtCore import QObject, QThread, Signal, Slot
from .errors import Cancelled


class Worker(QObject):
    result=Signal(object)
    failed=Signal(str)
    progress=Signal(float,str)
    finished=Signal()

    def __init__(self,function,token):
        super().__init__()
        self.function,self.token=function,token

    @Slot()
    def run(self):
        try:
            result=self.function(self.token,self.progress.emit)
            if not self.token.is_set():
                self.result.emit(result)
        except Cancelled:
            pass
        except Exception as e:
            traceback.print_exc()
            self.failed.emit(str(e))
        finally:
            self.finished.emit()


class JobRunner(QObject):
    progress=Signal(float,str)
    failed=Signal(str)
    busyChanged=Signal(bool)
    completed=Signal()

    def __init__(self,parent=None):
        super().__init__(parent)
        self.thread=None
        self.worker=None
        self.token=None
        self._success=None

    @property
    def busy(self):
        return self.thread is not None

    def start(self,function,on_success):
        if self.busy:
            return False
        self.token=threading.Event()
        self._success=on_success
        self.thread=QThread(self)
        self.worker=Worker(function,self.token)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.result.connect(self._deliver)
        self.worker.progress.connect(self.progress)
        self.worker.failed.connect(self.failed)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self._finished)
        self.busyChanged.emit(True)
        self.thread.start()
        return True

    @Slot(object)
    def _deliver(self,result):
        if self._success and not self.token.is_set():
            try:
                self._success(result)
            except Exception as e:
                self.failed.emit(str(e))

    @Slot()
    def _finished(self):
        old=self.thread
        self.thread=self.worker=None
        self._success=None
        old.deleteLater()
        self.busyChanged.emit(False)
        self.completed.emit()

    def cancel(self):
        if self.token:
            self.token.set()
