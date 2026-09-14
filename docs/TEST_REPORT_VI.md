# Infinity audio — báo cáo kiểm thử và bàn giao kỹ thuật

Ngày lập: 2026-09-14. Phiên bản mã đang chuẩn bị: **0.1.0-alpha.2**. Tên phần mềm: **Infinity audio**.

## Kết luận nghiệm thu

**Chưa hoàn thành sản phẩm đủ 47 tính năng.** Alpha.1 đã có installer `.exe` build từ Actions, cài/chạy/gỡ và self-test đạt trên Windows Server 2022 CI (run `34842761393`). Alpha.2 sửa VST3 state/parameter handling và chờ Actions build lại. Không coi bộ nối AI chưa chạy là tách stem hoàn tất.

Lượt pytest cuối: **101/101 ca đạt, 0 lỗi, 0 bỏ qua**; gồm **7 ca tích hợp Qt offscreen/lifecycle**. Windows CI alpha.1 run `34842761393` ghi 96/96 ca đạt; alpha.2 còn chờ build lại.

## Môi trường thực tế

| Mục | Quan sát |
|---|---|
| OS | Linux-6.18.44-x86_64-with-glibc2.39 |
| Python | 3.12.14 (main, Aug 25 2026, 14:00:49) [Clang 22.1.3 ] |
| Kiến trúc / CPU logic | x86_64 / 9 CPU logic được báo |
| CPU model / RAM tổng / GPU | Không được môi trường công bố; không tự suy đoán |
| Peak RSS trong script đo tải | 911.5 MiB (toàn script, chưa cô lập từng ca) |
| Thiết bị phát | Không có PortAudio; không nghe qua thiết bị vật lý |
| Windows / máy ảo | Windows Server 2022 hosted runner đã build/cài/chạy/gỡ; Windows 10/11 consumer chưa chạy |
| AI / VST3 thực | Không có runtime/model AI; CHOWTapeModel fixture pinned được kiểm tra riêng, alpha.2 chờ Windows run |

Dependencies thực: numpy 2.2.4, scipy 1.15.2, PySide6 6.8.3, soundfile 0.13.1, sounddevice 0.5.1, pedalboard 0.9.17, librosa 0.11.0, pyloudnorm 0.1.1, numba 0.61.2, llvmlite 0.44.0, pytest 8.3.5. Có venv dùng một số dependency từ runtime được cài sẵn. Chưa đo trên cấu hình tối thiểu/khuyến nghị Windows; các cấu hình đó trong kiến trúc là mục tiêu thiết kế.

## Luồng và an toàn dữ liệu

Đã kiểm thử GUI Qt với import WAV thật, chọn clip/vùng, hiệu ứng, preview, apply, split, copy/paste, comp, undo/redo, đổi tối/sáng, spectrogram và đường save/open/export. I/O đọc/ghi file thật; phát âm thanh trong test GUI được thay bởi transport buffer để quan sát dispatch, **không phải kiểm tra đầu ra loa**. Tests riêng kiểm tra EOF/zero-fill/loop/mono của transport.

Project tests xác minh giữ checksum nguồn/tài sản, số mẫu sau split/gain/pan, lưu/mở giữ cả history, hủy save giữ file cũ, mô phỏng lỗi disk/atomic replace, rollback nếu autosave lỗi, archive traversal/hash mismatch bị từ chối. Một subprocess đã kết thúc đột ngột bằng `os._exit(7)` rồi mở recovery và undo thành công. Chưa thử mất điện, lỗi ổ đĩa thật hoặc process kill trong kernel Windows.

Job cancellation test dùng heartbeat Qt để xác minh vòng lặp UI vẫn chạy và kết quả bị hủy không commit vào model. Native DSP có ranh giới hủy khác nhau; chưa đo thời gian hủy cho mọi phép.

## Mẫu âm thanh trước–sau

Tất cả mẫu dưới đây là **tín hiệu tổng hợp**, có reference sạch do script tạo: giọng kiểu harmonic/envelope, sine, noise, hum, impulse và tone bất chợt. Không có giọng người thật, đĩa than thật hoặc nhạc nhiều stem. SNR chỉ đúng với fixture và phép đo đã định, không ngoại suy chất lượng phục hồi thực tế. File WAV mono 48 kHz/24 bit, xử lý nội bộ 24 kHz, dài 6 giây.

| Phép xử lý | SNR trước (dB) | SNR sau (dB) | Thời gian DSP (s) | Kết quả |
|---|---:|---:|---:|---|
| denoise | 12.61 | 18.75 | 0.082 | Đạt phép đo fixture |
| dehum | 5.44 | 10.71 | 0.011 | Đạt phép đo fixture |
| declick | 23.70 | 64.04 | 0.051 | Đạt phép đo fixture |
| declip | 12.05 | 33.66 | 0.535 | Đạt phép đo fixture |
| spectral | 9.89 | 38.66 | 0.015 | Đạt phép đo fixture |

File ở `evidence/audio-samples/`: mỗi phép có `*-reference.wav`, `*-before.wav`, `*-after.wav`. Có thể import vào ba track, solo từng track và nghe A/B. Không có mẫu tách stem trước/sau vì chưa chạy inference. `scripts/validate_release.py` tái tạo mẫu và số liệu; `validation-results.json` lưu thiết lập chính xác.

## Cao độ, effects và codec

- Các processors kiểm tra output float32 hữu hạn, không sửa input. Ca riêng đo de-hum, de-click, de-clip, de-ess, EQ, bass, compressor, gate, effects, ceiling, LUFS, pan/phase, ducking và các vùng phổ.
- Pitch +12 semitone trên 440 Hz giữ số mẫu và ra gần 880 Hz. Tempo 1.25 giảm thời lượng đúng và giữ peak gần 440 Hz. Autotune đơn âm đưa 452 Hz về gần 440 Hz trong fixture. Chưa kiểm tra vibrato/nhạc phức tạp bằng tai.
- BPM/key test trên hợp âm tổng hợp C major với phách 120 BPM; không phải benchmark nhận diện trên danh mục bài hát.
- Roundtrip WAV16/24/float32, FLAC16/24, MP3, resample và mono/stereo đạt. Chặn file hỏng, NaN, format không hỗ trợ, ghi đè không cho phép và PCM/MP3 vượt mức.

| MP3 CBR yêu cầu | Bitrate ffprobe quan sát | Sample rate | Kênh | Kết quả |
|---:|---:|---:|---:|---|
| 96 kbps | 96 kbps | 48000 Hz | 2 | Khớp |
| 128 kbps | 128 kbps | 48000 Hz | 2 | Khớp |
| 160 kbps | 160 kbps | 48000 Hz | 2 | Khớp |
| 192 kbps | 192 kbps | 48000 Hz | 2 | Khớp |
| 256 kbps | 256 kbps | 48000 Hz | 2 | Khớp |
| 320 kbps | 320 kbps | 48000 Hz | 2 | Khớp |

Các bitrate này được xác minh với libsndfile tại Linux, không tự suy ra Windows DLL tương đương. FFmpeg/ffprobe không được đóng gói vào ứng dụng.

## Tải lớn trong giới hạn hiện có

| Tình huống | Thời gian đo | Kết quả và giới hạn |
|---|---:|---|
| 32 tracks × 30 seconds, same source at -40 dB | 0.966 s | Đạt — Sai số mẫu tối đa 3.73e-08 |
| 10-minute mono project, 24 kHz; save/reopen/export FLAC | 5.339 s | Đạt — 14,400,000 frame ở đầu ra resample đọc lại |
| 20 files × 6 seconds, EQ → limiter → FLAC | 0.384 s | Đạt — 20 file hoàn tất |

32 track dùng cùng một asset synthetic để đo tổng mix, không phải 32 bản thu độc lập với chuỗi AI. File 10 phút là mono 24 kHz không FX, lưu/mở và xuất FLAC; không chứng minh xử lý file nhiều giờ. Peak RSS toàn script gần 1 GiB bao gồm các mảng tồn tại đồng thời; số 128 MiB trong engine là ngân sách buffer cuối, không phải RAM tổng. Không đo GPU/VRAM hoặc Windows real-time dropout.

## Lỗi được phát hiện và xử lý

| ID | Lỗi thực tế | Sửa và bằng chứng |
|---|---|---|
| DSP-001 | De-ess split high-pass causal bị lệch pha; trừ khỏi dry không giảm dải 8 kHz đủ mức | Chuyển split offline sang zero-phase sosfiltfilt; chạy lại test giảm 8 kHz/giữ 440 Hz. Xem `deess-regression.xml` và pytest cuối |
| UI-001 | Nền mixer trắng trong theme tối | Đặt nền widget theo theme; chụp lại cửa sổ Qt thật |
| UI-002 | Biểu tượng full-width plus hiện ô thiếu glyph | Dùng ký tự plus tương thích; ảnh chụp lại |
| DSP-002 | Expander dùng ngược attack/release, dễ làm mất đầu tiếng | Attack mở, release đóng; kiểm tra transient DC, liên kết stereo, ratio=1 và đuôi im lặng |
| VST-001 | Giá trị tham số Pedalboard không truyền được qua pipe | Chuyển scalar theo kiểu tham số; VST3 thật quét/nạp/render và khôi phục dự án được kiểm tra |
| VST-002 | Hộp tham số sửa trực tiếp object trong dự án trước render | Sao chép thiết lập và bỏ cấu hình khi chọn plugin khác; thêm GUI tests và self-test trong binary |

Không có lỗi mất dữ liệu được phát hiện trong tập ca đã chạy. Không tuyên bố không còn P0/P1 trên Windows hoặc phần AI/plugin chưa thử. Cổng phát hành vẫn đóng.

## Giấy phép và đóng gói

Mã nguồn GPL-3.0-only, đi cùng toàn văn GPL và notice thu từ dependency. Script thu inventory theo dependency thực tế, bổ sung LICENSE.txt của CPython trên Windows và dừng build nếu thiếu notice CPython. Việc thu notice không thay thế audit nguồn tương ứng và quyền phân phối. Trọng số Demucs không được gộp và không tự tải. Chưa ký số.

PyInstaller, NSIS và quy trình cài/chạy/gỡ đã đạt trên Windows Server 2022 CI ở alpha.1, run `34842761393`, commit `bc75e6abc987f16ffeb9a04ca4498d6cda379c33`. Installer SHA-256: `641a1ab42d71b886f87e060dca051a537533d849a21f71dbb16c9aec61317107`. Đây là bằng chứng alpha.1; alpha.2 chứa sửa VST3 và Expander cần Windows run riêng. `clean_machine_confirmed` và `audio_hardware_verified` vẫn false.

Nhật ký binary Linux của mốc trước nằm ở `evidence/linux-freeze-smoke.txt`; không coi đó là bằng chứng alpha.2 hoặc Windows.

## Phần việc cần hoàn tất

1. Build và sửa mọi lỗi phát sinh trên Windows x64; nghiệm thu cài/khởi chạy/gỡ trên máy sạch không có môi trường lập trình, rồi nghe thiết bị thật.
2. Hoàn thiện các hạng mục thiếu trong ma trận: AI/stem/bleed, chất lượng phục hồi, note editor/warp/alignment, comping nâng cao, EQ trực quan, FX automation, true peak và tương thích nhiều plugin thực.
3. Có corpus âm thanh đại diện được cấp quyền và test mù trước/sau; đo chất lượng lẫn hiệu năng trên cấu hình mục tiêu.
4. Hoàn tất notice/source/model/codec audit, pin dependency Windows, chữ ký, kiểm tra DPI và phát hành khi không còn P0/P1 đã biết và đủ 47 yêu cầu có bằng chứng.

## Bảng đối chiếu đủ 47 tính năng

**Chưa nghiệm thu sản phẩm đầy đủ.** “Cơ bản đã kiểm thử” chỉ xác nhận hành vi được mô tả và test trong cột bằng chứng; không đồng nghĩa đạt chất lượng chuyên nghiệp hoặc chạy trên mọi bản Windows. Alpha.1 có 96 tests và cài/chạy/gỡ đạt trên Windows Server 2022 CI (run 34842761393); các thay đổi alpha.2 phải có kết quả Windows riêng. Cột thiếu là điều kiện tiếp tục, không bị bỏ khỏi phạm vi.

**22** Một phần / cần đánh giá thêm; **22** Cơ bản đã kiểm thử; **2** Bộ nối có mã, chưa nghiệm thu; **1** Chưa triển khai.

| # | Tính năng | Trạng thái / giai đoạn | Ca kiểm thử | Kết quả thực tế | Còn thiếu |
|---|---|---|---|---|---|
| 1 | Lọc nhiễu | Một phần / cần đánh giá thêm · M2/M4 | test_noise_reduction_improves_snr_on_gated_harmonics; sample denoise | Spectral gain có cường độ và nền còn lại; SNR tín hiệu tổng hợp cải thiện, xem bảng đo. | Chưa đánh giá giọng thật/nhiễu xe không dừng hoặc độ tự nhiên. |
| 2 | Phục hồi giọng hát | Một phần / cần đánh giá thêm · M2/M4 | test_processors_return_audio_without_mutating_input[restore] | Chuỗi khử nền, high-pass và EQ tạo audio thật, không sửa input. | Chưa phục hồi AI hoặc minh chứng giữ đặc trưng giọng trên bản thu hỏng. |
| 3 | Bass boosted | Cơ bản đã kiểm thử · M2 | test_bass_increases_low_relative_to_mid | Tăng vùng bass so với 1.5 kHz >2 lần trong ca thử; output dưới ceiling -1 dBFS. | Nghe đánh giá trên loa/tai nghe và nhạc thật; true-peak limiter còn thiếu. |
| 4 | De-clip | Một phần / cần đánh giá thêm · M2/M4 | test_declip_reduces_clipped_sine_mse; sample declip | Nội suy cubic giảm lỗi trên sine bị clip ngắn; threshold và mức sửa có tham số. | Không phục hồi plateau dài, clipping nhiều tầng hoặc nội dung đã mất; chưa test giọng thật. |
| 5 | De-click / De-crackle | Một phần / cần đánh giá thêm · M2 | test_declick_reduces_impulse_error; sample declick | Median detector giảm MSE xung thêm vào tín hiệu; có độ nhạy/cửa sổ. | Chưa dataset đĩa than/crackle dày; có nguy cơ xóa transient. |
| 6 | De-hum | Cơ bản đã kiểm thử · M2 | test_dehum_attenuates_50_and_harmonics_preserves_voice | 50/100 Hz bị giảm theo ngưỡng test, giữ tone 997 Hz; cơ bản/họa âm/Q chỉnh được. | Cần thử nhiễu điện trôi tần số và thiết bị Windows. |
| 7 | De-reverb | Một phần / cần đánh giá thêm · M4 | test_processors_return_audio_without_mutating_input[dereverb] | Có ước lượng giảm đuôi phổ trả dữ liệu hữu hạn. | Chưa WPE/AI, phép đo độ rõ hoặc nghe A/B phòng thật; không coi là phục hồi chuyên nghiệp. |
| 8 | De-ess và giảm bật hơi | Một phần / cần đánh giá thêm · M2 | test_deess_reduces_sibilant_band | Đã sửa lỗi lệch pha split-band; test giảm tone 8 kHz và giữ 440 Hz đạt. High-pass cho bật hơi. | Chưa mẫu phụ âm s/x/p/b người thật; cần đánh giá mất phụ âm và màu giọng. |
| 9 | Chỉnh sửa phổ âm | Cơ bản đã kiểm thử · M2 | test_spectral_selected_frequency_and_time; test_gui_spectrogram_and_direct_spectral_selection | Có ảnh STFT và chọn chữ nhật nối tham số. Tone 3 kHz vùng chọn giảm, 500 Hz và vùng ngoài được giữ. | Chưa brush, log axis, nội suy phục hồi phổ hoặc tách âm chồng tần số. |
| 10 | Tách vocal và nhạc nền | Bộ nối có mã, chưa nghiệm thu · M4 | test_ai_missing_and_plugin_invalid_file (chỉ lỗi/manifest) | Có bộ nối Demucs local và UI báo thiếu runtime/model. Không có lần inference thành công. | Runtime, model có quyền sử dụng/phân phối, kết quả và before/after stem thực tế. |
| 11 | Tách nhiều stem | Bộ nối có mã, chưa nghiệm thu · M4 | test_ai_missing_and_plugin_invalid_file (chỉ manifest) | Công bố 4 stem drums/bass/other/vocals; 6 stem thêm guitar/piano. Adapter kiểm tra nguồn model. | Chưa chạy model 4/6 stem, chưa quality benchmark/đóng gói. |
| 12 | Quản lý stem | Cơ bản đã kiểm thử · M1 | test_solo_mute_pan_gain_automation; test_gui_desktop flow | Stem nhập sẵn là track có mute/solo/gain và xuất riêng qua renderer. | Quản lý kết quả AI chưa có inference để nghiệm thu; UI export stem chưa tự động test riêng. |
| 13 | Giảm âm thanh lọt giữa stem | Chưa triển khai · M4 | Chưa có test hoặc thuật toán | Không có bộ giảm bleed chuyên biệt. | Thiết kế, triển khai thuật toán theo stem/reference, đo giảm bleed và mất nhạc cụ. |
| 14 | Tạo bản phối rút gọn | Cơ bản đã kiểm thử · M1/M4 | test_solo_mute_pan_gain_automation | Mute/solo các track cho mix rút gọn; lệnh karaoke tắt vocal khi đã có stem. | Chưa tách stem từ mix đầu vào; cần nghe bài thật. |
| 15 | Biên tập đoạn nhạc | Cơ bản đã kiểm thử · M1 | test_edit_save_reopen_export_equivalent; test_gui_comping_and_copy_paste | Chia/trim/copy/paste/duplicate/move/delete và gộp track tạo quyết định sửa thật. | Chưa nhiều clip selection/ripple mode; kéo GUI cần thử Windows/HiDPI. |
| 16 | Chỉnh sửa nhiều track | Cơ bản đã kiểm thử · M1 | test_32_track_deterministic_sum; stress 32×30s | 32 track render có sai số mẫu được đo; timeline, mixer và tài sản riêng. | Chưa engine streaming nhiều giờ/64 track nhạc thật. |
| 17 | Fade và crossfade | Cơ bản đã kiểm thử · M1/M2 | test_fade_split_and_trim_samples | Fade tuyến tính vào/ra có ảnh hưởng đo được; crossfade chỉnh overlap + hai fade bổ sung. | Cần nghe điểm ghép trên nhạc tương quan khác nhau; chưa equal-power curve lựa chọn. |
| 18 | Phát hiện khoảng lặng | Cơ bản đã kiểm thử · M2 | test_silence_detection_and_shorten | Tìm đoạn 1–2s trong fixture và rút ngắn về thời lượng mong đợi; GUI đặt marker hoặc áp dụng. | Chưa đánh giá threshold tối ưu trên giọng nhỏ/nhạc ambience. |
| 19 | Loop, marker và cấu trúc bài | Cơ bản đã kiểm thử · M1 | test_transport_eof_loop_and_mono; test_marker_structure_survives_roundtrip | Buffer lặp chính xác; marker Intro/Verse/Chorus lưu/mở lại đúng. | Chưa nghe loop qua driver thật hoặc giao diện quản lý marker nâng cao. |
| 20 | Chỉnh sửa không phá hủy | Cơ bản đã kiểm thử · M1 | test_undo_redo_branch_and_assets_immutable; test_edit_save_reopen_export_equivalent | Asset SHA bất biến; undo/redo, branch history và project roundtrip giữ số mẫu/state. | Giới hạn 100 snapshot; cần Windows filesystem/crash tests. |
| 21 | Sửa cao độ | Một phần / cần đánh giá thêm · M3/M4 | test_monophonic_correction_reduces_detuning | YIN + correction chromatic giảm lệch tone 452 Hz về gần 440 Hz; chỉnh tay qua vùng + bán âm. | Piano roll từng nốt, thang âm, retune/formant mượt và giọng thật chưa đạt. |
| 22 | Đổi tông giữ tốc độ | Cơ bản đã kiểm thử · M2 | test_pitch_shift_preserves_duration | Dịch +12 bán âm: tone 440→gần 880 Hz, giữ số mẫu. | Nghe artefact/transient/formant trên nhạc thật. |
| 23 | Đổi tốc độ giữ cao độ | Cơ bản đã kiểm thử · M2 | test_tempo_preserves_pitch | Rate 1.25 tạo số mẫu đúng và peak gần 440 Hz. | Chưa warp tempo map biến thiên hoặc chất lượng cực trị. |
| 24 | Căn nhịp | Một phần / cần đánh giá thêm · M3 | Session.move và lệnh quantize đầu clip | Snap đầu clip theo BPM có mã nối UI/model. | Chưa transient detection + warp marker cho các phách trong clip; chưa ca nghiệm thu riêng snap UI. |
| 25 | Căn các lớp vocal | Một phần / cần đánh giá thêm · M3/M4 | test_alignment_known_delay | Cross-correlation envelope tìm độ trễ 250 ms trong fixture; UI dịch clip theo tham chiếu. | Chưa căn từng âm tiết/câu hoặc DTW trên take khác nhau. |
| 26 | Comping | Một phần / cần đánh giá thêm · M1/M3 | test_gui_comping_and_copy_paste | Vùng take được chép đúng offset/length vào track Comp vocal. | Chưa take lanes, lựa chọn loại trừ hoặc tự mute tất cả take nguồn; cần nghe điểm nối. |
| 27 | Biến đổi giọng | Một phần / cần đánh giá thêm · M2/M4 | test_harmony_adds_requested_interval; test_formant_changes_envelope_preserves_fundamental | Tạo bè quãng cố định và formant envelope thử nghiệm tạo biến đổi đo được. | Chưa giữ tự nhiên hoặc chọn bè theo hợp âm; chưa model biến đổi giọng. |
| 28 | EQ | Một phần / cần đánh giá thêm · M2 | test_eq_mid_adjustment | Ba dải với shelf thấp/cao và parametric mid; gain/mid frequency/Q hoạt động. | Chưa đồ thị tương tác kéo các dải EQ trực tiếp. |
| 29 | Compressor | Cơ bản đã kiểm thử · M2 | test_compressor_reduces_dynamic_range | Threshold/ratio/attack/release/makeup; giảm chênh lệch mức theo test. | Chưa gain-reduction meter realtime, knee hay lookahead tùy chỉnh. |
| 30 | Gate / Expander | Cơ bản đã kiểm thử · M2 | test_gate_quiet_floor; test_expander_reduces_quiet_floor_with_soft_release; test_expander_attack_opens_and_release_closes_without_stereo_shift | Gate giảm nền; expander liên kết kênh có ratio, sàn dB, attack mở nhanh và release đóng chậm. Alpha.2 bổ sung kiểm tra cùng hành vi trong binary. | Bằng chứng mới cục bộ; Windows alpha.2 chờ chạy. Chưa có knee, sidechain detector riêng hoặc đánh giá nghe thật. |
| 31 | Reverb / delay / chorus / saturation | Cơ bản đã kiểm thử · M2 | test_effects_audibly_alter_signal (4 cases) | Bốn hiệu ứng tạo thay đổi đo được; wet/drive/feedback/rate có tham số. | Đuôi hiệu ứng bị giới hạn bởi độ dài clip; cần nghe A/B thật. |
| 32 | Pan và stereo width | Cơ bản đã kiểm thử · M1/M2 | test_pan_width_mono_and_phase; test_solo_mute_pan_gain_automation | Balance trái/phải và mid/side width được kiểm tra bằng dữ liệu. | Chưa tùy chọn pan law hoặc surround. |
| 33 | Automation | Một phần / cần đánh giá thêm · M2/M3 | test_solo_mute_pan_gain_automation; test_track_count_guard_and_automation_order | Điểm gain/pan nội suy theo thời gian, lưu trong project và ảnh hưởng render. | Chưa automation tham số hiệu ứng hoặc ghi đường cong realtime. |
| 34 | Sidechain / Ducking | Cơ bản đã kiểm thử · M2 | test_ducking_follows_reference | Mức nhạc giảm ở vùng có reference, vùng không có giữ nguyên; UI chọn source/depth. | Detector pre-FX, threshold cố định ở UI; chưa MIDI/sidechain plugin routing. |
| 35 | Limiter và cân bằng độ lớn | Một phần / cần đánh giá thêm · M2 | test_limiter_ceiling_and_normalize; test_loudness_normalization_and_channel_sum | Sample ceiling, RMS và integrated LUFS normalization có đo kiểm. | Chưa true-peak limiter được xác nhận; headroom có thể ngăn đạt LUFS mục tiêu. |
| 36 | Đo mức âm thanh | Một phần / cần đánh giá thêm · M2/M5 | test_loudness_normalization_and_channel_sum; meters on sample fixtures | LUFS/RMS/sample peak/clipping count và TP ước lượng 4×. | UI đo tối đa 60s; chưa realtime meter hoặc bộ chuẩn BS.1770/true-peak reference đầy đủ. |
| 37 | Kiểm tra pha và mono | Cơ bản đã kiểm thử · M2 | test_pan_width_mono_and_phase; test_transport_eof_loop_and_mono | Phản pha tương quan gần -1, mono triệt tiêu fixture đúng; có checkbox mono. | Chưa nghe thực qua driver Windows. |
| 38 | BPM, tông và hợp âm | Một phần / cần đánh giá thêm · M3 | test_bpm_key_chords_on_synthetic_c_major | Fixture C major/120 BPM qua nhận diện cơ bản; hộp cho sửa BPM/key/chords. | Chưa benchmark bài thật, hợp âm đảo/tông tương đối; kết quả heuristic cần sửa. |
| 39 | So sánh trước–sau | Một phần / cần đánh giá thêm · M1/M2 | test_rms_ab_matching; test_desktop_import_edit_preview_save_reopen_export | Preview tạo cặp A/B không commit, bù RMS; test route phát qua buffer giả lập. | Chưa nghe thiết bị thật; chuyển A/B khởi động lại đầu vùng, không seamless. |
| 40 | Xuất nhiều định dạng | Cơ bản đã kiểm thử · M1/M2 | test_audio_roundtrip (6 variants); codec ffprobe evidence | WAV16/24/float32, FLAC16/24, MP3; rate/channels; 6 CBR bitrate khớp ffprobe. | Cần kiểm lại Windows codec DLL và decoded MP3 true peak; chưa dither. |
| 41 | Xử lý hàng loạt | Một phần / cần đánh giá thêm · M2/M5 | stress 20×6s EQ→limiter→FLAC; export cancellation/error tests | 20 file xử lý thành công; UI batch có report từng file và tiếp tục sau lỗi. | Chưa end-to-end GUI batch 100 file/Windows hoặc resume sau restart. |
| 42 | Tự phát hiện vấn đề | Một phần / cần đánh giá thêm · M3 | test_issue_detection_positions | Quét heuristic đánh dấu gần clipping, nhỏ, chói, nền phổ phẳng; thời gian fixture clipping đúng. | Chưa precision/recall với dataset bản thu thật; false positives có thể nhiều. |
| 43 | Gợi ý xử lý | Một phần / cần đánh giá thêm · M3 | test_gui_desktop preview; source issue_clicked + effect mapping | Mỗi dấu hiệu có giải thích, vùng thời gian và preset/effect đề xuất; nghe thử trước áp dụng. | Chưa đánh giá hiệu quả đề xuất hoặc cá nhân hóa tham số theo nguồn. |
| 44 | Preset theo mục đích | Một phần / cần đánh giá thêm · M2/M4 | DSP chain tests; preset persistence implementation | Vocal tự nhiên, bản thu cũ, bass, lời nói; lưu preset JSON. Karaoke dùng stem sẵn có. | Karaoke AI chưa chạy; preset riêng chưa có ca GUI lưu/mở riêng. |
| 45 | Cường độ xử lý | Cơ bản đã kiểm thử · M2 | test_desktop_import_edit_preview_save_reopen_export; DSP parameter tests | Wet/dry tổng trong preview/apply và tham số mức xử lý từng effect. | Đổi thời lượng cần 100%; thanh tổng không tác động rack/batch; nghe đánh giá nhẹ/mạnh còn thiếu. |
| 46 | Lịch sử, tự lưu và phục hồi | Cơ bản đã kiểm thử · M1/M5 | test_recovery_after_process_abrupt_exit; test_failed_autosave_rolls_back_model; atomic-save tests | Kill process exit 7 rồi recovery giữ vị trí; undo sau recovery; lỗi save giữ bản cũ và rollback model. | Chưa crash khi Windows đang ghi đĩa thật, lost power hoặc cache cleanup; giới hạn 100 snapshots. |
| 47 | Plugin bên ngoài | Một phần / cần đánh giá thêm · M4/M5 | test_scan_vst_bundles_and_fault_isolation; test_ai_missing_and_plugin_invalid_file; self-test VST3 CHOWTapeModel | Quét/nạp plugin thật, kết xuất thay đổi audio, lưu/mở dự án và phục hồi state kèm tham số đạt trên Linux; workflow alpha.2 chạy cùng fixture trên binary Windows. | Chưa nhiều vendor, native crash fixture, GUI editor hoặc latency compensation. Raw state riêng của fixture không giữ gain; tham số công khai được lưu/nạp kèm. |
