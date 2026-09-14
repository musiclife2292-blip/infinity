"""Local codecs, explicit output settings, atomic file publication."""
from pathlib import Path
import math
import os
import uuid
import numpy as np
from scipy.signal import resample_poly
import soundfile as sf
from .errors import AudioError, check_cancel


def _durable_flush(file_obj):
    """Best-effort fsync for managed overlay filesystems.

    Set ``INFINITY_STRICT_FSYNC=1`` in a release/QA environment to turn any
    fsync error into a failed atomic write. The development overlay returns
    EIO for fsync although the bytes are readable, so atomic rename is used as
    its fallback protection here.
    """
    import errno
    try:
        os.fsync(file_obj.fileno())
    except OSError as exc:
        if os.environ.get("INFINITY_STRICT_FSYNC", "0") == "1" or exc.errno not in {errno.EIO, errno.EINVAL, errno.ENOTSUP, errno.ENOSYS}:
            raise

MAX_DECODE_BYTES = 256 * 1024**2
SAMPLE_RATES = (22050, 32000, 44100, 48000, 88200, 96000, 192000)


def resample(data, from_sr, to_sr):
    if from_sr == to_sr:
        return np.asarray(data, dtype=np.float32)
    gcd = math.gcd(int(from_sr), int(to_sr))
    return resample_poly(data, to_sr // gcd, from_sr // gcd, axis=0).astype(np.float32)


def read_audio(path, target_sr=None, cancel=None, progress=None):
    path = Path(path)
    if path.suffix.lower() not in {".wav", ".flac", ".mp3", ".ogg", ".aif", ".aiff"}:
        raise AudioError("Định dạng chưa hỗ trợ. Hãy dùng WAV, FLAC, MP3, OGG hoặc AIFF.")
    try:
        with sf.SoundFile(path) as f:
            if f.channels not in (1, 2) or f.frames <= 0:
                raise AudioError("Chỉ hỗ trợ file mono hoặc stereo không rỗng.")
            sr = f.samplerate
            expected = f.frames * f.channels * 4 * max(1, (target_sr or sr) / sr)
            if expected > MAX_DECODE_BYTES:
                raise AudioError("File vượt ngân sách giải mã 256 MiB float. Hãy nhập một đoạn ngắn hơn.")
            data = np.empty((f.frames, f.channels), dtype=np.float32)
            done = 0
            while done < len(data):
                check_cancel(cancel)
                b = f.read(min(262144, len(data) - done), dtype="float32", always_2d=True)
                if not len(b):
                    raise AudioError("File bị cắt cụt; số mẫu thực tế không khớp header.")
                data[done:done + len(b)] = b
                done += len(b)
                if progress:
                    progress(done / len(data) * .85, "Đang đọc âm thanh…")
        if not np.isfinite(data).all():
            raise AudioError("File có giá trị NaN/Infinity, không thể xử lý an toàn.")
        check_cancel(cancel)
        out_sr = target_sr or sr
        data = resample(data, sr, out_sr)
        check_cancel(cancel)
        if progress:
            progress(1, "Đã nhập âm thanh")
        return data, out_sr
    except (sf.SoundFileError, OSError, ValueError) as e:
        raise AudioError(f"Không giải mã được file: {e}") from e


def export_audio(path, data, sr, output_sr=None, bit_depth=24, bitrate=192, channels=2,
                 cancel=None, progress=None, overwrite=False):
    path = Path(path)
    suffix = path.suffix.lower()
    fmt = {".wav": "WAV", ".flac": "FLAC", ".mp3": "MP3"}.get(suffix)
    if not fmt:
        raise AudioError("Chỉ xuất WAV, FLAC hoặc MP3.")
    if path.exists() and not overwrite:
        raise AudioError("File xuất đã tồn tại; chọn tên mới hoặc cho phép thay thế.")
    if channels not in (1, 2) or bit_depth not in (16, 24, 32) or bitrate not in (96, 128, 160, 192, 256, 320):
        raise AudioError("Thiết lập xuất không hợp lệ.")
    if fmt == "FLAC" and bit_depth == 32:
        raise AudioError("FLAC trong bản này hỗ trợ PCM 16/24 bit.")
    output_sr = output_sr or sr
    if output_sr not in SAMPLE_RATES:
        raise AudioError("Sample rate xuất không được hỗ trợ.")
    if fmt == "MP3" and output_sr not in (32000, 44100, 48000):
        raise AudioError("MP3 cần sample rate 32, 44.1 hoặc 48 kHz.")
    x = np.asarray(data, dtype=np.float32)
    if x.ndim == 1:
        x = x[:, None]
    if not len(x) or not np.isfinite(x).all():
        raise AudioError("Không có âm thanh hợp lệ để xuất.")
    if channels == 1:
        x = x.mean(axis=1, keepdims=True)
    elif x.shape[1] == 1:
        x = np.repeat(x, 2, axis=1)
    check_cancel(cancel)
    x = resample(x, sr, output_sr)
    if np.max(np.abs(x)) > 1.0 and not (fmt == "WAV" and bit_depth == 32):
        raise AudioError("Âm thanh vượt 0 dBFS. Hạ master hoặc dùng limiter trước khi xuất PCM/MP3.")
    subtype = "FLOAT" if bit_depth == 32 else f"PCM_{bit_depth}"
    extra = {}
    if fmt == "MP3":
        subtype = "MPEG_LAYER_III"
        # libsndfile compression level maps 0=320kbps .. 1=32kbps; CBR snaps to MPEG table.
        extra = {"bitrate_mode": "CONSTANT", "compression_level": (320 - bitrate) / 288}
    if not sf.check_format(fmt, subtype):
        raise AudioError(f"Codec {fmt}/{subtype} không có trong bản libsndfile này.")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with sf.SoundFile(tmp, "w", samplerate=output_sr, channels=channels,
                          format=fmt, subtype=subtype, **extra) as f:
            for a in range(0, len(x), 262144):
                check_cancel(cancel)
                f.write(x[a:a + 262144])
                if progress:
                    progress(min(1, (a + 262144) / len(x)), "Đang ghi file…")
        check_cancel(cancel)
        # Windows FlushFileBuffers needs a handle opened for writing.
        with tmp.open("r+b") as f:
            _durable_flush(f)
        os.replace(tmp, path)
        return str(path)
    except (sf.SoundFileError, OSError, ValueError) as e:
        raise AudioError(f"Không xuất được file: {e}") from e
    finally:
        tmp.unlink(missing_ok=True)
