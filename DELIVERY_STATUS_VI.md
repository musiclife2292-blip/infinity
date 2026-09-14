# Infinity audio — trạng thái bàn giao alpha

Phiên bản mã: **0.1.0-alpha.1**. Tên sản phẩm: **Infinity audio**.

## Đã có trong mã nguồn

- Ứng dụng desktop Qt tiếng Việt, timeline waveform/spectrogram, mixer, project `.infinity`, undo/redo, autosave/recovery, preview A/B và các chuỗi DSP đã nối vào giao diện.
- Bộ test tự động 93 ca, bằng chứng trước/sau DSP, kiểm tra codec và tải lớn.
- Tài liệu kiến trúc, hướng dẫn sử dụng, ma trận 47 yêu cầu, giới hạn, thông báo bên thứ ba và checklist nghiệm thu Windows sạch.
- PyInstaller spec, NSIS installer script, PowerShell build/test và GitHub Actions workflow để tạo bộ cài Windows x64.

## Cổng phát hành còn mở

- Môi trường hiện tại là Linux; không có Windows, Wine, NSIS hoặc thiết bị PortAudio. Vì vậy **chưa có `.exe` Windows** và chưa thể xác nhận cài/chạy/gỡ trên máy Windows sạch.
- AI Demucs, chất lượng tách stem, giảm bleed giữa stem và plugin VST3 cần runtime/model/plugin được cấp quyền để chạy nghiệm thu.
- Ma trận `docs/FEATURE_MATRIX_VI.md` ghi trạng thái từng tính năng, ca kiểm thử, kết quả đo và phần còn thiếu; không đánh dấu các bộ nối chưa chạy là đã hoàn tất.

## Lệnh tái tạo trên máy build

Linux chỉ dùng để kiểm thử phát triển:

```bash
.venv/bin/python -m pytest -q
.venv/bin/python scripts/validate_release.py evidence
.venv/bin/python scripts/write_report.py
```

Windows x64 dùng PowerShell:

```powershell
.\scripts\build_windows.ps1
    .\scripts\test_windows_install.ps1 -Installer .\dist\Infinity-audio-0.1.0-alpha.1-win64-setup.exe
```

Sau khi hai script Windows và checklist máy sạch đạt, cần lưu SHA-256 bộ cài và cập nhật báo cáo trước khi gọi là bản phát hành.
