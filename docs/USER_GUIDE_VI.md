# Hướng dẫn sử dụng Infinity audio 0.1

Đây là hướng dẫn cho bản alpha đã có mã desktop. Bộ cài Windows chưa được kiểm chứng. Các nút chạy xử lý cơ bản có bộ xử lý thật; phần AI báo trạng thái chưa khả dụng khi thiếu runtime/model.

## Làm quen

Cột trái chứa tài nguyên và kết quả tìm vấn đề. Giữa là điều khiển phát, timeline và mixer. Cột phải chứa preset, tham số, nghe thử và rack hiệu ứng. Nút “Giao diện” đổi tối/sáng. Tooltip giải thích ngưỡng, tỷ lệ, Q, pan và giới hạn của phép xử lý.

1. Chọn **Nhập âm thanh** hoặc kéo nhiều file lên timeline. Mỗi file tạo một track. Định dạng nhập: WAV, FLAC, MP3, AIFF, OGG nếu codec tương ứng có trong libsndfile.
2. Nhấp clip để chọn. Nhấp đôi chọn toàn bộ clip. Kéo trên timeline trong chế độ **Chọn vùng** để đánh dấu thời gian. Hiệu ứng chỉ áp dụng phần giao giữa vùng chọn và clip đang chọn; không tự xử lý các clip khác.
3. **Space** phát vùng chọn của bản phối, hoặc cả dự án nếu không có vùng. Bật **Lặp vùng** để lặp buffer đó. Phát dựa trên buffer đã kết xuất, chưa phải engine FX realtime. Chỉnh mixer rồi phát lại để nghe thiết lập mới.
4. Chọn một preset hoặc hiệu ứng. **Nghe thử vùng chọn** tạo cặp A/B mà chưa sửa dự án. **A · Trước** và **B · Sau** nghe lại từ đầu vùng. Tùy chọn bù âm lượng cân bằng RMS của B; gain bù này không bị ghi vào kết quả áp dụng.
5. Chọn **Áp dụng lên clip** khi đã nghe. Tạo tài sản mới; file gốc và dữ liệu phiên bản cũ giữ nguyên. **Undo/Redo** phục hồi quyết định sửa.
6. **Ctrl+S** lưu gói `.infinity`; **Ctrl+O** mở lại; **Ctrl+E** xuất.

## Timeline và take

- **S** chia clip tại con trỏ. **Ctrl+C / Ctrl+V** sao chép/dán tại con trỏ; clipboard nội bộ chỉ dùng với tài sản của dự án hiện tại. **Ctrl+D** đặt bản sao ngay sau clip. **Delete** xóa clip, để lại khoảng trống trên timeline.
- **Ctrl+T / Giữ vùng** trim clip về vùng chọn. Để cắt một đoạn giữa: chia hai đầu, chọn đoạn giữa, Delete.
- Chuyển **Di chuyển clip**, kéo theo chiều ngang để đổi thời gian và theo chiều dọc để đổi track. Menu Biên tập có nhập vị trí số chính xác.
- **Fade** đặt cùng thời lượng fade in/out. **Crossfade hai clip** trong menu Biên tập đưa clip tiếp theo chồng lên cuối clip chọn và dùng fade tuyến tính bổ sung. Kiểm tra vị trí các clip khác sau khi crossfade.
- **Gộp track thành clip** kết xuất riêng track, gồm FX/mixer/automation rồi đưa các tham số track về mặc định để tránh xử lý hai lần. Master không bị bake vào clip.
- **Thêm vùng chọn vào comp** sao chép phần take đã chọn sang track “Comp vocal”. Tự tắt các take nguồn khi nghe comp; các vùng chồng nhau được cộng, chưa có take lane với lựa chọn loại trừ tự động.
- **M / Marker** đặt intro, verse, chorus hoặc tên tùy chọn tại con trỏ. **Căn đầu clip vào phách** dùng BPM dự án; chưa tạo warp marker hoặc co giãn từng phách.
- **Căn thời điểm vocal** so sánh envelope của clip với clip đầu ở track tham chiếu để dịch toàn clip trong ±2 giây. Không căn từng câu hoặc từng âm tiết. Hãy kiểm tra bằng tai.
- Nút **+ / −**, hoặc **Ctrl+con lăn**, thay đổi zoom. Thanh cuộn di chuyển trên dự án dài.

## Phục hồi và phổ

Lọc nhiễu dùng nền ước lượng theo phổ; bắt đầu cường độ thấp. Tiếng nhạc kéo dài có thể bị nhận nhầm là nền. De-hum dùng 50 Hz mặc định, đổi 60 Hz khi nguồn bị nhiễu điện ở 60 Hz. De-click dùng median để tìm xung; mức mạnh có thể xóa tiếng gảy hoặc transient trống. De-clip chỉ nội suy được một số vùng bão hòa ngắn; đặt ngưỡng phù hợp với mức plateau của nguồn, không chỉ mặc định 0.98.

“Làm rõ giọng” là chuỗi DSP; không được hiểu là tái tạo một giọng bị mất. “Giảm vang” là phép ước lượng đuôi phổ thử nghiệm; chưa có WPE hoặc mạng AI. De-ess nén dải cao; high-pass giảm bật hơi nhưng có thể làm giọng mỏng.

Chọn **Spectrogram** để tạo ảnh phổ của clip đã chọn. Trục dọc tăng từ 0 Hz ở dưới lên Nyquist ở trên, thang tuyến tính. Kéo một hình chữ nhật trên phần ảnh: thời gian/tần số được điền vào “Xóa vùng phổ”. Nghe thử rồi áp dụng để giảm tiếng động nằm trong vùng đó. Độ phân giải phổ hữu hạn; âm thanh chồng cùng vùng không thể phân biệt hoàn hảo. Sau sửa clip, chọn lại chế độ phổ để tạo ảnh mới.

## Cao độ, formant và phân tích

**Đổi tông** nhận số bán âm và giữ thời lượng. Để sửa thủ công một nốt, chọn đoạn của nốt đó và đổi bán âm (có phần thập phân); chưa có piano roll hoặc bộ dò nốt có thể kéo trực tiếp.

**Sửa cao độ · đơn âm** dùng YIN để tìm nốt chromatic gần nhất. Chỉ thử trên vocal một giọng, không vibrato quá mạnh và không nhạc nền; tối đa 60 giây/lần. Không tự nhận thang âm hoặc chỉnh formant đi kèm. **Đổi tốc độ** 1.25 nghĩa là nhanh hơn 25% với cao độ giữ gần nguyên.

**Tạo bè / làm dày** tạo một bè quãng cố định kèm trễ; không tự phối theo hợp âm. **Formant** dịch envelope phổ để đổi màu giọng; còn thử nghiệm và có thể tạo âm giả.

**Phân tích BPM/tông/hợp âm** trả về ước lượng. Trong hộp kết quả có thể sửa BPM, tông và hợp âm trước khi lưu. Chưa có bộ nhận diện được đánh giá trên danh mục bài hát thực; hợp âm đảo, tông tương đối và half/double tempo có thể sai.

## Mixer và rack

Tắt = mute. Riêng = solo; nếu có track solo, chỉ các track solo không bị mute được nghe. Gain dùng dB. Pan -1 trái, 0 giữa, +1 phải; đây là balance stereo, không phải pan law tùy chọn. Width 0 mono, 1 gốc, 2 tăng side. Mono có thể gây triệt tiêu âm lệch pha; xem tương quan pha.

**+ Rack** thêm hiệu ứng vào chuỗi track; dùng mũi tên đổi thứ tự và Xóa FX. Hiệu ứng thay đổi thời lượng phải áp dụng lên clip. Rack được kết xuất khi phát/xuất; chưa có bypass realtime riêng từng FX hoặc editor sửa lại FX tại chỗ, hãy xóa/thêm cấu hình mới.

**Automation** hiện hỗ trợ điểm gain dB và pan theo giây từ đầu dự án. Giá trị điểm được nội suy tuyến tính; ngoài khoảng điểm giữ giá trị gần nhất. Automation thay thế giá trị tĩnh của tham số đó. Lưu một đường tại mỗi lần mở hộp thoại. Chưa hỗ trợ tham số hiệu ứng.

**Sidechain/Ducking**: chọn track nhạc nền rồi chọn track giọng làm nguồn. Detector đọc clip nguồn trước FX/mixer/mute; dùng ngưỡng -35 dBFS và độ giảm tối đa tùy chỉnh. Không tạo vòng lặp sidechain vì detector không đọc đầu ra FX.

**Limiter** kiểm soát sample peak; chưa phải limiter true peak đạt chuẩn broadcast. **Chuẩn hóa LUFS** đo integrated loudness bằng pyloudnorm và đặt gain; nếu ceiling giới hạn gain thì LUFS thực tế thấp hơn mục tiêu. Meter UI hiện đo tối đa 60 giây đầu của buffer nghe/xuất và ghi rõ cửa sổ đó; không được coi là phép đo toàn bài dài. True peak là ước lượng oversampling 4×.

## Stem và plugin

Bạn có thể nhập các stem có sẵn, mute/solo/gain từng track và xuất riêng. **Tạo karaoke từ stem** tắt track tên “vocal”/“vocals” hoặc stem vocal do AI tạo. Đây không phải thuật toán loại vocal trên một file mix.

Bản alpha **chưa gộp mô hình AI/runtime**. Bộ nối nguồn hướng tới `htdemucs` với drums, bass, other, vocals; `htdemucs_6s` thêm guitar, piano. Other là mọi nội dung còn lại, không phải từng nhạc cụ riêng. Chưa có giảm bleed đã kiểm chứng. Chỉ source build tùy chỉnh có Demucs và repo local được cấp quyền mới có thể thử bộ nối.

**VST3** chỉ dành cho hiệu ứng có trên máy và do bạn tin cậy. Quét thư mục, chọn một plugin, nạp để đọc tham số, sửa JSON tham số rồi kết xuất lên clip. Không có editor gốc của plugin/MIDI/instrument. Mỗi lần nạp/render chạy trong tiến trình riêng, có timeout/hủy. Kết quả và state lưu trong clip; mở dự án không tự thực thi plugin. Lỗi plugin trong phiên quản lý bị chặn thử lại cho đến khi mở lại hộp quản lý. Chưa nghiệm thu với plugin Windows thật.

## Xuất, batch và phục hồi

WAV PCM16/24 hoặc float32; FLAC PCM16/24; MP3 CBR 96/128/160/192/256/320 kbps. WAV/FLAC hỗ trợ 22.05,32,44.1,48,88.2,96,192 kHz; MP3 giới hạn 32/44.1/48 kHz. Chọn mono/stereo. Float WAV có thể chứa đỉnh >0 dBFS; PCM/MP3 bị từ chối nếu đầu vào vượt 0 dBFS. Chưa thêm dither khi giảm bit depth. MP3 có thể tạo overshoot khi giải mã; hãy chừa headroom và kiểm tra file đã xuất.

Xuất từng track tạo tên file riêng gồm số thứ tự và ID, có tính FX/mixer/master hiện tại. Batch áp dụng preset hoặc hiệu ứng đã chọn, nối chuỗi đầy đủ; xuất WAV24 và ghi báo cáo JSON từng file. Batch hiện không áp dụng thanh wet/dry tổng. Hủy giữ các file đã hoàn tất, không công bố file đang ghi dở; các lỗi file riêng được ghi để tiếp tục file tiếp theo.

Gói `.infinity` chứa cả tài sản và tối đa 100 snapshot lịch sử. Khi lưu đè, bản trước nằm ở `.infinity.bak`. Mỗi thao tác commit tự lưu; timer 30 giây bổ sung khi không có tác vụ. Phiên chưa đóng đúng cách được đề nghị khôi phục ở lần mở sau. Dữ liệu phục hồi nằm trong AppLocalData của Infinity audio, không tự xóa khi gỡ cài đặt. Bản alpha chưa có màn hình dọn cache; có thể tăng dung lượng do giữ phiên và tài sản cũ.

Không đóng cưỡng bức trong lúc ổ đĩa đang lỗi. Nếu gặp lỗi lưu, giữ cửa sổ và lưu sang nơi còn dung lượng. Các lỗi nghiêm trọng chưa được chứng minh là không tồn tại trên Windows; báo cáo đi kèm phân biệt rõ kiểm thử đã chạy và chưa chạy.
