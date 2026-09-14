import json
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QLabel,QComboBox,QSpinBox,
    QDoubleSpinBox,QDialogButtonBox,QTableWidget,QTableWidgetItem,QPushButton,QFileDialog,
    QListWidget,QPlainTextEdit,QMessageBox)
from .audio_io import SAMPLE_RATES
from .errors import AudioError
from .jobs import JobRunner
from . import plugins


class ExportDialog(QDialog):
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setWindowTitle("Xuất âm thanh")
        self.setMinimumWidth(390)
        form=QFormLayout(self)
        self.format=QComboBox();self.format.addItems(["WAV","FLAC","MP3"])
        self.rate=QComboBox();self.rate.addItems([str(s) for s in SAMPLE_RATES]);self.rate.setCurrentText("48000")
        self.bits=QComboBox();self.bits.addItems(["16","24","32"]);self.bits.setCurrentText("24")
        self.bitrate=QComboBox();self.bitrate.addItems(["96","128","160","192","256","320"]);self.bitrate.setCurrentText("192")
        self.channels=QComboBox();self.channels.addItems(["Stereo","Mono"])
        form.addRow("Định dạng",self.format);form.addRow("Sample rate (Hz)",self.rate)
        form.addRow("Bit depth (WAV/FLAC)",self.bits);form.addRow("Bitrate MP3 (kbps)",self.bitrate);form.addRow("Kênh",self.channels)
        info=QLabel("Xuất toàn bộ bản phối. 32 bit WAV là float.\nFLAC hỗ trợ 16/24 bit; MP3 dùng 32/44.1/48 kHz.\nFile vượt 0 dBFS cần hạ gain hoặc limiter.")
        info.setWordWrap(True);form.addRow(info)
        self.format.currentTextChanged.connect(self.update_fields)
        box=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        box.accepted.connect(self.accept);box.rejected.connect(self.reject);form.addRow(box)
        self.update_fields()

    def update_fields(self):
        mp3=self.format.currentText()=="MP3"
        self.bits.setEnabled(not mp3);self.bitrate.setEnabled(mp3)
        if self.format.currentText()=="FLAC" and self.bits.currentText()=="32":
            self.bits.setCurrentText("24")
        if mp3 and self.rate.currentText() not in {"32000","44100","48000"}:
            self.rate.setCurrentText("48000")

    def options(self):
        return {"output_sr":int(self.rate.currentText()),"bit_depth":int(self.bits.currentText()),
                "bitrate":int(self.bitrate.currentText()),"channels":1 if self.channels.currentText()=="Mono" else 2}


class AutomationDialog(QDialog):
    def __init__(self,current,parent=None):
        super().__init__(parent)
        self.current=current
        self.setWindowTitle("Automation theo thời gian")
        self.resize(460,430)
        layout=QVBoxLayout(self)
        hint=QLabel("Mức ở điểm đầu/cuối được giữ ngoài đoạn có điểm.\nNội suy tuyến tính; thời gian tính từ đầu dự án.")
        hint.setWordWrap(True);layout.addWidget(hint)
        self.kind=QComboBox();self.kind.addItems(["gain_db","pan"]);layout.addWidget(self.kind)
        self.table=QTableWidget(0,2);self.table.setHorizontalHeaderLabels(["Thời gian (s)","Giá trị (dB / -1…1)"])
        self.table.horizontalHeader().setStretchLastSection(True);layout.addWidget(self.table)
        row=QHBoxLayout();add=QPushButton("Thêm điểm");remove=QPushButton("Xóa điểm")
        add.clicked.connect(lambda:self.add_row());remove.clicked.connect(lambda:self.table.removeRow(self.table.currentRow()))
        row.addWidget(add);row.addWidget(remove);layout.addLayout(row)
        self.kind.currentTextChanged.connect(self.populate)
        box=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel)
        box.accepted.connect(self.accept);box.rejected.connect(self.reject);layout.addWidget(box)
        self.populate()

    def populate(self):
        self.table.setRowCount(0)
        for a,b in self.current.get(self.kind.currentText(),[]):
            self.add_row(a,b)

    def add_row(self,a=0,b=0):
        n=self.table.rowCount();self.table.insertRow(n)
        self.table.setItem(n,0,QTableWidgetItem(str(a)));self.table.setItem(n,1,QTableWidgetItem(str(b)))

    def result_points(self):
        try:
            points=sorted([[float(self.table.item(r,0).text()),float(self.table.item(r,1).text())] for r in range(self.table.rowCount())])
            return self.kind.currentText(),points
        except (ValueError,AttributeError) as e:
            raise AudioError("Mỗi điểm cần hai giá trị số hợp lệ.") from e


class MusicDialog(QDialog):
    def __init__(self,result,parent=None):
        super().__init__(parent)
        self.setWindowTitle("BPM, tông và hợp âm · kiểm tra lại kết quả")
        self.resize(510,500)
        layout=QVBoxLayout(self);form=QFormLayout()
        self.bpm=QDoubleSpinBox();self.bpm.setRange(20,400);self.bpm.setValue(result["bpm"])
        from PySide6.QtWidgets import QLineEdit
        self.key=QLineEdit(result["key"])
        form.addRow("BPM",self.bpm);form.addRow("Tông",self.key);layout.addLayout(form)
        note=QLabel("Nhận diện dựa trên beat/chroma, có thể nhầm half/double tempo, trưởng/thứ và hợp âm đảo. Sửa trực tiếp trước khi lưu.")
        note.setWordWrap(True);layout.addWidget(note)
        self.table=QTableWidget(len(result["chords"]),2);self.table.setHorizontalHeaderLabels(["Thời gian (s)","Hợp âm"])
        self.table.horizontalHeader().setStretchLastSection(True)
        for i,c in enumerate(result["chords"]):
            self.table.setItem(i,0,QTableWidgetItem(f'{c["time"]:.3f}'));self.table.setItem(i,1,QTableWidgetItem(c["name"]))
        layout.addWidget(self.table)
        box=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel)
        box.accepted.connect(self.accept);box.rejected.connect(self.reject);layout.addWidget(box)

    def values(self):
        return {"bpm":self.bpm.value(),"key":self.key.text(),
                "chords":[{"time":float(self.table.item(i,0).text()),"name":self.table.item(i,1).text()} for i in range(self.table.rowCount())]}


class PluginDialog(QDialog):
    def __init__(self,parent=None,previous=None):
        super().__init__(parent)
        self.setWindowTitle("Plugin hiệu ứng VST3 · kết xuất offline")
        self.resize(670,590)
        self.info=None
        self.blacklist=set()
        self.jobs=JobRunner(self)
        self.jobs.failed.connect(self.failure)
        self.jobs.busyChanged.connect(self.on_busy)
        layout=QVBoxLayout(self)
        note=QLabel("Chọn thư mục chứa VST3 bạn tin cậy. Plugin được nạp trong tiến trình riêng; không nạp tự động từ dự án. Chưa hỗ trợ VST2, CLAP, AU, MIDI hay cửa sổ editor của plugin.")
        note.setWordWrap(True);layout.addWidget(note)
        self.scan=QPushButton("Quét thư mục VST3…");self.scan.clicked.connect(self.scan_folder);layout.addWidget(self.scan)
        self.list=QListWidget();layout.addWidget(self.list)
        self.inspect=QPushButton("Nạp plugin đã chọn / đọc tham số");self.inspect.clicked.connect(self.inspect_plugin);layout.addWidget(self.inspect)
        self.params=QPlainTextEdit();self.params.setPlaceholderText("Tham số plugin sẽ hiện ở đây (JSON). Chỉnh giá trị rồi áp dụng.");layout.addWidget(self.params)
        self.status=QLabel("Chưa nạp plugin.");self.status.setWordWrap(True);layout.addWidget(self.status)
        self.box=QDialogButtonBox(QDialogButtonBox.StandardButton.Apply|QDialogButtonBox.StandardButton.Close)
        self.box.button(QDialogButtonBox.StandardButton.Apply).setText("Áp dụng lên clip")
        self.box.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self.apply)
        self.box.rejected.connect(self.reject);layout.addWidget(self.box)
        if previous:
            self.list.addItem(previous["path"])
            self.list.setCurrentRow(0)
            self.params.setPlainText(json.dumps(previous.get("parameters",{}),ensure_ascii=False,indent=2))
            self.info=previous
            self.status.setText("Thiết lập đã lưu. Nạp lại có chủ ý hoặc áp dụng để chạy VST3.")
        self.on_busy(False)

    def on_busy(self,busy):
        self.scan.setEnabled(not busy);self.inspect.setEnabled(not busy)
        self.box.button(QDialogButtonBox.StandardButton.Apply).setEnabled(not busy and self.info is not None)

    def scan_folder(self):
        folder=QFileDialog.getExistingDirectory(self,"Chọn thư mục VST3")
        if folder:
            self.info=None
            self.jobs.start(lambda c,p:plugins.discover(folder),self.scanned)

    def scanned(self,paths):
        self.list.clear();self.list.addItems(paths)
        self.status.setText(f"Tìm thấy {len(paths)} mục VST3. Chọn từng plugin để kiểm tra nạp.")

    def inspect_plugin(self):
        item=self.list.currentItem()
        if not item:
            return
        path=item.text()
        if path in self.blacklist:
            self.status.setText("Plugin này lỗi trong lần thử trước. Mở lại trình quản lý để thử lại.")
            return
        self.status.setText("Đang nạp plugin trong tiến trình riêng (timeout 30 giây)…")
        self.jobs.start(lambda c,p:plugins.run_plugin(path,timeout=30,cancel=c),self.loaded)

    def loaded(self,info):
        self.info=info
        self.params.setPlainText(json.dumps(info["parameters"],ensure_ascii=False,indent=2))
        self.status.setText("Đã đọc tham số. Kết quả chỉ được ghi vào clip khi xử lý hoàn tất.")

    def failure(self,message):
        self.info=None
        if self.list.currentItem():
            self.blacklist.add(self.list.currentItem().text())
        self.status.setText(message)

    def apply(self):
        try:
            values=json.loads(self.params.toPlainText())
            if not isinstance(values,dict):
                raise ValueError("Cần một object JSON.")
            self.info["parameters"]=values
            self.accept()
        except ValueError as e:
            QMessageBox.warning(self,"Tham số chưa hợp lệ",str(e))

    def reject(self):
        if self.jobs.busy:
            self.jobs.cancel();self.status.setText("Đang dừng plugin. Đóng lại sau khi tác vụ kết thúc.")
            return
        super().reject()

    def closeEvent(self,event):
        if self.jobs.busy:
            self.jobs.cancel();event.ignore()
        else:
            event.accept()
