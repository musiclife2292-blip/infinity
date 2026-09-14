"""Regression coverage for native worker teardown and cancellation."""
import threading
import time

from PySide6.QtCore import QThread
from PySide6.QtTest import QTest

from infinity_audio.jobs import JobRunner


def drain(qapp, runner, timeout=5):
    deadline = time.monotonic() + timeout
    while runner.busy and time.monotonic() < deadline:
        qapp.processEvents()
        QTest.qWait(1)
    assert not runner.busy
    qapp.processEvents()


def test_repeated_jobs_complete_on_gui_thread_after_join(qapp):
    runner = JobRunner()
    received, completed, errors = [], [], []
    runner.failed.connect(errors.append)
    runner.completed.connect(lambda: completed.append(not runner.busy))
    for index in range(50):
        def receive(value):
            assert QThread.currentThread() == qapp.thread()
            received.append(value)
        assert runner.start(lambda cancel, progress, i=index: i, receive)
        drain(qapp, runner)
    assert received == list(range(50))
    assert completed == [True] * 50
    assert errors == []


def test_shutdown_joins_without_gui_events_and_suppresses_result(qapp):
    runner = JobRunner()
    started = threading.Event()
    received = []
    def work(cancel, progress):
        started.set()
        cancel.wait(2)
        return "must not commit cancelled audio"
    assert runner.start(work, received.append)
    assert started.wait(2)
    assert runner.shutdown(2000)
    # Leave old finished/result events queued while starting a new job.
    assert runner.start(lambda cancel, progress: "new job", received.append)
    drain(qapp, runner)
    assert received == ["new job"]


def test_failed_job_does_not_block_next_job(qapp):
    runner = JobRunner()
    errors, received = [], []
    runner.failed.connect(errors.append)
    def fail(cancel, progress):
        raise ValueError("broken source")
    assert runner.start(fail, received.append)
    drain(qapp, runner)
    assert errors == ["broken source"]
    assert runner.start(lambda cancel, progress: "recovered", received.append)
    drain(qapp, runner)
    assert received == ["recovered"]
