import os, sys, shutil, subprocess, threading, time
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QImage, QPixmap, QKeyEvent
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QLabel, QPushButton, QComboBox, QHBoxLayout, QVBoxLayout, QSpinBox, QMessageBox, QFrame

PORT = "27183"
PACKAGE = "com.example.usbmirlite"

def tool(name):
    base = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
    for p in [os.path.join(base, name), os.path.join(base, "tools", name)]:
        if os.path.isfile(p): return p
    return shutil.which(name)

def run(args, timeout=6):
    try:
        p = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return p.returncode, p.stdout.decode("utf-8", "replace").strip(), p.stderr.decode("utf-8", "replace").strip()
    except Exception as e: return -1, "", str(e)

class Stream(QThread):
    frame = Signal(QImage)
    status = Signal(str)
    error = Signal(str)
    done = Signal()
    def __init__(self, adb, ffmpeg, serial, fps, bitrate, w, h):
        super().__init__(); self.adb=adb; self.ffmpeg=ffmpeg; self.serial=serial
        self.fps=fps; self.bitrate=bitrate; self.w=w; self.h=h; self.stop_flag=threading.Event()
        self.procs=[]
    def stop(self):
        self.stop_flag.set()
        for p in self.procs:
            try: p.terminate()
            except: pass
    def run(self):
        try:
            self.status.emit("Membuka koneksi USB…")
            rc, out, err = run([self.adb, "-s", self.serial, "forward", f"tcp:{PORT}", f"tcp:{PORT}"])
            if rc: self.error.emit("ADB forward gagal: "+(err or out)); return
            # Launch Android helper; user must approve screen capture on the phone.
            run([self.adb, "-s", self.serial, "shell", "am", "start", "-n", PACKAGE+"/.MainActivity"])
            self.status.emit("Setujui izin berbagi layar di HP…")
            time.sleep(1.0)
            vf = f"scale={self.w}:{self.h}:force_original_aspect_ratio=decrease,pad={self.w}:{self.h}:(ow-iw)/2:(oh-ih)/2,fps={self.fps}" if self.w else f"fps={self.fps}"
            cmd=[self.ffmpeg,"-hide_banner","-loglevel","error","-fflags","nobuffer","-flags","low_delay",
                 "-f","h264","-i",f"tcp://127.0.0.1:{PORT}?tcp_nodelay=1","-an","-vf",vf,
                 "-q:v","5","-f","image2pipe","-vcodec","mjpeg","pipe:1"]
            p=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=0,
                               creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0)); self.procs.append(p)
            buf=bytearray(); last=time.monotonic(); count=0
            while not self.stop_flag.is_set():
                chunk=p.stdout.read(16384)
                if not chunk: break
                buf.extend(chunk)
                while True:
                    a=buf.find(b"\xff\xd8")
                    if a<0:
                        if len(buf)>1: del buf[:-1]
                        break
                    if a: del buf[:a]
                    b=buf.find(b"\xff\xd9",2)
                    if b<0: break
                    img=QImage.fromData(bytes(buf[:b+2]),"JPG"); del buf[:b+2]
                    if not img.isNull():
                        self.frame.emit(img); count+=1
                        if time.monotonic()-last>1:
                            self.status.emit(f"Mirroring aktif • {count} frame")
                            last=time.monotonic()
            if not self.stop_flag.is_set():
                self.error.emit("Stream berhenti. Pastikan APK UsbMirror Helper terbuka dan izin berbagi layar sudah disetujui.")
        except Exception as e:
            if not self.stop_flag.is_set(): self.error.emit(str(e))
        finally:
            for p in self.procs:
                try: p.kill()
                except: pass
            run([self.adb,"-s",self.serial,"forward","--remove",f"tcp:{PORT}"])
            self.done.emit()

class Preview(QLabel):
    tap=Signal(int,int); swipe=Signal(int,int,int,int,int); text=Signal(str); key=Signal(int)
    def __init__(self):
        super().__init__("Mulai mirroring, lalu setujui izin berbagi layar di HP.")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter); self.setMinimumSize(360,480)
        self.setFrameShape(QFrame.Shape.StyledPanel); self.setStyleSheet("background:#101318;color:#9ca8b9;border:1px solid #303744")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus); self.img=None; self.press=None; self.press_t=0
    def set_frame(self,img): self.img=img; self.render_img()
    def resizeEvent(self,e): super().resizeEvent(e); self.render_img()
    def render_img(self):
        if self.img: self.setPixmap(QPixmap.fromImage(self.img).scaled(self.size(),Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
    def map_pos(self,pos):
        if not self.img:return None
        iw,ih=self.img.width(),self.img.height(); s=min(self.width()/iw,self.height()/ih)
        rw,rh=iw*s,ih*s; ox,oy=(self.width()-rw)/2,(self.height()-rh)/2
        x,y=pos.x()-ox,pos.y()-oy
        if x<0 or y<0 or x>=rw or y>=rh:return None
        return int(x/s),int(y/s)
    def mousePressEvent(self,e):
        if e.button()==Qt.MouseButton.LeftButton: self.press=e.position().toPoint(); self.press_t=time.monotonic(); self.setFocus()
    def mouseReleaseEvent(self,e):
        if self.press is not None and e.button()==Qt.MouseButton.LeftButton:
            a,b=self.map_pos(self.press),self.map_pos(e.position().toPoint())
            if a and b:
                if abs(a[0]-b[0])+abs(a[1]-b[1])>12:self.swipe.emit(*a,*b,max(80,min(900,int((time.monotonic()-self.press_t)*1000))))
                else:self.tap.emit(*b)
            self.press=None
    def keyPressEvent(self,e):
        m={Qt.Key.Key_Backspace:67,Qt.Key.Key_Return:66,Qt.Key.Key_Enter:66,Qt.Key.Key_Escape:4,Qt.Key.Key_Home:3,Qt.Key.Key_Tab:61,Qt.Key.Key_Space:62,Qt.Key.Key_Up:19,Qt.Key.Key_Down:20,Qt.Key.Key_Left:21,Qt.Key.Key_Right:22}
        if e.key() in m:self.key.emit(m[e.key()]);return
        if e.text() and e.text().isprintable() and not(e.modifiers()&(Qt.KeyboardModifier.ControlModifier|Qt.KeyboardModifier.AltModifier|Qt.KeyboardModifier.MetaModifier)):
            self.text.emit(e.text());return
        super().keyPressEvent(e)

class Window(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle("UsbMirror v2 — Android USB Mirroring"); self.resize(1100,780)
        self.adb=tool("adb.exe") or tool("adb"); self.ff=tool("ffmpeg.exe") or tool("ffmpeg"); self.worker=None
        root=QWidget(); self.setCentralWidget(root); v=QVBoxLayout(root)
        head=QHBoxLayout(); title=QLabel("UsbMirror v2"); title.setStyleSheet("font-size:24px;font-weight:700")
        self.status=QLabel("Siap"); head.addWidget(title); head.addStretch(); head.addWidget(self.status); v.addLayout(head)
        bar=QHBoxLayout(); self.devices=QComboBox(); self.refresh=QPushButton("Deteksi perangkat")
        self.res=QComboBox(); self.res.addItem("Native",0); self.res.addItem("1280 × 720",720); self.res.addItem("1920 × 1080",1080)
        self.fps=QComboBox(); self.fps.addItems(["30","45","60"]); self.fps.setCurrentText("60")
        self.bitrate=QSpinBox(); self.bitrate.setRange(2,20); self.bitrate.setValue(8); self.bitrate.setSuffix(" Mbps")
        self.start=QPushButton("▶ Mulai"); self.stop=QPushButton("■ Berhenti"); self.stop.setEnabled(False)
        for w in [QLabel("Perangkat"),self.devices,self.refresh,QLabel("Resolusi"),self.res,QLabel("FPS"),self.fps,QLabel("Bitrate"),self.bitrate,self.start,self.stop]:bar.addWidget(w)
        v.addLayout(bar); self.preview=Preview(); v.addWidget(self.preview,1)
        note=QLabel("Klik = tap • Drag = swipe • Fokus preview lalu ketik • Esc = Back • Home = Home"); v.addWidget(note)
        self.setStyleSheet("QMainWindow,QWidget{background:#171b22;color:#e5eaf2;font-size:12px} QPushButton,QComboBox,QSpinBox{background:#252c37;color:#e5eaf2;border:1px solid #3a4555;border-radius:6px;padding:7px}")
        self.refresh.clicked.connect(self.scan); self.start.clicked.connect(self.begin); self.stop.clicked.connect(self.end)
        self.preview.tap.connect(lambda x,y:self.input(["tap",x,y])); self.preview.swipe.connect(lambda x,y,a,b,t:self.input(["swipe",x,y,a,b,t]))
        self.preview.key.connect(lambda k:self.input(["keyevent",k])); self.preview.text.connect(self.send_text)
        self.scan()
    def scan(self):
        if not self.adb: QMessageBox.warning(self,"ADB tidak ditemukan","Letakkan adb.exe dan DLL-nya di tools.");return
        rc,out,err=run([self.adb,"devices"])
        self.devices.clear()
        for line in out.splitlines()[1:]:
            p=line.split()
            if len(p)>1 and p[1]=="device":self.devices.addItem(p[0])
        self.status.setText(f"{self.devices.count()} perangkat terdeteksi")
    def begin(self):
        if not self.adb or not self.ff: QMessageBox.warning(self,"Tools kurang","Butuh adb.exe + DLL dan ffmpeg.exe di tools.");return
        serial=self.devices.currentText()
        if not serial: self.scan();return
        # Verify helper installed
        rc,out,err=run([self.adb,"-s",serial,"shell","pm","path",PACKAGE])
        if rc or "package:" not in out:
            QMessageBox.warning(self,"APK helper belum terpasang","Build dan pasang APK dari folder android terlebih dahulu. Lihat README.md.");return
        size=self.res.currentData(); w=0 if size==0 else (1280 if size==720 else 1920); h=0 if not w else (720 if size==720 else 1080)
        self.worker=Stream(self.adb,self.ff,serial,int(self.fps.currentText()),self.bitrate.value(),w,h)
        self.worker.frame.connect(self.preview.set_frame); self.worker.status.connect(self.status.setText)
        self.worker.error.connect(lambda x:self.status.setText(x)); self.worker.done.connect(self.finish)
        self.worker.start(); self.start.setEnabled(False); self.stop.setEnabled(True); self.refresh.setEnabled(False)
    def end(self):
        if self.worker:self.worker.stop();self.worker.wait(2000)
        self.finish()
    def finish(self): self.start.setEnabled(True);self.stop.setEnabled(False);self.refresh.setEnabled(True);self.status.setText("Berhenti")
    def input(self,args):
        s=self.devices.currentText()
        if s and self.adb: threading.Thread(target=run,args=([self.adb,"-s",s,"shell","input"]+[str(a) for a in args],3),daemon=True).start()
    def send_text(self,t): self.input(["text",t.replace("%",r"\%").replace(" ","%s")])
    def closeEvent(self,e):
        if self.worker and self.worker.isRunning():self.worker.stop();self.worker.wait(1500)
        e.accept()

app=QApplication(sys.argv); win=Window(); win.show(); sys.exit(app.exec())
