class AudioError(Exception):
    """Expected user-facing error, with a Vietnamese description."""


class Cancelled(AudioError):
    pass


def check_cancel(cancel=None):
    if cancel is not None and cancel.is_set():
        raise Cancelled("Đã hủy tác vụ; dự án chưa bị thay đổi.")
