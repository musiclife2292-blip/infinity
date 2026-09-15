# Build và đóng gói Windows

**Alpha.1 đã build bằng GitHub Actions và qua cài/chạy/gỡ trên Windows Server 2022 CI, run 34842761393. Alpha.2 bổ sung sửa lỗi và kiểm thử VST3 thật. Kiểm tra artifact và báo cáo của từng run trước khi sử dụng; Windows 10/11 sạch và thiết bị âm thanh vẫn chưa nghiệm thu.**

## Build bản cơ bản

Máy build Windows x64, Python 3.12 x64, NSIS 3.x (`makensis.exe`, workflow tham chiếu 3.11), Internet để lấy dependency. Không dùng Python 3.13 cho tập dependency này.

```powershell
Set-Location C:\src\infinity-audio
.\scripts\build_windows.ps1
```

Nếu cần chỉ rõ Python hoặc NSIS:

```powershell
.\scripts\build_windows.ps1 -Python C:\Python312\python.exe -Makensis "C:\Program Files (x86)\NSIS\makensis.exe"
```

Script tạo venv, cài dependency, chạy tests, kiểm kê license, tạo icon, PyInstaller onedir, chạy smoke test executable và NSIS. Kết quả **dự kiến khi build thành công**:

- `dist/InfinityAudio/InfinityAudio.exe` cùng `_internal/`.
- `dist/Infinity-audio-0.1.0-alpha.2-win64-setup.exe`.

Không chỉ sao chép `InfinityAudio.exe` trong onedir: cần toàn bộ `_internal`. Bộ cài NSIS đã cấu hình mang theo cả thư mục. Nó cài vào `%LOCALAPPDATA%\Programs\InfinityAudio`, tạo shortcut Start Menu, ghi Apps & Features cho user hiện tại và tạo uninstaller; không đòi admin. Chưa đăng ký liên kết mặc định `.infinity`. Cần kiểm tra máy Windows sạch để phát hiện thiếu Qt DLL, libsndfile, PortAudio, runtime MSVC hoặc lazy import librosa.

Các root dependency được pin. Các dependency bắc cầu chưa có lock Windows bằng hash đã nghiệm thu; mỗi artifact build chứa `third_party_licenses/inventory.json` và `evidence/windows-build/dependencies.txt` của chính máy build đó. Đây chưa phải SBOM hoàn chỉnh Windows. Trước release cần pin toàn bộ tập build Windows; workflow hiện đã lưu SHA-256 của installer và artifacts.

PyInstaller không là cross-compiler. Không đổi đuôi một file Linux thành `.exe`. Bản Qt offscreen trên Linux chỉ chứng minh logic/UI có thể chạy trong môi trường đó.

## Kiểm tra bộ cài

```powershell
.\scripts\test_windows_install.ps1 -Installer .\dist\Infinity-audio-0.1.0-alpha.2-win64-setup.exe
```

Script dùng thư mục thử riêng, từ chối nếu tài khoản đã có Infinity audio, chạy install silent, smoke-test, uninstall và ghi JSON cấu hình máy/kết quả. Cờ `clean_machine_confirmed` và `audio_hardware_verified` mặc định false: script không thể chứng minh những điều đó. Người thử cần hoàn thành checklist Windows sạch, dùng tài khoản không có Python/venv/NSIS trên máy đích, thử loa/tai nghe và các luồng thực.

Workflow `.github/workflows/windows-build.yml` dùng `windows-2022`, tạo **artifact alpha** trên repo `musiclife2292-blip/infinity`. Máy build và máy thử cài tách riêng; máy thử loại developer tools khỏi PATH. Fixture CHOWTapeModel được tải từ commit cố định, kiểm tra SHA-256 và chỉ dùng kiểm thử VST3. Windows Server CI không thay thế Windows 10/11 consumer sạch, HiDPI, WASAPI/thiết bị âm thanh và việc nghe đánh giá.

## AI — phần phát triển chưa nghiệm thu

Bản cơ bản không có Demucs/PyTorch/trọng số. `src/infinity_audio/ai.py` là bộ nối thử nghiệm qua tiến trình riêng. Không có HTTP hoặc auto-download trong ứng dụng. `get_model(..., repo=Path(...))` dùng repo local, cần cấu trúc signature `.th` và YAML đúng Demucs.

Để triển khai giai đoạn M4, cần:

1. Chốt một model được cấp phép phù hợp mục đích phân phối và tài liệu quyền trọng số; không suy ra từ MIT của mã nguồn.
2. Tạo môi trường AI riêng, pin cặp PyTorch/torchaudio phù hợp với Demucs 4 và Python/Windows đã chọn, gồm julius và các dependency cần thiết. Bộ nối hiện chưa được kiểm chứng với môi trường đó.
3. Chạy các mẫu phân tách có ground truth; đánh giá vocals/drums/bass/other và guitar/piano riêng; đo bleed, SDR/SI-SDR, artefact và nghe mù.
4. Đóng gói runtime/model vào gói tùy chọn tự chứa, kiểm tra CPU và CUDA; quản lý manifest/hash/license/version. Bản spec cơ bản cố ý loại torch/demucs vì chưa có thành phần này được nghiệm thu.
5. Cập nhật CI và matrix sau khi có bằng chứng; chưa gọi tách stem là tính năng hoàn tất.

Model dự kiến `htdemucs`: drums, bass, other, vocals. `htdemucs_6s`: thêm guitar, piano. Phải xác minh thứ tự/tên nguồn model; adapter từ chối manifest lệch. Hạn thử 2 phút/lần và timeout 30 phút, CPU mặc định; thông số này chưa dựa trên benchmark model thực.

## Giấy phép, ký số và phát hành

NSIS dùng zlib compression trong script để dùng phần nén zlib. Source chuẩn bị GPL-3.0-only do Pedalboard/JUCE. `collect_licenses.py` sao chép notice đi cùng các package tìm được, gồm CPython và notice Qt/Shiboken bổ sung. Inventory build run `34910577626` có 35 mục, không có mục thiếu notice; đây không thay thế rà soát đầy đủ nguồn tương ứng GPL, license/module Qt, codec và DLL cụ thể trên Windows. Fixture plugin chỉ nằm trên máy kiểm thử, không được đưa vào bộ cài; model AI chưa được phân phối.

Chưa có chứng thư ký số, chưa sign hoặc timestamp executable/installer, chưa đo hành vi SmartScreen/antivirus. Sau build và xử lý mọi lỗi P0/P1, dùng chứng thư của nhà phát hành để ký exe và installer; không ghi private key/password vào repository. Chỉ đánh dấu release sau khi các mục trong `WINDOWS_ACCEPTANCE_VI.md` và đủ 47 yêu cầu đạt bằng chứng.
