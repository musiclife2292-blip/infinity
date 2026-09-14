# Giới hạn và phần việc còn thiếu

**Chưa hoàn thành sản phẩm được yêu cầu.** Đây là mốc alpha có bộ xử lý và tests thật. Toàn bộ 47 yêu cầu vẫn là phạm vi mục tiêu; các khoảng trống dưới đây không được tự ý đổi thành tính năng đã hoàn tất.

## Các việc chặn nghiệm thu

1. Chưa có `.exe` Windows được build; chưa cài/khởi chạy/gỡ trên Windows sạch; chưa thử loa/tai nghe/driver thật.
2. Chưa có inference tách stem thực tế hoặc mẫu stem trước/sau; model/runtime chưa đóng gói, quyền trọng số chưa được giải quyết. Bộ giảm bleed chưa triển khai.
3. Phục hồi giọng/de-reverb còn DSP cơ bản thử nghiệm; chưa nghe đánh giá với bản thu người thật. Sửa pitch mới đơn âm/chromatic và chọn vùng thủ công; chưa có piano roll từng nốt, scale snapping thông minh, formant-preserving retune.
4. Căn nhịp chỉ dời đầu clip; căn vocal chỉ một độ trễ toàn clip. Chưa warp/DTW theo câu. Comping là ghép vùng thủ công, chưa take lanes với lựa chọn loại trừ.
5. EQ mới ba dải qua số, chưa đồ thị kéo điểm trực tiếp. Gate có xử lý, expander độc lập còn thiếu. Automation mới gain/pan, chưa tham số FX.
6. LUFS có phép đo thực nhưng UI chỉ đo tối đa 60 giây đầu buffer. True peak 4× là ước lượng, limiter chưa kiểm soát true peak đạt chuẩn; chưa có chứng nhận meter/limiter. Chưa dither xuất PCM16/24.
7. VST3 có code quét/nạp/state/render/cách ly tiến trình và đã thử lỗi đầu vào; chưa thử một plugin hợp lệ thực tế hoặc crash native. Chưa editor plugin gốc/MIDI/instrument/latency compensation. State recall thành công chưa có bằng chứng.
8. Audit notice và nguồn tương ứng GPL/Qt/DLL/codec trên Windows chưa hoàn tất; chưa chứng thư ký số. Bộ cài alpha không được coi là release đã kiểm duyệt.

## Giới hạn vận hành hiện có

- Import tối đa 256 MiB sau giải mã/resample dự kiến, mono/stereo. Không multichannel surround, recording input, video, ASIO hoặc MIDI.
- Render tối đa 128 MiB cho buffer stereo float32 cuối (~5 phút 50 giây ở 48 kHz). Đây là giới hạn buffer đầu ra, **không** là giới hạn RAM tổng; tests stress quan sát peak RSS gần 1 GiB. Bản phối nhiều giờ cần streaming engine.
- DSP tối đa 5 phút / 128 MiB mỗi lần; autotune tối đa 60 giây; spectrogram tối đa 5 phút clip; adapter AI tối đa 2 phút. Native operation có thể chỉ nhận cancel ở ranh giới phép toán; UI vẫn nhận sự kiện, nhưng thời gian hủy chưa được đo trên tất cả thuật toán.
- 128 track, 10.000 clip/track, 32 FX/track được kiểm tra schema; không nghĩa mọi cấu hình đó đã stress test. Bằng chứng thực tế: 32 track × 30 giây và 10 phút mono 24 kHz không FX.
- Toàn bộ DSP kết xuất trước khi phát; thay đổi mixer/effect phải phát lại. Không có engine realtime FX độ trễ thấp.
- Reverb/delay tail chỉ tồn tại trong thời lượng input; tail quá cuối clip bị cắt. Transient/vibrato có thể đổi trong phase vocoder, spectral gating, de-click và formant.
- Bù A/B là RMS, không LUFS; mỗi lần chuyển nghe lại từ đầu vùng, không chuyển liền mạch tại cùng sample. Meter và gain bảo vệ monitor không thay đổi file xuất.
- 100 snapshot lịch sử; gói dự án tối đa 8 GiB và manifest 16 MiB. Tài sản/phiên tạm không được tự dọn; cần quản lý dung lượng cho dự án dài. ZIP save dùng tài sản toàn bộ history nên lớn hơn mix cuối.
- GUI khóa thao tác sửa trong lúc có một job, vẫn repaint và cho hủy. Chưa có hàng đợi nhiều job đồng thời.
- Batch giữ các output đã hoàn tất khi hủy, và tiếp tục sau lỗi riêng từng file; chưa queue resume qua restart. Thanh cường độ tổng chỉ tác động Apply/Preview, không rack/batch.
- Tìm vấn đề và BPM/key/chords là heuristic; có thể nhầm nhạc cụ với nhiễu, false positive clipping hoặc hợp âm. Không chẩn đoán chất lượng giọng tự động.
- Giao diện spectral còn thang tần số tuyến tính; chưa log-frequency axis/brush/interpolation spectral repair. Chọn clip khác cần tạo ảnh phổ cho clip đó.

Không có bằng chứng “đạt chất lượng chuyên nghiệp” trên giọng thật, môi trường Windows, AI hoặc VST3 thật. Không có lỗi data-loss được phát hiện trong tập tests đã chạy; điều đó không đảm bảo không có lỗi ở phần chưa kiểm thử.
