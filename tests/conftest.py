import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
os.environ.setdefault("NUMBA_NUM_THREADS","2")
import numpy as np
import pytest
from infinity_audio.model import Session


@pytest.fixture
def sr():return 24000


@pytest.fixture
def tone(sr):
    t=np.arange(sr*2)/sr
    return (.2*np.sin(2*np.pi*440*t))[:,None].astype(np.float32)


@pytest.fixture
def session(tmp_path):return Session(tmp_path/"work",24000)


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication
    app=QApplication.instance() or QApplication([])
    yield app
