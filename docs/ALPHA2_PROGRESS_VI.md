# Infinity audio alpha.2 — mốc cập nhật 15/09/2026

Mã nền đã kiểm tra: commit `32fadea9f4b0e603dc78e7a221ec3529d4f9379b`, Windows Actions run `34934351614`. Run đó đã build/cài/chạy/gỡ thành công, 101 pytest và 30 kiểm tra ứng dụng, nhưng ảnh chụp cho thấy các tham số hiệu ứng bị co nhỏ ở cửa sổ tối thiểu.

## Sửa trong mốc này

- Bảng hiệu ứng cuộn theo chiều dọc; nhãn và ô nhập giữ kích thước tối thiểu, có thể tiếp cận khi cửa sổ 1180 × 760. Kiểm tra EQ, expander, spectral và compressor ở cả giao diện sáng/tối.
- Hiển thị đúng phiên bản mã ở thanh tiêu đề giao diện.
- Không đưa cache Numba `.nbc`/`.nbi` từ máy build vào bộ cài; source và frozen build dùng thư mục cache riêng. Build sẽ dừng nếu còn cache trong bundle.
- Thêm kiểm tra sửa tone 452 Hz về gần 440 Hz trong executable và chạy toàn bộ self-test hai lần liên tiếp sau cài đặt, trước khi gỡ.

## Bằng chứng Linux

102/102 pytest đạt (36,34 giây); 31/31 kiểm tra ứng dụng đạt với CHOWTapeModel thật. Các báo cáo ở `evidence/linux-alpha2-pytest.xml` và `evidence/linux-alpha2-vst3-selftest.json`.

Trong lượt trước, nhận diện cao độ đã segfault khi dùng cache cũ; ca tối giản tái hiện được với cache đó. Cache riêng qua hai lần chạy cao độ và toàn bộ tests. Quan sát này chưa chứng minh nguyên nhân nội bộ của Numba. Không sửa thuật toán hoặc nới ngưỡng kiểm thử để bỏ qua lỗi; Windows phải qua kiểm tra trong binary và lần khởi chạy tiếp theo.

## Cổng tiếp theo

Run `34957225215` dừng ở kiểm thử bố cục: Windows báo ô nhập 31 px trong khi minimumSizeHint cần 34 px. Bản sửa tiếp theo đặt chiều cao tối thiểu theo font/button metrics sau khi tạo tham số và đổi theme; giữ nguyên điều kiện kiểm thử. 101 ca còn lại của run đó đạt.

Chỉ dùng bộ cài của Actions run khớp commit này sau khi cả build và install đều thành công; đối chiếu SHA-256, xem `installed-selftest.json`, `installed-second-launch.json`, ảnh cửa sổ và `windows-install-result.json`. Cập nhật báo cáo, ma trận 47 yêu cầu và link tải sau khi có bằng chứng. Bộ cài của run trước không chứa sửa bố cục này.

Chưa nghiệm thu đủ 47 tính năng, model AI/stem, Windows 10/11 sạch hoặc thiết bị âm thanh vật lý. Giữ nguyên Infinity-Studio; mọi thay đổi ở repo `musiclife2292-blip/infinity`.
