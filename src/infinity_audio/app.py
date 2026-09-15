from __future__ import annotations
import argparse
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import uuid
import numpy as np
from PySide6.QtCore import Qt,QTimer,QStandardPaths,QSettings
from PySide6.QtGui import QAction,QKeySequence,QFont,QColor
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QFormLayout,
    QFrame,QLabel,QPushButton,QSplitter,QScrollArea,QComboBox,QDoubleSpinBox,QSpinBox,
    QSlider,QListWidget,QTabWidget,QCheckBox,QProgressBar,QFileDialog,QMessageBox,QInputDialog,
    QDialog,QDialogButtonBox,QPlainTextEdit,QLayout)

from . import __version__,dsp,render,plugins,ai
from .model import Session,track,clip,ident,atomic_json,recovery_candidates
from .audio_io import read_audio,export_audio
from .errors import AudioError,Cancelled,check_cancel
from .jobs import JobRunner
from .playback import Player
from .timeline import Timeline,spectrogram_rgb
from .theme import stylesheet
from .dialogs import ExportDialog,AutomationDialog,MusicDialog,PluginDialog


class MainWindow(QMainWindow):
    def __init__(self,data_dir=None,recover=True):
        super().__init__()
        self.setWindowTitle("Infinity audio")
        self.resize(1510,950)
        self.setMinimumSize(1180,760)
        self.base=Path(data_dir or QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation))
        self.base.mkdir(parents=True,exist_ok=True)
        self.sessions=self.base/"sessions";self.sessions.mkdir(exist_ok=True)
        self.session=Session(self.sessions/ident())
        self.settings=QSettings("InfinityAudio","Infinity audio")
        self.light=self.settings.value("light",False,type=bool)
        self.selected_id=None
        self.clipboard=None
        self.preview=None
        self.play_origin=0.
        self._close_pending=False
        self._saved_revision=0
        self.player=Player()
        self.jobs=JobRunner(self)
        self.jobs.failed.connect(self.show_error)
        self.jobs.busyChanged.connect(self.on_busy)
        self.jobs.progress.connect(self.on_progress)
        self.jobs.completed.connect(self.after_job)
        self.presets=copy.deepcopy(dsp.PRESETS)
        self.load_presets()
        self.build_ui()
        self.build_menus()
        self.set_theme(self.light)
        self.refresh()
        self.timer=QTimer(self);self.timer.timeout.connect(self.tick);self.timer.start(50)
        self.autosave_timer=QTimer(self);self.autosave_timer.timeout.connect(self.autosave);self.autosave_timer.start(30000)
        if recover:
            QTimer.singleShot(150,self.offer_recovery)

    def label(self,text,name=None):
        w=QLabel(text)
        if name:w.setObjectName(name)
        return w

    def button(self,text,fn,name=None,tip=None):
        b=QPushButton(text)
        if name:b.setObjectName(name)
        if tip:b.setToolTip(tip)
        b.clicked.connect(lambda checked=False:self.guard(fn))
        return b

    def guard(self,fn):
        try:return fn()
        except Exception as e:self.show_error(str(e))

    def show_error(self,message):
        self.statusBar().showMessage(message,12000)
        QMessageBox.warning(self,"Infinity audio",message)

    def build_ui(self):
        root=QWidget();layout=QVBoxLayout(root);layout.setContentsMargins(18,12,18,8);layout.setSpacing(12)
        header=QHBoxLayout();header.setSpacing(12)
        header.addWidget(self.label("∞","Infinity"));header.addWidget(self.label("Infinity audio","Brand"))
        header.addWidget(self.label(f"STUDIO · {__version__}","Pill"));header.addStretch()
        self.project_title=self.label("Dự án chưa đặt tên","Muted");header.addWidget(self.project_title)
        header.addWidget(self.button("◐  Giao diện",lambda:self.set_theme(not self.light),tip="Chuyển giao diện sáng/tối"))
        self.export_btn=self.button("Xuất âm thanh  ↗",self.export_dialog,"Primary");header.addWidget(self.export_btn)
        layout.addLayout(header)
        self.splitter=QSplitter(Qt.Orientation.Horizontal)
        # Files, presets, diagnostics.
        left=QFrame();left.setObjectName("Panel");lv=QVBoxLayout(left);lv.setContentsMargins(12,15,12,12);lv.setSpacing(11)
        lv.addWidget(self.label("KHÔNG GIAN LÀM VIỆC","Eyebrow"))
        lv.addWidget(self.button("+  Nhập âm thanh",self.import_dialog,"Primary", "Ctrl+I · Kéo thả nhiều file vào timeline"))
        file_buttons=QHBoxLayout();file_buttons.addWidget(self.button("Mở",self.open_dialog));file_buttons.addWidget(self.button("Lưu",self.save_dialog));lv.addLayout(file_buttons)
        self.left_tabs=QTabWidget();lv.addWidget(self.left_tabs,1)
        resources=QWidget();rv=QVBoxLayout(resources);rv.setContentsMargins(0,4,0,0)
        self.file_list=QListWidget();self.file_list.itemClicked.connect(self.resource_clicked);rv.addWidget(self.file_list)
        self.asset_label=self.label("0 track · Nguồn được giữ nguyên","Muted");self.asset_label.setWordWrap(True);rv.addWidget(self.asset_label)
        self.left_tabs.addTab(resources,"Tài nguyên")
        diagnostics=QWidget();dv=QVBoxLayout(diagnostics);dv.setContentsMargins(0,4,0,0)
        dv.addWidget(self.button("Tìm vấn đề trong clip",self.detect_issues))
        self.issue_list=QListWidget();self.issue_list.itemClicked.connect(self.issue_clicked);dv.addWidget(self.issue_list)
        msg=self.label("Kết quả là gợi ý. Chọn mục để định vị, rồi Nghe thử trước khi áp dụng.","Muted");msg.setWordWrap(True);dv.addWidget(msg)
        self.left_tabs.addTab(diagnostics,"Kiểm tra")
        lv.addWidget(self.label("THAO TÁC NHANH","Eyebrow"))
        lv.addWidget(self.button("Làm sạch vocal",lambda:self.select_preset("Vocal tự nhiên")))
        lv.addWidget(self.button("Phục hồi bản thu cũ",lambda:self.select_preset("Bản thu cũ")))
        lv.addWidget(self.button("Tạo karaoke từ stem",self.karaoke))
        lv.addWidget(self.button("Tách stem AI…",self.separate_dialog))
        self.splitter.addWidget(left)
        # Center timeline and mixer.
        center=QWidget();cv=QVBoxLayout(center);cv.setContentsMargins(0,0,0,0);cv.setSpacing(10)
        transport=QFrame();transport.setObjectName("Panel");tl=QHBoxLayout(transport);tl.setContentsMargins(12,9,12,9)
        self.play_btn=self.button("▶",self.play,"Play","Space · Phát vùng chọn hoặc bản phối");tl.addWidget(self.play_btn)
        tl.addWidget(self.button("■",self.stop,tip="Dừng phát"))
        self.loop=QCheckBox("Lặp vùng");tl.addWidget(self.loop)
        self.clock=self.label("00:00.000");self.clock.setFont(QFont("Consolas",16));tl.addWidget(self.clock);tl.addStretch()
        self.bpm_label=self.label("120 BPM","Pill");tl.addWidget(self.bpm_label)
        self.rate_label=self.label("48 kHz · 32f","Muted");tl.addWidget(self.rate_label)
        cv.addWidget(transport)
        title=QHBoxLayout();title.addWidget(self.label("Biên tập & phối âm","Title"));title.addStretch()
        self.view_combo=QComboBox();self.view_combo.addItems(["Waveform","Spectrogram"]);self.view_combo.currentIndexChanged.connect(self.toggle_spectral);title.addWidget(self.view_combo)
        self.mode_combo=QComboBox();self.mode_combo.addItems(["Chọn vùng","Di chuyển clip"]);self.mode_combo.currentIndexChanged.connect(lambda i:setattr(self.timeline,"mode","move" if i else "select"));title.addWidget(self.mode_combo)
        title.addWidget(self.button("−",lambda:self.timeline.set_zoom(self.timeline.zoom/1.3)));title.addWidget(self.button("+",lambda:self.timeline.set_zoom(self.timeline.zoom*1.3)))
        cv.addLayout(title)
        self.timeline=Timeline();self.timeline.set_session(self.session)
        self.timeline.selected.connect(self.select_clip);self.timeline.regionChanged.connect(self.region_changed)
        self.timeline.seek.connect(lambda t:self.update_clock(t));self.timeline.clipMoved.connect(lambda i,t,d:self.guard(lambda:self.move_clip(i,t,d)))
        self.timeline.filesDropped.connect(lambda p:self.guard(lambda:self.import_paths(p)))
        self.timeline.spectralSelected.connect(self.spectral_region)
        self.timeline_scroll=QScrollArea();self.timeline_scroll.setWidget(self.timeline);self.timeline_scroll.setWidgetResizable(True)
        cv.addWidget(self.timeline_scroll,3)
        edit=QHBoxLayout();edit.addWidget(self.button("Chia",self.split_clip,tip="S · Chia tại con trỏ"));edit.addWidget(self.button("Giữ vùng",self.trim_clip,tip="Ctrl+T · Giữ vùng đã chọn"))
        edit.addWidget(self.button("Fade",self.fade_dialog));edit.addWidget(self.button("Marker",self.marker_dialog));edit.addWidget(self.button("↶",self.undo));edit.addWidget(self.button("↷",self.redo))
        edit.addStretch();self.region_label=self.label("Kéo để chọn vùng · Nhấp đôi chọn clip","Muted");edit.addWidget(self.region_label);cv.addLayout(edit)
        mixer_header=QHBoxLayout();mixer_header.addWidget(self.label("MIXER","Eyebrow"));mixer_header.addStretch()
        self.mono=QCheckBox("Nghe mono");self.mono.toggled.connect(lambda b:self.guard(lambda:self.change_master(mono=b)));mixer_header.addWidget(self.mono)
        mixer_header.addWidget(self.label("Master","Muted"));self.master=QDoubleSpinBox();self.master.setRange(-90,24);self.master.setSuffix(" dB");self.master.setSingleStep(.5)
        self.master.editingFinished.connect(lambda:self.guard(lambda:self.change_master(master_db=self.master.value())));mixer_header.addWidget(self.master);cv.addLayout(mixer_header)
        self.mixer_content=QWidget();self.mixer_content.setObjectName("Mixer");self.mixer_layout=QHBoxLayout(self.mixer_content);self.mixer_layout.setContentsMargins(0,0,0,0)
        self.mixer_scroll=QScrollArea();self.mixer_scroll.setWidget(self.mixer_content);self.mixer_scroll.setWidgetResizable(True);self.mixer_scroll.setMinimumHeight(180);self.mixer_scroll.setMaximumHeight(215);cv.addWidget(self.mixer_scroll,1)
        self.meter_label=self.label("Đo bản phối sau kết xuất: RMS —   Peak —   TP ước lượng —   Pha —","Muted");self.meter_label.setWordWrap(True);cv.addWidget(self.meter_label)
        self.splitter.addWidget(center)
        # Effect panel.
        right=QFrame();right.setObjectName("Panel");ev=QVBoxLayout(right);ev.setContentsMargins(14,15,14,12);ev.setSpacing(10)
        ev.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        ev.addWidget(self.label("XỬ LÝ ÂM THANH","Eyebrow"));self.selected_label=self.label("Chọn một clip","Title");self.selected_label.setWordWrap(True);ev.addWidget(self.selected_label)
        self.preset_combo=QComboBox();self.preset_combo.addItem("Chọn preset…");self.preset_combo.addItems(list(self.presets));self.preset_combo.currentTextChanged.connect(self.preset_changed);ev.addWidget(self.preset_combo)
        self.effect_combo=QComboBox()
        for key,v in dsp.EFFECTS.items():self.effect_combo.addItem(v["title"],key)
        self.effect_combo.currentIndexChanged.connect(self.rebuild_params);ev.addWidget(self.effect_combo)
        self.effect_hint=self.label("","Muted");self.effect_hint.setWordWrap(True);ev.addWidget(self.effect_hint)
        self.param_widget=QWidget();self.param_form=QFormLayout(self.param_widget);self.param_form.setContentsMargins(0,2,0,2);self.param_form.setSpacing(10)
        self.param_form.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        self.param_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        ev.addWidget(self.param_widget)
        self.strength_label=self.label("Cường độ tổng: 100%","Muted");ev.addWidget(self.strength_label)
        self.strength=QSlider(Qt.Orientation.Horizontal);self.strength.setRange(0,100);self.strength.setValue(100);self.strength.valueChanged.connect(lambda v:self.strength_label.setText(f"Cường độ tổng: {v}%"));ev.addWidget(self.strength)
        self.match=QCheckBox("Cân bằng âm lượng khi A/B");self.match.setChecked(True);self.match.setToolTip("Bù RMS khi nghe B; không thay gain của kết quả được áp dụng.");ev.addWidget(self.match)
        ev.addWidget(self.button("◉  Nghe thử vùng chọn",lambda:self.process_clip(False),"Primary"))
        ab=QHBoxLayout();ab.addWidget(self.button("A · Trước",lambda:self.play_ab(False)));ab.addWidget(self.button("B · Sau",lambda:self.play_ab(True)));ev.addLayout(ab)
        ev.addWidget(self.button("Áp dụng lên clip",lambda:self.process_clip(True)))
        fxrow=QHBoxLayout();fxrow.addWidget(self.button("+ Rack",self.add_to_rack));fxrow.addWidget(self.button("Lưu preset",self.save_preset));ev.addLayout(fxrow)
        ev.addWidget(self.label("CHUỖI HIỆU ỨNG TRACK","Eyebrow"));self.rack=QListWidget();self.rack.setMaximumHeight(120);ev.addWidget(self.rack)
        rackrow=QHBoxLayout();rackrow.addWidget(self.button("↑",lambda:self.move_effect(-1)));rackrow.addWidget(self.button("↓",lambda:self.move_effect(1)));rackrow.addWidget(self.button("Xóa FX",self.remove_effect));ev.addLayout(rackrow)
        ev.addStretch();ev.addWidget(self.button("Automation / VST3…",self.advanced_menu))
        self.quality_note=self.label("Bản alpha · AI chưa khả dụng. Xem Trợ giúp để biết giới hạn xử lý.","Muted");self.quality_note.setWordWrap(True);ev.addWidget(self.quality_note)
        # Scroll the inspector rather than squeezing parameter rows into the
        # available window height. All fields remain reachable on small screens.
        self.effect_scroll=QScrollArea();self.effect_scroll.setWidget(right);self.effect_scroll.setWidgetResizable(True)
        self.effect_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.effect_scroll.setMinimumWidth(310)
        self.splitter.addWidget(self.effect_scroll)
        self.splitter.setSizes([220,940,320]);self.splitter.setCollapsible(0,True);self.splitter.setCollapsible(1,False);self.splitter.setCollapsible(2,True)
        left.setMinimumWidth(185);right.setMinimumWidth(285)
        layout.addWidget(self.splitter,1)
        task=QHBoxLayout();self.task_label=self.label("Sẵn sàng · File nguồn được giữ nguyên","Muted");task.addWidget(self.task_label,1)
        self.progress=QProgressBar();self.progress.setRange(0,1000);self.progress.setTextVisible(False);self.progress.setFixedWidth(200);task.addWidget(self.progress)
        self.cancel_btn=self.button("Hủy tác vụ",self.cancel_job);self.cancel_btn.setEnabled(False);task.addWidget(self.cancel_btn)
        layout.addLayout(task);self.setCentralWidget(root)
        self.rebuild_params()

    def build_menus(self):
        definitions={
         "Tệp":[("Dự án mới","Ctrl+N",self.new_project),("Nhập âm thanh…","Ctrl+I",self.import_dialog),("Mở dự án…","Ctrl+O",self.open_dialog),("Lưu dự án","Ctrl+S",self.save_dialog),("Lưu thành phiên bản…","Ctrl+Shift+S",lambda:self.save_dialog(True)),("Xuất bản phối…","Ctrl+E",self.export_dialog),("Xuất từng track/stem…",None,self.export_stems),("Xử lý hàng loạt…",None,self.batch_dialog)],
         "Biên tập":[("Hoàn tác","Ctrl+Z",self.undo),("Làm lại","Ctrl+Shift+Z",self.redo),("Chia clip","S",self.split_clip),("Sao chép clip","Ctrl+C",self.copy_clip),("Dán tại con trỏ","Ctrl+V",self.paste_clip),("Nhân đôi","Ctrl+D",self.duplicate_clip),("Xóa clip","Delete",self.delete_clip),("Giữ vùng chọn","Ctrl+T",self.trim_clip),("Di chuyển chính xác…",None,self.move_dialog),("Fade in / out…",None,self.fade_dialog),("Crossfade hai clip…",None,self.crossfade),("Gộp track thành clip",None,self.join_track),("Thêm vùng chọn vào comp",None,self.comp_selection),("Lịch sử…",None,self.history_dialog)],
         "Công cụ":[("Phát / dừng","Space",self.play),("Thêm marker","M",self.marker_dialog),("Căn đầu clip vào phách",None,self.quantize),("Căn thời điểm vocal…",None,self.align_vocal),("Phân tích BPM / tông / hợp âm…",None,self.analyze),("Tìm vấn đề / gợi ý sửa",None,self.detect_issues),("Phát hiện khoảng lặng…",None,self.find_silence),("Automation gain / pan…",None,self.automation_dialog),("Sidechain / Ducking…",None,self.sidechain_dialog),("VST3…",None,self.plugin_dialog),("Tách stem AI local…",None,self.separate_dialog)],
         "Trợ giúp":[("Hướng dẫn nhanh",None,self.quick_help),("Trạng thái 47 yêu cầu",None,self.status_dialog),("Về Infinity audio",None,self.about)]}
        self.edit_actions=[]
        for title,items in definitions.items():
            menu=self.menuBar().addMenu(title)
            for label,key,fn in items:
                a=QAction(label,self)
                if key:a.setShortcut(QKeySequence(key))
                a.triggered.connect(lambda checked=False,func=fn:self.guard(func))
                menu.addAction(a)
                if title!="Trợ giúp":self.edit_actions.append(a)

    def set_theme(self,light):
        self.light=light;self.settings.setValue("light",light)
        QApplication.instance().setStyleSheet(stylesheet(light))
        self.size_parameter_fields()
        self.timeline.light=light;self.timeline.update()

    def selected(self):
        return self.session.find_clip(self.selected_id)

    def select_clip(self,clip_id):
        self.selected_id=clip_id;self.timeline.selected_id=clip_id
        t,c=self.selected();self.selected_label.setText(c["name"])
        self.rack.clear()
        for fx in t["effects"]:self.rack.addItem(dsp.EFFECTS.get(fx["kind"],{}).get("title",fx["kind"]))
        self.timeline.update()

    def resource_clicked(self,item):
        index=self.file_list.row(item)
        tracks=self.session.state["tracks"]
        if 0<=index<len(tracks) and tracks[index]["clips"]:
            self.select_clip(tracks[index]["clips"][0]["id"])

    def region_changed(self,a,b):
        self.region_label.setText(f"{a:.3f} – {b:.3f} s  ·  {max(0,b-a):.3f} s")

    def refresh(self):
        self.preview=None
        self.timeline.set_session(self.session)
        tracks=self.session.state["tracks"]
        ids=[c["id"] for t in tracks for c in t["clips"]]
        if self.selected_id not in ids:self.selected_id=ids[0] if ids else None
        self.file_list.clear()
        for i,t in enumerate(tracks):self.file_list.addItem(f"{i+1:02}  {t['name']}\n      {len(t['clips'])} clip · {t['gain_db']:+.1f} dB")
        self.asset_label.setText(f"{len(tracks)} track · {len(self.session.all_assets())} tài sản\nNguồn được giữ nguyên")
        if self.selected_id:self.select_clip(self.selected_id)
        else:self.selected_label.setText("Chọn một clip");self.rack.clear()
        self.project_title.setText(self.session.state["name"])
        self.bpm_label.setText(f'{self.session.state["bpm"]:g} BPM')
        self.rate_label.setText(f'{self.session.state["sr"]/1000:g} kHz · 32f')
        self.master.blockSignals(True);self.master.setValue(self.session.state["master_db"]);self.master.blockSignals(False)
        self.mono.blockSignals(True);self.mono.setChecked(self.session.state["mono"]);self.mono.blockSignals(False)
        self.rebuild_mixer()

    def rebuild_mixer(self):
        while self.mixer_layout.count():
            item=self.mixer_layout.takeAt(0)
            if item.widget():item.widget().deleteLater()
        for t in self.session.state["tracks"]:
            tid=t["id"]
            frame=QFrame();frame.setObjectName("Panel");frame.setMinimumWidth(143);frame.setMaximumWidth(180)
            col=QVBoxLayout(frame);col.setContentsMargins(10,8,10,8);col.setSpacing(5)
            color=QColor(t["color"]).darker(155).name() if self.light else t["color"]
            title=self.label(t["name"]);title.setStyleSheet(f'color:{color};font-weight:600;');title.setToolTip(t["name"]);col.addWidget(title)
            toggles=QHBoxLayout()
            for text,key in [("Tắt","mute"),("Riêng","solo")]:
                b=QPushButton(text);b.setCheckable(True);b.setChecked(t[key]);b.setMaximumHeight(28)
                b.clicked.connect(lambda value,track_id=tid,k=key:self.guard(lambda:self.track_update(track_id,**{k:value})))
                toggles.addWidget(b)
            col.addLayout(toggles)
            gain=QDoubleSpinBox();gain.setRange(-90,24);gain.setValue(t["gain_db"]);gain.setSuffix(" dB");gain.setSingleStep(.5);gain.setToolTip("Âm lượng track")
            gain.editingFinished.connect(lambda track_id=tid,w=gain:self.guard(lambda:self.track_update(track_id,gain_db=w.value())));col.addWidget(gain)
            form=QFormLayout();form.setSpacing(3)
            pan=QDoubleSpinBox();pan.setRange(-1,1);pan.setSingleStep(.1);pan.setValue(t["pan"]);pan.setToolTip("-1 trái, 0 giữa, +1 phải")
            pan.editingFinished.connect(lambda track_id=tid,w=pan:self.guard(lambda:self.track_update(track_id,pan=w.value())));form.addRow("Pan",pan)
            width=QDoubleSpinBox();width.setRange(0,2);width.setSingleStep(.1);width.setValue(t["width"]);width.setToolTip("0 = mono; 1 = độ rộng gốc; 2 = tăng side")
            width.editingFinished.connect(lambda track_id=tid,w=width:self.guard(lambda:self.track_update(track_id,width=w.value())));form.addRow("Rộng",width)
            col.addLayout(form);self.mixer_layout.addWidget(frame)
        self.mixer_layout.addStretch()

    def track_update(self,tid,**values):
        self.stop();self.session.set_track(tid,**values);self.refresh()

    def change_master(self,**values):
        if all(self.session.state[k]==v for k,v in values.items()):return
        self.stop();self.session.commit("Chỉnh master",lambda s:s.update(values));self.refresh()

    def run_task(self,title,fn,done):
        if self.jobs.busy:raise AudioError("Đang có tác vụ chạy. Hãy chờ hoặc hủy tác vụ hiện tại.")
        self.stop();self.task_label.setText(title);self.progress.setValue(0)
        self.jobs.start(fn,done)

    def on_busy(self,busy):
        self.cancel_btn.setEnabled(busy);self.export_btn.setEnabled(not busy)
        self.splitter.setEnabled(not busy)
        for a in getattr(self,"edit_actions",[]):a.setEnabled(not busy)
        if not busy:
            self.progress.setValue(0);self.task_label.setText("Sẵn sàng · Thay đổi được tự lưu")

    def on_progress(self,value,label):
        self.progress.setValue(int(max(0,min(1,value))*1000));self.task_label.setText(label)

    def cancel_job(self):
        self.jobs.cancel();self.task_label.setText("Đang hủy… Một phép toán native cần kết thúc trước khi nhận hủy.")

    def after_job(self):
        if self._close_pending:self._close_pending=False;self.close()

    def autosave(self):
        if not self.jobs.busy:
            try:self.session.autosave()
            except OSError as e:self.statusBar().showMessage("Tự lưu lỗi: "+str(e))

    def offer_recovery(self):
        candidates=[p for p in recovery_candidates(self.sessions) if p!=self.session.root]
        if candidates and QMessageBox.question(self,"Khôi phục phiên làm việc","Có phiên làm việc chưa đóng đúng cách. Khôi phục phiên gần nhất?")==QMessageBox.StandardButton.Yes:
            self.session.autosave(clean=True)
            self.session=Session.recover(candidates[0]);self._saved_revision=-1;self.refresh()

    def confirm_discard(self):
        if not self.session.state["tracks"] or self.session.revision==self._saved_revision:return True
        result=QMessageBox.question(self,"Thay đổi chưa lưu thành file","Dự án có thay đổi chưa lưu thành file .infinity. Lưu trước khi tiếp tục?",QMessageBox.StandardButton.Save|QMessageBox.StandardButton.Discard|QMessageBox.StandardButton.Cancel)
        if result==QMessageBox.StandardButton.Save:self.save_dialog();return False
        return result==QMessageBox.StandardButton.Discard

    def new_project(self):
        if not self.confirm_discard():return
        self.stop();self.session.autosave(clean=True);self.session=Session(self.sessions/ident());self._saved_revision=0;self.selected_id=None;self.refresh()

    def import_dialog(self):
        paths,_=QFileDialog.getOpenFileNames(self,"Nhập âm thanh",filter="Âm thanh (*.wav *.flac *.mp3 *.aiff *.aif *.ogg)")
        if paths:self.import_paths(paths)

    def import_paths(self,paths):
        if not paths:return
        if len(paths)==1 and Path(paths[0]).suffix.lower()==".infinity":self.open_path(paths[0]);return
        sr=self.session.state["sr"]
        def job(cancel,progress):
            result=[]
            # Stage assets only; a failure/cancel cannot partially edit the timeline.
            for i,path in enumerate(paths):
                check_cancel(cancel)
                x,_=read_audio(path,sr,cancel,lambda v,m:progress((i+v)/len(paths),m))
                key=self.session.add_asset(x)
                result.append((key,len(x),Path(path).stem))
            return result
        def done(result):
            def change(s):
                for key,n,name in result:
                    t=track(name,len(s["tracks"]));t["clips"].append(clip(key,n,sr,name));s["tracks"].append(t)
            self.session.commit("Nhập "+str(len(result))+" file",change);self.refresh()
        self.run_task("Đang nhập âm thanh…",job,done)

    def open_dialog(self):
        path,_=QFileDialog.getOpenFileName(self,"Mở dự án",filter="Dự án Infinity (*.infinity *.infinity.bak)")
        if path:self.open_path(path)

    def open_path(self,path):
        if not self.confirm_discard():return
        dest=self.sessions/ident()
        def done(session):
            self.session.autosave(clean=True);self.session=session;self._saved_revision=self.session.revision;self.selected_id=None;self.refresh()
        self.run_task("Đang mở dự án…",lambda c,p:Session.load(path,dest,c,p),done)

    def save_dialog(self,save_as=False):
        path=self.session.saved_path
        if not path or save_as:
            path,_=QFileDialog.getSaveFileName(self,"Lưu dự án",path or "Du-an.infinity","Dự án Infinity (*.infinity)")
        if not path:return
        def done(result):
            self._saved_revision=self.session.revision;self.statusBar().showMessage("Đã lưu: "+result,10000)
        self.run_task("Đang lưu dự án…",lambda c,p:self.session.save(path,c,p),done)

    def export_dialog(self):
        if not self.session.state["tracks"]:raise AudioError("Nhập âm thanh trước khi xuất.")
        dlg=ExportDialog(self)
        if dlg.exec()!=QDialog.DialogCode.Accepted:return
        extension=dlg.format.currentText().lower()
        path,_=QFileDialog.getSaveFileName(self,"Xuất bản phối","Infinity-mix."+extension,extension.upper()+" (*."+extension+")")
        if not path:return
        options=dlg.options();state=copy.deepcopy(self.session.state)
        def job(c,p):
            x=render.render(self.session,state,cancel=c,progress=lambda v,m:p(v*.7,m))
            file=export_audio(path,x,state["sr"],**options,cancel=c,progress=lambda v,m:p(.7+v*.3,m),overwrite=True)
            return file,dsp.meters(x[:state["sr"]*60],state["sr"])
        def done(result):
            self.display_meters(result[1]);self.statusBar().showMessage("Đã xuất: "+result[0],15000)
        self.run_task("Đang kết xuất bản phối…",job,done)

    def export_stems(self):
        folder=QFileDialog.getExistingDirectory(self,"Thư mục xuất từng track/stem")
        if not folder:return
        state=copy.deepcopy(self.session.state)
        def job(c,p):
            results=[]
            for i,t in enumerate(state["tracks"]):
                check_cancel(c)
                x=render.render(self.session,state,only_track=t["id"],cancel=c)
                path=Path(folder)/f"{i+1:02}-stem-{t['id'][:6]}.wav"
                export_audio(path,x,state["sr"],cancel=c)
                results.append(str(path));p((i+1)/len(state["tracks"]),"Đang xuất "+t["name"])
            return results
        self.run_task("Xuất stem…",job,lambda r:self.statusBar().showMessage(f"Đã xuất {len(r)} track/stem",12000))

    def display_meters(self,m):
        loudness=f"{m['integrated_lufs']:.1f}" if m.get('integrated_lufs') is not None else "—"
        self.meter_label.setText(f"Đo tối đa 60 s: {loudness} LUFS   RMS {m['rms_dbfs']:.1f}   Peak {m['sample_peak_dbfs']:.1f} dBFS   TP≈ {m['true_peak_estimate_dbtp']:.1f} dBTP   Pha {m['phase_correlation']:+.2f}   Clip {m['clipped_samples']}")

    def play(self):
        if self.player.transport.playing:self.stop();return
        a,b=self.timeline.region
        if b<=a:a,b=0,None
        state=copy.deepcopy(self.session.state)
        def job(c,p):
            x=render.render(self.session,state,a,b,c,p)
            return x,dsp.meters(x[:state["sr"]*60],state["sr"])
        def done(result):
            self.display_meters(result[1]);self.play_origin=a;self.player.play(result[0],state["sr"],self.loop.isChecked())
        self.run_task("Đang chuẩn bị nghe…",job,done)

    def stop(self):
        self.player.stop()

    def tick(self):
        if self.player.transport.playing:
            at=self.play_origin+self.player.transport.position/self.player.sr
            self.timeline.cursor=at;self.timeline.update();self.update_clock(at)
        self.play_btn.setText("Ⅱ" if self.player.transport.playing else "▶")

    def update_clock(self,seconds):
        self.clock.setText(f"{int(seconds)//60:02}:{seconds%60:06.3f}")

    def undo(self):
        self.stop();self.session.undo();self.refresh()

    def redo(self):
        self.stop();self.session.redo();self.refresh()

    def split_clip(self):
        self.session.split(self.selected_id,self.timeline.cursor);self.refresh()

    def duplicate_clip(self):
        _,c=self.selected();self.session.duplicate(c["id"],c["start"]+c["length"]);self.refresh()

    def copy_clip(self):
        _,c=self.selected();self.clipboard=copy.deepcopy(c);self.statusBar().showMessage("Đã sao chép clip",3000)

    def paste_clip(self):
        if not self.clipboard:raise AudioError("Chưa sao chép clip.")
        if not (self.session.assets/self.clipboard["asset"]).exists():raise AudioError("Clipboard thuộc dự án khác. Hãy nhập lại nguồn.")
        t,_=self.selected();new=copy.deepcopy(self.clipboard);new.update(id=ident(),start=self.timeline.cursor)
        self.session.commit("Dán clip",lambda s:next(v for v in s["tracks"] if v["id"]==t["id"])["clips"].append(new));self.refresh()

    def delete_clip(self):
        self.session.delete(self.selected_id);self.refresh()

    def trim_clip(self):
        self.session.trim(self.selected_id,*self.timeline.region);self.refresh()

    def move_clip(self,i,t,d):
        self.session.move(i,t,d);self.refresh()

    def move_dialog(self):
        _,c=self.selected();value,ok=QInputDialog.getDouble(self,"Di chuyển clip","Vị trí bắt đầu (giây)",c["start"],0,86400,3)
        if ok:self.session.move(c["id"],value);self.refresh()

    def fade_dialog(self):
        _,c=self.selected();value,ok=QInputDialog.getDouble(self,"Fade in/out","Thời gian mỗi fade (giây)",.15,0,c["length"],3)
        if ok:self.session.fade(c["id"],value,value);self.refresh()

    def crossfade(self):
        t,c=self.selected();candidates=sorted(t["clips"],key=lambda x:x["start"]);i=next(i for i,v in enumerate(candidates) if v["id"]==c["id"])
        if i+1>=len(candidates):raise AudioError("Cần clip tiếp theo trong cùng track.")
        other=candidates[i+1];value,ok=QInputDialog.getDouble(self,"Crossfade","Độ dài chồng lấp (giây)",.1,.001,min(c["length"],other["length"]),3)
        if not ok:return
        def change(s):
            _,a=self.session.find_clip(c["id"],s);_,b=self.session.find_clip(other["id"],s)
            a["fade_out"]=value;b["fade_in"]=value;b["start"]=a["start"]+a["length"]-value
        self.session.commit("Crossfade tuyến tính",change);self.refresh()

    def join_track(self):
        t,_=self.selected();state=copy.deepcopy(self.session.state)
        def done(x):
            key=self.session.add_asset(x)
            def change(s):
                target=next(v for v in s["tracks"] if v["id"]==t["id"])
                target.update(clips=[clip(key,len(x),s["sr"],t["name"]+" · gộp")],effects=[],automation={},gain_db=0.,pan=0.,width=1.,sidechain=None)
            self.session.commit("Gộp track thành clip",change);self.refresh()
        # Master must not be baked twice.
        state["master_db"]=0;state["mono"]=False
        self.run_task("Gộp track…",lambda c,p:render.render(self.session,state,only_track=t["id"],cancel=c,progress=p),done)

    def comp_selection(self):
        _,c=self.selected();a,b=self.timeline.region
        lo,hi=max(a,c["start"]),min(b,c["start"]+c["length"])
        if hi<=lo:raise AudioError("Chọn phần tốt nhất của take trước khi thêm vào comp.")
        new=copy.deepcopy(c);new.update(id=ident(),start=lo,offset=c["offset"]+lo-c["start"],length=hi-lo,fade_in=.005,fade_out=.005)
        def change(s):
            dest=next((t for t in s["tracks"] if t["name"]=="Comp vocal"),None)
            if dest is None:dest=track("Comp vocal",len(s["tracks"]));s["tracks"].append(dest)
            dest["clips"].append(new)
        self.session.commit("Thêm vùng take vào comp",change);self.refresh()

    def marker_dialog(self):
        name,ok=QInputDialog.getText(self,"Đặt marker","Tên phần: intro, verse, chorus hoặc tùy chọn",text="Chorus")
        if ok and name.strip():self.session.commit("Thêm marker",lambda s:s["markers"].append({"time":self.timeline.cursor,"name":name.strip()}));self.refresh()

    def quantize(self):
        _,c=self.selected();beat=60/self.session.state["bpm"];self.session.move(c["id"],round(c["start"]/beat)*beat);self.refresh()

    def align_vocal(self):
        t,c=self.selected();choices=[v for v in self.session.state["tracks"] if v["id"]!=t["id"] and v["clips"]]
        if not choices:raise AudioError("Cần ít nhất hai track có clip để căn vocal.")
        labels=[f"{i+1}. {v['name']}" for i,v in enumerate(choices)];chosen,ok=QInputDialog.getItem(self,"Căn vocal","Track tham chiếu (clip đầu tiên)",labels,0,False)
        if not ok:return
        ref=choices[labels.index(chosen)]["clips"][0]
        reference=self.session.clip_audio(ref["id"]);target=self.session.clip_audio(c["id"])
        def done(offset):
            self.session.move(c["id"],max(0,ref["start"]+offset));self.refresh();self.statusBar().showMessage(f"Dịch thời điểm {offset:+.3f}s; chưa co giãn từng câu.",12000)
        self.run_task("Ước lượng độ trễ vocal…",lambda token,p:dsp.alignment_offset(reference,target,self.session.state["sr"]),done)

    def history_dialog(self):
        labels=[f"{i:02} {'●' if i==self.session.cursor else ' '} {h['label']}" for i,h in enumerate(self.session.history)]
        choice,ok=QInputDialog.getItem(self,"Lịch sử chỉnh sửa","Chọn phiên bản để khôi phục",labels,self.session.cursor,False)
        if ok:self.session.goto(labels.index(choice));self.refresh()

    def rebuild_params(self):
        while self.param_form.rowCount():self.param_form.removeRow(0)
        key=self.effect_combo.currentData();info=dsp.EFFECTS[key];self.effect_hint.setText(info["hint"]);self.param_fields={}
        for name,(title,default,lo,hi,step) in info["params"].items():
            widget=QDoubleSpinBox();widget.setRange(lo,hi);widget.setSingleStep(step);widget.setDecimals(3 if step<.1 else 2 if step<1 else 1);widget.setValue(default);widget.setToolTip(title+". "+info["hint"])
            self.param_form.addRow(title,widget);self.param_fields[name]=widget
        self.size_parameter_fields()

    def size_parameter_fields(self):
        # The stylesheet minimum alone can be smaller than a Windows spin
        # box's font/button metrics. Refresh after creation and theme changes.
        for widget in getattr(self,"param_fields",{}).values():
            widget.ensurePolished()
            widget.setMinimumHeight(max(widget.minimumHeight(),widget.minimumSizeHint().height()))

    def effect(self):
        return {"kind":self.effect_combo.currentData(),"params":{k:w.value() for k,w in self.param_fields.items()}}

    def active_effects(self):
        name=self.preset_combo.currentText()
        return copy.deepcopy(self.presets[name]) if name in self.presets else [self.effect()]

    def load_presets(self):
        path=self.base/"presets.json"
        if path.exists():
            try:
                values=json.loads(path.read_text(encoding="utf-8"))
                for k,chain in values.items():
                    for fx in chain:dsp.validate_effect(fx)
                    self.presets[k]=chain
            except Exception:pass

    def select_preset(self,name):
        self.preset_combo.setCurrentText(name)

    def preset_changed(self,name):
        active=name in self.presets
        self.effect_combo.setEnabled(not active);self.param_widget.setEnabled(not active)
        if active:self.effect_hint.setText("Chuỗi: "+" → ".join(dsp.EFFECTS[x["kind"]]["title"] for x in self.presets[name]))
        else:self.rebuild_params()

    def save_preset(self):
        effects=self.active_effects();name,ok=QInputDialog.getText(self,"Lưu preset","Tên preset cá nhân")
        if not ok or not name.strip():return
        name=name.strip();self.presets[name]=effects;atomic_json(self.base/"presets.json",self.presets)
        if self.preset_combo.findText(name)<0:self.preset_combo.addItem(name)
        self.preset_combo.setCurrentText(name)

    def selection_audio(self):
        _,c=self.selected();x=self.session.clip_audio(c["id"]);sr=self.session.state["sr"]
        a,b=self.timeline.region
        if b>a:
            lo,hi=max(a,c["start"]),min(b,c["start"]+c["length"])
            if hi<=lo:raise AudioError("Vùng chọn không giao với clip đang chọn.")
            first,last=round((lo-c["start"])*sr),round((hi-c["start"])*sr)
        else:first,last=0,len(x)
        return c,x,first,last

    def process_clip(self,commit=False):
        c,original,first,last=self.selection_audio();effects=self.active_effects();strength=self.strength.value()/100;sr=self.session.state["sr"]
        revision=self.session.revision
        def job(token,progress):
            before=original[first:last].copy();after=dsp.chain(before,sr,effects,token,progress)
            if len(after)==len(before):after=before*(1-strength)+after*strength
            elif strength!=1:raise AudioError("Thay đổi thời lượng cần cường độ tổng 100%.")
            return before,after
        def done(result):
            if self.session.revision!=revision:raise AudioError("Dự án đã thay đổi; bỏ kết quả cũ.")
            before,after=result
            if commit:
                # Feather only the internal selection seams, not whole-file boundaries.
                blended=after.copy()
                if len(after)==len(before):
                    n=min(int(sr*.005),len(after)//2)
                    if n and first>0:blended[:n]=before[:n]*np.linspace(1,0,n)[:,None]+after[:n]*np.linspace(0,1,n)[:,None]
                    if n and last<len(original):blended[-n:]=before[-n:]*np.linspace(0,1,n)[:,None]+after[-n:]*np.linspace(1,0,n)[:,None]
                full=np.concatenate([original[:first],blended,original[last:]],axis=0)
                self.session.replace_audio(c["id"],full,"Áp dụng "+" / ".join(dsp.EFFECTS[e["kind"]]["title"] for e in effects));self.timeline.images.pop(c["id"],None);self.refresh()
            else:
                self.preview={"before":before,"after":after,"sr":sr,"origin":c["start"]+first/sr,"revision":revision}
                self.display_meters(dsp.meters(after[:sr*60],sr));self.play_ab(True)
        self.run_task("Đang xử lý vùng chọn…",job,done)

    def play_ab(self,after):
        if not self.preview or self.preview["revision"]!=self.session.revision:raise AudioError("Chọn Nghe thử vùng chọn để tạo cặp A/B mới.")
        preview=self.preview;x=preview["after"] if after else preview["before"]
        if after and self.match.isChecked():x=dsp.match_rms(preview["before"],x)
        self.play_origin=preview["origin"];self.player.play(x,preview["sr"],self.loop.isChecked())

    def add_to_rack(self):
        t,_=self.selected();effects=self.active_effects()
        if any(e["kind"] in {"tempo","trim_silence"} for e in effects):raise AudioError("Hiệu ứng đổi thời lượng cần Áp dụng lên clip.")
        self.session.set_track(t["id"],effects=t["effects"]+effects);self.refresh()

    def remove_effect(self):
        t,_=self.selected();i=self.rack.currentRow()
        if i<0:return
        effects=copy.deepcopy(t["effects"]);effects.pop(i);self.session.set_track(t["id"],effects=effects);self.refresh()

    def move_effect(self,delta):
        t,_=self.selected();i=self.rack.currentRow();effects=copy.deepcopy(t["effects"])
        if 0<=i<len(effects) and 0<=i+delta<len(effects):
            effects[i],effects[i+delta]=effects[i+delta],effects[i];self.session.set_track(t["id"],effects=effects);self.refresh();self.rack.setCurrentRow(i+delta)

    def toggle_spectral(self,index):
        self.timeline.spectral=bool(index);self.timeline.update()
        if index and self.selected_id and not self.jobs.busy:
            c,x,_,_=self.selection_audio();sr=self.session.state["sr"]
            if len(x)>sr*300:self.show_error("Spectrogram tối đa 5 phút mỗi clip trong bản này.");return
            self.run_task("Đang tạo spectrogram…",lambda token,p:spectrogram_rgb(x,sr),lambda rgb:self.timeline.set_spectral_image(c["id"],rgb))

    def spectral_region(self,a,b,lo,hi):
        self.preset_combo.setCurrentIndex(0);self.effect_combo.setCurrentIndex(self.effect_combo.findData("spectral"))
        self.param_fields["start"].setValue(0);self.param_fields["end"].setValue(b-a)
        self.param_fields["low_hz"].setValue(lo);self.param_fields["high_hz"].setValue(max(lo+10,hi))

    def detect_issues(self):
        _,x,_,_=self.selection_audio();sr=self.session.state["sr"];clip_id=self.selected_id
        def done(results):
            self.findings=results;self.findings_clip=clip_id;self.issue_list.clear()
            for r in results:self.issue_list.addItem(f"{r['start']:.2f}–{r['end']:.2f}s · {r['kind']}\n{r['description']}")
            if not results:self.issue_list.addItem("Chưa thấy vấn đề theo các ngưỡng hiện tại.")
            self.left_tabs.setCurrentIndex(1)
        self.run_task("Đang tìm dấu hiệu lỗi…",lambda c,p:dsp.issues(x,sr),done)

    def issue_clicked(self,item):
        i=self.issue_list.row(item)
        if i>=len(getattr(self,"findings",[])):return
        self.select_clip(self.findings_clip);_,clip=self.selected();r=self.findings[i]
        self.timeline.region=(clip["start"]+r["start"],clip["start"]+r["end"]);self.timeline.cursor=self.timeline.region[0];self.region_changed(*self.timeline.region);self.timeline.update()
        self.preset_combo.setCurrentIndex(0);self.effect_combo.setCurrentIndex(self.effect_combo.findData(r["effect"]))

    def find_silence(self):
        self.selected();self.preset_combo.setCurrentIndex(0);self.effect_combo.setCurrentIndex(self.effect_combo.findData("trim_silence"))
        threshold,ok=QInputDialog.getDouble(self,"Phát hiện khoảng lặng","Ngưỡng RMS (dBFS)",-45,-80,-10,1)
        if not ok:return
        c,x,_,_=self.selection_audio();sr=self.session.state["sr"]
        def done(regions):
            def change(s):
                s["markers"].extend({"time":c["start"]+a,"name":f"Lặng {b-a:.2f}s"} for a,b in regions)
            self.session.commit("Đánh dấu khoảng lặng",change);self.refresh();self.param_fields["threshold_db"].setValue(threshold)
        self.run_task("Đang tìm khoảng lặng…",lambda token,p:dsp.silence_regions(x,sr,threshold),done)

    def analyze(self):
        _,x,_,_=self.selection_audio();sr=self.session.state["sr"]
        def done(result):
            dlg=MusicDialog(result,self)
            if dlg.exec()==QDialog.DialogCode.Accepted:self.session.commit("Sửa BPM/tông/hợp âm",lambda s:s.update(dlg.values()));self.refresh()
        self.run_task("Đang phân tích beat/chroma…",lambda c,p:dsp.analyze_music(x,sr,c),done)

    def automation_dialog(self):
        t,_=self.selected();dlg=AutomationDialog(t["automation"],self)
        if dlg.exec()!=QDialog.DialogCode.Accepted:return
        kind,points=dlg.result_points();values=copy.deepcopy(t["automation"]);values[kind]=points;self.session.set_track(t["id"],automation=values);self.refresh()

    def sidechain_dialog(self):
        t,_=self.selected();others=[v for v in self.session.state["tracks"] if v["id"]!=t["id"]]
        labels=["Tắt sidechain"]+[f"{i+1}. {v['name']}" for i,v in enumerate(others)]
        choice,ok=QInputDialog.getItem(self,"Ducking nhạc nền","Nguồn giọng nói/vocal để điều khiển",labels,0,False)
        if not ok:return
        config=None
        if choice!=labels[0]:
            depth,ok=QInputDialog.getDouble(self,"Độ giảm nhạc nền","Giảm tối đa (dB)",12,0,36,1)
            if not ok:return
            config={"track_id":others[labels.index(choice)-1]["id"],"threshold_db":-35,"depth_db":depth}
        self.session.set_track(t["id"],sidechain=config);self.refresh()

    def advanced_menu(self):
        choice,ok=QInputDialog.getItem(self,"Tùy chỉnh nâng cao","Chọn công cụ",["Automation gain / pan","Sidechain / Ducking","Plugin VST3"],0,False)
        if ok:{"Automation gain / pan":self.automation_dialog,"Sidechain / Ducking":self.sidechain_dialog,"Plugin VST3":self.plugin_dialog}[choice]()

    def plugin_dialog(self):
        _,c=self.selected();dlg=PluginDialog(self,c.get("plugin_state"))
        if dlg.exec()!=QDialog.DialogCode.Accepted:return
        info=dlg.info;x=self.session.clip_audio(c["id"]);sr=self.session.state["sr"]
        work=self.session.root/("plugin-"+ident());work.mkdir();input_path=work/"input.npy";output_path=work/"output.npy";np.save(input_path,x,allow_pickle=False)
        def job(token,p):
            result=plugins.run_plugin(info["path"],info["parameters"],info.get("state"),input_path,output_path,sr,timeout=180,cancel=token)
            return np.load(output_path,allow_pickle=False),result
        def done(result):
            audio,state=result;key=self.session.add_asset(audio)
            def change(s):
                _,target=self.session.find_clip(c["id"],s);target.update(asset=key,offset=0.,length=len(audio)/sr,plugin_state=state)
            self.session.commit("Kết xuất VST3",change);self.refresh()
        self.run_task("VST3 đang kết xuất clip…",job,done)

    def separate_dialog(self):
        self.selected()
        if not ai.available():raise AudioError("Tách stem chưa khả dụng trong bản cơ bản. Đã có bộ nối Demucs local, nhưng chưa gộp runtime/model hoặc kiểm chứng chất lượng. Danh sách dự kiến: vocals, drums, bass, other; model 6 stem thêm guitar và piano. Xem tài liệu build và ma trận 47 yêu cầu.")
        repo=QFileDialog.getExistingDirectory(self,"Chọn repository mô hình local mà bạn có quyền sử dụng")
        if not repo:return
        name,ok=QInputDialog.getItem(self,"Model stem","Chọn model",list(ai.STEMS),0,False)
        if not ok:return
        c,x,first,last=self.selection_audio();work=self.session.root/("ai-"+ident());work.mkdir();source=work/"input.npy";np.save(source,x[first:last],allow_pickle=False);sr=self.session.state["sr"]
        def done(paths):
            staged=[]
            for name,path in paths.items():
                data=np.load(path,allow_pickle=False);staged.append((name,self.session.add_asset(data),len(data)))
            def change(s):
                # Mute the source track to prevent double-summing the mixture and stems.
                original,_=self.session.find_clip(c["id"],s);original["mute"]=True
                for name,key,n in staged:
                    t=track(name,len(s["tracks"]));t["stem"]=name;t["clips"].append(clip(key,n,sr,name,c["start"]+first/sr));s["tracks"].append(t)
            self.session.commit("Nhập kết quả AI stem",change);self.refresh()
        self.run_task("Tách stem AI local…",lambda token,p:ai.separate(source,work,sr,repo,name,cancel=token,progress=p),done)

    def karaoke(self):
        vocals=[t for t in self.session.state["tracks"] if t.get("stem")=="vocals" or t["name"].strip().lower() in {"vocals","vocal"}]
        if not vocals:raise AudioError("Cần các stem đã tách. Nhập vocal/nhạc nền riêng hoặc dùng bộ nối AI khi có model. Công cụ này tắt track vocal để tạo karaoke.")
        self.session.commit("Preset karaoke: tắt vocal",lambda s:[t.update(mute=True) for t in s["tracks"] if t["id"] in {v["id"] for v in vocals}]);self.refresh()

    def batch_dialog(self):
        paths,_=QFileDialog.getOpenFileNames(self,"Chọn file xử lý hàng loạt",filter="Âm thanh (*.wav *.flac *.mp3 *.ogg *.aiff)")
        if not paths:return
        folder=QFileDialog.getExistingDirectory(self,"Chọn thư mục xuất WAV 24 bit")
        if not folder:return
        effects=self.active_effects();sr=self.session.state["sr"]
        def job(c,p):
            report=[]
            for i,path in enumerate(paths):
                check_cancel(c)
                try:
                    x,_=read_audio(path,sr,c);y=dsp.chain(x,sr,effects,c)
                    destination=Path(folder)/(Path(path).stem+f"-infinity-{i+1:03}.wav")
                    export_audio(destination,y,sr,cancel=c)
                    report.append({"input":path,"output":str(destination),"status":"ok"})
                except Cancelled:raise
                except Exception as e:report.append({"input":path,"status":"error","error":str(e)})
                p((i+1)/len(paths),"Batch: "+Path(path).name)
                atomic_json(Path(folder)/"Infinity-batch-report.json",report)
            return report
        def done(r):
            ok=sum(v["status"]=="ok" for v in r);QMessageBox.information(self,"Xử lý hàng loạt",f"Thành công {ok}/{len(r)} file. Xem Infinity-batch-report.json trong thư mục xuất.")
        self.run_task("Đang xử lý hàng loạt…",job,done)

    def quick_help(self):
        QMessageBox.information(self,"Hướng dẫn nhanh","1. Nhập hoặc kéo thả file. Mỗi file thành một track.\n2. Nhấp clip; kéo chọn vùng. Nhấp đôi chọn cả clip.\n3. Space phát bản phối; S chia; Ctrl+D nhân đôi; Delete xóa.\n4. Chọn preset/hiệu ứng, Nghe thử, so sánh A/B, rồi Áp dụng.\n5. Mixer: Tắt/Riêng, gain, pan, độ rộng. Menu Công cụ có automation và ducking.\n6. Ctrl+S lưu .infinity; Ctrl+E xuất. Giữ .infinity.bak để phục hồi.\n\nCác phép DSP kết xuất trước khi phát. Bản alpha chưa có DSP realtime, tự sửa từng nốt hoặc AI đóng gói. Tooltips và báo cáo nghiệm thu nêu giới hạn.")

    def status_dialog(self):
        path=Path(__file__).resolve().parent/"feature_status.json"
        if not path.exists():
            path=Path(__file__).resolve().parents[2]/"docs"/"feature_status.json"
        dlg=QDialog(self);dlg.setWindowTitle("47 yêu cầu · trạng thái có bằng chứng");dlg.resize(790,630);v=QVBoxLayout(dlg)
        text=QPlainTextEdit();text.setReadOnly(True)
        if path.exists():
            values=json.loads(path.read_text(encoding="utf-8"));text.setPlainText("CHƯA NGHIỆM THU SẢN PHẨM ĐẦY ĐỦ\n\n"+"\n\n".join(f"{r['id']:02}. {r['name']} — {r['status']}\n{r['result']}" for r in values))
        else:text.setPlainText("Xem docs/FEATURE_MATRIX_VI.md trong mã nguồn. Chưa nghiệm thu 47 tính năng hoặc bộ cài Windows.")
        v.addWidget(text);box=QDialogButtonBox(QDialogButtonBox.StandardButton.Close);box.rejected.connect(dlg.reject);v.addWidget(box);dlg.exec()

    def about(self):
        QMessageBox.information(self,"Infinity audio",f"Infinity audio {__version__}\nỨng dụng desktop tiếng Việt · GPL-3.0-only\n\nQt / NumPy / SciPy / Pedalboard / librosa / SoundFile / pyloudnorm.\nBản phát triển; chưa có chứng nhận nghiệm thu Windows.\nMeters: LUFS, RMS, sample peak và TP ước lượng 4×.\nGiấy phép và các giới hạn: xem tài liệu đi kèm.")

    def closeEvent(self,event):
        if self.jobs.busy:
            self._close_pending=True;self.cancel_job();event.ignore();return
        if not self.confirm_discard():event.ignore();return
        try:self.session.autosave(clean=True)
        except OSError as e:self.show_error("Không ghi được trạng thái đóng: "+str(e));event.ignore();return
        self.stop();event.accept()


def main():
    parser=argparse.ArgumentParser(description="Infinity audio desktop")
    parser.add_argument("project",nargs="?")
    parser.add_argument("--smoke-test",action="store_true",help="Qt launch/exit check; does not test audio hardware")
    parser.add_argument("--self-test",metavar="REPORT_JSON",help="Run isolated import/edit/DSP/save/export diagnostics and write a JSON report")
    args=parser.parse_args()
    QApplication.setOrganizationName("InfinityAudio");QApplication.setApplicationName("Infinity audio")
    app=QApplication(sys.argv[:1]);app.setStyle("Fusion")
    if args.self_test:
        from .selftest import run
        return run(app,args.self_test)
    if args.smoke_test:
        with tempfile.TemporaryDirectory(prefix="infinity-smoke-") as d:
            w=MainWindow(d,recover=False);w.show()
            QTimer.singleShot(350,w.close)
            return app.exec()
    w=MainWindow();w.show()
    if args.project:QTimer.singleShot(0,lambda:w.guard(lambda:w.open_path(args.project)))
    return app.exec()


if __name__=="__main__":
    from multiprocessing import freeze_support
    freeze_support();raise SystemExit(main())
