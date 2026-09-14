# Nghiệm thu Windows sạch — CHƯA CHẠY

Không đánh dấu bất kỳ ô nào chỉ vì code tồn tại hoặc Linux tests đạt.

| Nhóm | Cấu hình cần chạy | Bằng chứng bắt buộc | Trạng thái phiên này |
|---|---|---|---|
| Hệ điều hành | Windows 10 22H2 x64; Windows 11 23H2 và 24H2 x64 | Build OS, CPU, RAM, GPU, driver âm thanh, dung lượng SSD, độ phân giải, scaling | Chưa chạy |
| Máy sạch | Không Python, SDK, NSIS, venv; tài khoản tiêu chuẩn | Snapshot VM và danh sách môi trường trước cài | Chưa chạy |
| Cài đặt | Installer `.exe`, đường dẫn có dấu/khoảng trắng, hủy cài, cài lại | SHA256, log, shortcut, Apps & Features, exit code | Chưa chạy |
| Khởi chạy | Từ Start Menu và executable, offline | Không lỗi DLL/codec, cửa sổ hoàn chỉnh, cold-start time | Chưa chạy |
| Phát âm thanh | Thiết bị mặc định, USB DAC, đổi thiết bị, không có thiết bị | Nghe thực, loop không click bất thường, báo lỗi rõ, CPU/dropout | Chưa chạy |
| Luồng chính | Nhập WAV/FLAC/MP3 → chia/cắt/di chuyển → preview → DSP → save → open → export | Dự án, file xuất, log thao tác, phép so sample/độ dài | Chưa chạy |
| An toàn dữ liệu | Undo/redo, 100 snapshot, autosave; kill process khi idle/render/save | Nguồn nguyên vẹn; mở recovery; file cũ vẫn hợp lệ khi save lỗi/hủy | Linux có bằng chứng nền tảng; Windows chưa chạy |
| Dữ liệu thật | Vocal phòng ồn/clip/reverb, đĩa than, mix có stems chuẩn | Before/after, phép đo với reference, nghe A/B cân loudness | Chưa có file người dùng/benchmark được cấp quyền |
| AI | Model/version/hash/license, CPU và GPU | Danh sách stem, chất lượng từng stem, bleed, thời gian/RAM/VRAM, cancel/OOM | Chưa chạy |
| VST3 | Ít nhất 3 plugin có giấy phép thử, một plugin lỗi/crash | Quét/nạp/render/state recall/reopen/timeout; tương thích DLL/GUI state | Chưa chạy plugin thật |
| Tải lớn | File 60/120 phút; 32/64 track 48 kHz; batch 100 file | Peak RAM, swap, disk free, thời gian, cancel, không hang hoặc export sai | Ngoài bằng chứng Linux hiện có |
| Lỗi | File hỏng/cắt cụt/codec lạ, hết disk, asset mất, archive sai hash, plugin mất | Không đổi dự án trước khi đủ dữ liệu; thông báo và log | Một phần được test Linux |
| UI/UX | 1280×800, 1920×1080; 100/150/200% DPI; bàn phím VN/EN | Không cắt nút/dialog, contrast, tab order, drag/drop, tooltip | Ảnh Qt Linux tối/sáng; Windows/DPI chưa chạy |
| Gỡ cài đặt | Uninstaller và Apps & Features | Xóa app/shortcut/registry; giữ project và recovery của user | Chưa chạy |
| Phát hành | Audit dependency/model/plugin, source obligation, chữ ký, không P0/P1 | SBOM/notice/source, certificate/signature, release sign-off theo kết quả | Chưa đạt |

P0: mất/ghi đè dữ liệu nguồn/dự án ngoài ý định; thực thi plugin không chủ ý; đầu ra âm thanh hỏng/sai nghiêm trọng. P1: crash/hang ở luồng chính, không mở được project hợp lệ, export sai số mẫu/kênh/định dạng hoặc recovery không đáng tin cậy. Lỗi P0/P1 đã xác nhận phải được sửa và chạy lại ca tái hiện trước phát hành. Hiện không được suy ra “không có P0/P1” cho môi trường chưa thử.

Mẫu record thủ công cho từng lượt:

```json
{
  "tester": "",
  "date_utc": "",
  "installer_sha256": "",
  "windows_edition_build": "",
  "cpu_ram_gpu_driver": "",
  "clean_machine_confirmed": false,
  "case_id": "",
  "input_fixture_sha256": "",
  "expected": "",
  "observed": "",
  "result": "NOT_RUN",
  "evidence_paths": [],
  "blocking_bug_ids": []
}
```
