"""Create a vector-drawn brand glyph through Qt, not a generated photo."""
import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage,QPainter,QPainterPath,QPen,QColor
from PySide6.QtCore import Qt,QRectF
from PIL import Image

app=QApplication.instance() or QApplication([])
root=Path(__file__).resolve().parents[1]
image=QImage(256,256,QImage.Format.Format_ARGB32);image.fill(QColor("#121622"))
p=QPainter(image);p.setRenderHint(QPainter.RenderHint.Antialiasing)
p.setBrush(QColor("#8270eb"));p.setPen(Qt.PenStyle.NoPen);p.drawRoundedRect(QRectF(10,10,236,236),54,54)
path=QPainterPath();path.moveTo(128,128);path.cubicTo(70,25,10,120,62,165);path.cubicTo(97,195,133,119,155,96);path.cubicTo(208,37,259,145,199,167);path.cubicTo(172,177,153,155,128,128)
p.setPen(QPen(QColor("#ffffff"),16,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap,Qt.PenJoinStyle.RoundJoin));p.setBrush(Qt.BrushStyle.NoBrush);p.drawPath(path);p.end()
target=root/"assets"/"infinity.png";image.save(str(target))
Image.open(target).save(root/"assets"/"infinity.ico",sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
