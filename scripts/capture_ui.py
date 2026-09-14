"""Capture the real Qt application with synthetic multi-track content."""
import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
import sys
from pathlib import Path
import numpy as np
from PySide6.QtWidgets import QApplication

# Make the capture helper reproducible from an unpacked source tree.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from infinity_audio.app import MainWindow


def main():
    output=Path(sys.argv[1] if len(sys.argv)>1 else "evidence")
    output.mkdir(parents=True,exist_ok=True)
    app=QApplication([]);app.setStyle("Fusion")
    w=MainWindow(output/"ui-session",recover=False)
    sr=48000;t=np.arange(sr*11)/sr
    rng=np.random.default_rng(44)
    syllable=np.sin(np.pi*np.clip((t%1.2-.15)/.85,0,1))**2
    voice=syllable*(.29*np.sin(2*np.pi*(176*t+1.5*np.sin(t*3)))+.09*np.sin(2*np.pi*352*t))
    beat=np.exp(-((t%.5)/.08))*np.sin(2*np.pi*70*t)*.32
    guitar=.1*np.sin(2*np.pi*220*t)*np.exp(-((t%.5)/.22))+.06*np.sin(2*np.pi*330*t)
    ambience=rng.normal(0,.008,len(t))
    for name,x in [("Vocal chính · Take 02",voice),("Guitar acoustic",guitar),("Nhịp trống",beat),("Không gian phòng",ambience)]:
        w.session.add_track(x[:,None].astype(np.float32),name)
    first=w.session.state["tracks"][0];cid=first["clips"][0]["id"]
    w.session.set_track(first["id"],effects=[{"kind":"denoise","params":{"amount":25}},{"kind":"eq","params":{"mid_db":1.5}},{"kind":"compressor","params":{}}])
    w.session.commit("Cấu trúc bài",lambda s:s.update(name="Bản thu acoustic · phiên bản 02",markers=[{"time":0.,"name":"Intro"},{"time":3.5,"name":"Verse"},{"time":8.,"name":"Chorus"}]))
    w.refresh();w.select_clip(cid);w.timeline.region=(3.8,6.2);w.timeline.cursor=4.28;w.update_clock(4.28);w.region_changed(3.8,6.2)
    w.resize(1580,1000);w.timeline.set_zoom(60);w.show();app.processEvents()
    for light,name in [(False,"Infinity-audio-dark.png"),(True,"Infinity-audio-light.png")]:
        w.set_theme(light);app.processEvents();w.grab().save(str(output/name))
    w.session.save(output/"Demo-acoustic.infinity")
    w.confirm_discard=lambda:True;w.close()


if __name__=="__main__":main()
