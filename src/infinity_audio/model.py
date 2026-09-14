"""Versioned edit decision list and immutable, content-addressed float assets."""
from __future__ import annotations

import copy
import errno
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import tempfile
import uuid
import zipfile

import numpy as np
from .errors import AudioError, check_cancel

SCHEMA = 1
MAX_ARCHIVE_BYTES = 8 * 1024**3
MAX_MANIFEST_BYTES = 16 * 1024**2
ASSET_RE = re.compile(r"^[0-9a-f]{64}\.npy$")
COLORS = ["#9b8afb", "#55d7c0", "#73b9f8", "#efb969", "#f18fa9", "#a6d478"]


def ident():
    return uuid.uuid4().hex


def atomic_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(value, f, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
            f.flush()
            _durable_flush(f)
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def _durable_flush(file_obj):
    """Flush a file where the platform can provide fsync.

    The managed Linux overlay used for development returns EIO for fsync even
    after a successful write. Atomic rename still protects the previous file;
    Windows NTFS normally supports fsync and can opt into strict behavior with
    ``INFINITY_STRICT_FSYNC=1``.
    """
    try:
        os.fsync(file_obj.fileno())
    except OSError as exc:
        tolerated = {errno.EIO, errno.EINVAL, errno.ENOTSUP, errno.ENOSYS}
        if os.environ.get("INFINITY_STRICT_FSYNC", "0") == "1" or exc.errno not in tolerated:
            raise


def checksum(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def fresh_state(sr=48000):
    return {"schema": SCHEMA, "name": "Dự án chưa đặt tên", "sr": sr,
            "tracks": [], "markers": [], "bpm": 120.0, "key": "Chưa phân tích",
            "chords": [], "master_db": 0.0, "mono": False}


def number(v, lo, hi, label):
    if isinstance(v, bool) or not isinstance(v, (float, int)) or not math.isfinite(v) or not lo <= v <= hi:
        raise AudioError(f"Giá trị {label} không hợp lệ.")


def validate(state):
    if not isinstance(state, dict) or state.get("schema") != SCHEMA:
        raise AudioError("Phiên bản dự án chưa được hỗ trợ.")
    number(state.get("sr"), 8000, 192000, "sample rate")
    if int(state["sr"]) != state["sr"]:
        raise AudioError("Sample rate phải là số nguyên.")
    number(state.get("bpm"), 20, 400, "BPM")
    number(state.get("master_db"), -90, 24, "master")
    if not isinstance(state.get("tracks"), list) or len(state["tracks"]) > 128:
        raise AudioError("Dự án không hợp lệ hoặc quá 128 track.")
    seen = set()
    for t in state["tracks"]:
        if t["id"] in seen:
            raise AudioError("ID track/clip trùng lặp.")
        seen.add(t["id"])
        number(t["gain_db"], -90, 24, "gain")
        number(t["pan"], -1, 1, "pan")
        number(t["width"], 0, 2, "stereo width")
        if len(t["clips"]) > 10000 or len(t["effects"]) > 32:
            raise AudioError("Dự án vượt giới hạn clip/hiệu ứng.")
        for c in t["clips"]:
            if c["id"] in seen or not ASSET_RE.fullmatch(c["asset"]):
                raise AudioError("ID clip hoặc tài sản không hợp lệ.")
            seen.add(c["id"])
            for k in ["start", "offset", "length", "fade_in", "fade_out"]:
                number(c[k], 0, 86400, k)
            if c["length"] <= 0:
                raise AudioError("Clip phải có thời lượng dương.")
        for key, points in t.get("automation", {}).items():
            if key not in {"gain_db", "pan"}:
                raise AudioError("Automation chưa hỗ trợ tham số này.")
            last = -1
            for point in points:
                if len(point) != 2:
                    raise AudioError("Điểm automation không hợp lệ.")
                at, value = point
                number(at, 0, 86400, "thời gian automation")
                number(value, -90 if key == "gain_db" else -1, 24 if key == "gain_db" else 1, key)
                if at <= last:
                    raise AudioError("Các điểm automation phải tăng dần và không trùng thời gian.")
                last = at
    for m in state.get("markers", []):
        number(m["time"], 0, 86400, "marker")


def clip(asset, frames, sr, name="Âm thanh", start=0):
    return {"id": ident(), "asset": asset, "name": name, "start": float(start),
            "offset": 0.0, "length": frames / sr, "fade_in": 0.0, "fade_out": 0.0}


def track(name, index=0):
    return {"id": ident(), "name": name, "color": COLORS[index % len(COLORS)], "clips": [],
            "gain_db": 0.0, "pan": 0.0, "width": 1.0, "mute": False, "solo": False,
            "effects": [], "automation": {}, "sidechain": None}


class Session:
    def __init__(self, directory, sr=48000):
        self.root = Path(directory)
        self.assets = self.root / "assets"
        self.assets.mkdir(parents=True, exist_ok=True)
        self.state = fresh_state(sr)
        self.history = [{"label": "Dự án mới", "state": copy.deepcopy(self.state)}]
        self.cursor = 0
        self.saved_path = None
        self.revision = 0
        self.autosave()

    def payload(self, clean=False):
        return {"format": "infinity-audio", "schema": SCHEMA, "cursor": self.cursor,
                "history": self.history, "clean": clean, "saved_path": self.saved_path}

    def autosave(self, clean=False):
        atomic_json(self.root / "recovery.json", self.payload(clean))

    def add_asset(self, data):
        a = np.asarray(data, dtype=np.float32)
        if a.ndim == 1:
            a = a[:, None]
        if a.ndim != 2 or a.shape[1] not in (1, 2) or not len(a) or not np.isfinite(a).all():
            raise AudioError("Âm thanh phải hữu hạn, mono/stereo và không rỗng.")
        fd, name = tempfile.mkstemp(dir=self.assets, suffix=".tmp")
        tmp = Path(name)
        try:
            with os.fdopen(fd, "wb") as f:
                np.save(f, a, allow_pickle=False)
                f.flush()
                _durable_flush(f)
            key = checksum(tmp) + ".npy"
            target = self.assets / key
            if not target.exists():
                os.replace(tmp, target)
            return key
        finally:
            tmp.unlink(missing_ok=True)

    def audio(self, asset):
        if not ASSET_RE.fullmatch(asset):
            raise AudioError("Tên tài sản không an toàn.")
        try:
            a = np.load(self.assets / asset, allow_pickle=False, mmap_mode="r")
            if a.dtype != np.float32 or a.ndim != 2 or a.shape[1] not in (1, 2):
                raise AudioError("Dữ liệu audio dự án không hợp lệ.")
            return a
        except (OSError, ValueError) as e:
            raise AudioError(f"Không đọc được tài sản: {asset[:12]} — {e}") from e

    def commit(self, label, change):
        new = copy.deepcopy(self.state)
        change(new)
        validate(new)
        old_history, old_cursor, old_state = self.history, self.cursor, self.state
        self.history = (self.history[:self.cursor + 1] + [{"label": label, "state": new}])[-100:]
        self.cursor = len(self.history) - 1
        self.state = new
        try:
            self.autosave()
        except Exception:
            self.history, self.cursor, self.state = old_history, old_cursor, old_state
            raise
        self.revision += 1

    def goto(self, cursor):
        if not 0 <= cursor < len(self.history):
            return False
        old = self.cursor
        self.cursor = cursor
        self.state = copy.deepcopy(self.history[cursor]["state"])
        try:
            self.autosave()
        except Exception:
            self.cursor = old
            self.state = copy.deepcopy(self.history[old]["state"])
            raise
        self.revision += 1
        return True

    def undo(self):
        return self.goto(self.cursor - 1)

    def redo(self):
        return self.goto(self.cursor + 1)

    def add_track(self, data, name, start=0):
        key = self.add_asset(data)
        t = track(name, len(self.state["tracks"]))
        t["clips"].append(clip(key, len(data), self.state["sr"], name, start))
        self.commit("Nhập " + name, lambda s: s["tracks"].append(t))
        return t["id"], t["clips"][0]["id"]

    def find_clip(self, clip_id, state=None):
        for t in (state or self.state)["tracks"]:
            for c in t["clips"]:
                if c["id"] == clip_id:
                    return t, c
        raise AudioError("Hãy chọn một clip trên timeline.")

    def set_track(self, track_id, **values):
        def change(s):
            t = next(t for t in s["tracks"] if t["id"] == track_id)
            t.update(values)
        self.commit("Chỉnh mixer / track", change)

    def split(self, clip_id, at):
        def change(s):
            t, c = self.find_clip(clip_id, s)
            local = round((at - c["start"]) * s["sr"]) / s["sr"]
            if not 0 < local < c["length"]:
                raise AudioError("Điểm chia phải nằm trong clip.")
            right = copy.deepcopy(c)
            right.update(id=ident(), start=c["start"] + local, offset=c["offset"] + local,
                         length=c["length"] - local, fade_in=0.0)
            c["length"], c["fade_out"] = local, 0.0
            t["clips"].insert(t["clips"].index(c) + 1, right)
        self.commit("Chia clip", change)

    def duplicate(self, clip_id, start, destination=None):
        def change(s):
            t, c = self.find_clip(clip_id, s)
            dest = next((x for x in s["tracks"] if x["id"] == destination), t)
            new = copy.deepcopy(c)
            new.update(id=ident(), start=max(0.0, start))
            dest["clips"].append(new)
        self.commit("Sao chép clip", change)

    def move(self, clip_id, start, destination=None):
        def change(s):
            t, c = self.find_clip(clip_id, s)
            c["start"] = max(0.0, round(start * s["sr"]) / s["sr"])
            if destination and destination != t["id"]:
                dest = next(x for x in s["tracks"] if x["id"] == destination)
                t["clips"].remove(c)
                dest["clips"].append(c)
        self.commit("Di chuyển clip", change)

    def delete(self, clip_id):
        def change(s):
            t, c = self.find_clip(clip_id, s)
            t["clips"].remove(c)
        self.commit("Xóa clip", change)

    def trim(self, clip_id, left, right):
        def change(s):
            _, c = self.find_clip(clip_id, s)
            lo, hi = max(left, c["start"]), min(right, c["start"] + c["length"])
            if hi <= lo:
                raise AudioError("Vùng chọn không giao clip.")
            c["offset"] += lo - c["start"]
            c.update(start=lo, length=hi - lo)
        self.commit("Giữ vùng chọn", change)

    def fade(self, clip_id, fade_in, fade_out):
        def change(s):
            _, c = self.find_clip(clip_id, s)
            c.update(fade_in=min(fade_in, c["length"]), fade_out=min(fade_out, c["length"]))
        self.commit("Fade clip", change)

    def replace_audio(self, clip_id, data, label):
        key = self.add_asset(data)
        def change(s):
            _, c = self.find_clip(clip_id, s)
            c.update(asset=key, offset=0.0, length=len(data) / s["sr"])
        self.commit(label, change)

    def clip_audio(self, clip_id):
        _, c = self.find_clip(clip_id)
        sr = self.state["sr"]
        a = self.audio(c["asset"])
        begin = round(c["offset"] * sr)
        return np.array(a[begin:begin + round(c["length"] * sr)], copy=True)

    def all_assets(self):
        return sorted({c["asset"] for h in self.history for t in h["state"]["tracks"] for c in t["clips"]})

    def save(self, path, cancel=None, progress=None):
        path = Path(path)
        if path.suffix.lower() != ".infinity":
            path = path.with_suffix(".infinity")
        path.parent.mkdir(parents=True, exist_ok=True)
        keys = self.all_assets()
        estimated = sum((self.assets / k).stat().st_size for k in keys)
        if shutil.disk_usage(path.parent).free < estimated + 16 * 1024**2:
            raise AudioError("Không đủ dung lượng để lưu an toàn.")
        tmp = path.with_name(path.name + "." + ident() + ".tmp")
        try:
            payload = self.payload()
            payload["saved_path"] = str(path)
            with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as z:
                z.writestr("project.json", json.dumps(payload, ensure_ascii=False, allow_nan=False))
                for i, key in enumerate(keys):
                    check_cancel(cancel)
                    with open(self.assets / key, "rb") as src, z.open("assets/" + key, "w", force_zip64=True) as dst:
                        while b := src.read(1024 * 1024):
                            check_cancel(cancel)
                            dst.write(b)
                    if progress:
                        progress((i + 1) / max(1, len(keys)), "Đang lưu tài sản…")
            check_cancel(cancel)
            # Windows FlushFileBuffers needs a handle opened for writing.
            with tmp.open("r+b") as f:
                _durable_flush(f)
            if path.exists():
                shutil.copy2(path, path.with_suffix(".infinity.bak"))
            os.replace(tmp, path)
            self.saved_path = str(path)
            self.autosave()
            return str(path)
        finally:
            tmp.unlink(missing_ok=True)

    @classmethod
    def recover(cls, directory):
        root = Path(directory)
        payload = json.loads((root / "recovery.json").read_text(encoding="utf-8"))
        obj = cls.__new__(cls)
        obj.root, obj.assets = root, root / "assets"
        obj._restore(payload)
        obj._check_assets()
        return obj

    def _restore(self, payload):
        if payload.get("format") != "infinity-audio" or payload.get("schema") != SCHEMA:
            raise AudioError("Đây không phải dự án Infinity audio được hỗ trợ.")
        history, cursor = payload.get("history"), payload.get("cursor")
        if not isinstance(history, list) or not 1 <= len(history) <= 100 or not isinstance(cursor, int) or not 0 <= cursor < len(history):
            raise AudioError("Lịch sử dự án không hợp lệ.")
        for item in history:
            validate(item["state"])
        self.history, self.cursor = history, cursor
        self.state = copy.deepcopy(history[cursor]["state"])
        self.saved_path, self.revision = payload.get("saved_path"), 0

    def _check_assets(self):
        for k in self.all_assets():
            if checksum(self.assets / k) != k[:-4]:
                raise AudioError("Checksum tài sản không khớp; dự án có thể đã hỏng.")
            a = self.audio(k)
            for start in range(0, len(a), 262144):
                if not np.isfinite(a[start:start + 262144]).all():
                    raise AudioError("Tài sản chứa NaN/Infinity.")
        for h in self.history:
            for t in h["state"]["tracks"]:
                for c in t["clips"]:
                    if round((c["offset"] + c["length"]) * h["state"]["sr"]) > len(self.audio(c["asset"])):
                        raise AudioError("Clip tham chiếu vượt chiều dài tài sản.")

    @classmethod
    def load(cls, path, directory, cancel=None, progress=None):
        root = Path(directory)
        if (root / "recovery.json").exists():
            raise AudioError("Hãy mở dự án vào một workspace mới.")
        try:
            with zipfile.ZipFile(path) as z:
                infos = z.infolist()
                names = [i.filename for i in infos]
                if len(names) != len(set(names)) or len(names) > 20000 or sum(i.file_size for i in infos) > MAX_ARCHIVE_BYTES:
                    raise AudioError("Gói dự án trùng mục hoặc vượt giới hạn 8 GiB.")
                if "project.json" not in names or z.getinfo("project.json").file_size > MAX_MANIFEST_BYTES:
                    raise AudioError("Không tìm thấy manifest hợp lệ.")
                for n in names:
                    if n != "project.json" and not (n.startswith("assets/") and ASSET_RE.fullmatch(n[7:])):
                        raise AudioError("Gói dự án có đường dẫn không hợp lệ.")
                payload = json.loads(z.read("project.json"))
                obj = cls.__new__(cls)
                obj.root, obj.assets = root, root / "assets"
                obj.assets.mkdir(parents=True, exist_ok=True)
                obj._restore(payload)
                keys = obj.all_assets()
                for i, k in enumerate(keys):
                    with z.open("assets/" + k) as src, (obj.assets / k).open("wb") as dst:
                        while b := src.read(1024 * 1024):
                            check_cancel(cancel)
                            dst.write(b)
                    if progress:
                        progress((i + 1) / len(keys), "Đang xác minh dự án…")
                check_cancel(cancel)
                obj._check_assets()
                obj.saved_path = str(path)
                obj.autosave()
                return obj
        except AudioError:
            raise
        except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile) as e:
            raise AudioError(f"Không mở được dự án: {e}") from e


def recovery_candidates(base):
    out = []
    for p in Path(base).glob("*/recovery.json"):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            if not d.get("clean") and d.get("history"):
                out.append((p.stat().st_mtime, p.parent))
        except (OSError, ValueError):
            continue
    return [p for _, p in sorted(out, reverse=True)]
