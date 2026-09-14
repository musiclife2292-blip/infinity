"""Offline DSP. All processors are real and return fresh finite float32 arrays.

Restoration algorithms are baseline estimators, not reconstruction guarantees.
Approximate meters are explicitly labelled and are not BS.1770 certification.
"""
from __future__ import annotations
import math
import numpy as np
from scipy import signal, ndimage, interpolate
import pedalboard as pb
from .errors import AudioError, check_cancel


def spec(title, hint, **params):
    # parameter = (Vietnamese label, default, minimum, maximum, increment)
    return {"title": title, "hint": hint, "params": params}


EFFECTS = {
 "denoise": spec("Lọc nhiễu", "Ước lượng nền bằng phổ. Mức mạnh có thể làm giọng bị kim loại.", amount=("Cường độ (%)",50,0,100,1), floor_db=("Nền còn lại (dB)",-20,-60,0,1)),
 "restore": spec("Làm rõ giọng", "Chuỗi lọc nền, cắt trầm và EQ; chưa phải phục hồi giọng bằng AI.", amount=("Cường độ (%)",40,0,100,1)),
 "bass": spec("Bass boosted", "Low shelf tăng bass; limiter kiểm soát đỉnh sau xử lý.", gain_db=("Tăng bass (dB)",6,0,18,.5), cutoff_hz=("Tần số (Hz)",120,40,350,5)),
 "declip": spec("De-clip", "Nội suy cubic cho clipping ngắn. Không khôi phục thông tin đã mất hoàn toàn.", threshold=("Ngưỡng clipping",.98,.1,1,.01), amount=("Cường độ (%)",100,0,100,1)),
 "declick": spec("De-click / De-crackle", "Phát hiện xung theo median; có thể ảnh hưởng transient nhạc cụ.", sensitivity=("Độ nhạy",6,2,20,.5), width=("Cửa sổ (mẫu)",9,3,41,2)),
 "dehum": spec("De-hum", "Notch ở tần số điện và các họa âm; 50 Hz phổ biến tại Việt Nam.", fundamental=("Tần số cơ bản (Hz)",50,40,80,1), harmonics=("Số họa âm",8,1,16,1), q=("Độ hẹp Q",35,5,100,1)),
 "dereverb": spec("Giảm vang · thử nghiệm", "Giảm đuôi phổ theo thời gian; có thể mất sustain. Chưa phải WPE/AI.", amount=("Cường độ (%)",25,0,80,1)),
 "deess": spec("De-ess / bật hơi", "Nén dải âm xì; high-pass giảm bật hơi. Cần nghe lại phụ âm.", threshold_db=("Ngưỡng âm xì (dB)",-24,-60,0,1), frequency=("Dải âm xì từ (Hz)",4500,2000,10000,100), highpass=("Cắt bật hơi (Hz)",80,20,200,5)),
 "spectral": spec("Xóa vùng phổ", "Giảm vùng thời gian/tần số, biên mềm để hạn chế ringing.", start=("Bắt đầu trong vùng xử lý (s)",0,0,300,.01), end=("Kết thúc (s)",1,.01,300,.01), low_hz=("Từ tần số (Hz)",1000,0,20000,50), high_hz=("Đến tần số (Hz)",4000,10,24000,50), reduction_db=("Giảm (dB)",24,0,80,1)),
 "pitch": spec("Đổi tông", "Phase vocoder; giữ thời lượng. Transient và formant có thể thay đổi.", semitones=("Bán âm",0,-12,12,.1)),
 "autotune": spec("Sửa cao độ · đơn âm", "Thử nghiệm: YIN chia các vùng nốt, đưa về nốt chromatic gần nhất. Không dùng cho cả bản phối; chưa có piano roll.", amount=("Mức sửa (%)",70,0,100,1), tolerance=("Bỏ qua lệch dưới (cent)",10,0,50,1)),
 "formant": spec("Formant · thử nghiệm", "Dịch đường bao phổ để đổi màu giọng, giữ lưới cao độ. Không phải mô hình giọng nói AI.", semitones=("Dịch formant (bán âm)",0,-6,6,.1), amount=("Cường độ (%)",60,0,100,1)),
 "tempo": spec("Đổi tốc độ", "Tỷ lệ 1.2 = nhanh hơn 20%, giữ cao độ bằng phase vocoder.", rate=("Tỷ lệ tempo",1,.5,2,.01)),
 "harmonize": spec("Tạo bè / làm dày", "Một bè dịch cao độ; không tự chọn hợp âm hay điều khiển formant.", semitones=("Quãng bè (bán âm)",7,-12,12,.1), mix=("Mức bè (%)",30,0,100,1), delay_ms=("Trễ lớp bè (ms)",18,0,80,1)),
 "eq": spec("EQ ba dải", "Low/high shelf và một peak mid. Q quyết định độ rộng dải trung.", low_db=("Trầm (dB)",0,-18,18,.5), mid_db=("Trung (dB)",0,-18,18,.5), high_db=("Cao (dB)",0,-18,18,.5), mid_hz=("Tần số trung (Hz)",1200,100,10000,50), q=("Q trung",.7,.1,8,.1)),
 "compressor": spec("Compressor", "Nén chênh lệch âm lượng. Threshold là ngưỡng; ratio là tỷ lệ nén.", threshold_db=("Ngưỡng (dB)",-18,-60,0,1), ratio=("Tỷ lệ",3,1,20,.1), attack_ms=("Attack (ms)",10,.1,200,1), release_ms=("Release (ms)",120,5,1000,5), makeup_db=("Bù gain (dB)",0,0,18,.5)),
 "gate": spec("Gate", "Đóng âm dưới ngưỡng bằng cổng cứng; dùng Expander nếu muốn giảm mềm.", threshold_db=("Ngưỡng (dB)",-45,-80,0,1), attack_ms=("Attack (ms)",3,.1,100,.5), release_ms=("Release (ms)",100,5,1000,5)),
 "expander": spec("Expander", "Giảm mềm tín hiệu dưới ngưỡng; giữ transient và nền tự nhiên hơn gate cứng.", threshold_db=("Ngưỡng (dB)",-45,-80,0,1), ratio=("Tỷ lệ mở rộng",2,1,10,.1), attack_ms=("Attack (ms)",5,.1,200,1), release_ms=("Release (ms)",120,5,1000,5), floor_db=("Sàn giảm (dB)",-36,-80,0,1)),
 "reverb": spec("Reverb", "Tạo không gian bằng thuật toán reverb. Đuôi bị cắt ở cuối clip; thêm khoảng trống nếu cần.", room_size=("Kích thước phòng",.45,0,1,.01), damping=("Damping",.5,0,1,.01), mix=("Wet (%)",20,0,100,1)),
 "delay": spec("Delay", "Tiếng lặp có feedback; đuôi nằm trong độ dài vùng xử lý.", time_ms=("Thời gian (ms)",280,1,2000,10), feedback=("Feedback (%)",25,0,85,1), mix=("Wet (%)",20,0,100,1)),
 "chorus": spec("Chorus", "Điều biến trễ để làm dày âm thanh.", rate_hz=("Tốc độ (Hz)",1,.1,8,.1), depth=("Độ sâu",.25,0,1,.01), mix=("Wet (%)",25,0,100,1)),
 "saturation": spec("Saturation", "Méo hài mềm; mức drive cao thay đổi màu âm rõ rệt.", drive_db=("Drive (dB)",4,0,24,.5), mix=("Wet (%)",30,0,100,1)),
 "limiter": spec("Limiter", "Limiter sample peak và chặn overshoot sau render; chưa là true-peak limiter được chứng nhận.", ceiling_db=("Ceiling (dBFS)",-1,-12,0,.1), release_ms=("Release (ms)",100,10,1000,5)),
 "normalize": spec("Cân bằng độ lớn RMS", "Chuẩn hóa RMS có giới hạn đỉnh. Không gọi là chuẩn hóa LUFS.", target_db=("Mục tiêu RMS (dBFS)",-18,-36,-6,.5), ceiling_db=("Ceiling (dBFS)",-1,-12,0,.1)),
 "loudness": spec("Chuẩn hóa loudness LUFS", "Đo integrated loudness bằng pyloudnorm. Giới hạn peak có thể khiến không đạt LUFS mục tiêu; đo lại sau xuất.", target_lufs=("Mục tiêu (LUFS)",-16,-30,-8,.5), ceiling_db=("Ceiling (dBFS)",-1,-12,0,.1)),
 "trim_silence": spec("Rút ngắn khoảng lặng", "Phát hiện theo RMS khung 10 ms và giữ khoảng nghỉ tùy chọn.", threshold_db=("Ngưỡng (dBFS)",-45,-80,-10,1), min_s=("Dài tối thiểu (s)",.3,.05,3,.05), keep_s=("Giữ lại (s)",.08,0,1,.01)),
}

PRESETS = {
 "Vocal tự nhiên": [{"kind":"denoise","params":{"amount":30}}, {"kind":"dehum","params":{}}, {"kind":"deess","params":{}}, {"kind":"compressor","params":{"ratio":2}}, {"kind":"limiter","params":{}}],
 "Bản thu cũ": [{"kind":"declick","params":{}}, {"kind":"dehum","params":{}}, {"kind":"denoise","params":{"amount":40}}, {"kind":"normalize","params":{}}],
 "Bass boosted": [{"kind":"bass","params":{"gain_db":6}},{"kind":"limiter","params":{}}],
 "Lời nói rõ": [{"kind":"restore","params":{"amount":35}}, {"kind":"compressor","params":{"ratio":3}},{"kind":"normalize","params":{}}],
}


def defaults(kind):
    return {k: p[1] for k, p in EFFECTS[kind]["params"].items()}


def validate_effect(effect):
    kind = effect.get("kind")
    if kind not in EFFECTS:
        raise AudioError(f"Hiệu ứng chưa hỗ trợ: {kind}")
    params = defaults(kind)
    for k, value in effect.get("params", {}).items():
        if k not in params:
            raise AudioError(f"Tham số không xác định: {k}")
        _, _, lo, hi, _ = EFFECTS[kind]["params"][k]
        if not isinstance(value, (float, int)) or not np.isfinite(value) or not lo <= value <= hi:
            raise AudioError(f"Tham số ngoài giới hạn: {k}")
        params[k] = value
    return kind, params


def db(value):
    return 20 * np.log10(np.maximum(value, 1e-12))


def amp(value):
    return 10 ** (np.asarray(value) / 20)


def native(x, sr, plugins):
    return pb.Pedalboard(plugins)(np.ascontiguousarray(x.T), sr, reset=True).T.astype(np.float32)


def stft(x, sr):
    n = min(2048, max(16, 2 ** int(np.floor(np.log2(max(16, len(x)))))))
    return signal.stft(x, sr, nperseg=n, noverlap=n * 3 // 4, boundary="zeros"), n


def spectral_process(x, sr, kind, p, cancel=None):
    out = np.empty_like(x)
    for ch in range(x.shape[1]):
        check_cancel(cancel)
        (f, t, z), n = stft(x[:, ch], sr)
        mag = np.abs(z)
        if kind == "denoise":
            floor = np.quantile(mag, .18, axis=1, keepdims=True)
            ratio = floor / np.maximum(mag, 1e-10)
            gain = np.maximum(amp(p["floor_db"]), 1 - (p["amount"] / 100) * 1.8 * ratio)
            gain = ndimage.gaussian_filter(gain, (.6, .9))
        elif kind == "formant":
            envelope=ndimage.gaussian_filter1d(np.log(np.maximum(mag,1e-8)),sigma=max(2,200/(sr/n)),axis=0)
            ratio=2**(p["semitones"]/12)
            warped=interpolate.interp1d(f,envelope,axis=0,bounds_error=False,fill_value=(envelope[0],envelope[-1]))(f/ratio)
            gain=np.exp(np.clip(warped-envelope,-1.2,1.2)*p["amount"]/100)
        elif kind == "dereverb":
            history = signal.lfilter([.08], [1, -.92], mag, axis=1)
            gain = np.clip(1 - p["amount"] / 100 * history / np.maximum(mag, 1e-10), .15, 1)
        else:
            if p["end"] <= p["start"] or p["high_hz"] <= p["low_hz"]:
                raise AudioError("Vùng thời gian/tần số phải có chiều rộng dương.")
            mask = ((f[:, None] >= p["low_hz"]) & (f[:, None] <= p["high_hz"]) &
                    (t[None, :] >= p["start"]) & (t[None, :] <= p["end"]))
            if not mask.any():
                raise AudioError("Vùng phổ nằm ngoài âm thanh.")
            soft = ndimage.gaussian_filter(mask.astype(float), (.8, .8))
            gain = 1 - soft * (1 - amp(-p["reduction_db"]))
        _, y = signal.istft(z * gain, sr, nperseg=n, noverlap=n * 3 // 4)
        out[:, ch] = y[:len(x)]
    return out


def silence_regions(x, sr, threshold_db=-45, min_s=.3):
    y = np.mean(x * x, axis=1)
    hop = max(1, round(sr * .01))
    blocks = np.pad(y, (0, (-len(y)) % hop)).reshape(-1, hop)
    quiet = db(np.sqrt(blocks.mean(axis=1))) < threshold_db
    edges = np.diff(np.pad(quiet.astype(int), (1, 1)))
    return [(a * hop / sr, min(len(x), b * hop) / sr)
            for a, b in zip(np.where(edges == 1)[0], np.where(edges == -1)[0]) if (b-a)*hop/sr >= min_s]


def apply_effect(data, sr, effect, cancel=None):
    kind, p = validate_effect(effect)
    x = np.array(data, dtype=np.float32, copy=True)
    if x.ndim == 1:
        x = x[:, None]
    if len(x) < 16 or x.ndim != 2 or x.shape[1] not in (1, 2) or not np.isfinite(x).all():
        raise AudioError("Cần ít nhất 16 mẫu âm thanh hữu hạn, mono/stereo.")
    if len(x) > sr * 300 or x.nbytes > 128 * 1024**2:
        raise AudioError("Một lần DSP hỗ trợ tối đa 5 phút / 128 MiB. Hãy chọn vùng ngắn hơn.")
    check_cancel(cancel)
    if kind in {"denoise", "dereverb", "spectral", "formant"}:
        y = spectral_process(x, sr, kind, p, cancel)
    elif kind == "restore":
        y = spectral_process(x, sr, "denoise", {"amount":p["amount"] * .6,"floor_db":-16}, cancel)
        y = native(y, sr, [pb.HighpassFilter(70), pb.PeakFilter(250, -p["amount"]*.03, .7), pb.PeakFilter(3000, p["amount"]*.025, .7)])
    elif kind == "bass":
        y = native(x, sr, [pb.LowShelfFilter(p["cutoff_hz"], p["gain_db"], .7), pb.Limiter(-1, 100)])
        y = np.clip(y, -amp(-1), amp(-1))
    elif kind == "dehum":
        y = x.copy()
        for h in range(1, int(p["harmonics"])+1):
            if p["fundamental"]*h >= sr*.48:
                break
            b, a = signal.iirnotch(p["fundamental"]*h, p["q"], sr)
            y = signal.lfilter(b, a, y, axis=0)
    elif kind == "declick":
        width = int(p["width"]) | 1
        median = ndimage.median_filter(x, size=(width,1), mode="reflect")
        residual = np.abs(x-median)
        scale = ndimage.median_filter(residual, size=(101,1), mode="reflect") * 1.4826
        floor = max(1e-4, float(np.sqrt(np.mean(x*x))) * .08)
        mask = residual > p["sensitivity"] * np.maximum(scale, floor)
        y = np.where(mask, median, x)
    elif kind == "declip":
        y = x.copy()
        for ch in range(x.shape[1]):
            mask = np.abs(x[:,ch]) >= p["threshold"]
            edges = np.diff(np.pad(mask.astype(int), (1,1)))
            for a,b in zip(np.where(edges==1)[0], np.where(edges==-1)[0]):
                check_cancel(cancel)
                if a < 4 or b + 4 > len(x) or b-a > sr*.004:
                    continue
                indices = np.r_[np.arange(a-4,a), np.arange(b,b+4)]
                candidate = interpolate.CubicSpline(indices, x[indices,ch])(np.arange(a,b))
                candidate = np.clip(candidate, -4*p["threshold"], 4*p["threshold"])
                y[a:b,ch] = x[a:b,ch] + p["amount"]/100*(candidate-x[a:b,ch])
    elif kind == "deess":
        cutoff = min(p["frequency"], sr * .42)
        # Offline zero-phase split: a causal split would rotate the HF band and
        # subtraction from dry would fail to attenuate (or even boost) sibilance.
        sos=signal.butter(4, cutoff, "highpass", fs=sr, output="sos")
        high = signal.sosfiltfilt(sos,x,axis=0,padlen=min(len(x)-1,24))
        env = np.sqrt(ndimage.uniform_filter1d(np.mean(high*high,axis=1), max(1,int(sr*.005))))
        gain = amp(-np.maximum(0, db(env)-p["threshold_db"])*.75)
        y = x - high*(1-gain[:,None])
        y = native(y, sr, [pb.HighpassFilter(p["highpass"])])
    elif kind == "autotune":
        import librosa
        if len(x)>sr*60:
            raise AudioError("Sửa cao độ thử nghiệm giới hạn một phút mỗi lần.")
        mono=x.mean(axis=1)
        hop=512
        f0=librosa.yin(mono,fmin=65,fmax=min(1000,sr/4),sr=sr,frame_length=2048,hop_length=hop)
        midi=librosa.hz_to_midi(f0)
        target=ndimage.median_filter(np.round(midi),size=5,mode="nearest")
        y=x.copy()
        edges=np.r_[0,np.where(np.diff(target)!=0)[0]+1,len(target)]
        for a,b in zip(edges[:-1],edges[1:]):
            check_cancel(cancel)
            lo,hi=a*hop,min(len(x),b*hop)
            if hi-lo<sr*.08 or np.std(x[lo:hi])<.005:
                continue
            correction=float(target[a]-np.median(midi[a:b]))
            if abs(correction)*100<p["tolerance"] or abs(correction)>.8:
                continue
            corrected=librosa.effects.pitch_shift(x[lo:hi].T,sr=sr,n_steps=correction*p["amount"]/100).T
            blend=np.ones(hi-lo,dtype=np.float32);edge=min(int(sr*.008),(hi-lo)//2)
            blend[:edge]=np.linspace(0,1,edge);blend[-edge:]=np.linspace(1,0,edge)
            y[lo:hi]=x[lo:hi]*(1-blend[:,None])+corrected*blend[:,None]
    elif kind in {"pitch", "tempo", "harmonize"}:
        import librosa
        if kind == "tempo":
            y = librosa.effects.time_stretch(x.T, rate=p["rate"]).T
        else:
            y = librosa.effects.pitch_shift(x.T, sr=sr, n_steps=p["semitones"]).T
            if kind == "harmonize":
                delay = int(p["delay_ms"] * sr / 1000)
                if delay:
                    y = np.pad(y, ((delay,0),(0,0)))[:len(x)]
                y = x + y * p["mix"] / 100
    elif kind == "eq":
        y = native(x, sr, [pb.LowShelfFilter(160,p["low_db"],.7), pb.PeakFilter(min(p["mid_hz"],sr*.45),p["mid_db"],p["q"]), pb.HighShelfFilter(min(6000,sr*.4),p["high_db"],.7)])
    elif kind == "compressor":
        y = native(x, sr, [pb.Compressor(p["threshold_db"],p["ratio"],p["attack_ms"],p["release_ms"]), pb.Gain(p["makeup_db"])])
    elif kind == "gate":
        y = native(x, sr, [pb.NoiseGate(p["threshold_db"],10,p["attack_ms"],p["release_ms"])])
    elif kind == "expander":
        # A downward expander with a smoothed shared envelope.  The detector
        # is intentionally channel-linked so a stereo vocal does not wander
        # left/right when one side falls below the threshold.
        power = np.mean(x.astype(np.float64) ** 2, axis=1)
        window = max(1, int(sr * .008))
        env = np.sqrt(np.maximum(0, ndimage.uniform_filter1d(power, window, mode="nearest")))
        level_db = db(env)
        reduction_db = np.minimum(0, (level_db - p["threshold_db"]) * (p["ratio"] - 1))
        reduction_db = np.maximum(reduction_db, p["floor_db"])
        target = amp(reduction_db)
        smoothed = np.empty_like(target)
        previous = float(target[0])
        attack = max(1, int(sr * p["attack_ms"] / 1000))
        release = max(1, int(sr * p["release_ms"] / 1000))
        attack_coeff = math.exp(-1 / attack)
        release_coeff = math.exp(-1 / release)
        for i, value in enumerate(target):
            if i % 16384 == 0:
                check_cancel(cancel)
            # Attack opens the expander when wanted audio rises; release
            # closes it gradually after the signal drops below threshold.
            coeff = attack_coeff if value > previous else release_coeff
            previous = coeff * previous + (1 - coeff) * value
            smoothed[i] = previous
        y = x * smoothed[:, None]
    elif kind == "reverb":
        y = native(x, sr, [pb.Reverb(room_size=p["room_size"],damping=p["damping"],wet_level=p["mix"]/100,dry_level=1-p["mix"]/100)])
    elif kind == "delay":
        y = native(x, sr, [pb.Delay(p["time_ms"]/1000,p["feedback"]/100,p["mix"]/100)])
    elif kind == "chorus":
        y = native(x, sr, [pb.Chorus(rate_hz=p["rate_hz"],depth=p["depth"],mix=p["mix"]/100)])
    elif kind == "saturation":
        wet = np.tanh(x * amp(p["drive_db"])) / max(1, float(amp(p["drive_db"]*.4)))
        y = x*(1-p["mix"]/100) + wet*p["mix"]/100
    elif kind == "limiter":
        y = native(x, sr, [pb.Limiter(p["ceiling_db"], p["release_ms"])])
        y = np.clip(y, -amp(p["ceiling_db"]), amp(p["ceiling_db"]))
    elif kind == "normalize":
        rms = float(np.sqrt(np.mean(x.astype(float)**2)))
        gain = min(float(amp(p["target_db"]))/max(rms,1e-12), float(amp(p["ceiling_db"]))/max(float(np.max(np.abs(x))),1e-12))
        y = x*gain
    elif kind == "loudness":
        loudness=integrated_lufs(x,sr)
        if not np.isfinite(loudness):
            raise AudioError("Cần ít nhất 400 ms có âm thanh để chuẩn hóa LUFS.")
        gain=min(float(amp(p["target_lufs"]-loudness)),float(amp(p["ceiling_db"]))/max(float(np.max(abs(x))),1e-12))
        y=x*gain
    elif kind == "trim_silence":
        regions = silence_regions(x,sr,p["threshold_db"],p["min_s"])
        keep = np.ones(len(x),dtype=bool)
        for a,b in regions:
            lo = int((a + min(p["keep_s"],b-a)/2)*sr)
            hi = int((b - min(p["keep_s"],b-a)/2)*sr)
            keep[lo:hi] = False
        y = x[keep]
        if len(y) < 16:
            raise AudioError("Toàn bộ vùng là khoảng lặng; không tạo clip rỗng.")
    else:
        raise AudioError("Bộ xử lý chưa có.")
    check_cancel(cancel)
    if not np.isfinite(y).all():
        raise AudioError("Xử lý tạo dữ liệu không hữu hạn; kết quả đã bị loại bỏ.")
    return np.asarray(y,dtype=np.float32)


def chain(data, sr, effects, cancel=None, progress=None):
    x = np.array(data,dtype=np.float32,copy=True)
    for i, effect in enumerate(effects):
        check_cancel(cancel)
        x = apply_effect(x,sr,effect,cancel)
        if progress:
            progress((i+1)/max(1,len(effects)), EFFECTS[effect["kind"]]["title"])
    return x


def pan_width(x, pan=0, width=1):
    if x.shape[1] == 1:
        x = np.repeat(x,2,axis=1)
    mid = x.mean(axis=1)
    side = (x[:,0]-x[:,1])*.5*width
    y = np.column_stack([mid+side,mid-side])
    # Balance law: center unity on both stereo channels; full L/R suppresses other channel.
    p = np.asarray(pan)
    y[:,0] *= np.minimum(1,1-p)
    y[:,1] *= np.minimum(1,1+p)
    return y


def duck(x, reference, sr, threshold_db=-35, depth_db=12):
    power = np.mean(reference.astype(float)**2,axis=1)
    env = np.sqrt(ndimage.uniform_filter1d(power,max(1,int(sr*.025))))
    amount = np.clip((db(env)-threshold_db)/12,0,1)
    amount = ndimage.uniform_filter1d(amount,max(1,int(sr*.1)))
    return x * amp(-amount*depth_db)[:,None]


def integrated_lufs(x,sr):
    if len(x)<int(sr*.4) or not np.any(x):
        return float("-inf")
    import pyloudnorm
    return float(pyloudnorm.Meter(sr).integrated_loudness(np.asarray(x,dtype=np.float64)))


def meters(x, sr):
    x = np.asarray(x,dtype=np.float64)
    peak = float(np.max(np.abs(x))) if x.size else 0
    rms = float(np.sqrt(np.mean(x*x))) if x.size else 0
    # 4× polyphase estimate, explicitly not a certified ITU true-peak implementation.
    true = float(np.max(np.abs(signal.resample_poly(x,4,1,axis=0)))) if len(x) else 0
    corr = 1.0
    if x.ndim == 2 and x.shape[1] == 2 and np.std(x[:,0])>1e-12 and np.std(x[:,1])>1e-12:
        corr = float(np.corrcoef(x.T)[0,1])
    loudness=integrated_lufs(x,sr)
    return {"sample_peak_dbfs":float(db(peak)), "true_peak_estimate_dbtp":float(db(true)),
            "integrated_lufs":loudness if np.isfinite(loudness) else None,
            "rms_dbfs":float(db(rms)), "clipped_samples":int(np.count_nonzero(np.abs(x)>=1)),
            "phase_correlation":corr, "duration_s":len(x)/sr}


def match_rms(reference, processed):
    a = math.sqrt(float(np.mean(reference.astype(float)**2)))
    b = math.sqrt(float(np.mean(processed.astype(float)**2)))
    factor = min(10.0,a/max(b,1e-12))
    factor = min(factor, .99 / max(float(np.max(np.abs(processed))),1e-12))
    return (processed*factor).astype(np.float32)


def issues(data, sr):
    hop = max(1,int(sr*.1))
    findings = []
    for start in range(0,len(data),hop):
        x = data[start:start+hop]
        if len(x)<16:
            continue
        rms = float(np.sqrt(np.mean(x*x)))
        if np.max(np.abs(x)) >= .999:
            kind,text,fx = "clip","Có đỉnh gần 0 dBFS; kiểm tra clipping.","declip"
        elif -65 < db(rms) < -36:
            kind,text,fx = "quiet","Mức âm nhỏ; nghe kiểm tra trước khi tăng gain.","normalize"
        else:
            spectrum = np.abs(np.fft.rfft(x.mean(axis=1)))**2
            freqs = np.fft.rfftfreq(len(x),1/sr)
            high = spectrum[freqs>5000].sum()/max(spectrum.sum(),1e-12)
            flat = np.exp(np.mean(np.log(spectrum+1e-12)))/max(spectrum.mean(),1e-12)
            if high > .55 and rms > .01:
                kind,text,fx = "harsh","Năng lượng cao lớn; có thể chói hoặc âm xì.","deess"
            elif flat > .5 and rms > .005:
                kind,text,fx = "noise","Phổ gần nhiễu; có thể là tiếng nền hoặc nhạc cụ.","denoise"
            else:
                continue
        a,b = start/sr,min(len(data),start+hop)/sr
        if findings and findings[-1]["kind"] == kind and abs(findings[-1]["end"]-a)<.001:
            findings[-1]["end"] = b
        else:
            findings.append({"start":a,"end":b,"kind":kind,"description":text,"effect":fx})
    return findings


def analyze_music(x, sr, cancel=None):
    if len(x) > sr*300:
        raise AudioError("Phân tích tối đa 5 phút trong một lần.")
    import librosa
    mono = x.mean(axis=1)
    check_cancel(cancel)
    tempo, beats = librosa.beat.beat_track(y=mono,sr=sr,hop_length=512)
    check_cancel(cancel)
    chroma = librosa.feature.chroma_stft(y=mono,sr=sr,hop_length=512)
    profile = chroma.mean(axis=1)
    major=np.array([6.35,2.23,3.48,2.33,4.38,4.09,2.52,5.19,2.39,3.66,2.29,2.88])
    minor=np.array([6.33,2.68,3.52,5.38,2.60,3.53,2.54,4.75,3.98,2.69,3.34,3.17])
    notes=["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"]
    scores=[(float(np.corrcoef(profile,np.roll(template,k))[0,1]),notes[k]+suffix)
            for template,suffix in [(major," major"),(minor," minor")] for k in range(12)]
    scores=[s for s in scores if np.isfinite(s[0])]
    key=max(scores)[1] if scores else "Không rõ"
    chords=[]
    for start in range(0,chroma.shape[1],max(1,int(sr/512))):
        p=chroma[:,start:start+int(sr/512)].mean(axis=1)
        candidates=[(p[[k,(k+third)%12,(k+7)%12]].sum(),notes[k]+suffix)
                    for third,suffix in [(4,""),(3,"m")] for k in range(12)]
        chords.append({"time":start*512/sr,"name":max(candidates)[1]})
    check_cancel(cancel)
    value=float(np.asarray(tempo).reshape(-1)[0])
    return {"bpm":value if 20<=value<=400 else 120.,"key":key,"chords":chords,
            "beats":librosa.frames_to_time(beats,sr=sr,hop_length=512).tolist(),
            "method":"Ước lượng beat/chroma; cần người dùng kiểm tra và sửa."}


def alignment_offset(reference, target, sr, max_shift_s=2):
    hop=max(1,int(sr*.005))
    def envelope(x):
        y=np.mean(np.abs(x),axis=1)
        y=np.pad(y,(0,(-len(y))%hop)).reshape(-1,hop).mean(axis=1)
        return y-y.mean()
    a,b=envelope(reference),envelope(target)
    c=signal.correlate(a,b,mode="full",method="fft")
    lag=signal.correlation_lags(len(a),len(b),mode="full")
    keep=np.abs(lag)<=max_shift_s*sr/hop
    return float(lag[keep][np.argmax(c[keep])])*hop/sr
