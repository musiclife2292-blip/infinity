"""Native painter timeline: clips, waveforms, spectral rectangular selection, drag/zoom."""
import math
import numpy as np
from PySide6.QtCore import Qt, QRectF, QPointF, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QFont, QImage
from PySide6.QtWidgets import QWidget


class Timeline(QWidget):
    selected=Signal(str)
    regionChanged=Signal(float,float)
    clipMoved=Signal(str,float,str)
    spectralSelected=Signal(float,float,float,float)
    filesDropped=Signal(list)
    seek=Signal(float)
    HEADER=44
    ROW=102
    LABEL=160

    def __init__(self,parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setMouseTracking(True)
        self.session=None
        self.zoom=65.
        self.selected_id=None
        self.region=(0.,0.)
        self.cursor=0.
        self.mode="select"
        self.spectral=False
        self.light=False
        self.peaks={}
        self.images={}
        self._drag=None
        self.setMinimumHeight(390)

    def set_session(self,session):
        self.session=session
        self.refresh()

    def refresh(self):
        if not self.session:
            return
        from .render import duration
        self.setMinimumSize(max(680,int(max(8,duration(self.session.state)+1)*self.zoom)+self.LABEL),max(390,self.HEADER+len(self.session.state["tracks"])*self.ROW+30))
        self.update()

    def set_zoom(self,value):
        self.zoom=max(8,min(800,value))
        self.refresh()

    def x_to_time(self,x):
        return max(0,(x-self.LABEL)/self.zoom)

    def clip_rect(self,row,clip):
        return QRectF(self.LABEL+clip["start"]*self.zoom,self.HEADER+row*self.ROW+11,max(3,clip["length"]*self.zoom),self.ROW-22)

    def _find(self,pos):
        if self.session:
            for i,t in enumerate(self.session.state["tracks"]):
                for c in reversed(t["clips"]):
                    if self.clip_rect(i,c).contains(pos):
                        return i,t,c
        return None

    def _peaks(self,c):
        key=(c["asset"],c["offset"],c["length"])
        if key not in self.peaks:
            sr=self.session.state["sr"]
            a=self.session.audio(c["asset"])
            a=a[round(c["offset"]*sr):round((c["offset"]+c["length"])*sr)]
            block=max(1,math.ceil(len(a)/1200))
            # Reduce bounded blocks without copying the entire source asset.
            bins=[]
            for start in range(0,len(a),block):
                b=a[start:start+block]
                bins.append((float(b.min()),float(b.max())))
            self.peaks[key]=np.array(bins)
        return self.peaks[key]

    def set_spectral_image(self,clip_id,rgb):
        h,w,_=rgb.shape
        self.images[clip_id]=QImage(rgb.data,w,h,rgb.strides[0],QImage.Format.Format_RGB888).copy()
        self.update()

    def paintEvent(self,event):
        p=QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        bg="#f5f6fb" if self.light else "#10141d"
        panel="#e9ecf5" if self.light else "#171d28"
        grid="#d9deeb" if self.light else "#252e3d"
        text="#344058" if self.light else "#c5cedf"
        p.fillRect(self.rect(),QColor(bg))
        p.fillRect(0,0,self.width(),self.HEADER,QColor(panel))
        p.fillRect(0,0,self.LABEL,self.height(),QColor(panel))
        p.setFont(QFont("Segoe UI",9))
        p.setPen(QColor(text))
        p.drawText(QRectF(16,0,self.LABEL-20,self.HEADER),Qt.AlignmentFlag.AlignVCenter,"TRACK / STEM")
        tick=1 if self.zoom>=45 else 5
        for sec in range(0,math.ceil((self.width()-self.LABEL)/self.zoom)+1,tick):
            x=self.LABEL+sec*self.zoom
            p.setPen(QColor(grid))
            p.drawLine(QPointF(x,self.HEADER),QPointF(x,self.height()))
            p.setPen(QColor(text))
            p.drawText(QRectF(x+6,9,60,24),f"{sec//60:02}:{sec%60:02}")
        if not self.session or not self.session.state["tracks"]:
            p.setPen(QColor(text))
            p.setFont(QFont("Segoe UI",15))
            p.drawText(QRectF(self.LABEL+10,105,self.width()-self.LABEL-20,50),Qt.AlignmentFlag.AlignCenter,"Bắt đầu với âm thanh của bạn")
            p.setFont(QFont("Segoe UI",10))
            p.drawText(QRectF(self.LABEL+10,158,self.width()-self.LABEL-20,55),Qt.AlignmentFlag.AlignCenter,"Kéo file vào đây hoặc chọn Nhập âm thanh\nWAV · FLAC · MP3 · AIFF · OGG")
            return
        state=self.session.state
        for i,t in enumerate(state["tracks"]):
            top=self.HEADER+i*self.ROW
            p.setPen(QColor(grid));p.drawLine(0,top+self.ROW,self.width(),top+self.ROW)
            color=QColor(t["color"]).darker(155) if self.light else QColor(t["color"])
            p.fillRect(12,top+19,3,24,color)
            p.setPen(QColor(text));p.setFont(QFont("Segoe UI",10,QFont.Weight.DemiBold))
            label=p.fontMetrics().elidedText(t["name"],Qt.TextElideMode.ElideRight,self.LABEL-38)
            p.drawText(24,top+32,label)
            p.setFont(QFont("Segoe UI",8))
            status="TẮT" if t["mute"] else "SOLO" if t["solo"] else f'{t["gain_db"]:+.1f} dB  ·  {len(t["clips"])} clip'
            p.drawText(24,top+53,status)
            p.drawText(24,top+73,f'{len(t["effects"])} FX  ·  Pan {t["pan"]:+.2f}')
            for c in t["clips"]:
                r=self.clip_rect(i,c)
                if not r.intersects(QRectF(event.rect())):
                    continue
                p.save();p.setClipRect(r)
                fill=QColor(color);fill.setAlpha(32 if c["id"]!=self.selected_id else 65)
                p.setPen(QPen(color,2 if c["id"]==self.selected_id else .7))
                p.setBrush(fill);p.drawRoundedRect(r.adjusted(1,1,-1,-1),6,6)
                p.setFont(QFont("Segoe UI",9,QFont.Weight.DemiBold));p.setPen(color)
                label=p.fontMetrics().elidedText(c["name"],Qt.TextElideMode.ElideRight,max(1,int(r.width()-18)))
                p.drawText(QRectF(r.x()+9,r.y()+3,r.width()-16,20),label)
                content=r.adjusted(3,26,-3,-5)
                if self.spectral and c["id"] in self.images:
                    p.drawImage(content,self.images[c["id"]])
                else:
                    peaks=self._peaks(c)
                    if len(peaks):
                        p.setPen(QPen(color,1))
                        stride=max(1,int(len(peaks)/max(1,content.width())))
                        for b in range(0,len(peaks),stride):
                            x=content.x()+b/max(1,len(peaks)-1)*content.width()
                            p.drawLine(QPointF(x,content.center().y()-peaks[b,1]*content.height()*.48),QPointF(x,content.center().y()-peaks[b,0]*content.height()*.48))
                p.setPen(QPen(QColor("#ffffff" if not self.light else "#303f70"),1))
                if c["fade_in"]:
                    p.drawLine(r.bottomLeft(),QPointF(r.x()+min(r.width(),c["fade_in"]*self.zoom),r.y()+24))
                if c["fade_out"]:
                    p.drawLine(QPointF(r.right()-min(r.width(),c["fade_out"]*self.zoom),r.y()+24),r.bottomRight())
                p.restore()
        for m in state.get("markers",[]):
            x=self.LABEL+m["time"]*self.zoom
            p.setPen(QPen(QColor("#edbf78"),1,Qt.PenStyle.DashLine));p.drawLine(QPointF(x,0),QPointF(x,self.height()))
            p.setFont(QFont("Segoe UI",8));p.drawText(QRectF(x+4,0,110,14),m["name"])
        a,b=self.region
        if b>a:
            p.fillRect(QRectF(self.LABEL+a*self.zoom,self.HEADER,(b-a)*self.zoom,self.height()-self.HEADER),QColor(147,128,255,28))
            p.setPen(QColor("#ab98ff"))
            p.drawLine(QPointF(self.LABEL+a*self.zoom,self.HEADER),QPointF(self.LABEL+a*self.zoom,self.height()))
            p.drawLine(QPointF(self.LABEL+b*self.zoom,self.HEADER),QPointF(self.LABEL+b*self.zoom,self.height()))
        x=self.LABEL+self.cursor*self.zoom
        p.setPen(QPen(QColor("#f5f7fd" if not self.light else "#5e49ca"),1.4))
        p.drawLine(QPointF(x,self.HEADER),QPointF(x,self.height()))

    def mousePressEvent(self,event):
        pos=event.position()
        hit=self._find(pos)
        if hit:
            row,t,c=hit
            self.selected_id=c["id"]
            self.selected.emit(c["id"])
        self.cursor=self.x_to_time(pos.x())
        self.seek.emit(self.cursor)
        self._drag=(pos,hit)
        self.region=(self.cursor,self.cursor)
        self.regionChanged.emit(*self.region)
        self.update()

    def mouseMoveEvent(self,event):
        if self._drag and self.mode=="select":
            anchor,_=self._drag
            a,b=sorted((self.x_to_time(anchor.x()),self.x_to_time(event.position().x())))
            self.region=(a,b)
            self.regionChanged.emit(a,b)
            self.update()
        elif not self._drag:
            hit=self._find(event.position())
            self.setToolTip((hit[2]["name"]+"\nKéo để chọn vùng. Nhấp đôi chọn cả clip. Chế độ Di chuyển để kéo clip.") if hit else "Kéo vùng trống để chọn thời gian.")

    def mouseReleaseEvent(self,event):
        if not self._drag:
            return
        anchor,hit=self._drag
        pos=event.position()
        if hit and self.mode=="move" and abs(pos.x()-anchor.x())>3:
            _,t,c=hit
            row=max(0,min(len(self.session.state["tracks"])-1,int((pos.y()-self.HEADER)/self.ROW)))
            self.clipMoved.emit(c["id"],max(0,c["start"]+(pos.x()-anchor.x())/self.zoom),self.session.state["tracks"][row]["id"])
        elif hit and self.spectral and self.mode=="select" and self.region[1]>self.region[0]:
            row,t,c=hit
            r=self.clip_rect(row,c).adjusted(3,26,-3,-5)
            nyquist=self.session.state["sr"]/2
            f1=np.clip((r.bottom()-anchor.y())/r.height(),0,1)*nyquist
            f2=np.clip((r.bottom()-pos.y())/r.height(),0,1)*nyquist
            self.spectralSelected.emit(*self.region,float(min(f1,f2)),float(max(f1,f2)))
        self._drag=None

    def mouseDoubleClickEvent(self,event):
        hit=self._find(event.position())
        if hit:
            c=hit[2]
            self.selected_id=c["id"]
            self.region=(c["start"],c["start"]+c["length"])
            self.selected.emit(c["id"])
            self.regionChanged.emit(*self.region)
            self.update()

    def wheelEvent(self,event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.set_zoom(self.zoom*(1.2 if event.angleDelta().y()>0 else 1/1.2))
            event.accept()
        else:
            super().wheelEvent(event)

    def dragEnterEvent(self,event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self,event):
        self.filesDropped.emit([u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()])
        event.acceptProposedAction()


def spectrogram_rgb(data,sr):
    from scipy import signal
    x=data.mean(axis=1)
    n=min(1024,max(16,len(x)))
    _,_,z=signal.stft(x,fs=sr,nperseg=n,noverlap=n//2)
    v=20*np.log10(np.maximum(np.abs(z),1e-8))
    v=np.clip((v+85)/75,0,1)[::-1,::max(1,z.shape[1]//1600)]
    stops=np.array([[10,15,28],[32,29,82],[98,55,144],[205,95,108],[252,203,108],[255,249,218]])
    points=np.linspace(0,1,len(stops))
    return np.ascontiguousarray(np.stack([np.interp(v,points,stops[:,c]) for c in range(3)],axis=2).astype(np.uint8))
